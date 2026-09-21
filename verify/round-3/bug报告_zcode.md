# bug 报告（ZCode 起草）：关系图谱「内容叠加、不直观、还不如之前」

> multi-verify round-3 · B 模式 · 2026-08-30
> 用户原话：系统中的关系图谱治理很差，还不如之前的，看看能否修下，很多进去后里边的内容都叠加，一点也不直观
> 核查对象：`frontend/src/views/asset/`（graph/index.vue、components/AdvancedRelationGraph.vue、components/RelationGraph.vue、components/GraphToolbar.vue、graph/graphTransform.ts）+ `backend/app/api/v1/graph.py`
> 环境：本机 dev 栈（uvicorn 8000 + vite 8848）+ 隔离库灌入**生产真实图数据**（12702 表 / 1329 关系，2026-08-30 从 10.10.8.83 生产库只读导出，导出文件 graph_data_export.json）
> 背景：图谱最近一次大改 = 168 号 P0 改造（explore 默认 force、SVG 降级、Inspector 等，已随 r166-20260830 发布生产）；168 报告自认「真实浏览器截图仍待补验」

## 1. 现象与复现（已执行命令+原始输出）

### P1 首屏「图谱加载失败」错误面板（复现 ✔）

- 复现脚本 `复现v4.py`：goto `http://127.0.0.1:8848/#/asset/graph` → 等 45s → 截图 `复现截图/V4_D0_overview_settled.png` 与 `V4_E1_fail.png`。
- 截图实拍：页面中央 el-result 错误面板——标题「图谱加载失败」、副标题「接口超时或服务异常，请稍后重试」、关联编号 `graph-load-20260830163111123-5257`、按钮「重新加载/重置条件」。
- 后端日志（uvicorn.log 原文）：
  - `GET /api/v1/graph/overview 200 24939.39ms` / `23499.26ms` / `24105.71ms`（三次）
  - curl 实测 `http 200 time 23.5s`
- 前端 performance 条目（复现_原始输出.json）：`{'api': '/graph/overview', 'ms': 10008}` —— 恰为前端超时阈值 10s 处 abort。
- overview 响应体（ov_probe.json）：`meta.total_relations=12702, matched_relations=12702, returned_relations=1, truncated=true`；inner nodes=17（系统聚合层）。

结论：**后端 overview 聚合 12702 表需 ~23.5s，前端 10s 超时 → 首屏必然错误面板**。生产同数据同代码 → 生产用户进图谱页第一眼就是报错（或长时间 loading 后报错）。这直接构成「还不如之前的」（改造前 overview 分层视图可正常出图）。

### P2 节点堆叠成墨团、标签互相叠压（复现 ✔，用户主诉）

- 复现脚本 `复现.py`（v2）：全局搜索框聚焦 `HIS.PAT_VISIT`（placeholder「搜索表名、中文名、Schema 或五段物理键」+Enter）后，画布渲染 1~2 跳邻域。
- 截图 `复现截图/S3_explore_expand_multi.png`、`S4_search_focus.png`；中心放大 `S3_center_zoom.png`。
- 视觉判读（放大图）：节点**圆套圆完全重叠**、表名标签互相叠压仅可辨认 HIS.PAT_VISIT/HIS.PAT_MASTER_INDEX 少数几个、周边**漂浮未连接的中文标签**（「住院主记录」「在院记录」）。
- 像素量化（PIL，画布区 230,200-1580,980）：S3/S4 `dark=94.1%`、`center_dark=99.5%`（对照正常空白画布 0.2%/0.1%）——节点+标签+连线全部堆在中心形成墨团。
- 对照 S1/S2（搜索聚焦前）dark=0.2%：堆叠发生在邻域图渲染之后。

### P3 模式切换控件自动化不可达（复现 ✔，定性存疑）

- v3/v4 evaluate：`document.querySelector('.el-segmented')` 为 null（hasSegmented:false），但 GraphToolbar.vue:4 确用 `<el-segmented>`。
- 可能是 Element Plus 版本渲染结构差异或条件渲染（`v-if`），导致 E2E/自动化无法切换「关系探索」——也可能真实用户同样点不到（需独立审查验证 DOM）。168 报告「五类截图待补」未补成与此相关。

## 2. 根因假设（文件:行）

| # | 位置 | 假设 | 严重度 |
|---|---|---|---|
| R1 | `backend/app/api/v1/graph.py` overview 端点 | 全库 12702 表逐级聚合无缓存/无预聚合，23.5s 超前端 10s 超时 | 高 |
| R2 | `frontend/src/views/asset/components/AdvancedRelationGraph.vue:226-238` | G6 v5 force 布局 `alpha:0.35`（v5 默认 1）+`alphaDecay:0.022` 力导过弱，节点推不开堆中心 | 高 |
| R3 | 同文件 `:203-205` 注释 | 开发注释自认「不用 G6 force（会挤到中心重叠）」却让 explore/搜索聚焦走 force（`usesPresetPositions()` 仅 hierarchy/layered）——已知坑未防 | 高 |
| R4 | 同文件 `:337-352` 节点标签 | `labelWordWrap:false` + `labelMaxWidth:168` + `labelMaxLines:5` 组合矛盾（不换行则 maxLines 无效）；`labelPlacement:"bottom"` 在节点堆叠时标签互叠；漂浮中文标签疑 label 与节点错位（preset 坐标与 force 位移混用） | 中 |
| R5 | `frontend/src/views/asset/components/RelationGraph.vue:445-450` | SVG 降级引擎（>220 节点强制切换，graphLoadPolicy.ts:22）layout fallback=buildLayered 网格（列距 260/行距 92），但 label 最宽 168+节点 42~68px，密集邻域仍叠；且 explore/force 模式名落到 layered 语义错位 | 中 |
| R6 | `frontend/src/views/asset/graph/index.vue:486-497` + graphLoadPolicy | 前端 10s 超时阈值（http 工具层）与 overview 实际 23.5s 不匹配；无重试/降级到轻量层 | 高（与 R1 联合） |
| R7 | graph.py overview meta | `total_relations=12702`=表总数，relations 语义字段错位（口径 bug） | 低 |

## 3. 影响面

- 生产（r166-20260830 前端 + r166 后端镜像）：所有用户进「关系图谱」首屏报错；改用搜索聚焦/表详情进入邻域图则遭遇节点墨团——即用户主诉。
- 168 号「五类浏览器截图验收」至今未补，本报告的 V4/E 系列截图即为该验收的实测结果（不通过）。
- 表详情页「当前表关系图」（table-detail 复用 RelationGraph）与关系复核中心图谱视图同样受 R2/R4/R5 影响。

## 4. 最小修复思路（供审查，不在本轮实施）

1. P1：overview 后端加系统层预聚合/缓存（或 SQL 单查聚合，消除 Python 全表遍历）；前端 overview 失败降级到 system 层轻量请求而非错误面板。
2. P2：force 布局 alpha 提到 0.8~1、alphaDecay 降到 ~0.028 默认；或 explore/搜索聚焦改用预计算环形/层次布局（复用 computeCircularSpreadPositions）；标签开启 wordWrap。
3. P3：核对 el-segmented 渲染 DOM 与 v-if 条件，补 168 承诺的五类截图验收。

## 5. 尝试记录（如实）

- v1 复现失败（二次 goto 触发 refresh 401 登出）；v2 复现墨团但当时误归因双击展开；v3 模式切换选择器失败；v4 干净复现错误面板。四个脚本与全部截图/JSON 原样留档于本目录。
