"""测试数据库不可绕过门禁（111 号 S1）。

放置位置：SQLAlchemy create_engine() 之前，而非 conftest。
当且仅当进程是 pytest 测试进程或显式 APP_ENV=test 时强制要求：
  - APP_TEST_DB_URL 显式给出且数据库名符合测试规则；
  - 实际 APP_DB_URL 与 APP_TEST_DB_URL 完全一致；
  - 目标不在非测试拒绝清单；
  - 测试进程不得以 APP_ENV=dev/production 运行。

普通生产/运维脚本（非 pytest 且 APP_ENV!=test）不受影响，保持既有运行路径。
不允许脚本通过伪造 pytest 标记或 test URL 绕过：伪造 URL 连不通或库名不含 test，
伪造 pytest 标记仍需真实隔离测试 URL 才能通过。
"""
from __future__ import annotations

import os
import sys

from sqlalchemy.engine import make_url


def is_pytest_process() -> bool:
    """判断当前进程是否处于 pytest 测试环境（在 create_engine 前被调用）。

    检测依据（任一命中即认为测试进程）：
    - PYTEST_CURRENT_TEST 或 PYTEST_VERSION 环境变量；
    - sys.modules 中已加载 pytest/_pytest（import app 前由 conftest 触发加载）。
    """
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("PYTEST_VERSION"):
        return True
    return any(name == "pytest" or name == "_pytest" or name.startswith("_pytest.")
               for name in sys.modules)


# 数据库名必须包含的子串（测试规则）。
TEST_DB_NAME_REQUIRED = "test"
# 显式拒绝的数据库名（即使含 test 也禁止作为测试目标）。
# 默认内置 111 号 S2 记录的陈旧非测试环境，防止再次被当作测试库。
_DEFAULT_TEST_DB_DENYLIST = ("data_asset", "asset", "postgres", "template0", "template1")
TEST_DB_NAME_DENYLIST = frozenset(
    name.strip().lower()
    for name in (
        *_DEFAULT_TEST_DB_DENYLIST,
        *(
            n.strip()
            for n in os.environ.get("APP_TEST_DATABASE_DENYLIST", "").split(",")
            if n.strip()
        ),
    )
    if name.strip()
)


class DatabaseGuardError(RuntimeError):
    """测试数据库门禁拒绝建连。"""


def validate_test_database_url(url: str) -> None:
    """在 create_engine 前校验测试连接。

    非测试进程（非 pytest 且 APP_ENV!=test）直接放行，不误伤生产/运维脚本。
    测试进程/测试环境缺任一必要条件即抛 DatabaseGuardError。
    """
    env = (os.environ.get("APP_ENV") or "").strip().lower()
    is_test_proc = is_pytest_process()

    if not is_test_proc and env != "test":
        return

    if is_test_proc and env not in ("", "test"):
        raise DatabaseGuardError(
            f"pytest 测试进程不得以 APP_ENV={env!r} 运行；必须为 APP_ENV=test"
        )

    test_url = (os.environ.get("APP_TEST_DB_URL") or "").strip()
    if not test_url:
        raise DatabaseGuardError(
            "测试进程缺少显式 APP_TEST_DB_URL；禁止回退到 APP_DB_URL/.env"
        )
    if "test" not in test_url.lower():
        raise DatabaseGuardError("APP_TEST_DB_URL 必须包含 'test' 以标识测试库")

    if url != test_url:
        raise DatabaseGuardError(
            "测试进程要求 APP_DB_URL 与 APP_TEST_DB_URL 完全一致；"
            "当前 APP_DB_URL 指向非测试库，拒绝建连"
        )

    parsed = make_url(test_url)
    dbname = (parsed.database or "").lower()
    if TEST_DB_NAME_REQUIRED not in dbname:
        raise DatabaseGuardError(
            f"测试数据库名 {dbname or '<空>'!r} 不满足测试规则（必须包含 "
            f"{TEST_DB_NAME_REQUIRED!r}），拒绝建连"
        )
    if dbname in TEST_DB_NAME_DENYLIST:
        raise DatabaseGuardError(
            f"测试数据库名 {dbname!r} 命中非测试拒绝清单，拒绝建连"
        )
