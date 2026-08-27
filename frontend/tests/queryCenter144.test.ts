import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import RunProvenancePanel from "@/views/query-center/queries/components/RunProvenancePanel.vue";
import ProductParamForm from "@/views/query-center/queries/components/ProductParamForm.vue";
import {
  calculateMetric,
  executeDataProduct,
  fetchQueryRunDetail,
  runQueryVersion,
  submitFeedback,
  runEvaluation
} from "@/api/query-center";

vi.mock("@/utils/http", () => ({
  http: {
    request: vi.fn().mockResolvedValue({ code: 0, data: {} })
  }
}));

describe("RunProvenancePanel 溯源展示", () => {
  it("展示成功运行的版本/digest/batch，data_as_of 缺失时提示 unknown 而非运行时间", () => {
    const wrapper = mount(RunProvenancePanel, {
      global: { plugins: [ElementPlus] },
      props: {
        run: {
          id: 7,
          query_code: "QRY_X",
          version: 3,
          status: "success",
          row_count: 12,
          truncated: false,
          duration_ms: 240,
          data_as_of: null,
          result_digest: "d".repeat(64),
          schema_digest: "s".repeat(64),
          run_batch: "20260823-000007",
          correlation_id: "abc123",
          safe_parameters_summary: { month: "2026-07" }
        }
      }
    });
    const text = wrapper.text();
    expect(text).toContain("QRY_X@3");
    expect(text).toContain("unknown");
    expect(text).toContain("d".repeat(64));
    expect(text).toContain("20260823-000007");
    expect(text).toContain("abc123");
  });

  it("失败运行展示错误分类而不是原始堆栈", () => {
    const wrapper = mount(RunProvenancePanel, {
      global: { plugins: [ElementPlus] },
      props: {
        run: {
          id: 8,
          query_code: "QRY_Y",
          version: 1,
          status: "failed",
          error_class: "E_SOURCE",
          error_message: "数据源不可用或配置不合规：请核对只读连接登记"
        }
      }
    });
    expect(wrapper.text()).toContain("E_SOURCE");
    expect(wrapper.text()).not.toContain("Traceback");
  });
});

describe("ProductParamForm 参数表单", () => {
  it("按 schema 动态渲染月份/枚举/数值字段并暴露取值", async () => {
    const wrapper = mount(ProductParamForm, {
      global: { plugins: [ElementPlus] },
      props: {
        parameterSchema: {
          type: "object",
          required: ["month"],
          properties: {
            month: { type: "string", title: "月份" },
            dept: { type: "string", title: "科室", enum: ["内科", "外科"] },
            topn: { type: "integer", title: "TopN", minimum: 1, maximum: 50 }
          }
        }
      }
    });
    const html = wrapper.html();
    expect(html).toContain("月份");
    expect(html).toContain("科室");
    expect(html).toContain("TopN");
    expect(typeof wrapper.vm.getValues).toBe("function");
  });

  it("无 schema 时显示可直接执行提示", () => {
    const wrapper = mount(ProductParamForm, {
      global: { plugins: [ElementPlus] },
      props: { parameterSchema: null }
    });
    expect(wrapper.text()).toContain("可直接执行");
  });
});

describe("query-center 类型化 API 层", () => {
  it("runQueryVersion 携带 recalc 字段与参数", async () => {
    await runQueryVersion({
      query_code: "QRY_X",
      version: 2,
      parameters: { month: "2026-07" },
      recalc: true,
      recalc_reason: "2024 backfill"
    });
    const { http } = await import("@/utils/http");
    expect(http.request).toHaveBeenCalledWith("post", "/api/v1/queries/run", {
      data: expect.objectContaining({ query_code: "QRY_X", recalc: true, recalc_reason: "2024 backfill" })
    });
  });

  it("calculateMetric/executeDataProduct/submitFeedback/runEvaluation 走 144 端点", async () => {
    await calculateMetric("MET_X", { period_key: "2026-08" });
    await executeDataProduct("DP_X", { parameters: {}, execute_sql: true, caller_id: "web" });
    await submitFeedback({ answer_event_id: 1, rating: "incorrect", error_types: ["formula"] });
    await runEvaluation({ query_code: "QRY_X" });
    const { http } = await import("@/utils/http");
    const calls = (http.request as ReturnType<typeof vi.fn>).mock.calls as Array<[string, string]>;
    const paths = calls.map(c => c[1]);
    expect(paths).toContain("/api/v1/metrics/MET_X/calculate");
    expect(paths).toContain("/api/v1/data-products/DP_X/execute");
    expect(paths).toContain("/api/v1/ai/feedback");
    expect(paths).toContain("/api/v1/ai/evaluations/run");
    await expect(fetchQueryRunDetail(9)).resolves.toBeTruthy();
  });
});
