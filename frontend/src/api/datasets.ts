/** 193 B16：数据集 API（/api/v1/datasets，全部真实隔离/平台接口，无 mock） */
import { http } from "@/utils/http";
import type { ApiResponse } from "./types";

export interface DatasetListItem {
  dataset_code: string;
  title: string;
  purpose_code: string;
  grain: string;
  status: string | null;
  version: number | null;
  readable?: boolean;
  decision?: string;
}

export const listDatasets = () =>
  http.request<ApiResponse<DatasetListItem[]>>("get", "/api/v1/datasets");

export interface BatchDetail {
  run_id: string;
  status: string;
  counters: Record<string, number>;
  checkpoint_keys: number;
  error_class: string | null;
}

export const getDatasetBatch = (runId: string) =>
  http.request<ApiResponse<BatchDetail>>("get", `/api/v1/datasets/batches/${encodeURIComponent(runId)}`);
