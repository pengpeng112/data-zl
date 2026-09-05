# R163/R164 执行进度台账

| 时间 | 批 | 状态(DONE/WARN/BLOCKED) | 产物 | 数字摘要 |
|---|---|---|---|---|
| 2026-08-29 08:00 | R0 | WARN | output_r163/(progress+exceptions)、backend/_r163_work/ | HEAD=13ef9e8；SSH公钥OK；隧道改用15433（15432被不明python占用，见exceptions）；测试库连通 101表/alembic=b0c1d2e3f4a5 |
| 2026-08-29 08:06 | R0 | DONE | output_r163/progress.md | security_audit 冒烟 9 passed；基线B=161后全量 1175 passed/1 skipped/1 failed（引163§3，不重跑）|
| 2026-08-29 08:06 | R0 | WARN | CronList automation-89b8f2ec | 熔断复核分支：当前08:04早于08:30，按规则登记未到点跳过；自动化任务已确认08:30触发（一次性） |
| 2026-08-29 08:10 | R1 | DONE | backend/tests/plan127/test_s0_contract_unit.py | NF-1 复现(1 failed)→改断言 await loadData(1)（36b8743 证据在案）→plan127 25 passed；全量 0 failed 待 R7 复跑 |
| 2026-08-29 09:20 | R4 | WARN | output_r163/r4_night_checklist.md | 日间非夜窗：夜间执行清单已登记（sddw 重采+候选/SHA256 同步+159 补记录），夜窗补跑，不阻塞 R5–R7 |
| 2026-08-29 10:30 | R2 | DONE | 151_两字典表探索与圈定清单_结果.json、scripts/import_dict_value_domains.py、tests/test_value_domain_dict_import.py | E1 探索(145类/92字段/双schema差异)+E2'圈定(8主题53行)+E3 脚本7测试绿+E4 导入收敛0(全量1183 passed/0 failed)+E5 code9=69例·标志3=期限手术(6109台)+E5' TREAT_RESULT双编码错位实证+E6 导出18confirmed+1conflicted待裁决 |
| 2026-08-29 10:40 | R3 | DONE | _r163_work/ecg_import_package/(manifest/objects/columns/import_plan/relation_candidates.csv)、scripts/import_ecg_metadata.py、155_ECG元数据导入与关系候选_结果.json | 65对象/1119列(931+188)隔离库导入精确匹配+二跑幂等0；生产dry-run 0写入（新增65/1119候选）；关系候选9条(7C+2D)仅清单文件 |
| 2026-08-29 10:45 | R6 | 部分 | output_r163/r6_130_coverage.md | R6-3 adapter重试已核实(jhemr_identity_adapter.py:306)；R6-4 生产unbound=0(1键已绑定)；R6-5 死权限码11个清单；R6-6 149 P4/A/B维持后置；R6-2 H7=1/3(08-27 success,08-28/29 failed 熔断)；R6-1 130覆盖表24吸收/4开放 |
| 2026-08-29 10:32 | R2 | WARN | output_r163/exceptions.json | PORTAL DEPARTURE_METHOD_CODE(1=自行离开)与149种子confirmed(1=医嘱离院)/JHEMR字典(医嘱离院=1)三方语义冲突→confirmed行置conflicted待人工（注入链已自动排除，安全），归W3裁决 |
| 2026-08-29 11:30 | R7 | DONE | 164_163合并升级_执行报告.md + _结果.json + README/55 登记 | 总门禁全绿（1183/0 后端、194 前端、161 grep、单头）；R8 checkpoint 与 R4 夜窗清单为 WARN 待续；等待域 W1–W16 呈用户 |
| 2026-08-29 12:00 | W3 | DONE | backend/_r163_work/apply_w3_rulings.py + 导出重生成 | 用户授权按规处理：8 项裁决落隔离库（conflict 解除采信医嘱离院/code9=其他/emerg3=期限手术/TREAT_RESULT 五码按 JHEMR 语义含纠正 PORTAL 1=好转→治愈）；导出 26 confirmed/0 conflicted --check PASS；生产空库随 W1 导入 |
| 2026-08-29 12:25 | W10 | DONE | identity_sync_orchestrator.py + config.py + tests/test_identity_cb_align.py(7) + 镜像 w10c-202608291223 | 方案 C 落地：align_existing 单列（默认上限150，不计 max_new/ratio，检查失败回退保守）；全量 1190 passed/0 failed；热修链部署 8.83（p153 基镜像+代码层），容器 healthy/max_align=150/333 路由/日志净；回滚=p153 镜像+env.bak-w10c |
| 2026-08-29 12:30 | R8 | 增量 | ai-hms_qhd/evidence/GUI-20260829-01/result-summary.md | 批次 A 累计 10/26（通过 7/失败 2/待人工 1）；新增 DEF-A-004(P3 清空搜索不恢复)；IAB 工具限制如实登记，余量 checkpoint |
| 2026-08-29 12:40 | R8 | 终止(用户指示) | 本报告§14 | 血透 GUI 测试移除：批次A存档移交W11，B–G取消，W15撤销，164完成定义=R0–R7+R4 |
| 2026-08-29 12:55 | 165-E1 | DONE | 迁移 c1d2e3f4a5b6 + models/probe.py + probe_service.py + 权限种子 | 迁移往返 PASS；heads 单头；pytest -k probe 11 passed；probe.finding.read 进 catalog+四角色默认 |
| 2026-08-29 14:10 | 165-E2 | DONE | scripts/probe_templates/12条+测试 | T7 BLOCKED 登记；列名核验齐 |
| 2026-08-29 14:10 | 165-E2 | DONE | scripts/probe_templates/12条 + tests/test_probe_templates.py | 列名全核验；T7 side-b BLOCKED（ODS.PACSREPORT 无申请键）；T11 用 DIAGNOSIS_DATE/diagnosis_date |
| 2026-08-29 14:20 | 165-E4/E5 | DONE | app/api/v1/probe.py + main 注册 + test_probe_api.py(7) + service 复发测试(11) | 四端点+405 占位先于 /{id}；E5 专项全绿 |
| 2026-08-29 15:10 | 165 白天批次 | DONE | 全量 1274 passed/0 failed；链路重放+导出 --check PASS | E1-E5 全闭环，待夜窗 E3 |
| 2026-08-29 22:09 | R4 | DONE | r4_exec_log.md + 159 补记录 + sddw_snapshot_r4.json | 重采 index 859（旧 273,631 作废）/SYSTEM 隔离/443 表；候选 sha256 两侧一致（bloodnew 37+23）；3 次尝试含 2 次环境契约修正已登记 |
| 2026-08-30 10:20 | W10-2 | DONE | 镜像 w10c2-202608301011 + RUN-69d068f3793e | 水位阈值可配置化+发布；one-off 112 对齐 0 失败；水位推进/阈值复原 48/healthy；测试库上午两会话 pytest 并发碰撞致 28 setup 错（单跑全过，非代码问题） |
