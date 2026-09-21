# flush 执行证据（evidence.md，方案_r3 R0-R6，2026-09-06）

## R0
- 容器：`data-asset-api data-asset:r181-20260905 Up 22 hours (healthy)` ✓（与 02:25 D1 时同一容器，未重建）

## R1 全量探针（08:4x，容器内只读）
```
R1|watermark=2026-08-28 02:57:45+08:00|window_start=2026-08-27 02:57:45+08:00
R1|cands=110|deact=4|new=0|update=110|align=0|resync=0|scope=99
R1|true_ratio=1.152|gap_hours=166.44|source_row_delta_pct=0
R1|candmax=2026-09-05T08:47:41|candmin=2026-08-27T18:49:38
R1|deact_masked=['00**58','00**46','00**60','00**50']
R1b|cb_open=[('nightly_cdms',False),('nightly_jhemr',False)]
R1b|guard=2（skip_configured@jhemr_identity_adapter.py）
R1b|runner_login_sign=0（md5 87ff0c8f…=r175 旧版）
R1b|thresholds=150 50 48
```
**STOP 线逐项**：update 110≤140 ✓；new/deact 无激增 ✓；候选 max 硬闸（max−24h=09-04 08:47 ≫ 08-27 18:57:45，且 ≥08-30 底线）✓；CB 双 False ✓；守卫=2 ✓；runner=0 ✓；max_update=150 ✓；source_row_delta_pct=0 ✓ → **GO**；GAP=max(240, ceil(166.44)+24)=**240**。

## R2 备份
`/opt/data-asset/data_asset_pre_flush_20260906.dump` = **139M** ✓（口令仅入变量未回显）

## R3 一次性放行（08:44:06，唯一写操作）
命令=方案_r3 §4.R3 单行（cron 同款 8×-e + `APP_IDENTITY_CB_MAX_CHANGE_RATIO=2.0` + `APP_IDENTITY_CB_MAX_WATERMARK_GAP_HOURS=240`，均进程级）。stdout：
```json
{"status":"success","run_id":"RUN-2df6cd6db381","counts":{"main_planned":110,"main_success":111,"main_failed":0,"main_skipped":3,"signature_planned":1886,"signature_inserted":4,"signature_failed":0,"signature_skipped":1882,"title_planned":1,"title_updated":1,"title_failed":0,"title_skipped":2110,...},"error_classes":{},"failed_fingerprints":[]}
```
（111+3=114=110 update+4 deactivate，口径自洽）

## R4 六项验收（只读）
| # | 项 | 实测 | 判定 |
|---|---|---|---|
| 1 | run 行 | `RUN-2df6cd6db381\|success\|CB=False\|-\|110\|4\|111\|0\|3995\|09-06 08:44:06` | ✓ |
| 2 | **水位硬闸** | watermark=**2026-09-05 16:47:41+08**、window_start=09-04 16:47 ≫ 08-27 18:57:45 | ✓ **死锁解除** |
| 3 | 子任务 | main 110/111/3；signature 1886/**4**/0；user_dept 12/**12**/0；education_title 1/**1**/0——四行全 success；**无 login_sign 行**（=0，符合预期） | ✓ |
| 4 | 003531 守卫 | sign_way actions 当日=**0**；login_sign 子任务行=**0** | ✓ |
| 5 | 守恒 | failed=0；actions **2123** ≥ success 111；batches **114**；compensations **0** | ✓ |
| 6 | 配置 | env：ratio 覆盖 0 处、gap 覆盖 0 处、MAX_NEW=50、MAX_UPDATE=150；容器 Up 22h 未重启；cron md5 1e7d7a3639d6 未动 | ✓ 零持久改动 |

注：水位终值 16:47（预检 candmax 为 08:47）——R3 先跑 `sync_his_identity` 刷新采集，把该人当日更新值（16:47）带入候选集 max，更有利（窗口更靠前）。

## R5 次夜观察（09-07 02:00 cron 后）
**未排程**：本会话系 D1 定时任务派生，平台拒绝嵌套创建新定时任务（见 exceptions W-03）。需新会话人工/主 AI 在 09-07 02:25 后只读复查（口径已写入 nightly_r5 待办模板=方案_r3 §4.R5 二分支判定）。

## 结论
当日 DoD（R1 留痕+R2 备份+R3 success+R4 六项）**全部达成**；零持久配置改动；业务源零直连；零 git 写。
