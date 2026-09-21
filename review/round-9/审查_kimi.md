• 我先读取两个核心文件，再按需要查参考材料。

• 两文件已读。现在核查方案中可本地验证的技术事实（脚本名、env 变量名、水位推进逻辑、阈值读取方式）。

• 核心代码已核对。再验证几个配置默认值与方案引用的一致性。

• 再快速确认两个引用文件是否存在。

• 核查完成。以下是我的独立结论，依据为方案原文、crosscheck 原文，以及我对 `backend/` 实际代码的逐行核对（只读，未改任何文件）。

  # 核查结论（review/round-9/方案.md）

  ## ① 覆盖度与忠实度：总体忠实，无加戏，但有一处关键漏项

  方案对用户需求的覆盖是完整的：根因（§1）、立即放行（§3–§4）、治本随下次发布（§8）、交另一 AI 直接执行的执行卡形态（R0–R6 + DoD + 回滚）均在。§2 目标③ 的"次夜恢复"预期存在预测错误（见问题 3），§8 与 crosscheck §6/§7 对齐，未发现私自扩范围（R2 备份、R6 产物均有 crosscheck §5 依据；"不改 55/README" 与 crosscheck 落款一致）。

  以下代码事实经我本地核实**属实**，方案的机制诊断可信：

  - 失败不推水位：`identity_watermark.py:69-71`（`dry_run or not success` 即 return）+ `identity_sync_orchestrator.py:706`（`failed_count == 0` 才 advance）✓
  - 增量窗 = 水位 −24h：`config.py:73` ✓
  - F-2 豁免在增量模式下是死代码：`orchestrator.py:245-247`（`modified_by_code` 非空时只选带标记者）→ `436-439`（无 modified_time 才计 resync_unchanged）✓
  - ratio 分母可 < 分子：`orchestrator.py:445-451`（scope 只数 `source_create_date>=MANAGED_SINCE` 的 active 人，增量窗成员绕过该过滤）✓
  - env 覆盖变量名正确：`config.py:5` 前缀 `APP_` → `APP_IDENTITY_CB_MAX_CHANGE_RATIO` 有效 ✓
  - `PROVIDER=host_cron + NIGHTLY_ENABLED=false` 组合不会触发 `multiple_scheduler_providers` 误配（`orchestrator.py:542-563`）✓
  - 入口脚本存在且为一次性 job 形态：`backend/scripts/run_identity_modified_nightly.py` ✓

  ## ② 自发发现的问题（按严重度）

  ### 【致命】问题 1：放行命令漏了第二个熔断维度——watermark_continuity，R3 大概率照样失败

  - 代码事实：`check_thresholds` 在 ratio 之后还查水位连续性（`orchestrator.py:519-521`），阈值 `identity_cb_max_watermark_gap_hours = 48`（`config.py:106`）。`watermark_gap_hours` = now − 所有水位行中最大 `last_run_at`（`orchestrator.py:471-477`）；crosscheck §3 实测 main 行 `last_run_at=08-30`，执行时（09-06 白天）gap ≈ 145+ 小时，**远超 48h**。
  - 关键证据：`config.py:103-105` 的注释白纸黑字写着——"水位连续性阈值…连续失败后形成'失败→水位不推进→更失败'死锁；改为可配置以便**恢复性运行临时放宽**（方案 A 同款临时阈值先例）"。即 W10 先例的放行命令本来就带 `APP_IDENTITY_CB_MAX_WATERMARK_GAP_HOURS` 覆盖，而方案 R3 命令（§4 R3）只追加了 ratio 一个变量。
  - 为什么前面没暴露：`check_thresholds` 逐维 early-return（`orchestrator.py:497-525`），ratio 排在 continuity 之前，所以 crosscheck §4 复现和每晚熔断行都只能看到"第一个"失败维度。方案 §1 和 R1 所谓"**唯一**失败维度=max_change_ratio"是未证实的——它只是"第一个"，不是"唯一"。
  - 后果：按现方案执行，R3 放行 run 会在 ratio 放行后立刻被 watermark_continuity 熔断，status=failed、水位不推进；按铁律 3 禁止重试 → 任务失败收场。
  - 建议：R3 命令追加 `-e APP_IDENTITY_CB_MAX_WATERMARK_GAP_HOURS=<足够大，如 240>`（W10 同款先例，有授权脉络）；R1 复现改为**逐维独立评估**（而非只取 `check_thresholds` 的首个返回值），把 continuity 的实际 gap 值也留痕。

  ### 【中】问题 2：ratio 数值与代码口径不符——实为 114/99=1.152，非 110/99=1.111

  `orchestrator.py:515`：`change_ratio = (new + update + deactivate) / scope`，deactivate 在 `orchestrator.py:631` 被覆盖为 4，故真值 = (0+110+4)/99 = **1.152**。方案 §1 与 crosscheck §2#2/§3 的"精确实测 1.111"漏算了 deactivate；讽刺的是 B 会话最初的"ratio≈1.15"才是与代码一致的值，裁决反而把错的 1.111 标为"精确"。结论不受影响（1.152 同样 >0.3 且 <2.0，覆盖余量充足），但"实测"留痕是错的，且暴露 §4 复现输出可能未被逐字核对。

  ### 【中】问题 3：R5/目标③ 的次夜预期自相矛盾

  "候选个位数"与"`resync_unchanged` 首次出现"在代码上互斥：水位推进至 ≈09-05 08:47 后，次夜窗口起点 ≈09-04 08:47，窗内仍有 ≥1 名 modified 者（09-05 08:47:41 那条本身 > 窗口起点，会被重选）→ `modified_by_code` 非空 → 走增量分支 → 候选个位数且全为 update，**resync_unchanged=0**；只有当窗口完全为空时才会出现全托管圈 ~99 人的 resync_unchanged（`orchestrator.py:245-252`、`413-415`）。次夜 run 恢复 success 的判断不变，但执行 AI 若按方案字面核对"resync_unchanged 首现"不到，可能误判为异常。建议把 R5 预期改为二选一分支描述。

  ### 【低】问题 4：硬边界编号错位

  §3.1 写"唯一允许的生产写操作=**R4** 的一次性 docker exec"，但写操作定义在 **R3**（§4），R4 是只读后置核验。交给"别的 AI"执行时，铁律条款指错节号是真实误导风险。

  ### 【低】问题 5：数字与口径小瑕疵

  - R3 注"111 候选"——全文其他处为 110 update + 4 deactivate = 114，111 无出处。
  - R1.2 守卫核验放宽为 `grep -c skip_configured ≥1`，而 crosscheck §2#4 的实测值是 **2**；应改为 `=2`（=1 可能意味着守卫只装了一半）。
  - §3.1"其余一切生产访问只读"与 R2 在生产服务器落 pg_dump 文件（>100M）字面冲突；建议措辞改为"除 R2 备份文件与 R3 放行外只读"。

  ### 【低】问题 6：授权前提未写入执行卡

  crosscheck §5 标题明确"**待用户一句话授权**"，方案.md 全文没有这一前置条件，直接写"白天执行"。本次放行含 110 账号对齐 + 4 个 JHEMR 锁号（`orchestrator.py:772-850` 的 `execute_jhemr_lock` 是业务系统真实写），按仓库红线属"明确批准继续保留"项。执行 AI 拿到方案时应先确认用户授权到位，建议在 R0 增加一条。

  ### 【提示】问题 7：单点失败即不推水位的原子性未明示

  `orchestrator.py:706`：只要 1 个候选失败（含 4 个锁号中任何一个 JHEMR 写失败），`failed_count>0` → 水位不推进、run 判 failed（`692`），死锁依旧；且 failure_rate>0.2 还会再挂熔断标记（`686-690`）。方案 R4.2 能事后发现，但 R1 前置核验没有针对"110 人中是否存在注定失败的个体"（如 JHEMR 连接、门禁 blocked_gates 软阻断）的任何评估。这属于放行固有风险，建议至少在 §7 风险清单中明示。

  ## 总结

  方案的诊断框架、边界设计、DoD 和回滚叙述质量较高，对代码机制的理解基本准确；但**问题 1 是会让执行直接失败的硬伤**（且有 `config.py:103-105` 的自家注释为证），问题 2/3 会污染留痕与验收判断，问题 4/6 对"交给另一个 AI 执行"的场景有真实误导性。建议修正问题 1–4 后再交付执行。

