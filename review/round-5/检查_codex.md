结论：方案方向基本符合“更直观、接近 Neo4j 知识图谱”的诉求，但不能直接按现稿立项。最大问题不是遗漏功能，而是现状核查明显失真：它把已经存在的邻域查询、搜索定位、力导向布局和属性抽屉再次列为新建项，导致 P0 工作量、API 设计和实施顺序都不可靠。建议退回修订后再执行。

以下按重要性列出发现。

## 严重问题

1. “后端缺邻域渐进加载端点”与代码事实直接冲突

方案声称后端“缺邻域渐进加载端点”，并把新建 `/api/v1/relations/neighborhood` 列为 P0 核心任务，见[方案 §3](/F:/python/数据资产/review/round-5/方案.md:27)、[方案 P0-6](/F:/python/数据资产/review/round-5/方案.md:43)。

实际上已经存在：

- `GET /api/v1/graph/neighbors`
- 支持完整物理键、方向、深度、limit
- 深度限制 1–2，limit 最大 200
- 返回节点、边、中心物理键、截断和查询元信息

出处：[graph.py](/F:/python/数据资产/backend/app/api/v1/graph.py:1142)、[asset.ts](/F:/python/数据资产/frontend/src/api/asset.ts:864)。

而且前端已经实际调用该接口进行中心节点邻域加载，见[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:741)。

这意味着方案提出的新 `/relations/neighborhood?center=<schema.table>` 不只是重复建设，还会造成两个问题：

- 路由域从现有 `/graph/*` 错置到 `/relations/*`。
- `schema.table` 身份会丢失 system/source/namespace，可能把跨数据源同名表错误合并；当前代码已特意采用五段 `physical_key` 解决这一问题。

建议将 P0-6 改为“扩展现有 `/api/v1/graph/neighbors`”，明确需要补的是增量合并、节点度数、展开状态、截断游标等，而非新建平行接口。

2. “力导向布局替代当前布局”同样不符合现状

方案把力导向布局作为 P0-3 新功能，见[方案 P0-3](/F:/python/数据资产/review/round-5/方案.md:40)。

但现有高级图组件已经：

- `grouped` 使用 `force-atlas2`
- 默认模式使用 `force`
- 代码注释明确写着“Neo4j 风格的 d3-force 力导向布局”

出处：[AdvancedRelationGraph.vue](/F:/python/数据资产/frontend/src/views/asset/components/AdvancedRelationGraph.vue:217)。

因此真正待做的应是：

- 明确各 view mode 与 layout mode 的映射；
- 增加布局冻结、重新布局和稳定性控制；
- 做参数调优和性能测量；
- 判断现有 radial/layered/force 哪个应作为 explore 默认值。

若继续写成“接入力导向”，实施者很可能重复改造已经存在的逻辑，甚至破坏现有 hierarchy/preset 切换机制。

3. “无全局搜索聚焦”只部分成立，方案没有区分已有能力与缺失交互

现有前端已经具备：

- 表搜索接口 `/api/v1/graph/tables/search`
- 歧义表判断
- 根据搜索结果取得完整物理键
- 调用邻域接口加载并选择中心节点
- 设置中心节点和 radial 布局

出处：[asset.ts](/F:/python/数据资产/frontend/src/api/asset.ts:902)、[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:720)、[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:741)。

所以缺口更准确地说是“搜索入口的位置、已加载节点的纯前端聚焦、高亮反馈和搜索体验不足”，而不是从零建设全局搜索。

另外，方案承诺“拼音前缀搜索”，但当前后端搜索只覆盖表名、中文名、Schema、namespace，没有拼音索引或拼音字段。若坚持该承诺，就会引入新的搜索实现、索引或前端拼音转换依赖，与“不新增前端依赖”并不天然一致。

4. “无属性面板”与现有界面明显冲突

方案将节点/边属性侧栏列为 P0-5，痛点中写“无属性面板”，见[方案 §3](/F:/python/数据资产/review/round-5/方案.md:30)、[方案 P0-5](/F:/python/数据资产/review/round-5/方案.md:42)。

现有页面已有：

- 节点详情抽屉；
- 物理键、系统、数据源、Schema、表名、中文名、业务域、字段数、行数等字段；
- 边点击后打开证据抽屉；
- 边证据、状态和字段映射展示。

出处：[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:198)、[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:206)、[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:931)、[GraphEvidenceDrawer.vue](/F:/python/数据资产/frontend/src/views/asset/components/GraphEvidenceDrawer.vue:47)。

合理改造应是“把现有抽屉升级成可固定、与图并排、不打断上下文的 Inspector”，并明确哪些字段已经存在、哪些需要新接口补齐。否则会重复实现另一套详情组件。

