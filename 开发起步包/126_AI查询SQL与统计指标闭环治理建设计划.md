> 类别：模块规划
>
> 状态：P1–P5 最小闭环已生产；head `h5c6d7e8f9a0`；镜像 `data-asset:126p5-20260811223311`；全局调度开关已开、单条调度 27 全关；21 条占位已回写官方名称
> 接手交接：`128_126号查询指标闭环完成情况与接手交接.md`
>
> 制定日期：2026-08-11
>
> 上位入口：`55_系统未完成事项统一执行计划.md`
>
> 关联规范：`87_AI视图SQL生成与平台对接说明.md`、`.agents/skills/sql-relation-intake/SKILL.md`、`.agents/skills/query-governance-intake/SKILL.md`

# AI 查询 SQL 与统计指标闭环治理建设计划

## 0. 本计划的定位

本计划用于把日常通过不同 AI 完成的 SQL 查询，从“散落在聊天、临时文件和个人经验中”，逐步转为平台可查询、可复用、可修订、可追溯的查询资产和指标资产。

本文件目前只用于需求确认、架构规划和后续开发拆解：

- 本轮不修改后端、前端或数据库；
- 不创建本地查询工作区；
- 不执行平台迁移、生产发布或调度变更；
- 不执行任何业务源库 DML/DDL；
- 用户复核确认后，再按本文阶段逐项开发；
- 后续开发由其他 AI 按阶段执行边界明确的实现任务，当前主 AI 负责架构约束、代码复核、测试和收口；不绑定具体模型。

## 1. 用户需求登记

### 1.1 当前直接需求

1. 用户经常通过不同 AI 查询数据，希望每次查询使用的 SQL、统计指标、查询说明和结果能够自动记录到数据资产系统。
2. 已记录的 SQL 和指标应支持以后再次提取，不必让不同 AI 从头分析和重复编写。
3. 不同 AI 应能读取同一套当前资产、现行口径、历史版本和已知限制，用于继续分析或修订。
4. 指标口径必须支持修订；修订后不能直接覆盖历史内容，应能够查看版本、差异、启用时间和历史结果。
5. 常见工作方式是“本机电脑连接外网 AI，再通过本机或跳板能力访问内网服务器”，因此希望本地固定一个查询文件夹，供不同 AI 使用同一套输入、输出和交接规范。
6. 希望把平常 SQL 查询逐步形成闭环，服务于数据提取、数据应用、数据质量、关系治理、口径治理和资产管理，而不是只保存一份 SQL 文件。
7. 不同 AI 执行查询时，也必须遵循统一规划和处理要求，不能依赖某次聊天记忆。

### 1.2 中长期愿景

1. 后续增加闭环管理、查询结果展现和指标看板。
2. 平台成为统一的数据出口、AI 出口和数据来源对接入口。
3. 将查询逻辑、指标口径、元数据、关系、结果和服务接口掌握在医院自己的平台中，逐步降低对单一厂商报表、接口和人员经验的依赖。
4. 长期支持 AI、人员和业务应用从同一权威入口获取数据，不再各自维护一套 SQL 和口径。

### 1.3 本计划对需求的核心判断

- 该需求可以直接融入当前系统，不需要另建一套孤立应用。
- “SQL 查询资产”和“统计指标资产”必须分开建模：一个指标可能由多个 SQL 组成，一个 SQL 也可能服务多个指标。
- 本地固定文件夹适合作为跨 AI 的暂存、交换和离线队列，但不能作为最终权威库。
- 真正的“自动记录每次查询”必须经过统一只读执行入口；只监听文件夹只能证明文件出现过，不能证明 SQL 是否执行、执行了哪个版本和参数。
- 长期统一出口应只开放已发布、参数受控的查询或指标，不能建设成任意 SQL 公共执行接口。

## 2. 当前系统已有基础与复用边界

| 当前能力 | 现有实现 | 本计划处理方式 |
|---|---|---|
| AI 会话与工具调用审计 | `asset_ai_sessions`、`asset_ai_tool_calls` | 继续复用，记录 AI 来源、会话和摄取动作；不把完整聊天或敏感数据写入平台 |
| SQL 草稿 | `asset_view_drafts`、`/api/v1/ai/propose-sql` | 保留为接入暂存层；通过门禁后提升为正式查询资产版本 |
| SQL 风险扫描 | `/api/v1/ai/sql-risk-scan` | 扩展确定性解析、方言、大表、敏感字段和参数化检查 |
| 现有“审核后只读试运行” | `/api/v1/ai/drafts/{id}/execute`、只读连接器 | 复用连接器和只读保护，但 P1 改为自动门禁通过后直接运行，不保留人工确认要求；新增独立运行记录，结果内容按配置选择不保存或只保存小型结果 |
| 关系配方版本 | `asset_relation_recipes` | 继续作为 JOIN 和关系口径知识库；查询版本通过编号、版本、哈希引用，不复制一套关系真相 |
| AI 上下文 | `system-context`、`export-context`、`recipes/ai/context` | 扩展查询资产、指标资产和结果摘要上下文，供不同 AI 获取当前版本 |
| 治理审计 | `asset_govern_audit_logs` | 复用状态变更、激活、停用、执行和结果发布审计 |
| SQL 工作台 | 当前 `ops/sql-workbench` 主要用于受控平台 DML | 不改造成查询库，避免只读查询与高风险写工作台混在一起 |
| 质量指标 | `asset_quality_metrics` | 继续表示数据质量检测结果；不得与业务统计指标混用 |

### 2.1 当前缺口

1. `asset_view_drafts` 是单行可变草稿，没有稳定查询编码、版本链、方言、参数结构、表字段依赖和生效期。
2. 当前只读执行主要返回临时统计或脱敏样本，没有完整保存“查询版本 + 参数 + 执行时间 + 数据源 + 结果哈希 + 结果状态”。
3. 缺少业务指标主档、分子分母口径、时间字段、统计粒度、版本生效期和历史结果。
4. 缺少本地固定工作区、文件清单、离线队列、幂等同步和隔离区。
5. 现有 AI 规范主要解决“如何生成视图 SELECT”，尚未覆盖查询自动摄取、指标版本修订、结果复用和数据产品发布。
6. SQL 中解析出的关系还不能自动形成“候选关系证据 → 元数据核对 → 审核 → 正式关系/配方”的完整联动。
7. 缺少从表/字段变化追踪到查询、指标、结果和数据服务的影响分析。

