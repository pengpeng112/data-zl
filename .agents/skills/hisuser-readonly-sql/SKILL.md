---
name: hisuser-readonly-sql
description: 为山东省第二人民医院 HIS 源端业务库（平台系统编码 HIS_SOURCE，历史称 hisuser 库，Oracle 11g 多 Owner）检索表结构、分析与 ODS 的对接关系、编写只读 SQL，并在用户明确要求时通过仓库受控连接器执行限量 SELECT。用户提到 hisuser、HIS 源库、MEDREC、ORDADM、LAB、EXAM、INPBILL、OUTPBILL、OUTPADM、INPADM、DRUG_USER、PHARMACY、COMM、MEDADM、HIS 取数、HIS 表结构或 HIS 与 ODS 对接时应使用本技能。禁止执行 DML/DDL、创建视图、锁表、全表扫描或输出未脱敏患者信息；凭据只能来自环境变量或服务器凭据文件，不能写入提示词、代码、日志或 Git。
---

# HISUSER/HIS_SOURCE 只读查询

运行环境需要当前仓库 backend Python、python-oracledb thick、Oracle Client，以及直连网络或既有 SSH 跳板配置。凭据必须通过受控环境注入。

## 目标与边界

为 HIS 源端 Oracle 11g 多 Owner 业务库提供“查资产 → 核关系 → 生成 SQL → 静态门禁 → 可选限量只读执行”的标准流程。

`hisuser` 是历史连接账号/口头名称，不是业务主 Schema。业务对象分布于 `MEDREC`、`ORDADM`、`LAB`、`EXAM`、`INPBILL`、`OUTPBILL`、`OUTPADM`、`INPADM`、`DRUG_USER`、`PHARMACY`、`COMM`、`MEDADM` 等 Owner。SQL 必须写 `OWNER.TABLE_NAME`，不要写成 `HISUSER.PAT_VISIT`，也不要依赖会随账号改变的 PUBLIC synonym。

本技能只允许查询。即使用户有管理员权限，也不得通过本技能执行 `INSERT`、`UPDATE`、`DELETE`、`MERGE`、DDL、PL/SQL、存储过程、锁表或写通道。

## 使用前读取

按顺序完整或按主题读取：

1. `AGENTS.md`。
2. `开发起步包/README.md` 和 `55_系统未完成事项统一执行计划.md`。
3. 本技能 `references/his-source-guide.md`。
4. `开发起步包/数据资产_HIS源端资产包/` 中与需求相关的表、字段和关系。
5. 关系复杂时读取 `16`、`19`、`21`、`22`、`23`、`25` 的对应报告或结果 JSON。

不要使用 `_archive/` 作为当前依据。表字段以 `16_hisuser业务库元数据快照.json` 或平台当前元数据为准；统计行数只用于估算规模，不代表实时精确数量。

## 标准流程

### 1. 明确需求和数据粒度

确定业务主题、结果每行代表什么、字段、时间范围、筛选条件、是否汇总、返回上限以及是否涉及敏感字段。日期等具体值可使用绑定变量；会改变主表或 JOIN 的关键信息缺失时，先列问题，不猜测。

### 2. 从本地资产定位表结构

优先搜索：

- `his_source_tables.csv`：Owner、主题、角色、纳入状态、主键、规模和 ODS 同名覆盖；
- `his_source_columns.csv`：字段、类型、注释；
- `his_source_relationships.csv`：33 条源端关系及验证状态；
- `his_source_catalog.json`：程序可读汇总；
- `16_hisuser业务库元数据快照.json`：更宽的活库元数据快照。

如果平台接口可访问，使用 `system_code=HIS_SOURCE` 获取上下文；不要用 `DATA_CENTER` 代替 HIS 源端。ODS 中的同名表是同步/抽取覆盖，不代表所有 HIS 源表都进入数据中心。

### 3. 选择关系

优先级：完整验证关系 → 限定样本验证关系 → 已采纳的子集关系 → 候选关系。候选和 partial 关系不能无条件进入正式 SQL。

组合键必须完整，例如：

- 住院：`PATIENT_ID + VISIT_ID`；
- 医嘱费用/执行：再加 `ORDER_NO + ORDER_SUB_NO`；
- 检验：`TEST_NO`，项目级再加 `ITEM_NO`；
- 检查：`EXAM_NO`；
- 费用结算：按场景使用 `PATIENT_ID + VISIT_ID` 或 `RCPT_NO`。

门诊检验/检查当前只有患者加日期候选路径，不能伪装成唯一强键。

### 4. 生成只读 Oracle 11g SQL

- 只生成一条 `SELECT` 或只读 CTE；不要附带分号给执行脚本。
- 显式列字段，不交付 `SELECT *`。
- 使用 `OWNER.TABLE_NAME` 和绑定变量。
- Oracle 11g 不使用 `FETCH FIRST`；限量用外层 `ROWNUM`。
- 时间过滤使用左闭右开区间，避免对索引列做无必要函数转换。
- 事实大表必须先按业务键、时间范围或受限父键集合缩小范围。
- 默认不投影姓名、身份证、电话、住址等字段；只读执行结果进入 AI 上下文前必须脱敏。
- 交付和写入 Excel 的核查版 SQL 应使用 `--` 添加简洁中文注释，说明主要关联表的用途、JOIN 键、关键 `WHERE` 条件对应的业务口径、时间口径以及重要排除项。不要给每个显而易见的语法行添加注释。
- 受控执行器禁止 SQL 注释时，从核查版机械生成去注释执行版；不得顺便改写 JOIN、WHERE、字段、日期边界或聚合逻辑。执行后仍保留核查版作为交付版本，并注明实际执行的是逻辑一致的去注释副本。

