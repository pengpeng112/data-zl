// 186 v1.10 前端修复回归：P1-1 结果→反馈链、P2-6 handoff URL 清理、P2-5 键盘主路径。
// 行为断言为主（真实挂载页面组件 + mock API/router），不删改既有 plan186Features 用例。
import { beforeEach, describe, expect, it, vi } from "vitest";
import "./helpers/memoryLocalStorage";
import { createPinia, setActivePinia } from "pinia";
import { mount, flushPromises } from "@vue/test-utils";
import { nextTick, type Component } from "vue";
import ElementPlus from "element-plus";
import { storageLocal } from "@pureadmin/utils";

import { userKey } from "@/utils/auth";
import { useQueryDraftHandoffStore } from "@/store/modules/queryDraftHandoff";
import QueriesPage from "@/views/query-center/queries/index.vue";
import AccuracyPage from "@/views/query-center/accuracy/index.vue";
import SearchModal from "@/layout/components/lay-search/components/SearchModal.vue";

// ---------------------------------------------------------------------------
// 模块级 mock（对本文件全部用例生效）
// ---------------------------------------------------------------------------
const routerMock = vi.hoisted(() => ({
  push: vi.fn(() => Promise.resolve()),
  replace: vi.fn(() => Promise.resolve())
}));
const routeState = vi.hoisted(() => ({ query: {} as Record<string, unknown> }));
const qc = vi.hoisted(() => ({
  fetchQueries: vi.fn(),
  fetchQueryDetail: vi.fn(),
  fetchQueryRuns: vi.fn(),
  fetchQueryRunDetail: vi.fn(),
  runQueryVersion: vi.fn(),
  validateQueryVersion: vi.fn(),
  fetchQueryValidation: vi.fn(),
  fetchMetrics: vi.fn(),
  calculateMetric: vi.fn(),
  fetchMetricResults: vi.fn(),
  fetchDataProducts: vi.fn(),
  executeDataProduct: vi.fn(),
  registerAnswerEvent: vi.fn(),
  submitFeedback: vi.fn(),
  reviewFeedback: vi.fn(),
  fetchFeedback: vi.fn(),
  runEvaluation: vi.fn(),
  fetchAccuracyDashboard: vi.fn(),
  resolveContext: vi.fn(),
  fetchContext: vi.fn(),
  fetchLineageImpact: vi.fn(),
  previewQueryGate: vi.fn(),
  listAiFeedback: vi.fn(),
  ingestQuery: vi.fn(),
  ingestMetric: vi.fn(),
  fetchMetricDetail: vi.fn(),
  publishCoreDataProducts: vi.fn(),
  fetchMetricBoard: vi.fn(),
  fetchSchedules: vi.fn(),
  seedCoreSchedules: vi.fn(),
  upsertSchedule: vi.fn(),
  fetchQuerySourceCapabilities: vi.fn()
}));

vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => routerMock
}));
vi.mock("@/api/query-center", () => qc);
// SearchModal 依赖链会拉入真实 @/router（vue-router 已被 mock，真实路由无法构建）
vi.mock("@/router/index", () => ({
  router: {},
  resetRouter: vi.fn(),
  constantMenus: []
}));
vi.mock("@/layout/hooks/useNav", () => ({
  useNav: () => ({ device: "desktop" })
}));
const searchMenus = vi.hoisted(() => [
  { path: "/p/a", meta: { title: "甲查询", icon: "ep/search" } },
  { path: "/p/b", meta: { title: "乙查询", icon: "ep/search" } },
  { path: "/p/c", meta: { title: "丙查询", icon: "ep/search" } }
]);
vi.mock("@/store/modules/permission", () => ({
  usePermissionStoreHook: () => ({ wholeMenus: searchMenus })
}));

// jsdom 缺 ResizeObserver（@pureadmin/utils useResizeObserver 未做守卫）
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

// ---------------------------------------------------------------------------
// 公共夹具
// ---------------------------------------------------------------------------
function seedUser(permissions: string[]) {
  storageLocal().setItem(userKey, {
    accessToken: "",
    refreshToken: "",
    expires: 0,
    username: "tester",
    nickname: "tester",
    roles: [],
    permissions
  });
}

function mountPage(component: Component, pinia = createPinia()) {
  return mount(component, {
    // attachTo：jsdom 中 focus()/getElementById 只对已挂载文档的元素生效
    attachTo: document.body,
    global: {
      plugins: [ElementPlus, pinia],
      // v-perms 的移除逻辑由路由/权限集成测试覆盖；此处注册空指令保持元素可挂载
      directives: { perms: {} }
    }
  });
}

