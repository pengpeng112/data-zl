import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { requestContentLabel, requestStatusLabel } from "@/views/identity/permission-requests/contracts";
import { parseImportText } from "@/views/dict/general/contracts";
import { changeTypeColor, changeTypeLabel, severityLabel } from "@/views/metadata-changes/labels";

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), "utf-8");
}

describe("146 stage C1 permission request contracts", () => {
  it("renders role and data-scope request content, including legacy payload shape", () => {
    expect(requestContentLabel({
      entity_type: "user_role",
      request_content: { role_code: "identity_admin" },
      request_payload: undefined
    })).toBe("角色：identity_admin");
    expect(requestContentLabel({
      entity_type: "user_data_scope",
      request_content: { scope_type: "system", system_code: "HIS" },
      request_payload: undefined
    })).toBe("数据范围：system / HIS");
    expect(requestContentLabel({
      entity_type: "user_data_scope",
      request_content: null,
      request_payload: { scope_type: "source", source_code: "ods_8_216" }
    })).toBe("数据范围：source / ods_8_216");
    expect(requestContentLabel({ entity_type: "user_role", request_content: {}, request_payload: undefined })).toBe("角色：-");
  });

  it("maps request lifecycle statuses to Chinese labels with unknown passthrough", () => {
    expect(requestStatusLabel("pending")).toBe("待审批");
    expect(requestStatusLabel("approved")).toBe("已通过");
    expect(requestStatusLabel("rejected")).toBe("已驳回");
    expect(requestStatusLabel("executed")).toBe("已执行");
    expect(requestStatusLabel("revoked")).toBe("已撤销");
    expect(requestStatusLabel("weird_state")).toBe("weird_state");
    expect(requestStatusLabel(undefined)).toBe("-");
  });

  it("keeps dot-form permissions, server pagination and no confirmation dialogs on the page", () => {
    const page = source("src/views/identity/permission-requests/index.vue");
    for (const perm of [
      "identity.permission_request.create",
      "identity.permission_request.approve",
      "identity.permission_request.execute"
    ]) {
      expect(page).toContain(`v-perms="'${perm}'`);
    }
    expect(page).toContain("el-pagination");
    expect(page).toContain("getMyPermissionRequests({ page: minePage.value, page_size: pageSize })");
    expect(page).toContain("getPendingPermissionRequests({ page: pendingPage.value, page_size: pageSize })");
    expect(page).toContain("申请人不能审批自己的请求");
    expect(page).not.toContain("ElMessageBox");
    expect(page).not.toContain("http.request");
    expect(page).not.toContain(":auth");
  });

  it("types the permission request API layer against the canonical endpoints", () => {
    const api = source("src/api/permissions.ts");
    for (const fragment of [
      "get\", \"/api/v1/permission-requests/mine\"",
      "get\", \"/api/v1/permission-requests/pending\"",
      "post\", \"/api/v1/permission-requests\"",
      "/execute",
      "/revoke",
      // 153 F1：PageData 单源化后此处为再导出（types.ts 单份定义）。
      'export type { ApiResponse, PageData } from "./types";',
      "request_content: Record<string, unknown>"
    ]) {
      expect(api).toContain(fragment);
    }
  });
});

