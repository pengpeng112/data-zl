---
name: ods-readonly-sql
description: 为山东省第二人民医院数据资产平台的数据中心（DATA_CENTER/ODS，Oracle 11g）编写、复核或优化只读取数 SQL。用户提到 ODS、数据中心、V_EMR、CDR、住院、门诊、医嘱、费用、检验、检查、手麻、电子病历、移动护理、CDA 字典、取数 SQL、报表 SQL、视图 SELECT、字段或表关系时应使用本技能；即使用户没有明确说“使用技能”，只要目标是在数据中心取数，也应先按本技能核对本仓库元数据与关系证据。只生成 SELECT/只读 CTE，不创建视图、不执行 SQL、不执行任何 DDL/DML。
compatibility: 需要能够读取当前仓库文件；可选调用平台只读 API。无需数据库写权限。
---

# ODS 数据中心只读取数 SQL

## 目标

根据当前仓库中的活库元数据、已验证关系、已有视图 SQL 和治理口径，为数据中心生成可审查的 Oracle 11g `SELECT`。默认只交付 SQL，不连接源库、不执行 SQL；只有用户明确要求验证且环境允许时，才可通过平台的只读执行端点做限量验证。

源业务数据库是医疗生产数据源。错误 JOIN 会造成重复、漏数或错误归属，大表全扫会影响生产，因此先核对资产和关系，再编写 SQL。

## 首次使用时必须读取

按顺序读取，并仅加载与本次主题有关的部分：

1. `AGENTS.md`：安全红线、Oracle 11g 和大表限制。
2. `开发起步包/README.md`：当前权威目录及资产状态。
3. `开发起步包/55_系统未完成事项统一执行计划.md`：避免把未完成能力当成已完成。
4. 本技能的 `references/ods-sql-guide.md`：ODS 专用表、关联键、方言和输出规则。
5. 依据业务主题，从 `references/ods-sql-guide.md` 指向的权威资产中选读元数据、关系或视图 DDL。

不要把 `_archive/` 文档作为当前依据。文档与活元数据冲突时，以当前平台目录或 `08_数据中心元数据快照.json` 为准；关系是否可用于正式 SQL，则以已验证关系和治理口径为准。

## 工作流程

### 1. 收敛需求

从用户描述中提取：

- 业务主题和统计口径；
- 明细或汇总粒度；
- 所需字段及中文含义；
- 时间范围、科室、患者/就诊、状态等过滤条件；
- 期望一行代表什么；
- 是否允许返回敏感字段，以及脱敏方式；
- 目标是直接查询 SQL，还是未来视图的 `SELECT` 主体。

如果缺少不影响表关系的值（如具体日期），使用命名清楚的绑定变量，例如 `:start_time`、`:end_time`，不要反复询问。若缺少的信息会改变主表、粒度或关联键，则先列出缺口，不能猜测。

### 2. 定位真实资产

优先使用仓库本地资产：

- 在 `08_数据中心元数据快照.json` 核对 Owner、表/视图、字段、类型和视图 DDL；
- 在 `数据资产_资产包/tables.csv` 和 `columns.csv` 搜索业务表和字段；
- 在 `数据资产_资产包/relationships.csv` 核对正式关系和验证等级；
- 在 `03_view_registry.json`、`数据资产_关系图谱/ods_view_dependencies.csv` 和 `ods_view_join_edges.csv` 查已有视图依赖；
- 在 `09`、`10`、`12`、`14`、`15` 等报告中读取关系证据与限制。

如果能访问平台，可先调用：

- `GET /api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=30`
- `POST /api/v1/ai/export-context`
- `GET /api/v1/recipes/ai/context`

平台返回与仓库快照时间不同时，明确记录使用的证据日期或版本。不得根据中文表名、同名字段或记忆虚构不存在的表和字段。

### 3. 确定粒度和关系

先写一句“结果每行代表什么”，再选择主表。JOIN 使用优先级：

1. A/A+ 活库验证关系；
2. 已按治理口径采纳的 B/C 关系，并带上限定条件；
3. 已生效关系配方；
4. 可明确解析的现有视图 JOIN；
5. 仅同名字段推测的关系只能列为候选，不能进入正式 SQL。

组合键必须完整使用，例如住院关系使用 `PATIENT_ID + VISIT_ID`，不能只连接其中一列。先判断一对一、一对多、多对多；对字典或明细 JOIN 可能放大行数时，先去重或聚合，并解释规则。

### 4. 生成 Oracle 11g SQL

- 只允许一条 `SELECT`，可以使用只读 CTE；不要输出 `CREATE VIEW`。
- 最终投影显式列字段，不使用 `SELECT *`。
- 表使用 `OWNER.OBJECT_NAME` 全限定名，别名稳定且有含义。
- 使用绑定变量，不把患者信息、口令、Token、IP 或凭据写入 SQL。
- Oracle 11g 不使用 `FETCH FIRST`；限量检查使用外层 `ROWNUM <= N`。
- 时间范围优先使用左闭右开：`col >= :start_time AND col < :end_time`。
- 不在索引列上无必要地包 `TO_CHAR`、`TRUNC` 或隐式类型转换。
- 大表必须先用业务键、时间条件或受限子查询缩小范围；返回行数上限不能替代源端过滤。
- 默认排除姓名、身份证、电话、地址等敏感明细；确需输出时给出脱敏表达式并标注风险。

