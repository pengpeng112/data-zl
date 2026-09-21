<template>
  <div class="query-center">
    <RePageHeader
      title="查询与指标中心"
      subtitle="统一管理查询 SQL、统计指标与数据产品。结果默认不保存；参数真实绑定连接器；运行带完整溯源。"
    />

    <el-alert
      class="mb16"
      type="info"
      :closable="false"
      title="可通过查询资产摄取、自动门禁与版本校验维护受治理 SQL；指标可引用 query_code 版本。"
    />

    <el-tabs v-model="tab" @tab-change="onTab">
      <el-tab-pane label="查询资产" name="list">
        <el-card>
          <div class="toolbar">
            <el-input v-model="keyword" clearable placeholder="编码/标题/用途" style="width: 240px" @keyup.enter="doSearch" />
            <el-button type="primary" @click="doSearch">查询</el-button>
            <el-button v-perms="'query.create'" ref="ingestTriggerRef" @click="openIngest">提交 SQL</el-button>
          </div>
          <el-table v-loading="loading" :data="items" stripe size="small" @row-click="openDetail">
            <el-table-column prop="query_code" label="编码" width="200" />
            <el-table-column prop="title" label="名称" min-width="160" />
            <el-table-column prop="system_code" label="系统" width="120" />
            <el-table-column prop="source_code" label="连接" width="140" />
            <el-table-column label="现行版本" width="100">
              <template #default="{ row }">
                {{ row.active_version?.version ?? "-" }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag size="small">{{ queryStatusLabel(row.active_version?.status || row.status) }}</el-tag>
                <el-tag
                  v-if="row.active_version?.certification_status"
                  size="small"
                  :type="certTone(row.active_version.certification_status)"
                  class="ml4"
                >
                  {{ row.active_version.certification_status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            class="mt12"
            layout="total, prev, pager, next"
            :total="total"
            v-model:current-page="page"
            :page-size="pageSize"
            @current-change="loadList"
          />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="运行记录" name="runs">
        <el-card>
          <div class="toolbar">
            <el-button size="small" @click="loadRuns">刷新</el-button>
            <span class="muted">点击行查看运行溯源（版本/批次/digest/data_as_of/错误分类）</span>
          </div>
          <el-table v-loading="runsLoading" :data="runs" stripe size="small" class="mt12" @row-click="openRunDetail">
            <el-table-column prop="id" label="Run" width="80" />
            <el-table-column prop="query_code" label="编码" width="180" />
            <el-table-column prop="version" label="版本" width="70" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">
                  {{ queryStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="row_count" label="行数" width="80" />
            <el-table-column label="数据截至" width="170">
              <template #default="{ row }">{{ row.data_as_of ?? "unknown" }}</template>
            </el-table-column>
            <el-table-column prop="error_class" label="错误分类" width="110" />
            <el-table-column prop="correlation_id" label="关联ID" width="120" />
          </el-table>
          <el-pagination
            class="mt12"
            layout="total, sizes, prev, pager, next"
            :total="runsTotal"
            v-model:current-page="runsPage"
            v-model:page-size="runsPageSize"
            :page-sizes="[20, 50, 100]"
            @current-change="loadRuns"
            @size-change="loadRuns"
          />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="统计指标" name="metrics">
        <el-card>
          <div class="toolbar">
            <el-input v-model="metricKeyword" clearable placeholder="指标编码/名称" style="width: 240px" @keyup.enter="doMetricSearch" />
            <el-button type="primary" @click="doMetricSearch">查询</el-button>
            <el-button v-perms="'query.create'" @click="openMetricIngest">登记指标</el-button>
          </div>
          <el-table v-loading="metricLoading" :data="metricItems" stripe size="small" @row-click="openMetricDetail">
            <el-table-column prop="metric_code" label="编码" width="180" />
            <el-table-column prop="title" label="名称" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column label="现行版本" width="90">
              <template #default="{ row }">{{ row.active_version?.version ?? "-" }}</template>
            </el-table-column>
            <el-table-column label="查询引用" min-width="160">
              <template #default="{ row }">
                {{ row.active_version?.query_code || row.active_version?.numerator_query_code || "-" }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ queryStatusLabel(row.active_version?.status || row.status) }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="metricPage"
            :page-size="metricPageSize"
            :total="metricTotal"
            layout="total, prev, pager, next"
            size="small"
            class="pager"
            @current-change="loadMetrics"
          />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="数据产品" name="products">
        <el-card>
          <el-alert
            class="mb12"
            type="warning"
            :closable="false"
            title="数据产品只允许执行已发布目录项，禁止任意 SQL；参数按 schema 动态校验。"
          />
          <div class="toolbar">
            <el-input v-model="productKeyword" clearable placeholder="产品编码/名称" style="width: 240px" @keyup.enter="doProductSearch" />
            <el-button type="primary" @click="doProductSearch">查询</el-button>
            <el-button v-perms="'product.publish'" :loading="publishLoading" @click="publishCoreProducts">发布 CORE 产品</el-button>
          </div>
          <el-table v-loading="productLoading" :data="productItems" stripe size="small">
            <el-table-column prop="product_code" label="产品编码" width="220" />
            <el-table-column prop="title" label="名称" min-width="160" />
            <el-table-column prop="product_type" label="类型" width="90" />
            <el-table-column prop="query_code" label="查询" width="180" />
            <el-table-column prop="metric_code" label="指标" width="160" />
            <el-table-column label="pin/revision" width="110">
              <template #default="{ row }">
                {{ row.pin_version ? `pin@${row.pin_version}` : "跟随active" }} / r{{ row.revision ?? 1 }}
              </template>
            </el-table-column>
            <el-table-column label="启用" width="70">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "是" : "否" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button v-perms="'query.run'" link type="primary" size="small" @click="openProductExec(row)">执行</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            class="mt12"
            layout="total, prev, pager, next"
            :total="productTotal"
            v-model:current-page="productPage"
            :page-size="20"
            @current-change="loadProducts"
          />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="指标看板" name="board">
        <el-card>
          <div class="toolbar">
            <el-date-picker v-model="boardFrom" type="month" value-format="YYYY-MM" clearable placeholder="起始月" style="width: 150px" />
            <el-date-picker v-model="boardTo" type="month" value-format="YYYY-MM" clearable placeholder="结束月" style="width: 150px" />
            <el-button type="primary" :loading="boardLoading" @click="loadBoard">刷新看板</el-button>
            <el-button @click="exportBoardCsv">导出 CSV（含 provenance）</el-button>
            <span class="muted">结果格数：{{ boardTotal }}</span>
          </div>
          <div class="board-wrap">
            <el-table v-loading="boardLoading" :data="boardRows" stripe size="small" border height="520">
              <el-table-column prop="metric_code" label="编码" width="120" fixed />
              <el-table-column prop="title" label="指标" min-width="180" fixed show-overflow-tooltip />
              <el-table-column prop="has_active" label="可执行" width="70">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.has_active ? 'success' : 'info'">{{ row.has_active ? "是" : "否" }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column
                v-for="p in boardPeriods"
                :key="p"
                :prop="p"
                :label="p"
                min-width="110"
                show-overflow-tooltip
              />
            </el-table>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="调度与多源" name="ops">
        <el-card class="mb16">
          <template #header>查询调度（单条默认关闭；全局还需 APP_QUERY_SCHEDULE_ENABLED）</template>
          <div class="toolbar">
            <el-button type="primary" :loading="scheduleLoading" @click="loadSchedules">刷新</el-button>
            <el-button v-perms="'query.schedule'" :loading="seedLoading" @click="seedSchedules">种子 CORE 调度</el-button>
          </div>
          <el-table v-loading="scheduleLoading" :data="scheduleItems" stripe size="small">
            <el-table-column prop="query_code" label="查询编码" width="200" />
            <el-table-column prop="schedule_cron" label="Cron" width="140" />
            <el-table-column prop="source_code" label="连接" width="160" />
            <el-table-column label="启用" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "是" : "否" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="上次状态" width="100">
              <template #default="{ row }">{{ queryStatusLabel(row.last_status) }}</template>
            </el-table-column>
            <el-table-column prop="last_run_at" label="上次运行" min-width="160" />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button v-perms="'query.schedule'" link type="primary" size="small" @click="toggleSchedule(row)">
                  {{ row.enabled ? "关闭" : "启用" }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
        <el-card>
          <template #header>多源连接能力</template>
          <el-button size="small" class="mb12" :loading="sourceLoading" @click="loadSources">刷新</el-button>
          <el-table v-loading="sourceLoading" :data="sourceItems" stripe size="small">
            <el-table-column prop="source_code" label="连接编码" width="180" />
            <el-table-column prop="title" label="名称" min-width="140" />
            <el-table-column prop="system_code" label="系统" width="140" />
            <el-table-column prop="db_type" label="类型" width="100" />
            <el-table-column prop="write_policy" label="写策略" width="100" />
            <el-table-column label="查询适配" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.query_runner_supported ? 'success' : 'danger'">
                  {{ row.query_runner_supported ? "支持" : "不支持" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="参数绑定" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.bind_parameters_supported ? 'success' : 'warning'">
                  {{ row.bind_parameters_supported ? "是" : "受限" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="credential_status" label="凭据状态" width="120" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="ingestVisible" title="摄取查询 SQL" width="720px">
      <el-form label-width="100px">
        <el-form-item label="编码"><el-input v-model="form.query_code" /></el-form-item>
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="系统"><el-input v-model="form.system_code" placeholder="DATA_CENTER / HIS_SOURCE" /></el-form-item>
        <el-form-item label="连接"><el-input v-model="form.source_code" placeholder="ods_8_216" /></el-form-item>
        <el-form-item label="方言"><el-input v-model="form.dialect" /></el-form-item>
        <el-form-item label="用途"><el-input v-model="form.purpose" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="SQL">
          <el-input v-model="form.sql_text" type="textarea" :rows="10" placeholder="仅 SELECT / WITH；bind 参数用 :name" />
          <el-button link type="primary" @click="insertSqlExample">填入安全示例</el-button>
        </el-form-item>
        <!-- 186 Q3：语义契约字段（粒度/时间口径/限制/配方引用/参数表） -->
        <el-form-item label="行粒度">
          <el-input v-model="form.grain" placeholder="例如：一次住院（PATIENT_ID+VISIT_ID）" />
        </el-form-item>
        <el-form-item label="时间口径字段">
          <el-input v-model="form.period_field" placeholder="例如：DISCHARGE_DATE_TIME" />
        </el-form-item>
        <el-form-item label="使用限制">
          <el-input v-model="form.limitations_text" type="textarea" :rows="2" placeholder="每行一条，如：不含门诊" />
        </el-form-item>
        <el-form-item label="配方引用">
          <el-input v-model="form.recipe_refs_text" placeholder="逗号或换行分隔的 recipe code" />
        </el-form-item>
        <el-form-item label="参数契约">
          <el-table :data="form.parameter_rows" size="small" border>
            <el-table-column label="参数名" min-width="120">
              <template #default="{ row }"><el-input v-model="row.name" placeholder=":name" /></template>
            </el-table-column>
            <el-table-column label="类型" width="120">
              <template #default="{ row }">
                <el-select v-model="row.type">
                  <el-option value="string" /><el-option value="number" /><el-option value="date" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="必填" width="70">
              <template #default="{ row }"><el-checkbox v-model="row.required" /></template>
            </el-table-column>
            <el-table-column label="默认值" min-width="110">
              <template #default="{ row }">
                <el-input v-model="row.default_value" placeholder="留空=无默认" :disabled="row.required" />
              </template>
            </el-table-column>
            <el-table-column width="70">
              <template #default="{ $index }">
                <el-button link type="danger" @click="form.parameter_rows.splice($index, 1)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button
            link
            type="primary"
            @click="form.parameter_rows.push({ name: '', type: 'string', required: true, default_value: '' })"
          >
            添加参数
          </el-button>
          <div class="el-form-item__msg">SQL 中的 :name 参数请逐个登记；AI 生成不代表已具备可信参数契约。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeIngest">取消</el-button>
        <el-button @click="previewGate">门禁试算</el-button>
        <el-button v-perms="'query.create'" type="primary" :loading="saving" @click="submitIngest">提交（自动门禁）</el-button>
      </template>
      <el-alert v-if="gateResult" class="mt12" :type="gateResult.status === 'blocked' ? 'error' : 'success'" :closable="false">
        门禁: {{ gateResult.status }}；自动激活: {{ gateResult.auto_activate }}；
        错误: {{ (gateResult.errors || []).join("; ") || "无" }}
      </el-alert>
    </el-dialog>

    <el-drawer v-model="detailVisible" size="55%" title="查询详情">
      <template v-if="detail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="编码">{{ detail.definition?.query_code }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ detail.definition?.title }}</el-descriptions-item>
          <el-descriptions-item label="用途">{{ detail.definition?.purpose }}</el-descriptions-item>
          <el-descriptions-item label="现行版本">{{ detail.active_version?.version }}</el-descriptions-item>
          <el-descriptions-item label="认证状态">
            <el-tag size="small" :type="certTone(detail.active_version?.certification_status)">
              {{ detail.active_version?.certification_status ?? "legacy_unverified" }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="SQL 哈希">
            <code class="digest">{{ detail.active_version?.sql_sha256 }}</code>
          </el-descriptions-item>
        </el-descriptions>
        <h4 class="mt16">现行 SQL</h4>
        <pre class="sql-box">{{ detail.active_version?.sql_text || "（完整 SQL 需权限，默认仅哈希）" }}</pre>
        <div class="toolbar mt12">
          <el-button
            v-perms="'query.create'"
            size="small"
            type="primary"
            :loading="validating"
            @click="runValidate(detail.active_version)"
          >
            运行 G1–G3 验证
          </el-button>
          <el-button
            v-perms="'query.run'"
            size="small"
            :loading="runLoading"
            @click="openRunDialog(detail.active_version)"
          >
            执行查询
          </el-button>
        </div>
        <el-alert
          v-if="validationReport"
          class="mt12"
          :type="validationReport.overall === 'pass' ? 'success' : validationReport.overall === 'unresolved' ? 'warning' : 'error'"
          :closable="false"
        >
          验证结论: {{ validationReport.overall }}；
          层: {{ (validationReport.layers || []).map(l => `${l.layer}=${l.status}`).join(" · ") }}
        </el-alert>
        <h4 class="mt16">版本列表</h4>
        <el-table :data="detail.versions || []" size="small">
          <el-table-column prop="version" label="版本" width="70" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">{{ queryStatusLabel(row.status) }}</template>
          </el-table-column>
          <el-table-column prop="certification_status" label="认证" width="140" />
          <el-table-column prop="is_active" label="现行" width="70" />
          <el-table-column prop="revision_reason" label="修订原因" />
        </el-table>
      </template>
    </el-drawer>

    <el-dialog v-model="runVisible" title="执行查询（参数真实绑定连接器）" width="640px">
      <ProductParamForm
        v-if="runTarget"
        ref="runParamFormRef"
        :parameter-schema="runTarget?.parameter_schema"
      />
      <template #footer>
        <el-button v-perms="'query.run'" type="primary" :loading="runLoading" @click="submitRun">
          执行
        </el-button>
      </template>
      <RunProvenancePanel v-if="runOutcome" :run="runOutcome" class="mt12" />
      <!-- 186 P1-1：执行结果 → 准确性反馈入口（只带非敏感定位 ID） -->
      <div v-if="canFeedback && runOutcome" class="mt12">
        <el-button size="small" type="primary" plain @click="feedbackRun(runOutcome)">反馈此结果</el-button>
      </div>
      <el-table v-if="runSampleRows.length" :data="runSampleRows" size="small" border class="mt12" max-height="320">
        <el-table-column v-for="column in runSampleColumns" :key="column" :prop="column" :label="column" min-width="120" show-overflow-tooltip />
      </el-table>
    </el-dialog>

    <el-dialog v-model="runDetailVisible" title="运行溯源" width="720px">
      <RunProvenancePanel :run="runDetail" />
      <template #footer>
        <!-- 186 P1-1：运行详情 → 准确性反馈入口（上下文由 accuracy 页按 run_id 回读，不信任 URL） -->
        <el-button
          v-if="canFeedback && runDetail"
          size="small"
          type="primary"
          plain
          @click="feedbackRun(runDetail)"
        >
          反馈此结果
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="metricIngestVisible" title="登记统计指标" width="720px">
      <el-form label-width="110px">
        <el-form-item label="指标编码"><el-input v-model="metricForm.metric_code" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="metricForm.title" /></el-form-item>
        <el-form-item label="含义/口径"><el-input v-model="metricForm.definition_text" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="分子说明"><el-input v-model="metricForm.numerator_desc" /></el-form-item>
        <el-form-item label="分母说明"><el-input v-model="metricForm.denominator_desc" /></el-form-item>
        <el-form-item label="公式"><el-input v-model="metricForm.formula" /></el-form-item>
        <el-form-item label="关联查询"><el-input v-model="metricForm.query_code" placeholder="query_code" /></el-form-item>
        <el-form-item label="单位"><el-input v-model="metricForm.unit" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button v-perms="'query.create'" type="primary" :loading="metricSaving" @click="submitMetric">提交</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="metricDetailVisible" size="50%" title="指标详情">
      <template v-if="metricDetail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="编码">{{ metricDetail.definition?.metric_code }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ metricDetail.definition?.title }}</el-descriptions-item>
          <el-descriptions-item label="口径">{{ metricDetail.active_version?.definition_text }}</el-descriptions-item>
          <el-descriptions-item label="分子">{{ metricDetail.active_version?.numerator_desc }}</el-descriptions-item>
          <el-descriptions-item label="分母">{{ metricDetail.active_version?.denominator_desc }}</el-descriptions-item>
          <el-descriptions-item label="公式">{{ metricDetail.active_version?.formula }}</el-descriptions-item>
          <el-descriptions-item label="计算类型">
            {{ metricDetail.active_version?.calculation_type ?? "ratio" }} ·
            精度 {{ metricDetail.active_version?.precision ?? 2 }} ·
            {{ metricDetail.active_version?.rounding_mode ?? "half_up" }}
          </el-descriptions-item>
          <el-descriptions-item label="查询">
            {{ metricDetail.active_version?.query_code }} @ {{ metricDetail.active_version?.query_version }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="toolbar mt12">
          <el-input v-model="calcPeriod" placeholder="期间 YYYY-MM" style="width: 140px" />
          <el-button
            v-perms="'metric.calculate'"
            size="small"
            type="primary"
            :loading="calcLoading"
            @click="runCalculate(metricDetail)"
          >
            受控计算
          </el-button>
        </div>
        <el-alert v-if="calcResult" class="mt12" type="success" :closable="false">
          状态={{ calcResult.status }} 值={{ calcResult.metric_value ?? "-" }}
          批次={{ calcResult.run_batch }} 批次幂等={{ calcResult.idempotent }}
        </el-alert>
        <!-- 186 P1-1：指标计算结果 → 准确性反馈入口（metric_code/version 来自已加载详情） -->
        <el-button
          v-if="canFeedback && calcResult"
          class="mt12"
          size="small"
          type="primary"
          plain
          @click="feedbackMetricResult"
        >
          反馈此结果
        </el-button>
      </template>
    </el-drawer>

    <el-dialog v-model="productExecVisible" title="执行数据产品（参数按 schema 校验）" width="640px">
      <ProductParamForm
        v-if="productExecTarget"
        ref="productParamFormRef"
        :parameter-schema="productExecTarget?.parameter_schema"
      />
      <template #footer>
        <el-button v-perms="'query.run'" type="primary" :loading="productExecuting" @click="submitProductExec">
          执行
        </el-button>
      </template>
      <el-alert v-if="productExecResult" class="mt12" :closable="false" type="success">
        <pre class="result-box">{{ JSON.stringify(productExecResult, null, 2).slice(0, 2000) }}</pre>
      </el-alert>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter, type LocationQueryRaw } from "vue-router";
import { useQueryDraftHandoffStore } from "@/store/modules/queryDraftHandoff";
import { hasUserPermissions } from "@/utils/permission";
import { userKey, type DataInfo } from "@/utils/auth";
import { storageLocal } from "@pureadmin/utils";

const route = useRoute();
const router = useRouter();

function currentUserProfile(): DataInfo<number> | null {
  try {
    return storageLocal().getItem<DataInfo<number>>(userKey) ?? null;
  } catch {
    return null;
  }
}
import { ElMessage, ElMessageBox } from "element-plus";
import { extractErrorDetail } from "@/utils/errorMessage";
import RePageHeader from "@/components/RePageHeader/index.vue";
import RunProvenancePanel from "./components/RunProvenancePanel.vue";
import ProductParamForm from "./components/ProductParamForm.vue";
import {
  calculateMetric,
  executeDataProduct,
  fetchMetricResults,
  fetchMetricBoard,
  fetchMetricDetail,
  fetchQueries,
  fetchQueryDetail,
  fetchQueryRunDetail,
  fetchQueryRuns,
  fetchQueryValidation,
  fetchDataProducts,
  fetchMetrics,
  fetchQuerySourceCapabilities,
  fetchSchedules,
  ingestMetric,
  ingestQuery,
  previewQueryGate,
  publishCoreDataProducts,
  runQueryVersion,
  seedCoreSchedules,
  upsertSchedule,
  validateQueryVersion,
  type QueryRun,
  type QueryValidationReport,
  type QueryVersion
} from "@/api/query-center";

// 186 Q1：tab 与 URL 双向同步（tab=metrics/runs 直达可恢复；刷新保持；非法回 list）
const QUERY_TAB_WHITELIST = ["list", "metrics", "products", "runs", "board", "ops"] as const;
const tab = ref<string>("list");
const loading = ref(false);
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const keyword = ref("");

const runsLoading = ref(false);
const runs = ref<QueryRun[]>([]);
const runsTotal = ref(0);
const runsPage = ref(1);
const runsPageSize = ref(20);
const runDetailVisible = ref(false);
const runDetail = ref<QueryRun | null>(null);

const ingestVisible = ref(false);
const saving = ref(false);
const gateResult = ref<any>(null);
// 186 P2-5：摄取弹窗关闭（取消/X/Esc）后焦点回到触发按钮（键盘主路径不丢焦点）。
// 延迟到宏任务：Element Plus 焦点陷阱释放时会把焦点还原为打开前元素，需在其后回归。
const ingestTriggerRef = ref<{ $el?: HTMLElement } | null>(null);
function restoreIngestFocus() {
  setTimeout(() => {
    (ingestTriggerRef.value?.$el as HTMLElement | undefined)?.focus?.();
  }, 0);
}
watch(ingestVisible, open => {
  if (!open) restoreIngestFocus();
});
function closeIngest() {
  ingestVisible.value = false;
  restoreIngestFocus();
}
const form = reactive({
  query_code: "",
  title: "",
  system_code: "DATA_CENTER",
  source_code: "ods_8_216",
  dialect: "oracle",
  purpose: "",
  sql_text: "",
  // 186 Q3：语义门禁所需契约字段（Pydantic 可选≠门禁放行缺失值）
  grain: "",
  period_field: "",
  limitations_text: "",
  recipe_refs_text: "",
  parameter_rows: [] as Array<{ name: string; type: string; required: boolean; default_value: string }>
});

const detailVisible = ref(false);
const detail = ref<any>(null);
const validating = ref(false);
const validationReport = ref<QueryValidationReport | null>(null);
const runVisible = ref(false);
const runTarget = ref<QueryVersion | null>(null);
const runParamFormRef = ref<InstanceType<typeof ProductParamForm>>();
const runLoading = ref(false);
const runOutcome = ref<QueryRun | null>(null);

const metricLoading = ref(false);
const metricItems = ref<any[]>([]);
const metricKeyword = ref("");
// E6：指标 tab 分页状态（此前固定 page=1/50 无翻页）。
const metricPage = ref(1);
const metricPageSize = 20;
const metricTotal = ref(0);
const metricIngestVisible = ref(false);
const metricSaving = ref(false);
const metricDetailVisible = ref(false);
const metricDetail = ref<any>(null);
const calcPeriod = ref("");
const calcLoading = ref(false);
const calcResult = ref<any>(null);
const metricForm = reactive({
  metric_code: "",
  title: "",
  definition_text: "",
  numerator_desc: "",
  denominator_desc: "",
  formula: "",
  query_code: "",
  unit: "%"
});

const productLoading = ref(false);
const productItems = ref<any[]>([]);
const productTotal = ref(0);
const productPage = ref(1);
const productKeyword = ref("");
const publishLoading = ref(false);
const productExecVisible = ref(false);
const productExecTarget = ref<any>(null);
const productParamFormRef = ref<InstanceType<typeof ProductParamForm>>();
const productExecuting = ref(false);
const productExecResult = ref<Record<string, unknown> | null>(null);

const boardLoading = ref(false);
const boardFrom = ref("");
const boardTo = ref("");
const boardPeriods = ref<string[]>([]);
const boardRows = ref<any[]>([]);
const boardTotal = ref(0);
const boardCells = ref<Record<string, Record<string, any>>>({});

const scheduleLoading = ref(false);
const seedLoading = ref(false);
const scheduleItems = ref<any[]>([]);
const sourceLoading = ref(false);
const sourceItems = ref<any[]>([]);
const runSampleRows = computed(() => (runOutcome.value?.sample || []).slice(0, 20));
const runSampleColumns = computed(() => {
  const columns = new Set<string>();
  for (const row of runSampleRows.value) Object.keys(row || {}).forEach(key => columns.add(key));
  return Array.from(columns);
});

function queryStatusLabel(status?: string | null) {
  const labels: Record<string, string> = {
    success: "成功",
    succeeded: "成功",
    failed: "失败",
    running: "运行中",
    pending: "待运行",
    cancelled: "已取消",
    draft: "草稿",
    active: "生效",
    deprecated: "已停用",
    blocked: "已阻断",
    pending_review: "待审核",
    executed: "已执行（历史）"
  };
  return status ? labels[status] || status : "未知";
}

function certTone(status?: string): "success" | "warning" | "info" {
  if (status === "certified") return "success";
  if (status === "legacy_unverified") return "warning";
  return "info";
}

function onTab(name: string | number) {
  const next = String(name);
  if ((QUERY_TAB_WHITELIST as readonly string[]).includes(next)) {
    // 同步到 URL（replace 不产生历史记录堆叠）
    routeTabSync(next);
  }
  if (name === "metrics") loadMetrics();
  if (name === "runs") loadRuns();
  if (name === "products") loadProducts();
  if (name === "board") loadBoard();
  if (name === "ops") {
    loadSchedules();
    loadSources();
  }
}

// QA ST-029：列表请求序号守卫（与 detailSeq 同口径），防慢响应晚到覆盖新页。
let listSeq = 0;
async function loadList() {
  const seq = ++listSeq;
  loading.value = true;
  try {
    const res = await fetchQueries({ page: page.value, page_size: pageSize, keyword: keyword.value || undefined });
    if (seq !== listSeq) return;
    items.value = res.data?.items || [];
    total.value = res.data?.total || 0;
  } catch (e: any) {
    if (seq !== listSeq) return;
    ElMessage.error(extractErrorDetail(e, "加载查询列表失败"));
  } finally {
    if (seq === listSeq) loading.value = false;
  }
}

// E6：搜索入口统一重置 page=1（分页 current-change 仍直接 loadList 不重置）。
function doSearch() {
  page.value = 1;
  loadList();
}

let runsSeq = 0;
async function loadRuns() {
  const seq = ++runsSeq;
  runsLoading.value = true;
  try {
    const res = await fetchQueryRuns({ page: runsPage.value, page_size: runsPageSize.value });
    if (seq !== runsSeq) return;
    runs.value = res.data?.items || [];
    runsTotal.value = res.data?.total || 0;
  } catch (e: any) {
    if (seq !== runsSeq) return;
    ElMessage.error(extractErrorDetail(e, "加载运行记录失败"));
  } finally {
    if (seq === runsSeq) runsLoading.value = false;
  }
}

async function openRunDetail(row: QueryRun) {
  try {
    const res = await fetchQueryRunDetail(row.id);
    runDetail.value = res.data;
    runDetailVisible.value = true;
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "运行详情失败"));
  }
}

// 186 P1-1：结果 → 准确性反馈入口。只携带非敏感定位 ID（run_id/query_code/
// query_version，取自已加载的运行详情数据），不带 SQL/提示词/digest；
// accuracy 页按 run_id 回读真实上下文，不信任 URL 传值。
const canFeedback = computed(() =>
  hasUserPermissions(["feedback.create"], currentUserProfile())
);

function feedbackRun(run?: QueryRun | null) {
  if (!run || !run.id || !run.query_code) return;
  router.push({
    path: "/asset/queries/accuracy",
    query: {
      run_id: String(run.id),
      query_code: run.query_code,
      query_version: run.version == null ? "" : String(run.version)
    }
  });
}

function feedbackMetricResult() {
  const definition = metricDetail.value?.definition;
  const version = metricDetail.value?.active_version?.version;
  if (!definition?.metric_code) return;
  router.push({
    path: "/asset/queries/accuracy",
    query: {
      metric_code: definition.metric_code,
      ...(version != null ? { metric_version: String(version) } : {})
    }
  });
}

function openIngest() {
  gateResult.value = null;
  ingestVisible.value = true;
}

function insertSqlExample() {
  form.sql_text = "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 10";
}

function resetQueryForm() {
  Object.assign(form, {
    query_code: "",
    title: "",
    system_code: "DATA_CENTER",
    source_code: "ods_8_216",
    dialect: "oracle",
    purpose: "",
    grain: "",
    period_field: "",
    limitations_text: "",
    recipe_refs_text: "",
    parameter_rows: [],
    sql_text: ""
  });
  gateResult.value = null;
}

async function previewGate() {
  try {
    const res = await previewQueryGate({
      sql_text: form.sql_text,
      dialect: form.dialect,
      source_code: form.source_code
    });
    gateResult.value = res.data;
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "门禁失败"));
  }
}

async function submitIngest() {
  saving.value = true;
  try {
    // 186 Q3：契约字段组装；空值不传（避免空字符串污染 schema）
    const payload: Record<string, unknown> = {
      query_code: form.query_code,
      title: form.title,
      system_code: form.system_code,
      source_code: form.source_code || undefined,
      dialect: form.dialect,
      purpose: form.purpose,
      sql_text: form.sql_text,
      grain: form.grain || undefined,
      period_field: form.period_field || undefined,
      limitations: form.limitations_text
        ? form.limitations_text.split("\n").map(s => s.trim()).filter(Boolean)
        : undefined,
      recipe_refs: form.recipe_refs_text
        ? form.recipe_refs_text.split(/[,，\n]/).map(s => s.trim()).filter(Boolean)
        : undefined,
    };
    const paramRows = form.parameter_rows.filter(row => row.name.trim());
    if (paramRows.length) {
      const schema: Record<string, unknown> = {};
      for (const row of paramRows) {
        schema[row.name.trim()] = {
          type: row.type || "string",
          required: Boolean(row.required),
          ...(row.default_value ? { default: row.default_value } : {}),
        };
      }
      payload.parameter_schema = schema;
    }
    const res = await ingestQuery(payload);
    const d = res.data;
    ElMessage.success(
      d.idempotent
        ? `幂等：已有版本 v${d.version?.version}`
        : `已摄取 v${d.version?.version} 状态=${d.version?.status}`
    );
    ingestVisible.value = false;
    resetQueryForm();
    await loadList();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "摄取失败"));
  } finally {
    saving.value = false;
  }
}

// E7：请求序号守卫——快速连点行时仅最后一次详情生效。
let detailSeq = 0;
async function openDetail(row: any) {
  const seq = ++detailSeq;
  try {
    const res = await fetchQueryDetail(row.query_code);
    if (seq !== detailSeq) return;
    detail.value = res.data;
    validationReport.value = null;
    detailVisible.value = true;
  } catch (e: any) {
    if (seq !== detailSeq) return;
    ElMessage.error(extractErrorDetail(e, "详情失败"));
  }
}

async function runValidate(version?: QueryVersion) {
  if (!version || !detail.value?.definition) return;
  validating.value = true;
  try {
    const res = await validateQueryVersion(detail.value.definition.query_code, version.version);
    validationReport.value = res.data;
    const current = await fetchQueryValidation(detail.value.definition.query_code, version.version);
    void current;
    await openDetail({ query_code: detail.value.definition.query_code });
    detailVisible.value = true;
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "验证失败"));
  } finally {
    validating.value = false;
  }
}

function openRunDialog(version?: QueryVersion) {
  if (!version) return;
  runTarget.value = version;
  runOutcome.value = null;
  runVisible.value = true;
}

async function submitRun() {
  if (!runTarget.value || !detail.value?.definition) return;
  const params = runParamFormRef.value?.getValues() ?? {};
  const valid = await runParamFormRef.value?.validate();
  if (!valid) {
    ElMessage.warning("参数校验未通过，未发送请求");
    return;
  }
  runLoading.value = true;
  try {
    const res = await runQueryVersion({
      query_code: detail.value.definition.query_code,
      version: runTarget.value.version,
      parameters: params
    });
    runOutcome.value = res.data;
    if (res.data.status !== "success") {
      ElMessage.warning(`运行失败（${res.data.error_class}）：${res.data.error_message}`);
    }
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "执行失败"));
  } finally {
    runLoading.value = false;
  }
}

let metricsSeq = 0;
async function loadMetrics() {
  const seq = ++metricsSeq;
  metricLoading.value = true;
  try {
    const res = await fetchMetrics({
      page: metricPage.value,
      page_size: metricPageSize,
      keyword: metricKeyword.value || undefined
    });
    if (seq !== metricsSeq) return;
    metricItems.value = res.data?.items || [];
    metricTotal.value = res.data?.total || 0;
  } catch (e: any) {
    if (seq !== metricsSeq) return;
    ElMessage.error(extractErrorDetail(e, "加载指标失败"));
  } finally {
    if (seq === metricsSeq) metricLoading.value = false;
  }
}

// E6：指标搜索重置页码。
function doMetricSearch() {
  metricPage.value = 1;
  loadMetrics();
}

function openMetricIngest() {
  metricIngestVisible.value = true;
}

async function submitMetric() {
  metricSaving.value = true;
  try {
    const res = await ingestMetric({ ...metricForm });
    ElMessage.success(`指标 v${res.data?.version?.version} 状态=${res.data?.version?.status}`);
    metricIngestVisible.value = false;
    await loadMetrics();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "指标提交失败"));
  } finally {
    metricSaving.value = false;
  }
}

