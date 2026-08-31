from datetime import datetime, timezone
import hashlib
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_permission
from ...models.asset import AssetColumn, AssetRelation, AssetTable
from ...models.ai_collab import AiSession, AiToolCall, ViewDraft
from ...models.governance_base import GovernAuditLog
from ...schemas.common import ApiResponse
from ...services.data_masking import sanitize_text
from ...services.db_connectors import forbidden_keyword_hits

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

MAX_EXPORT_TABLES = 50


AVAILABLE_TOOLS = [
    {
        "name": "search_tables",
        "description": "按关键词或业务域搜索数据资产中的表",
        "method": "GET",
        "path": "/api/v1/tables",
        "auth_required": True,
        "parameters": {
            "keyword": {"type": "string", "description": "表名关键词"},
            "domain": {"type": "string", "description": "业务域"},
        },
    },
    {
        "name": "get_table_schema",
        "description": "获取某张表的字段清单、类型和注释",
        "method": "GET",
        "path": "/api/v1/tables/{schema}/{table}/columns",
        "auth_required": True,
        "parameters": {
            "table": {"type": "string", "description": "格式 SCHEMA.TABLE，如 HIS.PAT_VISIT"},
        },
    },
    {
        "name": "get_relations",
        "description": "获取某张表的正式关联关系",
        "method": "GET",
        "path": "/api/v1/tables/{schema}/{table}/relations",
        "auth_required": True,
        "parameters": {
            "table": {"type": "string", "description": "格式 SCHEMA.TABLE"},
        },
    },
    {
        "name": "get_path",
        "description": "查找两张表之间的关联路径",
        "method": "GET",
        "path": "/api/v1/relations/path",
        "auth_required": True,
        "parameters": {
            "from": {"type": "string", "description": "起点表"},
            "to": {"type": "string", "description": "终点表"},
        },
    },
    {
        "name": "search_columns",
        "description": "按业务词搜索字段",
        "method": "GET",
        "path": "/api/v1/columns/search",
        "auth_required": True,
        "parameters": {
            "keyword": {"type": "string", "description": "搜索词，如 住院号"},
        },
    },
    {
        "name": "get_graph",
        "description": "获取全局关系图谱（正式关系）",
        "method": "GET",
        "path": "/api/v1/graph",
        "auth_required": True,
        "parameters": {
            "schema": {"type": "string", "description": "按 schema 过滤"},
            "keyword": {"type": "string", "description": "表名关键字"},
        },
    },
    {
        "name": "get_graph_neighbors",
        "description": "获取某张表的邻居子图",
        "method": "GET",
        "path": "/api/v1/graph/neighbors",
        "auth_required": True,
        "parameters": {
            "table": {"type": "string", "description": "表名"},
            "depth": {"type": "integer", "description": "跳数 1-2"},
        },
    },
    {
        "name": "submit_feedback",
        "description": "提交绑定 answer/run/context 的准确性反馈（只写平台反馈表）",
        "method": "POST",
        "path": "/api/v1/ai/feedback",
        "permission": "feedback.create",
        "auth_required": True,
        "parameters": {
            "answer_event_id": {"type": "integer"},
            "rating": {"type": "string", "enum": ["correct", "partially_correct", "incorrect", "insufficient_evidence", "ambiguous"]},
            "error_types": {"type": "array"},
            "comment": {"type": "string"},
        },
    },
    {
        "name": "get_feedback_status",
        "description": "查询反馈解决状态与新版本引用",
        "method": "GET",
        "path": "/api/v1/ai/feedback/{feedback_id}",
        "permission": "query.view",
        "auth_required": True,
        "parameters": {"feedback_id": {"type": "integer"}},
    },
    {
        "name": "get_lineage_impact",
        "description": "分析某表被哪些 ODS 视图引用",
        "method": "GET",
        "path": "/api/v1/lineage/impact",
        "auth_required": True,
        "parameters": {
            "table": {"type": "string", "description": "表名"},
        },
    },
    {
        "name": "get_view_dependencies",
        "description": "查询 ODS 视图引用表依赖关系",
        "method": "GET",
        "path": "/api/v1/lineage/views",
        "auth_required": True,
        "parameters": {
            "view": {"type": "string", "description": "视图名"},
            "referenced_table": {"type": "string", "description": "被引用表"},
        },
    },
    {
        "name": "propose_sql",
        "description": "提交 AI 生成的 SQL/视图草稿供人工审核（不执行）",
        "method": "POST",
        "path": "/api/v1/ai/propose-sql",
        "auth_required": True,
        "parameters": {
            "title": {"type": "string", "description": "视图/查询标题"},
            "sql_text": {"type": "string", "description": "SQL 语句"},
            "purpose": {"type": "string", "description": "业务目的说明"},
        },
    },
    {
        "name": "execute_approved_sql",
        "description": "Execute a manually approved SQL draft through the read-only runner with row limits, masking, and audit.",
        "method": "POST",
        "path": "/api/v1/ai/drafts/{draft_id}/execute",
        "auth_required": True,
        "parameters": {
            "draft_id": {"type": "integer", "description": "Approved draft id"},
            "source_code": {"type": "string", "description": "Registered read-only data source code"},
            "max_rows": {"type": "integer", "description": "Maximum rows to fetch, <= 5000"},
            "sample_limit": {"type": "integer", "description": "Maximum masked sample rows to return"},
        },
    },
    {
        "name": "get_system_context",
        "description": "按系统/数据源获取全量表/字段/关系上下文 + 全量 confirmed 值域与陷阱（149：写 SQL 前必须先取）",
        "method": "GET",
        "path": "/api/v1/ai/system-context",
        "auth_required": True,
        "parameters": {
            "system_code": {"type": "string", "description": "系统编码，如 DATA_CENTER/HIS_SOURCE"},
            "max_tables": {"type": "integer", "description": "最大导出的表数，默认 30"},
        },
    },
    # 149 P1b/P1c：值域知识库主动查询入口（AI 可增量拉取）
    {
        "name": "list_value_domains",
        "description": "查询字段值域知识库（confirmed 值域+陷阱；支持 updated_since 增量与 conflicted 冲突列表）",
        "method": "GET",
        "path": "/api/v1/value-domains",
        "permission": "value_domain.read",
        "auth_required": True,
        "parameters": {
            "system_code": {"type": "string"},
            "schema_name": {"type": "string"},
            "table_name": {"type": "string"},
            "column_name": {"type": "string"},
            "domain_kind": {"type": "string", "description": "enum/threshold/literal/trap"},
            "status": {"type": "string", "description": "pending/confirmed/deprecated"},
            "conflicted": {"type": "boolean"},
            "updated_since": {"type": "string", "description": "ISO 时间，增量拉取"},
        },
    },
    {
        "name": "sql_risk_scan",
        "description": "对 SQL 草稿进行风险扫描（DML/DDL检测、大表全扫检测）",
        "method": "POST",
        "path": "/api/v1/ai/sql-risk-scan",
        "auth_required": True,
        "parameters": {
            "sql_text": {"type": "string", "description": "需扫描的 SQL"},
        },
    },
    # 126 P5: query / metric / data-product MCP tools (no arbitrary SQL)
    {
        "name": "list_queries",
        "description": "列出已登记查询资产（版本化 SQL 口径）",
        "method": "GET",
        "path": "/api/v1/queries",
        "auth_required": True,
        "parameters": {
            "keyword": {"type": "string", "description": "编码/标题关键词"},
            "page": {"type": "integer"},
        },
    },
    {
        "name": "get_query",
        "description": "获取查询资产详情与现行 SQL 版本",
        "method": "GET",
        "path": "/api/v1/queries/{query_code}",
        "auth_required": True,
        "parameters": {"query_code": {"type": "string", "description": "如 QRY_CORE_03"}},
    },
    {
        "name": "list_metrics",
        "description": "列出统计指标资产",
        "method": "GET",
        "path": "/api/v1/metrics",
        "auth_required": True,
        "parameters": {"keyword": {"type": "string"}},
    },
    {
        "name": "metric_board",
        "description": "获取核心制度指标月度结果看板（禁止改口径）",
        "method": "GET",
        "path": "/api/v1/metrics/board/overview",
        "auth_required": True,
        "parameters": {
            "period_from": {"type": "string", "description": "YYYY-MM"},
            "period_to": {"type": "string", "description": "YYYY-MM"},
        },
    },
    {
        "name": "list_data_products",
        "description": "列出已发布数据产品目录（禁止任意 SQL）",
        "method": "GET",
        "path": "/api/v1/data-products",
        "auth_required": True,
        "parameters": {"keyword": {"type": "string"}},
    },
    {
        "name": "execute_data_product",
        "description": "执行已发布数据产品（参数化，禁止传 SQL）",
        "method": "POST",
        "path": "/api/v1/data-products/{product_code}/execute",
        "auth_required": True,
        "parameters": {
            "product_code": {"type": "string"},
            "parameters": {"type": "object", "description": "产品参数，不得含 SQL"},
            "execute_sql": {"type": "boolean", "description": "metric 产品是否联动执行查询"},
        },
    },
    {
        "name": "list_source_capabilities",
        "description": "多源连接适配能力探测（只读）",
        "method": "GET",
        "path": "/api/v1/queries/sources/capabilities",
        "auth_required": True,
        "parameters": {},
    },
]


