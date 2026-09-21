先只读收集 round-9 原文、r2 修订稿、分歧表和此前审查意见，再逐条对照落实情况。目录已确认。接下来只读读取原审查意见、r2 方案和分歧表，逐条对照落实。对照已定位。接下来核源码、cron、备份先例和原文，确认 r2 命令与硬闸是否真能落地。**结论：可以按 `方案_r2.md` 执行（仍须用户点名）。** 此前 P0-1/2/3、P1-1~7、P2 系列均已按分歧表写入 r2，没有落实性倒退，也没有新的阻断级问题。R1 硬闸若判定「放行无法滑出聚簇」应 STOP，这是 P0-2 的预期出口，不是方案写错。

本次只读：对照 `审查_grok.md`、`分歧表.md`、`方案.md` / `方案_r2.md`，并核对 `identity_sync_orchestrator.py:497-525/705-722`、`identity_watermark.py:40-43/69-72`、`config.py:5/73/98-106`、`Dockerfile.hotpatch`、`output_r180/release_evidence.md` B5、`nightly_d.md`（r181 上 `login_sign=0`）。未改文件、未连生产、未触发同步。

---

## ① 逐条落实对照

### P0（3/3 已落实，无倒退）

| 原意见 | r2 落点 | 判定 | 偏差 |
|---|---|---|---|
| **P0-1** 只覆盖 ratio，下一道 `watermark_continuity` 会接手炸 | **§1** 写明七维短路、ratio=1.152 为第一失败维、gap≈145h+ 为被隐藏的第二维；**§3.2** 必须同时追加两个 `-e`；**§4.R1** 逐维独立评估并打印 `watermark_gap_hours`；**§4.R3** 含 `APP_IDENTITY_CB_MAX_WATERMARK_GAP_HOURS`，`GAP=max(240, ceil(实测)+24)` | **已落实** | 原建议下限是 `max(96, ceil+24)`，r2 抬到 240，更保守，可接受。命令示例仍写死 240，正文要求按 R1 替换——隔日执行若忘改且 gap>240，P0-1 会复发，属操作脚注不是方案错误 |
| **P0-2** 「单次收敛」未证；硬闸看 c+d 的 max，R4 看 `window_start` 而非 ≈09-05 | **§1** 改为「不确定，须 R1 实测」；**§4.R1** 硬闸 `max(c+d.modified_time)−24h > 2026-08-27 18:57` 否则 STOP；**§4.R4.2** 改为 `window_start(新 last_create_date) > 08-27 18:57`，原地踏步即使 success 也判死锁未解除 | **已落实** | 丢掉了原「至少 ≥08-30」安全底和 UTC/`+08` 对照，硬闸时刻也写成 `18:57` 而非聚簇 `18:57:45`。当前数据形态几乎是二元（停在聚簇 → STOP，或含 09-05 → 远超门槛），**实际不会误放**；临界 45 秒窗只是理论上的缝 |
| **P0-3** 铁律写 R4、正文写 R3 | **§3.1**「唯一生产写=R3」；R2 备份单独除外；**§4.R4** 标题「只读」 | **已落实** | 无 |

源码复核与 r2 一致：`check_thresholds` 在 ratio 之后才查 `watermark_continuity`（519-521），默认 48h（`config.py:106`）；`advance_watermark` 仅 success（`identity_watermark.py:71` + orchestrator 706）；推进值取 c+d 的 `max(modified_time)`（707-721）；`window_start = last_create_date − lookback 24h`（`config.py:73`）。

### P1（7/7 已落实）

| 原意见 | r2 落点 | 判定 | 偏差 |
|---|---|---|---|
| **P1-1** grep 文件写错 | **§4.R1** `jhemr_identity_adapter.py`，必须 `=2` | **已落实** | 原建议 `≥2`，r2/`分歧表` B5 收成 `=2`。本地 adapter 恰 2 处（919/935 行），181 冒烟也是 2。略严，不构成假 STOP |
| **P1-2** G2 / login_sign 自相矛盾 | **§1** 写明审计默认值；**§2 非目标** 不 docker cp runner；**§4.R4.3** 只验三子任务、不要求 login_sign；**§7④** | **已落实** | R1 **未**探针容器 runner。前提本身成立：`Dockerfile.hotpatch` 只 COPY `app/alembic`；181 报告「镜像不含 runner」；**09-06 02:25 `nightly_d.md` 在 r181 上实测 `grep login_sign=0`**，且子任务表无 `jhemr_login_sign_sync` 行。git 祖先谱系不能推翻热补 COPY 列表。仍建议 R1 加一条 runner grep 作加固，见下文 |
| **P1-3** ratio 1.111 → 1.152 | **§1** `(0+110+4)/99=1.152`；**§8** 单测锁定 `114/99` | **已落实** | 2.0 覆盖余量足够，无问题 |
| **P1-4** PowerShell / BatchMode / 公钥 | **§4.R0/R2/R3** 均 `BatchMode=yes` + `id_ed25519_ai`；R3 已改单行 | **已落实** | R1 仍指向 crosscheck §4 的 bash heredoc，**没有**可粘贴的 PowerShell 扩展脚本。R3 已修好，R1 需执行 AI 自己改 here-string |
| **P1-5** R2 备份空命令 | **§4.R2** 写死 dump 路径、`ls>100M`、失败 STOP、口令只进变量 | **已落实** | 不是 180 计划 B2 的逐字拷贝，但更接近 180 **实跑**（容器解析用户/库、口令进变量、`/usr/local/pgsql/bin/pg_dump`，见 `release_evidence.md` B0/B2）。失败会 STOP，方向正确 |
| **P1-6** 缺授权门禁 | **§3.0** + **§4.R0.1**：点名前 R2/R3 禁止 | **已落实** | 无。本次消息仍是复审，不是放行 |
| **P1-7** DoD 绑 R5 | **§2** 目标②不绑当日；**§4.R4**「当日 DoD 到此为止」；**§4.R5** 不绑完成；**§5** | **已落实** | 无 |

