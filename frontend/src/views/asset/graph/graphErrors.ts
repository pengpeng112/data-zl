/**
 * 108 号图谱错误分类与状态机辅助。
 *
 * 页面状态：initial / loading / success / empty / filter_empty /
 *           auth_error / permission_error / api_error / contract_error / render_error
 *
 * options / diagnostics / graph 三条请求链相互隔离，任一条失败都不得用
 * "暂无数据" 掩盖（108 §五）。
 */

export type GraphPageState =
  | "initial"
  | "loading"
  | "success"
  | "empty"
  | "filter_empty"
  | "auth_error"
  | "permission_error"
  | "api_error"
  | "contract_error"
  | "render_error";

export interface GraphErrorInfo {
  state: GraphPageState;
  title: string;
  description: string;
  correlationId: string;
  status?: number;
  canRetry: boolean;
  retryLabel?: string;
}

/** 生成脱敏 correlation ID（UUID 短码），不包含 Token/身份信息。 */
export function newCorrelationId(): string {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
}

interface RawError {
  status?: number;
  response?: { status?: number; data?: unknown };
  code?: string;
  message?: string;
  isCancelRequest?: boolean;
}

function errorStatus(err: unknown): number | undefined {
  const e = err as RawError;
  if (e?.response?.status) return e.response.status;
  if (e?.status) return e.status;
  return undefined;
}

/** 按 HTTP 状态与结构错误分类。 */
export function classifyGraphError(err: unknown): GraphErrorInfo {
  const correlationId = newCorrelationId();
  const status = errorStatus(err);
  if (status === 401) {
    return {
      state: "auth_error",
      title: "登录已过期",
      description: "请重新登录后再查看关系图谱。",
      correlationId,
      status,
      canRetry: false,
    };
  }
  if (status === 403) {
    return {
      state: "permission_error",
      title: "没有访问权限",
      description: "当前账号无权查看关系图谱，请联系管理员开通。",
      correlationId,
      status,
      canRetry: false,
    };
  }
  return {
    state: "api_error",
    title: "图谱接口请求失败",
    description: "请稍后重试；若持续失败请联系管理员并提供下方关联编号。",
    correlationId,
    status,
    canRetry: true,
    retryLabel: "重试",
  };
}

/** 校验图响应结构是否满足契约，缺字段则判 contract_error。 */
export function validateGraphData(data: unknown): data is {
  nodes: unknown[];
  edges: unknown[];
} {
  if (!data || typeof data !== "object") return false;
  const d = data as Record<string, unknown>;
  if (!Array.isArray(d.nodes) || !Array.isArray(d.edges)) return false;
  return true;
}

export function contractErrorInfo(err: unknown): GraphErrorInfo {
  return {
    state: "contract_error",
    title: "图谱数据格式异常",
    description: "接口返回结构与前端契约不一致，请检查前后端版本是否一致。",
    correlationId: newCorrelationId(),
    canRetry: true,
    retryLabel: "刷新",
  };
}
