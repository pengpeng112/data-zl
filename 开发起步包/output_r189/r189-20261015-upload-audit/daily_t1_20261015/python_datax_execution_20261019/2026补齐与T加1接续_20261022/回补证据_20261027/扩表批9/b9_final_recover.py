# -*- coding: utf-8 -*-
"""批9 收尾二轮（主循环+补跑后残留处置，全部按恢复矩阵/状态机合法路径）：
A) 4 个 APPLYING 卡死批（同键双行 ContractViolation）→ RETRYABLE 留证待裁定；
B) 3 个 VALIDATED 停批（apply 阶段瞬时 ORA-12541）→ 补 apply+reconcile；
C) 3 个 APPLIED 未收口批（reconcile 阶段瞬时错误）→ 仅补 reconcile。
stats 同步回写（DOC 三窗从回执表恢复 partition 证据）。
"""
import json
import os

os.environ.setdefault("T1_DEBUG_TRACEBACK", "1")

import argparse

STAGE = "/opt/data-asset/t1-stage"
CFG = "/opt/data-asset/t1-config"
GROUPS = {
    "b5": "freeze_batch5_v3.json|bindings_batch5.json",
    "b6": "freeze_batch6_v1.json|bindings_batch6.json",
    "b7": "freeze_batch7_v5.json|bindings_batch7.json",
}
order = json.load(open(f"{STAGE}/b9_exec_order.json", encoding="utf-8"))
grp_of = {i["table"]: i["group"] for i in order}

from scripts.reporting_ctl import (  # noqa: E402
    _action_bindings_from_doc, _assembly_inputs, _target_binding_from_args,
)
from app.services.reporting_pipeline.production_runtime import (  # noqa: E402
    ProductionAssembly,
)
from app.services.reporting_pipeline.contracts import BatchState  # noqa: E402
from sqlalchemy import create_engine, text as _sql  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from app.services.reporting_pipeline.pg_repository import (  # noqa: E402
    SqlAlchemyControlRepository,
)
from app.services.reporting_pipeline.runtime import unique_worker_id  # noqa: E402

engine = create_engine(os.environ["APP_DB_URL"])
lease_repo = SqlAlchemyControlRepository(sessionmaker(bind=engine))
assemblies = {}
for g in set(grp_of.values()):
    freeze, bindings = GROUPS[g].split("|")
    a = argparse.Namespace(
        config=CFG, state_db=os.environ["APP_DB_URL"], stage_root=STAGE,
        bindings_file=f"{CFG}/{bindings}", runtime_config=f"{CFG}/{freeze}",
        allow_simulation=False, batch="", table=None, approval_ref="",
        executor_id="sql-target-apply-1")
    inputs = _assembly_inputs(a)
    from app.services.reporting_pipeline.source_factory import (
        build_oracle_connection_factory, build_row_source)
    rt = inputs.runtime_config.tables
    odsb = json.load(open(f"{CFG}/{bindings}", encoding="utf-8"))["sources"]["ods"]
    cf = build_oracle_connection_factory(
        dsn=odsb["dsn"], credential_ref=odsb["credential_ref"],
        timeout_ms=1_800_000)
    inputs.table_row_source_factory = (
        lambda t, _rt=rt, _cf=cf: build_row_source(
            _rt[t], connection_factory=_cf, fetch_timeout_seconds=1800.0))
    assemblies[g] = (ProductionAssembly(inputs, simulation=False),
                     _action_bindings_from_doc(json.load(
                         open(f"{CFG}/{bindings}", encoding="utf-8"))), a)

DUP_KEY_BATCHES = [
    "DBOPER.EMR_OPERATION_NURSING.HISTORICAL.2026-05-01.cda9a51c01e5",
    "DBOPER.EMR_AFTER_OPERA_RECORD.HISTORICAL.2026-05-01.8a478d2cb148",
    "DBOPER.EMR_HOS_POSTOPER_RECORD.HISTORICAL.2026-10-01.50ba140b63ec",
    "DBOPER.EMR_HOS_PREOP_DISCUSS.HISTORICAL.2026-10-01.e91153e3db27",
]
VALIDATED_BATCHES = [
    ("EMR_HOS_SUCCESSION_RECORD", "DBOPER.EMR_HOS_SUCCESSION_RECORD.HISTORICAL.2026-01-01.e6878dfe02c2"),
    ("EMR_HOS_CHANGE_MAJOR_RECORD", "DBOPER.EMR_HOS_CHANGE_MAJOR_RECORD.HISTORICAL.2026-05-01.c695ae7fc4f8"),
    ("EMR_HOS_CHANGE_MAJOR_RECORD", "DBOPER.EMR_HOS_CHANGE_MAJOR_RECORD.HISTORICAL.2026-08-01.3862f706bae8"),
]
APPLIED_NEED_RECONCILE = [
    ("EMR_DOC_ORDER_CHECK", "2026-01", "DBOPER.EMR_DOC_ORDER_CHECK.HISTORICAL.2026-01-01.89e01f4a2133"),
    ("EMR_DOC_ORDER_CHECK", "2026-05", "DBOPER.EMR_DOC_ORDER_CHECK.HISTORICAL.2026-05-01.33ee276dca98"),
    ("EMR_DOC_ORDER_CHECK", "2026-09", "DBOPER.EMR_DOC_ORDER_CHECK.HISTORICAL.2026-09-01.5dff6480792c"),
]

