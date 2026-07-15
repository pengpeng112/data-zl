> 类别：证据链
> 状态：已完成
> 数据安全：源业务库只读，DML/DDL 为 0

# 移动护理 Oracle 活库探查与表关系分析报告

## 1. 范围与结论

本次对移动护理 Oracle 数据库进行只读探查，并结合 `系统表结构/移动护理数据库文档.md` 复核表结构和关系。凭据仅用于受控连接，没有写入代码、报告、日志或 Git。

活库权威范围：

| 项目 | 结果 |
|---|---:|
| 数据库 | `ewell` |
| Owner | `LUNA_MCS_SDSEY` |
| 表 | 508 |
| 视图 | 59（57 VALID、2 INVALID） |
| 字段 | 9,981 |
| 主键 | 368 |
| 唯一约束 | 4 |
| 声明外键 | 0 |
| 索引字段记录 | 930 |
| 源库写操作 | 0 |

该库没有声明外键，关系必须综合主键、视图 SQL、命名模式和限量数据命中率确认。文档只覆盖 113 张表，其中 73 张仍在活库，40 张已不存在，活库另有 435 张表未被旧文档覆盖。因此后续资产治理必须以 86 号活库快照为准，旧文档只用于中文含义参考。

## 2. 业务结构分类

| 主题 | 主要对象 | 说明 |
|---|---|---|
| 患者住院底座 | `INPATIENTS`、`MCS_HIS_PATIENT` | `INPATIENTS.PAT_INDEX_NO` 是当前护理事实稳定患者键；旧 HIS 镜像需降级 |
| 护理文书 | `MCS_DOC_FORM`、`MCS_DOC_FORM_RECORDS`、`MCS_DOC_TEMPLATE` | 表单主表、字段值明细、模板定义 |
| 体征与事件 | `MCS_VITAL_INFO`、`MCS_EVENT_INFO` | 体温、脉搏、出入量、护理事件等高频事实 |
| 护理评估 | `MCS_ASSESS_FORM*`、`MCS_DIABETES_ASSESS*` | 评估主表和扩展明细 |
| PICC | `MCS_PICC_*` | 置管、维护、并发症、拔管、输液工具评估 |
| 伤口与造口 | `MCS_WOUND_*`、`MCS_STOMA_*` | 登记、评估及扩展明细 |
| 交班报告 | `MCS_WARDREPORT_*`、`MCS_DAILY_SETTLE_*` | 班次、报告、患者明细、签名和统计 |
| 权限与病区配置 | `MCS_SYS_*` | 用户、病区和配置；旧文档中部分角色权限表已经消失 |
| 接口与标准视图 | `V_EMR_*`、`V_ESBHL_*`、`T_ITF_HL` | 把护理业务表转换为标准接口口径，是关系证据的重要来源 |

## 3. 数据规模与查询红线

以下为统计信息中的大表，不能全表扫描：

| 表 | 统计行数 |
|---|---:|
| `MCS_DOC_FORM_RECORDS` | 203,879,598 |
| `MCS_ASSESS_FORM_RECORD` | 41,898,062 |
| `MCS_ORDER_SCHEDULE_PROCESS` | 38,957,839 |
| `MCS_ORDER_SCHEDULE` | 37,010,970 |
| `MCS_PATROL_INFO` | 36,855,037 |
| `MCS_DOC_FORM_OPERATION_LOG` | 32,895,869 |
| `MCS_VITAL_INFO` | 16,182,306 |
| `MCS_DOC_FORM` | 12,015,722 |

本次验证对每条关系最多选择 10,000 个非空子表键，并设置只读事务和超时。后续查询上述表必须先按患者、表单、时间或 `ROWNUM` 限定。

## 4. 已确认的核心关系

### 4.1 患者、文书与体征主线

| 子表.字段 | 父表.字段 | 样本 | 命中率 | 结论 |
|---|---|---:|---:|---|
| `MCS_DOC_FORM.PATIENT_UID` | `INPATIENTS.PAT_INDEX_NO` | 10,000 | 100% | 正式关系 |
| `MCS_DOC_FORM_RECORDS.FORM_ID` | `MCS_DOC_FORM.ID` | 10,000 | 100% | 正式主从关系 |
| `MCS_DOC_FORM.TEMPLATE_CODE` | `MCS_DOC_TEMPLATE.CODE` | 10,000 | 100% | 正式模板关系 |
| `MCS_VITAL_INFO.PATIENT_UID` | `INPATIENTS.PAT_INDEX_NO` | 10,000 | 100% | 正式患者体征关系 |
| `MCS_DOC_FORM_RECORDS.PATIENT_UID` | `INPATIENTS.PAT_INDEX_NO` | 10,000 | 100% | 正式患者文书明细关系 |
| `MCS_EVENT_INFO.PATIENT_UID` | `INPATIENTS.PAT_INDEX_NO` | 10,000 | 100% | 正式患者事件关系 |

推荐的护理主链为：

```text
INPATIENTS.PAT_INDEX_NO
  ├─ MCS_DOC_FORM.PATIENT_UID
  │    ├─ MCS_DOC_FORM_RECORDS.FORM_ID → MCS_DOC_FORM.ID
  │    └─ MCS_DOC_FORM.TEMPLATE_CODE → MCS_DOC_TEMPLATE.CODE
  ├─ MCS_VITAL_INFO.PATIENT_UID
  └─ MCS_EVENT_INFO.PATIENT_UID
```

`MRN + SERIES` 可作为业务展示和跨系统核对键，但在本库内部优先使用 `PATIENT_UID/PAT_INDEX_NO`，不要仅凭姓名、床号或住院号单字段关联。

