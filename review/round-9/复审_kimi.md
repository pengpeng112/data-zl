• 我先读取 round-9 目录下的相关文件。

• 核对 r2 引用的其余行号与关键代码事实。

• 再确认 `source_row_delta_pct` 是否真有非零来源（决定它是否是第三隐藏维度）。

• 需要确定生产容器内 runner 版本与 crontab 实际调用的脚本。查 deploy 与相关证据。

• 关键疑点：确认 f691abb(runner 接线） 是否为 f071c85(r181 守卫修复） 的祖先提交。

• 核查完成。以下为逐条对照结论（本地代码证据均已只读复核，未改任何文件）。

  # round-9 r2 复审结论

  ## ① 原意见 1–7 逐条核对

  **问题 1（致命，watermark_continuity 漏覆盖）→ 已落实，正确。**
  - r2 §1 第 2–3 行列出 gap≈145h+ 为"第二个被短路隐藏的失败维度"，并明确"放行命令必须同时覆盖 ratio 与 gap 两个 env"；R1 标题改为"逐维独立评估，禁止只看 check_thresholds 首个返回"并要求打印 `stats["watermark_gap_hours"]`；R3 命令已含 `-e APP_IDENTITY_CB_MAX_WATERMARK_GAP_HOURS=240`，且 §4 R3 注给出 `GAP=max(240, ceil(R1 实测)+24)`。
  - 代码复核：维度存在（`orchestrator.py:519-521`）、默认 48（`config.py:106`）、W10 先例注释（`config.py:103-105`）均与 r2 引用一致。
  - **残留偏差（小，同类问题）**：`source_row_conservation` 是**第三个会被短路隐藏的触发维度**（`orchestrator.py:523-524`，阈值 20 **写死不可 env 覆盖**）。r2 只在 R1"一并打印" `source_row_delta_pct`，但 R1 末尾的 STOP 线未列入 `source_row_delta_pct>20`。当前代码中该值恒为 0（`orchestrator.py:489`，无其他赋值点），实际风险低，但按问题 1 的同一逻辑，STOP 线应补一条，否则又依赖执行 AI 自觉。另 §1"熔断共七维"实列 8 项、代码也是 8 个触发维度，数字小误。

  **问题 2（ratio 实值 1.152）→ 已落实，正确。** §1 第 2 行改为 `(0+110+4)/99=1.152`，§8 分母行"单测锁定 114/99 不再出现"口径一致；`orchestrator.py:515` 公式复核无误。

  **问题 3（R5 次夜预期互斥）→ 已落实，正确。** §4 R5 改为二分支（a) 候选个位全 update；b) 窗口空 → 全托管圈 resync_unchanged 首现），与代码行为（`orchestrator.py:245-252`、`436-439`）一致。

  **问题 4（铁律编号错位）→ 已落实。** §3 铁律 1 改为"唯一生产写操作=R3"，并同时吸收了问题 5 的措辞修正（"R2 备份文件除外"）。

  **问题 5（数字与口径小瑕疵）→ 三项全部落实。**
  - "111 候选"已消除（R3 不再出现该数）；
  - 守卫改为 `jhemr_identity_adapter.py` 且必须=2——我本地复核 `grep -c skip_configured`：adapter=2、`identity_login_sign_sync.py`=0，与 B5 裁决一致；
  - §3 铁律 1 措辞冲突已修。

  **问题 6（授权门禁）→ 已落实。** §3 铁律 0 + R0 第 1 步双重锚定"用户点名前仅 R0/R1 只读"。

  **问题 7（单点失败不推水位）→ 已落实。** §7 ③明示"1 人失败=整 run failed 且水位不动（orchestrator:706）"——代码 706 行 `failed_count==0` 才 advance 复核无误；铁律 3 禁重试与 §6 回滚注意项呼应。

  其余共识项抽查：B3（收敛条件入 §1 第 4 行 + R1 硬闸 `max−24h > 08-27 18:57` + R4.2 改判 window_start）✓；B7（DoD 当日=R1–R4，R5 单列）✓；B8（单行命令 + BatchMode + 密钥）✓；B9（R2 备份命令写死）✓。

  ## ② 新增问题

  **【阻断级，条件触发】N1：r2 的"login_sign 不执行（r175 旧 runner 无此调用）"前提未经证实，且与 git 证据存在正面张力——若为假，R3 将静默执行 G2 写操作且全程无验收。**

  证据链：

  1. A1 裁决的本地证据只证实了 `identity_sync_audit.py:173` 的默认值逻辑存在（我复核属实）——它证明"summary 的 success 可以是默认值"，**并未证明**"容器内 runner 不调用 login_sign"。
  2. 本地 git 实测：`f691abb`（2026-09-05 10:19）把 `sync_jhemr_login_sign_daily` 接进了 `run_identity_modified_nightly.py`（现文件第 11、75-80 行：主任务 success 后**必然执行** login_sign）；`f071c85`（同日 10:49，提交信息即标 "(181)"）给 adapter 加 skip_configured 守卫；`git merge-base --is-ancestor` 确认 **f691abb 是 f071c85 的祖先**。
  3. r2 自己断言 r181 镜像含该守卫（§7④"r181 已有治本守卫"；R1 守卫要求容器内 adapter grep=2）。若容器含 f071c85，按提交谱系必含 f691abb，即**容器内 runner 已接线 login_sign**——与"r175 旧 runner"互斥，除非 r181 是 docker cp 单文件热补（无证据，且与"不 docker cp runner"的非目标措辞暗示的部署习惯相反方向）。
  4. 后果：R3 放行成功主任务后，脚本第 80 行会真实执行 login_sign（JHEMR sublogin/subsign 实写），而 r2 §1/R4.3/§7④ 均宣称它不执行、R4.3 明确豁免验收——即方案作为执行卡可能**在无人察觉的情况下违反自身非目标（"不激活 G2"）**；R4.4 的 003531 检查在"不执行"前提下是空验（恒 0），在"执行"前提下又已被 R4.3 架空。
  5. 反方向证据存在但不充分：既往熔断夜 summary 的 login_sign:success 与旧 runner+默认值相容，但那些夜跑多在 r181（09-05）部署之前；且若 runner 已接线，熔断夜应显示 skipped 而非 success——分歧表未记录 09-06 02:00（r181 时代）run 的该行取值。
  6. 容器真实内容本地不可判定，但这恰说明它必须是 R1 的一条探针而非方案前提。**修复成本极低**：R1 增加 `docker exec data-asset-api grep -c sync_jhemr_login_sign_daily /app/scripts/run_identity_modified_nightly.py`——结果 ≥1 则 STOP 呈报（R3 将连带执行 login_sign，需用户先行授权 G2 或改验收口径）；=0 则 r2 现有口径成立。

  **【提示级】N2**：R2 备份命令 `grep -oP ... | head -1` 取 backend.env 中第一个含口令的 URL，若该文件含多条连接串（如只读源库在前）可能取错口令——有"失败→STOP"兜底，且系 180 B2 同款先例，可不动，但执行 AI 应知悉失败时的排查方向。

  ## 总结

  问题 1–7 全部落实且口径正确，无倒退；问题 1 有一处同逻辑残留（source_row_conservation 未入 STOP 线，低危）。N1 是本轮新发现的阻断级隐患：它不必然导致执行失败，但存在一条证据支持的现实路径，使方案在"成功执行"的同时静默违背自己的非目标；建议在交付执行前补上 R1 探针（一条 grep）并相应分支化 R4.3。

