import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import assetRoute from "@/router/modules/asset";
import {
  buildSystemTypeOptions,
  filterAndPaginateConnections,
  systemDetailToForm,
  validateWizardStep
} from "@/views/asset/systems/contracts";
import { snapshotOrderError } from "@/views/metadata-changes/diff/contracts";

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("146 stage B contracts", () => {
  it("B1 preserves system detail, unknown types, wizard validation and deterministic paging", () => {
    const form = systemDetailToForm({
      id: 1,
      system_code: "LEGACY",
      system_name_cn: "旧系统",
      system_type: "legacy_special",
      description_cn: "必须保留的说明"
    });
    expect(form.description_cn).toBe("必须保留的说明");
    expect(buildSystemTypeOptions([], form.system_type)).toContain("legacy_special");
    expect(validateWizardStep(0, { ...form, system_name_cn: "" }, [])).toContain("系统名称");
    expect(validateWizardStep(1, form, [])).toContain("至少加入");
    const page = filterAndPaginateConnections(
      [
        { system_code: "A", source_code: "A1", source_name_cn: "A1", db_type: "oracle" },
        { system_code: "A", source_code: "A2", source_name_cn: "A2", db_type: "mysql" },
        { system_code: "B", source_code: "B1", source_name_cn: "B1", db_type: "oracle" }
      ],
      { system_code: "A", db_type: "oracle" },
      1,
      10
    );
    expect(page).toMatchObject({ total: 1, items: [{ source_code: "A1" }] });
    expect(source("src/views/asset/systems/index.vue")).toContain("await getSystemDetail(row.system_code)");
  });

  it("B2 keeps classification and person_type as independent filters", () => {
    const persons = source("src/views/identity/persons/index.vue");
    expect(persons).toContain("classification: params.classification");
    expect(persons).toContain("person_type: params.person_type");
    expect(persons).toContain("multiple filterable allow-create");
    expect(persons).toContain("ReStatCard");
  });

  it("B3 validates same-source snapshot time order", () => {
    const snapshots = [
      { id: 1, snapshot_time: "2026-08-01T00:00:00Z" },
      { id: 2, snapshot_time: "2026-08-02T00:00:00Z" }
    ];
    expect(snapshotOrderError(1, 2, snapshots)).toBeNull();
    expect(snapshotOrderError(2, 1, snapshots)).toContain("必须早于");
    expect(snapshotOrderError(1, 1, snapshots)).toContain("不能相同");
    expect(source("src/views/metadata-changes/diff/index.vue")).not.toContain("value=\"his_8216\"");
  });

  it("B4 keeps canonical routes and one typed API layer with dot permissions", () => {
    const children = assetRoute.children || [];
    const main = children.find(route => route.path === "/asset/queries");
    const accuracy = children.find(route => route.path === "/asset/queries/accuracy");
    expect(main?.meta?.auths).toEqual(["query.view"]);
    expect(accuracy?.meta?.auths).toEqual(["query.view"]);
    const page = source("src/views/query-center/queries/index.vue");
    expect(page).not.toContain("http.request");
    expect(page).not.toContain("v-auth");
    expect(page).toContain("v-perms=\"'query.run'\"");
    expect(page).toContain("type=\"month\"");
    expect(page).toContain("sql_text: \"\"");
    expect(page).toContain("runSampleRows");
  });
});
