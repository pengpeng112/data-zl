先按仓库规则做只读目录自检，再读待审方案、核查包和相关证据，独立判断覆盖度与风险。目录入口已定位。接下来通读方案、核查包和夜跑证据，核对根因与处置是否一致。方案与核查包已对照。接着核代码、夜跑证据和 cron 口径，验证水位死锁与放行命令是否站得住。水位推进口径和熔断分母是方案能否单次收敛的关键，接下来对着 orchestrator、watermark 和 cron 原文核对。发现一个硬问题：`check_thresholds` 会短路，ratio 之后可能还有水位连续性熔断。继续核对 runner、配置项和 09-05 时间戳从哪来。核对完编排器短路顺序、水位推进公式和 W10 先例后，结论已经明确：方向对，但按现状执行会在下一道熔断上失败。**独立结论：战略方向正确，不能按 `review/round-9/方案.md` 原文直接执行。** 一次性进程级放行 + 治本随下次发布，与用户原话和 `deadlock_crosscheck.md` 两会话共识一致；但方案漏了 `check_thresholds` 的下一道短路熔断（水位连续性 48h）。按原文只覆盖 `APP_IDENTITY_CB_MAX_CHANGE_RATIO=2.0`，R3 很大概率仍 `failed`，且方案禁止重试，等于烧掉唯一放行机会。

本次为只读核查：未改任何文件、未连生产、未触发同步。下面数字以仓库源码 + `output_r180` 文档为准；09-05 时间戳是否落在「真正被处理的 110+4」里，执行前必须再测。

---

## 1. 覆盖度与忠实度

用户原话三件事：分析如何解决、方案细到可交其他 AI 执行、处置=一次性受控放行（进程级 ratio 覆盖）+ 治本随下次发布。

| 需求点 | 覆盖 | 忠实度 | 说明 |
|---|---|---|---|
| 根因=水位死锁（失败不推水位→110 人重选→ratio 熔断→再失败） | 有 | 高 | §1 机制正确，与 `nightly_d.md` §五B 一致 |
| F-2 未失效、增量下是死代码 | 弱 | 中 | 只在 §1 用「F-2 全判 update」带过，未写清「无 `modified_time` 才进 `resync_unchanged`」 |
| 一次性进程级 ratio 覆盖 | 有 | 高 | §3/§4.R3 不改 env/cron/镜像 |
| 治本随下次发布 | 有名无实 | 中低 | §8 只是清单，无文件/测试/验收，执行 AI 无法据此改代码 |
| 细到可直接执行 | 不够 | 低 | 缺授权门禁、缺可粘贴 dump、SSH 无公钥、R1 复现会误判「唯一失败维度」、R3/R4 编号打架 |
| 不扩大范围 | 基本 | 有破口 | 非目标写「不追认 G2」，目标又写「三+1 子任务」含 login_sign |

§0 内嵌的需求原文被截断，但要点没有被换成第三条路线（例如持久改阈值、等窗口自愈）。这一点是忠实的。

---

## 2. 自发问题（按严重度）

### P0-1 只覆盖 ratio，下一道 `watermark_continuity` 会接手炸（方案不可按原文执行）

**引用：** §3.2 / §4.R3 只追加 `APP_IDENTITY_CB_MAX_CHANGE_RATIO=2.0`；§1 与 R1 宣称「唯一失败维度=max_change_ratio」。

**源码：** `check_thresholds`（`identity_sync_orchestrator.py` 497–525 行）按顺序短路返回，ratio 之后才是水位连续性：

```515:521:backend/app/services/identity_sync_orchestrator.py
    change_ratio = (stats.get("new", 0) + stats.get("update", 0) + stats.get("deactivate", 0)) / scope
    if change_ratio > settings.identity_cb_max_change_ratio:
        return {"triggered": True, "dimension": "max_change_ratio", ...}
    wm_limit = settings.identity_cb_max_watermark_gap_hours  # 默认 48
    if stats.get("watermark_gap_hours", 0) > wm_limit:
        return {"triggered": True, "dimension": "watermark_continuity", ...}
```

`watermark_gap_hours` 取**任意** `asset_identity_sync_watermarks` 行的最新 `last_run_at`（同文件 471–477 行），且**只在 success 时**由 `advance_watermark` 更新。熔断失败路径不推进水位。

