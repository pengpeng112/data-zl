"""HIS COMM.INFECT_DIAG_DICT lookup for diagnosis mapping UI.

Readonly dictionary (~265 rows). Search by Chinese name, ICD code, or pinyin initials.
HIS live fetch is cached in-process; failure falls back to names already stored
on platform mapping rows and never raises to the page.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.asset_system import AssetDataSource
from ..models.dict_medical import DictMedicalCodeItem
from .medical_code_push import _build_connector, _pinyin_initials

logger = logging.getLogger(__name__)

HIS_TABLE = "COMM.INFECT_DIAG_DICT"
HIS_SQL = (
    "SELECT DIAG_CODE, INFECT_NAME FROM COMM.INFECT_DIAG_DICT WHERE ROWNUM <= 500"
)
CACHE_TTL_SECONDS = 300
MAX_ITEMS = 500

_cache: tuple[float, dict[str, Any]] | None = None


def clear_infect_diag_cache() -> None:
    global _cache
    _cache = None


def match_infect_diag_dict(items: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    q = (query or "").strip().lower()
    if not q:
        return list(items)
    matched: list[dict[str, str]] = []
    for item in items:
        name = (item.get("name") or "").lower()
        code = (item.get("code") or "").lower()
        pinyin = (item.get("input_code") or "").lower()
        if q in name or q in code or q in pinyin:
            matched.append(item)
    return matched


def _cell(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return str(row[key]).strip()
    lower = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        value = lower.get(key.lower())
        if value not in (None, ""):
            return str(value).strip()
    return ""


def normalize_infect_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in raw_rows[:MAX_ITEMS]:
        code = _cell(row, "DIAG_CODE", "diag_code", "code")
        name = _cell(row, "INFECT_NAME", "infect_name", "name")
        if not name:
            continue
        key = (code, name)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "code": code,
            "name": name,
            "input_code": _pinyin_initials(name, max_length=20),
        })
    items.sort(key=lambda item: (item["name"], item["code"]))
    return items


def _fallback_from_platform(db: Session) -> list[dict[str, str]]:
    rows = db.scalars(
        select(DictMedicalCodeItem).where(DictMedicalCodeItem.code_set_code == "diagnosis_local_clinical")
    ).all()
    raw: list[dict[str, Any]] = []
    for row in rows:
        extra = row.extra or {}
        name = str(extra.get("infectious_disease_name") or "").strip()
        if not name:
            continue
        raw.append({
            "DIAG_CODE": str(extra.get("infectious_disease_code") or "").strip(),
            "INFECT_NAME": name,
        })
    return normalize_infect_rows(raw)


def _resolve_his_source(db: Session) -> AssetDataSource | None:
    codes = [
        (settings.dict_medical_his_source_code or "").strip(),
        "his_source_10_10_10_15",
    ]
    for code in codes:
        if not code:
            continue
        source = db.scalar(select(AssetDataSource).where(AssetDataSource.source_code == code))
        if source and source.enabled is not False:
            return source
    return db.scalar(
        select(AssetDataSource).where(
            AssetDataSource.system_code.in_(["HIS_SOURCE", "HIS"]),
            AssetDataSource.enabled.is_(True),
        )
    )


def load_infect_diag_dict(
    db: Session,
    *,
    fetcher: Callable[[AssetDataSource], list[dict[str, Any]]] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Return {source, items}. source is HIS table, fallback, or unavailable."""
    global _cache
    ts = time.time() if now is None else now
    if _cache and ts - _cache[0] < CACHE_TTL_SECONDS:
        return _cache[1]

    payload = {"source": "unavailable", "table": HIS_TABLE, "items": []}
    try:
        source = _resolve_his_source(db)
        raw_rows: list[dict[str, Any]] = []
        if source is not None:
            if fetcher is not None:
                raw_rows = fetcher(source)
            else:
                connector = _build_connector(source, write=False)
                try:
                    raw_rows = connector.execute_readonly(HIS_SQL, max_rows=MAX_ITEMS)
                finally:
                    connector.close()
            items = normalize_infect_rows(raw_rows)
            if items:
                payload = {"source": HIS_TABLE, "table": HIS_TABLE, "items": items}
        if payload["source"] != HIS_TABLE:
            fallback = _fallback_from_platform(db)
            if fallback:
                payload = {"source": "fallback", "table": HIS_TABLE, "items": fallback}
    except Exception:
        logger.exception("infect_diag_dict lookup failed")
        try:
            fallback = _fallback_from_platform(db)
            if fallback:
                payload = {"source": "fallback", "table": HIS_TABLE, "items": fallback}
        except Exception:
            logger.exception("infect_diag_dict fallback failed")

    _cache = (ts, payload)
    return payload
