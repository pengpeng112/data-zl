/**
 * 153 F1：API 层通用类型单份定义。
 *
 * 此前 ApiResponse 在 8 个 api 文件、PageData 在 6 个 api 文件重复定义；
 * 统一收敛于此，各文件以 `export type { ... } from "./types"` 再导出，
 * 既有 `from "./asset"` 等导入路径保持兼容。
 */

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface PageData<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
  /** 部分分页端点附带聚合统计（如 identity 台账列表）。 */
  stats?: {
    total?: number;
    active?: number;
    inactive?: number;
    source_count?: number;
  };
}