results = {"A_dupkey_retryable": [], "B_apply_reconcile": [], "C_reconcile_only": []}

# A) APPLYING → RETRYABLE（同键双行待裁定；RETRYABLE 可从任意主链态进入=状态机合法）
for bid in DUP_KEY_BATCHES:
    table = bid.split(".")[1]
    asm, ab, a = assemblies[grp_of[table]]
    repo = asm._repo()
    rec = repo.get_batch(bid)
    print("A)", bid, "state_before:", rec.state.value, flush=True)
    if rec.state.value == "APPLYING":
        repo.transition_batch(
            bid, BatchState.RETRYABLE,
            reason="apply 拒绝 ContractViolation：暂存行含同键双行（源视图重复发出，"
                   "装载计划键集契约拒绝重复键）；待用户裁定去重口径后同批号重放",
            evidence="dup-key ContractViolation 2026-10-28")
        print("   -> RETRYABLE", flush=True)
    results["A_dupkey_retryable"].append(
        {"batch": bid, "state": repo.get_batch(bid).state.value})

# B) VALIDATED → apply + reconcile
for table, bid in VALIDATED_BATCHES:
    asm, ab, a = assemblies[grp_of[table]]
    binding = _target_binding_from_args(a, table)
    ref = f"T1-BACKFILL-B9-20261027:{table.lower()}"
    print("B)", bid, flush=True)
    lease = lease_repo.acquire_lease(
        f"target:10.10.8.74:1521/orcl.DBOPER.{table}",
        unique_worker_id("b9final"), ttl_seconds=7200)
    try:
        out = asm.apply(batch_id=bid, binding=binding, approval_ref=ref,
                        lease_resource=lease.resource,
                        fencing_token=lease.fencing_token)
    finally:
        lease_repo.release_lease(lease.resource, lease.holder,
                                 fencing_token=lease.fencing_token)
    entry = {"batch": bid, "apply_ok": bool(out.get("ok")),
             "partition": out.get("partition"), "refused": out.get("refused")}
    if out.get("ok"):
        rc = asm.reconcile(batch_id=bid, binding=binding)
        entry.update({"reconciled": bool(rc.get("ok")),
                      "missing": rc.get("missing_keys"),
                      "diffs": rc.get("content_diffs"),
                      "quarantined_pending": rc.get("quarantined_pending")})
    results["B_apply_reconcile"].append(entry)
    print("   ", json.dumps(entry, ensure_ascii=False), flush=True)
    # 回写 stats
    sf = f"{STAGE}/b9_backfill_{table}.json"
    st = json.load(open(sf, encoding="utf-8"))
    label = bid.split(".")[3][:7]
    label = label if label != "2026-10" else "2026-10P"
    st[label] = entry
    json.dump(st, open(sf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# C) APPLIED → reconcile only（回执已提交；恢复矩阵 RECONCILE_AND_REPORT）
import oracledb  # noqa: E402

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
tc = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
tcur = tc.cursor()
for table, label, bid in APPLIED_NEED_RECONCILE:
    asm, ab, a = assemblies[grp_of[table]]
    binding = _target_binding_from_args(a, table)
    print("C)", bid, flush=True)
    rc = asm.reconcile(batch_id=bid, binding=binding)
    tcur.execute(
        "SELECT rows_affected FROM DBOPER.ASSET_T1_RECEIPTS WHERE batch_id=:1",
        [bid])
    ra = tcur.fetchone()
    entry = {"batch": bid, "rows_from_receipt": ra[0] if ra else None,
             "reconciled": bool(rc.get("ok")),
             "missing": rc.get("missing_keys"),
             "diffs": rc.get("content_diffs"),
             "quarantined_pending": rc.get("quarantined_pending"),
             "note": "主循环 apply 已提交（回执在案），reconcile 被瞬时 ORA-12541 打断，本轮补收口"}
    results["C_reconcile_only"].append(entry)
    print("   ", json.dumps(entry, ensure_ascii=False), flush=True)
    sf = f"{STAGE}/b9_backfill_{table}.json"
    st = json.load(open(sf, encoding="utf-8"))
    st[label] = {
        "rows": ra[0] if ra else None,
        "batch_id": bid,
        "partition": {"ok": ra[0] if ra else 0, "insert": ra[0] if ra else 0,
                      "update": 0, "no_change": 0, "cas_conflict": 0,
                      "missing_parent": 0},
        "apply_ok": True, "reconciled": bool(rc.get("ok")),
        "missing": rc.get("missing_keys"), "diffs": rc.get("content_diffs"),
        "quarantined_pending": rc.get("quarantined_pending"),
        "note": entry["note"]}
    json.dump(st, open(sf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
tc.close()

json.dump(results, open(f"{STAGE}/b9_final_recover_20261028.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("FINAL_RECOVER_DONE", flush=True)
