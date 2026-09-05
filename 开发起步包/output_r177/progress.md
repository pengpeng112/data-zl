# 177 批执行台账（progress）

执行者：177 执行 AI（2026-09-03 晚单会话）
基线：HEAD=96ed027（171 收口）；隔离库 data_asset_test 经 15432 隧道（显式 URL）；生产容器 b866ffee（F-1 后）健康。

## R0 开工自检 — DONE

- 快照：`workspace_snapshot.txt`（SHA、git status/diff --stat、他人域 13 文件哈希基线）。
- 隧道：本地 15432 空闲自建（PID 36052）；无他人 pytest 进程；未 checkout/stash；未连业务源。
- 必读已读：AGENTS / README / 55 📌 / 177 全文 / 176 §4 / 173 问题清单 / 174 CDMS §1。
- 目录自检：README 与实际文件一致（173–177 在位；150 正文/脚本为 git D 属已登记幽灵条目）。

## R1 176 夜跑只读核验 — DEFERRED

2026-09-04 02:00 未到，按 177 批次序留待夜跑后补（查询口径见 177 R1：scheduler_runs 最新 02:00 行四指标 + 子任务 skipped 原因）。

## R2 173/171 缺陷修复 — DONE（C6 WARN 跳过）

| # | 修复 | 文件:位置 | 验证 |
|---|---|---|---|
| C1 | import170 重灌末尾 DO 块全量 setval（107 序列）+ last_value>=max(id) 硬校验（失败 RAISE） | `开发起步包/output_r170/import170.py`（token 块后） | 实跑重灌：12702 表/1329 关系/107 序列重置；ingest `POST /api/v1/queries/ingest` 200（修复前 500）；对账 behind=0、audit max(id)=194=last_value；r177 测试行已清 |
| C2 | 非 CANONICAL 分区返回 `row.system_code` 原值 + 真实 connection_count | `backend/app/services/asset_catalog.py` list_first_level_systems 第二循环 | 复现实验定位真实根因：**非 upper() 规范化覆盖了用户建库编码**（173 报告"只返回 CANONICAL"表述不精确——实际返回了 R177SYS 而非 r177sys，详情导航亦 404）；修复后混合编码可见+detail 200；`tests/test_r177_fixes.py` 2 用例 |
| C3 | 6 写按钮补 v-perms | probe-findings/index.vue（确认迁移=probe.finding.transition）、value-domains/index.vue（确认=value_domain.confirm）、dict/general/index.vue ×4（保存=dict.general.edit） | `tests/plan177R2.test.ts` 3 用例；存量锁 plan166StageD2 B3 计数 3→4 随库存更新（新按钮纳入保护，非弱化） |
| C4 | 新增 `edgeLabelText()`：字符串 label → label.formatter → from_columns 字符串；两处消费点改用 | `frontend/src/views/asset/components/RelationGraph.vue`（aggregate 聚合边 + materializeLayout SVG 边） | 根因链：RelationGraph 自身先经 graphNormalize（ECharts 风格 label 对象）再消费；`tests/plan177R2.test.ts` 2 用例 + 全量 267 tests |
| C5 | create 前置校验 `validate_recipe_tables`（422；空表仍合法草稿） | `backend/app/services/recipe_service.py`（新增共享 `extract_recipe_table_names`/`validate_recipe_tables`，generate_select_sql 复用提取）；`backend/app/api/v1/recipes.py` create_recipe | `tests/test_r177_fixes.py` 2 用例 |
| C6 | GraphToolbar props 突变改 emit | 未改 | **WARN 跳过**：父组件 graph/index.vue 传入自身响应式 filters/locate 对象并直接读取（共享对象设计），纯子组件改 emit 必破坏功能；父组件不在 R2 白名单。本地 computed 嫁接只灭 lint 不改数据流=假修，不做。（exceptions W-02） |

