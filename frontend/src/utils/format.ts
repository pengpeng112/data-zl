/**
 * Shared formatting helpers (146 D2).
 */

/** Thousands-separated number with a safe fallback for null/NaN. */
export function formatNumber(value: number | null | undefined, fallback = "-"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return value.toLocaleString("zh-CN");
}

/** ISO/local datetime -> `YYYY-MM-DD HH:mm`, invalid values fall back. */
export function formatTime(value?: string | null, fallback = "-"): string {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

const TRUTHY = new Set(["y", "yes", "true", "1", "是"]);
const FALSY = new Set(["n", "no", "false", "0", "否"]);

/** Nullable flag display: Y/N, true/false, case-insensitive, booleans. */
export function nullableLabel(value: unknown, fallback = "-"): string {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number") return value === 1 ? "是" : value === 0 ? "否" : fallback;
  const text = String(value).trim().toLowerCase();
  if (TRUTHY.has(text)) return "是";
  if (FALSY.has(text)) return "否";
  return String(value);
}
