"""E07 合成预检测试：工单闭环、日报分节、故障规则矩阵对拍、CLI 命令。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.manual_tickets import (
    ManualTicket,
    ReverifyEvidence,
    TicketRegistry,
    TicketTransitionError,
    seed_tickets_from_package,
)
from app.services.reporting_pipeline.recovery import FAULT_RULE_IMPLEMENTATION
from app.services.reporting_pipeline.reports import build_daily_report
from app.services.reporting_pipeline.repositories import InMemoryControlRepository
from app.services.reporting_pipeline.seed_loader import (
    PACKAGE_DIR,
    _load_json,
    load_seed_bundle,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


class TestTicketWorkflow(unittest.TestCase):
    def _ticket(self) -> ManualTicket:
        return ManualTicket(
            ticket_id="T-VIEW-1",
            tables=["EMR_TEST"],
            source_identity="ods__V_TEST",
            view_object="ODS.V_EMR_TEST",
            problem_category="TIME_BASIS",
            definition_fingerprint="a" * 64,
        )

    def test_user_fix_report_triggers_reverify_not_close(self):
        registry = TicketRegistry()
        registry.register(self._ticket())
        ticket = registry.report_fixed("T-VIEW-1")
        self.assertEqual(ticket.state, "REVERIFYING")
        # 用户说改完不能直接 CLOSED
        with self.assertRaises(TicketTransitionError):
            ticket.transition("CLOSED", reason="越权关单")

    def test_verify_requires_evidence(self):
        registry = TicketRegistry()
        registry.register(self._ticket())
        with self.assertRaises(TicketTransitionError):
            registry.get("T-VIEW-1").transition(
                "VERIFIED", reason="无证据不允许"
            )

    def test_definition_changed_forces_reextract(self):
        registry = TicketRegistry()
        registry.register(self._ticket())
        registry.report_fixed("T-VIEW-1")
        decision = registry.verify(
            "T-VIEW-1",
            ReverifyEvidence(
                new_definition_fingerprint="b" * 64,
                new_dependency_fingerprints={},
                field_check_passed=True,
                upstream_downstream_checked=True,
                acceptance_result_ref="R189:reverify/xxx.json",
            ),
            stage_fingerprint_matches_current=True,
        )
        self.assertEqual(decision["decision"], "REEXTRACT_AFFECTED_SCOPE")
        self.assertEqual(decision["state"], "VERIFIED")

    def test_unchanged_definition_stage_replay_with_check(self):
        registry = TicketRegistry()
        ticket = self._ticket()
        registry.register(ticket)
        registry.report_fixed("T-VIEW-1")
        decision = registry.verify(
            "T-VIEW-1",
            ReverifyEvidence(
                new_definition_fingerprint=ticket.definition_fingerprint,
                new_dependency_fingerprints={},
                field_check_passed=True,
                upstream_downstream_checked=True,
                acceptance_result_ref="R189:reverify/ok.json",
            ),
            stage_fingerprint_matches_current=True,
        )
        self.assertEqual(decision["decision"], "REPLAY_OLD_STAGE_WITH_CHECK")

    def test_stale_stage_not_reused(self):
        registry = TicketRegistry()
        ticket = self._ticket()
        registry.register(ticket)
        registry.report_fixed("T-VIEW-1")
        decision = registry.verify(
            "T-VIEW-1",
            ReverifyEvidence(
                new_definition_fingerprint=ticket.definition_fingerprint,
                new_dependency_fingerprints={},
                field_check_passed=True,
                upstream_downstream_checked=True,
                acceptance_result_ref="R189:reverify/ok.json",
            ),
            stage_fingerprint_matches_current=False,  # 旧 stage 与当前定义不一致
        )
        self.assertEqual(decision["decision"], "REEXTRACT_AFFECTED_SCOPE")

    def test_reopen_when_checks_fail(self):
        registry = TicketRegistry()
        registry.register(self._ticket())
        registry.report_fixed("T-VIEW-1")
        decision = registry.verify(
            "T-VIEW-1",
            ReverifyEvidence(
                new_definition_fingerprint="b" * 64,
                new_dependency_fingerprints={},
                field_check_passed=False,
                upstream_downstream_checked=True,
                acceptance_result_ref="x",
            ),
            stage_fingerprint_matches_current=True,
        )
        self.assertEqual(decision["state"], "REOPENED")

    def test_seed_tickets_loaded_open(self):
        seed_doc = _load_json(PACKAGE_DIR / "E01已知人工工单种子.json")
        registry = seed_tickets_from_package(seed_doc)
        self.assertEqual(len(registry.all_tickets()), 6)
        for ticket in registry.all_tickets():
            self.assertEqual(ticket.state, "OPEN")
            self.assertEqual(ticket.owner_role, "USER_HUMAN")


class TestDailyReport(unittest.TestCase):
    def setUp(self):
        self.bundle = load_seed_bundle(PACKAGE_DIR)

    def _report(self) -> dict:
        report = build_daily_report(
            business_day="2026-10-19",
            repository=InMemoryControlRepository(),
            bundle=self.bundle,
        )
        return report.to_dict()

    def test_required_sections_present(self):
        payload = self._report()
        for section in (
            "failed_windows_and_next_retry", "commit_unknown_tables",
            "affected_child_groups", "monthly_coverage_overdue",
            "deadline_unconfigured", "relay_delivery_state", "denominators",
        ):
            self.assertIn(section, payload)

    def test_deadline_unconfigured_sla_unknown(self):
        section = self._report()["deadline_unconfigured"]
        self.assertEqual(len(section["tables"]), 77)
        self.assertEqual(section["sla"], "SLA_UNKNOWN")
        self.assertIn("A12", section["todo"])

    def test_denominators_separated(self):
        denom = self._report()["denominators"]
        self.assertEqual(denom["canonical_items_total"], 77)
        self.assertEqual(denom["applicable_now"], 76)
        self.assertEqual(denom["not_provided_pending_applicability"], 1)
        self.assertEqual(denom["approved_for_production"], 0)

    def test_relay_waiting_integration(self):
        relay = self._report()["relay_delivery_state"]
        self.assertEqual(relay["integration_state"], "WAITING_INTEGRATION_SETUP")
        self.assertIn("202", relay["note"])

    def test_rescan_scope_unfrozen_explicit(self):
        coverage = self._report()["monthly_coverage_overdue"]
        self.assertEqual(coverage["scope_state"], "SCOPE_UNFROZEN_E01_TO_FILL")
        self.assertEqual(
            sorted(coverage["rescan_tables"]),
            ["EMR_DOC_ORDER_CHECK", "EMR_IN_FEE_INFO_CHILD"],
        )


class TestFaultMatrix(unittest.TestCase):
    def test_every_machine_rule_mapped_to_implementation(self):
        """故障隔离与继续执行规则.json 的每条 error 都有实现落点与测试。"""
        rules_doc = _load_json(PACKAGE_DIR / "故障隔离与继续执行规则.json")
        rule_errors = {rule["error"] for rule in rules_doc["rules"]}
        mapped = set(FAULT_RULE_IMPLEMENTATION)
        self.assertEqual(
            rule_errors, mapped,
            f"规则未映射: {rule_errors - mapped}; 映射多余: {mapped - rule_errors}",
        )
        for error, entry in FAULT_RULE_IMPLEMENTATION.items():
            self.assertTrue(entry["implemented_in"], error)
            self.assertTrue(entry["tested_by"], error)

    def test_default_policy_is_continue_independent(self):
        rules_doc = _load_json(PACKAGE_DIR / "故障隔离与继续执行规则.json")
        self.assertEqual(rules_doc["default"], "CONTINUE_INDEPENDENT_SCOPES")
        self.assertFalse(rules_doc["failure_terminal_success_allowed"])
        self.assertFalse(rules_doc["silent_skip_allowed"])


class TestCliCommands(unittest.TestCase):
    """CLI daily-report / ticket-export（进程内调用，不触网络/生产）。"""

    def test_daily_report_command(self):
        from scripts.reporting_ctl import main

        # A02：无 --state-db 且未显式允许模拟 → 拒绝静默回退模拟（exit 2）
        exit_code = main([
            "--config", str(PACKAGE_DIR), "daily-report",
            "--business-day", "2026-10-19",
        ])
        self.assertEqual(exit_code, 2)
        # 显式 --allow-simulation 才走内存模拟（exit 0，输出带 simulation）
        exit_code = main([
            "--config", str(PACKAGE_DIR), "daily-report",
            "--business-day", "2026-10-19", "--allow-simulation",
        ])
        self.assertEqual(exit_code, 0)

    def test_daily_report_default_day_not_hardcoded(self):
        """A02：默认业务日=院区时区昨天，不再硬编码 2026-10-19。"""
        from scripts import reporting_ctl

        parser = reporting_ctl.build_parser()
        sub = next(
            a for a in parser._subparsers._group_actions[0].choices.items()
            if a[0] == "daily-report"
        )[1]
        self.assertIsNone(
            next(
                a for a in sub._actions if a.dest == "business_day"
            ).default
        )

    def test_ticket_export_command(self):
        from scripts.reporting_ctl import main

        out = _REPO_ROOT / "_scratch" / "ticket_export_test.json"
        out.parent.mkdir(exist_ok=True)
        exit_code = main([
            "--config", str(PACKAGE_DIR), "ticket-export", "--output", str(out),
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue(out.exists())

    def test_not_implemented_command_explicit(self):
        # A02 后六真实命令已实现：本测试改为验证"缺真实装配输入即拒绝"
        from scripts.reporting_ctl import main

        # 缺必填参数（--batch/--approval-ref）→ argparse 用法错误（exit 2）
        with self.assertRaises(SystemExit) as ctx:
            main(["--config", str(PACKAGE_DIR), "apply"])
        self.assertEqual(ctx.exception.code, 2)
        # 参数齐但缺状态库/暂存根（未允许模拟）→ 装配拒绝（exit 2）
        exit_code = main([
            "--config", str(PACKAGE_DIR), "apply",
            "--batch", "B-NOASSEMBLY", "--approval-ref", "REF-X",
        ])
        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
