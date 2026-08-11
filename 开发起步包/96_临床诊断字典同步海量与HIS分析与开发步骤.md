> 类别：改造计划
>
> 状态：代码已落地（默认写通道关闭；待用户联调测试） | 优先级：P1 | 创建：2026-07-27 | 修订：2026-07-28
>
> 配套：`_archive/96_复核意见_字段缺失与SQL语法风险.md`、`96_诊断手术字典_示例导出与写入SQL.sql`
> 输入：
> - 诊断样本：`临床诊断字典与国家版本映射关系_图片提取.xlsx`
> - 诊断全量：`开发起步包/诊断与手术维护/山东省第二人民医院 临床诊断字典2026.06.04（全字段标识版）.xlsx`
> - 手术全量：`开发起步包/诊断与手术维护/山东省第二人民医院 临床手术操作字典2026.06.02（全字段标识版）.xlsx`
> 关联：字典中心 `asset_dict_medical_*`（5 表）、导入脚本 8 个 code_sets、`77` 海量资产包、HIS `COMM.DIAGNOSIS_DICT`(34 列)/`COMM.OPERATION_DICT`(22 列)
> 边界：分析与改造计划 + 示例 SQL；**未对业务源库执行写入**；业务库下发须用户另行授权。

# 诊断与手术字典同步海量与 HIS 改造计划

## 1. 目标

通过平台**字典中心**，将院内**临床诊断**与**临床手术**字典及国家版本映射，**逐条**同步到 HIS 源端与海量 EMR。

| 目标系统 | 连接标识（登记用） | 方言 |
|---|---|---|
| HIS 源端 Oracle | `HIS_SOURCE` / `his_source_10_10_10_15` | **Oracle 11g** |
| 海量 EMR Vastbase | `JHEMR_VASTBASE` / `jhemr_vastbase_10_10_8_177`，库 `jhemr` | **PostgreSQL 兼容** |

统一要求：主数据 → dry-run → 审批 → 逐条 apply；可审计、可续传；写通道须独立开关 + 写凭据 + 审批。

### 1.0 写操作硬限制（用户确认，开发强制执行）

| 规则 | 要求 | 禁止 |
|---|---|---|
| **只增不停改业务内容** | 目标库仅允许两类写操作：① **新增 INSERT**；② **停用**（单字段状态） | **禁止**对已存在字典行做名称/映射/等级等业务字段的 UPDATE/MERGE |
| **新增必须逐条** | 每次执行 **恰好 1 条** `INSERT ... VALUES (...单行...)` | 禁止 `INSERT SELECT` 多行、批量 VALUES 多行、脚本循环一次提交多码（应用层循环时也须 **一条 SQL / 一次 round-trip / 独立审计**） |
| **停用必须逐条** | 每次执行 **恰好 1 条** 单行停用，WHERE 必须定位到唯一业务键 | **禁止** `WHERE CODE IN (...)`、无精确键、按前缀/日期/批次批量 `UPDATE` 停用 |
| **停用是唯一允许的 UPDATE 形态** | HIS：`STOP_FLAG=1`；海量：`isstop=1`（仅改状态列 + 可选 last_update） | 禁止借停用夹带改名、改映射 |
| **已存在且未停用** | dry-run 记 `skip_exists`，**不覆盖** | 禁止“有则更新” |
| **灰码医保（诊断）** | 导入/下发时：海量 `jhemr.diagnosis_dict.ybhm = '灰码'`；**不写** `diagnosis_contrast_dict` | 禁止为灰码伪造医保对照行；无有效医保对照则**不做对照写入** |

#### 1.0.1 允许的 DML 白名单（形态）

```text
允许：
  INSERT INTO <白名单表> (...) VALUES (...);          -- 单行
  UPDATE <白名单表> SET STOP_FLAG=1 WHERE <唯一键>=:k; -- HIS 单行停用
  UPDATE <白名单表> SET isstop=1 WHERE <唯一键条件>;   -- 海量单行停用

禁止：
  UPDATE ... SET 业务字段=...
  UPDATE ... WHERE col IN (...多个...)
  UPDATE ... WHERE col LIKE ...
  MERGE / UPSERT / INSERT SELECT / 多行 VALUES
  DELETE / TRUNCATE / DDL
```

#### 1.0.2 唯一键（停用 WHERE 必须用）

| 目标 | 唯一键（探活可收紧，不得放宽） |
|---|---|
| HIS `COMM.DIAGNOSIS_DICT` | `DIAGNOSIS_CODE = :code`（若活库同码多名称，则 `CODE + NAME`） |
| HIS `COMM.OPERATION_DICT` | `OPERATION_CODE = :code`（同上） |
| 海量 `diagnosis_dict` / `operation_dict` / `operation_dict_code` | `operation_code/diagnosis_code + hospital_no`（及 name 若需要） |
| 海量对照表 | 一般**仅新增**；停用策略默认不适用对照表（无 isstop 则不提供停用，或整行不删） |

