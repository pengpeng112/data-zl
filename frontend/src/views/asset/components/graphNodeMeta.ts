/**
 * 146 E2（R5）：字段节点副标题（node.meta）渲染辅助。
 * RelationGraph 已在 LayoutNode.meta 中为字段节点计算副标题（数据类型/键类型），
 * 本模块负责把它截断成画布可读的短行——长文本一律截断加省略号，
 * 保证副标题不与相邻节点文字重叠、不溢出画布（146 E2 长文本截断/可读性要求）。
 */

/** 字段节点副标题最大字符数（SVG 内 11px 字号下的可读上限） */
export const GRAPH_META_MAX_CHARS = 26;

/** 单行截断：超长文本截断并追加省略号；空值统一返回空串（不渲染副标题）。 */
export function truncateGraphMeta(meta: string | null | undefined, max = GRAPH_META_MAX_CHARS): string {
  const text = String(meta ?? "").trim();
  if (!text) return "";
  if (text.length <= max) return text;
  const cut = Math.max(1, max - 1);
  return `${text.slice(0, cut)}…`;
}

/** 副标题渲染判定：只有非空截断结果才渲染，避免空 text 节点占位。 */
export function shouldRenderGraphMeta(meta: string | null | undefined, max = GRAPH_META_MAX_CHARS): boolean {
  return truncateGraphMeta(meta, max).length > 0;
}
