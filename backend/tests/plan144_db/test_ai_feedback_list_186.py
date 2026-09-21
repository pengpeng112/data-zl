"""186 Q2 DB tests: feedback list contract (§4.4) + single-item read scope.

Covers T13/T15 API-side semantics at the service layer:
- mine scope filters by submitted_by; legacy NULL submitted_by belongs to no one
- queue scope requires review permission (PermissionError otherwise)
- invalid status/scope → ValueError (API maps to 422)
- pagination caps + stable ordering (186 v1.10 P1-12/T60:
  submitted_at DESC NULLS LAST, id DESC)
- feedback_readable_by: owner-or-reviewer only; empty owner never matches

186 v1.10 P1-12：本模块自带 SQLite 内存 db_session（覆盖根 conftest 的
db_session 与数据库 autouse），可在哑 APP_TEST_DB_URL 下零真实数据库运行；
排序契约新增 submitted_at 乱序/相同/NULL 三类记录与跨页稳定性断言。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import BigInteger, create_engine, event, insert, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.ai_accuracy import AssetAiAnswerEvent, AssetAiFeedback
from app.services.ai_feedback_service import (
    feedback_readable_by,
    list_feedback,
    register_answer_event,
    submit_feedback,
)


# ai_accuracy 模型使用 PG 专有 JSONB / BigInteger 主键；在 SQLite 内存库上
# 编译为 JSON / INTEGER（与 identity_sync 的 PortableJSON/PortableBigInt 同义，
# 与 PG 类型能力等价：列表 JSON 序列化 + 整型自增主键）。
# 仅注册到 sqlite 方言，不影响 PostgreSQL 测试的编译结果。
@compiles(JSONB, "sqlite")
def _jsonb_as_json_sqlite(type_, compiler, **kw):  # pragma: no cover - 编译钩子
    return "JSON"


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_sqlite(type_, compiler, **kw):  # pragma: no cover - 编译钩子
    return "INTEGER"


@pytest.fixture(autouse=True)
def clean_test_database():
    """覆盖根 conftest 的数据库 autouse：本模块用各自 SQLite 内存引擎，
    不连接 APP_TEST_DB_URL 指向的库（与纯逻辑子目录 no-op 模式一致）。"""
    yield


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _attach_schema(dbapi_conn, connection_record):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS asset")

    Base.metadata.create_all(
        engine,
        tables=[AssetAiAnswerEvent.__table__, AssetAiFeedback.__table__],
    )
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def answer_event(db_session):
    result = register_answer_event(
        db_session,
        question_summary="2026年7月住院次均费用（186 Q2 测试）",
        caller_id="web-console",
        query_code="QRY_186",
        query_version=1,
        run_id=4242,
        result_digest="b" * 64,
        answer_text="示例答案",
    )
    db_session.commit()
    return result["answer_event_id"]


def _submit(db, event_id, submitted_by, rating="incorrect"):
    return submit_feedback(
        db, answer_event_id=event_id, rating=rating,
        error_types=["numerator"], submitted_by=submitted_by,
    )


def _row(db, event_id, submitted_at, *, submitted_by="alice", rating="correct"):
    row = AssetAiFeedback(
        answer_event_id=event_id, rating=rating, error_types=["numerator"],
        comment="", suggested_revision="", submitted_by=submitted_by,
        status="submitted", submitted_at=submitted_at,
    )
    db.add(row)
    db.flush()
    return row


def _null_row(db, event_id, *, submitted_by="alice"):
    """构造 submitted_at 为 NULL 的历史行。

    ORM 构造器对 None + server_default 会改走服务端默认，故用 Core insert
    显式绑定 NULL。"""
    db.execute(
        insert(AssetAiFeedback).values(
            answer_event_id=event_id, rating="correct", error_types=[],
            comment="", suggested_revision="", submitted_by=submitted_by,
            status="submitted", submitted_at=None,
        )
    )
    db.flush()
    return db.scalars(
        select(AssetAiFeedback)
        .where(AssetAiFeedback.submitted_at.is_(None))
        .order_by(AssetAiFeedback.id.desc())
    ).first()


def test_mine_scope_returns_only_own_history(db_session, answer_event):
    _submit(db_session, answer_event, "alice")
    _submit(db_session, answer_event, "bob", rating="correct")
    result = list_feedback(
        db_session, current_user="alice", has_review_permission=False, scope="mine"
    )
    assert result["total"] == 1
    item = result["items"][0]
    assert item["rating"] == "incorrect"
    # §4.4 最小字段集
    for key in (
        "feedback_id", "answer_event_id", "status", "rating", "error_types",
        "submitted_at", "query_code", "query_version", "metric_code",
        "metric_version", "product_code", "run_id", "result_digest",
    ):
        assert key in item
    assert item["run_id"] == 4242
    assert item["result_digest"] == "b" * 64
    # 长文本不在列表（详情按权限获取）
    assert "question_summary" not in item
    assert "comment" not in item


def test_legacy_null_submitted_by_belongs_to_no_one(db_session, answer_event):
    db_session.add(AssetAiFeedback(
        answer_event_id=answer_event, rating="correct",
        error_types=[], comment="", suggested_revision="",
        submitted_by=None, status="submitted",
    ))
    db_session.commit()
    result = list_feedback(
        db_session, current_user="alice", has_review_permission=False, scope="mine"
    )
    assert result["total"] == 0
    row = db_session.query(AssetAiFeedback).first()
    assert feedback_readable_by(row, current_user="alice", has_review_permission=False) is False
    assert feedback_readable_by(row, current_user=None, has_review_permission=False) is False
    assert feedback_readable_by(row, current_user="alice", has_review_permission=True) is True


def test_queue_scope_requires_review_permission(db_session, answer_event):
    _submit(db_session, answer_event, "alice")
    with pytest.raises(PermissionError):
        list_feedback(
            db_session, current_user="alice", has_review_permission=False, scope="queue"
        )
    result = list_feedback(
        db_session, current_user="reviewer", has_review_permission=True, scope="queue"
    )
    assert result["total"] == 1


def test_invalid_params_raise_value_error(db_session, answer_event):
    _submit(db_session, answer_event, "alice")
    with pytest.raises(ValueError):
        list_feedback(db_session, current_user="alice", has_review_permission=False, scope="all")
    with pytest.raises(ValueError):
        list_feedback(
            db_session, current_user="alice", has_review_permission=True,
            status="not_a_status",
        )


def test_pagination_and_stable_order(db_session, answer_event):
    for i in range(5):
        _submit(db_session, answer_event, f"alice", rating="correct")
    db_session.commit()
    page1 = list_feedback(
        db_session, current_user="alice", has_review_permission=False,
        scope="mine", page=1, page_size=2,
    )
    page4 = list_feedback(
        db_session, current_user="alice", has_review_permission=False,
        scope="mine", page=4, page_size=2,
    )
    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    # 超出最后页（5 条 / 每页 2 → 第 4 页）：200 + items=[] + total 真实值
    assert page4["items"] == []
    assert page4["total"] == 5
    ids = [item["feedback_id"] for item in page1["items"]]
    assert ids == sorted(ids, reverse=True)


def test_status_and_query_code_filters(db_session, answer_event):
    fb = _submit(db_session, answer_event, "alice")
    from app.services.ai_feedback_service import review_feedback

    review_feedback(db_session, feedback_id=fb["feedback_id"], action="triaged", reviewed_by="r")
    db_session.commit()
    submitted_only = list_feedback(
        db_session, current_user="alice", has_review_permission=True,
        scope="mine", status="submitted",
    )
    triaged_only = list_feedback(
        db_session, current_user="alice", has_review_permission=True,
        scope="mine", status="triaged",
    )
    assert submitted_only["total"] == 0
    assert triaged_only["total"] == 1
    by_code = list_feedback(
        db_session, current_user="alice", has_review_permission=True,
        scope="mine", query_code="QRY_186",
    )
    assert by_code["total"] == 1
    by_other_code = list_feedback(
        db_session, current_user="alice", has_review_permission=True,
        scope="mine", query_code="QRY_NONE",
    )
    assert by_other_code["total"] == 0


def test_read_scope_owner_or_reviewer(db_session, answer_event):
    fb = _submit(db_session, answer_event, "alice")
    row = db_session.query(AssetAiFeedback).filter_by(id=fb["feedback_id"]).first()
    assert feedback_readable_by(row, current_user="alice", has_review_permission=False) is True
    assert feedback_readable_by(row, current_user="bob", has_review_permission=False) is False
    assert feedback_readable_by(row, current_user="bob", has_review_permission=True) is True


# ---------------------------------------------------------------------------
# 186 v1.10 P1-12/T60：submitted_at DESC NULLS LAST, id DESC 排序契约
# ---------------------------------------------------------------------------


def test_order_submitted_at_desc_nulls_last_id_tiebreak(db_session, answer_event):
    tz = timezone.utc
    r_old = _row(db_session, answer_event, datetime(2026, 9, 1, 10, 0, tzinfo=tz))
    r_new = _row(db_session, answer_event, datetime(2026, 9, 3, 9, 0, tzinfo=tz))
    r_mid_a = _row(db_session, answer_event, datetime(2026, 9, 2, 8, 0, tzinfo=tz))
    r_mid_b = _row(db_session, answer_event, datetime(2026, 9, 2, 8, 0, tzinfo=tz))
    r_null = _null_row(db_session, answer_event)
    db_session.commit()

    result = list_feedback(
        db_session, current_user="alice", has_review_permission=False,
        scope="mine", page=1, page_size=100,
    )
    assert result["total"] == 5
    ids = [item["feedback_id"] for item in result["items"]]
    # 乱序插入：最新时间在前；相同 submitted_at 按 id 降序（b 后插入 id 更大）；
    # NULL（历史缺时间）排末尾。
    assert ids == [r_new.id, r_mid_b.id, r_mid_a.id, r_old.id, r_null.id]
    submitted = [item["submitted_at"] for item in result["items"]]
    assert submitted[4] is None
    assert all(submitted[i] is not None for i in range(4))
    # 时间降序（非 NULL 部分）
    non_null = submitted[:4]
    assert non_null == sorted(non_null, reverse=True)


def test_cross_page_stable_no_dup_no_gap(db_session, answer_event):
    tz = timezone.utc
    same = [
        _row(db_session, answer_event, datetime(2026, 9, 2, 8, 0, tzinfo=tz))
        for _ in range(4)
    ]
    null_a = _null_row(db_session, answer_event)
    null_b = _null_row(db_session, answer_event)
    db_session.commit()

    def _page(page: int):
        return list_feedback(
            db_session, current_user="alice", has_review_permission=False,
            scope="mine", page=page, page_size=2,
        )["items"]

    pages = [_page(1), _page(2), _page(3)]
    assert all(len(p) == 2 for p in pages)
    all_ids = [item["feedback_id"] for page in pages for item in page]
    # 跨页不重不漏：5 类记录 6 行全覆盖且无重复
    expected_ids = [
        same[3].id, same[2].id,   # 第1页：同时间按 id 降序
        same[1].id, same[0].id,   # 第2页：第1页末与第2页首衔接（同时间边界）
        null_b.id, null_a.id,     # 第3页：NULL 最后（组内同样 id 降序）
    ]
    assert all_ids == expected_ids
    assert len(all_ids) == len(set(all_ids)) == 6
    # 同时间跨页边界：第1页末与第2页首时间相同、id 严格衔接（不重不漏）
    assert pages[0][1]["submitted_at"] == pages[1][0]["submitted_at"]
    assert pages[0][1]["feedback_id"] > pages[1][0]["feedback_id"]
    # NULL 全部在最后一页
    assert [item["submitted_at"] for item in pages[2]] == [None, None]
    assert all(item["submitted_at"] is not None for page in pages[:2] for item in page)
    # 翻页外无第4页数据（total 真实值）
    full = list_feedback(
        db_session, current_user="alice", has_review_permission=False,
        scope="mine", page=4, page_size=2,
    )
    assert full["items"] == [] and full["total"] == 6
