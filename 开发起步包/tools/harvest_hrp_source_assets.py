from __future__ import annotations

import base64
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "数据资产_HRP源端资产包"
REPORT_PATH = BASE_DIR / "49_HRP源端资产探查报告.md"
RESULT_PATH = BASE_DIR / "49_HRP源端资产探查结果.json"

SOURCE_SYSTEM = "HRP"
SOURCE_DB = "10.10.10.23:1521/hrpdb"
JUMP_HOST = os.environ.get("APP_SSH_JUMP_HOST", "10.10.8.53")
JUMP_PORT = os.environ.get("APP_SSH_JUMP_PORT", "40022")
JUMP_USER = os.environ.get("APP_SSH_JUMP_USER", "root")
JUMP_KEY = os.environ.get(
    "APP_SSH_JUMP_KEY",
    str(Path.home() / ".ssh" / "id_ed25519_ai"),
)
ORACLE_CLIENT = os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle/instantclient_21")

SYSTEM_OWNERS = {
    "SYS",
    "SYSTEM",
    "XDB",
    "MDSYS",
    "CTXSYS",
    "OLAPSYS",
    "ORDSYS",
    "ORDPLUGINS",
    "OUTLN",
    "WMSYS",
    "DBSNMP",
    "APPQOSSYS",
    "EXFSYS",
    "DMSYS",
    "ANONYMOUS",
    "SYSMAN",
    "MDDATA",
    "FLOWS_FILES",
    "APEX_PUBLIC_USER",
    "ORDDATA",
    "SPATIAL_CSW_ADMIN_USR",
    "SPATIAL_WFS_ADMIN_USR",
    "OWBSYS",
    "OWBSYS_AUDIT",
}

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|merge|create|alter|drop|truncate|grant|revoke|commit|rollback|"
    r"execute|exec|call|begin|declare|dbms_|utl_)\b",
    re.IGNORECASE,
)


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("\r", " ").replace("\n", " ").strip()
    return str(value)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: clean(row.get(key)) for key in fieldnames})


def assert_readonly(sql: str) -> None:
    stripped = sql.strip()
    if not (stripped.upper().startswith("SELECT") or stripped.upper().startswith("WITH")):
        raise ValueError("Only SELECT/WITH SQL is allowed")
    if ";" in stripped.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")
    if FORBIDDEN_SQL.search(stripped):
        raise ValueError("Forbidden SQL keyword detected")


REMOTE_SCRIPT = r"""
import datetime
import decimal
import json
import sys

import oracledb


def normalize(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if hasattr(value, "read"):
        return value.read()
    if isinstance(value, bytes):
        return value.hex()
    return value


payload = json.loads(sys.stdin.read())
oracledb.init_oracle_client(lib_dir=payload["oracle_client"])
conn = oracledb.connect(
    user=payload["user"],
    password=payload["password"],
    dsn=payload["dsn"],
)
conn.call_timeout = int(payload.get("call_timeout_ms") or 60000)
cur = None
try:
    cur = conn.cursor()
    cur.arraysize = int(payload.get("arraysize") or 1000)
    results = {}
    errors = []
    for item in payload["queries"]:
        try:
            cur.execute(item["sql"], item.get("params") or {})
            rows = cur.fetchmany(int(item.get("max_rows") or 1000000))
            cols = [d[0].lower() for d in cur.description]
            results[item["name"]] = [
                {col: normalize(value) for col, value in zip(cols, row)}
                for row in rows
            ]
        except Exception as exc:
            errors.append({"query": item["name"], "error": str(exc)})
            results[item["name"]] = []
    if errors:
        results["__errors__"] = errors
    print(json.dumps(results, ensure_ascii=False))
finally:
    if cur is not None:
        cur.close()
    conn.close()
"""