#### 1.0.3 医保灰码（诊断）细则

| 平台侧判定 | 海量 `diagnosis_dict` | 海量 `diagnosis_contrast_dict` | HIS |
|---|---|---|---|
| 医保码/名为「灰码」或 `insurance_mapping_status=source_marker_not_mapping` | **INSERT 时** `ybhm='灰码'`（字段长度 10，足够） | **不 INSERT** 对照 | 默认**不写** `YB_CODE/YB_NAME`（仍为医保1.0 字段；与灰码无关） |
| 有效医保 2.0 对照 | `ybhm` 可空或按现网惯例 | 可 **单行 INSERT** 对照 | 业务确认后才写 YB（默认仍不写 1.0 列） |
| 无对照（空） | 不写对照；`ybhm` 空或不写灰码 | 不写对照 | 不写 YB |

手术若出现同类灰码标记：对称处理——`operation_dict`/`operation_dict_code` 的 `ybhm`（若有）标灰码，**不写** `operation_contrast_dict`。

### 1.1 示例 SQL 阅读约定（P1-1）

| 标记 | 含义 |
|---|---|
| `[HIS/Oracle]` | 仅连 HIS；`ROWNUM`、`SYSDATE`、`OWNER.TABLE` |
| `[海量/Vastbase-PG]` | 仅连海量 `jhemr`；`LIMIT`、`CURRENT_TIMESTAMP`、小写 schema.table |
| `[平台/PostgreSQL]` | 仅连平台 `data_asset` |

**禁止**把两组 SQL 拼进同一会话或同一 JDBC 连接。

---

## 2. 总体数据流与目标表

```text
维护 Excel → 平台 asset_dict_medical_*
                → dry-run 只读对账 HIS / 海量 → sync_diffs
                → 审批 + 写开关
                → 逐条下发 HIS + 海量
```

| 业务 | 角色 | HIS | 海量 jhemr |
|---|---|---|---|
| 诊断 | 临床+映射宽表 | `COMM.DIAGNOSIS_DICT`（**34 列**） | `diagnosis_dict` / `jhdict_icd_vs_clinic` / `diagnosis_contrast_dict` |
| 手术 | 临床字典 | `COMM.OPERATION_DICT`（**22 列**） | **`operation_dict`**（26 列） |
| 手术 | 标准编目 | 无独立表 → `OPERATION_CODE_GB/NAME_GB` | **`operation_dict_code`**（27 列） |
| 手术 | 医保对照 | 无独立表 → `YB_CODE/YB_NAME`（医保2.0） | **`operation_contrast_dict`**（5 列） |
| 手术 | 临床↔码映射（可选） | — | `jhdict_operation_vs_clinic`（10 列） |

HIS 源端元数据中**不存在** `OPERATION_DICT_CODE` / `OPERATION_CONTRAST_DICT` 物理表。

---

## 3. 诊断

### 3.1 Excel 与平台 code_set

| 来源 | 说明 |
|---|---|
| 样本 | 图片提取 xlsx，约 35 条院内扩展 |
| 全量 | 临床诊断字典 2026.06.04 |
| code_set | `diagnosis_local_clinical` / `diagnosis_national_clinical_v2` / `diagnosis_insurance_v2`（另有病理、外部原因等，本下发主线以门诊出入院诊断为准） |

表名校正：`jdiagnosis_dict`→`jhemr.diagnosis_dict`；`jdiagnosis_contrast_dict`→`jhemr.diagnosis_contrast_dict`。

### 3.2 HIS `COMM.DIAGNOSIS_DICT` 全 34 列与同步策略（P0-1 修订）

> 证据：`数据资产_HIS源端资产包/his_source_columns.csv`、`数据资产_资产包/columns.csv`（均为 34 列）。
> 若活库 `ALL_TAB_COLUMNS` 多于 34，阶段 0 必须升基线后再开发。

