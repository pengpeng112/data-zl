/**
 * 194 DEF-02 回归：查询中心列表取数形状。
 * 后端 GET /api/v1/queries 返回 ApiResponse 信封 {code,message,data:{items,total}}；
 * http 拦截器 return response.data（= 信封 body）。页面应从 res.data.items 取数。
 * 本测试用信封响应 mock，断言表格渲染出数据行；若页面层级写错将复现 194 的空列表。
 */
import { describe, expect, it, vi } from "vitest";
import "./helpers/memoryLocalStorage";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";

const routeState = { query: {}, path: "/asset/queries" };
const routerMock = { replace: vi.fn().mockResolvedValue(undefined), push: vi.fn() };

const mockApi = vi.hoisted(() => ({
  fetchQueries: vi.fn(),
  fetchRuns: vi.fn(),
  fetchMetricBoard: vi.fn(),
  fetchProducts: vi.fn(),
  fetchSchedules: vi.fn()
}));

const stubRouter = vi.hoisted(() => ({
  beforeEach: vi.fn(),
  afterEach: vi.fn(),
  push: vi.fn(),
  replace: vi.fn(),
  isReady: vi.fn().mockResolvedValue(undefined)
}));

vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => routerMock,
  createRouter: vi.fn(() => stubRouter),
  createWebHashHistory: vi.fn(),
  RouterLink: { template: "<a><slot /></a>" },
  RouterView: { template: "<div><slot /></div>" }
}));
vi.mock("@/api/query-center", async importOriginal => {
  const actual: Record<string, unknown> = await importOriginal();
  return {
    ...actual,
    fetchQueries: mockApi.fetchQueries,
    fetchRuns: mockApi.fetchRuns,
    fetchMetricBoard: mockApi.fetchMetricBoard,
    fetchProducts: mockApi.fetchProducts,
    fetchSchedules: mockApi.fetchSchedules
  };
});

import QueriesPage from "@/views/query-center/queries/index.vue";

function envelope(items: Array<Record<string, unknown>>, total: number) {
  return { code: 0, message: "success", data: { items, total, page: 1, page_size: 30 }, request_id: "t" };
}

describe("194 DEF-02 查询中心列表响应形状", () => {
  it("信封响应下列表应渲染数据行而非空表", async () => {
    mockApi.fetchQueries.mockResolvedValue(
      envelope(
        [
          {
            query_code: "Q-R194-001",
            title: "住院人次日查询",
            business_domain: "住院",
            status: "certified",
            active_version: { version_no: 3, status: "certified" }
          },
          {
            query_code: "Q-R194-002",
            title: "检验完成数月查询",
            business_domain: "检验",
            status: "active",
            active_version: { version_no: 2, status: "active" }
          }
        ],
        2
      )
    );
    mockApi.fetchRuns.mockResolvedValue(envelope([], 0));
    mockApi.fetchMetricBoard.mockResolvedValue(envelope([], 0));
    mockApi.fetchProducts.mockResolvedValue(envelope([], 0));
    mockApi.fetchSchedules.mockResolvedValue(envelope([], 0));

    const wrapper = mount(QueriesPage, {
      attachTo: document.body,
      global: {
        plugins: [ElementPlus, createPinia()],
        directives: { perms: {} }
      }
    });
    await flushPromises();

    const html = wrapper.html();
    expect(mockApi.fetchQueries).toHaveBeenCalled();
    expect(html).toContain("Q-R194-001");
    expect(html).toContain("Q-R194-002");
    wrapper.unmount();
  });
});
