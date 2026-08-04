---
name: docare-anesthesia-readonly-sql
description: 为山东省第二人民医院 Docare 手术麻醉独立源端（平台系统编码 DOCARE，Oracle 11g，MEDSURGERY/MEDCOMM/MEDICU 多 Owner）检索表结构、分析手术麻醉关系、编写只读 SQL，并在用户明确要求时受控执行限量 SELECT。用户提到 Docare、手麻、手术麻醉、麻醉计划、麻醉总结、麻醉事件、术中监护、手术排班、镇痛、交接、MED_OPERATION_MASTER、MEDSURGERY、MEDCOMM 或 MEDICU 时使用。禁止 DML/DDL、创建视图、锁表、存储过程、全表扫描和输出未脱敏患者信息；凭据仅可来自环境变量或服务器受控凭据文件。
---

# Docare 手术麻醉只读查询

## 边界

目标是独立源端 `DOCARE`。数据中心 `DATA_CENTER` 内的 `SM` 是同步镜像区，不是同一物理连接。只允许一条 `SELECT` 或只读 CTE；禁止 DML、DDL、PL/SQL、存储过程、锁表和写通道。

## 必读依据

1. `AGENTS.md`、`开发起步包/README.md` 和 `55_系统未完成事项统一执行计划.md`。
2. 本技能 [Docare 查询指南](references/docare-guide.md)。
3. 需要连接或执行时读取 [连接指南](references/connection-guide.md)。
4. 字段以 `开发起步包/80_手麻Docare系统Oracle元数据快照.json` 为准。
5. 关系以 `80_手麻Docare系统活库探查与关系分析报告.md` 和 `80_手麻Docare系统关系验证结果.json` 为准。

## 标准流程

1. 明确业务目的、每行粒度、手术范围、时间范围、字段、汇总口径和是否导出。
2. 在 80 号快照中确认 Owner、对象、字段和类型；不得依赖默认 Schema 或同义词。
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

默认只生成 SQL。只有用户明确要求连接、验证或查询，并且安全环境可用时，才按连接指南使用执行器。

## 查询和导出

- 普通查询：`--max-rows` 最大 10000。
- 文件导出：`--export-max-rows` 最大 50000，仅允许服务器内网 `direct` 模式及 Git 仓库外路径。
- 上限不构成全表扫描授权；业务键和时间边界始终优先。

```powershell
cd F:\python\数据资产\backend
python ..\.agents\skills\docare-anesthesia-readonly-sql\scripts\run_docare_readonly.py `
  --sql-file D:\temp\docare.sql `
  --params-file D:\temp\params.json `
  --max-rows 10000
```

## 必须停止

- 用户要求写入、创建视图、修改结构、调用过程或锁表。
- 认证信息未通过批准的环境变量或凭据文件提供。
- 表、字段或复合 JOIN 键未在活库证据中确认。
- 大表查询缺少手术键、患者键或时间边界。
- 查询会把未脱敏患者信息发送给 AI、日志或报告。
- 跨 Docare 与数据中心 SM/HIS 查询，却没有已验证同步对象、DBLINK 或分步对账方案。

## 输出要求

依次提供：查询口径、结果粒度、对象与字段、JOIN 关系及证据、Oracle 11g SQL、绑定参数、大表限制、敏感信息处理、风险与待确认、静态门禁结果。最后明确“业务源库写入为 0”。任一安全项不满足时标记“候选草稿，不可执行”。
