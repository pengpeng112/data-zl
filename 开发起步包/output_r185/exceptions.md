# 185 号执行 exceptions（WARN/受阻/修复明细）

| # | 级别 | 时间 | 事项 | 处置 | 状态 |
|---|---|---|---|---|---|
| W1 | WARN→已修复 | 09-06 17:2x | 184 产物 bug：dev_env.sh `tunnel_up()` 在本机 Git Bash（grep=ugrep）下 netstat 管道恒不命中（CRLF+GBK 头 × ugrep 流匹配交互），误判"15432 不通"→重复建转发必败（Address already in use） | 按 185 §0.6 语法级最小修复：改 bash 内建 `/dev/tcp/127.0.0.1/15432` 探测；`bash -n` 过；source 实测"复用+URL 推导"正常；结构未动 | 已修复留痕 |
| W2 | WARN | 09-06 17:0x | C1 首跑真发现：181 号文档未登记（他人域身份线新文档）+ output_r170/output_r181 未登记 + 19 老文档缺 `> 类别：` 首行 + 125 同号双题 | 只报告不代改（AGENTS：编辑任务只修正本次范围内或已核实的目录问题；181 属并行会话域） | 留等待域 |
| W3 | WARN 呈报 | 09-06 17:3x | N1b：docare 每日清单 list_20260906.md 存在但 0 字节；cron.log=ORA-12541 TNS 无监听（his_visits 连接源库失败，00:10 首跑即失败） | 只读呈报（185 §1.2 口径"异常只呈报"）；修复属生产运维决策待用户点名 | 待用户裁决 |
| W4 | WARN | 09-06 17:4x | C4：全局 multi-review/multi-verify SKILL.md 均未引用 multi_ai_evidence.py（grep 零命中） | 如实标"S4 调用链未接"，不宣称 S4 完成；接线须用户点名（改全局技能不在授权内） | 待用户决策 |
| W5 | WARN | 09-06 17:1x | 离线值域包 generated_at=2026-08-29 超 max_age_days=7 | N2 的 OPER_STATUS=0 含义标【值域待确认】只回读原值；报告提示重导 | 待重导 |
| — | 阻塞记录（已自愈） | 09-06 17:2x | 全量 pytest 首两次启动失败：①后台 shell 无 APP_TEST_DB_URL（conftest 立即 exit 4，未触库）；②相对路径 cwd 漂移（exit 127，未触库） | 第三次绝对路径+source 重发成功；两次失败均未触碰隔离库（无清理需求） | 已恢复 |
| — | STOP | — | 无（隔离库可用；他人域可避开；N1 实测与 output_r180/nightly_d.md 零矛盾；dev_env 最小修复有效） | — | 零触发 |
