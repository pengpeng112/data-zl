# N1 · 176 夜跑只读核验（2026-09-04，178 R1）

> 只读核验；未触发同步、未改 env/cron/镜像、未热进 F-2。结论按 178 §3 R1：FAIL 呈报，等用户，不自行调阈值。

## 环境

- 通道：`ssh root@10.10.8.83`（公钥 BatchMode）→ `docker exec data-asset-api python`（SELECT only，凭据经容器 env `APP_DB_URL`，零落盘）
- 容器 `data-asset-api`：**Up 28 hours (healthy)**（2026-09-04 23:31 CST 查）
- 熔断 env 实证：`APP_IDENTITY_CB_MAX_UPDATE=150`（F-1 在产）；`APP_IDENTITY_CB_MAX_NEW=130`（临时值，未动，只记录）

## 最新 nightly run（asset_identity_scheduler_runs，按 started_at 倒序前 5）

| started_at | run_id | status | total | new | update | deact | CB | 维度 |
|---|---|---|---|---|---|---|---|---|
| 2026-09-04 02:00 | **RUN-b3324c242e78** | **failed** | 110 | 0 | 0 | 3 | **True** | **max_change_ratio** |
| 2026-09-03 02:00 | RUN-2309f671219e | failed | 110 | 0 | 0 | 3 | True | max_update |
| 2026-09-02 18:26 | RUN-f2513dc373c1 | success | 0 | 0 | 0 | 0 | False | - |
| 2026-09-02 02:00 | RUN-4ecb56230848 | failed | 110 | 0 | 0 | 3 | True | max_update |
| 2026-09-01 02:00 | RUN-ea37dd9ce962 | failed | 110 | 0 | 0 | 3 | True | max_update |

- 注：熔断在计数落库前中止，new/update 列保持 0、change_ratio/duration 为空，不代表真实拆分为 0；真实拆分见下方归因。
- 时间戳为 2026-09-04 02:00（本夜 cron 已跑，非旧失败行）。

## RUN-b3324c242e78 明细

- 触发：`host_cron_modified_sync`；report_summary `overall_status=failed`，`main_account_sync.reason=threshold_exceeded`，`dimension=max_change_ratio`。
- 子任务（asset_identity_sync_subtasks）：`main_account_sync`(CDMS,JHEMR) failed；`jhemr_signature_sync` / `jhemr_user_dept_sync` / `jhemr_education_title_sync` 全部 **skipped，reason=main_account_sync_not_successful**（与 09-03 同样被一刀切）。
- 抽样空签名账号回补：**未发生**（签名子任务 skipped；最近一次成功补签仍为 09-01 手动 RUN-69d068f3793e，未复查工号明细）。

## 归因（代码对照，本地工作区只读）

- 生产语义仍为 F-2 之前：110 名托管圈人员例行 resync 全部计入 `update`。
- `check_thresholds` 检查顺序（identity_sync_orchestrator.py:500-511）：max_candidates(200) → max_new(130 在产) → **max_update(150 在产)** → max_align(150) → max_change_ratio(默认 0.3)。
- 本夜：update=110 **< 150 → max_update 已放行（F-1 对其目标维度生效）**；但 update/total = 110/110 = 1.0 **> 0.3 → max_change_ratio 熔断**。与 09-03（max_update 先触发即中止）维度不同属预期位移，不是新故障。
- 根治仍是 **F-2**（resync_unchanged 不计 max_update/ratio，已在工作区+9 测试，未上生产）：发布后 110 人纯 resync 应 success。生产发布 + MAX_NEW 130 回落 = 等待域 **G3**。

## N1 判定

**FAIL（仍熔断）**：run_id=RUN-b3324c242e78，维度=max_change_ratio，candidates_total=110（托管圈例行 resync），三个子任务被主任务失败一刀切 skip。按 178 铁律不调阈值、不热进 F-2，呈报用户走 G3。
