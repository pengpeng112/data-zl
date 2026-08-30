先按只读约束核对待审方案与用户原话，并对照现有 AI 质控/分析界面与内网对接实现。方案已读完。接下来对照现有 AI 质控、写 SQL 与作业模型实现，核对假设是否站得住。独立核查结论：**不能按 `review/round-6/方案.md` v0.9 直接交给执行 AI。** 需求方向大体对（质控页加演示巡查 + 另开写 SQL 页 + 用现有内网模型），但方案把若干**不存在或语义相反**的底座写成“可复用”，执行者会按错误地图开工。下面分需求忠实度与自发问题，均对照源码，不依赖方案自述。

---

## 总评

用户要的是：**演示级、只读、能看见内网模型在干活**的两块界面，并把巡查嵌进现有「AI 质控分析」。方案抓住了这条主线（§0–§2、H3–H5、§7 等待域），安全红线（不接写执行器、A 不连源库、生成 SQL 默认不执行）与仓库铁律一致。

但它把“复用”写得过满，且对现状 UI/API 描述失真。最危险的不是“定期调度延后”（H1 可接受），而是：**B 的试运行出口指向运维写库工作台；A 的作业复用与现有 jobs/results 契约对不上；§1 底座表有多处事实错误。**

---

## ① 需求覆盖与忠实度

对照用户原话（方案 §0）逐条：

| 原话要点 | 方案处置 | 忠实度 |
|---|---|---|
| 加 AI **定期只读巡查**界面 | §3 巡查 Tab + 手动触发/历史；真正 cron 进等待域（H1） | **部分忠实**。演示可接受，但未把“定期”在界面上说清楚（易被理解成已有调度） |
| **与当前 AI 质控与分析在一起，并一起优化** | A 合入 `ai-quality` | **意图对、拆法偏**。现页不是方案说的“分析任务/治理简报两 Tab”，而是左右工作台 + 底部任务表 + 流式出字。三 Tab 可能把现有分析流拆散，不像“一起优化” |
| 借**当前内网对接** | hospital_llm / deepseek-r1 / `10.255.255.10:9000` | **忠实**。与 `config.py`、`/status` 一致 |
| **固定巡检数据中心** | 默认 DATA_CENTER 演示集 | **忠实** |
| **固定找个有问题的表帮着分析、为了演示** | 3–5 张问题表 + 一键演示 + 离线回放 | **过设计但仍覆盖**。用户说的是“找个表”，方案做成多表巡查链；演示目标能达到 |
| 后期换更强内网模型、**证明当前在应用** | 引擎状态卡 + env 换模型（H4、A2） | **大体忠实**。但离线回放（A3）与“证明在应用”会打架，必须把直播路径当主路径 |
| **另加 AI 写 SQL 界面**，按**本机数据库关系**写 SQL | 新页 + context resolve + 依据卡 | **语义基本对**（“本机”=平台库关系，不是 Windows 本机库）。缺：自动按关系扩表，过度依赖用户手选表 |
| 界面好看直观 | §5 组件/时间线/标签云 | **有方向、不可执行**。没有线框、没有对照现页保留什么、没有空/错/超时态的交互稿 |
| 给别的 AI 开发的详细计划 | S1–S5 | **不够详细**。缺请求/响应契约、文件清单、禁止项、与 165/166 窗互斥、安全审计锁 |

H1–H6 作为假设大多合理，但 **H6「菜单挂 AI 协作组」「B 新页 `/ai/ai-sql`」与现网导航不符**：现有 AI 页全在 `数据资产` 下（`/asset/ai-quality`、`/asset/ai-tools`、`/asset/ai-context`），没有「AI 协作组」，也没有 `/ai/` 路由组。

未覆盖或弱覆盖：

1. **演示发生在哪套环境**（本机隔离库 vs 8.83 生产前端）。用户说“我需要进行演示”，方案 DoD 写隔离库联调 + 截图，**没有生产发布/演示账号路径**（§7 把生产发布放等待域）。隔离库上的“问题表”在 8.83 上可能对不上。
2. **“定期”的用户可见口径**。界面若只写“定期巡查”却只能点按钮，演示时会被问“定时在哪”。
3. **写 SQL 后能不能看见结果**。原话是“试试帮我写 sql”，复制 SQL 已能交差；方案却画了“去试运行”，而现成通道并不能安全地试跑生成 SELECT（见下）。

---

## ② 自发问题（按严重度）

