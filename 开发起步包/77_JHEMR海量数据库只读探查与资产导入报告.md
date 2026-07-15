> 类别：证据报告

# JHEMR 海量数据库只读探查与资产导入报告

## 1. 结论

2026-07-14 已完成电子病历 Vastbase 源库只读探查、文档对照、机器可读资产包生成和生产平台资产库导入。用户提供的默认库 `vastbase` 仅能看到系统对象；通过只读数据库目录确认实际业务库为 `jhemr`，后续采集均针对该库。

源业务库只执行元数据目录查询和连通性 `SELECT 1`，事务只读状态已确认；未执行 DML、DDL、锁表、全表业务数据扫描，源库写入为 0。

## 2. 数据源与范围

| 项目 | 结果 |
|---|---|
| 数据库类型 | Vastbase（PostgreSQL 协议兼容，服务端报告 9.2.4 兼容版本） |
| 目标 | `10.10.8.177:5432/jhemr` |
| 平台 source_code | `jhemr_vastbase_10_10_8_177` |
| 平台 system_code | `JHEMR_VASTBASE` |
| 写策略 | `readonly` |
| 业务 Schema | `jhemr`、`jhnis`、`report`、`jhcdr`、`jhfile`、`fxcx` |
| 对照文档 | `系统表结构/电子病历数据库.md` |

按对象统计，`jhemr` 894 表/99 视图、`jhnis` 370 表、`report` 34 表、`jhcdr` 13 表、`jhfile` 10 表、`fxcx` 1 表，共 1,421 个表或视图对象。平台最终导入 24,697 个字段及 6 个 Schema 节点。

## 3. 文档对照

- 文档索引识别出 542 个表名，其中 532 个可在活库六个业务 Schema 中匹配。
- 未匹配 10 项：`HAUTH_USER_VS_GROUP`、`HMR_PRINT_CATALOG_DICT`、`JHCDR`、`JHFILE`、`JHGWVGATE_PARAMETER_DICT`、`JHGWVGATE_TREND_DATA_MONITOR`、`JHMHT_FREQ_DICT`、`JMR_FILE_CALLBACK_RECORD`、`REPORT`、`SYS_TEMP_FBT`。
- `JHCDR`、`JHFILE`、`REPORT` 更像 Schema/章节标识；其余项目保留为“文档存在、活库未匹配”，不伪造为已采集资产。
- 活库快照是当前结构权威依据，旧文档用于中文含义和范围对照，不覆盖活库事实。

## 4. 关系保留方式

源库目录未发现业务外键。为避免丢失现有结构线索，从 99 个视图定义中静态解析并去重得到 283 条“基础表到视图”依赖，已导入 `asset_relations`，统一标为 `domain=JHEMR_VASTBASE`、`validation_level=static_view_sql`、`validation_status=candidate`、`confidence=B`。

这些关系是可追溯的视图 SQL 静态依赖，不等同于数据库外键或经过数据 JOIN 命中率验证的强业务关系。后续 AI 必须继续保留其候选等级；若提升为正式关系，应另做只读数据验证并记录指标。

## 5. 平台导入与生产验证

平台导入脚本为 `backend/scripts/import_jhemr_vastbase_assets.py`。脚本只读取离线快照；默认 dry-run，正式写平台库必须显式提供确认串。重复导入仅替换本 source_code 的表、字段、Schema 和本 domain 的关系。

首次导入因既有关系全局编号冲突而整笔事务回滚；随后将关系编号改为从平台当前最大 `rel_id` 后分配，重新导入成功。该故障及修复过程均未触及源业务库。

| 验证项 | 结果 |
|---|---:|
| 平台表/视图资产 | 1,421 |
| 平台字段资产 | 24,697 |
| 平台 Schema 节点 | 6 |
| 候选视图依赖 | 283 |
| 受控凭据状态 | configured（用户名仅脱敏展示，密码不入平台表/代码/文档） |
| 保存连接测试 | connected，约 17 ms |
| API/平台库健康 | ok / connected |
| 源业务库写入 | 0 |

生产写入前备份：`/opt/data-asset/backups/data_asset_pre_jhemr_vastbase_20260714191708.dump`，SHA-256：`4b70d5526134f29064000d44d4390587b159a5d59f11c0c7b14e9cec34aa41be`。

## 6. 产物与复现入口

- 原始只读元数据快照：`77_JHEMR海量数据库元数据快照.json`
- 结构化结果：`77_JHEMR海量数据库只读探查与资产导入结果.json`
- 机器可读资产包：`数据资产_JHEMR_Vastbase资产包/`
- 可复用导入脚本：`backend/scripts/import_jhemr_vastbase_assets.py`

资产包包含 `tables.csv`、`columns.csv`、`relationships.csv` 和 `catalog.json`。由于源端兼容版本较旧，后续探查 SQL 不应使用 PostgreSQL 新版 `FILTER` 聚合语法。