| # | 字段 | 类型 | 注释 | 同步策略 | 数据来源 |
|---:|---|---|---|---|---|
| 1 | DIAGNOSIS_CODE | VARCHAR2(50) | 诊断代码 | **必写** | 院内临床编码 |
| 2 | DIAGNOSIS_NAME | VARCHAR2(140) | 诊断名称 | **必写**；超长预检 | 院内临床名称 |
| 3 | STD_INDICATOR | NUMBER(1) | 正名 1/别名 0 | 默认 1 | 规则 |
| 4 | APPROVED_INDICATOR | NUMBER(1) | 标准化 | 默认 1 | 规则 |
| 5 | CREATE_DATE | DATE | 创建日期 | 新建=SYSDATE；更新**不覆盖** | 系统 |
| 6 | INPUT_CODE | VARCHAR2(50) | 输入码 | 可写 | 拼音生成 |
| 7 | HEALTH_LEVEL | CHAR(2) | — | **保留/空**；无 Excel 源则不覆盖已有 | — |
| 8 | INFECT_INDICATOR | VARCHAR2(2) | 传染相关 | 有传染病映射时写；否则**不覆盖** | 全量 Excel 传染病列 / CRB |
| 9 | INPUT_CODE_WB | VARCHAR2(8) | 五笔 | 可选 | 生成或空 |
| 10 | DISEASE_SORT | VARCHAR2(4) | — | **不覆盖**（无维护源） | — |
| 11 | CONTAGIONCODE | VARCHAR2(20) | — | 有则写，否则不覆盖 | 业务/传染病扩展 |
| 12 | DIAG_INDICATOR | NUMBER(1) | 1西医2中医3病理4外伤 | 门诊出入院默认 **1**；病理表另议 | 规则 |
| 13 | NM1 | VARCHAR2(6) | 内码1 | **不覆盖** | — |
| 14 | NM2 | VARCHAR2(2) | 内码2 | **不覆盖** | — |
| 15 | DIAGNOSIS_FJ_CODE | VARCHAR2(16) | 附加码 | **不覆盖** | — |
| 16 | CREATE_USER | VARCHAR2(20) | 创建者 | 新建可写平台操作者；更新不覆盖 | 审计 |
| 17 | DIAGNOSIS_CODE2 | VARCHAR2(16) | M码 | **不覆盖**（病理/形态学另线） | — |
| 18 | FLAG | NUMBER(1) | 1非传染2传染3食源 | 由传染病字段推导；无则默认 1 或不覆盖 | 规则 |
| 19 | YB_CODE | VARCHAR2(100) | **医保1.0**编码 | **默认不写 2.0**；待业务确认 | 确认后才映射 |
| 20 | YB_NAME | VARCHAR2(150) | **医保1.0**名称 | 同上 | 确认后才映射 |
| 21 | MTB_FLAG | VARCHAR2(10) | **门诊慢特病** 0/1 | **全量 Excel 有则写** | `门诊慢特病编码` 非空→1 |
| 22 | MTB_NAME | VARCHAR2(50) | 慢特病名称 | 全量有则写 | Excel 慢特病名称 |
| 23 | MTB_CODE | VARCHAR2(50) | 慢特病编码 | 全量有则写 | Excel 慢特病编码 |
| 24 | STOP_FLAG | NUMBER(1) | 停用 | 启用=0 | 规则 |
| 25 | DIAGNOSIS_CODE_GUO | VARCHAR2(100) | 国家临床版2.0 | **必写映射** | national_code |
| 26 | DIAGNOSIS_NAME_GUO | VARCHAR2(200) | 国家临床版2.0 | **必写映射** | national_name |
| 27 | DIAGNOSIS_CODE_MB | VARCHAR2(100) | 门诊慢特病病种映射 | 与 MTB 对齐时可同写 | Excel 慢特病 |
| 28 | DIAGNOSIS_NAME_MB | VARCHAR2(200) | 同上 | 同上 | Excel |
| 29 | DIAGNOSIS_CODE_ICD | VARCHAR2(100) | ICD低风险病种 | 全量有则写 | Excel 低风险类目 |
| 30 | DIAGNOSIS_NAME_ICD | VARCHAR2(200) | ICD低风险名称 | 全量有则写 | Excel |
| 31 | DIAGNOSIS_CODE_CRB | VARCHAR2(100) | 传染病诊断 | 全量有则写 | Excel 传染病 |
| 32 | DIAGNOSIS_NAME_CRB | VARCHAR2(200) | 传染病诊断 | 全量有则写 | Excel |
| 33 | DIAGNOSIS_TYPE | VARCHAR2(40) | 字典属性 | 写 | 院内扩展等 |
| 34 | MENTAL_ILLNESS | VARCHAR2(1) | 精神疾病标识 | **无 Excel 列则不覆盖**；待业务确认来源 | 业务 |

**策略标签说明**：

- **必写**：下发成功的必要条件。
- **全量 Excel 有则写**：图片提取样本可能无这些列；全量维护表 `import_medical_maintenance_dicts` 的 `extra` 已解析慢特病/低风险/传染病。
- **不覆盖**：UPDATE 时禁止用 NULL 抹掉现网值。
- **默认不写**：医保 1.0 列在未确认前不得用医保 2.0 覆盖。

### 3.3 海量诊断表（摘要）

| 表 | 列数 | 写入（受 §1.0 约束：只增 / 单条停用） |
|---|---:|---|
| `jhdict_icd_vs_clinic` | 10 | **仅不存在时 INSERT**；`serial_no` 程序预取 |
| `diagnosis_dict` | 35 | **仅不存在时 INSERT**；含 `ybhm`：有效医保可空，**灰码则 `ybhm='灰码'`** |
| `diagnosis_contrast_dict` | 5 | **仅有效医保 2.0 时单行 INSERT**；灰码或无对照 → **不写** |

