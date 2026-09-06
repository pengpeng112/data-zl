#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_test_environment.py — 测试环境三态预检器（185 号 C2；183-S3）。

只包装 `backend/app/core/database_guard.py` 的既有规则（URL 必含 test / 库名必含
test / 拒绝清单 / APP_DB_URL 一致性），不 import `tests/db_guard/`，不在 bash 里
另抽一套平行 Python 判断——规则唯一来源是 database_guard 本体。

三态：
  pure_logic_ready   未配置 APP_TEST_DB_URL：只能跑纯逻辑测试（给出可跑命令）
  integration_ready  URL 通过门禁规则 + 目标端口在监听（端口被占=复用语义，视为就绪；
                      占用者未知记 WARN 非 FAIL）
  migration_ready    integration_ready 基础上 --probe 实连 SELECT 1 成功
                      （库已可达、有权限；可清理性由「库名含 test 且不在拒绝清单」规则保证）

不做的事：不打印凭据（口令一律掩码）、不杀占用端口的进程、不跑 pytest/TRUNCATE/迁移。
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

GUARD_IMPORT_ERROR = ""
try:
    sys.path.insert(0, str(BACKEND))
    from app.core.database_guard import DatabaseGuardError, validate_test_database_url  # noqa: E402
except Exception as exc:  # pragma: no cover - 环境异常路径
    DatabaseGuardError = RuntimeError  # type: ignore[assignment]
    validate_test_database_url = None  # type: ignore[assignment]
    GUARD_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def mask_url(url: str) -> str:
    """口令掩码，凭据绝不进输出。"""
    if "://" in url and "@" in url:
        head, rest = url.split("://", 1)
        if "@" in rest:
            creds, hostpart = rest.rsplit("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                return f"{head}://{user}:***@{hostpart}"
    return url


def host_port_of(url: str) -> tuple[str, int] | None:
    """从 URL 提取 host:port（无端口的 PG 默认 5432）。解析失败返回 None。"""
    try:
        from sqlalchemy.engine import make_url

        u = make_url(url)
        return u.host or "127.0.0.1", u.port or 5432
    except Exception:
        return None


def probe_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """只探测端口是否在监听；不识别、不干预占用进程（复用语义）。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def guard_verdict(test_url: str, app_db_url: str | None) -> tuple[bool, str]:
    """复用 database_guard 规则判定 URL。

    以 APP_ENV=test 强制走门禁分支（本进程不是 pytest 时门禁默认放行，这里要的
    正是规则本身），判定完恢复原值。先后两次调用：
      ① validate(test_url)：存在性/test 标识/库名规则；
      ② validate(app_db_url)（若给了 APP_DB_URL）：一致性规则（url != APP_TEST_DB_URL 即拒）。
    """
    saved_env = os.environ.get("APP_ENV")
    saved_test_url = os.environ.get("APP_TEST_DB_URL")
    os.environ["APP_ENV"] = "test"
    os.environ["APP_TEST_DB_URL"] = test_url
    try:
        if validate_test_database_url is None:
            return False, f"database_guard 导入失败，无法执行唯一规则判定（{GUARD_IMPORT_ERROR}）"
        try:
            validate_test_database_url(test_url)
        except DatabaseGuardError as exc:
            return False, str(exc)
        if app_db_url:
            try:
                validate_test_database_url(app_db_url)
            except DatabaseGuardError as exc:
                return False, f"APP_DB_URL 一致性问题：{exc}"
        return True, "通过 database_guard 全部规则"
    finally:
        if saved_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = saved_env
        if saved_test_url is None:
            os.environ.pop("APP_TEST_DB_URL", None)
        else:
            os.environ["APP_TEST_DB_URL"] = saved_test_url


def evaluate(test_url: str, app_db_url: str | None, probe_connect: bool = False) -> dict:
    """核心判定，返回三态报告 dict（纯逻辑，不写任何东西）。"""
    result: dict = {"state": None, "reasons": [], "warns": [], "mask_url": None}
    if not test_url:
        result["state"] = "pure_logic_ready"
        result["reasons"].append("未配置 APP_TEST_DB_URL：数据库测试不可跑，仅纯逻辑测试可跑")
        result["commands"] = [
            "backend/.venv/Scripts/python.exe -m pytest backend/tests/db_guard backend/tests/alembic_env -q",
            "建隧道+推导 URL：source tools/dev_env.sh",
        ]
        return result

    result["mask_url"] = mask_url(test_url)
    ok, reason = guard_verdict(test_url, app_db_url)
    if not ok:
        result["state"] = "invalid_url"
        result["reasons"].append(reason)
        return result

    hp = host_port_of(test_url)
    if hp is None:
        result["state"] = "invalid_url"
        result["reasons"].append("URL 无法解析出 host:port")
        return result
    host, port = hp
    listening = probe_port(host, port)
    if not listening:
        result["state"] = "integration_blocked"
        result["reasons"].append(f"{host}:{port} 未监听（隧道未建？source tools/dev_env.sh）")
        return result

    # 端口在监听 = 就绪（复用语义）；不识别占用者，记 WARN 非 FAIL
    result["state"] = "integration_ready"
    result["warns"].append(
        f"{host}:{port} 已被占用/监听，按复用语义视为就绪（占用者未知，未做进程识别）"
    )
    if probe_connect:
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(test_url)
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                result["state"] = "migration_ready"
                result["reasons"].append("实连 SELECT 1 成功：库可达且有权限")
            finally:
                engine.dispose()
        except Exception as exc:
            result["warns"].append(
                f"--probe 实连失败，维持 integration_ready（不升级 migration_ready）：{type(exc).__name__}"
            )
    result.setdefault(
        "commands",
        [
            "backend/.venv/Scripts/python.exe -m pytest backend/tests -q  # 隔离库就绪后可跑 DB 测试",
        ],
    )
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="测试环境三态预检（包装 database_guard，只读不杀进程）")
    ap.add_argument("--url", default=None, help="显式测试 URL（默认读 APP_TEST_DB_URL；口令只掩码输出）")
    ap.add_argument("--probe", action="store_true", help="升级探测：实连 SELECT 1（migration_ready 判定）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args(argv)

    test_url = (args.url or os.environ.get("APP_TEST_DB_URL") or "").strip()
    app_db_url = os.environ.get("APP_DB_URL") or None
    report = evaluate(test_url, app_db_url, probe_connect=args.probe)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"测试环境预检：state={report['state']}")
        if report.get("mask_url"):
            print(f"  URL（掩码）：{report['mask_url']}")
        for r in report["reasons"]:
            print(f"  [info] {r}")
        for w in report["warns"]:
            print(f"  [warn] {w}")
        for c in report.get("commands", []):
            print(f"  [cmd] {c}")
    state = report["state"]
    return 0 if state in ("pure_logic_ready", "integration_ready", "migration_ready") else 1


if __name__ == "__main__":
    sys.exit(main())