def run_remote_queries(queries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    user = os.environ.get("HRP_USER")
    password = os.environ.get("HRP_PASSWORD")
    if not user or not password:
        raise RuntimeError("HRP_USER/HRP_PASSWORD are not set in the current environment")
    for query in queries:
        assert_readonly(query["sql"])

    encoded_script = base64.b64encode(REMOTE_SCRIPT.encode("utf-8")).decode("ascii")
    remote_cmd = f"python3 -c \"import base64; exec(base64.b64decode('{encoded_script}'))\""
    cmd = [
        "ssh",
        "-p",
        JUMP_PORT,
        "-i",
        JUMP_KEY,
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=10",
        f"{JUMP_USER}@{JUMP_HOST}",
        remote_cmd,
    ]
    payload = {
        "user": user,
        "password": password,
        "dsn": SOURCE_DB,
        "oracle_client": ORACLE_CLIENT,
        "call_timeout_ms": int(os.environ.get("HRP_QUERY_TIMEOUT_MS", "120000")),
        "arraysize": int(os.environ.get("HRP_ARRAYSIZE", "5000")),
        "queries": queries,
    }
    completed = subprocess.run(
        cmd,
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=int(os.environ.get("HRP_SSH_TIMEOUT_SECONDS", "300")),
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "HRP query failed")[:1000])
    stdout = completed.stdout.strip()
    if not stdout:
        return {}
    return json.loads(stdout.splitlines()[-1])


def metadata_queries() -> list[dict[str, Any]]:
    if os.environ.get("HRP_ALL_ACCESSIBLE") != "1":
        return user_metadata_queries()
    owner_filter = ",".join(f"'{owner}'" for owner in sorted(SYSTEM_OWNERS))
    return [
        {
            "name": "owners",
            "max_rows": 10000,
            "sql": f"""
SELECT u.username AS owner,
       COUNT(t.table_name) AS table_count,
       SUM(NVL(t.num_rows, 0)) AS num_rows_stats_sum
FROM all_users u
LEFT JOIN all_tables t ON t.owner = u.username
WHERE u.username NOT IN ({owner_filter})
GROUP BY u.username
ORDER BY COUNT(t.table_name) DESC, u.username
""",
        },
        {
            "name": "tables",
            "max_rows": 200000,
            "sql": f"""
SELECT t.owner,
       t.table_name,
       c.comments AS table_comment,
       t.num_rows AS num_rows_stats,
       t.blocks,
       TO_CHAR(t.last_analyzed, 'YYYY-MM-DD HH24:MI:SS') AS last_analyzed,
       t.tablespace_name
FROM all_tables t
LEFT JOIN all_tab_comments c
  ON c.owner = t.owner
 AND c.table_name = t.table_name
WHERE t.owner NOT IN ({owner_filter})
ORDER BY t.owner, t.table_name
""",
        },
        {
            "name": "columns",
            "max_rows": int(os.environ.get("HRP_COLUMNS_MAX_ROWS", "5000000")),
            "sql": f"""
SELECT c.owner,
       c.table_name,
       c.column_name,
       NULL AS column_comment,
       c.data_type,
       c.data_length,
       c.data_precision,
       c.data_scale,
       c.nullable,
       c.column_id
FROM all_tab_columns c
WHERE c.owner NOT IN ({owner_filter})
  AND c.table_name NOT LIKE 'BIN$%'
""",
        },
        {
            "name": "indexes",
            "max_rows": 1000000,
            "sql": f"""
SELECT i.owner,
       ic.table_name,
       i.index_name,
       i.uniqueness,
       ic.column_name,
       ic.column_position
FROM all_indexes i
JOIN all_ind_columns ic
  ON ic.index_owner = i.owner
 AND ic.index_name = i.index_name
WHERE i.owner NOT IN ({owner_filter})
ORDER BY i.owner, ic.table_name, i.index_name, ic.column_position
""",
        },
        {
            "name": "constraints",
            "max_rows": 1000000,
            "sql": f"""
SELECT c.owner,
       c.table_name,
       c.constraint_name,
       c.constraint_type,
       cc.column_name,
       r.owner AS ref_owner,
       r.table_name AS ref_table_name,
       rcc.column_name AS ref_column_name,
       cc.position AS column_position
FROM all_constraints c
LEFT JOIN all_cons_columns cc
  ON cc.owner = c.owner
 AND cc.constraint_name = c.constraint_name
LEFT JOIN all_constraints r
  ON r.owner = c.r_owner
 AND r.constraint_name = c.r_constraint_name
LEFT JOIN all_cons_columns rcc
  ON rcc.owner = r.owner
 AND rcc.constraint_name = r.constraint_name
 AND rcc.position = cc.position
WHERE c.owner NOT IN ({owner_filter})
  AND c.constraint_type IN ('P', 'U', 'R', 'C')
ORDER BY c.owner, c.table_name, c.constraint_name, cc.position
""",
        },
        {
            "name": "views",
            "max_rows": 200000,
            "sql": f"""
SELECT v.owner,
       v.view_name,
       v.text_length,
       NULL AS text_summary
FROM all_views v
WHERE v.owner NOT IN ({owner_filter})
ORDER BY v.owner, v.view_name
""",
        },
    ]


