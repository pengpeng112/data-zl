/**
 * 186 N2：菜单偏好（搜索历史/收藏/最近访问）按用户隔离的工具层。
 *
 * 设计约束（186 §5 N2）：
 * - 存储 key = 平台环境 + 稳定用户标识 + schema 版本；不存 Token/姓名/患者条件。
 * - 只保存允许列表中的 route name/path 与非敏感定位参数；含 SQL、患者、
 *   密钥的 query 不持久化（query 一律丢弃，仅保留 path/name）。
 * - 读取时与当前有效可访问路由重新求交，标题从当前 meta 重建；权限变化
 *   立即过滤，不依靠重新登录。
 * - 旧无用户标识缓存不能安全判断归属：忽略/清理旧通用键，不导入当前用户。
 * - 存储损坏、配额满、禁用 localStorage 时回退内存，不阻断导航。
 */

import { storageLocal } from "@pureadmin/utils";
import { userKey, type DataInfo } from "@/utils/auth";

export const PREFERENCES_SCHEMA_VERSION = "v2";
const MAX_ITEMS = 20;

/** 旧版无用户隔离的通用键：不再读取，读取即清理（E06 泄漏面收口） */
const LEGACY_KEYS = ["menu-search-history", "menu-search-collect"];

/** 允许持久化的定位参数键（白名单之外一律丢弃） */
const ALLOWED_QUERY_KEYS = new Set([
  "tab",
  "scope",
  "status",
  "page",
  "page_size",
  "keyword",
  "system_code",
  "source_code",
  "schema",
  "table",
  "view_mode",
  "class",
  "query_code",
  "run_id",
  "id"
]);

export interface MenuVisitItem {
  /** 稳定 route name（优先）或 path */
  routeName?: string;
  path: string;
  visitedAt: number;
}

export interface StableUserScope {
  envTag: string;
  userId: string;
}

function safeLocalStorage(): Storage | null {
  try {
    const probeKey = "__menu_pref_probe__";
    window.localStorage.setItem(probeKey, "1");
    window.localStorage.removeItem(probeKey);
    return window.localStorage;
  } catch {
    return null;
  }
}

/** 当前登录用户的稳定隔离 scope；未登录返回 null（调用方不持久化） */
export function currentUserScope(): StableUserScope | null {
  let profile: DataInfo<number> | null = null;
  try {
    profile = storageLocal().getItem<DataInfo<number>>(userKey) ?? null;
  } catch {
    profile = null;
  }
  const userId = profile?.username ?? (profile as any)?.id;
  if (!userId) return null;
  const envTag =
    (typeof import.meta.env.VITE_APP_PLATFORM_TAG === "string"
      ? import.meta.env.VITE_APP_PLATFORM_TAG
      : "") || "default";
  return { envTag, userId: String(userId) };
}

function scopedKey(kind: "history" | "collect" | "recent"): string | null {
  const scope = currentUserScope();
  if (!scope) return null;
  return `menu-pref-${PREFERENCES_SCHEMA_VERSION}:${scope.envTag}:${scope.userId}:${kind}`;
}

const memoryFallback: Record<string, any[]> = {};

function readList(kind: "history" | "collect" | "recent"): any[] {
  const key = scopedKey(kind);
  if (!key) return [];
  const storage = safeLocalStorage();
  if (!storage) return memoryFallback[key] ?? [];
  try {
    const raw = storage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    // 损坏数据：清掉这一项，回退空列表
    try {
      storage.removeItem(key);
    } catch {
      /* ignore */
    }
    return [];
  }
}

function writeList(kind: "history" | "collect" | "recent", items: any[]): void {
  const key = scopedKey(kind);
  if (!key) return;
  const bounded = items.slice(0, MAX_ITEMS);
  const storage = safeLocalStorage();
  if (!storage) {
    memoryFallback[key] = bounded;
    return;
  }
  try {
    storage.setItem(key, JSON.stringify(bounded));
  } catch {
    // 配额满等：回退内存，不抛错阻断导航
    memoryFallback[key] = bounded;
  }
}

/** 清理旧通用键（不可安全判断归属，不导入当前用户） */
export function purgeLegacyKeys(): void {
  const storage = safeLocalStorage();
  if (!storage) return;
  for (const key of LEGACY_KEYS) {
    try {
      storage.removeItem(key);
    } catch {
      /* ignore */
    }
  }
}

/** 登出清理：只清当前 scope 的偏好键（由 utils/auth 登出流程调用） */
export function clearCurrentUserPreferences(): void {
  const kinds: Array<"history" | "collect" | "recent"> = [
    "history",
    "collect",
    "recent"
  ];
  const storage = safeLocalStorage();
  for (const kind of kinds) {
    const key = scopedKey(kind);
    if (!key) continue;
    delete memoryFallback[key];
    if (storage) {
      try {
        storage.removeItem(key);
      } catch {
        /* ignore */
      }
    }
  }
}

// ---------------------------------------------------------------------------
// 与当前可访问路由求交 + 标题重建
// ---------------------------------------------------------------------------

export interface AccessibleRouteInfo {
  path: string;
  name?: string | symbol;
  title: string;
  parentTitle?: string;
}

