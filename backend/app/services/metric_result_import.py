"""Import historical monthly metric results from 48-item CSV files."""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.metric_asset import AssetMetricResult
from .metric_service import get_active_metric_version, get_metric, register_metric_result


def _norm_period(raw: str) -> str:
    s = (raw or "").strip()
    # 2026年1月 -> 2026-01
    m = re.match(r"(\d{4})\s*年\s*(\d{1,2})\s*月", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{4})-(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return s


def _norm_code(raw: str) -> str:
    s = str(raw or "").strip()
    m = re.search(r"(\d+)", s)
    if not m:
        return ""
    return f"MET_CORE_{int(m.group(1)):02d}"


def discover_result_csvs(repo_root: Path | None = None) -> list[Path]:
    """Find 48-item result CSVs under 取数/. Try common roots (repo / container)."""
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    if repo_root:
        candidates.append(Path(repo_root))
    # local monorepo: backend/app/services -> parents[3]=repo root
    # container layout: /app/app/services -> parents[2]=/app
    candidates.extend(
        [
            here.parents[3],
            here.parents[2],
            Path("/app"),
            Path("/opt/data-asset"),
            Path("/"),
        ]
    )
    seen: set[str] = set()
    out: list[Path] = []
    for root in candidates:
        base = root / "取数"
        if not base.is_dir():
            continue
        for p in base.rglob("*.csv"):
            name = p.name
            if "48" in name or "指标" in name or "补充" in name or "拆分" in name:
                if "结果" in name or "核查" in name:
                    key = str(p.resolve())
                    if key not in seen:
                        seen.add(key)
                        out.append(p)
        if out:
            break
    return sorted(out)


def import_metric_results_from_csv(
    db: Session,
    *,
    csv_path: Path,
    dry_run: bool = True,
    created_by: str = "metric_result_import",
) -> dict[str, Any]:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    inserted = 0
    skipped = 0
    samples = []
    for r in rows:
        code = _norm_code(r.get("指标编号") or "")
        period = _norm_period(r.get("月份") or "")
        if not code or not period:
            skipped += 1
            continue
        mv = get_active_metric_version(db, code)
        if not mv:
            # try without zero pad mismatch
            skipped += 1
            continue
        num = (r.get("分子") or r.get("分子分母") or "").strip() or None
        den = (r.get("分母") or "").strip() or None
        note = (r.get("结果状态及说明") or r.get("说明") or r.get("口径与说明") or "").strip() or None
        # compute simple rate if both numeric
        metric_value = None
        status = "ok"
        if note and ("无法" in note or "不可" in note or "未提取" in note):
            status = "partial" if ("部分" in note or "分子" in note) else "unavailable"
        try:
            if num is not None and den is not None and den not in {"", "0"}:
                metric_value = f"{float(num) / float(den) * 100:.4f}%"
        except ValueError:
            metric_value = None
        num_s = str(num) if num is not None else None
        den_s = str(den) if den is not None else None
        # Idempotent: skip if latest row for this metric+period already matches values
        prev = db.scalar(
            select(AssetMetricResult)
            .where(
                AssetMetricResult.metric_code == code,
                AssetMetricResult.period_key == period,
            )
            .order_by(AssetMetricResult.id.desc())
            .limit(1)
        )
        if prev and (prev.numerator_value or None) == num_s and (prev.denominator_value or None) == den_s:
            skipped += 1
            continue
        if dry_run:
            inserted += 1
            if len(samples) < 3:
                samples.append({"metric_code": code, "period": period, "num": num, "den": den})
            continue
        register_metric_result(
            db,
            metric_code=code,
            period_key=period,
            numerator_value=num_s,
            denominator_value=den_s,
            metric_value=metric_value,
            status=status,
            limitations_note=note,
            created_by=created_by,
        )
        inserted += 1
    if not dry_run:
        db.commit()
    return {
        "csv": str(csv_path),
        "dry_run": dry_run,
        "rows": len(rows),
        "inserted": inserted,
        "skipped": skipped,
        "samples": samples,
    }


def import_all_result_csvs(
    db: Session,
    *,
    dry_run: bool = True,
    created_by: str = "metric_result_import",
    repo_root: Path | None = None,
) -> dict:
    files = discover_result_csvs(repo_root=repo_root)
    items = []
    total = 0
    for f in files:
        r = import_metric_results_from_csv(db, csv_path=f, dry_run=dry_run, created_by=created_by)
        items.append(r)
        total += r["inserted"]
    return {"file_count": len(files), "total_inserted": total, "dry_run": dry_run, "items": items}
