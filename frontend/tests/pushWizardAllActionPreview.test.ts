import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

/**
 * 202 D2-1：PushWizard 全动作逐条预览与完整性门禁。
 * 覆盖：
 * 1) loadInsertCodeOptions 必须以 page_size=200 调用（第一日 422 缺陷回归）；
 * 2) 普通 insert 两动作逐条可见（此前仅传染病渲染表格）；
 * 3) actions 不完整（编码×目标覆盖缺失）时审批按钮禁用 + 提示可见；
 * 4) 创建人不能自审；审批人只持 approve 仍可加载并审核（完整 actions 时）。
 */
const mocks = vi.hoisted(() => ({
  approveMedicalPushPlan: vi.fn(),
  createMedicalPushPlan: vi.fn(),
  executeMedicalPushPlan: vi.fn(),
  getMedicalPushPlan: vi.fn(),
  getMedicalItems: vi.fn(),
  listSystems: vi.fn(),
  confirm: vi.fn(),
  success: vi.fn(),
  warning: vi.fn(),
  error: vi.fn()
}));

vi.mock("@/api/dict", () => ({
  approveMedicalPushPlan: mocks.approveMedicalPushPlan,
  createMedicalPushPlan: mocks.createMedicalPushPlan,
  executeMedicalPushPlan: mocks.executeMedicalPushPlan,
  getMedicalPushPlan: mocks.getMedicalPushPlan,
  getMedicalItems: mocks.getMedicalItems
}));
vi.mock("@/api/asset", () => ({ listSystems: mocks.listSystems }));
vi.mock("@/store/modules/user", () => ({ useUserStoreHook: () => ({ username: "reviewer" }) }));
vi.mock("element-plus", async importOriginal => {
  const actual = await importOriginal<typeof import("element-plus")>();
  return {
    ...actual,
    ElMessage: { success: mocks.success, warning: mocks.warning, error: mocks.error },
    ElMessageBox: { confirm: mocks.confirm }
  };
});

import PushWizard from "@/views/dict/medical/components/PushWizard.vue";

function makeInsertPlan(actionOverrides: Record<string, unknown>[] = []) {
  return {
    id: 901,
    plan_code: "push-d21",
    category_code: "diagnosis",
    target_systems: ["HIS_SOURCE"],
    status: "draft",
    execution_status: null,
    item_count: 2,
    is_expired: false,
    created_by: "creator",
    approved_by: null,
    latest_runs: {},
    outbox: {},
    actions: [
      {
        item_code: "QA_D01",
        item_name_cn: "测试诊断甲",
        action_type: "insert",
        target_system: "HIS_SOURCE",
        status: "planned",
        national_clinical_code: "N27.01",
        insurance_code: "Y27.01",
        ...actionOverrides[0]
      },
      {
        item_code: "QA_D02",
        item_name_cn: "测试诊断乙",
        action_type: "insert",
        target_system: "HIS_SOURCE",
        status: "planned",
        national_clinical_code: null,
        insurance_code: null,
        ...actionOverrides[1]
      }
    ]
  };
}

function mountWizard() {
  return mount(PushWizard, {
    global: {
      plugins: [ElementPlus],
      directives: { perms: { mounted() {} } }
    }
  });
}

async function gotoStep2(wrapper: ReturnType<typeof mountWizard>, plan: unknown) {
  mocks.createMedicalPushPlan.mockResolvedValue({ data: plan });
  // 默认 actionType=insert；勾选目标 + 两码
  const checkboxes = wrapper.findAll(".el-checkbox");
  const his = checkboxes.find(c => c.text().includes("HIS"));
  await his?.find("input").setValue(true);
  const codes = wrapper.findAllComponents({ name: "ElSelect" });
  expect(codes.length).toBeGreaterThan(0);
  // 直接调用生成（绕开 el-select 交互）：填 v-model
  (wrapper.vm as unknown as Record<string, unknown>).insertSelectedItemCodes = ["QA_D01", "QA_D02"];
  const createBtn = wrapper.findAll("button").find(b => b.text().includes("生成推送计划"));
  await createBtn?.trigger("click");
  await flushPromises();
}

