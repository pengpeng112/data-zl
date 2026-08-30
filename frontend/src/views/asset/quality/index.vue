<template>
  <div class="quality-page">
    <el-tabs v-model="activeTab" class="quality-tabs" @tab-change="onTabChange">
      <template #extra>
        <el-button v-perms="'asset.quality.ai.view'" type="primary" plain size="small" @click="router.push('/asset/ai-quality')">AI 质控分析</el-button>
      </template>
      <!-- ============================================================ -->
      <!-- Tab 1: 质量总览 -->
      <!-- ============================================================ -->
      <el-tab-pane label="质量总览" name="overview" lazy>
        <section class="quality-stat-grid mb20">
          <ReStatCard label="总问题数" :value="summary.total_findings" tone="primary">
            <template #icon><IssueIcon /></template>
          </ReStatCard>
          <ReStatCard label="待处理" :value="summary.open_count" tone="danger">
            <template #icon><AlertIcon /></template>
          </ReStatCard>
          <ReStatCard label="已解决" :value="summary.resolved_count" tone="accent">
            <template #icon><CheckIcon /></template>
          </ReStatCard>
          <ReStatCard label="严重" :value="summary.critical_count" tone="danger">
            <template #icon><ErrorIcon /></template>
          </ReStatCard>
          <ReStatCard label="重要" :value="summary.major_count" tone="warning">
            <template #icon><WarningIcon /></template>
          </ReStatCard>
          <ReStatCard label="一般" :value="summary.minor_count" tone="info">
            <template #icon><InfoIcon /></template>
          </ReStatCard>
        </section>

        <section class="quality-metric-grid mb20">
          <ReStatCard label="规则总数" :value="metrics.total_rules" tone="primary" />
          <ReStatCard label="启用规则" :value="metrics.enabled_rules" tone="accent" />
          <ReStatCard label="SQL 建议规则（未启用）" :value="metrics.suggested_rules" tone="info" />
          <ReStatCard label="整改率" :value="formatPercent(metrics.pass_rate)" tone="warning" />
        </section>

        <el-card class="mb20 system-overview-card">
          <template #header>
            <div class="system-overview-head">
              <span>按系统质量概览</span>
              <small>点击卡片进入该系统问题清单</small>
            </div>
          </template>
          <div v-if="systemsWithFindings.length" class="system-card-grid">
            <button
              v-for="row in systemsWithFindings"
              :key="row.system_code"
              type="button"
              class="system-card"
              @click="filterBySystem(row)"
            >
              <div class="system-card-title">
                <strong>{{ systemDisplayName(row) }}</strong>
                <el-tag v-if="row.system_code !== 'UNASSIGNED'" size="small" effect="plain">
                  {{ systemShortCode(row.system_code) }}
                </el-tag>
              </div>
              <dl class="system-card-metrics">
                <div>
                  <dt>问题</dt>
                  <dd>{{ row.total_findings }}</dd>
                </div>
                <div>
                  <dt>待处理</dt>
                  <dd class="metric-danger">{{ row.open_count }}</dd>
                </div>
                <div>
                  <dt>已解决</dt>
                  <dd>{{ row.resolved_count }}</dd>
                </div>
                <div>
                  <dt>严重</dt>
                  <dd :class="{ 'metric-danger': row.critical_count > 0 }">{{ row.critical_count }}</dd>
                </div>
              </dl>
            </button>
          </div>
          <p v-if="systemsWithoutFindings.length" class="quiet-systems">
            暂无问题：{{ systemsWithoutFindings.map(systemDisplayName).join("、") }}
          </p>
        </el-card>
      </el-tab-pane>

      <!-- ============================================================ -->
      <!-- Tab 2: 规则库 -->
      <!-- ============================================================ -->
      <el-tab-pane label="规则库" name="rules" lazy>
        <el-card>
          <template #header>
            <div class="rule-header">
              <div>
                <span>质量规则</span>
                <small class="rule-header-hint">先看已启用的平台规则；SQL 建议默认停用，启用前需复核。</small>
              </div>
              <div class="rule-header-actions">
                <el-button v-perms="'asset.quality.rule.create'" type="primary" size="small" @click="openRuleDialog()">新增规则</el-button>
                <el-button v-perms="'asset.quality.rule.create'" size="small" :loading="autoGenerating" @click="autoGenerateRules">按主键/关系/缺失生成建议</el-button>
              </div>
            </div>
          </template>

          <el-alert
            class="rule-hint"
            type="info"
            show-icon
            :closable="false"
            title="规则库覆盖唯一性、缺失性、关联性、一致性。看板可启用 200 条以上规则；一键执行默认只跑元数据规则，避免对 HIS/ODS 大表做全表 SQL。"
          />

          <div class="rule-chip-row">
            <button
              v-for="chip in ruleCategoryChips"
              :key="chip.value || 'all'"
              type="button"
              class="rule-chip"
              :class="{ 'is-active': (ruleFilters.rule_category || '') === chip.value }"
              @click="filterRuleCategory(chip.value)"
            >
              {{ chip.label }} {{ chip.count }}
            </button>
          </div>

          <el-form :inline="true" class="rule-filter-form">
            <el-form-item label="规则分类">
              <el-select
                v-model="ruleFilters.rule_category"
                placeholder="全部分类"
                clearable
                class="filter-md"
                @change="loadRules(1)"
              >
                <el-option v-for="opt in ruleCategoryOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="检查范围">
              <el-select
                v-model="ruleFilters.check_scope"
                placeholder="全部范围"
                clearable
                class="filter-md"
                @change="loadRules(1)"
              >
                <el-option label="表内" value="TABLE_INNER" />
                <el-option label="表间" value="TABLE_RELATION" />
                <el-option label="跨系统" value="SYSTEM_CROSS" />
                <el-option label="业务逻辑" value="BUSINESS_LOGIC" />
              </el-select>
            </el-form-item>
            <el-form-item label="约束级别">
              <el-select
                v-model="ruleFilters.constraint_level"
                placeholder="全部级别"
                clearable
                class="filter-md"
                @change="loadRules(1)"
              >
                <el-option label="硬约束" value="HARD" />
                <el-option label="软约束" value="SOFT" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select
                v-model="ruleFilters.enabled"
                placeholder="全部状态"
                clearable
                class="filter-sm"
                @change="loadRules(1)"
              >
                <el-option label="启用" :value="true" />
                <el-option label="停用" :value="false" />
              </el-select>
            </el-form-item>
            <el-form-item label="关键词">
              <el-input
                v-model="ruleFilters.keyword"
                placeholder="编码/名称/表名"
                clearable
                class="filter-md"
                @keyup.enter="loadRules(1)"
                @clear="loadRules(1)"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadRules(1)">查询</el-button>
              <el-button @click="resetRuleFilters">重置</el-button>
            </el-form-item>
          </el-form>

          <el-table v-loading="rulesLoading" :data="rules" stripe size="small" class="rule-table">
            <el-table-column label="规则" min-width="240">
              <template #default="{ row }">
                <div class="rule-name">{{ row.rule_name || row.rule_code }}</div>
                <small class="rule-code">{{ row.rule_code }}</small>
              </template>
            </el-table-column>
            <el-table-column label="检查对象" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ ruleTargetText(row) }}</template>
            </el-table-column>
            <el-table-column prop="rule_category" label="分类" width="88">
              <template #default="{ row }">
                <el-tag size="small" :type="ruleCategoryTag(row.rule_category)">
                  {{ ruleCategoryLabel(row.rule_category) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="check_scope" label="范围" width="78">
              <template #default="{ row }">
                {{ checkScopeLabel(row.check_scope) }}
              </template>
            </el-table-column>
            <el-table-column prop="constraint_level" label="约束" width="78">
              <template #default="{ row }">
                <el-tag size="small" :type="row.constraint_level === 'HARD' ? 'danger' : 'info'">
                  {{ constraintLevelLabel(row.constraint_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="88">
              <template #default="{ row }">
                {{ executionModeLabel(row.execution_mode) }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="70">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                  {{ row.enabled ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="168" fixed="right">
              <template #default="{ row }">
                <div class="rule-ops">
                  <el-button v-perms="'asset.quality.rule.create'" size="small" text type="primary" @click="openRuleDialog(row)">编辑</el-button>
                  <el-button
                    v-perms="'asset.quality.rule.create'"
                    size="small"
                    text
                    :type="row.enabled ? 'warning' : 'success'"
                    @click="toggleRuleEnabled(row)"
                  >
                    {{ row.enabled ? '停用' : '启用' }}
                  </el-button>
                  <el-dropdown trigger="click">
                    <el-button size="small" text>更多</el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item v-if="row.check_sql" @click="validateRuleSql(row)">校验 SQL</el-dropdown-item>
                        <el-dropdown-item v-perms="'asset.quality.rule.create'" divided @click="deleteRule(row)">删除</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="rulesPage"
            class="mt15"
            :page-size="rulesPageSize"
            :total="rulesTotal"
            layout="total, prev, pager, next"
            @current-change="loadRules"
          />
        </el-card>

        <!-- 规则编辑弹窗 -->
        <el-dialog
          v-model="ruleDialogVisible"
          :title="editingRuleId ? '编辑规则' : '新增规则'"
          width="600px"
        >
          <el-form ref="ruleFormRef" :model="ruleForm" label-width="100px">
            <el-form-item label="规则编码">
              <el-input v-model="ruleForm.rule_code" placeholder="如 RULE_UNIQUE_001" />
            </el-form-item>
            <el-form-item label="规则名称">
              <el-input v-model="ruleForm.rule_name" placeholder="规则中文名称" />
            </el-form-item>
            <el-form-item label="规则分类">
              <el-select v-model="ruleForm.rule_category" class="full-width">
                <el-option v-for="opt in ruleCategoryOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="检查范围">
              <el-select v-model="ruleForm.check_scope" class="full-width">
                <el-option label="表内" value="TABLE_INNER" />
                <el-option label="表间" value="TABLE_RELATION" />
                <el-option label="跨系统" value="SYSTEM_CROSS" />
                <el-option label="业务逻辑" value="BUSINESS_LOGIC" />
              </el-select>
            </el-form-item>
            <el-form-item label="约束级别">
              <el-select v-model="ruleForm.constraint_level" class="full-width">
                <el-option label="硬约束" value="HARD" />
                <el-option label="软约束" value="SOFT" />
                <el-option label="提醒" value="WARN" />
                <el-option label="信息" value="INFO" />
              </el-select>
            </el-form-item>
            <el-form-item label="业务域">
              <el-input v-model="ruleForm.business_domain" placeholder="如 住院、门诊" />
            </el-form-item>
            <el-form-item label="执行模式">
              <el-select v-model="ruleForm.execution_mode" class="full-width">
                <el-option label="元数据检查" value="metadata_only" />
                <el-option label="SQL模板" value="sql_template" />
                <el-option label="源库探查" value="source_probe" />
              </el-select>
            </el-form-item>
            <el-form-item label="目标表名">
              <el-input v-model="ruleForm.target_table" placeholder="如 HIS.PAT_MASTER_INDEX" />
            </el-form-item>
            <el-form-item label="目标字段">
              <el-input v-model="ruleForm.target_field" placeholder="单个或逗号分隔" />
            </el-form-item>
            <el-form-item label="检查SQL">
              <el-input v-model="ruleForm.check_sql" type="textarea" :rows="3" placeholder="SELECT ..." />
            </el-form-item>
            <el-form-item label="说明">
              <el-input v-model="ruleForm.description" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item label="启用">
              <el-switch v-model="ruleForm.enabled" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="ruleDialogVisible = false">取消</el-button>
            <el-button v-perms="'asset.quality.rule.create'" type="primary" @click="saveRule">保存</el-button>
          </template>
        </el-dialog>

        <!-- 校验SQL结果弹窗 -->
        <el-dialog v-model="sqlValidateVisible" title="SQL 校验结果" width="500px">
          <div v-if="sqlValidateResult">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="是否有效">{{ sqlValidateResult.valid ? '是' : '否' }}</el-descriptions-item>
              <el-descriptions-item v-if="sqlValidateResult.errors?.length" label="错误">
                {{ sqlValidateResult.errors.join('；') }}
              </el-descriptions-item>
              <el-descriptions-item v-if="sqlValidateResult.warnings?.length" label="提醒">
                {{ sqlValidateResult.warnings.join('；') }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
          <template #footer>
            <el-button @click="sqlValidateVisible = false">关闭</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- ============================================================ -->
      <!-- Tab 3: 质控任务 -->
      <!-- ============================================================ -->
      <el-tab-pane label="质控任务" name="tasks" lazy>
        <el-card class="mb20">
          <template #header>
            <span>执行质控检查</span>
          </template>
          <el-button v-perms="'asset.quality.rule.execute'"
            type="primary"
            :loading="checking"
            @click="runCheck"
          >
            一键执行
          </el-button>
          <div v-if="checkResult" class="mt15">
            <el-descriptions :column="4" border size="small">
              <el-descriptions-item label="执行规则数">{{ checkResult.total_rules }}</el-descriptions-item>
              <el-descriptions-item label="发现问题数">{{ checkResult.total_findings }}</el-descriptions-item>
              <el-descriptions-item label="扫描记录数">{{ checkResult.total_records }}</el-descriptions-item>
              <el-descriptions-item label="通过率">
                <span :class="passRateClass(checkResult.pass_rate)">
                  {{ formatPercent(checkResult.pass_rate) }}
                </span>
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>

        <el-card>
          <template #header>
            <span>最近检查记录</span>
          </template>
          <!-- 146 E10（R5）：批次/记录共用 CheckRunsTable 组件 -->
          <CheckRunsTable
            :runs="checkRuns"
            :loading="tasksLoading"
            clickable
            show-triggered-by
            :page="tasksPage"
            :page-size="tasksPageSize"
            :total="tasksTotal"
            @row-click="openFindingsForRun"
            @page-change="loadCheckRuns"
          />
        </el-card>
      </el-tab-pane>

      <!-- ============================================================ -->
      <!-- Tab 4: 问题整改 -->
      <!-- ============================================================ -->
      <el-tab-pane label="问题整改" name="findings" lazy>
        <el-card>
          <template #header>
            <div class="findings-head">
              <strong>问题清单（{{ findingsTotal }}）</strong>
              <span>按库、表、字段定位问题后再分派或忽略</span>
            </div>
          </template>

          <el-form :inline="true">
            <el-form-item label="业务系统">
              <el-select
                v-model="filters.system_code"
                placeholder="全部系统"
                clearable
                filterable
                class="filter-md"
                @change="loadFindings(1)"
              >
                <el-option
                  v-for="row in systemsWithFindings"
                  :key="row.system_code"
                  :label="systemDisplayName(row)"
                  :value="row.system_code"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="检查批次">
              <el-select
                v-model="filters.run_id"
                placeholder="全部批次"
                clearable
                filterable
                class="filter-lg"
                @change="loadFindings(1)"
                @focus="ensureRunOptions"
              >
                <el-option
                  v-for="run in findingRunOptions"
                  :key="run.id"
                  :label="`#${run.id} · ${run.status} · findings ${run.total_findings ?? 0}`"
                  :value="run.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="严重程度">
              <el-select
                v-model="filters.severity"
                placeholder="全部"
                clearable
                class="filter-sm"
                @change="loadFindings(1)"
              >
                <el-option label="严重" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="一般" value="minor" />
                <el-option label="信息" value="info" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select
                v-model="filters.status"
                placeholder="全部"
                clearable
                class="filter-sm"
                @change="loadFindings(1)"
              >
                <el-option label="待处理" value="open" />
                <el-option label="已分派" value="assigned" />
                <el-option label="已确认" value="acknowledged" />
                <el-option label="已解决" value="resolved" />
                <el-option label="已忽略" value="ignored" />
                <el-option label="规则错误" value="rule_error" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="filters.keyword"
                placeholder="搜索问题/规则/库/表/字段"
                clearable
                class="filter-xl"
                @clear="loadFindings(1)"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadFindings(1)">查询</el-button>
            </el-form-item>
          </el-form>

          <el-table
            v-loading="fLoading"
            :data="findings"
            stripe
            size="small"
            row-key="id"
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="sample-panel">
                  <p v-if="row.rule_description">{{ row.rule_description }}</p>
                  <div class="finding-loc">
                    <span>库 {{ findingDbText(row) }}</span>
                    <span>表 {{ findingTableTitle(row) }}<template v-if="findingTableCode(row)"> / {{ findingTableCode(row) }}</template></span>
                    <span>字段 {{ findingColumnText(row) }}</span>
                  </div>
                  <pre v-if="row.sample_data" class="sample-json">{{ formatSampleData(row.sample_data) }}</pre>
                  <span v-else class="rule-code">没有可展示的样本</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="问题" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">{{ findingProblemText(row) }}</template>
            </el-table-column>
            <el-table-column label="库" width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ findingDbText(row) }}</template>
            </el-table-column>
            <el-table-column label="表" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <div>{{ findingTableTitle(row) }}</div>
                <small v-if="findingTableCode(row)" class="tech-name">{{ findingTableCode(row) }}</small>
              </template>
            </el-table-column>
            <el-table-column label="字段" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ findingColumnText(row) }}</template>
            </el-table-column>
            <el-table-column label="分类" width="88">
              <template #default="{ row }">
                <el-tag v-if="row.rule_category" size="small" :type="ruleCategoryTag(row.rule_category)">
                  {{ ruleCategoryLabel(row.rule_category) }}
                </el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="严重程度" width="90">
              <template #default="{ row }">
                <el-tag :type="sevTag(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="error_cnt" label="异常数" width="80" align="center" />
            <el-table-column label="异常率" width="90" align="center">
              <template #default="{ row }">
                {{ formatFindingRate(row.error_rate, row.metric_value) }}
              </template>
            </el-table-column>
            <el-table-column prop="assigned_to" label="分派人" width="90" />
            <el-table-column label="操作" width="168" fixed="right">
              <template #default="{ row }">
                <div class="rule-ops">
                  <el-button v-perms="'asset.quality.rule.execute'" size="small" text type="primary" @click="openAssignDialog(row)">分派</el-button>
                  <el-dropdown trigger="click" @command="(cmd: string) => recheckFinding(row, cmd)">
                    <el-button v-perms="'asset.quality.rule.execute'" size="small" text>更多</el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="confirmed">确认有效</el-dropdown-item>
                        <el-dropdown-item command="fixed">已修复</el-dropdown-item>
                        <el-dropdown-item command="ignored">忽略</el-dropdown-item>
                        <el-dropdown-item command="rechecked">已复核</el-dropdown-item>
                        <el-dropdown-item divided @click="openFindingStatusDialog(row)">编辑状态</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="findingsPage"
            class="mt15"
            :page-size="findingsPageSize"
            :total="findingsTotal"
            layout="total, prev, pager, next"
            @current-change="loadFindings"
          />
        </el-card>

        <!-- 分派弹窗 -->
        <el-dialog v-model="assignDialogVisible" title="分派问题" width="400px">
          <el-form>
            <el-form-item label="分派人">
              <el-input v-model="assignForm.assigned_to" placeholder="输入分派人姓名" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="assignForm.note" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="assignDialogVisible = false">取消</el-button>
            <el-button v-perms="'asset.quality.rule.execute'" type="primary" @click="submitAssign">确定</el-button>
          </template>
        </el-dialog>

        <!-- 编辑状态弹窗 -->
        <el-dialog v-model="findingStatusDialogVisible" title="编辑问题状态" width="400px">
          <el-form>
            <el-form-item label="状态">
              <el-select v-model="findingStatusForm.status" class="full-width">
                <el-option label="待处理" value="open" />
                <el-option label="已分派" value="assigned" />
                <el-option label="已确认" value="acknowledged" />
                <el-option label="已解决" value="resolved" />
                <el-option label="已忽略" value="ignored" />
              </el-select>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="findingStatusForm.note" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="findingStatusDialogVisible = false">取消</el-button>
            <el-button v-perms="'asset.quality.rule.execute'" type="primary" @click="submitFindingStatus">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- ============================================================ -->
      <!-- Tab 5: 执行记录 -->
      <!-- ============================================================ -->
      <el-tab-pane label="执行记录" name="records" lazy>
        <el-card>
          <template #header>
            <span>检查执行记录</span>
          </template>
          <!-- 146 E10（R5）：批次/记录共用 CheckRunsTable 组件 -->
          <CheckRunsTable
            :runs="records"
            :loading="recordsLoading"
            show-task-id
            show-system
            show-failed-reason
            :system-name-map="systemNameMap"
            :page="recordsPage"
            :page-size="recordsPageSize"
            :total="recordsTotal"
            @page-change="loadRecords"
          />
        </el-card>
      </el-tab-pane>

      <!-- ============================================================ -->
      <!-- Tab 6: 质量看板 -->
      <!-- ============================================================ -->
      <el-tab-pane label="质量看板" name="dashboard" lazy>
        <div v-if="dashboardReady">
          <section class="quality-metric-grid mb20">
            <ReStatCard label="总规则数" :value="metrics.total_rules" tone="primary" />
            <ReStatCard label="启用规则" :value="metrics.enabled_rules || 0" tone="accent" />
            <ReStatCard label="未启用建议" :value="metrics.suggested_rules || 0" tone="info" />
            <ReStatCard label="整改率" :value="formatPercent(metrics.pass_rate)" :tone="passRateTone(metrics.pass_rate)" />
          </section>

          <el-row :gutter="16" class="chart-row">
            <el-col :xs="24" :lg="12">
              <el-card>
                <template #header>
                  <span>规则分类分布</span>
                  <el-button size="small" class="float-right" @click="refreshDashboard">刷新</el-button>
                </template>
                <ReChart
                  height="360px"
                  :dark="false"
                  :option="ruleCategoryChartOption"
                  :empty="!metrics.rule_categories?.length"
                />
              </el-card>
            </el-col>
            <el-col :xs="24" :lg="12">
              <el-card>
                <template #header>
                  <span>问题 Top 5 表</span>
                </template>
                <ReChart
                  height="360px"
                  :dark="false"
                  :option="topTablesChartOption"
                  :empty="!metrics.top_tables?.length"
                />
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import ReStatCard from "@/components/ReStatCard/index.vue";
import ReChart from "@/components/ReChart/index.vue";
import { computed, ref, reactive, onMounted } from "vue";
import { useRouter } from "vue-router";

import {
  getQualitySummary,
  getQualitySummaryBySystem,
  getQualityMetrics,
  getQualityFindings,
  getQualityCheckRuns,
  runQualityCheck,
  listSystems,
  listQualityRules,
  createQualityRule,
  updateQualityRule,
  toggleQualityRule,
  validateQualityRuleSql,
  deleteQualityRule,
  autoGenerateQualityRules,
  updateQualityFinding,
  assignQualityFinding,
  recheckQualityFinding,
  type QualitySummary
} from "@/api/asset";
import { ElMessage, ElMessageBox } from "element-plus";
import { extractErrorDetail } from "@/utils/errorMessage";
import { fetchSystemNameMap } from "@/utils/systemNames";

// E3：同一加载序列的失败提示合并为一条（3 秒窗口内相同消息去重，防九连弹）。
let lastLoadErrorAt = 0;
let lastLoadErrorMsg = "";
function notifyLoadError(message: string) {
  const now = Date.now();
  if (message === lastLoadErrorMsg && now - lastLoadErrorAt < 3000) return;
  lastLoadErrorMsg = message;
  lastLoadErrorAt = now;
  ElMessage.error(message);
}
import {
  RULE_CATEGORY_OPTIONS,
  checkScopeLabel,
  constraintLevelLabel,
  executionModeLabel,
  findingColumnText,
  findingDbText,
  findingProblemText,
  findingTableCode,
  findingTableTitle,
  formatFindingRate,
  ruleCategoryLabel,
  ruleCategoryTag,
  ruleTargetText
} from "@/views/asset/quality/qualityRuleLabels";
// 146 E10（R5）：共享类型与展示工具抽入 qualityContracts / CheckRunsTable
import CheckRunsTable from "@/views/asset/quality/CheckRunsTable.vue";
import {
  findingStatusLabel as statusLabel,
  findingStatusTag as statusTag,
  formatPercent,
  formatSampleData,
  passRateClass,
  passRateTone,
  runStatusLabel,
  severityLabel,
  severityTag as sevTag,
  type CheckRunItem,
  type FindingItem,
  type MetricsData,
  type RuleCreateForm,
  type RuleItem,
  type SystemSummaryItem
} from "@/views/asset/quality/qualityContracts";
import AlertIcon from "~icons/ri/alarm-warning-line";
import CheckIcon from "~icons/ri/checkbox-circle-line";
import ErrorIcon from "~icons/ri/error-warning-line";
import InfoIcon from "~icons/ri/information-line";
import IssueIcon from "~icons/ri/file-warning-line";
import WarningIcon from "~icons/ri/alert-line";

const systemNameMap = reactive<Record<string, string>>({});
const router = useRouter();

// F5：loadSystemNames 两份合一 → utils/systemNames。
async function loadSystemNames() {
  const map = await fetchSystemNameMap();
  Object.assign(systemNameMap, map);
}

// ============================================================
// Types：146 E10（R5）起由 qualityContracts 共享提供（SystemSummaryItem/RuleItem/
// RuleCreateForm/CheckRunItem/FindingItem/MetricsData），此处不再重复定义。
// ============================================================

// ============================================================
// Tab state
// ============================================================
const activeTab = ref("overview");

// ============================================================
// Tab 1: 质量总览
// ============================================================
const summary = ref<QualitySummary>({
  total_findings: 0,
  open_count: 0,
  acknowledged_count: 0,
  resolved_count: 0,
  critical_count: 0,
  major_count: 0,
  minor_count: 0,
  info_count: 0,
  top_tables: []
});

const systemSummary = ref<SystemSummaryItem[]>([]);

const metrics = ref<MetricsData>({
  total_rules: 0,
  enabled_rules: 0,
  suggested_rules: 0,
  sql_rules: 0,
  pass_rate: null,
  rule_categories: [],
  top_tables: []
});

function loadSummary() {
  getQualitySummary()
    .then(({ data }) => {
      summary.value = data;
    })
    .catch(error => {
      notifyLoadError(extractErrorDetail(error, "质量汇总加载失败"));
    });
}

function loadSystemSummary() {
  getQualitySummaryBySystem()
    .then(({ data }) => {
      const rows = (data as any) || [];
      systemSummary.value = rows.map((row: any) => ({
        system_code: row.system_code,
        system_name_cn: row.system_name_cn,
        total_findings: row.total_findings ?? row.findings_total ?? 0,
        open_count: row.open_count ?? row.findings_open ?? 0,
        resolved_count: row.resolved_count ?? 0,
        critical_count: row.critical_count ?? 0
      }));
    })
    .catch(error => {
      systemSummary.value = [];
      notifyLoadError(extractErrorDetail(error, "系统质量汇总加载失败"));
    });
}

function loadMetrics() {
  return getQualityMetrics()
    .then(({ data }) => {
      const raw = (data as any) || {};
      // Normalize rule_categories: accept array or legacy dict
      let cats = raw.rule_categories;
      if (cats && !Array.isArray(cats) && typeof cats === "object") {
        cats = Object.entries(cats).map(([category, count]) => ({ category, count: Number(count) || 0 }));
      }
      metrics.value = {
        total_rules: raw.total_rules || 0,
        enabled_rules: raw.enabled_rules ?? 0,
        suggested_rules: raw.suggested_rules ?? 0,
        sql_rules: raw.sql_rules || 0,
        pass_rate: raw.resolution_rate ?? raw.pass_rate ?? null,
        rules_pass_rate: raw.rules_pass_rate ?? null,
        rule_categories: Array.isArray(cats) ? cats : [],
        top_tables: raw.top_tables || []
      };
    })
    .catch(error => {
      notifyLoadError(extractErrorDetail(error, "质量指标加载失败"));
    });
}

function filterBySystem(row: SystemSummaryItem) {
  filters.system_code = row.system_code || "";
  filters.keyword = "";
  activeTab.value = "findings";
  loadFindings(1);
}

function systemDisplayName(row: SystemSummaryItem) {
  if (row.system_code === "UNASSIGNED") return "待归类";
  return row.system_name_cn || systemNameMap[row.system_code] || row.system_code;
}

function systemShortCode(code: string) {
  const aliases: Record<string, string> = {
    JHEMR_VASTBASE: "JHEMR",
    HIS_SOURCE: "HIS",
    LIS_SOURCE: "LIS",
    PACS_SOURCE: "PACS",
    PAPERLESS_CDMS: "CDMS",
    ULTRASOUND_ENDOSCOPY: "US/ES",
    MOBILE_NURSING: "护理",
    DATA_CENTER: "数据中心"
  };
  return aliases[code] || code;
}

const systemsWithFindings = computed(() =>
  systemSummary.value.filter(row => (row.total_findings || 0) > 0)
);
const systemsWithoutFindings = computed(() =>
  systemSummary.value.filter(row => row.system_code !== "UNASSIGNED" && !(row.total_findings || 0))
);

// ============================================================
// Tab 2: 规则库
// ============================================================
const rules = ref<RuleItem[]>([]);
const rulesLoading = ref(false);
const autoGenerating = ref(false);
const rulesPage = ref(1);
const rulesPageSize = ref(30);
const rulesTotal = ref(0);
const ruleFilters = reactive({
  rule_category: "",
  check_scope: "",
  constraint_level: "",
  enabled: undefined as boolean | undefined,
  keyword: ""
});
const ruleCategoryOptions = RULE_CATEGORY_OPTIONS;
const ruleCategoryChips = computed(() => {
  const counts = new Map((metrics.value.rule_categories || []).map(item => [item.category, item.count]));
  const total = metrics.value.total_rules || 0;
  return [
    { value: "", label: "全部", count: total },
    ...RULE_CATEGORY_OPTIONS.map(item => ({
      value: item.value,
      label: item.label,
      count: counts.get(item.value) || 0
    }))
  ];
});

const ruleDialogVisible = ref(false);
const editingRuleId = ref<number | null>(null);
const ruleForm = reactive<RuleCreateForm>({
  rule_code: "",
  rule_name: "",
  rule_category: "UNIQUE",
  check_scope: "TABLE_INNER",
  constraint_level: "HARD",
  business_domain: "",
  execution_mode: "sql_template",
  target_table: "",
  target_field: "",
  check_sql: "",
  description: "",
  enabled: true
});

const sqlValidateVisible = ref(false);
const sqlValidateResult = ref<any>(null);

function filterRuleCategory(value: string) {
  ruleFilters.rule_category = value;
  loadRules(1);
}

// formatPercent 由 qualityContracts 共享提供。

function loadRules(page?: number) {
  if (page) rulesPage.value = page;
  rulesLoading.value = true;
  const params: any = {
    page: rulesPage.value,
    page_size: rulesPageSize.value
  };
  if (ruleFilters.rule_category) params.rule_category = ruleFilters.rule_category;
  if (ruleFilters.check_scope) params.check_scope = ruleFilters.check_scope;
  if (ruleFilters.constraint_level) params.constraint_level = ruleFilters.constraint_level;
  if (ruleFilters.enabled !== undefined) params.enabled = ruleFilters.enabled;
  if (ruleFilters.keyword) params.keyword = ruleFilters.keyword;

  listQualityRules(params as any)
    .then(({ data }) => {
      const payload = data;
      // Transition: accept page envelope or legacy bare array
      if (Array.isArray(payload)) {
        rules.value = payload as any;
        rulesTotal.value = payload.length;
      } else {
        rules.value = (payload?.items || []) as any;
        rulesTotal.value = payload?.total || 0;
      }
    })
    .catch((err: any) => {
      rules.value = [];
      rulesTotal.value = 0;
      ElMessage.error(extractErrorDetail(err, "规则列表加载失败"));
    })
    .finally(() => {
      rulesLoading.value = false;
    });
}

async function autoGenerateRules() {
  autoGenerating.value = true;
  try {
    const res = await autoGenerateQualityRules({ limit: 200 });
    const data = res.data || {};
    ElMessage.success(`已生成 ${data.created || 0} 条建议，跳过 ${data.skipped || 0} 条重复规则`);
    loadMetrics();
    loadRules(1);
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "规则建议生成失败"));
  } finally {
    autoGenerating.value = false;
  }
}

function resetRuleFilters() {
  ruleFilters.rule_category = "";
  ruleFilters.check_scope = "";
  ruleFilters.constraint_level = "";
  ruleFilters.enabled = undefined;
  ruleFilters.keyword = "";
  loadRules(1);
}

function openRuleDialog(row?: RuleItem) {
  editingRuleId.value = row ? row.id : null;
  if (row) {
    ruleForm.rule_code = row.rule_code;
    ruleForm.rule_name = row.rule_name;
    ruleForm.rule_category = row.rule_category;
    ruleForm.check_scope = row.check_scope;
    ruleForm.constraint_level = row.constraint_level;
    ruleForm.business_domain = row.business_domain || "";
    ruleForm.execution_mode = row.execution_mode || "";
    ruleForm.target_table = row.target_table || "";
    ruleForm.target_field = row.target_field || "";
    ruleForm.check_sql = row.check_sql || "";
    ruleForm.description = row.description || "";
    ruleForm.enabled = row.enabled;
  } else {
    ruleForm.rule_code = "";
    ruleForm.rule_name = "";
    ruleForm.rule_category = "UNIQUE";
    ruleForm.check_scope = "TABLE_INNER";
    ruleForm.constraint_level = "HARD";
    ruleForm.business_domain = "";
    ruleForm.execution_mode = "sql_template";
    ruleForm.target_table = "";
    ruleForm.target_field = "";
    ruleForm.check_sql = "";
    ruleForm.description = "";
    ruleForm.enabled = true;
  }
  ruleDialogVisible.value = true;
}

function saveRule() {
  const payload: any = { ...ruleForm };
  const request = editingRuleId.value
    ? updateQualityRule(editingRuleId.value, payload)
    : createQualityRule(payload);
  request
    .then(() => {
      ElMessage.success(editingRuleId.value ? "规则已更新" : "规则已创建");
      ruleDialogVisible.value = false;
      loadRules();
    })
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "规则保存失败"));
    });
}

