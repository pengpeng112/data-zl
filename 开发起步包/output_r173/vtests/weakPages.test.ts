import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * r173 V-line weak-page source assertions (2026-09-01).
 * Weak pages = route-reachable views with zero test references
 * (algorithm output: output_r173/weak_pages.json). A failing assertion here is
 * recorded as problem evidence for the 173 problem list — these tests do NOT
 * enter the pnpm test gate.
 */
const FE = resolve(__dirname, "../../../frontend/src");

const page = (rel: string) => readFileSync(resolve(FE, rel), "utf-8");

describe("weak page: views/identity/authorizations/index.vue", () => {
  const src = page("views/identity/authorizations/index.vue");
  it("loads data through the typed api layer (not raw http)", () => {
    expect(src).toMatch(/from "@\/api\/(permissions|identity)"/);
    expect(src).not.toMatch(/http\.request/);
  });
  it("binds tables with data + loading state", () => {
    expect(src).toMatch(/el-table[^>]*:data=/);
    expect(src).toMatch(/v-loading="loading\w*"/);
  });
  it("handles load errors visibly (catch -> message)", () => {
    expect(src).toMatch(/catch[\s\S]{0,120}ElMessage\.error/);
  });
  it("bootstraps on mount", () => {
    expect(src).toMatch(/onMounted/);
  });
});

describe("weak page: views/identity/departments/index.vue", () => {
  const src = page("views/identity/departments/index.vue");
  it("loads via @/api/identity typed wrappers", () => {
    expect(src).toMatch(/from "@\/api\/identity"/);
  });
  it("binds el-table with data + loading", () => {
    expect(src).toMatch(/el-table[^>]*:data=/);
    expect(src).toMatch(/v-loading="loading"/);
  });
  it("paginates locally or remotely", () => {
    expect(src).toMatch(/(el-pagination|page_size|pageSize)/);
  });
  it("handles load errors visibly (catch -> message)", () => {
    expect(src).toMatch(/catch[\s\S]{0,120}ElMessage\.error/);
  });
});

describe("weak page: views/identity/roles/index.vue", () => {
  const src = page("views/identity/roles/index.vue");
  it("gates write actions by permissions (hasPerms/v-perms)", () => {
    expect(src).toMatch(/(hasPerms|v-perms)/);
  });
  it("shows loading states for role list and matrix", () => {
    expect(src).toMatch(/v-loading="loading"/);
    expect(src).toMatch(/v-loading="matrixLoading"/);
  });
  it("handles save errors visibly (catch -> message)", () => {
    expect(src).toMatch(/catch[\s\S]{0,160}ElMessage\.error/);
  });
  it("guards navigation away with unsaved changes (onBeforeRouteLeave or confirm)", () => {
    expect(src).toMatch(/(onBeforeRouteLeave|ElMessageBox\.confirm)/);
  });
});

describe("weak page: views/query-center/accuracy/index.vue", () => {
  const src = page("views/query-center/accuracy/index.vue");
  it("loads via @/api/query-center typed wrappers", () => {
    expect(src).toMatch(/from "@\/api\/query-center"/);
  });
  it("gates action buttons with v-perms", () => {
    expect(src).toMatch(/v-perms/);
  });
  it("binds evaluation cases table", () => {
    expect(src).toMatch(/el-table[^>]*:data="evalSummary/);
  });
  it("handles load errors (catch present)", () => {
    expect(src).toMatch(/catch/);
  });
});

describe("weak page: views/error/404.vue and 500.vue", () => {
  it("404 renders status and a way back", () => {
    const src = page("views/error/404.vue");
    expect(src).toMatch(/404/);
    expect(src).toMatch(/(router\.(push|back|replace)|to="\/")/);
  });
  it("500 renders status and a way back", () => {
    const src = page("views/error/500.vue");
    expect(src).toMatch(/500/);
    expect(src).toMatch(/(router\.(push|back|replace)|to="\/")/);
  });
});
