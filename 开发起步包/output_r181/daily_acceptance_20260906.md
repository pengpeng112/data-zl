# 每日生产只读验收 · 2026-09-06（独立验收 AI）

> 范围：生产只读验收 + 本地隔离环境全量回归 + 问题报告。禁止修复/发布/提交/写业务库——全部遵守，见 §6 零声明。
> 证据原则：全文脱敏（无工号全码、无患者号、无姓名、无口令、无 DSN）；计数与时间戳为主。
> 交叉核验：工作区 02:25 自动化产出的 `output_r180/nightly_d.md`（另一会话排程）与本报告对同一 run 的独立结论一致（FAIL/max_change_ratio）。

## 1. PASS/FAIL 总结

| 任务 | 判定 | 一句话结论 |
|---|---|---|
| 任务一 目录与工作区盘点 | **PASS** | 目录自检无孤儿/幽灵（范围引用误报已排除）；HEAD 与工作区改动已记录；期间出现并行会话新提交 2361e90（属他人资产，未触碰） |
| 任务二 生产夜跑验收 | **FAIL（P0-1）** | 容器/镜像/alembic/熔断配置/守卫六项全过；但 02:00 主任务 RUN-69e87f7f27dd 仍熔断（max_change_ratio），三子任务连带跳过；F-2 首个生产夜窗未达预期 |
| 任务二附加（签名异常） | **PASS** | 09-06 00:00 后 JHEMR users_subsign/users_sublogin 改动行=0，"已有签名方式又新增"异常用户=0（主任务预检即中止、零写入） |
| 任务三 Docare 每日扫描首跑 | **FAIL（P1-1）** | cron 00:10 唯一一条 ✓、清单文件生成 ✓、权限 0600 ✓；但脚本在 HIS 核验阶段连 ODS 报 ORA-12541（瞬态）崩溃，list_20260906.md 为 0 字节；零修订/零备份/零新增审计（安全侧干净） |
| 任务四 本地隔离回归 | **PASS** | pytest 1425P/1S/0F；alembic 隔离库 no-op 单头 d5e6f7a8b9c0；前端 typecheck+278 tests+build 预算三绿 |

**总判定：FAIL（1×P0、2×P1）。** 失败点集中在夜间身份同步死锁（存量问题未随 r181 解除）与 Docare 扫描首跑瞬态崩溃；本地代码质量与生产静态配置无回归。

## 2. 与上一基线（r181 发布态，2026-09-05）的差异

| 项 | 基线（09-05 发布后） | 本次实测（09-06） | 评价 |
|---|---|---|---|
| 后端镜像/容器 | data-asset:r181-20260905 healthy | 同（Up 12→16h healthy，started 09-05T02:50Z） | 无漂移 |
| alembic head | d5e6f7a8b9c0 | 同（容器 current + 本地隔离库一致，单头） | 无漂移 |
| 熔断 settings | max_update=150 / max_new=50 | 同（容器内 Settings 实读） | D2 正确未执行（D1 未 PASS） |
| 容器守卫 | skip_configured=2（镜像内） | 同（热修后文件 grep 仍=2） | 在产 |
| 02:00 夜跑 | 预期 success（180 §1/181 §9） | **failed@max_change_ratio，第 6 晚连续失败** | **负向差异（P0-1）** |
| login_sign 子任务 | 预期不出现（G2 未授权） | report_summary 出现 `{"status":"success"}` | 占位符误报（P3-1），实际未执行：0 动作/0 子任务行/runner 无调用 |
| Docare 扫描 | 182 §7 只读清单版 | **23:06 被并行会话升级 v3（含受控自动修订）** | 版本与口径变化（P1-2），首跑崩溃（P1-1） |
| 容器 app 文件 | 镜像态 | identity_login_sign_sync.py / jhemr_identity_adapter.py 于 09-05 22:42 被 docker cp 热修（003534 对齐逻辑） | 热修漂移（P2-1），重建即丢 |
| 本地后端全量 | 177 基线 1415P/1S | **1425P/1S/0F**（+10，含并行会话守卫新测试） | 无回归 |
| 前端 | 178 基线 278 tests | 278/278 过（含新 competitionCaptureMode 1 test） | 无回归 |
| Git | HEAD=b6b67a5 | 期间并行会话新增 2361e90（v3 脚本+182 §10+55/README 未提交修改） | 他人资产，未触碰 |

