/**
 * 153 F5：loadSystemNames 两份合一（quality/tables 各自内联）。
 */
import { listSystems } from "@/api/asset";

export async function fetchSystemNameMap(): Promise<Record<string, string>> {
  try {
    const res = await listSystems();
    const map: Record<string, string> = {};
    for (const item of res.data || []) {
      if (item.system_code) map[item.system_code] = item.system_name_cn || item.system_code;
    }
    return map;
  } catch {
    // 目录接口不可用时回退空映射（调用方以编码展示）。
    return {};
  }
}