---

## 4. 手术

### 4.1 Excel 与平台

| 项 | 值 |
|---|---|
| 文件 | 临床手术操作字典 2026.06.02 |
| 约行数 | 14,657 |
| code_set | `operation_local_clinical` / `operation_national_clinical_v3` / `operation_insurance_v2` |
| 国临版本 | **3.0**（诊断为 2.0，勿混） |

### 4.2 三表落点

| 用户称谓 | 海量 | HIS |
|---|---|---|
| 临床手术字典 `operation_dict` | `jhemr.operation_dict` | `COMM.OPERATION_DICT` |
| 标准编目 `operation_dict_code` | `jhemr.operation_dict_code` | → `OPERATION_CODE_GB/NAME_GB` |
| 医保对照 `operation_contrast_dict` | `jhemr.operation_contrast_dict` | → `YB_CODE/YB_NAME`（注释医保**2.0**） |

### 4.3 HIS `COMM.OPERATION_DICT` 22 列策略

| # | 字段 | len | 策略 |
|---:|---|---:|---|
| 1 | OPERATION_CODE | **16**（源端元数据） | 必写；阶段 0 活库再测 max 实际长 |
| 2 | OPERATION_NAME | 100 | 必写 |
| 3 | OPERATION_SCALE | 5 | 院内等级 |
| 4–5 | STD/APPROVED_INDICATOR | | 默认 1 |
| 6 | CREATE_DATE | | 新建 SYSDATE；更新不覆盖 |
| 7–8 | INPUT_CODE / WB | | 可选 |
| 9–10 | NM2 / CREATE_USER | | 不覆盖 / 新建可写 |
| 11 | OPERATION_INDICATOR | 2 | 0手术1治疗2诊断3介入（**映射表见阶段 0 交付**） |
| 12 | CLINIC_ITEM_CODE | | 不覆盖 |
| 13 | OPERATION_STATUS | | 微创时可 1 |
| 14–15 | YB_CODE / YB_NAME | | 医保 2.0 **可写**（与诊断 YB 不同） |
| 16 | STOP_FLAG | | 0 启用 |
| 17–18 | OPERATION_CODE_GB / NAME_GB | 16/100 | 国临 3.0 |
| 19–21 | FOUR/MIN/LIMIT_STATUS | | 绩效四级/微创/限制 |
| 22 | OPERATION_TYPE | 40 | 字典属性 |

### 4.4 海量手术三表

| 表 | 列数 | 默认写入 |
|---|---:|---|
| `operation_dict` | 26 | 院内临床；`boh_operation_code`=国临 3.0；`sjjxssbs/wcssbs/xzlbs` |
| `operation_dict_code` | 27 | 国临 3.0 去重；`is_catalog=1` |
| `operation_contrast_dict` | 5 | 院内↔医保 2.0 |
| `jhdict_operation_vs_clinic` | 10 | 可选，与诊断对称 |

`operation_type`（numeric）中文类别映射：**阶段 0 强制交付**，未交付不得进入阶段 3。

---

## 5. 字典中心现状与差距（P2-1 已核实）

| 能力 | 现状 | 改造 |
|---|---|---|
| 5 表 + 8 code_sets | 已有 | 增量批次导入 |
| mapping-rows API | 诊断/手术只读 | 待同步筛选 |
| `collect_medical_code_diffs` | 诊断→**CDA.CDA_DICTIONARY**；手术→**SM.MED_OPERATION_NAME**；只写平台 diffs | **禁止**当作 HIS/海量下发；新建 push planner 对账真实目标表 |
| sync/run | 不下发业务库 | push executor + 白名单 |

---

## 6. 实施阶段

### 阶段 0：只读探活（**强制交付，P1-3**）— 未完成不得进阶段 3

| 交付物 ID | 内容 | 通过标准 |
|---|---|---|
| D0-1 | 海量 `hospital_no` 分布 | 确定本院写入值 |
| D0-2 | HIS `DIAGNOSIS_DICT` 活库列清单 | 列数与 34 比对；若 36 则升基线 |
| D0-3 | HIS/海量长度实测 | `MAX(LENGTH(OPERATION_CODE))` 等；确认 16 是否硬限制 |
| D0-4 | 手术 `operation_type` / `OPERATION_INDICATOR` 样例映射表 | 四类中文→码 全覆盖 |
| D0-5 | `sjjxssbs/wcssbs/xzlbs` 与 `classify` 现网取值 | 枚举表 |
| D0-6 | 样本存在性 | 诊断 `I63.0011`；手术 `00.7000x001L` |
| D0-7 | 幂等键结论 | code 唯一 or code+name+hospital |
| D0-8 | 诊断路径 A/B 业务确认记录 | 书面确认 |

