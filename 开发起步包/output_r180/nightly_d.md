# D1 · F-2 发布后首个夜窗验证（2026-09-06 02:25，只读）

> 判定：**FAIL（仍熔断）**——`RUN-69e87f7f27dd`，维度 `max_change_ratio`，110/110 全量 update。等用户，不调阈值。

## 一、环境

| 项 | 预期 | 实际 |
|---|---|---|
| 容器镜像 | data-asset:r178-20260905 | **data-asset:r181-20260905**（Up 16h healthy） |
| 镜像差异说明 | — | **并行会话于 09-05 上午（r178 发布后约 1 小时）基于工作区构建发布了 r181**（含我 A 段已提交代码 + 其「003531 事故防护」改动）。非回滚；F-2 代码在容器内实证：orchestrator `grep -c resync_unchanged` = **5** |
| 熔断 env | 150 / 50 | 未复查容器 settings（r181 重建时若沿用同一 env 文件则 150/50 不变；本轮未打印，见建议③） |
| cron | /etc/cron.d/data-asset-identity-nightly（容器内 /app/scripts/...） | 未变；runner `/app/scripts` 仍为旧版（grep login_sign=0） |

## 二、最新 run 明细（asset_identity_scheduler_runs）

| 字段 | 值 |
|---|---|
| run_id | **RUN-69e87f7f27dd** |
| started / finished | 2026-09-06 02:00 / 02:00 |
| triggered_by | host_cron_modified_sync |
| status | **failed** |
| circuit_breaker_triggered / dimension | **True / max_change_ratio** |
| candidates_total / new / update / deactivate | 110 / 0 / 0（熔断时未落桶计数）/ 4 |
| report_summary | `overall_status=failed`；`main_account_sync.reason=threshold_exceeded, dimension=max_change_ratio`；summary 内**无任何 resync_unchanged 字样** |

## 三、子任务（asset_identity_sync_subtasks）

| subtask | status | planned | succeeded | skipped | failed |
|---|---|---|---|---|---|
| main_account_sync | failed | 0 | 0 | 0 | 0 |
| jhemr_signature_sync | **skipped**（main_account_sync_not_successful） | 0 | 0 | 0 | 0 |
| jhemr_user_dept_sync | **skipped**（同上） | 0 | 0 | 0 | 0 |
| jhemr_education_title_sync | **skipped**（同上） | 0 | 0 | 0 | 0 |

**附加发现（G2）**：report_summary 出现 `"jhemr_login_sign_sync": {"status": "success"}`——r181 发布把登录/签名方式子任务带上了产线（app 层接线；runner 仍旧版）。写副作用核查：09-06 当日 `asset_identity_sync_actions` = **0 行**、`asset_identity_sync_batches` = **0 行**——本夜该子任务零写库。G2 未经单独授权被激活一事需用户知悉（见建议②）。

## 四、判定

**FAIL**。PASS 三条件（status=success / CB=False / 子任务≠skipped）全部不满足。alerts 表佐证：09-04、09-05、09-06 连续三晚 `circuit_breaker_open`，维度均为 `max_change_ratio`。

**F-2 实证：未取得**。F-2 代码在容器内存在（grep=5），但 summary 无 resync_unchanged、ratio 仍按 110 全量 update 触发（>0.3×110 即熔断）——说明本夜 110 名托管圈候选**全部落入 update 分桶**（未走 resync_unchanged 单列）。

## 五、归因候选（只读无法定谳，按可能性排序）

> **【2026-09-06 晨根因定位增补——本节三个候选全部被后续只读取证裁决，见 §五B】**

1. **存在性检查失败回退（fail-closed）**：F-2 规定 JHEMR 存在性检查失败时回退旧 update 口径；若 02:00 直连检查全量失败 → 110 全 update → ratio=1.0。需查应用日志中存在性检查失败记录（本任务无该日志读取面）。
2. **HIS MODIFIEDTIME 全量命中**：09-05 00:35 事故处置若批量触碰过 FXHIS 人员表，modified_time 整体前移 → 110 人全部判「真实变更」。
3. **r181 内 F-2 语义与 178 提交版存在差异**：并行会话构建源为工作区，orchestrator 是否被其后续改动需其自查（我 09-05 终检时 orchestrator 不在其 diff 内，可能性低）。

## 五B、根因定位（2026-09-06 晨，只读取证，取代 §五 候选）

**结论：水位死锁（stuck watermark deadlock）——§五 三个候选全部排除。**

