# AGENTS.md

> 本仓包含**可运行代码**（`backend/` FastAPI、`frontend/` Vue3、`deploy/`）与**文档资产**（`开发起步包/`、`数据资产_*/`、`tools/`）。
> 启动阅读顺序：`INDEX.md` → 本文件 → `开发起步包/README.md`（唯一目录）与 `55_系统未完成事项统一执行计划.md`（唯一未完成入口）的**相关切片**；按需读 `02`/`40`。禁整读大文件或重复读取已读未变文件。

### 启动阅读与时效

- `INDEX.md` 只指路；本文件管统一规则；`README.md` 管目录；`55` 管未完成入口，旧总览与 `_archive/` 不作当前依据。
- 目标未明确前禁自动连库、扫全库或生产动作；已收口批次刷新 `checkpoint` 禁将完成态与旧卡点并存，缺证据标“待核实”。
- 分类归档依 `204`，只读再探索依 `205`（定源/窗口/范围/通道与超时）；编号正文保稳定路径，有引用/替代/哈希依据才归档。

## 1. 核心原则

- 全程简体中文；代码、命令、路径、原始错误日志保持原样，专有名词可保留英文。
- 先明确用户真正想完成什么再行动；判断基于代码、配置、日志、文档或命令结果，不靠猜测。
- 最小充分交付：只做当前任务，不扩范围、不顺手优化、不为未来需求预建能力；存在更简单方案时先指出。
- 不创建无必要的文件、流程、Agent、脚本或自动化；本文件及专项规范优先，达标且证据充分即止。

## 2. 执行、自主与批准边界

### 自主执行与澄清

- 需求明确且风险低：按「分析 → 执行 → 验证」完成范围内可逆编辑、静态检查与匹配测试，不在阶段间重复请示。
- 仅当歧义改变业务目标、数据粒度/安全、范围、交付形式或授权边界且无法推断时提问；多解时列出选项及影响。
- 复杂或高风险任务最多给 3 步计划；小任务直接执行。涉及现有项目先读最新相关文件，不做无边界全仓扫描。
- 局部依赖缺失时只停依赖步骤，继续独立工作并注明受阻项与恢复条件；禁改用生产库、降校验、猜字段或扩范围绕过。
- 未回复不构成批准；缺失项标“待输入/待批准”，禁作完成或永久跳过。可选偏好说明默认值后即时采用，交付注明可调。
- **交付完整性**：数字须对应实际查询或注明出处（如“厂商台账”）；交付 SQL 须为实测文本或去注释副本，未重跑标“未执行”；禁推算补齐数字。

### 明确批准红线（零扩权）

以下动作**必须**取得本次具体对象与范围的逐例明确授权（详细需求≠已授权高风险操作，历史一次性授权不得自动沿用；本会话等价授权不重复索取）：

1. 业务源库写入（须经 `asset_action_executors` 白名单与审批，禁临时直连写脚本）；
2. 生产平台 apply、迁移、发布、权限/cron/env 或运行配置调整；
3. 关系、值域（`confirm`）、查询/指标/数据产品的人工治理终态；
4. 删除核心文件、破坏性库/配置变更、引新外部依赖、高风险 Git（`push`/`tag`/强推等）；
5. 生产或真实敏感数据大规模动用、外部付费/第三方服务、显著扩范围。

### 安全红线与查询通道

- 业务源库仅只读 `SELECT`/只读 CTE，禁 DML/DDL/建视图/锁/过程；凭据与敏感明细（姓名/身份证/电话/地址）禁入代码、AI、日志或 Git，交付前脱敏。
- **批量探查**：无具体业务目的普查、无键跨表扫或单次预计扫 >1000 万行大表，限**夜间窗口**并设超时；离线/静态检查不限时段。
- **白天定向查询**：业务源库（ODS 见下）白天 live 查询若用户已写明目标系统与查询目的，即视为已授权该范围限量定量查询（单条 SELECT/WITH、按业务键或时间窗收窄、走受控连接器、超时 ≤120s、巨表按键限），可直接执行；泛化目标只备 SQL/范围/超时并问时段批准。
- **五要素任务级判断**：源、范围、时段、通道与既有批准一致时，同任务内增改 SQL 由原批准覆盖；换源/换通道/超窗/升级普查须重批。
- **通道① vs 通道②**：`/api/v1/ai` 草稿人工审批仅属通道①留痕流程；日常只读核对默认走通道②（`sjzc`/8.83 容器连接器），免草稿审批但保持时段/只读/大表/脱敏门禁。
- **ODS 只读例外（2026-10-21）**：`ods_8_216`（`10.10.8.216:1521/orcl`）为数据仓库，用户任务范围内免按白天窗反复申批，可直走受控连接器只读核查，留对象/范围/超时与脱敏回执；不外推 HIS 业务库、DBLINK 或写操作。

## 3. 多 AI 协作与防撞机制

