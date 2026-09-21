# 水位死锁 · 双会话诊断合并核查包（deadlock_crosscheck.md）

> 2026-09-06 晨。用途：交多 AI 交叉核查「180 批 F-2 发布后夜跑持续熔断」的根因与处置方案。
> 输入两份独立诊断：A=本会话（nightly_d.md §五B/§六）；B=另一会话（方案 A/B 分析）。
> 本文所有「已裁决」项均附可在生产容器只读复现的命令；裁决数据采集自 2026-09-06 晨。

## 1. 两会话一致结论（无需再辩）

1. **根因=水位死锁**：失败 run 不推水位（`advance_watermark` 仅 success 提交）→ 增量窗（水位−24h lookback）内 110 名真实变更者每晚重选、全带 modified_time → 全进 update 桶 → ratio>0.3 熔断 → 再失败。自愈不可能。
2. **F-2 未失效但豁免在增量模式下是死代码**：`resync_unchanged` 只豁免「无 modified_time 标记者」，而增量模式下候选人必带标记——设计缺口（双方独立得出同一结论）。
3. **首选处置=一次性受控放行**（08-30 W10 先例 RUN-69d068f3793e 同款）：进程级 docker exec 覆盖 `APP_IDENTITY_CB_MAX_CHANGE_RATIO`，让一次 run 成功 → 水位越过 08-27 批量 MODIFIEDTIME → 窗口滑走 → 次夜恢复例行 success。
4. 均不推荐：等窗口自然滑出（不会自愈）、持久调高 ratio 阈值（熔断永久洞开）。

## 2. 事实对账表（B 会话主张 vs 实测裁决）

| # | B 会话主张 | A 会话主张 | **裁决（实测）** | 证据/命令 |
|---|---|---|---|---|
| 1 | 水位停在 **08-30** | last_create_date=**08-28 02:57:45** | **A 正确**：`last_create_date=2026-08-28 02:57:45+08:00`；08-30 是 `last_run_at`（W10 手动跑的 align 路径未推 main 水位）。B 混淆两列 | 容器内 `get_watermark(db,'HIS','main_account_sync')`（本文 §4 快照） |
| 2 | ratio≈1.15、**scope=99 < 候选 110，分子可大于分母** | 未量化分母 | **B 正确且已精确实测**：scope=**99**、update=**110**、ratio=**1.111**。scope 查询只数 `source_create_date>=MANAGED_SINCE(07-20) 且 active 且 eligible` 的 persons；增量窗成员绕过 MANAGED_SINCE 过滤进候选但不进分母——**ratio>1 的数学 bug 属实**，应随方案 B 修 | §4 复现脚本输出 |
| 3 | 110 人=「08-27 职称批量改动余量」 | 129 人 MODIFIEDTIME 聚簇于 **08-27 18:49:38/18:57:45**（同秒=HIS 批量 UPDATE），成因未定 | **聚簇时间双方一致**；「职称」归因**未证实**（160 职称包按 55 记录尚未执行）——成因标签不影响机制与处置，留开放项 | HIS 只读 COUNT：`MODIFIEDTIME>=08-30` 仅 3 人（近期无批量）；平台 `IdentityPersonSource.raw_data` 聚簇值 |
| 4 | 存在性检查正常（set(110)）、skip_configured 守卫在产（grep=2） | 检查正常（探针返回 set 非 None） | **一致**，双方独立验证通过；r181 含 003531 治本守卫 | 双方探针记录 |
| 5 | 成功 run 将补：**约 4 个 deactivate（JHEMR 锁定）**+三子任务积压 | 同（candidates_deactivate=4 自 09-01 每晚重现） | **一致且已定位机制**：4=增量窗内 inactive 待锁账号（`select_deactivate_candidates`，增量口径）；随窗口滑走一并清零 | run 行 deactivate 列；orchestrator:611 |
| 6 | 只需放宽 change_ratio 一道 | 同（update=110<150、new=0<50） | **已实证充分**：五维阈值真值——candidates 114<200 ✓、new 0<50 ✓、update 110<150 ✓、align 0<150 ✓、deactivate **4**<20 ✓、ratio 1.111>0.3 ✗（唯一失败维度） | §4 `check_thresholds` 真管线口径复现 |
| 7 | （B 的 P3-2/P3-3）阈值路径 stats 构成被 finalize 覆盖、熔断行不落桶计数 | bare except 无日志、排障靠只读重放 | **双方互补，且 A 干跑时亲身踩中**：直接调 `_compute_change_stats` 得 deactivate=90（托管圈口径），真管线在 `orchestrator.py:632` 用 `stats["deactivate"]=len(deactivate_candidates)` 覆盖为 4——内部构成与生效值不一致即 P3-2 所指 | 本地代码 630-633 行；§4 对照 |

## 3. 已裁决的关键新数据（2026-09-06 晨实测快照）

