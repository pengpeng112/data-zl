> 类别：模块规划
>
> 状态：**v1.1 定稿待执行（2026-08-29 拍板落地：P1=巡查计划卡纯演示展示，不做真调度（用户裁决"只是演示界面即可，不用真定期"）；P2=演示环境隔离库（已确认）。round-6 v5 核查 20 项裁决不变，证据链 `review/round-6/`）**
>
> 上位入口：`55_系统未完成事项统一执行计划.md`
>
> 关联：`ai_quality.py`/`ai.py`/`hospital_llm_*`（复用底座）；`144/149`（上下文与值域注入）；`review/round-6/`（核查与裁决）
>
> 执行方式：单执行者连续推进、checkpoint 跨会话续跑；**执行窗互斥：在 164→165→166 完成后开工**（与 165"探查发现"命名/菜单互不重叠——本功能名为"AI 巡查演示"）

# AI 巡查演示界面与 AI 写 SQL 工作台开发计划（167）

## 0. 用户原始需求（原话，2026-08-29）

> "我需要加一个ai 帮助定期只读巡查的界面 可以与当前的ai质控与分析 界面在一起 一起优化下这个界面，借助当前内网对接的，可以先让他固定巡检数据中心，然后固定找个表有问题的帮着分析即可，因为我需要进行演示。 同时后期会改为更强大内网模型，就是为了证明我当前是在应用的。 还有就是加个界面 能够让ai试试帮我写sql的 界面，根据本机数据库的关系帮我写sql。 界面一定好看直观一些。"

## 1. 现状底座（round-6 更正版，禁止重探）

| 底座 | 事实 |
|---|---|
| AI 质控页 | `views/asset/ai-quality/index.vue`（446 行）：页头（院内模型标签/连接测试/总览报告）+**左右工作台（左待分析问题/右分析结果含 `partial_text` 流式轮询 0.4s，最长 10 分钟）+底部最近分析表**；无 Tab。本计划**保留全部现有布局与能力** |
| AI 质控后端 | `ai_quality.py` **10 端点**，路由前缀 **`/api/v1/quality/ai`**；作业=后台线程+流式；`POST /jobs` 强制 preview 请求签名（AQJ-+HMAC）链；`AiQualityJob.task_type` Literal（finding/finding_batch/run_summary）；`AiQualityResult.job_id` 一对一；status 已含 `last_success_at`，**host 字段当前硬编码**（S1 修） |
| 调度字段（备注） | `QualityTask.schedule_cron/enabled/last_run_at` 存在但**本计划不使用**（P1 已拍板：计划卡纯演示展示，不做真调度） |
| 内网模型 | hospital_llm：deepseek-r1@10.255.255.10:9000、90s、max_tokens 1800、**max_payload 24KB**、凭据受控文件 |
| 写 SQL 底座 | `ai.py` propose-sql/sql-risk-scan/sessions/AiToolCall 审计表；**`ai_context_builder` 的 business_relations 现仅含 from/to_table+cardinality（无 join 列、不按系统过滤、全局前 200）——S3a 必须先扩展**；AssetRelation 模型本身有 from_columns/to_columns/join_condition（数据现成） |
| 试运行通道 | sql-workbench=受控 DML 运维台（**与本项目无关，禁跳转**）；真实只读执行=草稿批准后 `POST /ai/drafts/{id}/execute`（ai.sql.execute）或查询中心认证查询 |
| 前端约束 | 无 Monaco 依赖（不引入）；新页须异步 chunk；测试=plan146 源码断言式；权限码点号；AI 页全在 `/asset/*` |

## 2. 假设与拍板结果（2026-08-29 用户已裁决）

H1–H5 沿用草案（演示集配置文件化/平台库内指标/引擎状态卡/生成 SQL 不直接执行/复用规范）。
**P1 已拍板**：巡查"定期"=**计划卡纯演示展示**——静态呈现"计划：每日 02:00｜状态：演示形态（未启用调度）"及说明文案；**不连 QualityTask 表、无启停开关、不实现任何真实调度路径**（用户原话"只是演示界面即可，不用真定期"）。
**P2 已拍板**：演示环境=**隔离库**（8.83 只读演示留作备选，随主 AI 发布窗口）。