**门禁**：D0-4 映射表为空 → **阻断阶段 3 编码**。

### 阶段 1：平台主数据

1. 诊断/手术 Excel → `asset_dict_medical_*`
2. 长度预检：**优先** his_source_columns / 阶段 0 活库结果；**禁止**仅依赖平台 `asset_columns.length IS NULL`（P1-2）
3. 诊断全量字段：慢特病/低风险/传染病写入 item.extra，供 HIS 34 列策略使用

### 阶段 2：差异引擎（只读）

| category | 对账目标 |
|---|---|
| diagnosis | HIS DIAGNOSIS_DICT（关注必写+MTB/CRB/ICD/GUO）；海量三表 |
| operation | HIS OPERATION_DICT；海量 operation_dict / _code / contrast（+可选 vs_clinic） |

### 阶段 3：下发执行器（需授权 + D0 齐套 + §1.0 硬限制）

- `category`：diagnosis / operation / all
- `targets`：HIS_SOURCE / JHEMR_VASTBASE / all
- `mode`：dry_run / apply
- **动作类型仅两种**：`insert` | `stop`（无 `update_fields`）
- 每次 API/任务步只处理 **1 个业务码 × 1 个目标表 × 1 条 DML**
- 门禁扫描：拒绝多行 VALUES、`IN` 列表、`INSERT SELECT`、业务列 UPDATE
- 灰码：诊断 INSERT 海量 `diagnosis_dict` 时写 `ybhm='灰码'`，跳过 contrast
- 白名单见 §6.1；开关 `APP_DICT_MEDICAL_PUSH_ENABLED`

### 阶段 4：前端同步面板

- 诊断/手术共用；dry-run 预览「将新增 / 将跳过(已存在) / 将停用(显式勾选)」
- **停用须用户点选单条**，不得“全选停用”
- 新增执行进度：一条成功后再下一条

### 阶段 5：验收与回滚（P2-3 修订 + 只增停用）

| 行类型 | 回滚 |
|---|---|
| **错误新增** | 对该码执行 **单条停用**（§1.0）；不物理删除非二次审批 |
| **错误停用** | 单条恢复启用（`STOP_FLAG=0`/`isstop=0`）视为**高风险例外操作**，须单独审批开关，不在常规同步入口 |
| 禁止 | 批量 DELETE；批量改业务字段；无审批批量恢复 |

验收：诊断 35 条样本 dry-run；灰码样本 `ybhm=灰码` 且 contrast 0 行；单条 INSERT/单条 STOP 门禁用例；拒绝批量 UPDATE 的负向测试。

### 6.1 写表白名单

**HIS**：`COMM.DIAGNOSIS_DICT`、`COMM.OPERATION_DICT`
**海量**：`diagnosis_dict`、`jhdict_icd_vs_clinic`、`diagnosis_contrast_dict`、`operation_dict`、`operation_dict_code`、`operation_contrast_dict`、可选 `jhdict_operation_vs_clinic`

---

## 7. 路径默认

| 类别 | 默认 |
|---|---|
| 诊断 | **待 D0-8 确认 A/B** |
| 手术 | **B 对称**：operation_dict=院内；operation_dict_code=国临 3.0 去重；contrast=医保 2.0；HIS 单表宽字段 |

---

## 8. 示例 SQL（均已标注连接目标）

### 8.1 [HIS/Oracle] 诊断探查

```sql
-- 连接：HIS_SOURCE / Oracle 11g / COMM
SELECT DIAGNOSIS_CODE, DIAGNOSIS_NAME, STOP_FLAG,
       DIAGNOSIS_CODE_GUO, DIAGNOSIS_NAME_GUO,
       YB_CODE, YB_NAME, MTB_FLAG, MTB_CODE, MTB_NAME,
       DIAGNOSIS_CODE_ICD, DIAGNOSIS_CODE_CRB, MENTAL_ILLNESS,
       DIAGNOSIS_TYPE, FLAG, INFECT_INDICATOR
FROM COMM.DIAGNOSIS_DICT
WHERE DIAGNOSIS_CODE = 'I63.0011'
  AND ROWNUM <= 10;
```

### 8.2 [HIS/Oracle] 手术探查与长度

```sql
-- 连接：HIS_SOURCE / Oracle 11g / COMM
SELECT OPERATION_CODE, OPERATION_NAME, OPERATION_SCALE, OPERATION_INDICATOR,
       OPERATION_CODE_GB, OPERATION_NAME_GB, YB_CODE, YB_NAME,
       FOUR_MERIT_STATUS, MIN_MERIT_STATUS, LIMIT_STATUS,
       STOP_FLAG, OPERATION_TYPE
FROM COMM.OPERATION_DICT
WHERE OPERATION_CODE IN ('00.7000x001L', '00.7000x001R', '00.7000x001')
  AND ROWNUM <= 20;

SELECT MAX(LENGTH(OPERATION_CODE)) AS max_code_len,
       MAX(LENGTH(OPERATION_NAME)) AS max_name_len,
       MAX(LENGTH(OPERATION_CODE_GB)) AS max_gb_len
FROM COMM.OPERATION_DICT
WHERE ROWNUM <= 100000;
```