function toggleRuleEnabled(row: RuleItem) {
  const newEnabled = !row.enabled;
  toggleQualityRule(row.id, newEnabled)
    .then(() => {
      ElMessage.success(`已${newEnabled ? '启用' : '停用'}`);
      loadRules();
    })
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "规则启停失败"));
    });
}

function validateRuleSql(row: RuleItem) {
  validateQualityRuleSql(row.id)
    .then(({ data }) => {
      sqlValidateResult.value = data;
      sqlValidateVisible.value = true;
    })
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "SQL 校验失败"));
    });
}

function deleteRule(row: RuleItem) {
  ElMessageBox.confirm(`确定删除规则 "${row.rule_code}"？`, "删除规则", {
    confirmButtonText: "删除",
    cancelButtonText: "取消",
    type: "warning"
  })
    .then(() => {
      deleteQualityRule(row.id)
        .then(() => {
          ElMessage.success("已删除");
          loadRules();
        })
        .catch(error => {
          ElMessage.error(extractErrorDetail(error, "规则删除失败"));
        });
    })
    .catch(() => {}); // 用户取消删除
}

// ============================================================
// Tab 3: 质控任务
// ============================================================
const checking = ref(false);
const checkResult = ref<any>(null);
const checkRuns = ref<CheckRunItem[]>([]);
const tasksLoading = ref(false);
const tasksPage = ref(1);
const tasksPageSize = ref(20);
const tasksTotal = ref(0);

