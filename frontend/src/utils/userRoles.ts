/**
 * 146 E2（R5）：轻量角色读取工具。
 *
 * 供不依赖 Pinia 的展示组件（如 GraphToolbar 统计折叠）判断当前账号是否为治理角色，
 * 避免在纯展示组件里引入 store 依赖。与 store/modules/user.ts 一样从
 * localStorage 的 user-info（userKey）读取 roles；任何读取异常都按"普通用户"兜底。
 */

const USER_INFO_KEY = "user-info";

/** 从本地缓存读取当前账号角色；异常一律返回空数组（普通用户语义）。 */
export function cachedUserRoles(): string[] {
  try {
    const raw = window.localStorage?.getItem?.(USER_INFO_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as { roles?: unknown };
    return Array.isArray(parsed?.roles) ? (parsed.roles as string[]).map(String) : [];
  } catch {
    return [];
  }
}

/** 治理角色判定：admin / *_admin（platform_admin、asset_admin、dict_admin 等）。 */
export function isGovernanceRole(roles: Array<string> | undefined | null): boolean {
  return (roles || []).some(role => role === "admin" || String(role).endsWith("_admin"));
}

/** 当前账号是否治理角色（供展示组件直接调用）。 */
export function isGovernanceUser(): boolean {
  return isGovernanceRole(cachedUserRoles());
}
