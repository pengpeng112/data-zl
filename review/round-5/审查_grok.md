先读取方案原文、未完成事项入口和关系图谱相关实现，再按只读约束独立核查覆盖度与问题。对照源码与既有计划核验方案中的规模、接口与交互主张。**结论：方案不能按现状立项执行。** 它给出了分层改造计划，对用户原话里「详细计划 / 更直观 / 像 Neo4j」的**方向**大体对齐，但对仓库现状盘点严重失实：多处把已落地能力写成缺口，会造出重复 API、重复图抽象，并与 108/129/130/138/146 的硬口径打架。应先改成「在现有图谱上做交互增量」再谈执行。

覆盖度约六成（有计划骨架、有边界、有分期），忠实度偏低：把「像 Neo4j」扩成新邻域端点 + 新 GraphStore，超出原话，也未核实现有实现。

---

## 一、对用户需求的覆盖与忠实度

用户原话（方案 §0）：分析如何把关系图谱做得更直观，像 Neo4j 知识图谱，并给出详细改造计划。

| 原话要素 | 方案做法 | 判定 |
|---|---|---|
| 分析如何完善、更直观 | §3 六条痛点 + §4 P0 六项 | 形式有，归因多数不成立（见下） |
| 像 Neo4j 知识图谱 | 对标 Neo4j Browser 交互，不默认上库 | 交互对标合理；P2-1 仍把图库写进架构，越读 |
| 详细改造计划 | P0/P1/P2、步骤、验收、风险、DoD | 有立项外形；文件范围、接口、验收混层，不可直接开工 |

合理之处：不把「像 Neo4j」理解成换库或上 Cypher；§2 不改关系数据模型、不自动写关系；P2 单列授权。这与 `01`「第一版可先不用 Neo4j」、`130` §2.3「当前需求是 Neo4j 式视觉，不是新建 Neo4j」、`138` Q07「首期不引入 Neo4j」一致。

不忠实之处：§0 把同日 PPT「Neo4j 图数据库为目标架构」写进本轮诉求。仓库里能核实的是：`01` 蓝图有 Neo4j 框，`98/99` 已做 PoC 骨架且默认 `UnavailableGraphAdapter`，`130` 明确**不实施图库**。用户原话没有要求图数据库、邻域新 API、GraphStore。方案把架构愿望和实施捆在一起，扩大了范围。

---

## 二、硬伤：现状盘点与代码不符（执行会做错活）

### 1. 「缺邻域渐进加载端点」为假 —— P0-6 会重复造轮

方案 §3、§4 P0-6、§5 第一步都写缺邻域 API，拟新增 `GET /api/v1/relations/neighborhood?center=<schema.table>`。

事实：

- 已有 `GET /api/v1/graph/neighbors`（`backend/app/api/v1/graph.py` 约 1142 行）：`physical_key` / `center_physical_key`、`depth` 1–2、`direction` in/out/both、`limit` 1–200。
- 前端 `getGraphNeighbors` + `loadChain()` 已在 explore 调用；血缘页 `center` 深链已走这条路（`index.vue` 约 961–966 行，146 E1）。
- 契约测试在 `test_graph.py` / `test_graph_contract.py`。

风险：新端点挂在 `/relations/`，中心键用 `schema.table`。108 号已把节点 id 定为五段物理键，明确禁止用 `schema.table` 当唯一键（`graph.py` 文件头第 1–5 点）。跨源同名表会串边。`hops≤3` 也突破现网 `depth≤2` 的防爆设计。

正确做法：扩展现有 neighbors（例如增量合并、截断原因、度数），不要新路径。

### 2. 「无全局搜索聚焦」为假 —— P0-1 大半已存在

方案 §3 痛点①、P0-1 写「复用现有远程搜索、拼音前缀」。

事实：

- `GET /api/v1/graph/tables/search`：表名 / 中文名 / schema ILIKE，**无拼音**（`graph.py` 约 1729–1757 行）。
- explore 顶栏已有定位框 + 1/2 跳 + 方向 +「展开关系」（`GraphToolbar.vue` 约 16–21 行）。
- 非 explore 有 `filters.keyword`，只做当前图画布高亮（`graphNormalize.ts` `focusKeyword`），不会拉邻域、不会 `fitView`。
- 菜单拼音是 `pinyin-pro`，与图谱搜索无关。P0-1「复用拼音」没有实现可复用。

真实缺口只是：搜索不在四种模式共用、命中后不居中、同名仍靠候选表而不是下拉即选。不是从零做搜索。

### 3. 「力导向替代当前布局」会覆盖已有 Neo4j 式实现，且标签与实现反了

方案 P0-3：explore/review 用 G6 force 替代当前布局。

事实：`AdvancedRelationGraph.vue` 已有 force / radial / force-atlas2，以及 layered/hierarchy 预计算（约 199–236 行）。129/130 已按 Neo4j 视觉改过一轮。

更关键：工具栏「知识图谱」绑定的是 `layout_mode=layered`（`GraphToolbar.vue` 第 8 行），而 `usesPresetPositions()` 对 layered **直接关掉布局引擎**，走环形散布，**永远进不了 force 分支**。explore 加载后还被写成 `radial`（`index.vue` 约 759 行）。注释写「默认 layered → d3-force」，代码先把 layered 判成 preset，force 成死代码。