5. Neo4j 后端现状盘点不完整，P2 有重复建设风险

仓库已经存在图同步与分析层骨架：

- `GraphSyncAdapter`
- `UnavailableGraphAdapter`
- `InMemoryGraphAdapter`
- 图同步批次表
- 图分析 API
- 默认 Neo4j 未配置时返回 degraded

出处：[graph_sync.py](/F:/python/数据资产/backend/app/services/graph_sync.py:6)、[graph_sync.py](/F:/python/数据资产/backend/app/services/graph_sync.py:140)、[graph_analysis.py](/F:/python/数据资产/backend/app/api/v1/graph_analysis.py:8)。

方案却提出重新抽象 `GraphStore(neighbors/path/subgraph)`，没有说明它与现有 `GraphSyncAdapter`、图分析 API、同步批次的关系，见[方案 P2-1](/F:/python/数据资产/review/round-5/方案.md:57)。

必须先裁决：

- 扩展现有 adapter，还是引入第二套 GraphStore；
- 查询适配器与同步适配器是否分离；
- 图分析 API 与普通图展示 API如何共用数据；
- Neo4j 不可用时如何稳定回退 PostgreSQL；
- 同步批次、数据版本和前端缓存如何保持一致。

现稿未处理这些问题，直接实施会形成双抽象、双数据口径。

## API、数据与正确性问题

6. 新 API 使用 `schema.table` 作为中心节点，违背仓库当前的物理身份设计

方案示例为：

```text
center=<schema.table>
```

见[方案 P0-6](/F:/python/数据资产/review/round-5/方案.md:43)。

现有系统已经因为同名资产歧义而采用：

```text
system|source|namespace|schema|table
```

并在搜索时要求无法唯一确定的表补充系统、数据连接或 Owner，见[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:720)、[graph.py](/F:/python/数据资产/backend/app/api/v1/graph.py:1145)。

所以方案的新参数模型会造成身份降级。任何新增或扩展接口都应以 `center_physical_key` 为主，旧式 `schema.table` 最多作为明确标注的兼容参数。

7. “递归 CTE”与当前实现、分页语义均未核实

方案指定 PostgreSQL 递归 CTE，见[方案 P0-6](/F:/python/数据资产/review/round-5/方案.md:43)。

当前邻域接口实际上按深度逐轮查询 frontier，不是递归 CTE，见[graph.py](/F:/python/数据资产/backend/app/api/v1/graph.py:1173)。

如果改成 CTE，方案至少应说明：

- 是优化现有接口还是替换实现；
- PostgreSQL 实际执行计划及需要的复合索引；
- limit 是总边数、每跳边数还是节点数；
- 高度节点如何公平截断；
- 截断后如何继续展开；
- 有向查询的 in/out/both 语义；
- 多边、回路、自环和重复节点如何处理。

当前代码的 limit 实际接近全次调用的总关系限制，而方案又写“limit≤200/跳”，两者语义不同。这个差异可能把最多 200 条边变成最多约 600 条甚至更多，必须先定契约。

8. P0-2 的“再次双击折叠其邻域”缺少正确的数据状态模型

在多中心、多次展开的图中，一个邻居可能同时由多个已展开节点引入。若简单删除“该节点的邻域”，可能误删另一条展开路径仍依赖的节点或边。

方案应明确：

- 每个中心节点的 expansion set；
- 节点和边引用计数或来源集合；
- 重叠邻域的去重规则；
- 折叠时只删除不再被任何展开引用的元素；
- 请求乱序、取消、重复双击和失败回滚；
- 当前节点是否已完整加载，以及截断状态；
- 折叠是否保留被选中、被固定或属于 path 结果的节点。

现稿只有交互描述，没有足以正确实现的状态设计。

9. 请求返回字段与现有 DTO没有对齐

P0-5/P0-6要求节点提供“关联值域摘要、度数”，边提供“来源 SQL 摘要”。但现有 `GraphNode`/`GraphEdge` 契约没有完整覆盖这些字段；当前节点详情主要显示表资产元数据，见[graph.py schema](/F:/python/数据资产/backend/app/schemas/graph.py:23)、[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:206)。

需要在方案中逐项说明：

- degree 是全图度数还是当前子图度数；
- in/out degree 是否分别返回；
- 值域摘要来自哪个表/API，权限如何处理；
- SQL 摘要是否可能包含敏感字面量；
- SQL 如何截断、脱敏和按需加载；
- 这些字段内嵐到 neighborhood 响应，还是点击后调用 detail 接口。

