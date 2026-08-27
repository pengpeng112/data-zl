import { http } from "@/utils/http";


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

export interface PermissionRequestItem {
  id: number;
  entity_type: "user_role" | "user_data_scope" | string;
  entity_ref: string;
  request_type: string;
  request_content: Record<string, unknown>;
  reason?: string | null;
  status: string;
  requested_by: string;
  approved_by?: string | null;
  executed_by?: string | null;
  created_at?: string | null;
  request_payload?: Record<string, unknown>;
  approval_status?: string;
}

export type { ApiResponse, PageData } from "./types";
import type { ApiResponse, PageData } from "./types";

export interface PermissionRequestCreate {
  request_kind: "role" | "data_scope";
  target_user_identifier: string;
  role_code?: string;
  scope_type?: string;
  system_code?: string;
  source_code?: string;
  schema_name?: string;
  domain?: string;
  reason: string;
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

export function createPermissionRequest(data: PermissionRequestCreate) {
  return http.request<ApiResponse<PermissionRequestItem>>("post", "/api/v1/permission-requests", { data });
}
export function getMyPermissionRequests(params?: { page?: number; page_size?: number }) {
  return http.request<ApiResponse<PageData<PermissionRequestItem>>>("get", "/api/v1/permission-requests/mine", { params });
}
export function getPendingPermissionRequests(params?: { page?: number; page_size?: number }) {
  return http.request<ApiResponse<PageData<PermissionRequestItem>>>("get", "/api/v1/permission-requests/pending", { params });
}
export function decidePermissionRequest(id: number, action: "approve" | "reject", note?: string) {
  return http.request<ApiResponse<PermissionRequestItem>>("patch", `/api/v1/permission-requests/${id}/${action}`, { data: { note } });
}
export function executePermissionRequest(id: number) {
  return http.request<ApiResponse<PermissionRequestItem>>("post", `/api/v1/permission-requests/${id}/execute`);
}
export function revokePermissionRequest(id: number) {
  return http.request<ApiResponse<PermissionRequestItem>>("post", `/api/v1/permission-requests/${id}/revoke`);
}
