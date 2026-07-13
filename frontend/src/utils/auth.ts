import Cookies from "js-cookie";
import { useUserStoreHook } from "@/store/modules/user";
import { storageLocal, isString, isIncludeAllChildren } from "@pureadmin/utils";

export interface DataInfo<T> {
  /** token — 运行期保存在内存，不写 localStorage */
  accessToken: string;
  /** accessToken 的过期时间（时间戳） */
  expires: T;
  /** Refresh 由 HttpOnly Cookie 承载；此字段仅兼容模板 */
  refreshToken: string;
  /** 头像 */
  avatar?: string;
  /** 用户名 */
  username?: string;
  /** 昵称 */
  nickname?: string;
  /** 当前登录用户的角色 */
  roles?: Array<string>;
  /** 当前登录用户的按钮级别权限 */
  permissions?: Array<string>;
  must_change_password?: boolean;
  user_identifier?: string;
}

export const userKey = "user-info";
export const TokenKey = "authorized-token";
/**
 * 通过 multiple-tabs 是否在 cookie 中，判断用户是否已经登录系统
 */
export const multipleTabsKey = "multiple-tabs";

/** Access Token 仅保存在运行内存（59 号计划） */
let memoryAccessToken = "";
let memoryExpires = 0;

export function setMemoryAccessToken(token: string, expiresTs: number) {
  memoryAccessToken = token || "";
  memoryExpires = expiresTs || 0;
}

export function getMemoryAccessToken(): { accessToken: string; expires: number } {
  return { accessToken: memoryAccessToken, expires: memoryExpires };
}

export function clearMemoryAccessToken() {
  memoryAccessToken = "";
  memoryExpires = 0;
}

/** 获取 token（优先内存 Access Token） */
export function getToken(): DataInfo<number> {
  const profile = storageLocal().getItem<DataInfo<number>>(userKey);
  if (memoryAccessToken) {
    return {
      accessToken: memoryAccessToken,
      expires: memoryExpires,
      refreshToken: "",
      avatar: profile?.avatar,
      username: profile?.username,
      nickname: profile?.nickname,
      roles: profile?.roles,
      permissions: profile?.permissions,
      must_change_password: profile?.must_change_password,
      user_identifier: profile?.user_identifier
    };
  }
  // 兼容：旧 cookie 中的 token（迁移期）
  if (Cookies.get(TokenKey)) {
    try {
      return JSON.parse(Cookies.get(TokenKey));
    } catch {
      return profile as DataInfo<number>;
    }
  }
  return profile as DataInfo<number>;
}

/**
 * 设置 token：Access Token 进内存；用户画像进 localStorage（不含 accessToken）
 */
export function setToken(data: DataInfo<Date | string | number>) {
  const { accessToken, refreshToken } = data;
  const { isRemembered, loginDay } = useUserStoreHook();

  let expires = 0;
  if (typeof data.expires === "number") {
    expires = data.expires;
  } else if (data.expires) {
    expires = new Date(data.expires as string | Date).getTime();
  }

  setMemoryAccessToken(accessToken || "", expires);

  // 不再把 Access Token 写入可读 Cookie；仅保留多标签会话标记
  Cookies.remove(TokenKey);
  Cookies.set(
    multipleTabsKey,
    "true",
    isRemembered
      ? {
          expires: loginDay
        }
      : {}
  );

  function setUserKey({
    avatar,
    username,
    nickname,
    roles,
    permissions,
    must_change_password,
    user_identifier
  }: {
    avatar: string;
    username: string;
    nickname: string;
    roles: Array<string>;
    permissions: Array<string>;
    must_change_password?: boolean;
    user_identifier?: string;
  }) {
    useUserStoreHook().SET_AVATAR(avatar);
    useUserStoreHook().SET_USERNAME(username);
    useUserStoreHook().SET_NICKNAME(nickname);
    useUserStoreHook().SET_ROLES(roles);
    useUserStoreHook().SET_PERMS(permissions);
    storageLocal().setItem(userKey, {
      // 不持久化 accessToken
      accessToken: "",
      refreshToken: refreshToken || "",
      expires,
      avatar,
      username,
      nickname,
      roles,
      permissions,
      must_change_password,
      user_identifier
    });
  }

  if (data.username && data.roles) {
    setUserKey({
      avatar: data?.avatar ?? "",
      username: data.username,
      nickname: data?.nickname ?? "",
      roles: data.roles,
      permissions: data?.permissions ?? [],
      must_change_password: data.must_change_password,
      user_identifier: data.user_identifier
    });
  } else {
    const prev = storageLocal().getItem<DataInfo<number>>(userKey);
    setUserKey({
      avatar: data?.avatar ?? prev?.avatar ?? "",
      username: data?.username ?? prev?.username ?? "",
      nickname: data?.nickname ?? prev?.nickname ?? "",
      roles: data?.roles ?? prev?.roles ?? [],
      permissions: data?.permissions ?? prev?.permissions ?? [],
      must_change_password: data.must_change_password ?? prev?.must_change_password,
      user_identifier: data.user_identifier ?? prev?.user_identifier
    });
  }
}

/** 删除 token 与用户信息 */
export function removeToken() {
  clearMemoryAccessToken();
  Cookies.remove(TokenKey);
  Cookies.remove(multipleTabsKey);
  storageLocal().removeItem(userKey);
}

/** 格式化 token（Bearer） */
export const formatToken = (token: string): string => {
  return "Bearer " + token;
};

/** 是否有按钮级别的权限 */
export const hasPerms = (value: string | Array<string>): boolean => {
  if (!value) return false;
  const allPerms = "*:*:*";
  const { permissions } = useUserStoreHook();
  if (!permissions) return false;
  if (permissions.length === 1 && permissions[0] === allPerms) return true;
  const isAuths = isString(value)
    ? permissions.includes(value)
    : isIncludeAllChildren(value, permissions);
  return isAuths ? true : false;
};