否则“属性侧栏”会变成 N+1 请求或把大量证据塞进首屏响应。

10. 搜索与邻域接口缺少结果完整性设计

当前搜索最多返回 30 项，并可能存在同名歧义；邻域结果也会被 limit 截断。方案只写“超限提示改用 path 模式”，不够充分：

- path 适合已知起终点，不等价于浏览高度节点邻域；
- 应显示“已展示 50/实际 N”；
- 应提供继续加载、按关系类型加载或按系统分组加载；
- 需要稳定排序，否则同一节点重复展开可能看到不同的前 50 条；
- 高度节点应优先展示 A 级/validated/跨系统关键边，排序口径必须明确。

## 权限与安全问题

11. “复用现有权限 value 域”表述错误且不可执行

P0-6 写“复用现有权限 value 域”，见[方案 P0-6](/F:/python/数据资产/review/round-5/方案.md:43)。“value 域”既不是权限码，也不能说明接口授权策略。

当前页面权限是 `asset.graph.view`，见[asset router](/F:/python/数据资产/frontend/src/router/modules/asset.ts:69)；复核写操作使用 `asset.relation.review`，见[relations.py](/F:/python/数据资产/backend/app/api/v1/relations.py:470)。两个权限并不等价。

必须分别规定：

- 图、搜索、邻域、边详情：`asset.graph.view`
- 复核按钮可见性和写接口：`asset.relation.review`
- 无复核权限用户仍可看哪些 review 字段
- 后端必须强制校验，不能只依赖前端按钮隐藏

12. 现有 graph 路由本身似乎没有细粒度 `require_permission`

`graph.py` 各 GET 端点主要依赖 `get_db`，未见像 relations review 路由一样逐端点声明 `require_permission`。方案应把“核实并补齐 graph API 后端权限”列为显式任务，而不是含糊地说权限不变。

尤其新增全局搜索、证据摘要和值域摘要后，单靠前端路由权限不足以形成后端安全边界。

13. “来源 SQL 摘要”存在敏感信息和超量响应风险

SQL 可能含患者标识、业务常量、源系统结构和其他敏感字面量。方案未规定：

- 是否只显示 SQL hash、来源文件和已脱敏片段；
- 最大字符数；
- 是否按权限延迟加载；
- 日志和错误上报是否排除 SQL 文本；
- 是否沿用已有脱敏管道。

这是医院数据平台场景下必须进入方案和验收的安全项。

## 交互设计问题

14. 单击与双击的语义仍不完整

当前 overview 模式的单击节点已经执行逐层下钻，见[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:894)。其他模式单击打开节点抽屉，见[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:926)。

方案新增双击展开，但没有处理浏览器/G6中双击前通常会先触发一次或两次单击的问题，可能出现：

- 双击时先打开侧栏，再展开；
- overview 中先下钻，导致第二次点击落在已销毁画布；
- 双击与画布双击缩放冲突。

需要设计事件延迟/取消机制，并为键盘和触屏提供等价入口。仅写“模式划分”不能解决事件竞争。

15. “拖节点后停止仿真”定义过于粗糙

如果拖动任一节点就永久停止整个 force simulation：

- 新增邻域节点后可能不再自动布局；
- 其他节点仍可能重叠；
- 用户难以恢复布局；
- 固定一个节点与冻结全图是两个不同操作。

建议区分：

- 拖动节点：固定该节点位置；
- 冻结布局：显式按钮；
- 重新布局：解除部分或全部固定；
- 增量节点加入：局部重热仿真；
- 保存视图：记录固定节点坐标。

16. 三维边编码过载，可能反而降低直观性

方案同时用：

- 线型表示 relation_type；
- 明度表示 confidence；
- 橙色虚线和呼吸动画表示 draft；
- 粗细也参与类型表达。

见[方案 P0-4](/F:/python/数据资产/review/round-5/方案.md:41)。

这会发生视觉通道冲突：例如 C级 draft 边到底以浅色为主还是橙色为主；虚线既表示类型又表示状态时无法区分。建议形成明确、互斥的视觉语法，例如：

- 颜色：关系层/状态；
- 线型：关系类型；
- 透明度：置信度；
- 粗细：当前选择或路径；
- 动画：只用于短时焦点，不持续表示状态。

同时必须补充色盲可辨、暗色主题、`prefers-reduced-motion` 和关闭动画能力。持续呼吸动画在大量 draft 边场景也会拖累渲染。

17. “像 Neo4j”被直接解释成 Neo4j Browser，而用户需求本身仍有产品歧义

