# 独立初审（ZCode，互不通气起点）

> multi-verify round-3 · 问题清单草案 · 每条=编号|位置|问题猜想|严重度|验证方法

| 编号 | 位置 | 问题猜想 | 严重度 | 验证方法 |
|---|---|---|---|---|
| Z1 | backend/app/api/v1/graph.py overview 端点 | 12702 表全库聚合 ~23.5s（uvicorn.log 三次 23.4~24.9s；curl 23.5s），无预聚合/缓存 | 高 | 复现v4 + ov_probe.json meta（matched=12702） |
| Z2 | 前端 http 层 10s 超时 × overview 23.5s | 首屏必现「图谱加载失败」error-panel（performance ms=10008 恰为阈值） | 高 | V4_D0/V4_E1_fail 截图 + 关联编号 |
| Z3 | AdvancedRelationGraph.vue:226-238 | force alpha:0.35 过低（G6 v5 默认 1）→ 力导推不开，节点堆中心成墨团 | 高 | S3_center_zoom.png（圆套圆）+ dark 94%/center 99.5% |
| Z4 | AdvancedRelationGraph.vue:203-205 | 注释自认「force 会挤到中心重叠」但 explore/聚焦仍走 force（usesPresetPositions 只覆盖 hierarchy/layered）——回归防护缺失 | 高 | 读源码 :187,:203,:445-450 |
| Z5 | AdvancedRelationGraph.vue:337-352 | labelWordWrap:false 与 labelMaxLines:5 矛盾；堆叠时标签互叠；漂浮中文标签疑 preset 坐标与 force 位移混用 | 中 | S3_center_zoom.png 漂浮「住院主记录」 |
| Z6 | RelationGraph.vue:445-450 + graphLoadPolicy.ts:22 | SVG 降级（>220 节点）fallback=buildLayered 网格，行距 92px 装不下 168px 宽标签+42~68px 节点；force 模式名落到 layered 语义错位 | 中 | 读源码 buildLayered :320-336 + materializeLayout |
| Z7 | GraphToolbar.vue:4 / index.vue | el-segmented 在运行页 DOM 查询为 null（hasSegmented:false）——EP 版本渲染结构或 v-if 条件致自动化/可能用户不可达 | 中（定性存疑） | v3/v4 evaluate 输出 |
| Z8 | graph.py overview meta | total_relations=12702=表数，字段口径错位 | 低 | ov_probe.json meta |
| Z9 | 168 报告 §4 | 「五类浏览器截图验收」未做即随 r166 发布生产——发布门禁缺口（流程问题） | 中 | 168_报告.md §4 与发布时间线对照 |

验证方法补充说明：Z1/Z2/Z3 已有原始输出；Z4-Z6/Z8 为源码行级证据；Z7 需三方独立核实 DOM。
