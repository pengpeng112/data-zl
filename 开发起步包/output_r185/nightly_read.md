# 185 号 R5 只读核对结论（N1 三行对账 / N1b docare 清单 / N2 孤儿排班）

> 执行：2026-09-06 17:21–17:35（避开 01:45–02:30 夜跑窗口）；全程只读
> （平台库 SELECT、容器内文件读取、Docare 限量键限定 SELECT），零写入。
> 原始输出：`raw_r5_platform_output.json` + `raw_r5_full_output.txt`；脚本 `r5_readonly_check.py`。
> **09-07 晨检补记见文末「09-07 晨检」节**（N1③ 出数 + docare 第二晚观察 + 09-07 清单补跑）。

## N1 夜跑三行对账（口径：禁用"最新一行"判定，逐 run_id 定点核对）

| # | run_id | 预期（185 §1.2） | 实测 | 判定 |
|---|---|---|---|---|
| ① | `RUN-69e87f7f27dd`（09-06 02:00 cron） | failed / max_change_ratio | **status=failed，circuit_breaker_triggered=True，dimension=max_change_ratio**；candidates_total=110，started 02:00:03，finished 02:00:52 | ✅ 与 `output_r180/nightly_d.md` 对账一致（水位死锁，不重做根因分析） |
| ② | `RUN-2df6cd6db381`（09-06 08:44 排水） | success、update=110 | **status=success**；main_account_sync：candidates=110（=update 110 例）、success=111、failed=0、skipped=3；其余子任务（jhemr_signature_sync inserted=4、jhemr_user_dept_sync 12/12、jhemr_education_title_sync 1/1）全 success，签名水印已 committed（candidate 推进至 2026-09-04T23:11:06Z） | ✅ 与 `output_r180/flush/progress.md` 预期一致（真实 update 不出现 resync_unchanged） |
| ③ | 09-07 02:00 cron 行 | 缺失则 SKIP | `started_at >= 2026-09-06 12:00` 查询返回 **0 行** | ⏭️ **SKIP 待 09-07**（flush 方案 R5 观察点；**不宣称 F-2 验证完成**） |

## N1b docare 每日任务首份清单核对（独立项，不与 F-2 绑验收）

**结论：异常，如实呈报（不修复，不属本计划授权）。**

- `/opt/data-asset/evidence/docare_mismatch/list_20260906.md` **存在但 0 字节**（mtime 09-06 00:10，权限 600 正确）。
- 同目录 `cron.log`（09-06 00:10）内容为 Python traceback：
  `docare_mismatch_daily.py` 在 `his_visits` 步骤连接源库失败
  **`ORA-12541: TNS: 无监听程序`**（db_connectors.execute_readonly → oracledb.connect），
  导致清单未生成任何分组内容。
- 形态参照（同目录既有产物，非 09-06 生成）：
  - `testrun_yesterday_20260905.md`：标题/窗口/错配行数/判据（182 号口径）/处置
    （手术室在手麻系统改住院次，T_ITF_SM 自动更新）+ 按患者分组明细——形态完整；
  - `manual_c0632940_20260905.md`：单人全时段修正清单（同一患者的另两处错配
    OPER_ID=2/4，登记住院次 1→应改 2/3）；`c0632940_revision_backup.json`（650KB，09-05 22:52）在位。
- **呈报要点**：每日任务 09-06 00:10 首跑因源库（HIS 侧）无监听失败；修复动作
  （重跑/连接修正/告警）属生产运维决策，须用户点名，本计划零写入不动 cron。
- 计划预期的"自动修订/dry 标注/人工裁决分组"形态在 09-06 清单中**无从核验**
  （文件为空）；昨日试跑文件仅含人工处置分组，未见 dry 标注段。

## N1b 补跑（2026-09-06 晚，用户授权"按建议来"→ 白天补清单+观察自愈）

- 方式：`--dry-run` 模式（无参模式=每日自动**含受控自动修订**，超出"只读补清单"授权范围，未跑）；窗口按 SYSDATE 计算=昨日全天（09-05→09-06），与失败那晚一致。
- 结果：**RC=0，list_20260906.md 重生为 1251 字节**（原 0 字节），副本 `docare_list_20260906_dryrun.md`。
- 形态核验（185 §1.2 要求）：✅ dry 标注（标题"HIS 核验自动修订，dry-run"）+ 人工裁决分组（4 组逐条"仅清单（…人工裁决）"）+ 自动条件/上限声明。自动修订动作组在 09-05→09-06 窗口**无一组满足条件**（4 组均"本地号≠HIS 号，编号体系不一致"）。
- **重要副结论：那晚 cron 即使成功也是零自动修订**——错过夜跑没有遗漏任何受控修复；且 4 组 FBINCU 均已与 HIS 一致（视图值正确），业务上大概率无需动作，仅留人工裁决记录。
- ORA-12541 定性：目标是 ODS（10.10.8.216:1521 orcl，`his_visits` 步骤）；白天连接正常 → **00:10 时段性问题**（是否与 ODS 夜间维护窗口重合待观察）；09-07 00:10 cron 是否自愈与 N1③ 一并晨检。cron/告警未动（生产变更需另行点名）。

