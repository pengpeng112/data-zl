结论：方案抓住了两个界面和演示诉求，但目前还不能直接交给其他 AI 开发。存在 6 个阻断级问题，尤其是“定期”被改成手动、统一上下文不含 JOIN 字段、同步巡查无法展示逐表进度，以及“零迁移”与逐表结果/生成历史冲突。

全程只读，未修改任何文件，也未连接数据库。

## 阻断级发现

1. “定期巡查”被实质改成手动巡查，不忠实满足原需求

方案将“定期”定义为“手动触发 + 历史”，真正调度放入等待域：[方案.md:23](</F:/python/数据资产/review/round-6/方案.md:23>)、[方案.md:96](</F:/python/数据资产/review/round-6/方案.md:96>)。但用户明确要求的是“AI 定期只读巡查”。

这不是普通实现细节，而是功能范围缩减，必须获得用户明确确认。更关键的是，现有模型已经有 `QualityTask.schedule_cron`、`enabled`、`last_run_at` 等调度字段，可直接作为设计底座：[quality.py:92](</F:/python/数据资产/backend/app/models/quality.py:92>)、[quality.py:102](</F:/python/数据资产/backend/app/models/quality.py:102>)。方案完全遗漏了这项现成能力。

建议首期至少设计：

- 演示默认关闭的固定计划，例如每日 02:00；
- 启停、Cron/频率、时区、上次/下次执行时间；
- 手动执行与定时执行共用同一巡查服务；
- 防重入、并发锁、超时、补偿和失败重试；
- 即使演示环境不开调度，也要让界面真实呈现“定期巡查配置”。

2. SQL 生成所依赖的 `context/resolve` 当前不足以写 JOIN SQL

方案声称：

> context resolve 注入关系 → 根据本机数据库关系生成 SQL

见 [方案.md:27](</F:/python/数据资产/review/round-6/方案.md:27>)、[方案.md:68](</F:/python/数据资产/review/round-6/方案.md:68>)。

但当前统一上下文的 `business_relations` 只包含：

- `from_table`
- `to_table`
- `validation_status`
- `cardinality`

没有 `from_columns`、`to_columns` 或 `join_condition`：[ai_context_builder.py:95](</F:/python/数据资产/backend/app/services/ai_context_builder.py:95>)。模型知道“两张表有关”，却不知道用哪些字段连接，无法可靠生成 JOIN。

此外，该关系查询没有按 `system_code`、`source_code` 或选中表过滤，只是从全平台取前 200 条已验证关系：[ai_context_builder.py:104](</F:/python/数据资产/backend/app/services/ai_context_builder.py:104>)。这既可能漏掉选中表关系，也可能把其他系统关系注入提示词。

这会直接破坏需求核心。方案应明确先扩展上下文契约：

- 输出完整连接列、组合键、连接表达式、基数和证据等级；
- 按系统、物理来源和选中表闭包过滤；
- 只允许正式/已验证关系进入可执行 SQL；
- 候选关系只能展示为“待确认”，不得自动生成正式 JOIN；
- 为完整组合键编写测试，例如 `PATIENT_ID + VISIT_ID` 两列缺一即失败。

3. 巡查接口被设计成同步逐表调用，与“进度条逐表推进”矛盾

方案要求同步依次分析 3–5 张表，每表最长 90 秒：[方案.md:43](</F:/python/数据资产/review/round-6/方案.md:43>)、[方案.md:53](</F:/python/数据资产/review/round-6/方案.md:53>)。最坏耗时达到 270–450 秒。

同步 HTTP 请求返回前，前端拿不到逐表状态，因此无法实现方案承诺的实时逐表进度。反向代理、浏览器或网关也很可能先超时。

现有 AI 质控实现已经采用后台线程提交、前端轮询，并支持部分文本与阶段信息；前端轮询最长 10 分钟：[ai-quality/index.vue:271](</F:/python/数据资产/frontend/src/views/asset/ai-quality/index.vue:271>)、[ai-quality/index.vue:278](</F:/python/数据资产/frontend/src/views/asset/ai-quality/index.vue:278>)。