### 5. 静态门禁

在仓库根目录运行：

```powershell
python .agents/skills/hisuser-readonly-sql/scripts/validate_his_sql.py path/to/query.sql
```

门禁检查单语句、只读关键字、锁语法、Oracle 11g 兼容性、巨表 WHERE 条件和关键业务键。通过仅表示“静态上可进入人工审核”，不证明业务口径正确。

### 6. 可选连接与执行

只有用户明确要求“连接/验证/查询”，且当前 AI 被授权访问医院内网时，才执行。连接前必须读取 `references/connection-guide.md`，按 Windows 跳板、服务器内网直连或平台 API 三种环境选择。优先使用平台 `/api/v1/ai` 只读执行流程；也可使用本技能封装的本地脚本：

```powershell
cd F:\python\数据资产\backend
$env:APP_HIS_SOURCE_PASSWORD = '<由安全渠道注入，不要粘贴到提示词>'
python ..\.agents\skills\hisuser-readonly-sql\scripts\run_his_readonly.py `
  --sql-file D:\temp\query.sql `
  --params-file D:\temp\params.json `
  --max-rows 100
```

服务器容器已挂载凭据时，不传密码；通过 `APP_HIS_CREDENTIAL_FILE` 指向受控 `.readonly` 文件。连接模式由 `APP_HIS_SOURCE_CONNECTION_MODE=direct|ssh_jump` 控制。跳板配置只使用既有 `APP_SSH_JUMP_*` 环境变量和已校验的 known_hosts。

执行脚本：

- 复用 `backend/app/services/db_connectors.py` 的 SQL 门禁；
- 开启 Oracle `SET TRANSACTION READ ONLY`；
- 强制超时；普通查询最多 `10000` 行；文件导出最多 `50000` 行；
- 自动遮蔽常见敏感列；
- 不打印用户名、密码、连接串或原始异常凭据；
- 不保存查询结果到仓库。

只做连接测试时：

```powershell
python ..\.agents\skills\hisuser-readonly-sql\scripts\run_his_readonly.py --test-connection
```

普通查询：

```powershell
python ..\.agents\skills\hisuser-readonly-sql\scripts\run_his_readonly.py `
  --sql-file D:\temp\his_query.sql `
  --params-file D:\temp\his_params.json `
  --max-rows 10000
```

文件导出只能在服务器/容器内网 direct 模式执行，最多 `50000` 行：

```powershell
python ..\.agents\skills\hisuser-readonly-sql\scripts\run_his_readonly.py `
  --sql-file D:\temp\his_query.sql `
  --params-file D:\temp\his_params.json `
  --export-file D:\exports\his_result.csv `
  --export-format csv `
  --export-max-rows 50000
```

导出文件必须位于 Git 仓库外并保持受限权限。提高行数上限不代表允许无条件扫描医嘱、检验结果、费用等大表；仍必须先按业务键和时间范围收窄。

在医院 Windows 工作站且 `F:\python\数据资产\.ssh\config_ai` 存在时，优先使用已登记别名：

```powershell
ssh -F "F:\python\数据资产\.ssh\config_ai" data-asset-83
```

保持配置文件中的 `StrictHostKeyChecking`；不得读取、显示、复制或修改私钥。连接成功后，在 `data-asset-api` 容器内使用 `/etc/data-asset/credentials/his_source_10_10_10_15` 和仓库 `OracleConnector` 执行受控只读查询。不得把凭据内容、患者明细或未脱敏结果带出容器。执行、回写和清理步骤见 `references/connection-guide.md`。

连接失败时只报告错误类型和脱敏摘要，不尝试扫描网络、搜索凭据或降低 SSH 主机校验。

## 必须停止的情况

- 用户要求写入、修改表结构、创建视图或调用存储过程；
- 认证信息未通过安全环境提供；
- 连接账号不是已登记只读源或平台 `write_policy` 不是 `readonly`；
- 主表、字段或 JOIN 关系没有元数据/验证证据；
- 巨表查询没有业务键或时间边界；
- 查询会把患者敏感明细直接发送到 AI、日志或报告；
- SQL 跨越 HIS 源端与数据中心等物理实例，却没有已核实 DBLINK/同步对象。

## 输出格式

```markdown
## 查询口径

- 业务目的：
- 结果粒度：每行代表……
- 系统：HIS（HIS_SOURCE）
- 数据库：Oracle 11g，多 Owner
- 使用对象：
- 时间与业务过滤：

## 表结构与系统对接

| 对象 | 业务含义 | 主键/粒度 | ODS 同名覆盖 | 证据来源 |
|---|---|---|---|---|

## 关系依据

| from | to | JOIN 键 | 验证状态 | 限制 |
|---|---|---|---|---|

## SQL

```sql
SELECT ...
-- 中文说明：以下关联用于……，关联键已经……验证
JOIN ...
-- 中文说明：以下条件对应统计口径中的……
WHERE ...
```

## 参数

| 参数 | Oracle 类型 | 含义 | 必填 |
|---|---|---|---|

## 执行结果

- 默认：未执行，仅生成并静态检查。
- 若已执行：连接方式、返回行数、耗时、是否截断、脱敏情况；不得输出凭据。

## 风险与待确认

## 自检

- 单条 SELECT/只读 CTE：是/否
- DDL/DML/锁：无/有
- Owner、表和字段已核对：是/否
- JOIN 有验证证据：是/否
- 大表已限定：是/否/不涉及
- 敏感结果已排除或脱敏：是/否/不涉及
- 业务源库写入：0
```

任何关键自检为“否”时，标记“候选草稿，不可执行”。