偏离记录：
- D-01：177 C3 建议 `dict.general.manage`，但该权限码不存在（后端/种子均无），同页既有写按钮统一 `dict.general.edit`——按 177 自身"同页怎么挂就怎么挂"规则采用 `dict.general.edit`。
- D-02：177 引用文件路径 `views/asset/graph/RelationGraph.vue` 有误，实际 `views/asset/components/RelationGraph.vue`；同 GraphToolbar。

## R3 身份线复核 — DONE（代码完成，生产未发布）

- **I1 复核**：`cdms_identity_adapter.py` diff = FFREE3 四处（模板常量/INSERT 列/建户 dict/align 幂等补齐 `NVL(FFREE3,' ')<> '1'`），与 172 §6 一致，additive、幂等。生产接入 = G1。
- **I2 复核**：`identity_login_sign_sync.py`（新增，模块注释明确 additive 只补缺 0/2/4、不删已有方式/默认；fail-closed；TARGET_MAX_ROWS=20000）+ `jhemr_identity_adapter.apply_login_sign_gaps`（FOR UPDATE 行锁 + 存在性复核 + 单事务）+ runner/audit/status/log 五处接线（子任务随主任务成败门控，比照签名/职称）。生产接 cron = G2。
- **I3 实现（F-2）**：`identity_sync_orchestrator.py`
  - `_compute_change_stats`：托管候选拆分——有 `modified_time`（HIS MODIFIEDTIME 增量命中）或存在性检查失败(None) → `update`（保守）；无增量标记且存在性检查成功 → `resync_unchanged` 单列（不计 max_update/change_ratio，仍受 max_candidates 约束）。
  - `check_thresholds`：max_update 语义注释更新；change_ratio 分子自然不含 resync。
  - 测试：`tests/test_identity_cb_resync_f2.py` 9 用例——110 人纯 resync 不熔断 ✓、110 人真实 update 仍熔断（阈值 100）✓、存在性检查失败回退旧口径 ✓、混合增量拆桶 ✓、ratio 排除 resync ✓、max_candidates 仍兜底 ✓、未托管候选不受影响 ✓。
- 门禁：`test_identity_sync + test_identity_sync_122_unit + identity_login_sign_sync + identity_cb_align + identity_cb_resync_f2` = **126 passed / 0 failed**。

## R4 门禁与文档 — DONE

- 后端全量 pytest：**1415 passed / 1 skipped / 0 failed**（1920s；171 基线 1341+174 生产批 1397 之后零新增失败，本批新增后端测试 13）。
- alembic current（隔离库，只读）：`d5e6f7a8b9c0 (head)`（与生产一致，只记录）。
- 前端：typecheck（tsc+vue-tsc）双过；vitest 267/267；build 主入口/图谱异步包/CSS gzip 预算三绿。
- 重灌：全量 pytest 后按 171 T2.5 惯例重灌基准数据（import170 现自带序列重置）：systems=26/tables=12702/relations=1329/value_domains=77/quality_rules=422/107 序列 behind=0。

## R5 CDMS 赋权 — SKIP

用户未选 004066「不行」表现（A 登录失败 / B 能登功能空白 / C 管理界面显示未赋权）。未写 KESHID、未改密码、未补赵慧权限。

## R6 等待域呈报包 — DONE

`wait_domain.md`（A1–A11 勾选表 + 165 六条 finding 明细 + 150 三选一 + 复核池数字 + G1–G17 快照）。

## R7 DoD 自检 — DONE

- 他人域 layout/captureMode 13 文件哈希终检=R0 基线一致（`workspace_snapshot.txt`）。
- progress.md 覆盖 R0–R7（R1 DEFERRED、R5 SKIP 均有原因）。
- 执行报告 + `_结果.json` + README 目录更新记录 + 55 📌 已写。
- 零越权：未发布/未 push/未写业务源/未 confirm 值域/未点探查终态/未改生产 env/cron/镜像。
