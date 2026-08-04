"""Extract review candidates from conventional ANSI JOIN SQL.

This tool never writes formal relationship assets or connects to a database.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


IDENT = r'(?:"[^"]+"|[A-Za-z_][\w$#]*)(?:\.(?:"[^"]+"|[A-Za-z_][\w$#]*)){0,2}'
TABLE_REF = re.compile(
    rf"\b(?:FROM|JOIN)\s+({IDENT})(?:\s+(?:AS\s+)?([A-Za-z_][\w$#]*))?",
    re.IGNORECASE,
)
JOIN_REF = re.compile(
    rf"\bJOIN\s+({IDENT})(?:\s+(?:AS\s+)?([A-Za-z_][\w$#]*))?\s+ON\s+"
    rf"(.+?)(?=\b(?:LEFT|RIGHT|FULL|INNER|CROSS)?\s*JOIN\b|\bWHERE\b|\bGROUP\s+BY\b|"
    rf"\bORDER\s+BY\b|\bHAVING\b|\bUNION\b|$)",
    re.IGNORECASE | re.DOTALL,
)
EQUALITY = re.compile(
    rf"({IDENT})\s*=\s*({IDENT})",
    re.IGNORECASE,
)
RESERVED = {
    "WHERE", "JOIN", "LEFT", "RIGHT", "FULL", "INNER", "CROSS", "ON", "GROUP",
    "ORDER", "HAVING", "UNION", "CONNECT", "START", "MODEL",
}


def strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\r\n]*", " ", sql)


def normalize_identifier(value: str) -> str:
    return ".".join(part.strip('"').upper() for part in value.strip().split("."))


def split_column(value: str) -> tuple[str | None, str]:
    parts = [part.strip('"') for part in value.split(".")]
    if len(parts) < 2:
        return None, parts[-1].upper()
    return parts[-2].upper(), parts[-1].upper()


def relation_key(
    from_table: str,
    from_columns: list[str],
    to_table: str,
    to_columns: list[str],
) -> tuple[tuple[str, tuple[str, ...]], tuple[str, tuple[str, ...]]]:
    left = (normalize_identifier(from_table), tuple(column.upper() for column in from_columns))
    right = (normalize_identifier(to_table), tuple(column.upper() for column in to_columns))
    return tuple(sorted((left, right)))  # type: ignore[return-value]


def load_existing(path: Path | None) -> dict[tuple, dict]:
    if path is None or not path.exists():
        return {}
    result: dict[tuple, dict] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = relation_key(
                row["from_table"],
                row["from_columns"].split("|"),
                row["to_table"],
                row["to_columns"].split("|"),
            )
            result[key] = row
    return result


def extract(sql: str, existing: dict[tuple, dict], source_file: str, system_code: str, dialect: str) -> dict:
    clean = re.sub(r"\s+", " ", strip_comments(sql)).strip()
    aliases: dict[str, str] = {}
    tables: list[str] = []
    warnings: list[str] = []

    for match in TABLE_REF.finditer(clean):
        table = normalize_identifier(match.group(1))
        alias = (match.group(2) or table.split(".")[-1]).upper()
        if alias in RESERVED:
            alias = table.split(".")[-1]
        aliases[alias] = table
        if table not in tables:
            tables.append(table)

    candidates = []
    for join in JOIN_REF.finditer(clean):
        joined_table = normalize_identifier(join.group(1))
        condition = join.group(3).strip()
        pairs = []
        qualifiers = condition
        for equality in EQUALITY.finditer(condition):
            left_alias, left_column = split_column(equality.group(1))
            right_alias, right_column = split_column(equality.group(2))
            if not left_alias or not right_alias or left_alias == right_alias:
                continue
            left_table = aliases.get(left_alias)
            right_table = aliases.get(right_alias)
            if not left_table or not right_table:
                continue
            pairs.append((left_table, left_column, right_table, right_column, equality.group(0)))
            qualifiers = qualifiers.replace(equality.group(0), " ")

        grouped: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
        for left_table, left_col, right_table, right_col, expression in pairs:
            grouped.setdefault((left_table, right_table), []).append((left_col, right_col, expression))

        if not grouped:
            warnings.append(f"JOIN {joined_table} 的 ON 条件未解析出跨别名等值键，需要人工检查")
            continue

        for (left_table, right_table), columns in grouped.items():
            left_columns = [item[0] for item in columns]
            right_columns = [item[1] for item in columns]
            key = relation_key(left_table, left_columns, right_table, right_columns)
            matched = existing.get(key)
            candidates.append(
                {
                    "from_table": left_table,
                    "from_columns": left_columns,
                    "to_table": right_table,
                    "to_columns": right_columns,
                    "join_condition": " AND ".join(item[2] for item in columns),
                    "qualifiers": re.sub(r"(?i)\bAND\b|\bOR\b|[()]", " ", qualifiers).strip(),
                    "intake_status": "existing" if matched else "candidate",
                    "existing_relation_id": matched.get("id") if matched else None,
                    "confidence": "existing" if matched else "C",
                }
            )

    upper = clean.upper()
    from_match = re.search(
        r"\bFROM\b(.+?)(?=\b(?:LEFT|RIGHT|FULL|INNER|CROSS)?\s*JOIN\b|\bWHERE\b|"
        r"\bGROUP\s+BY\b|\bORDER\s+BY\b|\bUNION\b|$)",
        upper,
    )
    if from_match and "," in from_match.group(1):
        warnings.append("检测到可能的旧式逗号连接；脚本不会自动推断 WHERE 中的隐式关系")
    if " EXECUTE IMMEDIATE " in f" {upper} ":
        warnings.append("检测到动态 SQL；必须展开运行期 SQL 后再解析")
    if re.search(r"\bUNION(?:\s+ALL)?\b", upper):
        warnings.append("检测到 UNION；需要分别核对每个分支的别名和关系")

    return {
        "source_sql_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        "source_file": source_file,
        "system_code": system_code,
        "dialect": dialect,
        "tables": tables,
        "aliases": aliases,
        "candidates": candidates,
        "warnings": warnings,
        "formal_assets_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract review-only relation candidates from SQL.")
    parser.add_argument("--sql-file", required=True, type=Path)
    parser.add_argument("--system-code", required=True)
    parser.add_argument("--dialect", default="oracle")
    parser.add_argument("--relationships", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    sql = args.sql_file.read_text(encoding="utf-8-sig")
    default_relationships = Path("开发起步包/数据资产_资产包/relationships.csv")
    relationship_path = args.relationships or (default_relationships if default_relationships.exists() else None)
    result = extract(
        sql,
        load_existing(relationship_path),
        str(args.sql_file),
        args.system_code,
        args.dialect,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"tables={len(result['tables'])} candidates={len(result['candidates'])} "
        f"warnings={len(result['warnings'])} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
