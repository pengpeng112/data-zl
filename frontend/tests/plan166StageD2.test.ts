import "./helpers/memoryLocalStorage";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { createPinia } from "pinia";
import { storageLocal } from "@pureadmin/utils";
import { userKey } from "@/utils/auth";

vi.mock("vue-router", () => ({
  useRoute: () => ({
    params: { schema: "HIS", table: "PAT_VISIT" },
    query: {}
  }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() })
}));

// pinia user store → store/utils → 真实 router 单例（导入期 createRouter）；
// 组件测试不依赖真实 router，mock 断链（同 D1 测试处理）
vi.mock("@/router/index", () => ({ router: {} }));

const api = vi.hoisted(() => ({
  listValueDomains: vi.fn(),
  getValueDomainDetail: vi.fn(),
  getValueDomainVersions: vi.fn(),
  confirmValueDomain: vi.fn(),
  deprecateValueDomain: vi.fn(),
  resolveValueDomainConflict: vi.fn(),
  exportValueDomains: vi.fn(),
  getTableDetail: vi.fn(),
  getTableColumns: vi.fn(),
  getTableRelations: vi.fn(),
  getGraphNeighbors: vi.fn(),
  updateTableAnnotation: vi.fn(),
  updateColumnAnnotation: vi.fn()
}));

vi.mock("@/api/asset", () => api);

import ValueDomainsPage from "@/views/asset/value-domains/index.vue";
import TableDetailPage from "@/views/asset/table-detail/index.vue";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

/** v-perms 走 pinia user store（读 storageLocal user-key）：播种 platform_admin 后行为确定 */
function mountPage(component: any) {
  storageLocal().setItem(userKey, {
    accessToken: "",
    refreshToken: "",
    expires: 0,
    username: "t",
    nickname: "t",
    roles: ["platform_admin"],
    permissions: ["*:*:*"]
  });
  return mount(component, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body
  });
}

function makeDomainItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    system_code: "HIS_SOURCE",
    source_code: "his_source_10_10_10_15",
    schema_name: "MEDREC",
    table_name: "PAT_VISIT",
    column_name: "DISCHARGE_DISPOSITION",
    code: "4",
    meaning: "非医嘱离院（自愿离院）",
    note: null,
    domain_kind: "enum",
    scope_condition: null,
    status: "pending",
    conflict_status: "none",
    confirmed_by: null,
    confirmed_at: null,
    current_version_id: null,
    version_no: 1,
    evidence_count: 2,
    created_at: "2026-08-01T00:00:00",
    updated_at: "2026-08-20T00:00:00",
    ...overrides
  };
}

function mockListOnce(items: any[], total: number) {
  return vi.fn().mockImplementation((params: any) =>
    Promise.resolve({
      data: {
        items:
          params.status === "pending" && params.page_size === 1
            ? []
            : params.conflicted === true && params.page_size === 1
              ? []
              : items,
        total
      }
    })
  );
}
void mockListOnce;

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = "";
});

