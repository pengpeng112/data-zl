// 186 各任务组行为/源码契约测试（行为优先；源码断言仅锁结构性契约）
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import "./helpers/memoryLocalStorage";
import { createPinia, setActivePinia } from "pinia";

import { useQueryDraftHandoffStore } from "@/store/modules/queryDraftHandoff";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

describe("plan186 W1 工作台", () => {
  it("工作台页面存在且首屏业务请求 ≤5（mine + ops 两个）", () => {
    const page = source("src/views/workbench/index.vue");
    expect(page).toContain("listQualityIssues");
    expect(page).toContain("scope: \"mine\"");
    expect(page).toContain("page_size: 5");
    expect(page).toContain("getOpsRuns");
    // 无权限卡片零请求：条件加载
    expect(page).toMatch(/if \(!canReadIssue\.value\) return;/);
    expect(page).toMatch(/if \(!canViewOps\.value\) return;/);
    const requestCalls = (page.match(/await (listQualityIssues|getOpsRuns)/g) || []).length;
    expect(requestCalls).toBeLessThanOrEqual(5);
  });

  it("空账号有明确说明而非空白/循环", () => {
    const page = source("src/views/workbench/index.vue");
    expect(page).toContain("暂无业务功能权限");
  });
});

describe("plan186 Q1 查询中心页签", () => {
  it("六个页签名称保留且与 URL 双向同步、非法回退", () => {
    const page = source("src/views/query-center/queries/index.vue");
    for (const name of ["list", "runs", "metrics", "products", "board", "ops"]) {
      expect(page).toContain(`name="${name}"`);
    }
    expect(page).toContain("QUERY_TAB_WHITELIST");
    expect(page).toContain("restoreTabFromUrl");
  });

  it("运行详情面板展示 provenance 字段（digest/data_as_of/schema_digest）", () => {
    const panel = source("src/views/query-center/queries/components/RunProvenancePanel.vue");
    for (const field of ["result_digest", "schema_digest", "data_as_of", "safe_parameters_summary"]) {
      expect(panel).toContain(field);
    }
  });
});

describe("plan186 Q2 反馈闭环", () => {
  it("准确性页消费 mine/queue 列表并处理 403 提示", () => {
    const page = source("src/views/query-center/accuracy/index.vue");
    expect(page).toContain("listAiFeedback");
    expect(page).toContain('value="mine"');
    expect(page).toContain('value="queue"');
    expect(page).toContain("审核队列需要 feedback:review 权限");
  });

  it("运行详情后端返回真实 provenance（get_run 扩展）", () => {
    const api = source("../backend/app/api/v1/queries.py");
    for (const field of [
      '"result_digest": r.result_digest',
      '"schema_digest": r.schema_digest',
      '"data_as_of"',
      '"safe_parameters_summary"',
    ]) {
      expect(api).toContain(field);
    }
  });
});

describe("plan186 Q3 AI SQL → 查询草稿", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it("交接 store：入队/一次性消费/过期清空/ID 匹配", () => {
    const store = useQueryDraftHandoffStore();
    const id = store.stage({
      systemCode: "DATA_CENTER",
      sqlText: "SELECT 1 FROM DUAL",
      questionSummary: "示例",
      selectedTables: ["S.T"],
      contextDigest: {},
      risk: {}
    });
    expect(id).toMatch(/^hd-/);
    expect(store.peek(id)?.sqlText).toBe("SELECT 1 FROM DUAL");
    // ID 不匹配不消费
    expect(store.consume("hd-other")).toBeNull();
    // 一次性消费
    const draft = store.consume(id);
    expect(draft?.sqlText).toBe("SELECT 1 FROM DUAL");
    expect(store.consume(id)).toBeNull();
  });

  it("过期草稿（30 分钟）不可消费", () => {
    const store = useQueryDraftHandoffStore();
    const id = store.stage({
      systemCode: "DATA_CENTER",
      sqlText: "SELECT 1",
      questionSummary: "x",
      selectedTables: [],
      contextDigest: {},
      risk: {}
    });
    // 直接改 createdAt 模拟过期
    (store.draft as any).createdAt = Date.now() - 31 * 60 * 1000;
    expect(store.consume(id)).toBeNull();
    expect(store.draft).toBeNull();
  });

  it("AI 页提供带入入口且不自动提交（URL 仅带 id）", () => {
    const ai = source("src/views/asset/ai-sql/index.vue");
    expect(ai).toContain("带入查询中心");
    expect(ai).toContain("handoffToQueryCenter");
    expect(ai).not.toContain("ingestQuery");
    const queries = source("src/views/query-center/queries/index.vue");
    expect(queries).toContain("consumeDraftHandoff");
    expect(queries).toContain("临时草稿已失效");
    // sourceCode 无证据时清空默认值
    expect(queries).toContain('form.source_code = draft.sourceCode || "";');
  });

  it("摄取表单契约字段齐全（不只是内存跳转）", () => {
    const queries = source("src/views/query-center/queries/index.vue");
    for (const field of ["grain", "period_field", "limitations_text", "recipe_refs_text", "parameter_rows"]) {
      expect(queries).toContain(`form.${field}`);
    }
    expect(queries).toContain("parameter_schema = schema");
  });
});