- 全 AI 工具与模型共用本文件规则（`204 §8`），不按模型另设启动文件。
- **编辑前双检**：改文件前必先跑 `python tools/ai_handoff.py status` 与 `git status --short`，用 `claim` 登记范围（长任务 `heartbeat`，交付 `release`）；审阅不占位，扩范围先补登记。
- **保护他人成果**：禁覆盖他人未提交改动（含 `output_r215/` 成果），禁未授权改动 `tools/dev_env.sh` 13 个保护文件；过期占用亦须核实交接证据，禁强占。
- **单一整合者**：无其他活跃会话时当前会话即整合者，由其统一更新共享入口；子任务交接写原任务 `run` 目录，沿用原 `checkpoint`，禁另建平行进度表。

## 4. 技能与数据查询统一路由

查数据、查表结构、执行/验证 SQL **禁新建直连或索要密码**，统一走 `sjzc` 与受控通道（平台 API 或 8.83 容器 `/etc/data-asset/credentials/` 37+ 只读源，禁打印凭据内容；连接细节见 `开发起步包/216_数据库连接说明_AI工具与项目通用.md`）。

| 场景 | 必读技能 / 入口 | 边界 |
|---|---|---|
| 系统清单、连库、表结构与临时核验 | `~/.zcode/skills/sjzc/SKILL.md` | 系统明确直查该系统；平台元数据优先，不可用回退同系统快照注日期 |
| 日常取数、保存/复用 SQL、`queryctl`、指标 | `.agents/skills/query-governance-intake/SKILL.md` + `取数/START_HERE.md` | 检索查询资产为主；源明确再叠加下方 SQL 技能 |
| 历史 SQL 解析 JOIN 与关系沉淀 | `.agents/skills/sql-relation-intake/SKILL.md` | 只出可审核候选与只读验证，未经审核不改正式关系 |
| 源端只读 SQL 编写（按物理源） | `.agents/skills/{ods,hisuser,mobile-nursing,docare-anesthesia}-readonly-sql/SKILL.md` | 补对应方言、主键与业务约束；禁抄录覆盖本文件 |
| HIS 日常运维故障排查 | `F:\python\Wx_ltjl\docs\知识库\HIS日常问题处理知识库.md` + `开发起步包/HIS问题表映射.csv` | 查库走 `sjzc` 只读；涉写操作仍须逐例审批 |
| 生产发布、夜跑核验、受控修复 | `.agents/skills/ops-runbook/SKILL.md` | 仅提供标准运维与踩坑，发布与写库仍须点名授权 |
| 跨会话断点续跑 / 接手编号计划 | `.agents/skills/project-task-resume/SKILL.md` | 四步恢复，不建平行总表，不沿用历史授权 |

- **三甲独立工作区（2026-11-04 起）**：`88`/`189`/`191`/`195`/`218`×4、`output_r189`、exports《23》已迁至 `E:\三甲复审\6、数管中心三甲数据上报\三甲复审数据接口规范+值域2.3`（启动先读 `governance\视图核查与抽取总控.md`），不从本仓启动；同守只读与脱敏红线。
- **三仓库互通（L1）**：本仓（数据连接）+ `F:\python\Wx_ltjl`（运维/聊天）+ `D:\Users\Administrator\Desktop\嘉和`（嘉和逆向）；跨仓细节读 `三仓库互通地图.md`。

## 探库/写 SQL 时的硬约束

1. **跳板与公钥**：Windows 不直连业务源库，走 8.83 受控连接器（SSH 公钥 `id_ed25519_ai`，见 `48`/`216`），禁将 SSH/库密码写入命令、代码或日志。
2. **Oracle 11g 兼容**：`oracledb` 须 thick 模式 + `/opt/oracle/instantclient_21`；禁用 `FETCH FIRST`，限量外层包 `ROWNUM <= N`。
3. **`HIS.LAB_RESULT` 约 1 亿行**：定向查必须按 `TEST_NO` 等业务键收窄；批量普查 >1000 万行表只采元数据，上限不替代范围控制。
4. **`HIS.OPERATION.OPER_ID` 全为 NULL**：手术主从关联改用 `SM.MED_OPERATION_NAME`。
5. **`HIS.EXAM_MASTER.EXAM_CLASS` 存中文**：按 `'CT'`/`'磁共振'` 中文过滤，勿 join 字典码。
6. **字段值域禁猜测（149 强制）**：编码/状态/类型/阈值字段依次查平台 `GET /api/v1/ai/system-context` `value_domains` → `开发起步包/数据资产_资产包/value_domains.json`（超 `max_age_days=7` 提示重导）→ `开发起步包/148_病案首页关键值域与离院方式口径字典.md`；均无标 `【值域待确认：…】`（已授权范围可用 `GROUP BY` 计数补证“实测候选值域”，不自动 confirm）。关键口径：
   - 离院方式 `PAT_VISIT.DISCHARGE_DISPOSITION`：4=非医嘱离院、5=死亡（2025-04 前老系统 3=死亡/5=自愿，2025-05 起 5=死亡；勿混 `COMM.DISCHARGE_DISPOSITION_DICT` 治疗结果字典；`DEATH_DATE_TIME` 源端不填）。
   - 手术急诊标志 `OPERATION.OPERATION_EMER_INDICATOR`：2=急诊手术（1=择期）。
   - 病理在 ODS `BL` schema；门诊疾病谱用 `OUTPDOCT.OUTP_MR_DIAG_DESC`；麻醉台数用 `MED_OPERATION_MASTER`+`OPER_STATUS>=35`。