### P0-1 — §1 / B1 / B3：sql-workbench **不是**只读试运行，更没有 Monaco

方案原文：

> `146 E 批 sql-workbench（Monaco+try-run 只读试运行+复核驳回，376 行）`  
> `去试运行（携 SQL 跳 sql-workbench try-run 只读）`

源码事实：

- `frontend/src/views/ops/sql-workbench/index.vue` 是 **平台 `asset` schema 的受控 INSERT/UPDATE 工作台**，默认 SQL 就是 `UPDATE asset.asset_table_owners ...`，`allowed_operations: ["INSERT","UPDATE"]`，权限 `ops.sql.view`，业务源库明确只读禁止写模板。
- 全仓前端 **没有 monaco / Monaco** 依赖或引用（`frontend/package.json` 无此包）。
- 只读执行生成 SQL 的既有通道是：`POST /api/v1/ai/drafts/{id}/execute`（须 **人工批准** + `ai.sql.execute`），或查询中心对 **已登记查询版本** 的 `runQueryVersion`。都不是“把生成 SQL 丢进 sql-workbench”。

风险：执行 AI 按方案做跳转，演示会落到写库工具；权限更宽；还可能误导后续加 DML。这与用户“只读巡查 / 试试写 SQL”和仓库“AI 不接写执行器”直接冲突。

**应改为：** 写 SQL 页出口只保留复制 + `propose-sql` 存草稿；若演示必须跑数，走「存草稿 → 审核 → `drafts/{id}/execute`」或查询中心认证查询，并写明不能即席执行。不要碰 `/ops/sql-workbench`。

### P0-2 — §1 / A4：API 前缀写错，会带出一整条错误路由

方案：`/api/v1/ai-quality/patrol/...`  
实现：`backend/app/api/v1/ai_quality.py` 第 35 行 `prefix="/api/v1/quality/ai"`，前端 `asset.ts` 也走 `/api/v1/quality/ai/*`。

风险：执行者新开一套 `/ai-quality` 路由，与现网、OpenAPI、权限扫描、前端 API 全部对不上。

### P0-3 — A1：把现页结构写错，三 Tab 会毁掉已可用的分析流

方案：

> 现状「分析任务/治理简报」保留为两 Tab，新增「定期巡查」Tab

现页 `frontend/src/views/asset/ai-quality/index.vue` 实际是：

- 页头「AI 质控分析」+ 院内模型标签 + 连接测试 + **生成总览报告按钮**（不是独立 Tab）
- **左：待分析问题 / 右：分析结果**（含思考中流式 `partial_text`）
- 底：**最近分析**表

这就是用户说的“当前的 ai 质控与分析”。改成三 Tab 且误命名，等于重做信息架构，146 E3 刚补的流式轮询/Markdown/跨页勾选容易被冲掉。

**更贴需求的做法：** 保留现有左右工作台，页头加强引擎状态卡；巡查作为第三块（时间线/一键演示）叠在同页下部或次级分段，而不是把分析塞进 Tab。

### P0-4 — A3/A4：「零迁移复用 jobs/results」与表契约冲突，且同步逐表会超时

事实：

- `AiQualityResult.job_id` **一对一 unique**（`quality.py` 第 161 行）。一轮巡查多表「每表一张分析卡」不能塞进一个 job 的多条 result。
- `task_type` 在 Pydantic 里是 `Literal["finding","finding_batch","run_summary"]`（`schemas/ai_quality.py`），前端 `AiQualityJob.task_type` 同样收窄。`type=patrol` 必须改契约，不是“薄层”。
- `job_key` 由 `quality|task_type|finding_ids|run_id|digest|prompt_version` 哈希，命中即 **reuse 不重跑**。演示「再点一次立即巡查」会被静默复用旧结果。
- `GET /jobs` **不分类型**。patrol 作业会混进「最近分析」，现页会把非 `run_summary` 一律显示成「问题分析」。
- 现分析是 **后台线程 + `complete_stream` + 0.4s 刷 `partial_text` + 前端最多轮询 10 分钟**。方案改成 `POST /patrol/run` **同步逐表、单表 90s**。3–5 表墙钟可达 7.5 分钟，网关/浏览器/uvicorn 默认超时远低于此；前端也没有与现页同级的流式进度。

风险：演示当场 504；或“零迁移”做不成又临时加表/加 JSON 塞车，结果形态不稳定。