async function openMetricDetail(row: any) {
  try {
    const res = await fetchMetricDetail(row.metric_code);
    metricDetail.value = res.data;
    calcResult.value = null;
    metricDetailVisible.value = true;
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "指标详情失败"));
  }
}

async function runCalculate(metricDetailData: any) {
  if (!calcPeriod.value) {
    ElMessage.warning("请填写期间 YYYY-MM");
    return;
  }
  calcLoading.value = true;
  try {
    const res = await calculateMetric(metricDetailData.definition.metric_code, {
      period_key: calcPeriod.value
    });
    calcResult.value = res.data;
    void fetchMetricResults(metricDetailData.definition.metric_code);
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "计算失败（需 metric:calculate 权限）"));
  } finally {
    calcLoading.value = false;
  }
}

let productsSeq = 0;
async function loadProducts() {
  const seq = ++productsSeq;
  productLoading.value = true;
  try {
    const res = await fetchDataProducts({
      page: productPage.value,
      page_size: 20,
      keyword: productKeyword.value || undefined,
      enabled: true
    });
    if (seq !== productsSeq) return;
    productItems.value = res.data?.items || [];
    productTotal.value = res.data?.total || 0;
  } catch (e: any) {
    if (seq !== productsSeq) return;
    ElMessage.error(extractErrorDetail(e, "加载数据产品失败"));
  } finally {
    if (seq === productsSeq) productLoading.value = false;
  }
}

