"""178 R3（C7，173 P3-6）：空库 alembic upgrade 自建 asset schema。

纯逻辑源码锁：读 backend/alembic/env.py 文本断言 DDL 与两条执行路径
（online 拿到 connection 后先建 schema；offline 在 run_migrations 前
发出同一 DDL），不连数据库。历史 revision 文件一律不改。
"""
from __future__ import annotations

from pathlib import Path

ENV_PY = Path(__file__).resolve().parents[2] / "alembic" / "env.py"
SRC = ENV_PY.read_text(encoding="utf-8")


def test_ensure_asset_schema_helper_emits_idempotent_ddl() -> None:
    start = SRC.find("def _ensure_asset_schema")
    assert start > -1, "env.py 必须定义 _ensure_asset_schema"
    block = SRC[start : SRC.find("def ", start + 10)]
    assert 'text("CREATE SCHEMA IF NOT EXISTS asset")' in block
    assert "connection.commit()" in block
    # 不带 IF NOT EXISTS 的裸建 schema 会让已有库重复执行炸掉，禁止。
    assert "CREATE SCHEMA asset" not in block.replace("CREATE SCHEMA IF NOT EXISTS asset", "")


def test_online_path_creates_schema_before_configure_and_migrations() -> None:
    start = SRC.find("def run_migrations_online")
    assert start > -1
    block = SRC[start : SRC.find("def ", start + 10)]
    conn_pos = block.find("with connectable.connect() as connection:")
    ensure_pos = block.find("_ensure_asset_schema(connection)")
    configure_pos = block.find("context.configure(")
    run_pos = block.find("context.run_migrations()")
    assert -1 not in (conn_pos, ensure_pos, configure_pos, run_pos)
    assert conn_pos < ensure_pos < configure_pos < run_pos, (
        "online 路径必须先建 schema 再 configure/run_migrations"
    )


def test_offline_path_emits_schema_ddl_before_migrations() -> None:
    start = SRC.find("def run_migrations_offline")
    assert start > -1
    block = SRC[start : SRC.find("def ", start + 10)]
    ddl_pos = block.find('context.execute(text("CREATE SCHEMA IF NOT EXISTS asset"))')
    run_pos = block.find("context.run_migrations()")
    assert ddl_pos > -1, "offline 路径必须发出同一 DDL，保证离线 SQL 脚本含该句"
    assert run_pos > -1
    assert ddl_pos < run_pos


def test_history_revisions_untouched_by_schema_bootstrap() -> None:
    """自建 schema 只允许存在于 env.py，不得进入任何历史 revision。"""
    versions = (ENV_PY.parent / "versions").glob("*.py")
    offenders = [
        str(path.name)
        for path in versions
        if "CREATE SCHEMA" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
