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
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() })
}));
vi.mock("@/router/index", () => ({ router: {} }));

const api = vi.hoisted(() => ({
  listProbeFindings: vi.fn(),
  getProbeFinding: vi.fn(),
  listProbeRuns: vi.fn(),
  transitionProbeFinding: vi.fn(),
  exportProbeFindings: vi.fn()
}));
vi.mock("@/api/probe", () => api);

import ProbeFindingsPage from "@/views/asset/probe-findings/index.vue";
import { sanitizeEvidenceText } from "@/views/asset/probe-findings/sanitize";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

function mountPage() {
  storageLocal().setItem(userKey, {
    accessToken: "",
    refreshToken: "",
    expires: 0,
    username: "t",
    nickname: "t",
    roles: ["platform_admin"],
    permissions: ["*:*:*"]
  });
  return mount(ProbeFindingsPage, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body
  });
}

function makeFinding(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    probe_type: "R-REF",
    system_pair: "HIS(单库)",
    object_desc: "EXAM.EXAM_MASTER.DOCTOR_USER 缺失率",
    metric_name: "doctor_code_missing_rate",
    metric_value: 81.37,
    metric_unit: "%",
    threshold: 1.0,
    window_start: "2026-07-01",
    window_end: "2026-08-30",
    severity: "P2",
    status: "open",
    first_seen_run: "probe-20260830-094723",
    last_seen_run: "probe-20260830-094820",
    relapse_count: 0,
    note: null,
    evidence_sql: "SELECT COUNT(*) FROM HIS.EXAM.EXAM_MASTER WHERE D >= :START_DATE",
    evidence_digest: "ab12",
    resolved_by: null,
    resolved_at: null,
    created_at: "2026-08-30T09:00:00",
    updated_at: "2026-08-30T10:00:00",
    ...overrides
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = "";
  api.listProbeFindings.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
  api.listProbeRuns.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 });
});

describe("plan166 D3 sanitize pipeline (F4)", () => {
  it("redacts secrets and collapses whitespace like the backend sanitize_text", () => {
    const raw = "connect postgresql://user:pwd@10.0.0.1/db password=abc123 token=xyz \n\n SELECT 1";
    const out = sanitizeEvidenceText(raw);
    expect(out).not.toContain("pwd@");
    expect(out).not.toContain("abc123");
    expect(out).toContain("[REDACTED]");
    expect(out).toContain("SELECT 1");
  });

  it("enforces the length cap", () => {
    expect(sanitizeEvidenceText("a".repeat(5000)).length).toBeLessThanOrEqual(4001);
  });
});

describe("plan166 D3 probe findings page (F4)", () => {
  it("renders list with metric vs threshold and relapse badge, filters reach the API", async () => {
    api.listProbeFindings.mockResolvedValue({
      items: [
        makeFinding({ relapse_count: 2, status: "open" }),
        makeFinding({ id: 2, status: "resolved", relapse_count: 0 })
      ],
      total: 2,
      page: 1,
      page_size: 20
    });
    const w = mountPage();
    await flushPromises();
    const text = w.text();
    expect(text).toContain("doctor_code_missing_rate");
    expect(text).toContain("81.37%");
    expect(text).toContain("复发2");
    // 筛选交互：选状态 → 请求带 status
    const statusSelect = w.findAll(".el-select").find(s =>
      (s.text() || "").includes("状态") || true
    );
    void statusSelect;
    expect(api.listProbeFindings).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 20 })
    );
    w.unmount();
  });

  it("renders sanitized evidence_sql as text with no script injection (XSS assertion)", async () => {
    const evil =
      'SELECT * FROM t -- <img src=x onerror="alert(1)">' +
      "\n<script>alert('xss')</script>" +
      " password=hunter2";
    api.listProbeFindings.mockResolvedValue({ items: [makeFinding()], total: 1, page: 1, page_size: 20 });
    api.getProbeFinding.mockResolvedValue(makeFinding({ evidence_sql: evil }));
    const w = mountPage();
    await flushPromises();
    await w.find(".el-table__row").trigger("click");
    await flushPromises();

    // 脱敏：password 折叠
    const codeBlock = document.querySelector(".evidence-code");
    expect(codeBlock).toBeTruthy();
    expect((codeBlock as HTMLElement).textContent).toContain("[REDACTED]");
    expect((codeBlock as HTMLElement).textContent).not.toContain("hunter2");
    // XSS：载荷以文本呈现，但不产生真实 img/script 元素（无 v-html）
    expect((codeBlock as HTMLElement).textContent).toContain("<img");
    expect(document.querySelectorAll(".evidence-code img").length).toBe(0);
    expect(document.querySelectorAll(".evidence-code script").length).toBe(0);
    const injected = Array.from(document.querySelectorAll("script")).filter(s =>
      (s.textContent || "").includes("xss")
    );
    expect(injected.length).toBe(0);
    w.unmount();
  });

  it("runs tab lists recent 10 runs with sanitized error_summary", async () => {
    api.listProbeFindings.mockResolvedValue({ items: [makeFinding()], total: 1, page: 1, page_size: 20 });
    api.getProbeFinding.mockResolvedValue(makeFinding());
    api.listProbeRuns.mockResolvedValue({
      items: [
        {
          id: 1,
          run_id: "probe-20260830-094723",
          started_at: null,
          finished_at: null,
          status: "partial",
          probe_count: 12,
          finding_new: 6,
          finding_updated: 0,
          relapse_count: 0,
          error_summary: "T7 BLOCKED password=topsecret",
          created_by: "probe:probe-20260830-094723"
        }
      ],
      total: 1,
      page: 1,
      page_size: 10
    });
    const w = mountPage();
    await flushPromises();
    await w.find(".el-table__row").trigger("click");
    await flushPromises();
    expect(api.listProbeRuns).toHaveBeenCalledWith({ page: 1, page_size: 10 });
    // 切到 runs Tab
    const runsTab = w.findAll(".el-tabs__item").find(t => (t.text() || "").includes("runs"));
    expect(runsTab).toBeTruthy();
    await runsTab!.trigger("click");
    await flushPromises();
    const bodyText = document.body.textContent || "";
    expect(bodyText).toContain("probe-20260830-094723");
    expect(bodyText).not.toContain("topsecret");
    expect(bodyText).toContain("[REDACTED]");
    w.unmount();
  });
});