## 3. 问题清单（P0–P3）

### P0-1 夜间身份同步主任务连续第 6 晚失败；F-2 上产未解除熔断（结构性死锁）

- **现象**：`RUN-69e87f7f27dd`（09-06 02:00:03–02:00:52）status=failed，circuit_breaker_triggered=True，dimension=**max_change_ratio**；candidates_total=110、deactivate=4；signature/user_dept/education_title 三子任务全部 skipped（reason=main_account_sync_not_successful）。alerts 表 09-04/05/06 连续三晚 circuit_breaker_open（09-01~03 为 max_update 维度）。
- **根因（本会话只读重放实证，非推测）**：水位表 last_run_at 停在 **08-30 10:16/10:17**（失败 run 不推进水位）→ 此后 HIS MODIFIEDTIME 增量窗内的人员每夜全量重选。实测当前候选 110 人**全部带 modified_time 标记**（`select_nightly_candidates` 在增量模式下只返回窗内人员且必带标记）→ `_compute_change_stats` 全部落 update 桶（resync_unchanged=0）→ F-2 豁免条件"无 modified_time"**永不满足**→ ratio=(110+4)/scope(99)≈1.15>0.3 → 熔断 → 水位继续停滞 → 死锁闭环。
- **命令与脱敏证据**：
  1. `docker exec -i data-asset-api python -` 查 scheduler_runs/subtasks/alerts（started_at 02:00:03+08、CB dimension=max_change_ratio、三子任务 skipped）。
  2. 只读重放（容器内，`select_nightly_candidates` + `_fetch_jhemr_existing_emp_nos` + `_compute_change_stats`，全部 SELECT）：candidates=110（modified_time=110）、jhemr_existing=set(110)（存在性检查正常，排除瞬态说）、new=0/update=110/resync_unchanged=0/scope=99。
  3. 水位：`select * from asset.asset_identity_sync_watermarks` → 两行均 2026-08-30 10:1x。
- **影响**：自 09-01 起签名/职称/科室子任务零执行，HIS 侧人员变更（含 08-27 职称批量改动余量）持续积压；004057 类签名缺口无法经夜间任务补齐；D2（MAX_UPDATE 150→100）被正确阻断（若执行，110>100 将叠加 max_update 熔断）。
- **建议（不修复，待主 AI/用户裁决）**：三选一——① 参照 W10 先例，授权一次受控重放（临时放宽 change_ratio 或单通道对齐）成功后推进水位，死锁即解；② 修订 ratio 语义：增量窗内"已对齐幂等行"不计分子（代码改动，需另立任务）；③ 持续等待并接受每晚失败告警（不推荐）。注：176"110 人例行 resync"的诊断前提有偏——他们不是无标记 resync，而是带标记的窗内重入者。

### P1-1 Docare 每日扫描首跑崩溃（ODS 瞬态无监听），首份清单缺失

- **现象**：cron.log 记录 00:10 执行 `docare_mismatch_daily.py` 在 HIS 核验阶段（`his_visits`→ODS 8.216）抛 `ORA-12541: TNS 无监听`，进程崩溃；list_20260906.md 生成但 0 字节（权限 600 正确）。
- **命令与脱敏证据**：`cat /opt/data-asset/evidence/docare_mismatch/cron.log`（Traceback 至 ORA-12541）；`stat -c '%a' list_20260906.md` → 600；崩溃后实测 `/dev/tcp/10.10.8.216/1521` OPEN + 容器内受控连接器 `SELECT 1 FROM DUAL` 成功 → 判定瞬态（同夜 02:00 JHEMR 相关链路亦未受影响）。
- **影响**：09-05 全天新增错配未产出清单（首份正式清单缺失）；无数据损坏、零修订执行（fix_backup 文件=0、docare 模块审计新增=0）。
- **建议**：明晨巡检确认 cron 自愈（ODS 已恢复，预计正常）；脚本加连接重试/降级（Ods 失败时只出本地口径清单）属代码修改，留主 AI 决策。

### P1-2 扫描脚本已升级 v3 含"受控自动修订"，与任务书/182 §7 的"全程只读"口径不一致，授权链待确认