### 8.3 [海量/Vastbase-PG] 手术探查

```sql
-- 连接：JHEMR_VASTBASE / Vastbase / database=jhemr
SELECT hospital_no, COUNT(*) AS cnt
FROM jhemr.operation_dict
GROUP BY hospital_no
ORDER BY cnt DESC
LIMIT 20;

SELECT operation_code, operation_name, operation_scale, hospital_no,
       isstop, iszdy, synchron, boh_operation_code, operation_type,
       sjjxssbs, wcssbs, xzlbs
FROM jhemr.operation_dict
WHERE operation_code IN ('00.7000x001L', '00.7000x001', '01.13001')
LIMIT 20;

-- 类别映射探活（D0-4）
SELECT operation_type, COUNT(*) AS cnt
FROM jhemr.operation_dict
GROUP BY operation_type
ORDER BY cnt DESC
LIMIT 20;

SELECT operation_code, operation_name, is_catalog, ybhm
FROM jhemr.operation_dict_code
WHERE operation_code IN ('00.7000x001', '01.1300')
LIMIT 20;

SELECT classify, operation_code, operation_name,
       operation_code_standard, operation_name_standard
FROM jhemr.operation_contrast_dict
WHERE operation_code IN ('00.7000x001L', '00.7000x001')
LIMIT 20;
```

### 8.4 [海量/Vastbase-PG] 诊断探查

```sql
-- 连接：JHEMR_VASTBASE / Vastbase / jhemr
SELECT hospital_no, COUNT(*) AS cnt
FROM jhemr.diagnosis_dict
GROUP BY hospital_no
ORDER BY cnt DESC
LIMIT 20;
```

### 8.5 [HIS/Oracle] 手术写入示例

```sql
-- 连接：HIS_SOURCE 写账号（非 readonly）/ Oracle
UPDATE COMM.OPERATION_DICT
SET OPERATION_NAME        = '左侧髋关节假体翻修术',
    OPERATION_SCALE       = '四',
    STD_INDICATOR         = 1,
    APPROVED_INDICATOR    = 1,
    STOP_FLAG             = 0,
    OPERATION_INDICATOR   = '0',
    OPERATION_CODE_GB     = '00.7000x001',
    OPERATION_NAME_GB     = '全髋关节假体翻修术',
    YB_CODE               = '00.7000x001',
    YB_NAME               = '全髋关节假体翻修术',
    FOUR_MERIT_STATUS     = 1,
    MIN_MERIT_STATUS      = 0,
    LIMIT_STATUS          = 0,
    OPERATION_TYPE        = '院内扩展'
WHERE OPERATION_CODE = '00.7000x001L';

INSERT INTO COMM.OPERATION_DICT (
    OPERATION_CODE, OPERATION_NAME, OPERATION_SCALE,
    STD_INDICATOR, APPROVED_INDICATOR, CREATE_DATE, INPUT_CODE,
    OPERATION_INDICATOR, YB_CODE, YB_NAME, STOP_FLAG,
    OPERATION_CODE_GB, OPERATION_NAME_GB,
    FOUR_MERIT_STATUS, MIN_MERIT_STATUS, LIMIT_STATUS, OPERATION_TYPE
) VALUES (
    '00.7000x001L', '左侧髋关节假体翻修术', '四',
    1, 1, SYSDATE, 'ZCCHGJZTFS',
    '0', '00.7000x001', '全髋关节假体翻修术', 0,
    '00.7000x001', '全髋关节假体翻修术',
    1, 0, 0, '院内扩展'
);
```

### 8.6 [海量/Vastbase-PG] `operation_dict`

```sql
-- 连接：JHEMR_VASTBASE 写账号 / jhemr
-- operation_type 数值以 D0-4 映射表为准，下例 0=手术 为占位
INSERT INTO jhemr.operation_dict (
    operation_code, operation_name, operation_scale,
    std_indicator, approved_indicator, create_date, input_code,
    synchron, operation_type, isstop, iszdy, hospital_no, pym,
    is_catalog, boh_operation_code, sjjxssbs, wcssbs, xzlbs
) VALUES (
    '00.7000x001L', '左侧髋关节假体翻修术', '四',
    1, 1, CURRENT_TIMESTAMP, 'zcchgjztfs',
    1, 0, 0, 1, :hospital_no, 'zcchgjztfs',
    0, '00.7000x001', '1', NULL, NULL
);
```