巡查应设计为：

- `POST /patrol/runs` 立即创建 run 并返回 `run_id`；
- 每张表一个子任务或明确的子任务状态；
- `GET /patrol/runs/{id}` 返回总进度及逐表状态；
- 可选 SSE，或复用轮询；
- 单表失败不阻断其他表；
- 服务重启后将运行中任务标记为未知/失败并支持重试。

4. “零迁移”与“每表一张分析卡、巡查 run、生成历史”不自洽

现有 `AiQualityResult.job_id` 是唯一值，一个 job 只能有一条结果：[quality.py:157](</F:/python/数据资产/backend/app/models/quality.py:157>)、[quality.py:161](</F:/python/数据资产/backend/app/models/quality.py:161>)。现有任务关联表又只能关联真实 `QualityFinding`：[quality.py:149](</F:/python/数据资产/backend/app/models/quality.py:149>)。

而方案同时要求：

- 一轮巡查包含多张表；
- 每表独立分析卡；
- 单表失败继续；
- 巡查时间线和统计；
- SQL 页展示所有“本人生成历史”。

见 [方案.md:43](</F:/python/数据资产/review/round-6/方案.md:43>)、[方案.md:44](</F:/python/数据资产/review/round-6/方案.md:44>)、[方案.md:64](</F:/python/数据资产/review/round-6/方案.md:64>)。

当前模型没有巡查 run—item 层级，也没有保存未提交草稿的 SQL 生成结果。若强行零迁移，只能把整轮结果塞进单个 JSONB，后续分页、逐表重试、统计、复核和状态更新都会脆弱。

方案必须二选一：

- 正式设计 `patrol_run`、`patrol_run_item`、必要的 SQL generation history 表，并手写迁移；或
- 明确降级：每张表建立一个现有 AI job，使用共同 batch key 聚合，SQL 历史只展示已保存草稿。

当前“零迁移”不能作为既定事实。

5. API 路径写错，会让开发方按不存在的基路径实现

现有 AI 质控路由前缀是：

`/api/v1/quality/ai`

见 [ai_quality.py:35](</F:/python/数据资产/backend/app/api/v1/ai_quality.py:35>)。

方案却定义为：

`/api/v1/ai-quality/patrol/*`

见 [方案.md:50](</F:/python/数据资产/review/round-6/方案.md:50>)。

应统一为现有前缀下的 `/api/v1/quality/ai/patrol/*`，或者明确说明为何新增兼容路由。否则会造成 API 层、前端类型化 API、权限测试和兼容性分裂。

6. 最终验收允许只用 mock，无法证明“当前内网模型正在应用”

用户特别强调要证明“当前是在应用”。但方案的联调标准允许模型不可达时只留下 mock 证据：[方案.md:89](</F:/python/数据资产/review/round-6/方案.md:89>)。

离线回放适合防止演示中断，却不能作为“真实应用内网模型”的验收证据。必须区分：

- 产品验收：必须至少完成一次真实内网模型调用；
- 演示兜底：现场不可达时允许回放，并显著标记；
- mock：只允许用于自动化测试，不可作为真实应用证明。

真实调用证据建议显示 provider、model、调用时间、request/job ID、耗时、成功状态和脱敏输入摘要，不展示密钥或完整主机。

## 高优先级问题

7. “换模型只改环境变量，界面自动反映”与当前代码不完全一致

方案称状态卡完全配置驱动：[方案.md:15](</F:/python/数据资产/review/round-6/方案.md:15>)、[方案.md:26](</F:/python/数据资产/review/round-6/方案.md:26>)。

模型名确实来自配置，但当前 status 返回的 host 是硬编码 `"10.255.255.10:9000"`：[ai_quality.py:210](</F:/python/数据资产/backend/app/api/v1/ai_quality.py:210>)、[ai_quality.py:214](</F:/python/数据资产/backend/app/api/v1/ai_quality.py:214>)。若后期更换地址，界面仍可能显示旧地址。

应要求后端由解析后的配置生成脱敏 endpoint 标识，禁止硬编码。同时最好展示“配置模型”和“服务实际返回模型”，避免只改标签却仍调用旧引擎。

