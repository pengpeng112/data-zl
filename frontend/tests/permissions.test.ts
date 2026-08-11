import { describe, expect, it } from "vitest";
import { hasUserPermissions } from "@/utils/permission";

describe("button permission contract", () => {
  it("uses the user's effective permissions, not route meta auths", () => {
    const profile = { permissions: ["source.manage"] };
    expect(hasUserPermissions("source.manage", profile)).toBe(true);
    expect(hasUserPermissions("asset.admin.view", profile)).toBe(false);
  });

  it("keeps administrator and wildcard grants", () => {
    expect(hasUserPermissions("any.write.action", { roles: ["platform_admin"] })).toBe(true);

    const profile = { permissions: ["*:*:*"] };
    expect(hasUserPermissions("ops.sql.execute", profile)).toBe(true);
    expect(hasUserPermissions("asset.annotation", profile)).toBe(true);
    expect(hasUserPermissions("source.manage", { permissions: ["source.*"] })).toBe(false);
  });

  it("requires every code when a button declares multiple permissions", () => {
    const profile = { permissions: ["source.manage", "source.test"] };
    expect(hasUserPermissions(["source.manage", "source.test"], profile)).toBe(true);
    expect(hasUserPermissions(["source.manage", "source.credential_manage"], profile)).toBe(false);
  });
});
