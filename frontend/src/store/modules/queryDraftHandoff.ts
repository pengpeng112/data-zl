import { defineStore } from "pinia";

/**
 * 186 Q3：AI SQL → 查询中心摄取表单的临时交接（内存 Pinia，不持久化）。
 *
 * 契约（186 §4.5）：
 * - URL 仅带 tab=list 与随机 handoffId，不带 SQL/需求全文；
 * - 切换用户、登出、提交成功、明确放弃或 30 分钟过期时清空；
 * - 接收端有未保存草稿时不静默覆盖（组件侧提供冲突处理）；
 * - 浏览器刷新后内存不存在 → 提示失效，不自动生成/提交/恢复他人内容。
 */

export type QueryDraftHandoff = {
  handoffId: string;
  systemCode: "DATA_CENTER";
  sourceCode?: string;
  sqlText: string;
  questionSummary: string;
  selectedTables: string[];
  contextDigest: Record<string, unknown>;
  risk: Record<string, unknown>;
  createdAt: number;
};

const HANDOFF_TTL_MS = 30 * 60 * 1000;

function isExpired(draft: QueryDraftHandoff | null): boolean {
  if (!draft) return true;
  return Date.now() - draft.createdAt > HANDOFF_TTL_MS;
}

export const useQueryDraftHandoffStore = defineStore("queryDraftHandoff", {
  state: () => ({
    draft: null as QueryDraftHandoff | null
  }),
  getters: {
    /** 未过期草稿；过期自动清空并返回 null */
    activeDraft(state): QueryDraftHandoff | null {
      if (isExpired(state.draft)) {
        if (state.draft) state.draft = null;
        return null;
      }
      return state.draft;
    }
  },
  actions: {
    stage(draft: Omit<QueryDraftHandoff, "handoffId" | "createdAt">) {
      this.draft = {
        ...draft,
        handoffId: `hd-${Date.now().toString(36)}-${Math.random()
          .toString(36)
          .slice(2, 8)}`,
        createdAt: Date.now()
      };
      return this.draft.handoffId;
    },
    /** 消费一次：读取并清空（草稿归表单内存后 store 不再持有） */
    consume(handoffId?: string): QueryDraftHandoff | null {
      const draft = this.activeDraft;
      if (!draft) return null;
      if (handoffId && draft.handoffId !== handoffId) return null;
      this.draft = null;
      return draft;
    },
    peek(handoffId?: string): QueryDraftHandoff | null {
      const draft = this.activeDraft;
      if (!draft) return null;
      if (handoffId && draft.handoffId !== handoffId) return null;
      return draft;
    },
    clear() {
      this.draft = null;
    }
  }
});
