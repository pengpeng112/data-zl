"""126: import 48-item core institution SQL packages as query + metric assets.

Reads 取数/48项目核心制度/指标SQL/*.sql headers and SQL body.
Does not execute source DB SQL; only registers definitions/versions.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .metric_service import ingest_metric
from .query_intake import ingest_query

_HEADER_TITLE = re.compile(r"指标\s*(\d+)\s*[：:]\s*(.+?)(?:\s*（|$)", re.M)
_NUM = re.compile(r"分子[：:]\s*(.+)")
_DEN = re.compile(r"分母[：:]\s*(.+)")
_PERIOD = re.compile(r"月份归属[：:]\s*(.+)")
_SCOPE = re.compile(r"纳排[：:]\s*(.+)")
_NOTE = re.compile(r"说明[：:]\s*(.+)|有限可用|不可提取|部分")


def default_core_sql_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[3]
    # Prefer exact name under 取数
    base = root / "取数"
    for p in base.iterdir() if base.exists() else []:
        if p.is_dir() and "48" in p.name:
            sql_dir = p / "指标SQL"
            if sql_dir.is_dir():
                return sql_dir
    return base / "48项目核心制度" / "指标SQL"


def parse_metric_sql_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    header = text[:2000]
    m = _HEADER_TITLE.search(header)
    if m:
        num, title = m.group(1), m.group(2).strip()
    else:
        # fallback from filename 指标03_xxx.sql
        fm = re.match(r"指标(\d+)_(.+)\.sql$", path.name)
        num = fm.group(1) if fm else "0"
        title = fm.group(2) if fm else path.stem
    num_i = int(num)
    code_num = f"{num_i:02d}"

    def _first(rx: re.Pattern[str]) -> str | None:
        hit = rx.search(header)
        return hit.group(1).strip() if hit else None

    num_desc = _first(_NUM)
    den_desc = _first(_DEN)
    period = _first(_PERIOD)
    scope = _first(_SCOPE)
    limitations = []
    if "有限可用" in header:
        limitations.append("有限可用（依赖标题/字段语义）")
    if "不可提取" in header:
        limitations.append("文档标注不可完整提取")
    if scope:
        limitations.append(f"纳排: {scope}")

    # Strip block comment header for SQL body but keep WITH/SELECT
    body = re.sub(r"/\*.*?\*/", "", text, count=1, flags=re.S).strip()
    if not body:
        body = text
    # Remove leading pure comment lines
    lines = [ln for ln in body.splitlines() if not ln.strip().startswith("--")]
    sql = "\n".join(lines).strip()

    return {
        "metric_no": num_i,
        "metric_code": f"MET_CORE_{code_num}",
        "query_code": f"QRY_CORE_{code_num}",
        "title": title,
        "numerator_desc": num_desc,
        "denominator_desc": den_desc,
        "period_field": period or "HIS.PAT_VISIT.DISCHARGE_DATE_TIME",
        "limitations": limitations,
        "sql_text": sql,
        "source_path": str(path),
        "formula": "分子/分母" if (num_desc or den_desc) else None,
        "definition_text": f"48项核心制度 指标{num_i}：{title}",
    }


def discover_core_sql_files(sql_dir: Path | None = None) -> list[Path]:
    d = sql_dir or default_core_sql_dir()
    if not d.is_dir():
        return []
    return sorted(d.glob("指标*.sql"), key=lambda p: p.name)


def import_core_metrics(
    db: Session,
    *,
    sql_dir: Path | None = None,
    dry_run: bool = True,
    system_code: str = "DATA_CENTER",
    source_code: str = "ods_8_216",
    dialect: str = "oracle",
    created_by: str = "core_metric_import",
    only_numbers: set[int] | None = None,
) -> dict[str, Any]:
    files = discover_core_sql_files(sql_dir)
    results = []
    for path in files:
        parsed = parse_metric_sql_file(path)
        if only_numbers and parsed["metric_no"] not in only_numbers:
            continue
        item = {
            "file": path.name,
            "metric_code": parsed["metric_code"],
            "query_code": parsed["query_code"],
            "title": parsed["title"],
            "sql_len": len(parsed["sql_text"] or ""),
        }
        if dry_run:
            item["dry_run"] = True
            results.append(item)
            continue
        q = ingest_query(
            db,
            query_code=parsed["query_code"],
            title=f"{parsed['title']}（查询）",
            sql_text=parsed["sql_text"],
            purpose=parsed["definition_text"],
            system_code=system_code,
            source_code=source_code,
            dialect=dialect,
            business_domain="电子病历核心制度",
            grain="month",
            period_field=parsed["period_field"],
            limitations=parsed["limitations"],
            source_path=parsed["source_path"],
            created_by=created_by,
        )
        m = ingest_metric(
            db,
            metric_code=parsed["metric_code"],
            title=parsed["title"],
            meaning=parsed["definition_text"],
            category="48项核心制度",
            unit="%",
            frequency="month",
            grain="month",
            definition_text=parsed["definition_text"],
            numerator_desc=parsed["numerator_desc"],
            denominator_desc=parsed["denominator_desc"],
            formula=parsed["formula"],
            query_code=parsed["query_code"],
            query_version=q["version"]["version"] if q.get("version") else None,
            period_field=parsed["period_field"],
            limitations=parsed["limitations"],
            system_code=system_code,
            source_code=source_code,
            created_by=created_by,
            auto_activate=True,
        )
        item["query"] = {
            "version": q["version"]["version"],
            "status": q["version"]["status"],
            "idempotent": q.get("idempotent"),
            "activated": q.get("activated"),
        }
        item["metric"] = {
            "version": m["version"]["version"],
            "status": m["version"]["status"],
            "idempotent": m.get("idempotent"),
            "activated": m.get("activated"),
        }
        results.append(item)
    if not dry_run:
        db.commit()
    return {
        "sql_dir": str(sql_dir or default_core_sql_dir()),
        "dry_run": dry_run,
        "count": len(results),
        "items": results,
    }