describe("plan186 D2 AI质量分析", () => {
  it("复制完整结构化报告（非仅 summary）", () => {
    const page = source("src/views/asset/ai-quality/index.vue");
    expect(page).toContain("buildFullReportText");
    for (const section of ["根因分析", "噪声判断", "建议", "人工复核状态", "证据摘要", "生成时间"]) {
      expect(page).toContain(section);
    }
    expect(page).toContain("报告生成中");
  });

  it("巡查轮询到终态（3s/10min 上限/卸载停止/不重复提交）", () => {
    const page = source("src/views/asset/ai-quality/index.vue");
    expect(page).toContain("patrolTick");
    expect(page).toContain("PATROL_POLL_TIMEOUT_MS");
    expect(page).toContain("stopPatrolWatch();");
    // 轮询仅 refreshPatrolJobs（查状态），不再调用 runAiPatrol
    const tickBody = page.split("async function patrolTick")[1].split("async function startPatrol")[0];
    expect(tickBody).not.toContain("runAiPatrol");
  });
});

describe("plan186 O1 治理配置页签", () => {
  it("四个页签懒加载（未打开零请求）+ tab 白名单", () => {
    const page = source("src/views/asset/admin/index.vue");
    for (const tab of ['name="tokens"', 'name="owners"', 'name="terms"', 'name="snapshots"']) {
      expect(page).toContain(tab);
    }
    expect(page).toContain("ADMIN_TAB_WHITELIST");
    expect(page).toContain("loadAdminTab");
    // onMounted 只加载当前页签
    expect(page).toMatch(/onMounted\(\(\) => \{[\s\S]{0,200}loadAdminTab\(activeAdminTab\.value\);/);
  });

  it("两类快照分开展示且不混比", () => {
    const page = source("src/views/asset/admin/index.vue");
    expect(page).toContain("资产汇总快照");
    expect(page).toContain("两类快照不可混比");
  });
});

describe("plan186 I1 人员与权限展示", () => {
  it("同步日志页展示双来源账号状态（§4.6.5 字段）", () => {
    const page = source("src/views/identity/sync-logs/index.vue");
    expect(page).toContain("getAccountStates");
    expect(page).toContain("账号启停状态");
    for (const col of ["在职状态", "HIS人员", "HIS账号", "期望状态", "嘉和结果", "无纸化结果"]) {
      expect(page).toContain(col);
    }
  });
});

describe("plan186 A3 隐藏页常驻入口", () => {
  it("元数据变更页提供快照管理/快照对比入口（独立权限）", () => {
    const page = source("src/views/metadata-changes/changes/index.vue");
    expect(page).toContain("v-perms=\"'metadata.snapshot.view'\"");
    expect(page).toContain("v-perms=\"'metadata.diff.view'\"");
    expect(page).toContain("/metadata/snapshots");
    expect(page).toContain("/metadata/diff");
  });

  it("关系复核/配方页提供验证统计与 AI 上下文入口", () => {
    const review = source("src/views/asset/relation-review/index.vue");
    expect(review).toContain("v-perms=\"'asset.relation.view'\"");
    expect(review).toContain("/asset/relation-rates");
    const recipes = source("src/views/asset/relation-recipes/index.vue");
    expect(recipes).toContain("v-perms=\"'asset.ai_context.view'\"");
    expect(recipes).toContain("/asset/ai-context");
  });
});