## 3. 总体建设原则

1. **平台是唯一事实源**：本地文件是缓存和交接，不是最终权威版本。
2. **定义与运行分离**：查询定义、查询版本、执行批次、执行结果分别管理。
3. **查询与指标分离**：SQL 是实现，指标是业务语义；两者通过版本引用关联。
4. **发布版本不可变**：已生效版本不直接修改；修订必须复制新版本并保留差异。
5. **参数不制造版本**：只改变月份、科室等运行参数，不创建新 SQL 版本；业务逻辑或 SQL 变化才创建版本。
6. **SQL 必存、结果可选**：查询 SQL、口径和版本必须保存；查询结果默认可以不保存。确有复用需要时只保存小型汇总结果，患者级明细不进入外网 AI、日志或普通结果库。
7. **关系先作为证据**：历史 SQL 中的 JOIN 只能作为关系证据或配方候选，未经核查不得自动发布为正式关系。
8. **源库始终只读**：查询入口只允许单条 SELECT/只读 CTE，不允许 DML、DDL、存储过程和锁表。
9. **跨物理数据源不伪装直连**：无法直接跨库执行时拆成多个查询及平台汇聚步骤。
10. **开放格式避免锁定**：SQL、YAML、JSON、CSV 和 REST/MCP 为主要交换格式，不把核心口径锁在某个 AI 或厂商专有格式中。
11. **自动入库仍须自动门禁**：普通查询通过确定性安全、元数据和关系门禁后直接保存并成为默认现行版本，不要求管理员单击确认；未通过门禁的查询进入 candidate/blocked，不得伪装为现行口径。

## 4. 目标架构

```text
外网 AI / 本机 AI / 人工 SQL
              |
              v
F:\python\数据资产\取数
  context / inbox / working / outbox / synced / quarantine
              |
              | queryctl 校验、脱敏、指纹、离线排队
              v
数据资产平台 AI 查询摄取接口
              |
       +------+------------------+
       |                         |
       v                         v
查询资产库与版本链          关系/配方候选摄取
       |                         |
       v                         v
统一只读执行器             元数据核对与关系审核
       |
       v
运行记录与可选小型结果
       |
       +-------------> 指标定义与指标版本
                              |
                              v
                    查询复用 / 月报 / 看板 / API
                              |
                              v
                 人员、AI、应用的统一数据出口
```

### 4.1 三个统一出口

| 使用方 | 统一出口 | 返回内容 |
|---|---|---|
| 不同 AI | REST/MCP、本地脱敏 context 包或受控只读连接 | 当前查询/指标版本、参数、SQL、表字段、关系配方和限制；结果摘要仅在选择保存时返回 |
| 人员 | 查询与指标中心页面 | 搜索、版本差异、运行历史、月度结果、导出和影响分析 |
| 业务应用 | 数据产品 API | 仅已生效、参数白名单、权限受控、可缓存的查询或指标结果 |

## 5. 核心业务对象

### 5.1 查询定义 Query Definition

稳定表示“要解决什么查询问题”，建议最少包含：

- `query_code`：稳定编码，例如 `QRY_EMR_PREOP_DISCUSSION_RATE`；
- 中文名称、业务目的、业务域；
- 所属业务系统、数据连接、数据库、Schema/Owner；
- 负责人/维护人；
- 数据敏感等级；
- 当前生效版本；
- 是否允许 AI 读取、是否允许计划任务、是否允许数据服务发布。

### 5.2 查询版本 Query Version

不可变保存某次具体口径和 SQL：

- 版本号、父版本、版本状态、生效起止时间；
- 原始 SQL、规范化 SQL、SQL SHA-256、语义指纹；
- 数据库方言；
- 参数定义、输出字段结构和统计粒度；
- 使用的表、字段和关系；
- 关系配方 `recipe_id/version/content_hash`；
- 时间口径、纳入条件、排除条件、去重逻辑；
- 已知限制、无法提取项、风险标记；
- 修订原因、与上一版本的 SQL/口径差异；
- 来源文件、AI 来源、会话编号和摄取时间。

### 5.3 查询运行 Query Run

表示某版本的一次真实执行：

- 固定引用 `query_code + version`；
- 数据连接、数据库方言和连接资产版本；
- 参数值的脱敏副本和参数哈希；
- 计划/开始/结束时间、耗时、状态；
- 执行人或 AI 会话、相关 ID；
- 返回行数、是否截断、警告、错误分类；
- SQL 版本哈希、结果哈希、数据截至时间；
- 验证范围：全量、受限全量或样本。

### 5.4 查询结果 Query Result（可选）

- 查询运行必须留存版本、参数哈希、来源、时间和状态，但结果内容默认可以不保存；
- 每次运行使用 `result_storage=none|summary|file_ref` 明确结果策略，默认 `none`；
- 选择 `summary` 时，只保存小型分子、分母、指标值、状态等 JSONB/结构化结果；
- 选择 `file_ref` 时，只允许小文件，并保存受控文件引用、SHA-256、格式、大小、保留期限和权限；
- 大文件和患者级结果不纳入首期；不得同步给外网 AI；
- 即使不保存结果内容，也可保存结果哈希、返回行数和是否截断，用于重复运行和审计判断。

### 5.5 指标定义 Metric Definition

稳定表示业务指标：

- `metric_code`、指标名称、业务分类、责任部门；
- 指标含义、单位、频率、统计粒度；
- 当前版本和状态；
- 是否有分子、分母、计算公式；
- 是否允许看板展示、导出或 API 服务。

### 5.6 指标版本 Metric Version

- 指标定义文本；
- 分子、分母、计算公式；
- 对应查询版本，可以是一个查询，也可以分别引用分子/分母查询；
- 统计时间字段、纳入/排除、去重和空值口径；
- 适用组织和业务系统；
- 生效起止时间、修订原因和差异说明；
- 已知限制与“只能提取分母”等可理解的中文状态说明；
- 当前版本只允许一个处于 active。

