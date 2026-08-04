# HIS_SOURCE 表结构与系统对接快速参考
## 1. 系统身份

- 平台一级系统编码：`HIS_SOURCE`；中文展示名：`HIS`。
- 历史源编码：`his_source_10_10_10_15`，只用于兼容旧记录。
- 数据库：Oracle 11g，多 Owner。
- `hisuser` 账号自身 Schema 主要是报表/中间表，不是业务主 Schema；查询核心业务表必须使用真实 Owner。
- 当前第一版资产范围：12 个 Owner、1234 张表、19831 个字段、33 条源端关系；以机器资产包的当前版本为准。

## 2. Owner 与主题

| Owner | 主题 | 典型对象 |
|---|---|---|
| `MEDREC` | 患者、住院、病案、诊断、手术 | `PAT_MASTER_INDEX`、`PAT_VISIT`、`DIAGNOSIS`、`OPERATION` |
| `INPADM` | 住院登记和在院管理 | `PATS_IN_HOSPITAL`、`ADT_LOG` |
| `OUTPADM` | 门诊挂号和就诊 | `CLINIC_MASTER` |
| `ORDADM` | 医嘱、费用和执行 | `ORDERS`、`ORDERS_COSTS`、`ORDERS_EXECUTE_DETAILS` |
| `LAB` | 检验申请、项目和结果 | `LAB_TEST_MASTER`、`LAB_TEST_ITEMS`、`LAB_RESULT` |
| `EXAM` | 检查申请、报告和计费 | `EXAM_MASTER`、`EXAM_REPORT`、`EXAM_BILL_ITEMS` |
| `INPBILL` | 住院结算、费用、预交金 | `INP_SETTLE_MASTER`、`INP_BILL_DETAIL`、`PREPAYMENT_RCPT` |
| `OUTPBILL` | 门诊收据和费用 | `OUTP_RCPT_MASTER`、`OUTP_BILL_ITEMS` |
| `DRUG_USER` | 新药库、住院发药和执行 | `PHA_INP_REQUEST_DRUG`、`PHA_INP_DISPDETAIL`、`INP_ORDER_EXECDATA` |
| `PHARMACY` | 旧处方和发药主线 | `DRUG_PRESC_DETAIL`、`DRUG_DISPENSE_REC` 等 |
| `COMM` | 通用字典、价表、组织人员 | `DEPT_DICT`、`STAFF_DICT`、`PRICE_LIST`、`DIAGNOSIS_DICT` |
| `MEDADM` | 医疗管理和床位快照 | `BEDPATS_IN_HOSPITAL`；`ST_*` 统计表不进主线 |

## 3. 关键表规模与主键

以下为历史 Oracle 统计信息，用于识别大表，不是实时精确行数：

| 对象 | 规模量级 | 主键/业务键 | 规则 |
|---|---:|---|---|
| `MEDREC.PAT_MASTER_INDEX` | 约190万 | `PATIENT_ID` | 患者主索引 |
| `MEDREC.PAT_VISIT` | 约57万 | `PATIENT_ID,VISIT_ID` | 住院主表 |
| `MEDREC.DIAGNOSIS` | 约330万 | `PATIENT_ID,VISIT_ID,DIAGNOSIS_TYPE,DIAGNOSIS_NO` | 一次就诊多诊断 |
| `ORDADM.ORDERS` | 约4100万 | 住院键+医嘱号 | 必须限定时间/住院键 |
| `LAB.LAB_TEST_MASTER` | 约910万 | `TEST_NO` | 非零 VISIT_ID 才可按住院强关联 |
| `LAB.LAB_RESULT` | 约9300万 | `TEST_NO,ITEM_NO,PRINT_ORDER` | 必须先限定 TEST_NO |
| `EXAM.EXAM_MASTER` | 约340万 | `EXAM_NO` | 住院与门诊子集分开 |
| `EXAM.EXAM_REPORT` | 约130万 | `EXAM_NO` | 经 EXAM_NO 关联主表 |
| `INPBILL.INP_BILL_DETAIL` | 约2.2亿 | 住院键、`RCPT_NO` | 禁止无边界查询 |
| `OUTPBILL.OUTP_BILL_ITEMS` | 约3000万 | `RCPT_NO` | 按收据/时间/患者限定 |

## 4. 正式或已验证关系

完整清单读取 `数据资产_HIS源端资产包/his_source_relationships.csv`。常用路径：

