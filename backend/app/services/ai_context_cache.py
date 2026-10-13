"""215 E5：AI 上下文构建缓存与过期清理。

裁决要点（round-12 方案 v2 建议 3，执行合同 215 §1）：

- **缓存键绝不用 manifest_hash**——实测它只哈希各类计数，同计数不同题会串
  快照。本模块的键 = schema 版本 + system_code + question 归一化 + 全部
  构建参数 + 权限过滤摘要。
- **缓存命中不消除留档**：每次 resolve 仍写一条 asset_ai_context_snapshots
  留档行（复用 ai_context_builder._insert_snapshot_row 的微秒时间戳+重试
  防护，DEF212-002 语义不变）。
- 性能收益口径为「待测」——本模块不宣称任何具体毫秒数。
- 过期清理挂现有调度器（main.py），受 ai_context_cache_cleanup_enabled
  开关控制，不新造调度器。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from ..core.config import settings

CACHE_KEY_SCHEMA = "ai-ctx-cache/v1"


def normalize_question(question: str | None) -> str:
    """question 归一化：去首尾空白、折叠连续空白、casefold。

    「离院方式 统计」与「 离院方式统计 」视为同一问题；大小写不敏感。
    归一化只影响缓存键，不改写入快照的 question_summary 原文。
    """
    if not question:
        return ""
    return " ".join(question.split()).casefold()


def compute_context_cache_key(
    *,
    system_code: str | None,
    question_summary: str | None,
    source_code: str | None = None,
    business_domain: str | None = None,
    max_objects: int = 200,
    include_sql: bool = False,
    permission_scope: Iterable[str] | None = None,
) -> str:
    """构建缓存键（sha256）。任何影响快照内容或可见性的输入都必须进键。"""
    payload = json.dumps(
        {
            "schema": CACHE_KEY_SCHEMA,
            "system_code": (system_code or "").strip() or None,
            "question": normalize_question(question_summary),
            "source_code": (source_code or "").strip() or None,
            "business_domain": (business_domain or "").strip() or None,
            "max_objects": int(max_objects),
            "include_sql": bool(include_sql),
            "permission_scope": sorted({p for p in (permission_scope or []) if p}),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_block(hit: bool, *, age_seconds: float | None = None) -> dict[str, Any]:
    block: dict[str, Any] = {"enabled": True, "hit": bool(hit)}
    if hit:
        block["age_seconds"] = age_seconds
    return block


def resolve_context_cached(
    db,
    *,
    question_summary: str | None = None,
    system_code: str | None = None,
    source_code: str | None = None,
    business_domain: str | None = None,
    max_objects: int = 200,
    include_sql: bool = False,
    created_by: str | None = None,
    permission_scope: Iterable[str] | None = None,
    enabled: bool | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """带缓存的 context resolve：返回 (doc, cache_meta)。

    - 未启用缓存：走原 build_context_snapshot 全量路径，不写缓存条目。
    - 命中：复用缓存内容（跳过重建），但仍写一条留档行；返回的 doc 带
      新 context_id 与 cache 元信息。
    - 未命中：全量构建 + upsert 缓存条目。
    doc["cache"] 会被一并持久化到留档行，供审计区分命中/重建。
    """
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from ..models.ai_collab import AiContextCacheEntry
    from .ai_context_builder import DEFAULT_TTL_HOURS, _insert_snapshot_row, build_context_snapshot

    cache_enabled = settings.ai_context_cache_enabled if enabled is None else enabled
    if not cache_enabled:
        doc = build_context_snapshot(
            db,
            question_summary=question_summary,
            system_code=system_code,
            source_code=source_code,
            business_domain=business_domain,
            max_objects=max_objects,
            include_sql=include_sql,
            created_by=created_by,
        )
        doc["cache"] = {"enabled": False, "hit": False}
        return doc, doc["cache"]

    cache_key = compute_context_cache_key(
        system_code=system_code,
        question_summary=question_summary,
        source_code=source_code,
        business_domain=business_domain,
        max_objects=max_objects,
        include_sql=include_sql,
        permission_scope=permission_scope,
    )
    now = datetime.now(timezone.utc)
    entry = db.scalar(
        select(AiContextCacheEntry).where(
            AiContextCacheEntry.cache_key == cache_key,
            AiContextCacheEntry.expires_at > now,
        )
    )
    if entry is not None:
        content = dict(entry.snapshot_json or {})
        content.pop("cache", None)
        age_seconds = max(0.0, (now - entry.built_at).total_seconds()) if entry.built_at else None
        content["cache"] = _cache_block(True, age_seconds=age_seconds)
        _insert_snapshot_row(db, content, created_by=created_by)
        entry.hit_count = (entry.hit_count or 0) + 1
        db.flush()
        return content, content["cache"]

    doc = build_context_snapshot(
        db,
        question_summary=question_summary,
        system_code=system_code,
        source_code=source_code,
        business_domain=business_domain,
        max_objects=max_objects,
        include_sql=include_sql,
        created_by=created_by,
    )
    doc["cache"] = _cache_block(False)
    upsert = pg_insert(AiContextCacheEntry).values(
        cache_key=cache_key,
        built_at=now,
        expires_at=now + timedelta(hours=DEFAULT_TTL_HOURS),
        snapshot_json={k: v for k, v in doc.items() if k != "cache"},
        created_by=created_by,
    )
    # 同键并发未命中（击穿窗口）双双到达时，后到者覆盖先到者——内容同源同参，
    # 无正确性影响；ON CONFLICT 保证不抛唯一约束错误。
    upsert = upsert.on_conflict_do_update(
        index_elements=[AiContextCacheEntry.cache_key],
        set_={
            "built_at": now,
            "expires_at": now + timedelta(hours=DEFAULT_TTL_HOURS),
            "snapshot_json": {k: v for k, v in doc.items() if k != "cache"},
            "created_by": created_by,
        },
    )
    db.execute(upsert)
    db.flush()
    return doc, doc["cache"]


def cleanup_expired_contexts(db) -> dict[str, int]:
    """过期清理：缓存条目到期即删；留档快照按 grace 宽限期删。

    挂现有调度器周期执行（settings.ai_context_cache_cleanup_enabled 控制），
    返回删除计数供日志留痕。留档行带 grace（默认 72h）是为了过期后短时间内
    仍可经 GET /context/{id} 复现刚过期的上下文。
    """
    from sqlalchemy import delete

    from ..models.ai_collab import AiContextCacheEntry, AiContextSnapshot

    now = datetime.now(timezone.utc)
    grace = timedelta(hours=settings.ai_context_cache_cleanup_grace_hours)
    cache_res = db.execute(
        delete(AiContextCacheEntry).where(AiContextCacheEntry.expires_at < now)
    )
    snapshot_res = db.execute(
        delete(AiContextSnapshot).where(AiContextSnapshot.expires_at < now - grace)
    )
    db.commit()
    return {
        "cache_entries_deleted": cache_res.rowcount or 0,
        "snapshots_deleted": snapshot_res.rowcount or 0,
    }
