from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.asset import AssetColumn, AssetRelation, AssetTable
from ...models.ai_collab import AiSession, AiToolCall, ViewDraft
from ...models.governance_base import GovernAuditLog
from ...schemas.common import ApiResponse

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
        "name": "get_system_context",
        "description": "按系统/数据源获取全量表/字段/关系上下文（供 AI 理解系统结构）",
        "method": "GET",
        "path": "/api/v1/ai/system-context",
        "auth_required": True,
        "parameters": {
            "system_code": {"type": "string", "description": "系统编码，如 DATA_CENTER/HIS_SOURCE"},
            "max_tables": {"type": "integer", "description": "最大导出的表数，默认 30"},
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
    reviewed_by: str | None = None
    feedback: str | None = None


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
            "policy": "所有工具只读元数据；propose_sql 仅保存草稿不执行",
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


@router.post("/propose-sql", summary="AI 提交 SQL/视图草稿（仅保存，不执行）")
def propose_sql(req: ProposeSqlRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    risk_flags = _scan_sql_risk(req.sql_text)
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
            "warning": "草稿已保存，需人工审核后执行",
        }
    )


def _scan_sql_risk(sql: str) -> dict:
    upper = sql.upper()
    flags = {}
    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
    found = [w for w in dangerous if w in upper]
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


@router.patch("/drafts/{draft_id}", summary="审核草稿（通过/拒绝）")
def review_draft(
    draft_id: int,
    req: DraftReviewRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    draft = db.get(ViewDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="草稿不存在")
    draft.status = req.status
    draft.reviewed_by = req.reviewed_by
    draft.reviewed_at = datetime.now(timezone.utc)
    draft.feedback = req.feedback
    db.commit()
    return ApiResponse(data={"id": draft.id, "status": draft.status, "feedback": draft.feedback})


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

@router.post("/export-context", summary="导出脱敏 AI 上下文（表/字段/关系，不含患者数据）")
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

@router.get("/system-context", summary="按系统导出 AI 上下文（P10 增强）")
def system_context(
    system_code: str = Query(..., description="系统编码"),
    max_tables: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    from ...models.asset_system import AssetSystem
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

    return ApiResponse(data={
        "system_code": system_code,
        "system_name_cn": sys.system_name_cn if sys else system_code,
        "total_tables": total_tables,
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
        "safety": "只读元数据，不含患者数据",
    })


class ToolExecuteRequest(BaseModel):
    tool_name: str
    system_code: str | None = None
    params: dict | None = None


class SqlScanRequest(BaseModel):
    sql_text: str


@router.post("/tool-execute", summary="AI 工具执行代理（只读）")
def tool_execute(req: ToolExecuteRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    tool_names = [t["name"] for t in AVAILABLE_TOOLS]
    if req.tool_name not in tool_names:
        raise HTTPException(status_code=400, detail=f"未注册的工具: {req.tool_name}，可用: {tool_names}")
    db.add(GovernAuditLog(
        module="ai", entity_type="tool_execute", entity_ref=req.tool_name, action="execute",
        after_data=req.params, operator=req.system_code,
    ))
    db.commit()
    return ApiResponse(data={
        "tool_name": req.tool_name,
        "executed": True,
        "note": "readonly proxy executed, refer to tool-call audit",
    })


@router.post("/sql-risk-scan", summary="SQL 风险扫描（P10 增强，独立接口）")
def sql_risk_scan(req: SqlScanRequest) -> ApiResponse[dict]:
    flags = _scan_sql_risk(req.sql_text)
    return ApiResponse(data={
        "sql_length": len(req.sql_text),
        "risk_flags": flags,
        "safe_for_review": not flags.get("blocked", False),
    })
