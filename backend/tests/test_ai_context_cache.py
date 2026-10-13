"""215 E5：AI 上下文构建缓存与过期清理测试。

核心裁决回归：
- 缓存键不得用 manifest_hash（同计数不同题会串快照）——键含 question
  归一化与权限过滤，同参命中、异 question/异权限不串。
- 缓存命中不消除留档（每次 resolve 仍写一条 snapshots 行）。
- 击穿防护：并发同键 resolve 不撞 context_id 唯一约束（DEF212-002 场景
  在缓存路径的回归）。
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.ai_collab import AiContextCacheEntry, AiContextSnapshot
from app.services.ai_context_cache import (
    cleanup_expired_contexts,
    compute_context_cache_key,
    normalize_question,
    resolve_context_cached,
)


def _snapshot_count(db) -> int:
    return len(db.scalars(select(AiContextSnapshot)).all())


def test_normalize_question_collapses_whitespace_and_case():
    assert normalize_question("  离院方式   统计 ") == "离院方式 统计"
    assert normalize_question("Discharge Stats") == "discharge stats"
    assert normalize_question(None) == ""
    assert normalize_question("  A  B ") == normalize_question("A B")


def test_cache_key_separates_same_counts_different_question():
    """manifest_hash 陷阱回归：内容计数完全相同（空库两问）键也必须不同。"""
    k1 = compute_context_cache_key(
        system_code="HIS", question_summary="离院方式 统计", permission_scope=["ai.context.read"]
    )
    k2 = compute_context_cache_key(
        system_code="HIS", question_summary="手术量 统计", permission_scope=["ai.context.read"]
    )
    assert k1 != k2
    # 归一化后同题（多余空白差异）同键
    k3 = compute_context_cache_key(
        system_code="HIS", question_summary="  离院方式   统计 ", permission_scope=["ai.context.read"]
    )
    assert k1 == k3


def test_cache_key_separates_system_params_and_permissions():
    base = dict(system_code="HIS", question_summary="q")
    assert compute_context_cache_key(**base, permission_scope=["a"]) != compute_context_cache_key(
        **base, permission_scope=["a", "b"]
    )
    assert compute_context_cache_key(**base, permission_scope=["a"]) != compute_context_cache_key(
        system_code="LIS", question_summary="q", permission_scope=["a"]
    )
    assert compute_context_cache_key(**base, permission_scope=["a"], max_objects=50) != (
        compute_context_cache_key(**base, permission_scope=["a"], max_objects=200)
    )


def test_cache_hit_reuses_content_and_keeps_archive(db_session, monkeypatch):
    monkeypatch.setattr("app.services.ai_context_cache.settings.ai_context_cache_enabled", True)
    before = _snapshot_count(db_session)

    doc1, meta1 = resolve_context_cached(
        db_session, question_summary="离院方式统计", system_code="HIS",
        permission_scope=["ai.context.read"],
    )
    db_session.commit()
    assert meta1["hit"] is False
    assert _snapshot_count(db_session) == before + 1

    doc2, meta2 = resolve_context_cached(
        db_session, question_summary="离院方式统计", system_code="HIS",
        permission_scope=["ai.context.read"],
    )
    db_session.commit()
    # 命中：跳过重建但仍留档一条，context_id 与首次不同
    assert meta2["hit"] is True
    assert _snapshot_count(db_session) == before + 2
    assert doc2["context_id"] != doc1["context_id"]
    # 内容复用（对象清单一致），且 doc 带命中元信息
    assert doc2["objects"] == doc1["objects"]
    assert doc2["cache"]["hit"] is True and doc2["cache"]["age_seconds"] is not None
    entry = db_session.scalar(select(AiContextCacheEntry))
    assert entry.hit_count == 1


def test_different_question_or_permission_no_cross_contamination(db_session, monkeypatch):
    monkeypatch.setattr("app.services.ai_context_cache.settings.ai_context_cache_enabled", True)
    _, meta_q1 = resolve_context_cached(
        db_session, question_summary="手术量", system_code="HIS", permission_scope=["p1"]
    )
    _, meta_q2 = resolve_context_cached(
        db_session, question_summary="离院方式", system_code="HIS", permission_scope=["p1"]
    )
    _, meta_p2 = resolve_context_cached(
        db_session, question_summary="离院方式", system_code="HIS", permission_scope=["p1", "p2"]
    )
    assert meta_q1["hit"] is False and meta_q2["hit"] is False and meta_p2["hit"] is False
    keys = db_session.scalars(select(AiContextCacheEntry.cache_key)).all()
    assert len(keys) == 3  # 三个不同键，各自独立缓存

    # 同参再来一次全部命中（正例）
    _, meta_again = resolve_context_cached(
        db_session, question_summary="离院方式", system_code="HIS", permission_scope=["p1"]
    )
    assert meta_again["hit"] is True


def test_cache_disabled_passthrough_writes_no_entry(db_session, monkeypatch):
    monkeypatch.setattr("app.services.ai_context_cache.settings.ai_context_cache_enabled", False)
    doc, meta = resolve_context_cached(
        db_session, question_summary="q", system_code="HIS",
        permission_scope=["ai.context.read"], enabled=False,
    )
    assert meta["hit"] is False and meta["enabled"] is False
    assert db_session.scalar(select(AiContextCacheEntry)) is None
    assert doc["context_id"].startswith("ctx-")


def test_concurrent_same_key_resolves_never_hit_unique_violation(monkeypatch):
    """DEF212-002 回归（缓存路径）：并发同参构建/命中留档不撞 context_id 唯一约束。

    每线程独立会话，模拟多请求并发 resolve；全部成功、context_id 全不同。
    """
    from app.core.db import SessionLocal

    results: list[tuple[str, str]] = []
    errors: list[Exception] = []
    barrier = threading.Barrier(4)

    def _worker(idx: int) -> None:
        db = SessionLocal()
        try:
            barrier.wait(timeout=10)
            doc, meta = resolve_context_cached(
                db,
                question_summary="并发同键构建",
                system_code="HIS",
                permission_scope=["ai.context.read"],
            )
            db.commit()
            results.append((doc["context_id"], str(meta["hit"])))
        except Exception as exc:  # noqa: BLE001 — 收集后统一断言
            errors.append(exc)
            db.rollback()
        finally:
            db.close()

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not errors, f"并发 resolve 出现异常: {errors!r}"
    context_ids = [cid for cid, _ in results]
    assert len(context_ids) == 4 and len(set(context_ids)) == 4
    # 至多一个缓存条目（同键），全部留档行独立存在
    db = SessionLocal()
    try:
        entries = db.scalars(select(AiContextCacheEntry)).all()
        assert len(entries) == 1
    finally:
        db.close()


def test_api_resolve_reports_cache_meta(client):
    """端到端：同参两次 POST /context/resolve，第二次命中且响应带 cache 块。"""
    payload = {"question_summary": "E5 端到端缓存验证", "system_code": "HIS", "max_objects": 50}
    r1 = client.post("/api/v1/ai/context/resolve", json=payload)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()["data"]
    assert d1["cache"]["hit"] is False

    r2 = client.post("/api/v1/ai/context/resolve", json=payload)
    assert r2.status_code == 200, r2.text
    d2 = r2.json()["data"]
    assert d2["cache"]["hit"] is True
    assert d2["context_id"] != d1["context_id"]
    # 命中留档仍可按新 context_id 复现（留档语义未被缓存消除）
    r3 = client.get(f"/api/v1/ai/context/{d2['context_id']}")
    assert r3.status_code == 200, r3.text


def test_cleanup_deletes_expired_cache_and_respects_snapshot_grace(db_session, monkeypatch):
    from app.core.config import settings as app_settings

    monkeypatch.setattr("app.services.ai_context_cache.settings.ai_context_cache_enabled", True)
    doc, _ = resolve_context_cached(
        db_session, question_summary="待过期", system_code="HIS", permission_scope=["p"]
    )
    db_session.commit()
    now = datetime.now(timezone.utc)

    # 缓存条目改为已过期；留档行：一条刚过期（grace 内保留）、一条早过期（删）
    entry = db_session.scalar(select(AiContextCacheEntry))
    entry.expires_at = now - timedelta(seconds=1)
    fresh_snap = db_session.scalar(
        select(AiContextSnapshot).where(AiContextSnapshot.context_id == doc["context_id"])
    )
    fresh_snap.expires_at = now - timedelta(hours=1)  # grace(72h) 内 → 保留
    old_snap = AiContextSnapshot(
        context_id=f"ctx-old-{now.strftime('%Y%m%dT%H%M%S%f')}",
        schema_version="ai-data-context/v1",
        question_summary="旧",
        generated_at=now - timedelta(hours=200),
        expires_at=now - timedelta(hours=100),  # 远超 grace → 删
        snapshot_json={"legacy": True},
    )
    db_session.add(old_snap)
    db_session.commit()
    old_context_id = old_snap.context_id  # 删除后对象属性不可再读，先取值

    summary = cleanup_expired_contexts(db_session)
    assert summary == {"cache_entries_deleted": 1, "snapshots_deleted": 1}
    assert db_session.scalar(select(AiContextCacheEntry)) is None
    remaining = db_session.scalars(select(AiContextSnapshot.context_id)).all()
    assert doc["context_id"] in remaining  # grace 内的留档保留
    assert old_context_id not in remaining
    assert app_settings.ai_context_cache_cleanup_grace_hours == 72