### 5.7 指标结果 Metric Result

- 指标结果内容为可选能力；首期允许只保存指标定义、口径版本和对应 SQL；
- 指标版本、统计周期、维度、分子、分母、指标值；
- 对应查询运行 ID；
- 结果状态、质量状态、数据截至时间；
- 是否重算、重算原因、上一结果差异；
- 结果发布后不可原地覆盖，修订或重算形成新批次并保留旧记录。

## 6. 建议数据模型

所有新表继续位于 `asset` schema，并遵守 `asset_<模块>_<实体>` 前缀。

| 建议表 | 用途 | 关键约束 |
|---|---|---|
| `asset_query_definitions` | 查询主档 | `query_code` 唯一，指向唯一现行版本 |
| `asset_query_versions` | SQL 与口径版本 | `(query_id, version)` 唯一；active 后内容不可改；保存哈希和父版本 |
| `asset_query_dependencies` | 表、字段、关系、配方依赖 | 依赖类型明确；关系候选不冒充正式关系 |
| `asset_query_runs` | 每次执行记录 | 固定查询版本、参数哈希、数据源和运行状态 |
| `asset_query_results` | 可选小型结果或文件引用 | 允许不保存结果内容；保存时记录策略、结果哈希、敏感级别、保留期和是否截断 |
| `asset_metric_definitions` | 指标主档 | `metric_code` 唯一，指向唯一现行版本 |
| `asset_metric_versions` | 指标口径版本 | 分子/分母/公式与查询版本固定引用 |
| `asset_metric_results` | 可选周期指标结果 | 只有启用结果保存时写入；`(metric_version, period, dimensions, run_batch)` 可追溯 |

继续复用而不重复建模：

- `asset_ai_sessions`、`asset_ai_tool_calls`：AI 会话与调用审计；
- `asset_view_drafts`：外部 AI 和本地工作区的草稿暂存；
- `asset_relation_recipes`：可复用关系配方；
- `asset_govern_audit_logs`：治理操作审计；
- `asset_systems`、`asset_data_sources`、`asset_tables`、`asset_columns`、`asset_relations`：系统、连接、表、字段和关系权威资产。

不得复用：

- `asset_ops_tool_templates`：它是受控运维写模板，不应承载日常 SELECT 查询；
- `asset_quality_metrics`：它是数据质量指标，不应混入业务统计指标结果。

## 7. 本地固定查询工作区规划

### 7.1 建议位置

用户已确认直接使用现有 `取数` 目录作为固定根目录：

```text
F:\python\数据资产\取数\
```

现有 `取数\48项目核心制度`、`取数\exports` 等目录先保留，不自动移动。后续可通过一次性导入工具，将历史 SQL 作为来源证据摄取。

### 7.2 目录结构

```text
取数/
├─ START_HERE.md              # 所有 AI 必读规则
├─ _query_templates/          # query.yaml、SQL、说明和可选结果模板
├─ _query_context/            # 从平台导出的脱敏当前上下文
├─ _query_inbox/              # AI 或人工新提交的查询包
├─ _query_working/            # 正在修改、尚未提交的查询包
├─ _query_outbox/             # 已校验、等待同步到内网平台
├─ _query_synced/             # 已同步并带平台 query/version/run ID
├─ _query_quarantine/         # 风险、敏感、结构错误或无法解析的包
├─ _query_results/            # 可选小型结果，默认不保存结果内容
├─ .query_state/              # 文件哈希、同步游标和锁，不供 AI 手改
├─ 48项目核心制度/            # 现有项目目录，保留
└─ exports/                   # 现有导出目录，保留
```

运行目录、结果和上下文缓存在实施时加入 `.gitignore`；只有模板、规则和 JSON Schema 可以进入 Git。

### 7.3 单个查询包

```text
QRY-20260811-0001/
├─ query.yaml
├─ query.sql
├─ result.csv                 # 可选；默认不生成，只允许小型结果
├─ explanation.md
└─ evidence.json
```

`query.yaml` 最少字段：

```yaml
query_code: QRY_EXAMPLE
title: 示例查询
purpose: 业务用途
system_code: DATA_CENTER
source_code: ods_8_216
dialect: oracle
status: captured
period_field: HIS.PAT_VISIT.DISCHARGE_DATE_TIME
grain: month
parameters:
  start_date: date
  end_date: date
metric_refs: []
recipe_refs: []
sensitivity: aggregate
limitations: []
ai_source:
  provider: unknown
  model: unknown
  session_ref: local-only
```

不得在包中出现数据库密码、Token、完整身份证、姓名、电话、地址、未脱敏患者 ID 或签名图片。

## 8. 本地工具与自动记录机制

计划新增统一命令 `queryctl`，不同 AI 不直接拼接平台接口或连接凭据。

| 命令 | 作用 |
|---|---|
| `queryctl init` | 从模板创建查询包和稳定本地编号 |
| `queryctl context` | 通过受控通道拉取脱敏系统、表、字段、关系、配方、查询和指标上下文 |
| `queryctl validate` | 检查清单、SQL 单语句、只读、方言、大表、敏感内容、字段和关系证据 |
| `queryctl submit` | 计算哈希并幂等提交平台草稿；离线时进入 outbox |
| `queryctl run` | 通过平台统一只读执行器执行并自动创建 run；按 `none/summary/file_ref` 决定是否保存结果 |
| `queryctl revise` | 从当前版本复制新草稿，要求填写修订原因和生效期 |
| `queryctl sync` | 将 outbox 与平台双向同步，回写平台 ID 和状态 |
| `queryctl export` | 为外网 AI 生成不含凭据和患者数据的上下文包 |

### 8.1 自动记录的硬边界

- 通过 `queryctl run` 或平台查询 API 执行：能够自动记录 SQL 版本、参数哈希、数据源、时间、状态和结果。
- AI 只把 SQL 文件写进 inbox：只能自动摄取为草稿，不能声称已经执行。
- AI 绕过平台直接 SSH 后运行 sqlplus/python：平台无法可靠自动发现。长期应把 AI 可用的源库访问收敛到统一只读网关，直接凭据只保留给受控运维人员。