// E6：产品搜索重置页码。
function doProductSearch() {
  productPage.value = 1;
  loadProducts();
}

async function publishCoreProducts() {
  publishLoading.value = true;
  try {
    const res = await publishCoreDataProducts();
    ElMessage.success(`已发布 ${res.data?.count ?? 0} 个 CORE 数据产品`);
    await loadProducts();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "发布失败"));
  } finally {
    publishLoading.value = false;
  }
}

function openProductExec(row: any) {
  productExecTarget.value = row;
  productExecResult.value = null;
  productExecVisible.value = true;
}

async function submitProductExec() {
  if (!productExecTarget.value) return;
  const params = productParamFormRef.value?.getValues() ?? {};
  const valid = await productParamFormRef.value?.validate();
  if (!valid) {
    ElMessage.warning("参数校验未通过，未发送请求");
    return;
  }
  productExecuting.value = true;
  try {
    const res = await executeDataProduct(productExecTarget.value.product_code, {
      parameters: params,
      execute_sql: productExecTarget.value.product_type === "query",
      caller_id: "web-console"
    });
    productExecResult.value = res.data;
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "执行失败"));
  } finally {
    productExecuting.value = false;
  }
}

async function loadBoard() {
  boardLoading.value = true;
  try {
    const res = await fetchMetricBoard({
      period_from: boardFrom.value || undefined,
      period_to: boardTo.value || undefined
    });
    const d = res.data;
    boardPeriods.value = d?.periods || [];
    boardCells.value = d?.cells || {};
    boardTotal.value = d?.total_results || 0;
    boardRows.value = (d?.metrics || []).map((m: any) => {
      const row: any = {
        metric_code: m.metric_code,
        title: m.title,
        has_active: m.has_active
      };
      for (const p of boardPeriods.value) {
        const cell = boardCells.value[m.metric_code]?.[p];
        row[p] = cell?.metric_value || cell?.status || (cell ? `${cell.numerator_value || ""}/${cell.denominator_value || ""}` : "-");
      }
      return row;
    });
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "加载看板失败"));
  } finally {
    boardLoading.value = false;
  }
}

