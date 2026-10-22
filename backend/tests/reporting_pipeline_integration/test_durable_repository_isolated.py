"""R02 耐久仓储隔离集成测试：迁移往返后的并发/重启/失败注入语义。

对应补充验收 RT1-003（捕获后重启恢复）、RT1-004（多工作者租约）、
RT1-005（耐久原子性）与迁移 f4a5b6c7d8e9 往返。

前置（与目录 conftest 一致）：
1. source tools/dev_env.sh 且 APP_TEST_DB_URL 指向 data_asset_test
   （已核实、允许清理的隔离库）；
2. 运行前 alembic upgrade head；
3. 根 conftest 的清库/TRUNCATE 行为仍然生效——绝不指向生产/共享库。

未满足时整目录 SKIP（BLOCKED_ENV），不冒充通过。
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    EndReason,
    RowClassification,
)
from app.services.reporting_pipeline.planner import TimeWindow
from app.services.reporting_pipeline.pg_repository import (
    SqlAlchemyControlRepository,
)
from app.services.reporting_pipeline.repositories import LeaseDenied

TEST_URL = os.environ.get("APP_TEST_DB_URL", "")
ISOLATED = bool(TEST_URL) and "data_asset_test" in TEST_URL


def _manifest(batch_id: str, attempt: str, rows: int = 3) -> BatchManifest:
    return BatchManifest(
        batch_id=batch_id, attempt_id=attempt, task_id="EMR_IT",
        config_version="v1", definition_fingerprint=None,
        source_identity="ods__V_IT", window_fingerprint="win:it",
        source_visibility_cutoff="cut",
        rows=RowClassification(source_read_rows=rows, valid=rows),
        pagination_complete=True, end_reason=EndReason.WINDOW_COMPLETE,
        shard_count=1, file_count=1, total_bytes=32, schema_version="v",
        type_contract_version="t", payload_sha256="b" * 64,
    )


@unittest.skipUnless(ISOLATED, "BLOCKED_ENV: 需已核实的 data_asset_test 隔离库")
class TestDurableRepositoryIsolated(unittest.TestCase):
    """两连接工厂=两个进程语义；断言跨进程原子性与恢复。"""

    @classmethod
    def setUpClass(cls) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        cls.engine = create_engine(TEST_URL)
        cls.session_factory = sessionmaker(bind=cls.engine)

    def _repo(self) -> SqlAlchemyControlRepository:
        return SqlAlchemyControlRepository(self.session_factory)

    def test_rt1_003_attempt_and_watermark_survive_reopen(self):
        repo_a = self._repo()
        repo_a.create_batch("it-b1", "EMR_IT", "2026-10-19")
        repo_a.attach_attempt_manifest("it-b1", _manifest("it-b1", "A1"))
        repo_a.select_manifest("it-b1")
        repo_a.advance_capture_watermark(
            "EMR_IT", datetime(2026, 10, 20, tzinfo=timezone.utc)
        )
        # "进程 B"：全新仓储对象（同库不同连接）
        repo_b = self._repo()
        record = repo_b.select_manifest("it-b1")
        self.assertEqual(record.attempt_id, "A1")
        wm = repo_b.get_watermarks("EMR_IT")
        self.assertIsNotNone(wm.capture_h)

    def test_rt1_004_two_workers_single_lease_and_stale_token(self):
        repo_a = self._repo()
        repo_b = self._repo()
        lease_a = repo_a.acquire_lease("it-res-1", "worker-a", 60)
        with self.assertRaises(LeaseDenied):
            repo_b.acquire_lease("it-res-1", "worker-b", 60)
        # a 过期后 b 接管：token 前进；旧 token 续期/围栏被拒
        with self.engine.begin() as conn:
            from sqlalchemy import text

            conn.execute(
                text(
                    "UPDATE asset.asset_reporting_leases SET expires_at = now() - "
                    "interval '1 second' WHERE resource = 'it-res-1'"
                )
            )
        lease_b = repo_b.acquire_lease("it-res-1", "worker-b", 60)
        self.assertGreater(lease_b.fencing_token, lease_a.fencing_token)
        with self.assertRaises(LeaseDenied):
            repo_a.renew_lease("it-res-1", "worker-a", lease_a.fencing_token)
        with self.assertRaises(LeaseDenied):
            repo_a.validate_fencing("it-res-1", lease_a.fencing_token)
        repo_b.validate_fencing("it-res-1", lease_b.fencing_token)

    def test_rt1_005_gap_guards_continuous_cursor(self):
        repo = self._repo()
        repo.advance_capture_watermark(
            "EMR_IT2", datetime(2026, 10, 20, tzinfo=timezone.utc)
        )
        repo.record_gap(
            "EMR_IT2",
            TimeWindow(
                datetime(2026, 10, 5, tzinfo=timezone.utc),
                datetime(2026, 10, 6, tzinfo=timezone.utc),
            ),
            "it outage",
        )
        # 历史缺口不阻塞日捕获；阻塞连续完成
        repo.advance_capture_watermark(
            "EMR_IT2", datetime(2026, 10, 21, tzinfo=timezone.utc)
        )
        with self.assertRaises(Exception):
            repo.advance_continuous_completion(
                "EMR_IT2", datetime(2026, 10, 19, tzinfo=timezone.utc)
            )
        gaps = repo.open_gaps("EMR_IT2")
        self.assertTrue(gaps)
        repo.close_gap(gaps[0].gap_id, evidence="补抽完成")
        repo.advance_continuous_completion(
            "EMR_IT2", datetime(2026, 10, 19, tzinfo=timezone.utc)
        )

    def test_version_registry_scoped_keys(self):
        from app.services.reporting_pipeline.apply_port import VersionScope
        from app.services.reporting_pipeline.pg_repository import PgVersionRegistry

        registry = PgVersionRegistry(self.session_factory)
        scope = VersionScope("orcl-it", "t", "EMR_IT")
        registry.register_version(scope, ("K1",), "1000", operation_id="OP-IT-1")
        self.assertEqual(registry.current_version(scope, ("K1",)), "1000")
        self.assertIsNone(
            registry.current_version(
                VersionScope("orcl-it", "t", "EMR_OTHER"), ("K1",)
            )
        )


if __name__ == "__main__":
    unittest.main()
