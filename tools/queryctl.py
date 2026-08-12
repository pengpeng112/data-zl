#!/usr/bin/env python3
"""126 P1 queryctl — local workspace helper for multi-AI query packages.

Does not embed credentials. Platform sync uses APP_DB_URL / env HTTP if configured.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = ROOT / "取数"
TEMPLATES = DEFAULT_WORKSPACE / "_query_templates"

FORBIDDEN = {
    "INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "CALL", "EXEC", "EXECUTE",
}


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_yaml_or_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".json"}:
        return json.loads(text)
    # Minimal YAML subset: key: value (no nested lists required for validate)
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except Exception:
        # fallback: parse simple key: value lines
        data: dict = {}
        for line in text.splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
        return data


def cmd_init(args: argparse.Namespace) -> int:
    ws = Path(args.workspace)
    for sub in (
        "_query_templates",
        "_query_context",
        "_query_inbox",
        "_query_working",
        "_query_outbox",
        "_query_synced",
        "_query_quarantine",
        "_query_results",
        ".query_state",
    ):
        (ws / sub).mkdir(parents=True, exist_ok=True)

    code = args.query_code or f"QRY-{_now_stamp()}-0001"
    pack_name = args.pack or code
    dest = ws / "_query_working" / pack_name
    dest.mkdir(parents=True, exist_ok=True)

    yaml_path = dest / "query.yaml"
    sql_path = dest / "query.sql"
    exp_path = dest / "explanation.md"
    if not yaml_path.exists():
        yaml_path.write_text(
            f"""query_code: {code}
title: {args.title or code}
purpose: {args.purpose or '待填写业务用途'}
system_code: {args.system_code or 'DATA_CENTER'}
source_code: {args.source_code or 'ods_8_216'}
dialect: {args.dialect or 'oracle'}
status: captured
period_field:
grain: month
parameters: {{}}
metric_refs: []
recipe_refs: []
sensitivity: aggregate
limitations: []
result_storage: none
ai_source:
  provider: unknown
  model: unknown
  session_ref: local-only
