"""种子装载：任务包机器 JSON → TaskSpec 契约对象 + E01 盘点报告。

输入目录为执行包目录（含 77项任务候选种子.json、每表性能与通道画像候选.json、
LIS双源路由候选.json、迟到漂移月度重扫策略.json、E01已知人工工单种子.json、
故障隔离与继续执行规则.json、告警触发与升级规则.json）。

装载只读 JSON、不连库、不外发；种子默认 disabled/UNKNOWN，装载后仍保持该
状态——本模块不做任何“变 READY”的推导。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.reporting_pipeline.contracts import (
    Applicability,
    ContractViolation,
    DeadlineState,
    Engine,
    IncrementalStrategy,
    ReadinessLayer,
    TaskAssociations,
    TaskSpec,
    summarize_verdicts,
)

SEED_FILE = "77项任务候选种子.json"
PROFILE_FILE = "每表性能与通道画像候选.json"
LIS_ROUTE_FILE = "LIS双源路由候选.json"
RESCAN_FILE = "迟到漂移月度重扫策略.json"
TICKET_FILE = "E01已知人工工单种子.json"
FAILURE_POLICY_FILE = "故障隔离与继续执行规则.json"
ALERT_RULES_FILE = "告警触发与升级规则.json"

# E01-DATETIME-DEPENDENCY 工单覆盖的三张表（种子 human_view_ticket_state 之外
# 的显式依赖登记：住院费用明细、门诊费用明细、医嘱检查）
DATETIME_DEPENDENCY_TABLES = (
    "EMR_IN_FEE_INFO_CHILD",
    "EMR_OUT_FEE_INFO_CHILD",
    "EMR_DOC_ORDER_CHECK",
)

_EXPECTED_COUNT = 77
_EXPECTED_SOURCE_GROUPS = 11

# 默认执行包目录（测试与 CLI 共用；可被 --config 覆盖）
PACKAGE_DIR = (
    Path(__file__).resolve().parents[4] / "开发起步包" / "output_r189"
    / "r189-20261015-upload-audit" / "daily_t1_20261015" / "python_datax_execution_20261019"
)


@dataclass
class SeedBundle:
    package_id: str
    config_dir: Path
    tasks: list[TaskSpec]
    profiles: dict[str, dict[str, Any]]
    lis_routes: dict[str, dict[str, Any]]
    rescan_policy: dict[str, Any]
    tickets: list[dict[str, Any]]
    raw_scope: dict[str, Any]
    problems: list[str] = field(default_factory=list)

    # -- 聚合视图 -------------------------------------------------------

    def source_group_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for task in self.tasks:
            for src in task.source_candidates:
                counts[src.source_group] = counts.get(src.source_group, 0) + 1
        return dict(sorted(counts.items()))

    def dual_source_tasks(self) -> list[TaskSpec]:
        return [t for t in self.tasks if t.dual_source()]

    def not_provided_tasks(self) -> list[TaskSpec]:
        return [
            t for t in self.tasks
            if t.applicability == Applicability.WAITING_BUSINESS_CONFIRMATION
        ]

    def rescan_tasks(self) -> list[TaskSpec]:
        return [t for t in self.tasks if t.associations.monthly_rescan_policy_ref]

    def datetime_dependency_tasks(self) -> list[TaskSpec]:
        return [t for t in self.tasks if t.canonical_table in DATETIME_DEPENDENCY_TABLES]

    def readiness_summary(self) -> dict[str, dict[str, int]]:
        return summarize_verdicts(self.tasks)

    def inventory_report(self) -> dict[str, Any]:
        """E01 盘点：已知/待核分开，不让缺失冒充已核。"""
        profiles_unmeasured = [
            p["canonical_table"] for p in self.profiles.values()
            if p.get("measurement_state") != "MEASURED_VERIFIED"
        ]
        writer_snapshot = {
            "state": "LIVE_SNAPSHOT_REQUIRED_AT_E01_AND_REFRESH_AT_CUTOVER",
            "snapshot_captured": False,
            "note": "8.53 进程快照需 ops-runbook 受控通道与具体批准；本轮未 SSH，"
                    "不把 manual2/dqueue/gap_exec 的用户时点陈述当已停证据",
        }
        credentials = {
            "policy": "APPROVED_SECRET_STORE_REF_NOT_TMP_ENV",
            "configured_refs": sorted({
                t.associations.long_lived_credential_ref
                for t in self.tasks if t.associations.long_lived_credential_ref
            }),
            "unconfigured_tables": sum(
                1 for t in self.tasks if not t.associations.long_lived_credential_ref
            ),
        }
        return {
            "package_id": self.package_id,
            "counts": {
                "canonical_items": len(self.tasks),
                "unique_canonical_tables": len({t.canonical_table for t in self.tasks}),
                "source_groups": len(self.source_group_counts()),
                "dual_source_tables": [t.canonical_table for t in self.dual_source_tasks()],
                "not_provided_pending_applicability": [
                    t.canonical_table for t in self.not_provided_tasks()
                ],
                "rescan_tables": [t.canonical_table for t in self.rescan_tasks()],
                "datetime_dependency_tables": [
                    t.canonical_table for t in self.datetime_dependency_tasks()
                ],
            },
            "seed_state": {
                "enabled_any": any(t.enabled for t in self.tasks),
                "engine_distribution": _distribution(t.engine.value for t in self.tasks),
                "applicability_distribution": _distribution(
                    t.applicability.value for t in self.tasks
                ),
                "deadline_state_distribution": _distribution(
                    t.associations.deadline_state.value for t in self.tasks
                ),
            },
            "readiness_layers": self.readiness_summary(),
            "source_group_object_counts": self.source_group_counts(),
            "performance_profiles": {
                "total": len(self.profiles),
                "unmeasured": len(profiles_unmeasured),
                "measured_verified": len(self.profiles) - len(profiles_unmeasured),
                "missing_action": "REFUSE_PRODUCTION_READY_ALLOW_OFFLINE_DEVELOPMENT",
            },
            "lis_routes": {
                table: {
                    "segments": len(route.get("segments", [])),
                    "overlap_q4_2023": any(
                        seg.get("mode") == "PRESERVE_DOCUMENTED_OVERLAP_REVERIFY_BOUNDARIES"
                        for seg in route.get("segments", [])
                    ),
                    "route_clock_verified": bool(route.get("route_clock_and_timezone_verified")),
                }
                for table, route in self.lis_routes.items()
            },
            "monthly_rescan": {
                "tables": self.rescan_policy.get("tables"),
                "managed_history_start_month": self.rescan_policy.get("managed_history_start_month"),
                "managed_history_end_month": self.rescan_policy.get("managed_history_end_month"),
                "scope_state": "SCOPE_UNFROZEN_E01_TO_FILL"
                if not self.rescan_policy.get("managed_history_start_month")
                else "SCOPE_FROZEN",
            },
            "manual_tickets": {
                "count": len(self.tickets),
                "ids": [t.get("ticket") for t in self.tickets],
                "never_auto_close": True,
            },
            "writer_handoff": writer_snapshot,
            "long_lived_credentials": credentials,
            "problems": list(self.problems),
        }


def _distribution(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _task_spec_from_seed(item: dict[str, Any]) -> TaskSpec:
    from app.services.reporting_pipeline.contracts import (
        ApplyPolicy,
        ChangePolicy,
        ProjectionField,
        ResourceBudget,
        SourceRef,
        StableKey,
        TargetRef,
        TimeSemantics,
    )

    sources = [
        SourceRef(
            object_id=str(s["object_id"]),
            role=str(s.get("role", "primary")),
            source_group=str(s["source_group"]),
            host=str(s["host"]),
            port=int(s["port"]),
            object_name_candidates=list(s.get("object_name_candidates", [])),
            owner_hint=s.get("owner_hint"),
            database_hint=s.get("database_hint"),
            current_identity_verified=bool(s.get("current_identity_verified", False)),
        )
        for s in item.get("source_candidates", [])
    ]
    target_raw = item.get("target_candidate") or {}
    target = TargetRef(
        host=str(target_raw.get("host", "")),
        port=int(target_raw.get("port", 0)),
        service=str(target_raw.get("service", "")),
        owner=str(target_raw.get("owner", "")),
        table=str(target_raw.get("table", item["canonical_table"])),
        current_identity_verified=bool(target_raw.get("current_identity_verified", False)),
    )
    key_raw = item.get("stable_key") or {}
    stable_key = StableKey(
        candidate=list(key_raw.get("candidate", [])),
        verified=bool(key_raw.get("verified", False)),
    )
    change_raw = item.get("change_policy") or {}
    change_policy = ChangePolicy(
        strategy=IncrementalStrategy(item.get("incremental_strategy", "UNRESOLVED")),
        insert_evidence=item.get("insert_evidence") or change_raw.get("insert_evidence"),
        update_evidence=item.get("update_evidence") or change_raw.get("update_evidence"),
        retract_evidence=item.get("delete_or_retract_evidence") or change_raw.get("retract_evidence"),
        source_version_order=item.get("source_version_order") or change_raw.get("source_version_order"),
        child_only_change_trigger=list(
            change_raw.get(
                "child_only_change_trigger",
                item.get("child_only_change_trigger", []),
            )
        ),
        version_order_verified=bool(
            change_raw.get("version_order_verified", False)
        ),
    )
    time_raw = item.get("time_semantics") or {}
    time_semantics = TimeSemantics(
        business_time_expression=time_raw.get("business_time_expression"),
        business_time_verified=bool(time_raw.get("business_time_verified", False)),
        change_time_expression=time_raw.get("change_time_expression"),
        change_time_verified=bool(time_raw.get("change_time_verified", False)),
        visibility_cutoff_rule=time_raw.get("visibility_cutoff_rule"),
        overlap_seconds=time_raw.get("overlap_seconds"),
        timezone=time_raw.get("timezone"),
        same_second_cursor_rule=time_raw.get("same_second_cursor_rule"),
    )
    budget_raw = item.get("resource_budget") or {}
    resource_budget = ResourceBudget(
        per_source_concurrency=budget_raw.get("per_source_concurrency"),
        query_timeout_seconds=budget_raw.get("query_timeout_seconds"),
        cancel_supported=bool(budget_raw.get("cancel_supported", False)),
        max_rows_per_slice=budget_raw.get("max_rows_per_slice"),
        max_bytes_per_slice=budget_raw.get("max_bytes_per_slice"),
        max_attempts=budget_raw.get("max_attempts"),
        max_elapsed_seconds=budget_raw.get("max_elapsed_seconds"),
    )
    projection = [
        ProjectionField(
            name=str(field["name"]),
            target_type=str(field["target_type"]),
            order=int(field["order"]),
            source_expression=field.get("source_expression"),
            type_verified=bool(field.get("type_verified", False)),
        )
        for field in item.get("projection", [])
    ]
    apply_raw = item.get("apply_policy") or {}
    apply_policy = ApplyPolicy(
        executor_ref=apply_raw.get("executor_ref"),
        allowed_operations=list(apply_raw.get("allowed_operations", [])),
        idempotency_key=list(apply_raw.get("idempotency_key", [])),
        txn_row_budget=apply_raw.get("txn_row_budget"),
        txn_byte_budget=apply_raw.get("txn_byte_budget"),
        commit_receipt_mode=apply_raw.get("commit_receipt_mode"),
        approval_refs=list(apply_raw.get("approval_refs", [])),
    )
    table = item["canonical_table"]
    associations = TaskAssociations(
        failure_policy_ref=item.get("failure_policy_ref", FAILURE_POLICY_FILE),
        alert_policy_ref=item.get("alert_policy_ref", ALERT_RULES_FILE),
        performance_profile_id=item.get("performance_profile_ref"),
        route_policy_ref=item.get("route_policy_ref"),
        monthly_rescan_policy_ref=item.get("monthly_rescan_policy_ref"),
        datetime_dependency_ticket=(
            "E01-DATETIME-DEPENDENCY" if table in DATETIME_DEPENDENCY_TABLES else None
        ),
        long_lived_credential_ref=item.get("long_lived_credential_ref"),
        running_writer_handoff_state=item.get("running_writer_handoff_state", "NOT_LIVE_VERIFIED"),
        deadline_state=DeadlineState(item.get("deadline_state", "UNCONFIGURED")),
        deadline=item.get("deadline"),
        human_view_ticket_state=item.get("human_view_ticket_state", "TO_REVIEW"),
    )
    return TaskSpec(
        canonical_table=table,
        business_name=item.get("business_name", ""),
        index=int(item.get("index", 0)),
        enabled=bool(item.get("enabled", False)),
        applicability=Applicability(item.get("applicability", "TO_VERIFY")),
        engine=Engine(item.get("engine", "UNDECIDED")),
        incremental_strategy=IncrementalStrategy(item.get("incremental_strategy", "UNRESOLVED")),
        source_candidates=sources,
        target=target,
        stable_key=stable_key,
        associations=associations,
        projection=projection,
        definition_fingerprint=item.get("definition_fingerprint"),
        dependency_fingerprints=dict(item.get("dependency_fingerprints", {})),
        declared_parent_candidates=list(item.get("declared_parent_candidates", [])),
        change_policy=change_policy,
        time_semantics=time_semantics,
        apply_policy=apply_policy,
        resource_budget=resource_budget,
        config_version=item.get("config_version", "v0-seed"),
        note=item.get("note"),
    )


def load_seed_bundle(config_dir: str | Path) -> SeedBundle:
    """装载并校验任务包。结构矛盾收集进 problems（validate 命令据此非零退出）。"""
    config_dir = Path(config_dir)
    problems: list[str] = []

    seed_doc = _load_json(config_dir / SEED_FILE)
    profile_doc = _load_json(config_dir / PROFILE_FILE)
    lis_doc = _load_json(config_dir / LIS_ROUTE_FILE)
    rescan_doc = _load_json(config_dir / RESCAN_FILE)
    ticket_doc = _load_json(config_dir / TICKET_FILE)
    # 引用文件存在性（failure/alert 规则被每个 TaskSpec 关联）
    for ref in (FAILURE_POLICY_FILE, ALERT_RULES_FILE):
        if not (config_dir / ref).exists():
            problems.append(f"关联策略文件缺失: {ref}")

    items = seed_doc.get("items", [])
    if len(items) != _EXPECTED_COUNT:
        problems.append(f"种子条目数 {len(items)} != {_EXPECTED_COUNT}")
    tables = [i.get("canonical_table") for i in items]
    if len(tables) != len(set(tables)):
        problems.append("canonical_table 存在重复")

    profiles = {p["canonical_table"]: p for p in profile_doc.get("profiles", [])}
    lis_routes = {r["canonical_table"]: r for r in lis_doc.get("tables", [])}
    rescan_tables = set(rescan_doc.get("tables", []))
    tickets = list(ticket_doc.get("tickets", []))

    tasks: list[TaskSpec] = []
    for item in items:
        try:
            spec = _task_spec_from_seed(item)
        except (KeyError, TypeError, ValueError) as exc:
            problems.append(f"种子字段异常 [{item.get('canonical_table', '?')}]: {exc!r}")
            continue
        table = spec.canonical_table
        # 关联一致性：profile 引用必须可解析
        pid = spec.associations.performance_profile_id
        if pid and pid not in profiles.values() and table not in profiles:
            problems.append(f"[{table}] performance_profile_ref 无法解析: {pid}")
        if spec.associations.route_policy_ref and table not in lis_routes:
            problems.append(f"[{table}] route_policy_ref 无法解析")
        if spec.associations.monthly_rescan_policy_ref and table not in rescan_tables:
            problems.append(f"[{table}] monthly_rescan_policy_ref 与策略表集不一致")
        if table in rescan_tables and not spec.associations.monthly_rescan_policy_ref:
            problems.append(f"[{table}] 在重扫策略表集内但种子未引用")
        try:
            spec.validate_structure()
        except ContractViolation as exc:
            problems.append(str(exc))
        tasks.append(spec)

    # 77项不漏不重 + 双源/未提供单列（验收场景 AT-001 机器口径）
    group_counts: dict[str, int] = {}
    for task in tasks:
        for src in task.source_candidates:
            group_counts[src.source_group] = group_counts.get(src.source_group, 0) + 1
    if len(group_counts) > _EXPECTED_SOURCE_GROUPS:
        problems.append(f"源分组数 {len(group_counts)} 超过冻结值 {_EXPECTED_SOURCE_GROUPS}")

    # 种子保护：全部 disabled / UNKNOWN（不得伪装 READY）
    enabled = [t.canonical_table for t in tasks if t.enabled]
    if enabled:
        problems.append(f"存在 enabled=true 种子: {enabled[:5]}")

    return SeedBundle(
        package_id=seed_doc.get("package_id", ""),
        config_dir=config_dir,
        tasks=tasks,
        profiles=profiles,
        lis_routes=lis_routes,
        rescan_policy=rescan_doc,
        tickets=tickets,
        raw_scope=seed_doc.get("scope"),
        problems=problems,
    )


def validate_bundle(bundle: SeedBundle) -> dict[str, Any]:
    """结构校验 + 分层就绪汇总；problems 非空即整体失败。"""
    report = bundle.inventory_report()
    report["validation"] = {
        "structural_problems": bundle.problems,
        "structure_ok": not bundle.problems,
        # 未知不能变 READY：任一生产层存在 READY 即为契约违背（种子期应为 0）
        "ready_violations": _ready_violations(bundle),
    }
    report["offline"] = True
    return report


def _ready_violations(bundle: SeedBundle) -> list[str]:
    violations: list[str] = []
    for task in bundle.tasks:
        for layer, verdict in task.layer_verdicts().items():
            if layer != ReadinessLayer.CONFIG_VALID and verdict.status.value == "READY":
                violations.append(
                    f"[{task.canonical_table}] {layer.value}=READY 违反未知不可就绪"
                )
    return violations
