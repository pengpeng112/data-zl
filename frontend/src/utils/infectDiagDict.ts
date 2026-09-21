export type InfectDiagOption = {
  code: string;
  name: string;
  input_code: string;
};

export function matchInfectDiagDict(
  items: InfectDiagOption[],
  query: string
): InfectDiagOption[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter(item => {
    const name = (item.name || "").toLowerCase();
    const code = (item.code || "").toLowerCase();
    const pinyin = (item.input_code || "").toLowerCase();
    return name.includes(q) || code.includes(q) || pinyin.includes(q);
  });
}
