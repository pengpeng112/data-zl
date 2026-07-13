import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("auth frontend contract", () => {
  it("user.ts points to /api/v1/auth endpoints", () => {
    const src = readFileSync(
      resolve(__dirname, "../src/api/user.ts"),
      "utf-8"
    );
    expect(src).toContain("/api/v1/auth/login");
    expect(src).toContain("/api/v1/auth/refresh");
    expect(src).toContain("/api/v1/auth/logout");
    expect(src).toContain("/api/v1/auth/me");
    expect(src).toContain("/api/v1/auth/change-password");
    expect(src).not.toMatch(/["']\/login["']/);
    expect(src).not.toMatch(/["']\/refresh-token["']/);
    expect(src).toContain("withCredentials: true");
  });

  it("auth.ts keeps access token in memory helpers and clears cookie TokenKey", () => {
    const src = readFileSync(
      resolve(__dirname, "../src/utils/auth.ts"),
      "utf-8"
    );
    expect(src).toContain("memoryAccessToken");
    expect(src).toContain("setMemoryAccessToken");
    expect(src).toContain("clearMemoryAccessToken");
    expect(src).toContain('Cookies.remove(TokenKey)');
    // localStorage profile must not keep usable access token
    expect(src).toMatch(/accessToken:\s*""/);
  });

  it("http client enables credentials and auth white list", () => {
    const src = readFileSync(
      resolve(__dirname, "../src/utils/http/index.ts"),
      "utf-8"
    );
    expect(src).toContain("withCredentials: true");
    expect(src).toContain("/api/v1/auth/login");
    expect(src).toContain("/api/v1/auth/refresh");
  });
});
