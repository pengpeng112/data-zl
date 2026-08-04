---
name: mobile-nursing-readonly-sql
description: 为山东省第二人民医院移动护理独立源端（平台系统编码 MOBILE_NURSING，Oracle 11g，Owner LUNA_MCS_SDSEY）检索表结构、分析护理业务关系、编写只读 SQL，并在用户明确要求时受控执行限量 SELECT。用户提到移动护理、LUNA、MCS、护理文书、护理评估、体征、护理事件、PICC、伤口、造口、交班报告、INPATIENTS、PATIENT_UID 或移动护理与 HIS/数据中心 YDHL 对接时使用。禁止 DML/DDL、创建视图、锁表、存储过程、全表扫描和输出未脱敏患者信息；凭据仅可来自环境变量或服务器凭据文件。
---

# 移动护理只读查询

## 边界

目标是独立移动护理源端 `MOBILE_NURSING`，不是数据中心 `DATA_CENTER` 内的历史 `YDHL` Owner。只允许生成一条 `SELECT` 或只读 CTE。即使账号具有写权限，也禁止任何 DML、DDL、PL/SQL、存储过程、锁表或写通道。

## 必读依据

按任务需要读取：

1. 仓库 `AGENTS.md`、`开发起步包/README.md`、`55_系统未完成事项统一执行计划.md`。
2. 本技能 [移动护理查询指南](references/mobile-nursing-guide.md)。
3. 需要连接或执行时再读 [连接指南](references/connection-guide.md)。
4. 需要具体字段时检索 `开发起步包/86_移动护理Oracle元数据快照.json`。
5. 需要关系证据时读取 `86_移动护理Oracle活库探查与表关系分析报告.md` 和 `86_移动护理Oracle关系验证结果.json`。

旧文档 `系统表结构/移动护理数据库文档.md` 仅用于中文含义参考；活库对象和字段以 86 号快照为准。

## 工作流程

1. 明确业务目的、每行粒度、字段、时间范围、病区/患者范围、汇总口径和是否导出。
2. 在 86 号快照中确认 Owner、表、字段、类型和对象状态；不得凭表名猜字段。
3. 仅采用已验证关系。`partial`、静态视图依赖或无样本关系必须标注限制，不得伪装成强关系。
4. 显式列出字段，使用 `LUNA_MCS_SDSEY.TABLE_NAME`，参数使用 Oracle 绑定变量。
5. 大表必须先按患者键、表单键、病区和时间范围收窄；Oracle 11g 限量使用外层 `ROWNUM`，禁止 `FETCH FIRST`。
6. 默认排除姓名、身份证、电话、地址、患者标识等敏感明细；需要患者级结果时先设计脱敏输出。
7. 运行静态门禁：

```powershell
python .agents/skills/mobile-nursing-readonly-sql/scripts/validate_mobile_nursing_sql.py D:\temp\mobile_nursing.sql
```

8. 默认只交付 SQL，不连接数据库。只有用户明确要求查询/验证且安全环境可用时，才按连接指南执行。

## 执行限制

- 普通查询 `--max-rows` 最大 10000 行。
- 文件导出 `--export-max-rows` 最大 50000 行，仅允许服务器内网 `direct` 模式，输出路径必须在 Git 仓库外。
- 上限不是全表扫描授权；大事实表仍必须有业务键或时间边界。
- 执行器开启只读事务、超时、回滚和敏感列遮蔽，不打印凭据或原始连接异常。

```powershell
cd F:\python\数据资产\backend
python ..\.agents\skills\mobile-nursing-readonly-sql\scripts\run_mobile_nursing_readonly.py `
  --sql-file D:\temp\mobile_nursing.sql `
  --params-file D:\temp\params.json `
  --max-rows 10000
```

## 必须停止

- 请求包含写入、建视图、改结构、调用过程或锁表。
- 凭据不是从批准的环境变量/凭据文件提供。
- 表或字段未在活库快照确认。
- 大表查询缺少患者、业务键或时间边界。
- 查询会把未脱敏患者信息发给 AI、日志或报告。
- 跨移动护理、HIS、ODS 物理实例，却没有已核实 DBLINK、同步对象或分步对账方案。

## 交付格式

依次给出：查询口径、表结构与关系证据、SQL、绑定参数、风险/待确认、自检。自检必须说明：

- 单条 SELECT/只读 CTE；
- DDL/DML/锁为 0；
- Owner、表、字段已核对；
- JOIN 证据等级；
- 大表已收窄；
- 敏感信息已排除或脱敏；
- 业务源库写入为 0。

任一项不满足时标记“候选草稿，不可执行”。
