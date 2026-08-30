# 审查_zcode（GLM 独立初审 round-4，起草后立即固化）

> 对象：`开发起步包/165_数据问题AI探查与入库执行计划.md`（sha256 8841e821…）与 `166_值域与探查问题展示导出功能开发计划.md`（sha256 851c07bb…）。固化后不改；外部审查若推翻走分歧表。

## 165 自审（逐条）

1. **【缺口·执行器核心】"何为发现"未定义**：模板执行后 metric_value 与 threshold 的比对/触发逻辑没写——应定义：`trigger`（如 `mismatch_rate > threshold`）成立才生成 finding 行，不成立仅进 run 摘要（否则每轮全量入库刷行）。severity 可随超限幅度分级。
2. **【缺口·双源模板】R-CNT/R-KEY 需要跨两个库取数比对**（HIS 侧+ODS/JHEMR 侧），现模板 schema 单 `sql` 字段不够——应扩展 `sides[]`（side_name/source_code/sql）+`compare`（按键 JOIN 后比对的 Python 侧逻辑或第三条 SQL 形态）。
3. **【缺口·终态审计字段】** findings 表缺 `resolved_by/resolved_at`（快照），人工终态只有 note 不够追溯——补三列，完整历史走审计日志。
4. **【矛盾·权限顺序】** 165 E4 只读 API 挂 `probe.finding.read`，但权限码种子写在 166 F7——顺序倒置。应在 165 E1（或 E4）就把 `probe.finding.read` 幂等 seed 进去，166 F7 只补 `probe.finding.manage`+矩阵。
5. **【缺口·metric 类型】** metric_value 应定 numeric+新增 metric_unit（"%"、"条"、"例"），避免文本混型。
6. **【待写明】连接方式**：run_probe 按 `source_code` 经平台注册数据源+db_connectors 只读门禁连接（凭据不落脚本参数）。
7. 【同意】五类模板、夜间约束、AI 不裁决终态、X1–X4 等待域、幂等键设计。

## 166 自审（逐条）

8. **【过设计·mock 开关】** `APP_PROBE_API_READY` 前端开关多余——空态+提示文案已够联调（165 未就绪=API 404/空数据）。建议删除开关，改"API 不可达/空数据→引导空态"。
9. **【过严·状态机】** "resolved→false_positive 不允许"不对：人工纠错（先误 resolve 后发现是误报）应允许任意人工终态互转（附理由），仅执行器不可碰终态。简化为：open↔confirmed/false_positive/resolved 全开放+理由必填+审计。
10. **【缺口·菜单挂载】** 两个新页面未写挂载菜单组——建议 `/value-domains` 挂"数据治理"组、`/probe-findings` 挂"质量管理"组（与既有 QualityFinding 相邻），图标/排序按仓内惯例。
11. **【缺口·XSS】** F4 evidence_sql 代码块展示必须转义测试断言（长 SQL/含尖括号注释）。
12. **【缺口·契约依赖】** 166 mock 依赖 165 E4 响应模型——165 应定义 Pydantic 响应 schema（findings 列表/详情/runs 字段名），166 按契约 mock，联调才不返工。
13. 【同意】导出四硬约束复用 146 E7、权限矩阵、零迁移、P2 后置、按页一次触碰。

## 总体

两计划骨架成立；主要弱点集中在 165 执行器语义（触发/双源/审计字段）与 165↔166 的权限和契约顺序。上述 7 条缺口/矛盾建议全部采纳进 v1.1 修订。