function runCheck() {
  checking.value = true;
  runQualityCheck()
    .then(({ data }) => {
      checkResult.value = data;
      ElMessage.success(`检查完成：${data.total_findings} 个问题`);
      loadCheckRuns(1);
    })
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "质量检查执行失败"));
    })
    .finally(() => {
      checking.value = false;
    });
}

function openFindingsForRun(row: CheckRunItem) {
  filters.run_id = row.id;
  activeTab.value = "findings";
  loadFindings(1);
}

function loadCheckRuns(page?: number) {
  if (page) tasksPage.value = page;
  tasksLoading.value = true;
  getQualityCheckRuns({ page: tasksPage.value, page_size: tasksPageSize.value })
    .then(({ data }) => {
      checkRuns.value = (data.items || []) as any;
      tasksTotal.value = data.total || 0;
    })
    .catch(error => {
      notifyLoadError(extractErrorDetail(error, "检查历史加载失败"));
    })
    .finally(() => {
      tasksLoading.value = false;
    });
}

// runStatusLabel 由 qualityContracts 共享提供。

// ============================================================
// Tab 4: 问题整改
// ============================================================
const findings = ref<FindingItem[]>([]);
const fLoading = ref(false);
const findingsPage = ref(1);
const findingsPageSize = ref(30);
const findingsTotal = ref(0);
const findingRunOptions = ref<CheckRunItem[]>([]);
const filters = reactive({
  rule_code: "",
  severity: "",
  status: "open",
  keyword: "",
  system_code: "",
  run_id: undefined as number | undefined
});

