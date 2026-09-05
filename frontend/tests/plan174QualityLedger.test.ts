import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

/** 174 S7：质量治理台账前端——路由兼容、API 契约、allowed_actions、409 处理、导出。 */
describe("plan174 quality governance ledger", () => {
  it("routes: 质量管理默认入口切到台账，旧路径全部保留", () => {
    const qualityRouter = source("src/router/modules/quality.ts");
    expect(qualityRouter).toContain('redirect: "/quality/issues"');
    expect(qualityRouter).toContain('path: "/quality/issues"');
    expect(qualityRouter).toContain('path: "/quality/issues/mine"');
    expect(qualityRouter).toContain('path: "/quality/issues/department"');
    expect(qualityRouter).toContain('path: "/quality/issues/:id"');
    expect(qualityRouter).toContain('path: "/quality/controls"');
    expect(qualityRouter).toContain('path: "/quality/observations"');
    // 旧探查发现路径保留且仍可从菜单进入
    expect(qualityRouter).toContain('path: "/probe-findings"');
    expect(qualityRouter).toContain('title: "探查发现"');
  });

  it("routes: /asset/quality 路径不变、显示名改为元数据质控", () => {
    const assetRouter = source("src/router/modules/asset.ts");
    expect(assetRouter).toContain('path: "/asset/quality"');
    expect(assetRouter).toContain('title: "元数据质控"');
    expect(assetRouter).not.toContain('title: "数据质量"');
  });

  it("api: 三前缀契约 + 命令 envelope + 导出 POST/blob", () => {
    const api = source("src/api/quality.ts");
    expect(api).toContain('"/api/v1/quality-issues"');
    expect(api).toContain('"/api/v1/quality-controls"');
    expect(api).toContain('"/api/v1/quality-observations"');
    // 命令端点全集（专用命令，不允许通用 PATCH 改状态）
    for (const ep of [
      "/assign",
      "/transition",
      "/request-verification",
      "/verify",
      "/accept-risk",
      "/mark-false-positive",
      "/comment"
    ]) {
      expect(api).toContain(`\${id}${ep}`);
    }
    expect(api).toContain("/api/v1/quality-issues/export");
    expect(api).toContain("/api/v1/quality-issues/assignment-options/departments");
    expect(api).toContain("/api/v1/quality-issues/assignment-options/persons");
    // ingest 是内部受控端点，前端不封装（174 §8.2）
    // 导出走 POST+body+blob（六硬约束之五/六）
    const exportFn = api.slice(api.indexOf("exportQualityIssues"));
    expect(exportFn.slice(0, 400)).toContain('"post"');
    expect(exportFn.slice(0, 400)).toContain("responseType: \"blob\"");
    // 乐观锁 envelope 类型
    expect(api).toContain("expected_lock_version");
  });

  it("ledger page: 范围切换（mine/department/all）与逾期标记", () => {
    const page = source("src/views/quality/issues/index.vue");
    expect(page).toContain('value="mine"');
    expect(page).toContain('value="department"');
    expect(page).toContain('value="all"');
    expect(page).toContain("scope: activeScope.value");
    expect(page).toContain("仅逾期");
    // 台账默认 all；我的/科室走独立 path；KeepAlive 随路由刷新
    expect(page).toContain('else activeScope.value = "all"');
    expect(page).toContain("path.endsWith(\"/mine\")");
    expect(page).toContain("onActivated");
    expect(page).toContain("watch(");
    // read_all 403 回退提示
    expect(page).toContain("已回退本人范围");
    // 手工登记 + 导出入口有权限码
    expect(page).toContain('v-perms="\'quality.issue.create\'"');
    expect(page).toContain('v-perms="\'quality.issue.export\'"');
  });

  it("detail page: 按钮全部走 allowed_actions，乐观锁 409 刷新", () => {
    const page = source("src/views/quality/issue-detail/index.vue");
    expect(page).toContain("function can(action: string)");
    // 关键动作按钮受 allowed_actions 控制（模板内单引号形态）
    for (const action of [
      "acknowledge",
      "assign",
      "request_verification",
      "verify",
      "accept_risk",
      "mark_false_positive",
      "reopen"
    ]) {
      expect(page).toContain(`can('${action}')`);
    }
    // 所有命令都携带 expected_lock_version
    expect((page.match(/expected_lock_version/g) || []).length).toBeGreaterThanOrEqual(8);
    // 409 冲突提示并刷新
    expect(page).toContain("已刷新为最新版本，请重试");
    // 双人验证提示
    expect(page).toContain("验证人不能是最后提交待复测的同一经办人");
    // 复发链链接
    expect(page).toContain("上一轮问题");
    // 事件时间线 + 观测两个 Tab
    expect(page).toContain('label="业务时间线"');
    expect(page).toContain('label="关联观测"');
  });

  it("detail page: 状态命令走专用端点而非通用 PATCH 状态", () => {
    const page = source("src/views/quality/issue-detail/index.vue");
    // patch 只提交非状态字段
    const editFn = page.slice(page.indexOf("function submitEdit"));
    expect(editFn).not.toContain("status");
    expect(editFn).toContain("fields.action_plan");
  });

  it("probe-findings page: 保留原功能并新增台账入口", () => {
    const page = source("src/views/asset/probe-findings/index.vue");
    expect(page).toContain("查看台账");
    expect(page).toContain('v-perms="\'quality.issue.read\'"');
    // 原筛选/导出仍在
    expect(page).toContain("doExport");
    expect(page).toContain("exportProbeFindings");
  });

  it("controls page: 状态/检测器渲染与激活/执行/废弃权限码", () => {
    const page = source("src/views/quality/controls/index.vue");
    expect(page).toContain('v-perms="\'quality.control.manage\'"');
    expect(page).toContain('v-perms="\'quality.control.run\'"');
    expect(page).toContain("detector_kind");
    expect(page).toContain("不伪造结果");
  });

  it("observations page: 不可变流水只读（无编辑按钮）", () => {
    const page = source("src/views/quality/observations/index.vue");
    expect(page).not.toContain("el-dialog");
    expect(page).not.toContain("http.post");
    expect(page).toContain("historical_precision");
  });
});
