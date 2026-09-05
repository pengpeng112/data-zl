# R165 晨检记录（机械采集，不分析不修复）

> 采集时刻：2026-08-30 07:03 CST
> 采集方式：全程只读；15432 隧道本次会话内按 BatchMode 公钥重建（`SSH_OK` + `127.0.0.1:15432 LISTENING`）；连接串仅进会话环境变量，零落盘；零 Git 写；未向用户提问。
> 口径：原文摘录，缺什么记"缺失"，不猜测不补跑。

## 一、R4（来源：output_r163）

来源文件：`开发起步包/output_r163/r4_exec_log.md`、`开发起步包/output_r163/progress.md`（末 3 行）。

### progress.md 末 3 行（原样摘录）

| 2026-08-29 14:20 | 165-E4/E5 | DONE | app/api/v1/probe.py + main 注册 + test_probe_api.py(7) + service 复发测试(11) | 四端点+405 占位先于 /{id}；E5 专项全绿 |
| 2026-08-29 15:10 | 165 白天批次 | DONE | 全量 1274 passed/0 failed；链路重放+导出 --check PASS | E1-E5 全闭环，待夜窗 E3 |
| 2026-08-29 22:09 | R4 | DONE | r4_exec_log.md + 159 补记录 + sddw_snapshot_r4.json | 重采 index 859（旧 273,631 作废）/SYSTEM 隔离/443 表；候选 sha256 两侧一致（bloodnew 37+23）；3 次尝试含 2 次环境契约修正已登记 |

### 三项核对（摘自 r4_exec_log.md 原文）

- **新 sddw 快照 owners 是否含 SYSTEM**：不含。原文表格行：`owners | 11（**含 SYSTEM**） | 14（**无 SYSTEM**）`（新增 MDSYS/ORACLE_OCM/SPATIAL_* 为 Oracle 辅助 owner，观察项）。
- **index_columns 数**：**859**（旧快照 273,631 已作废，污染原因为 SYSTEM 混入与重复采集）。
- **两侧 sha256 是否一致**：一致 ✓。原文：`本地 sha256 = 服务器 sha256 = 2b687912b8c963962c77dae8f46671994fe48ea61118cf8c25c23d7464f4d709 ✓`。

## 二、E3（output_r165/runs + 测试库）

### runs/ 目录 JSON 清单

`开发起步包/output_r165/runs/` 目录存在但为空，无任何 JSON 文件：**缺失**（无 status/probe_count/finding_new 可摘录）。

### 测试库查询（data_asset_test，经隧道 15432，只读）

- `SELECT probe_type, count(*) FROM asset.asset_probe_findings GROUP BY 1` → **(0 rows)**
- `SELECT run_id,status FROM asset.asset_probe_runs ORDER BY id DESC LIMIT 4` → **(0 rows)**

（两条 SQL 均执行成功，两表存在但为空；按要求不补跑。）

## 三、W10 首验（生产库 data_asset，127.0.0.1:15432，只读）

`SELECT id,run_id,status,candidates_total,success_count,failed_count FROM asset.asset_identity_scheduler_runs ORDER BY id DESC LIMIT 1` →

| id | run_id | status | candidates_total | success_count | failed_count |
|---|---|---|---|---|---|
| 33 | RUN-d46f6ffc1db4 | failed | 112 | 0 | 0 |
