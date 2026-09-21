import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

const mocks = vi.hoisted(() => ({
  approveMedicalPushPlan: vi.fn(),
  createMedicalPushPlan: vi.fn(),
  executeMedicalPushPlan: vi.fn(),
  getMedicalPushPlan: vi.fn(),
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
  getMedicalPushPlan: mocks.getMedicalPushPlan
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

const planSummary = {
  id: 725,
  plan_code: "push-test",
  category_code: "diagnosis",
  target_systems: ["HIS_SOURCE"],
  status: "draft",
  item_count: 2,
  is_expired: false,
  created_by: "creator",
  actions: [
    {
      item_code: "A01",
      item_name_cn: "诊断一",
      action_type: "sync_infectious",
      target_system: "HIS_SOURCE",
      infectious_disease_name: "目标名称"
    },
    {
      item_code: "B02",
      item_name_cn: "诊断二",
      action_type: "sync_infectious",
      target_system: "HIS_SOURCE",
      infectious_disease_name: null
    }
  ]
};

function mountWizard() {
  return mount(PushWizard, {
    global: {
      plugins: [ElementPlus],
      directives: { perms: { mounted() {} } }
    }
  });
}

describe("infectious diagnosis sync plan UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listSystems.mockResolvedValue({ data: [{ system_code: "HIS_SOURCE" }, { system_code: "JHEMR_VASTBASE" }] });
    mocks.createMedicalPushPlan.mockResolvedValue({ data: planSummary });
    mocks.confirm.mockResolvedValue(true);
  });

  it("creates only an explicit diagnosis/HIS scope and does not auto-approve", async () => {
    const wrapper = mountWizard();
    await flushPromises();

    await wrapper.findAll('input[type="radio"]')[1].setValue(true);
    await flushPromises();
    await wrapper.find("textarea").setValue("A01\nB02，A01");
    await wrapper.findAll("button").find(button => button.text().includes("生成推送计划"))!.trigger("click");
    await flushPromises();

    expect(mocks.createMedicalPushPlan).toHaveBeenCalledWith({
      category_code: "diagnosis",
      target_systems: ["HIS_SOURCE"],
      action_type: "sync_infectious",
      item_codes: ["A01", "B02"]
    });
    expect(mocks.approveMedicalPushPlan).not.toHaveBeenCalled();
    expect(mocks.confirm).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("计划 ID");
    expect(wrapper.text()).toContain("明确清空");
    wrapper.unmount();
  });

  it("rejects an empty explicit code selection without creating a plan", async () => {
    const wrapper = mountWizard();
    await flushPromises();
    await wrapper.findAll('input[type="radio"]')[1].setValue(true);
    await flushPromises();
    await wrapper.findAll("button").find(button => button.text().includes("生成推送计划"))!.trigger("click");
    await flushPromises();

    expect(mocks.createMedicalPushPlan).not.toHaveBeenCalled();
    expect(mocks.warning).toHaveBeenCalledWith("专项同步必须填写 1–500 个明确的院内诊断编码");
    wrapper.unmount();
  });
});
