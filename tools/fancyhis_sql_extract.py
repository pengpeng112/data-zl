"""fancyhis T1: extract SQL dictionary from Fancy.His.Micro.dll string heap.

Method (user-validated): pull UTF-16LE printable runs >= 8 chars, then keep
strings that look like SQL statements; classify owner-qualified table tokens
after FROM/JOIN/INTO/UPDATE. Read-only against the vendor DLL copy.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DLL = Path(r"E:\fancyhis\HisApi\HisApi\Fancy.His.Micro.dll")
OUT_DIR = Path(r"F:\python\数据资产\开发起步包\数据资产_新HIS逆向资产包")

SQL_PREFIX_RE = re.compile(
    r"^(SELECT|INSERT|INSERT\s+INTO|UPDATE|DELETE|DELETE\s+FROM|MERGE|WITH|DECLARE|BEGIN|TRUNCATE|CALL)\b",
    re.IGNORECASE,
)
UTF16_RUN_RE = re.compile(rb"(?:[\x20-\x7e]\x00){8,}")
TABLE_TOKEN_RE = re.compile(
    r"(?:\bFROM\b|\bJOIN\b|\bINTO\b|\bUPDATE\b|\bMERGE\s+INTO\b)\s+([A-Za-z_][A-Za-z0-9_$#]*)(?:\.([A-Za-z_][A-Za-z0-9_$#]*))?",
    re.IGNORECASE,
)
# owner prefixes that signal a library / schema directly
KNOWN_OWNER_PREFIXES = {"MEDREC", "COMM", "FXHIS", "HIS", "ODS", "HRP", "SM", "GW", "JH", "JHEMR", "BIS"}

# heuristic classification of bare table names to fancyhis dbconfig keys
MASTER_PAT = re.compile(r"^(SYS_|PUB_|SYS\d|CFG_|ORG_|ROLE_|USER_|MENU_)")
OLD_HIS_PAT = re.compile(
    r"^(PAT_|OUTP_|INP_|LAB_|EXAM_|ORD_|OPER_|COMM\.|MED_|DRUG_|CHARGE_|BILL_|ACCT_|TST_|V_|FIN_|INSUR|YB_|MR_)"
)


def classify_library(owner: str, table: str) -> str:
    if owner:
        if owner.upper() in {"MEDREC"}:
            return "MEDREC(老HIS病案owner)"
        if owner.upper() in {"COMM"}:
            return "老HIS(COMM owner)"
        if owner.upper() in {"FXHIS"}:
            return "老HIS(FXHIS owner)"
        return f"owner:{owner.upper()}"
    name = table.upper()
    if MASTER_PAT.match(name):
        return "masterdb(新HIS主库,SYS_/PUB_)"
    if OLD_HIS_PAT.match(name):
        return "HisRead/HisV2Open(老HIS风格)"
    if name.startswith(("IPC_",)) or "PIVAS" in name:
        return "ipc*(SqlServer,静配/ICU)"
    if name.startswith(("BLOOD", "TRANSFUS")):
        return "bloodSystem"
    if name.startswith(("LOG", "OPERATE_LOG")):
        return "HISLOG"
    return "未归类(待核)"


def main() -> int:
    data = DLL.read_bytes()
    strings = [m.group().decode("utf-16-le") for m in UTF16_RUN_RE.finditer(data)]
    sqls: dict[str, int] = Counter()
    for text in strings:
        stripped = text.strip()
        if not SQL_PREFIX_RE.match(stripped):
            continue
        if len(stripped) < 12:
            continue
        normalized = re.sub(r"\s+", " ", stripped)
        sqls[normalized] += 1

    table_hits: Counter = Counter()
    table_in_sql: dict[str, set] = defaultdict(set)
    for sql, _count in sqls.items():
        for match in TABLE_TOKEN_RE.finditer(sql):
            part1, part2 = match.group(1), match.group(2)
            if part2:
                owner, table = part1, part2
            else:
                owner, table = "", part1
            if owner.upper() in KNOWN_OWNER_PREFIXES or not part2:
                if part2:
                    key = f"{owner}.{table}".upper()
                else:
                    key = table.upper()
                table_hits[key] += 1
                table_in_sql[key].add(sql[:120])

    table_map = []
    for key, count in table_hits.most_common():
        if "." in key:
            owner, table = key.split(".", 1)
        else:
            owner, table = "", key
        table_map.append({
            "table": key,
            "library_class": classify_library(owner, table),
            "sql_ref_count": count,
            "sample_sql_head": sorted(table_in_sql[key])[:2],
        })

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "source_dll": str(DLL),
        "dll_size": DLL.stat().st_size,
        "utf16_strings_total": len(strings),
        "sql_statements": [
            {"sql": sql, "count": count, "length": len(sql)}
            for sql, count in sorted(sqls.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "sql_total": len(sqls),
        "tables": table_map,
        "table_total": len(table_map),
        "library_class_summary": dict(Counter(t["library_class"] for t in table_map)),
    }
    out_path = OUT_DIR / "fancyhis_sql_dictionary.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "strings": len(strings),
        "sql_total": result["sql_total"],
        "table_total": result["table_total"],
        "library_class_summary": result["library_class_summary"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
