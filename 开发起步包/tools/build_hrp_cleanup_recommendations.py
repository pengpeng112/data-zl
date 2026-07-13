from __future__ import annotations

import base64
import csv
import datetime as dt
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
PKG_DIR = BASE_DIR / "数据资产_HRP源端资产包"
TABLES_PATH = PKG_DIR / "hrp_source_tables.csv"
COLUMNS_PATH = PKG_DIR / "hrp_source_columns.csv"
CONSTRAINTS_PATH = PKG_DIR / "hrp_source_constraints.csv"
INDEXES_PATH = PKG_DIR / "hrp_source_indexes.csv"

SOURCE_SYSTEM = "HRP"
SOURCE_DB = "10.10.10.23:1521/hrpdb"

DATE_PAT = re.compile(
    r"(^|_)(19|20)\d{2}[-_]?([01]\d)[-_]?([0-3]\d)($|_)|"
    r"(^|_)(19|20)\d{2}[-_]?([01]\d)($|_)"
)
BACKUP_PAT = re.compile(
    r"(^|_)(BAK|BACKUP|BK|COPY|OLD|HIS|HISTORY|TEMP|TMP|TEST)($|_)|"
    r"(_BAK\d*|_BK\d*|_OLD\d*|_TMP\d*)$",
    re.I,
)
LOG_PAT = re.compile(r"(^|_)(LOG|AUDIT|TRACE|ERR|ERROR|SECURITYLOG)($|_)|(_LOG|LOG_)", re.I)
TEMP_VIEW_PAT = re.compile(r"^TEMQ_[A-Z0-9]+_\d+$")

CORE_TABLES = {
    "BD_PSNDOC",
    "HI_PSNJOB",
    "ORG_DEPT",
    "ORG_ADMINORG",
    "ORG_ORGS",
    "OM_JOB",
    "SM_USER",
    "BD_DEFDOC",
    "MD_ENUMVALUE",
    "BD_PSNCL",
    "HI_PSNDOC_EDU",
    "HI_PSNDOC_GLBDEF2",
    "BD_SUPPLIER",
    "BD_SUPPLIERCLASS",
    "BD_MATERIAL",
    "BD_MARBASCLASS",
    "BD_MEASDOC",
    "BD_STORDOC",
    "GL_DETAIL",
    "GL_DOCFREE1",
    "IC_MATERIAL_H",
    "IC_MATERIAL_B",
    "IC_ONHANDDIM",
    "IC_ONHANDNUM",
    "PO_INVOICE",
    "PO_INVOICE_B",
    "WA_ITEM",
    "WA_DATA",
}