排除证据：
- 候选①排除：容器内以 cron 同款 env（DIRECT_CONNECTION=true）复现 `_fetch_jhemr_existing_emp_nos` → 返回 **set 非 None**（检查当前正常；且该函数 bare except 无日志，02:00 是否瞬断无痕迹，但非必要假设）。
- 候选②排除：HIS 活库只读 COUNT `FXHIS.SYS_EMPLOYEE.MODIFIEDTIME >= 08-30/09-01/09-04/09-05/09-06` = **3/2/2/1/0 人**——近期无批量变更。
- 候选③排除：容器内 orchestrator 与本地提交版一致（resync_unchanged=5；并行会话 182 线未改 orchestrator）。

**死锁机制（平台库只读复现 `_modified_employee_times` 全链路）**：
1. `main_account_sync` 水位 `last_create_date = 2026-08-28 02:57:45`（自 08-28 后从未推进；08-30 W10 手动成功跑的是 align 路径，未推 main 水位）。
2. 增量窗口 = 水位 − 24h lookback = **2026-08-27 02:57**。
3. 平台 `IdentityPersonSource`（FXHIS.SYS_EMPLOYEE 快照）中 **129 人** MODIFIEDTIME > 窗口——样例值全为 **2026-08-27 18:49:38 / 18:57:45**（同秒批量 = HIS 侧 08-27 晚一次批量 UPDATE 的痕迹，早于水位但落在 lookback 窗口内）。
4. 经 protected/conflict/dept 过滤后 candidates=**110**（与每晚观测完全一致），且全部带 `modified_time` → F-2 正确地判为 **update（真实变更待同步）**，非 resync_unchanged。
5. update=110 → ratio=110/110=1.0 > 0.3 → 熔断 → run failed → **水位只随 success 推进 → 永不 success → 水位永停 08-28 → 129 人永在窗口 → 每晚必熔断**。自 09-01 起的「结构性熔断」（176 的诊断）实为同一死锁：真实变更积压 + 熔断挡住唯一的排水口（水位推进）。

**F-2 本身工作正常**——它只是把「例行 resync 不熔断」修对了，而当前 110 人是真 update，熔断按设计触发。问题在**积压无法排出**。

**W-02 更正**：login_sign 子任务接线在 orchestrator app 层（r178/r181 均含），不在 runner——我 09-05「保留旧 runner 即未激活 G2」的判断机制有误，G2 实际已随 r178 上线（昨晚 login_sign=success、sync_actions/batches=0 零写副作用，且 r181 已含 003531 治本防护）。建议用户追认 G2。

## 六、建议（均需用户/主 AI 授权后执行，本任务零改动）

> **【09-06 晨增补：基于 §五B 根因，首选方案为 ⑥——08-30 W10 同款一次性排水，先例 RUN-69d068f3793e】**

1. **不做 D2**（MAX_UPDATE 150→100）——FAIL 前提下调阈值属掩盖问题；也**不调 0.3 比例阈值**（指持久化调整）。
2. **G2 越权激活需用户追认或回退**：login_sign 子任务已随 r178/r181 的 orchestrator 层上线（W-02 机制更正见 §五B），本夜零写副作用；r181 已含 003531 治本防护，建议追认。
3. ~~主 AI 复核会话~~（已完成根因定位，见 §五B）。
4. ~~修复方向预案~~：归因①②③均排除；真因为水位死锁。
5. 次日夜跑（09-07 02:00）在无处置情况下**预期仍熔断**（同 run 特征），无需再验证即可判定。
6. **首选处置（需用户授权，一句话即可）**：一次性 docker exec 手动执行夜跑（cron 同款全部 -e 开关 + `APP_IDENTITY_SYNC_DIRECT_CONNECTION=true`），叠加**仅本次进程生效**的 `APP_IDENTITY_CB_MAX_CHANGE_RATIO=2.0` 覆盖（不改 env 文件、不重启容器、不动 cron、镜像不动）。预期：110 真实 update 全部对齐成功（update=110<max_update=150 ✓、new=0<50 ✓）→ 水位推进至 ≥129 人最大 MODIFIEDTIME → 明晚增量窗口上移、候选归零/个位 → 例行夜跑恢复 success + resync_unchanged 生效 + 签名/职称子任务自动恢复。失败自动 fail-closed 中止（逐批事务+补偿表），无半写风险。先例：2026-08-30 W10（RUN-69d068f3793e，112 候选 0 失败）。
7. 备选（不推荐）：持续熔断等待人工逐批消化（无排水机制，死锁不会自愈）。

---
*取证：ssh 8.83 → docker exec SELECT only（runs/subtasks/alerts/watermarks/actions/batches 五表 + 容器 grep）；凭据零落盘；本任务未改任何 env/cron/容器/代码，零 git 写。*