```text
WM_RAW: last_create_date=2026-08-28 02:57:45+08:00 | employee_key_set=True
CANDIDATES=110 | new=0 update=110 align=0 resync_unchanged=0 deactivate(内部口径)=90 | scope=99
ratio=update/scope=1.111
真管线（stats["deactivate"]被覆盖为增量口径4）后五维判定：唯一失败维度=max_change_ratio(1.111>0.3)
HIS 活库：MODIFIEDTIME>=08-30/09-01/09-04/09-05/09-06 → 3/2/2/1/0 人（近期无批量变更）
平台快照：FXHIS.SYS_EMPLOYEE person_sources 2527 行中 129 行 MODIFIEDTIME>窗口(08-27 02:57)，样例全为 2026-08-27T18:49:38/18:57:45
```

## 4. 核查 AI 只读复现命令（生产容器，零写入）

```bash
ssh -o BatchMode=yes -i C:/Users/Administrator/.ssh/id_ed25519_ai root@10.10.8.83 \
  "docker exec -e APP_IDENTITY_SYNC_DIRECT_CONNECTION=true -i data-asset-api python -" <<'PY'
from app.core.db import SessionLocal
from app.services.identity_watermark import get_watermark
from app.services.identity_sync_orchestrator import (
    select_nightly_candidates, select_deactivate_candidates,
    _compute_change_stats, check_thresholds)
db = SessionLocal()
print(get_watermark(db, source_code="HIS", watermark_key="main_account_sync").create_date)
c = select_nightly_candidates(db); d = select_deactivate_candidates(db)
s = _compute_change_stats(db, c, jhemr_existing=set())
s["deactivate"] = len(d)                      # ← 真管线同款覆盖（orchestrator:632）
print(len(c), s, check_thresholds(c + d, s))
db.close()
PY
```
注意：不追加 `stats["deactivate"]=len(d)` 覆盖而直接 check_thresholds 会得到 max_deactivate=90 的**假判定**（内部托管圈口径），勿据此推翻方案 A。

## 5. 合并方案 A · 一次性受控放行执行卡（待用户一句话授权）

- **命令**：与 `/etc/cron.d/data-asset-identity-nightly` 逐项同款的 docker exec（PROVIDER/NIGHTLY_ENABLED/PYTHONPATH/SYNC_ENABLED/JHEMR_PASSWORD_WRITE/CDMS_FID/PHASE_D/DIRECT_CONNECTION 全套），仅追加 `-e APP_IDENTITY_CB_MAX_CHANGE_RATIO=2.0`（进程级，不改 env 文件/不重启/不切镜像；1.111<2.0 且留余量）。B 会话给出的完整命令可用。
- **白天执行**（W10/172 先例），今晚 02:00 cron 即天然恢复验证。
- **前置**（只读/低风险）：生产库 pg_dump（惯例备份）；确认 r181 在产（skip_configured 守卫 grep=2）。
- **预期效果**：110 update 对齐成功 + 4 deactivate（设计内锁定）+ 签名/职称/科室子任务积压补齐 + login_sign（带守卫）；水位推进至 ≥08-27 18:57（或刷新后更新值）。
- **后置核验**（只读）：run status=success；watermark.last_create_date 推进；子任务有真实计数；审计动作守恒（actions/batches 对账）；「已有签名方式又新增 sign_way=0」复核（B 会话脱敏查询）；**09-07 02:00 cron** 预期 success 且候选个位数、resync_unchanged 首次出现。
- **回滚**：逐批事务+补偿表（identity_sync_compensations）+审计 before/after；env/镜像/cron 零持久改动，无需回滚生产配置。

## 6. 合并方案 B · 治本清单（立项改代码+测试+随下次镜像发布，排主 AI）

1. **ratio 分子改真实写计划口径**：增量窗内幂等重入者（plan 无实际 diff）不计分子——消除 F-2 豁免死代码（两会话同议）。
2. **ratio 分母口径修正**：scope=99<分子 110 的数学 bug（分子可>分母）；分母应与候选同口径。
3. **P3-2/P3-3 可观测性**：阈值路径保留 stats 构成快照（勿被 finalize_run 覆盖）；熔断 run 行落 new/update/align/resync 桶计数；`_fetch_jhemr_existing_emp_nos` 与 `_compute_change_stats` 内部 deactivate 口径对齐或拆名。
4. （A 会话补充）`_fetch_jhemr_existing_emp_nos` bare except 至少落一条 WARN（当前失败零痕迹）。
5. （关联）G2 追认：login_sign 接线在 orchestrator 层已随 r178/r181 上线（A 会话 W-02 更正），r181 带治本守卫，建议用户书面追认。

## 7. 开放项（不阻塞方案 A）

- 08-27 18:49 HIS 批量 UPDATE 的具体业务成因（「职称」仅为猜测；160 包未执行）。
- F-3（主熔断时子任务降级，177 G17）在本次事件中再次显现价值，可随方案 B 一并评估。

## 8. 核查边界（给交叉核查 AI）

只读：SELECT/容器 grep/本地代码对照；禁止触发同步、改 env/cron/镜像/代码、git 写、凭据落盘；HIS/JHEMR 仅限平台连接器限量只读。结论分歧时以 §3 实测快照与 §4 复现命令为准。

---
*裁决与快照采集：A 会话（180 批执行 AI）2026-09-06 晨，全部只读；本文不改 55/README（留后续批次）。*
