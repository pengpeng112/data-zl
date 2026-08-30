/**
 * 146 R5 批（163 号计划）：E2–E8/E10 剩余子项的针对性测试。
 * 纯函数直接测行为；页面交互按仓库既有约定做源码契约断言。
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { shouldRenderGraphMeta, truncateGraphMeta } from "@/views/asset/components/graphNodeMeta";
import { aiQualityJobStatusLabel } from "@/views/asset/ai-quality/contracts";
import {
  buildSyncDiffFieldDiff,
  runSerialBatch,
  syncDiffStatusLabel,
  loadSyncDiffTotals
} from "@/composables/useSyncDiffPanel";
import {
  findingStatusLabel,
  formatPercent,
  passRateClass,
  runStatusLabel,
  severityLabel
} from "@/views/asset/quality/qualityContracts";

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("146 R5 E2 graph", () => {
  it("truncates long field node meta with an ellipsis and keeps short text intact", () => {
    expect(truncateGraphMeta("VARCHAR2(64) · PK")).toBe("VARCHAR2(64) · PK");
    const long = "VARCHAR2(128) · 关系键 · 超长说明文本需要被截断保证画布可读性";
    const cut = truncateGraphMeta(long);
    expect(cut.length).toBeLessThanOrEqual(26);
    expect(cut.endsWith("…")).toBe(true);
    expect(truncateGraphMeta("")).toBe("");
    expect(truncateGraphMeta(null)).toBe("");
    expect(shouldRenderGraphMeta("  ")).toBe(false);
    expect(shouldRenderGraphMeta("NUMBER · PK")).toBe(true);
  });

  it("RelationGraph renders node.meta as the field node subtitle with truncation", () => {
    const graph = source("src/views/asset/components/RelationGraph.vue");
    expect(graph).toContain("shouldRenderGraphMeta(node.meta)");
    expect(graph).toContain("truncateGraphMeta(node.meta)");
    expect(graph).toContain('class="node-meta"');
  });

  it("GraphToolbar collapses stats for ordinary users and expands for governance roles", () => {
    const toolbar = source("src/views/asset/components/GraphToolbar.vue");
    expect(toolbar).toContain("statsExpanded = ref(isGovernanceUser())");
    expect(toolbar).toContain('v-show="statsExpanded"');
    expect(toolbar).toContain("展开统计");
    const roles = source("src/utils/userRoles.ts");
    expect(roles).toContain("endsWith(\"_admin\")");
    expect(roles).not.toContain("@/store");
  });

  it("AdvancedRelationGraph only destroys the instance on preset/layout-mode class change", () => {
    const advanced = source("src/views/asset/components/AdvancedRelationGraph.vue");
    expect(advanced).toContain('graphCreatedAt !== (wantsLayout ? "engine-layout" : "preset")');
    expect(advanced).not.toContain("if (usesPresetPositions() && graph)");
  });
});

describe("146 R5 E3 ai-quality", () => {
  it("labels job statuses in Chinese", () => {
    expect(aiQualityJobStatusLabel("succeeded")).toBe("已完成");
    expect(aiQualityJobStatusLabel("running")).toBe("分析中");
    expect(aiQualityJobStatusLabel("failed")).toBe("失败");
    expect(aiQualityJobStatusLabel("blocked")).toBe("已拦截");
    expect(aiQualityJobStatusLabel("")).toBe("-");
  });

  it("uses server pagination with cross-page selection kept via reserve-selection", () => {
    const page = source("src/views/asset/ai-quality/index.vue");
    expect(page).toContain("findingsTotal.value = data.total || 0");
    expect(page).toContain("jobsTotal.value = data.total || 0");
    expect(page).toContain("reserve-selection");
    expect(page).toContain("selectedFindingRows.value = rows");
    expect(page).toContain("aiQualityJobStatusLabel(row.status)");
    expect(page).not.toContain('row.status === "succeeded" ? "已完成" : row.status');
  });
});

describe("146 R5 E4 admin", () => {
  it("enforces owner/term form validation before save", () => {
    const admin = source("src/views/asset/admin/index.vue");
    expect(admin).toContain("ownerRules");
    expect(admin).toContain("termRules");
    expect(admin).toContain("ownerFormRef.value?.validate()");
    expect(admin).toContain("termFormRef.value?.validate()");
    expect(admin).toContain("SCHEMA.TABLE 形态");
  });

  it("selects snapshots for comparison via checkboxes limited to two", () => {
    const admin = source("src/views/asset/admin/index.vue");
    expect(admin).toContain("onSnapshotSelectionChange");
    expect(admin).toContain("toggleRowSelection(last, false)");
    expect(admin).toContain("最多勾选两个快照进行对比");
  });

  it("removes internal plan numbering (E12 comments) from the admin page", () => {
    const admin = source("src/views/asset/admin/index.vue");
    expect(admin).not.toContain("E12");
  });
});

describe("146 R5 E5 tables", () => {
  it("loads schema tables incrementally with a load-more tree node", () => {
    const tables = source("src/views/asset/tables/index.vue");
    expect(tables).toContain("SCHEMA_TABLES_PAGE_SIZE");
    expect(tables).toContain("loadmore:");
    expect(tables).toContain("加载更多（已加载");
    expect(tables).toContain("loadSchemaTables(schemaNode, true)");
    expect(tables).not.toContain("page_size: 500");
  });

  it("offers backend-driven domain candidates and a clear-filters action", () => {
    const tables = source("src/views/asset/tables/index.vue");
    expect(tables).toContain("loadDomainCandidates");
    expect(tables).toContain("getGraphOptions()");
    expect(tables).toContain("clearFilters");
    expect(tables).toContain("allow-create");
  });
});

describe("146 R5 E6 identity sync-diffs", () => {
  it("loads sources dynamically, shows field diff, and consolidates actions", () => {
    const page = source("src/views/identity/sync-diffs/index.vue");
    expect(page).toContain('import { listSources } from "@/api/asset"');
    expect(page).toContain("loadSourceOptions");
    expect(page).toContain("buildSyncDiffFieldDiff");
    expect(page).toContain("detailFieldDiff");
    expect(page).toContain("更多同步动作");
    expect(page).toContain("runSyncAction");
    // 161 P2-2 的 doSync catch 不得回退
    const doSyncBody = page.slice(page.indexOf("async function doSync"), page.indexOf("async function doHisSync"));
    expect(doSyncBody).toContain("extractErrorDetail");
  });
});

describe("146 R5 E7 ops", () => {
  it("polls runs silently while a run is executing with cap and cleanup", () => {
    const runs = source("src/views/ops/runs/index.vue");
    expect(runs).toContain("scheduleExecutingPoll");
    expect(runs).toContain("EXECUTING_POLL_MAX_MS");
    expect(runs).toContain("onBeforeUnmount(stopExecutingPoll)");
    expect(runs).toContain("approval_status === \"executing\"");
  });

  it("shows audit before/after in a frontend drawer", () => {
    const audit = source("src/views/ops/audit/index.vue");
    expect(audit).toContain("openAuditDetail");
    expect(audit).toContain("formatJsonField(detailRow.before_data)");
    expect(audit).toContain("ReDetailDrawer");
  });
});

describe("146 R5 E8 dict", () => {
  it("dict sync-diffs gains detail drawer, serial batch, note prompt and full summary", () => {
    const page = source("src/views/dict/sync-diffs/index.vue");
    expect(page).toContain("openDetail(row)");
    expect(page).toContain("batchSetStatus");
    expect(page).toContain("promptNote");
    expect(page).toContain("loadSyncDiffTotals");
    expect(page).toContain('from "@/composables/useSyncDiffPanel"');
    // 161 P2-2 的 doSync catch 不得回退
    expect(page).toContain("extractErrorDetail(error, \"医学编码同步失败\")");
  });

  it("mappings gains column config, readable blanks, option cache and elastic height", () => {
    const page = source("src/views/dict/mappings/index.vue");
    expect(page).toContain("visibleColumnGroups");
    expect(page).toContain("blankFormatter");
    expect(page).toContain("optionsCache");
    expect(page).toContain(":height=\"tableHeight\"");
    expect(page).toContain("请先完善必填项");
  });

  it("medical push wizard gains rules alert, dynamic targets, cancel handling and category", () => {
    const wizard = source("src/views/dict/medical/components/PushWizard.vue");
    expect(wizard).toContain("下发规则");
    expect(wizard).toContain("loadSystemOptions");
    expect(wizard).toContain('categoryCode = ref<"diagnosis" | "operation">');
    expect(wizard).toContain('.catch(() => null)');
    expect(wizard).toContain("extractErrorDetail");
  });

  it("medical page auto-expands code sets, resolves push source codes dynamically and drops the enabled dead field", () => {
    const page = source("src/views/dict/medical/index.vue");
    expect(page).toContain("openCodeSetItems");
    expect(page).toContain("toggleRowExpansion");
    expect(page).toContain("loadPushSourceCodes");
    expect(page).toContain("暂无编码体系：请先在「导入审核」完成诊断/手术维护表导入");
    expect(page).not.toContain("enabled: true");
    expect(page).not.toContain("his_source_code: \"his_source_10_10_10_15\"");
  });
});

describe("146 R5 E10 asset", () => {
  it("quality page extracts shared contracts and a shared check-runs table", () => {
    const page = source("src/views/asset/quality/index.vue");
    expect(page.match(/<CheckRunsTable/g)?.length).toBe(2);
    expect(page).toContain('from "@/views/asset/quality/qualityContracts"');
    const component = source("src/views/asset/quality/CheckRunsTable.vue");
    expect(component).toContain("showFailedReason");
  });

  it("quality shared helpers behave as before the split", () => {
    expect(runStatusLabel("success")).toBe("成功");
    expect(severityLabel("critical")).toBe("严重");
    expect(findingStatusLabel("open")).toBe("待处理");
    expect(formatPercent(null)).toBe("-");
    expect(passRateClass(96)).toBe("metric-accent");
  });

  it("lineage surfaces real error states with retry for impact and dependencies", () => {
    const lineage = source("src/views/asset/lineage/index.vue");
    expect(lineage).toContain("impactError");
    expect(lineage).toContain("depsError");
    expect(lineage).toContain('@retry="runImpact"');
    expect(lineage).toContain('@retry="loadDeps"');
  });

  it("ai-context syncs selection with tags and fixes export/copy/download", () => {
    const page = source("src/views/asset/ai-context/index.vue");
    expect(page).toContain("ctxRowKey");
    expect(page).toContain("reserve-selection");
    expect(page).toContain("searchTableRef.value?.toggleRowSelection?.(row, false)");
    expect(page).toContain("document.body.appendChild(a)");
    expect(page).toContain("剪贴板不可用");
  });

  it("overview and welcome refine failure states", () => {
    const overview = source("src/views/asset/overview/index.vue");
    expect(overview).toContain("summaryError");
    expect(overview).toContain("重试汇总");
    const welcome = source("src/views/welcome/index.vue");
    expect(welcome).toContain("加载失败，请点右上角刷新重试");
  });
});

describe("146 R5 shared sync-diff panel", () => {
  it("builds field-level diff with changed flags", () => {
    const diff = buildSyncDiffFieldDiff(
      { sex: "M", phone: "13800000000", extra: { a: 1 } },
      { sex: "M", phone: "13911111111" }
    );
    const byField = Object.fromEntries(diff.map(row => [row.field, row]));
    expect(byField.sex.changed).toBe(false);
    expect(byField.phone.changed).toBe(true);
    expect(byField.phone.after).toBe("13911111111");
    expect(byField.extra.changed).toBe(true);
    expect(byField.extra.before).toBe('{"a":1}');
    expect(byField.extra.after).toBe("（无）");
  });

  it("runs serial batches and summarizes partial failures instead of aborting", async () => {
    const action = vi.fn(async (item: number) => {
      if (item === 2) throw new Error("row 2 rejected");
    });
    const result = await runSerialBatch([1, 2, 3], action);
    expect(result.done).toBe(2);
    expect(result.failed).toBe(1);
    expect(result.lastError).toContain("row 2 rejected");
    expect(action).toHaveBeenCalledTimes(3);
  });

  it("loads full totals per status and marks unknown on failure", async () => {
    const totals = await loadSyncDiffTotals(async params => {
      if (params.status === "ignored") throw new Error("boom");
      return { total: params.status === "open" ? 7 : 3 };
    });
    expect(totals).toEqual({ open: 7, resolved: 3, ignored: -1 });
    expect(syncDiffStatusLabel("open")).toBe("未处理");
  });
});
