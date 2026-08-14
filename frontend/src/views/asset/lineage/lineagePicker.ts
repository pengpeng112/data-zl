export type ImpactTableOption = {
  value: string;
  label: string;
  schema?: string;
  table?: string;
};

export function impactTableValue(schema?: string | null, table?: string | null): string {
  const schemaName = String(schema || "").trim();
  const tableName = String(table || "").trim();
  if (schemaName && tableName) return `${schemaName}.${tableName}`;
  return tableName;
}

export function impactTableLabel(item: {
  display_name?: string | null;
  table_name_cn?: string | null;
  schema_name?: string | null;
  table_name?: string | null;
  technical_name?: string | null;
}): string {
  const tech = String(item.technical_name || impactTableValue(item.schema_name, item.table_name) || "").trim();
  const cn = String(item.table_name_cn || item.display_name || "").trim();
  if (cn && tech && cn !== tech && cn !== item.table_name) return `${cn}（${tech}）`;
  return cn || tech;
}

export function optionFromCatalog(item: {
  display_name?: string | null;
  table_name_cn?: string | null;
  schema_name?: string | null;
  table_name?: string | null;
  technical_name?: string | null;
}): ImpactTableOption | null {
  const value = String(item.technical_name || impactTableValue(item.schema_name, item.table_name) || "").trim();
  if (!value) return null;
  return {
    value,
    label: impactTableLabel(item),
    schema: item.schema_name || value.split(".")[0],
    table: item.table_name || value.split(".").slice(1).join(".")
  };
}

export function parseImpactTableQuery(query: Record<string, unknown> | undefined): {
  systemCode: string;
  schemaName: string;
  table: string;
} {
  const raw = query || {};
  const table = String(raw.table || raw.table_name || "").trim();
  const schemaName = String(raw.schema || raw.schema_name || "").trim();
  const systemCode = String(raw.system_code || raw.system || "").trim();
  if (table.includes(".")) {
    const [schema, name] = table.split(".", 2);
    return { systemCode, schemaName: schemaName || schema, table };
  }
  return {
    systemCode,
    schemaName,
    table: impactTableValue(schemaName, table)
  };
}

export function mergeTableOptions(current: ImpactTableOption[], next: ImpactTableOption[]): ImpactTableOption[] {
  const seen = new Set<string>();
  const merged: ImpactTableOption[] = [];
  for (const item of [...next, ...current]) {
    if (!item.value || seen.has(item.value)) continue;
    seen.add(item.value);
    merged.push(item);
  }
  return merged.slice(0, 80);
}