### 4.2 专科护理主从关系

以下视图 SQL 明确给出 JOIN，且限量非空键样本 100% 命中：

- `MCS_DIABETES_ASSESS_S.XFORM_SOURCE_ID → MCS_DIABETES_ASSESS.ID`
- `MCS_PICC_CATHETERIZATION_S.XFORM_SOURCE_ID → MCS_PICC_CATHETERIZATION.ID`
- `MCS_PICC_COMPLICATION_S.XFORM_SOURCE_ID → MCS_PICC_COMPLICATION.ID`
- `MCS_PICC_COMPLICATION.MAINTENANCE_ID → MCS_PICC_MAINTENANCE_RECORD.ID`
- `MCS_PICC_MAINTENANCE_RECORD.PICC_ID → MCS_PICC_CATHETERIZATION.PICC_ID`
- `MCS_PICC_ASSESSMENT_S_PICC.XFORM_SOURCE_ID → MCS_PICC_ASSESSMENT.ID`
- `MCS_PICC_DROP_TUBE_S.XFORM_SOURCE_ID → MCS_PICC_DROP_TUBE.ID`
- `MCS_STOMA_REGISTER_S.XFORM_SOURCE_ID → MCS_STOMA_REGISTER.ID`

`XFORM_SOURCE_ID → 主表.ID` 是该系统扩展明细表的稳定建模模式，可用于继续扩展 CVC、输液港、静脉留置针等子表，但新增关系仍需逐表验证。

## 5. 部分关系和禁止提升项

| 关系 | 样本/命中 | 处置 |
|---|---:|---|
| `MCS_STOMA_ASSESS_S.XFORM_SOURCE_ID → MCS_STOMA_ASSESS.ID` | 6/4，66.67% | 保留 partial，调查历史/删除主表 |
| `MCS_WOUND_ASSESS_S.XFORM_SOURCE_ID → MCS_WOUND_ASSESS.ID` | 20/15，75% | 保留 partial，不能标 100% 强关系 |
| `MCS_EVENT_INFO.PATIENT_UID → MCS_HIS_PATIENT.PATIENT_UID` | 10,000/0 | 否决当前镜像关系，改挂 `INPATIENTS` |
| `MCS_HIS_PATIENT.PATIENT_UID → INPATIENTS.PAT_INDEX_NO` | 无非空样本 | `MCS_HIS_PATIENT` 当前不可作为权威患者底座 |
| 交班报告主从两条候选 | 当前无非空样本 | 结构候选，待有数据后复核 |

旧视图 `V_ESBHL_OUTPUT_ASS_GUIDE` 使用 `MCS_EVENT_INFO.PATIENT_UID = MCS_HIS_PATIENT.PATIENT_UID`，但当前样本完全不匹配；该视图逻辑应视为历史口径，不得据此导入正式关系。

## 6. 视图关系分析

59 个视图中解析出 41 条直接表依赖。重点证据包括：

- `T_ITF_HL`：`INPATIENTS.PAT_INDEX_NO = MCS_DOC_FORM.PATIENT_UID`，并使用 `MCS_DOC_FORM.TEMPLATE_CODE = MCS_DOC_TEMPLATE.CODE`。
- `PICC_V_Q_*`：编码了 PICC 置管、维护、并发症和拔管主从关系。
- `STOMA_V_Q_*`、`WOUND_V_Q_ASSESS`：编码造口和伤口主从关系，但活数据存在孤儿，必须标 partial。
- `V_EMR_*`：以 `INPATIENTS`、护理表单、体征和事件为源生成标准文档。
- `V_ESBHL_*`：部分仍使用历史患者镜像，不能不经数据验证直接采信。

两个会诊视图 `CONSULTATION_V_Q_RECORD`、`CONSULTATION_V_Q_RECORD_JUNIOR` 为 INVALID；其 SQL 引用的 `MCS_CONSULTATION_RECORD*` 旧对象在当前 Owner 下不存在。这两项只能归档为历史视图证据，不能进入在线图谱正式层。

## 7. 与旧文档的差异

- 文档表：113。
- 活库仍存在：73。
- 文档存在但活库缺失：40。
- 活库新增或文档未覆盖：435。

缺失对象主要集中在旧护理管理、权限角色、健康教育和手工执行模块，例如 `MCS_SYS_ROLES`、`MCS_SYS_RIGHTS`、`MCS_SYS_ROLE_RIGHTS`、`MCS_NM_SCHEDULE` 等。不得依据旧文档为这些表建立当前有效关系。

## 8. 系统归属建议

该来源的真实目标地址与数据中心 `10.10.8.216` 不同，应登记为独立物理连接：

```text
移动护理
  └─ 10.10.10.125:1521/ewell
      └─ LUNA_MCS_SDSEY
          ├─ TABLE
          └─ VIEW
```

在业务主题上它属于移动护理；在平台物理连接层不能与 8.216 内的历史 `YDHL` Owner 混为同一连接。后续需要以患者键验证两者是否为同步副本、历史迁移或不同产品实例。

## 9. 交付物

- `86_移动护理Oracle元数据快照.json`：508 表、59 视图、9,981 字段、约束、索引和视图 SQL。
- `86_移动护理Oracle关系验证结果.json`：20 条限量关系验证、41 条视图依赖、文档差异和安全记录。
- 本报告：业务分类、正式关系、partial/否决项和后续接入建议。

本轮未向平台资产库执行导入，也未改动移动护理源库。若后续导入平台，应先备份平台库，使用独立 source_code，dry-run 对账后再写平台库。
