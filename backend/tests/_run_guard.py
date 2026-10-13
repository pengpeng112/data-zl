"""tests/_run_guard.py — pytest 运行期守卫（215 号 E2）。

两个职责，规则唯一来源（防各 conftest 自带一套平行判断漂移）：

1. 隔离库互斥（advisory lock）：根 conftest 在启动时对 APP_TEST_DB_URL 取
   PostgreSQL 会话级咨询锁。第二个 pytest 进程对同一隔离库启动时立即失败
   ——双进程共享一个可 TRUNCATE 的库会互相清场（212 DEF212-001 实证）。
   锁随持锁连接存活，进程退出自动释放，无需显式清理。

2. 纯逻辑哨兵作用域：纯逻辑子目录 conftest 的哨兵 URL 只在「本次运行没有
   真实测试库配置」时落 env。混合目录运行（纯逻辑 + 根级 DB 测试同进程）
   时根 conftest 已设置真实 APP_TEST_DB_URL，哨兵必须让位，否则收集期
   os.environ 全局写会污染同进程后续所有 DB 集成测试。

不打印口令；不做进程管理；不替代 database_guard 的 URL 门禁。
"""
from __future__ import annotations

import hashlib
import os


def run_lock_key(db_url: str) -> int:
    """同一测试库 URL 映射到同一把锁（sha256 前 8 字节，带符号 64 位）。"""
    digest = hashlib.sha256(db_url.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def try_acquire_run_lock(db_url: str):
    """尝试为本 pytest 进程取得该测试库的独占锁。

    返回 ``(connection, True)`` 表示取得（调用方必须在进程存续期引用该连接，
    连接关闭即释放锁）；``(None, False)`` 表示已有别的活跃 pytest 会话持有。
    连接失败向上抛出，由调用方决定 fail-fast 文案。
    """
    import psycopg

    dsn = db_url.replace("postgresql+psycopg://", "postgresql://", 1)
    conn = psycopg.connect(dsn, connect_timeout=10, autocommit=True)
    try:
        acquired = conn.execute(
            "SELECT pg_try_advisory_lock(%s)", (run_lock_key(db_url),)
        ).fetchone()[0]
    except Exception:
        conn.close()
        raise
    if not acquired:
        conn.close()
        return None, False
    return conn, True


def has_real_test_db_url() -> bool:
    """当前进程是否已配置真实（非哨兵占位）测试库 URL。

    与根 conftest 门禁同口径：URL 存在且含 "test"。纯逻辑哨兵 URL
    本身也含 "test"（满足 database_guard），因此哨兵一旦落下，后续
    子目录 conftest 也不会重复改写。
    """
    current = os.environ.get("APP_TEST_DB_URL", "")
    return bool(current) and "test" in current.lower()


def apply_pure_logic_env_sentinel(sentinel: str) -> bool:
    """纯逻辑子目录的哨兵 env 写入（条件化）。

    无真实测试库配置时落哨兵（满足传递导入 app.core.db 的守卫，引擎惰性
    构造从不连接）；已有真实配置（典型=混合目录运行）时原样保留，返回
    False 表示未落哨兵。
    """
    if has_real_test_db_url():
        return False
    os.environ["APP_TEST_DB_URL"] = sentinel
    os.environ["APP_DB_URL"] = sentinel
    os.environ.setdefault("APP_ENV", "test")
    return True
