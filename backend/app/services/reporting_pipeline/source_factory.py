"""受控源工厂（第一批批1-2a）：投影 query builder + ConnectionProvider。

把 PythonReaderAdapter 需要的两类注入落到真实实现：
- query_builder：按冻结投影生成显式列 SELECT + 左闭右开窗口谓词 +
  稳定键 keyset 续页谓词 + 方言限量（Oracle 旧版用 ROWNUM，禁
  FETCH FIRST；PG 用 LIMIT）；
- ConnectionProvider：只经注入的连接工厂取得驱动连接（Oracle 生产
  =容器受控连接器/凭据文件；隔离验收=PG 测试 URL），打开即
  SET TRANSACTION READ ONLY，不新建任何直连写通道。

窗口参数不经字符串/UTC：tz-aware 业务时间按院区时区转 naive 墙钟
再绑定（Oracle DATE 无时区语义；PG 隔离源表同为院区墙钟）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from app.services.reporting_pipeline.adapters.python_reader import (
    ControlledConnectorRowSource,
    RowSource,
)
from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.planner import KeysetCursor, TimeWindow
from app.services.reporting_pipeline.runtime_config import TableRuntimeSpec

BUSINESS_TZ = ZoneInfo("Asia/Shanghai")


class SourceFactoryError(ContractViolation):
    """源工厂装配失败：缺凭据/缺绑定/方言不支持。"""


def _wall_clock(moment: datetime) -> datetime:
    """tz-aware 业务时间 → 院区时区 naive 墙钟（不经字符串/UTC）。"""
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(BUSINESS_TZ).replace(tzinfo=None)


class OracleProjectionQueryBuilder:
    """Oracle 11g 兼容投影查询：ROWNUM 限量 + 序内 keyset。

    结构：
      SELECT <投影列> FROM (
        SELECT <投影列> FROM <对象>
        WHERE <锚点> >= :b1 AND <锚点> < :b2 [AND (keyset 谓词)]
        ORDER BY <稳定键>
      ) WHERE ROWNUM <= :lim
    旧版 Oracle 不支持 FETCH FIRST；外层 ROWNUM 保证限量。
    """

    def __init__(self, spec: TableRuntimeSpec) -> None:
        self._object = spec.source_object
        self._columns = [f.source_expression for f in spec.projection]
        self._anchor = spec.anchor_column
        if not self._anchor:
            raise SourceFactoryError(
                f"[{spec.canonical_table}] 冻结配置缺业务锚点列，无法构建窗口查询"
            )
        self._keys = list(spec.stable_key)
        if not self._keys:
            raise SourceFactoryError(f"[{spec.canonical_table}] 稳定键为空")

    def __call__(
        self, window: TimeWindow, keyset: KeysetCursor | None, limit_rows: int
    ) -> tuple[str, list]:
        column_list = ", ".join(self._columns)
        # oracledb 序列绑定要求严格位置占位符 :1 :2 ...（命名占位符须配 dict）
        params: list = [_wall_clock(window.start), _wall_clock(window.end_exclusive)]
        sql = (
            f"SELECT {column_list} FROM ("
            f"SELECT {column_list} FROM {self._object} "
            f"WHERE {self._anchor} >= :1 AND {self._anchor} < :2"
        )
        if keyset is not None:
            sql += " AND (" + self._keyset_predicate(keyset, params) + ")"
        sql += " ORDER BY " + ", ".join(self._keys) + ")"
        sql += f" WHERE ROWNUM <= :{len(params) + 1}"
        params.append(int(limit_rows))
        return sql, params

    def _keyset_predicate(self, keyset: KeysetCursor, params: list) -> str:
        if list(keyset.order_columns) != self._keys:
            raise SourceFactoryError(
                "keyset 排序列与冻结稳定键不一致（禁止未核键续页）"
            )
        columns = self._keys
        values = list(keyset.last_values)
        # 严格字典序推进：(k1,c1) OR (k1=c1 AND k2>c2) OR ...
        parts: list[str] = []
        for depth in range(len(columns)):
            binds: list[str] = []
            for value in values[:depth]:
                binds.append(f":{len(params) + 1}")
                params.append(value)
            equality = " AND ".join(
                f"{columns[i]} = {binds[i]}" for i in range(depth)
            )
            strict_bind = f":{len(params) + 1}"
            params.append(values[depth])
            strict = f"{columns[depth]} > {strict_bind}"
            parts.append(f"({strict})" if not equality else f"({equality} AND {strict})")
        return " OR ".join(parts)


class PgProjectionQueryBuilder:
    """PostgreSQL 投影查询：LIMIT 限量 + 序内 keyset（隔离验收/PG 源）。"""

    def __init__(self, spec: TableRuntimeSpec) -> None:
        self._object = spec.source_object
        self._columns = [f.source_expression for f in spec.projection]
        self._anchor = spec.anchor_column
        if not self._anchor:
            raise SourceFactoryError(
                f"[{spec.canonical_table}] 冻结配置缺业务锚点列，无法构建窗口查询"
            )
        self._keys = list(spec.stable_key)
        if not self._keys:
            raise SourceFactoryError(f"[{spec.canonical_table}] 稳定键为空")

    def __call__(
        self, window: TimeWindow, keyset: KeysetCursor | None, limit_rows: int
    ) -> tuple[str, list]:
        column_list = ", ".join(f'"{c}"' for c in self._columns)
        params: list = [_wall_clock(window.start), _wall_clock(window.end_exclusive)]
        sql = (
            f"SELECT {column_list} FROM {self._object} "
            f'WHERE "{self._anchor}" >= %s AND "{self._anchor}" < %s'
        )
        if keyset is not None:
            if list(keyset.order_columns) != self._keys:
                raise SourceFactoryError(
                    "keyset 排序列与冻结稳定键不一致（禁止未核键续页）"
                )
            columns = self._keys
            values = list(keyset.last_values)
            parts: list[str] = []
            for depth in range(len(columns)):
                equality = " AND ".join(
                    f'"{columns[i]}" = %s' for i in range(depth)
                )
                params.extend(values[:depth])
                strict = f'"{columns[depth]}" > %s'
                params.append(values[depth])
                parts.append(f"({strict})" if not equality else f"({equality} AND {strict})")
            sql += " AND (" + " OR ".join(parts) + ")"
        sql += ' ORDER BY ' + ", ".join(f'"{k}"' for k in self._keys) + " LIMIT %s"
        params.append(int(limit_rows))
        return sql, params


QUERY_BUILDER_BY_DIALECT: Mapping[str, Callable[[TableRuntimeSpec], Callable]] = {
    "oracle": OracleProjectionQueryBuilder,
    "pg": PgProjectionQueryBuilder,
}


# -- ConnectionProvider 实现 ------------------------------------------------


class DbapiCursorAdapter:
    """ManagedCursor 适配：驱动游标 → execute(sql, params)/fetchmany/close。"""

    def __init__(self, cursor) -> None:
        self._cursor = cursor

    def execute(self, sql: str, params: Sequence) -> None:
        # Oracle 位置绑定用序列；psycopg2 用 %s 序列；两者都接受序列
        self._cursor.execute(sql, params)

    def fetchmany(self, size: int) -> list[tuple]:
        return self._cursor.fetchmany(size)

    def close(self) -> None:
        self._cursor.close()


class OracleConnectionProvider:
    """Oracle 源连接提供者：连接工厂注入（凭据在容器侧解析，不进本模块）。

    打开连接即 SET TRANSACTION READ ONLY；call_timeout 交给连接工厂
    配置。本类不读凭据文件、不落明文、不新建直连写通道。
    """

    def __init__(self, connection_factory: Callable[[], object]) -> None:
        self._connection_factory = connection_factory

    def cursor(self) -> DbapiCursorAdapter:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("SET TRANSACTION READ ONLY")
        except Exception:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 - 清理尽力而为
                pass
            raise
        return DbapiCursorAdapter(cursor)


class PgConnectionProvider:
    """PG 源连接提供者（隔离验收/PG 源）：连接工厂注入，只读会话。"""

    def __init__(self, connection_factory: Callable[[], object]) -> None:
        self._connection_factory = connection_factory

    def cursor(self) -> DbapiCursorAdapter:
        conn = self._connection_factory()
        try:
            conn.set_session(readonly=True, autocommit=False)
            cursor = conn.cursor()
        except Exception:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
            raise
        return DbapiCursorAdapter(cursor)


PROVIDER_BY_DIALECT: Mapping[str, type] = {
    "oracle": OracleConnectionProvider,
    "pg": PgConnectionProvider,
}


def resolve_oracle_credentials(credential_ref: str) -> tuple[str, str]:
    """容器侧凭据文件解析（首行 user:password）；文件缺失即拒绝。

    生产仅在 8.83 容器内可用；本机/隔离环境无该文件时如实拒绝，
    不退回环境变量明文或硬编码。凭据不写日志、不返回给调用方以外
    的任何输出。
    """
    from pathlib import Path

    marker = "container-credentials:"
    if not credential_ref.startswith(marker):
        raise SourceFactoryError(
            f"Oracle 凭据引用格式非法（须 {marker}<源名>）: {credential_ref!r}"
        )
    name = credential_ref[len(marker):]
    path = Path("/etc/data-asset/credentials") / name
    if not path.exists():
        raise SourceFactoryError(
            f"容器凭据文件不存在: {name}（本机无 /etc/data-asset/credentials；"
            "Oracle 生产源只能在 8.83 容器内装配）"
        )
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    user, _, password = first_line.partition(":")
    if not user or not password:
        raise SourceFactoryError(f"凭据文件首行格式非法: {name}")
    return user, password


def _ensure_oracle_thick() -> None:
    """Oracle 11g 须 thick 模式；lib 目录取容器约定路径（幂等初始化）。"""
    import os

    import oracledb

    lib_dir = (
        os.environ.get("APP_ORACLE_CLIENT_LIB_DIR")
        or ("/opt/oracle" if os.path.isdir("/opt/oracle") else "/opt/oracle/instantclient_21")
    )
    try:
        oracledb.init_oracle_client(lib_dir=lib_dir)
    except Exception:  # noqa: BLE001 - 已初始化（重复 init）继续连接
        pass


def build_oracle_connection_factory(
    *, dsn: str, credential_ref: str, timeout_ms: int = 600_000
) -> Callable[[], object]:
    """构造 oracledb 连接工厂（thick 模式；凭据容器侧解析）。"""
    _ensure_oracle_thick()

    def factory() -> object:
        import oracledb

        user, password = resolve_oracle_credentials(credential_ref)
        host_port, _, service = dsn.partition("/")
        host, _, port = host_port.partition(":")
        params = oracledb.ConnectParams(
            host=host,
            port=int(port or 1521),
            service_name=service,
            tcp_connect_timeout=30,
            retry_count=0,
        )
        conn = oracledb.connect(user=user, password=password, params=params)
        conn.call_timeout = timeout_ms
        return conn

    return factory


def build_pg_connection_factory(*, url: str) -> Callable[[], object]:
    """构造 psycopg2 连接工厂（隔离验收/PG 源；URL 来自受控环境变量）。"""

    def factory() -> object:
        import psycopg2

        # SQLAlchemy 方言后缀（postgresql+psycopg://）对驱动不可用
        driver_url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
        driver_url = driver_url.replace("postgresql+psycopg://", "postgresql://", 1)
        return psycopg2.connect(driver_url)

    return factory


def build_connection_factory(
    *, dialect: str, dsn: str | None = None, url_env: str | None = None,
    credential_ref: str | None = None,
) -> Callable[[], object]:
    if dialect == "oracle":
        if not dsn or not credential_ref:
            raise SourceFactoryError("Oracle 源需 dsn + credential_ref")
        return build_oracle_connection_factory(
            dsn=dsn, credential_ref=credential_ref
        )
    if dialect == "pg":
        import os

        url = url_env and os.environ.get(url_env)
        if not url:
            raise SourceFactoryError(
                f"PG 源需环境变量 {url_env}（未设置即拒绝，不留默认值）"
            )
        return build_pg_connection_factory(url=url)
    raise SourceFactoryError(f"不支持的源方言: {dialect}")


# -- RowSource 工厂 ----------------------------------------------------------


def _normalize_numeric_types(row: tuple) -> tuple:
    """驱动数值规整：Oracle 计算列可能返回 float；金额类精确数值必须
    Decimal（质量门拒绝 float 进 hash，str(float) 最短 repr 无损往返）。"""
    from decimal import Decimal

    return tuple(
        Decimal(str(value)) if type(value) is float else value
        for value in row
    )


def build_row_source(
    spec: TableRuntimeSpec,
    *,
    connection_factory: Callable[[], object],
    fetch_timeout_seconds: float = 300.0,
) -> RowSource:
    builder_cls = QUERY_BUILDER_BY_DIALECT.get(spec.dialect)
    provider_cls = PROVIDER_BY_DIALECT.get(spec.dialect)
    if builder_cls is None or provider_cls is None:
        raise SourceFactoryError(
            f"[{spec.canonical_table}] 源方言不支持: {spec.dialect}"
        )
    return ControlledConnectorRowSource(
        physical_source=f"{spec.source_group}@{spec.source_object}",
        provider=provider_cls(connection_factory),
        query_builder=builder_cls(spec),
        row_transform=_normalize_numeric_types,
        fetch_timeout_seconds=fetch_timeout_seconds,
    )


def build_row_source_factory(
    runtime_tables: Mapping[str, TableRuntimeSpec],
    source_bindings: Mapping[str, Mapping],
) -> Callable[[str], RowSource]:
    """按物理源组构建 RowSource 工厂（capture 装配用）。

    source_bindings: {source_group: {dialect, dsn?, url_env?, credential_ref?}}
    绑定缺该组即拒绝（不猜源）。
    """
    built: dict[str, RowSource] = {}

    def factory(physical_source_group: str) -> RowSource:
        if physical_source_group in built:
            return built[physical_source_group]
        binding = source_bindings.get(physical_source_group)
        if not binding:
            raise SourceFactoryError(
                f"源绑定缺物理源组 {physical_source_group}（不猜测连接）"
            )
        specs = [
            spec for spec in runtime_tables.values()
            if spec.source_group == physical_source_group
        ]
        if not specs:
            raise SourceFactoryError(
                f"冻结配置无任何表使用源组 {physical_source_group}"
            )
        connection_factory = build_connection_factory(
            dialect=binding.get("dialect", ""),
            dsn=binding.get("dsn"),
            url_env=binding.get("url_env"),
            credential_ref=binding.get("credential_ref"),
        )
        # 同源组共用连接工厂；按表各建 RowSource（投影不同）
        # 工厂签名按 physical（源组）调用，取该组首个表构建基准；各表
        # 投影差异由表级工厂（build_table_row_source）处理。
        spec = specs[0]
        source = build_row_source(spec, connection_factory=connection_factory)
        built[physical_source_group] = source
        return source

    return factory


def build_table_row_source(
    spec: TableRuntimeSpec,
    source_bindings: Mapping[str, Mapping],
    *,
    fetch_timeout_seconds: float = 300.0,
) -> RowSource:
    """表级 RowSource（生产 capture 按 canonical_table 解析投影后使用）。"""
    binding = source_bindings.get(spec.source_group)
    if not binding:
        raise SourceFactoryError(
            f"[{spec.canonical_table}] 源绑定缺物理源组 {spec.source_group}"
        )
    connection_factory = build_connection_factory(
        dialect=binding.get("dialect", ""),
        dsn=binding.get("dsn"),
        url_env=binding.get("url_env"),
        credential_ref=binding.get("credential_ref"),
    )
    return build_row_source(
        spec, connection_factory=connection_factory,
        fetch_timeout_seconds=fetch_timeout_seconds,
    )


class DualSourceRouter:
    """双源路由（LIS 类）：按键位段把行分配到主/次源（A/B 段账本）。

    路由表来自已核双源路由候选：每段声明 (key_range, source_group)；
    段外键一律落主源并标记 ROUTE_FALLBACK_CANDIDATE 进隔离账，
    不静默归并。本类只做键→源组的判定；读取仍走各源组 RowSource。
    """

    def __init__(
        self,
        primary_group: str,
        segments: Sequence[Mapping],
    ) -> None:
        self.primary_group = primary_group
        self._segments = list(segments)

    def route(self, key: str) -> tuple[str, bool]:
        """返回 (source_group, in_segment)；段外键回主源并带越段标记。"""
        for segment in self._segments:
            low = segment.get("key_from")
            high = segment.get("key_to")  # 含端点语义由候选文档声明
            inclusive_to = bool(segment.get("key_to_inclusive", True))
            if low is not None and key < str(low):
                continue
            if high is not None:
                if inclusive_to and key > str(high):
                    continue
                if not inclusive_to and key >= str(high):
                    continue
            return str(segment.get("source_group")), True
        return self.primary_group, False
