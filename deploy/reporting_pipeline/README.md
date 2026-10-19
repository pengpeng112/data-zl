# deploy/reporting_pipeline —— R189-T1 报送管道生产审阅包（E08 交付）

> 包 ID：R189-T1-ENGINEERING-20261019-v1.2。本目录是**静态生产审阅材料**，
> 不代表任何生产部署已执行。状态权威：原 run checkpoint 的
> `daily_t1.engineering_execution_20261019`。

## 本包内容

| 文件 | 用途 |
|---|---|
| `生产接入审阅清单.md` | 上线前逐项审批矩阵：控制库迁移、DataX 白名单、relay 注册、凭据、写者交接、逐表启用 |
| `运行手册草稿.md` | 日常运维：T+1 周期、COMMIT_UNKNOWN 处置、告警处置、月重扫、回读对账 |
| `回滚方案.md` | 代码/迁移/配置三层回滚与数据回滚边界 |
| `观测计划.md` | E10 分组上线后至少 7 业务日的观测指标与判定门 |

## 已验证 / 未验证边界（截至 2026-10-19）

- 已验证（本地+隔离）：单元 173 例全过、ruff 干净；迁移
  `e3f4a5b6c7d8` 在 data_asset_test 上升级/回退/再升级往返通过，
  5 项约束核验（outbox 字节往返/唯一、月覆盖复合唯一、租约唯一、
  缺口账本读写）全过，集成测试 3 例全过（`tests/reporting_pipeline_integration/`，
  需 `source tools/dev_env.sh`）。
- 未验证（需真实环境与批准）：Oracle 源读、DataX 真实插件协议、
  stage 写通道、正式装载、企微 relay 真实联调、生产发布/调度。
  PG 集成**不**冒充 Oracle 事务/LOB 兼容（E09 前提）。

## 上线总门禁（E09/E10 前必须齐备）

1. E08.isolated_integration = VERIFIED（已达成，见上）；
2. E08.production_review_pack = READY（本包审阅通过）；
3. 具体的生产/联调批准（逐对象、逐操作、逐额度）；
4. relay 管理员完成源注册/订阅/secret_ref 配置并给出测试订阅。