7. **`EXAM_REPORT` 无 `PATIENT_ID`**：必须经 `EXAM_NO` 关联 `EXAM_MASTER`。
8. **HIS 万能主键**：`PATIENT_ID + VISIT_ID`（住院）/ `OUTPATIENT_NUM`（门诊）；检验 `TEST_NO`、检查 `EXAM_NO`。
9. **跨库 DBLINK**：前置机已建 `sjzx` 指向 ODS，可 `SELECT ... FROM V_EMR_xxx@sjzx`。

## 值域映射模式

- `V_EMR_*` 通过 `CDA.CDA_DICTIONARY` 映射：`nvl((SELECT zd.国标编码 FROM cda.cda_dictionary zd WHERE zd.字典名称='性别代码' AND zd.院内编码=pmi.sex), '9')`。
- 固定机构字段：`'49557032X' AS ORG_CODE`、`'山东省第二人民医院' AS ORG_NAME`、`'370104' AS DISTRICT_CODE`；ID = `'49557032X'||'|'||patient_id||'|'||visit_id`。（`YLV21051` 已过期勿用。）
- 已知数据坑（`02` §5）：`EMR_ANES_AFTER_RECORD` ID 重复 ~30%；`EMR_OUTPATIENT_RECIPE_ITEM.OR_ID` 100% 孤儿；`EMR_OUTPATIENT_DIAG` 0 行；4 表缺 `ADMISSION_ID`。

## 5. 取数导出、交付口气与文档维护

- **导出目录**：执行器导出放仓库外受控目录；可交付脱敏结果与 SQL 归集至 `取数/exports/<序号、任务名>/`（最大序号 +1，中文命名、文件头注数据源与口径、核 gitignore、清理/合并中间 SQL）。
- **交付口气（2026-10-13）**：按同事交接写完整句子，写清时间/系统/科室/条数/排除与空列原因；禁 AI 腔与假署名；`query_code`/`run_id`/哈希仅放 SQL 头或内部备注。导出保留模板列，用户明示指定的列优先。
- **文档维护（仅编辑 `开发起步包/` 时执行）**：改前只读检查 `python tools/check_doc_index.py`（审阅只报告）；新增 4 步：`register_doc.py` 取号 → 首行 `> 类别：` → 登记 README → 记更新记录；废弃只迁 `_archive/` 不删，双向记录并核零引用。
- **新建文件与用户文书自动规范（所有 AI 强制）**：
  - 开发新建文件禁堆仓库根（临时脚本→`_scratch/`、构建/离线包→`artifacts/`、后端探查→`backend/scripts/`，禁平行总表）。
  - 用户在根目录、`开发起步包/` 或任务目录新放入文书/需求/表格（`.md`/`.xlsx`/`.docx`/`.pdf`）交 AI 处理时，主任务顺带整理：① **归位**：取数→`取数/exports/<序号+1、中文任务名>/`，开发文档→`开发起步包/`（`register_doc.py` 取号 `NN_中文.md`），草稿→`_scratch/`，外部原件留原样并在 README 注出处；② **规范**：Markdown 补 `> 类别：` 与日期/来源/状态、去 AI 腔、脱敏凭据明细，数据/SQL 注数据源与口径；③ **登记**：同步 `README.md` 及「目录更新记录」并跑 `check_doc_index.py`（0E0W）。**红线**：原件保留不删，旧版只迁 `_archive/`，不动无关历史文件。

## 6. 代码修改、验证、阻塞与回复

- **编码**：只改明确需求，不扩边界/不覆盖他人改动/禁过度封装 wrapper，复用既有实现与标准库，引新依赖先确认；修错先定位根因，留既有注释。
  - **后端**（`backend/AGENTS.md`）：`asset` 单 schema + `asset_<模块>_<实体>`；留 4 旧 MVP 表；Alembic 手写禁 autogenerate；AI 工具仅调只读端点+审计，禁接 `asset_action_executors`。
  - **前端**（`frontend/AGENTS.md`）：`pure-admin-thin` + Vue3 + TS；**必用 pnpm**；留既有路径（`/relations/{id}/review`、`/dict-medical/*`）；`typecheck` 过 `tsc --noEmit` 与 `vue-tsc`。
- **验证与阻塞**：按影响选最小验证，只修本轮引入失败，禁改断言绕过；连续 3 次同类失败或 ~30 秒无进展立即停手报阻塞。根级 `pytest` 会 `TRUNCATE`，运行前核清在跑进程与 `APP_TEST_DB_URL=data_asset_test`。常用验证：`.venv\Scripts\python.exe -m pytest tests/ -q`、`python tools/check_migrations_tracked.py`、`pnpm run typecheck && pnpm run build && pnpm exec vitest run`。
- **回复格式**：结论先行、简洁直白，仅陈述本轮实测输出或已读文件事实；修改、风险、未验及受阻项分节列清。
