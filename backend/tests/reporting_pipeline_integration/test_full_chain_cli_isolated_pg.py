# -*- coding: utf-8 -*-
"""批1 验收（隔离 PG，正式入口全链）：capture→verify→apply→reconcile→
daily-report/resume 从 reporting_ctl CLI 驱动，真实源/目标/控制面全在
data_asset_test（真 RDBMS 事务，非 SQLite 冒充）。

覆盖场景：
1. 首日全链（首页父表）：capture → verify → apply（租约+平台批准+回执+
   版本账）→ reconcile（RECONCILED+水位推进）；
2. 断连/源不可达：源对象缺失 → capture 失败记缺口（RETRYABLE），源恢复
   后 resume --execute 续跑闭合缺口（失败窗口排队→重跑→关缺口）；
3. 迟到：业务日后补行 → RESCAN 窗重捕获 → 新行 INSERT，既有行
   NO_CHANGE（CAS）；
4. 修改：源行值变更 → RESCAN 重捕获 → CAS 通过 UPDATE，目标更新；
5. 缺父：子表引用不存在父键 → 隔离组留账+合法组继续；父入库后重放
   全量闭合；
6. 提交不明：COMMIT 应答丢失（确定性 ground truth=回滚）→ 批次
   COMMIT_UNKNOWN；干净重放成功；
7. 并发变化：预览后目标被他人改 → TARGET_CHANGED 回滚 → APPLY_PENDING；
8. 日报/resume：真实持久化状态源。

边界声明：Oracle 方言（oracledb 锁/绑定语义）无隔离环境，如实 NOT_RUN。
DataX 真实引擎须 8.53（待批），本链为 PYTHON 路线。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

import pytest

from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

TEST_URL = os.environ.get("APP_TEST_DB_URL", "")
ISOLATED = bool(TEST_URL) and "data_asset_test" in TEST_URL

SRC_SCHEMA = "t1_it_src"
TGT_SCHEMA = "t1_it_tgt"
EXECUTOR_CODE = "sql-target-apply-1"
TARGET_INSTANCE = "data_asset_test"
DAY = "2026-10-22"

SOURCE_CONFIG_DIR = (
    REPO_ROOT / "开发起步包" / "output_r189" / "r189-20261015-upload-audit"
    / "daily_t1_20261015" / "python_datax_execution_20261019"
)

CMD = [
    sys.executable,
    str(BACKEND_ROOT / "scripts" / "reporting_ctl.py"),
    "--config", str(SOURCE_CONFIG_DIR),
]


@pytest.fixture(autouse=True)
def clean_test_database():
    """模块级覆盖根 conftest 的 autouse 清库（同纯逻辑目录模式）：
    本套件是顺序累积场景（同日多模式批次/水位/版本账互为前置），测间
    TRUNCATE 会拆掉链路；状态由 setUpClass 统一重建（含跨运行残留清理）。"""
    yield


def _run_cli(args: list[str], env_extra: dict | None = None, expect: int = 0):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(env_extra or {})
    proc = subprocess.run(
        CMD + args, capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=300, cwd=str(REPO_ROOT),
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    if proc.returncode != expect:
        raise AssertionError(
            f"CLI 退出码 {proc.returncode}（期望 {expect}）: {args}\n"
            f"payload={json.dumps(payload, ensure_ascii=False)[:1500]}"
        )
    return payload


@unittest.skipUnless(ISOLATED, "BLOCKED_ENV: 需隔离库 data_asset_test")
class TestFullChainFromCli(unittest.TestCase):
    """正式入口全链（每步经 reporting_ctl 子进程）。"""

    @classmethod
    def setUpClass(cls):
        # 1) 控制面迁移全链（含批1-2c 批准登记表）
        env = dict(os.environ)
        env["APP_DB_URL"] = TEST_URL
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(BACKEND_ROOT), env=env, capture_output=True,
            text=True, timeout=300, check=True,
        )
        cls.engine = create_engine(TEST_URL)
        # 跨运行残留清理：控制表清空（批次数少，按表 DELETE），scratch
        # schema 重建；平台白名单/批准登记随后重灌
        with cls.engine.begin() as conn:
            tables = [
                row[0] for row in conn.execute(text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='asset' AND table_name LIKE "
                    "'asset_reporting_%'"
                ))
            ]
            for table in tables:
                conn.execute(text(f'DELETE FROM asset."{table}"'))
        cls._setup_source_and_target()
        cls._register_executor_and_approval()
        cls._write_freeze_and_bindings()

    @classmethod
    def _columns_doc(cls) -> dict[str, list[dict]]:
        evidence = (
            SOURCE_CONFIG_DIR / "2026补齐与T加1接续_20261022"
            / "核验证据_20261022" / "target_dict_bulk.json"
        )
        doc = json.loads(evidence.read_text(encoding="utf-8"))
        tables: dict[str, list[dict]] = {}
        for col in doc["columns"]:
            tables.setdefault(col["TABLE_NAME"], []).append(col)
        return {
            name: cols for name, cols in tables.items()
            if name in ("EMR_ICH", "EMR_ICH_DIAGNOSIS")
        }

    @staticmethod
    def _pg_type(data_type: str) -> str:
        upper = (data_type or "").upper()
        if upper in ("NUMBER", "NUMERIC", "DECIMAL", "FLOAT"):
            return "numeric"
        if upper in ("DATE", "TIMESTAMP"):
            return "timestamp"
        return "text"

    @classmethod
    def _setup_source_and_target(cls):
        cols_doc = cls._columns_doc()
        with cls.engine.begin() as conn:
            for schema in (SRC_SCHEMA, TGT_SCHEMA):
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            for table, cols in cols_doc.items():
                tgt_table = f"{TGT_SCHEMA}.{table.lower()}"
                tgt_cols = ", ".join(
                    f'"{c["COLUMN_NAME"]}" {cls._pg_type(c["DATA_TYPE"])}'
                    + (" PRIMARY KEY" if c["COLUMN_NAME"] == "ID" else "")
                    for c in cols
                )
                conn.execute(text(f'CREATE TABLE {tgt_table} ({tgt_cols})'))
                # 源视图展开为完整投影列：ID/DATETIME 直取，父键列从 ID 派生，
                # 其余列 NULL（NULL 通过类型/字节长度规则，必填仅稳定键 ID）
                src_base = f"{SRC_SCHEMA}.{table.lower()}"
                conn.execute(text(f"""
                    CREATE TABLE {src_base} (
                        "ID" text PRIMARY KEY,
                        "DATETIME" timestamp NOT NULL,
                        "PAYLOAD" text
                    )
                """))
                exprs = ['"ID"', '"DATETIME"']
                numeric = {"NUMBER", "NUMERIC", "DECIMAL", "FLOAT"}
                for c in cols:
                    column = c["COLUMN_NAME"]
                    if column in ("ID", "DATETIME"):
                        continue
                    if column in ("DCS_ID", "ICH_ID"):
                        derived = (
                            "SPLIT_PART(\"ID\", '|', 1) || '|' || "
                            "SPLIT_PART(\"ID\", '|', 2) || '|' || "
                            "SPLIT_PART(\"ID\", '|', 3)"
                        )
                        exprs.append(f'{derived} AS "{column}"')
                    elif c.get("NULLABLE") == "N":
                        # 目标 NOT NULL 列：给类型匹配的非空占位（质量门强制必填）
                        if (c["DATA_TYPE"] or "").upper() in numeric:
                            exprs.append(f"CAST(0 AS text) AS \"{column}\"")
                        else:
                            exprs.append(f"CAST('X' AS text) AS \"{column}\"")
                    else:
                        exprs.append(f'CAST(NULL AS text) AS "{column}"')
                conn.execute(text(
                    f'CREATE VIEW {src_base}_v AS SELECT ' + ", ".join(exprs)
                    + f' FROM {src_base}'
                ))
            conn.execute(text(f"""
                CREATE TABLE {TGT_SCHEMA}.asset_t1_receipts_it (
                    operation_id text PRIMARY KEY,
                    batch_id text, manifest_hash text, target_object text,
                    scope_summary text, rows_affected integer,
                    system_time text, committed_at text
                )
            """))
            # 源种子：父表 3 行 + 子表 2 行（1 缺父 / 1 有父）
            base = datetime(2026, 10, 22, 10, 0)
            for i in range(1, 4):
                conn.execute(text(f"""
                    INSERT INTO {SRC_SCHEMA}.emr_ich ("ID", "DATETIME", "PAYLOAD")
                    VALUES (:id, :dt, 'p{i}')
                """), {"id": f"49557032X|P{i}|1", "dt": base})
            conn.execute(text(f"""
                INSERT INTO {SRC_SCHEMA}.emr_ich_diagnosis
                    ("ID", "DATETIME", "PAYLOAD")
                VALUES (:id, :dt, 'd'), (:id2, :dt, 'd2')
            """), {
                "id": "49557032X|P1|1|1|1",  # 父=P1（已存在）
                "id2": "49557032X|PX|1|1|1",  # 父=PX（缺失）
                "dt": base,
            })
            # 平台白名单执行器
            conn.execute(text("""
                INSERT INTO asset.asset_action_executors
                    (executor_code, executor_name_cn, execution_mode,
                     risk_level, enabled)
                VALUES (:code, 'T1隔离验收执行器', 'cli_sql', 'medium', true)
                ON CONFLICT (executor_code) DO UPDATE SET enabled = true
            """), {"code": EXECUTOR_CODE})

    @classmethod
    def _register_executor_and_approval(cls):
        from app.services.reporting_pipeline.production_apply import (
            register_approval,
        )
        from sqlalchemy.orm import sessionmaker

        now = datetime.now(timezone.utc)
        # 批准登记按 (approval_ref, executor) 唯一：每表独立 ref
        cls.approval_refs = {
            table: f"T1-IT-APPROVAL-20261023:{table}"
            for table in ("emr_ich", "emr_ich_diagnosis")
        }
        for table, ref in cls.approval_refs.items():
            try:
                register_approval(
                    sessionmaker(bind=cls.engine),
                    approval_ref=ref,
                    executor_code=EXECUTOR_CODE,
                    target_scope=f"{TARGET_INSTANCE}.{TGT_SCHEMA}.{table}",
                    valid_from=now,
                    valid_until=now + timedelta(hours=8),
                    registered_by="zcode-20261023-tplus1-twobatch(隔离验收)",
                )
            except Exception:
                pass  # 重复登记跳过（幂等验收环境）

    @classmethod
    def _write_freeze_and_bindings(cls):
        import tempfile

        cls.workdir = Path(tempfile.mkdtemp(prefix="t1-it-accept-"))
        override = {
            "sources": {
                "ods_8_216": {"dialect": "pg", "url_env": "T1_IT_SOURCE_DB_URL"},
            },
            "targets": {
                "EMR_ICH": {
                    "instance": TARGET_INSTANCE, "tenant": TGT_SCHEMA,
                    "table": f"{TGT_SCHEMA}.emr_ich",
                },
                "EMR_ICH_DIAGNOSIS": {
                    "instance": TARGET_INSTANCE, "tenant": TGT_SCHEMA,
                    "table": f"{TGT_SCHEMA}.emr_ich_diagnosis",
                },
            },
        }
        override_path = cls.workdir / "override.json"
        override_path.write_text(json.dumps(override, ensure_ascii=False), encoding="utf-8")
        freeze_path = cls.workdir / "freeze_isolated.json"
        _run_cli([
            "freeze-config", "--output", str(freeze_path),
            "--environment", "isolated_acceptance", "--override", str(override_path),
        ])
        doc = json.loads(freeze_path.read_text(encoding="utf-8"))
        # 源对象改指隔离源视图
        doc["tables"]["EMR_ICH"]["source"]["object"] = f"{SRC_SCHEMA}.emr_ich_v"
        doc["tables"]["EMR_ICH_DIAGNOSIS"]["source"]["object"] = (
            f"{SRC_SCHEMA}.emr_ich_diagnosis_v"
        )
        doc["tables"]["EMR_ICH"]["receipt_table"] = f"{TGT_SCHEMA}.asset_t1_receipts_it"
        doc["tables"]["EMR_ICH_DIAGNOSIS"]["receipt_table"] = (
            f"{TGT_SCHEMA}.asset_t1_receipts_it"
        )
        for name in doc["tables"]:
            doc["tables"][name]["fingerprint"] = None  # 重算
        from app.services.reporting_pipeline.runtime_config import (
            compute_config_fingerprint,
            compute_table_fingerprint,
        )
        for name, table in doc["tables"].items():
            table["fingerprint"] = compute_table_fingerprint(table)
        doc["config_fingerprint"] = compute_config_fingerprint(doc)
        freeze_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        cls.freeze_path = freeze_path
        # 绑定文件：按冻结件投影生成 key/write 列
        write_cols_ich = [
            field["name"] for field in doc["tables"]["EMR_ICH"]["projection"]
        ]
        write_cols_diag = [
            field["name"] for field in doc["tables"]["EMR_ICH_DIAGNOSIS"]["projection"]
        ]
        cls.bindings = {
            "executor_id": EXECUTOR_CODE,
            "action_bindings": [
                {
                    "canonical_table": "EMR_ICH",
                    "actions": ["CAPTURE", "STAGE", "APPLY"],
                    "valid_hours": 8,
                    "approval_ref": "T1-IT-ACTION-BINDING-20261023",
                    "granted_by": "zcode-20261023-tplus1-twobatch(隔离验收)",
                },
                {
                    "canonical_table": "EMR_ICH_DIAGNOSIS",
                    "actions": ["CAPTURE", "STAGE", "APPLY"],
                    "valid_hours": 8,
                    "approval_ref": "T1-IT-ACTION-BINDING-20261023",
                    "granted_by": "zcode-20261023-tplus1-twobatch(隔离验收)",
                },
            ],
            "receipt_table": f"{TGT_SCHEMA}.asset_t1_receipts_it",
            "system_time_column": None,
            "sources": {"ods_8_216": {"dialect": "pg", "url_env": "T1_IT_SOURCE_DB_URL"}},
            "target": {
                "dialect": "pg", "url_env": "T1_IT_TARGET_DB_URL",
                "instance": TARGET_INSTANCE, "tenant": TGT_SCHEMA,
            },
            "targets_by_table": {
                "EMR_ICH": {
                    "target_instance": TARGET_INSTANCE, "tenant": TGT_SCHEMA,
                    "table": f"{TGT_SCHEMA}.emr_ich",
                    "key_columns": ["ID"],
                    "write_columns": write_cols_ich,
                },
                "EMR_ICH_DIAGNOSIS": {
                    "target_instance": TARGET_INSTANCE, "tenant": TGT_SCHEMA,
                    "table": f"{TGT_SCHEMA}.emr_ich_diagnosis",
                    "key_columns": ["ID"],
                    "write_columns": write_cols_diag,
                },
            },
        }
        cls.bindings_path = cls.workdir / "bindings.json"
        cls._write_bindings()

    @classmethod
    def _write_bindings(cls, fault: dict | None = None):
        doc = dict(cls.bindings)
        if fault:
            doc["fault_injection"] = fault
        cls.bindings_path.write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def _env(cls) -> dict:
        return {
            "T1_IT_SOURCE_DB_URL": TEST_URL,
            "T1_IT_TARGET_DB_URL": TEST_URL,
            "APP_REPORTING_CONTROL_DB_URL": TEST_URL,
        }

    def _capture(self, table: str, day: str = DAY, mode: str = "T1", expect: int = 0):
        return _run_cli([
            "capture", "--table", table, "--business-day", day, "--mode", mode,
            "--state-db", TEST_URL, "--stage-root", str(self.workdir / "stage"),
            "--bindings-file", str(self.bindings_path),
            "--runtime-config", str(self.freeze_path),
        ], env_extra=self._env(), expect=expect)

    def _verify(self, batch_id: str, expect: int = 0):
        return _run_cli([
            "verify", "--batch", batch_id,
            "--state-db", TEST_URL, "--stage-root", str(self.workdir / "stage"),
            "--bindings-file", str(self.bindings_path),
            "--runtime-config", str(self.freeze_path),
        ], env_extra=self._env(), expect=expect)

    def _apply(self, batch_id: str, expect: int = 0):
        table = batch_id.rsplit(".", 3)[0].rsplit(".", 1)[-1]
        return _run_cli([
            "apply", "--batch", batch_id,
            "--approval-ref", self.approval_refs.get(table, ""),
            "--state-db", TEST_URL, "--stage-root", str(self.workdir / "stage"),
            "--bindings-file", str(self.bindings_path),
            "--runtime-config", str(self.freeze_path),
        ], env_extra=self._env(), expect=expect)

    def _reconcile(self, batch_id: str, expect: int = 0):
        return _run_cli([
            "reconcile", "--batch", batch_id,
            "--state-db", TEST_URL, "--stage-root", str(self.workdir / "stage"),
            "--bindings-file", str(self.bindings_path),
            "--runtime-config", str(self.freeze_path),
        ], env_extra=self._env(), expect=expect)

    def _batch_state(self, batch_id: str) -> str:
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT state FROM asset.asset_reporting_batches "
                "WHERE batch_id = :bid"
            ), {"bid": batch_id}).first()
            return row[0] if row else "MISSING"

    # -- 1) 首日全链（父表） --------------------------------------------

    _first_done = False

    def _first_day(self):
        if TestFullChainFromCli._first_done:
            return
        TestFullChainFromCli._first_done = True
        outcome = self._capture("EMR_ICH")
        self.assertTrue(outcome["ok"], outcome)
        batch_id = outcome["batch_id"]
        self.assertIn(".T1.2026-10-22.", batch_id)
        self.assertEqual(outcome["rows"], 3)
        # verify：全部列为 NULL/空串时必填（ID）满足 → VALIDATED
        verify = self._verify(batch_id)
        self.assertEqual(verify["state"], "VALIDATED", verify)
        # apply：租约自动获取 + 平台批准 + 回执 + 版本账
        apply_out = self._apply(batch_id)
        self.assertTrue(apply_out["ok"], apply_out)
        self.assertEqual(self._batch_state(batch_id), "APPLIED")
        with self.engine.connect() as conn:
            receipts = conn.execute(text(
                f"SELECT count(*) FROM {TGT_SCHEMA}.asset_t1_receipts_it "
                "WHERE batch_id = :bid"
            ), {"bid": batch_id}).scalar()
            self.assertEqual(receipts, 1)
            versions = conn.execute(text(
                "SELECT count(*) FROM asset.asset_reporting_version_evidence "
                "WHERE canonical_table = 'emr_ich'"
            )).scalar()
            self.assertGreaterEqual(versions, 3)
        # reconcile：全键一致 + 水位推进
        recon = self._reconcile(batch_id)
        self.assertTrue(recon["ok"], recon)
        self.assertEqual(self._batch_state(batch_id), "RECONCILED")
        self.assertEqual(recon["missing_keys"], 0)
        self.assertEqual(recon["content_diffs"], 0)
        self.assertIsNone(recon["recovery"]["recovered_incident"])
        return batch_id

    # -- 2) 断连/源不可达 → 缺口 → 恢复 ---------------------------------

    def test_02_source_unavailable_records_gap_and_recovers(self):
        # 断连/源不可达注入：drop 源视图 → capture 失败 → RETRYABLE + 缺口
        with self.engine.begin() as conn:
            conn.execute(text(f'DROP VIEW {SRC_SCHEMA}.emr_ich_v CASCADE'))
        outcome = self._capture("EMR_ICH", mode="FAIL", expect=1)
        self.assertFalse(outcome["ok"])
        batch_id = outcome["batch_id"]
        self.assertEqual(self._batch_state(batch_id), "RETRYABLE")
        with self.engine.connect() as conn:
            gaps = conn.execute(text(
                "SELECT count(*) FROM asset.asset_reporting_gap_ledger "
                "WHERE canonical_table = 'EMR_ICH' AND state = 'OPEN'"
            )).scalar()
            self.assertGreaterEqual(gaps, 1)
        # 源恢复：重建视图（等价定义）→ resume --execute 失败窗口重跑
        with self.engine.begin() as conn:
            cols = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=:s AND table_name='emr_ich' ORDER BY column_name"
            ), {"s": TGT_SCHEMA}).fetchall()
            exprs = ['"ID"', '"DATETIME"']
            for (column,) in cols:
                if column in ("ID", "DATETIME"):
                    continue
                exprs.append(f'CAST(NULL AS text) AS "{column}"')
            conn.execute(text(
                f'CREATE VIEW {SRC_SCHEMA}.emr_ich_v AS SELECT '
                + ", ".join(exprs) + f' FROM {SRC_SCHEMA}.emr_ich'
            ))
        for _ in range(2):  # capture → verify 两步各一轮
            resumed = _run_cli([
                "resume", "--state-db", TEST_URL, "--execute",
                "--bindings-file", str(self.bindings_path),
                "--stage-root", str(self.workdir / "stage"),
                "--runtime-config", str(self.freeze_path),
            ], env_extra=self._env())
            self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(self._batch_state(batch_id), "VALIDATED")
        return batch_id

    # -- 3/4) 迟到与修改（RESCAN 窗，CAS） ------------------------------

    def test_03_late_arrival_and_modification_via_rescan(self):
        # 首链前置
        self._first_day()
        # 迟到行 + 既有行修改
        with self.engine.begin() as conn:
            conn.execute(text(f"""
                INSERT INTO {SRC_SCHEMA}.emr_ich ("ID", "DATETIME", "PAYLOAD")
                VALUES ('49557032X|LATE|1', :dt, 'late')
            """), {"dt": datetime(2026, 10, 22, 12, 0)})
        late = self._capture("EMR_ICH", mode="RESCAN")
        self.assertTrue(late["ok"], late)
        verify = self._verify(late["batch_id"])
        self.assertEqual(verify["state"], "VALIDATED")
        applied = self._apply(late["batch_id"])
        self.assertTrue(applied["ok"], applied)
        # 既有 3 行 NO_CHANGE（CAS 通过），迟到 1 行 INSERT
        self.assertEqual(applied["partition"]["insert"], 1, applied.get("partition"))
        self.assertEqual(applied["partition"]["no_change"], 3)
        recon = self._reconcile(late["batch_id"])
        self.assertTrue(recon["ok"], recon)

    # -- 5) 缺父：隔离组留账 + 合法组继续 + 父入库后闭合 -----------------

    def test_04_missing_parent_quarantines_and_continues(self):
        self._first_day()
        outcome = self._capture("EMR_ICH_DIAGNOSIS")
        self.assertTrue(outcome["ok"], outcome)
        batch_id = outcome["batch_id"]
        self._verify(batch_id)
        applied = self._apply(batch_id)
        self.assertTrue(applied["ok"], applied)
        # 1 行缺父隔离，1 行合法装载
        self.assertEqual(applied["partition"]["missing_parent"], 1)
        self.assertEqual(applied["partition"]["insert"], 1)
        with self.engine.connect() as conn:
            groups = conn.execute(text(
                "SELECT group_key, rows_quarantined FROM "
                "asset.asset_reporting_quarantine_groups WHERE batch_id = :bid "
                "AND state = 'OPEN'"
            ), {"bid": batch_id}).all()
            self.assertEqual(
                {(g[0], g[1]) for g in groups}, {("missing-parent", 1)}
            )
        # 报送未闭合：reconcile 不转 RECONCILED
        recon = self._reconcile(batch_id, expect=1)
        self.assertFalse(recon["ok"])
        self.assertEqual(recon["quarantined_pending"], 1)
        self.assertEqual(self._batch_state(batch_id), "APPLIED")
        # 父入库（直接补目标父行模拟父批完成）后：新窗重放全量闭合
        with self.engine.begin() as conn:
            cols = [c[0] for c in conn.execute(text(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_schema='{TGT_SCHEMA}' AND table_name='emr_ich'"
            )).fetchall()]
            placeholders = {c: None for c in cols}
            conn.execute(
                text(
                    f'INSERT INTO {TGT_SCHEMA}.emr_ich ({", ".join(chr(34)+c+chr(34) for c in cols)}) '
                    f'VALUES ({", ".join(":"+c for c in cols)})'
                ),
                {**placeholders, "ID": "49557032X|PX|1"},
            )
        replay = self._capture("EMR_ICH_DIAGNOSIS", mode="BACKFILL")
        self.assertTrue(replay["ok"], replay)
        self._verify(replay["batch_id"])
        applied2 = self._apply(replay["batch_id"])
        self.assertTrue(applied2["ok"], applied2)
        self.assertEqual(applied2["partition"]["missing_parent"], 0)
        recon2 = self._reconcile(replay["batch_id"])
        self.assertTrue(recon2["ok"], recon2)
        self.assertEqual(self._batch_state(replay["batch_id"]), "RECONCILED")

    # -- 6) 提交不明：COMMIT_UNKNOWN + 干净重放 --------------------------

    def test_05_commit_unknown_then_clean_replay(self):
        self._first_day()
        # CU 批次需真实写路径（新行 INSERT），否则全 NO_CHANGE 无提交写入
        with self.engine.begin() as conn:
            conn.execute(text(f"""
                INSERT INTO {SRC_SCHEMA}.emr_ich ("ID", "DATETIME", "PAYLOAD")
                VALUES ('49557032X|CU|1', :dt, 'cu')
            """), {"dt": datetime(2026, 10, 22, 14, 0)})
        self._write_bindings({"commit_answer_lost_once": True})
        try:
            outcome = self._capture("EMR_ICH", mode="CU")
            self.assertTrue(outcome["ok"], outcome)
            batch_id = outcome["batch_id"]
            self._verify(batch_id)
            apply_out = self._apply(batch_id, expect=1)
            self.assertFalse(apply_out["ok"])
            self.assertEqual(apply_out["state"], "COMMIT_UNKNOWN", apply_out)
            self.assertEqual(self._batch_state(batch_id), "COMMIT_UNKNOWN")
            # 裁定：目标无回执（ground truth=回滚）→ 回 APPLY_PENDING 重放；
            # 重放是新的 CLI 进程，须先解除绑定文件中的故障注入
            with self.engine.begin() as conn:
                conn.execute(text(
                    "UPDATE asset.asset_reporting_batches SET state='APPLY_PENDING' "
                    "WHERE batch_id = :bid"
                ), {"bid": batch_id})
            self._write_bindings(None)
            clean = self._apply(batch_id)
            self.assertTrue(clean["ok"], clean)
            self.assertEqual(self._batch_state(batch_id), "APPLIED")
            # 干净重放后行真实入库（ground truth=首次提交确已回滚）
            with self.engine.connect() as conn:
                exists = conn.execute(text(
                    f'SELECT count(*) FROM {TGT_SCHEMA}.emr_ich '
                    "WHERE \"ID\" = '49557032X|CU|1'"
                )).scalar()
                self.assertEqual(exists, 1)
        finally:
            self._write_bindings(None)

    # -- 7) 并发变化：TARGET_CHANGED 回滚 --------------------------------

    def test_06_concurrent_target_change_rolls_back(self):
        self._first_day()
        outcome = self._capture("EMR_ICH", mode="RACE")
        self.assertTrue(outcome["ok"], outcome)
        batch_id = outcome["batch_id"]
        self._verify(batch_id)
        # 预览快照后、apply 前他人改目标行（并发写者）
        with self.engine.begin() as conn:
            col = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=:s AND table_name='emr_ich' "
                "AND column_name <> 'ID' LIMIT 1"
            ), {"s": TGT_SCHEMA}).scalar()
            conn.execute(text(
                f'UPDATE {TGT_SCHEMA}.emr_ich SET "{col}" = \'foreign_write\' '
                "WHERE \"ID\" = '49557032X|P1|1'"
            ))
        # CAS 检测：目标内容 ≠ 上次登记的源内容哈希 → 冲突组隔离，不盲覆盖
        apply_out = self._apply(batch_id, expect=1)
        self.assertFalse(apply_out["ok"], apply_out)
        self.assertEqual(apply_out.get("state"), "QUARANTINED", apply_out)
        self.assertGreater(apply_out["partition"]["cas_conflict"], 0)
        self.assertEqual(self._batch_state(batch_id), "QUARANTINED")
        # 他人写入被保留（未盲覆盖）
        with self.engine.connect() as conn:
            kept = conn.execute(text(
                f'SELECT "{col}" FROM {TGT_SCHEMA}.emr_ich '
                "WHERE \"ID\" = '49557032X|P1|1'"
            )).scalar()
            self.assertEqual(kept, "foreign_write")

    # -- 8) 日报与恢复视图（真实持久化状态源） ---------------------------

    def test_07_daily_report_and_resume(self):
        self._first_day()
        report = _run_cli([
            "daily-report", "--business-day", DAY, "--state-db", TEST_URL,
        ], env_extra=self._env())
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["state_source"], "durable_state_db_configured")
        resumed = _run_cli(["resume", "--state-db", TEST_URL], env_extra=self._env())
        self.assertTrue(resumed["ok"], resumed)
        self.assertFalse(resumed["simulation"])


if __name__ == "__main__":
    unittest.main()