const assignDialogVisible = ref(false);
const assignFindingId = ref<number | null>(null);
const assignForm = reactive({ assigned_to: "", note: "" });

const findingStatusDialogVisible = ref(false);
const findingStatusFindingId = ref<number | null>(null);
const findingStatusForm = reactive({ status: "", note: "" });

// 146 E10（R5）：sevTag/severityLabel/statusLabel/statusTag/formatSampleData
// 由 qualityContracts 共享提供（import 处已别名），本文件不再重复定义。

function ensureRunOptions() {
  if (findingRunOptions.value.length) return;
  getQualityCheckRuns({ page: 1, page_size: 50 })
    .then(({ data }) => {
      findingRunOptions.value = (data.items || []) as any;
    })
    .catch(() => {
      // 下拉选项预取失败不弹窗（非关键路径），保持空列表回退。
      findingRunOptions.value = [];
    });
}

function loadFindings(page?: number) {
  if (page) findingsPage.value = page;
  fLoading.value = true;
  ensureRunOptions();
  getQualityFindings({
    page: findingsPage.value,
    page_size: findingsPageSize.value,
    severity: filters.severity || undefined,
    status: filters.status || undefined,
    rule_code: filters.rule_code || undefined,
    keyword: filters.keyword || undefined,
    system_code: filters.system_code || undefined,
    run_id: filters.run_id || undefined
  })
    .then(({ data }) => {
      findings.value = data.items as any;
      findingsTotal.value = data.total;
    })
    .catch(error => {
      notifyLoadError(extractErrorDetail(error, "质量问题列表加载失败"));
    })
    .finally(() => {
      fLoading.value = false;
    });
}

