# 中期 checkpoint（2026-09-09，T0/T2 完成，T1/T3 待动态窗口）

## 已完成
- T0：432 后端端点 / 74 前端路由 / 隔离库连通（115 表）/ vite proxy 8848→8000
- 基线-前端：typecheck EXIT=0；vitest EXIT=0（147s）；build EXIT=0（gzip 预算三绿）
- T2-静态（3 只读代理 + 本人核实）：
  - 前端 10 条（2 P2 双击无锁 + 表详情路由缺 auths；7 P3）→ 全部定位已核实存在
  - 后端 API 层 10 条（P0×1 governance.py:552 approver 自我提权——本人核实属实；P2×4；P3×5）
  - 后端服务层 11 条（P2×6 并发锁/超时缺失/异常未脱敏/cookie secure；P3×5）

## 已知问题台账（铁律5 分类基准）
- 171 §10.5：图谱聚合边标签 [object Object]（P2 已登记）
- 171 §6/R4：165 T7 BLOCKED（PACSREPORT side-b）；168 P1（Minimap/视口历史/LOD 等）；166 P2（对账矩阵/趋势/互链/AI 入口/批量导入）
- exceptions W1-W9（output_r171）：W5 169 工装 A3/A4 状态依赖；W8 /api/health 401 系全局鉴权设计
- 代码内 TODO/FIXME：0（grep 证实）

## 运行中
- backend pytest 全量：出现 E 标记（≥7，error 类），完成后归因分类

## 动态窗口计划（pytest 完成后立即执行）
1. reseed 隔离库（import170.py，APP_DB_URL 显式指向 15432）
2. 本地 uvicorn :8000（APP_DB_URL=隔离库）+ /health 冒烟
3. 造 approver 角色测试 token → 动态实证 P0 提权
4. qa_probe.py 五轮探测（未认证/坏token/合法只读/fuzz/错误语义）
5. vite dev :8848 → qa_frontend.py 逐页 + 三视口 + XSS + 双击 + 过期会话 + 后端停机
