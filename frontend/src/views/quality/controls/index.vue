<template>
  <div class="quality-controls-page">
    <RePageHeader title="质控清单" subtitle="版本化的质控规则清单：稳定编码 + 口径版本，绑定检测来源。">
      <template #actions>
        <el-button @click="loadList">刷新</el-button>
        <el-button v-perms="'quality.control.manage'" type="primary" @click="openCreate">
          新建清单
        </el-button>
      </template>
    </RePageHeader>

    <el-card shadow="never" class="main-card">
      <div class="filter-row">
        <el-select v-model="filters.lifecycle_status" placeholder="状态" clearable class="f-item">
          <el-option label="草稿" value="draft" />
          <el-option label="激活" value="active" />
          <el-option label="阻塞" value="blocked" />
          <el-option label="废弃" value="deprecated" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="编码/名称关键字"
          clearable
          class="f-item f-wide"
          @keyup.enter="applyFilter"
        />
        <el-button type="primary" @click="applyFilter">筛选</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="items" stripe row-key="id">
        <el-table-column prop="control_code" label="清单编码" width="170" show-overflow-tooltip />
        <el-table-column label="名称" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.title }}
            <el-tag size="small" class="ml4">v{{ row.version }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="86" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="lifeTagType(row.lifecycle_status)">
              {{ lifeLabel(row.lifecycle_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类别" width="86" align="center" />
        <el-table-column prop="dimension" label="维度" width="110" show-overflow-tooltip />
        <el-table-column prop="primary_system_code" label="主责系统" width="90" align="center" />
        <el-table-column label="指标/阈值" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.metric_name">
              {{ row.metric_name }} {{ row.comparator || "" }} {{ row.threshold_value ?? "-" }}{{ row.metric_unit || "" }}
            </template>
            <span v-else class="muted">手工清单</span>
          </template>
        </el-table-column>
        <el-table-column label="检测器" min-width="170">
          <template #default="{ row }">
            <div v-for="d in row.detectors" :key="d.id" class="detector-line">
              <el-tag size="small" :type="detectorTagType(d.status)" class="mr4">{{ d.status }}</el-tag>
              <span class="muted">{{ detectorKindLabel(d.detector_kind) }}:{{ d.detector_ref }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button
              v-if="row.lifecycle_status === 'active'"
              v-perms="'quality.control.run'"
              size="small"
              link
              @click="doPreflight(row)"
            >
              预检
            </el-button>
            <el-button
              v-if="row.lifecycle_status !== 'active'"
              v-perms="'quality.control.manage'"
              size="small"
              type="primary"
              link
              @click="doActivate(row)"
            >
              激活
            </el-button>
            <el-button
              v-if="row.lifecycle_status === 'active'"
              v-perms="'quality.control.run'"
              size="small"
              type="success"
              link
              @click="doRun(row)"
            >
              执行
            </el-button>
            <el-button
              v-if="row.lifecycle_status === 'active'"
              v-perms="'quality.control.manage'"
              size="small"
              type="warning"
              link
              @click="doDeprecate(row)"
            >
              废弃
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager-row">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadList"
          @size-change="onPageSizeChange"
        />
      </div>
    </el-card>

    <!-- 新建/编辑清单 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新建质控清单' : `编辑清单 ${controlForm.control_code}`"
      width="860px"
      top="4vh"
    >
      <el-form label-width="110px" label-position="right">
        <el-divider content-position="left">基本信息</el-divider>
        <div class="form-grid">
          <el-form-item label="清单编码" required>
            <el-input v-model="controlForm.control_code" :disabled="dialogMode === 'edit'" placeholder="如 QC-HIS-0001" />
          </el-form-item>
          <el-form-item label="名称" required>
            <el-input v-model="controlForm.title" maxlength="256" />
          </el-form-item>
          <el-form-item label="描述" class="grid-span">
            <el-input v-model="controlForm.description" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="维度">
            <el-select v-model="controlForm.dimension" filterable allow-create clearable placeholder="选择或输入">
              <el-option v-for="d in DIMENSIONS" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="类别">
            <el-select v-model="controlForm.category" filterable allow-create clearable placeholder="选择或输入">
              <el-option v-for="c in CATEGORIES" :key="c.value" :label="c.label" :value="c.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="主责系统">
            <el-input v-model="controlForm.primary_system_code" placeholder="如 HIS / LIS" />
          </el-form-item>
          <el-form-item label="关联系统">
            <el-input v-model="controlForm.related_system_codes" placeholder="逗号分隔，如 HIS,LIS" />
          </el-form-item>
          <el-form-item label="对象键" class="grid-span">
            <el-input v-model="controlForm.object_key" placeholder="如 MEDREC.PAT_VISIT.DISCHARGE_DISPOSITION" />
          </el-form-item>
          <el-form-item label="指标名称">
            <el-input v-model="controlForm.metric_name" placeholder="如 空值率（手工清单可留空）" />
          </el-form-item>
          <el-form-item label="指标单位">
            <el-input v-model="controlForm.metric_unit" placeholder="如 %、ms" />
          </el-form-item>
          <el-form-item label="比较符">
            <el-select v-model="controlForm.comparator" clearable placeholder="与阈值成对填写">
              <el-option v-for="c in COMPARATORS" :key="c" :label="c" :value="c" />
            </el-select>
          </el-form-item>
          <el-form-item label="阈值">
            <el-input-number v-model="controlForm.threshold_value" controls-position="right" placeholder="与比较符成对填写" />
          </el-form-item>
          <el-form-item label="无数据策略">
            <el-select v-model="controlForm.no_data_policy">
              <el-option label="按通过（pass）" value="pass" />
              <el-option label="按未通过（fail）" value="fail" />
              <el-option label="受阻（blocked）" value="blocked" />
            </el-select>
          </el-form-item>
          <el-form-item label="默认严重度">
            <el-select v-model="controlForm.default_severity">
              <el-option label="严重" value="critical" />
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
              <el-option label="提示" value="info" />
            </el-select>
          </el-form-item>
          <el-form-item label="默认优先级">
            <el-select v-model="controlForm.default_priority" class="w-full">
              <el-option v-for="p in PRIORITIES" :key="p" :label="p" :value="p" />
            </el-select>
          </el-form-item>
        </div>

        <el-divider content-position="left">检测器</el-divider>
        <div v-for="(d, index) in controlDetectors" :key="index" class="detector-form-row">
          <div class="detector-form-line">
            <el-select v-model="d.detector_kind" placeholder="类型" class="df-kind">
              <el-option v-for="(label, kind) in DETECTOR_KIND_MAP" :key="kind" :label="label" :value="kind" />
            </el-select>
            <el-input v-model="d.detector_ref" placeholder="检测引用（模板/规则编码）" class="df-ref" />
            <el-input v-model="d.detector_version" placeholder="版本" class="df-ver" />
            <el-select v-model="d.status" placeholder="状态" class="df-status">
              <el-option label="草稿" value="draft" />
              <el-option label="激活" value="active" />
              <el-option label="阻塞" value="blocked" />
              <el-option label="停用" value="disabled" />
            </el-select>
            <el-button size="small" type="danger" link @click="removeDetectorRow(index)">删除</el-button>
          </div>
          <!-- T08 值域绑定：confirmed 码集按列身份绑定（生效时间与指纹由执行链冻结） -->
          <div v-if="d.detector_kind === 'value_domain'" class="detector-binding-row">
            <el-input v-model="d.binding.system_code" placeholder="系统码（如 HIS）" class="df-bind" />
            <el-input v-model="d.binding.source_code" placeholder="物理源 source_code" class="df-bind" />
            <el-input v-model="d.binding.schema_name" placeholder="schema" class="df-bind" />
            <el-input v-model="d.binding.table_name" placeholder="表名" class="df-bind" />
            <el-input v-model="d.binding.column_name" placeholder="列名" class="df-bind" />
          </div>
        </div>
        <el-button size="small" @click="addDetectorRow">+ 添加检测器</el-button>

        <el-divider content-position="left">执行与复测</el-divider>
        <div class="form-grid">
          <el-form-item label="数据来源">
            <el-input v-model="controlForm.source_code" placeholder="如 ODS / HIS / DOCARE" />
          </el-form-item>
          <el-form-item label="调度表达式">
            <el-input v-model="controlForm.schedule_expr" placeholder="如 0 2 * * *" />
          </el-form-item>
          <el-form-item label="时区">
            <el-input v-model="controlForm.timezone" placeholder="如 Asia/Shanghai" />
          </el-form-item>
          <el-form-item label="启用调度">
            <el-switch v-model="controlForm.schedule_enabled" />
          </el-form-item>
          <el-form-item label="新鲜度(小时)">
            <el-input-number v-model="controlForm.freshness_hours" :min="0" controls-position="right" placeholder="观测过期阈值" />
          </el-form-item>
          <el-form-item label="SLA(小时)">
            <el-input-number v-model="controlForm.sla_hours" :min="0" controls-position="right" placeholder="处理时限" />
          </el-form-item>
          <el-form-item label="复测策略">
            <el-select v-model="controlForm.recheck_policy">
              <el-option label="自动复测" value="auto" />
              <el-option label="人工复测" value="manual" />
            </el-select>
          </el-form-item>
          <el-form-item label="验证策略">
            <el-select v-model="controlForm.verification_policy" clearable placeholder="编辑时留空表示不变更">
              <el-option label="人工验证" value="manual" />
              <el-option label="自动复测+人工关闭" value="auto_recheck_manual_close" />
            </el-select>
          </el-form-item>
          <el-form-item label="连续通过次数">
            <el-input-number v-model="controlForm.required_pass_count" :min="1" controls-position="right" placeholder="关闭所需连续通过" />
          </el-form-item>
          <el-form-item label="默认科室">
            <el-input v-model="controlForm.default_dept_code" placeholder="开单默认主责科室" />
          </el-form-item>
          <el-form-item label="默认责任人">
            <el-input v-model="controlForm.default_person_code" placeholder="开单默认责任人" />
          </el-form-item>
        </div>

        <el-form-item v-if="dialogMode === 'edit'" label="变更原因" required>
          <el-input v-model="controlForm.reason" type="textarea" :rows="2" placeholder="PATCH 需携带版本与变更原因（入审计）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitControlDialog">
          {{ dialogMode === "create" ? "创建" : "保存" }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 清单详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      size="780px"
      :title="detailItem ? `清单详情 ${detailItem.control_code}` : '清单详情'"
    >
      <template v-if="detailItem">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="编码">{{ detailItem.control_code }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ detailItem.title }}</el-descriptions-item>
          <el-descriptions-item label="版本 / 锁">
            v{{ detailItem.version }} / lock {{ detailItem.lock_version }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="lifeTagType(detailItem.lifecycle_status)">
              {{ lifeLabel(detailItem.lifecycle_status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="类别">{{ detailItem.category || "-" }}</el-descriptions-item>
          <el-descriptions-item label="维度">{{ detailItem.dimension || "-" }}</el-descriptions-item>
          <el-descriptions-item label="主责系统">{{ detailItem.primary_system_code || "-" }}</el-descriptions-item>
          <el-descriptions-item label="数据来源">{{ detailItem.source_code || "-" }}</el-descriptions-item>
          <el-descriptions-item label="调度表达式" :span="2">
            {{ scheduleExprText(detailItem) }}
          </el-descriptions-item>
          <el-descriptions-item label="启用调度">
            {{ detailItem.schedule_enabled ? "是" : "否" }}
          </el-descriptions-item>
          <el-descriptions-item label="下次运行">{{ formatTime(detailItem.next_run_at) }}</el-descriptions-item>
          <el-descriptions-item label="上次运行">{{ formatTime(detailItem.last_run_at) }}</el-descriptions-item>
          <el-descriptions-item label="新鲜度 / SLA">
            {{ detailItem.freshness_hours ?? "-" }} 小时 / {{ detailItem.sla_hours ?? "-" }} 小时
          </el-descriptions-item>
          <el-descriptions-item label="复测策略">
            {{ detailItem.recheck_policy === "auto" ? "自动复测" : detailItem.recheck_policy === "manual" ? "人工复测" : detailItem.recheck_policy || "-" }}
          </el-descriptions-item>
          <el-descriptions-item label="指标" :span="2">
            <template v-if="detailItem.metric_name">
              {{ detailItem.metric_name }} {{ detailItem.comparator || "" }} {{ detailItem.threshold_value ?? "-" }}{{ detailItem.metric_unit || "" }}
            </template>
            <span v-else class="muted">手工清单</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="detailItem.description" label="描述" :span="2">
            {{ detailItem.description }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="section-title">检测器</div>
        <el-table :data="detailItem.detectors" stripe size="small">
          <el-table-column label="类型" width="100">
            <template #default="{ row }">{{ detectorKindLabel(row.detector_kind) }}</template>
          </el-table-column>
          <el-table-column prop="detector_ref" label="引用" min-width="150" show-overflow-tooltip />
          <el-table-column prop="detector_version" label="版本" width="80" align="center" />
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="detectorTagType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="受阻原因" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ row.blocked_reason || "-" }}</template>
          </el-table-column>
        </el-table>

        <div v-perms="'quality.run.read'" class="section-title">
          最近运行
          <el-button size="small" link type="primary" @click="loadRuns(detailItem.id)">刷新</el-button>
        </div>
        <el-table v-perms="'quality.run.read'" v-loading="runsLoading" :data="runs" stripe size="small">
          <el-table-column prop="run_code" label="运行单" width="140" show-overflow-tooltip />
          <el-table-column label="目的" width="64" align="center">
            <template #default="{ row }">{{ purposeLabel(row.purpose) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="84" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="runStatusTagType(row.status)">{{ runStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="trigger_kind" label="触发" width="86" show-overflow-tooltip />
          <el-table-column label="尝试" width="62" align="center">
            <template #default="{ row }">{{ row.attempt ?? "-" }}/{{ row.max_attempts ?? "-" }}</template>
          </el-table-column>
          <el-table-column label="开始 / 结束" width="170">
            <template #default="{ row }">{{ formatTime(row.started_at) }} ~ {{ formatTime(row.finished_at) }}</template>
          </el-table-column>
          <el-table-column label="错误摘要" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span :class="{ 'err-text': row.error_message_sanitized }">{{ runErrorBrief(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="104" align="center">
            <template #default="{ row }">
              <el-button
                v-perms="'quality.run.manage'"
                size="small"
                type="warning"
                link
                :disabled="runCancelDisabled(row)"
                @click="doCancelRun(row)"
              >
                取消
              </el-button>
              <el-button
                v-perms="'quality.run.manage'"
                size="small"
                type="primary"
                link
                :disabled="runRetryDisabled(row)"
                @click="doRetryRun(row)"
              >
                重试
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty
          v-perms="'quality.run.read'"
          v-if="!runs.length && !runsLoading"
          description="暂无运行"
          :image-size="60"
        />

        <div class="drawer-footer">
          <el-button v-perms="'quality.control.manage'" type="primary" size="small" @click="openEditFromDetail">
            编辑
          </el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 执行预检 -->
    <el-dialog v-model="preflightVisible" title="执行预检" width="760px">
      <div v-loading="preflightLoading" class="preflight-body">
        <template v-if="preflightData">
          <el-descriptions :column="3" border size="small" class="mb8">
            <el-descriptions-item label="可执行">
              <el-tag :type="preflightData.executable ? 'success' : 'danger'">
                {{ preflightData.executable ? "可执行" : "不可执行" }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="手工清单">
              {{ preflightData.manual_required ? "是（走人工路径）" : "否" }}
            </el-descriptions-item>
            <el-descriptions-item label="执行窗口">
              <el-tag :type="preflightData.window.in_window ? 'success' : 'warning'">
                {{ preflightData.window.in_window ? "窗口内" : "窗口外" }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="允许时段">
              {{ formatAllowedHours(preflightData.window.allowed_hours) }}
            </el-descriptions-item>
            <el-descriptions-item label="下次窗口">
              {{ formatTime(preflightData.window.next_window_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="范围键">
              {{ preflightData.scope_summary.scope_key || "-" }}
            </el-descriptions-item>
            <el-descriptions-item label="系统">
              {{ preflightData.scope_summary.system_code || "-" }}
            </el-descriptions-item>
            <el-descriptions-item label="来源">
              {{ preflightData.scope_summary.source_code || "-" }}
            </el-descriptions-item>
            <el-descriptions-item label="对象 / 粒度">
              {{ preflightData.scope_summary.object_key || "-" }} / {{ preflightData.scope_summary.granularity || "-" }}
            </el-descriptions-item>
          </el-descriptions>
          <div v-if="preflightData.blocked_reasons.length" class="mb8">
            <b>受阻原因：</b>
            <ul class="reason-list">
              <li v-for="(reason, i) in preflightData.blocked_reasons" :key="i">{{ reason }}</li>
            </ul>
          </div>
          <el-alert v-if="preflightData.warnings.length" type="warning" :closable="false" class="mb8">
            <div v-for="(warning, i) in preflightData.warnings" :key="i">{{ warning }}</div>
          </el-alert>
          <el-table :data="preflightData.detectors" stripe size="small">
            <el-table-column label="检测器" min-width="170" show-overflow-tooltip>
              <template #default="{ row }">{{ detectorKindLabel(row.detector_kind) }}：{{ row.detector_ref }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80" align="center" />
            <el-table-column label="可执行" width="76" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.executable ? 'success' : 'danger'">
                  {{ row.executable ? "是" : "否" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="受阻原因" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.blocked_reason || "-" }}</template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else-if="!preflightLoading" description="无预检结果" :image-size="60" />
      </div>
    </el-dialog>

    <!-- 执行受理结果 -->
    <el-dialog v-model="runVisible" title="执行受理结果" width="760px">
      <div v-loading="runLoading" class="run-body">
        <template v-if="runResult">
          <el-alert
            type="info"
            :closable="false"
            class="mb8"
            title="运行由后台执行器异步执行，本入口不伪造结果；可在「详情」抽屉查看最近运行。"
          />
          <el-descriptions :column="2" border size="small" class="mb8">
            <el-descriptions-item label="受理状态">
              <el-tag :type="runStatusTagType(runResult.status)">{{ runStatusLabel(runResult.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="运行单">
              {{ runResult.run_code || (runResult.run_id ? `#${runResult.run_id}` : "-") }}
            </el-descriptions-item>
            <el-descriptions-item v-if="runResult.status === 'waiting_window'" label="下次窗口">
              {{ formatTime(runResult.next_window_at) }}
            </el-descriptions-item>
            <el-descriptions-item v-if="runResult.duplicate" label="幂等">
              <el-tag type="info" size="small">重复受理（已命中等价运行，未重复创建）</el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <div v-if="runResult.status === 'blocked' && runResult.blocked_reasons.length" class="mb8">
            <b>受阻原因：</b>
            <ul class="reason-list">
              <li v-for="(reason, i) in runResult.blocked_reasons" :key="i">{{ reason }}</li>
            </ul>
          </div>
          <el-alert
            v-if="runResult.status === 'manual_required'"
            type="warning"
            :closable="false"
            class="mb8"
            title="手工清单：本次执行走人工验证路径，不产生自动运行单。"
          />
          <template v-if="runResult.children && runResult.children.length">
            <b>子运行单：</b>
            <el-table :data="runResult.children" stripe size="small">
              <el-table-column prop="run_id" label="#" width="70" align="center" />
              <el-table-column prop="run_code" label="运行单" width="150" show-overflow-tooltip />
              <el-table-column label="检测器" min-width="170" show-overflow-tooltip>
                <template #default="{ row }">{{ detectorKindLabel(row.detector_kind) }}：{{ row.detector_ref }}</template>
              </el-table-column>
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <el-tag size="small" :type="runStatusTagType(row.status)">{{ runStatusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  activateQualityControl,
  cancelQualityRun,
  createQualityControl,
  deprecateQualityControl,
  listQualityControls,
  listQualityRuns,
  patchQualityControl,
  preflightQualityControl,
  retryQualityRun,
  runQualityControl,
  type QualityControlItem,
  type QualityPreflightResult,
  type QualityRunAccepted,
  type QualityRunItem
} from "@/api/quality";
import { extractErrorDetail } from "@/utils/errorMessage";
import { formatTime } from "@/utils/format";

defineOptions({ name: "QualityControls" });

const PRIORITIES = ["P1", "P2", "P3", "P4"];
const DIMENSIONS = [
  { value: "completeness", label: "完整性" },
  { value: "accuracy", label: "准确性" },
  { value: "timeliness", label: "及时性" },
  { value: "consistency", label: "一致性" },
  { value: "uniqueness", label: "唯一性" },
  { value: "validity", label: "有效性" }
];
const CATEGORIES = [
  { value: "general", label: "通用" },
  { value: "special", label: "专项" },
  { value: "regulatory", label: "监管" },
  { value: "interface", label: "接口" }
];
const COMPARATORS = [">=", ">", "<=", "<", "=", "!=", "between"];

/** 207 U01：运行状态 / 检测器类型中文映射。 */
const RUN_STATUS_MAP: Record<string, string> = {
  queued: "排队中",
  waiting_window: "等待窗口",
  running: "执行中",
  succeeded: "成功",
  partial: "部分成功",
  failed: "失败",
  cancelled: "已取消",
  blocked: "受阻"
};
const DETECTOR_KIND_MAP: Record<string, string> = {
  probe_template: "探查模板",
  quality_rule: "质量规则",
  value_domain: "值域绑定",
  manual: "人工",
  external: "外部"
};
const RUN_TERMINAL = new Set(["succeeded", "failed", "cancelled", "partial", "blocked"]);
const RUN_RETRYABLE = new Set(["failed", "cancelled", "partial", "blocked"]);

const loading = ref(false);
const acting = ref(false);
const items = ref<QualityControlItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);

const filters = reactive({ lifecycle_status: "", keyword: "" });

function lifeLabel(status: string): string {
  return { draft: "草稿", active: "激活", blocked: "阻塞", deprecated: "废弃" }[status] || status;
}

function lifeTagType(status: string): "success" | "warning" | "info" | "danger" {
  return (
    { draft: "info", active: "success", blocked: "danger", deprecated: "warning" } as Record<
      string,
      "success" | "warning" | "info" | "danger"
    >
  )[status] || "info";
}

function detectorTagType(status: string): "success" | "warning" | "info" | "danger" {
  return (
    { active: "success", blocked: "danger", draft: "info", disabled: "warning" } as Record<
      string,
      "success" | "warning" | "info" | "danger"
    >
  )[status] || "info";
}

function runStatusLabel(status: string): string {
  return RUN_STATUS_MAP[status] || status;
}

function runStatusTagType(
  status: string
): "success" | "warning" | "info" | "danger" | "primary" {
  return (
    {
      queued: "info",
      waiting_window: "warning",
      running: "primary",
      succeeded: "success",
      partial: "warning",
      failed: "danger",
      cancelled: "info",
      blocked: "danger"
    } as Record<string, "success" | "warning" | "info" | "danger" | "primary">
  )[status] || "info";
}

function detectorKindLabel(kind: string): string {
  return DETECTOR_KIND_MAP[kind] || kind;
}

function purposeLabel(purpose: string): string {
  return { check: "检查", recheck: "复测" }[purpose] || purpose;
}

function scheduleExprText(row: QualityControlItem): string {
  const plan = row.execution_plan as Record<string, unknown> | null;
  const expr = (plan && (plan.schedule_expr as string)) || "";
  const tz = (plan && (plan.timezone as string)) || "";
  return `${expr || "未配置"}${tz ? `（${tz}）` : ""}`;
}

function runErrorBrief(row: QualityRunItem): string {
  if (!row.error_message_sanitized && !row.error_code) return "-";
  return `${row.error_code ? `[${row.error_code}] ` : ""}${row.error_message_sanitized || ""}`;
}

function formatAllowedHours(value: number[] | string | null): string {
  if (value === null || value === undefined) return "-";
  if (Array.isArray(value)) return value.length ? value.join("、") : "-";
  return String(value) || "-";
}

function runCancelDisabled(row: QualityRunItem): boolean {
  return row.cancel_requested || RUN_TERMINAL.has(row.status);
}

function runRetryDisabled(row: QualityRunItem): boolean {
  return !RUN_RETRYABLE.has(row.status);
}

async function loadList() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = {
      page: page.value,
      page_size: pageSize.value
    };
    for (const [key, value] of Object.entries(filters)) {
      if (value) params[key] = value;
    }
    const res = await listQualityControls(params as any);
    items.value = res.items;
    total.value = res.total;
  } catch (error: any) {
    items.value = [];
    total.value = 0;
    ElMessage.error(extractErrorDetail(error, "质控清单加载失败"));
  } finally {
    loading.value = false;
  }
}

function applyFilter() {
  page.value = 1;
  loadList();
}

function resetFilter() {
  filters.lifecycle_status = "";
  filters.keyword = "";
  page.value = 1;
  loadList();
}

function onPageSizeChange() {
  page.value = 1;
  loadList();
}

async function doActivate(row: QualityControlItem) {
  try {
    await activateQualityControl(row.id);
    ElMessage.success(`已激活 ${row.control_code}`);
    loadList();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "激活失败（自动规则需至少一个 active 检测器）"));
  }
}

async function doDeprecate(row: QualityControlItem) {
  try {
    await ElMessageBox.confirm(`确认废弃清单 ${row.control_code}？`, "废弃确认", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deprecateQualityControl(row.id);
    ElMessage.success(`已废弃 ${row.control_code}`);
    loadList();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "废弃失败"));
  }
}

// ─────────────────────────── U01：新建 / 编辑清单 ───────────────────────────

interface VdBindingForm {
  system_code: string;
  source_code: string;
  schema_name: string;
  table_name: string;
  column_name: string;
}

interface DetectorFormRow {
  detector_kind: string;
  detector_ref: string;
  detector_version: string;
  status: string;
  binding?: VdBindingForm; // 仅 value_domain 类型使用
}

function emptyBinding(): VdBindingForm {
  return { system_code: "", source_code: "", schema_name: "", table_name: "", column_name: "" };
}

function bindingFilled(b?: VdBindingForm): boolean {
  return !!b && Object.values(b).some(v => v.trim() !== "");
}

function bindingComplete(b?: VdBindingForm): boolean {
  return !!b && Object.values(b).every(v => v.trim() !== "");
}

const dialogVisible = ref(false);
const dialogMode = ref<"create" | "edit">("create");
const editingId = ref<number | null>(null);
const editingLockVersion = ref(0);
const controlDetectors = ref<DetectorFormRow[]>([]);

const controlForm = reactive({
  control_code: "",
  title: "",
  description: "",
  dimension: "",
  category: "",
  primary_system_code: "",
  related_system_codes: "",
  object_key: "",
  metric_name: "",
  metric_unit: "",
  comparator: "",
  threshold_value: null as number | null,
  no_data_policy: "fail",
  default_severity: "medium",
  default_priority: "P3",
  source_code: "",
  schedule_expr: "",
  timezone: "Asia/Shanghai",
  schedule_enabled: false,
  freshness_hours: null as number | null,
  sla_hours: null as number | null,
  recheck_policy: "auto",
  verification_policy: "manual",
  required_pass_count: null as number | null,
  default_dept_code: "",
  default_person_code: "",
  reason: ""
});

function addDetectorRow() {
  controlDetectors.value.push({
    detector_kind: "probe_template",
    detector_ref: "",
    detector_version: "",
    status: "draft",
    binding: emptyBinding()
  });
}

function removeDetectorRow(index: number) {
  controlDetectors.value.splice(index, 1);
}

function resetControlForm() {
  for (const key of Object.keys(controlForm) as (keyof typeof controlForm)[]) {
    (controlForm as any)[key] = key === "threshold_value" ||
      key === "freshness_hours" ||
      key === "sla_hours" ||
      key === "required_pass_count"
      ? null
      : "";
  }
  controlForm.no_data_policy = "fail";
  controlForm.default_severity = "medium";
  controlForm.default_priority = "P3";
  controlForm.timezone = "Asia/Shanghai";
  controlForm.recheck_policy = "auto";
  controlForm.verification_policy = "manual";
  controlForm.schedule_enabled = false;
}

function openCreate() {
  dialogMode.value = "create";
  editingId.value = null;
  resetControlForm();
  controlDetectors.value = [];
  addDetectorRow();
  dialogVisible.value = true;
}

/** 详情抽屉/列表行进入编辑：复用新建 dialog 预填（无法从列表项回填的字段留空，PATCH 不提交空值）。 */
function openEdit(row: QualityControlItem) {
  dialogMode.value = "edit";
  editingId.value = row.id;
  editingLockVersion.value = row.lock_version;
  resetControlForm();
  controlForm.control_code = row.control_code;
  controlForm.title = row.title;
  controlForm.description = row.description || "";
  controlForm.dimension = row.dimension || "";
  controlForm.category = row.category || "";
  controlForm.primary_system_code = row.primary_system_code || "";
  controlForm.object_key = row.object_name_snapshot || "";
  controlForm.metric_name = row.metric_name || "";
  controlForm.metric_unit = row.metric_unit || "";
  controlForm.comparator = row.comparator || "";
  controlForm.threshold_value = row.threshold_value;
  controlForm.default_severity = row.default_severity || "medium";
  controlForm.default_priority = row.default_priority || "P3";
  controlForm.source_code = row.source_code || "";
  controlForm.schedule_enabled = !!row.schedule_enabled;
  controlForm.freshness_hours = row.freshness_hours;
  controlForm.sla_hours = row.sla_hours;
  controlForm.recheck_policy = row.recheck_policy || "auto";
  controlForm.verification_policy = row.verification_policy || "";
  controlDetectors.value = row.detectors.map(d => ({
    detector_kind: d.detector_kind,
    detector_ref: d.detector_ref,
    detector_version: d.detector_version || "",
    status: d.status,
    binding: {
      system_code: String(d.result_mapping?.system_code ?? ""),
      source_code: String(d.result_mapping?.source_code ?? ""),
      schema_name: String(d.result_mapping?.schema_name ?? ""),
      table_name: String(d.result_mapping?.table_name ?? ""),
      column_name: String(d.result_mapping?.column_name ?? "")
    }
  }));
  dialogVisible.value = true;
}

function openEditFromDetail() {
  if (detailItem.value) openEdit(detailItem.value);
}

function parseRelatedSystems(text: string): string[] | undefined {
  const parts = text
    .split(/[,，、]/)
    .map(part => part.trim())
    .filter(Boolean);
  return parts.length ? parts : undefined;
}

/** 组装提交体：空字符串/空值剔除，布尔与检测器始终提交。 */
function buildControlPayload(): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  const put = (key: string, value: unknown) => {
    if (value !== "" && value !== null && value !== undefined) payload[key] = value;
  };
  put("title", controlForm.title.trim());
  put("description", controlForm.description.trim());
  put("dimension", controlForm.dimension);
  put("category", controlForm.category);
  put("primary_system_code", controlForm.primary_system_code.trim());
  // 关联系统无法从列表项回填：仅在填写时提交，编辑留空即保持原值不覆盖
  const relatedSystems = parseRelatedSystems(controlForm.related_system_codes);
  if (relatedSystems) payload.related_system_codes = relatedSystems;
  put("object_key", controlForm.object_key.trim());
  put("metric_name", controlForm.metric_name.trim());
  put("metric_unit", controlForm.metric_unit.trim());
  put("comparator", controlForm.comparator);
  put("threshold_value", controlForm.threshold_value);
  put("no_data_policy", controlForm.no_data_policy);
  put("default_severity", controlForm.default_severity);
  put("default_priority", controlForm.default_priority);
  put("source_code", controlForm.source_code.trim());
  put("schedule_expr", controlForm.schedule_expr.trim());
  put("timezone", controlForm.timezone.trim());
  payload.schedule_enabled = controlForm.schedule_enabled;
  put("freshness_hours", controlForm.freshness_hours);
  put("sla_hours", controlForm.sla_hours);
  put("recheck_policy", controlForm.recheck_policy);
  put("verification_policy", controlForm.verification_policy);
  put("required_pass_count", controlForm.required_pass_count);
  put("default_dept_code", controlForm.default_dept_code.trim());
  put("default_person_code", controlForm.default_person_code.trim());
  payload.detectors = controlDetectors.value.map(d => ({
    detector_kind: d.detector_kind,
    detector_ref: d.detector_ref.trim(),
    detector_version: d.detector_version.trim() || undefined,
    status: d.status,
    // 值域绑定走 result_mapping；其余类型保持原样（未填绑定不提交该键）
    ...(d.detector_kind === "value_domain" && bindingComplete(d.binding)
      ? { result_mapping: { ...d.binding } }
      : {})
  }));
  return payload;
}

async function submitControlDialog() {
  if (!controlForm.control_code.trim() || !controlForm.title.trim()) {
    ElMessage.warning("清单编码与名称必填");
    return;
  }
  const hasComparator = !!controlForm.comparator;
  const hasThreshold = controlForm.threshold_value !== null && controlForm.threshold_value !== undefined;
  if (hasComparator !== hasThreshold) {
    ElMessage.warning("比较符与阈值需成对填写（或同时留空）");
    return;
  }
  for (const [index, detector] of controlDetectors.value.entries()) {
    if (!detector.detector_kind || !detector.detector_ref.trim()) {
      ElMessage.warning(`检测器第 ${index + 1} 行的类型与引用必填`);
      return;
    }
    if (detector.detector_kind === "value_domain" && bindingFilled(detector.binding) && !bindingComplete(detector.binding)) {
      ElMessage.warning(`检测器第 ${index + 1} 行值域绑定需填齐系统/物理源/schema/表/列五项`);
      return;
    }
  }
  if (dialogMode.value === "edit" && !controlForm.reason.trim()) {
    ElMessage.warning("编辑保存需填写变更原因（入审计）");
    return;
  }
  acting.value = true;
  try {
    if (dialogMode.value === "create") {
      await createQualityControl({
        control_code: controlForm.control_code.trim(),
        ...buildControlPayload()
      });
      ElMessage.success(`清单已创建：${controlForm.control_code}`);
    } else {
      await patchQualityControl(editingId.value!, {
        ...buildControlPayload(),
        expected_lock_version: editingLockVersion.value,
        reason: controlForm.reason.trim()
      });
      ElMessage.success(`清单已更新：${controlForm.control_code}`);
    }
    dialogVisible.value = false;
    loadList();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, dialogMode.value === "create" ? "创建失败" : "更新失败（可能版本冲突，请刷新重试）"));
  } finally {
    acting.value = false;
  }
}

// ─────────────────────────── U01：详情抽屉与最近运行 ───────────────────────────

const detailVisible = ref(false);
const detailItem = ref<QualityControlItem | null>(null);
const runsLoading = ref(false);
const runs = ref<QualityRunItem[]>([]);

function openDetail(row: QualityControlItem) {
  detailItem.value = row;
  runs.value = [];
  detailVisible.value = true;
  loadRuns(row.id);
}

async function loadRuns(controlId: number) {
  runsLoading.value = true;
  try {
    const res = await listQualityRuns({ control_id: controlId, page: 1, page_size: 20 });
    runs.value = res.items;
  } catch (error: any) {
    runs.value = [];
    ElMessage.error(extractErrorDetail(error, "最近运行加载失败"));
  } finally {
    runsLoading.value = false;
  }
}

async function doCancelRun(run: QualityRunItem) {
  let reason = "";
  try {
    const { value } = await ElMessageBox.prompt("取消原因（必填，入审计）", `取消运行 ${run.run_code}`, {
      inputValidator: (input: string) => (input && input.trim() ? true : "取消原因必填")
    });
    reason = value.trim();
  } catch {
    return;
  }
  try {
    await cancelQualityRun(run.id, { expected_lock_version: run.lock_version, reason });
    ElMessage.success(`已请求取消 ${run.run_code}`);
    if (detailItem.value) loadRuns(detailItem.value.id);
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "取消失败（可能已被执行完毕或版本冲突）"));
  }
}

async function doRetryRun(run: QualityRunItem) {
  let reason = "";
  try {
    const { value } = await ElMessageBox.prompt("重试原因（可选）", `重试运行 ${run.run_code}`, {
      inputValue: ""
    });
    reason = (value || "").trim();
  } catch {
    return;
  }
  try {
    await retryQualityRun(run.id, reason ? { reason } : undefined);
    ElMessage.success(`已重新入队 ${run.run_code}`);
    if (detailItem.value) loadRuns(detailItem.value.id);
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "重试失败"));
  }
}

// ─────────────────────────── U01：预检与执行 ───────────────────────────

const preflightVisible = ref(false);
const preflightLoading = ref(false);
const preflightData = ref<QualityPreflightResult | null>(null);

async function doPreflight(row: QualityControlItem) {
  preflightData.value = null;
  preflightLoading.value = true;
  preflightVisible.value = true;
  try {
    preflightData.value = await preflightQualityControl(row.id);
  } catch (error: any) {
    preflightVisible.value = false;
    ElMessage.error(extractErrorDetail(error, "预检失败（清单需为激活状态）"));
  } finally {
    preflightLoading.value = false;
  }
}

const runVisible = ref(false);
const runLoading = ref(false);
const runResult = ref<QualityRunAccepted | null>(null);

async function doRun(row: QualityControlItem) {
  runResult.value = null;
  runLoading.value = true;
  runVisible.value = true;
  try {
    runResult.value = await runQualityControl(row.id, { expected_control_version: row.version });
  } catch (error: any) {
    runVisible.value = false;
    ElMessage.error(extractErrorDetail(error, "执行请求失败（清单需为激活状态，版本需一致）"));
  } finally {
    runLoading.value = false;
  }
}

onMounted(loadList);
</script>

<style scoped>
.quality-controls-page {
  min-height: calc(100vh - 84px);
}

.main-card {
  margin: 12px 16px;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.f-item {
  width: 160px;
}

.f-wide {
  width: 220px;
}

.muted {
  color: #909399;
  font-size: 12px;
}

.ml4 {
  margin-left: 4px;
}

.mr4 {
  margin-right: 4px;
}

.detector-line {
  line-height: 1.6;
}

.pager-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 12px;
}

.grid-span {
  grid-column: span 2;
}

.detector-form-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.detector-form-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.detector-binding-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-left: 138px;
}

.df-bind {
  width: 150px;
}

.df-kind {
  width: 130px;
}

.df-ref {
  flex: 1;
  min-width: 200px;
}

.df-ver {
  width: 100px;
}

.df-status {
  width: 100px;
}

.section-title {
  margin: 16px 0 8px;
  font-weight: 600;
}

.drawer-footer {
  margin-top: 16px;
}

.reason-list {
  margin: 4px 0 0 20px;
  padding: 0;
  color: #f56c6c;
}

.err-text {
  color: #f56c6c;
}

.preflight-body,
.run-body {
  min-height: 80px;
}

.mb8 {
  margin-bottom: 8px;
}

.w-full {
  width: 100%;
}
</style>