const RUN_ROW = { id: 101, query_code: "QC_IP_COUNT", version: 3, status: "success" };
const RUN_DETAIL = {
  id: 101,
  query_code: "QC_IP_COUNT",
  version: 3,
  status: "success",
  row_count: 5,
  result_digest: "sha256:abc123",
  schema_digest: "sha256:def456",
  data_as_of: "2026-09-01",
  safe_parameters_summary: {}
};

const DASH = {
  schema_version: "1",
  audited_feedback_total: 0,
  feedback_rating_distribution: {},
  error_type_trend: {},
  golden_case_runs_window: "",
  golden_pass: 0,
  golden_fail: 0,
  golden_error: 0,
  golden_pass_rate: null,
  unevaluated_feedback: 0,
  notes: ""
};

function mockQueriesDefaults() {
  qc.fetchQueries.mockResolvedValue({ data: { items: [], total: 0 } });
  qc.fetchQueryRuns.mockResolvedValue({ data: { items: [], total: 0 } });
}

function mockAccuracyDefaults() {
  qc.fetchAccuracyDashboard.mockResolvedValue({ data: DASH });
  qc.listAiFeedback.mockResolvedValue({ data: { items: [], total: 0, page: 1, page_size: 20 } });
}

function mockSubmitSuccess() {
  qc.registerAnswerEvent.mockResolvedValue({
    data: { answer_event_id: 9, question_digest: "d" }
  });
  qc.submitFeedback.mockResolvedValue({ data: { feedback_id: 77, status: "pending" } });
}

async function findButton(
  wrapper: { findAll: (selector: string) => Array<{ text: () => string }> },
  text: string
) {
  return wrapper.findAll("button").find(b => b.text().includes(text));
}

beforeEach(() => {
  routerMock.push.mockClear();
  routerMock.replace.mockClear();
  Object.values(qc).forEach(fn => fn.mockReset());
  routeState.query = {};
  localStorage.clear();
});

// ---------------------------------------------------------------------------
// P1-1：运行详情 → 反馈链
// ---------------------------------------------------------------------------
describe("plan186 P1-1 运行详情→反馈链", () => {
  it("点击「反馈此结果」携带 run_id/query_code/query_version 跳转，不含 SQL/digest 明文", async () => {
    seedUser(["query.view", "feedback.create"]);
    routeState.query = { tab: "runs" };
    mockQueriesDefaults();
    qc.fetchQueryRuns.mockResolvedValue({ data: { items: [RUN_ROW], total: 1 } });
    qc.fetchQueryRunDetail.mockResolvedValue({ data: RUN_DETAIL });

    const wrapper = mountPage(QueriesPage);
    await flushPromises();

    // tab=runs 点击行打开运行详情（RunProvenancePanel 所在 dialog）
    const row = wrapper.find(".el-table__row");
    expect(row.exists()).toBe(true);
    await row.trigger("click");
    await flushPromises();

    const feedbackBtn = await findButton(wrapper, "反馈此结果");
    expect(feedbackBtn).toBeTruthy();
    await feedbackBtn!.trigger("click");

    expect(routerMock.push).toHaveBeenCalledTimes(1);
    const arg = routerMock.push.mock.calls[0][0];
    expect(arg.path).toBe("/asset/queries/accuracy");
    // 只带三个非敏感定位 ID（值来自已加载的运行详情数据）
    expect(Object.keys(arg.query).sort()).toEqual(["query_code", "query_version", "run_id"]);
    expect(arg.query).toMatchObject({
      run_id: "101",
      query_code: "QC_IP_COUNT",
      query_version: "3"
    });
    // 不带 SQL / digest 明文
    const serialized = JSON.stringify(arg);
    expect(serialized).not.toContain("sha256:");
    expect(serialized).not.toContain("SELECT");
    wrapper.unmount();
  });

  it("无 feedback.create 权限时「反馈此结果」不渲染", async () => {
    seedUser(["query.view"]);
    routeState.query = { tab: "runs" };
    mockQueriesDefaults();
    qc.fetchQueryRuns.mockResolvedValue({ data: { items: [RUN_ROW], total: 1 } });
    qc.fetchQueryRunDetail.mockResolvedValue({ data: RUN_DETAIL });

    const wrapper = mountPage(QueriesPage);
    await flushPromises();
    await wrapper.find(".el-table__row").trigger("click");
    await flushPromises();

    expect(await findButton(wrapper, "反馈此结果")).toBeFalsy();
    wrapper.unmount();
  });
});

