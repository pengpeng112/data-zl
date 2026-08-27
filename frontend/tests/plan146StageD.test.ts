import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { describe, expect, it } from "vitest";
import ReEmptyState from "@/components/ReEmptyState/index.vue";
import { extractErrorDetail, maskSensitiveText } from "@/utils/errorMessage";
import { formatNumber, formatTime, nullableLabel } from "@/utils/format";
import {
  accountStatusLabel,
  OPS_RUN_SUCCESS_TERMINAL,
  opsRunStatusLabel,
  qualitySeverityLabel,
  relationValidationLabel
} from "@/constants/labels";

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("146 stage D1 empty/error states", () => {
  it("ReEmptyState renders variants and emits retry", async () => {
    const empty = mount(ReEmptyState, { props: { title: "暂无数据" } });
    expect(empty.text()).toContain("暂无数据");
    expect(empty.find(".is-error").exists()).toBe(false);

    const error = mount(ReEmptyState, {
      props: { variant: "error", retryable: true, description: "请求失败" },
      global: { plugins: [ElementPlus] }
    });
    expect(error.find(".is-error").exists()).toBe(true);
    expect(error.text()).toContain("请求失败");
    await error.find(".empty-action button").trigger("click");
    expect(error.emitted("retry")).toHaveLength(1);

    const custom = mount(ReEmptyState, {
      props: { variant: "error" },
      slots: { action: "<button id='custom'>自定义</button>" },
      global: { plugins: [ElementPlus] }
    });
    expect(custom.find("#custom").exists()).toBe(true);
    expect(custom.findAll("button")).toHaveLength(1);
  });

  it("extracts error details in priority order and masks secrets", () => {
    expect(extractErrorDetail({ response: { data: { detail: "role_code not found" } } })).toBe("role_code not found");
    expect(extractErrorDetail({ response: { data: { message: "服务暂不可用" } } })).toBe("服务暂不可用");
    expect(extractErrorDetail({ response: { data: { error_summary_masked: "摘要" } } })).toBe("摘要");
    expect(extractErrorDetail({ message: "network down" })).toBe("network down");
    expect(extractErrorDetail({}, "兜底")).toBe("兜底");
    expect(extractErrorDetail(null, "兜底")).toBe("兜底");

    const masked = extractErrorDetail({
      response: { data: { detail: "connect failed with password=SuperSecret123 host=1.2.3.4" } }
    });
    expect(masked).toContain("password=***");
    expect(masked).not.toContain("SuperSecret123");
    expect(maskSensitiveText("x".repeat(400)).length).toBeLessThanOrEqual(302);
  });

  it("graph page uses the #action slot instead of the old #extra", () => {
    const graph = source("src/views/asset/graph/index.vue");
    expect(graph).toContain("<template #action>");
    expect(graph).not.toContain('<template #extra>\n            <el-button type="primary" @click="resetFilters">');
  });
});

describe("146 stage D2 formatting and enum labels", () => {
  it("formats numbers, times and nullable flags", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
    expect(formatNumber(null)).toBe("-");
    expect(formatNumber(Number.NaN, "无")).toBe("无");
    expect(formatTime("2026-08-24T08:30:00")).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
    expect(formatTime("not-a-date", "-")).toBe("-");
    expect(formatTime(undefined)).toBe("-");
    expect(nullableLabel("Y")).toBe("是");
    expect(nullableLabel("n")).toBe("否");
    expect(nullableLabel(true)).toBe("是");
    expect(nullableLabel("FALSE")).toBe("否");
    expect(nullableLabel(1)).toBe("是");
    expect(nullableLabel(null)).toBe("-");
    expect(nullableLabel("", "空")).toBe("空");
  });

  it("keeps succeeded as the only success terminal with executed read-only", () => {
    expect(OPS_RUN_SUCCESS_TERMINAL).toBe("succeeded");
    expect(opsRunStatusLabel("succeeded")).toBe("成功");
    expect(opsRunStatusLabel("executed")).toBe("成功（旧终态）");
    expect(opsRunStatusLabel("failed")).toBe("失败");
    expect(qualitySeverityLabel("critical")).toBe("严重");
    expect(relationValidationLabel("A_rechecked")).toBe("复核确认 (A)");
    expect(accountStatusLabel("locked")).toBe("锁定");
  });
});

describe("146 stage D3 typed API layer", () => {
  it("has no raw http.request left in plan-touched views", () => {
    const views = [
      "src/views/asset/overview/index.vue",
      "src/views/asset/relation-review/index.vue",
      "src/views/dict/medical/components/PushWizard.vue",
      "src/views/identity/sync-logs/index.vue",
      "src/views/ops/audit/index.vue",
      "src/views/metadata-changes/snapshots/index.vue",
      "src/views/welcome/index.vue"
    ];
    for (const view of views) {
      expect(source(view)).not.toContain("http.request");
    }
  });

  it("wraps the recipe state machine without new backend endpoints", () => {
    const recipes = source("src/api/recipes.ts");
    for (const fn of ["submitRecipeVersion", "approveRecipeVersion", "rejectRecipeVersion", "activateRecipeVersion", "deprecateRecipeVersion"]) {
      expect(recipes).toContain(fn);
    }
  });
});

describe("146 stage D5 frontend permission closures", () => {
  it("guards action buttons with canonical dot permissions", () => {
    const checks: Array<[string, string]> = [
      ["src/views/ops/tools/index.vue", "ops.tool.manage"],
      ["src/views/dict/mappings/index.vue", "dict.medical.edit"],
      ["src/views/dict/sync-diffs/index.vue", "dict.medical.execute"],
      ["src/views/asset/ai-tools/index.vue", "asset.ai_draft.review"],
      ["src/views/asset/table-detail/index.vue", "asset.annotation"],
      ["src/views/metadata-changes/changes/index.vue", "metadata.change.edit"]
    ];
    for (const [view, perm] of checks) {
      expect(source(view)).toContain(`v-perms="'${perm}'`);
    }
  });

  it("keeps route meta.auths codes inside the backend resource catalog", () => {
    const catalog = source("../backend/app/api/v1/permissions.py");
    const assetRoutes = source("src/router/modules/asset.ts");
    const identityRoutes = source("src/router/modules/identity.ts");
    const codes = [...`${assetRoutes}${identityRoutes}`.matchAll(/auths: \["([^"]+)"\]/g)].map(m => m[1]);
    expect(codes.length).toBeGreaterThan(10);
    for (const code of codes) {
      expect(catalog).toContain(`"code": "${code}"`);
    }
  });
});