## N2 处置决策记录（用户 2026-09-06 晚拍板）

- 用户决定：**交给手术室人工作废**，本仓库/平台侧不再改动该数据。AI 不代点、不做受控写。
- 后续核验（可选，作废后任意会话只读）：`MED_OPERATION_MASTER` 该键 OPER_STATUS 应从 0 变为 -80（作废口径，值域库 confirmed）。

## N2 c0632940 孤儿排班核对（Docare 只读，键限定）

- 走 `.agents/skills/docare-anesthesia-readonly-sql` 技能；列名证据 =
  `开发起步包/80_手麻Docare系统Oracle元数据快照.json`（MEDSURGERY.MED_OPERATION_MASTER，
  139,198 行）：该表**无 `STATUS` 列，状态列= `OPER_STATUS`（NUMBER）**——计划中
  "STATUS" 即此列，未猜列名。
- 查询（全限定 + 复合键 + ROWNUM<=10 + 绑定参数，业务源库写入 0）：

```sql
SELECT * FROM (SELECT PATIENT_ID, VISIT_ID, OPER_ID, OPER_STATUS, SCHEDULED_DATE_TIME,
  START_DATE_TIME, END_DATE_TIME, OPERATING_ROOM, OPERATION_NAME
FROM MEDSURGERY.MED_OPERATION_MASTER
WHERE PATIENT_ID=:pid AND VISIT_ID=:vid AND OPER_ID=:oid) WHERE ROWNUM<=10
-- :pid='c0632940', :vid=3, :oid=1
```

- **实测：行存在，OPER_STATUS = 0**（排班日 2026-08-31 13:00，手术室 040902，
  手术名"踝关节内固定装置去除术"，START/END_DATE_TIME 均 NULL=从未执行）。
  → **孤儿排班仍在，未被处理，与预期一致（仍=0）**。
- 值域口径：confirmed 值域仅有 `OPER_STATUS>=35`=完成、`-80`=作废（SM 镜像同源）；
  **0 的精确含义【值域待确认：DOCARE.MEDSURGERY.MED_OPERATION_MASTER.OPER_STATUS】**，
  本核对只回读原值不作语义假设。离线值域包 generated_at=2026-08-29 已超
  max_age_days=7，按规则提示重导（平台 `GET /api/v1/ai/system-context` 重导出）。
- **处置建议（仅写入本报告，不执行）**：该排班为 2026-08-31 计划手术但从未执行
  （START/END 空、状态 0），对应文书错配已由 manual_c0632940 清单覆盖登记住院次
  修正；建议**人工在手麻系统「手术登记」中将该排班作废/取消**（与
  OPER_STATUS=-80 作废口径对齐），避免其继续作为孤儿排班参与每日错配比对。
  实际作废须手术室/用户在手麻系统操作，AI 不代点。

## 09-07 晨检（N1③ 出数 + docare 第二晚观察 + 09-07 清单补跑）

- **N1③ ✅ 通过**：09-07 02:00 cron `RUN-464a660b0cb3` = **success，零熔断**（circuit_breaker_triggered=False）；四个子任务全 success——main_account_sync candidates=**0**（排水前死锁水位 110 已清空，无待处理变更）、jhemr_signature_sync 水位正常推进至 2026-09-06T14:54:00Z（1886 例全 skipped_existing=例行 resync，未触发 max_update——F-2 语义按设计工作）、user_dept_sync/education_title 无变更。**排水后首个完整夜窗通过，F-2 验证观察点就此完成（185 N1③ 收口）**。原始输出 `raw_morning_0907_platform.json`。
- **docare 00:10 cron 未自愈 ❌**：syslog 证实 00:10:01 正常触发，但 list_20260907.md 再次 0 字节，cron.log 新增 traceback 与首晚相同（`his_visits` 连 ODS 8.216:1521 **ORA-12541 无监听**）。连续两晚同时段失败、白天连接正常（06:1x 补跑成功即证明）→ **定性：ODS 监听每晚 00:10 前后不可用（疑夜间维护/备份窗口）**。cron/告警/脚本均未动（生产变更需点名）。
- **09-07 清单已按昨日同类授权模式白天补跑**（--dry-run，06:1x）：753 字节、2 组（00705241/c0460474）全部"FBINCU 已与 HIS 一致+本地号≠HIS 号→人工裁决"、**零自动修订候选**（连续两天该窗口形态一致：无纸化视图值已正确，仅需人工裁决留档）。副本 `docare_list_20260907_dryrun.md`。
- **待用户决策（docare 根治三选）**：① cron 时间后挪（需先确认 ODS 监听恢复时刻，如 00:40/01:00 试探）；② 脚本加重试/退避（改服务器脚本需点名）；③ 失败告警（cron 邮件或平台通知）。不改则维持"白天人工补跑"模式亦可运行，但每晚都会产生 0 字节清单+traceback 噪音。
