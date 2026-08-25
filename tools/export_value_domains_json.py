#!/usr/bin/env python
"""149 P3: 值域知识库单向导出（离线兜底 JSON + 148 导出视图重写）。

用法（仓库根 tools/ 目录）：
  python tools/export_value_domains_json.py                     # 导出 confirmed 值域 JSON
  python tools/export_value_domains_json.py --check             # 校验 JSON 与库内 confirmed 一致
  python tools/export_value_domains_json.py --regenerate-148    # 同时把 148 重写为平台导出视图

规则（149 §5）：
  - 单向导出 开起步包/数据资产_资产包/value_domains.json，含 schema 版本、内容哈希、
    导出时间、最大可接受龄期（默认 7 天）；超龄技能须提示用户。
  - 148 号文档停止手改：由 --regenerate-148 重写为平台导出视图（头部标注生成时间勿手改）；
    平台故障期例外改动须在恢复后回灌平台并在导出前仲裁。
  - 目标库由 backend/.env 的 APP_DB_URL 决定（或环境变量覆盖）；只读查询，不写平台库。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

JSON_PATH = REPO_ROOT / "开发起步包" / "数据资产_资产包" / "value_domains.json"
DOC_148_PATH = REPO_ROOT / "开发起步包" / "148_病案首页关键值域与离院方式口径字典.md"

SCHEMA_VERSION = "value-domains/v1"
MAX_AGE_DAYS = 7


def _canonical_payload(domains: list[dict]) -> str:
    return json.dumps(domains, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_hash(domains: list[dict]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_payload(domains).encode("utf-8")).hexdigest()


def load_confirmed(db) -> tuple[list[dict], dict]:
    from sqlalchemy import func, select

    from app.models.value_domain import AssetColumnValueDomain
    from app.services.value_domain_service import confirmed_domains_for_injection

    domains = confirmed_domains_for_injection(db)
    counts = {}
    for status in ("confirmed", "pending", "deprecated"):
        counts[status] = int(
            db.scalar(
                select(func.count()).select_from(AssetColumnValueDomain).where(
                    AssetColumnValueDomain.status == status
                )
            )
            or 0
        )
    counts["conflicted"] = int(
        db.scalar(
            select(func.count()).select_from(AssetColumnValueDomain).where(
                AssetColumnValueDomain.conflict_status == "conflicted"
            )
        )
        or 0
    )
    return domains, counts


def load_pending(db) -> list[dict]:
    """148 导出视图附带 pending 待核项（仅提示勿用，不进 JSON domains 与内容哈希）。"""
    from sqlalchemy import select

    from app.models.value_domain import AssetColumnValueDomain

    rows = db.scalars(
        select(AssetColumnValueDomain)
        .where(AssetColumnValueDomain.status == "pending")
        .order_by(
            AssetColumnValueDomain.schema_name,
            AssetColumnValueDomain.table_name,
            AssetColumnValueDomain.column_name,
        )
    ).all()
    return [
        {
            "system_code": r.system_code,
            "schema_name": r.schema_name,
            "table_name": r.table_name,
            "column_name": r.column_name,
            "code": r.code,
            "meaning": r.meaning,
            "domain_kind": r.domain_kind,
            "note": r.note,
        }
        for r in rows
    ]


def build_document(domains: list[dict], counts: dict) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "max_age_days": MAX_AGE_DAYS,
        "counts": {"injected_confirmed": len(domains), **counts},
        "content_sha256": _content_hash(domains),
        "domains": domains,
    }


def is_stale(doc: dict) -> bool:
    generated = datetime.fromisoformat(doc["generated_at"])
    return datetime.now(timezone.utc) - generated > timedelta(days=int(doc.get("max_age_days", MAX_AGE_DAYS)))


def check(json_path: Path) -> int:
    from app.core.db import SessionLocal

    if not json_path.exists():
        print(f"[check] FAIL: {json_path} 不存在，先运行导出")
        return 1
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        domains, counts = load_confirmed(db)
    finally:
        db.close()

    problems: list[str] = []
    json_domains = doc.get("domains", [])
    db_hash = _content_hash(domains)
    if doc.get("content_sha256") != db_hash:
        db_by_key = {
            (d["system_code"], d["source_code"], d["schema_name"], d["table_name"], d["column_name"], d["code"]): d
            for d in domains
        }
        json_by_key = {
            (d["system_code"], d["source_code"], d["schema_name"], d["table_name"], d["column_name"], d["code"]): d
            for d in json_domains
        }
        only_db = set(db_by_key) - set(json_by_key)
        only_json = set(json_by_key) - set(db_by_key)
        for key in sorted(only_db):
            problems.append(f"库内有 JSON 缺失: {key}")
        for key in sorted(only_json):
            problems.append(f"JSON 有库内缺失(已下线?): {key}")
        for key in sorted(set(db_by_key) & set(json_by_key)):
            if db_by_key[key]["meaning"] != json_by_key[key]["meaning"]:
                problems.append(f"meaning 不一致: {key}: 库内={db_by_key[key]['meaning']!r} JSON={json_by_key[key]['meaning']!r}")
            elif (db_by_key[key].get("version_no") or None) != (json_by_key[key].get("version_no") or None):
                problems.append(
                    f"version_no 不一致: {key}: 库内={db_by_key[key].get('version_no')} JSON={json_by_key[key].get('version_no')}"
                )
    if is_stale(doc):
        print(f"[check] WARN: 导出已超过最大龄期 {doc.get('max_age_days')} 天（generated_at={doc['generated_at']}），技能使用前须提示用户重新导出")
    if problems:
        print(f"[check] FAIL: JSON 与库内 confirmed 不一致（{len(problems)} 项）")
        for line in problems[:30]:
            print(f"  - {line}")
        return 1
    print(f"[check] PASS: JSON 与库内 confirmed 一致（{len(domains)} 条，hash {db_hash[:19]}…；"
          f"库内 pending={counts['pending']} conflicted={counts['conflicted']} 不入导出）")
    return 0


# ── 148 导出视图重写 ──────────────────────────────────────────────────────────

HEADER_148 = """> 类别：证据链（字段值域平台导出视图）

