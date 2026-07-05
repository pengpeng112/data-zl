<template>
  <div class="identity-departments">
    <el-card shadow="never">
      <template #header>
        <span>科室基线列表</span>
      </template>
      <el-table v-loading="loading" :data="items" stripe @row-click="showDetail">
        <el-table-column prop="dept_code" label="科室编码" width="140" />
        <el-table-column prop="dept_name_cn" label="科室名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="dept_type" label="科室类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.dept_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_system" label="来源系统" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ row.source_system }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'active' ? 'success' : 'warning'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="科室详情" width="600px" destroy-on-close>
      <div v-if="detailLoading" style="text-align:center;padding:40px">
        <el-icon class="is-loading"><i-ep-loading /></el-icon>
      </div>
      <el-descriptions v-else-if="detail" :column="2" border>
        <el-descriptions-item label="科室编码">{{ detail.dept_code }}</el-descriptions-item>
        <el-descriptions-item label="科室名称">{{ detail.dept_name_cn }}</el-descriptions-item>
        <el-descriptions-item label="科室类型">{{ detail.dept_type }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag size="small" :type="detail.status === 'active' ? 'success' : 'warning'">
            {{ detail.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="来源系统">{{ detail.source_system }}</el-descriptions-item>
        <el-descriptions-item label="来源系统编码">{{ detail.source_dept_code }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ detail.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间" :span="2">{{ detail.updated_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { getDepartments, getDepartmentDetail } from "@/api/identity";

const items = ref<any[]>([]);
const loading = ref(false);

const dialogVisible = ref(false);
const detailLoading = ref(false);
const detail = ref<any>(null);

async function loadData() {
  loading.value = true;
  try {
    const res = await getDepartments();
    items.value = res.data ?? [];
  } catch {
    ElMessage.error("加载科室列表失败");
  } finally {
    loading.value = false;
  }
}

async function showDetail(row: any) {
  dialogVisible.value = true;
  detailLoading.value = true;
  detail.value = null;
  try {
    const res = await getDepartmentDetail(row.dept_code);
    detail.value = res.data;
  } catch {
    ElMessage.error("加载科室详情失败");
  } finally {
    detailLoading.value = false;
  }
}

onMounted(loadData);
</script>
