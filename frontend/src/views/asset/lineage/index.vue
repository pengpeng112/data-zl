<template>
  <div>
    <h2 class="page-title">血缘与影响分析</h2>

    <el-card class="mb20">
      <template #header>表影响分析</template>
      <el-form :inline="true">
        <el-form-item label="表名">
          <el-input
            v-model="impactTable"
            placeholder="例如 HIS.PAT_VISIT"
            style="width: 300px"
            @keyup.enter="runImpact"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="impactLoading" @click="runImpact">
            分析
          </el-button>
        </el-form-item>
      </el-form>

      <div v-if="impactResult" class="impact-result">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="分析表">{{
            impactResult.table
          }}</el-descriptions-item>
          <el-descriptions-item label="引用视图数">{{
            impactResult.total_views
          }}</el-descriptions-item>
          <el-descriptions-item label="关联关系数">{{
            impactResult.total_relations
          }}</el-descriptions-item>
          <el-descriptions-item label="" />
        </el-descriptions>

        <div v-if="impactResult.referencing_views.length > 0" class="mt15">
          <h4>被以下 ODS 视图引用</h4>
          <el-tag
            v-for="v in impactResult.referencing_views"
            :key="v"
            class="mr5 mb5"
            type="info"
          >
            {{ v }}
          </el-tag>
        </div>

        <div v-if="impactResult.dependent_relations.length > 0" class="mt15">
          <h4>关联的正式关系</h4>
          <div
            v-for="r in impactResult.dependent_relations"
            :key="r"
            class="relation-line"
          >
            {{ r }}
          </div>
        </div>
        <el-empty
          v-if="
            impactResult &&
            impactResult.total_views === 0 &&
            impactResult.total_relations === 0
          "
          description="未找到该表相关的视图或关系"
        />
      </div>
    </el-card>

    <el-card>
      <template #header>ODS 视图依赖（{{ depsTotal }}）</template>
      <el-form :inline="true">
        <el-form-item>
          <el-input
            v-model="depView"
            placeholder="视图名"
            clearable
            @clear="loadDeps"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="depTable"
            placeholder="被引用表名"
            clearable
            @clear="loadDeps"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadDeps">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="depsLoading" :data="depsItems" stripe>
        <el-table-column prop="view_name" label="ODS 视图" min-width="200" />
        <el-table-column
          prop="referenced_schema"
          label="被引用 Schema"
          width="120"
        />
        <el-table-column
          prop="referenced_table"
          label="被引用表"
          min-width="200"
        />
        <el-table-column prop="alias" label="别名" width="100" />
      </el-table>
      <el-pagination
        v-model:current-page="depPage"
        class="mt15"
        :page-size="depPageSize"
        :total="depsTotal"
        layout="total, prev, pager, next"
        @current-change="loadDeps"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { getViewDependencies, getImpactAnalysis } from "@/api/asset";
import type { ViewDependencyItem, ImpactResult } from "@/api/asset";
import { ElMessage } from "element-plus";

const impactTable = ref("");
const impactLoading = ref(false);
const impactResult = ref<ImpactResult | null>(null);

const depsLoading = ref(false);
const depsItems = ref<ViewDependencyItem[]>([]);
const depsTotal = ref(0);
const depPage = ref(1);
const depPageSize = ref(50);
const depView = ref("");
const depTable = ref("");

function runImpact() {
  if (!impactTable.value.trim()) {
    ElMessage.warning("请输入表名");
    return;
  }
  impactLoading.value = true;
  getImpactAnalysis(impactTable.value.trim())
    .then(({ data }) => {
      impactResult.value = data;
    })
    .catch(() => {
      impactResult.value = null;
    })
    .finally(() => {
      impactLoading.value = false;
    });
}

function loadDeps() {
  depsLoading.value = true;
  getViewDependencies({
    page: depPage.value,
    page_size: depPageSize.value,
    view: depView.value || undefined,
    referenced_table: depTable.value || undefined
  })
    .then(({ data }) => {
      depsItems.value = data.items;
      depsTotal.value = data.total;
    })
    .finally(() => {
      depsLoading.value = false;
    });
}

loadDeps();
</script>

<style scoped>
.page-title {
  margin-bottom: 20px;
}
.mb20 {
  margin-bottom: 20px;
}
.mt15 {
  margin-top: 15px;
}
.mr5 {
  margin-right: 5px;
}
.mb5 {
  margin-bottom: 5px;
}
.impact-result h4 {
  margin: 10px 0 5px 0;
}
.relation-line {
  padding: 3px 0;
  color: #606266;
  font-size: 13px;
}
</style>
