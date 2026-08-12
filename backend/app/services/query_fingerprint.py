"""126 P1: SQL normalize + hash + parameter hash for query versions."""
from __future__ import annotations

import hashlib
import json
import re


_WS = re.compile(r"\s+")
_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)


def normalize_sql(sql: str) -> str:
    text = (sql or "").strip()
    text = _COMMENTS.sub(" ", text)
    text = _WS.sub(" ", text)
    return text.strip().rstrip(";").strip().upper()


def sql_sha256(sql: str) -> str:
    return hashlib.sha256(normalize_sql(sql).encode("utf-8")).hexdigest()


def semantic_fingerprint(sql: str, *, system_code: str | None = None, source_code: str | None = None) -> str:
    payload = {
        "sql": normalize_sql(sql),
        "system_code": (system_code or "").upper(),
        "source_code": (source_code or "").lower(),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parameters_hash(params: dict | None) -> str:
    raw = json.dumps(params or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def result_hash(payload) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