## 9. 多 AI 统一处理流程

### 9.1 每次查询的标准闭环

```text
用户提出业务问题
  → AI 读取 START_HERE 和最新 context
  → 查找现有指标/查询，优先复用现行版本
  → 无可复用资产时创建查询包
  → 核对表字段、正式关系和现行配方
  → 生成参数化 SELECT 与中文口径说明
  → 本地 validate
  → submit 为 captured/candidate
  → 可选只读 run
  → 保存运行记录、限制和可选小型结果
  → 确认是否形成新查询资产、指标版本或关系候选
  → 自动门禁通过后设为默认现行版本，否则保留候选/阻断
  → 后续 AI 通过 context 读取
```

### 9.2 AI 强制规则

1. 开始前读取 `START_HERE.md`，不得只依赖聊天记忆。
2. 先按 `metric_code/query_code` 搜索，找到现行版本时优先复用。
3. 必须记录 `system_code/source_code/dialect`，使用系统总览的中文显示名称对人展示。
4. SQL 只能是单条 SELECT/只读 CTE，最终字段显式列出。
5. 必须记录业务目的、时间字段、统计范围、纳入、排除、去重、分子、分母、粒度和已知限制。
6. 必须引用当前关系或配方证据；同名字段不视为关系。
7. 历史 SQL 的 JOIN 先交给 `sql-relation-intake`，只形成候选或补充证据。
8. 口径变化创建新版本；只改运行月份等参数不创建版本。
9. SQL 未运行时写“未执行”，失败或不确定时写真实原因，不得伪造结果。
10. 任何患者级样本必须在内网脱敏，默认不提供给外网 AI。
11. AI 只能提交查询和运行请求；系统按自动门禁决定是否成为现行版本，AI 不能绕过门禁强制激活，也不能修改业务源库。
12. AI 可以通过平台、跳板机或仓库受控连接器对数据库执行必要的只读核查；凭据仍由受控文件或 secret provider 提供，不得写入提示词、SQL、日志或 Git。

### 9.3 计划新增技能路由

用户批准开发后，建议新增：

```text
.agents/skills/query-governance-intake/SKILL.md
```

该技能负责：

- 查询包初始化、校验、摄取和版本管理；
- 指标定义、分子分母和结果登记；
- 调用 `sql-relation-intake` 解析关系证据；
- 再按物理来源调用 ODS、HIS、移动护理或 Docare 只读 SQL 技能；
- 禁止越过平台状态和安全门禁。

根目录 `AGENTS.md` 在实施阶段补充触发规则：只要用户要求日常取数、保存 SQL、复用指标、修订口径或导入历史查询，必须优先使用该技能和 `queryctl`。

## 10. 查询与指标版本规则

### 10.1 查询状态

```text
captured → parsed → candidate → validated → active → superseded/deprecated
                         ↘ blocked
```

- `captured`：已收到本地包或 API 请求；
- `parsed`：格式、SQL 和依赖已解析；
- `candidate`：可以继续核查，但未完成验证；
- `validated`：表字段、关系、安全和只读运行已达到记录的验证范围；通过自动门禁后立即进入 active；
- `active`：自动门禁通过后形成的默认现行版本，当前推荐给人、AI 和任务使用；
- `superseded`：已被新版本替代；
- `deprecated`：不再使用但保留历史；
- `blocked`：缺字段、缺关系、跨库不可达、数据质量或安全门禁失败。

不新增管理员确认、双人审批或审批队列。系统按确定性门禁自动激活通过验证的新版本并记录来源、原因和差异；AI 不能绕过门禁强制激活。未通过门禁的版本只进入 candidate/blocked。

### 10.2 何时创建新版本

必须创建新版本：

- SQL 逻辑、JOIN、字段、时间口径、纳入/排除或去重改变；
- 分子、分母、公式、粒度或适用范围改变；
- 切换业务系统、数据连接、数据库方言或主数据源；
- 已发布限制说明发生会影响结果解释的变化。

不创建新版本：

- 只改变查询月份、科室、机构等参数值；
- 重新执行同一版本；
- 仅改变页面排序或不影响语义的展示样式；
- SQL 只有空白和无业务含义注释变化，且规范化指纹一致。

### 10.3 修订后的结果处理（仅适用于已选择保存结果）

- 旧版本和旧结果永久保留可追溯；
- 新版本可选择从生效月份开始运行，或明确发起历史重算；
- 历史重算形成新批次，不覆盖旧批次；
- 页面展示“旧值、新值、差异、修订原因、影响月份”；
- 外部 AI 默认只获取 active 版本，要求历史分析时才返回指定旧版本；外部 AI 可通过受控只读连接核查数据库，但不能获得明文凭据或写权限。

## 11. SQL 关系、元数据和治理联动

每个查询版本在摄取时执行以下只读治理步骤：

1. 解析表、字段、别名、JOIN、过滤、分组、窗口函数和输出字段；
2. 用平台当前元数据核对表字段存在性；
3. 与正式 `asset_relations` 和 active `asset_relation_recipes` 查重；
4. 按 `existing/candidate/partial/recipe_candidate/rejected` 标记 SQL 关系证据；
5. 不把历史 SQL 自动写成正式关系；
6. 如用户授权验证，再按所属源的只读技能生成限量验证 SQL；
7. 关系或字段变化时反向标记受影响查询和指标为 `needs_review`；
8. 查询验证中发现的空值、重复、孤儿和放大倍数可转成质量规则候选，但不自动启用。

最终形成以下影响链：

```text
业务系统 → 数据连接 → 表 → 字段/关系 → 查询版本 → 指标版本 → 运行结果 → 看板/API
```

## 12. 后端接口规划

具体路径在开发前以 OpenAPI 风格复核，建议能力如下：

