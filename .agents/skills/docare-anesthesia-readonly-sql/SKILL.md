---
name: docare-anesthesia-readonly-sql
description: 为山东省第二人民医院 Docare 手术麻醉独立源端（平台系统编码 DOCARE，Oracle 11g，MEDSURGERY/MEDCOMM/MEDICU 多 Owner）检索表结构、分析手术麻醉关系、编写只读 SQL，并在用户明确要求时受控执行限量 SELECT。用户提到 Docare、手麻、手术麻醉、麻醉计划、麻醉总结、麻醉事件、术中监护、手术排班、镇痛、手术护理交接、MED_OPERATION_MASTER、MEDSURGERY、MEDCOMM 或 MEDICU 时使用。禁止 DML/DDL、创建视图、锁表、存储过程、全表扫描和输出未脱敏患者信息；凭据仅可来自环境变量或服务器受控凭据文件。
---

# Docare 手术麻醉只读查询

## 边界

目标是独立源端 `DOCARE`。数据中心 `DATA_CENTER` 内的 `SM` 是同步镜像区，不是同一物理连接。只允许一条 `SELECT` 或只读 CTE；禁止 DML、DDL、PL/SQL、存储过程、锁表和写通道。

## 必读依据

1. 按 `AGENTS.md`「启动阅读与时效」读取入口文件；本会话已读的不重复读。
2. 本技能 [Docare 查询指南](references/docare-guide.md)。
3. 需要连接或执行时读取 [连接指南](references/connection-guide.md)。
4. 字段优先取 DOCARE 平台当前元数据；缺失或不可用时回退 `开发起步包/80_手麻Docare系统Oracle元数据快照.json` 并标注日期。
5. 关系以 `80_手麻Docare系统活库探查与关系分析报告.md` 和 `80_手麻Docare系统关系验证结果.json` 为准。

## 请求与执行批准

以仓库 `AGENTS.md`「安全红线」（白天定向查询、批量探查定义、五要素任务级判断、通道与审批）和「自主执行、澄清与批准边界」为唯一规则源，本技能不另设审批。用户明确要求连接、查询或验证即构成该范围内的操作请求，无需再问是否开始。

## 字段值域硬规则（149 值域知识库，强制）

- 涉及编码/状态/类型/阈值/字典类字段（如 手术/麻醉状态码、急诊标志、离院方式等（含跨系统镜像 `SM.MED_OPERATION_MASTER.OPER_STATUS` 口径））写 SQL/给口径前**必须先取值域，禁止凭字典表名、字段注释或惯例猜测**。
- 取值顺序、缺失处理（含“实测候选值域”补证）、离线 JSON 超龄处理和陷阱，统一按仓库 `AGENTS.md` 硬约束 6 执行（平台 `system_code=DOCARE`）；新值域证据仅在用户要求摄取/登记或任务已授权候选提交时提交平台 pending，确认/裁决须人工，不因未提交阻塞原任务。

## 标准流程

1. 明确业务目的、每行粒度、手术范围、时间范围、字段、汇总口径和是否导出。
2. 在 DOCARE 平台当前元数据中确认 Owner、对象、字段和类型，缺失或不可用时回退 80 号快照并标注日期；不得依赖默认 Schema 或同义词。
3. 优先选择已验证关系，保留孤儿率和历史数据限制。
4. 使用全限定对象名和完整复合键：
   - 患者：`PATIENT_ID`
   - 就诊：`PATIENT_ID + VISIT_ID`
   - 实际手术：`PATIENT_ID + VISIT_ID + OPER_ID`
   - 排班：`PATIENT_ID + VISIT_ID + SCHEDULE_ID`
5. 显式投影字段、使用绑定参数。Oracle 11g 限量使用外层 `ROWNUM`，禁止 `FETCH FIRST`。
6. 监护、事件、检验、自定义数据等大表必须先按手术键、患者键或时间范围收窄。
7. 默认排除姓名、证件号、电话、地址和患者标识；患者级结果进入 AI 前必须脱敏。
8. 运行静态门禁：

```powershell
python .agents/skills/docare-anesthesia-readonly-sql/scripts/validate_docare_sql.py D:\temp\docare.sql
```

用户仅需 SQL 时到此交付；用户明确要求连接、查询或验证且环境可用时，直接按 `AGENTS.md` 与连接指南执行受控只读查询。

## 查询和导出

- 普通查询：`--max-rows` 最大 10000。
- 文件导出：`--export-max-rows` 最大 50000，仅允许服务器内网 `direct` 模式及 Git 仓库外执行器路径（不得降低执行器路径门禁）。允许交付的脱敏结果最终按根 AGENTS.md 取数导出目录规则归集至 `取数/exports/<序号、任务名>/`，交付前核验 Git 忽略状态；原始患者明细不因此获得带出权限。
- 上限不构成全表扫描授权；业务键和时间边界始终优先。

```powershell
cd F:\python\数据资产\backend
python ..\.agents\skills\docare-anesthesia-readonly-sql\scripts\run_docare_readonly.py `
  --sql-file D:\temp\docare.sql `
  --params-file D:\temp\params.json `
  --max-rows 10000
```

## 阻塞范围与停止条件

以下情况只停止依赖该条件的连接、SQL 生成或执行步骤；继续完成已授权的本地资产核对、候选说明、静态检查和其他独立工作。不得猜测字段、改用写连接或降低校验来绕过。

- 用户要求写入、创建视图、修改结构、调用过程或锁表。
- 认证信息未通过批准的环境变量或凭据文件提供。
- 表、字段或复合 JOIN 键经平台当前元数据、80 号快照和允许的只读结构通道核对后仍未确认。
- 大表查询缺少手术键、患者键或时间边界。
- 查询会把未脱敏患者信息发送给 AI、日志或报告。
- 跨 Docare 与数据中心 SM/HIS 查询，却没有已验证同步对象、DBLINK 或分步对账方案。

## 输出要求

依次提供：查询口径、结果粒度、对象与字段、JOIN 关系及证据、Oracle 11g SQL、绑定参数、大表限制、敏感信息处理、风险与待确认、静态门禁结果。最后明确“业务源库写入为 0”。任一安全项不满足时标记“候选草稿，不可执行”。
