"""Regress real assembly failures using injected in-memory ports only."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.reporting_pipeline import contracts as c
from app.services.reporting_pipeline.adapters.python_reader import ReadPage
from app.services.reporting_pipeline.apply_port import ApplyPlan
from app.services.reporting_pipeline.apply_port import (
    ApplyPort, InMemoryApplyExecutor, InMemoryVersionRegistry, VersionGuard,
)
from app.services.reporting_pipeline.durable_staging import DurableFileStageStore
from app.services.reporting_pipeline.production_runtime import (
    AssemblyInputs, AssemblyRefused, ProductionAssembly, TargetBindingConfig,
    business_window,
)
from app.services.reporting_pipeline.repositories import InMemoryControlRepository
from app.services.reporting_pipeline.target_executor import FakeTargetConnection, SqlTargetApplyExecutor
from test_a01_a05_k_fixes import _verified_spec, _SimBundle, _apply_request, _EXEC_CONFIG


def assembly_for(tmp_path, rows):
    spec = _verified_spec(enabled=True)
    spec.projection += [
        c.ProjectionField("AMOUNT", "NUMBER(18,2)", 3, type_verified=True),
        c.ProjectionField("BIZ_TIME", "DATE", 4, type_verified=True),
    ]
    source = SimpleNamespace(physical_source="ods", fetch_page=lambda *a, **kw: ReadPage(rows=rows, row_bytes=256, has_more=False))
    inputs = AssemblyInputs(
        bundle=_SimBundle(spec), repository=InMemoryControlRepository(),
        stage_store=DurableFileStageStore(tmp_path), row_source_factory=lambda _: source,
    )
    binding = TargetBindingConfig("10.10.8.74:1521/orcl", "DBOPER", spec.canonical_table,
                                  ("ID",), ("ID", "V1", "AMOUNT", "BIZ_TIME"))
    # Explicitly inject an in-memory repository into the real action path;
    # public build(real=True) rejects this repository in production.
    return ProductionAssembly(inputs, simulation=False), binding


def test_real_capture_preserves_projection_types_and_definition(tmp_path):
    when = datetime(2026, 10, 21, 9, 0)
    row = ("synthetic", "text", Decimal("123456789.12"), when)
    assembly, binding = assembly_for(tmp_path, [row])
    result = assembly.capture(table=binding.table, business_day="2026-10-21", binding=binding)
    manifest = assembly._repo().select_manifest(result["batch_id"])
    assert manifest.definition_fingerprint == "a" * 64
    assert assembly._staged_rows(result["batch_id"], result["attempt_id"]) == [dict(zip(binding.write_columns, row))]
    verified = assembly.verify(batch_id=result["batch_id"])
    assert verified["ok"], verified
    assert verified["quality"]["valid_rows"] == 1


def test_capture_wrong_width_refuses_instead_of_truncating(tmp_path):
    assembly, binding = assembly_for(tmp_path, [("synthetic", "text", "extra")])
    with pytest.raises(AssemblyRefused, match="ROW_WIDTH"):
        assembly.capture(table=binding.table, business_day="2026-10-21", binding=binding)
    assert not list(tmp_path.rglob("complete.json"))


def test_business_window_is_clinic_day():
    window = business_window("2026-10-21")
    assert window.start.utcoffset() == timedelta(hours=8)
    assert window.start.astimezone(timezone.utc) == datetime(2026, 10, 20, 16, tzinfo=timezone.utc)
    assert window.end_exclusive - window.start == timedelta(days=1)


def test_wrong_target_refuses_before_source_or_state(tmp_path):
    assembly, binding = assembly_for(tmp_path, [])
    binding.tenant = "OTHER_TENANT"
    with pytest.raises(AssemblyRefused, match="TARGET_BINDING"):
        assembly.capture(table=binding.table, business_day="2026-10-21", binding=binding)
    assert assembly._repo().list_batches() == []


def test_datax_route_never_silently_uses_python(tmp_path):
    assembly, binding = assembly_for(tmp_path, [])
    assembly.bundle.tasks[0].engine = c.Engine.DATAX
    with pytest.raises(AssemblyRefused, match="CAPTURE_ROUTE"):
        assembly.capture(table=binding.table, business_day="2026-10-21", binding=binding)
    assert assembly._repo().list_batches() == []


def test_real_apply_cannot_self_approve_from_json(tmp_path):
    assembly, binding = assembly_for(tmp_path, [])
    result = assembly.capture(table=binding.table, business_day="2026-10-21", binding=binding)
    assembly.verify(batch_id=result["batch_id"])
    assembly.inputs.approval_refs = ("caller-controlled",)
    with pytest.raises(AssemblyRefused, match="production_apply_port"):
        assembly.apply(batch_id=result["batch_id"], binding=binding, approval_ref="caller-controlled")
    assert assembly._repo().get_batch(result["batch_id"]).state == c.BatchState.VALIDATED


def test_preview_connection_released_before_next_transaction(tmp_path):
    assembly, binding = assembly_for(tmp_path, [])
    events = []
    class Connection(FakeTargetConnection):
        def begin(self):
            events.append("begin")
            super().begin()
        def rollback(self):
            events.append("rollback")
            super().rollback()
        def close(self):
            events.append("close")
    assembly.inputs.target_connection_factory = Connection
    assert assembly._read_target_snapshot(binding, []) == {}
    assert events == ["begin", "rollback", "close"]


@pytest.mark.parametrize("action,existing", [("INSERT", {("k",): {"K1": "k", "V1": "other"}}), ("UPDATE", {})])
def test_concurrent_target_change_rolls_back_without_success_receipt(action, existing):
    conn = FakeTargetConnection(existing)
    request = _apply_request([{"K1": "k", "V1": "new"}])
    executor = SqlTargetApplyExecutor(lambda: conn, _EXEC_CONFIG, simulation=True)
    with pytest.raises(c.ContractViolation, match="TARGET_CHANGED"):
        executor.execute(request, ApplyPlan([(("k",), action)], {action: 1}))
    assert conn.receipts == {}
    assert conn.rows == existing
    assert not conn.in_transaction


def test_stale_preview_content_cannot_overwrite_new_target():
    old = {("k",): {"K1": "k", "V1": "old"}}
    current = {("k",): {"K1": "k", "V1": "concurrent-change"}}
    conn = FakeTargetConnection(current)
    executor = SqlTargetApplyExecutor(lambda: conn, _EXEC_CONFIG, simulation=True, expected_target_rows=old)
    with pytest.raises(c.ContractViolation, match="TARGET_CHANGED"):
        executor.execute(_apply_request([{"K1": "k", "V1": "new"}]), ApplyPlan([(("k",), "UPDATE")], {}))
    assert conn.rows == current
    assert conn.receipts == {}


def test_lost_fence_before_commit_rolls_back():
    conn = FakeTargetConnection()
    calls = []
    def fence():
        calls.append(1)
        if len(calls) == 2:
            raise c.ContractViolation("expired fence")
    executor = SqlTargetApplyExecutor(lambda: conn, _EXEC_CONFIG, simulation=True, fence_check=fence)
    with pytest.raises(c.ContractViolation, match="expired"):
        executor.execute(_apply_request([{"K1": "k", "V1": "new"}]), ApplyPlan([(("k",), "INSERT")], {}))
    assert conn.rows == {} and conn.receipts == {}


def test_short_dml_count_cannot_commit_receipt():
    class ShortWriter(FakeTargetConnection):
        def insert_rows(self, *args):
            super().insert_rows(*args)
            return 0
    conn = ShortWriter()
    executor = SqlTargetApplyExecutor(lambda: conn, _EXEC_CONFIG, simulation=True)
    with pytest.raises(c.ContractViolation, match="DML_ROWCOUNT_MISMATCH"):
        executor.execute(_apply_request([{"K1": "k", "V1": "new"}]), ApplyPlan([(("k",), "INSERT")], {}))
    assert conn.rows == {} and conn.receipts == {}


def test_month_replace_requires_explicit_scope_keys():
    """批1-5：REPLACE_MONTH 已实现（同事务先删后插），但缺显式范围键清单
    仍拒绝——不得按不存在列删除。原"仅支持MERGE"拒绝语义已由实现取代。"""
    from dataclasses import replace
    executor = SqlTargetApplyExecutor(lambda: pytest.fail("must not open target"), _EXEC_CONFIG, simulation=True)
    with pytest.raises(c.ContractViolation, match="REPLACE_MONTH"):
        executor.execute(replace(_apply_request([]), mode="REPLACE_MONTH"), ApplyPlan([], {}))


@pytest.mark.parametrize("actions", [[], [(("k",), "CONFLICT")]])
def test_incomplete_or_conflicting_plan_cannot_claim_success(actions):
    executor = SqlTargetApplyExecutor(lambda: pytest.fail("must not open target"), _EXEC_CONFIG, simulation=True)
    with pytest.raises(c.ContractViolation):
        executor.execute(_apply_request([{"K1": "k", "V1": "new"}]), ApplyPlan(actions, {}))


def test_cli_doctor_does_not_claim_production_ready(capsys):
    from scripts.reporting_ctl import main
    assert main(["doctor"]) == 2
    assert '"production_ready": false' in capsys.readouterr().out


def test_real_build_rejects_memory_repository(tmp_path):
    assembly, _ = assembly_for(tmp_path, [])
    with pytest.raises(AssemblyRefused, match="VOLATILE_STATE"):
        ProductionAssembly.build(assembly.inputs)


def test_stage_tampering_after_complete_is_rejected(tmp_path):
    assembly, binding = assembly_for(tmp_path, [("synthetic", "text", Decimal("1"), datetime(2026, 10, 21))])
    result = assembly.capture(table=binding.table, business_day="2026-10-21", binding=binding)
    path = next(tmp_path.rglob("*.bin"))
    path.write_bytes(path.read_bytes().replace(b"synthetic", b"tampered!"))
    with pytest.raises(c.ContractViolation, match="哈希"):
        assembly.verify(batch_id=result["batch_id"])


def test_config_changed_after_capture_requires_revalidation(tmp_path):
    assembly, binding = assembly_for(tmp_path, [])
    result = assembly.capture(table=binding.table, business_day="2026-10-21", binding=binding)
    assembly.bundle.tasks[0].config_version = "new-version"
    with pytest.raises(AssemblyRefused, match="CONFIG_DRIFT"):
        assembly.verify(batch_id=result["batch_id"])


def test_production_version_registry_scopes_same_id_by_target_table():
    from dataclasses import replace
    class Verifier:
        trust_level = "platform"
        def verify(self, **kwargs):
            return SimpleNamespace(approved=True)
    class TestRegistry:
        # A protocol fake for scope isolation only, never a production store.
        def __init__(self):
            self.memory = InMemoryVersionRegistry()
        def current_version(self, *args):
            return self.memory.current_version(*args)
        def register_version(self, *args, **kwargs):
            return self.memory.register_version(*args, **kwargs)
    registry = TestRegistry()
    port = ApplyPort(
        whitelisted_executors=["sim-apply-1"], approval_verifier=Verifier(),
        version_guard=VersionGuard(registry), lease_validator=lambda *args: None,
        production_mode=True,
    )
    request = replace(
        _apply_request([{"K1": "k", "V1": "first"}]), executor_id="sim-apply-1",
        target_object="10.10.8.74:1521/orcl.DBOPER.TABLE_A",
        lease_resource="target:A", fencing_token=1, version_order="10", version_kind="int",
    )
    port.apply(request, InMemoryApplyExecutor(), {})
    second = replace(request, target_object="10.10.8.74:1521/orcl.DBOPER.TABLE_B", version_order="1")
    plan = port.preview(second, {("k",): {"K1": "k", "V1": "old"}})
    assert plan.counts == {"UPDATE": 1}  # TABLE_A's version=10 must not block TABLE_B.


def test_explicit_memory_version_registry_is_not_durable():
    assert not VersionGuard(InMemoryVersionRegistry()).durable


def test_reconcile_diagnostics_do_not_expose_row_keys_or_values(tmp_path):
    assembly, binding = assembly_for(tmp_path, [])
    assembly.simulation = True
    result = assembly.capture(
        table=binding.table, business_day="2026-10-21", binding=binding,
        sim_rows_provider=lambda: [{"ID": "synthetic-private-key", "V1": "source-private-value"}],
    )
    assembly.verify(batch_id=result["batch_id"])
    assembly.inputs.approval_refs = ("test",)
    assembly.apply(batch_id=result["batch_id"], binding=binding, approval_ref="test")
    output = assembly.reconcile(batch_id=result["batch_id"], binding=binding,
        sim_target_rows={("synthetic-private-key",): {"ID": "synthetic-private-key", "V1": "target-private-value"}})
    assert not output["ok"]
    assert output["diff_sample"] == [{"columns": ["V1"]}]
    assert "private" not in str(output)
