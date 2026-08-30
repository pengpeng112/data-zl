• 我先读取待审方案和相关参考文件。

• 方案已读。现在核查方案中的事实性 claims 是否与仓库实际一致。

• 最后核查一处：现有表搜索是否支持拼音前缀。

• 核查完成。以下是我的独立评审结论。

  ---

  # 独立评审：review/round-5/方案.md

  ## 总体结论

  方案对用户需求**覆盖完整、立场忠实**（"像 Neo4j"定位为交互对标、Neo4j 存储列为可选件，均有依据），结构（盘点→痛点→P0–P2→步骤→验收→风险）符合"详细改造计划"的要求。**但 §3 现状盘点存在多处与仓库实测不符的事实错误，导致 P0-3、P0-6 两个核心工作项建立在错误前提上**，其中 P0-6 属于重复造轮子（目标能力已存在并已接线）。建议打回修订盘点后再执行，不应按现文直接开工。

  ## ① 需求覆盖度与忠实度

  - **覆盖无遗漏**。用户要"更直观 + 像 Neo4j 知识图谱 + 详细改造计划"，方案的搜索聚焦、渐进展开、力导向、属性面板、关系过滤、图例、治理联动均为该需求的合理展开；§4"非目标"（不全量渲染 1.1 万表、不自动改关系、不换图库）是恰当的自我约束，非漏项。
  - **无私自加戏**。唯一可能被视为加戏的是 P2-1 Neo4j 读模型——但用户原话点名 neo4j，且 `开发起步包/01_平台执行方案.md:1771` 本就载明"Neo4j 第一版不部署、第二阶段视需求增加"，方案将其列为可选件+单独授权门禁，与 01 蓝图和 164 红线（`164...专项计划.md:80,90` 离线依赖审计+单独授权）一致，立场正确。
  - **可核验的事实 claims 大多属实**：`graph/index.vue` 确为 1070 行、`AdvancedRelationGraph.vue` 535 行、G6 `^5.1.1`（package.json:59）、path 端点 direction/max_hops 1–8（relations.py:94-99）、batch-review 走 `asset.relation.review` 权限码（relations.py:467-470，方案 §7"权限码不变"可行）、11,182 表（55 号文/README/143 号文互证）、4 视图模式（index.vue:322）、vitest 已配置（package.json:27）、URL 深链已有基础（index.vue:514-533 + 164 执行报告"G-07 深链刷新通过"）。

  ## ② 自发发现的问题（按严重度）

  ### 高-1｜P0-6 重复造轮子：邻域端点已存在且前端已接线

  §3 称"**缺邻域渐进加载端点**"，P0-6 据此新建 `GET /api/v1/relations/neighborhood`。实测：`backend/app/api/v1/graph.py:1142` 已有 `GET /api/v1/graph/neighbors`（"某表邻居图"），支持 `physical_key` 中心、`depth` 1–2 跳、`direction` in/out/both、`limit` ≤200；前端 `api/asset.ts:875` 已封装，explore 模式的"中心表+深度+方向"搜索（`GraphToolbar.vue:16-19`）走的就是它。§3 的后端盘点只枚举了 `/relations/*` 六个端点，**完全漏掉 `/api/v1/graph/*` 这一整个 API 面**（graph、neighbors、overview、edges/{id}、tables/search、filter-options、diagnostics）——而那才是图谱页真正使用的 API。

  - 风险：新建第二套邻域 API 会造成口径分裂、双份维护；§5 第一批排期"搜索聚焦/双击展开（依赖 API）"的错误前提会让工作量高估、顺序错误。
  - 正确做法：P0-6 应改写为**扩展既有 `/graph/neighbors`**——depth 上限 2→3、响应补每节点度数、支持"在已加载图上增量合并"语义，而不是新建端点。

  ### 高-2｜P0-6 入参格式违背仓库既有约定

  方案拟用 `center=<schema.table>`。但 `graph.py:1144-1146` 的注释明确：`schema.table` 跨系统同名有歧义，物理唯一必须走五段式 `physical_key`（system|source|namespace|schema|table），现有 neighbors/tables/search 均按此设计（tables/search 还专门返回 `ambiguous` 标志，graph.py:1753）。新端点若用 schema.table 会把已解决的歧义问题重新引入。

  ### 中-3｜P0-3 对布局现状误判，有重做已完成工作的风险

  P0-3 称"G6 force 布局**替代当前布局**"。实测四个模式的布局由后端下发（`graph.py:288-344`）：overview=grouped(**force-atlas2**)、path=layered（预计算坐标）、explore=radial（中心辐射）、review=grouped(**force-atlas2**)；d3-force 已是组件兜底默认（`AdvancedRelationGraph.vue:220-235`）。即 4 个模式中 3 个已是力导向家族或辐射式。且 `129_图谱修复权限整改布局美化交接.md:90-98` 记载：2026-08-12 用户已要求"改 Neo4j 风格"并**已部署过 force 改造**——方案全文未引用这段历史。另注意 `AdvancedRelationGraph.vue:200` 的教训注释：hierarchy/layered **刻意不用 force**（"会挤到中心重叠"），方案未提及。真正的新工作只剩：参数调优、"重新布局"按钮、拖拽后冻结仿真——工作量远小于"替换布局"的字面含义。

  ### 中-4｜痛点③与图例现状不符，会污染验收基准

  §3 痛点③"边样式区分度低（类型/置信度/待审状态视觉不分离）"。实测两个引擎的图例均已区分：A/正式、已验证、B/C、D/待分析、视图依赖五种边样式（`AdvancedRelationGraph.vue:4-11`、`RelationGraph.vue:4-10`）。P0-4 真正的新增是"**可点击图例过滤**"和 draft 呼吸动画。痛点失真直接导致 §6"draft 边视觉可辨率 100%"的验收失去基线意义（现状可能已接近达成）。

  ### 中-5｜§6 性能验收与既有负载策略自相矛盾、不可达

  §6 要求"2k 节点/8k 边平移缩放 ≥30fps"。但 `graphLoadPolicy.ts:17-20` 现行策略：≥140 节点/180 边**自动开聚合**、≥220 节点/320 边**强制切 SVG**（index.vue:496-508 会自动改 `graphEngine="svg"` 并弹警告）。不先调整这套阈值，"2k 节点 G6 场景"在现有产品行为下根本不会出现，验收无法执行；方案只字未提负载策略的配套修改。

  ### 中-6｜痛点①归因失真

  "无全局搜索聚焦节点"——实际 explore 模式工具栏已有中心表远程搜索+候选消歧（index.vue:112-114、GraphToolbar.vue:17），非 explore 模式也有 keyword 搜索（GraphToolbar.vue:43）。真实缺口是"**已加载图上的聚焦/高亮/视口适配**"和跨模式统一入口。方向正确但现状描述会让 reviewer 低估复用面。

  ### 低-7｜P1-3"超节点聚合"部分已存在

  `aggregate_groups` 筛选项 + 阈值自动聚合已在 graphLoadPolicy 中运行，方案当作全新功能列出，未引用现状。

  ### 低-8｜P0-1"拼音前缀搜索"伪装成纯复用

  `tables/search` 仅对 table_name/table_name_cn/schema/namespace 做 ilike（graph.py:1741），**无拼音能力**。在"不新增前端依赖"红线（§2）下，拼音要么后端新增字段/计算列，要么引入拼音库——方案未承认这笔工作量和依赖决策。

  ### 低-9｜其余表述/归属问题

  - §3/§2 组件路径含糊：`components/AdvancedRelationGraph.vue` 实际位于 `frontend/src/views/asset/components/`（`graph/` 下只有 index.vue 和 6 个 .ts 工具），§2 的改动范围应写全路径。
  - RelationGraph.vue 被称"简化版"，实为 677 行的 SVG 降级引擎（比 G6 版 535 行更长），性质是 fallback 引擎。
  - P0-6"复用现有权限 value 域"措辞含糊且与现状脱节：`/graph/neighbors` 等读端点目前**无任何 require_permission 依赖**，方案应明说沿用此现状还是补鉴权，而不是一句含混带过。
  - §5 第一批内部顺序自相矛盾：箭头写"后端 API 先行"，括号又写侧栏/图例"纯 UI，先行"。
  - §2 把"前端不改现有路径"归给 164 号文，实际出自 AGENTS.md 代码开发约束 §8（164 中无此条）；约束本身真实存在，仅引用出处错。

  ## 处置建议

  不推翻方案框架，但要求修订后再执行：

  1. §3 补盘 `/api/v1/graph/*` 全部端点、129 号 Neo4j 风格改造史、graphLoadPolicy 阈值策略、四模式实际布局映射；
  2. P0-6 改写为"扩展 `/graph/neighbors`（hops 3、度数、增量合并、physical_key 入参）"，删除新建 `/relations/neighborhood`；
  3. P0-3 改写为"explore/review 布局参数调优 + 重新布局 + 拖拽冻结"，明确哪些模式已有 force 家族布局；
  4. §6 性能验收与 graphLoadPolicy 阈值口径对齐（要么改阈值并写明，要么把验收规模降到阈值内）；
  5. 修正痛点①③的现状描述与组件路径、引用出处。