| 能力 | 建议接口 |
|---|---|
| 查询主档搜索 | `GET /api/v1/queries` |
| 查询详情和现行版本 | `GET /api/v1/queries/{query_code}` |
| 版本列表与差异 | `GET /api/v1/queries/{query_code}/versions`、`.../diff` |
| 本地包摄取 | `POST /api/v1/query-intake/packages` |
| 查询校验 | `POST /api/v1/query-intake/validate` |
| 只读运行 | `POST /api/v1/queries/{query_code}/versions/{version}/runs` |
| 运行与可选结果 | `GET /api/v1/query-runs/{run_id}`、`.../result`；未保存结果时明确返回 `result_storage=none` |
| 查询修订 | `POST /api/v1/queries/{query_code}/versions` |
| 自动激活状态/人工停用 | 自动门禁通过后激活；`POST /api/v1/queries/{query_code}/versions/{version}/deprecate` 供受权用户停用 |
| 指标主档与版本 | `/api/v1/metrics`、`/api/v1/metrics/{metric_code}/versions` |
| 指标结果 | `GET /api/v1/metrics/{metric_code}/results` |
| AI 当前上下文 | `GET /api/v1/ai/query-context`、`GET /api/v1/ai/metric-context` |
| 脱敏离线导出 | `POST /api/v1/ai/export-query-package` |
| 影响分析 | `GET /api/v1/queries/{query_code}/impact`、`GET /api/v1/metrics/{metric_code}/lineage` |

接口不得接受任意目标主机、明文凭据或绕过登记连接的 SQL。运行必须引用平台登记的 `source_code` 和不可变查询版本。

## 13. 前端功能规划

建议新增一级业务功能“查询与指标中心”，不复用高风险运维 SQL 工作台。

### 13.1 查询资产

- 按业务系统、数据连接、业务域、状态、表、负责人和关键词搜索；
- 展示当前 SQL、参数、字段、关系配方、限制和数据截至时间；
- 版本时间线、SQL diff、口径 diff；
- 运行、复制修订、导出查询包；
- 查看表/字段/关系和下游指标影响。

### 13.2 指标口径

- 指标名称、定义、分子、分母、公式、时间字段、粒度；
- 当前版本与历史版本；
- 关联查询版本；
- 月度结果、重算批次、差异和中文状态说明；
- 支持“只能提取分母、分子病历模板未结构化无法提取”等可读限制。

### 13.3 运行记录

- 查询版本、参数摘要、来源、耗时、行数、结果状态；
- 错误分类、大表警告、是否截断、验证范围；
- 选择保存时展示小型结果预览和受控导出；默认仅显示运行元数据；
- 通过 correlation ID 串联 AI 会话、查询运行、指标结果和治理审计。

### 13.4 AI 接入箱

- inbox/outbox 同步状态；
- 重复查询识别；
- 格式错误、敏感风险、缺元数据和缺关系的隔离原因；
- 草稿提升为查询资产或指标版本；
- 不提供人工确认或 AI 强制激活按钮；展示自动门禁和自动激活结果。

### 13.5 数据服务（长期）

- 将已生效查询/指标发布为参数化数据产品；
- 提供 API 文档、权限、调用量、缓存、刷新时间和 SLA；
- 支持 CSV/Excel、看板和应用接口，但全部引用同一 active 版本。

## 14. 统一出口与降低厂商依赖的长期设计

### 14.1 能够逐步自主掌握的部分

- 系统、连接、表、字段和关系资产；
- 查询 SQL、参数、口径和版本；
- 指标定义、结果和修订历史；
- 数据质量、血缘和影响分析；
- AI 上下文和统一调用规范；
- 自建 REST/MCP、导出、看板和数据产品服务。

### 14.2 不能忽略的现实边界

- HIS、电子病历、LIS 等源系统仍可能由厂商维护，源表升级会影响查询；
- “摆脱依赖”不是绕过合法授权或直接写厂商业务库，而是把读取适配、口径和服务层掌握在本方；
- 每个源系统应通过独立连接适配器隔离，厂商升级时只调整适配器和受影响查询版本；
- 必须保留源系统许可、接口边界、变更通知和回归测试。

### 14.3 最终目标形态

平台逐步形成“医院数据产品层”：

- 上游接入各业务系统，只读获取数据；
- 中间沉淀元数据、关系、查询、指标、质量和版本；
- 下游统一服务人员、AI、报表、看板和业务应用；
- 同一个指标无论由谁调用，都能定位到同一版本、同一 SQL 和同一批结果。

## 15. 安全、隐私和合规门禁

1. 外网 AI 可以接收脱敏元数据、查询逻辑、可选小型汇总结果和必要的业务说明，也可以通过受控只读通道连接数据库进行核查；不得获得明文连接凭据或写权限。
2. 姓名、身份证、电话、地址、患者 ID、签名和病历正文不得进入外网 AI 上下文包、提示词或查询结果回传。
3. 凭据只来自服务器受控凭据文件或现有 secret provider，本地包和平台 SQL 不保存密码。
4. 查询执行器只接受登记数据连接；禁止用户提交 host、port、user、password。
5. 强制单语句 SELECT/只读 CTE；拒绝 DDL/DML、动态 SQL、存储过程、锁表和多语句。
6. Oracle 11g、HIS 大表和各源方言继续遵守仓库技能门禁。
7. 默认不保存查询结果内容；选择保存时仅允许小型结果。患者明细不纳入首期，后续如需落盘必须另行设计内网受控存储、权限和保留期。
8. 运行错误只保存脱敏摘要，不把原始连接异常中的凭据写入日志。
9. AI 会话只保存提供方、模型、会话引用和摘要，不保存完整外网对话。
10. 所有激活、停用、执行、重算、导出和服务发布都记录审计。

## 16. 分阶段实施计划

### 阶段 P0：用户复核与边界确认

本计划即 P0 交付。用户已补充第 20 节 Q1–Q8，当前只等待用户对修订后的完整计划做最终复核并明确是否开始开发。

完成判定：

- 需求范围、术语和统一出口方向获得确认；
- 本地工作区位置已确认使用 `F:\python\数据资产\取数`；
- 结果策略已确认为默认不保存、按需只保存小型结果；
- 自动门禁通过后直接存储并成为默认现行版本，不增加管理员确认；
- 允许 AI 通过受控只读连接核查数据库；
- 本轮仍无代码、数据库和生产变更。

