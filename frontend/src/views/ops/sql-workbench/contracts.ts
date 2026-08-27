export function parseParameterObject(raw: string): Record<string, unknown> {
  const value = JSON.parse(raw.trim() || "{}");
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new Error("参数 JSON 必须是对象");
  }
  return value as Record<string, unknown>;
}