describe("PushWizard all-action preview (202 D2-1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listSystems.mockResolvedValue({ data: [{ system_code: "HIS_SOURCE" }, { system_code: "JHEMR_VASTBASE" }] });
    mocks.getMedicalItems.mockResolvedValue({
      data: { items: [{ item_code: "QA_D01", item_name_cn: "测试诊断甲", status: "active" }] }
    });
    mocks.confirm.mockResolvedValue(true);
  });

  it("loadInsertCodeOptions 以 page_size=200 调用（422 回归）", async () => {
    const wrapper = mountWizard();
    await flushPromises();
    expect(mocks.getMedicalItems).toHaveBeenCalled();
    const call = mocks.getMedicalItems.mock.calls[0];
    expect(call[1]).toMatchObject({ status: "active", page_size: 200 });
    wrapper.unmount();
  });

  it("普通 insert 计划逐条渲染两 action 行（编码/动作/目标/国标医保值）", async () => {
    const wrapper = mountWizard();
    await gotoStep2(wrapper, makeInsertPlan());
    await flushPromises();
    const table = wrapper.find('[data-testid="plan-actions-table"]');
    expect(table.exists()).toBe(true);
    const text = table.text();
    expect(text).toContain("QA_D01");
    expect(text).toContain("QA_D02");
    expect(text).toContain("N27.01 / Y27.01");
    expect(text).toContain("新增");
    expect(text).toContain("HIS");
    const rows = table.findAll(".el-table__row");
    expect(rows.length).toBe(2);
    wrapper.unmount();
  });

  it("actions 覆盖缺失（第二码缺目标）时审批禁用且提示可见", async () => {
    const plan = makeInsertPlan([{ target_system: "HIS_SOURCE" }, { target_system: "" }]);
    plan.actions[1] = { ...plan.actions[1], target_system: "JHEMR_VASTBASE" };
    // 目标系统为 [HIS_SOURCE] 但第二码动作挂 JHEMR_VASTBASE → 编码×目标覆盖缺失
    const wrapper = mountWizard();
    await gotoStep2(wrapper, plan);
    await flushPromises();
    const alert = wrapper.find('[data-testid="actions-incomplete-alert"]');
    expect(alert.exists()).toBe(true);
    const approveBtn = wrapper.findAll("button").find(b => b.text().includes("审批计划并排队"));
    expect(approveBtn).toBeDefined();
    expect((approveBtn?.element as HTMLButtonElement).disabled).toBe(true);
    wrapper.unmount();
  });

  it("actions 为空数组时审批禁用", async () => {
    const plan = makeInsertPlan();
    plan.actions = [];
    const wrapper = mountWizard();
    await gotoStep2(wrapper, plan);
    await flushPromises();
    const approveBtn = wrapper.findAll("button").find(b => b.text().includes("审批计划并排队"));
    expect(approveBtn).toBeDefined();
    expect((approveBtn?.element as HTMLButtonElement).disabled).toBe(true);
    wrapper.unmount();
  });

  it("完整 insert 计划：非创建人可审批（approveMedicalPushPlan 被调用）", async () => {
    mocks.approveMedicalPushPlan.mockResolvedValue({ data: { ...makeInsertPlan(), status: "approved", approved_by: "reviewer" } });
    const wrapper = mountWizard();
    await gotoStep2(wrapper, makeInsertPlan());
    await flushPromises();
    const approveBtn = wrapper.findAll("button").find(b => b.text().includes("审批计划并排队"));
    expect(approveBtn).toBeDefined();
    expect((approveBtn?.element as HTMLButtonElement).disabled).toBe(false);
    await approveBtn?.trigger("click");
    await flushPromises();
    expect(mocks.approveMedicalPushPlan).toHaveBeenCalledWith(901, "工作台审批");
    wrapper.unmount();
  });

  it("创建人不能自审（currentUsername=创建人时按钮禁用）", async () => {
    vi.mocked(mocks.listSystems); // keep mock clean
    const wrapper = mount(PushWizard, {
      global: {
        plugins: [ElementPlus],
        directives: { perms: { mounted() {} } }
      }
    });
    // user store mock 返回 reviewer；把 plan.created_by 设为 reviewer 模拟自审场景
    const selfPlan = { ...makeInsertPlan(), created_by: "reviewer" };
    mocks.createMedicalPushPlan.mockResolvedValue({ data: selfPlan });
    (wrapper.vm as unknown as Record<string, unknown>).insertSelectedItemCodes = ["QA_D01", "QA_D02"];
    const his = wrapper.findAll(".el-checkbox").find(c => c.text().includes("HIS"));
    await his?.find("input").setValue(true);
    const createBtn = wrapper.findAll("button").find(b => b.text().includes("生成推送计划"));
    await createBtn?.trigger("click");
    await flushPromises();
    const warn = wrapper
      .findAll(".el-alert")
      .find(a => a.text().includes("计划创建人"));
    expect(warn).toBeDefined();
    expect(warn?.text()).toContain("不能审批");
    wrapper.unmount();
  });
});