def user_metadata_queries() -> list[dict[str, Any]]:
    return [
        {
            "name": "owners",
            "max_rows": 1,
            "sql": """
SELECT USER AS owner,
       NULL AS table_count,
       NULL AS num_rows_stats_sum
FROM dual
""",
        },
        {
            "name": "tables",
            "max_rows": 200000,
            "sql": """
SELECT USER AS owner,
       t.table_name,
       c.comments AS table_comment,
       t.num_rows AS num_rows_stats,
       t.blocks,
       TO_CHAR(t.last_analyzed, 'YYYY-MM-DD HH24:MI:SS') AS last_analyzed,
       t.tablespace_name
FROM user_tables t
LEFT JOIN user_tab_comments c
  ON c.table_name = t.table_name
ORDER BY t.table_name
""",
        },
        {
            "name": "columns",
            "max_rows": int(os.environ.get("HRP_COLUMNS_MAX_ROWS", "5000000")),
            "sql": """
SELECT USER AS owner,
       c.table_name,
       c.column_name,
       NULL AS column_comment,
       c.data_type,
       c.data_length,
       c.data_precision,
       c.data_scale,
       c.nullable,
       c.column_id
FROM user_tab_columns c
WHERE c.table_name NOT LIKE 'BIN$%'
""",
        },
        {
            "name": "indexes",
            "max_rows": 1000000,
            "sql": """
SELECT USER AS owner,
       ic.table_name,
       i.index_name,
       i.uniqueness,
       ic.column_name,
       ic.column_position
FROM user_indexes i
JOIN user_ind_columns ic
  ON ic.index_name = i.index_name
ORDER BY ic.table_name, i.index_name, ic.column_position
""",
        },
        {
            "name": "constraints",
            "max_rows": 1000000,
            "sql": """
SELECT USER AS owner,
       c.table_name,
       c.constraint_name,
       c.constraint_type,
       cc.column_name,
       c.r_owner AS ref_owner,
       r.table_name AS ref_table_name,
       rcc.column_name AS ref_column_name,
       cc.position AS column_position
FROM user_constraints c
LEFT JOIN user_cons_columns cc
  ON cc.constraint_name = c.constraint_name
LEFT JOIN all_constraints r
  ON r.owner = c.r_owner
 AND r.constraint_name = c.r_constraint_name
LEFT JOIN all_cons_columns rcc
  ON rcc.owner = r.owner
 AND rcc.constraint_name = r.constraint_name
 AND rcc.position = cc.position
WHERE c.constraint_type IN ('P', 'U', 'R', 'C')
ORDER BY c.table_name, c.constraint_name, cc.position
""",
        },
        {
            "name": "views",
            "max_rows": 200000,
            "sql": """
SELECT USER AS owner,
       v.view_name,
       v.text_length,
       NULL AS text_summary
FROM user_views v
ORDER BY v.view_name
""",
        },
    ]


