import { http } from "@/utils/http";

export type UserResult = {
  success: boolean;
  code?: number;
  message?: string;
  data: {
    /** 头像 */
    avatar: string;
    /** 用户名 */
    username: string;
    /** 昵称 */
    nickname: string;
    /** 当前登录用户的角色 */
    roles: Array<string>;
    /** 按钮级别权限 */
    permissions: Array<string>;
    /** Access Token（短期，仅内存） */
    accessToken: string;
    /** Refresh 由 HttpOnly Cookie 承载；body 通常为空 */
    refreshToken: string;
    /** accessToken 过期时间（格式'xxxx/xx/xx xx:xx:xx'） */
    expires: Date | string;
    must_change_password?: boolean;
    user_identifier?: string;
  };
};

export type RefreshTokenResult = {
  success: boolean;
  code?: number;
  message?: string;
  data: {
    accessToken: string;
    refreshToken: string;
    expires: Date | string;
    username?: string;
    nickname?: string;
    roles?: Array<string>;
    permissions?: Array<string>;
    must_change_password?: boolean;
    user_identifier?: string;
  };
};

export type AuthMeResult = {
  code: number;
  message: string;
  data: {
    username: string;
    user_identifier: string;
    person_name?: string | null;
    roles: string[];
    permissions: string[];
    must_change_password?: boolean;
    enabled?: boolean;
  };
};

/** 登录（Refresh 写入 HttpOnly Cookie） */
export const getLogin = (data?: object) => {
  return http.request<UserResult>("post", "/api/v1/auth/login", {
    data,
    withCredentials: true,
    headers: { "X-Requested-With": "XMLHttpRequest" }
  });
};

/** 刷新 Access Token（依赖 Cookie） */
export const refreshTokenApi = (_data?: object) => {
  return http.request<RefreshTokenResult>("post", "/api/v1/auth/refresh", {
    data: {},
    withCredentials: true,
    headers: { "X-Requested-With": "XMLHttpRequest" }
  });
};

/** 登出并撤销会话 */
export const logoutApi = () => {
  return http.request<{ code: number; data: { logged_out: boolean } }>(
    "post",
    "/api/v1/auth/logout",
    {
      data: {},
      withCredentials: true,
      headers: { "X-Requested-With": "XMLHttpRequest" }
    }
  );
};

/** 当前账号摘要 */
export const getAuthMe = () => {
  return http.request<AuthMeResult>("get", "/api/v1/auth/me", {
    withCredentials: true
  });
};

/** 修改密码 */
export const changePasswordApi = (data: {
  old_password?: string;
  new_password: string;
}) => {
  return http.request<{ code: number; message: string }>(
    "post",
    "/api/v1/auth/change-password",
    { data }
  );
};
