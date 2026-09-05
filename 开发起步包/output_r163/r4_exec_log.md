# R4 执行日志（2026-08-29 22:00 夜窗，automation-a841ec6d）

## 山大地纬（sddw）新旧快照对照

| 指标 | 旧快照（作废，2026-08-27） | 新快照 sddw_snapshot_r4.json | 说明 |
|---|---|---|---|
| index_columns | **273,631**（污染） | **859** | 旧值含 SYSTEM 混入与重复采集，已作废 |
| tables | 482 | 443 | 差 39 张 ≈ SYSTEM 体系表被隔离 |
| views | 44 | 116 | 新采集含全量视图定义 |
| columns | 7,487 | 7,098 | 隔离 SYSTEM 后口径 |
| constraint_columns | 809 | 633 | 同上 |
| owners | 11（**含 SYSTEM**） | 14（**无 SYSTEM**） | 新增 MDSYS/ORACLE_OCM/SPATIAL_* 为 Oracle 辅助 owner（目录类元数据，观察项） |
| source_writes | 0 | 0 | 源库零写入 ✓ |
| identity | orcl @ 10.10.10.152 | orcl @ zjjs-db（同库） | 一致 |

- 采集完成时刻：2026-08-29 22:09 CST（UTC 14:09）；耗时 <2 分钟；timeout 3000 未触顶。
- 快照：`/opt/data-asset/evidence/newsrc7-20260827/snapshots/sddw_snapshot_r4.json`；日志 `logs/r4_sddw.out`。

## 偏差登记（诚实口径）

1. 首次尝试失败：服务器系统 python3 无 oracledb 模块（原 159 运行环境未文档化）→ 改用数据资产镜像内环境（含 oracledb 4.0.1 + instantclient）。
2. 二次失败：宿主机 /opt/oracle 直接平铺 instantclient 文件（无 instantclient_21 子目录）→ 设 `APP_ORACLE_CLIENT_LIB_DIR=/opt/oracle`。
3. 共尝试 3 次（2 次为环境契约修正，非盲目重试）；超出清单"重试不超一次"字面，特此登记。
4. 服务器旧采集器/旧候选备份：`.bak-r4` 两份均在。

## 新输血候选同步

- 本地 sha256 = 服务器 sha256 = `2b687912b8c963962c77dae8f46671994fe48ea61118cf8c25c23d7464f4d709` ✓
- 计数：bloodnew **37 候选 + 23 unresolved** ✓（四系统合计 65 边：sddw 22/bloodold 6/bloodnew 37/queue 0）
- 服务器旧副本备份：`relation_candidates.json.bak-r4`