### P2（11 项：10 项落实，1 项部分）

| # | 原意见 | r2 | 判定 |
|---|---|---|---|
| 1 | 超时 15–30 min，不因超时杀了再跑 | **§4.R3** 20–30 min，「超时≠失败，以库内 run 行为准」 | 已落实。注意：若把超时实现成 SIGKILL `docker exec`，会制造部分写入+禁重试 |
| 2 | 避开 01:45–02:30 | **§3.5**、**§4.R3** | 已落实 |
| 3 | 并行会话含 CDMS 补行 | **§9**「182 线+CDMS 补行」，靠人工确认 | 已落实 |
| 4 | 守恒：`failed_count=0`；actions≥success；compensations=0 或说明 | **§4.R4.5** | 已落实 |
| 5 | 4 个 deactivate 脱敏名单 | **§4.R1** | 已落实。口径写「后四位掩码」，代码 `_mask_emp_no` 实际是前 2+后 2；候选里已有 `emp_no_masked`，应用现成字段 |
| 6 | 「业务源零直连」易被读成不准跑 nightly | **§3.4** 禁止 AI 直连，仅允许 R3 经 nightly 通道写 | 已落实 |
| 7 | R1 无 `refresh_source=True` | **§4.R3** 末句点明真跑会先 `sync_his_identity`，STOP 线覆盖漂移 | 已落实 |
| 8 | 1 人失败不推水位、已写不回滚 | **§3.3**、**§6**、**§7③**（引用 orchestrator:706） | 已落实 |
| 9 | 治本升级为下次发布规格 | **§8** 改法+验收表 | 已落实 |
| 10 | 55/README 登记标成主 AI 义务 | **§4.R6**「此义务写入报告」 | 已落实 |
| 11 | 缺一次性执行提示词 | 全文即 R0–R6 执行卡，无 177/180 那种独立「§提示词」 | **部分落实**：可交付执行，但没有可整段粘贴的角色/禁令/产出格式块 |

Kimi 原「R5 候选个位 vs resync 互斥」也已写入 **§4.R5** 二分支，与 `orchestrator.py:245-252/436-439` 一致。

---

## ② 落实偏差与 r2 新引入（均非阻断）

1. **R4.3 加严「且有真实计数」**（新引入，P1 措辞）  
   原修正只要求三子任务 `≠skipped`。积压补齐后完全可能 `status=success` 且插入=0（`skipped_equal`）。若执行 AI 把「真实计数」读成 `succeeded>0`，会误判当日 DoD 失败。应按「有子任务行且非 skipped / 非审计默认值」理解。

2. **R4.1 仍写 `candidates_total≈110、deactivate≈4`**  
   与 P2-7「刷新后候选可能变」并用。`≈` 可吸收小幅漂移；不要把 110 当成硬等式。

3. **§1「熔断共七维」实列 8 个触发点**  
   `check_thresholds` 顺序是 candidates / new / update / align / deactivate / ratio / watermark_continuity / **source_row_conservation**。后者阈值 20 **写死、不能 env 覆盖**，但 `_compute_change_stats` 把 `source_row_delta_pct` 恒置 0（489 行），当前是死维。r2 要求打印、未进 STOP 线，可接受。

4. **R1 缺两条低成本探针**（验证空洞，P1）  
   - 容器 runner：`grep -c sync_jhemr_login_sign_daily /app/scripts/run_identity_modified_nightly.py`，预期 **=0**（与 09-06 实测一致）；若 ≥1 则 R3 会真实跑 G2，应 STOP 等授权。  
   - 生效阈值：回读 `identity_cb_max_update` / `identity_cb_max_new`。STOP 线是 `update>140`，默认代码值却是 100（`config.py:96`）。若 r181 重建弄丢 F-1 的 150，R1 不会拦，R3 会在 ratio 之前死在 `max_update`。180 B6 终值是 150/50，r181 沿用同一 env 的概率高，所以不是阻断。

5. **R1 脚本仍不可直接在 PowerShell 粘贴**  
   硬闸字段（c+d max、gap、CB `is_open`、4 个脱敏工号、守卫=2）已写清，缺的是扩展后的完整 stdin 脚本。

---

## ③ 有无新增阻断级问题

**没有。**

特别说明：有人把「本地 runner 已接线 login_sign，且 f691abb 是 r181 守卫提交的祖先」外推成「r181 容器会静默执行 G2」。这条链不成立。

- 热补 Dockerfile **不复制** `scripts/`；  
- 181 构建记录写明「镜像不含 runner=维持 W-02」；  
- 09-06 02:25 在 **r181 容器**上 `grep login_sign=0`，子任务表也没有 login_sign 行；summary 里的 `login_sign:success` 仍是 `identity_sync_audit.py:173` 默认值（与 A1 裁决一致）。

因此 r2 **§1 / §2 / §4.R4.3 / §7④** 的「本轮不跑 login_sign」不是假前提。缺的是 R1 再 grep 一次，防止事后 `docker cp` 了 runner——那是加固，不是当前阻断。

---

## 给主 AI / 用户的一句话

**采纳 r2，点名后再放行。** 不必因上述残余再开一轮大修。执行 AI 只需在 R1 多做两件事：runner `login_sign` grep=0、回读 `max_update=150`；R4.3 不要把「真实计数」理解成必须非零。未听到「按方案 r2 执行」之前，R2/R3 仍禁止动。