### 阶段 P1：查询资产最小闭环

范围：

- 查询主档、查询版本、依赖和运行最小表；结果内容为可选能力；
- 手写 Alembic 迁移和回退；
- `queryctl init/context/validate/submit/run/sync`；
- 本地固定工作区模板与忽略规则；
- 复用 AI 草稿、关系配方、只读连接器和治理审计；
- 查询资产、版本 diff、运行记录和 AI 接入箱最小页面；
- 新查询摄取技能和 `AGENTS.md` 路由。

不包含：自动调度、看板、任意明细下载、对外数据 API。

### 阶段 P2：统计指标与口径修订闭环

范围：

- 指标主档和指标版本；指标结果按需启用，允许只保存 SQL 和口径；
- 分子、分母、公式、月份、数据截至时间和中文限制说明；
- 查询版本与指标版本引用；
- 修订和影响月份；选择保存结果时再支持历史重算和结果差异；
- 指标页面必须展示口径和 SQL；选择保存结果时再提供月度结果和 Excel/CSV 小型汇总导出；
- 将现有 48 项核心制度等历史 SQL 作为首批导入试点。

### 阶段 P3：治理反馈与自动运行

范围：

- 定时运行、失败重试、超时、熔断、告警和幂等；
- 表字段变化对查询/指标的影响分析；
- SQL 关系候选、配方候选和质量规则候选联动；
- 结果新鲜度、完整性和异常波动监测；
- 历史结果对比和数据质量状态。

生产调度启用必须单独授权，不因代码完成自动开启。

### 阶段 P4：统一数据产品出口（长期）

范围：

- 已生效查询和指标的参数化数据 API；
- MCP/AI 工具目录；
- 看板、专题展示、CSV/Excel 和应用接口；
- RBAC、行列权限、限流、缓存、SLA 和调用审计；
- 数据产品目录、负责人、版本、上下游和服务健康度。

禁止将任意 SQL 执行能力直接暴露为公共出口。

### 阶段 P5：多源适配与自主运营（长期）

范围：

- 各厂商系统连接适配器和契约测试；
- 源系统升级差异自动检测；
- 查询/指标回归测试；
- 自主维护的数据服务、指标和 AI 上下文；
- 开放格式备份和迁移，避免平台自身形成新的锁定。

## 17. 预计代码与文档影响范围

以下仅为开发前范围预估，不代表已经创建：

### 17.1 后端

- `backend/app/models/query_asset.py`
- `backend/app/models/metric_asset.py`
- `backend/app/schemas/query_asset.py`
- `backend/app/schemas/metric_asset.py`
- `backend/app/api/v1/queries.py`
- `backend/app/api/v1/metrics.py`
- `backend/app/api/v1/query_intake.py`
- `backend/app/services/query_intake.py`
- `backend/app/services/query_fingerprint.py`
- `backend/app/services/query_runner.py`
- `backend/app/services/query_impact.py`
- 手写 Alembic 迁移和对应 tests。

### 17.2 前端

- 扩展 `frontend/src/api/asset.ts` 或按现有 API 模块约定选择已有文件；
- `frontend/src/views/query-center/queries/`
- `frontend/src/views/query-center/metrics/`
- `frontend/src/views/query-center/runs/`
- `frontend/src/views/query-center/intake/`
- 在现有路由模块中增加菜单，不改变已有 URL。

### 17.3 本地工具与技能

- `tools/queryctl.py` 或独立 `tools/queryctl/` 包；
- `取数/START_HERE.md`、`取数/_query_*` 运行目录和模板；
- `.agents/skills/query-governance-intake/SKILL.md`；
- 根 `AGENTS.md` 技能路由；
- `87_AI视图SQL生成与平台对接说明.md` 增补查询资产接口；
- README、55 和阶段交付报告同步维护。

## 18. 测试与验收矩阵

### 18.1 后端与数据模型

- 手写迁移 `upgrade → downgrade → upgrade` 通过；
- 查询和指标的稳定编码、版本唯一、active 唯一约束通过；
- active 版本不可直接编辑；
- 重复包按 SQL/清单哈希幂等，不重复建版本；
- 运行参数不创建版本；业务口径变化必须创建版本；
- 选择保存结果时，旧结果不被新版本或重算覆盖。

### 18.2 SQL 安全

- DDL/DML、多语句、动态 SQL、注入注释全部拒绝；
- 未登记数据连接拒绝；
- 大表无业务限定拒绝或进入 blocked；
- 方言不匹配能够识别；
- 患者敏感字段输出和本地包敏感模式门禁有效；
- 源库连接始终只读。

### 18.3 查询闭环

- 本地 init → validate → submit → run → synced 全链路通过；
- 断网时 outbox 保留，恢复后幂等同步；
- 文件被改动后哈希变化可识别；
- 查询版本、运行、可选结果、AI 会话和审计可通过 correlation ID 串联；
- 同一 SQL 不同月份运行形成不同 run，不形成新 version。

### 18.4 指标闭环

- 指标分子、分母、公式和查询版本可追溯；
- 修订后 active 版本唯一且由自动门禁激活；
- 选择保存结果时，指定月份结果可重算且旧批次保留；
- 页面能展示中文限制、数据截至时间和结果状态；
- 48 项核心制度试点能够按月份复用并区分可提取、部分提取和无法提取。

### 18.5 多 AI

- 两个不同 AI 使用同一 context，对同一现行指标得到相同版本和 SQL 哈希；
- AI 使用过期 context 时明确告警；
- AI 缺少字段或关系时提交 blocked/candidate，不虚构结果；
- AI 无法绕过自动门禁强制激活查询/指标版本；
- AI 受控只读数据库核查不泄露凭据，外网 AI 上下文包不包含患者明细。

### 18.6 前端和发布

- `pnpm run typecheck` 中 `tsc`、`vue-tsc` 均通过；
- Vitest 覆盖版本、状态、差异、权限和错误态；
- 后端完整 pytest 通过；
- 构建和既有 gzip 预算通过；
- 离线包补入新增依赖并完成断网演练；
- 生产发布、调度和任何平台 apply 仍需单独授权。