### 8.7 [海量/Vastbase-PG] `operation_dict_code`

```sql
INSERT INTO jhemr.operation_dict_code (
    operation_code, operation_name, operation_scale,
    std_indicator, approved_indicator, create_date, input_code,
    synchron, isstop, iszdy, hospital_no, pym, is_catalog, boh_operation_code
) VALUES (
    '00.7000x001', '全髋关节假体翻修术', '四',
    1, 1, CURRENT_TIMESTAMP, 'qhgjztfs',
    1, 0, 0, :hospital_no, 'qhgjztfs', 1, '00.7000x001'
);
```

### 8.8 [海量/Vastbase-PG] `operation_contrast_dict`

```sql
INSERT INTO jhemr.operation_contrast_dict (
    classify, operation_name, operation_code,
    operation_name_standard, operation_code_standard
) VALUES (
    '医保2.0', '左侧髋关节假体翻修术', '00.7000x001L',
    '全髋关节假体翻修术', '00.7000x001'
);
```

### 8.9 [HIS/Oracle] 诊断写入（含关键扩展字段示例）

```sql
-- 连接：HIS_SOURCE 写账号 / Oracle
-- 全量 Excel 含慢特病/传染病/低风险时写入对应列；样本仅有 GUO 时其余列不覆盖
UPDATE COMM.DIAGNOSIS_DICT
SET DIAGNOSIS_NAME       = '基底动脉血栓形成的急性脑梗死',
    DIAGNOSIS_CODE_GUO   = 'I63.001',
    DIAGNOSIS_NAME_GUO   = '基底动脉血栓形成脑梗死',
    DIAGNOSIS_TYPE        = '院内扩展',
    STD_INDICATOR        = 1,
    APPROVED_INDICATOR   = 1,
    STOP_FLAG            = 0,
    DIAG_INDICATOR       = 1,
    MTB_FLAG             = NVL(:mtb_flag, MTB_FLAG),
    MTB_CODE             = NVL(:mtb_code, MTB_CODE),
    MTB_NAME             = NVL(:mtb_name, MTB_NAME),
    DIAGNOSIS_CODE_MB    = NVL(:mtb_code, DIAGNOSIS_CODE_MB),
    DIAGNOSIS_NAME_MB    = NVL(:mtb_name, DIAGNOSIS_NAME_MB),
    DIAGNOSIS_CODE_ICD   = NVL(:icd_lr_code, DIAGNOSIS_CODE_ICD),
    DIAGNOSIS_NAME_ICD   = NVL(:icd_lr_name, DIAGNOSIS_NAME_ICD),
    DIAGNOSIS_CODE_CRB   = NVL(:crb_code, DIAGNOSIS_CODE_CRB),
    DIAGNOSIS_NAME_CRB   = NVL(:crb_name, DIAGNOSIS_NAME_CRB)
    -- YB_CODE/YB_NAME：医保1.0，默认不更新
WHERE DIAGNOSIS_CODE = 'I63.0011';

INSERT INTO COMM.DIAGNOSIS_DICT (
    DIAGNOSIS_CODE, DIAGNOSIS_NAME,
    STD_INDICATOR, APPROVED_INDICATOR, CREATE_DATE, DIAG_INDICATOR, STOP_FLAG,
    DIAGNOSIS_CODE_GUO, DIAGNOSIS_NAME_GUO, DIAGNOSIS_TYPE,
    MTB_FLAG, MTB_CODE, MTB_NAME,
    DIAGNOSIS_CODE_MB, DIAGNOSIS_NAME_MB,
    DIAGNOSIS_CODE_ICD, DIAGNOSIS_NAME_ICD,
    DIAGNOSIS_CODE_CRB, DIAGNOSIS_NAME_CRB, FLAG
) VALUES (
    'I63.0011', '基底动脉血栓形成的急性脑梗死',
    1, 1, SYSDATE, 1, 0,
    'I63.001', '基底动脉血栓形成脑梗死', '院内扩展',
    :mtb_flag, :mtb_code, :mtb_name,
    :mtb_code, :mtb_name,
    :icd_lr_code, :icd_lr_name,
    :crb_code, :crb_name, :flag
);
```

### 8.10 [平台/PostgreSQL] 手术宽表

```sql
-- 连接：平台 data_asset / PostgreSQL
SELECT
    i.item_code AS local_code,
    i.item_name_cn AS local_name,
    i.extra->>'operation_level' AS operation_level,
    i.extra->>'operation_category' AS operation_category,
    mn.to_item_code AS national_code,
    mi.to_item_code AS insurance_code
FROM asset.asset_dict_medical_code_items i
LEFT JOIN asset.asset_dict_medical_code_mappings mn
  ON mn.from_code_set = 'operation_local_clinical'
 AND mn.from_item_code = i.item_code
 AND mn.to_code_set = 'operation_national_clinical_v3'
LEFT JOIN asset.asset_dict_medical_code_mappings mi
  ON mi.from_code_set = 'operation_local_clinical'
 AND mi.from_item_code = i.item_code
 AND mi.to_code_set = 'operation_insurance_v2'
WHERE i.code_set_code = 'operation_local_clinical'
  AND i.item_code = '00.7000x001L';
```