function openAssignDialog(row: FindingItem) {
  assignFindingId.value = row.id;
  assignForm.assigned_to = row.assigned_to || "";
  assignForm.note = "";
  assignDialogVisible.value = true;
}

function submitAssign() {
  if (!assignFindingId.value) return;
  assignQualityFinding(assignFindingId.value, {
    assigned_to: assignForm.assigned_to,
    note: assignForm.note
  })
    .then(() => {
      ElMessage.success("已分派");
      assignDialogVisible.value = false;
      loadFindings();
    })
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "问题分派失败"));
    });
}

function recheckFinding(row: FindingItem, status: string) {
  recheckQualityFinding(row.id, status)
    .then(() => {
      ElMessage.success("复核完成");
      loadFindings();
    })
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "问题复核失败"));
    });
}

function openFindingStatusDialog(row: FindingItem) {
  findingStatusFindingId.value = row.id;
  findingStatusForm.status = row.status || "";
  findingStatusForm.note = "";
  findingStatusDialogVisible.value = true;
}

function submitFindingStatus() {
  if (!findingStatusFindingId.value) return;
  const body: any = {
    status: findingStatusForm.status,
    note: findingStatusForm.note
  };
  updateQualityFinding(findingStatusFindingId.value, body)
    .then(() => {
      ElMessage.success("状态已更新");
      findingStatusDialogVisible.value = false;
      loadFindings();
    })
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "问题状态更新失败"));
    });
}