方案把用户的“想 neo4j知识图谱”解释为“交互像 Neo4j Browser、存储可选”，这一判断可能合理，但不是用户原话能够唯一推出的结论，见[方案 §0](/F:/python/数据资产/review/round-5/方案.md:5)。

用户也可能想要：

- 真正采用 Neo4j 存储；
- Neo4j Browser 式图形表现；
- 属性图数据模型；
- Cypher 查询能力；
- 只要视觉效果类似。

详细改造计划应该增加一个前置决策点，把“交互对标”和“存储引入”分别确认。否则方案可能忠实满足了自己的解释，却未必忠实满足用户意图。

18. 缺少直观的视觉原型和页面布局方案

用户核心诉求是“更加直观”，但方案没有：

- 当前界面截图标注；
- 改造后线框图；
- 顶栏、画布、图例、Inspector、review 队列的空间布局；
- 空态、加载态、截断态、错误态；
- 小屏幕降级策略。

只有功能表不足以验证“直观”。至少应补桌面端主视图线框、节点/边两种选中态、渐进展开过程和 review 模式布局。

## Neo4j平台化问题

19. P2-1远达不到可实施的 Neo4j 引入方案

现稿只说 GraphStore 抽象、同步副本和授权门禁，遗漏了关键设计：

- 节点 label 与属性模型；
- 关系 type 和多边身份；
- 五段物理键唯一约束；
- 正式关系、candidate、dependency 是否共库；
- 全量初始化与增量 CDC/轮询；
- 删除和状态变更如何同步；
- 读一致性及最大允许延迟；
- 数据版本和同步水位；
- 索引/约束；
- Neo4j 版本、社区版/企业版选择；
- 驱动和容器离线包；
- TLS、账号、最小权限和凭据托管；
- 容量估算、备份、恢复、监控；
- PostgreSQL/Neo4j结果一致性测试；
- 故障回退和熔断。

因此 P2目前只能算方向说明，不能称为“详细改造计划”。

20. 没有论证为什么现阶段需要 Neo4j

仓库关系规模与资产表规模并不自动证明必须采用图数据库。需要给出决策指标：

- 典型邻域和路径查询的 P95；
- 图深度和平均/最大度数；
- 当前 PostgreSQL查询性能；
- 图算法需求是否超出已有适配器；
- 数据同步与运维成本；
- Neo4j 带来的具体收益。

建议设立 Go/No-Go 门槛，例如只有在多跳查询 P95、并发或图算法需求超过 PostgreSQL方案上限时才启用 Neo4j 读模型。

## 性能与验收问题

21. 性能目标与分期相互矛盾

P1-3 才建设超节点和 LOD，但验收标准直接要求 2k 节点/8k 边达到 30fps，见[方案 P1-3](/F:/python/数据资产/review/round-5/方案.md:51)、[方案 §6](/F:/python/数据资产/review/round-5/方案.md:73)。

同时 DoD 又规定 P1只要求至少 path 和 minimap，未强制 P1-3，见[方案 §8](/F:/python/数据资产/review/round-5/方案.md:88)。于是可能出现：

- 性能验收要求 2k/8k；
- 支撑该目标的 LOD/聚合却不在本轮必做范围；
- DoD 和验收标准不能同时满足。

应把性能目标分层，例如：

- P0：200节点/800边；
- P1完成LOD后：2k/8k；
- SVG降级：单独设更低上限。

22. `<500ms`指标没有定义测量边界

“邻域首屏 <500ms”需要明确：

- 服务端 P95还是本地单次；
- 是否包含网络、Vue更新和G6布局；
- 冷缓存还是热缓存；
- 测试数据规模；
- 哪个浏览器和机器；
- force 仿真何时算“首屏完成”。

否则该指标无法稳定验收。建议拆成 API P95、首次可见时间和布局稳定时间三项。

23. `30fps`也缺少可复现基准

“开发环境 Chrome”不够，至少要固定：

- Chrome版本；
- CPU/内存；
- Canvas/WebGL/SVG渲染器；
- 图数据生成种子；
- 平移、缩放、拖动的自动化脚本；
- P50/P95 frame time；
- 是否关闭 DevTools。

否则性能结论无法跨机器比较。

24. SVG降级要求与大图目标没有区分

现有页面在 G6失败时自动降级到内置 SVG，见[index.vue](/F:/python/数据资产/frontend/src/views/asset/graph/index.vue:936)。SVG组件承担 2k/8k 图的可能性很低。方案写“SVG不回归”但没有定义其容量和功能降级：

- 是否支持双击增量展开；
- 是否支持力导向；
- 最大节点/边数；
- 超限时是否只显示列表或提示。

