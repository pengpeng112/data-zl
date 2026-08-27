import { http } from "@/utils/http";

export type { ApiResponse } from "./types";
import type { ApiResponse } from "./types";

export interface LocalAuthUser {
  id: number;
  username: string;
  user_identifier?: string | null;
  person_name_cn?: string | null;
  enabled: boolean;
  must_change_password: boolean;
  failed_login_count?: number;
  locked_until?: string | null;
  last_login_at?: string | null;
  created_at?: string | null;
}

export interface LoginEvent {
  id: number;
  username?: string | null;
  user_identifier?: string | null;
  result: string;
  reason_code?: string | null;
  client_ip_masked?: string | null;
  created_at?: string | null;
}

export function listLocalUsers(params?: {
  q?: string;
  page?: number;
  page_size?: number;
}) {
  return http.request<ApiResponse<{ items: LocalAuthUser[]; page: number; page_size: number }>>(
    "get",
    "/api/v1/auth/users",
    { params }
  );
}

export function createLocalUser(data: {
  username: string;
  password?: string;
  user_identifier?: string;
  must_change_password?: boolean;
  enabled?: boolean;
  role_codes?: string[];
}) {
  return http.request<
    ApiResponse<{
      id: number;
      username: string;
      user_identifier?: string | null;
      person_name_cn?: string | null;
      must_change_password: boolean;
      initial_password?: string | null;
      warning?: string | null;
    }>
  >("post", "/api/v1/auth/users", { data });
}

export function patchLocalUser(
  userId: number,
  data: {
    enabled?: boolean;
    unlock?: boolean;
    must_change_password?: boolean;
    reset_password?: string;
    user_identifier?: string | null;
  }
) {
  return http.request<ApiResponse<Record<string, unknown>>>(
    "patch",
    `/api/v1/auth/users/${userId}`,
    { data }
  );
}

export function listLoginEvents(params?: { page?: number; page_size?: number }) {
  return http.request<ApiResponse<{ items: LoginEvent[]; page: number; page_size: number }>>(
    "get",
    "/api/v1/auth/login-events",
    { params }
  );
}
