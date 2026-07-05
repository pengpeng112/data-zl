<template>
  <div class="dict-mappings">
    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <span>编码对照关系</span>
        </div>
      </template>

      <div class="filter-bar">
        <el-radio-group v-model="categoryCode" @change="doSearch">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="diagnosis">诊断</el-radio-button>
          <el-radio-button value="operation">手术</el-radio-button>
        </el-radio-group>
        <el-select
          v-model="reviewStatus"
          placeholder="审核状态"
          clearable
          style="width: 140px; margin-left: 12px"
          @change="doSearch"
        >
          <el-option label="待审核" value="pending" />
          <el-option label="已审核" value="approved" />
          <el-option label="已拒绝" value="rejected" />
        </el-select>
        <el-button type="primary" style="margin-left: 12px" @click="openDialog()">新增对照</el-button>
      </div>

      <el-table v-loading="loading" :data="items" stripe style="margin-top: 12px">
        <el-table-column prop="from_code_set" label="来源编码体系" width="160" />
        <el-table-column prop="from_item_code" label="来源编码" width="160" />
        <el-table-column prop="to_code_set" label="目标编码体系" width="160" />
        <el-table-column prop="to_item_code" label="目标编码" width="160" />
        <el-table-column label="映射类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.mapping_type || "-" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cardinality" label="基数" width="80" align="center" />
        <el-table-column label="置信度" width="80" align="center">
          <template #default="{ row }">
            <el-tag
              :type="
                row.confidence === 'high'
                  ? 'success'
                  : row.confidence === 'medium'
                    ? 'warning'
                    : 'info'
              "
              size="small"
            >
              {{ row.confidence === 'high' ? '高' : row.confidence === 'medium' ? '中' : '低' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审核状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag
              :type="
                row.review_status === 'approved'
                  ? 'success'
                  : row.review_status === 'pending'
                    ? 'warning'
                    : 'danger'
              "
              size="small"
            >
              {{ row.review_status === 'approved' ? '已审核' : row.review_status === 'pending' ? '待审核' : '已拒绝' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[10, 20, 50, 100]"
        style="margin-top: 16px; justify-content: flex-end"
        @change="loadData"
      />
    </el-card>

    <el-dialog
      v-model="dialog.visible"
      :title="dialog.isEdit ? '编辑对照关系' : '新增对照关系'"
      width="560px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="dialog.form" label-width="110px">
        <el-form-item label="分类" prop="category_code">
          <el-select v-model="dialog.form.category_code" style="width: 100%">
            <el-option label="诊断" value="diagnosis" />
            <el-option label="手术" value="operation" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源编码体系" prop="from_code_set">
          <el-input v-model="dialog.form.from_code_set" />
        </el-form-item>
        <el-form-item label="来源编码" prop="from_item_code">
          <el-input v-model="dialog.form.from_item_code" />
        </el-form-item>
        <el-form-item label="目标编码体系" prop="to_code_set">
          <el-input v-model="dialog.form.to_code_set" />
        </el-form-item>
        <el-form-item label="目标编码" prop="to_item_code">
          <el-input v-model="dialog.form.to_item_code" />
        </el-form-item>
        <el-form-item label="映射类型" prop="mapping_type">
          <el-select v-model="dialog.form.mapping_type" style="width: 100%">
            <el-option label="等价" value="equivalent" />
            <el-option label="上位" value="broader" />
            <el-option label="下位" value="narrower" />
            <el-option label="关联" value="related" />
          </el-select>
        </el-form-item>
        <el-form-item label="基数" prop="cardinality">
          <el-input v-model="dialog.form.cardinality" />
        </el-form-item>
        <el-form-item label="置信度" prop="confidence">
          <el-select v-model="dialog.form.confidence" style="width: 100%">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="审核状态" prop="review_status">
          <el-select v-model="dialog.form.review_status" style="width: 100%">
            <el-option label="待审核" value="pending" />
            <el-option label="已审核" value="approved" />
            <el-option label="已拒绝" value="rejected" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="dialog.submitting" @click="saveMapping">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { getMedicalMappings, upsertMedicalMapping } from "@/api/dict";

const loading = ref(false);
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const categoryCode = ref("");
const reviewStatus = ref("");

function doSearch() {
  page.value = 1;
  loadData();
}

async function loadData() {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize.value
    };
    if (categoryCode.value) params.category_code = categoryCode.value;
    if (reviewStatus.value) params.review_status = reviewStatus.value;
    const res = await getMedicalMappings(params);
    items.value = (res as any).data.items;
    total.value = (res as any).data.total;
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false;
  }
}

const dialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: {
    category_code: "diagnosis",
    from_code_set: "",
    from_item_code: "",
    to_code_set: "",
    to_item_code: "",
    mapping_type: "equivalent",
    cardinality: "",
    confidence: "high",
    review_status: "pending"
  }
});

function openDialog(row?: any) {
  if (row) {
    dialog.isEdit = true;
    dialog.form = {
      category_code: row.category_code || "diagnosis",
      from_code_set: row.from_code_set || "",
      from_item_code: row.from_item_code || "",
      to_code_set: row.to_code_set || "",
      to_item_code: row.to_item_code || "",
      mapping_type: row.mapping_type || "equivalent",
      cardinality: row.cardinality || "",
      confidence: row.confidence || "high",
      review_status: row.review_status || "pending"
    };
  } else {
    dialog.isEdit = false;
    dialog.form = {
      category_code: categoryCode.value || "diagnosis",
      from_code_set: "",
      from_item_code: "",
      to_code_set: "",
      to_item_code: "",
      mapping_type: "equivalent",
      cardinality: "",
      confidence: "high",
      review_status: "pending"
    };
  }
  dialog.visible = true;
}

async function saveMapping() {
  dialog.submitting = true;
  try {
    await upsertMedicalMapping(dialog.form);
    ElMessage.success(dialog.isEdit ? "编辑成功" : "新增成功");
    dialog.visible = false;
    loadData();
  } catch {
    ElMessage.error("保存失败");
  } finally {
    dialog.submitting = false;
  }
}

onMounted(loadData);
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
