# R211 A4/A5 修订设计与本地整改记录

> run: r211-20261008-zcode-r214b ｜ 日期: 2026-10-08
> 原则（211 §6.1）：使用既有能力完成可验证改进，不借"架构优化"重建系统；缺业务裁决不猜测。

## FIX-211-01（P1，已实施+验证）

- **问题触发**：`POST /api/v1/ai/context/resolve` 全量 500"上下文构建失败"；批次A全量 pytest 4 失败（plan144_db/test_ai_context_contract×3 + test_value_domain_injection×1）。
- **根因与证据**：210 S8 工作区 WIP 新增 `_security_policy_block()` 使用 `sqlalchemy.select`，但该函数未导入（文件仅 `_load_*` 一处函数内局部导入），`ai_context_builder.py:264` NameError。批次A stash-bisect 已证实失败源于此 WIP，非批次A引入。
- **最新需求ID**：R211-002（211/212链）；关联 U05（AI上下文能力）。
- **目标行为**：AI 上下文构建成功并在快照中含 `security_policy` 段（structure_only 契约）。
- **文件范围**：仅 `backend/app/services/ai_context_builder.py`（+1行函数内导入）。
- **兼容性**：纯导入补全，无契约变化；`security_policy` 段形状沿 210 S8 设计（schema_version ds-security/b02_v1）。
- **权限/审计/迁移**：无变化（只读构建路径）。
- **测试ID**：tests/plan144_db/test_ai_context_contract.py（3）、tests/test_value_domain_injection.py（1）——断言未改一字。
- **验证**：修后 12/12 passed（2026-10-08）。
- **回滚**：删除该行即回到修复前（不推荐——回到500）。

## FIX-211-02（P3 文档时效，已实施）

- 55 当前批次表 207 行尾巴"剩余=生产发布…与209独立验收"过期表述 → 改为"生产迁移与代码已随210 S10落地；209独立验收已执行（09-29）；剩余=专项生产验收（旧记录盘点回填、真实规则试跑、worker运行配置、完整调度周期、真实整改复测）+试点+T35"。
- 依据：210 S10 生产执行报告 + 209 测试报告（211 §4 线索3核清）。

## 评估后不修/不越界项（保留原因）

| 项 | 原因 |
|---|---|
| 治理队列自然键查重（R211-041） | 属205线B剩余，211不越权重跑live查重；离线包准备见205线 |
| graph_sync 接真实图库 | 设计决策 fail-closed（UnavailableGraphAdapter），无新需求输入（F-211-03） |
| AI注释建议占位端点 | 端点显式自述"待P5.5"，非假装实现；接真实生成属新需求（F-211-03） |
| 通知铃铛接线（R211-003） | 待产品排期（NEEDS_CONFIRMATION） |
| platform_admin 隐式全码（R211-004） | 待后端工单裁决（NEEDS_CONFIRMATION） |
| 全部待输入族（R211-030/040/060/070/080/091 等） | 按 214 §6 挂起待输入，不擅自替用户裁决业务口径 |

## 优先级顺序核对（211 §6.1）

隐私与误写门禁（无新缺口）→ 关键判断/数据口径（FIX-211-01 即 AI 判断支撑链）→ 业务闭环（无本地可逆项缺失）→ 可观察性与恢复（212 O 项覆盖）→ 体验/维护（FIX-211-02）。
