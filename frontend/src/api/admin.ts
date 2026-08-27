/**
 * 治理管理 API（153 F4：asset/admin 页 12 处裸 http 收编）。
 */
import { http } from "@/utils/http";
import type { ApiResponse, PageData } from "./types";

export interface AdminKeyItem {
  id: number;
  key_name: string;
  user_identifier: string | null;
  has_legacy_token: boolean;
  enabled: boolean;
  created_at: string | null;
  last_used_at: string | null;
}

export interface AdminOwnerItem {
  id: number;
  full_table_name: string;
  owner_name: string | null;
  department: string | null;
  contact: string | null;
  note: string | null;
  updated_at: string | null;
}

export interface AdminTermItem {
  id: number;
  term: string;
  mapping_type: string | null;
  mapping_target: string;
  description: string | null;
  created_at: string | null;
}

export interface AdminSnapshotItem {
  id: number;
  label: string | null;
  snapshot_time: string | null;
  scope: string | null;
  table_count: number;
  column_count: number;
  relation_count: number;
}

export const listAdminKeys = () => {
  return http.get<ApiResponse<AdminKeyItem[]>, object>("/api/v1/admin/keys");
};

export const createAdminKey = (data: { key_name: string; user_identifier: string }) => {
  return http.post<
    ApiResponse<{ id: number; key_name: string; token: string; warning: string }>,
    object
  >("/api/v1/admin/keys", { data });
};

export const toggleAdminKey = (keyId: number, enabled: boolean) => {
  return http.patch<ApiResponse<AdminKeyItem>, object>(
    `/api/v1/admin/keys/${keyId}`,
    null,
    { params: { enabled } }
  );
};

export const listAdminOwners = (params: {
  page?: number;
  page_size?: number;
  keyword?: string;
}) => {
  return http.get<ApiResponse<PageData<AdminOwnerItem>>, object>("/api/v1/admin/owners", {
    params
  });
};

export const upsertAdminOwner = (data: {
  full_table_name: string;
  owner_name?: string | null;
  department?: string | null;
  contact?: string | null;
  note?: string | null;
}) => {
  return http.put<ApiResponse<{ id: number; full_table_name: string }>, object>(
    "/api/v1/admin/owners",
    { data }
  );
};

export const deleteAdminOwner = (ownerId: number) => {
  return http.delete<ApiResponse<{ deleted: number }>, object>(
    `/api/v1/admin/owners/${ownerId}`
  );
};

export const listAdminTerms = (params: {
  page?: number;
  page_size?: number;
  keyword?: string;
}) => {
  return http.get<ApiResponse<PageData<AdminTermItem>>, object>("/api/v1/admin/terms", {
    params
  });
};

export const upsertAdminTerm = (data: {
  term: string;
  mapping_target: string;
  description?: string;
}) => {
  return http.put<ApiResponse<{ id: number; term: string }>, object>("/api/v1/admin/terms", {
    data
  });
};

export const deleteAdminTerm = (termId: number) => {
  return http.delete<ApiResponse<{ deleted: number }>, object>(
    `/api/v1/admin/terms/${termId}`
  );
};

export const listAdminSnapshots = (params?: { page?: number; page_size?: number }) => {
  return http.get<ApiResponse<PageData<AdminSnapshotItem>>, object>(
    "/api/v1/admin/snapshots",
    { params }
  );
};

export const createAdminSnapshot = (data?: { label?: string }) => {
  return http.post<
    ApiResponse<{ id: number; label: string; table_count: number; column_count: number; relation_count: number }>,
    object
  >("/api/v1/admin/snapshots", { data: data ?? {} });
};

export const compareAdminSnapshots = (id1: number, id2: number) => {
  return http.get<ApiResponse<Record<string, unknown>>, object>(
    "/api/v1/admin/snapshots/compare",
    { params: { id1, id2 } }
  );
};
