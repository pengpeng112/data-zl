# 174 执行进度（执行工件，非平行计划）

| 批次 | 状态 | 证据 |
|---|---|---|
| S0 基线与保护 | DONE | Alembic head=c1d2e3f4a5b6（与方案记录一致）；探查域基线 110P；测试库隧道 15432 连通；用户改动域零接触（git status 对照） |
| S1 契约和迁移 | DONE | 迁移 d5e6f7a8b9c0（手写 upgrade/downgrade 对称）；隔离库 upgrade 成功；往返验证见 test-results |
| S2 领域服务 | DONE | quality_governance_service.py；36 服务测试全过 |
| S3 来源适配 | DONE | probe_template/quality_rule/manual 三适配器；run_key 幂等验证 |
| S4 权限与身份 | DONE | 12 权限码迁移种子+静态目录；中间件前缀豁免（发现并修复 /api/v1/quality 粗门禁误伤新前缀）；assignment-options 只读接口 |
| S5 API 与导出 | DONE | 三前缀路由；命令 envelope；导出六硬约束；20 API 测试全过 |
| S6 种子工具 | DONE | dry-run 零写；apply 17 清单+5 会议问题+T7 monitoring_gap；二次 apply 全 existing/duplicate 零新增 |
| S7 前端 | DONE | api/quality.ts + 4 页面 + 路由/菜单；typecheck 双过；build gzip 预算三绿；9 前端测试 |
| S8 静态验收 | DONE | 后端全量 1397P/1S/0F；前端 262 tests；迁移往返；安全扫描 4 项 |
| S9 端到端 | DONE | 13/13 场景全过（s9_e2e_results.json） |
| S10 交付 | DONE | 执行报告+结果 JSON+README/55/174 状态同步；生产步骤未执行（未授权） |

## 过程中发现并修复的问题
1. 中间件 `ROLE_PATH_MAP["quality"]="/api/v1/quality"` 粗前缀把 `/api/v1/quality-issues|controls|observations` 一并要求 quality_admin，普通处理人被 403——新增 `FINE_GRAINED_Rbac_PREFIXES_174` 豁免（三模块每个路由都有显式 require_permission，安全性不降级）。
2. 模型 COALESCE 唯一索引表达式初版用 func.coalesce(字符串) 会产生字面量——改 sa.text 表达式。
3. 前端命令 envelope 交叉类型导致 excess-property 报错——body 放宽为 Record<string, unknown>。
4. 测试侧三处笔误（抑制到期场景先落终态、事件断言口径、种子计数断言）修正后全绿。

## 设计裁决记录（小歧义最小合理假设）
- run 端点不伪造执行：只做检测器可用性校验+审计+执行器提示（探查真实执行仍归夜间 run_probe.py，源侧走 8.83 受控连接器）。
- 观测 created 事件自带 observation_id；observation_linked 事件只在持续 FAIL/PASS 挂接既有问题时发（避免建单时双事件）。
- 我的任务/科室任务用独立路径 /quality/issues/mine|department 而非 query（菜单高亮需要）；页内仍可自由切范围。
- issue_code 序列为全局序列+月份前缀（唯一性由序列保证，月份仅展示）。