// ============================================================
// Tab 5: 执行记录
// ============================================================
const records = ref<CheckRunItem[]>([]);
const recordsLoading = ref(false);
const recordsPage = ref(1);
const recordsPageSize = ref(20);
const recordsTotal = ref(0);


function loadRecords(page?: number) {
  if (page) recordsPage.value = page;
  recordsLoading.value = true;
  getQualityCheckRuns({ page: recordsPage.value, page_size: recordsPageSize.value })
    .then(({ data }) => {
      records.value = (data.items || []) as any;
      recordsTotal.value = data.total || 0;
    })
    .catch(error => {
      notifyLoadError(extractErrorDetail(error, "执行记录加载失败"));
    })
    .finally(() => {
      recordsLoading.value = false;
    });
}

// ============================================================
// Tab 6: 质量看板
// ============================================================
const dashboardReady = ref(false);

// passRateTone/passRateClass 由 qualityContracts 共享提供。

const ruleCategoryChartOption = computed(() => {
  let categories: any[] = metrics.value.rule_categories || [];
  if (!Array.isArray(categories) && categories && typeof categories === "object") {
    categories = Object.entries(categories as Record<string, number>).map(([category, count]) => ({
      category,
      count
    }));
  }
  const data = (Array.isArray(categories) ? categories : []).map((c: any) => ({
    name: ruleCategoryLabel(c.category ?? c.name ?? "other"),
    value: Number(c.count ?? c.value ?? 0)
  }));
  return {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { orient: "vertical", left: 10, top: 20 },
    series: [
      {
        type: "pie",
        radius: ["42%", "70%"],
        center: ["58%", "55%"],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 8, borderColor: "#fff", borderWidth: 2 },
        data,
        label: { formatter: "{b}: {c}" }
      }
    ]
  };
});

