export type GraphEngine = "svg" | "g6";

export interface GraphLoadPolicyInput {
  nodeCount: number;
  edgeCount: number;
  viewMode: string;
  graphEngine: GraphEngine;
  aggregateGroups: boolean;
}

export interface GraphLoadPolicy {
  shouldAggregate: boolean;
  shouldUseSvg: boolean;
  notice: string;
}

const AGGREGATE_NODE_THRESHOLD = 140;
const AGGREGATE_EDGE_THRESHOLD = 180;
const SVG_NODE_THRESHOLD = 220;
const SVG_EDGE_THRESHOLD = 320;

function isAggregationViewMode(viewMode: string) {
  return ["system", "schema", "domain", "deferred"].includes(viewMode);
}

export function decideGraphLoadPolicy(input: GraphLoadPolicyInput): GraphLoadPolicy {
  const large = input.nodeCount >= AGGREGATE_NODE_THRESHOLD || input.edgeCount >= AGGREGATE_EDGE_THRESHOLD;
  const veryLarge = input.nodeCount >= SVG_NODE_THRESHOLD || input.edgeCount >= SVG_EDGE_THRESHOLD;
  const shouldAggregate = large && !input.aggregateGroups && !isAggregationViewMode(input.viewMode);
  const shouldUseSvg = veryLarge && input.graphEngine === "g6";
  const actions: string[] = [];
  if (shouldAggregate) actions.push("已自动开启节点聚合");
  if (shouldUseSvg) actions.push("已切换到 SVG 轻量图");
  const prefix = large ? `大图模式：${input.nodeCount} 个节点、${input.edgeCount} 条关系` : "";
  return {
    shouldAggregate,
    shouldUseSvg,
    notice: [prefix, ...actions].filter(Boolean).join("，")
  };
}
/**
 * 169 G2：overview 失败自动降级决策（纯函数，页面 loadData 调用）。
 * 仅当当前层级可降（非 system）且本会话未降过时降级一次——防止与
 * 错误面板形成"重试→再超时"死循环（round-3 P1）。
 */
export function shouldDowngradeOverview(
  level: string,
  alreadyDowngraded: boolean
): boolean {
  return level !== "system" && !alreadyDowngraded;
}
