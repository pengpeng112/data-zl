# -*- coding: utf-8 -*-
"""A03/PA7 执行器真实事务验收（隔离 PG，8.83 data_asset_test）。

SqlTargetApplyExecutor 的 TargetConnection 协议用真 PostgreSQL 实现：
- 同事务回执：业务 DML 与回执原子提交（回执失败→业务行一并回滚）；
- SYSTEM_TIME：目标库时钟（SELECT now()），非应用时钟；
- 行锁围栏：两个真实会话，未提交锁持有者挡住第二个写者（lock_timeout）；
- 幂等重放：同 operation_id 重放返回原回执，不重写业务行；
- COMMIT_UNKNOWN：应答丢失（确定性 ground truth=已回滚）→ committed=None，
  重放走全新执行并干净提交。

边界声明：本文件是**真 RDBMS 事务证明**（真实行锁/原子性/目标时钟），
不是 Oracle 方言证明（oracledb 驱动行为、Oracle 锁语义差异仍待授权的
隔离 Oracle schema）；不以 SQLite 冒充（主计划 §四-A04 红线）。

前置：source tools/dev_env.sh 且 APP_TEST_DB_URL 指向 data_asset_test；
未满足时整目录 SKIP，不冒充通过。
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text

from app.services.reporting_pipeline.apply_port import (
    ApplyPort,
    ApplyRequest,
    INSERT,
    UPDATE,
)
from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    EndReason,
    RowClassification,
)
from app.services.reporting_pipeline.readback_types import ColumnMeta
from app.services.reporting_pipeline.target_executor import (
    AmbiguousCommit,
    ExecutorTargetConfig,
    SqlTargetApplyExecutor,
    stable_operation_id,
)

TEST_URL = os.environ.get("APP_TEST_DB_URL", "")
ISOLATED = bool(TEST_URL) and "data_asset_test" in TEST_URL

SCHEMA = "t1_exec_it"
TABLE = f"{SCHEMA}.emr_test_table"
RECEIPTS = f"{SCHEMA}.asset_receipts_it"

EXEC_CONFIG = ExecutorTargetConfig(
    target_instance="data_asset_test", tenant="t1_exec_it",
    table=TABLE, key_columns=("K1",), write_columns=("K1", "V1"),
    system_time_column="SYSTEM_TIME", receipt_table=RECEIPTS,
)


class PgTargetConnection:
    """TargetConnection 协议的 PostgreSQL 实现（隔离验收用）。

    commit_answer_lost=True 时模拟"COMMIT 已发出但应答丢失"：
    确定性 ground truth = 实际回滚（与单元级 FakeTargetConnection 同语义，
    但回滚发生在真实数据库会话上）。
    """

    def __init__(self, engine, *, lock_timeout_seconds: int = 10,
                 commit_answer_lost: bool = False) -> None:
        self._engine = engine
        self._conn = engine.connect()
        self._tx = None
        self._lock_timeout = lock_timeout_seconds
        self._commit_answer_lost = commit_answer_lost

    # -- 协议实现 -------------------------------------------------------
    def begin(self) -> None:
        from sqlalchemy import text as _t

        self._tx = self._conn.begin()
        self._conn.execute(_t(f"SET LOCAL lock_timeout = '{self._lock_timeout}s'"))

    def lock_and_read_rows(self, table, key_columns, keys):
        if not keys:
            return {}
        cols = ", ".join(f'"{c}"' for c in key_columns)
        flat = [k[0] if len(key_columns) == 1 else k for k in keys]
        rows = self._conn.execute(
            text(f'SELECT * FROM {table} WHERE ({cols}) = ANY(:keys) FOR UPDATE'),
            {"keys": flat if len(key_columns) == 1 else [list(k) for k in keys]},
        ).mappings().all()
        return {tuple(r[c] for c in key_columns): dict(r) for r in rows}

    def current_timestamp(self) -> datetime:
        return self._conn.execute(text("SELECT now()")).scalar()

    def insert_rows(self, table, columns, rows) -> int:
        if not rows:
            return 0
        collist = ", ".join(f'"{c}"' for c in columns)
        ph = ", ".join(f":{c}" for c in columns)
        result = self._conn.execute(
            text(f'INSERT INTO {table} ({collist}) VALUES ({ph})'),
            [dict(r) for r in rows],
        )
        return result.rowcount

    def update_rows(self, table, columns, rows, *, key_columns) -> int:
        if not rows:
            return 0
        setlist = ", ".join(f'"{c}" = :{c}' for c in columns if c not in key_columns)
        where = " AND ".join(f'"{c}" = :{c}' for c in key_columns)
        result = self._conn.execute(
            text(f'UPDATE {table} SET {setlist} WHERE {where}'),
            [dict(r) for r in rows],
        )
        return result.rowcount

    def find_receipt(self, receipt_table, operation_id):
        row = self._conn.execute(
            text(f'SELECT * FROM {receipt_table} WHERE operation_id = :oid'),
            {"oid": operation_id},
        ).mappings().first()
        return dict(row) if row else None

    def insert_receipt(self, receipt_table, receipt) -> None:
        cols = list(receipt.keys())
        collist = ", ".join(f'"{c}"' for c in cols)
        ph = ", ".join(f":{c}" for c in cols)
        self._conn.execute(
            text(f'INSERT INTO {receipt_table} ({collist}) VALUES ({ph})'),
            dict(receipt),
        )

    def commit(self) -> bool:
        if self._commit_answer_lost:
            # 应答丢失 ground truth=实际未提交：真实会话回滚后抛 Ambiguous
            self._tx.rollback()
            self._conn.close()
            raise AmbiguousCommit("COMMIT 应答丢失（隔离测试注入）")
        self._tx.commit()
        self._conn.close()
        return True

    def rollback(self) -> None:
        try:
            if self._tx is not None:
                self._tx.rollback()
        finally:
            self._conn.close()


def _apply_request(rows, batch_id="B-EXECIT-0"):
    manifest = BatchManifest(
        batch_id=batch_id, attempt_id="A1", task_id="EMR_TEST_TABLE",
        config_version="v1", definition_fingerprint=None,
        source_identity="s", window_fingerprint="win:x/y",
        source_visibility_cutoff="cut",
        rows=RowClassification(source_read_rows=len(rows), valid=len(rows)),
        pagination_complete=True, end_reason=EndReason.WINDOW_COMPLETE,
        shard_count=1, file_count=1, total_bytes=10, schema_version="v",
        type_contract_version="t", payload_sha256="e" * 64,
    )
    return ApplyRequest(
        manifest=manifest,
        quality_verified=True,
        approval_ref="APPROVAL-IT",
        executor_id="sql-target-apply-1",
        target_object="data_asset_test.t1_exec_it.EMR_TEST_TABLE",
        allowed_operations=("INSERT", "UPDATE"),
        idempotency_key_columns=("K1",),
        rows=tuple(rows),
        column_meta={
            "K1": ColumnMeta(name="K1", logical_type="VARCHAR"),
            "V1": ColumnMeta(name="V1", logical_type="VARCHAR"),
        },
    )


def _plan_for(request, target_rows):
    port = ApplyPort(
        whitelisted_executors=["sql-target-apply-1"],
        enforce_fence=False, lease_validator=lambda r, t: None,
    )
    return port.preview(request, target_rows)


@unittest.skipUnless(ISOLATED, "BLOCKED_ENV: 需要 APP_TEST_DB_URL=data_asset_test")
class TestExecutorOnRealPg(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(TEST_URL)
        with cls.engine.begin() as c:
            c.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            c.execute(text(f"CREATE SCHEMA {SCHEMA}"))
            c.execute(text(
                f'CREATE TABLE {TABLE} ("K1" text PRIMARY KEY, "V1" text,'
                f' "SYSTEM_TIME" timestamptz)'
            ))
            c.execute(text(
                f'CREATE TABLE {RECEIPTS} (operation_id text PRIMARY KEY,'
                f' batch_id text, manifest_hash text, target_object text,'
                f' scope_summary text, rows_affected int, system_time text,'
                f' committed_at text)'
            ))
            c.execute(text(
                f'INSERT INTO {TABLE} ("K1", "V1") VALUES (\'k1\', \'old\')'
            ))

    @classmethod
    def tearDownClass(cls):
        with cls.engine.begin() as c:
            c.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        cls.engine.dispose()

    def _db_now(self):
        with self.engine.connect() as c:
            return c.execute(text("SELECT now()")).scalar()

    def _table_rows(self):
        with self.engine.connect() as c:
            return {r[0]: (r[1], r[2]) for r in c.execute(
                text(f'SELECT "K1", "V1", "SYSTEM_TIME" FROM {TABLE}'))}

    def _receipts(self):
        with self.engine.connect() as c:
            return c.execute(text(
                f"SELECT operation_id, rows_affected, system_time FROM {RECEIPTS}"
            )).fetchall()

    def test_rt_exec_1_single_tx_receipt_and_db_clock(self):
        rows = [
            {"K1": "k1", "V1": "new"},   # UPDATE（旧值 old）
            {"K1": "k2", "V1": "ins"},   # INSERT
        ]
        request = _apply_request(rows, batch_id="B-IT1")
        target_rows = {("k1",): {"K1": "k1", "V1": "old"}}
        plan = _plan_for(request, target_rows)
        self.assertEqual(
            {a for _, a in plan.actions}, {UPDATE, INSERT}
        )
        before = self._db_now()
        executor = SqlTargetApplyExecutor(
            lambda: PgTargetConnection(self.engine), EXEC_CONFIG, simulation=True
        )
        result = executor.execute(request, plan)
        after = self._db_now()
        self.assertIs(result.committed, True)
        self.assertEqual(result.rows_affected, 2)
        # 回执存在且唯一；SYSTEM_TIME=目标时钟（落在 [before, after] 区间）
        receipts = self._receipts()
        self.assertEqual(len(receipts), 1)
        st = datetime.fromisoformat(receipts[0][2])
        self.assertLessEqual(before, st)
        self.assertGreaterEqual(after, st)
        # 业务行 SYSTEM_TIME 与回执同刻（同事务一次取值）
        table = self._table_rows()
        self.assertEqual(table["k1"][0], "new")
        self.assertEqual(table["k2"][0], "ins")
        self.assertEqual(table["k1"][1].isoformat(), receipts[0][2])

    def test_rt_exec_2_idempotent_replay_returns_original(self):
        rows = [{"K1": "k3", "V1": "once"}]
        request = _apply_request(rows, batch_id="B-IT2")
        plan = _plan_for(request, {})
        executor = SqlTargetApplyExecutor(
            lambda: PgTargetConnection(self.engine), EXEC_CONFIG, simulation=True
        )
        first = executor.execute(request, plan)
        self.assertIs(first.committed, True)
        self.assertEqual(first.rows_affected, 1)
        # 重放：同 batch+manifest → 同 operation_id → 返回原回执不重写
        second = executor.execute(request, plan)
        self.assertIs(second.committed, True)
        self.assertEqual(second.rows_affected, first.rows_affected)
        self.assertEqual(second.operation_id, first.operation_id)
        # 业务行不重复、回执仍唯一
        table = self._table_rows()
        self.assertEqual(table["k3"], ("once", table["k3"][1]))
        self.assertEqual(len(self._receipts_for(first.operation_id)), 1)

    def _receipts_for(self, operation_id):
        with self.engine.connect() as c:
            return c.execute(text(
                f"SELECT * FROM {RECEIPTS} WHERE operation_id=:o"
            ), {"o": operation_id}).fetchall()

    def test_rt_exec_3_atomic_rollback_when_receipt_fails(self):
        class ReceiptBreaker(PgTargetConnection):
            def insert_receipt(self, receipt_table, receipt):
                raise RuntimeError("回执写入失败（测试注入）")

        rows = [{"K1": "k9", "V1": "must-not-persist"}]
        request = _apply_request(rows, batch_id="B-IT3")
        plan = _plan_for(request, {})
        receipts_before = len(self._receipts())
        executor = SqlTargetApplyExecutor(
            lambda: ReceiptBreaker(self.engine), EXEC_CONFIG, simulation=True
        )
        with self.assertRaises(RuntimeError):
            executor.execute(request, plan)
        # 同事务原子性：业务行与回执一并回滚（回执总数不增）
        self.assertNotIn("k9", self._table_rows())
        self.assertEqual(len(self._receipts()), receipts_before)

    def test_rt_exec_4_row_lock_fence_blocks_second_writer(self):
        current_v1 = self._table_rows()["k1"][0]
        holder = PgTargetConnection(self.engine)
        holder.begin()
        holder.lock_and_read_rows(TABLE, ("K1",), [("k1",)])  # 持锁不提交
        try:
            fenced = SqlTargetApplyExecutor(
                lambda: PgTargetConnection(self.engine, lock_timeout_seconds=2),
                EXEC_CONFIG, simulation=True,
            )
            rows = [{"K1": "k1", "V1": "stale-writer"}]
            request = _apply_request(rows, batch_id="B-IT4")
            plan = _plan_for(request, {("k1",): {"K1": "k1", "V1": current_v1}})
            with self.assertRaises(Exception):  # noqa: B017 - 锁超时/取消
                fenced.execute(request, plan)
            # 被围栏挡住：目标行未被第二个写者改动
            self.assertEqual(self._table_rows()["k1"][0], current_v1)
        finally:
            holder.rollback()

    def test_rt_exec_5_commit_unknown_then_clean_retry(self):
        rows = [{"K1": "k5", "V1": "ambiguous"}]
        request = _apply_request(rows, batch_id="B-IT5")
        plan = _plan_for(request, {})
        executor = SqlTargetApplyExecutor(
            lambda: PgTargetConnection(self.engine, commit_answer_lost=True),
            EXEC_CONFIG, simulation=True,
        )
        result = executor.execute(request, plan)
        self.assertIsNone(result.committed)  # COMMIT_UNKNOWN：不盲重试
        # ground truth=实际回滚：无业务行、无回执
        self.assertNotIn("k5", self._table_rows())
        op_id = stable_operation_id(
            request.manifest.batch_id, request.manifest.payload_sha256
        )
        self.assertEqual(len(self._receipts_for(op_id)), 0)
        # 裁定后重放（确认未提交）：全新执行并干净提交
        executor2 = SqlTargetApplyExecutor(
            lambda: PgTargetConnection(self.engine), EXEC_CONFIG, simulation=True
        )
        retried = executor2.execute(request, plan)
        self.assertIs(retried.committed, True)
        self.assertEqual(retried.rows_affected, 1)
        self.assertEqual(self._table_rows()["k5"][0], "ambiguous")


if __name__ == "__main__":
    unittest.main()