describe("146 stage C2 dict/general contracts", () => {
  it("parses pasted JSON arrays and CSV lines into import items", () => {
    const json = parseImportText(
      '[{"system_item_code":"QD","system_item_name_cn":"每日一次"},{"system_item_code":"TID","system_item_name_cn":"每日三次"}]'
    );
    expect(json.error).toBeNull();
    expect(json.items).toHaveLength(2);
    expect(json.items[0]).toMatchObject({ system_item_code: "QD", system_item_name_cn: "每日一次" });

    const csv = parseImportText("QD,每日一次\nTID\t每日三次");
    expect(csv.error).toBeNull();
    expect(csv.items).toEqual([
      { system_item_code: "QD", system_item_name_cn: "每日一次" },
      { system_item_code: "TID", system_item_name_cn: "每日三次" }
    ]);
    expect(parseImportText("QD").items[0].system_item_name_cn).toBe("QD");

    expect(parseImportText("").error).toContain("粘贴");
    expect(parseImportText("[{bad json").error).toContain("JSON 解析失败");
    expect(parseImportText("[1,2]").items).toEqual([]);
  });

  it("targets the canonical /api/v1/dictionaries endpoints with typed DTOs", () => {
    const api = source("src/api/dict.ts");
    for (const fragment of [
      '"/api/v1/dictionaries/categories"',
      '"/api/v1/dictionaries/standard-items"',
      '"/api/v1/dictionaries/system-items"',
      "/system-items/${id}/enabled",
      '"/api/v1/dictionaries/mappings"',
      '"/api/v1/dictionaries/import"'
    ]) {
      expect(api).toContain(fragment);
    }
    expect(api).not.toContain("/dict-general");
    expect(api).toContain("standard_code: string");
    expect(api).toContain("system_item_code: string");
    expect(api).toContain("system_item_name_cn: string");
  });

  it("uses backend DTO fields, server pagination, backend-driven systems and dot permissions", () => {
    const page = source("src/views/dict/general/index.vue");
    expect(page).not.toContain("target_system");
    expect(page).not.toContain('prop="item_code"');
    expect(page).toContain("listSystems");
    expect(page).toContain("dict.general.edit");
    expect(page).toContain("dict.general.import");
    expect(page).toContain("dry_run: true");
    expect(page).toContain("setDictSystemItemEnabled");
    expect(page).toContain("raw_status");
    expect(page).toContain("el-pagination");
    expect(page).not.toContain("ElMessageBox");
    expect(page).not.toContain("http.request");
  });
});

describe("146 stage C3 metadata diff preview contracts", () => {
  it("labels real change types shared by both metadata pages", () => {
    expect(changeTypeLabel("column_data_type_changed")).toBe("字段类型变更");
    expect(changeTypeLabel("column_nullable_changed")).toBe("非空约束变更");
    expect(changeTypeLabel("column_length_changed")).toBe("字段长度变更");
    expect(changeTypeLabel("weird")).toBe("weird");
    expect(changeTypeColor("column_added")).toBe("success");
    expect(changeTypeColor("column_removed")).toBe("danger");
    expect(changeTypeColor("column_comment_changed")).toBe("warning");
    expect(severityLabel("high")).toBe("高");
  });

  it("splits zero-write preview from explicit event generation in the API layer", () => {
    const api = source("src/api/metadata.ts");
    expect(api).toContain('"/api/v1/metadata-changes/diff-preview"');
    expect(api).toContain('"/api/v1/metadata-changes/diff"');
    expect(api).toContain("Zero-write field-level preview");
    expect(api).toContain("idempotent per object key");
  });

  it("runs the read-only preview for 对比 and keeps generation as an explicit action", () => {
    const page = source("src/views/metadata-changes/diff/index.vue");
    expect(page).toContain("diffMetadataPreview({");
    expect(page).toContain("runMetadataDiff({");
    expect(page).toContain("生成变更事件");
    expect(page).toContain("v-perms=\"'metadata.snapshot.collect'\"");
    expect(page).toContain("只读预览，不落库");
    expect(page).toContain("skipped_existing");
    expect(page).toContain("el-pagination");
    expect(page).toContain('value="inline"');
    expect(page).toContain('value="side"');
    expect(page).not.toContain("http.request");
    // Changes list page consumes the shared labels and new value fields.
    const changes = source("src/views/metadata-changes/changes/index.vue");
    expect(changes).toContain('from "../labels"');
    expect(changes).toContain('prop="namespace"');
    expect(changes).toContain("row.before_value");
    expect(changes).toContain("row.after_value");
  });
});