## 19. 历史 SQL 导入策略

1. 第一阶段只选少量代表性目录试点，不全量扫描个人磁盘。
2. 优先试点 `取数/48项目核心制度` 中已经形成最终 SQL 和月度汇总结果的资产。
3. 每份历史 SQL 计算 SHA-256，记录来源路径和原始修改时间；先生成脱敏副本。
4. SQL 解析出的 JOIN 按 `sql-relation-intake` 进入候选，不直接回写正式关系。
5. 能映射现有查询或指标时补历史版本/证据；无法映射时建立 candidate 查询。
6. 临时探查 SQL、无效 SQL 和中间尝试进入“参考/废弃”或 quarantine，不进入现行查询库。
7. 历史结果只有在能够确认 SQL 版本、参数、统计周期和结果含义时才登记；无法确认的文件仅保留引用。

## 20. 用户复核问题与答复落实

| 编号 | 需要确认 | 原建议 | 用户答复及计划落实 |
|---|---|---|---|
| Q1 | 本地固定目录 | 使用 `F:\python\数据资产\取数` | 已确认；直接以该目录为根，新增 `_query_*` 管理子目录，不移动现有项目 |
| Q2 | 首期结果保存范围 | 只保存汇总，不保存患者明细 | 调整为 SQL/口径必须保存，结果内容默认不保存；需要时只保存小型结果 |
| Q3 | active 是否需管理员确认 | 管理员单击确认 | 已否决；自动门禁通过后直接保存并成为默认现行版本，不设确认步骤 |
| Q4 | 实施顺序 | 先 SQL 资产闭环，再做指标版本 | 已确认 |
| Q5 | 首批试点 | 使用 48 项核心制度 SQL | 已确认 |
| Q6 | AI 数据库核查 | 外网 AI 只读脱敏 context，不直连数据库 | 调整为允许 AI 经平台、跳板或受控连接器执行只读核查；凭据不进入提示词/文件，禁止写库 |
| Q7 | 结果文件 | 仅保存平台小结果和文件引用 | 调整为结果可以不保存；选择保存时只保留小文件或小型汇总，不建设大文件存储 |
| Q8 | 长期数据产品 API | 允许业务系统调用 active 参数化模板 | 已确认；保留 RBAC、参数白名单、限流和审计 |

以上答复已经回写本计划，不再作为开始开发前的未答复阻断；仍需用户对修订后的完整计划做最终复核并明确下达开发指令。

## 21. 后续其他 AI 执行方式

用户批准开发后，按阶段给不同的其他 AI 分配边界明确的任务，不绑定具体模型，也不一次性让单个 AI 同时改模型、执行器、前端和部署。

建议顺序：

1. 其他 AI-A：数据模型、迁移、Pydantic schema 和纯逻辑测试；
2. 其他 AI-B：`queryctl`、清单 JSON Schema、哈希和离线队列；
3. 其他 AI-C：摄取、查询版本和只读运行 API；
4. 其他 AI-D：查询资产、运行记录和 AI 接入箱前端；
5. 其他 AI-E：指标主档、指标版本、可选小型结果和前端；
6. 主 AI：逐阶段代码复核、权限/安全审计、完整测试、文档和 Git 收口；
7. 生产迁移、发布、调度启用和历史导入分别申请授权。

每个其他 AI 任务必须写清：

- 允许修改的文件和禁止修改的范围；
- 不得执行生产操作；
- 不得读取或输出凭据；
- 不得执行源库 DML/DDL；
- 必须保留用户现有 dirty 文件；
- 必须运行的针对性测试；
- 只提交实现结果，不自行 push、tag 或发布。

## 22. 给不同 AI 的计划版标准提示词

正式技能和 `START_HERE.md` 未开发前，可使用以下规则作为规划基线：

```text
你正在为山东省第二人民医院处理日常数据查询。

1. 先读取仓库 AGENTS.md、开发起步包/README.md、55 号计划、87 号 AI SQL 规范和 126 号查询指标闭环计划。
2. 先搜索是否已有相同 metric_code/query_code 和 active 版本，优先复用，不从聊天记忆重建口径。
3. 记录业务目的、系统、数据连接、方言、时间字段、参数、粒度、纳入、排除、去重、分子、分母和限制。
4. SQL 只能是单条 SELECT/只读 CTE；禁止 DDL/DML、存储过程、锁表和未限定的大表扫描。
5. 表字段来自当前元数据；JOIN 来自正式关系或 active 配方。同名字段不能直接当关系。
6. 历史 SQL 中的新关系只生成候选，按 sql-relation-intake 处理，未经审核不得发布。
7. 口径或 SQL 改变必须创建新版本；只改变月份等参数只创建新运行。
8. 未执行、失败、部分可提取或不确定时如实记录，不得伪造结果。
9. 不把凭据、姓名、身份证、电话、地址、患者 ID、签名或病历正文写入外网 AI、SQL 注释、日志或 Git。
10. 当前未实现 queryctl 时，只能按计划输出规范查询包；不得声称已自动接入平台。
11. 可以通过平台、跳板机或仓库受控连接器执行必要的只读数据库核查；不得索取或输出明文凭据，不得执行任何 DML/DDL。
12. 查询 SQL 和口径必须保存；结果内容默认不保存，用户明确需要时才保存小型结果。
```

## 23. 当前状态与开始开发的条件

### 23.1 历史门槛（已满足）

- 用户已答复 Q1–Q8 并下达开发指令（2026-08-11）；
- 127 底座可用性整改已完成测试门禁，可启动 126 P1。

### 23.2 P1 执行记录（2026-08-11）

