<template>
  <div>
    <h2 class="page-title">
      候选关系审核
      <el-tag type="warning" size="large" class="ml10"
        >共 {{ total }} 条候选中</el-tag
      >
    </h2>

    <el-card>
      <el-form :inline="true">
        <el-form-item>
          <el-input
            v-model="keyword"
            placeholder="搜索表名"
            clearable
            @clear="load"
          />
        </el-form-item>
        <el-form-item>
          <el-select
            v-model="statusFilter"
            placeholder="状态"
            clearable
            style="width: 120px"
            @change="load"
          >
            <el-option label="候选" value="candidate" />
            <el-option label="已提升" value="promoted" />
            <el-option label="已拒绝" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="sourceViewFilter"
            placeholder="来源视图"
            clearable
            @clear="load"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="items" stripe>
        <el-table-column prop="from_table" label="源表" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.from_table }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="join_condition" label="关联条件" min-width="180">
          <template #default="{ row }">
            <span v-if="row.join_condition" class="mono">{{
              row.join_condition
            }}</span>
            <span v-else class="mono"
              >{{ row.from_columns }} -> {{ row.to_columns }}</span
            >
          </template>
        </el-table-column>
        <el-table-column prop="to_table" label="目标表" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.to_table }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="source_view" label="来源视图" width="180" />
        <el-table-column prop="confidence" label="置信度" width="80" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag
              v-if="row.status === 'candidate'"
              type="warning"
              size="small"
              >候选</el-tag
            >
            <el-tag
              v-else-if="row.status === 'promoted'"
              type="success"
              size="small"
              >已提升</el-tag
            >
            <el-tag
              v-else-if="row.status === 'rejected'"
              type="info"
              size="small"
              >已拒绝</el-tag
            >
            <el-tag v-else size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <template v-if="row.status === 'candidate'">
              <el-button
                type="primary"
                size="small"
                @click="handlePromote(row)"
              >
                提升
              </el-button>
              <el-button type="danger" size="small" @click="handleReject(row)">
                拒绝
              </el-button>
            </template>
            <el-tag v-else type="info" size="small">已处理</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        class="mt15"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </el-card>

    <el-dialog v-model="promoteVisible" title="提升候选关系" width="450px">
      <el-form>
        <el-form-item label="业务域">
          <el-input v-model="promoteForm.domain" placeholder="如 住院、检验" />
        </el-form-item>
        <el-form-item label="基数">
          <el-select
            v-model="promoteForm.cardinality"
            placeholder="one-to-many / many-to-one"
          >
            <el-option label="一对多" value="one-to-many" />
            <el-option label="多对一" value="many-to-one" />
            <el-option label="一对一" value="one-to-one" />
            <el-option label="多对多" value="many-to-many" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="promoteForm.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="promoteVisible = false">取消</el-button>
        <el-button type="primary" :loading="promoting" @click="submitPromote"
          >确认提升</el-button
        >
      </template>
    </el-dialog>

    <el-dialog v-model="rejectVisible" title="拒绝候选关系" width="400px">
      <el-form>
        <el-form-item label="拒绝原因">
          <el-input
            v-model="rejectNote"
            type="textarea"
                        :rows="3"
            placeholder="请填写拒绝原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="submitReject"
          >确认拒绝</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { getCandidates, promoteCandidate, rejectCandidate } from "@/api/asset";
import type { CandidateRelationItem } from "@/api/asset";
import { ElMessage, ElMessageBox } from "element-plus";

const loading = ref(false);
const items = ref<CandidateRelationItem[]>([]);
const total = ref(0);
const page = ref<number>(1);
const pageSize = ref<number>(30);
const keyword = ref("");
const statusFilter = ref("candidate");
const sourceViewFilter = ref("");

const promoteVisible = ref(false);
const promoting = ref(false);
const activeCandidate = ref<CandidateRelationItem | null>(null);
const promoteForm = ref({ domain: "", cardinality: "", note: "" });

const rejectVisible = ref(false);
const rejecting = ref(false);
const rejectNote = ref("");

function load() {
  loading.value = true;
  getCandidates({
    page: page.value,
    page_size: pageSize.value,
    keyword: keyword.value || undefined,
    status: statusFilter.value || undefined,
    source_view: sourceViewFilter.value || undefined
  })
    .then(({ data }) => {
      items.value = data.items;
      total.value = data.total;
    })
    .finally(() => {
      loading.value = false;
    });
}

function handlePromote(row: CandidateRelationItem) {
  activeCandidate.value = row;
  promoteForm.value = { domain: "", cardinality: "", note: "" };
  promoteVisible.value = true;
}

function submitPromote() {
  if (!activeCandidate.value) return;
  promoting.value = true;
  promoteCandidate(activeCandidate.value.id, {
    ...promoteForm.value,
    reviewer: "manual"
  })
    .then(() => {
      ElMessage.success("已提升为正式关系");
      promoteVisible.value = false;
      load();
    })
    .finally(() => {
      promoting.value = false;
    });
}

function handleReject(row: CandidateRelationItem) {
  activeCandidate.value = row;
  rejectNote.value = "";
  rejectVisible.value = true;
}

function submitReject() {
  if (!activeCandidate.value) return;
  rejecting.value = true;
  rejectCandidate(activeCandidate.value.id, {
    reviewer: "manual",
    note: rejectNote.value
  })
    .then(() => {
      ElMessage.success("已拒绝");
      rejectVisible.value = false;
      load();
    })
    .finally(() => {
      rejecting.value = false;
    });
}

load();
</script>

<style scoped>
.page-title {
  margin-bottom: 20px;
}
.ml10 {
  margin-left: 10px;
}
.mt15 {
  margin-top: 15px;
}
.mono {
  font-family: "Courier New", monospace;
  font-size: 13px;
}
</style>
