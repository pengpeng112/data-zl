import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


TOOL = Path(__file__).resolve().parents[1] / "ai_handoff.py"
sys.path.insert(0, str(TOOL.parent))
import ai_handoff  # noqa: E402


class AiHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root.joinpath("src").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(TOOL), "--repo", str(self.root), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def claim(self, session, *scopes, ttl=120):
        return self.run_cli(
            "claim", "--session", session, "--tool", "codex", "--model", "test-model",
            "--task", "bounded local task", *sum((["--scope", scope] for scope in scopes), []),
            "--ttl-minutes", str(ttl),
        )

    def test_conflict_ancestor_descendant_but_not_near_prefix(self):
        first = self.claim("alpha", "src")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertNotEqual(self.claim("beta", "src/pkg/file.py").returncode, 0)
        self.assertEqual(self.claim("gamma", "src2/file.py").returncode, 0)

    def test_disjoint_parallel_scopes_can_both_be_claimed(self):
        first = self.claim("one", "src/a.py")
        second = self.claim("two", "src/b.py")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(ai_handoff.status(str(self.root))), 2)

    def test_expired_claim_still_blocks_until_release(self):
        self.assertEqual(self.claim("alpha", "src/a.py", ttl=1).returncode, 0)
        claims_dir = self.root / ".agents" / "collaboration" / "claims"
        record_path = claims_dir / "alpha.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["created_at"] = "2000-01-01T00:00:00Z"
        record["heartbeat_at"] = "2000-01-01T00:00:00Z"
        record["expires_at"] = "2000-01-01T00:01:00Z"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        rows = ai_handoff.status(str(self.root))
        self.assertTrue(rows[0]["expired"])
        self.assertNotEqual(self.claim("beta", "src/a.py").returncode, 0)

    def test_rejects_absolute_traversal_wildcard_root_and_outside_symlink(self):
        bad_scopes = ["/tmp/out.py", "../outside.py", "src/*.py", "."]
        for index, scope in enumerate(bad_scopes):
            with self.subTest(scope=scope):
                self.assertNotEqual(self.claim(f"bad{index}", scope).returncode, 0)
        outside = Path(self.temp.name).parent / (Path(self.temp.name).name + "_outside")
        try:
            outside.mkdir()
            link = self.root / "escape"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable")
            self.assertNotEqual(self.claim("escape", "escape/file.py").returncode, 0)
        finally:
            if outside.exists():
                outside.rmdir()

    def test_wrong_session_and_missing_heartbeat_release_fail(self):
        self.assertNotEqual(self.run_cli("heartbeat", "--session", "missing").returncode, 0)
        self.assertNotEqual(self.run_cli("release", "--session", "missing").returncode, 0)
        self.assertEqual(self.claim("owner", "src/a.py").returncode, 0)
        self.assertNotEqual(self.run_cli("heartbeat", "--session", "other").returncode, 0)
        self.assertNotEqual(self.run_cli("release", "--session", "other").returncode, 0)

    def test_heartbeat_and_release_require_existing_owner_record(self):
        self.assertEqual(self.claim("owner", "src/a.py").returncode, 0)
        updated = self.run_cli("heartbeat", "--session", "owner", "--checkpoint", "step two")
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertIn('"checkpoint": "step two"', updated.stdout)
        released = self.run_cli("release", "--session", "owner")
        self.assertEqual(released.returncode, 0, released.stderr)
        self.assertEqual(ai_handoff.status(str(self.root)), [])

    def test_busy_guard_is_reported_and_not_removed(self):
        claims_dir = self.root / ".agents" / "collaboration" / "claims"
        claims_dir.mkdir(parents=True)
        guard = claims_dir / ".guard"
        guard.write_text("other-owner", encoding="ascii")
        result = self.claim("owner", "src/a.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("busy", result.stderr)
        self.assertEqual(guard.read_text(encoding="ascii"), "other-owner")

    def test_simultaneous_processes_cannot_claim_the_same_scope(self):
        claims_dir = self.root / ".agents" / "collaboration" / "claims"
        claims_dir.mkdir(parents=True)
        commands = [
            [sys.executable, str(TOOL), "--repo", str(self.root), "claim", "--session", session,
             "--tool", "codex", "--model", "test-model", "--task", "bounded local task",
             "--scope", "src/shared.py"]
            for session in ("process-one", "process-two")
        ]
        processes = [subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for cmd in commands]
        outcomes = [process.communicate(timeout=10) + (process.returncode,) for process in processes]
        successful = [index for index, (_, _, code) in enumerate(outcomes) if code == 0]
        self.assertEqual(len(successful), 1, outcomes)
        loser = 1 - successful[0]
        self.assertEqual(outcomes[loser][2], 2, outcomes)
        retry_session = ("process-one", "process-two")[loser]
        retry = self.claim(retry_session, "src/shared.py")
        self.assertEqual(retry.returncode, 2, retry.stderr)
        self.assertIn("conflicts", retry.stderr)

    def test_malformed_claim_fails_closed_and_is_preserved(self):
        claims_dir = self.root / ".agents" / "collaboration" / "claims"
        claims_dir.mkdir(parents=True)
        record = claims_dir / "broken.json"
        record.write_text(json.dumps({"session": "broken", "scopes": []}), encoding="utf-8")
        before = record.read_bytes()
        blocked = self.claim("new-owner", "src/shared.py")
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("invalid scopes", blocked.stderr)
        self.assertEqual(record.read_bytes(), before)

    def test_timezone_naive_corrupt_timestamp_is_reported_without_traceback(self):
        self.assertEqual(self.claim("owner", "src/a.py").returncode, 0)
        record = self.root / ".agents" / "collaboration" / "claims" / "owner.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        data["expires_at"] = "2030-01-01T00:00:00"
        record.write_text(json.dumps(data), encoding="utf-8")
        result = self.run_cli("status")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_casefold_and_unicode_normalization_conflict(self):
        self.assertEqual(self.claim("first", "src/Café.py").returncode, 0)
        decomposed = "src/Cafe\u0301.py"
        self.assertNotEqual(self.claim("second", decomposed).returncode, 0)
        self.assertNotEqual(self.claim("third", "SRC/café.PY").returncode, 0)

    def test_status_does_not_modify_claim_files(self):
        self.assertEqual(self.claim("owner", "src/a.py").returncode, 0)
        record = self.root / ".agents" / "collaboration" / "claims" / "owner.json"
        before = record.read_bytes()
        output = self.run_cli("status")
        self.assertEqual(output.returncode, 0)
        self.assertEqual(record.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
