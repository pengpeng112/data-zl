<template>
  <div>
    <h2 class="page-title">数据质量</h2>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- ============================================================ -->
      <!-- Tab 1: 质量总览 -->
      <!-- ============================================================ -->
      <el-tab-pane label="质量总览" name="overview" lazy>
        <el-row :gutter="16" class="mb20">
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-num">{{ summary.total_findings }}</div>
              <div class="stat-label">总问题数</div>
            </el-card>
          </el-col>
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card stat-open">
              <div class="stat-num">{{ summary.open_count }}</div>
              <div class="stat-label">待处理</div>
            </el-card>
          </el-col>
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card stat-resolved">
              <div class="stat-num">{{ summary.resolved_count }}</div>
              <div class="stat-label">已解决</div>
            </el-card>
          </el-col>
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card stat-critical">
              <div class="stat-num">{{ summary.critical_count }}</div>
              <div class="stat-label">严重</div>
            </el-card>
          </el-col>
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card stat-major">
              <div class="stat-num">{{ summary.major_count }}</div>
              <div class="stat-label">重要</div>
            </el-card>
          </el-col>
          <el-col :span="4">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-num">{{ summary.minor_count }}</div>
              <div class="stat-label">一般</div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16" class="mb20">
          <el-col :span="8">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-num" style="color: #409eff">{{ metrics.total_rules }}</div>
              <div class="stat-label">规则总数</div>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-num" style="color: #67c23a">{{ metrics.sql_rules }}</div>
              <div class="stat-label">SQL 规则数</div>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-num" style="color: #e6a23c">
                {{ formatPercent(metrics.pass_rate) }}
              </div>
              <div class="stat-label">通过率</div>
            </el-card>
          </el-col>
        </el-row>

        <el-card class="mb20">
          <template #header>
            <span>按系统质量概览</span>
          </template>
          <el-table
            :data="systemSummary"
            stripe
            size="small"
            @row-click="filterBySystem"
            style="cursor: pointer"
          >
            <el-table-column prop="system_code" label="系统编码" width="160" />
            <el-table-column prop="total_findings" label="问题总数" width="100" align="center" />
            <el-table-column prop="open_count" label="待处理" width="100" align="center" />
            <el-table-column prop="resolved_count" label="已解决" width="100" align="center" />
            <el-table-column prop="critical_count" label="严重问题数" width="120" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.critical_count > 0 ? '#f56c6c' : '' }">
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
            <el-button type="primary" size="small" style="margin-left: 12px" @click="openRuleDialog()">
              新增规则
            </el-button>
          </template>

          <el-form :inline="true">
            <el-form-item label="规则分类">
              <el-select
                v-model="ruleFilters.rule_category"
                placeholder="全部分类"
                clearable
                style="width: 130px"
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
                style="width: 130px"
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
                style="width: 130px"
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
                style="width: 110px"
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
                <el-button size="small" @click="openRuleDialog(row)">编辑</el-button>
                <el-button
                  size="small"
                  :type="row.enabled ? 'warning' : 'success'"
                  @click="toggleRuleEnabled(row)"
                >
                  {{ row.enabled ? '停用' : '启用' }}
                </el-button>
                <el-button
                  v-if="row.check_sql"
                  size="small"
                  type="info"
                  @click="validateRuleSql(row)"
                >
                  校验SQL
                </el-button>
                <el-button size="small" type="danger" @click="deleteRule(row)">删除</el-button>
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
              <el-select v-model="ruleForm.rule_category" style="width: 100%">
                <el-option label="唯一性" value="UNIQUE" />
                <el-option label="完整性" value="COMPLETE" />
                <el-option label="规范性" value="STANDARD" />
                <el-option label="关联性" value="RELATION" />
                <el-option label="准确性" value="ACCURACY" />
              </el-select>
            </el-form-item>
            <el-form-item label="检查范围">
              <el-select v-model="ruleForm.check_scope" style="width: 100%">
                <el-option label="表内" value="TABLE_INNER" />
                <el-option label="表间" value="TABLE_RELATION" />
                <el-option label="跨系统" value="SYSTEM_CROSS" />
                <el-option label="业务逻辑" value="BUSINESS_LOGIC" />
              </el-select>
            </el-form-item>
            <el-form-item label="约束级别">
              <el-select v-model="ruleForm.constraint_level" style="width: 100%">
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
              <el-select v-model="ruleForm.execution_mode" style="width: 100%">
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
            <el-button type="primary" @click="saveRule">保存</el-button>
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
          <el-button
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
                <span :style="{ color: (checkResult.pass_rate ?? 0) >= 95 ? '#67c23a' : '#f56c6c' }">
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
          <el-table v-loading="tasksLoading" :data="checkRuns" stripe size="small">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="started_at" label="开始时间" width="170" />
            <el-table-column prop="triggered_by" label="触发方式" width="80" />
            <el-table-column prop="total_rules" label="规则数" width="80" align="center" />
            <el-table-column prop="total_findings" label="发现问题" width="100" align="center" />
            <el-table-column prop="total_records" label="扫描记录" width="100" align="center" />
            <el-table-column prop="error_records" label="异常记录" width="100" align="center" />
            <el-table-column label="通过率" width="100" align="center">
              <template #default="{ row }">
                <span v-if="row.pass_rate != null" :style="{ color: row.pass_rate >= 95 ? '#67c23a' : '#f56c6c' }">
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
            <el-form-item label="规则编码">
              <el-input
                v-model="filters.rule_code"
                placeholder="规则编码"
                clearable
                style="width: 160px"
                @clear="loadFindings(1)"
              />
            </el-form-item>
            <el-form-item label="严重程度">
              <el-select
                v-model="filters.severity"
                placeholder="全部"
                clearable
                style="width: 110px"
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
                style="width: 110px"
                @change="loadFindings(1)"
              >
                <el-option label="待处理" value="open" />
                <el-option label="已确认" value="acknowledged" />
                <el-option label="已解决" value="resolved" />
                <el-option label="已忽略" value="ignored" />
              </el-select>
            </el-form-item>
            <el-form-item label="整改状态">
              <el-select
                v-model="filters.rectification_status"
                placeholder="全部"
                clearable
                style="width: 130px"
                @change="loadFindings(1)"
              >
                <el-option label="待整改" value="pending" />
                <el-option label="整改中" value="in_progress" />
                <el-option label="已完成" value="done" />
                <el-option label="无需整改" value="not_needed" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="filters.keyword"
                placeholder="搜索表名/系统"
                clearable
                style="width: 200px"
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
                <div style="padding: 8px 20px">
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
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="整改状态" width="100">
              <template #default="{ row }">
                <el-tag :type="rectificationTag(row.rectification_status)" size="small">
                  {{ rectificationLabel(row.rectification_status) }}
                </el-tag>
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
                <el-button size="small" @click="openAssignDialog(row)">分派</el-button>
                <el-dropdown style="margin-left: 4px" @command="(cmd: string) => recheckFinding(row, cmd)">
                  <el-button size="small">
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
                <el-button size="small" type="info" style="margin-left: 4px" @click="openFindingStatusDialog(row)">
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
            <el-button type="primary" @click="submitAssign">确定</el-button>
          </template>
        </el-dialog>

        <!-- 编辑状态弹窗 -->
        <el-dialog v-model="findingStatusDialogVisible" title="编辑问题状态" width="400px">
          <el-form>
            <el-form-item label="状态">
              <el-select v-model="findingStatusForm.status" style="width: 100%">
                <el-option label="待处理" value="open" />
                <el-option label="已确认" value="acknowledged" />
                <el-option label="已解决" value="resolved" />
                <el-option label="已忽略" value="ignored" />
              </el-select>
            </el-form-item>
            <el-form-item label="整改状态">
              <el-select v-model="findingStatusForm.rectification_status" style="width: 100%">
                <el-option label="待整改" value="pending" />
                <el-option label="整改中" value="in_progress" />
                <el-option label="已完成" value="done" />
                <el-option label="无需整改" value="not_needed" />
              </el-select>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="findingStatusForm.note" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="findingStatusDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="submitFindingStatus">保存</el-button>
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
            <el-table-column prop="system_code" label="系统编码" width="140" />
            <el-table-column prop="started_at" label="开始时间" width="170" />
            <el-table-column prop="total_rules" label="规则数" width="80" align="center" />
            <el-table-column prop="total_findings" label="发现问题" width="100" align="center" />
            <el-table-column prop="total_records" label="扫描记录" width="100" align="center" />
            <el-table-column prop="error_records" label="异常记录" width="100" align="center" />
            <el-table-column label="通过率" width="100" align="center">
              <template #default="{ row }">
                <span v-if="row.pass_rate != null" :style="{ color: passRateColor(row.pass_rate) }">
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
          <el-row :gutter="16" class="mb20">
            <el-col :span="6">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-num" style="color: #409eff">{{ metrics.total_rules }}</div>
                <div class="stat-label">总规则数</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-num" style="color: #67c23a">{{ metrics.sql_rules }}</div>
                <div class="stat-label">启用规则数</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-num" style="color: #f56c6c">{{ summary.total_findings }}</div>
                <div class="stat-label">问题总数</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-num" style="color: #e6a23c">
                  {{ formatPercent(metrics.pass_rate) }}
                </div>
                <div class="stat-label">通过率</div>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-card>
                <template #header>
                  <span>规则分类分布</span>
                  <el-button size="small" style="float: right" @click="refreshDashboard">刷新</el-button>
                </template>
                <div ref="pieChartRef" style="height: 360px" />
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card>
                <template #header>
                  <span>问题 Top 5 表</span>
                </template>
                <div ref="barChartRef" style="height: 360px" />
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, nextTick } from "vue";
import * as echarts from "echarts";
import { http } from "@/utils/http";
import {
  getQualitySummary,
  getQualityFindings,
  getQualityCheckRuns,
  runQualityCheck,
  type QualitySummary
} from "@/api/asset";
import { ElMessage } from "element-plus";