def infer_domain(owner: str, table_name: str, comment: str = "") -> str:
    text = f"{owner}.{table_name}.{comment}".upper()
    if any(k in text for k in ["PSN", "PERSON", "STAFF", "EMP", "RYDA", "人员", "职工", "员工"]):
        return "人员"
    if any(k in text for k in ["DEPT", "ORG", "ADMINORG", "部门", "科室", "组织"]):
        return "科室/组织"
    if any(k in text for k in ["JOB", "POST", "TITLE", "POSITION", "岗位", "职务", "职称"]):
        return "岗位/职务"
    if any(k in text for k in ["USER", "ROLE", "ACCOUNT", "LOGIN", "账号", "用户", "权限"]):
        return "用户账号"
    if any(k in text for k in ["SALARY", "WAGE", "PAYROLL", "PERF", "ATTEND", "考勤", "绩效", "薪酬", "工资"]):
        return "薪酬/绩效/考勤"
    if any(k in text for k in ["SUPPLIER", "VENDOR", "INV", "MATERIAL", "STOCK", "WZ", "HC", "供应商", "物资", "耗材", "库存"]):
        return "供应商/物资"
    if any(k in text for k in ["GL_", "BILL", "VOUCHER", "ACCOUNT", "FIN", "财务", "凭证", "会计"]):
        return "财务"
    if any(k in text for k in ["DICT", "DEF", "CODE", "ENUM", "CLASS", "TYPE", "字典", "编码"]):
        return "字典/编码"
    return "其他"


def infer_role(table_name: str, domain: str, num_rows: Any) -> tuple[str, str, str]:
    table = table_name.upper()
    if any(k in table for k in ["LOG", "TMP", "TEMP", "BAK", "BACKUP", "HIS_", "TEST"]):
        return "excluded", "excluded", "日志/临时/备份/测试类表，第一版不纳入治理主清单"
    if domain in {"人员", "科室/组织", "岗位/职务", "用户账号", "字典/编码"}:
        return "included", "dimension", ""
    if domain in {"薪酬/绩效/考勤", "供应商/物资", "财务"}:
        return "included", "fact_or_business", ""
    if num_rows in (None, ""):
        return "candidate", "candidate", "缺少统计行数，需人工确认是否纳入"
    try:
        if int(num_rows) == 0:
            return "candidate", "empty_or_unanalyzed", "统计行数为 0，需确认是否为配置空表"
    except (TypeError, ValueError):
        pass
    return "candidate", "candidate", "非重点 HRP 业务表，保留候选"


def infer_semantic_type(column_name: str, comment: str = "") -> str:
    text = f"{column_name}.{comment}".upper()
    if any(k in text for k in ["IDCARD", "ID_CARD", "CERT", "身份证", "证件"]):
        return "身份证/证件"
    if any(k in text for k in ["PHONE", "MOBILE", "TEL", "电话", "手机"]):
        return "电话"
    if any(k in text for k in ["ADDR", "ADDRESS", "地址"]):
        return "地址"
    if any(k in text for k in ["NAME", "姓名", "名称"]):
        return "名称"
    if any(k in text for k in ["PSN", "PERSON", "STAFF", "EMP", "人员", "职工", "员工"]):
        return "人员标识"
    if any(k in text for k in ["DEPT", "ORG", "部门", "科室", "组织"]):
        return "组织科室"
    if any(k in text for k in ["USER", "LOGIN", "账号", "用户"]):
        return "账号"
    if any(k in text for k in ["DATE", "TIME", "日期", "时间"]):
        return "时间"
    if any(k in text for k in ["AMOUNT", "MONEY", "PRICE", "COST", "金额", "价格", "费用"]):
        return "金额"
    if any(k in text for k in ["CODE", "编码", "代码"]):
        return "编码"
    return "其他"


def pii_flag(column_name: str, comment: str = "") -> str:
    semantic = infer_semantic_type(column_name, comment)
    if semantic in {"身份证/证件", "电话", "地址"}:
        return "high"
    if semantic in {"名称"} and any(k in f"{column_name}.{comment}".upper() for k in ["NAME", "姓名"]):
        return "medium"
    return "none"