## 3. 功能 A：AI 巡查演示（合入 ai-quality 页）

### A1 页面改造（保留现有，零重构）

现页顶部插"**引擎状态卡**"横幅；正文加 `el-segment`（问题分析=现视图默认｜**AI 巡查演示**=新视图）；146 E3 流式/Markdown/任务表能力零触碰。

### A2 引擎状态卡（常驻页头）

provider/模型名/**host（S1 改由 config 派生+尾段脱敏）**/最近成功时间（已有）/累计成功次数（新：GovernAuditLog 聚合 `module=quality_ai AND action=succeeded`，带索引聚合+60s 缓存）/连接测试按钮。角注："引擎由服务器配置驱动（APP_HOSPITAL_LLM_*），换更强模型无需发版"。

### A3 巡查演示视图（新 segment）

- **巡查计划卡**（**P1 拍板：纯演示展示**）：静态配置呈现"计划：每日 02:00｜状态：演示形态（未启用调度）"+说明文案"定时执行未启用，当前通过一键巡查手动演示"；**不连 QualityTask、无启停开关、无调度代码路径**。
- **巡查目标集卡**：`backend/app/services/ai_patrol_targets.json`——每表条目=system/source/schema/table/中文名/问题标签/**证据链（rule_id/finding_id/指标值/采集时间/数据截至时间/快照版本）**；证据链必须真实（S1 从生产平台库只读质量规则最近结果选取固化；演示标签如"注释缺失 92%"只能来自该证据，禁止手填数字）。详情抽屉展示字段数/指标摘要/证据。
- **一键巡查**（权限 `asset.quality.ai.analyze`）：前端编排——对目标集每表固定 findings 批次**走既有 preview→POST /jobs 链**（finding_batch 类型；`input_summary` 附 `patrol_run_id=patrol-<ts>`，job_key 掺 run_id 防静默复用）；逐表进度（复用现有流式轮询，每表一张进行中→完成卡）；单表失败继续。
- **巡查结果**：每表分析卡（问题指标+**patrol prompt 版本化输出**：逐表结论/风险等级/证据引用/局限说明；schema 解析失败降级为可读文本且明确标注）+跳表详情/质量页；**结果标注"指标数据截至 <证据链采集时间>"**。
- **巡查历史**：新端点聚合（按 patrol_run_id 分组：时间/表数/完成数/结论摘要）。
- **一键演示**：按固化剧本顺序执行（计划卡讲解→巡查→结论高亮→跳 AI 写 SQL）；**离线回放**：LLM 不可达自动展示最近成功 run，全屏醒目"离线回放（引擎最后成功 HH:MM）"，不刷累计次数。

### A4 patrol prompt（版本化，扩展 hospital_llm_analysis）

输入=表元数据+指标快照+findings+证据时间；输出=逐表{结论,风险等级,证据引用[],局限}；硬规则"只依据给定证据分析，禁止虚构统计值"；`INPUT_SCHEMA=patrol-analysis-input/v1`；复用 preview 签名机制。

## 4. 功能 B：AI 写 SQL 工作台（新页 `/asset/ai-sql`）

### B1 布局（左需求右结果，异步 chunk）

- 左：需求 textarea+4 条示例芯片；系统选择器**锁 DATA_CENTER（Oracle）**（其他置灰"后续开放"）；关联表选择器（系统内表搜索多选，可留空=由 AI 按关系解析）；依据偏好开关；生成按钮（loading+取消=停止等待，服务端调用仍完成并计次——界面注记）。
- 右：**生成 SQL**（只读语法高亮 pre + 复制 + "编辑模式"切 textarea——**无 Monaco**）；**依据卡**（注入的表/关系（含 join 条件）/值域三色标签云）；**风险徽标**（sql-risk-scan：只读/大表 WHERE/方言）；操作条：**存为草稿**（propose-sql→AI 草稿审核流）+说明文字"查看执行结果：草稿经人工审核后由管理员执行（既有通道）"；**删除任何即席执行/试运行入口**。
- 底：本人历史（复用 AiToolCall：tool_name=ai_sql_generate、仅本人、question 脱明文只存摘要+hash）。

### B2 生成链（POST `/api/v1/ai/ai-sql/generate`）

question → `sanitize_text` → S3a 裁剪上下文（选中表+1 跳邻居≤20 表、关系≤40 条**含 join 三要素**、值域选中表相关）→ hospital_llm（system prompt：Oracle 方言/只读/ROWNUM 限量/禁写；**输出清洗：围栏剥离+截断检测+一次重试**）→ sql-risk-scan → 返回 `{sql, risk, context_digest{tables,relations,value_domains}}`；权限 `ai.context.read`（与 propose-sql 对齐）+审计（含限流注记）；24KB payload 裁剪规则固化于 S3a 测试。

## 5. 界面规范（好看直观·可验收）

状态卡渐变主题+状态呼吸点；巡查时间线红黄绿问题数徽章；结论富文本（146 E3 渲染器+XSS 转义）；一键演示按钮主题渐变；B 页三色标签云+芯片；空态文案（A"尚无巡查记录，点一键演示试试"/B"描述你的取数需求试试"）；1280+ 双栏、<1280 折叠单栏；主路径三步内（生成→复制/存草稿）。视觉验收=两页截图对照本节+现页能力零回归清单。

## 6. 逐文件变更表

| 文件 | 动作 |
|---|---|
| `backend/app/services/hospital_llm_analysis.py` | +patrol prompt/解析（v1，只增） |
| `backend/app/services/ai_patrol_targets.py`（新，含 json） | 目标集加载+证据链校验 |
| `backend/app/api/v1/ai_quality.py` | +`GET /patrol/targets`、`GET /patrol/runs`、`POST /patrol/run`（编排=循环建 preview+jobs，**不绕签名**）；status：host 派生+累计次数 |
| `backend/app/services/ai_context_builder.py` | S3a：relations 补 join 三要素+系统/表闭包过滤+裁剪参数（只增不改既有输出兼容） |
| `backend/app/api/v1/ai.py` | +`POST /ai-sql/generate`；AiToolCall 登记 |
| `frontend/src/router/modules/asset.ts` | +/asset/ai-sql（meta.auths=ai.context.read，异步 chunk） |
| `frontend/src/api/asset.ts`（或新 probe 风格 api 文件） | patrol/ai-sql API 函数 |
| `frontend/src/views/asset/ai-quality/index.vue` | 状态卡+segment+巡查视图（现有布局零删改） |
| `frontend/src/views/asset/ai-sql/index.vue`（新） | B 页 |
| `backend/tests/test_ai_patrol.py`、`test_ai_sql_generate.py`、`test_ai_context_join_columns.py`（新） | 专项测试 |
| `docs/demo/ai-patrol-demo.md`（新） | 3 分钟演示剧本 |
| permissions.py/security_audit | 无新码（全复用既有权限码；若新增路由扫描断言按既有清单同步） |

## 7. 端点契约

| 端点 | 方法/权限 | 请求→响应（要点） |
|---|---|---|
| /api/v1/quality/ai/patrol/targets | GET/view | →{targets:[{schema,table,name_cn,issue_label,evidence{rule_id,finding_id,metric,captured_at,data_as_of}}]} |
| /api/v1/quality/ai/patrol/runs | GET/view | ?page&page_size→{items:[{patrol_run_id,started_at,tables_total,tables_done,summary}],total,...}（按 input_summary 聚合） |
| /api/v1/quality/ai/patrol/run | POST/analyze | {patrol_run_id?}→{patrol_run_id, jobs:[{table,job_id}]}（服务端逐表建 preview+job；202 语义） |
| /api/v1/ai/ai-sql/generate | POST/ai.context.read | {question,system_code='DATA_CENTER',tables?,prefer?}→{sql,risk,context_digest}（422：方言锁/超裁剪；504→前端取消提示） |

## 8. 执行批次（S0→S6）

| 批 | 内容 | 验收 |
|---|---|---|
| S0 准备 | 确认前置窗（164/165/166 完成）；读 ai_quality.py/ai_context_builder.py 源码核对 §1 事实；P1/P2 按已拍板值登记（计划卡纯演示展示/隔离库演示） | 事实核对表入 progress |
| S1 A 后端 | patrol prompt/目标集服务/3 端点/status 修 host+计数+审计聚合缓存；目标集证据链（生产只读选取固化） | `pytest tests/ -k "patrol or quality" -q` 全绿；目标集每表证据链完整 |
| S2 A 前端 | 状态卡+segment+巡查视图+一键演示+离线回放+剧本 md | typecheck 双过+源码断言测试≥4+现页能力回归清单全绿+截图 |
| S3a 上下文扩展 | ai_context_builder：join 三要素+闭包过滤+裁剪；组合键测试（PATIENT_ID+VISIT_ID 缺一失败）、候选关系不进 JOIN | `pytest tests/ -k context -q` 全绿（含既有 context 测试零回归） |
| S3 B 后端 | generate 端点（清洗/重试/风险/审计/取消语义） | `pytest tests/ -k ai_sql -q` 全绿 |
| S4 B 前端 | /asset/ai-sql 页+历史+互链 | 源码断言测试≥4+截图 |
| S5 联调门禁 | 隔离库端到端：**至少一次真实内网模型调用留证**（provider/model/job_id/耗时/脱敏摘要；不可达则 BLOCKED 登记并等待窗口补跑，mock 不作数）+全量 pytest+三件套+gzip（新页异步 chunk） | 门禁输出+两页截图+真实调用证据 |

## 9. 铁律（STOP 白名单）

四类 STOP 沿用 163 §1；其余偏差 WARN 落 `output_r167/exceptions.json` 继续。硬约束：LLM 只收元数据/关系/脱敏文本（零患者数据）；生成 SQL 永不即席执行；不触碰 sql-workbench；preview 签名链不可绕；现有 ai-quality 能力零回归（S2 验收项）；零新前端依赖；零迁移；与 165/166 文件窗互斥；凭据零落盘；零 Git 写；pnpm。

## 10. DoD

S0–S5 checkpoint 齐；专项测试全绿+全量 0 failed（plan127 s0 例外口径沿用）；前端三件套+gzip 全绿（新页异步 chunk）；**至少一次真实内网模型调用证据**；两页截图+演示剧本+现页回归清单；README/55 登记；等待域呈用户。

## 11. 等待域

真定时调度：**用户已裁决首期不做（2026-08-29，P1）**，如未来需要另行立项；8.83 只读演示发布（P2 备选，随主 AI 窗口）；live 采样巡查（受控连接器）；换更强内网模型（改 env）；生成 SQL 的草稿审核与执行（既有流程人工）。

## 12. 执行提示词（复制给执行 AI，勿增删）

```text
【任务】一次性执行 开发起步包/167_AI巡查演示界面与AI写SQL工作台开发计划.md（v1.0）的 S0→S6。
【前置】164/165/166 均已完成（执行窗互斥）；开工前 git log 确认且未 checkout/stash 他会话成果。
【必读】AGENTS.md；167 号 v1.0 全文；review/round-6/分歧表.md（20 项裁决依据，尤其 #1 sql-workbench 禁触碰、#3 异步复用、#7 S3a join 三要素）；backend/app/api/v1/ai_quality.py 与 app/services/ai_context_builder.py、hospital_llm_analysis.py 源码（S0 逐条核对 §1 事实表）；149 §8、146 §11 E3（渲染器与测试风格）。
【铁律】167 §1 底座表与 §9：preview 签名链不可绕、生成 SQL 永不执行、LLM 输入零患者数据且 question 先 sanitize、现页能力零回归（S2 回归清单必过）、零新依赖零迁移、新页异步 chunk、权限码点号、测试用 plan146 源码断言式。
【节奏】S0→S1→S2→S3a→S3→S4→S5，每批验收全过才进下一批；S5 真实模型调用不可达时记 BLOCKED 待窗口补跑（mock 不作数）；偏差一律 WARN 落 output_r167/exceptions.json 继续，禁止向用户提问、禁止弱化断言。
【产出】167 §10 DoD 逐项自检；执行报告+同号 _结果.json（含真实调用证据/两页截图索引/回归清单）；README/55 登记「隔离库完成，待主 AI 复核与发布」；等待域呈用户（P1/P2 已拍板：计划卡纯演示展示、隔离库演示）。
```
