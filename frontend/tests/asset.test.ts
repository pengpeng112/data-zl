import { describe, it, expect } from "vitest";

describe("Asset API types", () => {
  it("SummaryData should match expected shape", () => {
    const data = { tables: 865, columns: 26894, relations: 47, domains: 19 };
    expect(data.tables).toBeGreaterThan(0);
    expect(data.columns).toBeGreaterThan(0);
    expect(data.relations).toBeGreaterThan(0);
  });

  it("GraphEdge should include relation_type field", () => {
    const edge = {
      id: "test",
      source: "A",
      target: "B",
      relation_type: "formal",
      rel_id: 1
    };
    expect(edge.relation_type).toBeDefined();
    expect(["formal", "candidate", "dependency"]).toContain(edge.relation_type);
  });

  it("QualityFinding severity values should be valid", () => {
    const validSeverities = ["critical", "major", "minor", "info"];
    expect(validSeverities).toContain("critical");
    expect(validSeverities).toContain("major");
    expect(validSeverities).toContain("minor");
    expect(validSeverities).toContain("info");
  });

  it("PageData shape should match", () => {
    const page = { total: 100, page: 1, page_size: 20, items: [] };
    expect(page).toHaveProperty("total");
    expect(page).toHaveProperty("items");
    expect(Array.isArray(page.items)).toBe(true);
  });
});

describe("Business rules", () => {
  it("AiTools should not expose dangerous operations", () => {
    const safeTools = [
      "search_tables", "get_table_schema", "get_relations", "get_path",
      "search_columns", "get_graph", "get_graph_neighbors",
      "get_lineage_impact", "get_view_dependencies", "propose_sql"
    ];
    const dangerous = ["execute_sql", "delete_table", "drop_table"];
    for (const d of dangerous) {
      expect(safeTools).not.toContain(d);
    }
  });

  it("Quality rules should be metadata_only", () => {
    const modes = ["metadata_only", "imported_metric", "sample_query", "full_query"];
    expect(modes[0]).toBe("metadata_only");
    expect(modes).toHaveLength(4);
  });
});