必须给两种渲染器分别制定能力矩阵和验收规模。

25. 截断判断可能还需修复，方案没有识别

现有邻域接口在查询中一旦 `len(collected) >= limit` 就停止，但最终 meta 使用 `len(collected) > limit` 判断 truncated。由于 collected 通常不会超过 limit，这一字段很可能无法准确表示“还有更多结果”，见[graph.py](/F:/python/数据资产/backend/app/api/v1/graph.py:1173)。

渐进展开依赖可靠的截断信号，方案应把该契约修正列入 API 增强任务。

## 测试与实施计划问题

26. 测试清单混合了 P0、P1、P2，无法对应两批交付

方案要求新增至少8个测试，其中包含：

- P0搜索、展开、过滤、属性面板；
- P1超节点、path步骤条；
- P2 URL序列化。

见[方案 §6](/F:/python/数据资产/review/round-5/方案.md:74)。

但第一批只实施 P0，P2又是另行立项。第一批显然无法通过这组统一门禁。应按阶段拆分测试矩阵，而不是用一个“≥8”混合数量指标。

27. “邻域 API 契约”不能只写进 Vitest清单

后端 API契约至少需要：

- FastAPI/Pytest路由测试；
- 参数边界 1/2/3跳和limit；
- 权限 401/403；
- 物理键歧义；
- in/out/both方向；
- 截断；
- 环、自环、多边；
- 大度数节点；
- 数据库查询次数或执行时间。

Vitest可以测试前端 API适配器，但不能替代真实后端契约测试。

28. 验收命令没有完全遵循仓库既定门禁

方案写 `pytest -k relations -q`，但仓库规定最终后端验收是全量：

```powershell
python -m pytest tests/ -q
python -m alembic upgrade head
```

前端既定门禁包括 `pnpm run typecheck` 和 `pnpm run build`；实际 package 中还有 `pnpm test`，见[package.json](/F:/python/数据资产/frontend/package.json:7)。

计划虽提到“全量0 failed”，但实施步骤和命令应明确区分：

- 开发中专项测试；
- 合入前全量测试；
- Alembic迁移验证；
- typecheck双过；
- build预算；
- 浏览器视觉验收。

29. 计划没有给文件级影响范围

它只笼统限定 `graph/`、`components/` 和后端关系 API，但实际至少涉及：

- `frontend/src/api/asset.ts`
- Graph DTO 类型
- `AdvancedRelationGraph.vue`
- SVG降级组件
- `index.vue`
- 权限判定
- 后端 `graph.py`
- `schemas/graph.py`
- graph相关测试
- 可能的权限种子或迁移

没有文件级范围会导致不同任务交叉修改同一大文件，尤其 `index.vue` 和 `AdvancedRelationGraph.vue` 已经较大。

30. 缺少功能开关、灰度和回滚设计

大图布局和交互改造风险较高。建议至少定义：

- 新版图谱 feature flag；
- force布局异常时切回原布局；
- 新邻域响应字段向后兼容；
- Neo4j adapter 故障自动回PG；
- 浏览器本地视图状态版本；
- 生产灰度与回滚验证。

现稿只有“G6失败降级SVG”，不足以覆盖功能回滚。

31. 没有工期、依赖、负责人和交付物估算

用户要求“详细的改造计划”，现稿有优先级和两批顺序，但没有：

- 每项预计人日；
- 前后端依赖；
- 可并行项；
- 每批退出条件；
- 设计评审、API评审、性能基线、UAT和发布节点；
- 业务用户验收角色。

因此还未达到可排期执行的详细度。

## 建议的修订结构

建议把方案重写成四阶段：

1. 现状修正与基线测量  
   承认现有搜索、neighbors、force、节点抽屉和证据抽屉；通过截图、性能数据和用户走查确定真正痛点。

2. P0 交互升级  
   基于现有接口实现已加载节点聚焦、双击增量合并、正确折叠状态、Inspector、清晰视觉语法、图例过滤、权限补齐和截断提示。

3. P1 大图与治理体验  
   超节点、LOD、minimap、视口历史、path走查、review队列联动及可复现性能测试。

4. P2 Neo4j决策与适配  
   先复用/扩展现有 GraphSyncAdapter，完成 PostgreSQL与Neo4j的基准对比、数据模型、同步一致性、安全运维和 Go/No-Go评审，再决定是否部署。

总体判断：需求方向覆盖较好，但“现状盘点”可信度不足，导致多个核心任务重复或路由错误；Neo4j部分也仅是概念级方向，不足以实施。应先修正上述严重问题，再把它作为正式改造计划。全程仅进行了只读核查，未修改任何文件。