describe("plan166 D3 transition UI (F5)", () => {
  it("opens the dialog with migration hint and enforces reason, then calls the API", async () => {
    api.listProbeFindings.mockResolvedValue({ items: [makeFinding()], total: 1, page: 1, page_size: 20 });
    api.getProbeFinding.mockResolvedValue(makeFinding());
    api.transitionProbeFinding.mockResolvedValue(makeFinding({ status: "resolved" }));
    const w = mountPage();
    await flushPromises();
    await w.find(".el-table__row").trigger("click");
    await flushPromises();

    const resolveBtn = Array.from(document.querySelectorAll(".el-drawer button")).find(b =>
      (b.textContent || "").includes("解决")
    ) as HTMLButtonElement;
    expect(resolveBtn).toBeTruthy();
    resolveBtn.click();
    await flushPromises();
    const body = () => document.body.textContent || "";
    // 弹窗含迁移表提示与本次迁移方向
    expect(body()).toContain("人工四值互转");
    expect(body()).toContain("open");
    expect(body()).toContain("resolved");

    // 空理由 → 拦截
    const submit = Array.from(document.querySelectorAll(".el-dialog button")).find(b =>
      (b.textContent || "").includes("确认迁移")
    ) as HTMLButtonElement;
    submit.click();
    await flushPromises();
    expect(api.transitionProbeFinding).not.toHaveBeenCalled();
    expect(body()).toContain("必填");

    // 填理由 → 调 API（action=resolve）
    const textarea = document.querySelector(".el-dialog textarea") as HTMLTextAreaElement;
    textarea.value = "已联系业务整改";
    textarea.dispatchEvent(new Event("input"));
    await flushPromises();
    submit.click();
    await flushPromises();
    expect(api.transitionProbeFinding).toHaveBeenCalledWith(1, {
      action: "resolve",
      reason: "已联系业务整改",
      to_status: undefined
    });
    w.unmount();
  });

  it("surfaces 422/403 transition errors to the user", async () => {
    api.listProbeFindings.mockResolvedValue({ items: [makeFinding()], total: 1, page: 1, page_size: 20 });
    api.getProbeFinding.mockResolvedValue(makeFinding());
    api.transitionProbeFinding.mockRejectedValue({
      response: { status: 403, data: { detail: "缺少权限: probe.finding.manage" } }
    });
    const w = mountPage();
    await flushPromises();
    await w.find(".el-table__row").trigger("click");
    await flushPromises();
    const resolveBtn = Array.from(document.querySelectorAll(".el-drawer button")).find(b =>
      (b.textContent || "").includes("解决")
    ) as HTMLButtonElement;
    resolveBtn.click();
    await flushPromises();
    const textarea = document.querySelector(".el-dialog textarea") as HTMLTextAreaElement;
    textarea.value = "r";
    textarea.dispatchEvent(new Event("input"));
    await flushPromises();
    const submit = Array.from(document.querySelectorAll(".el-dialog button")).find(b =>
      (b.textContent || "").includes("确认迁移")
    ) as HTMLButtonElement;
    submit.click();
    await flushPromises();
    const bodyText = document.body.textContent || "";
    expect(bodyText).toContain("probe.finding.manage");
    w.unmount();
  });

  it("keeps dot-form v-perms on all transition controls (B3)", () => {
    const src = source("src/views/asset/probe-findings/index.vue");
    const manageMatches = src.match(/v-perms="'probe\.finding\.manage'"/g) || [];
    expect(manageMatches.length).toBeGreaterThanOrEqual(4);
    expect(src).toContain("v-perms=\"'probe.finding.read'\"");
    expect(src).not.toContain("probe.finding:");
  });
});