- **现象**：服务器脚本 09-05 23:06 更新为 v3（md5 daeff846…，341 行）：无参 cron 路径即 `auto_all`（`--dry-run` 才禁用），对满足四重与门（登记值来源+默认 1+HIS 落窗核验+本地==HIS 编号）的组执行 备份→UPDATE 16 表模式→平台审计，单晚上限 10 组。并行会话已在 182 §10、55 顶注登记 v3 上线；本会话未检索到用户对"每日自动修订"的点名授权记录（c0632940 样例为逐例授权；55 旧条目曾写"如需同款自动修订需另行逐例授权"）。
- **命令与脱敏证据**：`grep -nE 'UPDATE |auto_all|DAILY_FIX_LIMIT' /opt/data-asset/scripts/docare_mismatch_daily.py`（L212-215 UPDATE 语句、L38 DAILY_FIX_LIMIT=10、L283 auto_all 判定）；今夜实际执行=0 修订（崩溃于核验阶段，未达修订分支）。
- **影响**：若授权链成立则属既定决策；若不成立，明晚起 cron 将自动写业务库（MED_OPERATION_MASTER 等 16 表），与"每日 AI 不做业务库修订"的任务边界冲突。
- **建议**：主 AI 与用户确认 v3 自动修订的授权事实并落档；未确认前，明日验收必须核查 fix_backup 文件数与 docare 审计行数，出现即升级呈报。

### P2-1 容器内两处 docker cp 热修与镜像态漂移

- **现象**：`/app/app/services/identity_login_sign_sync.py` 与 `jhemr_identity_adapter.py` mtime=09-05 22:42:55（容器 10:50 启动之后），为并行会话热修（003534 对齐逻辑：登录有/签名无→default=0 补齐）。55 顶注已声明"重建镜像会丢，须随下次正式发布"。
- **命令与证据**：`docker exec data-asset-api ls -l --time-style=+%F_%T /app/app/services/identity_login_sign_sync.py ...`。
- **影响**：镜像重建/回滚即回退到 r181 镜像态，行为差异无 Git 承载；与本验收基线的"容器代码=镜像"假设不符。
- **建议**：主 AI 复核该改动后随下次镜像发布固化（并入 180 W-02 的 G2 决策面一并收口）。

### P3-1 report_summary 中 login_sign 的 success 为默认占位符（展示误导）

- **现象**：runner（r175 旧版）不调用 login_sign，`finalize_run` 的 `login_sign_result or {"status": "success"}` 默认值被写入汇总；实际 0 动作、0 子任务行。02:25 D1 自动化曾将该条解读为"G2 被激活"——代码级证据表明是占位符，G2 未激活。
- **建议**：后续把默认改为 `not_configured` 之类中性值（代码改动留主 AI）。

### P3-2 阈值路径丢失 stats 构成；run 行 new/update 恒 0

- **现象**：熔断分支先写 `{threshold, stats}` 后被 `finalize_run` 整体覆盖；`candidates_new/update` 在阈值路径从不赋值（默认 0）。排障只能靠只读重放（本次即如此）。
- **建议**：finalize_run 合并保留 stats 摘要（含 resync_unchanged/align_check），run 行在阈值分支也落桶计数。

### P3-3 目录维护：55/README 存在并行会话未提交修改（在制状态）

- 现状即协作常态，非缺陷；本次验收未触碰。主 AI 提交时注意 CRLF 警告行。

## 4. 验收明细（按任务书逐项）

### 任务二 · 生产夜跑（02:00 后核验）
- 容器 healthy：`docker inspect` → healthy，image=r181-20260905 ✓
- 镜像 r181-20260905 ✓（非 r178：r181 为 09-05 上午经用户授权的后续发布，181 §8）
- alembic head 未漂移：容器 current=`d5e6f7a8b9c0 (head)` ✓
- 熔断配置：max_update=**150**、max_new=**50**（max_align=150、ratio=0.3）✓；D2 回落=未执行 ✓（门禁正确）
- 最新主任务：started_at=09-06 02:00:03（当日夜窗 ✓）、status=**failed** ✗、CB triggered=True（max_change_ratio）✗
- report_summary：无 resync_unchanged 字样 ✗（F-2 未生效，见 P0-1）；signature/user_dept/education_title 均 skipped ✗（因主任务失败，属设计内连带，但主任务本身应成功而未成功）
- login_sign：未实际接入 runner（G2 未激活）——report_summary 的 success 为占位符（P3-1），**非误报为异常，亦非已执行**
- skip_configured 守卫：容器内 `grep -c skip_configured jhemr_identity_adapter.py`=2 ✓（含 22:42 热修版本）
- 签名异常扫描（脱敏计数）：09-06 00:00 起 users_subsign/users_sublogin 改动行=0；"已有配置又新增"用户=0 ✓