describe("plan166 D2 value-domain management page (F2/F3)", () => {
  it("renders the paged list with pending badge and conflict counter", async () => {
    const impl = vi.fn().mockImplementation((params: any) => {
      if (params.status === "pending") return Promise.resolve({ data: { items: [], total: 7 } });
      if (params.conflicted === true) return Promise.resolve({ data: { items: [], total: 2 } });
      return Promise.resolve({
        data: {
          items: [
            makeDomainItem(),
            makeDomainItem({
              id: 2,
              column_name: "SEX",
              code: "1",
              meaning: "男",
              conflict_status: "conflicted"
            })
          ],
          total: 2
        }
      });
    });
    api.listValueDomains.mockImplementation(impl as any);
    const w = mountPage(ValueDomainsPage);
    await flushPromises();
    const text = w.text();
    expect(text).toContain("非医嘱离院（自愿离院）");
    expect(text).toContain("未裁决");
    // pending 计数徽标（status=pending 的 total）
    expect(w.find(".pending-badge").text()).toContain("7");
    // 列表主调用带分页契约
    expect(impl).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 20 })
    );
    w.unmount();
  });

  it("opens the detail drawer with evidence chain and version history", async () => {
    api.listValueDomains.mockImplementation(
      vi.fn().mockImplementation((params: any) => {
        if (params.status === "pending") return Promise.resolve({ data: { items: [], total: 0 } });
        if (params.conflicted === true) return Promise.resolve({ data: { items: [], total: 0 } });
        return Promise.resolve({ data: { items: [makeDomainItem()], total: 1 } });
      }) as any
    );
    api.getValueDomainDetail.mockResolvedValue({
      data: {
        ...makeDomainItem(),
        evidences: [
          {
            id: 1,
            source_type: "live_probe",
            source_system: "HIS",
            observed_meaning: null,
            method: "2026-08 实测 120 例",
            sample_count: 120,
            observed_at: null,
            actor: "probe",
            snippet_ref: "148 §1"
          },
          {
            id: 2,
            source_type: "cross_system",
            source_system: "JHEMR",
            observed_meaning: "死亡",
            method: "report.r_pat_visit 交叉验证",
            sample_count: 30,
            observed_at: null,
            actor: "probe",
            snippet_ref: "152 E5"
          }
        ]
      }
    });
    api.getValueDomainVersions.mockResolvedValue({
      data: {
        domain_id: 1,
        current_version_no: 1,
        items: [
          {
            id: 1,
            version_no: 1,
            snapshot: {},
            change_reason: "submit",
            evidence_ref: "148 §1",
            actor: "ai",
            created_at: "2026-08-01T00:00:00"
          }
        ]
      }
    });
    const w = mountPage(ValueDomainsPage);
    await flushPromises();
    await w.find(".el-table__row").trigger("click");
    await flushPromises();
    expect(api.getValueDomainDetail).toHaveBeenCalledWith(1);
    expect(api.getValueDomainVersions).toHaveBeenCalledWith(1);
    const bodyText = document.body.textContent || "";
    expect(bodyText).toContain("live_probe");
    expect(bodyText).toContain("148 §1");
    // 竞争口径（competing meaning）在证据链中呈现
    expect(bodyText).toContain("死亡");
    w.unmount();
  });

  it("conflict tab queries conflicted=true and conflicted rows guide resolve first (B4)", async () => {
    const conflictedRow = makeDomainItem({
      id: 2,
      conflict_status: "conflicted",
      meaning: "含义A"
    });
    api.listValueDomains.mockImplementation((params: any) => {
      if (params.status === "pending") return Promise.resolve({ data: { items: [], total: 0 } });
      if (params.conflicted === true && params.page_size === 1) {
        return Promise.resolve({ data: { items: [], total: 1 } });
      }
      return Promise.resolve({ data: { items: [conflictedRow], total: 1 } });
    });
    api.getValueDomainDetail.mockResolvedValue({
      data: {
        ...makeDomainItem({ conflict_status: "conflicted" }),
        evidences: []
      }
    });
    api.getValueDomainVersions.mockResolvedValue({
      data: { domain_id: 1, current_version_no: 1, items: [] }
    });
    const w = mountPage(ValueDomainsPage);
    await flushPromises();

    // 切到冲突 Tab → conflicted: true
    const conflictTab = w
      .findAll(".el-tabs__item")
      .find(t => (t.text() || "").includes("冲突"));
    expect(conflictTab).toBeTruthy();
    await conflictTab!.trigger("click");
    await flushPromises();
    expect(api.listValueDomains).toHaveBeenCalledWith(
      expect.objectContaining({ conflicted: true })
    );

    // conflicted 行详情：点确认 → 引导先裁决，裁决弹窗打开
    await w.find(".el-table__row").trigger("click");
    await flushPromises();
    const body = () => document.body.textContent || "";
    const confirmBtn = Array.from(document.querySelectorAll(".el-drawer button")).find(b =>
      (b.textContent || "").trim() === "确认"
    ) as HTMLButtonElement | undefined;
    expect(confirmBtn).toBeTruthy();
    confirmBtn!.click();
    await flushPromises();
    expect(body()).toContain("先完成冲突裁决");
    // 裁决弹窗已打开（竞争口径区 + 采纳按钮）
    expect(body()).toContain("竞争口径");
    expect(body()).toContain("采纳并解除冲突");
    w.unmount();
  });

  it("surfaces a 403 rejection from confirm as an error message (vi.mock 403 case)", async () => {
    api.listValueDomains.mockImplementation(
      vi.fn().mockImplementation((params: any) => {
        if (params.status === "pending") return Promise.resolve({ data: { items: [], total: 0 } });
        if (params.conflicted === true) return Promise.resolve({ data: { items: [], total: 0 } });
        return Promise.resolve({ data: { items: [makeDomainItem()], total: 1 } });
      }) as any
    );
    api.getValueDomainDetail.mockResolvedValue({
      data: { ...makeDomainItem(), evidences: [] }
    });
    api.getValueDomainVersions.mockResolvedValue({
      data: { domain_id: 1, current_version_no: 1, items: [] }
    });
    api.confirmValueDomain.mockRejectedValue({
      response: { status: 403, data: { detail: "缺少权限: value_domain.confirm" } }
    });
    const w = mountPage(ValueDomainsPage);
    await flushPromises();
    await w.find(".el-table__row").trigger("click");
    await flushPromises();
    const body = () => document.body.textContent || "";
    // 打开确认弹窗并提交（提交按钮限定在 .el-dialog 内，避免命中抽屉同名按钮）
    const drawerConfirm = Array.from(document.querySelectorAll(".el-drawer button")).find(b =>
      (b.textContent || "").trim() === "确认"
    ) as HTMLButtonElement;
    drawerConfirm.click();
    await flushPromises();
    const dialogSubmit = Array.from(document.querySelectorAll(".el-dialog button")).find(b =>
      (b.textContent || "").trim() === "确认"
    ) as HTMLButtonElement;
    dialogSubmit.click();
    await flushPromises();
    expect(api.confirmValueDomain).toHaveBeenCalled();
    expect(body()).toContain("value_domain.confirm");
    w.unmount();
  });

  it("keeps dot-form v-perms on all three manual action buttons (B3)", () => {
    const src = source("src/views/asset/value-domains/index.vue");
    const matches = src.match(/v-perms="'value_domain\.confirm'"/g) || [];
    expect(matches.length).toBe(3);
    expect(src).not.toContain("value_domain:confirm");
  });
});

