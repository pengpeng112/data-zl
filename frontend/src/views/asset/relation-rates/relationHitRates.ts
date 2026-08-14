export const SCENE_OPTIONS = [
  { value: "exam_inpatient", label: "检查·住院" },
  { value: "exam_outpatient", label: "检查·门诊" },
  { value: "lab_inpatient", label: "检验·住院" },
  { value: "lab_outpatient", label: "检验·门诊" },
  { value: "exam_mixed", label: "检查·未拆分" },
  { value: "lab_mixed", label: "检验·未拆分" }
] as const;

export const HIGHLIGHT_SCENES = [
  "exam_inpatient",
  "exam_outpatient",
  "lab_inpatient",
  "lab_outpatient"
] as const;

export function formatHitRate(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${(value * 100).toFixed(2)}%`;
}

export function hitRatePercent(value?: number | null): number {
  if (value === null || value === undefined || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(Math.round(value * 1000) / 10, 100));
}

export function pickHighlight<T extends { scene?: string | null; from_system_code?: string | null }>(
  items: T[],
  scene: string
): T | null {
  const matched = items.filter(item => item.scene === scene);
  return (
    matched.find(item => String(item.from_system_code || "").toUpperCase() === "DATA_CENTER") ||
    matched.find(item => String(item.from_system_code || "").toUpperCase() === "HIS_SOURCE") ||
    matched[0] ||
    null
  );
}

export function systemShortLabel(code?: string | null): string {
  const value = String(code || "").toUpperCase();
  if (value === "HIS_SOURCE") return "HISUSER";
  if (value === "DATA_CENTER") return "ODS";
  if (value === "JHEMR_VASTBASE") return "嘉和";
  return value || "-";
}