def build_assets(raw: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    tables = []
    for row in raw.get("tables", []):
        owner = row.get("owner", "")
        table_name = row.get("table_name", "")
        table_comment = row.get("table_comment") or ""
        domain = infer_domain(owner, table_name, table_comment)
        include_status, role, reason = infer_role(table_name, domain, row.get("num_rows_stats"))
        tables.append(
            {
                "source_system": SOURCE_SYSTEM,
                "source_db": SOURCE_DB,
                "owner": owner,
                "table_name": table_name,
                "table_comment": table_comment,
                "num_rows_stats": row.get("num_rows_stats"),
                "blocks": row.get("blocks"),
                "last_analyzed": row.get("last_analyzed"),
                "tablespace_name": row.get("tablespace_name"),
                "inferred_domain": domain,
                "table_role": role,
                "include_status": include_status,
                "exclude_reason": reason,
            }
        )

    columns = []
    pii_counter: Counter[str] = Counter()
    for row in raw.get("columns", []):
        semantic = infer_semantic_type(row.get("column_name", ""), row.get("column_comment") or "")
        flag = pii_flag(row.get("column_name", ""), row.get("column_comment") or "")
        if flag != "none":
            pii_counter[flag] += 1
        columns.append(
            {
                "source_system": SOURCE_SYSTEM,
                "source_db": SOURCE_DB,
                "owner": row.get("owner"),
                "table_name": row.get("table_name"),
                "column_name": row.get("column_name"),
                "column_comment": row.get("column_comment") or "",
                "data_type": row.get("data_type"),
                "data_length": row.get("data_length"),
                "data_precision": row.get("data_precision"),
                "data_scale": row.get("data_scale"),
                "nullable": row.get("nullable"),
                "column_id": row.get("column_id"),
                "inferred_semantic_type": semantic,
                "pii_flag": flag,
            }
        )

    indexes = raw.get("indexes", [])
    constraints = raw.get("constraints", [])
    views = raw.get("views", [])
    owners = raw.get("owners", [])

    domain_priority = {
        "人员": 1,
        "科室/组织": 2,
        "岗位/职务": 3,
        "用户账号": 4,
        "薪酬/绩效/考勤": 5,
        "供应商/物资": 6,
        "财务": 7,
        "字典/编码": 8,
    }
    core_candidate_tables = sorted(
        [
            {
                "owner": row["owner"],
                "table_name": row["table_name"],
                "table_comment": row["table_comment"],
                "inferred_domain": row["inferred_domain"],
                "num_rows_stats": row["num_rows_stats"],
            }
            for row in tables
            if row["inferred_domain"] in domain_priority and row["include_status"] == "included"
        ],
        key=lambda r: (domain_priority.get(r["inferred_domain"], 99), r["owner"], r["table_name"]),
    )[:100]

    pii_by_table: dict[str, list[str]] = defaultdict(list)
    for row in columns:
        if row["pii_flag"] != "none":
            pii_by_table[f"{row['owner']}.{row['table_name']}"].append(row["column_name"])
    pii_summary = {
        "by_flag": dict(pii_counter),
        "tables_count": len(pii_by_table),
        "columns": [
            {"table": table, "columns": sorted(set(cols))}
            for table, cols in sorted(pii_by_table.items())
        ][:200],
    }

    catalog = {
        "generated_at": utc_now_iso(),
        "source_system": SOURCE_SYSTEM,
        "source_db": SOURCE_DB,
        "owners_count": len(owners),
        "tables_count": len(tables),
        "columns_count": len(columns),
        "indexes_count": len(indexes),
        "constraints_count": len(constraints),
        "views_count": len(views),
        "core_candidate_tables": core_candidate_tables,
        "pii_columns_summary": pii_summary,
        "warnings": [
            "仅采集 Oracle 数据字典元数据与注释，未查询业务明细数据。",
            "行数来自 ALL_TABLES.NUM_ROWS 统计值，可能不是实时行数。",
            "PII 识别基于字段名和字段注释启发式规则，需人工复核。",
            "视图仅采集名称、DDL 长度和前 200 字符摘要，未输出完整视图文本。",
        ],
    }
    column_cap = int(os.environ.get("HRP_COLUMNS_MAX_ROWS", "5000000"))
    if len(columns) >= column_cap:
        catalog["warnings"].append(
            f"字段采集达到 HRP_COLUMNS_MAX_ROWS={column_cap} 上限，可能仍有未采集字段；需夜间分段补采。"
        )
    for item in raw.get("__errors__", []):
        catalog["warnings"].append(f"元数据查询 {item.get('query')} 失败或超时：{item.get('error')}")
    return {
        "tables": tables,
        "columns": columns,
        "indexes": indexes,
        "constraints": constraints,
        "views": views,
        "owners": owners,
        "catalog": catalog,
    }


def write_assets(assets: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(
        OUT_DIR / "hrp_source_tables.csv",
        [
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
        ],
        assets["tables"],
    )
    write_csv(
        OUT_DIR / "hrp_source_columns.csv",
        [
            "source_system",
            "source_db",
            "owner",
            "table_name",
            "column_name",
            "column_comment",
            "data_type",
            "data_length",
            "data_precision",
            "data_scale",
            "nullable",
            "column_id",
            "inferred_semantic_type",
            "pii_flag",
        ],
        assets["columns"],
    )
    write_csv(
        OUT_DIR / "hrp_source_indexes.csv",
        ["owner", "table_name", "index_name", "uniqueness", "column_name", "column_position"],
        assets["indexes"],
    )
    write_csv(
        OUT_DIR / "hrp_source_constraints.csv",
        [
            "owner",
            "table_name",
            "constraint_name",
            "constraint_type",
            "column_name",
            "ref_owner",
            "ref_table_name",
            "ref_column_name",
        ],
        assets["constraints"],
    )
    (OUT_DIR / "hrp_source_catalog.json").write_text(
        json.dumps(assets["catalog"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def render_report(assets: dict[str, Any], status: str, error: str = "") -> str:
    catalog = assets["catalog"]
    owner_lines = [
        f"| {row.get('owner')} | {row.get('table_count')} | {row.get('num_rows_stats_sum')} |"
        for row in assets.get("owners", [])[:30]
    ]
    core_lines = [
        f"| {row['owner']}.{row['table_name']} | {row['table_comment'] or '需要人工确认'} | "
        f"{row['inferred_domain']} | {row['num_rows_stats']} |"
        for row in catalog.get("core_candidate_tables", [])[:50]
    ]
    pii_lines = []
    for item in catalog.get("pii_columns_summary", {}).get("columns", [])[:80]:
        pii_lines.append(f"| {item['table']} | {', '.join(item['columns'])} |")
    warning_lines = [f"- {w}" for w in catalog.get("warnings", [])]
    if error:
        warning_lines.insert(0, f"- 本次未完成 HRP 连接采集：{error}")

    return f"""> 类别：元数据
# HRP 源端资产探查报告

## 1. 连接方式和安全说明

- 系统：HRP
- 数据库：Oracle `{SOURCE_DB}`
- 访问方式：本机通过 `10.10.8.53:40022` 跳板机执行，跳板机使用 Oracle thick mode `{ORACLE_CLIENT}`。
- 凭据来源：临时环境变量 `HRP_USER` / `HRP_PASSWORD`，报告和资产包不记录明文密码。
- SQL 范围：仅查询 `ALL_USERS`、`ALL_TABLES`、`ALL_TAB_COLUMNS`、`ALL_TAB_COMMENTS`、`ALL_COL_COMMENTS`、`ALL_CONSTRAINTS`、`ALL_CONS_COLUMNS`、`ALL_INDEXES`、`ALL_IND_COLUMNS`、`ALL_VIEWS` 等数据字典视图。
- 安全状态：`{status}`。

## 2. owner/schema 概览

| Owner | 表数量 | NUM_ROWS 统计合计 |
|---|---:|---:|
{chr(10).join(owner_lines) if owner_lines else '| 未采集 | 0 | 0 |'}

## 3. 资产统计

| 指标 | 数量 |
|---|---:|
| Owner | {catalog['owners_count']} |
| 表 | {catalog['tables_count']} |
| 字段 | {catalog['columns_count']} |
| 视图 | {catalog['views_count']} |
| 约束 | {catalog['constraints_count']} |
| 索引字段 | {catalog['indexes_count']} |

## 4. HRP 核心候选表

| 表 | 注释 | 识别域 | NUM_ROWS 统计 |
|---|---|---|---:|
{chr(10).join(core_lines) if core_lines else '| 未采集 | 未采集 | 未采集 | 0 |'}

重点识别域包括：人员、科室/组织、岗位/职务、用户账号、人员科室关系、薪酬/绩效/考勤、供应商/物资、财务、字典/编码。

## 5. PII 字段识别摘要

仅输出字段名和表名，不输出真实业务数据。

| 表 | 疑似 PII 字段 |
|---|---|
{chr(10).join(pii_lines) if pii_lines else '| 未发现或未采集 |  |'}

## 6. 可导入资产系统的文件清单

- `开发起步包/数据资产_HRP源端资产包/hrp_source_tables.csv`
- `开发起步包/数据资产_HRP源端资产包/hrp_source_columns.csv`
- `开发起步包/数据资产_HRP源端资产包/hrp_source_indexes.csv`
- `开发起步包/数据资产_HRP源端资产包/hrp_source_constraints.csv`
- `开发起步包/数据资产_HRP源端资产包/hrp_source_catalog.json`
- `开发起步包/49_HRP源端资产探查结果.json`

## 7. 未确认事项

- 人员唯一键：需确认 HRP 人员主表主键与工号字段口径。
- 科室编码：需确认 HRP 科室编码与 HIS 科室编码是否通过对照表或同编码映射。
- 一人多科室：需确认 HRP 是否存在任职/兼职/借调等多科室关系表。
- HIS 工号一致性：需与 HIS `COMM.STAFF_DICT`、`COMM.SYS_EMPLOYEE` 的工号/登录名口径做后续只读比对。

## 8. 警告与限制

{chr(10).join(warning_lines)}
"""


def empty_assets(error: str) -> dict[str, Any]:
    return {
        "tables": [],
        "columns": [],
        "indexes": [],
        "constraints": [],
        "views": [],
        "owners": [],
        "catalog": {
            "generated_at": utc_now_iso(),
            "source_system": SOURCE_SYSTEM,
            "source_db": SOURCE_DB,
            "owners_count": 0,
            "tables_count": 0,
            "columns_count": 0,
            "indexes_count": 0,
            "constraints_count": 0,
            "views_count": 0,
            "core_candidate_tables": [],
            "pii_columns_summary": {"by_flag": {}, "tables_count": 0, "columns": []},
            "warnings": [f"HRP metadata collection not completed: {error}"],
        },
    }


def main() -> int:
    try:
        raw = run_remote_queries(metadata_queries())
        assets = build_assets(raw)
        status = "已完成。所有查询均为 SELECT，只采集元数据和聚合统计，不输出业务明细。"
        error = ""
    except Exception as exc:
        error = str(exc)
        assets = empty_assets(error)
        status = "未完成。未生成真实 HRP 元数据资产，仅生成可复跑脚本和空结构文件。"
    write_assets(assets)
    REPORT_PATH.write_text(render_report(assets, status=status, error=error), encoding="utf-8")
    result = {
        "status": "success" if not error else "blocked",
        "generated_at": utc_now_iso(),
        "source_system": SOURCE_SYSTEM,
        "source_db": SOURCE_DB,
        "output_dir": str(OUT_DIR.relative_to(BASE_DIR)),
        "report": REPORT_PATH.name,
        "catalog_summary": assets["catalog"],
        "error": error,
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "status": result["status"],
        "error": error,
        "generated_at": assets["catalog"]["generated_at"],
        "source_system": assets["catalog"]["source_system"],
        "source_db": assets["catalog"]["source_db"],
        "owners_count": assets["catalog"]["owners_count"],
        "tables_count": assets["catalog"]["tables_count"],
        "columns_count": assets["catalog"]["columns_count"],
        "indexes_count": assets["catalog"]["indexes_count"],
        "constraints_count": assets["catalog"]["constraints_count"],
        "views_count": assets["catalog"]["views_count"],
        "warnings": assets["catalog"]["warnings"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not error else 2


if __name__ == "__main__":
    sys.exit(main())