| From | To | 键 | 状态/限制 |
|---|---|---|---|
| `MEDREC.PAT_VISIT` | `MEDREC.PAT_MASTER_INDEX` | `PATIENT_ID` | full_pass |
| `MEDREC.DIAGNOSIS` | `MEDREC.PAT_VISIT` | `PATIENT_ID+VISIT_ID` | full_pass |
| `MEDREC.OPERATION` | `MEDREC.PAT_VISIT` | `PATIENT_ID+VISIT_ID` | `OPER_ID` 全空，禁用 |
| `ORDADM.ORDERS` | `MEDREC.PAT_VISIT` | `PATIENT_ID+VISIT_ID` | sample_pass |
| `ORDADM.ORDERS_COSTS` | `ORDADM.ORDERS` | 住院键+`ORDER_NO+ORDER_SUB_NO` | sample_pass |
| `ORDADM.ORDERS_EXECUTE_DETAILS` | `ORDADM.ORDERS` | 住院键+`ORDER_NO+ORDER_SUB_NO` | sample_pass |
| `DRUG_USER.INP_ORDER_EXECDATA` | `ORDADM.ORDERS` | 住院键+`ORDER_NO+ORDER_SUB_NO` | sample_pass |
| `LAB.LAB_TEST_ITEMS` | `LAB.LAB_TEST_MASTER` | `TEST_NO` | full_pass |
| `LAB.LAB_RESULT` | `LAB.LAB_TEST_MASTER` | `TEST_NO` | sample_pass，大表 |
| `LAB.LAB_TEST_MASTER` | `MEDREC.PAT_VISIT` | `PATIENT_ID+VISIT_ID` | 仅非零 VISIT_ID 住院子集 |
| `EXAM.EXAM_REPORT` | `EXAM.EXAM_MASTER` | `EXAM_NO` | full_pass |
| `EXAM.EXAM_BILL_ITEMS` | `EXAM.EXAM_MASTER` | `EXAM_NO` | full_pass |
| `EXAM.EXAM_MASTER` | `MEDREC.PAT_VISIT` | `PATIENT_ID+VISIT_ID` | 仅非零 VISIT_ID 住院子集 |
| `INPBILL.INP_SETTLE_MASTER` | `MEDREC.PAT_VISIT` | `PATIENT_ID+VISIT_ID` | full_pass |
| `INPBILL.INP_BILL_DETAIL` | `INPBILL.INP_SETTLE_MASTER` | `RCPT_NO` | sample_pass，大表 |
| `INPBILL.PREPAYMENT_RCPT` | `MEDREC.PAT_VISIT` | `PATIENT_ID+VISIT_ID` | 仅非零 VISIT_ID 子集 |
| `OUTPBILL.OUTP_BILL_ITEMS` | `OUTPBILL.OUTP_RCPT_MASTER` | `RCPT_NO` | sample_pass |

`LAB_TEST_ITEMS_DETAIL` 和 `EXAM_ITEMS` 是 partial；门诊检验/检查通过患者加申请日期关联 `CLINIC_MASTER` 仍是 candidate，不能作为唯一正式关系。

## 5. HIS 源端与数据中心 ODS 对接

- 数据中心 `ODS.HIS` 不是 HIS 源端全量镜像。
- 12 个源端 Owner 的 1234 张表中，历史同名进入数据中心 `HIS` Owner 的只有 105 张。
- 核心患者、住院、诊断、医嘱、检验、检查、费用表多为同名覆盖。
- 药房药库流水、医嘱执行、预交金、统计、配置和扩展字典大量未同名进入 ODS。
- 跨源对账时，必须同时记录 `source_system/source_owner/table_name`，不能把 `MEDREC.PAT_VISIT` 与数据中心 `HIS.PAT_VISIT` 当成同一物理对象。
- 同名覆盖只证明名称对应，不自动证明数据实时同步、全量一致或字段口径完全一致。`DIAGNOSIS_EMR` 已发现字段差异。

## 6. 纳入与排除口径

纳入核心业务事实、执行事实、缴费事实和持续维护字典。第一版排除：

- `ST_*` 统计汇总表；
- `*_LOG`、`*LOG*` 日志表；
- 临时、备份、历史复制表；
- 接口中间表，除非已证明是唯一业务事实来源；
- `COMM.OPERATION_LOG` 明确排除。

## 7. 连接方式

优先级：

1. 平台登记的 `HIS_SOURCE` 只读连接及 `/api/v1/ai` 只读执行端点；
2. 服务器容器内 `OracleConnector` 直连；
3. 当前环境无法直连时，使用既有 `ssh_jump` 模式。

认证只允许：

- `APP_HIS_SOURCE_USER` + `APP_HIS_SOURCE_PASSWORD` 环境变量；
- `CRED_HIS_SOURCE`，格式为 `user:password`；
- `APP_HIS_CREDENTIAL_FILE` 指向受控只读凭据文件。

不得在命令行参数、SQL、提示词、Markdown、Git 或错误日志中写密码。SSH 必须使用 known_hosts 严格校验，不使用 `AutoAddPolicy` 或关闭主机校验。

Oracle 旧版需要 python-oracledb thick。服务器通常使用 `/opt/oracle`；跳板历史环境可能使用 `/opt/oracle/instantclient_21`，以 `APP_ORACLE_CLIENT_LIB_DIR` 为准。

完整的 Windows 跳板、服务器内网直连、平台 API、环境变量和可复制命令见同目录 `connection-guide.md`。连接前必须读取该文件。

## 8. 权威文件

| 目的 | 文件 |
|---|---|
| 活库结构 | `开发起步包/16_hisuser业务库元数据快照.json` |
| 首次探查 | `16_hisuser业务库探查报告.md` / `结果.json` |
| 药房药库 | `19_药房药库关系验证报告.md` / `结果.json` |
| 核心 Owner 关系 | `21_HIS主业务owner关系补验报告.md` / `结果.json` |
| ODS 覆盖 | `22_HIS源端字段主题与ODS覆盖差异报告.md` / `结果.json` |
| 纳入规则 | `23_HIS源端资产范围复核与下一步计划报告.md` / `结果.json` |
| 机器资产 | `开发起步包/数据资产_HIS源端资产包/` |
| 治理口径 | `40_数据治理复核口径与方法记录.md` |
| 平台 AI 对接 | `87_AI视图SQL生成与平台对接说明.md` |