**证据：**  
- 晨检脚本先撞 ratio，所以看不到后一道。失败 run 的 `report_summary` 还故意丢掉 `watermark_gap_hours`（orchestrator 640 行）。  
- 上次同类死锁（55 号 08-30 W10）**必须**临时放宽 `identity_cb_max_watermark_gap_hours` 到 96 才跑通。  
- 最近一次主链 success 不晚于 08-30/08-31，到 09-06 已约 150h+ ≫ 48。

**风险：** 按原文执行 → R3 仍 `failed`（维度换成 `watermark_continuity`）→ 方案 §3.3 禁止重试 → 死锁继续，还可能让执行 AI 误报「ratio 覆盖无效」。

**修正：** R1 必须**单独打印** `stats["watermark_gap_hours"]`。若 `>48`，同进程再加  
`-e APP_IDENTITY_CB_MAX_WATERMARK_GAP_HOURS=<ceil(gap)+24>`  
（建议下限 96，与 W10 同款；现估 180–240）。仍禁止改 env 文件。

---

### P0-2 「单次收敛」取决于 09-05 时间戳是否在 110+4 里；方案把它写成已证事实

**引用：** §1「窗内 max MODIFIEDTIME=**2026-09-05 08:47:41** → 一次成功 run 后水位推进至该值，窗口滑过全部积压，**单次收敛**」；R4.2「推进至 ≈2026-09-05T08:47:41（允许=候选集 max）」。

**源码：** 水位推进到的是 **candidates+deactivate 的 max(`modified_time`)**，不是 129 人快照的 max，也不是 now（orchestrator 705–722 行）。`advance_watermark` **没有「禁止回退」守卫**。下一夜窗口起点 = 新水位 − `lookback` 24h。

要滑出 08-27 18:49/18:57 聚簇，必须：

`新水位 > 聚簇时刻 + 24h`  
即大约 `last_create_date > 2026-08-28 18:57 UTC`（或 `08-29 02:57+08`）。

当前水位 `2026-08-28 02:57:45+08` 与聚簇 `2026-08-27T18:57:45`（naive 当 UTC）是**同一瞬间**。若 110+4 的 max 仍是这条聚簇，成功 run 的水位原地踏步，24h lookback 下一夜把同一批人再选进来——这正是 W10 的真实结局：55 号写「水位推进至 10:16」，crosscheck §2.1 已裁决那是 `last_run_at`，`last_create_date` 从未越过聚簇。

HIS 活库 `MODIFIEDTIME>=08-30` 只有 **3** 人（crosscheck §3）。这 3 人若在 19 名被过滤者里（无科室/冲突/protected/非医护药），候选集 max 就到不了 09-05。

**风险：** R3 `success` 但死锁不破；R4.2「允许=候选集 max」会把「没动」判成通过。  
**修正：** R1 打印 `max(modified_time of c+d)`。硬闸：该值必须 `> 聚簇+24h`（至少 ≥08-30）。否则 STOP，不要放行。R4.2 改为：新水位必须让 `window_start > 08-27 18:57`，而不是「约等于 09-05 或候选 max」。

---

### P0-3 硬边界写「唯一写操作=R4」，正文写操作在 R3

**引用：** §3.1 vs §4.R3/R4。

**风险：** 执行 AI 在 R4 只读核验里找 docker exec，或漏跑真正的放行。属指令级事故。  
**修正：** 全文统一：R3=唯一写；R4=只读核验。

---

### P1-1 R1 守卫 grep 文件错误，可能假 STOP

**引用：** §4.R1.2  
`grep -c skip_configured /app/app/services/identity_login_sign_sync.py` ≥1。

**事实：** 本地源码里 `skip_configured` **只**出现在 `jhemr_identity_adapter.py`（align 主路径，约 919/935 行，共 2 处）。`identity_login_sign_sync.py` 用的是 `skipped_configured`。181 号在产实证也是 adapter ≥2。主任务 110 人走的是 `align_existing_user`，不是 login_sign 子任务。

**风险：** 守卫其实在产，grep 到 0 → 错误 STOP；或执行 AI 改 grep 整树凑数。  
**修正：**  
`grep -c skip_configured /app/app/services/jhemr_identity_adapter.py` 预期 ≥2。

---

### P1-2 G2 / login_sign 目标自相矛盾

