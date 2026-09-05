# R165 E3 首轮夜间探查执行记录（只记录不判断）

- 日期：2026-08-30
- 命令：`.\.venv\Scripts\python.exe scripts\run_probe.py --window last-full-month --today-cut --write-db postgresql+psycopg://postgres@127.0.0.1:15432/data_asset_test --out ..\开发起步包\output_r165\runs\`
- 前置自检 4/4 PASS；执行期两轮均失败（asset.asset_probe_runs 表不存在，详见 exceptions.json）

## Run 1（首轮）

| 字段 | 值 |
|---|---|
| run_id | probe-20260830-082738 |
| status | failed（exit 1，事务回滚零落库） |
| probe_count | 无产出（执行器未输出） |
| finding_new | 无产出（执行器未输出） |
| finding_updated | 无产出（执行器未输出） |
| relapse_count | 无产出（执行器未输出） |
| error_summary | psycopg.errors.UndefinedTable: 关系 "asset.asset_probe_runs" 不存在（register_run INSERT 失败） |

## Run 2（同窗收敛验证轮）

| 字段 | 值 |
|---|---|
| run_id | probe-20260830-082838 |
| status | failed（exit 1，事务回滚零落库） |
| probe_count | 无产出（执行器未输出） |
| finding_new | 无产出（执行器未输出） |
| finding_updated | 无产出（执行器未输出） |
| relapse_count | 无产出（执行器未输出） |
| error_summary | psycopg.errors.UndefinedTable: 关系 "asset.asset_probe_runs" 不存在（register_run INSERT 失败） |

## 收敛结论

- finding_new 应=0 的收敛验证未能达成：两轮均未产出任何计数。

---

# 2026-08-30 日间补录（v1.2 豁免，用户授权；run_probe.py 两处缺陷修复后重做）

> 09:03 轮（probe-20260830-092312 之前的同一缺陷轮）run_id 见 `e3_day_run1_console.log` 早期内容，与 08:27/08:28 同因（写侧未指 --write-db）失败，事务回滚零落库。
> 09:23 试跑 probe-20260830-092312：修复 import-order 后成功落库，但 T2 因执行器缺 name_mismatch_rate 分支恒 0.0（无效值），定性试跑；两表清空后重做（审计行保留）。

## Run 试跑（2026-08-30 09:23，仅存证）

| 字段 | 值 |
|---|---|
| run_id | probe-20260830-092312 |
| status | partial |
| probe_count | 12 |
| finding_new | 5（已随两表清空移除，JSON 留存 runs/） |
| finding_updated | 0 |
| relapse_count | 0 |
| error_summary | T7:BLOCKED: ODS.PACSREPORT 70 列无申请键/患者键（2026-08-29 核验）；结果侧键位未定位，按 BLOCKED 登记（164 §5 口径），定位后补 side-b |

## Run 1（正式首轮）

| 字段 | 值 |
|---|---|
| run_id | probe-20260830-094723 |
| status | partial |
| probe_count | 12 |
| finding_new | 6 |
| finding_updated | 0 |
| relapse_count | 0 |
| error_summary | T7:BLOCKED（同上，计划内） |

## Run 2（同窗收敛轮）

| 字段 | 值 |
|---|---|
| run_id | probe-20260830-094820 |
| status | partial |
| probe_count | 12 |
| finding_new | 0 |
| finding_updated | 6 |
| relapse_count | 0 |
| error_summary | T7:BLOCKED（同上，计划内） |

## 收敛结论（2026-08-30 更新）

- **finding_new=0 达成**：同窗重跑 6 条 findings 全部走同窗幂等更新（finding_updated=6），last_seen_run 全部推进至收敛轮。
- partial 唯一来源为 T7 计划内 BLOCKED（164 §5 口径），非执行故障。
- 窗口：2026-07-01 → 2026-08-30（last-full-month + today-cut）；每 run 一条 GovernAuditLog。

## 2026-08-30 11:19 收尾双轮（全量回归夹具清表后恢复库内证据，详见 exceptions.json WARN-5）

## Run 恢复首轮

| 字段 | 值 |
|---|---|
| run_id | probe-20260830-111903 |
| status | partial（T7 计划内 BLOCKED） |
| probe_count | 12 |
| finding_new | 6 |
| finding_updated | 0 |
| relapse_count | 0 |

## Run 恢复收敛轮

| 字段 | 值 |
|---|---|
| run_id | probe-20260830-111935 |
| status | partial（T7 同上） |
| probe_count | 12 |
| finding_new | 0 |
| finding_updated | 6 |
| relapse_count | 0 |

- 最终库态：probe_runs=2、probe_findings=6、probe 审计行=2；全量回归 1288 passed / 1 skipped / 0 failed（27 分 22 秒）。
