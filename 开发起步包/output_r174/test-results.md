# 174 测试与验收记录（隔离库 data_asset_test，隧道 127.0.0.1:15432）

| # | 命令 | 退出码 | 摘要 |
|---|---|---|---|
| 1 | `pytest tests/test_quality_governance_service.py -q` | 0 | 36 passed（状态机矩阵/归并/复发/抑制/部分唯一索引/乐观锁/事件审计/数据范围/种子幂等） |
| 2 | `pytest tests/test_quality_governance_api.py -q` | 0 | 20 passed（路由优先级/401/RBAC/数据范围/全生命周期/同经办人验证403/409锁/export六硬约束） |
| 3 | `alembic upgrade head`（隔离库） | 0 | c1d2e3f4a5b6 → d5e6f7a8b9c0 |
| 4 | `alembic downgrade -1` | 0 | 回到 c1d2e3f4a5b6；五表+序列+部分唯一索引+12权限码+30授权全部消失（旧表未动） |
| 5 | `alembic upgrade head`（往返再升） | 0 | 五表/序列/部分唯一索引/12权限码/30授权全部恢复 |
| 6 | `seed_quality_governance --dry-run` | 0 | 17 清单+5 会议问题+T7 monitoring_gap，committed=false（零写） |
| 7 | `seed_quality_governance --apply`（首次） | 0 | created=17/5/1，committed=true |
| 8 | `seed_quality_governance --apply`（二次） | 0 | created=0，existing=17/5，t7=duplicate（零新增） |
| 9 | `pytest tests/ -q`（全量） | 0 | **1397 passed, 1 skipped, 0 failed**（171 基线 1341 + 新增 56；1944s） |
| 10 | `pnpm run typecheck` | 0 | tsc --noEmit + vue-tsc 双过 |
| 11 | `pnpm run build` | 0 | main 657.2KB/graph 404.5KB/css 103.5KB，gzip 预算三绿 |
| 12 | `npx vitest run`（全量） | 0 | **262 passed**（253 基线 + 9 新增 plan174QualityLedger） |
| 13 | `tools/s9_e2e_r174.py` | 0 | **S9 十三场景 13/13 PASS**（s9_e2e_results.json） |

## 安全静态扫描（S8）
- 敏感信息：新文件无密码/Token/身份证/电话/患者样本（grep 命中仅为“不返回敏感字段”注释）；
- 源库写风险：新模块零源库连接、零 DML/DDL（源侧执行仍归 run_probe.py 受控连接器）；
- 大表全扫风险：无对 LAB_RESULT/EXAM_MASTER 等源表的任何 SQL（种子只读平台 asset schema 与模板 JSON）；
- 迁移边界：d5e6f7a8b9c0 全部 DDL/DML 限定 schema=asset；downgrade 只删本迁移对象。
