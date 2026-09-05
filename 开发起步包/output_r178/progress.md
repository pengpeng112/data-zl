# 178 批执行进度（progress.md）

计划：`开发起步包/178_177收口后可执行改进一次性执行计划.md`（v1.1）
基线 HEAD=96ed027（与 177 收口一致，未 checkout/stash）。

## R0 开工自检 ✅

- 快照：`output_r178/workspace_snapshot.txt`（HEAD、脏文件、他人域 13 文件 git hash-object 基线）。
- 他人域 13 文件哈希与 177 R0 基线**集合完全一致**。
- 端口 15432 被 PID 36052 占用（外部转发，未杀；隔离库自建 15532 隧道，PID 39464）。
- 无残留 python/pytest 进程。
- 用户两问（004066 表现 / 150 三选一）：AskUserQuestion 提问一次**未获答复** → R5 CDMS 整批 SKIP、G9 记「仍开」，不空转等待。
- 未连业务源库；未 checkout/stash。

## R1 176 夜跑只读核验 ✅（结论 FAIL，呈报不调阈值）

- 通道：ssh 8.83 → docker exec data-asset-api python（SELECT only，凭据不落盘不回显）。
- 容器 healthy；`APP_IDENTITY_CB_MAX_UPDATE=150`（F-1 在产）、`APP_IDENTITY_CB_MAX_NEW=130`（未动）。
- 最新夜跑 **RUN-b3324c242e78（2026-09-04 02:00）failed，CB=True，维度 max_change_ratio**（09-03 为 max_update；F-1 已放行 update 维度 110<150，比例维度 110/110=1.0>0.3 仍熔断）。
- 三个子任务（签名/职称/科室）全部 skipped（main_account_sync_not_successful 一刀切）；空签名账号未回补。
- 归因：生产仍是 F-2 前语义，110 托管圈例行 resync 计入 update。根治=G3（发布 F-2）。未改任何 env/阈值/镜像。
- 详见 `nightly_n1.md`。55 未动（按计划留到 R7）。

## R2 C6 GraphToolbar 单向数据流 ✅

- 前置：两文件 `git diff` 干净 → 按计划必做。
- `GraphToolbar.vue`：`defineEmits` 增补 `update:locate` / `update:filters`；13 处 props v-model 全改受控（locate.table/depth/direction + filters.system_code/source_code/schema/domain/validation_status/confidence/limit/include_candidates/include_dependencies/show_review_layer），逐字段展开 payload，无 `{ field: val }` 字面键；`advancedVisible` 本地 ref 保持 v-model。
- `changeDisplay` 改为 `emit("update:filters", { ...props.filters, layout_mode })`，script 内 props 赋值归零。
- `graph/index.vue`：只加 `@update:filters` / `@update:locate` 监听 + 两个 `Object.assign` 处理函数（保留 reactive 引用），不改布局算法与 169 错误态工具栏逻辑。
- 测试：新增 `tests/plan178R2.test.ts`（5 用例：v-model 禁令、props 赋值禁令、父组件接线、changeDisplay、逐字段 payload）。
- 批内 vitest：plan178R2 + graphPage + graphPageMount + plan169G2/G3/G4 + graphNeo4jP0 = **7 文件 47/47 绿**（graphNeo4jP0 的「搜索并聚焦」「高级筛选」`command="force"` 锁未动、未适配）。
- `pnpm exec eslint src/views/asset/components/GraphToolbar.vue`：`vue/no-mutating-props` **0 条**（其余 148 条为该文件既有 prettier 风格债，173 P3-4 明确不做全仓 prettier，未触碰）。

## R3 C7 alembic 空库自建 schema ✅

