<script setup lang="ts">
import { ref, onMounted } from "vue";
import { http } from "@/utils/http";
import { ElMessage } from "element-plus";

interface AuditLog {
  id: number;
  module: string;
  entity_type: string;
  entity_ref: string;
  action: string;
  operator: string;
  created_at: string;
}

const tableData = ref<AuditLog[]>([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);

function actionTagType(action: string): any {
  const map: Record<string, string> = {
    "create": "", "approve": "success", "reject": "danger",
    "execute": "primary", "success": "success", "failed": "danger"
  };
  return map[action] || "info";
}

async function fetchData() {
  loading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/govern/audit-logs", {
      params: { module: "ops", page: page.value, page_size: pageSize.value }
    });
    tableData.value = res.data?.items || [];
    total.value = res.data?.total || 0;
  } catch {
    ElMessage.error("获取审计日志失败");
  } finally {
    loading.value = false;
  }
}

function handlePageChange(p: number) {
  page.value = p;
  fetchData();
}

function handleSizeChange(s: number) {
  pageSize.value = s;
  page.value = 1;
  fetchData();
}

onMounted(fetchData);
</script>

<template>
  <div>
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>运维审计日志</span>
          <el-button @click="fetchData">刷新</el-button>
        </div>
      </template>
      <el-table :data="tableData" v-loading="loading" size="small">
        <el-table-column prop="id" label="日志ID" width="80" />
        <el-table-column prop="entity_type" label="实体类型" width="120" />
        <el-table-column prop="entity_ref" label="实体引用" width="100" />
        <el-table-column prop="action" label="操作" width="100">
          <template #default="{ row }">
            <el-tag :type="actionTagType(row.action)" size="small">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="操作人" width="120" />
        <el-table-column prop="created_at" label="时间" width="180" />
      </el-table>
      <div style="display:flex;justify-content:flex-end;margin-top:16px">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>