""",
            encoding="utf-8",
        )
    if not sql_path.exists():
        sql_path.write_text(
            "SELECT 1 AS ok FROM dual WHERE 1 = 0\n",
            encoding="utf-8",
        )
    if not exp_path.exists():
        exp_path.write_text(
            f"# {code}\n\n## 业务目的\n\n待填写\n\n## 限制说明\n\n待填写\n",
            encoding="utf-8",
        )
    print(json.dumps({"ok": True, "pack": str(dest), "query_code": code}, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    pack = Path(args.pack)
    yaml_file = pack / "query.yaml"
    sql_file = pack / "query.sql"
    errors: list[str] = []
    warnings: list[str] = []
    if not yaml_file.exists():
        errors.append("缺少 query.yaml")
    if not sql_file.exists():
        errors.append("缺少 query.sql")
    meta = _load_yaml_or_json(yaml_file) if yaml_file.exists() else {}
    sql = sql_file.read_text(encoding="utf-8") if sql_file.exists() else ""
    # strip line/block comments before keyword checks
    sql_body = re.sub(r"--[^\n]*", " ", sql)
    sql_body = re.sub(r"/\*.*?\*/", " ", sql_body, flags=re.S)
    upper = re.sub(r"\s+", " ", sql_body.upper()).strip()
    if ";" in sql_body.rstrip().rstrip(";"):
        errors.append("禁止多语句")
    first = upper.split()[0] if upper.split() else ""
    if first not in {"SELECT", "WITH"}:
        errors.append(f"只允许 SELECT/WITH，当前={first or '(empty)'}")
    for kw in FORBIDDEN:
        if re.search(rf"\b{kw}\b", upper):
            errors.append(f"禁止关键字: {kw}")
    for field in ("query_code", "title", "system_code", "source_code", "dialect"):
        if not meta.get(field):
            warnings.append(f"清单缺少字段: {field}")
    # credential leakage
    if re.search(r"(password|passwd|token)\s*[:=]", sql, re.I):
        errors.append("SQL 疑似包含凭据")
    sha = _sha256_text(re.sub(r"\s+", " ", sql.strip().upper()))
    result = {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "sql_sha256": sha,
        "query_code": meta.get("query_code"),
        "pack": str(pack),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


def cmd_submit(args: argparse.Namespace) -> int:
    """Validate and stage to outbox; optional platform ingest via APP_TEST/APP_DB."""
    pack = Path(args.pack)
    rc = cmd_validate(argparse.Namespace(pack=str(pack), workspace=args.workspace))
    # re-run validate logic without double print - simplify: call internal
    if rc != 0 and not args.force:
        # move to quarantine
        ws = Path(args.workspace)
        q = ws / "_query_quarantine" / pack.name
        if pack.exists() and pack.resolve() != q.resolve():
            q.parent.mkdir(parents=True, exist_ok=True)
            if q.exists():
                shutil.rmtree(q)
            shutil.copytree(pack, q)
        print(json.dumps({"ok": False, "staged": "quarantine", "path": str(q)}, ensure_ascii=False))
        return 2

    ws = Path(args.workspace)
    out = ws / "_query_outbox" / pack.name
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(pack, out)

    # state hash
    sql = (pack / "query.sql").read_text(encoding="utf-8")
    state_dir = ws / ".query_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{pack.name}.json").write_text(
        json.dumps(
            {
                "pack": pack.name,
                "sql_sha256": _sha256_text(sql),
                "staged_at": datetime.now(timezone.utc).isoformat(),
                "status": "outbox",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    platform = None
    if args.to_platform:
        platform = _platform_ingest(pack, dry_run=args.dry_run)
        if platform and platform.get("ok") and not args.dry_run:
            synced = ws / "_query_synced" / pack.name
            if synced.exists():
                shutil.rmtree(synced)
            shutil.copytree(out, synced)
            meta_path = synced / "platform.json"
            meta_path.write_text(json.dumps(platform, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {"ok": True, "outbox": str(out), "platform": platform},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _platform_ingest(pack: Path, dry_run: bool = False) -> dict:
    """Ingest via local app services when APP_DB_URL points to platform/test DB."""
    meta = _load_yaml_or_json(pack / "query.yaml")
    sql = (pack / "query.sql").read_text(encoding="utf-8")
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "query_code": meta.get("query_code"),
            "sql_sha256": _sha256_text(sql),
        }
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from app.core.db import SessionLocal
        from app.services.query_intake import ingest_query

        db = SessionLocal()
        try:
            result = ingest_query(
                db,
                query_code=str(meta.get("query_code") or pack.name),
                title=str(meta.get("title") or meta.get("query_code") or pack.name),
                sql_text=sql,
                purpose=meta.get("purpose"),
                system_code=meta.get("system_code"),
                source_code=meta.get("source_code"),
                dialect=str(meta.get("dialect") or "oracle"),
                grain=meta.get("grain"),
                period_field=meta.get("period_field"),
                limitations=meta.get("limitations") if isinstance(meta.get("limitations"), list) else [],
                source_path=str(pack),
                ai_source=meta.get("ai_source") if isinstance(meta.get("ai_source"), dict) else None,
                created_by="queryctl",
            )
            db.commit()
            return {"ok": True, "dry_run": False, **result}
        finally:
            db.close()
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def cmd_context(args: argparse.Namespace) -> int:
    ws = Path(args.workspace)
    ctx_dir = ws / "_query_context"
    ctx_dir.mkdir(parents=True, exist_ok=True)
    note = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "优先调用平台 GET /api/v1/queries/ai/context 与 system-context；本文件仅为本地占位",
        "safety": "不含凭据与患者明细",
        "system_code": args.system_code,
    }
    out = ctx_dir / f"context_{(args.system_code or 'ALL').lower()}.json"
    out.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="queryctl", description="126 query workspace control")
    p.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    sub = p.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="create working query pack")
    init_p.add_argument("--query-code")
    init_p.add_argument("--pack")
    init_p.add_argument("--title")
    init_p.add_argument("--purpose")
    init_p.add_argument("--system-code")
    init_p.add_argument("--source-code")
    init_p.add_argument("--dialect", default="oracle")
    init_p.set_defaults(func=cmd_init)

    val_p = sub.add_parser("validate", help="validate pack")
    val_p.add_argument("pack")
    val_p.set_defaults(func=cmd_validate)

    sub_p = sub.add_parser("submit", help="stage to outbox; optional platform ingest")
    sub_p.add_argument("pack")
    sub_p.add_argument("--to-platform", action="store_true")
    sub_p.add_argument("--dry-run", action="store_true")
    sub_p.add_argument("--force", action="store_true")
    sub_p.set_defaults(func=cmd_submit)

    ctx_p = sub.add_parser("context", help="write local context placeholder")
    ctx_p.add_argument("--system-code")
    ctx_p.set_defaults(func=cmd_context)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
