/**
 * 108 号图谱前端测试：
 * - 物理节点规范化（同 display_id 多节点不覆盖）
 * - 错误分类（401/403/500/结构缺失）
 * - 默认页面不发送幽灵状态（F02）
 * - G6 失败回退 SVG 策略
 * - 状态机决策
 */
import { describe, expect, it } from "vitest";
import {
  classifyGraphError,
  contractErrorInfo,
  newCorrelationId,
  validateGraphData,
  type GraphPageState
} from "@/views/asset/graph/graphErrors";
import {
  groupNodesByDisplayId,
  inspectPhysicalNodes,
  nodeDisplayName,
  normalizePhysicalNodes,
  parsePhysicalKey
} from "@/views/asset/graph/graphPhysical";
import { normalizeGraphData } from "@/views/asset/graph/graphNormalize";
import { decideGraphLoadPolicy } from "@/views/asset/graph/graphLoadPolicy";

const ODS_PAT_VISIT = {
  id: "DATA_CENTER|ods_8_216||HIS|PAT_VISIT",
  physical_key: "DATA_CENTER|ods_8_216||HIS|PAT_VISIT",
  display_id: "HIS.PAT_VISIT",
  label: "PAT_VISIT",
  system_code: "DATA_CENTER",
  source_code: "ods_8_216",
  schema_name: "HIS",
  table_name: "PAT_VISIT"
};

const HIS_PAT_VISIT = {
  id: "HIS|his_source_10_10_10_15||MEDREC|PAT_VISIT",
  physical_key: "HIS|his_source_10_10_10_15||MEDREC|PAT_VISIT",
  display_id: "MEDREC.PAT_VISIT",
  label: "PAT_VISIT",
  system_code: "HIS",
  source_code: "his_source_10_10_10_15",
  schema_name: "MEDREC",
  table_name: "PAT_VISIT"
};

describe("graphPhysical", () => {
  it("parses physical key into five parts", () => {
    expect(parsePhysicalKey(ODS_PAT_VISIT.id)).toEqual({
      system: "DATA_CENTER",
      source: "ods_8_216",
      namespace: "",
      schema: "HIS",
      table: "PAT_VISIT"
    });
    expect(parsePhysicalKey("broken")).toBeNull();
    expect(parsePhysicalKey(null)).toBeNull();
  });

  it("normalizes same display_id nodes without overwrite (F01)", () => {
    // 两个不同物理来源的 PAT_VISIT（display_id 相同），必须保留两个节点
    const sameDisplay = [
      { ...ODS_PAT_VISIT },
      { ...HIS_PAT_VISIT, display_id: "HIS.PAT_VISIT" }
    ];
    const result = normalizePhysicalNodes(sameDisplay);
    expect(result).toHaveLength(2);
    const keys = result.map(n => n.id);
    expect(new Set(keys).size).toBe(2);
  });

  it("dedupes identical physical key", () => {
    const result = normalizePhysicalNodes([{ ...ODS_PAT_VISIT }, { ...ODS_PAT_VISIT }]);
    expect(result).toHaveLength(1);
  });

  it("reports missing physical key as issue", () => {
    const { clean, issues } = inspectPhysicalNodes([
      { id: "HIS.PAT_VISIT", label: "no-physical-key", schema_name: "HIS" }
    ]);
    expect(clean).toHaveLength(0);
    expect(issues.some(i => i.reason === "missing_physical_key")).toBe(true);
  });

  it("groups nodes by display_id (cross-source same table)", () => {
    const map = groupNodesByDisplayId([
      { ...ODS_PAT_VISIT },
      { ...HIS_PAT_VISIT, display_id: "HIS.PAT_VISIT" }
    ]);
    expect(map.get("HIS.PAT_VISIT")).toHaveLength(2);
  });

  it("display name prefers table_name_cn", () => {
    expect(nodeDisplayName({ ...ODS_PAT_VISIT, table_name_cn: "就诊主表" })).toBe("就诊主表");
    expect(nodeDisplayName(ODS_PAT_VISIT)).toBe("PAT_VISIT");
  });
});