- `backend/alembic/env.py`：新增 `_ensure_asset_schema`（`CREATE SCHEMA IF NOT EXISTS asset` + commit）；online 拿到 connection 后先建 schema 再 configure/run_migrations；offline 在 run_migrations 前 `context.execute(text(...))` 同一 DDL（离线脚本含该句）。
- `backend/tests/conftest.py`：仅把 `"alembic_env"` 追加进 `_PURE_LOGIC_SUBDIRS`。
- 新增 `tests/alembic_env/conftest.py`（plan144 模式哨兵）+ `test_schema_ddl.py`（4 用例：DDL 幂等、online 先建 schema、offline 先发 DDL、历史 revision 零触碰）。
- `pytest tests/alembic_env -q`：**4/4 绿**（纯逻辑不连库）。
- 隔离库（8.83 data_asset_test，本地 15532 隧道，显式 URL）：`alembic upgrade head` **no-op 通过**（无 Running upgrade 行，IF NOT EXISTS 在已有 schema 上不炸）；`alembic current` 仍 `d5e6f7a8b9c0 (head)`。
- 无空 postgres：从零 upgrade 实验按计划跳过（不记失败）；未 drop 任何 schema；未新建 8.83 业务库。

## R4 L1 台账↔探查互链 ✅（①②③全部落地，无整项 WARN）

- 新增纯函数 `frontend/src/views/quality/sourceRef.ts`：`parseProbeFindingRef`（^asset_probe_findings:(\d+)$）、`probeFindingLink`（/probe-findings?finding_id=）、`probeFindingSourceRef`、`findingIdFromRouteQuery`（缺省/非数字→null）。
- ① 正向：`issue-detail/index.vue` 与 `observations/index.vue` 的来源列改 scoped-slot 读 `row.source_record_ref`，命中渲染 el-link 跳 `/probe-findings?finding_id={id}`，未命中纯文本（两页各只改一列，未超限）。
- ② 探查页消费：`probe-findings/index.vue` 补 `useRoute` + `watch(route.query.finding_id)` + onMounted 列表加载后消费；找到→打开既有详情抽屉；未找到→同一 id 只 warning 一次，不清筛选盲扫。
- ③ 反查：选中行后 `listQualityObservations({source_kind:'probe_finding',page:1,page_size:100})` 客户端匹配 `asset_probe_findings:{id}` 取 issue_id（total>100 补拉 page=2 一次）；命中显示「查看质量台账」按钮跳 `/quality/issues/{issue_id}`；未命中/403/网络失败一律隐藏按钮不打错误态（console.warn 级）。未新增后端、未改 API 签名、未动 transition 流转。
- 测试：新增 `tests/plan178R4.test.ts`（6 用例）+ 验收回归 `plan174QualityLedger` + `plan166StageD2` = **3 文件 22/22 绿**。

## R5 CDMS ⛔ SKIP

用户未选 004066 表现（开工提问未获答复）。G7 保持开放；未写 KESHID/未改 FPWD/未补权限。

## R6 等待域 ✅

`output_r178/wait_domain.md`：G1–G17 全 17 项逐条誊写并标注本轮未动；N1 FAIL 结论佐证 G3；150/004066 未答复记「仍开」；新增等待：C6/C7/L1 代码完成待 G13 提交与下次发布。

## R7 门禁与文档 ✅

- 后端专项：`pytest tests/alembic_env tests/test_r177_fixes.py tests/test_identity_cb_resync_f2.py -q` = **17 passed / 0 failed**（隔离库显式 URL）。
- 隔离库 alembic：upgrade head no-op + current=d5e6f7a8b9c0（R3 已跑，R7 引用）。
- 后端全量 `pytest tests/ -q`（隔离库）：见执行报告 §4（本文件末尾补记）。
- 前端：typecheck（tsc+vue-tsc）exit 0；vitest 全量 **44 文件 278/278**（177 基线 267 + plan178R2 5 + plan178R4 6）；build 三预算绿（657.2/700、404.5/430、103.5/110 KB gzip）。
- 他人域 13 文件哈希终检 = R0 基线（13/13 一致）。
- Git：零 commit/push/tag（用户未点名授权）。
- 文档：178 §8 日志一行、55 追加 📌 一条、README 目录更新记录一行 + 178 行状态更新、执行报告 + _结果.json、本文件与 exceptions/nightly/wait_domain 齐备。

## 附：后端全量 pytest 终值

`pytest tests/ -q`（隔离库 data_asset_test）：**1419 passed / 1 skipped / 0 failed**，2053.39s（34:13）。177 基线 1415P/1S/0F + 本批新增 tests/alembic_env 4 用例 = 1419，无回归。
