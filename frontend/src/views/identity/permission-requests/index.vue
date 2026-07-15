<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { decidePermissionRequest, executePermissionRequest, getMyPermissionRequests, getPendingPermissionRequests } from "@/api/permissions";
const mine = ref<any[]>([]); const pending = ref<any[]>([]); const loading = ref(false);
async function load() { loading.value = true; try { const [a, b] = await Promise.all([getMyPermissionRequests(), getPendingPermissionRequests()]); mine.value = a.data || []; pending.value = b.data || []; } catch (e: any) { ElMessage.error(e?.response?.data?.detail || "加载权限申请失败"); } finally { loading.value = false; } }
async function decide(id: number, action: "approve" | "reject") { await decidePermissionRequest(id, action); ElMessage.success("处理成功"); await load(); }
async function execute(id: number) { await executePermissionRequest(id); ElMessage.success("执行成功"); await load(); }
onMounted(load);
</script>
<template>
  <div class="p-4"><RePageHeader title="权限申请审批" subtitle="申请、审批与执行分离，申请人不能审批自己的请求。" />
    <el-card v-loading="loading" class="mt-4"><template #header>待审批</template><el-table :data="pending"><el-table-column prop="id" label="编号" width="90"/><el-table-column prop="entity_ref" label="目标用户"/><el-table-column prop="approval_status" label="状态"/><el-table-column label="操作" width="220"><template #default="{ row }"><el-button size="small" type="primary" @click="decide(row.id, 'approve')">通过</el-button><el-button size="small" @click="decide(row.id, 'reject')">驳回</el-button></template></el-table-column></el-table><el-empty v-if="!pending.length" description="暂无待审批申请"/></el-card>
    <el-card class="mt-4"><template #header>我的申请</template><el-table :data="mine"><el-table-column prop="id" label="编号" width="90"/><el-table-column prop="entity_ref" label="目标用户"/><el-table-column prop="approval_status" label="状态"/><el-table-column label="操作"><template #default="{ row }"><el-button v-if="row.approval_status === 'approved'" size="small" type="success" @click="execute(row.id)">执行</el-button></template></el-table-column></el-table></el-card>
  </div>
</template>
