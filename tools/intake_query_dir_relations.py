"""Batch-extract HIS JOIN evidence from 取数 SQL/TXT. Review-only, no formal write."""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / ".agents" / "skills" / "sql-relation-intake" / "scripts"))
from extract_sql_relations import (  # type: ignore
    EQUALITY,
    RESERVED,
    extract,
    normalize_identifier,
    relation_key,
    split_column,
    strip_comments,
)

SKIP_NAME_PARTS = {
    "01_创建只读用户",
    "飞检-创建表",
    "模板列名",
    "QRY_CTL_SMOKE",
    "_query_templates",
    "docx_text",
}
HIS_TABLES = REPO / "开发起步包/数据资产_HIS源端资产包/his_source_tables.csv"
HIS_COLS = REPO / "开发起步包/数据资产_HIS源端资产包/his_source_columns.csv"
HIS_RELS = REPO / "开发起步包/数据资产_HIS源端资产包/his_source_relationships.csv"
ODS_RELS = REPO / "开发起步包/数据资产_资产包/relationships.csv"
ODS_COLS = REPO / "开发起步包/数据资产_资产包/columns.csv"


def load_his_tables() -> dict[str, list[str]]:
    owners: dict[str, list[str]] = defaultdict(list)
    with HIS_TABLES.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            owners[row["table_name"].upper()].append(row["source_owner"].upper())
    return owners


def load_his_columns() -> set[tuple[str, str]]:
    cols: set[tuple[str, str]] = set()
    with HIS_COLS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            cols.add((f"{row['source_owner'].upper()}.{row['table_name'].upper()}", row["column_name"].upper()))
    return cols


def load_ods_columns() -> set[tuple[str, str]]:
    cols: set[tuple[str, str]] = set()
    if not ODS_COLS.exists():
        return cols
    with ODS_COLS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            schema = (row.get("schema_name") or row.get("schema") or "").upper()
            table = (row.get("table_name") or "").upper()
            col = (row.get("column_name") or "").upper()
            if table and col:
                cols.add((f"{schema}.{table}" if schema else table, col))
                cols.add((table, col))
    return cols


def load_his_rels() -> dict[tuple, dict]:
    result = {}
    with HIS_RELS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            keys = [part for part in re.split(r"[+|]", row["join_keys"]) if part]
            key = relation_key(row["from_table"], keys, row["to_table"], keys)
            result[key] = row
    return result


def load_ods_rels() -> dict[tuple, dict]:
    result = {}
    with ODS_RELS.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = relation_key(
                row["from_table"],
                row["from_columns"].split("|"),
                row["to_table"],
                row["to_columns"].split("|"),
            )
            result[key] = row
    return result


OWNER_ALIASES = {
    "HIS": ("MEDREC", "COMM", "ORDADM", "LAB", "EXAM", "INPBILL", "OUTPBILL", "OUTPADM", "INPADM", "DRUG_USER", "SURGERY"),
}


def alias_tables(table: str) -> list[str]:
    t = normalize_identifier(table)
    names = {t}
    if "." not in t:
        return list(names)
    owner, name = t.split(".", 1)
    if owner == "HIS":
        for alt in OWNER_ALIASES["HIS"]:
            names.add(f"{alt}.{name}")
    elif owner in OWNER_ALIASES["HIS"]:
        names.add(f"HIS.{name}")
    return list(names)


def qualify(table: str, owners: dict[str, list[str]]) -> tuple[str, str]:
    t = normalize_identifier(table)
    if "." in t:
        owner, name = t.split(".", 1)
        if owner == "HIS":
            hits = owners.get(name, [])
            if len(hits) == 1:
                return f"{hits[0]}.{name}", "resolved_his_unique"
            preferred = [o for o in hits if o in OWNER_ALIASES["HIS"]]
            if len(preferred) == 1:
                return f"{preferred[0]}.{name}", "resolved_his_preferred"
            if preferred:
                return t, "ambiguous_his:" + ",".join(preferred)
        return t, "qualified"
    hits = owners.get(t, [])
    if len(hits) == 1:
        return f"{hits[0]}.{t}", "resolved_unique"
    if not hits:
        return t, "missing"
    preferred = [o for o in hits if o in {"MEDREC", "COMM", "ORDADM", "LAB", "EXAM", "INPBILL", "OUTPBILL", "DRUG_USER"}]
    if len(preferred) == 1:
        return f"{preferred[0]}.{t}", "resolved_preferred"
    return t, "ambiguous:" + ",".join(hits)


