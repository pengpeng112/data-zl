import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  findingIdFromRouteQuery,
  parseProbeFindingRef,
  probeFindingLink,
  probeFindingSourceRef
} from "@/views/quality/sourceRef";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

/**
 * 178 R4（L1，166 P2 最小切片）：质量台账 ↔ 探查发现互链。
 * ① 台账观测来源列 scoped-slot 正向链接；② 探查页消费 query.finding_id；
 * ③ 探查行经 listQualityObservations 反查 issue_id 跳台账详情。
 */
describe("plan178 R4 sourceRef pure functions", () => {
  it("parses asset_probe_findings:{id} refs", () => {
    expect(parseProbeFindingRef("asset_probe_findings:12")).toEqual({ type: "probe_finding", id: 12 });
    expect(parseProbeFindingRef("  asset_probe_findings:7  ")).toEqual({ type: "probe_finding", id: 7 });
    expect(parseProbeFindingRef("asset_probe_findings:0")).toBeNull();
    expect(parseProbeFindingRef("asset_probe_findings:-3")).toBeNull();
    expect(parseProbeFindingRef("asset_probe_findings:12:x")).toBeNull();
    expect(parseProbeFindingRef("asset_probe_findings:abc")).toBeNull();
    expect(parseProbeFindingRef("probe_run:12")).toBeNull();
    expect(parseProbeFindingRef("")).toBeNull();
    expect(parseProbeFindingRef(null)).toBeNull();
    expect(parseProbeFindingRef(undefined)).toBeNull();
  });

  it("builds the forward link on the existing /probe-findings route", () => {
    expect(probeFindingLink({ type: "probe_finding", id: 12 })).toBe("/probe-findings?finding_id=12");
    expect(probeFindingSourceRef(12)).toBe("asset_probe_findings:12");
  });

  it("ignores missing or non-numeric finding_id query values", () => {
    expect(findingIdFromRouteQuery("12")).toBe(12);
    expect(findingIdFromRouteQuery(["12", "9"])).toBe(12);
    expect(findingIdFromRouteQuery("")).toBeNull();
    expect(findingIdFromRouteQuery(undefined)).toBeNull();
    expect(findingIdFromRouteQuery("abc")).toBeNull();
    expect(findingIdFromRouteQuery("12x")).toBeNull();
    expect(findingIdFromRouteQuery("0")).toBeNull();
    expect(findingIdFromRouteQuery("-1")).toBeNull();
  });
});

describe("plan178 R4 cross-link wiring (source locks)", () => {
  it("issue-detail + observations render source column via scoped-slot on row.source_record_ref", () => {
    for (const page of [
      "src/views/quality/issue-detail/index.vue",
      "src/views/quality/observations/index.vue"
    ]) {
      const src = source(page);
      expect(src).toContain("parseProbeFindingRef(row.source_record_ref)");
      expect(src).toContain('label="来源"');
      expect(src).not.toMatch(/prop="source_kind" label="来源"/);
    }
  });

  it("probe-findings consumes route query.finding_id with useRoute + watch", () => {
    const src = source("src/views/asset/probe-findings/index.vue");
    expect(src).toContain("useRoute");
    expect(src).toContain("route.query.finding_id");
    expect(src).toContain("未在当前筛选结果中找到该发现");
    // 不自动清筛选盲扫：无 resetFilter 触发于 consume 路径
    expect(src).toContain("lastMissingFindingId");
  });

  it("probe-findings reverse lookup uses existing listQualityObservations, button hidden when no match", () => {
    const src = source("src/views/asset/probe-findings/index.vue");
    expect(src).toContain('listQualityObservations({ source_kind: "probe_finding", page: 1, page_size: 100 })');
    expect(src).toContain("probeFindingSourceRef(findingId)");
    expect(src).toMatch(/v-if="ledgerIssueId !== null"/);
    expect(src).toContain("查看质量台账");
    expect(src).toMatch(/router\.push\(`\/quality\/issues\/\$\{ledgerIssueId\.value\}`\)/);
    // 失败隐藏而非错误态：catch 里重置为 null，不弹 ElMessage.error
    const fnStart = src.indexOf("async function resolveLedgerIssue");
    const fnBlock = src.slice(fnStart, src.indexOf("function goLedgerIssue"));
    expect(fnBlock).toContain("ledgerIssueId.value = null");
    expect(fnBlock).not.toContain("ElMessage.error");
    // 不新增后端：API 层只 import 既有函数
    expect(src).toMatch(/import \{ listQualityObservations, type QualityObservationItem \} from "@\/api\/quality"/);
  });
});