| 交付 | 状态 | 说明 |
|---|---|---|
| 表 `asset_query_definitions/versions/dependencies/runs/results` | **PASS** | 迁移 `e2f3a4b5c6d7`，测试库 upgrade/downgrade/upgrade PASS |
| 指纹/门禁/摄取/运行服务 | **PASS** | `query_fingerprint` / `query_gate` / `query_intake` / `query_runner` |
| API `/api/v1/queries/*` | **PASS** | list/detail/versions/diff/gate/ingest/revise/run/runs/ai-context |
| `tools/queryctl.py` | **PASS** | init/validate/submit（outbox）/context |
| `取数/START_HERE.md` + 模板 | **PASS** | 固定根目录；运行目录 gitignore |
| 技能 `query-governance-intake` + AGENTS 路由 | **PASS** | |
| 前端「查询与指标中心」最小页 | **PASS** | `/asset/queries` 列表/摄取/版本详情/运行记录 |
| 测试 | **PASS** | plan126 单元 5 + test_query_asset 7 = **12 passed** |
| P2 指标表/API | **PASS** | `asset_metric_*` + `/api/v1/metrics/*`；结果不覆盖历史批次 |
| 生产迁移/发布 | **PASS** | 见 §23.3 |

### 23.3 生产升级记录（2026-08-11）

| 项 | 结果 |
|---|---|
| 备份 | `/opt/data-asset/backups/data_asset_pre_126p12-20260811213058.dump`（6.9M） |
| 迁移 | `d1e2f3a4b5c6` → `e2f3a4b5c6d7` → `f3a4b5c6d7e8` |
| 后端 | docker cp 入 `data-asset-api` + restart；health 200 |
| 前端 | `frontend-dist/releases/126p12-20260811213058`；current 已切；previous→g8-20260810192501 |
| OpenAPI | queries / metrics / relation-reviews / overview/charts OK |
| 测试库专项 | query+metric **16 passed**；前端 typecheck+build PASS |

**回滚**：

```bash
# DB
sudo -u postgres pg_restore -c -d data_asset /opt/data-asset/backups/data_asset_pre_126p12-20260811213058.dump
# 前端
ln -sfn /opt/data-asset/frontend-dist/releases/g8-20260810192501-e1e24a6bf5cea97a /opt/data-asset/frontend-dist/current
nginx -t && systemctl reload nginx
# 后端需从备份目录或旧镜像恢复代码后 restart
```

### 23.4 P3 + 48 项试点导入（2026-08-11）

| 交付 | 状态 |
|---|---|
| `asset_query_schedules` 迁移 `g4b5c6d7e8f9` | PASS（enabled 默认 false；`APP_QUERY_SCHEDULE_ENABLED` 默认 false） |
| 表影响分析 `GET /queries/impact/table` | PASS |
| JOIN 候选 `GET /queries/{code}/relation-candidates` | PASS（不写正式关系） |
| 48 项 SQL 解析导入（27 个现成文件） | 测试库+生产均 **27 active** 查询/指标 |
| 工具 | `tools/import_core_48_metrics.py`、`POST /queries/import/core-48` |
| 专项测试 | **21 passed** |
| 生产调度启用 | **未开**（需改 env 并登记 enabled=true） |

**生产导入结果**：`MET_CORE_03`…`MET_CORE_45` 等 27 条；对应 `QRY_CORE_*`。缺失编号因仓库仅有 27 个拆分 SQL（非 48 全量 docx 指标）。

### 23.5 P4 数据产品 + 结果/占位收口（2026-08-11）

| 交付 | 状态 | 说明 |
|---|---|---|
| 表 `asset_data_products` 迁移 `h5c6d7e8f9a0` | **PASS** | 生产 head 现为 `h5c6d7e8f9a0` |
| API `/api/v1/data-products/*` | **PASS** | list / detail / upsert / publish-core / execute / import-metric-results / ai-context |
| 执行约束 | **PASS** | 仅执行已发布产品；禁止任意 SQL；`allow_data_product` 随发布置位 |
| 缺失指标占位 | **PASS** | 21 条 `MET_CORE_*`（1–2,11–15,22,29–30,33–40,46–48）`blocked`、非 active |
| 历史 CSV 结果导入 | **PASS** | 5 个 CSV → **687** 条 `asset_metric_results` |
| CORE 产品发布 | **PASS** | **54** 个 `DP_QRY_CORE_*` / `DP_MET_CORE_*`（仅 active 可执行资产） |
| 生产计数 | **PASS** | 查询 27 / 指标 48 / active 查询 27 / active 指标 27 / 产品 54 / 结果 687 |
| Docker 镜像 | **PASS** | `data-asset:126complete-20260811220449`（commit 自运行容器）+ `latest-hot` |
| 前端 | **PASS** | 查询中心增加「数据产品」页签；发布 `frontend-dist/releases/126complete-20260811220449`；previous→`126p12-20260811213058` |
| 备份 | **PASS** | `/opt/data-asset/backups/data_asset_pre_126complete-20260811220449.dump` |
| 专项测试 | **PASS** | query+metric+data_products **14 passed**；前端 typecheck+build/gzip PASS |

### 23.6 P5 最小闭环 + 调度安全启用（2026-08-11）

| 交付 | 状态 | 说明 |
|---|---|---|
| 指标看板 API `GET /metrics/board/overview` | **PASS** | 按月份透视最新批次；前端 CSV 导出 |
| MCP 工具目录 `GET /ai/mcp/catalog` + tools 扩容 | **PASS** | 查询/指标/数据产品/多源；禁 arbitrary SQL |
| 多源能力 `GET /queries/sources/capabilities` | **PASS** | 登记连接方言与只读策略探测 |
| 调度种子 `POST /schedules/seed-core` | **PASS** | 27 条 QRY_CORE_* 默认 enabled=false |
| 全局调度开关 | **PASS** | `APP_QUERY_SCHEDULE_ENABLED=true`；日志 `Query schedules registered: 0` |
| 21 条占位官方标题 | **PASS** | 自 docx 回写（如 MET_CORE_01 转科率…） |
| 结果导入幂等 | **PASS** | 同 metric+period+分子分母跳过；生产去重保留最新 |
| 镜像/前端 | **PASS** | `data-asset:126p5-20260811223311`；前端 `126p5-20260811223311` |
| 专项测试 | **PASS** | plan126_p5 + 相关 **18 passed** |

**仍可选**：21 条无 SQL 指标的业务补录与修订激活；完整多源厂商适配器/契约回归；看板可视化图表增强；从零 Dockerfile+wheel 全量重建（当前为 known-good 运行时 + hotpatch/commit）。
