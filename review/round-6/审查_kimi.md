• 我先读待审方案，再对照仓库代码核查。

• 方案已读完。现在核查方案引用的代码事实，逐项验证。

• 继续核查：作业模型是否有 type 字段、sql-workbench 实际形态、巡检同步执行可行性等。

• 关键疑点浮现：sql-workbench 实为受控 DML 运维台，非"Monaco+只读试运行"。继续核实 146 计划原文与 ai-quality 现有 Tab。

• 最后核对一下编号与"167"是否冲突，以及前端请求超时默认值。

• 核查完毕。以下是我的独立审查结论，全部基于仓库实际代码与文档验证（全程只读，未改任何文件）。

  ---

  ## 总体结论

  方案对用户需求**覆盖完整、无明显加戏**，技术路线（复用 hospital_llm + ai_quality 作业模型 + 144 上下文注入）方向正确，大量事实核查准确（ai-quality 页 446 行、config 中 `10.255.255.10:9000`/`deepseek-r1`/90s/1800 tokens、`build_analysis_prompt` 存在于 `hospital_llm_analysis.py:45`、`QualityFinding` 模型存在、865 表/26,894 字段与 `02`/`144` 文档一致、167 为正确续号（当前最大 166）、`ai.context.read` 等权限码真实存在）。

  但存在 **2 个会导致执行 AI 直接撞墙的硬伤（P1）** 和若干事实性/可行性偏差，建议修订后再交付开发。

  ---

  ## 一、需求覆盖度与忠实度（对照原话逐条）

  | 需求原话 | 覆盖情况 | 评价 |
  |---|---|---|
  | "ai 帮助定期只读巡查的界面，与 ai质控与分析 界面在一起、一起优化" | §3 A1 三 Tab 合入 ai-quality 页 | 覆盖 |
  | "借助当前内网对接的" | §1/§3 复用 hospital_llm | 覆盖 |
  | "固定巡检数据中心" | H2 + `ai_patrol_targets.json` 默认 DATA_CENTER | 覆盖 |
  | "固定找个表有问题的帮着分析" | H2 演示集 3–5 张已知问题表 | 覆盖 |
  | "我需要演示" | A3 一键演示 + 离线回放兜底 + S2 演示剧本 | 覆盖，且离线回放是合理的演示保障，不算加戏 |
  | "后期改为更强大内网模型" | H4 env 驱动 + §7 等待域 | 覆盖（但见 P3-6 的 host 硬编码问题） |
  | "证明我当前是在应用的" | A2 引擎状态卡 | 覆盖 |
  | "让 ai 帮我写 sql 的界面，根据本机数据库的关系" | §4 B，144 context resolve 注入关系+值域 | 覆盖（语义忠实） |
  | "生成详细设计方案 md 让别的 ai 执行" | 方案本体 + S1–S5 批次 | 覆盖 |
  | "界面好看直观" | §5 有具体组件级规范 | 覆盖 |
  | "定期" | **H1 降级为"手动触发+历史"，真定时调度进等待域** | 这是对字面的有意识偏离，方案已明示为假设。**建议交付前向用户确认这一点可接受**——"定期"是需求标题级词汇，演示时评委可能问"定时在哪" |

  未发现私自加戏：一键演示、离线回放、示例问题芯片均直接服务于"演示"目的，属合理补充。

  ---

  ## 二、自发发现的问题（按严重度）

  ### P1-1：§A4 `POST /patrol/run`"同步逐表"在现有架构下不可行

  方案 §A4 写"触发一轮（**同步逐表**，单表超时 90s）"。问题：

  - 前端 HTTP 客户端默认超时 **10 秒**（`frontend/src/utils/http/index.ts:34`，`timeout: 10000`），单次 LLM 调用读超时就是 90s，3–5 表串行最坏 7.5 分钟——同步接口必然前端超时、且大概率撞 nginx/网关超时。
  - 既有 ai_quality 作业**本来就是异步模型**：`_submit_hospital` 用 `threading.Thread(target=_finish_hospital_job, daemon=True)` 后台执行（`ai_quality.py:471-475`），前端轮询 jobs。方案 §A3 同时声称"复用 ai_quality jobs 模型落库"，与"同步逐表"自相矛盾。

  **修订建议**：patrol/run 改为"创建父作业立即返回，后台线程逐表推进，前端按既有轮询模式拉进度"——这正是现有页面已实现的交互，改动反而更小。

  ### P1-2：§1/§4 对 sql-workbench 的描述失实，B1"去试运行"出口不存在

  方案 §1 称"146 E 批 sql-workbench（**Monaco+try-run 只读试运行**+复核驳回，376 行）"，§4 B1 据此设计"**去试运行**（携 SQL 跳 sql-workbench try-run 只读）"。实测：

  - `frontend/src/views/ops/sql-workbench/index.vue`（确实 376 行，行数巧合吻合）是**受控 DML 运维台**：仅 asset schema 白名单 INSERT/UPDATE 模板、dry-run 影响行预估、二次确认执行；用 el-input textarea，**无 Monaco、无任意 SELECT 只读试运行**。
  - 146 计划原文中 sql-workbench 在 E7 仅做了"**适配分页响应**"（146 文档 §E7 任务矩阵）；"试运行表格"属于 146 B4 的**查询中心**（已登记查询资产的试算），与任意 SQL 无关。
  - 前端 `package.json` **无 monaco/codemirror 任何编辑器依赖**（见 P2-1）。

  后果：执行 AI 到 S4 会发现跳转目标的能力不存在，要么搁浅要么擅自造轮子。**真正的只读执行通道是 `POST /api/v1/ai/drafts/{draft_id}/execute`**（`ai.py:623`，限 approved 草稿、`ai.sql.execute` 权限、只读 runner 限量+脱敏）。修订方向：B 的"试运行"出口改为"存草稿→（审核后）草稿执行"，或显式新增一个只读试运行端点并计入工作量。

  ### P2-1：Monaco 是新依赖，方案未排工作量

  §B1 与 §5 两处指定 Monaco 编辑器，但前端当前**零编辑器依赖**。引入 Monaco 需要 `pnpm add` + Vite worker/打包配置，体积增加数 MB，且 S4 验收"前端三件套"的构建时间会明显变化。方案 S4 批次完全未提。要么在 S4 显式列入"新增 Monaco 依赖及构建配置"，要么降级为只读高亮 pre/textarea（演示场景足够）。

  ### P2-2：路由与菜单约定偏离

  H6/§4 定 B 页路径为 `/ai/ai-sql`、"菜单挂 AI 协作组"。实测：前端**没有 `/ai` 顶级模块，也没有任何"组"级菜单**；全部现有 AI 页平铺在 `router/modules/asset.ts` 下：`/asset/ai-context`（AI上下文）、`/asset/ai-quality`（AI质控分析）、`/asset/ai-tools`（AI 接入与协作）。新开顶级模块会让这一个页面孤立于既有导航体系，也增加执行 AI 的自由发挥空间。**建议改 `/asset/ai-sql` 挂 asset.ts**。

  ### P3 事实性小错（不影响方向，但会误导执行 AI 的现状认知）

  1. §1 称 ai_quality.py "11 端点"——实际 **10 个**（status/connection-test/preview/jobs 列/jobs 详/jobs 建/jobs retry/results review/results attach/governance-report）。
  2. §A1"现状'分析任务/治理简报'保留为两 Tab"——当前 `ai-quality/index.vue` **没有任何 el-tabs**，是单页多卡片布局（问题表 + 报告面板 + 任务列表）。改造实为"新增 Tab 容器重组"，不是"保留两 Tab"。
  3. §A4 status 扩展"最近成功时间"——`_status_payload` **已返回 `last_success_at`**（`ai_quality.py:208`，取自最近 succeeded 作业），真正新增的只有"累计调用次数"。
  4. §A3/A4"落 jobs type=patrol"——实际列名是 `AiQualityJob.task_type`（`models/quality.py:130`），零迁移结论成立但字段名要改对。
  5. **patrol 复用 jobs 模型绕不开 preview 签名机制**：`POST /jobs` 强制 `_require_preview_request_id` + input_digest HMAC 校验（`ai_quality.py:460,465`）。patrol 没有 preview 环节，必须走自建的作业创建内部路径（类似 `_submit_hospital` 绕过签名的方式），方案对此只字未提，执行时会卡住。
  6. **host 硬编码破坏 H4 承诺**：status 载荷中 `"host": "10.255.255.10:9000"` 是**写死的字符串**（`ai_quality.py:214`），不读 `hospital_llm_base_url`。H4 承诺"换更强模型只改 env、界面自动反映"——model 名会变，但换主机时状态卡 host 不会变。S1 做 status 扩展时应顺手改为从 config 派生（含脱敏）。
  7. B2 生成端点挂只读码 `ai.context.read`，但它会真实调用 LLM（耗时+计费资源）；既有 LLM 调用端点惯例是挂 `analyze` 类动作码。不算错误，但建议方案说明理由或新设权限码。

  ### 提示（非问题）

  - `backend/app/services/ai_patrol_targets.json` 放包内意味着改演示目标集要发版；演示场景可接受，但值得在方案中注明取舍。
  - H2"S1 执行时在隔离库跑质量规则选 top 问题表"依赖目标表已有 QualityFinding 数据，若隔离库无对应 findings，"已知问题标签"会落空——建议 S1 验收加一条"目标集每表至少 1 条真实 finding 证据"。

  ---

  ## 三、最终意见

  方案**不建议原样交付执行**。骨架（需求覆盖、批次划分、安全边界、DoD）合格且忠实，但必须先修订：①patrol 改异步作业模型（P1-1）；②重写 B 的"试运行"出口并修正 sql-workbench 现状描述（P1-2）；③Monaco 依赖与路由位置两项决策显式化（P2）。P3 各条可作为修订批注一并改正。修订后该方案具备直接交付其他 AI 执行的成熟度。

