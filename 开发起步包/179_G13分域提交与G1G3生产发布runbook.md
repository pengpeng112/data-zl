> 类别：待办（授权后执行）
>
> 状态：**runbook v1.0（2026-09-05，待用户点名授权；未授权时本文档仅为预案，零 Git 零生产）**
>
> 上位入口：`55_系统未完成事项统一执行计划.md`；承接 `178_177收口后可执行改进_执行报告.md` §7 交接
>
> 覆盖等待域：G13（分域提交）+ G1（镜像重建持久化 FFREE3）+ G3（发布 F-2 + MAX_NEW 回落）；G2（生产接 jhemr_login_sign_sync 夜窗子任务）作为可选追加段

# 179 · G13 分域提交与 G1/G3 生产发布 runbook

## 0. 用途与授权门槛

- 本文是 178 收口后唯一建议的下一步执行预案。**执行任何一段都必须用户在本会话点名授权**（178 硬边界 5/6：未点名则零 Git 写、零生产发布）。
- 三段可独立授权：A=G13 只提交（不 push）；B=G1+G3 后端发布；C=前端 r178 原子切换。推荐顺序 A→B→C。
- 本文本身零 Git、零生产、零业务源连接。

## 1. 当前漂移盘点（2026-09-05 快照，发布动机）

| 项 | 工作区 | 生产（8.83） | 风险 |
|---|---|---|---|
| CDMS FFREE3 建户模板 | 有（172 热修） | 容器热修在、**镜像 r175 无** | 容器按现镜像重建即丢（G1 根因） |
| 177 C2–C5（系统 readback/六按钮 v-perms/图谱边标签/配方 create 422） | 有 | 无 | 已修缺陷不生效 |
| 176 F-2 熔断语义（例行 resync 不计 update/ratio） | 有+9 测试 | 无 | **N1 实证仍每夜熔断**（09-04 RUN-b3324c242e78，维度 max_change_ratio；签名/职称/科室三子任务连续被一刀切 skip） |
| 178 C6/C7/L1（GraphToolbar 单向流/alembic 自建 schema/台账↔探查互链） | 有+11 测试 | 无 | 不生效（互链用户可见收益未上线） |
| jhemr_login_sign_sync 夜窗子任务 | 代码+测试就绪 | cron 未接 | 登录/签名方式字段不回补（G2） |
| 生产迁移头 / env | — | `d5e6f7a8b9c0`；`MAX_UPDATE=150`、`MAX_NEW=130` | F-2 发布后两项均可回落（见 §4.6） |

## 2. A 段 · G13 分域提交方案（默认不 push）

### 2.1 提交组（10 组，按此序）

| # | commit message | 文件 | 备注 |
|---|---|---|---|
| 1 | `chore(hygiene): ignore one-shot work dirs` | `.gitignore` | 173 行已在；**建议顺带补** `backend/_r172_work/`、`backend/_r175_work/` 两行（现未被 ignore，check-ignore 实证） |
| 2 | `feat(174): quality governance ledger backend` | `app/api/v1/permissions.py`、`app/main.py`、`alembic/versions/d5e6f7a8b9c0_*.py`、`app/api/v1/quality_{issues,controls,observations}.py`、`app/models/quality_governance.py`、`app/services/quality_governance_{service,adapters}.py`、`app/scripts/`（seed）、`tests/test_quality_governance_{api,service}.py`、`tests/security_audit/test_fine_grained_write_permissions.py` | 迁移文件**必须与 main.py 路由注册同组**，保证任一提交点可 alembic upgrade |
| 3 | `feat(175): governance import scripts` | `backend/scripts/import_plan175_governance.py`、`backend/scripts/import_ecg_relation_reviews.py` | 只读取证/导入工装 |
| 4 | `feat(174): quality ledger frontend + routes` | `src/api/quality.ts`、`src/router/modules/quality.ts`、`src/router/modules/asset.ts`（菜单改名"元数据质控"）、`src/views/quality/{issues,controls,observations}/`、`tests/plan174QualityLedger.test.ts` | **issue-detail/index.vue 与 observations/index.vue 含 178 R4 增量（单文件无法拆）→ 归本组并在提交信息正文注明"含 178 互链①"** |
| 5 | `feat(178): probe finding cross links` | `src/views/quality/sourceRef.ts`、`src/views/asset/probe-findings/index.vue`（**仅 178 R4 hunk**，拆分见 2.2）、`tests/plan178R4.test.ts` | ②③ 消费 query + listQualityObservations 反查 |
| 6 | `fix(177): catalog readback, recipe validation, edge labels, v-perms` | `services/asset_catalog.py`、`api/v1/recipes.py`+`services/recipe_service.py`、`components/RelationGraph.vue`、`value-domains/index.vue`、`dict/general/index.vue`、probe-findings 的 **177 C3 v-perms hunk**（拆分见 2.2）、`tests/test_r177_fixes.py`、`tests/plan166StageD2.test.ts`（B3 计数 3→4 库存更新） | dict.general.edit 为同页既有码 |
| 7 | `feat(identity): FFREE3, login/sign subtask, F-2 resync semantics` | `services/cdms_identity_adapter.py`、`services/jhemr_identity_adapter.py`、`services/identity_sync_{audit,log,status}.py`、`services/identity_sync_orchestrator.py`（F-2）、`scripts/run_identity_modified_nightly.py`、`services/identity_login_sign_sync.py`、`tests/identity_login_sign_sync/`、`tests/test_identity_sync.py`、`tests/test_identity_sync_122_unit.py`、`tests/test_identity_cb_resync_f2.py`、`tests/conftest.py` 的 177 hunk（拆分见 2.2） | **G1+G2+G3 的全部载体** |
| 8 | `fix(alembic): create asset schema if not exists` | `alembic/env.py`、`tests/alembic_env/`、`tests/conftest.py` 的 alembic_env 行（拆分见 2.2） | 178 C7 |
| 9 | `fix(178): GraphToolbar one-way data flow` | `src/views/asset/components/GraphToolbar.vue`、`src/views/asset/graph/index.vue`、`tests/plan178R2.test.ts` | 178 C6 |
| 10 | `docs(173-178): reports, plans, output dirs` | `开发起步包/` 下 148(M)/150(2×D)/172(M)/55/README/173–178 全部报告+计划+_结果.json+`output_r163..r178/` | 一笔入库，提交信息列明细；150 两删除按现状提交（G9 裁决后如恢复再追加） |