**引用：** §2 非目标「不追认 G2（仅呈报）」；同节目标「三+1 子任务积压补齐」；§7.3「login_sign 子任务将执行」；R4.3 要求四行子任务 success。

**事实：**  
- `Dockerfile.hotpatch` 只 COPY `app/ alembic/ alembic.ini`，不含 `scripts/`。  
- 180 `release_evidence.md` B5：容器 runner 仍是 r175，`login_sign=0`，**刻意不激活 G2**。  
- 新 runner 才调用 `sync_jhemr_login_sign_daily`。旧 runner 调 `finalize_run` 时不传 `login_sign_result`，审计层默认 `{"status":"success"}`（`identity_sync_audit.py` 173 行）。这就是 `nightly_d.md` 里 login_sign=success 且当日 actions=0 的来源——**假成功，不是 G2 已上线**。

**风险：** 执行 AI 为凑 R4.3 去 docker cp 新 runner，等于未授权激活 G2（写 JHEMR 登录/签名方式全托管圈）。或 R4.3 因找不到第四行子任务而误判失败。  
**修正：** 本轮明确 **不跑 login_sign**。R4.3 只验收既有三子任务（signature / user_dept / education_title）。G2 维持呈报。主路径 align 的 `skip_configured` 仍要核（见 P1-1）。

---

### P1-3 ratio 口径写错，2.0 仍够用，但会误导阈值选择

**引用：** §1「ratio=110/99=1.111」。

**源码：** 分子是 `new+update+deactivate`，覆盖 deactivate=4 后是 **114/99≈1.152**，不是 1.111。若有人按 1.111 把覆盖改成 1.2，仍然能过；不要再往下压。2.0 对 1.152 有余量，这点方案选值是对的。

---

### P1-4 R3 命令在 Windows 上不可直接粘贴；缺 SSH 公钥/BatchMode

