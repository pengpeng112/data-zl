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

export interface DashboardNamedCount {
  name: string;
  count: number;
}

export interface DashboardActivity {
  title: string;
  desc: string;
  status: string;
  tone: string;
  href?: string;
}

export interface DashboardSummary {
  generated_at?: string;
  assets: SummaryData;
  systems: number;
  sources_enabled: number;
  sources_total: number;
  persons: number;
  departments: number;
  identity_diffs_open: number;
  quality_rules: number;
  quality_findings_open: number;
  quality_last_run: {
    id: number;
    status?: string | null;
    total_rules?: number | null;
    total_findings?: number | null;
    pass_rate?: number | null;
    triggered_by?: string | null;
    finished_at?: string | null;
  } | null;
  metadata_snapshots: number;
  domain_top: DashboardNamedCount[];
  relation_by_confidence: DashboardNamedCount[];
  schema_top: DashboardNamedCount[];
  quality_run_trend: {
    id: number;
    label: string;
    findings: number;
    pass_rate: number;
  }[];
  activities: DashboardActivity[];
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
  name_cn_source?: string | null;
  name_cn_status?: string | null;
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
  name_cn_source?: string | null;
  name_cn_status?: string | null;
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

export interface RelationListItem extends RelationInfo {
  id: number;
  rel_id: number | null;
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

/** 首页指挥中心聚合指标 */
export const getDashboardSummary = () => {
  return http.get<ApiResponse<DashboardSummary>, object>(
    "/api/v1/dashboard/summary"
  );
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
  name_cn_source?: string | null;
  name_cn_status?: string | null;
  column_count?: number | null;
  domain?: string | null;
}

export interface AssetTreeSchema {
  namespace: string;
  source_code?: string | null;
  namespace_name_cn?: string | null;
  name_cn_source?: string | null;
  name_cn_status?: string | null;
  table_count: number;
  tables: AssetTreeTable[];
  tables_loaded?: boolean;
}

export interface AssetTreeNode {
  source_code: string;
  physical_source_code?: string | null;
  source_name_cn: string;
  connection_endpoint?: string | null;
  system_code: string;
  system_name_cn?: string | null;
  /** plan 90: 不再使用人为大类；目录异常时为 catalog_anomaly */
  system_category?: string | null;
  system_category_cn?: string | null;
  /** 连接标识 / 展示 */
  source_system?: string | null;
  source_system_cn?: string | null;
  table_count: number;
  schemas: AssetTreeSchema[];
  tables_embedded?: boolean;
  empty_catalog_hint?: string | null;
}

export const getAssetTree = (params?: {
  system_code?: string;
  system_category?: string;
  /** 默认 false：仅骨架+schema 计数，表走 getAssetTreeTables */
  include_tables?: boolean;
  max_tables_per_schema?: number;
}) => {
  return http.get<ApiResponse<AssetTreeNode[]>, object>("/api/v1/assets/tree", {
    params
  });
};

/** 懒加载某 schema 下的表 */
export const getAssetTreeTables = (params: {
  source_code: string;
  schema_name?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
}) => {
  return http.get<
    ApiResponse<{
      source_code: string;
      schema_name: string;
      total: number;
      page: number;
      page_size: number;
      items: AssetTreeTable[];
    }>,
    object
  >("/api/v1/assets/tree/tables", { params });
};

/** 按表名搜索（返回路径） */
export const searchAssetTree = (params: {
  keyword: string;
  system_category?: string;
  limit?: number;
}) => {
  return http.get<
    ApiResponse<{ keyword: string; total: number; items: AssetTreeTable[] }>,
    object
  >("/api/v1/assets/tree/search", { params });
};

// --- 业务系统与数据连接 ---

export interface AssetSystemItem {
  id: number;
  system_code: string;
  system_name_cn: string;
  system_type?: string | null;
  status?: string | null;
  target_host?: string | null;
  connection_count?: number;
  table_count?: number;
  created_at?: string | null;
}

export interface AssetSourceItem {
  id?: number;
  system_code: string;
  source_code: string;
  source_name_cn: string;
  db_type?: string | null;
  db_type_label?: string | null;
  target_host?: string | null;
  host_masked?: string | null;
  port?: number | null;
  service_mode?: string | null;
  service_name?: string | null;
  database_name?: string | null;
  default_schema?: string | null;
  environment?: string | null;
  collect_mode?: string | null;
  write_policy?: string | null;
  enabled?: boolean;
  last_check_status?: string | null;
  credential_configured?: boolean;
  credential_status?: string | null;
  credential_username_masked?: string | null;
  write_credential_configured?: boolean;
  write_credential_status?: string | null;
  write_username_masked?: string | null;
  supports_medical_dict_push?: boolean;
  is_writeable?: boolean;
  display_order?: number;
}

export interface DbTypeMeta {
  db_type: string;
  label: string;
  default_port: number;
  service_modes: string[];
  requires_database_name: boolean;
  requires_service_or_sid: boolean;
}

export const listSystems = (params?: { include_merged?: boolean }) =>
  http.request<ApiResponse<AssetSystemItem[]>>("get", "/api/v1/systems", { params });

export const getSystemDetail = (systemCode: string) =>
  http.request<ApiResponse<any>>("get", `/api/v1/systems/${systemCode}/detail`);

export const upsertSystem = (data: Record<string, any>) =>
  http.request<ApiResponse<any>>("put", "/api/v1/systems", { data });

export const createSystemWithConnections = (data: Record<string, any>) =>
  http.request<ApiResponse<any>>("post", "/api/v1/systems-with-connections", { data });

export const listSources = (params?: { system_code?: string }) =>
  http.request<ApiResponse<AssetSourceItem[]>>("get", "/api/v1/sources", { params });

export const upsertSource = (data: Record<string, any>) =>
  http.request<ApiResponse<any>>("put", "/api/v1/sources", { data });

export const addSystemConnection = (systemCode: string, data: Record<string, any>) =>
  http.request<ApiResponse<any>>("post", `/api/v1/systems/${systemCode}/connections`, { data });

export const checkSource = (sourceCode: string) =>
  http.request<ApiResponse<any>>("post", `/api/v1/sources/${sourceCode}/check`);

export const updateSourceCredential = (
  sourceCode: string,
  data: {
    username: string;
    password: string;
    purpose?: "readonly" | "write";
    write_policy?: string;
  }
) => http.request<ApiResponse<any>>("put", `/api/v1/sources/${sourceCode}/credential`, { data });

export const clearSourceCredential = (
  sourceCode: string,
  params?: { purpose?: "readonly" | "write" }
) =>
  http.request<ApiResponse<any>>("delete", `/api/v1/sources/${sourceCode}/credential`, {
    params
  });

export const patchSource = (sourceCode: string, data: Record<string, any>) =>
  http.request<ApiResponse<any>>("patch", `/api/v1/sources/${sourceCode}`, { data });

export const disableSource = (sourceCode: string) =>
  http.request<ApiResponse<any>>("delete", `/api/v1/sources/${sourceCode}`);

export const softDisableSystem = (systemCode: string) =>
  http.request<ApiResponse<any>>("delete", `/api/v1/systems/${systemCode}`);

export const listDbTypes = () =>
  http.request<ApiResponse<DbTypeMeta[]>>("get", "/api/v1/db-types");

export const listConnections = (params?: { include_aliases?: boolean }) =>
  http.request<ApiResponse<AssetSourceItem[]>>("get", "/api/v1/connections", { params });

export const getConnection = (id: number) =>
  http.request<ApiResponse<any>>("get", `/api/v1/connections/${id}`);

export const testConnectionDraft = (data: Record<string, any>) =>
  http.request<ApiResponse<any>>("post", "/api/v1/connections/test-draft", { data });

export const testSavedConnection = (id: number) =>
  http.request<ApiResponse<any>>("post", `/api/v1/connections/${id}/test`);

export const listConnectionTargets = () =>
  http.request<ApiResponse<any[]>>("get", "/api/v1/connections-targets");

// --- P1.5 关系图谱 ---

export interface GraphNode {
  id: string;
  label: string;
  physical_key?: string | null;
  display_id?: string | null;
  system_code?: string | null;
  source_code?: string | null;
  namespace_name?: string | null;
  schema_name?: string | null;
  table_name?: string | null;
  table_name_cn?: string | null;
  table_role?: string | null;
  domain?: string | null;
  business_domain?: string | null;
  column_count?: number | null;
  source?: string | null;
  category?: string | null;
  row_count_stats?: string | null;
  grain?: string | null;
  pk?: string | null;
  confidence?: string | null;
  include_status?: string | null;
  review_status?: string | null;
  note?: string | null;
  object_type?: string | null;
  technical_name?: string | null;
  metadata_match?: string | null;
  asset_count?: number | null;
  child_count?: number | null;
  path?: string | null;
  is_aggregate?: boolean;
  /** 字段层只读契约：字段节点挂在 parent 表下。 */
  column_name?: string | null;
  column_name_cn?: string | null;
  data_type?: string | null;
  nullable?: boolean | string | null;
  is_primary_key?: boolean | null;
  is_relation_key?: boolean | null;
}

export interface GraphFieldMapping {
  from_column?: string | null;
  from_column_name_cn?: string | null;
  to_column?: string | null;
  to_column_name_cn?: string | null;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  display_source?: string | null;
  display_target?: string | null;
  from_system_code?: string | null;
  from_source_code?: string | null;
  from_schema_name?: string | null;
  from_table_name?: string | null;
  from_table_name_cn?: string | null;
  from_table_role?: string | null;
  from_include_status?: string | null;
  to_system_code?: string | null;
  to_source_code?: string | null;
  to_schema_name?: string | null;
  to_table_name?: string | null;
  to_table_name_cn?: string | null;
  to_table_role?: string | null;
  to_include_status?: string | null;
  label?: string | null;
  relation_type?: string | null;
  relation_layer?: string | null;
  db_id?: number | null;
  rel_id?: number | null;
  join_condition?: string | null;
  from_columns?: string | null;
  to_columns?: string | null;
  field_mappings?: GraphFieldMapping[];
  cardinality?: string | null;
  business_domain?: string | null;
  confidence?: string | null;
  validation_level?: string | null;
  validation_status?: string | null;
  validation_metrics?: string | null;
  is_deferred?: boolean | null;
  deferred_reason?: string | null;
  note?: string | null;
  validation_note?: string | null;
}

export interface GraphMeta {
  total_relations: number;
  matched_relations: number;
  returned_relations: number;
  truncated: boolean;
  unresolved_endpoints?: number;
  filters?: Record<string, unknown>;
  data_version?: string | null;
  backend_build_id?: string | null;
  query_ms?: number | null;
  matched_total?: number | null;
  returned_nodes?: number | null;
  estimated_total?: number | null;
  enrichment?: Record<string, number>;
  warnings?: string[];
  center_physical_key?: string | null;
  direction_semantics?: string | null;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta?: GraphMeta | null;
}

export interface GraphViewMode {
  code: string;
  label: string;
  description?: string | null;
  group_by: "system" | "source" | "schema" | "domain";
  layout_mode: "layered" | "grouped" | "radial" | "hierarchy";
  confidence?: string | null;
  validation_status?: string | null;
  include_candidates: boolean;
  include_dependencies: boolean;
  show_review_layer: boolean;
  requires_table: boolean;
  deprecated?: boolean;
}

export interface GraphOptionItem {
  value: string;
  label: string;
  count?: number;
  disabled?: boolean;
}

export interface GraphOptionsData {
  systems: string[];
  sources: string[];
  schemas: string[];
  domains: string[];
  system_options?: GraphOptionItem[];
  source_options?: GraphOptionItem[];
  schema_options?: GraphOptionItem[];
  domain_options?: GraphOptionItem[];
  validation_statuses: string[];
  confidences: string[];
  relation_types: string[];
  view_modes: GraphViewMode[];
  default_mode?: string | null;
  backend_build_id?: string | null;
}

export interface GraphOverviewResponse {
  level: "system" | "source" | "schema" | "object" | "field";
  next_level?: "system" | "source" | "schema" | "object" | "field" | null;
  selected_path: Record<string, string>;
  data: GraphData;
}

export interface GraphFilterOption {
  value: string;
  label: string;
  count: number;
  disabled?: boolean;
}

export interface GraphFilterOptionsData {
  selected_path: Record<string, string>;
  next_level: "system" | "source" | "schema" | "object";
  items: GraphFilterOption[];
  business_domains: GraphFilterOption[];
  object_types: GraphFilterOption[];
}

export interface GraphTableSearchItem {
  physical_key: string;
  display_name: string;
  technical_name: string;
  system_code?: string | null;
  source_code?: string | null;
  namespace_name?: string | null;
  schema_name?: string | null;
  table_name?: string | null;
  object_type: string;
  business_domain?: string | null;
  column_count?: number | null;
  ambiguous?: boolean;
}

export const getGraph = (params: {
  system_code?: string;
  source_code?: string;
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
  table?: string;
  physical_key?: string;
  center_physical_key?: string;
  system_code?: string;
  source_code?: string;
  schema?: string;
  depth?: number;
  direction?: "in" | "out" | "both";
  limit?: number;
}) => {
  return http.get<ApiResponse<GraphData>, object>("/api/v1/graph/neighbors", {
    params
  });
};

export const getGraphOverview = (params?: {
  level?: "system" | "source" | "schema" | "object" | "field";
  parent_physical_key?: string;
  system_code?: string;
  source_code?: string;
  schema?: string;
  domain?: string;
  object_type?: "table" | "view";
  limit?: number;
}) => {
  return http.get<ApiResponse<GraphOverviewResponse>, object>("/api/v1/graph/overview", { params });
};

export const getGraphFilterOptions = (params?: {
  system_code?: string;
  source_code?: string;
  schema?: string;
  next_level?: "system" | "source" | "schema" | "object";
}) => {
  return http.get<ApiResponse<GraphFilterOptionsData>, object>("/api/v1/graph/filter-options", { params });
};

export const searchGraphTables = (params: {
  q: string;
  system_code?: string;
  source_code?: string;
  schema?: string;
  limit?: number;
}) => {
  return http.get<ApiResponse<{ items: GraphTableSearchItem[]; total: number; query: string }>, object>("/api/v1/graph/tables/search", { params });
};

export const getGraphEdgeDetail = (edgeId: string) => {
  return http.get<ApiResponse<GraphEdge>, object>(
    `/api/v1/graph/edges/${encodeURIComponent(edgeId)}`
  );
};

export const getGraphOptions = () => {
  return http.get<ApiResponse<GraphOptionsData>, object>(
    "/api/v1/graph/options"
  );
};

export const getGraphDiagnostics = () => {
  return http.get<ApiResponse<{ table_count: number; relation_count: number; warnings: string[]; healthy: boolean }>, object>("/api/v1/graph/diagnostics");
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
  system_code?: string | null;
  source_code?: string | null;
  namespace_name?: string | null;
  schema_name?: string | null;
  table_name?: string | null;
  column_name?: string | null;
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
  total_records?: number | null;
  error_records?: number | null;
  pass_rate?: number | null;
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
  run_id?: number;
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

// --- S5 Dify AI 质控工作台（服务端只读组包；浏览器永不接触 Key） ---
export interface AiQualityStatus {
  enabled: boolean;
  configured: boolean;
  reachable?: boolean | null;
  workflow_name?: string | null;
  workflow?: string | null;
  prompt_version?: string | null;
  schema_version?: string | null;
  last_success_at?: string | null;
  timeout_seconds?: number | null;
  quota_state?: string | null;
  message?: string | null;
}

export interface AiQualityPreview {
  request_id: string;
  task_type: "finding" | "finding_batch" | "run_summary";
  finding_ids?: number[];
  run_id?: number | null;
  fields?: string[];
  item_count?: number;
  payload_bytes?: number;
  input_digest: string;
  redacted_count?: number;
  dropped_count?: number;
  dropped_fields?: string[];
  warnings?: string[];
  payload_json?: string;
}

export type AiQualityJobStatus = "queued" | "running" | "succeeded" | "failed" | "unknown" | "blocked";

export interface AiQualityJob {
  id: number | string;
  request_id?: string | null;
  task_type: "finding" | "finding_batch" | "run_summary";
  status: AiQualityJobStatus;
  finding_ids?: number[];
  run_id?: number | null;
  input_digest?: string | null;
  prompt_version?: string | null;
  dify_run_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  token_usage?: Record<string, unknown> | null;
  error_class?: string | null;
  error_message?: string | null;
  result?: AiQualityResultItem | null;
}

export interface AiQualityResult {
  schema_version?: string;
  request_id?: string;
  input_digest?: string;
  summary: string;
  risk_level?: "critical" | "high" | "medium" | "low" | "unknown";
  root_causes?: { title: string; reason?: string; confidence?: number; evidence_finding_ids?: number[] }[];
  recommendations?: { title: string; action_type?: string; priority?: string; reason?: string; confidence?: number; target_refs?: string[] }[];
  false_positive?: { possible?: boolean; reason?: string };
  follow_up_checks?: { description: string; sql_draft?: string | null }[];
  limitations?: string[];
}

export interface AiQualityResultItem {
  id: number;
  job_id: number;
  risk_level: string;
  summary: string;
  structured_result: AiQualityResult;
  output_digest?: string | null;
  review_status: "pending" | "accepted" | "rejected" | "partial";
  attached_by?: string | null;
  attached_at?: string | null;
  accepted_recommendations?: number[] | null;
}

const AI_QUALITY_BASE = "/api/v1/quality/ai";
export const getAiQualityStatus = () => http.get<ApiResponse<AiQualityStatus>, object>(`${AI_QUALITY_BASE}/status`);
export const testAiQualityConnection = () => http.post<ApiResponse<AiQualityStatus>, object>(`${AI_QUALITY_BASE}/connection-test`);
export const previewAiQuality = (data: { task_type: AiQualityPreview["task_type"]; finding_ids?: number[]; run_id?: number }) =>
  http.post<ApiResponse<AiQualityPreview>, object>(`${AI_QUALITY_BASE}/preview`, { data });
export const createAiQualityJob = (data: { task_type: AiQualityPreview["task_type"]; finding_ids?: number[]; run_id?: number; input_digest: string; request_id: string }) =>
  http.post<ApiResponse<AiQualityJob>, object>(`${AI_QUALITY_BASE}/jobs`, { data });
export const getAiQualityJobs = (params?: { page?: number; page_size?: number; status?: AiQualityJobStatus }) =>
  http.get<ApiResponse<PageData<AiQualityJob>>, object>(`${AI_QUALITY_BASE}/jobs`, { params });
export const getAiQualityJob = (jobId: number | string) => http.get<ApiResponse<AiQualityJob>, object>(`${AI_QUALITY_BASE}/jobs/${encodeURIComponent(String(jobId))}`);
export const retryAiQualityJob = (jobId: number | string) => http.post<ApiResponse<AiQualityJob>, object>(`${AI_QUALITY_BASE}/jobs/${encodeURIComponent(String(jobId))}/retry`);
export const reviewAiQualityResult = (resultId: number | string, data: { status: "accepted" | "rejected" | "partial"; note?: string; accepted_recommendations?: number[] }) =>
  http.patch<ApiResponse<AiQualityResultItem>, object>(`${AI_QUALITY_BASE}/results/${encodeURIComponent(String(resultId))}/review`, { data });
export const attachAiQualityResult = (resultId: number | string, data: { recommendation_indexes: number[]; note?: string }) =>
  http.post<ApiResponse<AiQualityResultItem>, object>(`${AI_QUALITY_BASE}/results/${encodeURIComponent(String(resultId))}/attach`, { data });

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