function exportBoardCsv() {
  if (!boardRows.value.length) {
    ElMessage.warning("无看板数据");
    return;
  }
  // provenance columns ride along with values (144 §10.2)
  const headers = ["metric_code", "title", "has_active", ...boardPeriods.value];
  const lines = [headers.join(",")];
  for (const r of boardRows.value) {
    lines.push(
      headers
        .map(h => {
          const v = r[h] ?? "";
          const s = String(v).replace(/"/g, '""');
          return `"${s}"`;
        })
        .join(",")
    );
  }
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `metric_board_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function loadSchedules() {
  scheduleLoading.value = true;
  try {
    const res = await fetchSchedules();
    scheduleItems.value = res.data || [];
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "加载调度失败"));
  } finally {
    scheduleLoading.value = false;
  }
}

async function seedSchedules() {
  seedLoading.value = true;
  try {
    const res = await seedCoreSchedules();
    ElMessage.success(`已种子 ${res.data?.count ?? 0} 条（默认关闭）`);
    await loadSchedules();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "种子失败"));
  } finally {
    seedLoading.value = false;
  }
}

async function toggleSchedule(row: any) {
  try {
    await upsertSchedule({
      query_code: row.query_code,
      schedule_cron: row.schedule_cron || "0 3 * * *",
      source_code: row.source_code,
      enabled: !row.enabled,
      result_storage: "none"
    });
    ElMessage.success(row.enabled ? "已关闭" : "已启用（仍依赖全局开关）");
    await loadSchedules();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "更新失败"));
  }
}

async function loadSources() {
  sourceLoading.value = true;
  try {
    const res = await fetchQuerySourceCapabilities();
    sourceItems.value = res.data?.items || [];
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "加载多源能力失败"));
  } finally {
    sourceLoading.value = false;
  }
}

function routeTabSync(next: string) {
  tab.value = next;
  if (route.query.tab !== next) {
    router.replace({ query: { ...route.query, tab: next } }).catch(() => undefined);
  }
}

// 186 P2-6：handoff 参数一次性消费后立即从 URL 清除（保留 tab 等其他参数），
// 避免刷新/分享时误报"临时草稿已失效"。
function clearHandoffQuery() {
  if (!route.query.handoff) return;
  const query: LocationQueryRaw = { ...route.query };
  delete query.handoff;
  router.replace({ query }).catch(() => undefined);
}

function restoreTabFromUrl() {
  const fromUrl = String(route.query.tab || "");
  tab.value = (QUERY_TAB_WHITELIST as readonly string[]).includes(fromUrl) ? fromUrl : "list";
  onTab(tab.value);
}

// 186 Q3：消费 AI SQL 交接草稿（一次取用；无权限不可带入；URL 只带 id）
function consumeDraftHandoff() {
  const handoffId = route.query.handoff;
  if (!handoffId || typeof handoffId !== "string") return;
  const store = useQueryDraftHandoffStore();
  const draft = store.consume(handoffId);
  if (!draft) {
    ElMessage.info("临时草稿已失效，可返回重新生成或粘贴 SQL");
    return;
  }
  // P2-6：一次性消费成功（含权限不足被丢弃的情况），URL 不再保留 handoff
  clearHandoffQuery();
  if (!hasUserPermissions(["query.create"], currentUserProfile())) {
    ElMessage.warning("缺少 query.create 权限，草稿未带入");
    return;
  }
  const dirty =
    form.sql_text.trim() ||
    form.query_code.trim() ||
    form.title.trim() ||
    form.purpose.trim();
  const apply = () => {
    form.sql_text = draft.sqlText;
    form.system_code = draft.systemCode;
    // §4.5：sourceCode 无证据时清空默认值，要求有效来源选择，不沿用默认冒充已确认
    form.source_code = draft.sourceCode || "";
    if (draft.questionSummary) {
      form.title = form.title || draft.questionSummary.slice(0, 60);
      form.purpose = form.purpose || draft.questionSummary.slice(0, 200);
    }
    ingestVisible.value = true;
  };
  if (dirty) {
    ElMessageBox.confirm(
      "表单已有未保存内容。保留当前输入，还是替换为新草稿？",
      "草稿冲突",
      { confirmButtonText: "替换为新草稿", cancelButtonText: "保留当前", type: "warning" }
    )
      .then(apply)
      .catch(() => ElMessage.info("已保留当前表单内容"));
  } else {
    apply();
  }
}

onMounted(() => {
  restoreTabFromUrl();
  consumeDraftHandoff();
  loadList();
  loadRuns();
});
</script>

<style scoped>
.query-center {
  padding: 4px;
}
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.mb16 {
  margin-bottom: 16px;
}
.mt12 {
  margin-top: 12px;
}
.mt16 {
  margin-top: 16px;
}
.ml4 {
  margin-left: 4px;
}
.sql-box {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
  font-size: 12px;
  white-space: pre-wrap;
}
.digest {
  font-family: monospace;
  font-size: 11px;
  word-break: break-all;
}
.result-box {
  font-size: 12px;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  margin: 0;
}
.muted {
  color: #64748b;
  font-size: 13px;
  align-self: center;
}
.board-wrap {
  overflow: auto;
}
.mb12 {
  margin-bottom: 12px;
}
</style>
