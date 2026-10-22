# -*- coding: utf-8 -*-
"""R01 冻结件生成：带版本冻结配置 + 输入差异清单 + 用例映射。

产物：R01_冻结配置与差异清单_<日期>.json（本目录）
- 输入指纹：seed/LIS路由/画像/场景矩阵/工单种子的当前 sha256；
- 血透 DSN 纠正：87 地址 + database_hint=dialysis 与交接 hdis 的错位
  在冻结件中登记为 corrected_value=hdis（证据=交接与整改计划§3.3），
  相关项 READ_READY 维持 UNKNOWN，R07 受控实测后才可核；
- 逐表字段缺口统计：身份未核/引擎未定/凭据未配等计数与清单；
- 原 112 场景 + RT1 补充场景到实际测试的映射（执行过的填证据，
  未执行的保持 NOT_RUN，不批量置 PASS）。

用法：python build_r01_freeze.py（只读本目录与上级输入，不连库）
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent

INPUTS = {
    "seed_77": PKG / "77项任务候选种子.json",
    "lis_routes": PKG / "LIS双源路由候选.json",
    "perf_profiles": PKG / "每表性能与通道画像候选.json",
    "acceptance_matrix_112": PKG / "验收场景矩阵.json",
    "manual_ticket_seed": PKG / "E01已知人工工单种子.json",
    "long_task_contract": PKG / "长任务执行契约.json",
    "late_drift_policy": PKG / "迟到漂移月度重扫策略.json",
}

# 已核纠正（证据链固定，不改原输入文件，只在冻结件中生效）
CORRECTIONS = [
    {
        "correction_id": "R01-CORR-DIALYSIS-DB",
        "scope": "source_group=dialysis（EMR_BLOOD_DIALY_RECORD/DETAIL/ORDER）",
        "field": "source_candidates[].database_hint",
        "input_value": "dialysis",
        "frozen_value": "hdis",
        "evidence": [
            "交接终版源 10.10.8.87:5432/hdis（8.86 主库实时只读从库）",
            "T加1上线前整改与接续验收计划.md §3.3",
        ],
        "rule": "冻结件统一 hdis；不得把 hint 拼成连接串；R07 受控实测前 READ_READY 维持 UNKNOWN",
        "voided_todos": [
            "旧 17432 防火墙/pg_hba 网络改造待办（17432 仅为备用点，待办作废）",
        ],
    },
]

# RT1 补充场景 → 本轮实际执行的测试（离线部分）
RT1_OFFLINE_EVIDENCE = {
    "RT1-003": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r02_durable_and_watermarks.py::TestDurableFileStageStore",
        "evidence": "A/B 两进程语义=同目录两次打开：块恢复、COMPLETE 清单、截断/取消/半截拒绝",
        "remaining": "ISOLATED_PG：两进程并发+重启注入（RT1-004/005 同）",
    },
    "RT1-004": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r05_scheduler_fixes.py::TestLeaseTokenPassthrough::test_stale_token_rejected_after_reacquire",
        "evidence": "内存仓储：过期接管 token 前进+旧 token 拒绝；PG 跨进程 FOR UPDATE 原子性待隔离库",
        "remaining": "ISOLATED_PG：两工作者同时领取只有一个成功（SqlAlchemyControlRepository）",
    },
    "RT1-006": {
        "executed_offline_part": "既有 test_adapters.TestPythonReaderSplit + test_r02 拆窗守恒（173 内）",
        "evidence": "递归拆分/keyset/PARKED 算法既有测试保持通过",
        "remaining": "ISOLATED_DRIVER：真实 Oracle 驱动上 5 万+行实测",
    },
    "RT1-009": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r03_r06_adapters_alerts.py::TestRealSubprocessDataX",
        "evidence": "真实子进程假 datax：exit0+dirty/缺指标/超时全拒绝 COMPLETE（SubprocessProcessRunner+DataXRunner）",
        "remaining": "ISOLATED_DATAX：真实 DataX 插件/密钥/stage 装载",
    },
    "RT1-011": {
        "executed_offline_part": "既有 test_adapters EngineRouter（不自动 fallback）+ JobFileWorkspace 投影白名单测试",
        "evidence": "DataX-only 失败不切 Python；job 渲染投影/窗口/白名单拒绝路径覆盖",
        "remaining": "通道与投影的受控 stage 实测",
    },
    "RT1-012": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r04_version_fence.py::TestApprovalCannotBeForged",
        "evidence": "PlatformApprovalVerifier 拒未登记批准/停用执行器/失效批准；production_mode 拒静态核验器",
        "remaining": "接入平台 asset_action_executors 真实查询的联调",
    },
    "RT1-014": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r04_version_fence.py::TestExactVersionCompare + TestVersionScopeIsolation",
        "evidence": "float 不可分大整数精确比较；跨表/跨实例同 ID 隔离；未知顺序 CONFLICT",
        "remaining": "ISOLATED：PG 版本账（asset_reporting_version_evidence）落库验证",
    },
    "RT1-019": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r05_scheduler_fixes.py::TestRunnableQueueOrdering",
        "evidence": "历史父先于 T1 子；独立 T1 不受父子约束；周期内派发顺序父先子后",
        "remaining": "无（离线即完整覆盖该回归）",
    },
    "RT1-020": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r05_scheduler_fixes.py::TestSameTableMultiTask",
        "evidence": "同表 T1/月重扫/回看/多窗全部保留派发，task_key 唯一不覆盖",
        "remaining": "无（离线即完整覆盖该回归）",
    },
    "RT1-021": {
        "executed_offline_part": "tests/reporting_pipeline_unit（contracts.validate_action）+ CLI plan 动作级就绪输出",
        "evidence": "REPORT_UNKNOWN 不阻塞 CAPTURE/STAGE/APPLY 动作判定；全链 validate_enable 语义保留",
        "remaining": "ISOLATED：路由级动作校验接调度实测",
    },
    "RT1-022": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r05_scheduler_fixes.py::TestHonestOverallStatus",
        "evidence": "熔断全跳过=WAITING_WITH_BACKLOG；run 返回 FAILED/QUARANTINED 计入失败；无任务=NO_WORK",
        "remaining": "ISOLATED 联调下的周期状态复核",
    },
    "RT1-023": {
        "executed_offline_part": "既有 test_quality_staging（组隔离+独立组继续）+ 逐表快照隔离计数测试",
        "evidence": "质量组隔离与 PENDING_PARENT 语义既有测试保持；快照 per_table 可查",
        "remaining": "ISOLATED：真实装载中的隔离组落 PG 账",
    },
    "RT1-024": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r05_scheduler_fixes.py::TestFrozenAnchorWindow",
        "evidence": "院区固定昨天半开窗；跨午夜新锚点=新业务日（重试须复用旧锚点）；naive 时钟拒绝",
        "remaining": "多时区源换算实测（R07）",
    },
    "RT1-025": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r02_durable_and_watermarks.py::TestContinuousCompletionCursor + test_r06_daily_report",
        "evidence": "历史缺口不阻塞日捕获、阻塞连续完成游标；日报两游标分开展示",
        "remaining": "ISOLATED：PG continuous_through 列与门禁落库验证",
    },
    "RT1-026": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r02_durable_and_watermarks.py::TestCoverageAgeReport",
        "evidence": "只扫当月=NO_HISTORY_VISIT；单月轮转=DEGRADED；全周期=WITHIN；未冻结=SCOPE_UNFROZEN",
        "remaining": "ISOLATED：月覆盖账真实重访记录",
    },
    "RT1-031": {
        "executed_offline_part": "tests/reporting_pipeline_unit/test_r06_daily_report.py",
        "evidence": "日报来自仓储（simulation 标记）；SLA_UNKNOWN 单列；载荷隐私白名单/敏感词拒绝",
        "remaining": "ISOLATED_PG_AND_LOCAL_HTTP：耐久状态+真实外发脱敏复核",
    },
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    fingerprints = {}
    for name, path in INPUTS.items():
        if path.exists():
            fingerprints[name] = {
                "path": str(path.relative_to(HERE)) if path.is_relative_to(HERE)
                else str(path.relative_to(HERE.parent)) if path.is_relative_to(HERE.parent)
                else str(path),
                "sha256": sha256_of(path),
            }
        else:
            fingerprints[name] = {"path": str(path), "missing": True}

    seed = json.loads(INPUTS["seed_77"].read_text(encoding="utf-8"))
    items = seed["items"]
    stats = {
        "total": len(items),
        "identity_unverified": 0,
        "engine_undecided": 0,
        "incremental_unresolved": 0,
        "deadline_unconfigured": 0,
        "secret_ref_unconfigured": 0,
        "dialysis_hint_mismatch": [],
        "enabled": 0,
    }
    per_item_pending: dict[str, list[str]] = {}
    for item in items:
        table = item["canonical_table"]
        pending: list[str] = []
        if item.get("engine") == "UNDECIDED":
            stats["engine_undecided"] += 1
            pending.append("engine=UNDECIDED")
        if item.get("incremental_strategy") == "UNRESOLVED":
            stats["incremental_unresolved"] += 1
            pending.append("incremental=UNRESOLVED")
        for src in item.get("source_candidates", []):
            if not src.get("current_identity_verified", False):
                stats["identity_unverified"] += 1
                pending.append(f"identity:{src['object_id']}")
            if src.get("source_group") == "dialysis" and src.get("database_hint") != "hdis":
                stats["dialysis_hint_mismatch"].append(
                    {
                        "table": table,
                        "object_id": src["object_id"],
                        "input_hint": src.get("database_hint"),
                        "frozen_hint": "hdis",
                    }
                )
                pending.append("dialysis_hint_corrected_to_hdis")
        if item.get("enabled"):
            stats["enabled"] += 1
        if pending:
            per_item_pending[table] = pending

    matrix = json.loads(INPUTS["acceptance_matrix_112"].read_text(encoding="utf-8"))
    matrix_summary = {
        "total": len(matrix["cases"]),
        "by_state": {},
        "mapping_note": (
            "112 条 NOT_RUN 保持；离线已实现的先由 RT1 证据覆盖对应主题，"
            "逐条映射随隔离/试点推进补 actual_evidence，不批量置 PASS"
        ),
    }
    for case in matrix["cases"]:
        state = case.get("execution_state", "NOT_RUN")
        matrix_summary["by_state"][state] = matrix_summary["by_state"].get(state, 0) + 1

    rt1_list_path = HERE / "整改任务与验收清单.json"
    rt1 = json.loads(rt1_list_path.read_text(encoding="utf-8"))
    rt1_states = {}
    for case in rt1.get("supplemental_acceptance_cases", []):
        cid = case["id"]
        env = case.get("environment", "")
        if cid in RT1_OFFLINE_EVIDENCE:
            executed = RT1_OFFLINE_EVIDENCE[cid]
            # 环境完全离线的场景标记 EXECUTED_OFFLINE；含隔离/真实部分的标记 PARTIAL_OFFLINE
            if executed["remaining"].startswith("无"):
                new_state = "EXECUTED_OFFLINE"
            else:
                new_state = "PARTIAL_OFFLINE_REMAINING_ISOLATED_OR_APPROVED"
            rt1_states[cid] = {
                "environment": env,
                "state_after_r0x": new_state,
                "offline_evidence": executed["executed_offline_part"],
                "evidence_note": executed["evidence"],
                "remaining": executed["remaining"],
            }
        else:
            rt1_states[cid] = {
                "environment": env,
                "state_after_r0x": case.get("execution_state", "NOT_RUN"),
                "offline_evidence": None,
                "remaining": "按环境依赖推进（隔离库/真实驱动/批准）",
            }

    freeze = {
        "kind": "R01_FROZEN_CONFIG_AND_INPUT_DIFF",
        "freeze_version": f"R01-FREEZE-{date.today().isoformat()}",
        "package_id": seed.get("package_id"),
        "input_fingerprints": fingerprints,
        "corrections": CORRECTIONS,
        "seed_gap_stats": stats,
        "per_item_pending_fields": per_item_pending,
        "original_112_cases_summary": matrix_summary,
        "rt1_case_states": rt1_states,
        "rules": [
            "本冻结件为执行端唯一配置引用；上游候选 JSON 变更须重跑本脚本生成新版本",
            "血透 frozen hdis 未经 R07 受控实测不得置 READ_READY=READY",
            "77 项 enabled=false 保持；启用走 TaskSpec.validate_enable 五层门禁",
            "旧 zip/旧提示词与本件冲突时以本件+最新证据为准",
        ],
        "no_production_authorization_granted": True,
    }
    out = HERE / f"R01_冻结配置与差异清单_{date.today().isoformat()}.json"
    out.write_text(
        json.dumps(freeze, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({
        "ok": True,
        "output": str(out),
        "items": stats["total"],
        "dialysis_corrected": len(stats["dialysis_hint_mismatch"]),
        "identity_unverified": stats["identity_unverified"],
        "rt1_offline_covered": len(RT1_OFFLINE_EVIDENCE),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