### 8.11 [平台/PostgreSQL] 诊断宽表（含 extra 扩展）

```sql
SELECT
    i.item_code AS local_code,
    i.item_name_cn AS local_name,
    i.extra->>'dict_attribute' AS dict_attribute,
    i.extra->>'special_disease_code' AS mtb_code,
    i.extra->>'special_disease_name' AS mtb_name,
    i.extra->>'low_risk_category_code' AS icd_lr_code,
    i.extra->>'low_risk_disease_name' AS icd_lr_name,
    i.extra->>'infectious_disease_name' AS crb_name,
    mn.to_item_code AS national_code,
    mi.to_item_code AS insurance_code,
    i.extra->>'insurance_mapping_status' AS insurance_mapping_status
FROM asset.asset_dict_medical_code_items i
LEFT JOIN asset.asset_dict_medical_code_mappings mn
  ON mn.from_code_set = 'diagnosis_local_clinical'
 AND mn.from_item_code = i.item_code
 AND mn.to_code_set = 'diagnosis_national_clinical_v2'
LEFT JOIN asset.asset_dict_medical_code_mappings mi
  ON mi.from_code_set = 'diagnosis_local_clinical'
 AND mi.from_item_code = i.item_code
 AND mi.to_code_set = 'diagnosis_insurance_v2'
WHERE i.code_set_code = 'diagnosis_local_clinical'
  AND i.item_code = 'I63.0011';
```

---

## 9. 待确认问题（分级，P2-2）

### P0（阻断 apply）

| ID | 问题 |
|---|---|
| Q-P0-1 | 是否授权业务库写通道与写账号 |
| Q-P0-2 | 诊断路径 A 还是 B |
| Q-P0-3 | 活库 DIAGNOSIS_DICT 列数是否仍为 34 |

### P1（阻断完整字段同步）

| ID | 问题 |
|---|---|
| Q-P1-1 | 诊断 HIS `YB_*`（医保1.0）是否允许被医保2.0覆盖 |
| Q-P1-2 | `MENTAL_ILLNESS` 数据来源 |
| Q-P1-3 | `hospital_no` 本院值 |
| Q-P1-4 | 手术 contrast 左侧用院内码还是国临码 |
| Q-P1-5 | 是否下发 `jhdict_operation_vs_clinic` |

### P2（可默认策略）

| ID | 问题 | 默认 |
|---|---|---|
| Q-P2-1 | 同 code 不同 name | **跳过不改**（只增原则）；记 `skip_conflict` |
| Q-P2-2 | 全量新增节奏 | 应用层逐条串行；可限速，**不得**合并为一条 SQL |
| Q-P2-3 | 错误新增回滚 | **单条停用**；物理删二次审批 |
| Q-P2-4 | 灰码字符串 | 精确匹配 `灰码`（trim 后） |

---

## 10. 结论

1. 诊断+手术统一流水线与手术三表落点设计保持不变。
2. **写操作硬限制（2026-07-28）**：**只允许单行新增 + 单行停用**；禁止改已有业务字段；禁止批量 UPDATE。
3. **灰码**：海量 `diagnosis_dict.ybhm='灰码'`，无对照则不写 `diagnosis_contrast_dict`。
4. DIAGNOSIS_DICT **34 列**策略、SQL 分库标注、阶段 0 强制交付仍有效。
5. **未写业务库**；开发前门禁 = 用户确认 Q-P0 + 阶段 0 + §1.0 门禁测试通过。
6. 示例导出/写入 SQL 见 `96_诊断手术字典_示例导出与写入SQL.sql`（**仅供复核，默认不执行写语句**）。

---

## 11. 相关索引

| 类型 | 路径 |
|---|---|
| 本计划 | `96_临床诊断字典同步海量与HIS分析与开发步骤.md` |
| 复核意见（已回写归档） | `_archive/96_复核意见_字段缺失与SQL语法风险.md` |
| **示例导出/写入 SQL** | **`96_诊断手术字典_示例导出与写入SQL.sql`** |
| 维护 Excel | `开发起步包/诊断与手术维护/` |
| HIS 列 | `数据资产_HIS源端资产包/his_source_columns.csv` |
| 海量列 | `数据资产_JHEMR_Vastbase资产包/columns.csv` |
| 导入/模型 | `import_medical_maintenance_dicts.py`、`dict_medical.py` |
| collector（非下发） | `medical_code_source_collector.py` |
