import { http } from "@/utils/http";

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface PermissionResource {
  code: string;
  name_cn: string;
  type: "menu" | "page" | "api" | "button" | string;
  parent_code?: string | null;
  module_code?: string;
  action_code?: string;
  enabled?: boolean;
}

export interface PermissionRole {
  id?: number;
  role_code: string;
  role_name_cn: string;
  role_type?: string | null;
  description?: string | null;
}

export interface UserRoleAssignment {
  id: number;
  user_identifier: string;
  role_code: string;
  granted_by?: string | null;
  granted_at?: string | null;
  expires_at?: string | null;
}

export interface ApiKeyBinding {
  id: number;
  key_name: string;
  token_masked: string;
  enabled: boolean;
  user_identifier?: string | null;
  created_at?: string | null;
  last_used_at?: string | null;
}

export interface PermissionAuditLog {
  id: number;
  module: string;
  entity_type: string;
  entity_ref: string;
  action: string;
  before_data?: Record<string, unknown> | null;
  after_data?: Record<string, unknown> | null;
  operator?: string | null;
  reason?: string | null;
  created_at?: string | null;
}

export function seedPermissions(operator = "console") {
  return http.request<ApiResponse<any>>("post", "/api/v1/permissions/seed", { params: { operator } });
}

export function getPermissionResources() {
  return http.request<ApiResponse<PermissionResource[]>>("get", "/api/v1/permissions/resources");
}

export function getPermissionRoles() {
  return http.request<ApiResponse<PermissionRole[]>>("get", "/api/v1/permissions/roles");
}

export function upsertPermissionRole(data: Partial<PermissionRole> & { operator?: string }) {
  return http.request<ApiResponse<PermissionRole>>("put", "/api/v1/permissions/roles", { data });
}

export function getRoleMatrix(roleCode: string) {
  return http.request<ApiResponse<{ role: PermissionRole; resources: PermissionResource[]; granted: string[] }>>(
    "get",
    `/api/v1/permissions/roles/${roleCode}/matrix`
  );
}

export function updateRoleMatrix(roleCode: string, data: { permissions: string[]; operator?: string; reason?: string }) {
  return http.request<ApiResponse<any>>("put", `/api/v1/permissions/roles/${roleCode}/matrix`, { data });
}

export function getUserRoles(params?: Record<string, any>) {
  return http.request<ApiResponse<UserRoleAssignment[]>>("get", "/api/v1/permissions/user-roles", { params });
}

export function replaceUserRoles(userIdentifier: string, data: { user_identifier: string; role_codes: string[]; granted_by?: string; reason?: string }) {
  return http.request<ApiResponse<any>>("put", `/api/v1/permissions/users/${userIdentifier}/roles`, { data });
}

export function getUserPermissions(userIdentifier: string) {
  return http.request<ApiResponse<any>>("get", `/api/v1/permissions/users/${userIdentifier}/permissions`);
}

export function getPermissionApiKeys() {
  return http.request<ApiResponse<ApiKeyBinding[]>>("get", "/api/v1/permissions/api-keys");
}

export function bindPermissionApiKey(keyId: number, data: { key_id: number; user_identifier?: string | null; operator?: string }) {
  return http.request<ApiResponse<any>>("patch", `/api/v1/permissions/api-keys/${keyId}/bind`, { data });
}

export function getMyPermissions() {
  return http.request<ApiResponse<any>>("get", "/api/v1/permissions/me");
}
export function getPermissionAuditLogs(params?: Record<string, any>) {
  return http.request<ApiResponse<PermissionAuditLog[]>>("get", "/api/v1/permissions/audit", { params });
}

export function createPermissionRequest(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/permission-requests", { data });
}
export function getMyPermissionRequests() {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/permission-requests/mine");
}
export function getPendingPermissionRequests() {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/permission-requests/pending");
}
export function decidePermissionRequest(id: number, action: "approve" | "reject", note?: string) {
  return http.request<ApiResponse<any>>("patch", `/api/v1/permission-requests/${id}/${action}`, { data: { note } });
}
export function executePermissionRequest(id: number) {
  return http.request<ApiResponse<any>>("post", `/api/v1/permission-requests/${id}/execute`);
}