const topTablesChartOption = computed(() => {
  const tables = (metrics.value.top_tables || []).slice(0, 5).reverse();
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 120, right: 24, top: 28, bottom: 28, containLabel: true },
    xAxis: { type: "value", name: "问题数" },
    yAxis: {
      type: "category",
      data: tables.map(t => t.table),
      axisLabel: { width: 100, overflow: "truncate" }
    },
    series: [
      {
        type: "bar",
        barWidth: 14,
        data: tables.map(t => t.count),
        itemStyle: {
          borderRadius: [0, 8, 8, 0],
          color: "#0EA5E9"
        }
      }
    ]
  };
});

async function loadDashboardData() {
  loadSummary();
  await loadMetrics();
}

async function initDashboard() {
  dashboardReady.value = true;
  await loadDashboardData();
}

function refreshDashboard() {
  loadDashboardData();
}
// ============================================================
// Tab change handler
// ============================================================
function onTabChange(tabName: any) {
  const name = String(tabName);
  switch (name) {
    case "overview":
      loadSummary();
      loadSystemSummary();
      loadMetrics();
      break;
    case "rules":
      loadRules();
      loadMetrics();
      break;
    case "tasks":
      loadCheckRuns();
      break;
    case "findings":
      loadFindings(findingsPage.value);
      break;
    case "records":
      loadRecords();
      break;
    case "dashboard":
      initDashboard();
      break;
  }
}