**应写清一种模型：**  
- 推荐：一轮巡查 = 多个现有 `finding`/`finding_batch` job（异步+流式），前端编排进度；用 `input_summary.patrol_run_id` 串起来。  
- 或：一轮 = 一个 job，多表结论全部进 **一条** `structured_result`。  
不要再写“零迁移 + 每表一张 result + 同步 90s”。

### P0-5 — A3：复用 `build_analysis_prompt` 会产出质控口吻，不是巡查报告

`hospital_llm_analysis.py` 的系统提示写死：「只分析当前传入的问题」「材料来自平台库」「按【结论】【问题定位】…五个标题」「不要输出 JSON」。这是 **finding 解读器**。

巡查若只喂「表名 + 注释缺失 92%」，模型仍按质控 finding 说话，和“定期巡查数据中心”的演示叙事不一致。也与 `INPUT_SCHEMA = quality-analysis-input/v1`、preview HMAC（`AQJ-` + jwt 签名）不是同一条提交链。方案的 patrol POST **绕过 preview**，等于另开一条不受现网「先 preview 再 jobs」门禁约束的 LLM 入口。

---

### P1-1 — 「根据关系写 SQL」链条在 24KB 限制下会静默截断

- `hospital_llm_max_payload_bytes = 24000`，`max_tokens = 1800`。
- `context/resolve` 默认 `max_objects=200`，DATA_CENTER 登记约 865 表；关系是 **全局** `validation_status in (validated,A,A_rechecked) LIMIT 200`，**不按所选表过滤**（`ai_context_builder.py`）。
- 方案 B2：`context resolve → hospital_llm → sql-risk-scan`。若不做「只注入选中表及其 1–2 跳邻居 + 相关值域」，模型看到的是被截断的杂烩，依据卡会显得“有关系”，JOIN 却可能乱编。

用户要的是关系驱动，不是「先手选表再生成」。手选表可以作为约束，但默认应从问题自动解析表/路径（已有 `get_path` / 表搜索工具）。

B2 还把 SQL 方言 **写死 Oracle**。目标系统选择器若切到 JHEMR（Vastbase）或 ECG（SQL Server），生成 SQL 会错方言。演示应锁死 DATA_CENTER，并禁用或隐藏其它系统。

### P1-2 — 生成 SQL 的权限、脱敏、取消都不完整

- 权限 `ai.context.read` 与 `propose-sql` 一致，任何能看上下文的角色都能打满 90s 内网模型。演示可接受，但应限流/审计；`ai_user` 默认就有该码。
- 审计写「question 脱敏 hash」，**未规定送进 LLM 的 question 必须先 `sanitize_text`**。用户可能把病案号/姓名贴进需求框。
- 「前端可取消」只取消 HTTP 客户端；现有 hospital 作业在 daemon 线程里跑完。取消后模型仍占 90s。应写明：取消=停等 UI，服务端仍计一次调用。

### P1-3 — 与 165/166「AI 探查」产品撞名、撞菜单

165 是夜间受控连接器探源入库；166 要做 `/probe-findings` 展示。本方案再做一个叫「定期巡查」的 AI 页，都挂质量/AI 域。

用户这次要的是 **演示界面**，165 要的是 **真探源**。方案 §7 把 live 采样放等待域是对的，但 **未声明命名与菜单差异**（例如「质控 AI 演示巡查」vs「探查发现」）。后续两个 AI 都会改 `ai-quality` / 菜单 / 55 号登记，窗不互斥就会互相覆盖。

### P1-4 — 「固定问题表」依赖隔离库现跑质量规则，生产演示无保证

H2/S1：在隔离库跑质量规则，选 top 问题表写入 `ai_patrol_targets.json`。

平台规则如 `COL_NULL_COMMENT` 确实只扫平台库元数据、不连 HIS，隔离库 **可以** 产出 finding。但：

- 演示若在 8.83，json 里的表必须是生产元数据里也有、且问题标签仍成立的表；
- 现质控页 `getQualityFindings` **未按系统过滤**，DATA_CENTER 问题可能被其它系统淹没；
- 方案写「注释缺失 92%」类标签，必须来自真实聚合，不能手填演出数字（否则和“证明在应用”相反）。

### P1-5 — 离线回放 vs「证明当前在应用」

A3 离线回放对演示防翻车有用，但用户原话是证明 **正在用内网模型**。若现场 LLM 超时就自动播上次结果，观众看到的是缓存。

必须：默认走 live；回放要全屏醒目标「离线回放」；状态卡的「最近成功时间 / 累计次数」必须来自真实 `GovernAuditLog`/`AiQualityJob`，不能用回放刷次数。