// ---------------------------------------------------------------------------
// P1-1：accuracy 页接收参数回读并预填
// ---------------------------------------------------------------------------
describe("plan186 P1-1 accuracy 页反馈上下文回读", () => {
  it("收到 run_id 后调用运行详情 API，表单上下文用回读值（不信任 URL 传值），提交携带回读上下文与反馈编号", async () => {
    seedUser(["feedback.create"]);
    routeState.query = {
      run_id: "101",
      query_code: "SHOULD_NOT_TRUST",
      query_version: "9"
    };
    mockAccuracyDefaults();
    qc.fetchQueryRunDetail.mockResolvedValue({
      data: { ...RUN_DETAIL, query_code: "QC_CORRECT", version: 7 }
    });

    const wrapper = mountPage(AccuracyPage);
    await flushPromises();

    // 调用运行详情 API（run_id 转 number）
    expect(qc.fetchQueryRunDetail).toHaveBeenCalledWith(101);
    // 表单上方提示"已关联运行记录"，且展示的是回读值而非 URL 传值
    expect(wrapper.text()).toContain("已关联运行记录");
    expect(wrapper.text()).toContain("QC_CORRECT@v7");
    expect(wrapper.text()).not.toContain("SHOULD_NOT_TRUST");
    // 问题摘要留空由用户填写
    const question = wrapper.find('input[placeholder="例：2026年7月住院次均费用"]');
    expect((question.element as HTMLInputElement).value).toBe("");

    // 提交：registerAnswerEvent 携带回读的 query_code/version/run_id/digest
    mockSubmitSuccess();
    await question.setValue("测试问题摘要");
    const submitBtn = await findButton(wrapper, "登记回答并提交反馈");
    expect(submitBtn).toBeTruthy();
    await submitBtn!.trigger("click");
    await flushPromises();

    expect(qc.registerAnswerEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        question_summary: "测试问题摘要",
        query_code: "QC_CORRECT",
        query_version: 7,
        run_id: 101,
        result_digest: "sha256:abc123"
      })
    );
    // 成功后显示反馈编号与「查看我的反馈」链接（锚点到反馈记录卡）
    expect(wrapper.text()).toContain("77");
    const link = wrapper.findAll(".el-link").find(l => l.text().includes("查看我的反馈"));
    expect(link).toBeTruthy();
    const scrollSpy = vi.fn();
    (Element.prototype as unknown as { scrollIntoView: unknown }).scrollIntoView =
      scrollSpy;
    await link!.trigger("click");
    expect(scrollSpy).toHaveBeenCalled();
    expect(qc.listAiFeedback).toHaveBeenCalled();
    wrapper.unmount();
  });

  it("回读 404 时不预填，显示通用意见提示且提交不带运行上下文", async () => {
    seedUser(["feedback.create"]);
    routeState.query = { run_id: "404" };
    mockAccuracyDefaults();
    qc.fetchQueryRunDetail.mockRejectedValue({ response: { status: 404 } });

    const wrapper = mountPage(AccuracyPage);
    await flushPromises();

    expect(wrapper.text()).toContain("未找到运行记录，可提交通用意见");
    expect(wrapper.text()).not.toContain("已关联运行记录");

    mockSubmitSuccess();
    const question = wrapper.find('input[placeholder="例：2026年7月住院次均费用"]');
    await question.setValue("测试问题摘要");
    const submitBtn = await findButton(wrapper, "登记回答并提交反馈");
    await submitBtn!.trigger("click");
    await flushPromises();

    const payload = qc.registerAnswerEvent.mock.calls[0][0];
    expect(payload).not.toHaveProperty("run_id");
    expect(payload).not.toHaveProperty("query_code");
    wrapper.unmount();
  });

  it("指标结果入口同样回读 metric 上下文并随反馈提交", async () => {
    seedUser(["feedback.create"]);
    routeState.query = { metric_code: "M_IP7" };
    mockAccuracyDefaults();
    qc.fetchMetricDetail.mockResolvedValue({
      data: { definition: { metric_code: "M_IP7" }, active_version: { version: 2 } }
    });

    const wrapper = mountPage(AccuracyPage);
    await flushPromises();

    expect(qc.fetchMetricDetail).toHaveBeenCalledWith("M_IP7");
    expect(wrapper.text()).toContain("已关联指标记录");
    expect(wrapper.text()).toContain("M_IP7@v2");

    mockSubmitSuccess();
    const question = wrapper.find('input[placeholder="例：2026年7月住院次均费用"]');
    await question.setValue("测试问题摘要");
    const submitBtn = await findButton(wrapper, "登记回答并提交反馈");
    await submitBtn!.trigger("click");
    await flushPromises();

    expect(qc.registerAnswerEvent).toHaveBeenCalledWith(
      expect.objectContaining({ metric_code: "M_IP7", metric_version: 2 })
    );
    wrapper.unmount();
  });
});

