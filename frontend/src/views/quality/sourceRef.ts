/**
 * 178 R4（L1，166 P2 最小切片）：质量台账观测 ↔ 探查发现互链的纯函数。
 *
 * 后端写入约定（quality_governance_adapters.py）：
 *   source_kind = "probe_finding"
 *   source_record_ref = `asset_probe_findings:{finding_id}`
 * 三页共用解析，禁止各自手写正则造成口径漂移。
 */

export interface ProbeFindingRef {
  type: "probe_finding";
  id: number;
}

/** 匹配 `^asset_probe_findings:(\d+)$` → { type, id }；其它/空 → null */
export function parseProbeFindingRef(sourceRecordRef: string | null | undefined): ProbeFindingRef | null {
  if (!sourceRecordRef) return null;
  const match = /^asset_probe_findings:(\d+)$/.exec(sourceRecordRef.trim());
  if (!match) return null;
  const id = Number(match[1]);
  return Number.isInteger(id) && id > 0 ? { type: "probe_finding", id } : null;
}

/** 正向链接目标：现有路由 /probe-findings（router/modules/quality.ts），不发明新 path */
export function probeFindingLink(ref: ProbeFindingRef): string {
  return `/probe-findings?finding_id=${ref.id}`;
}

/** 反查观测时的精确匹配串 */
export function probeFindingSourceRef(id: number): string {
  return `asset_probe_findings:${id}`;
}

/** ② 探查页消费路由 query：finding_id 缺省/非数字 → null（忽略） */
export function findingIdFromRouteQuery(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value;
  const id = Number(raw);
  return Number.isInteger(id) && id > 0 ? id : null;
}
