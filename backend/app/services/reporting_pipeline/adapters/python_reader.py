"""读取适配器：Python 路线（源抽象注入，无 DB 依赖；真实源绑定走受控连接器）。

对应计划 §2/§8.1 与失败规则：
- RowSource 是唯一源接口：生产实现绑定仓库受控连接器；模拟实现注入故障。
- 行/字节上限触发递归二分拆窗：拆分树持久化（由 Repository 承载），到最小
  粒度转已核稳定 keyset，否则局部待处理；不能无限递归或截断成功。
- 源级熔断按物理源（不是表名）：连续断连进入 OPEN，有界退避+抖动，仅单探针
  半开；其他源不受影响，禁止逐表重连风暴。
- ORA-12541/12547/DPY-4011 归为瞬时断连（监听器），不与 SQL/视图错误混类。
- 取消令牌在页间检查，协作式取消。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Protocol, Sequence

from app.services.reporting_pipeline.contracts import (
    EndReason,
)
from app.services.reporting_pipeline.planner import (
    KeysetCursor,
    SplitNode,
    TimeWindow,
)

# 监听器断连特征（Oracle/驱动错误码白名单，不含 SQL 文本）
TRANSIENT_DISCONNECT_MARKERS = (
    "ORA-12541",  # no listener
    "ORA-12547",  # lost contact
    "DPY-4011",
)
SQL_VIEW_ERROR_MARKERS = ("ORA-00942", "ORA-01722", "invalid identifier", "invalid state")


class OperationCancelled(Exception):
    """协作式取消。"""


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def check(self) -> None:
        if self._cancelled:
            raise OperationCancelled("读取已被取消")


class SourceError(Exception):
    """源读取错误：error_class 驱动隔离/重试/熔断决策，不含患者数据。"""

    def __init__(self, error_class: str, safe_code: str, message: str) -> None:
        super().__init__(f"[{error_class}] {safe_code}: {message}")
        self.error_class = error_class
        self.safe_code = safe_code


def classify_source_error(raw_message: str) -> str:
    """安全分类：只看白名单特征，不把原始 SQL/堆栈带回业务层。"""
    text = raw_message or ""
    if any(marker in text for marker in TRANSIENT_DISCONNECT_MARKERS):
        return "TRANSIENT_DISCONNECT"
    if any(marker in text for marker in SQL_VIEW_ERROR_MARKERS):
        return "READ_SQL_OR_VIEW_ERROR"
    if "identity" in text.lower() or "mismatch" in text.lower():
        return "SOURCE_IDENTITY_MISMATCH"
    return "SOURCE_UNKNOWN_ERROR"


class RowSource(Protocol):
    """源接口：物理源身份 + 窗口/keyset 取页。"""

    physical_source: str

    def fetch_page(
        self,
        window: TimeWindow,
        *,
        limit_rows: int,
        keyset: KeysetCursor | None = None,
    ) -> "ReadPage":
        ...


class ConnectionProvider(Protocol):
    """受控连接提供者（R03）：由仓库受控连接器实现（如 db_connectors 的
    OracleConnector 封装），只读身份；实现负责凭据与 thick 模式。"""

    def cursor(self) -> "ManagedCursor":
        ...


class ManagedCursor(Protocol):
    """受管游标：支持超时关闭底层连接（阻塞 fetch 的硬取消）。"""

    def execute(self, sql: str, params: Sequence) -> None: ...

    def fetchmany(self, size: int) -> list[tuple]: ...

    def close(self) -> None: ...


class FetchTimeoutReached(SourceError):
    """驱动级 fetch 超时：连接被关闭打断，attempt 不得发布。"""


class ControlledConnectorRowSource:
    """受控连接器行源（R03）：真实驱动绑定 + 页间取消 + 阻塞 fetch 硬取消。

    - 连接只经注入的 ConnectionProvider（平台受控连接器/只读身份），
      本类不新建直连、不持有明文凭据；
    - 驱动超时落实在"看门狗关闭连接"：页间协作取消只能中止下一页，
      不能中断正在阻塞的 fetch——超时时看门狗线程关闭底层连接强制打断，
      之后 attempt 按不完整处理，不伪造完整结束；
    - CLOB 等大对象必须在连接关闭前读完（本类逐行同步取值）；流式
      转存由装配方在 row_transform 中处理，关闭后不再触达 LOB 惰性读取。
    """

    def __init__(
        self,
        *,
        physical_source: str,
        provider: ConnectionProvider,
        query_builder: Callable[[TimeWindow, KeysetCursor | None, int], tuple[str, Sequence]],
        row_transform: Callable[[tuple], tuple] | None = None,
        page_size: int = 5000,
        # 069 会话 2026-11-05：必须大于 Oracle 源连接 call_timeout（600s），
        # 让 OCI 原生超时先在调用线程内干净触发（DPY-4024）；看门狗跨线程
        # cursor.close() 打断进行中的 OCI 调用会触发 thick 竞态 SIGSEGV
        # （DEAD_TF/MEDICAL_RECORD_INFO 崩溃取证，T-B07-3 同族）。
        fetch_timeout_seconds: float = 700.0,
        cancellation: CancellationToken | None = None,
    ) -> None:
        self.physical_source = physical_source
        self._provider = provider
        self._query_builder = query_builder
        self._row_transform = row_transform
        self._page_size = page_size
        self._fetch_timeout = fetch_timeout_seconds
        self._cancellation = cancellation or CancellationToken()

    def fetch_page(
        self,
        window: TimeWindow,
        *,
        limit_rows: int,
        keyset: KeysetCursor | None = None,
    ) -> ReadPage:
        import threading

        # query_builder's third argument is the SQL row limit (not fetchmany's
        # array size). Fetch one sentinel row beyond the returned limit so
        # has_more is meaningful even when SQL itself applies the limit. In
        # particular, _fetch_all requests budget + 1 rows to detect truncation;
        # passing the driver fetch batch size here could silently cap SQL at
        # page_size and make an oversized window look complete.
        sql, params = self._query_builder(window, keyset, limit_rows + 1)
        cursor = self._provider.cursor()
        watchdog_done = threading.Event()
        holder = {"cursor": cursor, "timed_out": False}

        def _watchdog() -> None:
            if not watchdog_done.wait(self._fetch_timeout):
                holder["timed_out"] = True
                # 阻塞 fetch 的硬取消：关闭游标/连接打断底层 socket 读
                try:
                    cursor.close()
                except Exception:  # noqa: BLE001 - 取消路径尽力而为
                    pass

        watchdog = threading.Thread(target=_watchdog, daemon=True)
        watchdog.start()
        rows: list[tuple] = []
        row_bytes = 0
        try:
            self._cancellation.check()
            cursor.execute(sql, params)
            while len(rows) < limit_rows:
                self._cancellation.check()
                batch = cursor.fetchmany(min(self._page_size, limit_rows - len(rows)))
                if not batch:
                    break
                for raw in batch:
                    row = self._row_transform(raw) if self._row_transform else raw
                    rows.append(row)
                    row_bytes += _approx_row_bytes(row)
            has_more = len(rows) >= limit_rows and bool(
                cursor.fetchmany(1)
            )
            last_key = rows[-1][:2] if rows else None
            return ReadPage(rows=rows, row_bytes=row_bytes, last_key=last_key, has_more=has_more)
        except OperationCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 - 分类后抛 SourceError
            if holder["timed_out"]:
                raise FetchTimeoutReached(
                    "FETCH_TIMEOUT",
                    "DRIVER_FETCH_TIMEOUT",
                    f"阻塞 fetch 超时（>{self._fetch_timeout}s），连接已关闭打断",
                ) from exc
            raise SourceError(
                classify_source_error(str(exc)),
                "READ_PAGE_FAILED",
                type(exc).__name__,
            ) from exc
        finally:
            watchdog_done.set()
            watchdog.join(timeout=1.0)
            try:
                cursor.close()
            except Exception:  # noqa: BLE001
                pass


def _approx_row_bytes(row: tuple) -> int:
    total = 0
    for value in row:
        if isinstance(value, str):
            total += len(value.encode("utf-8"))
        elif value is not None:
            total += 32
    return total


@dataclass
class ReadPage:
    rows: list[tuple]
    row_bytes: int
    last_key: tuple | None = None
    has_more: bool = False


@dataclass
class ReadBudget:
    max_rows_per_slice: int = 50_000
    max_bytes_per_slice: int = 256 * 1024 * 1024
    page_size: int = 5_000
    max_attempts: int = 3
    transient_backoff_seconds: float = 2.0
    max_split_depth: int = 20


@dataclass
class SliceResult:
    """单个窗的结果：完整则给行分类；不完整给拆分树。"""

    window: TimeWindow
    complete: bool
    rows: list[tuple] = field(default_factory=list)
    total_bytes: int = 0
    end_reason: EndReason | None = None
    split_root: SplitNode | None = None
    keyset_fallback_used: bool = False
    error_class: str | None = None


class SourceCircuitBreaker:
    """物理源熔断：连续瞬时断连触发 OPEN；半开仅单探针。"""

    def __init__(
        self,
        failure_threshold: int = 3,
        open_seconds: float = 60.0,
        jitter: float = 0.3,
        seed: int = 20261019,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self._rng = random.Random(seed)  # 确定性抖动（测试可复现）
        self._jitter = jitter
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, datetime] = {}
        self._half_open_probe: dict[str, bool] = {}
        self._now_fn: Callable[[], datetime] = lambda: datetime.now()

    def use_clock(self, now_fn: Callable[[], datetime]) -> None:
        self._now_fn = now_fn

    def allow(self, physical_source: str) -> bool:
        until = self._open_until.get(physical_source)
        if until is None:
            return True
        if self._now_fn() < until:
            return False
        # 半开：只放行一个探针
        if self._half_open_probe.get(physical_source):
            return False
        self._half_open_probe[physical_source] = True
        return True

    def record_success(self, physical_source: str) -> None:
        self._failures[physical_source] = 0
        self._open_until.pop(physical_source, None)
        self._half_open_probe.pop(physical_source, None)

    def record_failure(self, physical_source: str, error_class: str) -> float:
        """记失败并返回建议退避秒（含抖动）；达到阈值熔断。"""
        if error_class != "TRANSIENT_DISCONNECT":
            return 0.0
        count = self._failures.get(physical_source, 0) + 1
        self._failures[physical_source] = count
        self._half_open_probe.pop(physical_source, None)
        if count >= self.failure_threshold:
            jittered = self.open_seconds * (1 + self._rng.uniform(0, self._jitter))
            self._open_until[physical_source] = self._now_fn() + timedelta(
                seconds=jittered
            )
            return jittered
        backoff = self._backoff(count)
        return backoff

    def _backoff(self, attempt: int) -> float:
        base = 2.0 ** min(attempt, 6)
        return base * (1 + self._rng.uniform(0, self._jitter))

    def state(self, physical_source: str) -> str:
        if self._open_until.get(physical_source) and self._now_fn() < self._open_until[physical_source]:
            return "OPEN"
        if self._half_open_probe.get(physical_source):
            return "HALF_OPEN_PROBE"
        return "CLOSED"


class PythonReaderAdapter:
    """页式读取 + 上限触发递归拆分 + 熔断。产出 SliceResult，manifest 由上层组装。"""

    def __init__(
        self,
        source: RowSource,
        budget: ReadBudget | None = None,
        breaker: SourceCircuitBreaker | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.source = source
        self.budget = budget or ReadBudget()
        self.breaker = breaker or SourceCircuitBreaker()
        self._sleep = sleep_fn or (lambda seconds: None)

    def capture_window(
        self,
        window: TimeWindow,
        *,
        cancel: CancellationToken | None = None,
        keyset_columns: tuple[str, ...] | None = None,
        keyset_unique_verified: bool = False,
    ) -> SliceResult:
        cancel = cancel or CancellationToken()
        if not self.breaker.allow(self.source.physical_source):
            return SliceResult(
                window=window, complete=False,
                end_reason=EndReason.SOURCE_ERROR,
                error_class="SOURCE_CIRCUIT_OPEN",
            )
        try:
            rows, total_bytes = self._fetch_all(window, cancel)
        except SourceError as exc:
            backoff = self.breaker.record_failure(
                self.source.physical_source, exc.error_class
            )
            if exc.error_class == "TRANSIENT_DISCONNECT" and backoff:
                self._sleep(backoff)
            return SliceResult(
                window=window, complete=False,
                end_reason=EndReason.SOURCE_ERROR, error_class=exc.error_class,
            )
        except OperationCancelled:
            return SliceResult(
                window=window, complete=False, end_reason=EndReason.CANCELLED
            )
        self.breaker.record_success(self.source.physical_source)

        over_rows = len(rows) > self.budget.max_rows_per_slice
        over_bytes = total_bytes > self.budget.max_bytes_per_slice
        if not (over_rows or over_bytes):
            return SliceResult(
                window=window, complete=True, rows=rows, total_bytes=total_bytes,
                end_reason=EndReason.WINDOW_COMPLETE,
            )

        # 超预算：递归二分；完整叶之前不算捕获完整
        root = SplitNode(window=window)
        leaves_rows = self._split_collect(
            root, cancel,
            keyset_columns=keyset_columns,
            keyset_unique_verified=keyset_unique_verified,
        )
        if leaves_rows is None:
            return SliceResult(
                window=window, complete=False,
                end_reason=EndReason.SPLIT_REQUIRED,
                split_root=root,
                error_class="SPLIT_EXHAUSTED_PARKED",
            )
        all_rows = [row for leaf_rows in leaves_rows for row in leaf_rows]
        return SliceResult(
            window=window, complete=True, rows=all_rows,
            total_bytes=self._sum_bytes(leaves_rows),
            end_reason=EndReason.WINDOW_COMPLETE,
            split_root=root,
            keyset_fallback_used=any(
                n.used_keyset for n in self._walk(root)
            ),
        )

    # -- 内部 ---------------------------------------------------------------

    def _fetch_all(
        self, window: TimeWindow, cancel: CancellationToken
    ) -> tuple[list[tuple], int]:
        """完整性上限探针：单页取 limit=行上限+1。

        返回超限页（len > 上限）即视为未完整分片信号，由上层拆窗；无游标
        推进的重复拉页会造成重复行，禁止。keyset 分页在 _keyset_collect 中
        显式推进游标。
        """
        cancel.check()
        page = self.source.fetch_page(
            window, limit_rows=self.budget.max_rows_per_slice + 1
        )
        return page.rows, page.row_bytes

    def _split_collect(
        self,
        node: SplitNode,
        cancel: CancellationToken,
        *,
        keyset_columns: tuple[str, ...] | None,
        keyset_unique_verified: bool,
    ) -> list[list[tuple]] | None:
        """递归拆分；返回全部完整叶的行集，无法完整时返回 None（PARKED）。"""
        try:
            rows, total_bytes = self._fetch_all(node.window, cancel)
        except OperationCancelled:
            return None
        except SourceError:
            node.status = "PENDING"
            node.reason = "读取失败待重试"
            return None
        within = (
            len(rows) <= self.budget.max_rows_per_slice
            and total_bytes <= self.budget.max_bytes_per_slice
        )
        if within:
            node.status = "LEAF_COMPLETE"
            return [rows]
        if not node.window.can_split():
            # 最小粒度仍超限：转稳定 keyset（已核唯一）或待处理
            if keyset_columns and keyset_unique_verified:
                node.status = "KEYSET"
                node.reason = "最小粒度超限，转稳定 keyset 分页"
                return self._keyset_collect(node, cancel, keyset_columns)
            node.status = "PARKED"
            node.reason = "最小粒度超限且无已核稳定键，转待处理工单"
            return None
        node.split(max_depth=self.budget.max_split_depth)
        if node.status != "SPLIT":
            node.status = "PARKED"
            node.reason = node.reason or "拆分预算耗尽"
            return None
        collected: list[list[tuple]] = []
        for child in node.children:
            part = self._split_collect(
                child, cancel,
                keyset_columns=keyset_columns,
                keyset_unique_verified=keyset_unique_verified,
            )
            if part is None:
                return None
            collected.extend(part)
        return collected

    def _keyset_collect(
        self, node: SplitNode, cancel: CancellationToken, keyset_columns: tuple[str, ...]
    ) -> list[list[tuple]] | None:
        """稳定 keyset 分页：页大小内逐页取，直到 has_more=False。"""
        rows: list[tuple] = []
        last_values: tuple | None = None
        while True:
            cancel.check()
            cursor = (
                KeysetCursor(
                    order_columns=keyset_columns,
                    last_values=last_values,
                    unique_verified=True,
                )
                if last_values is not None else None
            )
            try:
                page = self.source.fetch_page(
                    node.window, limit_rows=self.budget.page_size, keyset=cursor
                )
            except (SourceError, OperationCancelled):
                node.status = "PENDING"
                node.reason = "keyset 分页中断待重试"
                return None
            rows.extend(page.rows)
            if not page.has_more:
                break
            if page.last_key is None:
                node.status = "PARKED"
                node.reason = "keyset 页未返回游标键，无法续页"
                return None
            last_values = page.last_key
        node.status = "LEAF_COMPLETE"
        node.used_keyset = True
        return [rows]

    @staticmethod
    def _walk(node: SplitNode) -> list[SplitNode]:
        out = [node]
        for child in node.children:
            out.extend(PythonReaderAdapter._walk(child))
        return out

    @staticmethod
    def _sum_bytes(leaves_rows: Sequence[list[tuple]]) -> int:
        # 模拟环境行字节由源给；此处近似为字符数（真实实现按驱动字节数）
        return sum(len(str(row)) for rows in leaves_rows for row in rows)
