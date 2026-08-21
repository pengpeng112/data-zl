import { describe, expect, it } from "vitest";
import { buildGraphNodeKey, filterOneHopNeighbors, filterTwoHopNeighbors, filterNeighborsByDepth, findGraphPath, formatGraphNodeLabel, graphEdgeStyle, graphNeighborDirectionLabel, graphNodeStyle, graphNodeVisualStyle, isCandidateNode, isCoreFactNode, isDeferredEdge, isDeferredNode, isDimensionNode, isExcludedNode, isHighConfidenceEdge, isOneHopDepth, isTwoHopDepth, isSamplePassEdge, linkAdjacentOverviewNodes, normalizeGraphNeighborDirection, matchesTableSearch, transformGraphData } from "@/views/asset/graph/graphTransform";
import type { GraphData } from "@/api/asset";
import { normalizeGraphData } from "@/views/asset/graph/graphNormalize";
import { decideGraphLoadPolicy } from "@/views/asset/graph/graphLoadPolicy";

describe("graphTransform", () => {
  it("builds system aggregation key from systemCode", () => {
    expect(buildGraphNodeKey({ id: "MEDREC.PAT_VISIT", label: "PAT_VISIT", system_code: "HIS", source_code: "ODS" }, "system")).toBe("system:HIS");
  });

  it("falls back to source for system aggregation key", () => {
    expect(buildGraphNodeKey({ id: "ODS.PAT_VISIT", label: "PAT_VISIT", source_code: "ODS" }, "system")).toBe("system:ODS");
  });


  it("builds schema aggregation key from systemCode and schemaName", () => {
    expect(buildGraphNodeKey({ id: "MEDREC.PAT_VISIT", label: "PAT_VISIT", system_code: "HIS", schema_name: "MEDREC" }, "schema")).toBe("schema:HIS:MEDREC");
  });

  it("falls back to namespace/category for schema aggregation key", () => {
    expect(buildGraphNodeKey({ id: "ODS.PAT_VISIT", label: "PAT_VISIT", source_code: "ODS", namespace_name: "HIS" }, "schema")).toBe("schema:ODS:HIS");
    expect(buildGraphNodeKey({ id: "LAB.RESULT", label: "RESULT", source: "HIS", category: "LAB" }, "schema")).toBe("schema:HIS:LAB");
  });

  it("builds domain aggregation key from systemCode and businessDomain", () => {
    expect(buildGraphNodeKey({ id: "LAB.LAB_TEST_MASTER", label: "LAB_TEST_MASTER", system_code: "HIS", business_domain: "检验", domain: "医技" }, "domain")).toBe("domain:HIS:检验");
  });

  it("falls back to domain for domain aggregation key", () => {
    expect(buildGraphNodeKey({ id: "DRUG_USER.STOCK", label: "STOCK", system_code: "HIS", domain: "药品" }, "domain")).toBe("domain:HIS:药品");
  });

  it("builds table aggregation key from systemCode schemaName and tableName", () => {
    expect(buildGraphNodeKey({ id: "MEDREC.PAT_VISIT", label: "PAT_VISIT", system_code: "HIS", schema_name: "MEDREC", table_name: "PAT_VISIT" }, "table")).toBe("table:HIS:MEDREC:PAT_VISIT");
  });

  it("falls back to table id suffix for table aggregation key", () => {
    expect(buildGraphNodeKey({ id: "EXAM.EXAM_MASTER", label: "EXAM_MASTER", system_code: "HIS", schema_name: "EXAM" }, "table")).toBe("table:HIS:EXAM:EXAM_MASTER");
  });

  it("wraps system and schema names instead of truncating", () => {
    expect(formatGraphNodeLabel({
      display_id: "Docare手术麻醉",
      is_aggregate: true,
      category: "system",
      count: 646
    })).toBe("Docare\n手术麻醉\n(646)");
    expect(formatGraphNodeLabel({
      display_id: "新电子病历区（jhemr）",
      is_aggregate: true,
      category: "schema",
      count: 993
    })).toBe("新电子病历区\njhemr\n(993)");
    const tableLabel = formatGraphNodeLabel({
      table_name_cn: "诊断手术-字典类-CCHI字典表",
      table_name: "cchi_dict",
      category: "table",
      count: 1
    });
    expect(tableLabel).toBe("诊断手术\n字典类\nCCHI字典表\ncchi_dict");
    expect(formatGraphNodeLabel({
      table_name_cn: "新电子病历区数据表",
      table_name: "dc_cda_doctype",
      category: "table",
      count: 1
    })).toBe("新电子病历区\n数据表\ndc_cda_doctype");
    expect(formatGraphNodeLabel({
      table_name_cn: "病案首页-业务类-输血信息",
      table_name: "blood_transfusion",
      category: "table"
    })).toBe("病案首页\n业务类\n输血信息\nblood_transfusion");
    expect(formatGraphNodeLabel({
      table_name_cn: "病案首页-业务类-新生儿记录",
      table_name: "newborn_record",
      category: "table"
    })).toBe("病案首页\n业务类\n新生儿记录\nnewborn_record");
    expect(formatGraphNodeLabel({
      table_name_cn: "病案首页-业务类-入院记录",
      table_name: "admission_record",
      category: "table"
    })).toBe("病案首页\n业务类\n入院记录\nadmission_record");
  });

  it("links isolated top-level systems into a ring", () => {
    const nodes = [{ id: "A" }, { id: "B" }, { id: "C" }];
    const linked = linkAdjacentOverviewNodes(nodes, [{ id: "e1", source: "A", target: "B", label: "1 条关系" }]);
    expect(linked.some(edge => edge.source === "B" && edge.target === "C")).toBe(true);
    expect(linked.some(edge => edge.source === "C" && edge.target === "A")).toBe(true);
    expect(linked.filter(edge => edge.source === "A" && edge.target === "B")).toHaveLength(1);
  });

  it("returns node style by graph node type", () => {
    expect(graphNodeStyle("system").fill).toBe("#d96a1a");
    expect(graphNodeStyle("schema").fill).toBe("#5a9628");
    expect(graphNodeStyle("domain").shape).toBe("ellipse");
    expect(graphNodeStyle("table").shape).toBe("roundRect");
    expect(graphNodeStyle("field").shape).toBe("roundRect");
    expect(graphNodeVisualStyle({ category: "field", object_type: "column" }).fill).toBe("#5a8f32");
  });
  it("highlights core fact table nodes by table role", () => {
    expect(isCoreFactNode({ type: "table", role: "核心事实表" })).toBe(true);
    expect(isCoreFactNode({ table_role: "core_fact" })).toBe(true);
    expect(graphNodeVisualStyle({ type: "table", role: "核心事实表" }).fill).toBe("#d4a017");
    expect(graphNodeVisualStyle({ type: "table", role: "核心事实表" }).stroke).toBe("#8a6a0a");
    expect(graphNodeVisualStyle({ type: "table", role: "普通表" }).fill).toBe("#2f7eb8");
  });
  it("highlights dictionary and dimension table nodes by table role", () => {
    expect(isDimensionNode({ type: "table", role: "字典表" })).toBe(true);
    expect(isDimensionNode({ type: "table", role: "维表" })).toBe(true);
    expect(isDimensionNode({ table_role: "dimension" })).toBe(true);
    expect(isDimensionNode({ table_role: "dict" })).toBe(true);
    expect(graphNodeVisualStyle({ type: "table", role: "字典/维表" }).fill).toBe("#2a8f99");
    expect(graphNodeVisualStyle({ type: "table", role: "字典/维表" }).stroke).toBe("#16565c");
  });
  it("dims excluded table nodes by status or table role", () => {
    expect(isExcludedNode({ type: "table", role: "排除表" })).toBe(true);
    expect(isExcludedNode({ include_status: "excluded" })).toBe(true);
    expect(isExcludedNode({ status: "exclude" })).toBe(true);
    expect(graphNodeVisualStyle({ type: "table", role: "排除表" }).fill).toBe("#f1f5f9");
    expect(graphNodeVisualStyle({ type: "table", role: "核心事实表", status: "excluded" }).fill).toBe("#f1f5f9");
  });
  it("highlights candidate table nodes by status or table role", () => {
    expect(isCandidateNode({ type: "table", role: "候选表" })).toBe(true);
    expect(isCandidateNode({ include_status: "pending" })).toBe(true);
    expect(isCandidateNode({ status: "candidate" })).toBe(true);
    expect(graphNodeVisualStyle({ type: "table", role: "候选表" }).fill).toBe("#d4891d");
    expect(graphNodeVisualStyle({ type: "table", role: "候选表" }).stroke).toBe("#8a5310");
    expect(graphNodeVisualStyle({ type: "table", role: "候选表", status: "excluded" }).fill).toBe("#f1f5f9");
  });
  it("marks D-class deferred relation nodes with dashed purple style", () => {
    expect(isDeferredNode({ type: "table", role: "D类延后关系节点" })).toBe(true);
    expect(isDeferredNode({ status: "待分析" })).toBe(true);
    expect(isDeferredNode({ include_status: "deferred" })).toBe(true);
    expect(graphNodeVisualStyle({ type: "table", role: "D类延后关系节点" }).fill).toBe("#8b6cc7");
    expect(graphNodeVisualStyle({ type: "table", role: "D类延后关系节点" }).lineDash).toEqual([8, 5]);
    expect(graphNodeVisualStyle({ type: "table", role: "D类延后关系节点", status: "excluded" }).fill).toBe("#f1f5f9");
  });
  it("detects high-confidence relationship edges", () => {
    expect(isHighConfidenceEdge({ confidence: "A" })).toBe(true);
    expect(isHighConfidenceEdge({ validationStatus: "verified" })).toBe(true);
    expect(isHighConfidenceEdge({ validation_status: "sample_pass" })).toBe(true);
    expect(isHighConfidenceEdge({ confidence: "D" })).toBe(false);
    expect(isHighConfidenceEdge({ relationType: "candidate" })).toBe(false);
    expect(isHighConfidenceEdge({ relationType: "dependency", confidence: "A" })).toBe(false);
  });
  it("detects sample_pass relationship edges", () => {
    expect(isSamplePassEdge({ validationStatus: "sample_pass" })).toBe(true);
    expect(isSamplePassEdge({ validation_status: "sample_pass" })).toBe(true);
    expect(isSamplePassEdge({ validationStatus: "verified" })).toBe(false);
    expect(graphEdgeStyle({ validationStatus: "sample_pass" }).stroke).toBe("#58a05c");
    expect(graphEdgeStyle({ validationStatus: "sample_pass" }).lineWidth).toBe(2.6);
  });
  it("detects deferred relationship edges", () => {
    expect(isDeferredEdge({ deferred: true })).toBe(true);
    expect(isDeferredEdge({ is_deferred: true })).toBe(true);
    expect(isDeferredEdge({ confidence: "D" })).toBe(true);
    expect(isDeferredEdge({ relationType: "candidate" })).toBe(true);
    expect(isDeferredEdge({ confidence: "A" })).toBe(false);
    expect(graphEdgeStyle({ deferred: true }).stroke).toBe("#9b7ec8");
    expect(graphEdgeStyle({ deferred: true }).lineDash).toEqual([8, 5]);
  });
  it("matches table search by full name table name Chinese name and context", () => {
    const node = {
      id: "MEDREC.PAT_VISIT",
      label: "PAT_VISIT",
      system_code: "HIS",
      source_code: "hisuser",
      schema_name: "MEDREC",
      table_name: "PAT_VISIT",
      table_name_cn: "患者就诊记录",
      business_domain: "就诊"
    };
    expect(matchesTableSearch(node, "MEDREC.PAT_VISIT")).toBe(true);
    expect(matchesTableSearch(node, "pat_visit")).toBe(true);
    expect(matchesTableSearch(node, "患者就诊")).toBe(true);
    expect(matchesTableSearch(node, "hisuser")).toBe(true);
    expect(matchesTableSearch(node, "费用")).toBe(false);
  });
  it("returns edge style by relation confidence and deferred layer", () => {
    expect(graphEdgeStyle({ confidence: "A" }).stroke).toBe("#3f7cac");
    expect(graphEdgeStyle({ validationStatus: "sample_pass" }).stroke).toBe("#58a05c");
    expect(graphEdgeStyle({ confidence: "B" }).stroke).toBe("#dd8b2e");
    expect(graphEdgeStyle({ confidence: "D" }).stroke).toBe("#9b7ec8");
    expect(graphEdgeStyle({ confidence: "D" }).stroke).not.toBe(graphEdgeStyle({ confidence: "A" }).stroke);
    expect(graphEdgeStyle({ confidence: "D" }).lineDash).toEqual([8, 5]);
    expect(graphEdgeStyle({ relationType: "dependency" }).lineDash).toEqual([2, 5]);
  });

  it("hides D-class deferred edges unless the review layer is explicitly enabled", () => {
    const nodes = [
      { id: "A", label: "A" },
      { id: "B", label: "B" },
      { id: "C", label: "C" }
    ];
    const edges = [
      { id: "formal", source: "A", target: "B", confidence: "A" },
      { id: "deferred", source: "A", target: "C", confidence: "D", is_deferred: true }
    ];
    const hidden = normalizeGraphData(nodes, edges, { groupBy: "schema", showReviewLayer: false });
    expect(hidden.edges.map(edge => edge.id)).toEqual(["formal"]);
    expect(hidden.reviewHiddenCount).toBe(1);
    const visible = normalizeGraphData(nodes, edges, { groupBy: "schema", showReviewLayer: true });
    expect(visible.edges.map(edge => edge.id).sort()).toEqual(["deferred", "formal"]);
    expect(visible.edges.find(edge => edge.id === "deferred")?.lineStyle.type).toBe("dashed");
    expect(visible.edges.find(edge => edge.id === "deferred")?.lineStyle.color).toBe("#9b7ec8");
  });

  it("keeps isolated overview systems when a single cross-system edge exists", () => {
    const nodes = [
      { id: "overview|system|DATA_CENTER", label: "数据中心", is_aggregate: true, category: "system", system_code: "DATA_CENTER" },
      { id: "overview|system|DOCARE", label: "Docare手术麻醉", is_aggregate: true, category: "system", system_code: "DOCARE" },
      { id: "overview|system|HIS_SOURCE", label: "HIS", is_aggregate: true, category: "system", system_code: "HIS_SOURCE" },
      { id: "overview|system|LIS_SOURCE", label: "LIS", is_aggregate: true, category: "system", system_code: "LIS_SOURCE" }
    ];
    const edges = [
      { id: "e1", source: "overview|system|DATA_CENTER", target: "overview|system|DOCARE", relation_type: "formal" }
    ];
    const normalized = normalizeGraphData(nodes as any, edges as any, { groupBy: "system" });
    expect(normalized.nodes.map((n: any) => n.id).sort()).toEqual([
      "overview|system|DATA_CENTER",
      "overview|system|DOCARE",
      "overview|system|HIS_SOURCE",
      "overview|system|LIS_SOURCE"
    ]);
    expect(normalized.edges).toHaveLength(1);
  });

  it("uses canonical system and connection labels for graph groups while keeping physical keys", () => {
    const nodes = [
      {
        id: "DATA_CENTER|docare_oracle|MEDSURGERY|MED_OPERATION_MASTER",
        label: "MED_OPERATION_MASTER",
        system_code: "DATA_CENTER",
        source_code: "docare_oracle",
        schema_name: "MEDSURGERY",
        table_name: "MED_OPERATION_MASTER"
      }
    ];
    const bySystem = normalizeGraphData(nodes, [], {
      groupBy: "system",
      systemNames: { DATA_CENTER: "数据中心" },
      sourceNames: { docare_oracle: "Docare手术麻醉连接" }
    });
    expect(bySystem.topGroups[0]?.name).toBe("数据中心");
    expect(bySystem.nodes[0]?.id).toBe(nodes[0].id);

    const bySource = normalizeGraphData(nodes, [], {
      groupBy: "source",
      systemNames: { DATA_CENTER: "数据中心" },
      sourceNames: { docare_oracle: "Docare手术麻醉连接" }
    });
    expect(bySource.topGroups[0]?.name).toBe("Docare手术麻醉连接");
  });
  it("normalizes and labels upstream downstream direction switches", () => {
    expect(normalizeGraphNeighborDirection("in")).toBe("in");
    expect(normalizeGraphNeighborDirection("out")).toBe("out");
    expect(normalizeGraphNeighborDirection("invalid")).toBe("both");
    expect(graphNeighborDirectionLabel("in")).toBe("只看上游");
    expect(graphNeighborDirectionLabel("out")).toBe("只看下游");
    expect(graphNeighborDirectionLabel("both")).toBe("双向");
  });

  it("filters one-hop neighbors by edge direction", () => {
    const data: GraphData = {
      nodes: [
        { id: "A", label: "A" },
        { id: "B", label: "B" },
        { id: "C", label: "C" },
        { id: "D", label: "D" }
      ],
      edges: [
        { id: "in", source: "B", target: "A" },
        { id: "out", source: "A", target: "C" },
        { id: "other", source: "C", target: "D" }
      ]
    };
    expect(isOneHopDepth(1)).toBe(true);
    expect(isOneHopDepth(2)).toBe(false);
    expect(filterOneHopNeighbors(data, "A", "in").edges.map(edge => edge.id)).toEqual(["in"]);
    expect(filterOneHopNeighbors(data, "A", "out").edges.map(edge => edge.id)).toEqual(["out"]);
    expect(filterOneHopNeighbors(data, "A", "both").nodes.map(node => node.id).sort()).toEqual(["A", "B", "C"]);
  });

  it("filters two-hop neighbors by traversal direction", () => {
    const data: GraphData = {
      nodes: [
        { id: "A", label: "A" },
        { id: "B", label: "B" },
        { id: "C", label: "C" },
        { id: "D", label: "D" },
        { id: "E", label: "E" },
        { id: "X", label: "X" }
      ],
      edges: [
        { id: "up1", source: "B", target: "A" },
        { id: "up2", source: "D", target: "B" },
        { id: "down1", source: "A", target: "C" },
        { id: "down2", source: "C", target: "E" },
        { id: "outside", source: "X", target: "D" }
      ]
    };
    expect(isTwoHopDepth(2)).toBe(true);
    expect(isTwoHopDepth(1)).toBe(false);
    expect(filterTwoHopNeighbors(data, "A", "in").edges.map(edge => edge.id)).toEqual(["up1", "up2"]);
    expect(filterTwoHopNeighbors(data, "A", "out").edges.map(edge => edge.id)).toEqual(["down1", "down2"]);
    expect(filterTwoHopNeighbors(data, "A", "both").nodes.map(node => node.id).sort()).toEqual(["A", "B", "C", "D", "E"]);
    expect(filterNeighborsByDepth(data, "A", 0).edges).toEqual([]);
  });
  it("finds the shortest path for path highlighting", () => {
    const data: GraphData = {
      nodes: [],
      edges: [
        { id: "ab", source: "A", target: "B" },
        { id: "bc", source: "B", target: "C" },
        { id: "cd", source: "C", target: "D" },
        { id: "ae", source: "A", target: "E" },
        { id: "ed", source: "E", target: "D" },
        { id: "side", source: "B", target: "X" }
      ]
    };
    expect(findGraphPath(data, "A", "D")).toEqual({ nodeIds: ["A", "E", "D"], edgeIds: ["ae", "ed"] });
    expect(findGraphPath(data, "A", "A")).toEqual({ nodeIds: ["A"], edgeIds: [] });
    expect(findGraphPath(data, "A", "Z")).toEqual({ nodeIds: [], edgeIds: [] });
  });

  it("highlights only the selected path during graph normalization", () => {
    const nodes = ["A", "B", "C", "D"].map(id => ({ id, label: id }));
    const edges = [
      { id: "ab", source: "A", target: "B", confidence: "A" },
      { id: "bc", source: "B", target: "C", confidence: "A" },
      { id: "bd", source: "B", target: "D", confidence: "A" }
    ];
    const normalized = normalizeGraphData(nodes, edges, { groupBy: "schema", centerTable: "A", selectedNodeId: "C" });
    expect(normalized.edges.find(edge => edge.id === "ab")?.lineStyle.opacity).toBe(1);
    expect(normalized.edges.find(edge => edge.id === "bc")?.lineStyle.opacity).toBe(1);
    expect(normalized.edges.find(edge => edge.id === "bd")?.lineStyle.opacity).toBe(0.1);
    expect(normalized.nodes.find(node => node.id === "D")?.itemStyle.opacity).toBe(0.22);
  });

  it("aggregates tables into system nodes", () => {
    const data: GraphData = {
      nodes: [
        { id: "MEDREC.PAT_VISIT", label: "PAT_VISIT", system_code: "HIS", schema_name: "MEDREC", table_name: "PAT_VISIT" },
        { id: "LAB.LAB_TEST_MASTER", label: "LAB_TEST_MASTER", system_code: "HIS", schema_name: "LAB", table_name: "LAB_TEST_MASTER" },
        { id: "PACS.EXAM", label: "EXAM", system_code: "PACS", schema_name: "PACS", table_name: "EXAM" }
      ],
      edges: [
        { id: "e1", source: "MEDREC.PAT_VISIT", target: "LAB.LAB_TEST_MASTER", relation_type: "formal", confidence: "A" },
        { id: "e2", source: "MEDREC.PAT_VISIT", target: "PACS.EXAM", relation_type: "formal", confidence: "A" },
        { id: "e3", source: "LAB.LAB_TEST_MASTER", target: "PACS.EXAM", relation_type: "formal", confidence: "A" }
      ]
    };
    const result = transformGraphData(data, { level: "system" });
    expect(result.nodes.map(node => node.id).sort()).toEqual(["system:HIS", "system:PACS"]);
    expect(result.edges).toHaveLength(1);
    expect(result.edges[0].source).toBe("system:HIS");
    expect(result.edges[0].target).toBe("system:PACS");
    expect(result.edges[0].sourceEdges).toHaveLength(2);
  });
});