class ExportRequest(BaseModel):
    tables: list[str] = Field(
        default_factory=list, min_length=1, max_length=MAX_EXPORT_TABLES,
        description=f"限定导出的表名列表，必填且最多 {MAX_EXPORT_TABLES} 张"
    )
    include_relations: bool = True
    include_columns: bool = True


class SessionStartRequest(BaseModel):
    purpose: str | None = None


class ToolCallLogRequest(BaseModel):
    session_key: str
    tool_name: str
    request: dict | None = None
    response_summary: str | None = None


class ProposeSqlRequest(BaseModel):
    session_key: str | None = None
    title: str | None = None
    sql_text: str
    purpose: str | None = None


class DraftReviewRequest(BaseModel):
    status: str = Field(..., description="approved/rejected")
    feedback: str | None = None


class DraftExecuteRequest(BaseModel):
    source_code: str = Field(..., min_length=1)
    max_rows: int = Field(1000, ge=1, le=5000)
    sample_limit: int = Field(20, ge=0, le=100)


def _audit_tool_call(
    session_key: str,
    tool_name: str,
    request: dict | None,
    response_summary: str | None,
    db: Session,
) -> None:
    db.add(
        AiToolCall(
            session_key=session_key,
            tool_name=tool_name,
            request=request,
            response_summary=response_summary,
        )
    )
    db.commit()


