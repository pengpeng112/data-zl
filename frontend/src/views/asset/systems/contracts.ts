import type { AssetSourceItem, AssetSystemItem } from "@/api/asset";

export interface SystemFormValue {
  system_code: string;
  system_name_cn: string;
  system_type: string;
  target_host: string;
  description_cn: string;
  status: string;
}

const DEFAULT_SYSTEM_TYPES = ["business", "clinical", "platform", "external"];

export function buildSystemTypeOptions(
  systems: AssetSystemItem[],
  current?: string | null
): string[] {
  return Array.from(
    new Set(
      [...DEFAULT_SYSTEM_TYPES, ...systems.map(item => item.system_type), current]
        .map(value => String(value || "").trim())
        .filter(Boolean)
    )
  );
}

export function systemDetailToForm(detail: Partial<AssetSystemItem>): SystemFormValue {
  return {
    system_code: detail.system_code || "",
    system_name_cn: detail.system_name_cn || "",
    system_type: detail.system_type || "business",
    target_host: detail.target_host || "",
    description_cn: detail.description_cn || "",
    status: detail.status || "active"
  };
}

export function validateWizardStep(
  step: number,
  form: SystemFormValue,
  connections: Array<{ source_code?: string; target_host?: string }>
): string | null {
  if (step === 0 && (!form.system_code.trim() || !form.system_name_cn.trim())) {
    return "请填写系统编码和系统名称";
  }
  if (step === 1 && connections.length === 0) {
    return "请至少加入一个数据连接";
  }
  return null;
}

export function filterAndPaginateConnections(
  rows: AssetSourceItem[],
  filters: { system_code?: string; db_type?: string },
  page: number,
  pageSize: number
) {
  const filtered = rows.filter(row => {
    if (filters.system_code && row.system_code !== filters.system_code) return false;
    if (filters.db_type && row.db_type !== filters.db_type) return false;
    return true;
  });
  const safePage = Math.max(1, page);
  const start = (safePage - 1) * pageSize;
  return { total: filtered.length, items: filtered.slice(start, start + pageSize) };
}