### P1-6 — A 其实可以几乎不写新后端

现成链路已经是：勾选 QualityFinding → preview → jobs → hospital_llm 流式分析。演示「固定一张 DATA_CENTER 问题表」= 前端预勾该表 findings + 一键调用现有 `createAiQualityJob`。

新 `ai_patrol_service` + 3 端点对演示不是必需，却引入 P0-4/P0-5。若坚持新端点，须把契约写成现网 `/api/v1/quality/ai` 的扩展，而不是平行 API。

### P1-7 — 执行规格达不到「交给别的 AI」的密度

对比 165/166 定稿：本方案没有 STOP 白名单、没有逐文件变更表、没有 OpenAPI 示例、没有 `RESOURCE_CATALOG`/security_audit 必改项、没有 checkpoint 文件格式。S5「gzip 全绿」在引入 Monaco 时会炸（主包预算见 `check-bundle-budget.mjs`）；即使不用 Monaco，新页也必须 **异步 chunk**，方案未写。

「组件测试每页 ≥4」：本仓页面测试多数是读源码字符串断言（`plan146StageE.test.ts`），不是挂载 Vue。执行者若去写 `@vue/test-utils` 满页测试，会和现风格冲突且拖时间。

### P1-8 — 导航与「在一起」

B 放独立页符合「还有就是加个界面」。路径应是 `/asset/ai-sql`（或挂在 `/asset/ai-tools` 里一块「写 SQL」），不要 `/ai/ai-sql`。菜单与质控页互链（质控页按钮「去写 SQL」、写 SQL 页返回质控）才能算“在一起”。

### P1-9 — 生成历史 / 累计次数与零迁移

B1「底部本人生成历史」无新表。可复用 `AiToolCall`（`ai.py` 已有），须规定 `tool_name`、只返回本人、question 不存明文。A2「累计调用次数」若扫全表审计，会把连接测试、失败、开发重试算进去，演示数字会难看。应定义为：`module=quality_ai` 且 `action=succeeded` 的次数，并与巡查/分析分列。

### P1-10 — 美观度方案偏空，且可能回归

现页已有 RePageHeader、状态标签、双栏、流式 Markdown。§5 只点组件名，没有：1280 下双栏是否折叠、巡查与分析抢纵向空间、一键演示主按钮别压过「分析所选问题」。用户点名「好看直观」，执行者没有可验收的视觉基准（截图对照/间距/主路径三步）。

---

## 独立结论

1. **需求覆盖：约 70%。** 两块界面、内网模型、DATA_CENTER 演示、换模型不改 UI、只读、不执行生成 SQL——这些读懂了。缺口是：定期的用户语义、演示环境、写 SQL 的真实试跑能力、现页优化而非重做。
2. **不可执行的主因是底座不实，不是文笔不够。** 错路由前缀、错把 sql-workbench 当只读 Monaco、错把现页当成两 Tab、错以为 jobs/results 能零迁移扛多表同步巡查。
3. **安全上方案意图对，出口选错。** H3/H5/§7 的只读边界成立；一旦按 B1 跳 sql-workbench，只读故事破功。
4. **建议修订后再开发（仍可很小）：**
   - A：保留现双栏分析；加引擎状态卡（模型/脱敏主机/最近成功/连接测试，status 已有 `last_success_at` 可扩次数）；「一键演示」= 预置 DATA_CENTER 问题表 findings → **复用现有异步 jobs + 流式**；目标集 json 锁定 1 张（最多 3 张）在生产元数据也成立的表；LLM 失败则明确失败，回放必须大字标注。
   - B：新页 `/asset/ai-sql`；生成链 context（**按选中表+邻居裁剪**，锁 DATA_CENTER/Oracle）→ hospital_llm → sql-risk-scan；出口=复制+存草稿；**删除 sql-workbench 跳转和 Monaco 必选项**（textarea + 语法高亮即可，或独立异步编辑器且不进主包）。
   - 补：真实 API 前缀、作业模型、权限仍用现码并改 security_audit、question 进模型前脱敏、与 165/166 命名和文件窗互斥、演示在 8.83 还是本机由用户拍板。
5. **H1（不做 cron）我同意**，但界面文案应叫「只读巡查（演示）」而不是暗示已有定时任务。

未改任何文件。本结论只依据方案原文与当前仓库实现，不采信方案 §1「禁止重探」里的底座表。