// ============================================================
// Initialization
// ============================================================
onMounted(() => {
  void loadSystemNames();
  loadSummary();
  loadSystemSummary();
  loadMetrics();
});

</script>

<style scoped>
.quality-page {
  padding: 4px;
}
.quality-tabs { margin-top: 0; }
.findings-head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 22px;
}
.findings-head span {
  color: var(--text-secondary, #64748b);
  font-size: 12px;
  font-weight: 400;
}
.tech-name { color: var(--text-secondary, #64748b); font-size: 12px; }
.finding-loc {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 6px 0 10px;
  color: var(--text-secondary, #64748b);
  font-size: 12px;
}
.rule-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.rule-header-hint {
  display: block;
  margin-top: 4px;
  color: var(--text-secondary, #64748b);
  font-size: 12px;
  font-weight: 400;
}
.rule-header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.rule-hint { margin-bottom: 12px; }
.rule-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.rule-chip {
  border: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}
.rule-chip.is-active {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.rule-filter-form { margin-bottom: 8px; }
.rule-name { font-weight: 600; line-height: 1.3; }
.rule-code { color: var(--text-secondary, #64748b); font-size: 12px; }
.rule-ops {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  white-space: nowrap;
  gap: 0;
}
.rule-ops :deep(.el-button) {
  margin: 0;
  padding: 0 6px;
}
.system-code-inline { display: block; color: var(--text-secondary); font-size: 11px; }
.quality-stat-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 16px;
}
.quality-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.system-overview-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.system-overview-head small {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 400;
}
.system-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.system-card {
  display: block;
  width: 100%;
  padding: 14px 16px;
  text-align: left;
  cursor: pointer;
  background: var(--bg-page, #f8fafc);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 12px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.system-card:hover {
  border-color: #7dd3fc;
  box-shadow: 0 6px 16px rgb(14 165 233 / 10%);
}
.system-card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}
.system-card-title strong {
  font-size: 15px;
  color: var(--text-primary, #0f172a);
}
.system-card-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}
.system-card-metrics dt {
  margin: 0;
  color: var(--text-secondary, #64748b);
  font-size: 11px;
}
.system-card-metrics dd {
  margin: 2px 0 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary, #0f172a);
}
.quiet-systems {
  margin: 14px 0 0;
  color: var(--text-secondary, #64748b);
  font-size: 12px;
  line-height: 1.5;
}
.quality-page :deep(.el-card) {
  border-color: var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);
}
.quality-page :deep(.el-table) {
  --el-table-header-bg-color: var(--bg-elevated);
  --el-table-row-hover-bg-color: rgb(14 165 233 / 6%);
  --el-table-border-color: var(--border-light);
  font-size: 13px;
}
@media (max-width: 1280px) {
  .quality-stat-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .quality-stat-grid,
  .quality-metric-grid { grid-template-columns: 1fr; }
}
.metric-accent {
  color: var(--accent-500);
  font-weight: 700;
}
.metric-warning {
  color: var(--warning);
  font-weight: 700;
}
.metric-danger {
  color: var(--danger);
  font-weight: 700;
}
.sample-panel {
  padding: 8px 20px;
}
.clickable-row { cursor: pointer; }
.ml12 { margin-left: 12px; }
.ml4 { margin-left: 4px; }
.float-right { float: right; }
.filter-sm { width: 110px; }
.filter-md { width: 130px; }
.filter-lg { width: 160px; }
.filter-xl { width: 200px; }
.full-width { width: 100%; }
.sample-json {
  max-height: 300px;
  padding: 10px;
  overflow: auto;
  font-size: 12px;
  color: var(--text-regular);
  word-break: break-all;
  white-space: pre-wrap;
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
}
</style>