### 2.2 混合 hunk 拆分（2 个文件）

- `backend/tests/conftest.py`：`_PURE_LOGIC_SUBDIRS` 里 `"identity_login_sign_sync"` 行→组 7；`"alembic_env"` 行→组 8。方法=171 先例：`git diff -- <file>` 导出补丁按 hunk 拆分后 `git apply --cached`。
- `frontend/src/views/asset/probe-findings/index.vue`：177 C3 仅 transition 确认按钮一行 v-perms → 组 6；其余（import/route/watch/反查/按钮）→ 组 5。
- 备选（若执行时拆分受阻）：整文件归组并在提交信息注明混域内容，**不得**因此把文件踢出提交。

### 2.3 禁入清单（任何组都不许出现）

- **他人域 13 文件**：`frontend/src/layout/**` 5 个、`store/modules/app.ts`、`layout/captureMode.ts`、`tests/competitionCaptureMode.test.ts`、`tools/capture_*.py` 5 个（R0/R7 哈希基线锁定对象）。
- 工作目录：`backend/_r172_work/`、`backend/_r175_work/`、`backend/_oa_work/`（已 ignore）、`review/`、`verify/`、`frontend/审查_grok.*`。
- `backend/app/scripts/__pycache__/`（.gitignore 应已覆盖，add 时用显式路径不用目录通配）。

### 2.4 提交后门禁

- 每组 `git show --stat <sha>` 核对零越界（对照 2.1/2.3）；
- 全部提交后：`git status --short` 剩余未提交=仅他人域 13 文件+工作目录（理想态）；
- 后端 `pytest tests/alembic_env tests/test_r177_fixes.py tests/test_identity_cb_resync_f2.py -q` + 前端 `pnpm run typecheck` 快速复验（可引用 178 已跑全量，不重跑 34 分钟全量）。
- push 需**单独点名**（171 先例：ssh.github.com:443 + deploy_key）。

## 3. B 段 · G1+G3 后端发布（镜像重建 + F-2 上产 + MAX_NEW 回落）

### 3.0 前置探查（只读，发布第一步）

服务器构建/重建的具体命令**以服务器既有 deploy 事实为准**，执行时先只读确认：`docker inspect data-asset-api`（compose 工作目录、build 上下文、挂载）、`ls` 服务器 deploy/compose 目录，再按 r175/176 同款流程操作。禁止凭本文猜测路径。

### 3.1 DB 备份（保险，虽无迁移）

`docker exec <pg容器> pg_dump -U <user> data_asset > data_asset_pre_r178_<date>.dump`，校验大小/TOC 后继续。

### 3.2 镜像构建与重建

