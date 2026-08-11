<template>
  <div class="quality-page">
    <RePageHeader title="数据质量" subtitle="集中查看质量问题、规则库、执行任务、整改状态和质量看板。">
      <template #icon><QualityIcon /></template>
    </RePageHeader>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
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
          <ReStatCard label="SQL 规则数" :value="metrics.sql_rules" tone="accent" />
          <ReStatCard label="通过率" :value="formatPercent(metrics.pass_rate)" tone="warning" />
        </section>

        <el-card class="mb20">
          <template #header>
            <span>按系统质量概览</span>
          </template>
          <el-table
            :data="systemSummary"
            stripe
            size="small"
            @row-click="filterBySystem"
            class="clickable-row"
          >
            <el-table-column label="业务系统" width="180">
              <template #default="{ row }">
                {{ row.system_name_cn || systemNameMap[row.system_code] || row.system_code }}
                <small class="system-code-inline">{{ row.system_code }}</small>
              </template>
            </el-table-column>
            <el-table-column prop="total_findings" label="问题总数" width="100" align="center" />
            <el-table-column prop="open_count" label="待处理" width="100" align="center" />
            <el-table-column prop="resolved_count" label="已解决" width="100" align="center" />
            <el-table-column prop="critical_count" label="严重问题数" width="120" align="center">
              <template #default="{ row }">
                <span :class="{ 'metric-danger': row.critical_count > 0 }">
                  {{ row.critical_count }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- ============================================================ -->
      <!-- Tab 2: 规则库 -->
      <!-- ============================================================ -->
      <el-tab-pane label="规则库" name="rules" lazy>
        <el-card>
          <template #header>
            <span>质量规则</span>
            <el-button v-perms="'asset.quality.rule.create'" type="primary" size="small" class="ml12" @click="openRuleDialog()">新增规则</el-button>
            <el-button v-perms="'asset.quality.rule.create'" size="small" :loading="autoGenerating" @click="autoGenerateRules">按主键/关系生成建议</el-button>
          </template>

          <el-form :inline="true">
            <el-form-item label="规则分类">
              <el-select
                v-model="ruleFilters.rule_category"
                placeholder="全部分类"
                clearable
                class="filter-md"
                @change="loadRules(1)"
              >
                <el-option label="唯一性" value="UNIQUE" />
                <el-option label="完整性" value="COMPLETE" />
                <el-option label="规范性" value="STANDARD" />
                <el-option label="关联性" value="RELATION" />
                <el-option label="准确性" value="ACCURACY" />
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
            <el-form-item>
              <el-button type="primary" @click="loadRules(1)">查询</el-button>
              <el-button @click="resetRuleFilters">重置</el-button>
            </el-form-item>
          </el-form>

          <el-table v-loading="rulesLoading" :data="rules" stripe size="small">
            <el-table-column prop="rule_code" label="规则编码" width="200" show-overflow-tooltip />
            <el-table-column prop="rule_name" label="规则名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="rule_category" label="分类" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="ruleCategoryTag(row.rule_category)">
                  {{ ruleCategoryLabel(row.rule_category) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="check_scope" label="范围" width="80">
              <template #default="{ row }">
                {{ checkScopeLabel(row.check_scope) }}
              </template>
            </el-table-column>
            <el-table-column prop="constraint_level" label="约束" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.constraint_level === 'HARD' ? 'danger' : 'info'">
                  {{ constraintLevelLabel(row.constraint_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="business_domain" label="业务域" width="100" />
            <el-table-column prop="execution_mode" label="执行模式" width="90" />
            <el-table-column label="状态" width="70">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                  {{ row.enabled ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="240" fixed="right">
              <template #default="{ row }">
                <el-button v-perms="'asset.quality.rule.create'" size="small" @click="openRuleDialog(row)">编辑</el-button>
                <el-button
                  v-perms="'asset.quality.rule.create'"
                  size="small"
                  :type="row.enabled ? 'warning' : 'success'"
                  @click="toggleRuleEnabled(row)"
                >
                  {{ row.enabled ? '停用' : '启用' }}
                </el-button>
                <el-button v-perms="'asset.quality.rule.create'"
                  v-if="row.check_sql"
                  size="small"
                  type="info"
                  @click="validateRuleSql(row)"
                >
                  校验SQL
                </el-button>
                <el-button v-perms="'asset.quality.rule.create'" size="small" type="danger" @click="deleteRule(row)">删除</el-button>
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
                <el-option label="唯一性" value="UNIQUE" />
                <el-option label="完整性" value="COMPLETE" />
                <el-option label="规范性" value="STANDARD" />
                <el-option label="关联性" value="RELATION" />
                <el-option label="准确性" value="ACCURACY" />
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
          <el-table
            v-loading="tasksLoading"
            :data="checkRuns"
            stripe
            size="small"
            class="clickable-row"
            @row-click="openFindingsForRun"
          >
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="started_at" label="开始时间" width="170" />
            <el-table-column prop="triggered_by" label="触发方式" width="80" />
            <el-table-column prop="total_rules" label="规则数" width="80" align="center" />
            <el-table-column prop="total_findings" label="发现问题" width="100" align="center" />
            <el-table-column prop="total_records" label="扫描记录" width="100" align="center" />
            <el-table-column prop="error_records" label="异常记录" width="100" align="center" />
            <el-table-column label="通过率" width="100" align="center">
              <template #default="{ row }">
                <span v-if="row.pass_rate != null" :class="passRateClass(row.pass_rate)">
                  {{ formatPercent(row.pass_rate) }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === 'success' ? 'success' : row.status === 'running' ? 'warning' : 'danger'"
                  size="small"
                >
                  {{ runStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="tasksPage"
            class="mt15"
            :page-size="tasksPageSize"
            :total="tasksTotal"
            layout="total, prev, pager, next"
            @current-change="loadCheckRuns"
          />
        </el-card>
      </el-tab-pane>

      <!-- ============================================================ -->
      <!-- Tab 4: 问题整改 -->
      <!-- ============================================================ -->
      <el-tab-pane label="问题整改" name="findings" lazy>
        <el-card>
          <template #header>
            <span>问题清单（{{ findingsTotal }}）</span>
          </template>

          <el-form :inline="true">
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
            <el-form-item label="规则编码">
              <el-input
                v-model="filters.rule_code"
                placeholder="规则编码"
                clearable
                class="filter-lg"
                @clear="loadFindings(1)"
              />
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
                placeholder="搜索表名/系统"
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
                  <strong>样本数据：</strong>
                  <pre class="sample-json">{{ formatSampleData(row.sample_data) }}</pre>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="rule_code" label="规则编码" width="160" show-overflow-tooltip />
            <el-table-column prop="table_name" label="表名" min-width="180" show-overflow-tooltip />
            <el-table-column prop="column_name" label="字段" width="120" show-overflow-tooltip />
            <el-table-column label="严重程度" width="90">
              <template #default="{ row }">
                <el-tag :type="sevTag(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="error_cnt" label="异常数" width="80" align="center" />
            <el-table-column label="异常率" width="90" align="center">
              <template #default="{ row }">
                <span v-if="row.error_rate != null">
                  {{ (row.error_rate * 100).toFixed(2) }}%
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="assigned_to" label="分派人" width="100" />
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button v-perms="'asset.quality.rule.execute'" size="small" @click="openAssignDialog(row)">分派</el-button>
                <el-dropdown class="ml4" @command="(cmd: string) => recheckFinding(row, cmd)">
                  <el-button v-perms="'asset.quality.rule.execute'" size="small">
                    复核<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="confirmed">确认有效</el-dropdown-item>
                      <el-dropdown-item command="fixed">已修复</el-dropdown-item>
                      <el-dropdown-item command="ignored">忽略</el-dropdown-item>
                      <el-dropdown-item command="rechecked">已复核</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button v-perms="'asset.quality.rule.execute'" size="small" type="info" class="ml4" @click="openFindingStatusDialog(row)">
                  编辑状态
                </el-button>
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
          <el-table v-loading="recordsLoading" :data="records" stripe size="small">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="task_id" label="任务ID" width="80" />
            <el-table-column label="业务系统" width="180">
              <template #default="{ row }">
                {{ row.system_name_cn || systemNameMap[row.system_code] || row.system_code || '-' }}
                <small class="system-code-inline">{{ row.system_code }}</small>
              </template>
            </el-table-column>
            <el-table-column prop="started_at" label="开始时间" width="170" />
            <el-table-column prop="total_rules" label="规则数" width="80" align="center" />
            <el-table-column prop="total_findings" label="发现问题" width="100" align="center" />
            <el-table-column prop="total_records" label="扫描记录" width="100" align="center" />
            <el-table-column prop="error_records" label="异常记录" width="100" align="center" />
            <el-table-column label="通过率" width="100" align="center">
              <template #default="{ row }">
                <span v-if="row.pass_rate != null" :class="passRateClass(row.pass_rate)">
                  {{ formatPercent(row.pass_rate) }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === 'success' ? 'success' : row.status === 'running' ? 'warning' : 'danger'"
                  size="small"
                >
                  {{ runStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="failed_reason" label="失败原因" min-width="150" show-overflow-tooltip />
          </el-table>
          <el-pagination
            v-model:current-page="recordsPage"
            class="mt15"
            :page-size="recordsPageSize"
            :total="recordsTotal"
            layout="total, prev, pager, next"
            @current-change="loadRecords"
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
            <ReStatCard label="SQL 规则数" :value="metrics.sql_rules" tone="accent" />
            <ReStatCard label="问题总数" :value="summary.total_findings" tone="danger" />
            <ReStatCard label="通过率" :value="formatPercent(metrics.pass_rate)" :tone="passRateTone(metrics.pass_rate)" />
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
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import ReChart from "@/components/ReChart/index.vue";
import { computed, ref, reactive, onMounted } from "vue";

import { http } from "@/utils/http";
import {
  getQualitySummary,
  getQualityFindings,
  getQualityCheckRuns,
  runQualityCheck,
  listSystems,
  type QualitySummary
} from "@/api/asset";
import { ElMessage, ElMessageBox } from "element-plus";
import AlertIcon from "~icons/ri/alarm-warning-line";
import CheckIcon from "~icons/ri/checkbox-circle-line";
import ErrorIcon from "~icons/ri/error-warning-line";
import InfoIcon from "~icons/ri/information-line";
import IssueIcon from "~icons/ri/file-warning-line";
import QualityIcon from "~icons/ri/shield-check-line";
import WarningIcon from "~icons/ri/alert-line";

const systemNameMap = reactive<Record<string, string>>({});

async function loadSystemNames() {
  try {
    const res = await listSystems();
    for (const item of res.data || []) systemNameMap[item.system_code] = item.system_name_cn;
  } catch {
    // Technical codes remain a safe fallback if the catalog endpoint is unavailable.
  }
}

// ============================================================
// Types
// ============================================================
interface SystemSummaryItem {
  system_code: string;
  system_name_cn?: string;
  total_findings: number;
  open_count: number;
  resolved_count: number;
  critical_count: number;
}

interface RuleItem {
  id: number;
  rule_code: string;
  rule_name: string;
  rule_category: string;
  check_scope: string;
  constraint_level: string;
  business_domain: string;
  execution_mode: string;
  target_table: string;
  target_field: string;
  check_sql: string;
  description: string;
  enabled: boolean;
}

interface RuleCreateForm {
  rule_code: string;
  rule_name: string;
  rule_category: string;
  check_scope: string;
  constraint_level: string;
  business_domain: string;
  execution_mode: string;
  target_table: string;
  target_field: string;
  check_sql: string;
  description: string;
  enabled: boolean;
}

interface CheckRunItem {
  id: number;
  task_id: string;
  system_code: string;
  system_name_cn?: string;
  started_at: string;
  triggered_by: string;
  total_rules: number;
  total_findings: number;
  total_records: number;
  error_records: number;
  pass_rate: number | null;
  status: string;
  failed_reason: string;
}

interface FindingItem {
  id: number;
  rule_code: string;
  table_name: string;
  column_name: string;
  severity: string;
  status: string;
  error_cnt: number;
  error_rate: number | null;
  assigned_to: string;
  sample_data: any;
}

interface MetricsData {
  total_rules: number;
  sql_rules: number;
  pass_rate: number | null;
  rule_categories: { category: string; count: number }[];
  top_tables: { table: string; count: number }[];
}

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
    .catch(() => {});
}

function loadSystemSummary() {
  http
    .get<any, any>("/api/v1/quality/summary/by-system")
    .then((d: any) => {
      systemSummary.value = d.data || [];
    })
    .catch(() => {});
}

function loadMetrics() {
  return http
    .get<any, any>("/api/v1/quality/metrics", { params: { system_code: "DATA_CENTER" } })
    .then((d: any) => {
      metrics.value = d.data || { total_rules: 0, sql_rules: 0, pass_rate: null, rule_categories: [], top_tables: [] };
    })
    .catch(() => {});
}

function filterBySystem(row: SystemSummaryItem) {
  filters.keyword = row.system_code;
  activeTab.value = "findings";
  loadFindings(1);
}

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
  enabled: undefined as boolean | undefined
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

type TagType = "primary" | "success" | "warning" | "danger" | "info";

function ruleCategoryTag(cat: string): TagType {
  const m: Record<string, TagType> = {
    UNIQUE: "danger",
    COMPLETE: "warning",
    STANDARD: "primary",
    RELATION: "info",
    ACCURACY: "success"
  };
  return m[cat] || "info";
}

function ruleCategoryLabel(cat: string): string {
  const m: Record<string, string> = {
    UNIQUE: "唯一性",
    COMPLETE: "完整性",
    STANDARD: "规范性",
    RELATION: "关联性",
    ACCURACY: "准确性"
  };
  return m[cat] || cat;
}

function checkScopeLabel(scope: string): string {
  const m: Record<string, string> = {
    TABLE_INNER: "表内",
    TABLE_RELATION: "表间",
    SYSTEM_CROSS: "跨系统",
    BUSINESS_LOGIC: "业务逻辑"
  };
  return m[scope] || scope || "-";
}

function constraintLevelLabel(level: string): string {
  const m: Record<string, string> = {
    HARD: "硬约束",
    SOFT: "软约束",
    WARN: "提醒",
    INFO: "信息"
  };
  return m[level] || level || "-";
}

function formatPercent(value: number | null | undefined): string {
  return value == null ? "-" : `${Number(value).toFixed(1)}%`;
}

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

  http
    .get<any, any>("/api/v1/quality/rules", { params })
    .then((d: any) => {
      rules.value = d.data.items || [];
      rulesTotal.value = d.data.total || 0;
    })
    .finally(() => {
      rulesLoading.value = false;
    });
}

async function autoGenerateRules() {
  autoGenerating.value = true;
  try {
    const res = await http.post<any, any>("/api/v1/quality/rules/auto-generate", {
      data: { limit: 100 }
    });
    const data = res.data || {};
    ElMessage.success(`已生成 ${data.created || 0} 条建议，跳过 ${data.skipped || 0} 条重复规则`);
    loadRules(1);
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || "规则建议生成失败");
  } finally {
    autoGenerating.value = false;
  }
}

function resetRuleFilters() {
  ruleFilters.rule_category = "";
  ruleFilters.check_scope = "";
  ruleFilters.constraint_level = "";
  ruleFilters.enabled = undefined;
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
  if (editingRuleId.value) {
    http
      .patch<any, any>(`/api/v1/quality/rules/${editingRuleId.value}`, { data: payload })
      .then(() => {
        ElMessage.success("规则已更新");
        ruleDialogVisible.value = false;
        loadRules();
      })
      .catch(() => {});
  } else {
    http
      .post<any, any>("/api/v1/quality/rules", { data: payload })
      .then(() => {
        ElMessage.success("规则已创建");
        ruleDialogVisible.value = false;
        loadRules();
      })
      .catch(() => {});
  }
}

function toggleRuleEnabled(row: RuleItem) {
  const newEnabled = !row.enabled;
  http
    .post<any, any>(`/api/v1/quality/rules/${row.id}/enable?enabled=${newEnabled}`)
    .then(() => {
      ElMessage.success(`已${newEnabled ? '启用' : '停用'}`);
      loadRules();
    })
    .catch(() => {});
}

function validateRuleSql(row: RuleItem) {
  http
    .post<any, any>(`/api/v1/quality/rules/${row.id}/validate-sql`)
    .then((d: any) => {
      sqlValidateResult.value = d.data;
      sqlValidateVisible.value = true;
    })
    .catch(() => {
      ElMessage.error("SQL 校验失败");
    });
}

function deleteRule(row: RuleItem) {
  ElMessageBox.confirm(`确定删除规则 "${row.rule_code}"？`, "删除规则", {
    confirmButtonText: "删除",
    cancelButtonText: "取消",
    type: "warning"
  })
    .then(() => {
      http
        .delete<any, any>(`/api/v1/quality/rules/${row.id}`)
        .then(() => {
          ElMessage.success("已删除");
          loadRules();
        })
        .catch(() => {});
    })
    .catch(() => {});
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
    .finally(() => {
      tasksLoading.value = false;
    });
}

function runStatusLabel(s: string): string {
  const m: Record<string, string> = {
    success: "成功",
    failed: "失败",
    running: "运行中",
    pending: "待执行"
  };
  return m[s] || s;
}

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
  status: "",
  keyword: "",
  run_id: undefined as number | undefined
});

const assignDialogVisible = ref(false);
const assignFindingId = ref<number | null>(null);
const assignForm = reactive({ assigned_to: "", note: "" });

const findingStatusDialogVisible = ref(false);
const findingStatusFindingId = ref<number | null>(null);
const findingStatusForm = reactive({ status: "", note: "" });

function sevTag(s: string | null): TagType {
  const m: Record<string, TagType> = {
    critical: "danger",
    major: "warning",
    minor: "primary",
    info: "info"
  };
  return m[s ?? ""] || "info";
}

function severityLabel(s: string | null): string {
  const m: Record<string, string> = {
    critical: "严重",
    major: "重要",
    minor: "一般",
    info: "信息"
  };
  return m[s ?? ""] || s || "";
}

function statusLabel(s: string | null): string {
  const m: Record<string, string> = {
    open: "待处理",
    assigned: "已分派",
    confirmed: "已确认",
    fixed: "已修复",
    rechecked: "已复核",
    acknowledged: "已确认",
    resolved: "已解决",
    ignored: "已忽略",
    rule_error: "规则错误",
  };
  return m[s ?? ""] || s || "";
}

function statusTag(s: string | null): TagType {
  const m: Record<string, TagType> = {
    open: "danger",
    assigned: "warning",
    confirmed: "primary",
    fixed: "success",
    rechecked: "success",
    acknowledged: "warning",
    resolved: "success",
    ignored: "info",
    rule_error: "danger",
  };
  return m[s ?? ""] || "info";
}

function formatSampleData(data: any): string {
  if (!data) return "无";
  try {
    return typeof data === "string" ? data : JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

function ensureRunOptions() {
  if (findingRunOptions.value.length) return;
  getQualityCheckRuns({ page: 1, page_size: 50 })
    .then(({ data }) => {
      findingRunOptions.value = (data.items || []) as any;
    })
    .catch(() => {
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
    run_id: filters.run_id || undefined
  })
    .then(({ data }) => {
      findings.value = data.items as any;
      findingsTotal.value = data.total;
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
  http
    .post<any, any>(`/api/v1/quality/findings/${assignFindingId.value}/assign`, {
      data: { assigned_to: assignForm.assigned_to, note: assignForm.note }
    })
    .then(() => {
      ElMessage.success("已分派");
      assignDialogVisible.value = false;
      loadFindings();
    })
    .catch(() => {});
}

function recheckFinding(row: FindingItem, status: string) {
  http
    .post<any, any>(`/api/v1/quality/findings/${row.id}/recheck?status=${status}`)
    .then(() => {
      ElMessage.success("复核完成");
      loadFindings();
    })
    .catch(() => {});
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
  http
    .patch<any, any>(`/api/v1/quality/findings/${findingStatusFindingId.value}`, { data: body })
    .then(() => {
      ElMessage.success("状态已更新");
      findingStatusDialogVisible.value = false;
      loadFindings();
    })
    .catch(() => {});
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
    .finally(() => {
      recordsLoading.value = false;
    });
}

// ============================================================
// Tab 6: 质量看板
// ============================================================
const dashboardReady = ref(false);

function passRateTone(rate: number | null | undefined): "accent" | "warning" | "danger" {
  if (rate == null) return "warning";
  if (rate >= 95) return "accent";
  if (rate >= 80) return "warning";
  return "danger";
}

function passRateClass(rate: number | null | undefined): string {
  return `metric-${passRateTone(rate)}`;
}

const ruleCategoryChartOption = computed(() => {
  const categories = metrics.value.rule_categories || [];
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
        data: categories.map(c => ({
          name: ruleCategoryLabel(c.category),
          value: c.count
        })),
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
.system-code-inline { display: block; color: var(--text-secondary); font-size: 11px; }
.quality-stat-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 16px;
}
.quality-metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
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