风险：P0-3 若「替换当前布局」，可能毁掉 129 的分层下钻和中心辐射，且不修「名称叫知识图谱、实际不是力导向」这个用户能直接感到的问题。

### 4. 属性面板、图例、聚合、URL、血缘跳转都已有，P0-5 / P1-3 / P2-2 / P2-3 写成新功能

| 方案项 | 现实现 |
|---|---|
| P0-5 属性侧栏 | 节点 `ReDetailDrawer`、边 `GraphEvidenceDrawer`（点边已拉 `/graph/edges/{id}`） |
| P0-4 图例 | G6 组件顶部静态图例（类型/置信度/D 类），不可点 |
| P1-3 超节点 | `aggregateGroups` + `aggregationThreshold` 已在组件里 |
| P2-2 URL | `view_mode` / `center` / `from` / `to` / `keyword` 等已进 query |
| P2-3 血缘「在图谱中展开」 | `lineage/index.vue` `expandInGraph()` 已跳 `/asset/graph?center=` |

P0-5 的增量只是「侧栏不挡图 + 度数/值域摘要」。P1-3 应写增强 LOD，而不是新做聚合。P2-2/P2-3 不应再当改造项。

### 5. 文件范围写错，按方案改会漏主路径、误伤无关目录

§2：「只改 `frontend/src/views/asset/graph/`、`components/`（图谱域）」。

事实：渲染组件在 `frontend/src/views/asset/components/`（`AdvancedRelationGraph.vue` 约 503 行，不是方案写的 535；`index.vue` 约 1007 行，不是 1070）。边样式在 `graphTransform.ts`（约 654 行），工具栏在 `GraphToolbar.vue`。后端主路径是 `graph.py`，不是 `relations.py`。`frontend/src/components/` 是 Re* 通用件，不是图谱域。

风险：执行者会改错目录，或漏掉 `graphTransform` / `GraphToolbar` / `api/asset.ts` / 测试。

### 6. 后端能力清单不完整，还漏了已有图分析抽象

§3 只列 `/api/v1/relations/list|list-counts|path|...`，图谱真正用的是 `/api/v1/graph`、`/overview`、`/neighbors`、`/tables/search`、`/options`、`/diagnostics`、`/edges/{id}`。

另已有：

- `/api/v1/graph-analysis/*`（上下游、最短路、影响、环路；拒绝自由 Cypher）
- `services/graph_sync.py`：`GraphSyncAdapter` + `UnavailableGraphAdapter`，文件头写明「PostgreSQL 是唯一事实源；Neo4j 或内存适配器是单向只读副本」

P2-1 再发明 `GraphStore`，等于无视 98/99 骨架。`graph-analysis` 默认 degraded，前端图谱也没用它。方案完全没提这条死链。

### 7. 「draft 边一眼可辨 + 一键复核」把两套对象混为一谈

§1 目标 3、P0-4、P0-5、P1-4 把图上的 draft 边和 `batch-review` 当成同一件事。

事实：

- 图边来自 `asset_relations` / candidate / dependency，样式按 confidence A/B/C、D 延后、candidate（紫虚线，129 pastel）。
- 待审草稿在 `asset_relation_reviews.review_status=draft`，页面是 `/asset/relation-review`，权限 `asset.relation.review`。
- 图路由权限是 `asset.graph.view`；`graph.py` 只要求登录 Token（`main.py` 约 329 行）。
- `GraphEvidenceDrawer` **没有**批准/驳回按钮。

风险：图上画橙色呼吸线，用户会以为那是复核队列；在 `graph.view` 页塞复核按钮，权限模型会被打穿。P0-4 还可能覆盖 129 已对用户解释过的 D 类灰紫语义。

### 8. 引用编号不准确

- 「164 既有约束前端不改现有路径」：这是 `AGENTS.md` 代码约束第 8 条，164 是 163 合并升级计划。
- 「164 §6 红线沿用」：164 正文对应的是 GE/Soda 等治理工具授权，不是 Neo4j。图库红线在 `130` §2.3 与 `138` Q07。

---

## 三、交互与产品：即便修完盘点，方案仍可能更不直观

### 9. 没抓住「不直观」的主因：控件堆叠，而不是缺能力

现页已经是：模式切换 + 四种布局名 + 系统/连接/Schema/域 + 搜索 + limit + 统计折叠 + path 双端表 + 候选表 + 引擎状态 + 抽屉。画布高度是 `calc(100vh - 400px)`。Neo4j Browser 的直观来自**少控件**：搜 → 图画布 → 属性。

方案在已有工具栏上再加顶栏搜索、三维图例、侧栏、呼吸动画、复核入口，不收敛现有筛选。风险是更像驾驶舱，更不像知识图谱。缺少「先做减法」的信息架构。

### 10. 单击下钻 vs 双击展开：方案低估冲突