8. 固定问题表的选取流程不够真实、稳定，也有自相矛盾

方案一处要求用隔离库运行质量规则选 top 问题表：[方案.md:24](</F:/python/数据资产/review/round-6/方案.md:24>)；另一处又称巡查只使用平台元数据和既有 `QualityFinding`，零源库连接：[方案.md:25](</F:/python/数据资产/review/round-6/方案.md:25>)。

需要说明“跑质量规则”究竟是：

- 只执行 metadata-only 规则；
- 读取既有 QualityFinding；
- 还是连接 DATA_CENTER 做 live 质量 SQL。

这三种安全边界和数据真实性不同。演示目标应固定到已有、可追溯的问题证据，至少保存：

- `system_code/source_code/schema/table`；
- finding/rule ID；
- 指标值及采集时间；
- 证据来源和数据截至时间；
- 演示快照版本。

方案中“注释缺失 92%”“键重复”等只是示例文字：[方案.md:42](</F:/python/数据资产/review/round-6/方案.md:42>)。不得在没有真实证据时固化成演示结论。

9. 现有 prompt 是针对 QualityFinding 的，不能无设计地复用于巡查摘要

方案写“复用 `build_analysis_prompt`”：[方案.md:43](</F:/python/数据资产/review/round-6/方案.md:43>)。

但现有 prompt 明确要求分析“当前传入的问题”，并按问题定位、明细举例、处理建议等固定结构输出：[hospital_llm_analysis.py:16](</F:/python/数据资产/backend/app/services/hospital_llm_analysis.py:16>)。现有结果解析也只有单个 summary、root causes 和 recommendations 结构，不是巡查 run 或逐表结果结构：[hospital_llm_analysis.py:134](</F:/python/数据资产/backend/app/services/hospital_llm_analysis.py:134>)。

应新增版本化 patrol prompt/schema，而非直接复用：

- 输入：目标表、指标快照、对应 findings、证据时间；
- 输出：每表结论、风险等级、证据引用、限制、建议；
- 明确“只根据给定证据分析，不得虚构统计值”；
- 每个结论能回链到 finding/rule/metric；
- schema 校验失败要降级为人工可读文本，但不能冒充结构化成功。

10. SQL 方言固定 Oracle，却允许用户选择任意目标系统

方案左栏提供“目标系统选择”，但后端 prompt 写死 Oracle 语法：[方案.md:62](</F:/python/数据资产/review/round-6/方案.md:62>)、[方案.md:68](</F:/python/数据资产/review/round-6/方案.md:68>)。

平台已有多种数据库类型，连接信息也有 `db_type` 字段及不同策略。如果首期只服务 DATA_CENTER，应锁定 DATA_CENTER/Oracle 11g，而不是提供任意系统选择。若支持多系统，则必须：

- 从 source connection 获取实际 `db_type`；
- 按 Oracle/PostgreSQL/MySQL/SQL Server 选择 prompt 与风险规则；
- 不对非 Oracle 输出 `ROWNUM`；
- 目标系统和物理来源必须同时确定，防止同名表串库。

11. “选择表强制入上下文”没有出现在后端接口契约中

前端设计允许多选表并声称强制注入：[方案.md:62](</F:/python/数据资产/review/round-6/方案.md:62>)。但现有 `ContextResolveRequest` 只有 question、system、source、business domain 和 max objects，没有 tables 参数：[ai.py:986](</F:/python/数据资产/backend/app/api/v1/ai.py:986>)。

方案新增的 generate 接口虽接受 `tables[]`，却没有说明如何让 `context/resolve` 对这些表进行精确闭包解析。必须设计：

- 验证每张表确实属于所选 system/source；
- 加载表的真实 owner、列、PK/唯一键；
- 获取这些表之间及一跳必要邻表的正式关系；
- 对超限、找不到表、同名多源、关系不足明确阻断；
- 返回实际采用和被忽略的表，而不只是 digest。

12. 只授予 `ai.context.read` 不足以覆盖生成行为

生成端点不仅读取上下文，还会：

