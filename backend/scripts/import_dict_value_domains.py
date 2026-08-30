"""163 R2-E3（151 E3）：两字典表批量导入值域知识库（幂等，一律 pending）。

消费 151_两字典表探索与圈定清单_结果.json 的 circled 段（纯字典内容，零患者数据）：
  - PORTAL_SYS_DICT（DATA_CENTER）：DICT_CODE→DICT_NAME，定位键由圈定表指定；
  - EMR_FIRST_PAGE_ITEM_DICT（JHEMR）：ITEM_VALUE（库内存值）→ITEM_TEXT（对照码）。

硬规则（151 §2.2 + 163 R2）：
  - 字典导入一律 status=pending，永不自动 confirm；
  - 同键已有 confirmed 且 meaning 不一致 → 不改 meaning，仅 mark_conflict + 追加竞争含义证据；
  - pending 同键 meaning 漂移 → 刷新 meaning + 版本（字典刷新语义，收敛幂等）；
  - 批量审计一条 seed_import（module=value_domain）；
  - 规模门禁：单 scope 导入行数 ≤200，超限拒绝（回 151 候选清单）；
  - GB_CODE/GB_NAME 记 note。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.db import SessionLocal  # noqa: E402
from app.models.governance_base import GovernAuditLog  # noqa: E402
from app.models.value_domain import AssetColumnValueDomain  # noqa: E402
from app.services import value_domain_service as vds  # noqa: E402

SCALE_GATE = 200
METHOD = "sjzc live 限量采样 2026-08-29（163 R2 / 151 E1）"


def _portal_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    targets = {t["type_code"]: t for t in payload["circled"]["portal"]["types_selected"]}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in payload["circled"]["portal"]["rows"]:
        grouped.setdefault(row["type_code"], []).append(row)
    items: list[dict[str, Any]] = []
    for type_code, rows in grouped.items():
        spec = targets[type_code]
        for row in rows:
            note_parts = [f"PORTAL 字典 {type_code}（{row.get('type_name', '')}）"]
            if row.get("gb_code"):
                note_parts.append(
                    f"GB_CODE={row['gb_code']}" + (f"（{row['gb_name']}）" if row.get("gb_name") else "")
                )
            items.append(
                {
                    "key": spec["target"],
                    "code": row["dict_code"],
                    "meaning": row["dict_name"],
                    "note": "；".join(note_parts),
                    "evidence": {
                        "source_type": "dict_table",
                        "source_system": "DATA_CENTER",
                        "observed_meaning": row["dict_name"],
                        "method": METHOD,
                        "snippet_ref": f"PORTAL_SYS_DICT:{type_code}",
                        "sample_count": len(rows),
                    },
                }
            )
    return items


def _jhemr_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    specs = {f["field_name"]: f for f in payload["circled"]["jhemr"]["fields_selected"]}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in payload["circled"]["jhemr"]["rows"]:
        grouped.setdefault(row["field_name"], []).append(row)
    items: list[dict[str, Any]] = []
    for field_name, rows in grouped.items():
        spec = specs[field_name]
        for row in rows:
            value, code_text = row["item_value"], row["item_text"]
            meaning = value if (code_text is None or value == code_text) else f"{value}（对照码 {code_text}）"
            note_parts = [
                f"JHEMR 病案首页字典 {field_name}；ITEM_VALUE=库内存值、ITEM_TEXT=对照码（老文档§176）"
            ]
            if row.get("boh_code"):
                note_parts.append(f"boh {row.get('boh_name') or ''}→{row['boh_code']}")
            items.append(
                {
                    "key": spec["target"],
                    "code": value,
                    "meaning": meaning,
                    "note": "；".join(note_parts),
                    "evidence": {
                        "source_type": "dict_table",
                        "source_system": "JHEMR_VASTBASE",
                        "observed_meaning": meaning,
                        "method": METHOD,
                        "snippet_ref": f"EMR_FIRST_PAGE_ITEM_DICT:{field_name}",
                        "sample_count": len(rows),
                    },
                }
            )
    return items


def build_items(payload: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    if scope == "portal":
        return _portal_items(payload)
    if scope == "jhemr":
        return _jhemr_items(payload)
    raise ValueError(f"unknown scope: {scope}")


def run_import(
    db, payload: dict[str, Any], scope: str, dry_run: bool = False
) -> dict[str, Any]:
    items = build_items(payload, scope)
    if len(items) > SCALE_GATE:
        raise ValueError(
            f"规模门禁：{scope} 待导入 {len(items)} 行 > {SCALE_GATE}（超出部分回候选清单）"
        )

    stats = {
        "scope": scope,
        "payload_rows": len(items),
        "created": 0,
        "attached": 0,
        "already_current": 0,
        "refreshed": 0,
        "confirmed_conflicts": 0,
        "dry_run": bool(dry_run),
    }
    conflicts: list[str] = []

    for item in items:
        key = item["key"]
        existing = vds.find_by_key(
            db,
            system_code=key["system_code"],
            source_code=key["source_code"],
            schema_name=key["schema_name"],
            table_name=key["table_name"],
            column_name=key["column_name"],
            code=item["code"],
        )
        if existing is None:
            stats["created"] += 1
            if dry_run:
                continue
            row = AssetColumnValueDomain(
                system_code=key["system_code"],
                source_code=key["source_code"],
                schema_name=key["schema_name"],
                table_name=key["table_name"],
                column_name=key["column_name"],
                code=item["code"],
                meaning=item["meaning"],
                note=item["note"],
                domain_kind="enum",
                status="pending",
                conflict_status="none",
            )
            db.add(row)
            db.flush()
            db.add(vds.evidence_row(row.id, item["evidence"]))
            vds.next_version(
                db, row, change_reason=f"dict_import_151_{scope}", actor="dict_import_script",
                evidence_ref=item["evidence"]["snippet_ref"],
            )
            continue

        if existing.status == "confirmed":
            if vds.meanings_differ(existing.meaning, item["meaning"]):
                stats["confirmed_conflicts"] += 1
                conflicts.append(
                    f"{key['system_code']}|{key['schema_name']}.{key['table_name']}."
                    f"{key['column_name']}#{item['code']}: confirmed={existing.meaning!r} 字典={item['meaning']!r}"
                )
                if dry_run:
                    continue
                if not vds.evidence_duplicate(db, existing.id, item["evidence"]):
                    db.add(vds.evidence_row(existing.id, item["evidence"]))
                vds.mark_conflict(db, existing)
                continue
            if not vds.evidence_duplicate(db, existing.id, item["evidence"]):
                stats["attached"] += 1
                if dry_run:
                    continue
                db.add(vds.evidence_row(existing.id, item["evidence"]))
                continue
            stats["already_current"] += 1
            continue

        # pending（或其它非终态）既有行
        if vds.meanings_differ(existing.meaning, item["meaning"]):
            stats["refreshed"] += 1
            if dry_run:
                continue
            existing.meaning = item["meaning"]
            existing.note = item["note"]
            existing.updated_at = datetime.now(timezone.utc)
            if not vds.evidence_duplicate(db, existing.id, item["evidence"]):
                db.add(vds.evidence_row(existing.id, item["evidence"]))
            vds.next_version(
                db, existing, change_reason=f"dict_import_refresh_151_{scope}",
                actor="dict_import_script", evidence_ref=item["evidence"]["snippet_ref"],
            )
            continue
        if not vds.evidence_duplicate(db, existing.id, item["evidence"]):
            stats["attached"] += 1
            if dry_run:
                continue
            db.add(vds.evidence_row(existing.id, item["evidence"]))
            continue
        stats["already_current"] += 1

    stats["conflicts"] = conflicts
    if dry_run:
        db.rollback()
        return stats

    db.add(GovernAuditLog(
        module="value_domain",
        entity_type="column_value_domain",
        entity_ref=f"import:dict:{scope}",
        action="seed_import",
        after_data={k: v for k, v in stats.items() if k != "conflicts"},
        operator="dict_import_script",
        reason="163 R2 / 151 E3–E4 两字典表批量导入（一律 pending，永不自动 confirm）",
    ))
    db.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="163 R2 / 151 E3：两字典表值域批量导入（幂等、一律 pending）")
    parser.add_argument("--payload", default=str(_BACKEND_ROOT.parent / "开发起步包" / "151_两字典表探索与圈定清单_结果.json"))
    parser.add_argument("--scope", choices=["portal", "jhemr", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true", help="只读预演：不写库")
    args = parser.parse_args()

    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    scopes = ["portal", "jhemr"] if args.scope == "both" else [args.scope]

    exit_code = 0
    for scope in scopes:
        db = SessionLocal()
        try:
            stats = run_import(db, payload, scope, dry_run=args.dry_run)
            tag = "[dry-run]" if args.dry_run else "[import]"
            print(
                f"{tag} {scope}: payload={stats['payload_rows']} created={stats['created']} "
                f"attached={stats['attached']} refreshed={stats['refreshed']} "
                f"already_current={stats['already_current']} confirmed_conflicts={stats['confirmed_conflicts']}"
            )
            for line in stats["conflicts"]:
                print(f"  冲突（未改写，需人工裁决）: {line}")
            if stats["payload_rows"] > 0 and stats["created"] == 0 and stats["attached"] == 0 \
                    and stats["refreshed"] == 0 and stats["confirmed_conflicts"] == 0:
                print(f"  幂等收敛：{scope} 无待导入项")
        except ValueError as exc:
            print(f"[gate] {exc}")
            exit_code = 2
        finally:
            db.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