### 5. 静态安全检查

交付前执行本技能脚本：

```powershell
python .agents/skills/ods-readonly-sql/scripts/validate_readonly_sql.py path/to/query.sql
```

检查不通过就修订。脚本仅做基础静态门禁，不能替代元数据核对、执行计划分析和人工复核。

若平台接口可用，可再调用 `/api/v1/ai/sql-risk-scan`；被阻断时不得绕过。除非用户明确要求且具备只读验证条件，否则到此停止，不执行 SQL。

### 6. 数据库连接与只读执行

用户明确要求连接或验证时，先读取 `references/connection-guide.md`，按当前运行位置选择连接方式：

- Windows 本机不能直连数据中心，使用既有 SSH 跳板配置；
- 生产应用容器位于内网，可使用平台登记的 `ods_8_216` 只读连接直连；
- 有平台 Token 时优先走 `/api/v1/ai` 的草稿、风险扫描和只读执行端点。

本技能提供受控执行器：

```powershell
cd F:\python\数据资产\backend
python ..\.agents\skills\ods-readonly-sql\scripts\run_ods_readonly.py --test-connection
```

限量执行：

```powershell
python ..\.agents\skills\ods-readonly-sql\scripts\run_ods_readonly.py `
  --sql-file D:\temp\ods_query.sql `
  --params-file D:\temp\ods_params.json `
  --max-rows 10000
```

普通查询最大返回 `10000` 行。需要文件导出时只能在服务器/容器内网 direct 模式执行，最多导出 `50000` 行：

```powershell
python ..\.agents\skills\ods-readonly-sql\scripts\run_ods_readonly.py `
  --sql-file D:\temp\ods_query.sql `
  --params-file D:\temp\ods_params.json `
  --export-file D:\exports\ods_result.csv `
  --export-format csv `
  --export-max-rows 50000
```

执行器只从环境变量或服务器只读凭据文件取认证信息，开启只读事务，限制超时和行数，并对常见敏感列脱敏。导出文件必须位于 Git 仓库外，输出目录须预先创建，文件权限尽量收紧为仅当前用户可读写。不得把密码作为命令行参数，也不得自行修改执行器解除门禁。提高返回上限不能替代业务键或时间范围过滤。

## 强制停止条件

出现以下任一情况，只交付“已确认信息 + 缺失清单 + 待确认问题”，不生成伪完整 SQL：

- 主表或目标粒度不明确；
- 字段未在当前元数据中找到；
- JOIN 只有同名猜测或 D 类待验证关系；
- 需求跨越不可直接互联的物理实例，却要求一条 SQL 完成；
- 无法为事实大表提供业务键或时间范围；
- 用户要求对业务源库写入、创建视图或修改对象。

对 DDL/DML 请求说明本技能只负责生成只读取数 SQL，不要改写成可执行写操作，也不要调用运维写通道。

## 交付格式

始终按以下结构输出：

```markdown
## 取数口径

- 业务目的：
- 结果粒度：每行代表……
- 目标系统：数据中心（DATA_CENTER）
- 数据库方言：Oracle 11g
- 使用 Owner/对象：
- 时间口径与过滤条件：

## 表关系依据

| 主表/关联表 | JOIN 键 | 基数 | 证据来源 | 验证等级 | 限制 |
|---|---|---|---|---|---|

## SQL

```sql
SELECT
    ...
FROM ...
WHERE ...;
```

## 参数

| 参数 | 类型 | 示例含义 | 是否必填 |
|---|---|---|---|

## 风险与待确认

- 无则写“无”；不确定关系必须明确列出，不能藏在 SQL 中。

## 自检

- 单条 SELECT/只读 CTE：是/否
- DDL/DML：无/有
- 表和字段已由当前元数据确认：是/否
- JOIN 均有证据：是/否
- 组合键完整：是/否/不涉及
- 大表已由业务键或时间范围限制：是/否/不涉及
- 敏感字段已排除或脱敏：是/否/不涉及
- 是否执行 SQL：否（默认）
```

如果自检任一关键项为“否”，将结果标记为“候选草稿，不可直接使用”。

## 常见请求的处理方式

- “写住院患者的诊断和医嘱 SQL”：以住院就诊为粒度，用完整 `PATIENT_ID + VISIT_ID`，医嘱一对多时明确是否保留明细或聚合。
- “查检验结果”：先限定 `TEST_NO` 集合，再关联 `HIS.LAB_RESULT`；禁止从结果大表无边界扫描。
- “查检查报告”：`HIS.EXAM_REPORT` 没有 `PATIENT_ID`，经 `EXAM_NO` 连接 `HIS.EXAM_MASTER`。
- “按性别/诊断国标码输出”：使用 `CDA.CDA_DICTIONARY`，先确认字典过滤后是否唯一，避免一对多放大。
- “把数据中心和独立业务库放在一条 SQL”：先核对是否存在真实 DBLINK 或同步 Owner；没有证据时拆成各物理源独立 SELECT，不虚构跨库能力。