describe("plan166 D2 table-detail value-domain block (F1)", () => {
  it("always sends system_code and loops pages until short page (B9)", async () => {
    api.getTableDetail.mockResolvedValue({
      data: {
        id: 1,
        system_code: "HIS_SOURCE",
        source_code: "his_source_10_10_10_15",
        schema_name: "HIS",
        table_name: "PAT_VISIT",
        table_name_cn: null,
        table_role: null,
        comment: "住院主表",
        column_count: 40,
        column_count_actual: 2,
        domain: "病案",
        source: "his_source_10_10_10_15",
        row_count_stats: null,
        grain: null,
        pk: "PATIENT_ID+VISIT_ID",
        confidence: null,
        note: null,
        relation_count: 0
      }
    });
    api.getTableColumns.mockResolvedValue({
      data: [
        { column_id: 1, column_name: "DISCHARGE_DISPOSITION", data_type: "VARCHAR2", length: 1, nullable: "Y", comment: "离院方式" },
        { column_id: 2, column_name: "PATIENT_ID", data_type: "VARCHAR2", length: 18, nullable: "N", comment: "患者ID" }
      ]
    });
    api.getTableRelations.mockResolvedValue({ data: [] });
    api.getGraphNeighbors.mockResolvedValue({ data: { nodes: [], edges: [] } });
    // 第 1 页满 200 → 续拉；第 2 页 3 条 → 停止（循环拉全+上限 5 页）
    api.listValueDomains.mockImplementation((params: any) => {
      if (params.page === 1) {
        return Promise.resolve({
          data: {
            items: Array.from({ length: 200 }, (_, i) =>
              makeDomainItem({ id: i + 1, code: `c${i}` })
            ),
            total: 203
          }
        });
      }
      return Promise.resolve({
        data: {
          items: [
            makeDomainItem({ id: 201, code: "201" }),
            makeDomainItem({ id: 202, code: "202" }),
            makeDomainItem({ id: 203, code: "203" })
        ],
        total: 203
        }
      });
    });

    const w = mountPage(TableDetailPage);
    await flushPromises();
    expect(api.listValueDomains).toHaveBeenCalledTimes(2);
    expect(api.listValueDomains).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        system_code: "HIS_SOURCE",
        schema_name: "HIS",
        table_name: "PAT_VISIT",
        page: 1,
        page_size: 200
      })
    );
    expect(api.listValueDomains).toHaveBeenNthCalledWith(2, expect.objectContaining({ page: 2 }));
    // 列粒度分组 + 暂无值域列提示
    const text = w.text();
    expect(text).toContain("DISCHARGE_DISPOSITION");
    expect(text).toContain("暂无值域");
    expect(text).toContain("PATIENT_ID");
    w.unmount();
  });

  it("skips the request entirely when system_code is absent (anti cross-source)", async () => {
    api.getTableDetail.mockResolvedValue({
      data: {
        id: 1,
        system_code: null as any,
        schema_name: "HIS",
        table_name: "PAT_VISIT",
        comment: null,
        column_count: 1,
        column_count_actual: 0,
        domain: null,
        source: null,
        row_count_stats: null,
        grain: null,
        pk: null,
        confidence: null,
        note: null,
        relation_count: 0
      }
    });
    api.getTableColumns.mockResolvedValue({ data: [] });
    api.getTableRelations.mockResolvedValue({ data: [] });
    api.getGraphNeighbors.mockResolvedValue({ data: { nodes: [], edges: [] } });
    const w = mountPage(TableDetailPage);
    await flushPromises();
    expect(api.listValueDomains).not.toHaveBeenCalled();
    expect(w.text()).toContain("暂无值域");
    w.unmount();
  });
});