1. 构建：按 3.0 探查到的上下文 `docker build -t data-asset:r178-20260905 <context>`；
2. 重建容器（沿用现有 env/compose 参数），等待 healthy；
3. 冒烟：`/health` 200；三 API 前缀 401；`alembic current`=`d5e6f7a8b9c0`（无新迁移，no-op）；settings 回读 `identity_cb_max_update=150`、`identity_cb_max_new=130`（发布时刻仍为现值，验证语义未变）。
4. **FFREE3 持久化核验**（G1 目标）：确认镜像内 `cdms_identity_adapter.py` 含 FFREE3 模板常量（`docker exec ... grep FFREE3`）——这是 r175 镜像缺失、容器重建即丢的热修。

### 3.3 G3 env 回落（两步走，每步回读）

1. `MAX_NEW` 130→50：`cp /etc/data-asset/backend.env{,.bak-maxnew-20260905}` → 改 `APP_IDENTITY_CB_MAX_NEW=50` → 重建容器 → settings 回读 50；
2. `MAX_UPDATE` 150→100 **放在 F-2 验证成功之后**（3.5 夜跑 PASS 再做，防回退过早）：同款备份 `bak-cbmaxupd2` → 改 100 → 重建 → 回读。

### 3.4 G2 可选追加（与 G3 同窗执行最省）

`run_identity_modified_nightly.py` 已含登录/签名方式子任务接线（代码+测试就绪）；发布 r178 镜像后子任务自动可用，仅需确认 cron 入口调用的是新版脚本（inspect 容器内文件 hash 与镜像一致即可，无额外 env）。**此项需单独点名**（改变夜窗子任务集合）。

### 3.5 发布后验证（关键收口）

- 次日夜窗（02:00）后只读查 `asset_identity_scheduler_runs` 最新行：预期 **status=success、circuit_breaker_triggered=false**；F-2 生效后 110 例行 resync 应走 `resync_unchanged` 单列（不计 update/ratio；新列出现即 F-2 在产实证）；
- 子任务核验：`jhemr_signature_sync`/`jhemr_education_title_sync`/`jhemr_user_dept_sync` 状态≠skipped（主任务 success 后自动恢复）；若 G2 已授权，还应出现 `jhemr_login_sign_sync` 行；
- 抽样空签名账号回补（工号后四位掩码记录）。

### 3.6 回滚链

- 后端容器：`docker tag data-asset:r175-20260903 data-asset:rollback && ` 重建（或直接改 compose 镜像引用）；
- env：`.bak-maxnew-20260905` / `bak-cbmaxupd2` 恢复+重建；
- DB：无迁移；极端情况用 3.1 dump 恢复；
- 前端见 4.3。

## 4. C 段 · 前端 r178 原子切换

1. 本地 `pnpm run build`（178 已验证预算三绿：657.2/700、404.5/430、103.5/110 KB gzip）；记录入口 hash；
2. 上传 dist 至服务器前端版本目录 `r178-20260905`，**previous=r175-20260903 保留**；
3. 按 r175/166 同款原子切换（symlink/配置指向新版本）+ `nginx -t && nginx -s reload`；
4. 回读：首页 200；入口 JS hash 与本地构建一致；`/probe-findings` 与 `/quality/issues` 路由可达（401 冒烟；浏览器实拍互链可另行授权）。
5. 回滚：指回 previous 目录 + reload。

## 5. 红线重申（执行 AI 侧）

1. 他人域 13 文件零入库（2.3）；push 单独点名；
2. 150 课题（G9）与 004066（G7）仍未裁决，发布流程不夹带任何相关改动；
3. 值域不自动 confirm、探查发现不代点终态、业务源库零写入；
4. 每段落盘证据到 `output_r179/`（progress.md / exceptions.json），完成后按 AGENTS.md 登记 README 与 55。

## 6. 执行日志

| 时间 | 操作 | 结果 |
|---|---|---|
| 2026-09-05 | 依据 178 §7 交接与 N1 FAIL 证据，起草 G13+G1+G3 runbook | 仅文档；零 Git/零生产/零业务源；git 只读核实 .gitignore、asset.ts、app/scripts、work-dir ignore 状态 |
| 2026-09-05 | 升级为 180 号一次性执行计划（交 5.3 flash） | A 段分组以 180 为准：采用本文 §2.2 备选路线（不拆 hunk，整文件归组+提交信息注明）；B/C 段步骤在 180 中细化为带预期输出的机械命令（Dockerfile.hotpatch 构建链/run_data_asset_api.sh/release_frontend.sh 均经只读核实）。本文保留为背景与理由 |
