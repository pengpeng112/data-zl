> 类别：模块执行报告

# 167 AI 巡查演示界面与 AI 写 SQL 工作台执行报告

> 结论：v1.1 S0→S6 已完成；隔离库门禁全绿，并按用户追加授权同步升级至 8.83。完成时间：2026-08-30。

## 交付

- AI 质控页保留原问题分析，追加引擎状态与巡查演示。计划卡仅展示“每日 02:00 / 未启用调度”，不连 `QualityTask`。
- 3 张目标表来自平台质量 run 49 的只读聚合证据；巡查复用 preview HMAC 与异步 job，按 `patrol_run_id` 聚合。
- `/asset/ai-sql` 和 generate/history 已落地。上下文仅含所选表+一跳正式关系、JOIN 三要素和相关 confirmed 值域，上限 20 表/40 关系/24KB。
- question 先脱敏；Oracle 11g 只读；围栏清洗、截断一次重试、风险扫描；恒 `executed=false`。审计仅存摘要/hash/context digest。
- 未触碰 `sql-workbench`；零新依赖、零迁移、零患者数据进入模型。

## 门禁

| 项目 | 结果 |
|---|---|
| patrol/quality | 61 passed |
| context | 20 passed |
| ai_sql | 7 passed |
| 后端全量（data_asset_test） | 1287 passed，1 skipped，0 failed；2620.02s |
| 前端全量 | 31 files / 210 tests，0 failed |
| 前端三件套 | 双 typecheck、build、gzip 预算 PASS（656.3/700KB；404.6/430KB；100.3/110KB） |
| Alembic | 167 本任务零迁移；服务器同步时补齐已完成前置 165 的既有手写迁移，生产 current=`c1d2e3f4a5b6` |

## 真实模型

`hospital_llm / deepseek-r1`，reachable=true，8996ms，脱敏响应“只读分析已接通。”；8.83 受控容器真实调用，非 mock、无患者数据。

## 截图

- [AI 巡查演示](output_r167/screenshots/ai-quality-patrol.png)
- [AI 写 SQL 工作台](output_r167/screenshots/ai-sql-workbench.png)

截图使用隔离视觉夹具模拟只读 API 响应，以稳定核对布局/空态/证据链，不冒充生产业务结果。

## 发布与回滚

- 后端 `data-asset:r167-20260830`，容器 healthy；AI SQL/巡查路由已注册，路由总数 343。
- 前端 `/opt/data-asset/frontend-dist/releases/r167-20260830` 原子切换；previous=`p144-149-20260826`。
- 升级前生产备份：`/opt/data-asset/backups/data_asset_pre_r167_20260830.dump`（10,758,931 bytes）；随后仅补齐前置 165 的 `b0→c1` 迁移，167 自身无迁移。
- 后端回滚标签保留 `data-asset:w10c-202608291223`；需要回退前置 165 时须按其迁移审批单独执行，不自动 downgrade。
- 旧服务器启动脚本忽略镜像变量的偏差已纠正，详见 exceptions。

## DoD / 等待域

S0–S6、专项/全量、真实模型、截图、README/55/JSON 均完成。等待域仅保留未来真定时调度（另立项）、更强内网模型环境切换，以及继续走既有人工审核的 SQL 草稿执行链。
