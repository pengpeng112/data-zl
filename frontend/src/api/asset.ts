import { http } from "@/utils/http";

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface SummaryData {
  tables: number;
  columns: number;
  relations: number;
  domains: number;
}

export interface PageData<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

export interface TableBrief {
  id?: number;
  system_code?: string | null;
  source_code?: string | null;
  namespace_name?: string | null;
  schema_name: string;
  table_name: string;
  table_name_cn?: string | null;
  table_role?: string | null;
  comment: string | null;
  column_count: number | null;
  domain: string | null;
  source: string | null;
}

export interface TableDetail {
  schema_name: string;
  table_name: string;
  table_name_cn?: string | null;
  table_role?: string | null;
  comment: string | null;
  column_count: number | null;
  column_count_actual: number | null;
  domain: string | null;
  source: string | null;
  row_count_stats: string | null;
  grain: string | null;
  pk: string | null;
  confidence: string | null;
  note: string | null;
  relation_count: number | null;
}

export interface ColumnInfo {
  id?: number;
  system_code?: string | null;
  source_code?: string | null;
  namespace_name?: string | null;
  schema_name?: string | null;
  table_name?: string | null;
  column_id: number | null;
  column_name: string | null;
  column_name_cn?: string | null;
  business_desc_cn?: string | null;
  value_desc_cn?: string | null;
  data_type: string | null;
  length: number | null;
  nullable: string | null;
  comment: string | null;
}

export interface RelationInfo {
  rel_id: number | null;
  domain: string | null;
  from_table: string | null;
  from_columns: string | null;
  to_table: string | null;
  to_columns: string | null;
  join_condition: string | null;
  cardinality: string | null;
  confidence: string | null;
  validation_level: string | null;
  validation_status: string | null;
  validation_metrics: string | null;
  note: string | null;
  validation_note: string | null;
}

export interface HopInfo {
  from: string;
  to: string;
  rel_id: number | null;
  join_condition: string | null;
  cardinality: string | null;
  confidence: string | null;
  validation_level: string | null;
  validation_status: string | null;
  validation_metrics: string | null;
  note: string | null;
  validation_note: string | null;
  from_columns: string | null;
  to_columns: string | null;
}

export interface PathResult {
  from: string;
  to: string;
  path: string[] | null;
  hops: HopInfo[];
}

export interface ExportContext {
  safety: string;
  tables: any[];
  columns: any[];
  relations: any[];
}

/** 资产总览 */
export const getSummary = () => {
  return http.get<ApiResponse<SummaryData>, object>("/api/v1/summary");
};

/** 表清单 */
export const getTables = (params: {
  keyword?: string;
  domain?: string;
  system_code?: string;
  source_code?: string;
  schema_name?: string;
  page?: number;
  page_size?: number;
}) => {
  return http.get<ApiResponse<PageData<TableBrief>>, object>("/api/v1/tables", {
    params
  });
};

/** 表详情 */
export const getTableDetail = (schema: string, table: string) => {
  return http.get<ApiResponse<TableDetail>, object>(
    `/api/v1/tables/${schema}/${table}`
  );
};

/** 表字段 */
export const getTableColumns = (schema: string, table: string) => {
  return http.get<ApiResponse<ColumnInfo[]>, object>(
    `/api/v1/tables/${schema}/${table}/columns`
  );
};

/** 表关系 */
export const getTableRelations = (schema: string, table: string) => {
  return http.get<ApiResponse<RelationInfo[]>, object>(
    `/api/v1/tables/${schema}/${table}/relations`
  );
};

/** 字段搜索 */
export const searchColumns = (params: {
  keyword: string;
  page?: number;
  page_size?: number;
}) => {
  return http.get<ApiResponse<PageData<ColumnInfo>>, object>(
    "/api/v1/columns/search",
    { params }
  );
};

/** 关系路径 */
export const getRelationPath = (fromTable: string, toTable: string) => {
  return http.get<ApiResponse<PathResult>, object>("/api/v1/relations/path", {
    params: { from: fromTable, to: toTable }
  });
};

/** AI 上下文导出 */
export const exportContext = (data: {
  tables?: string[];
  include_relations?: boolean;
  include_columns?: boolean;
}) => {
  return http.post<ApiResponse<ExportContext>, object>(
    "/api/v1/ai/export-context",
    { data }
  );
};

export interface AssetTreeTable {
  id: number;
  table_name: string;
  table_name_cn?: string | null;
  column_count?: number | null;
  domain?: string | null;
}