def split_statements(sql: str) -> list[str]:
    parts = re.split(r";\s*(?=(?:SELECT|WITH|CREATE)\b)", sql, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def extract_implicit(sql: str) -> list[dict]:
    clean = re.sub(r"\s+", " ", strip_comments(sql)).strip()
    aliases: dict[str, str] = {}
    from_match = re.search(
        r"\bFROM\b(.+?)(?=\b(?:LEFT|RIGHT|FULL|INNER|CROSS)?\s*JOIN\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bUNION\b|$)",
        clean,
        re.IGNORECASE,
    )
    if not from_match or "," not in from_match.group(1):
        return []
    for item in from_match.group(1).split(","):
        token = item.strip()
        if not token:
            continue
        bits = token.split()
        table = normalize_identifier(bits[0])
        alias = table.split(".")[-1]
        if len(bits) >= 2 and bits[1].upper() not in RESERVED:
            alias = bits[-1].upper().strip('"')
        aliases[alias] = table
    where_match = re.search(r"\bWHERE\b(.+?)(?=\bGROUP\s+BY\b|\bORDER\s+BY\b|\bUNION\b|$)", clean, re.IGNORECASE)
    if not where_match:
        return []
    grouped: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
    for equality in EQUALITY.finditer(where_match.group(1)):
        left_alias, left_col = split_column(equality.group(1))
        right_alias, right_col = split_column(equality.group(2))
        if not left_alias or not right_alias or left_alias == right_alias:
            continue
        left_table = aliases.get(left_alias.upper())
        right_table = aliases.get(right_alias.upper())
        if not left_table or not right_table:
            continue
        grouped.setdefault((left_table, right_table), []).append((left_col, right_col, equality.group(0)))
    out = []
    for (left_table, right_table), cols in grouped.items():
        out.append(
            {
                "from_table": left_table,
                "from_columns": [c[0] for c in cols],
                "to_table": right_table,
                "to_columns": [c[1] for c in cols],
                "join_condition": " AND ".join(c[2] for c in cols),
                "qualifiers": "implicit_comma_join",
                "parse_kind": "implicit_where",
            }
        )
    return out


def iter_sql_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if path.suffix.lower() not in {".sql", ".txt"}:
            continue
        text = str(path)
        if any(part in text for part in SKIP_NAME_PARTS):
            continue
        if "抗菌" in path.parts and path.suffix.lower() == ".txt" and "sql" not in path.name.lower():
            continue
        files.append(path)
    return files


def main() -> int:
    root = REPO / "取数"
    owners = load_his_tables()
    his_cols = load_his_columns()
    ods_cols = load_ods_columns()
    his_rels = load_his_rels()
    ods_rels = load_ods_rels()
    merged: dict[tuple, dict] = {}
    file_stats = []

    for path in iter_sql_files(root):
        try:
            sql = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            sql = path.read_text(encoding="gb18030", errors="ignore")
        rel_sql = path.relative_to(REPO).as_posix()
        found = 0
        for stmt in split_statements(sql):
            parsed = extract(stmt, {}, rel_sql, "HIS_SOURCE", "oracle")
            cands = parsed["candidates"]
            for item in extract_implicit(stmt):
                cands.append({**item, "intake_status": "candidate", "confidence": "C"})
            for cand in cands:
                from_q, from_res = qualify(cand["from_table"], owners)
                to_q, to_res = qualify(cand["to_table"], owners)
                cand["from_table"] = from_q
                cand["to_table"] = to_q
                cand["from_resolve"] = from_res
                cand["to_resolve"] = to_res
                from_ok = all((from_q, col) in his_cols or (from_q, col) in ods_cols for col in cand["from_columns"])
                to_ok = all((to_q, col) in his_cols or (to_q, col) in ods_cols for col in cand["to_columns"])
                cand["metadata_ok"] = bool(from_ok and to_ok and "." in from_q and "." in to_q)
                key = relation_key(from_q, cand["from_columns"], to_q, cand["to_columns"])
                his_hit = his_rels.get(key)
                ods_hit = ods_rels.get(key)
                if not his_hit and not ods_hit:
                    for fa in alias_tables(from_q):
                        for ta in alias_tables(to_q):
                            alt = relation_key(fa, cand["from_columns"], ta, cand["to_columns"])
                            his_hit = his_hit or his_rels.get(alt)
                            ods_hit = ods_hit or ods_rels.get(alt)
                if his_hit or ods_hit:
                    cand["intake_status"] = "existing"
                    cand["confidence"] = "existing"
                    cand["existing_relation_id"] = (his_hit or {}).get("relationship_id") or (ods_hit or {}).get("id")
                elif not cand["metadata_ok"] or from_res.startswith("ambiguous") or to_res.startswith("ambiguous") or from_res == "missing" or to_res == "missing":
                    cand["intake_status"] = "rejected" if from_res == "missing" or to_res == "missing" else "partial"
                    cand["confidence"] = "D"
                else:
                    same = cand["from_columns"] == cand["to_columns"]
                    cand["intake_status"] = "candidate"
                    cand["confidence"] = "B" if same and cand["from_columns"] in (
                        ["PATIENT_ID", "VISIT_ID"],
                        ["PATIENT_ID"],
                        ["TEST_NO"],
                        ["EXAM_NO"],
                        ["ORDER_NO"],
                    ) else "C"
                rec = merged.setdefault(
                    key,
                    {
                        **cand,
                        "source_files": [],
                        "evidence_count": 0,
                    },
                )
                if rel_sql not in rec["source_files"]:
                    rec["source_files"].append(rel_sql)
                rec["evidence_count"] += 1
                found += 1
        file_stats.append({"file": rel_sql, "candidates": found})

    items = list(merged.values())
    summary = {
        "files": len(file_stats),
        "unique_relations": len(items),
        "existing": sum(1 for i in items if i["intake_status"] == "existing"),
        "candidate": sum(1 for i in items if i["intake_status"] == "candidate"),
        "partial": sum(1 for i in items if i["intake_status"] == "partial"),
        "rejected": sum(1 for i in items if i["intake_status"] == "rejected"),
    }
    out_dir = REPO / "取数/_query_outbox/SQL_RELATION_INTAKE_20260818"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps({"summary": summary, "files": file_stats}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "candidates.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