// ============================================================
// Types
// ============================================================
interface SystemSummaryItem {
  system_code: string;
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
  rectification_status: string;
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
  if (!confirm(`确定删除规则 "${row.rule_code}"？`)) return;
  http
    .delete<any, any>(`/api/v1/quality/rules/${row.id}`)
    .then(() => {
      ElMessage.success("已删除");
      loadRules();
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
const filters = reactive({
  rule_code: "",
  severity: "",
  status: "",
  rectification_status: "",
  keyword: ""
});

const assignDialogVisible = ref(false);
const assignFindingId = ref<number | null>(null);
const assignForm = reactive({ assigned_to: "", note: "" });

const findingStatusDialogVisible = ref(false);
const findingStatusFindingId = ref<number | null>(null);
const findingStatusForm = reactive({ status: "", rectification_status: "", note: "" });

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
    acknowledged: "已确认",
    resolved: "已解决",
    ignored: "已忽略"
  };
  return m[s ?? ""] || s || "";
}

function statusTag(s: string | null): TagType {
  const m: Record<string, TagType> = {
    open: "danger",
    acknowledged: "warning",
    resolved: "success",
    ignored: "info"
  };
  return m[s ?? ""] || "info";
}

function rectificationLabel(s: string | null): string {
  const m: Record<string, string> = {
    pending: "待整改",
    in_progress: "整改中",
    done: "已完成",
    not_needed: "无需整改"
  };
  return m[s ?? ""] || s || "";
}

function rectificationTag(s: string | null): TagType {
  const m: Record<string, TagType> = {
    pending: "danger",
    in_progress: "warning",
    done: "success",
    not_needed: "info"
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

function loadFindings(page?: number) {
  if (page) findingsPage.value = page;
  fLoading.value = true;
  getQualityFindings({
    page: findingsPage.value,
    page_size: findingsPageSize.value,
    severity: filters.severity || undefined,
    status: filters.status || undefined,
    rule_code: filters.rule_code || undefined,
    keyword: filters.keyword || undefined
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
  findingStatusForm.rectification_status = row.rectification_status || "";
  findingStatusForm.note = "";
  findingStatusDialogVisible.value = true;
}

function submitFindingStatus() {
  if (!findingStatusFindingId.value) return;
  const body: any = {
    status: findingStatusForm.status,
    rectification_status: findingStatusForm.rectification_status,
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

function passRateColor(rate: number): string {
  if (rate >= 95) return "#67c23a";
  if (rate >= 80) return "#e6a23c";
  return "#f56c6c";
}

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
const pieChartRef = ref<HTMLElement>();
const barChartRef = ref<HTMLElement>();

let pieChart: echarts.ECharts | null = null;
let barChart: echarts.ECharts | null = null;

function initPieChart() {
  if (!pieChartRef.value) return;
  if (pieChart) pieChart.dispose();
  pieChart = echarts.init(pieChartRef.value);
  const cats = metrics.value.rule_categories || [];
  pieChart.setOption({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { orient: "vertical", left: 10, top: 20 },
    series: [
      {
        type: "pie",
        radius: ["40%", "70%"],
        center: ["55%", "55%"],
        data: cats.map(c => ({
          name: ruleCategoryLabel(c.category),
          value: c.count
        })),
        label: { show: true, formatter: "{b}: {c}" },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: "rgba(0,0,0,0.5)" }
        }
      }
    ]
  });
}

function initBarChart() {
  if (!barChartRef.value) return;
  if (barChart) barChart.dispose();
  barChart = echarts.init(barChartRef.value);
  const tables = (metrics.value.top_tables || []).slice(0, 5);
  barChart.setOption({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 120 },
    xAxis: { type: "value", name: "问题数" },
    yAxis: {
      type: "category",
      data: tables.map(t => t.table).reverse(),
      axisLabel: { width: 100, overflow: "truncate" }
    },
    series: [
      {
        type: "bar",
        data: tables.map(t => t.count).reverse(),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: "#f56c6c" },
            { offset: 1, color: "#e6a23c" }
          ])
        }
      }
    ]
  });
}

async function loadDashboardData() {
  loadSummary();
  loadMetrics();
}

async function initDashboard() {
  dashboardReady.value = true;
  await loadDashboardData();
  await nextTick();
  initPieChart();
  initBarChart();
}

function refreshDashboard() {
  loadMetrics().then(() => {
    initPieChart();
    initBarChart();
  });
}

function disposeCharts() {
  if (pieChart) {
    pieChart.dispose();
    pieChart = null;
  }
  if (barChart) {
    barChart.dispose();
    barChart = null;
  }
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
  loadSummary();
  loadSystemSummary();
  loadMetrics();
});

// Clean up charts when leaving the component
onBeforeUnmount(() => {
  disposeCharts();
});
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
.mt10 {
  margin-top: 10px;
}
.stat-card {
  text-align: center;
}
.stat-num {
  font-size: 28px;
  font-weight: 700;
}
.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
.stat-open .stat-num {
  color: #f56c6c;
}
.stat-resolved .stat-num {
  color: #67c23a;
}
.stat-critical .stat-num {
  color: #f56c6c;
}
.stat-major .stat-num {
  color: #e6a23c;
}
.sample-json {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