### 任务三 · Docare 扫描（00:10 后核验）
- cron 唯一性：root crontab 中 `10 0 * * *` 仅一条（另有既有 02:00 pg_backup，无关）✓
- list_20260906.md：已生成、0600 ✓，但内容为空（P1-1）✗
- cron.log：有 ORA-12541 Traceback ✗
- 扫描量/错配组数/建议修订数：**未产出**（崩溃于 HIS 核验前段；本地候选行数因崩溃未输出，不引用 09-05 旧试跑数字冒充今日结果）
- 自动修订执行：0（fix_backup=0、审计新增=0）✓；未触碰 MED_OPERATION_MASTER 等任何 Docare 表 ✓
- 历史 2 万余份存量：未处理 ✓（且 v3 重计口径为 358 组/1,469 份，见 182 §10）

### 任务四 · 本地隔离回归
- 测试库指向：`APP_TEST_DB_URL=postgresql+psycopg://postgres@127.0.0.1:15533/data_asset_test`（自建 SSH 隧道 15533；conftest 门禁含 "test" 校验通过；backend/.env 的 APP_DB_URL 未被任何测试加载）✓
- `pytest tests/ -q` → **1425 passed / 1 skipped / 0 failed**（1938s）✓
- `alembic upgrade head`（隔离库）→ no-op，current=`d5e6f7a8b9c0 (head)`；`alembic heads` 单头 ✓
- `pnpm run typecheck` → tsc+vue-tsc 0 错 ✓
- `pnpm test` → 44 文件 / **278/278** ✓
- `pnpm run build` → 预算三绿（main 657.2/700、graph 404.5/430、css 103.5/110 KB gzip）✓

## 5. 未执行事项与原因

| 事项 | 原因 |
|---|---|
| 任何代码修复、阈值调整、水位人工推进 | 任务书禁止修复；P0-1 仅报告 |
| D2（MAX_UPDATE 150→100） | 授权门禁=D1 PASS；D1 FAIL，正确不做 |
| Docare 扫描补跑/加 --fix/重试 | 禁止触发同步与修订；留明晨 cron 自愈验证 |
| 历史 20,651（v3 重计 358 组）存量处理 | 用户已裁决不处理；禁止改 Docare 表 |
| `pnpm install`、带 --fix 的 lint | 任务书禁止；依赖完整未缺失 |
| 生产库 alembic upgrade | 生产 head 未漂移，无需迁移；任务书仅授权隔离库执行 |
| Git add/commit/push、stash、checkout、清理 | 全部他人资产；任务书禁止 |
| Word 锁文件、r178/r181 构建包清理 | 任务书明确不处理 |

## 6. 零声明（本会话全程）

- **生产平台库写入 = 0**（仅 SELECT；报告查询含只读重放，均未产生写事务）
- **业务源库（Docare/HIS/JHEMR/CDMS/ODS）DML/DDL = 0**（仅 SELECT，含签名异常计数查询）
- **env / cron / 容器 / 镜像修改或切换 = 0**（仅只读 inspect/exec 查询）
- **Git 写操作 = 0**（无 add/commit/push/stash/checkout/reset）
- 本地写入仅两类：隔离测试库 data_asset_test（任务四既定回归，含测试数据 TRUNCATE/重建）+ 本报告文件本身；SSH 隧道（15533）为临时通道，会话结束即失效
- JHEMR 探查经只读凭据；全程未打印任何口令/Token/DSN/工号全码/患者号

---
*验收 AI 生成于 2026-09-06（覆盖 09-05 23:00 – 09-06 06:45 时窗：00:10 Docare 首跑与 02:00 身份夜跑均在窗口内实测）。*