@router.get("/tools", summary="获取 AI 可调用工具列表（供 Dify/MCP/外部 AI 注册）")
def list_tools() -> ApiResponse[dict]:
    return ApiResponse(
        data={
            "platform": "医院数据资产平台",
            "tools": AVAILABLE_TOOLS,
            "mcp_compatible": True,
            "policy": (
                "默认只读元数据与风险扫描；propose_sql 仅保存草稿不执行；"
                "execute_approved_sql 仅在草稿已人工批准后经只读 runner 限量执行；"
                "数据产品/查询/指标工具禁止任意 SQL，仅可调用已发布资产"
            ),
        }
    )


UNIFIED_TOOLS_144 = [
    {
        "name": "resolve_query_intent",
        "description": "按问题/系统/业务域构建统一 AI context 快照（认证资产优先；149 起携带全量 confirmed 值域+陷阱 value_domains 段）",
        "method": "POST",
        "path": "/api/v1/ai/context/resolve",
        "permission": "ai.context.read",
        "auth_required": True,
        "parameters": {
            "question_summary": {"type": "string"},
            "system_code": {"type": "string"},
            "business_domain": {"type": "string"},
            "max_objects": {"type": "integer", "default": 200},
        },
    },
    {
        "name": "get_certified_context",
        "description": "按 context_id 读取可复现上下文（含过期/截断状态）",
        "method": "GET",
        "path": "/api/v1/ai/context/{context_id}",
        "permission": "ai.context.read",
        "auth_required": True,
        "parameters": {"context_id": {"type": "string"}},
    },
    {
        "name": "search_certified_queries",
        "description": "检索现行查询资产（certified 优先标注，禁止重写口径）",
        "method": "GET",
        "path": "/api/v1/queries",
        "permission": "query.view",
        "auth_required": True,
        "parameters": {"keyword": {"type": "string"}, "system_code": {"type": "string"}},
    },
    {
        "name": "explain_metric",
        "description": "解释指标口径：分子/分母/公式/版本/认证状态",
        "method": "GET",
        "path": "/api/v1/metrics/{metric_code}",
        "permission": "query.view",
        "auth_required": True,
        "parameters": {"metric_code": {"type": "string"}},
    },
    {
        "name": "execute_data_product",
        "description": "执行已发布数据产品（参数化、限流、禁止任意 SQL）",
        "method": "POST",
        "path": "/api/v1/data-products/{product_code}/execute",
        "permission": "query.run",
        "auth_required": True,
        "parameters": {"product_code": {"type": "string"}, "parameters": {"type": "object"}},
    },
    {
        "name": "validate_query_result",
        "description": "运行查询版本 G1-G3 验证并回传逐层证据",
        "method": "POST",
        "path": "/api/v1/queries/{query_code}/versions/{version}/validate",
        "permission": "query.create",
        "auth_required": True,
        "parameters": {"query_code": {"type": "string"}, "version": {"type": "integer"}},
    },
    {
        "name": "get_lineage_impact",
        "description": "精确 object_key 血缘影响（typed nodes/edges）",
        "method": "GET",
        "path": "/api/v1/lineage/impact",
        "permission": "asset.lineage.view",
        "auth_required": True,
        "parameters": {"object_key": {"type": "string"}, "table": {"type": "string"}},
    },
]


@router.get("/mcp/catalog", summary="126 P5 + 144 S6：MCP 工具目录（全部真实可执行）")
def mcp_catalog() -> ApiResponse[dict]:
    """Catalog where every declared tool maps to a real executable endpoint.

    144 A23: no tool is listed that returns "unsupported" — the two feedback
    feedback tools map to the plan144 S7 endpoints.
    """
    names = {
        "list_queries",
        "get_query",
        "list_metrics",
        "metric_board",
        "list_data_products",
        "execute_data_product",
        "list_source_capabilities",
        "search_tables",
        "get_table_schema",
        "get_relations",
        "sql_risk_scan",
        "list_value_domains",
    }
    tools = [t for t in AVAILABLE_TOOLS if t["name"] in names] + UNIFIED_TOOLS_144
    return ApiResponse(
        data={
            "name": "data-asset-governance",
            "version": "144-s6",
            "tools": tools,
            "tool_count": len(tools),
            "forbidden": ["arbitrary_sql", "dml", "ddl", "credential_export"],
        }
    )


