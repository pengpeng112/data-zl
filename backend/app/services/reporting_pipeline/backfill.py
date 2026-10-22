"""B02 2026历史补齐离线工具：拆窗预演 / 键集差异框架 / 父子发布顺序编排。

对应主计划 §五-B02 与接续说明第 4 节。三件工具全部离线/模拟语义：
- 不连接生产源库、不写前置机目标；真实键集比较与正式装载等批准后另行装配。
- 拆窗预演复用 planner.SplitNode 的状态语义（PENDING/SPLIT/LEAF/KEYSET），
  但按"月→日→小时"日历对齐递归，不做盲目二分。
- 覆盖校验是硬验收：叶窗互斥、连续、无空洞、恰好覆盖 [start,end)。
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Iterable, Mapping, Sequence

from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.planner import TimeWindow

# ---------------------------------------------------------------------------
# 工具一：历史范围拆窗预演
# ---------------------------------------------------------------------------

DEFAULT_MAX_ROWS_PER_LEAF = 2_000_000
DEFAULT_MAX_BYTES_PER_LEAF = 512 * 1024 * 1024


@dataclass(frozen=True)
class WindowEstimate:
    """单窗预算估计（离线画像模型或批准后的实测画像输入）。"""

    rows: int
    bytes: int

    def exceeds(self, max_rows: int, max_bytes: int) -> bool:
        return self.rows > max_rows or self.bytes > max_bytes


EstimateFn = Callable[[TimeWindow], WindowEstimate]


def _month_windows(start: datetime, end_exclusive: datetime) -> list[TimeWindow]:
    """第一层按日历月切分（跨年逐月推进），月内不再受二分影响。"""
    if start >= end_exclusive:
        raise ContractViolation(f"非法历史范围: {start} >= {end_exclusive}")
    out: list[TimeWindow] = []
    cur = datetime(start.year, start.month, 1)
    while cur < end_exclusive:
        last_day = calendar.monthrange(cur.year, cur.month)[1]
        month_end = datetime(cur.year, cur.month, last_day) + timedelta(days=1)
        w_start = max(cur, start)
        w_end = min(month_end, end_exclusive)
        if w_start < w_end:
            out.append(TimeWindow(w_start, w_end))
        cur = month_end
    return out


def _calendar_split(window: TimeWindow, grain: str) -> list[TimeWindow]:
    """日→小时（grain='hour'）或月→日（grain='day'）的日历对齐切分。"""
    if grain == "day":
        out: list[TimeWindow] = []
        cur = window.start
        while cur < window.end_exclusive:
            day_end = datetime(cur.year, cur.month, cur.day) + timedelta(days=1)
            w_end = min(day_end, window.end_exclusive)
            if cur < w_end:
                out.append(TimeWindow(cur, w_end))
            cur = w_end
        return out
    if grain == "hour":
        out = []
        cur = window.start
        while cur < window.end_exclusive:
            hour_end = cur.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            w_end = min(hour_end, window.end_exclusive)
            if cur < w_end:
                out.append(TimeWindow(cur, w_end))
            cur = w_end
        return out
    raise ContractViolation(f"未知拆分粒度: {grain}")


def plan_backfill_windows(
    start: datetime,
    end_exclusive: datetime,
    estimate_fn: EstimateFn,
    *,
    max_rows_per_leaf: int = DEFAULT_MAX_ROWS_PER_LEAF,
    max_bytes_per_leaf: int = DEFAULT_MAX_BYTES_PER_LEAF,
) -> dict:
    """[start,end) 月→日→小时递归拆窗；超限到小时仍超转 KEYSET 待处理。

    返回 {"leaves": [...], "coverage": {...}, "totals": {...}}。叶窗状态沿用
    SplitNode 语义：LEAF_PENDING（可整窗捕获）/ KEYSET（最小粒度仍超限，
    需稳定 keyset 分页，禁止继续盲目二分）。
    """
    if start.tzinfo is not None or end_exclusive.tzinfo is not None:
        raise ContractViolation("拆窗预演用 naive 本地时间（院区时区）；不要混入 tz-aware")
    leaves: list[dict] = []

    def recurse(window: TimeWindow, grain: str, depth: int) -> None:
        est = estimate_fn(window)
        if not est.exceeds(max_rows_per_leaf, max_bytes_per_leaf):
            leaves.append(_leaf(window, "LEAF_PENDING", est, depth))
            return
        if grain == "month":
            children = _calendar_split(window, "day")
            child_grain = "day"
        elif grain == "day":
            children = _calendar_split(window, "hour")
            child_grain = "hour"
        else:  # hour 粒度仍超限：转 keyset，不再按时间拆
            leaves.append(_leaf(window, "KEYSET", est, depth))
            return
        # 子窗数量为 1 说明日历对齐已到边界（如半小时残窗），防无限递归
        if len(children) <= 1:
            leaves.append(_leaf(window, "KEYSET", est, depth))
            return
        for child in children:
            recurse(child, child_grain, depth + 1)

    for month in _month_windows(start, end_exclusive):
        est = estimate_fn(month)
        if est.exceeds(max_rows_per_leaf, max_bytes_per_leaf):
            recurse(month, "month", 1)
        else:
            leaves.append(_leaf(month, "LEAF_PENDING", est, 1))
    coverage = verify_leaf_coverage(leaves, start, end_exclusive)
    totals = {
        "leaves": len(leaves),
        "keyset_leaves": sum(1 for lf in leaves if lf["status"] == "KEYSET"),
        "estimated_rows": sum(lf["estimated_rows"] for lf in leaves),
        "estimated_bytes": sum(lf["estimated_bytes"] for lf in leaves),
        "range": f"{start.isoformat()}/{end_exclusive.isoformat()}",
    }
    return {"leaves": leaves, "coverage": coverage, "totals": totals}


def _leaf(window: TimeWindow, status: str, est: WindowEstimate, depth: int) -> dict:
    return {
        "window_start": window.start.isoformat(),
        "window_end_exclusive": window.end_exclusive.isoformat(),
        "duration_seconds": int(window.duration_seconds()),
        "status": status,
        "estimated_rows": est.rows,
        "estimated_bytes": est.bytes,
        "depth": depth,
    }


def verify_leaf_coverage(
    leaves: Sequence[Mapping], start: datetime, end_exclusive: datetime
) -> dict:
    """硬验收：叶窗互斥、连续、无空洞、恰好覆盖 [start,end)。"""
    parsed = [
        (datetime.fromisoformat(lf["window_start"]), datetime.fromisoformat(lf["window_end_exclusive"]))
        for lf in leaves
    ]
    parsed.sort()
    problems: list[str] = []
    if not parsed:
        problems.append("叶窗为空")
    else:
        if parsed[0][0] != start:
            problems.append(f"首叶起点 {parsed[0][0]} != 范围起点 {start}")
        if parsed[-1][1] != end_exclusive:
            problems.append(f"末叶终点 {parsed[-1][1]} != 范围终点 {end_exclusive}")
        for (_, prev_end), (cur_start, _) in zip(parsed, parsed[1:]):
            if cur_start < prev_end:
                problems.append(f"叶窗重叠: {cur_start} < {prev_end}")
            elif cur_start > prev_end:
                problems.append(f"叶窗空洞: ({prev_end}, {cur_start})")
    return {
        "ok": not problems,
        "leaf_count": len(parsed),
        "problems": problems,
    }


def uniform_profile_estimate(rows_per_day: int, bytes_per_row: int = 512) -> EstimateFn:
    """离线预演用均匀画像模型（按天线性插值；正式执行前用实测画像替换）。"""

    def estimate(window: TimeWindow) -> WindowEstimate:
        days = max(window.duration_seconds() / 86400.0, 1.0 / 86400.0)
        rows = max(1, int(round(rows_per_day * days)))
        return WindowEstimate(rows=rows, bytes=rows * bytes_per_row)

    return estimate


# ---------------------------------------------------------------------------
# 工具二：2026 缺口差异清单框架（只读核验；实际执行等批准）
# ---------------------------------------------------------------------------

@dataclass
class GapDiffLedger:
    """源键集 vs 目标键集的差异分账（框架产物，不含患者数据）。"""

    table: str
    window_start: str
    window_end_exclusive: str
    source_keys: int = 0
    target_keys: int = 0
    missing_in_target: list[str] = field(default_factory=list)
    extra_in_target: list[str] = field(default_factory=list)
    content_diff: list[str] = field(default_factory=list)
    source_duplicate_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "table": self.table,
            "window": f"{self.window_start}/{self.window_end_exclusive}",
            "source_keys": self.source_keys,
            "target_keys": self.target_keys,
            "missing_in_target_count": len(self.missing_in_target),
            "extra_in_target_count": len(self.extra_in_target),
            "content_diff_count": len(self.content_diff),
            "source_duplicate_keys_count": len(self.source_duplicate_keys),
            "missing_in_target": self.missing_in_target,
            "extra_in_target": self.extra_in_target,
            "content_diff": self.content_diff,
            "source_duplicate_keys": self.source_duplicate_keys,
            "note": "离线框架分账；键值为模型/样例，真实键集读取与差异装载等批准后执行",
        }


def build_gap_diff(
    table: str,
    window: TimeWindow,
    source_keys: Iterable[str],
    target_keys: Iterable[str],
    content_equal: Callable[[str], bool] | None = None,
) -> GapDiffLedger:
    """源/目标键集 → 缺失/多余/内容差异分账。

    content_equal(key) 返回 False 记 content_diff（键在两侧都存在但内容不一致）。
    源侧重复键单独分账（键唯一性验收失败不得静默去重）。
    """
    src: list[str] = list(source_keys)
    tgt = set(target_keys)
    src_seen: set[str] = set()
    ledger = GapDiffLedger(
        table=table,
        window_start=window.start.isoformat(),
        window_end_exclusive=window.end_exclusive.isoformat(),
        source_keys=len(src),
        target_keys=len(tgt),
    )
    for key in src:
        if key in src_seen:
            ledger.source_duplicate_keys.append(key)
            continue
        src_seen.add(key)
        if key not in tgt:
            ledger.missing_in_target.append(key)
        elif content_equal is not None and not content_equal(key):
            ledger.content_diff.append(key)
    ledger.extra_in_target = sorted(tgt - src_seen)
    ledger.missing_in_target.sort()
    ledger.content_diff.sort()
    return ledger


def gap_diff_keyset_sql(
    source_object: str, key_expr: str, anchor_column: str = "DATETIME"
) -> str:
    """批准后用于双侧键集的限量只读 SQL 模板（半开窗 + 行数上限由通道控制）。"""
    return (
        f"SELECT {key_expr} AS K FROM {source_object} "
        f"WHERE {anchor_column} >= :start AND {anchor_column} < :end"
    )


# ---------------------------------------------------------------------------
# 工具三：父子发布顺序编排
# ---------------------------------------------------------------------------

@dataclass
class PublishPlanTable:
    canonical_table: str
    wave: int
    mode: str  # PUBLISH / WAITING_PARENT_AUTO_WAKE / REUSE_EXISTING_PARENT
    parents: list[str]
    blocked_by: list[str] = field(default_factory=list)


def build_publish_order(
    tasks: Sequence[Mapping],
    existing_parent_checker: Callable[[str, str], bool] | None = None,
) -> dict:
    """父先子后的发布波次编排。

    - tasks 元素需含 canonical_table 与 declared_parent_candidates（[{parent}]）。
    - 目标已有父（existing_parent_checker(parent, child) 为真）→ 子表该依赖
      标 REUSE_EXISTING_PARENT，不等待本轮父发布。
    - 父不在编排范围且目标也没有 → 依赖标 WAITING_PARENT_AUTO_WAKE（沿用恢复
      层等待-唤醒语义：父提交后自动重排，不造父、不丢子）。
    - 循环依赖直接拒绝（ContractViolation）。
    """
    by_table = {t["canonical_table"]: t for t in tasks}
    deps: dict[str, list[str]] = {}
    modes: dict[str, set[str]] = {}
    for tbl, task in by_table.items():
        modes[tbl] = set()
        for rel in task.get("declared_parent_candidates") or []:
            parent = rel["parent"] if isinstance(rel, Mapping) else rel
            if parent not in by_table:
                if existing_parent_checker and existing_parent_checker(parent, tbl):
                    modes[tbl].add("REUSE_EXISTING_PARENT")
                    continue
                modes[tbl].add("WAITING_PARENT_AUTO_WAKE")
                continue
            if existing_parent_checker and existing_parent_checker(parent, tbl):
                modes[tbl].add("REUSE_EXISTING_PARENT")
                continue
            deps.setdefault(tbl, []).append(parent)

    # Kahn 拓扑分层（父波次 < 子波次；同层按任务序稳定排序；无依赖任务进第0波）
    remaining: dict[str, list[str]] = {tbl: deps.get(tbl, []) for tbl in by_table}
    order_index = {t["canonical_table"]: t.get("index", 0) for t in tasks}
    waves: list[list[str]] = []
    placed: set[str] = set()
    while remaining:
        ready = sorted(
            (tbl for tbl, ps in remaining.items() if all(p in placed for p in ps)),
            key=lambda t: order_index.get(t, 0),
        )
        if not ready:
            raise ContractViolation(f"父子依赖存在循环: {sorted(remaining)}")
        waves.append(ready)
        for tbl in ready:
            placed.add(tbl)
            del remaining[tbl]

    plan: list[PublishPlanTable] = []
    waiting_blocked: dict[str, list[str]] = {}
    for tbl, task in by_table.items():
        wave_no = 0
        for i, wave in enumerate(waves):
            if tbl in wave:
                wave_no = i
                break
        mode_set = modes[tbl]
        if "WAITING_PARENT_AUTO_WAKE" in mode_set:
            missing = [
                (rel["parent"] if isinstance(rel, Mapping) else rel)
                for rel in task.get("declared_parent_candidates") or []
                if (rel["parent"] if isinstance(rel, Mapping) else rel) not in by_table
            ]
            exists_check = existing_parent_checker or (lambda p, c: False)
            still_missing = [p for p in missing if not exists_check(p, tbl)]
            if still_missing:
                waiting_blocked[tbl] = still_missing
        mode = (
            "WAITING_PARENT_AUTO_WAKE"
            if "WAITING_PARENT_AUTO_WAKE" in mode_set
            else ("REUSE_EXISTING_PARENT" if "REUSE_EXISTING_PARENT" in mode_set else "PUBLISH")
        )
        plan.append(
            PublishPlanTable(
                canonical_table=tbl,
                wave=wave_no,
                mode=mode,
                parents=[p for ps in [deps.get(tbl, [])] for p in ps]
                or [
                    (rel["parent"] if isinstance(rel, Mapping) else rel)
                    for rel in task.get("declared_parent_candidates") or []
                ],
                blocked_by=waiting_blocked.get(tbl, []),
            )
        )
    plan.sort(key=lambda p: (p.wave, order_index.get(p.canonical_table, 0)))
    return {
        "waves": [
            {"wave": i, "tables": wave, "note": f"第{i}波（先父后子）"}
            for i, wave in enumerate(waves)
        ],
        "tables": [
            {
                "table": p.canonical_table,
                "wave": p.wave,
                "mode": p.mode,
                "parents": p.parents,
                "blocked_by_missing_parents": p.blocked_by,
            }
            for p in plan
        ],
        "waiting_parent_tables": sorted(waiting_blocked),
        "semantics": {
            "PUBLISH": "本轮正常发布（父波次在前）",
            "REUSE_EXISTING_PARENT": "目标已有父，验后直接复用，不等待本轮父发布",
            "WAITING_PARENT_AUTO_WAKE": "父不在本轮且目标缺父：组等待，父提交后自动唤醒重排（不造父不丢子）",
        },
    }