- 调用内网模型；
- 写上下文快照；
- 写审计；
- 可能被用户认为具有 SQL 生成/执行能力。

现有 `context/resolve` 本身会持久化 `AiContextSnapshot`：[ai_context_builder.py:213](</F:/python/数据资产/backend/app/services/ai_context_builder.py:213>)、[ai_context_builder.py:215](</F:/python/数据资产/backend/app/services/ai_context_builder.py:215>)。

方案只要求 `ai.context.read`：[方案.md:68](</F:/python/数据资产/review/round-6/方案.md:68>)，权限语义过宽。建议新增或复用明确的 `ai.sql.generate` 权限；执行仍单独要求 `ai.sql.execute`，草稿审核仍使用审核权限。

13. 前端“取消”只能停止等待，不能取消服务端模型调用

方案承诺“生成按钮可取消”和“超时 90 秒前端可取消”：[方案.md:62](</F:/python/数据资产/review/round-6/方案.md:62>)、[方案.md:72](</F:/python/数据资产/review/round-6/方案.md:72>)，但没有取消端点、job ID、服务端取消标志或模型流中断方案。

应准确区分：

- 取消前端等待；
- 请求断开后服务端是否继续；
- 真正取消尚未开始的任务；
- 正在调用模型时是否支持中止。

不能仅用 `AbortController` 就宣称任务已取消。

14. “本人生成历史”没有可靠数据来源

方案仅返回 `{sql, risk, context_digest}`，审计只存问题 hash：[方案.md:64](</F:/python/数据资产/review/round-6/方案.md:64>)、[方案.md:68](</F:/python/数据资产/review/round-6/方案.md:68>)。

未保存的生成结果不会进入 draft，只有 hash 的审计也无法回填 SQL，因此“点击历史回填”无法实现。需要明确：

- 所有生成记录都持久化，还是历史仅指已保存草稿；
- 记录用户、SQL、context ID、模型、prompt 版本、风险扫描、创建时间；
- 保存完整自然语言问题前先做敏感信息策略；
- 列表只能读取本人记录，管理员范围另定；
- 提供保留周期与删除/归档规则。

15. `propose-sql` 的复用描述不准确

当前实现中工具名称是 `propose_sql`，会创建 `ViewDraft` 并写工具调用审计：[ai.py:142](</F:/python/数据资产/backend/app/api/v1/ai.py:142>)、[ai.py:526](</F:/python/数据资产/backend/app/api/v1/ai.py:526>)。方案多处将其写成类似独立端点的 `propose-sql`：[方案.md:16](</F:/python/数据资产/review/round-6/方案.md:16>)、[方案.md:63](</F:/python/数据资产/review/round-6/方案.md:63>)。

交付给其他 AI 前应写明准确调用路径、请求 DTO、session 生命周期以及草稿状态机，避免重复开发另一个近似接口。

## 中优先级问题

16. 风险扫描能力被描述得比现状强

方案 UI 要展示：

- 只读通过；
- 大表 WHERE 通过；
- 方言通过。

见 [方案.md:63](</F:/python/数据资产/review/round-6/方案.md:63>)。

当前风险扫描至少包含静态警告，但方案没有定义：

- 如何判断具体表是不是大表；
- `WHERE 1=1`、无边界子查询、笛卡尔积、函数包索引列；
- 组合键缺失；
- Oracle 11g 不兼容语法；
- 未登记表/字段；
- 候选关系误用。

“绿色徽标”必须绑定明确的机器检查结果，不能只是 LLM 自报或粗粒度字符串扫描。

17. “LLM 只收元数据与关系”表述不准确

自然语言问题本身也会发给 LLM，且可能包含患者标识或其他敏感文本：[方案.md:62](</F:/python/数据资产/review/round-6/方案.md:62>)、[方案.md:72](</F:/python/数据资产/review/round-6/方案.md:72>)。现有 context 还保存截断后的 `question_summary`：[ai_context_builder.py:174](</F:/python/数据资产/backend/app/services/ai_context_builder.py:174>)。

需要补充：