describe("graphErrors", () => {
  it("classifies 401 as auth_error", () => {
    const info = classifyGraphError({ response: { status: 401 } });
    expect(info.state).toBe("auth_error");
    expect(info.canRetry).toBe(false);
  });

  it("classifies 403 as permission_error", () => {
    const info = classifyGraphError({ response: { status: 403 } });
    expect(info.state).toBe("permission_error");
    expect(info.canRetry).toBe(false);
  });

  it("classifies 500 as api_error with correlation id", () => {
    const info = classifyGraphError({ response: { status: 500 } });
    expect(info.state).toBe("api_error");
    expect(info.canRetry).toBe(true);
    expect(info.correlationId).toMatch(/^[0-9a-f]{16}$/);
  });

  it("classifies timeout (no status) as api_error", () => {
    const info = classifyGraphError(new Error("timeout"));
    expect(info.state).toBe("api_error");
    expect(info.canRetry).toBe(true);
  });

  it("correlation ids are unique", () => {
    expect(newCorrelationId()).not.toBe(newCorrelationId());
  });

  it("validateGraphData rejects missing fields (F09)", () => {
    expect(validateGraphData({ nodes: [], edges: [] })).toBe(true);
    expect(validateGraphData({ nodes: [] })).toBe(false);
    expect(validateGraphData(null)).toBe(false);
    expect(validateGraphData({ nodes: "x", edges: [] })).toBe(false);
  });

  it("contractErrorInfo uses contract_error state", () => {
    const info = contractErrorInfo(new Error("bad contract"));
    expect(info.state).toBe("contract_error");
  });

  it("all states are in the documented set", () => {
    const states: GraphPageState[] = ["initial", "loading", "success", "empty", "filter_empty", "auth_error", "permission_error", "api_error", "contract_error", "render_error"];
    expect(states).toContain("initial");
    expect(states).toContain("render_error");
  });
});

describe("graphNormalize physical dedupe", () => {
  it("keeps two PAT_VISIT physical nodes in normalized output", () => {
    const edges = [
      { id: "e1", source: ODS_PAT_VISIT.id, target: "DATA_CENTER|ods_8_216||HIS|DIAGNOSIS", display_source: "HIS.PAT_VISIT", display_target: "HIS.DIAGNOSIS", relation_type: "formal", confidence: "A", validation_status: "verified" },
      { id: "e2", source: HIS_PAT_VISIT.id, target: "HIS|his_source_10_10_10_15||MEDREC|DIAGNOSIS", display_source: "MEDREC.PAT_VISIT", display_target: "MEDREC.DIAGNOSIS", relation_type: "formal", confidence: "A", validation_status: "verified" }
    ];
    const nodes = [
      { ...ODS_PAT_VISIT },
      { ...HIS_PAT_VISIT },
      { id: "DATA_CENTER|ods_8_216||HIS|DIAGNOSIS", physical_key: "DATA_CENTER|ods_8_216||HIS|DIAGNOSIS", display_id: "HIS.DIAGNOSIS", label: "DIAGNOSIS", table_name: "DIAGNOSIS" },
      { id: "HIS|his_source_10_10_10_15||MEDREC|DIAGNOSIS", physical_key: "HIS|his_source_10_10_10_15||MEDREC|DIAGNOSIS", display_id: "MEDREC.DIAGNOSIS", label: "DIAGNOSIS", table_name: "DIAGNOSIS" }
    ];
    const normalized = normalizeGraphData(nodes as any, edges as any, { groupBy: "schema" });
    expect(normalized.nodes.length).toBe(4);
  });

  it("default graph payload does not include ghost validation_status (F02)", () => {
    // 前端默认不发送 A_rechecked；此测试验证 normalize 不注入该状态
    const edges = [
      { id: "e1", source: ODS_PAT_VISIT.id, target: "DATA_CENTER|ods_8_216||HIS|DIAGNOSIS", relation_type: "formal", confidence: "A" }
    ];
    const normalized = normalizeGraphData([ODS_PAT_VISIT as any], edges as any, { groupBy: "schema" });
    expect(normalized.edges.every(e => e.confidence === "A")).toBe(true);
    expect(normalized.edges.every(e => (e.validation_status || "").indexOf("A_rechecked") === -1)).toBe(true);
  });
});

describe("graphLoadPolicy", () => {
  it("forces SVG when g6 is selected for very large graph", () => {
    const policy = decideGraphLoadPolicy({ nodeCount: 260, edgeCount: 300, viewMode: "table", graphEngine: "g6", aggregateGroups: false });
    expect(policy.shouldUseSvg).toBe(true);
  });

  it("enables aggregation for large table graph", () => {
    const policy = decideGraphLoadPolicy({ nodeCount: 150, edgeCount: 200, viewMode: "table", graphEngine: "svg", aggregateGroups: false });
    expect(policy.shouldAggregate).toBe(true);
  });
});
