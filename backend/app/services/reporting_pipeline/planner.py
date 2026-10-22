"""计划层：固定窗、keyset 游标语义、任务 DAG、LIS 路由解析、拆分树、月覆盖账。

对应计划 §4/§8.1：
- 业务归属日与变更捕获时间分开；捕获窗 [W-overlap, H)。
- keyset 复合键必须唯一（否则拒绝），游标比较是严格字典序 >，保证同秒同ID
  并列记录不被跳过（排序键含稳定键时唯一）。
- LIS 四表双源路由：业务时间落段决定源集合；2023Q4 重叠段保留双源并标记
  边界待核，不做静默去重。
- 递归二分拆窗有最小粒度与深度预算，到限转稳定 keyset 或局部待处理。
- 历史业务月覆盖账：业务月不等于运行月，欠账按月/来源显式。
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Mapping, Sequence

from app.services.reporting_pipeline.contracts import ContractViolation

# 拆窗最小粒度（秒）：低于该粒度不再对半拆，转 keyset 或待处理
MIN_SPLIT_SECONDS = 60


@dataclass(frozen=True)
class TimeWindow:
    """左闭右开固定窗。"""

    start: datetime
    end_exclusive: datetime

    def __post_init__(self) -> None:
        if self.start >= self.end_exclusive:
            raise ContractViolation(
                f"非法窗口: start={self.start} >= end={self.end_exclusive}"
            )

    def duration_seconds(self) -> float:
        return (self.end_exclusive - self.start).total_seconds()

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end_exclusive

    def overlaps(self, other: "TimeWindow") -> bool:
        return self.start < other.end_exclusive and other.start < self.end_exclusive

    def split_binary(self) -> tuple["TimeWindow", "TimeWindow"]:
        mid = self.start + (self.end_exclusive - self.start) / 2
        return TimeWindow(self.start, mid), TimeWindow(mid, self.end_exclusive)

    def can_split(self, min_seconds: int = MIN_SPLIT_SECONDS) -> bool:
        return self.duration_seconds() > min_seconds

    def fingerprint(self) -> str:
        return f"win:{self.start.isoformat()}/{self.end_exclusive.isoformat()}"


def plan_capture_window(
    business_day: date,
    *,
    visibility_cutoff: datetime,
    overlap: timedelta,
) -> TimeWindow:
    """D+1 批次捕获窗：[D日业务窗起点 - overlap, H)。

    H 为本次运行的源可见上界（由调用方按源新鲜度证据给出，不在此伪造）。
    """
    day_start = datetime(business_day.year, business_day.month, business_day.day)
    window = TimeWindow(day_start - overlap, visibility_cutoff)
    if window.start >= window.end_exclusive:
        raise ContractViolation(
            f"捕获窗为空: business_day={business_day} cutoff={visibility_cutoff}"
        )
    return window


# ---------------------------------------------------------------------------
# 院区固定业务日窗（R05：跨午夜重试不漂窗）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyRunAnchor:
    """一次日轮的冻结锚点：业务日、业务时区、冻结时刻 H。

    - 业务日 D = 冻结时刻在院区业务时区下的"昨天"（T+1 语义）。
    - 业务窗固定为院区时区下的 [D 00:00, D+1 00:00)，半开。
    - 同一轮的所有重试复用同一锚点：23:59 启动、00:01 重试都用当初
      冻结的 D 与 H，不因真实时钟跨午夜而漂到新的业务日。
    - H 只作捕获可见上界参考，不作为变更捕获依据（变更必须依赖已核
      业务/变更时间语义，禁止用动态 SYSTEM_TIME 当水位）。
    """

    business_day: date
    business_tz_name: str
    frozen_at: datetime
    visibility_cutoff: datetime

    def business_window(self) -> TimeWindow:
        start = datetime(
            self.business_day.year, self.business_day.month, self.business_day.day
        )
        return TimeWindow(start, start + timedelta(days=1))

    def fingerprint(self) -> str:
        return (
            f"anchor:{self.business_day.isoformat()}@{self.business_tz_name}"
            f"/{self.frozen_at.isoformat()}"
        )


def freeze_daily_anchor(
    now: datetime, *, business_tz_name: str = "Asia/Shanghai"
) -> DailyRunAnchor:
    """按冻结时刻计算本轮 T+1 锚点（业务日=院区时区昨天）。

    now 必须带时区信息。业务时区固定为院区确认值，不随源库时区漂移；
    跨源不同时区时，源侧时间换算到业务时区后再判窗。
    """
    if now.tzinfo is None:
        raise ContractViolation("冻结锚点需要带时区的当前时刻（naive 时钟不可用）")
    try:
        import zoneinfo

        tz = zoneinfo.ZoneInfo(business_tz_name)
    except Exception as exc:  # noqa: BLE001 - 未知时区名统一拒绝
        raise ContractViolation(f"未知业务时区: {business_tz_name} ({exc})") from exc
    local = now.astimezone(tz)
    business_day = (local - timedelta(days=1)).date()
    return DailyRunAnchor(
        business_day=business_day,
        business_tz_name=business_tz_name,
        frozen_at=now,
        visibility_cutoff=now,
    )


@dataclass(frozen=True)
class KeysetCursor:
    """复合键游标：order_columns 必须构成唯一键（verified），比较为严格字典序。"""

    order_columns: tuple[str, ...]
    last_values: tuple
    unique_verified: bool = False

    def __post_init__(self) -> None:
        if not self.order_columns:
            raise ContractViolation("keyset 游标需要排序列")
        if len(self.order_columns) != len(self.last_values):
            raise ContractViolation("游标值与排序列数不一致")
        if not self.unique_verified:
            raise ContractViolation(
                "keyset 排序列未核唯一：并列同键记录会被跳过，禁止使用"
            )

    def row_after(self, row_values: tuple) -> bool:
        """严格字典序 >。排序键唯一时，> 与分页完备等价（同秒同ID不跳行）。"""
        if len(row_values) != len(self.last_values):
            raise ContractViolation("行键列数与游标不一致")
        return tuple(row_values) > tuple(self.last_values)


@dataclass
class SplitNode:
    """持久拆分树节点：仅完整叶可装载；到最小粒度转 keyset 或待处理。"""

    window: TimeWindow
    status: str = "PENDING"  # PENDING/SPLIT/LEAF_COMPLETE/EXHAUSTED/KEYSET/PARKED
    children: list["SplitNode"] = field(default_factory=list)
    attempt: int = 0
    reason: str | None = None
    used_keyset: bool = False  # 叶经稳定 keyset 分页收全（最小粒度超限回退）

    def split(self, max_depth: int = 20, min_seconds: int = MIN_SPLIT_SECONDS) -> "SplitNode":
        if not self.window.can_split(min_seconds):
            self.status = "EXHAUSTED"
            self.reason = "已达最小拆分粒度"
            return self
        if max_depth <= 0:
            self.status = "EXHAUSTED"
            self.reason = "拆分深度预算耗尽"
            return self
        left, right = self.window.split_binary()
        self.status = "SPLIT"
        self.children = [
            SplitNode(window=left, attempt=self.attempt),
            SplitNode(window=right, attempt=self.attempt),
        ]
        return self

    def all_leaves_complete(self) -> bool:
        """所有叶完整之前不算捕获完整（验收要点）。"""
        if self.status == "LEAF_COMPLETE":
            return True
        if self.status == "SPLIT":
            return bool(self.children) and all(ch.all_leaves_complete() for ch in self.children)
        return False

    def incomplete_leaves(self) -> list["SplitNode"]:
        if self.status in ("LEAF_COMPLETE",):
            return []
        if self.status == "SPLIT":
            out: list[SplitNode] = []
            for ch in self.children:
                out.extend(ch.incomplete_leaves())
            return out
        return [self]


def split_tree_stats(root: SplitNode) -> dict[str, int]:
    leaves = _leaves(root)
    return {
        "leaves": len(leaves),
        "complete": sum(1 for n in leaves if n.status == "LEAF_COMPLETE"),
        "incomplete": sum(1 for n in leaves if n.status not in ("LEAF_COMPLETE",)),
        "exhausted": sum(1 for n in leaves if n.status == "EXHAUSTED"),
    }


def _leaves(node: SplitNode) -> list[SplitNode]:
    if node.status == "SPLIT" and node.children:
        out: list[SplitNode] = []
        for ch in node.children:
            out.extend(_leaves(ch))
        return out
    return [node]


# ---------------------------------------------------------------------------
# 任务 DAG（父子依赖；子仅变化触发父组核对）
# ---------------------------------------------------------------------------


def build_dag(parents_by_table: Mapping[str, Sequence[str]]) -> list[str]:
    """拓扑排序（父先子后）。环或未登记依赖 → ContractViolation。"""
    tables = set(parents_by_table)
    indegree = {t: 0 for t in tables}
    children: dict[str, list[str]] = {t: [] for t in tables}
    for table, deps in parents_by_table.items():
        for dep in deps:
            if dep not in tables:
                raise ContractViolation(f"[{table}] 依赖未登记的表 {dep}")
            indegree[table] += 1
            children[dep].append(table)
    ready = sorted(t for t, d in indegree.items() if d == 0)
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for ch in children[node]:
            indegree[ch] -= 1
            if indegree[ch] == 0:
                ready.append(ch)
        ready.sort()
    if len(order) != len(tables):
        unresolved = sorted(t for t, d in indegree.items() if d > 0)
        raise ContractViolation(f"DAG 存在环或未解析依赖: {unresolved}")
    return order


def affected_child_groups(
    failed_parent: str, parents_by_table: Mapping[str, Sequence[str]]
) -> list[str]:
    """父表失败只阻对应子组：返回直接依赖该父键的子表。"""
    return [t for t, deps in parents_by_table.items() if failed_parent in deps]


@dataclass
class CapturePlan:
    """一次捕获计划：任务、业务日、窗或 keyset、路由与父组核对要求。"""

    task_id: str
    business_day: date
    window: TimeWindow | None = None
    keyset: KeysetCursor | None = None
    route_sources: list[str] = field(default_factory=list)
    route_boundary_reverify: bool = False
    parent_group_checks: list[str] = field(default_factory=list)
    mode: str = "T1"  # T1/LATE_BACKLOG/LOOKBACK/MONTHLY_RESCAN/HISTORICAL_REPAIR


def resolve_lis_route(
    segments: Sequence[Mapping], business_time: datetime
) -> tuple[list[str], bool]:
    """按业务时间解析 LIS 双源段。返回 (源集合, 边界待核)。

    重叠段（mode=PRESERVE_DOCUMENTED_OVERLAP_REVERIFY_BOUNDARIES）返回双源并
    要求边界复核；不做静默去重或删另一源。
    """
    matched: list[Mapping] = []
    for seg in segments:
        start = seg.get("start_inclusive") or seg.get("start")
        end = seg.get("end_exclusive") or seg.get("end")
        if start is not None and business_time < _parse_ts(start):
            continue
        if end is not None and business_time >= _parse_ts(end):
            continue
        matched.append(seg)
    if not matched:
        raise ContractViolation(
            f"业务时间 {business_time} 未命中任何路由段（禁止回退单源整段跑）"
        )
    sources: list[str] = []
    for seg in matched:
        for src in seg.get("sources", []):
            if src not in sources:
                sources.append(src)
    boundary_reverify = any(
        seg.get("mode") == "PRESERVE_DOCUMENTED_OVERLAP_REVERIFY_BOUNDARIES"
        for seg in matched
    )
    return sources, boundary_reverify


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ---------------------------------------------------------------------------
# 历史业务月覆盖账（迟到漂移月度重扫）
# ---------------------------------------------------------------------------


def month_bounds(month: str) -> tuple[date, date]:
    """'2025-03' → (2025-03-01, 2025-04-01)。"""
    year, mon = month.split("-")
    year_i, mon_i = int(year), int(mon)
    if not (1 <= mon_i <= 12):
        raise ContractViolation(f"非法月份: {month}")
    start = date(year_i, mon_i, 1)
    end_mon = mon_i + 1
    end_year = year_i
    if end_mon > 12:
        end_mon = 1
        end_year += 1
    return start, date(end_year, end_mon, 1)


def month_sequence(start_month: str, end_month: str) -> list[str]:
    start, _ = month_bounds(start_month)
    end, _ = month_bounds(end_month)
    if start > end:
        raise ContractViolation(f"起始月晚于结束月: {start_month} > {end_month}")
    out: list[str] = []
    cursor = start
    while cursor < end:
        out.append(f"{cursor.year:04d}-{cursor.month:02d}")
        cursor = month_bounds(f"{cursor.year:04d}-{cursor.month:02d}")[1]
    out.append(f"{end.year:04d}-{end.month:02d}")
    return out


@dataclass
class MonthCoverageRecord:
    table: str
    business_month: str
    route_or_origin: str
    last_complete_snapshot_cutoff: datetime | None = None
    last_reconciled_at: datetime | None = None
    cycle_days: int | None = None
    pending_slices: int = 0
    failed_slices: int = 0
    unresolved_quality: int = 0
    overdue_reason: str | None = None

    def next_due(self) -> datetime | None:
        if self.last_reconciled_at is None or self.cycle_days is None:
            return None
        return self.last_reconciled_at + timedelta(days=self.cycle_days)

    def is_overdue(self, now: datetime) -> bool:
        due = self.next_due()
        if due is None:
            # 从未核过且已纳入范围：按未知处理，显式欠账而非静默
            return self.last_reconciled_at is None
        return now > due


def missing_months_in_scope(
    scope_start_month: str | None,
    scope_end_month: str | None,
    covered: set[str],
) -> list[str]:
    """范围内未覆盖的业务月清单。范围未冻结 → 返回空并要求先冻结（不猜）。"""
    if not scope_start_month or not scope_end_month:
        return []
    return [m for m in month_sequence(scope_start_month, scope_end_month) if m not in covered]


def month_days(month: str) -> int:
    start, end = month_bounds(month)
    return (end - start).days


def days_in_year(year: int) -> int:
    return 366 if calendar.isleap(year) else 365


# ---------------------------------------------------------------------------
# 覆盖年龄（R05：只扫当月不得冒充无限历史保障）
# ---------------------------------------------------------------------------


def coverage_age_report(
    *,
    managed_months: Sequence[str],
    last_visit_month_by_key: Mapping[str, str],
    now_month: str,
    cycle_days: int,
) -> dict:
    """按"每个月被重访的最长间隔"评估历史漂移保障等级。

    managed_months：声明的管理历史月清单（起止冻结后的完整清单，不是
    只扫过的月）。last_visit_month_by_key：每业务月最后一次重访所在的
    调度月（YYYY-MM）。cycle_days：声明的重访周期（天）。

    只扫当月（各月从未被重访）或 60 个月每月只轮访 1 个月时，最大重访
    间隔是全部历史，不能宣称"30 天内可见历史变化"；报告按月列
    max_interval_months 与保障等级，供日报如实展示与降级声明。
    """
    if not managed_months:
        return {
            "managed_months": 0,
            "coverage_level": "SCOPE_UNFROZEN",
            "note": "管理历史范围未冻结，不声称任何历史漂移保障",
        }
    now_start, _ = month_bounds(now_month)
    rows: list[dict] = []
    worst_gap_days = 0
    never_visited = 0
    for month in managed_months:
        visit = last_visit_month_by_key.get(month)
        if visit is None:
            never_visited += 1
            gap_days = (now_start - month_bounds(month)[0]).days
        else:
            visit_start, _ = month_bounds(visit)
            gap_days = max(0, (now_start - visit_start).days)
        worst_gap_days = max(worst_gap_days, gap_days)
        rows.append(
            {
                "month": month,
                "last_visit_month": visit,
                "days_since_visit": gap_days,
                "overdue": visit is None or gap_days > cycle_days,
            }
        )
    if never_visited == len(managed_months):
        level = "NO_HISTORY_VISIT"
    elif worst_gap_days > cycle_days * 2:
        level = "DEGRADED_BEYOND_DECLARED_CYCLE"
    elif worst_gap_days > cycle_days:
        level = "AT_DECLARED_CYCLE_EDGE"
    else:
        level = "WITHIN_DECLARED_CYCLE"
    return {
        "managed_months": len(managed_months),
        "never_visited": never_visited,
        "max_days_since_any_visit": worst_gap_days,
        "declared_cycle_days": cycle_days,
        "coverage_level": level,
        "rows": rows,
        "note": (
            "保障等级按每个月实际被重访的最长间隔计算；只扫当前月或单月轮转"
            "不得声称全历史周期内可见"
        ),
    }
