import { http } from "@/utils/http";

export interface RecipeItem {
  id: number;
  recipe_id: string;
  version: number;
  recipe_name?: string | null;
  status: string;
  is_active: boolean;
  domain?: string | null;
  description?: string | null;
  primary_tables?: unknown[] | null;
  joins?: unknown[] | null;
  generated_sql?: string | null;
}

interface ApiResponse<T> { code: number; message: string; data: T; }

export function listRecipes(params?: Record<string, unknown>) {
  return http.request<ApiResponse<{ total: number; items: RecipeItem[] }>>("get", "/api/v1/recipes", { params });
}
export function createRecipe(data: Record<string, unknown>) {
  return http.request<ApiResponse<RecipeItem>>("post", "/api/v1/recipes", { data });
}
export function copyRecipeVersion(recipeId: string, version?: number) {
  return http.request<ApiResponse<RecipeItem>>("post", `/api/v1/recipes/${encodeURIComponent(recipeId)}/versions`, { params: version ? { version } : undefined });
}
export function submitRecipe(recipeId: string, version: number) {
  return http.request<ApiResponse<RecipeItem>>("post", `/api/v1/recipes/${encodeURIComponent(recipeId)}/versions/${version}/submit`);
}
export function generateRecipeSql(recipeId: string, version: number, dialect = "oracle") {
  return http.request<ApiResponse<{ sql: string; executed: false }>>("post", `/api/v1/recipes/${encodeURIComponent(recipeId)}/versions/${version}/sql`, { data: { dialect } });
}