- 输入侧敏感信息检测和脱敏；
- 命中身份证、姓名、电话、住院号等模式时阻断或确认；
- prompt、日志、审计和错误信息不得保存原始敏感文本；
- hash 前使用服务端盐/HMAC，避免低熵文本被字典反推。

18. 状态卡“累计调用次数”口径未定义

当前 status 只查最近成功的 AI Quality job：[ai_quality.py:178](</F:/python/数据资产/backend/app/api/v1/ai_quality.py:178>)。新增 SQL 生成调用若只写通用审计，不会自然进入这个统计。

应定义：

- 是质控调用数、巡查调用数、SQL 生成调用数，还是全部；
- 是否只计成功；
- 回放和 mock 不计真实调用；
- 按 provider/model 分组；
- 最近成功时间必须标明具体能力；
- 统计查询索引和时间窗口。

19. 离线回放必须防止被误认成新分析结果

方案虽要求标注“离线回放”，这是正确方向，但还应显示：

- 原始生成时间；
- 当时模型和 prompt 版本；
- 数据截至时间；
- 当前巡查是否真正执行；
- 旧结果与当前目标集是否仍一致。

否则用户可能看到旧结论，却以为是本轮刚巡检的数据。

20. 视觉方案仍偏组件清单，缺少可执行的页面状态设计

“好看直观”目前主要是卡片、渐变、标签云和时间线：[方案.md:75](</F:/python/数据资产/review/round-6/方案.md:75>)。缺少交给开发方所需的具体视觉契约：

- 桌面宽度下的栅格比例和卡片层级；
- loading、partial、failed、replay、empty、permission denied 状态；
- 风险颜色及无障碍对比度；
- 长表名、长 SQL、长模型输出的折叠规则；
- 1366×768/1440×900 演示分辨率；
- 移动或窄屏策略；
- 截图验收基准和关键 DOM 标识。

21. DoD 缺少最关键的业务验收样例

当前 DoD 以测试命令和截图为主：[方案.md:100](</F:/python/数据资产/review/round-6/方案.md:100>)。应增加至少以下可观察验收：

- 定时任务配置后能计算并展示下一次执行时间；
- 一轮巡查对固定问题表产生可回链的真实分析；
- 其中一表模型失败，其他表仍成功；
- 回放与真实调用视觉上明确区分；
- 给出一条需要组合键的自然语言问题，生成 SQL 完整使用组合键；
- 删除 WHERE、加入 DML、使用未验证关系时风险扫描阻断；
- 非 Oracle 系统不会输出 Oracle 语法；
- 无关系证据时拒绝伪造 JOIN；
- 普通用户不能连接测试、生成、审核或执行超出权限的操作。

22. 文档交付位置不符合本仓库文档规则

方案要求创建 `docs/demo/ai-patrol-demo.md`：[方案.md:91](</F:/python/数据资产/review/round-6/方案.md:91>)。但仓库规则规定新增文档应采用当前最大编号 +1、放入 `开发起步包/`、加类别并登记唯一 README 目录。

方案自己也称“167 号计划草案”，但当前 README 和 55 中没有 167 登记。作为 `review/` 下待审草案可以暂不登记；一旦采纳，应迁入正确编号位置并同步 README/55，不能再创建未登记的 `docs/` 平行文档体系。

## 值得保留的部分

以下方向与需求基本一致，可以保留：

- 将巡查并入现有 AI 质控页面；
- DATA_CENTER 作为首期固定范围；
- 只把脱敏元数据、关系和质量摘要发送给内网模型；
- SQL 默认只生成、不直接执行；
- 复用既有草稿审核及受控只读试运行；
- 展示模型、调用时间与调用证据；
- 演示提供明确标识的离线回放；
- SQL 页面展示采用的表、关系、值域和风险依据；
- 逐表失败隔离；
- 前端双 typecheck、build、组件测试和浏览器截图门禁。

总体判断：需求方向覆盖约七成，但核心数据契约和任务模型尚未闭合。至少修复“定期调度、关系列级上下文、异步任务、存储模型、真实模型验收、准确 API 契约”六项后，才适合作为其他 AI 的正式开发方案。