overview **单击**已用于系统→库→表→字段整层替换（`selectNode`，`index.vue` 约 890–924 行）。G6 目前只有 `NodeEvent.CLICK`，无 dblclick。explore 单击开抽屉，邻域是整图替换，不是画布上长出来。

§7 用「模式划分 + help」打发，不够。用户肌肉记忆是单击下钻。P0-2 若不写清「overview 单击保持下钻；仅 explore 双击增量展开；已展开节点再次双击折叠哪些边（只折叶子还是整棵星型）」执行会来回改手势。

### 11. 跨系统故事与 explore 默认滤镜相反

§0 立意是 HIS↔LIS↔PACS↔EMR 直观呈现。`40` 把跨系统放在 D 类延后层。explore 默认 `confidence=A` 且 `show_review_layer=false`（`GRAPH_VIEW_MODES`）。用户按方案去「搜表看关系」，默认看不到跨系统边。方案没有「跨系统图层」产品设计，只给了 draft 橙色线。

### 12. 图例「边类型 × 置信度 × 状态」三维开关

组合爆炸，和 review 模式已有的状态下拉、置信度、候选/依赖勾选重叠。比 Neo4j 的关系类型勾选更重。应降为「类型 / 等级 / 待审」三组互斥或少量芯片，而不是矩阵。

### 13. 双引擎被写成附带验收，不是设计约束

降级 SVG（`RelationGraph.vue` 约 617 行，并不「简化」）是 108 的硬路径。P0-3 力导向、P0-4 动画、P1-2 minimap 若只做 G6，SVG 会差一截，§6「SVG 不回归」会空转。G6 5 小地图要用插件，§2「不新增前端依赖」是否允许 `@antv/g6` 插件要写死。

### 14. 验收与 DoD 混层，无法按 P0 收口

§6 把 2k 节点/8k 边 30fps（P1-3）、超节点测试、path 步骤条、URL 序列化（P2-2）写进同一验收；§8 DoD 又说 P0 全过且 P1 至少两项。第一批合入标准不清。`pytest -k relations` 测不到 `/graph/neighbors`。`vitest ≥8` 混了未做的 P1/P2。500ms 邻域无环境基线（本机不直连库）。「draft 视觉 100%」未定义选择器，和现有 D 类紫虚线如何共存未写。

---

## 四、其它问题（仍建议方案修订时改）

15. **P0-1 拼音**：现搜索无拼音；要做就要新依赖或后端列，与「零新依赖」冲突。  
16. **P0-6「权限 value 域」**：语义不清。图接口无细权限码；复核是 `asset.relation.review`。不能「复用 value 域」。  
17. **邻居实现**：现网是 Python 前沿 BFS + `limit`，不是递归 CTE。方案写 CTE 没有对照现实现，也没写截断时 `truncated` 已有字段怎么展示。153 已做图谱端点反查批量化，新 CTE 可能打回 N+1。  
18. **path 已是内存 BFS**（`relations.py` 约 94–145 行），不是 CTE。P1-1 无路径「最近可达」是新查询，成本和歧义未写。  
19. **呼吸动画**：无障碍、打印、性能、SVG；review 大图会闪。  
20. **内联复核**：即使用既有 `batch-review`，图上一点批准仍改变正式关系，和「只读关系模型」并排写会误导执行者。至少要 `v-perms`、二次确认、审计，且不得放进 P0。  
21. **55/146**：146 图谱 E2 已 28/28 DONE（含 R5 统计折叠、destroy、node.meta）。方案当新专项，未说明与 146/129 的继承，也未进 55 队列。DoD 要改 README/55，但本文不是编号计划。  
22. **「cystoscape」** 拼写错误，应为 cytoscape；且 129 已选定 G6。  
23. **自审 `审查_zcode.md`** 未核对源码，把假缺口当成真缺口，不能当作本方案已过初审。

---

## 五、建议的修订方向（仍只评方案，不改文件）

把目标收成一句话：**在现有 G6 图谱上，把「搜表 → 画布上长出邻居 → 侧栏看属性」做成连续手势，不新造图 API，不上 Neo4j。**

建议保留的真增量：

- 全局搜索下拉（复用 `/graph/tables/search`），命中已加载节点则 `fitView`+高亮；未加载则 `getGraphNeighbors` **合并进当前图**，不要整图替换。  
- 仅 explore：双击增量展开 / 再双击按规则折叠；overview 单击下钻不动。  
- 修正「知识图谱」与 force 名实不符；拖拽后冻结仿真。  
- 图例改为可点的类型/等级显隐，颜色不要推翻 129。  
- 抽屉改固定侧栏，不挡画布。  
- path 走查动画、minimap 放 P1；P2 图库维持 130/138：不实施，沿用已有 `GraphSyncAdapter`。

建议从本期删除：新 `/relations/neighborhood`、新 GraphStore、拼音（除非单独立项）、P0 内联复核、把 URL/血缘跳转/聚合当新功能。

**总评**：作为「详细改造计划」结构合格，作为「可执行方案」不合格。主要风险是按假缺口开工，重复接口、打穿物理键和权限，并让已经偏满的图谱页更难用。应退回重写 §3 现状与 §4 P0，再进入执行队列。