// ---------------------------------------------------------------------------
// P2-6：handoff 消费成功后清理 URL
// ---------------------------------------------------------------------------
describe("plan186 P2-6 handoff URL 清理", () => {
  it("消费成功后 router.replace 去掉 handoff 参数且保留 tab", async () => {
    seedUser(["query.create"]);
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useQueryDraftHandoffStore(pinia);
    const handoffId = store.stage({
      systemCode: "DATA_CENTER",
      sqlText: "SELECT 1 FROM DUAL",
      questionSummary: "示例问题",
      selectedTables: [],
      contextDigest: {},
      risk: {}
    });
    routeState.query = { tab: "list", handoff: handoffId };
    mockQueriesDefaults();

    const wrapper = mountPage(QueriesPage, pinia);
    await flushPromises();

    // 草稿已一次性消费并带入摄取表单（弹窗打开、SQL 已填充）
    expect(store.peek(handoffId)).toBeNull();
    const sqlTextarea = wrapper
      .findAll("textarea")
      .find(t => (t.element as HTMLTextAreaElement).value.includes("SELECT 1 FROM DUAL"));
    expect(sqlTextarea).toBeTruthy();

    // URL 清理：handoff 移除，tab 保留
    expect(routerMock.replace).toHaveBeenCalled();
    const cleared = routerMock.replace.mock.calls
      .map(call => call[0])
      .find(target => target?.query && !("handoff" in target.query));
    expect(cleared).toBeTruthy();
    expect(cleared!.query).toMatchObject({ tab: "list" });
    expect(cleared!.query).not.toHaveProperty("handoff");
    wrapper.unmount();
  });
});

// ---------------------------------------------------------------------------
// P2-5：键盘主路径（搜索弹窗 ↑↓/Enter；弹窗关闭焦点回归）
// ---------------------------------------------------------------------------
describe("plan186 P2-5 键盘主路径", () => {
  it("SearchModal 打开后 ↑↓ 移动高亮、Enter 导航到高亮项", async () => {
    const wrapper = mount(SearchModal, {
      props: { value: false },
      global: { plugins: [ElementPlus, createPinia()] }
    });
    await wrapper.setProps({ value: true });
    await nextTick();
    // el-dialog append-to-body → 从 document.body 找输入框
    const input = document.body.querySelector(
      'input[placeholder="搜索菜单（支持拼音搜索）"]'
    ) as HTMLInputElement | null;
    expect(input).toBeTruthy();

    // 输入关键词（300ms debounce 后执行搜索）
    input!.value = "查询";
    input!.dispatchEvent(new Event("input"));
    await new Promise(resolve => setTimeout(resolve, 500));
    await nextTick();

    const items = Array.from(document.body.querySelectorAll(".result-item"));
    expect(items.length).toBe(3);
    const isActive = (el: Element) => (el as HTMLElement).style.fontSize === "16px";
    // 初始高亮第一项
    expect(isActive(items[0])).toBe(true);

    // ↓ 下移高亮
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown" }));
    await nextTick();
    expect(isActive(items[1])).toBe(true);
    expect(isActive(items[0])).toBe(false);

    // ↑ 上移高亮
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp" }));
    await nextTick();
    expect(isActive(items[0])).toBe(true);

    // Enter 选中并导航到高亮项（mock router.push 断言目标）
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await nextTick();
    expect(routerMock.push).toHaveBeenCalledWith("/p/a");
    wrapper.unmount();
  });

  it("摄取弹窗关闭（取消）后焦点回到「提交 SQL」触发按钮", async () => {
    seedUser(["query.view", "query.create"]);
    routeState.query = { tab: "list" };
    mockQueriesDefaults();

    const wrapper = mountPage(QueriesPage);
    await flushPromises();

    const trigger = await findButton(wrapper, "提交 SQL");
    expect(trigger).toBeTruthy();
    await trigger!.trigger("click");
    await nextTick();
    expect(wrapper.find(".el-dialog").exists()).toBe(true);

    // 取消路径：点击弹窗底部「取消」按钮关闭
    const cancelBtn = await findButton(wrapper, "取消");
    expect(cancelBtn).toBeTruthy();
    await cancelBtn!.trigger("click");
    // 焦点回归在宏任务中执行（Element Plus 焦点陷阱释放之后）
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(document.activeElement).toBe(trigger!.element);
    wrapper.unmount();
  });
});
