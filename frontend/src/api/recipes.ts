import { http } from "@/utils/http";

export interface RecipePrimaryTable {
  table?: string;
  name?: string;
  alias?: string;
  role?: string;
  [key: string]: unknown;
}

export interface RecipeJoin {
  join_type?: "INNER" | "LEFT" | "RIGHT" | "FULL" | string;
  from?: string;
  to?: string;
  on?: string;
  join_condition?: string;
  [key: string]: unknown;
}

export interface RecipeItem {
  id: number;
  recipe_id: string;
  version: number;
  recipe_name?: string | null;
  status: string;
  is_active: boolean;
  domain?: string | null;
  source_system?: string | null;
  business_domain?: string | null;
  recommended_view_name?: string | null;
  description?: string | null;
  primary_tables?: RecipePrimaryTable[] | null;
  joins?: RecipeJoin[] | null;
  recipe_json?: Record<string, unknown> | null;
  content_hash?: string | null;
  ai_readable?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  [key: string]: unknown;
}

export interface RecipeListParams {
  page?: number;
  page_size?: number;
  keyword?: string;
  status?: string;
  domain?: string;
  business_domain?: string;
}

export interface RecipeDraftPayload {
  recipe_name?: string;
  description?: string;
  domain?: string;
  business_domain?: string;
  primary_tables: RecipePrimaryTable[];
  joins: RecipeJoin[];
  recipe_json?: Record<string, unknown>;
}

/** Validate the JSON editor payload before it reaches the API. */
export function validateRecipeDraft(primaryTablesText: string, joinsText: string) {
  const parseArray = (text: string, label: string): unknown[] => {
    let value: unknown;
    try {
      value = JSON.parse(text);
    } catch {
      throw new Error(`${label}必须是合法的 JSON 数组`);
    }
    if (!Array.isArray(value)) throw new Error(`${label}必须是 JSON 数组`);
    return value;
  };
  const primaryTables = parseArray(primaryTablesText, "主表") as RecipePrimaryTable[];
  const joins = parseArray(joinsText, "关联") as RecipeJoin[];
  if (!primaryTables.length) throw new Error("至少填写一张主表，不能创建没有可生成 SQL 内容的空配方");
  primaryTables.forEach((table, index) => {
    const name = typeof table === "string" ? table : table?.table || table?.name;
    if (typeof name !== "string" || !name.trim()) throw new Error(`主表第 ${index + 1} 项缺少 table 或 name`);
  });
  joins.forEach((join, index) => {
    if (!join || typeof join !== "object") throw new Error(`关联第 ${index + 1} 项必须是 JSON 对象`);
    const condition = join.on || join.join_condition;
    if (typeof condition !== "string" || !condition.trim()) throw new Error(`关联第 ${index + 1} 项缺少非空的 on 或 join_condition`);
  });
  if (primaryTables.length > 1 && joins.length < primaryTables.length - 1) {
    throw new Error(`当前有 ${primaryTables.length} 张主表，至少需要 ${primaryTables.length - 1} 条关联条件`);
  }
  return { primaryTables, joins };
}

import type { ApiResponse } from "./types";

export function listRecipes(params?: RecipeListParams) {
  return http.request<ApiResponse<{ total: number; page: number; page_size: number; items: RecipeItem[] }>>("get", "/api/v1/recipes", { params });
}

export function getRecipe(recipeId: string) {
  return http.request<ApiResponse<RecipeItem>>("get", `/api/v1/recipes/${encodeURIComponent(recipeId)}`);
}

export function listRecipeVersions(recipeId: string) {
  return http.request<ApiResponse<RecipeItem[]>>("get", `/api/v1/recipes/${encodeURIComponent(recipeId)}/versions`);
}

export function getRecipeVersion(recipeId: string, version: number) {
  return http.request<ApiResponse<RecipeItem>>("get", `/api/v1/recipes/${encodeURIComponent(recipeId)}/versions/${version}`);
}

export function createRecipe(data: RecipeDraftPayload & { recipe_id: string }) {
  return http.request<ApiResponse<RecipeItem>>("post", "/api/v1/recipes", { data });
}

export function updateRecipeVersion(recipeId: string, version: number, data: Partial<RecipeDraftPayload>) {
  return http.request<ApiResponse<RecipeItem>>("put", `/api/v1/recipes/${encodeURIComponent(recipeId)}/versions/${version}`, { data });
}

export function copyRecipeVersion(recipeId: string, version?: number) {
  return http.request<ApiResponse<RecipeItem>>("post", `/api/v1/recipes/${encodeURIComponent(recipeId)}/versions`, { params: version ? { version } : undefined });
}

export function generateRecipeSql(recipeId: string, version: number, dialect = "oracle") {
  return http.request<ApiResponse<{ recipe_id: string; version: number; dialect: string; sql: string; executed: false }>>("post", `/api/v1/recipes/${encodeURIComponent(recipeId)}/versions/${version}/sql`, { data: { dialect } });
}

// ── 状态流转（146 D3：复用后端既有状态机，仅补前端封装）──

function versionAction(recipeId: string, version: number, action: string, data?: Record<string, unknown>) {
  return http.request<ApiResponse<RecipeItem>>(
    "post",
    `/api/v1/recipes/${encodeURIComponent(recipeId)}/versions/${version}/${action}`,
    { data: data ?? {} }
  );
}

export const submitRecipeVersion = (recipeId: string, version: number) => versionAction(recipeId, version, "submit");
export const approveRecipeVersion = (recipeId: string, version: number) => versionAction(recipeId, version, "approve");
export const rejectRecipeVersion = (recipeId: string, version: number, reason?: string) =>
  versionAction(recipeId, version, "reject", reason ? { reason } : undefined);
export const activateRecipeVersion = (recipeId: string, version: number) => versionAction(recipeId, version, "activate");
export const deprecateRecipeVersion = (recipeId: string, version: number) => versionAction(recipeId, version, "deprecate");