**引用：** §4.R3 `ssh root@10.10.8.83 "docker exec \` 多行反斜杠。

本机是 PowerShell，`\` 续行无效；AGENTS 要求 `BatchMode=yes` + `C:\Users\Administrator\.ssh\id_ed25519_ai`。无 BatchMode 会挂在密码提示（红线禁止把 SSH 密码写入命令）。

**修正：** 单行、带密钥，见文末修订命令。

---

### P1-5 R2 备份「同款」指向空命令

**引用：** §4.R2「crosscheck §5 同款」。crosscheck §5 只有一句话「生产库 pg_dump」，没有命令。可复制的是 180 §B2（还可能撞口令墙）。

**风险：** 执行 AI 猜 dump 命令、回显 `APP_DB_URL`、或跳过备份。  
**修正：** 写死 180/181 同款：从 env 解析用户/库，口令只进变量，路径 `/opt/data-asset/data_asset_pre_flush_YYYYMMDD.dump`，`ls` >100M。

---

### P1-6 缺「用户点名授权」硬闸

crosscheck §5 写明「待用户一句话授权」。方案 R0 没有「未点名则 STOP」。当前这条用户消息是**审查**，不是放行。生产写 JHEMR/CDMS（经既有 nightly 通道）仍须点名。

---

### P1-7 DoD 把次夜 R5 绑进「宣称完成」

**引用：** §5「R5 次夜 success + resync_unchanged 首现」为完成必要条件。

单会话白天无法完成 R5。应拆成：当日 DoD = R1–R4；R5 = 排程观察，失败只呈报。

---

### P2 其他

1. **R3 预估 1–5 分钟偏紧。** 签名子任务扫托管圈缺签，积压 6 晚。W10 约这个量级，但应给 ssh/docker 15–30 分钟超时；超时以 run 行为准，不自动杀后重试。锁超时 3600s。  
2. **禁止 01:45–02:30 执行。** cron 有 `flock -n`，手动 exec 不进同一 flock；库内还有 `identity_nightly_sync` 分布式锁。  
3. **并行会话范围写窄了。** §9 只提 182。55 号当天还有 CDMS `T_MSS_HOSPITALFOFFN` 批量补行；放行会对 110 人做 CDMS align。应避开其他会话写 CDMS/JHEMR 的窗口。  
4. **R4.4「同量级」过软。** 改为：`failed_count=0`；`actions≥success_count`；compensations=0 或逐条说明。  
5. **4 个 deactivate 是锁 JHEMR 账号。** §7.2 有知情，但 R1 应脱敏列出 4 个工号再放行。  
6. **§3.4「业务源库零直连」易被读成「不准跑会写 JHEMR 的任务」。** 应写成：禁止 AI 直连 HIS/JHEMR/CDMS；允许且仅允许经本条 nightly 通道写。  
7. **R1 复现不含 `refresh_source=True`，真跑会先 `sync_his_identity`。** 候选集可能变。R1 STOP 线（update>140、new/deactivate 激增）要保留。  
8. **部分失败不推水位。** `failed_count==0` 才 `advance_watermark`。1 人失败则整 run failed、水位不动。禁止自动重试是对的；呈报时要说明「已写入的逐人事务不会回滚，水位仍卡死」。  
9. **§8 治本不可执行。** 用户要的「详细方案」含治本，但明确本轮不改代码。清单应升级为「下次发布规格」，见第 4 节。  
10. **R6 不改 55/README** 与 AGENTS 登记规则冲突。可暂避并行撞写，但必须把登记标成主 AI 收口义务。  
11. **缺一次性执行提示词**（177/178/180 都有）。用户原话就是要交给别的 AI。

---

## 3. 对「问题如何解决」的独立判断

机制（已核实，不必再辩）：

1. `main_account_sync.last_create_date` 停在 `2026-08-28 02:57:45+08`。  
2. 增量窗 = 水位 − 24h → 从 08-27 02:57 一直开到现在，08-27 HIS 批量 UPDATE 的人每晚重入。  
3. 这些候选人**都带** `modified_time` → F-2 正确记 update，**不会**进 `resync_unchanged`。F-2 没坏，只是豁免条件在增量模式下根本走不到。  
4. `update=110` 过了 F-1 的 150，但 `ratio=(110+4)/99≈1.15>0.3` 熔断；失败不推水位 → 死锁。  
5. 自愈不存在。持久调高 ratio 等于拆掉熔断。正确应急仍是 **W10 同款：进程级阈值覆盖 + 一次成功把水位推过「聚簇+24h」**。  
6. 治本必须改：ratio 分子用真实 diff、分母与候选同口径、失败也要能把水位推过已处理集合或缩短 lookback、熔断构成写入 run 行（含 `watermark_gap_hours`）。

---

## 4. 修订后执行卡（给执行 AI；本轮仍须用户点名）

未听到用户明确说「按修订方案执行 / 授权放行」之前：**R2/R3 禁止动**。

### 硬边界

- 唯一生产写 = 一次 `docker exec` 跑既有 `run_identity_modified_nightly.py`（进程级 `-e`，不改 env/cron/镜像、不重启、不 cp runner）。  
- 禁止 Git push、禁止业务库直连、凭据零落盘。  
- 失败不得自行重试。  
- 不激活 G2（不 docker cp 新 runner）。  
- 避开 01:45–02:30，避开其他会话写 CDMS/JHEMR。

### R0

读 `AGENTS.md`、`output_r180/deadlock_crosscheck.md`、`nightly_d.md` §五B/§六。  
`ssh -o BatchMode=yes -i C:/Users/Administrator/.ssh/id_ed25519_ai root@10.10.8.83 "docker ps --filter name=data-asset-api --format '{{.Image}} {{.Status}}'"`  
镜像必须是 `data-asset:r181-20260905` 且 healthy，否则 STOP。

### R1 只读（必须打印，禁止只看 check_thresholds 的第一返回值）

在容器内用 crosscheck §4 脚本，**额外**打印：

- `s["watermark_gap_hours"]`、`s["scope"]`、覆盖后的 `deactivate=len(d)`  
- 真 ratio = `(new+update+deactivate)/scope`  
- `max/min modified_time` of `c+d`（不要用 129 人快照代替）  
- `asset.asset_identity_circuit_breaker` 的 `nightly_cdms/nightly_jhemr.is_open`  
- adapter：`grep -c skip_configured /app/app/services/jhemr_identity_adapter.py` ≥2  
- 4 个 deactivate 工号脱敏名单

**STOP：** 持久 CB 已 open；update>140；new 或 deactivate 激增；`max(c+d.modified_time)` 不能保证下一夜 `window_start > 08-27 18:57`；守卫 grep <2。

### R2 备份

用 180/181 同款 pg_dump（口令只进变量），输出  
`/opt/data-asset/data_asset_pre_flush_20260906.dump`，`ls` >100M。失败 STOP。

### R3 唯一写（白天，单行）

在 R1 测得的 gap 上取 `GAP_LIMIT = max(96, ceil(gap)+24)`。下面以 240 为例，执行时换成实测值：

```powershell
ssh -o BatchMode=yes -i C:/Users/Administrator/.ssh/id_ed25519_ai root@10.10.8.83 "docker exec -e APP_IDENTITY_SCHEDULER_PROVIDER=host_cron -e APP_IDENTITY_NIGHTLY_ENABLED=false -e PYTHONPATH=/app -e APP_IDENTITY_SYNC_ENABLED=true -e APP_IDENTITY_JHEMR_PASSWORD_WRITE_ENABLED=true -e APP_IDENTITY_CDMS_FID_SEMANTICS_CONFIRMED=true -e APP_IDENTITY_PHASE_D_APPROVAL_VERSION=identity-nightly-modified-20260805-v1 -e APP_IDENTITY_SYNC_DIRECT_CONNECTION=true -e APP_IDENTITY_CB_MAX_CHANGE_RATIO=2.0 -e APP_IDENTITY_CB_MAX_WATERMARK_GAP_HOURS=240 data-asset-api python /app/scripts/run_identity_modified_nightly.py"
```

超时 20–30 分钟。stdout 可能是 `success` 或 `partial_success`；**以库内 run 行为准**。

### R4 只读验收（当日 DoD）

| 项 | 通过标准 |
|---|---|
| 主任务 | `status=success`，`circuit_breaker_triggered=false`，`failed_count=0` |
| 水位 | `window_start(last_create_date, 24h) > 08-27 18:57`；若仍停在 08-28 02:57 → **未解除死锁**，即使 success 也要呈报失败 |
| 子任务 | signature / user_dept / education_title ≠ skipped；**不要求** login_sign 行 |
| 守卫 | 已有登录/签名方式的用户，审计中无新的 `sign_way=0` INSERT |
| 守恒 | actions≥success_count，compensations=0 或逐条说明 |
| 配置 | env/cron/镜像未改；ratio/gap 覆盖随进程结束消失 |

### R5（次日，不阻塞当日完成）

09-07 02:00 后只读：预期候选个位数、`resync_unchanged` 首次出现、CB=false。仍熔断则原样呈报。

产物建议：`开发起步包/output_r180/flush/`。55/README 由主 AI 登记。

---

## 5. 治本（下次镜像发布，本轮不编码）

| 项 | 改什么 | 验收 |
|---|---|---|
| ratio 分子 | 只计计划内真实 diff；幂等重入不计 | 110 人带 `modified_time` 但 align 无 diff → 不熔断；110 真字段变更仍熔断 |
| ratio 分母 | 与候选同口径，禁止分子>分母 | 单测锁定 110/99 不再出现 |
| 水位 | success 后推进到 `max(候选 modified_time, window_start+lookback+ε)` 或等价「已处理集合不再入窗」 | 用 08-27 聚簇夹具：成功一次后次夜候选不含该聚簇 |
| 可观测性 | 熔断行保留完整 stats（含 `watermark_gap_hours`、分桶计数）；`_fetch_jhemr_existing_emp_nos` 的 bare except 打 WARN | 失败 run 能直接读出全部维度，不必重放 |
| F-3（可选） | 主熔断时签名/职称/科室仍补缺 | 独立开关，默认关 |
| G2 | 书面追认后再换 runner | r181 已有 align 守卫；不要和本次放行绑在一起 |

---

## 6. 目录自检（只读，未改文件）

`review/round-9/` 是评审产物，不在 `开发起步包/README.md` 编号清单里，符合惯例。本轮没有新的 `18x_*.md`。55 顶部仍写 180 D1 待出、181 预期 F-2 首夜 success——与 09-06 实测 FAIL 已不一致，登记留给主 AI，本次不改。

---

**给主 AI / 用户的一句话：** 不要批准原文方案执行。采纳 P0-1（同时覆盖 gap 小时数）+ P0-2（R1 验证候选 max 能滑出窗口）+ P1-1/P1-2（grep 改 adapter、砍掉 login_sign DoD）之后，再点名授权一次白天放行。