@router.post("/sessions", summary="创建 AI 探索会话")
def start_session(req: SessionStartRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    import uuid
    key = str(uuid.uuid4())[:12]
    db.add(AiSession(session_key=key, purpose=req.purpose))
    db.commit()
    return ApiResponse(data={"session_key": key, "purpose": req.purpose})


@router.post("/tool-call", summary="记录工具调用（供审计）")
def log_tool_call(req: ToolCallLogRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    existing = db.scalar(select(AiSession).where(AiSession.session_key == req.session_key).limit(1))
    if not existing:
        db.add(AiSession(session_key=req.session_key, purpose="auto-created"))
        db.commit()
    _audit_tool_call(req.session_key, req.tool_name, req.request, req.response_summary, db)
    return ApiResponse(data={"logged": True})


@router.get("/tool-calls", summary="查询工具调用记录")
def list_tool_calls(
    session_key: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AiToolCall)
    if session_key:
        stmt = stmt.where(AiToolCall.session_key == session_key)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AiToolCall.called_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "session_key": r.session_key,
            "tool_name": r.tool_name,
            "request": r.request,
            "response_summary": r.response_summary,
            "called_at": r.called_at.isoformat() if r.called_at else None,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.post(
    "/propose-sql",
    summary="AI 提交 SQL/视图草稿（仅保存，不执行；149 附精确字段值域）",
    dependencies=[Depends(require_permission("ai.context.read"))],
)
def propose_sql(req: ProposeSqlRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    risk_flags = _scan_sql_risk(req.sql_text)
    # 149 P1c 补充注入：基于 144 sqlglot（app/services/sql_ast.py）提取字段附精确值域；
    # 解析失败显式返回 value_domains_not_injected_reason，禁止静默。
    from ...services.value_domain_service import value_domains_for_sql

    vd = value_domains_for_sql(db, req.sql_text, dialect="oracle")
    draft = ViewDraft(
        session_key=req.session_key,
        title=req.title or "未命名",
        sql_text=req.sql_text,
        purpose=req.purpose,
        risk_flags=risk_flags,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    if req.session_key:
        _audit_tool_call(req.session_key, "propose_sql", {"sql_len": len(req.sql_text)}, f"draft_id={draft.id}", db)

    return ApiResponse(
        data={
            "draft_id": draft.id,
            "title": draft.title,
            "risk_flags": risk_flags,
            "value_domains": vd["value_domains"],
            "value_domain_injection": {
                "injected": vd["injected"],
                "matched_count": len(vd["value_domains"]),
                "parser_version": vd["parser_version"],
                "value_domains_not_injected_reason": vd["not_injected_reason"],
            },
            "warning": "草稿已保存，需人工审核后执行",
        }
    )


def _scan_sql_risk(sql: str) -> dict:
    # B7：危险词判定用整词（词边界）匹配，复用 db_connectors 的公共实现，
    # 避免 UPDATED_AT/CREATED_BY 等列名被子串匹配误杀；启发式（LAB_RESULT/
    # 大表/无 WHERE）保持原口径不搬运连接器校验。
    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
    found = forbidden_keyword_hits(sql, keywords=dangerous)
    upper = sql.upper()
    flags: dict = {}
    if found:
        flags["dangerous_keywords"] = found
        flags["blocked"] = True
    if "LAB_RESULT" in upper and "TEST_NO" not in upper:
        flags["big_table_warning"] = "LAB_RESULT 约 1 亿行，建议加 TEST_NO 限定"
    if "INP_BILL_DETAIL" in upper:
        flags["big_table_warning"] = "INP_BILL_DETAIL 约 2.15 亿行，需严格限定患者/时间/住院号"
    if "ORDERS" in upper and "PATIENT_ID" not in upper and "VISIT_ID" not in upper:
        flags["big_table_warning"] = "ORDERS 约 4103 万行，建议加 PATIENT_ID+VISIT_ID 限定"
    if "FROM" in upper and "WHERE" not in upper:
        flags["no_filter_warning"] = "SQL 缺少 WHERE 条件，可能触发大表全扫"
    return flags


@router.get("/drafts", summary="查询草稿列表")
def list_drafts(
    session_key: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(ViewDraft)
    if session_key:
        stmt = stmt.where(ViewDraft.session_key == session_key)
    if status:
        stmt = stmt.where(ViewDraft.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ViewDraft.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": r.id,
            "session_key": r.session_key,
            "title": r.title,
            "sql_text": r.sql_text,
            "purpose": r.purpose,
            "status": r.status,
            "risk_flags": r.risk_flags,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "feedback": r.feedback,
        }
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


@router.patch("/drafts/{draft_id}", summary="审核草稿（通过/拒绝）", dependencies=[Depends(require_permission("asset.ai_draft.review"))])
def review_draft(
    draft_id: int,
    req: DraftReviewRequest, request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    draft = db.get(ViewDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")
    draft.status = req.status
    draft.reviewed_by = current_user
    draft.reviewed_at = datetime.now(timezone.utc)
    draft.feedback = req.feedback
    db.commit()
    return ApiResponse(data={"id": draft.id, "status": draft.status, "feedback": draft.feedback})


@router.post(
    "/drafts/{draft_id}/execute",
    summary="Execute approved SQL draft in read-only mode",
    dependencies=[Depends(require_permission("ai.sql.execute"))],
)
def execute_approved_draft(
    draft_id: int,
    req: DraftExecuteRequest, request: Request,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    current_user = get_current_user(request)
    from ...services import quality_sql_runner
    from ...services.quality_rule_engine import validate_sql_safety

    draft = db.get(ViewDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="SQL draft not found")
    if draft.status != "approved":
        raise HTTPException(status_code=400, detail="SQL draft must be approved before execution")

    risk_flags = _scan_sql_risk(draft.sql_text or "")
    if risk_flags.get("blocked"):
        raise HTTPException(
            status_code=400,
            detail={"message": "SQL risk scan blocked execution", "risk_flags": risk_flags},
        )

    validation = validate_sql_safety(draft.sql_text or "")
    if not validation.get("valid"):
        raise HTTPException(
            status_code=400,
            detail={"message": "SQL safety validation failed", "errors": validation.get("errors", [])},
        )

    result = quality_sql_runner.execute_quality_sql(
        rule_code=f"AI_DRAFT_{draft.id}",
        sql=draft.sql_text or "",
        source_code=req.source_code,
        max_rows=req.max_rows,
        sample_limit=req.sample_limit,
        db=db,
    )
    if result.get("status") != "success":
        # B3：失败回显统一走 sanitize_text，防止 note 携带连接串/路径外泄。
        sanitized = {**result, "note": sanitize_text(str(result.get("note") or ""), limit=500)}
        raise HTTPException(status_code=400, detail={"message": "SQL execution failed", "result": sanitized})

    draft.status = "executed"
    draft.feedback = (draft.feedback or "") + f"\nexecuted_by={current_user}; source_code={req.source_code}"
    db.add(GovernAuditLog(
        module="ai",
        entity_type="sql_draft",
        entity_ref=str(draft.id),
        action="execute_readonly_sql",
        before_data={"status": "approved", "source_code": req.source_code},
        after_data={
            "status": result.get("status"),
            "total_cnt": result.get("total_cnt"),
            "error_cnt": result.get("error_cnt"),
            "error_rate": result.get("error_rate"),
            "warnings": result.get("warnings", []),
        },
        operator=current_user,
        reason=draft.purpose,
    ))
    db.commit()

    if draft.session_key:
        _audit_tool_call(
            draft.session_key,
            "execute_approved_sql",
            {"draft_id": draft.id, "source_code": req.source_code, "max_rows": req.max_rows},
            f"status={result.get('status')}; total_cnt={result.get('total_cnt')}; error_cnt={result.get('error_cnt')}",
            db,
        )

    return ApiResponse(data={
        "draft_id": draft.id,
        "source_code": req.source_code,
        "status": "executed",
        "risk_flags": risk_flags,
        "warnings": result.get("warnings", []),
        "total_cnt": result.get("total_cnt", 0),
        "error_cnt": result.get("error_cnt", 0),
        "error_rate": result.get("error_rate", 0),
        "sample_data": result.get("sample_data", []),
    })


@router.get("/sessions", summary="查询 AI 会话列表")
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    stmt = select(AiSession)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AiSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {"id": r.id, "session_key": r.session_key, "purpose": r.purpose,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": items})


# --- 保留的原有接口 ---

@router.post(
    "/export-context",
    summary="导出脱敏 AI 上下文（表/字段/关系，不含患者数据）",
    dependencies=[Depends(require_permission("ai.context.read"))],
)
def export_context(req: ExportRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    if not req.tables:
        raise HTTPException(status_code=400, detail="请至少选择 1 张表")
    if len(req.tables) > MAX_EXPORT_TABLES:
        raise HTTPException(status_code=400, detail=f"单次最多导出 {MAX_EXPORT_TABLES} 张表")
    stmt = select(AssetTable).where(
        (AssetTable.schema_name + "." + AssetTable.table_name).in_(req.tables)
    )
    tables = db.scalars(stmt).all()
    names = [f"{t.schema_name}.{t.table_name}" for t in tables]

    columns: list[dict] = []
    if req.include_columns and names:
        conds = [
            (AssetColumn.schema_name == t.schema_name)
            & (AssetColumn.table_name == t.table_name)
            for t in tables
        ]
        cols_q = select(AssetColumn).where(or_(*conds)) if conds else select(AssetColumn)
        for c in db.scalars(
            cols_q.order_by(AssetColumn.schema_name, AssetColumn.table_name, AssetColumn.column_id)
        ):
            columns.append(
                {
                    "table": f"{c.schema_name}.{c.table_name}",
                    "column": c.column_name,
                    "data_type": c.data_type,
                    "length": c.length,
                    "nullable": c.nullable,
                    "comment": c.comment,
                }
            )

    relations: list[dict] = []
    if req.include_relations and names:
        rels_q = select(AssetRelation).where(
            AssetRelation.from_table.in_(names) | AssetRelation.to_table.in_(names)
        )
        for r in db.scalars(rels_q):
            relations.append(
                {
                    "rel_id": r.rel_id,
                    "from": r.from_table,
                    "to": r.to_table,
                    "from_columns": r.from_columns,
                    "to_columns": r.to_columns,
                    "join_condition": r.join_condition,
                    "cardinality": r.cardinality,
                    "confidence": r.confidence,
                    "validation_status": r.validation_status,
                }
            )

    data = {
        "safety": "脱敏元数据：仅含表名/字段/类型/注释/已确认关系，不含患者数据与真实样本值",
        "tables": [
            {
                "name": f"{t.schema_name}.{t.table_name}",
                "comment": t.comment,
                "column_count": t.column_count,
                "domain": t.domain,
                "row_count_stats": t.row_count_stats,
                "pk": t.pk,
            }
            for t in tables
        ],
        "columns": columns,
        "relations": relations,
    }
    return ApiResponse(data=data)


# ──────────────────────────────────────────────
# P10 新增：系统级别上下文 + SQL 风险扫描独立接口
# ──────────────────────────────────────────────

@router.get(
    "/system-context",
    summary="按系统导出 AI 上下文（P10 增强；149 附带全量 confirmed 值域+陷阱）",
    dependencies=[Depends(require_permission("ai.context.read"))],
)
def system_context(
    system_code: str = Query(..., description="系统编码"),
    max_tables: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...models.asset_system import AssetSystem
    from ...services.value_domain_service import confirmed_domains_for_injection
    sys = db.scalar(select(AssetSystem).where(AssetSystem.system_code == system_code))
    tables = db.scalars(
        select(AssetTable).where(AssetTable.system_code == system_code).limit(max_tables)
    ).all()
    total_tables = db.scalar(
        select(func.count()).select_from(AssetTable).where(AssetTable.system_code == system_code)
    ) or 0

    table_names = [f"{t.namespace_name or t.schema_name}.{t.table_name}" for t in tables]
    relations: list[dict] = []
    if table_names:
        rels = db.scalars(
            select(AssetRelation).where(
                AssetRelation.from_table.in_(table_names) | AssetRelation.to_table.in_(table_names)
            )
        ).all()
        relations = [
            {"from": r.from_table, "to": r.to_table, "join_condition": r.join_condition,
             "confidence": r.confidence, "validation_status": r.validation_status}
            for r in rels
        ]

    total_columns = db.scalar(
        select(func.count()).select_from(AssetColumn).where(AssetColumn.system_code == system_code)
    )
    if total_columns is None:
        # fallback when column.system_code sparse: sum column_count on tables
        total_columns = sum(int(t.column_count or 0) for t in tables)
    total_relations = db.scalar(select(func.count()).select_from(AssetRelation)) or 0
    if table_names:
        total_relations = len(relations)

    # 149 P1c 主注入路径：该系统全部 confirmed 值域+陷阱（全量，不依赖列级解析；
    # 未裁决冲突与 pending/deprecated 已在服务层过滤），逐条回带 version_no 供留痕。
    value_domains = confirmed_domains_for_injection(db, system_code=system_code)

    return ApiResponse(data={
        "system_code": system_code,
        "system_name_cn": sys.system_name_cn if sys else system_code,
        "total_tables": total_tables,
        "total_columns": int(total_columns or 0),
        "total_relations": int(total_relations or 0),
        "exported_tables": len(tables),
        "tables": [
            {
                "name": f"{t.namespace_name or t.schema_name}.{t.table_name}",
                "table_name_cn": t.table_name_cn,
                "domain": t.domain,
                "column_count": t.column_count,
                "pk": t.pk,
            }
            for t in tables
        ],
        "relations": relations,
        "value_domains": value_domains,
        "value_domain_count": len(value_domains),
        "safety": "只读元数据，不含患者数据",
    })


class ToolExecuteRequest(BaseModel):
    tool_name: str
    system_code: str | None = None
    params: dict | None = None


class SqlScanRequest(BaseModel):
    sql_text: str


class AiSqlGenerateRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    system_code: str = Field("DATA_CENTER", pattern="^DATA_CENTER$")
    selected_tables: list[str] = Field(..., min_length=1, max_length=20)


def _clean_generated_sql(text: str) -> str:
    visible = re.sub(r"<think>[\s\S]*?</think>", "", text or "", flags=re.I).strip()
    fenced = re.search(r"```(?:sql|oracle)?\s*([\s\S]*?)```", visible, flags=re.I)
    candidate = (fenced.group(1) if fenced else visible).strip()
    start = re.search(r"\b(?:SELECT|WITH)\b", candidate, flags=re.I)
    if not start:
        return ""
    candidate = candidate[start.start():].strip()
    candidate = re.split(r"\n\s*(?:说明|解释|注意)\s*[:：]", candidate, maxsplit=1)[0].strip()
    return candidate.rstrip(";").strip() + ";"


def _llm_was_truncated(reply) -> bool:
    choices = (getattr(reply, "raw", None) or {}).get("choices") or []
    return bool(choices and (choices[0] or {}).get("finish_reason") == "length")


@router.post(
    "/ai-sql/generate",
    summary="依据正式关系与值域生成 Oracle 只读 SQL（永不执行）",
    dependencies=[Depends(require_permission("ai.context.read"))],
)
def generate_ai_sql(req: AiSqlGenerateRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    from ...core.config import settings
    from ...services.ai_context_builder import build_ai_sql_context
    from ...services.hospital_llm_client import HospitalLlmClient, HospitalLlmError

    question = sanitize_text(req.question, limit=1000).strip()
    question = re.sub(r"<[^>]{0,200}>", "", question).strip()
    if len(question) < 2:
        raise HTTPException(422, "需求描述清洗后为空")
    prompt_prefix = (
        "你是 Oracle 11g 只读 SQL 编写助手。只能输出一条 SELECT 或只读 CTE，禁止 DDL/DML，"
        "明细必须用 ROWNUM <= N 限量；只可使用上下文给出的表、字段与正式 JOIN 三要素。"
        "不确定的值域不得猜测。不要解释，不要 Markdown 围栏，不得执行 SQL。\n"
        f"用户需求（已脱敏）：{question}\n上下文："
    )
    # 客户端限制的是完整 prompt，而非 context 单体。167 初版按 24 KiB 构建
    # context，再叠加提示词后可能超过生产 24000-byte 门禁。
    context_budget = settings.hospital_llm_max_payload_bytes - len(prompt_prefix.encode("utf-8")) - 256
    if context_budget < 1024:
        raise HTTPException(503, "院内模型上下文预算配置过小")
    try:
        context = build_ai_sql_context(
            db,
            system_code=req.system_code,
            selected_tables=req.selected_tables,
            max_payload_bytes=context_budget,
        )
    except ValueError as exc:
        raise HTTPException(422, "所选表上下文过大，请减少选表后重试") from exc
    context_json = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    prompt = prompt_prefix + context_json
    client = HospitalLlmClient()
    sql = ""
    reply = None
    try:
        for attempt in range(2):
            reply = client.complete(prompt + ("\n上次输出被截断或格式无效，请重新完整输出一条 SQL。" if attempt else ""), max_tokens=1800)
            sql = _clean_generated_sql(reply.text)
            if sql and not _llm_was_truncated(reply):
                break
    except HospitalLlmError as exc:
        raise HTTPException(503, f"院内模型暂不可用：{exc.error_class}") from exc
    if not sql or (reply is not None and _llm_was_truncated(reply)):
        raise HTTPException(502, "模型未返回完整 SQL")
    risk = _scan_sql_risk(sql)
    user = get_current_user(request)
    question_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()
    session_key = f"ai-sql:{user}"
    db.add(AiToolCall(
        session_key=session_key,
        tool_name="ai_sql_generate",
        request={
            "question_summary": question[:120], "question_sha256": question_hash,
            "system_code": req.system_code, "selected_tables": req.selected_tables,
            "context_digest": {"tables": len(context["tables"]), "relations": len(context["relations"]), "value_domains": len(context["value_domains"]), "payload_bytes": context["payload_bytes"]},
        },
        response_summary=f"generated={len(sql)} chars; blocked={bool(risk.get('blocked'))}",
    ))
    db.commit()
    return ApiResponse(data={
        "sql": sql, "risk": risk, "dialect": "oracle", "executed": False,
        "context_digest": {"tables": len(context["tables"]), "relations": len(context["relations"]), "value_domains": len(context["value_domains"]), "payload_bytes": context["payload_bytes"], "truncated": context["truncated"]},
    })


@router.get("/ai-sql/history", dependencies=[Depends(require_permission("ai.context.read"))])
def ai_sql_history(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)) -> ApiResponse[dict]:
    session_key = f"ai-sql:{get_current_user(request)}"
    stmt = select(AiToolCall).where(AiToolCall.session_key == session_key, AiToolCall.tool_name == "ai_sql_generate")
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AiToolCall.called_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return ApiResponse(data={"total": total, "page": page, "page_size": page_size, "items": [{"id": row.id, "request": row.request, "response_summary": row.response_summary, "called_at": row.called_at.isoformat() if row.called_at else None} for row in rows]})


# Tools that can be safely dispatched inline (metadata-only, no source DB write)
_INLINE_TOOL_DISPATCH = {
    "sql_risk_scan",
    "list_tools",
}


@router.post(
    "/tool-execute",
    summary="AI 工具执行代理（只读，真实分发或明确不支持）",
    # 161 P2-3（round-2 P8 裁决）：当前 AVAILABLE_TOOLS 全部为只读组包工具（无真实
    # 执行类工具），整端点挂只读码 ai.context.read，不再让执行码套读接口；未来新增
    # 真实执行类工具时，改挂 ai.sql.execute 并在函数体内按工具名分流。
    dependencies=[Depends(require_permission("ai.context.read"))],
)
def tool_execute(req: ToolExecuteRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    """Never return fake executed=True. Dispatch known read-only helpers or mark unsupported."""
    tool_names = [t["name"] for t in AVAILABLE_TOOLS]
    if req.tool_name not in tool_names:
        raise HTTPException(status_code=400, detail=f"未注册的工具: {req.tool_name}，可用: {tool_names}")

    params = req.params or {}
    result: dict
    executed = False
    status = "unsupported"

    if req.tool_name == "sql_risk_scan":
        sql_text = str(params.get("sql_text") or "")
        flags = _scan_sql_risk(sql_text)
        result = {
            "sql_length": len(sql_text),
            "risk_flags": flags,
            "safe_for_review": not flags.get("blocked", False),
        }
        executed = True
        status = "success"
    elif req.tool_name == "get_system_context" and req.system_code:
        # Reuse system_context logic via internal call pattern
        ctx = system_context(system_code=req.system_code, max_tables=int(params.get("max_tables") or 30), db=db)
        result = ctx.data if hasattr(ctx, "data") else ctx
        executed = True
        status = "success"
    elif req.tool_name in _INLINE_TOOL_DISPATCH:
        result = {"note": f"tool {req.tool_name} registered; use dedicated endpoint"}
        executed = False
        status = "unsupported"
    else:
        # Explicit unsupported — client must call the dedicated path from AVAILABLE_TOOLS
        tool_meta = next((t for t in AVAILABLE_TOOLS if t["name"] == req.tool_name), {})
        result = {
            "note": "tool-execute does not proxy arbitrary HTTP; call the dedicated path",
            "method": tool_meta.get("method"),
            "path": tool_meta.get("path"),
            "auth_required": tool_meta.get("auth_required", True),
        }
        executed = False
        status = "unsupported"

    db.add(GovernAuditLog(
        module="ai",
        entity_type="tool_execute",
        entity_ref=req.tool_name,
        action="execute" if executed else "unsupported",
        after_data={"params": params, "status": status, "executed": executed},
        operator=req.system_code,
    ))
    db.commit()
    return ApiResponse(data={
        "tool_name": req.tool_name,
        "executed": executed,
        "status": status,
        "result": result,
    })


@router.post("/sql-risk-scan", summary="SQL 风险扫描（P10 增强，独立接口）")
def sql_risk_scan(req: SqlScanRequest) -> ApiResponse[dict]:
    flags = _scan_sql_risk(req.sql_text)
    return ApiResponse(data={
        "sql_length": len(req.sql_text),
        "risk_flags": flags,
        "safe_for_review": not flags.get("blocked", False),
    })


# ===== 144 S6: unified AI context (ai-data-context/v1) =====


class ContextResolveRequest(BaseModel):
    question_summary: str | None = Field(None, max_length=500)
    system_code: str | None = None
    source_code: str | None = None
    business_domain: str | None = None
    max_objects: int = Field(200, ge=1, le=2000)


@router.post(
    "/context/resolve",
    summary="144 S6：按问题/系统/业务域构建统一上下文快照",
    dependencies=[Depends(require_permission("ai.context.read"))],
)
def resolve_context(
    req: ContextResolveRequest, request: Request, db: Session = Depends(get_db)
) -> ApiResponse[dict]:
    from ...services.ai_context_builder import build_context_snapshot

    try:
        doc = build_context_snapshot(
            db,
            question_summary=req.question_summary,
            system_code=req.system_code,
            source_code=req.source_code,
            business_domain=req.business_domain,
            max_objects=req.max_objects,
            include_sql=False,  # unified context never carries full SQL (144 §4.6)
            created_by=getattr(request.state, "user_identifier", None),
        )
        db.commit()
    except Exception as exc:  # sanitized error taxonomy only
        db.rollback()
        raise HTTPException(status_code=500, detail="上下文构建失败，请稍后重试") from exc
    return ApiResponse(data=doc)


@router.get(
    "/context/{context_id}",
    summary="144 S6：读取可复现上下文（含过期/截断状态）",
    dependencies=[Depends(require_permission("ai.context.read"))],
)
def get_context(
    context_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...services.ai_context_builder import load_context_snapshot

    doc = load_context_snapshot(db, context_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"context 不存在: {context_id}")
    return ApiResponse(data=doc)
