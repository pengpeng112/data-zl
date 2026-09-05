# R6-1 130 覆盖度核对表（163 执行会话产，2026-08-29）

> 口径：130 的 A01–A28 验收条目逐条标注「已被 144/146/153/161（及后续 163）吸收（引证据）/仍开放」。
> 仍开放项按 163 R6-1 要求转入等待域清单（见 §7 报告表）。

| 编号 | 条目 | 状态 | 证据（一句话） |
|---|---|---|---|
| A01 | 测试库身份/权限 | 已吸收 | `tests/conftest.py:44-47` 强制 APP_TEST_DB_URL 且显式拒 APP_DB_URL；`app/core/database_guard.py` 连库前门禁 |
| A02 | Alembic 往返 | 已吸收 | h8d9e0f1a2b3、i9e0f1a2b3c4 隔离库往返 PASS（55 2026-08-24 条）；163 R2 迁移链继续以 head=b0c1d2e3f4a5 单头推进 |
| A03 | 后端全量 0 failed | 吸收中（本会话落数） | 161 基线 1175 passed/1 skipped/1 failed；163 R1 修 NF-1（plan127 25 passed）；R7 复跑全量为本表终值 |
| A04 | 前端三件套 | 已吸收（R5/R7 复跑） | 161 门禁 typecheck 0 错/168 tests/build 预算 PASS（161 执行报告）；R5 子任务完成后再验 |
| A05 | 写路由权限 | 已吸收 | 153 后端高危/细粒度授权批次 + security_audit 冒烟 9 passed（163 R0 实测） |
| A06 | 源库 SQL 安全 | 已吸收 | db_connectors 只读校验+大表门禁；sjzc 受控连接器；161 P1-1 pymssql 占位符口径 |
| A07 | 图谱层级下钻 | 已吸收 | 146 E1（图谱 path 子模式/双端选择/1–8 跳）；44efaa0 前端 batch |
| A08 | 图谱关系 | 已吸收 | 139 导入 592 声明 FK/729 依赖（142 收口）；132 关系复核升级 |
| A09 | 图谱视觉 | 已吸收 | 44efaa0 graph polish（行点击联动 path、labels） |
| A10 | 质量/总览 | 部分闭合于 R5 | 146 E10 剩余「quality 页拆分共享组件」属 163 R5 批；其余 146 E10 核心 2026-08-24 已落地 |
| A11 | 关系复核 | 已吸收 | 132 报告（relation review upgrade）+ 2a9a259（复核证据系统归属+61 草稿回填） |
| A12 | 配方 | 已吸收 | 137/138：v8c9d0e1f2a3 版本化、z2f3a4b5c6d7 幂等索引修复、dry-run/inactive 默认 |
| A13 | 查询/指标 | 已吸收 | 144 黄金用例+真实指标引擎（722ff56、5185bd5）；48 项口径由 144 S 批接管 |
| A14 | 数据产品/调度 | 已吸收（现状符合） | 生产实查：asset_query_schedules 27 条全部 enabled=false（130 要求的"27 调度仍 enabled=0"保持）；asset_scheduler_jobs 50 success/1 registered；153 P 批完善调度与发布 |
| A15 | 夜间任务 | 已吸收 | identity nightly 每夜在跑；08-28 熔断事件已裁决并 08-29 08:30 自动复核（automation-89b8f2ec） |
| A16 | 字典关闭态 | 已吸收 | 153 字典链路收口 + dict push smoke（scripts/_smoke_medical_push.py）；未授权业务库写入 0 |
| A17 | 发布 | 已吸收 | p153 生产发布于 8.83（commit 13ef9e8 docs 记录） |
| A18 | 浏览器真实登录 | 已吸收（历史证据） | e2e_graph_acceptance/e2e_graph_g7_acceptance 脚本与 122-era 浏览器验收记录 |
| A19 | 回滚 | 已吸收 | 8.83 镜像链 p153+p144-149 releases 与 previous 版本保留（139/153 发布记录） |
| A20 | 文档/Git 一致 | 持续项 | 每次会话 README/55 登记+目录自检（163/本会话均执行）；无终态 |
| A21 | Dify 网络/配置 | 已吸收 | dify_quality_client.py:42 host allowlist 拒绝（ssrf_blocked）；未配置关闭态 |
| A22 | Dify 输入安全 | 已吸收 | digest 契约（hospital_llm_client/dify_quality_client）+ 153 A 系列测试 |
| A23 | Dify 出站安全 | 已吸收 | 两客户端 ssrf_blocked 拒绝路径（grep 证据）；超时/超大响应拒收 |
| A24 | Dify 契约 | 已吸收 | test_153_g1_g3.py 契约补强（153 G 批） |
| A25 | Dify 幂等/恢复 | 部分开放 | digest+prompt 复用已实现；视觉验收部分归 W5（127/130 余项人工验收） |
| A26 | Dify RBAC/审计 | 已吸收 | 153/161 细权限闭环 + security_audit 断言 |
| A27 | Dify 结果安全 | 已吸收 | 130 U10 呈报不自动改 finding 边界；客户端只读结果处理 |
| A28 | Dify 真实 E2E | 仍开放（BLOCKED） | 受控 Key/已发布 Workflow 未提供 → 关闭态 PASS 成立、E2E BLOCKED；归等待域（用户授权后做） |

**仍开放/转等待域汇总**：A28（E2E 需受控 Key，用户授权）；A25 视觉验收部分（W5）；A14 的 27 调度现状核对（163 R6-2 执行）；A20 为持续治理无终态。其余 24 项均已吸收且有证据锚点。