/**
 * 用当前权限过滤后的可访问路由集合，重建历史/收藏条目：
 * - path 命中且（若有 name）name 一致 → 保留，标题取当前 meta；
 * - 未命中（权限撤回/路由下线）→ 丢弃。
 */
export function revalidateAgainstRoutes<T extends { path: string; routeName?: string }>(
  items: T[],
  accessible: AccessibleRouteInfo[]
): Array<T & { title: string; parentTitle?: string }> {
  const byPath = new Map(accessible.map(r => [r.path, r]));
  const result: Array<T & { title: string; parentTitle?: string }> = [];
  const seen = new Set<string>();
  for (const item of items) {
    const info = byPath.get(item.path);
    if (!info) continue;
    if (item.routeName && info.name && String(info.name) !== item.routeName) {
      continue;
    }
    const dedupeKey = item.path;
    if (seen.has(dedupeKey)) continue;
    seen.add(dedupeKey);
    result.push({ ...item, title: info.title, parentTitle: info.parentTitle });
  }
  return result.slice(0, MAX_ITEMS);
}

// ---------------------------------------------------------------------------
// 最近访问（20 条上限、去重、白名单 query）
// ---------------------------------------------------------------------------

export function sanitizeQuery(query: Record<string, any> | undefined): string {
  if (!query) return "";
  const pairs: string[] = [];
  for (const key of Object.keys(query)) {
    if (!ALLOWED_QUERY_KEYS.has(key)) continue;
    const value = String(query[key] ?? "");
    if (!value) continue;
    pairs.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
  }
  return pairs.length ? `?${pairs.join("&")}` : "";
}

export function recordRecentVisit(route: {
  path: string;
  name?: string | symbol;
  query?: Record<string, any>;
}): void {
  const scope = currentUserScope();
  if (!scope) return;
  const path = route.path.split("?")[0];
  // 登录页/重定向壳不记录
  if (path === "/login" || path.startsWith("/redirect") || path === "/") return;
  const suffix = sanitizeQuery(route.query);
  const entry: MenuVisitItem & { querySuffix?: string } = {
    routeName: route.name ? String(route.name) : undefined,
    path,
    visitedAt: Date.now(),
    querySuffix: suffix || undefined
  };
  const existing = readList("recent") as Array<MenuVisitItem & { querySuffix?: string }>;
  const filtered = existing.filter(
    item => !(item.path === path && (item.querySuffix ?? "") === (entry.querySuffix ?? ""))
  );
  writeList("recent", [entry, ...filtered]);
}

export function getRecentVisits(): Array<MenuVisitItem & { querySuffix?: string }> {
  return readList("recent") as Array<MenuVisitItem & { querySuffix?: string }>;
}

// ---------------------------------------------------------------------------
// 搜索历史与收藏（SearchModal 迁移到用户隔离键）
// ---------------------------------------------------------------------------

export const searchHistory = {
  read: () => readList("history"),
  write: (items: any[]) => writeList("history", items)
};

export const searchCollect = {
  read: () => readList("collect"),
  write: (items: any[]) => writeList("collect", items)
};

// ---------------------------------------------------------------------------
// 旧名称别名（186 N1：菜单中文名更改后，搜索保留旧名）
// ---------------------------------------------------------------------------

/** 旧中文名 → 现行标题（或标题片段）的别名映射；命中即纳入搜索结果 */
export const MENU_TITLE_ALIASES: Record<string, string> = {
  同步日志: "人员同步日志",
  同步差异: "人员同步差异",
  人员与科室: "人员与权限",
  数据资产: "资产目录",
  字典中心: "标准与关系",
  数据治理: "标准与关系",
  变更检测: "元数据变更",
  质量管理: "质量治理",
  指挥中心: "运行总览",
  首页: "日常工作台",
  查询与指标中心: "查询、指标与产品",
  查询中心: "查询、指标与产品",
  "AI 写 SQL": "AI辅助编写",
  AI写SQL: "AI辅助编写",
  业务系统与数据资源: "系统与数据资源",
  表资产: "表与字段",
  关系复核中心: "关系复核",
  关系配方库: "关系配方",
  关系命中率: "关系验证统计",
  "SQL 工作台": "受控SQL运维",
  工具模板: "运维工具模板",
  运维审计: "操作审计",
  治理管理: "治理基础配置",
  诊断手术维护: "诊断手术字典",
  编码关系明细: "编码映射",
  跨系统账号: "业务系统账号",
  本地账号: "平台本地账号",
  角色权限: "平台角色权限",
  权限申请审批: "权限申请与审批",
  我的任务: "我的质量任务",
  科室任务: "科室质量任务",
  数据资产系统图: "平台能力全景",
  资产总览: "资产统计",
  AI质控分析: "AI质量分析",
  元数据质控: "元数据质控"
};

/** 标题（或别名）匹配：大小写不敏感子串 */
export function titleMatchesAlias(title: string, keyword: string): boolean {
  const kw = keyword.trim().toLowerCase();
  if (!kw) return false;
  if (title.toLowerCase().includes(kw)) return true;
  for (const [alias, target] of Object.entries(MENU_TITLE_ALIASES)) {
    if (alias.toLowerCase().includes(kw) && target === title) return true;
  }
  return false;
}