> ⚠️ 本文件为平台值域知识库导出视图（149 P3 起由 tools/export_value_domains_json.py --regenerate-148 重写），**勿手工编辑**。
> 平台为唯一权威源；平台故障期例外改动须在恢复后回灌平台并在导出前仲裁。值域申请走平台 API（AI 仅可提交 pending，确认须人工）。

"""

APPENDIX_148 = """
## 附录：暂未入值域库的补充口径（随导出保留，勿手改）

- 门诊疾病谱用 `OUTPDOCT.OUTP_MR_DIAG_DESC`（门诊病历诊断，约 315 万行，按 PATIENT_ID+VISIT_DATE+VISIT_NO 关联 CLINIC_MASTER）；该表在 16 快照有、未入 1234 表资产包。
- 病理数据在 ODS 8.216 的 `BL` schema（BL.PITAYA 主表：SPECRECVTIME 标本接收时间 / BBMC 标本名称 / ISFROZE=1 冰冻），**不在 HIS EXAM 检查系统**。
- 诊断书写规范差异：缺血性贫血→实际写"缺铁性贫血"；急性脑血管病→常具体化为脑出血/脑梗死。

## 维护约定

- 后续 AI 发现新值域证据（含实测数字与验证方法）时：平台可用则提交 pending 候选（149 API，证据必填），平台不可用时记录到本地待回灌清单，恢复后回灌；不得凭猜测新增值域。
- 值域确认、冲突裁决、废弃均为人工动作（value_domain:confirm 权限码）；AI 仅可提交 pending。
"""


def _group_domains(domains: list[dict]) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = {}
    for d in domains:
        key = (d["system_code"], d["schema_name"], d["table_name"], d["column_name"])
        groups.setdefault(key, []).append(d)
    return groups


def render_148(doc: dict, pending: list[dict] | None = None) -> str:
    lines: list[str] = [HEADER_148]
    lines.append("# 病案首页关键值域与离院方式口径字典（平台导出视图）\n")
    lines.append(f"> 导出时间：{doc['generated_at']}　|　内容哈希：{doc['content_sha256']}")
    lines.append(f"> 导出口径：仅 status=confirmed 且无未裁决冲突的值域（pending/冲突项见平台 `?conflicted=true` 列表）")
    lines.append(f"> 最大可接受龄期：{doc['max_age_days']} 天，超龄须重新导出后再供取数 AI 使用\n")
    lines.append("> 来源：规培基地/三甲复审取数实测（HIS 源端 + JHEMR report.r_pat_visit 交叉验证 + 用户人工确认），原始证据链见各条 evidence 与平台 `asset_column_value_domain_evidences`。\n")

    groups = _group_domains(doc["domains"])
    order = {"trap": 0, "enum": 1, "threshold": 2, "literal": 3}
    for (system, schema, table, column) in sorted(groups):
        entries = sorted(groups[(system, schema, table, column)], key=lambda d: (order.get(d["domain_kind"], 9), str(d["code"])))
        title = f"## {schema}.{table}.{column}（{system}）"
        traps = [e for e in entries if e["domain_kind"] == "trap"]
        normal = [e for e in entries if e["domain_kind"] != "trap"]
        lines.append("")
        lines.append(title)
        if normal:
            lines.append("")
            lines.append("| 类型 | 代码/值 | 含义 | 适用条件 | 版本 |")
            lines.append("|---|---|---|---|---|")
            for e in normal:
                scope = e.get("scope_condition") or "—"
                lines.append(f"| {e['domain_kind']} | {e['code']} | {e['meaning']} | {scope} | v{e.get('version_no') or '-'} |")
        for e in traps:
            lines.append("")
            lines.append(f"> 🚫 **陷阱（{e['code']}）**：{e['meaning']}")
            if e.get("note"):
                lines.append(">")
                lines.append(f"> {e['note']}")
        note_done = any(e.get("note") for e in normal)
        if note_done:
            lines.append("")
            for e in normal:
                if e.get("note"):
                    lines.append(f"- 代码 {e['code']}：{e['note']}")

    if pending:
        lines.append("")
        lines.append("## ⏳ 待核值域（平台 pending，人工核实前不得用于统计口径）")
        lines.append("")
        lines.append("| 字段 | 代码/值 | 平台含义（待核） | 说明 |")
        lines.append("|---|---|---|---|")
        for p in pending:
            field = f"{p['schema_name']}.{p['table_name']}.{p['column_name']}"
            lines.append(f"| {field} | {p['code']} | {p['meaning']} | {p.get('note') or '—'} |")

    lines.append(APPENDIX_148)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="149 P3 值域知识库导出")
    parser.add_argument("--check", action="store_true", help="校验 JSON 与库内 confirmed 一致（不写任何文件）")
    parser.add_argument("--regenerate-148", action="store_true", help="导出 JSON 的同时把 148 重写为平台导出视图")
    parser.add_argument("--output", type=Path, default=JSON_PATH, help="JSON 输出路径")
    args = parser.parse_args()

    if args.check:
        return check(args.output)

    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        domains, counts = load_confirmed(db)
        pending = load_pending(db)
    finally:
        db.close()
    doc = build_document(domains, counts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[export] 写出 {args.output}（confirmed 注入 {len(domains)} 条；"
          f"库内 pending={counts['pending']} conflicted={counts['conflicted']} 不导出）")

    if args.regenerate_148:
        DOC_148_PATH.write_text(render_148(doc, pending), encoding="utf-8")
        print(f"[export] 148 已重写为平台导出视图: {DOC_148_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