IMPORTANT_VIEWS = {
    "HR_RYDA",
    "EMR_HOS_INFORMATION",
    "EMR_HOS_PRACTITIONER",
    "HRP_HIS_HCCKXX",
    "SEY_HCCK",
    "SEY_WZCK",
    "GYS_JBXX",
    "HR_LTXRY",
    "HR_RYLZXX",
    "HR_RYRZXX",
    "HR_LZXX",
    "HR_ORG_DEPT_V",
    "WZ_KC",
    "WZ_QTRK_MXJL_JYK",
    "PL_WZXHMX",
    "PL_WZZD",
    "PL_CWPZMX",
    "PL_GDZCZJMX",
    "SB_DJKP",
    "SB_ZJJL",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: clean(row.get(key, "")) for key in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def as_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def classify_table(row: dict[str, Any]) -> dict[str, Any]:
    table = row["table_name"].upper()
    num_rows = as_int(row.get("num_rows_stats"))
    is_empty = num_rows == 0
    is_unanalyzed = num_rows is None
    is_date = bool(DATE_PAT.search(table))
    is_backup = bool(BACKUP_PAT.search(table))
    is_log = bool(LOG_PAT.search(table)) and "CATALOG" not in table
    is_temp_view = bool(TEMP_VIEW_PAT.match(table))
    is_core = table in CORE_TABLES

    reasons: list[str] = []
    if is_core:
        reasons.append("核心表白名单")
    if is_empty:
        reasons.append("NUM_ROWS=0")
    if is_unanalyzed:
        reasons.append("NUM_ROWS缺失")
    if is_date:
        reasons.append("表名含日期快照")
    if is_backup:
        reasons.append("表名疑似备份/临时/测试")
    if is_log:
        reasons.append("日志/审计/跟踪类")
    if is_temp_view:
        reasons.append("TEMQ临时查询对象")

    domain = row.get("inferred_domain", "")
    status = row.get("include_status", "")
    if is_core:
        decision = "core_keep"
    elif is_log or is_temp_view or is_backup or is_date:
        decision = "exclude_candidate"
    elif is_empty and domain not in {"字典/编码", "科室/组织", "用户账号"}:
        decision = "exclude_candidate"
    elif is_unanalyzed:
        decision = "review_candidate"
    elif status == "included" or domain in {
        "人员",
        "科室/组织",
        "岗位/职务",
        "用户账号",
        "薪酬/绩效/考勤",
        "供应商/物资",
        "财务",
        "字典/编码",
    }:
        decision = "core_candidate"
    else:
        decision = "review_candidate"

    return {
        **row,
        "num_rows_i": num_rows,
        "is_empty_stats": str(is_empty).lower(),
        "is_missing_stats": str(is_unanalyzed).lower(),
        "is_date_like": str(is_date).lower(),
        "is_backup_like": str(is_backup).lower(),
        "is_log_like": str(is_log).lower(),
        "is_temp_query_like": str(is_temp_view).lower(),
        "cleanup_decision": decision,
        "cleanup_reason": "; ".join(reasons),
    }


REMOTE_SCRIPT = r"""
import json
import sys

import oracledb

payload = json.loads(sys.stdin.read())
oracledb.init_oracle_client(lib_dir=payload["oracle_client"])
conn = oracledb.connect(user=payload["user"], password=payload["password"], dsn=payload["dsn"])
conn.call_timeout = int(payload.get("call_timeout_ms") or 60000)
cur = conn.cursor()
try:
    results = {}
    for item in payload["queries"]:
        cur.execute(item["sql"])
        cols = [d[0].lower() for d in cur.description]
        rows = cur.fetchmany(int(item.get("max_rows") or 10000))
        results[item["name"]] = [dict(zip(cols, row)) for row in rows]
    print(json.dumps(results, ensure_ascii=False))
finally:
    cur.close()
    conn.close()
"""


def fetch_view_dependencies() -> dict[str, list[dict[str, Any]]]:
    user = os.environ.get("HRP_USER")
    password = os.environ.get("HRP_PASSWORD")
    if not user or not password:
        return {
            "__errors__": [
                {
                    "query": "view_dependencies",
                    "error": "HRP_USER/HRP_PASSWORD not set; skipped live view dependency scan",
                }
            ]
        }

    encoded = base64.b64encode(REMOTE_SCRIPT.encode("utf-8")).decode("ascii")
    remote_cmd = f"python3 -c \"import base64; exec(base64.b64decode('{encoded}'))\""
    jump_key = os.environ.get("APP_SSH_JUMP_KEY") or str(Path.home() / ".ssh" / "id_ed25519_ai")
    cmd = [
        "ssh",
        "-p",
        os.environ.get("APP_SSH_JUMP_PORT", "40022"),
        "-i",
        jump_key,
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=10",
        f"{os.environ.get('APP_SSH_JUMP_USER', 'root')}@{os.environ.get('APP_SSH_JUMP_HOST', '10.10.8.53')}",
        remote_cmd,
    ]
    payload = {
        "user": user,
        "password": password,
        "dsn": SOURCE_DB,
        "oracle_client": os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle/instantclient_21"),
        "call_timeout_ms": 60000,
        "queries": [
            {
                "name": "views",
                "max_rows": 1000,
                "sql": "SELECT view_name, text_length FROM user_views ORDER BY view_name",
            },
            {
                "name": "view_deps",
                "max_rows": 20000,
                "sql": """
SELECT name AS view_name, referenced_name, referenced_type
FROM user_dependencies
WHERE type = 'VIEW'
  AND referenced_owner = USER
  AND referenced_type IN ('TABLE','VIEW')
ORDER BY name, referenced_name
""",
            },
        ],
    }
    completed = subprocess.run(
        cmd,
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        return {"__errors__": [{"query": "view_dependencies", "error": (completed.stderr or "")[:500]}]}
    return json.loads(completed.stdout.strip().splitlines()[-1])


def main() -> None:
    tables = [classify_table(row) for row in read_csv(TABLES_PATH)]

    column_counts: Counter[str] = Counter()
    pii_counts: Counter[str] = Counter()
    semantic_counts_by_table: dict[str, Counter[str]] = defaultdict(Counter)
    with COLUMNS_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            table = row["table_name"].upper()
            column_counts[table] += 1
            pii_counts[row.get("pii_flag", "none")] += 1
            semantic_counts_by_table[table][row.get("inferred_semantic_type", "其他")] += 1

    pk_tables: set[str] = set()
    constraint_types: Counter[str] = Counter()
    with CONSTRAINTS_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            constraint_types[row.get("constraint_type", "")] += 1
            if row.get("constraint_type") == "P":
                pk_tables.add(row["table_name"].upper())

    nonunique_index_tables: set[str] = set()
    with INDEXES_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("uniqueness") == "NONUNIQUE":
                nonunique_index_tables.add(row["table_name"].upper())

    by_name = {row["table_name"].upper(): row for row in tables}
    for row in tables:
        t = row["table_name"].upper()
        row["column_count_in_current_file"] = column_counts.get(t, 0)
        row["has_primary_key"] = str(t in pk_tables).lower()
        row["has_nonunique_index"] = str(t in nonunique_index_tables).lower()

    core_rows = [
        row
        for row in tables
        if row["cleanup_decision"] in {"core_keep", "core_candidate"}
        and row["cleanup_decision"] != "exclude_candidate"
    ]
    exclude_rows = [row for row in tables if row["cleanup_decision"] == "exclude_candidate"]
    review_rows = [row for row in tables if row["cleanup_decision"] == "review_candidate"]

    view_raw = fetch_view_dependencies()
    view_meta = {row["view_name"]: row for row in view_raw.get("views", [])}
    refs_by_view: dict[str, list[str]] = defaultdict(list)
    for row in view_raw.get("view_deps", []):
        refs_by_view[row["view_name"]].append(row["referenced_name"])
    view_rows = []
    for view, refs in sorted(refs_by_view.items()):
        upper_refs = {r.upper() for r in refs}
        is_temp = bool(TEMP_VIEW_PAT.match(view.upper()))
        is_important = view.upper() in IMPORTANT_VIEWS or bool(upper_refs & CORE_TABLES)
        if is_temp and not is_important:
            view_role = "exclude_temp_query_view"
        elif is_important:
            view_role = "relationship_seed"
        else:
            view_role = "review_view"
        view_rows.append(
            {
                "source_system": SOURCE_SYSTEM,
                "source_db": SOURCE_DB,
                "owner": "HRPSEY656",
                "view_name": view,
                "text_length": view_meta.get(view, {}).get("text_length", ""),
                "referenced_count": len(refs),
                "referenced_objects": ";".join(refs),
                "view_role": view_role,
            }
        )

    heavy_rows = []
    for table, count in column_counts.most_common():
        row = by_name.get(table, {})
        if count < 120 and table not in CORE_TABLES:
            continue
        semantics = semantic_counts_by_table.get(table, Counter())
        if table in CORE_TABLES:
            recommendation = "keep_core_even_if_wide"
        elif row.get("is_date_like") == "true" or row.get("is_backup_like") == "true":
            recommendation = "exclude_backup_or_snapshot"
        elif row.get("is_log_like") == "true" or row.get("is_temp_query_like") == "true":
            recommendation = "exclude_log_or_temp"
        elif as_int(row.get("num_rows_stats")) == 0:
            recommendation = "review_empty_wide_table"
        elif count >= 300:
            recommendation = "review_wide_table"
        else:
            recommendation = "normal_wide_business_table"
        heavy_rows.append(
            {
                "source_system": SOURCE_SYSTEM,
                "source_db": SOURCE_DB,
                "owner": row.get("owner", "HRPSEY656"),
                "table_name": table,
                "num_rows_stats": row.get("num_rows_stats", ""),
                "inferred_domain": row.get("inferred_domain", ""),
                "cleanup_decision": row.get("cleanup_decision", ""),
                "column_count_in_current_file": count,
                "pii_like_columns": semantics.get("名称", 0)
                + semantics.get("身份证/证件", 0)
                + semantics.get("电话", 0)
                + semantics.get("地址", 0),
                "semantic_summary": ";".join(f"{k}:{v}" for k, v in semantics.most_common(8)),
                "recommendation": recommendation,
                "reason": row.get("cleanup_reason", ""),
            }
        )

    common_fields = [
        "source_system",
        "source_db",
        "owner",
        "table_name",
        "table_comment",
        "num_rows_stats",
        "blocks",
        "last_analyzed",
        "tablespace_name",
        "inferred_domain",
        "table_role",
        "include_status",
        "exclude_reason",
        "column_count_in_current_file",
        "has_primary_key",
        "has_nonunique_index",
        "cleanup_decision",
        "cleanup_reason",
    ]
    write_csv(PKG_DIR / "hrp_tables_core_candidates.csv", common_fields, core_rows)
    write_csv(PKG_DIR / "hrp_tables_exclude_candidates.csv", common_fields, exclude_rows)
    write_csv(PKG_DIR / "hrp_tables_review_candidates.csv", common_fields, review_rows)
    write_csv(
        PKG_DIR / "hrp_view_relationship_seeds.csv",
        [
            "source_system",
            "source_db",
            "owner",
            "view_name",
            "text_length",
            "referenced_count",
            "referenced_objects",
            "view_role",
        ],
        view_rows,
    )
    write_csv(
        PKG_DIR / "hrp_field_heavy_tables.csv",
        [
            "source_system",
            "source_db",
            "owner",
            "table_name",
            "num_rows_stats",
            "inferred_domain",
            "cleanup_decision",
            "column_count_in_current_file",
            "pii_like_columns",
            "semantic_summary",
            "recommendation",
            "reason",
        ],
        heavy_rows,
    )

    summary = {
        "generated_at": now_iso(),
        "source_system": SOURCE_SYSTEM,
        "source_db": SOURCE_DB,
        "inputs": {
            "tables": TABLES_PATH.name,
            "columns": COLUMNS_PATH.name,
            "constraints": CONSTRAINTS_PATH.name,
            "indexes": INDEXES_PATH.name,
        },
        "counts": {
            "total_tables": len(tables),
            "core_candidates": len(core_rows),
            "exclude_candidates": len(exclude_rows),
            "review_candidates": len(review_rows),
            "field_heavy_tables": len(heavy_rows),
            "views": len(view_raw.get("views", [])),
            "view_dependency_edges": len(view_raw.get("view_deps", [])),
        },
        "table_flags": {
            "num_rows_zero": sum(1 for r in tables if r["is_empty_stats"] == "true"),
            "num_rows_missing": sum(1 for r in tables if r["is_missing_stats"] == "true"),
            "date_like": sum(1 for r in tables if r["is_date_like"] == "true"),
            "backup_like": sum(1 for r in tables if r["is_backup_like"] == "true"),
            "log_like": sum(1 for r in tables if r["is_log_like"] == "true"),
            "temp_query_like": sum(1 for r in tables if r["is_temp_query_like"] == "true"),
        },
        "domain_counts": dict(Counter(r["inferred_domain"] for r in tables)),
        "constraint_type_counts": dict(constraint_types),
        "pii_flag_counts_in_current_columns": dict(pii_counts),
        "field_capture_warning": (
            "hrp_source_columns.csv contains 5000000 rows and reached previous capture cap; "
            "field counts are lower-bound estimates for tables not fully reached."
        ),
        "view_dependency_errors": view_raw.get("__errors__", []),
        "outputs": [
            "hrp_tables_core_candidates.csv",
            "hrp_tables_exclude_candidates.csv",
            "hrp_tables_review_candidates.csv",
            "hrp_view_relationship_seeds.csv",
            "hrp_field_heavy_tables.csv",
            "hrp_cleanup_summary.json",
        ],
    }
    (PKG_DIR / "hrp_cleanup_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary["counts"] | summary["table_flags"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
