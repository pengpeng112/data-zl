"""123 R3 / 118-U9：部署链 SSH known_hosts 失败关闭。

1) deploy/scripts/sync_local_to_server.py 与 backend 受控连接脚本不得调用 AutoAddPolicy；
2) 必须使用 RejectPolicy（或等价严格策略）；
3) 文档注释中出现 “杜绝 AutoAddPolicy” 字样不算违规，仅检测实际策略调用。
不连接任何主机。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
DEPLOY = REPO / "deploy"

DEPLOY_CHAIN_FILES = [
    DEPLOY / "scripts" / "sync_local_to_server.py",
    BACKEND / "scripts" / "tunnel_test_db.py",
    BACKEND / "app" / "services" / "db_connectors.py",
    BACKEND / "app" / "services" / "jhemr_identity_adapter.py",
]

# 实际启用 AutoAdd 的调用形态（注释/说明文字不算）。
_AUTO_ADD_CALL = re.compile(
    r"set_missing_host_key_policy\s*\(\s*(?:paramiko\.)?AutoAddPolicy\s*\(?\s*\)?\s*\)"
    r"|(?<![\w.])paramiko\.AutoAddPolicy\s*\("
)


def test_deploy_chain_no_auto_add_policy():
    missing = [str(p) for p in DEPLOY_CHAIN_FILES if not p.is_file()]
    assert not missing, f"missing deploy-chain files: {missing}"

    offenders = []
    for path in DEPLOY_CHAIN_FILES:
        text = path.read_text(encoding="utf-8", errors="replace")
        if _AUTO_ADD_CALL.search(text):
            offenders.append(str(path.relative_to(REPO)))
        strict = (
            "RejectPolicy" in text
            or "StrictHostKeyChecking" in text
            or "UserKnownHostsFile" in text
            or "known_hosts" in text
        )
        assert strict, f"{path.name} must enforce known_hosts / reject unknown hosts"

    assert not offenders, f"AutoAddPolicy call forbidden on deploy chain: {offenders}"


def test_sync_local_to_server_reject_policy_source():
    path = DEPLOY / "scripts" / "sync_local_to_server.py"
    text = path.read_text(encoding="utf-8", errors="replace")
    assert "RejectPolicy" in text
    assert "set_missing_host_key_policy(paramiko.RejectPolicy())" in text.replace(" ", "")
    assert _AUTO_ADD_CALL.search(text) is None
    assert "load_host_keys" in text or "load_system_host_keys" in text