export interface AssetTreeSchema {
  namespace: string;
  table_count: number;
  tables: AssetTreeTable[];
}

export interface AssetTreeNode {
  source_code: string;
  source_name_cn: string;
  system_code: string;
  table_count: number;
  schemas: AssetTreeSchema[];
}

export const getAssetTree = (params?: { system_code?: string }) => {
  return http.get<ApiResponse<AssetTreeNode[]>, object>("/api/v1/assets/tree", {
    params
  });
};
// --- P1.5 关系图谱 ---

export interface GraphNode {
  id: string;
  label: string;
  schema_name?: string | null;
  table_name?: string | null;
  domain?: string | null;
  column_count?: number | null;
  source?: string | null;
  category?: string | null;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string | null;
  relation_type?: string | null;
  rel_id?: number | null;
  join_condition?: string | null;
  from_columns?: string | null;
  to_columns?: string | null;
  cardinality?: string | null;
  confidence?: string | null;
  validation_level?: string | null;
  validation_status?: string | null;
  validation_metrics?: string | null;
  note?: string | null;
  validation_note?: string | null;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphOptionsData {
  schemas: string[];
  domains: string[];
  validation_statuses: string[];
  confidences: string[];
  relation_types: string[];
}

export const getGraph = (params: {
  schema?: string;
  domain?: string;
  validation_status?: string;
  confidence?: string;
  keyword?: string;
  limit?: number;
  include_candidates?: boolean;
  include_dependencies?: boolean;
}) => {
  return http.get<ApiResponse<GraphData>, object>("/api/v1/graph", {
    params
  });
};

export const getGraphNeighbors = (params: {
  table: string;
  depth?: number;
  direction?: "in" | "out" | "both";
  limit?: number;
}) => {
  return http.get<ApiResponse<GraphData>, object>("/api/v1/graph/neighbors", {
    params
  });
};

export const getGraphOptions = () => {
  return http.get<ApiResponse<GraphOptionsData>, object>(
    "/api/v1/graph/options"
  );
};

// --- P2 血缘与候选关系 ---

export interface ViewDependencyItem {
  id: number;
  view_name: string;
  referenced_schema: string | null;
  referenced_table: string;
  alias: string | null;
  source_file: string | null;
}

export interface ImpactResult {
  table: string;
  referencing_views: string[];
  dependent_relations: string[];
  total_views: number;
  total_relations: number;
}

export interface CandidateRelationItem {
  id: number;
  from_table: string | null;
  from_columns: string | null;
  to_table: string | null;
  to_columns: string | null;
  join_condition: string | null;
  source_view: string | null;
  source_file: string | null;
  confidence: string | null;
  status: string | null;
  domain: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  note: string | null;
  created_at: string | null;
}

export const getViewDependencies = (params: {
  view?: string;
  referenced_table?: string;
  schema?: string;
  page?: number;
  page_size?: number;
}) => {
  return http.get<ApiResponse<PageData<ViewDependencyItem>>, object>(
    "/api/v1/lineage/views",
    { params }
  );
};

export const getImpactAnalysis = (table: string) => {
  return http.get<ApiResponse<ImpactResult>, object>("/api/v1/lineage/impact", {
    params: { table }
  });
};

export const getCandidates = (params: {
  page?: number;
  page_size?: number;
  status?: string;
  keyword?: string;
  source_view?: string;
}) => {
  return http.get<ApiResponse<PageData<CandidateRelationItem>>, object>(
    "/api/v1/candidates",
    { params }
  );
};

export const promoteCandidate = (
  candidateId: number,
  data?: {
    reviewer?: string;
    note?: string;
    domain?: string;
    cardinality?: string;
  }
) => {
  return http.post<ApiResponse<any>, object>(
    `/api/v1/candidates/${candidateId}/promote`,
    { data }
  );
};

export const rejectCandidate = (
  candidateId: number,
  data?: {
    reviewer?: string;
    note?: string;
  }
) => {
  return http.post<ApiResponse<any>, object>(
    `/api/v1/candidates/${candidateId}/reject`,
    { data }
  );
};

// --- P3 数据质量 ---

export interface QualityRuleItem {
  id: number;
  rule_code: string;
  rule_type: string | null;
  target_type: string | null;
  execution_mode: string | null;
  description: string | null;
  threshold_config: any;
  enabled: boolean | null;
}

export interface QualityFindingItem {
  id: number;
  rule_code: string | null;
  target_type: string | null;
  target_ref: string | null;
  severity: string | null;
  status: string | null;
  metric_value: string | null;
  detail: any;
  found_at: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  note: string | null;
}

export interface QualityCheckRunItem {
  id: number;
  started_at: string | null;
  finished_at: string | null;
  triggered_by: string | null;
  total_rules: number | null;
  total_findings: number | null;
  status: string | null;
}

export interface QualitySummary {
  total_findings: number;
  open_count: number;
  acknowledged_count: number;
  resolved_count: number;
  critical_count: number;
  major_count: number;
  minor_count: number;
  info_count: number;
  top_tables: { table: string; count: number }[];
}

export const getQualityRules = () => {
  return http.get<ApiResponse<QualityRuleItem[]>, object>(
    "/api/v1/quality/rules"
  );
};

export const runQualityCheck = (ruleCodes?: string[]) => {
  let url = "/api/v1/quality/checks/run";
  if (ruleCodes && ruleCodes.length > 0) {
    url += "?" + ruleCodes.map(c => `rule_codes=${c}`).join("&");
  }
  return http.post<ApiResponse<any>, object>(url);
};

export const getQualityCheckRuns = (params?: {
  page?: number;
  page_size?: number;
}) => {
  return http.get<ApiResponse<PageData<QualityCheckRunItem>>, object>(
    "/api/v1/quality/checks/runs",
    { params }
  );
};

export const getQualityFindings = (params: {
  page?: number;
  page_size?: number;
  severity?: string;
  status?: string;
  rule_code?: string;
  keyword?: string;
}) => {
  return http.get<ApiResponse<PageData<QualityFindingItem>>, object>(
    "/api/v1/quality/findings",
    { params }
  );
};

export const updateQualityFinding = (
  findingId: number,
  data?: { status?: string; resolved_by?: string; note?: string }
) => {
  return http.patch<ApiResponse<QualityFindingItem>, object>(
    `/api/v1/quality/findings/${findingId}`,
    { data }
  );
};

export const getQualitySummary = () => {
  return http.get<ApiResponse<QualitySummary>, object>(
    "/api/v1/quality/summary"
  );
};

// --- P4A AI 工具与草稿 ---

export interface AiToolDef {
  name: string;
  description: string;
  parameters: Record<string, any>;
}

export interface AiToolsResponse {
  platform: string;
  tools: AiToolDef[];
  policy: string;
}

export interface AiSessionItem {
  id: number;
  session_key: string;
  purpose: string | null;
  created_at: string | null;
}

export interface AiToolCallItem {
  id: number;
  session_key: string;
  tool_name: string;
  request: any;
  response_summary: string | null;
  called_at: string | null;
}

export interface ViewDraftItem {
  id: number;
  session_key: string | null;
  title: string | null;
  sql_text: string | null;
  purpose: string | null;
  status: string | null;
  risk_flags: any;
  created_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  feedback: string | null;
}

export const getAiTools = () => {
  return http.get<ApiResponse<AiToolsResponse>, object>("/api/v1/ai/tools");
};

export const startAiSession = (purpose?: string) => {
  return http.post<ApiResponse<any>, object>("/api/v1/ai/sessions", {
    data: { purpose }
  });
};

export const logToolCall = (data: {
  session_key: string;
  tool_name: string;
  request?: any;
  response_summary?: string;
}) => {
  return http.post<ApiResponse<any>, object>("/api/v1/ai/tool-call", { data });
};

export const getToolCalls = (params?: {
  session_key?: string;
  page?: number;
  page_size?: number;
}) => {
  return http.get<ApiResponse<PageData<AiToolCallItem>>, object>(
    "/api/v1/ai/tool-calls",
    { params }
  );
};

export const getDrafts = (params?: {
  session_key?: string;
  status?: string;
  page?: number;
  page_size?: number;
}) => {
  return http.get<ApiResponse<PageData<ViewDraftItem>>, object>(
    "/api/v1/ai/drafts",
    { params }
  );
};

export const reviewDraft = (
  draftId: number,
  data?: { status: string; reviewed_by?: string; feedback?: string }
) => {
  return http.patch<ApiResponse<any>, object>(`/api/v1/ai/drafts/${draftId}`, {
    data
  });
};

export const getAiSessions = (params?: {
  page?: number;
  page_size?: number;
}) => {
  return http.get<ApiResponse<PageData<AiSessionItem>>, object>(
    "/api/v1/ai/sessions",
    { params }
  );
};
