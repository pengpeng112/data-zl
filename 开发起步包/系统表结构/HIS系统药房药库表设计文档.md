# 药房药库表设计文档（AI可读完整Markdown）

> 本文件由上传的 Word/Flat OPC 文档转换整理。
> 结构规则：每个数据库表一个二级标题；字段清单统一转换为 Markdown 表格，便于 AI 检索、比对和生成 SQL。

## 文档信息

- 数据库表结构文档
- **数据库名**：DRUG_USER_SDSR
- **文档版本**：1.0.0
- **文档描述**：数据库设计文档
- **表数量**：67

## 表目录

| 序号 | 表名 | 中文说明 | 字段数 | 主键字段 |
|---:|---|---|---:|---|
| 1 | `INIT_ACCOUNT_LOG` |  | 13 | ID |
| 2 | `MED_ADJUST_PRICE_DETAIL` | 调价明细表 | 22 | RECORD_ID |
| 3 | `MED_ADJUST_PRICE_LIST` | 调价盈亏记录表 | 27 | RECORD_NO |
| 4 | `MED_ADJUST_PRICE_MASTER` | 调价主表 | 20 | ADJUST_BILLNO |
| 5 | `MED_CARE_DETAIL` | 药品养护记录明细表 | 18 | RECORD_NO |
| 6 | `MED_CARE_MASTER` | 药品养护记录主表 | 9 |  |
| 7 | `MED_CHECK_DETAIL` | 盘点明细表 | 36 |  |
| 8 | `MED_CHECK_MASTER` | 盘点主表 | 23 | CHECK_NO |
| 9 | `MED_CODE_GENERATE_RULE` | 单号生成规则表 | 19 | ID |
| 10 | `MED_CODE_MASTER` | 单号主表 | 15 | ID |
| 11 | `MED_DETAIL_STORAGE` | 药品结存记录 | 25 |  |
| 12 | `MED_DICT_BASEINFO` | 药品目录表 | 86 |  |
| 13 | `MED_DICT_BASEINFO_RECORD` | 药品修改记录表 | 15 |  |
| 14 | `MED_DICT_DEPT` | 药房药库名称编码表 | 21 |  |
| 15 | `MED_DICT_FACTORY` | 药品字典厂商 | 23 | FACTORY_CODE |
| 16 | `MED_DICT_INTYPE` | 药品字典入库类型 | 18 | IN_KIND |
| 17 | `MED_DICT_LOC` | 药品字典库位编码 | 10 | ORG_CODE, STORE_CODE, LOC_CODE |
| 18 | `MED_DICT_LOCRULE` | 药品字典库位编码规则 | 5 | ORG_CODE, STORE_CODE, SORT_NO |
| 19 | `MED_DICT_OUTTYPE` | 药品字典出库类型 | 19 | OUT_TYPE_ID |
| 20 | `MED_DICT_PRICE` | 药品产地价格表 | 44 | DRUG_PRI |
| 21 | `MED_DICT_PRICE_RECORD` | 药品产地价格修改记录表 | 4 | UPDATE_PRICE_ID |
| 22 | `MED_DICT_SUPPLIER` | 药品字典供货商 | 20 | SUPPLIER_ID |
| 23 | `MED_DRUG_LOC` | 药品库位对照表 | 6 | BIND_ID |
| 24 | `MED_FIN_DAYDETAIL` | 财务月结明细表 | 13 | RECORD_NO |
| 25 | `MED_FIN_DAYSETTLE` | 财务月结主表 | 7 | FIN_ID |
| 26 | `MED_FIN_MONTHDETAIL` | 财务月结明细表 | 23 | RECORD_NO |
| 27 | `MED_FIN_MONTHSETTLE` | 财务月结主表 | 19 | FIN_ID |
| 28 | `MED_INIT_ACCOUNT` | 药库初始化建账表 | 35 | ID |
| 29 | `MED_IN_DETAIL` | 采购入库明细表 | 40 | SORT_NO |
| 30 | `MED_IN_MASTER` | 采购入库主表 | 31 | IN_BILLNO |
| 31 | `MED_IN_PAY` | 财务验收付款主表 | 21 | ORG_CODE, ORDER_NO |
| 32 | `MED_IN_PAYDETAIL` | 财务验收付款明细表 | 19 | ID |
| 33 | `MED_IN_PLAN` | 采购计划主表 | 34 | ORG_CODE, PLAN_BILLNO |
| 34 | `MED_IN_PLAN_DETAIL` | 采购计划明细表 | 19 |  |
| 35 | `MED_OUT_DETAIL` | 出库信息明细表 | 33 | RECORD_NO |
| 36 | `MED_OUT_MASTER` | 出库信息主表 | 36 | OUT_BILLNO |
| 37 | `MED_PHARMACY` |  | 4 | ID |
| 38 | `MED_STORAGE` | 药品库存信息 | 29 | RECORD_NO |
| 39 | `MED_TRACE_RECORD` | 药品追溯码记录表 | 26 | RECORD_ID |
| 40 | `MED_TRACE_STORGE` | 药品追溯码库存表 | 22 | RECORD_ID |
| 41 | `MESSAGE_CENTER` | PDA消息提醒 | 7 |  |
| 42 | `PHA_ALLOCAT_MASTER` | 药房调拨主表 | 25 | REQUEST_NO |
| 43 | `PHA_ALOOCAT_DETAIL` | 药房调拨明细表 | 28 | RECORD_NO |
| 44 | `PHA_BALANCE` | 药房价格差额表（平账表） | 30 | RECORD_NO |
| 45 | `PHA_CHECK_DETAIL` | 药房盘点明细表 | 37 |  |
| 46 | `PHA_CHECK_MASTER` | 药房盘点主表 | 24 |  |
| 47 | `PHA_CLI_REQUEST_DRUG` | 门诊发药申请表 | 95 | ID |
| 48 | `PHA_DETAIL_STORAGE` | 药房库存结存信息 | 25 | DETAIL_ID |
| 49 | `PHA_DICT_MEDINFO` | 药品字典药房药品 | 26 | ORG_CODE, PHA_CODE, DRUG_PRI |
| 50 | `PHA_FALSE_STORAGE` | 药房库存信息 | 9 | ID |
| 51 | `PHA_FIN_DAYDETAIL` | 财务月结明细表 | 13 | RECORD_NO |
| 52 | `PHA_FIN_DAYSETTLE` | 财务月结主表 | 9 | FIN_ID |
| 53 | `PHA_FIN_MONTHDETAIL` | 财务月结明细表 | 24 | RECORD_NO |
| 54 | `PHA_FIN_MONTHSETTLE` | 财务月结主表 | 20 | FIN_ID |
| 55 | `PHA_INIT_ACCOUNT` | 药房初始化建账表 | 35 | ID |
| 56 | `PHA_INP_DISPDETAIL` | 住院发药明细 | 49 | ORG_CODE, RECORD_NO |
| 57 | `PHA_INP_DISPMASTER` | 药房发药住院记录主表 | 22 | DIS_RECORDNO |
| 58 | `PHA_INP_REQUEST_DRUG` | 住院发药申请 | 85 |  |
| 59 | `PHA_SPECIAL_DRUG_REVIEW` | 特殊药品审核记录表 | 40 | ID |
| 60 | `PHA_STORAGE` | 药房库存信息 | 29 | RECORD_NO |
| 61 | `PHA_VISIT_DISPDETAIL` | 门诊发药申请详情? | 39 | RECORD_NO |
| 62 | `PHA_VISIT_DISPMASTER` |  | 14 | ORG_CODE, PHA_CODE, PRESC_NO |
| 63 | `PUB_CONFIG` | 系统配置表 | 22 | ID |
| 64 | `PUB_CONFIG_SET` | 系统配置选项设置表 | 15 | ID |
| 65 | `SUPPLIER_IN_DETAIL` | 采购入库明细 | 26 |  |
| 66 | `SUPPLIER_IN_MASTER` | 采购入库主表对象 | 18 | IN_BILLNO |
| 67 | `SYSTEM_CONFIG` | 系统配置项 | 7 |  |

## 表结构明细

### 01. INIT_ACCOUNT_LOG

- **表名**：`INIT_ACCOUNT_LOG`
- **字段数**：13
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ID | number | 19 | 0 | N | Y |  |  |
| 2 | SYSTEM_FLAG | number | 1 | 0 | Y | N |  | 药房、药库库房识别码 |
| 3 | STORE_CODE | varchar2 | 255 | 0 | Y | N |  | 系统标记：1药房、2药库 |
| 4 | IS_DELETED | number | 1 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 5 | CREATE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 创建者id |
| 6 | CREATE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 创建者姓名 |
| 7 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 8 | MODIFY_USER_ID | varchar2 | 30 | 0 | Y | N |  | 修改者id |
| 9 | MODIFY_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 修改者姓名 |
| 10 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 11 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 12 | DELETE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 删除人id |
| 13 | DELETE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 删除人姓名 |

### 02. MED_ADJUST_PRICE_DETAIL（调价明细表）

- **表名**：`MED_ADJUST_PRICE_DETAIL`
- **中文说明**：调价明细表
- **字段数**：22
- **主键字段**：RECORD_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_ID | number | 20 | 0 | N | Y |  | 记录序号 |
| 2 | ORG_CODE | varchar2 | 50 | 0 | Y | N | 1 | 机构ID |
| 3 | STORE_CODE | varchar2 | 16 | 0 | N | N |  | 库房编码 |
| 4 | ADJUST_TYPE | number | 4 | 0 | N | N |  | 调价方式 |
| 5 | ADJUST_BILLNO | varchar2 | 32 | 0 | N | N |  | 调价单号 |
| 6 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品主键,MED_DICT_PRICE.DRUG_PRI |
| 7 | ADJUST_QUANTITY | number | 12 | 4 | N | N | 0 | 调价数量 |
| 8 | TRADE_PRICE | number | 14 | 6 | N | N |  | 原采购价 |
| 9 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 原零售价 |
| 10 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 原批发价 |
| 11 | TRADE_NEWPRICE | number | 14 | 6 | N | N |  | 新采购价 |
| 12 | RETAIL_NEWPRICE | number | 14 | 6 | N | N |  | 新零售价 |
| 13 | WHOLESALE_NEWPRICE | number | 14 | 6 | Y | N |  | 新批发价 |
| 14 | RETAIL_DIF | number | 12 | 4 | N | N | 0 | 零售差额 |
| 15 | WHOLESALE_DIF | number | 12 | 4 | N | N | 0 | 批发差额 |
| 16 | TRADE_DIF | number | 12 | 4 | N | N | 0 | 进货差额 |
| 17 | RETAIL_OLDSUM | number | 12 | 4 | N | N | 0 | 原零售额 |
| 18 | WHOLESALE_OLDSUM | number | 12 | 4 | N | N | 0 | 原批发额 |
| 19 | TRADE_OLDSUM | number | 12 | 4 | N | N | 0 | 原进货额 |
| 20 | RETAIL_NEWSUM | number | 12 | 4 | N | N | 0 | 新零售额 |
| 21 | WHOLESALE_NEWSUM | number | 12 | 4 | N | N | 0 | 新批发额 |
| 22 | TRADE_NEWSUM | number | 12 | 4 | N | N | 0 | 新进货额 |

### 03. MED_ADJUST_PRICE_LIST（调价盈亏记录表）

- **表名**：`MED_ADJUST_PRICE_LIST`
- **中文说明**：调价盈亏记录表
- **字段数**：27
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 2 | RECORD_NO | number | 30 | 0 | N | Y |  | 记录序号 |
| 3 | STORE_CODE | varchar2 | 50 | 0 | N | N |  | 库房编码 |
| 4 | ADJUST_TYPE | number | 8 | 0 | N | N |  | 调价类型 |
| 5 | ADJUST_BILLNO | varchar2 | 32 | 0 | N | N |  | 调价单号 |
| 6 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品主键,MED_DICT_PRICE.DRUG_PRI |
| 7 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  | 药品批号 |
| 8 | EXPIRE_DATE | date | 7 | 0 | Y | N |  | 药品效期2 |
| 9 | ADJUST_QUANTITY | number | 12 | 4 | N | N | 0 | 调价数量 |
| 10 | TRADE_PRICE | number | 14 | 6 | N | N |  | 原采购价 |
| 11 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 原零售价 |
| 12 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 原批发价 |
| 13 | TRADE_NEWPRICE | number | 14 | 6 | N | N |  | 新采购价 |
| 14 | RETAIL_NEWPRICE | number | 14 | 6 | N | N |  | 新零售价 |
| 15 | WHOLESALE_NEWPRICE | number | 14 | 6 | Y | N |  | 新批发价 |
| 16 | STORE_ID | varchar2 | 50 | 0 | N | N | 0 | 库存ID,MED_STORAGE.RECORD、PHA_STORAGE.RECORD_NO |
| 17 | STORE_QUANTITY | number | 12 | 4 | N | N | 0 | 库存数量 |
| 18 | RETAIL_DIF | number | 12 | 4 | N | N | 0 | 零售差额 |
| 19 | WHOLESALE_DIF | number | 12 | 4 | N | N | 0 | 批发差额 |
| 20 | TRADE_DIF | number | 12 | 4 | N | N | 0 | 进货差额 |
| 21 | RETAIL_OLDSUM | number | 12 | 4 | N | N | 0 | 原零售额 |
| 22 | WHOLESALE_OLDSUM | number | 12 | 4 | N | N | 0 | 原批发额 |
| 23 | TRADE_OLDSUM | number | 12 | 4 | N | N | 0 | 原进货额 |
| 24 | RETAIL_NEWSUM | number | 12 | 4 | N | N | 0 | 新零售额 |
| 25 | WHOLESALE_NEWSUM | number | 12 | 4 | N | N | 0 | 新批发额 |
| 26 | TRADE_NEWSUM | number | 12 | 4 | N | N | 0 | 新进货额 |
| 27 | PRODUCT_DATE | date | 7 | 0 | Y | N |  | 药品效期 |

### 04. MED_ADJUST_PRICE_MASTER（调价主表）

- **表名**：`MED_ADJUST_PRICE_MASTER`
- **中文说明**：调价主表
- **字段数**：20
- **主键字段**：ADJUST_BILLNO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 50 | 0 | N | N | '1' | 机构编码 |
| 2 | STORE_CODE | varchar2 | 50 | 0 | N | N |  | 库房编码 |
| 3 | ADJUST_BILLNO | varchar2 | 32 | 0 | N | Y |  | 主键 调价单号 |
| 4 | ADJUST_TYPE | number | 8 | 0 | N | N | 1 | 调价类型 1 立即生效 2 定时生效 |
| 5 | ADJST_DATE | timestamp(6) | 11 | 6 | Y | N |  | 开始调价日期 |
| 6 | RECEIVE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 收文日期 |
| 7 | ADJUST_FILENO | varchar2 | 32 | 0 | Y | N |  | 调价文号 |
| 8 | EXECUTE_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 执行人名称 |
| 9 | EXECUTE_OPER | varchar2 | 16 | 0 | Y | N |  | 执行工号 |
| 10 | EXECUTE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 执行日期 |
| 11 | OPERATOR_NAME | varchar2 | 50 | 0 | Y | N |  | 操作人姓名 |
| 12 | OPERATOR_CODE | varchar2 | 50 | 0 | Y | N |  | 操作工号 |
| 13 | TASK_DATE | date | 7 | 0 | Y | N |  | 定时日期 |
| 14 | TASK_TIME | date | 7 | 0 | Y | N |  | 定时时间 |
| 15 | ADJUST_REASON | varchar2 | 4000 | 0 | Y | N |  | 调价原因 |
| 16 | ADJUST_STATE | number | 1 | 0 | Y | N |  | 调价状态 0未生效 1成功 2失败 3已作废 |
| 17 | JOB_ID | number | 30 | 0 | Y | N |  | 门户的调度id |
| 18 | STORE_PHA_IDEN | varchar2 | 50 | 0 | Y | N |  | 调价 药库和药房标识 store 药库 pha 药房 all 所有 |
| 19 | ADJUST_MARK | varchar2 | 4000 | 0 | Y | N |  | 调价备注 |
| 20 | ADJUST_SOURCE | number | 1 | 0 | Y | N |  | 调价 0院内、1院外 |

### 05. MED_CARE_DETAIL（药品养护记录明细表）

- **表名**：`MED_CARE_DETAIL`
- **中文说明**：药品养护记录明细表
- **字段数**：18
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | number | 22 | 0 | N | Y |  | 记录序号 |
| 2 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 3 | STORE_CODE | varchar2 | 50 | 0 | N | N |  | 库房编码 |
| 4 | CARE_BILLNO | varchar2 | 32 | 0 | N | N |  | 养护单号 |
| 5 | DRUG_PRI | varchar2 | 32 | 0 | N | N |  | 药品主键 |
| 6 | PRODUCT_DATE | date | 7 | 0 | Y | N |  | 生产日期 |
| 7 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  | 药品批号 |
| 8 | EXPIRE_DATE | date | 7 | 0 | Y | N |  | 药品效期 |
| 9 | TRADE_PRICE | number | 14 | 6 | N | N |  | 采购价 |
| 10 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 11 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 12 | STORE_QUANTITY | number | 12 | 4 | N | N | 0 | 库存数量 |
| 13 | BREAK_QUANTITY | number | 12 | 4 | N | N | 0 | 损坏数量 |
| 14 | STORE_TYPE | number | 6 | 0 | N | N | 0 | 库存性质 |
| 15 | STORE_ID | number | 18 | 0 | N | N | 0 | 库存识别ID |
| 16 | DEAL_OPTION | varchar2 | 64 | 0 | Y | N |  | 处理意见 |
| 17 | QUALITY | varchar2 | 32 | 0 | Y | N |  | 质量状况 |
| 18 | DEAL_RESULT | varchar2 | 32 | 0 | Y | N |  | 处理结果 |

### 06. MED_CARE_MASTER（药品养护记录主表）

- **表名**：`MED_CARE_MASTER`
- **中文说明**：药品养护记录主表
- **字段数**：9

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 2 | STORE_CODE | varchar2 | 50 | 0 | N | N |  | 库房编码 |
| 3 | CARE_BILLNO | varchar2 | 32 | 0 | N | N |  | 养护单号 |
| 4 | CARE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 养护日期 创建日期 |
| 5 | CARE_OPER | varchar2 | 16 | 0 | Y | N |  | 养护工号 |
| 6 | OPERATOR | varchar2 | 16 | 0 | Y | N |  | 操作工号 |
| 7 | OPER_DATE | timestamp(6) | 11 | 6 | Y | N |  | 操作日期 |
| 8 | MEMO | varchar2 | 100 | 0 | Y | N |  | 备注信息 |
| 9 | CARE_STATE | number | 1 | 0 | Y | N | 0 | 0待执行 1执行中 2已执行 |

### 07. MED_CHECK_DETAIL（盘点明细表）

- **表名**：`MED_CHECK_DETAIL`
- **中文说明**：盘点明细表
- **字段数**：36

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | number | 20 | 0 | N | N |  | 记录序号 |
| 2 | ORG_CODE | varchar2 | 50 | 0 | N | N |  | 机构代码 |
| 3 | CHECK_NO | varchar2 | 50 | 0 | N | N |  | 盘点单号 |
| 4 | STORE_CODE | varchar2 | 50 | 0 | N | N |  | 库房编码 |
| 5 | DRUG_LOC | varchar2 | 1000 | 0 | Y | N |  | 库存货位编码 |
| 6 | DRUG_PRI | varchar2 | 32 | 0 | N | N |  | 药品主键,MED_DICT_PRICE.DRUG_PRI |
| 7 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  | 药品批号 |
| 8 | EXPIRE_DATE | date | 7 | 0 | Y | N |  | 药品效期 |
| 9 | START_TIME | date | 7 | 0 | Y | N |  | 盘点开始时间 |
| 10 | START_QUANTITY | number | 12 | 4 | Y | N |  | 起始库存数量 |
| 11 | TRADE_PRICE | number | 14 | 6 | Y | N |  | 进货价格 |
| 12 | RETAIL_PRICE | number | 14 | 6 | Y | N |  | 零售价格 |
| 13 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价格 |
| 14 | STORE_ID | varchar2 | 50 | 0 | N | N |  | 库存识别ID |
| 15 | REAL_QUANTITY | number | 12 | 4 | Y | N |  | 实盘数量 |
| 16 | REAL_TIME | date | 7 | 0 | Y | N |  | 实盘完成时间 |
| 17 | REAL_STORAGE | number | 12 | 4 | Y | N |  | 实盘时库存 |
| 18 | CHECK_OPER | varchar2 | 50 | 0 | Y | N |  | 实盘人 |
| 19 | CHECK_INOUT | number | 12 | 4 | Y | N |  | 盘点期间入出数量 |
| 20 | STORAGE_COST | number | 12 | 4 | N | N | 0 | 进货金额 |
| 21 | WHOLESALE_COST | number | 12 | 4 | N | N | 0 | 批发金额 |
| 22 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售金额 |
| 23 | MEMO | varchar2 | 128 | 0 | Y | N |  | 备注信息 |
| 24 | PRODUCT_DATE | date | 7 | 0 | Y | N |  | 生产日期 |
| 25 | PDA_STATE | number | 1 | 0 | Y | N | 0 | 盘点状态 |
| 26 | STORE_TYPE | number | 4 | 0 | Y | N |  | 库存类型 |
| 27 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 28 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 29 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 30 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 31 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 32 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 33 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 34 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 35 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 36 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |

### 08. MED_CHECK_MASTER（盘点主表）

- **表名**：`MED_CHECK_MASTER`
- **中文说明**：盘点主表
- **字段数**：23
- **主键字段**：CHECK_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 2 | DRUG_STORE | varchar2 | 50 | 0 | N | N |  | 库房识别 |
| 3 | CHECK_NO | varchar2 | 32 | 0 | N | Y |  | 盘点单号 |
| 4 | DRUG_LOC | varchar2 | 512 | 0 | Y | N |  | 库位类别 |
| 5 | DRUG_TYPE | varchar2 | 512 | 0 | N | N |  | 药品类别 |
| 6 | CHECK_DATE | timestamp(6) | 11 | 6 | Y | N |  | 开始盘点日期 |
| 7 | CHECK_OPER | varchar2 | 16 | 0 | Y | N |  | 开始盘点工号 |
| 8 | FINISH_OPER | varchar2 | 16 | 0 | Y | N |  | 完成盘点工号 |
| 9 | FINISH_DATE | timestamp(6) | 11 | 6 | Y | N |  | 完成盘点日期 |
| 10 | MZMO | varchar2 | 100 | 0 | Y | N |  | 备注信息 |
| 11 | CHECK_STATE | number | 1 | 0 | Y | N | 0 | 盘点状态 0 未盘点 1 盘点中 2已完成 |
| 12 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 13 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 14 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 15 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 16 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 17 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 18 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 19 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 20 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 21 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 22 | CHECK_USER_ID | varchar2 | 255 | 0 | Y | N |  | 盘点人编码 |
| 23 | CHECK_USER_NAME | varchar2 | 255 | 0 | Y | N |  | 盘点人名称 |

### 09. MED_CODE_GENERATE_RULE（单号生成规则表）

- **表名**：`MED_CODE_GENERATE_RULE`
- **中文说明**：单号生成规则表
- **字段数**：19
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ID | varchar2 | 32 | 0 | N | Y |  | 主键ID |
| 2 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 3 | CODE_TYPE | varchar2 | 30 | 0 | N | N |  | 出入库类型编码 |
| 4 | CODE_PREFIX | varchar2 | 30 | 0 | N | N |  | 出入库单号前缀 |
| 5 | FIXED_CODE | varchar2 | 30 | 0 | Y | N |  | 固定编码 位于前缀后面（出入库类型大写） |
| 6 | DATE_FORMAT | varchar2 | 16 | 0 | Y | N |  | 日期格式 1-yyyyMMdd 2-yyyyMM 3-yyyy |
| 7 | CODE_BEGIN_RULE | varchar2 | 16 | 0 | Y | N |  | 日期重置规则 1-每天从1开始 2-每月从1开始 3-每年从1开始 |
| 8 | INVALID_FLAG | varchar2 | 16 | 0 | N | N | '0' | 是否作废(启用禁用) 0、否(启用) 1、是(禁用) |
| 9 | CODE_LENGTH | number | 16 | 0 | Y | N |  | 单号长度 |
| 10 | CREATE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 创建人id |
| 11 | CREATE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 创建人姓名 |
| 12 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 13 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改人id |
| 14 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改人姓名 |
| 15 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改时间 |
| 16 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0否、1是 |
| 17 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 18 | DELETE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 删除人id |
| 19 | DELETE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 删除人姓名 |

### 10. MED_CODE_MASTER（单号主表）

- **表名**：`MED_CODE_MASTER`
- **中文说明**：单号主表
- **字段数**：15
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ID | varchar2 | 32 | 0 | N | Y |  | 主键ID |
| 2 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 3 | CODE_TYPE | varchar2 | 30 | 0 | N | N |  | 出入库类型 |
| 4 | CODE_NO | varchar2 | 30 | 0 | N | N |  | 单号序号 |
| 5 | WORK_TIME | timestamp(6) | 11 | 6 | N | N |  | 业务时间 |
| 6 | CREATE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 创建人id |
| 7 | CREATE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 创建人姓名 |
| 8 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 9 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改人id |
| 10 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改人姓名 |
| 11 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改时间 |
| 12 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0否1是 |
| 13 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 14 | DELETE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 删除人id |
| 15 | DELETE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 删除人姓名 |

### 11. MED_DETAIL_STORAGE（药品结存记录）

- **表名**：`MED_DETAIL_STORAGE`
- **中文说明**：药品结存记录
- **字段数**：25

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | DETAIL_ID | varchar2 | 50 | 0 | N | N |  | PHA |
| 2 | STORE_CODE | varchar2 | 16 | 0 | Y | N |  | 库房识别 |
| 3 | ORG_CODE | varchar2 | 32 | 0 | Y | N |  | 机构编码 |
| 4 | DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药品主键,MED_DICT_PRICE.DRUG_PRI |
| 5 | BATCH_NO | varchar2 | 50 | 0 | Y | N |  | 药品批号 |
| 6 | EXPIRE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 药品效期 |
| 7 | TRADE_PRICE | number | 14 | 6 | Y | N |  | 采购价 |
| 8 | RETAIL_PRICE | number | 14 | 6 | Y | N |  | 零售价 |
| 9 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 10 | STORAGE_QUANTITY | number | 12 | 4 | Y | N |  | 库存数量 |
| 11 | STORAGE_COST | number | 12 | 4 | Y | N |  | 进货金额 |
| 12 | WHOLESALE_COST | number | 12 | 4 | Y | N |  | 批发金额 |
| 13 | RETAIL_COST | number | 12 | 4 | Y | N |  | 零售金额 |
| 14 | INOUT_KIND | varchar2 | 50 | 0 | Y | N |  | 出入库方式 |
| 15 | INOUT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 业务时间 |
| 16 | PRODUCT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 生产日期 |
| 17 | RECORD_NO | varchar2 | 50 | 0 | Y | N |  | 记录序号 |
| 18 | IN_OUT_TYPE | varchar2 | 50 | 0 | Y | N |  | 出入库标识 in 入库 out 出库 |
| 19 | TOTAL_QUANTITY | number | 0 | -127 | Y | N |  | 药品总数量(不区分批次等属性) |
| 20 | BEFORE_QUANTITY | number | 12 | 4 | N | N |  | 原库存数量 |
| 21 | IN_QUANTITY | number | 12 | 4 | N | N |  | 入库数量 |
| 22 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 23 | TOTAL_RETAIL_COST | number | 14 | 6 | N | N |  | 零售总金额 |
| 24 | TOTAL_WHOLESALE_COST | number | 14 | 6 | N | N |  | 批发总金额 |
| 25 | TOTAL_STORAGE_COST | number | 14 | 6 | N | N |  | 进货总金额 |

### 12. MED_DICT_BASEINFO（药品目录表）

- **表名**：`MED_DICT_BASEINFO`
- **中文说明**：药品目录表
- **字段数**：86

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | DRUG_ID | varchar2 | 50 | 0 | N | N |  | 药品id |
| 2 | DRUG_CODE | varchar2 | 50 | 0 | Y | N |  | 药品编码 |
| 3 | DRUG_NAME | varchar2 | 80 | 0 | N | N |  | 药品名称 |
| 4 | SPELL_CODE | varchar2 | 50 | 0 | Y | N |  | 药品名拼音简码 |
| 5 | WB_CODE | varchar2 | 50 | 0 | Y | N |  | 药品名五笔简码 |
| 6 | OTHER_NAME | varchar2 | 80 | 0 | Y | N |  | 别名 |
| 7 | OTHER_SPELL | varchar2 | 50 | 0 | Y | N |  | 别名拼音码 |
| 8 | OTHER_WB | varchar2 | 50 | 0 | Y | N |  | 别名五笔码 |
| 9 | REGULAR_NAME | varchar2 | 80 | 0 | Y | N |  | 通用名 |
| 10 | REGULAR_SPELL | varchar2 | 50 | 0 | Y | N |  | 通用名拼音码 |
| 11 | REGULAR_WB | varchar2 | 50 | 0 | Y | N |  | 通用名五笔码 |
| 12 | DRUG_TYPE | varchar2 | 50 | 0 | Y | N |  | 药品类别1.西药，2.中成药，3.草药 |
| 13 | PHY_CLASS | varchar2 | 50 | 0 | Y | N |  | 药理分类 |
| 14 | DOSE | number | 12 | 4 | Y | N |  | 包装剂量 |
| 15 | ONCE_DOSE | number | 12 | 4 | Y | N |  | 成人一次剂量 |
| 16 | CHILD_ONCEDOSE | number | 12 | 4 | Y | N |  | 儿童一次剂量 |
| 17 | DOSE_UNIT | varchar2 | 50 | 0 | Y | N |  | 剂量单位 |
| 18 | MIN_PACK | number | 12 | 4 | Y | N |  | 最小包装数量 |
| 19 | MIN_UNIT | varchar2 | 50 | 0 | Y | N |  | 最小包装单位 |
| 20 | USAGE | varchar2 | 50 | 0 | Y | N |  | 默认用法编码 |
| 21 | FREQUENCY | varchar2 | 50 | 0 | Y | N |  | 默认频次编码 |
| 22 | TEST_FLAG | number | 1 | 0 | Y | N |  | 是否需要试敏 0不需要1易过敏提示是否做2需要做皮试 |
| 23 | DANGER_FLAG | number | 1 | 0 | Y | N |  | 是否是高危药品，1为是，0为否 |
| 24 | SELF_FLAG | number | 1 | 0 | Y | N |  | 自产标志 0-非自产，1-自产 |
| 25 | DDD_QTY | number | 12 | 4 | Y | N |  | DDD值 |
| 26 | DDD_UNIT | varchar2 | 50 | 0 | Y | N |  | DDD剂量单位 |
| 27 | BASICDRUG | number | 1 | 0 | Y | N | '0' | 基本药物标记 0非基本药物1国家基本药物2省基本药物 |
| 28 | DEL_FLAG | number | 1 | 0 | Y | N | 0 | 药库作废标记：0正常1作废 |
| 29 | CLI_DELFLAG | number | 1 | 0 | Y | N | 0 | 门诊作废标记 1 作废 0 未作废 |
| 30 | INP_DELFLAG | number | 1 | 0 | Y | N | 0 | 住院作废标记 1 作废 0 未作废 |
| 31 | FIN_CODE | varchar2 | 50 | 0 | Y | N |  | 会计账类别（会计科目） |
| 32 | FEE_CODE | varchar2 | 50 | 0 | Y | N |  | 费用类别 |
| 33 | CANCER_FLAG | number | 1 | 0 | Y | N |  | 肿瘤和辅助用药：0、否 1、是 |
| 34 | DRUG_CLASS | varchar2 | 50 | 0 | Y | N |  | 药品目录 |
| 35 | CARE_FLAG | number | 1 | 0 | Y | N |  | 养护标记0是养护1是不养护 |
| 36 | DOSE_MODEL_CODE | varchar2 | 50 | 0 | Y | N |  | 剂型 |
| 37 | ANTI_FLAG | varchar2 | 20 | 0 | Y | N |  | 抗生素级别: 1非限制2限制3特殊 |
| 38 | STORE_CONDITION | char | 1 | 0 | Y | N |  | 储藏条件（字典项）:1阴凉、2常温、3低温、4避光 |
| 39 | ITEM_GRADE | number | 0 | -127 | Y | N |  | 药品等级(医保等级) 1甲类2乙类3丙类 |
| 40 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建人id |
| 41 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建人姓名 |
| 42 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 43 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改人id |
| 44 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改人姓名 |
| 45 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改时间 |
| 46 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 47 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 48 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 49 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标志 0否 1是 |
| 50 | ANES_LEVEL | number | 1 | 0 | Y | N |  | 麻醉药品级别：0非麻醉药品1麻醉一级2麻醉二级 |
| 51 | PSY_LEVEL | number | 1 | 0 | Y | N |  | 精神药品级别：0非精神药品1精神一级2精神二级3精神三级 |
| 52 | POISON_FLAG | number | 1 | 0 | Y | N |  | 毒性药品标记：0非毒性1毒性 |
| 53 | ANTI_CLASS | varchar2 | 28 | 0 | Y | N |  | 抗生素分类（字典项） |
| 54 | ANTI_PREVENT | number | 1 | 0 | Y | N |  | 预防用药：0不可以作废预防用药1可以作废预防用药 |
| 55 | ANTI_OVER | number | 1 | 0 | Y | N |  | 越权使用：0可以越权使用，只提醒1不可以约权使用，禁止使用 |
| 56 | ANTI_CHECK | number | 1 | 0 | Y | N |  | 审批使用：0不需要审批1审批使用 |
| 57 | ANTI_CUT1 | number | 1 | 0 | Y | N |  | 一类切口预防首选：非一类切口首选1一类切口首选 |
| 58 | ANTI_CUT2 | number | 1 | 0 | Y | N |  | 二类切口预防首选：0非二类切口首选1二类切口首选 |
| 59 | ANTI_CUT3 | number | 1 | 0 | Y | N |  | 三类切口预防首选：0非三类切口首选1三类切口首选 |
| 60 | DRUG_VALUE | number | 1 | 0 | Y | N |  | 贵重药品：0、否 1、是 |
| 61 | DRUG_CHEMO | number | 1 | 0 | Y | N |  | 化疗药品：0、否 1、是 |
| 62 | DRUG_HORMONE | number | 1 | 0 | Y | N |  | 激素类药品：0、否 1、是 |
| 63 | DRUG_BLOOD | number | 1 | 0 | Y | N |  | 血液制品：0、否 1、是 |
| 64 | COMPOUND_DOSE | number | 12 | 4 | Y | N |  | 复方剂量 |
| 65 | COMPOUND_DOSE_UNIT | varchar2 | 50 | 0 | Y | N |  | 复方剂量单位 |
| 66 | ANTIBIOTIC_FLAG | number | 1 | 0 | Y | N |  | 抗生素标记：0、否 1、是 |
| 67 | DRUG_PRECURSOR | number | 1 | 0 | Y | N |  | 易制毒药品：0、否 1、是 |
| 68 | DRUG_LOC | varchar2 | 255 | 0 | Y | N |  |  |
| 69 | STORE_CONDITION_LEVEL | varchar2 | 10 | 0 | Y | N |  | 低温储藏条件：A01、2-8℃，A02、20℃以下，A03、-20-5℃ |
| 70 | VISIT_SHARING_RATIO | varchar2 | 255 | 0 | Y | N |  | 门诊分摊比例 |
| 71 | INP_SHARING_RATIO | varchar2 | 255 | 0 | Y | N |  | 住院分摊比例 |
| 72 | MAIN_DRUG | varchar2 | 255 | 0 | Y | N |  | 重点药品：0、否 1、是 |
| 73 | EXPERIMENT_DRUG | varchar2 | 255 | 0 | Y | N |  | 试验药物：0、否 1、是 |
| 74 | ASSISTANT_DRUG | varchar2 | 255 | 0 | Y | N |  | 辅助药品：0、否 1、是 |
| 75 | ANIT_TUMOR_MONITORING | varchar2 | 255 | 0 | Y | N |  | 抗肿瘤监测：0、否 1、是 |
| 76 | EXCLUDE_BASED_DRUG | varchar2 | 255 | 0 | Y | N |  | 药占比剔除品种：0、否 1、是 |
| 77 | DUAL_CHANNEL | varchar2 | 255 | 0 | Y | N |  | 双通道：0、否 1、是 |
| 78 | DISPENSING | varchar2 | 255 | 0 | Y | N | '0' | 摆药：0、否 1、是 |
| 79 | DRUG_SPEC | varchar2 | 255 | 0 | Y | N |  | 基础规格 |
| 80 | DRUG_REMARK | varchar2 | 1000 | 0 | Y | N |  | 药品说明 |
| 81 | ZY_INJECTION | number | 1 | 0 | Y | N | 0 | 中药注射剂：0否、1是 |
| 82 | PROTON_PUMP | number | 1 | 0 | Y | N | 0 | 质子泵仰制剂：0否、1是 |
| 83 | DISABLE_BEGIN_TIME | date | 7 | 0 | Y | N |  | 禁用开始时间 |
| 84 | DISABLE_END_TIME | date | 7 | 0 | Y | N |  | 禁用结束时间 |
| 85 | ACCOUNT_SUBJECT | varchar2 | 255 | 0 | Y | N |  | 核算科目 |
| 86 | CASE_CLASS | varchar2 | 255 | 0 | Y | N |  | 病案分类 |

### 13. MED_DICT_BASEINFO_RECORD（药品修改记录表）

- **表名**：`MED_DICT_BASEINFO_RECORD`
- **中文说明**：药品修改记录表
- **字段数**：15

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | DRUG_UPDATE_RECORD_ID | varchar2 | 50 | 0 | N | N |  | 药品修改记录id |
| 2 | DRUG_ID | varchar2 | 50 | 0 | Y | N |  | 药品主键id |
| 3 | DRUG_UPDATE_DATA | varchar2 | 1024 | 0 | Y | N |  | 药物更新数据 |
| 4 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建人id |
| 5 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建人姓名 |
| 6 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 7 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改人id |
| 8 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改人姓名 |
| 9 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改时间 |
| 10 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 11 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 12 | DELETE_TIME | date | 7 | 0 | Y | N |  | 删除时间 |
| 13 | IS_DELETED | number | 10 | 0 | Y | N |  | 删除标志 0否 1是 |
| 14 | DRUG_NAME_OLD | varchar2 | 1024 | 0 | Y | N |  | 药品名称老 |
| 15 | DRUG_NAME_NEW | varchar2 | 1024 | 0 | Y | N |  | 药品名称新 |

### 14. MED_DICT_DEPT（药房药库名称编码表）

- **表名**：`MED_DICT_DEPT`
- **中文说明**：药房药库名称编码表
- **字段数**：21

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | STORE_CODE | varchar2 | 16 | 0 | N | N |  | 药房编码 |
| 2 | STORE_NAME | varchar2 | 64 | 0 | Y | N |  | 药房名称 |
| 3 | SPELL_CODE | varchar2 | 16 | 0 | Y | N |  | 拼音码 |
| 4 | DEPT_CODE | varchar2 | 16 | 0 | Y | N |  | 科室编码 |
| 5 | WEST_DRUG | number | 1 | 0 | Y | N |  | 西药标记 |
| 6 | TRAD_DRUG | number | 1 | 0 | Y | N |  | 中成药标记 |
| 7 | HERBS_DRUG | number | 1 | 0 | Y | N |  | 草药标记 |
| 8 | ORG_CODE | varchar2 | 32 | 0 | Y | N |  | 机构编码 |
| 9 | VALID_STATE | number | 1 | 0 | Y | N |  | 有效性标志(1: 有效, 0: 无效) |
| 10 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 11 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建人id |
| 12 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建人姓名 |
| 13 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改人id |
| 14 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改人姓名 |
| 15 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改时间 |
| 16 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标志 0否 1是 |
| 17 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 18 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 19 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 20 | PACKAGE_TYPE | varchar2 | 8 | 0 | Y | N |  | 1 门诊 2 住院 3 未选择 |
| 21 | TWO_LEVEL_STORGE | number | 1 | 0 | Y | N | 0 | 二级库标识 0 否 1 是 |

### 15. MED_DICT_FACTORY（药品字典厂商）

- **表名**：`MED_DICT_FACTORY`
- **中文说明**：药品字典厂商
- **字段数**：23
- **主键字段**：FACTORY_CODE

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | FACTORY_ID | number | 19 | 0 | N | N |  |  |
| 2 | FACTORY_ABBR | varchar2 | 80 | 0 | N | N |  | 厂家简称 |
| 3 | FACTORY_NAME | varchar2 | 160 | 0 | N | N |  | 厂家全名 |
| 4 | SPELL_CODE | varchar2 | 50 | 0 | Y | N |  | 拼音简码 |
| 5 | WB_CODE | varchar2 | 50 | 0 | Y | N |  | 五笔编码 |
| 6 | FACTORY_ADDRESS | varchar2 | 160 | 0 | Y | N |  | 厂家地址 |
| 7 | TEL | varchar2 | 32 | 0 | Y | N |  | 联系电话 |
| 8 | DEL_FLAG | number | 1 | 0 | N | N | 0 | 作废标记 |
| 9 | ORG_CODE | varchar2 | 32 | 0 | Y | N |  | 机构编码 |
| 10 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 11 | FACTORY_CODE | varchar2 | 50 | 0 | N | Y |  | 厂家编码 |
| 12 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 13 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 14 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N | sysdate | 创建日期 |
| 15 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 16 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 17 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 18 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 19 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 20 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 21 | IS_IMPORTED | varchar2 | 1 | 0 | Y | N | 0 | 是否进口 0否 1是（默认0） |
| 22 | FOREIGN_NAME | varchar2 | 255 | 0 | Y | N |  | 国外名称 |
| 23 | LICENSE_HOLDER | varchar2 | 255 | 0 | Y | N |  | 上市许可持有人 |

### 16. MED_DICT_INTYPE（药品字典入库类型）

- **表名**：`MED_DICT_INTYPE`
- **中文说明**：药品字典入库类型
- **字段数**：18
- **主键字段**：IN_KIND

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | IN_KIND | varchar2 | 50 | 0 | N | Y |  | 入库方式 |
| 2 | KIND_NAME | varchar2 | 80 | 0 | N | N |  | 方式类型名称 |
| 3 | ID | number | 22 | 0 | N | N |  | ID |
| 4 | SPELL_CODE | varchar2 | 32 | 0 | Y | N |  | 拼音码 |
| 5 | DEL_FLAG | number | 1 | 0 | Y | N |  | 作废 |
| 6 | WB_CODE | varchar2 | 50 | 0 | Y | N |  | 五笔码 |
| 7 | NOTE | varchar2 | 255 | 0 | Y | N |  | 备注 |
| 8 | SHOW_FLAG | char | 1 | 0 | Y | N | 'Y' | 新增的时候是否显示 Y 显示 N 不显示 |
| 9 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 10 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 11 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 12 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 13 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 14 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 15 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 16 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 17 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 18 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |

### 17. MED_DICT_LOC（药品字典库位编码）

- **表名**：`MED_DICT_LOC`
- **中文说明**：药品字典库位编码
- **字段数**：10
- **主键字段**：ORG_CODE, STORE_CODE, LOC_CODE

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | LOC_ID | number | 20 | 0 | Y | N |  | 库位id |
| 2 | ORG_CODE | varchar2 | 50 | 0 | N | Y |  | 机构编码 |
| 3 | STORE_CODE | varchar2 | 50 | 0 | N | Y |  | 库房识别 |
| 4 | UP_CODE | varchar2 | 64 | 0 | Y | N |  | 上级编码 |
| 5 | LOC_CODE | varchar2 | 64 | 0 | N | Y |  | 库位编码 |
| 6 | SORT_NO | number | 18 | 0 | N | N |  | 库位编码等级 |
| 7 | LOC_NAME | varchar2 | 80 | 0 | Y | N |  | 库位名称 |
| 8 | SPELL_CODE | varchar2 | 16 | 0 | Y | N |  | 拼音简写 |
| 9 | WB_CODE | varchar2 | 16 | 0 | Y | N |  | 五笔编码 |
| 10 | MEMO | varchar2 | 160 | 0 | Y | N |  | 备注信息 |

### 18. MED_DICT_LOCRULE（药品字典库位编码规则）

- **表名**：`MED_DICT_LOCRULE`
- **中文说明**：药品字典库位编码规则
- **字段数**：5
- **主键字段**：ORG_CODE, STORE_CODE, SORT_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | Y |  | 机构ID |
| 2 | STORE_CODE | varchar2 | 16 | 0 | N | Y |  | 库房编码 |
| 3 | SORT_NO | number | 18 | 0 | N | Y |  | 编码级别(编码等级) |
| 4 | CODENAME | varchar2 | 80 | 0 | N | N |  | 编码名称 |
| 5 | CODELENGTH | number | 4 | 0 | N | N | 0 | 编码长度 |

### 19. MED_DICT_OUTTYPE（药品字典出库类型）

- **表名**：`MED_DICT_OUTTYPE`
- **中文说明**：药品字典出库类型
- **字段数**：19
- **主键字段**：OUT_TYPE_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | OUT_KIND_CODE | varchar2 | 50 | 0 | N | N |  | 出库方式 |
| 2 | KIND_NAME | varchar2 | 80 | 0 | N | N |  | 方式类型名称 |
| 3 | SPELL_CODE | varchar2 | 32 | 0 | Y | N |  | 拼音码 |
| 4 | OUT_TYPE | number | 1 | 0 | Y | N |  | 出库方式类型 |
| 5 | DEL_FLAG | number | 1 | 0 | Y | N |  | 作废 |
| 6 | SECOND_FLAG | number | 1 | 0 | Y | N |  | 二级库判别 |
| 7 | OUT_TYPE_ID | number | 20 | 0 | N | Y |  | 出库类型id |
| 8 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 9 | WB_CODE | varchar2 | 50 | 0 | Y | N |  | 五笔编码 |
| 10 | SHOW_FLAG | char | 1 | 0 | Y | N | 'Y' | 新增是否展示 是否为业务类型 Y展示 N不展示 |
| 11 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 12 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 13 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 14 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 15 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 16 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 17 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 18 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 19 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |

### 20. MED_DICT_PRICE（药品产地价格表）

- **表名**：`MED_DICT_PRICE`
- **中文说明**：药品产地价格表
- **字段数**：44
- **主键字段**：DRUG_PRI

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | DRUG_PRI | varchar2 | 50 | 0 | N | Y |  | 药品价格id(唯一主键) |
| 2 | DRUG_ID | varchar2 | 50 | 0 | N | N |  | med_dict_base的id，用来区分一个药品 |
| 3 | DRUG_CODE | varchar2 | 32 | 0 | N | N |  | med_dict_base的code，用来区分一个药品 |
| 4 | FACTORY_CODE | varchar2 | 32 | 0 | Y | N |  | 生产单位编码 |
| 5 | PACK_UNIT | varchar2 | 16 | 0 | Y | N |  | 包装单位 字典 |
| 6 | PACK_QTY | number | 10 | 4 | Y | N |  | 包装数量 |
| 7 | APPROVE_INFO | varchar2 | 32 | 0 | Y | N |  | 批文信息 |
| 8 | BAR_CODE | varchar2 | 64 | 0 | Y | N |  | 条形码，或者是商品二维码 |
| 9 | CLI_PACK | number | 12 | 4 | Y | N |  | 门诊包装 |
| 10 | CLI_UNIT | varchar2 | 32 | 0 | Y | N |  | 门诊包装单位 |
| 11 | INP_PACK | number | 12 | 4 | Y | N |  | 住院包装 |
| 12 | INP_UNIT | varchar2 | 32 | 0 | Y | N |  | 住院包装单位 |
| 13 | GB_CODE | varchar2 | 64 | 0 | Y | N |  | 国标码 |
| 14 | INSUR_CODE | varchar2 | 64 | 0 | Y | N |  | 医保编码 |
| 15 | TRADE_PRICE | number | 14 | 6 | N | N |  | 采购价 |
| 16 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 17 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 18 | SPECS | varchar2 | 64 | 0 | N | N |  | 药品规格 |
| 19 | PURCHASE_MODE | varchar2 | 32 | 0 | Y | N |  | 字典维护省采国采等（集采模式） |
| 20 | DEL_FLAG | number | 1 | 0 | Y | N | 0 | 作废标记 0 正常 1作废 |
| 21 | DRUG_SIGN | char | 1 | 0 | Y | N | '0' | 有效性标志 0在用 1停用 |
| 22 | SHOW_FLAG | number | 1 | 0 | Y | N | 1 | 大屏幕显示标记 0非屏幕显示 1为大屏幕显示，默认为1 |
| 23 | CLI_TOPLINE | number | 12 | 4 | Y | N |  | 门诊库存报警上限 |
| 24 | CLI_LOWLINE | number | 12 | 4 | Y | N |  | 门诊库存报警下限 |
| 25 | INP_TOPLINE | number | 12 | 4 | Y | N |  | 住院库存报警上限 |
| 26 | INP_LOWLINE | number | 12 | 4 | Y | N |  | 住院库存报警下限 |
| 27 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 28 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 29 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 30 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 31 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 32 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 33 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 34 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 35 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 36 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 37 | PLATFORM_DRUG_ID | varchar2 | 50 | 0 | Y | N |  | 省平台药品id |
| 38 | PACK_UNIT_NAME | varchar2 | 50 | 0 | Y | N |  | 单位名称 |
| 39 | SERIAL | varchar2 | 10 | 0 | Y | N |  | 包装序列号，数字越小对应的包装越小 |
| 40 | DRUG_SERIAL | varchar2 | 255 | 0 | Y | N |  | 药品价格组号 |
| 41 | CLI_USE | number | 1 | 0 | Y | N | 0 | 门诊药房使用 0 未使用 1 使用 |
| 42 | INP_USE | number | 1 | 0 | Y | N | 0 | 住院药房使用 0 未使用 1 使用 |
| 43 | STORAGE_USE | number | 1 | 0 | Y | N | 0 | 药库使用 0 未使用 1 使用 |
| 44 | PACK_BOX_QTY | number | 10 | 4 | Y | N |  | 包装箱数 |

### 21. MED_DICT_PRICE_RECORD（药品产地价格修改记录表）

- **表名**：`MED_DICT_PRICE_RECORD`
- **中文说明**：药品产地价格修改记录表
- **字段数**：4
- **主键字段**：UPDATE_PRICE_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | UPDATE_PRICE_ID | varchar2 | 50 | 0 | N | Y |  | 药价更新id |
| 2 | DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药价id |
| 3 | DRUG_UPDATE_RECORD_ID | varchar2 | 50 | 0 | Y | N |  | 药品修改记录id |
| 4 | PRICE_UPDATE_DATA | varchar2 | 1024 | 0 | Y | N |  | 药品价格表修改内容 |

### 22. MED_DICT_SUPPLIER（药品字典供货商）

- **表名**：`MED_DICT_SUPPLIER`
- **中文说明**：药品字典供货商
- **字段数**：20
- **主键字段**：SUPPLIER_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | SUPPLIER_CODE | varchar2 | 10 | 0 | N | N |  | 供货商编码 |
| 2 | SUPPLIER_ABBR | varchar2 | 80 | 0 | N | N |  | 供货商简称 |
| 3 | SUPPLIER_NAME | varchar2 | 160 | 0 | N | N |  | 供货商全名 |
| 4 | SPELL_CODE | varchar2 | 32 | 0 | Y | N |  | 拼音简码 |
| 5 | WB_CODE | varchar2 | 32 | 0 | Y | N |  | 五笔编码 |
| 6 | SUPPLIER_ADDRESS | varchar2 | 160 | 0 | Y | N |  | 供货商地址 |
| 7 | TEL | varchar2 | 32 | 0 | Y | N |  | 联系电话 |
| 8 | DEL_FLAG | number | 1 | 0 | N | N |  | 作废标记 |
| 9 | ORG_CODE | varchar2 | 32 | 0 | N | N |  | 机构编码 |
| 10 | SUPPLIER_ID | varchar2 | 50 | 0 | N | Y |  | 供应商id |
| 11 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 12 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 13 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 14 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 15 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 16 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 17 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 18 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 19 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 20 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |

### 23. MED_DRUG_LOC（药品库位对照表）

- **表名**：`MED_DRUG_LOC`
- **中文说明**：药品库位对照表
- **字段数**：6
- **主键字段**：BIND_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | BIND_ID | varchar2 | 20 | 0 | N | Y |  | 绑定id |
| 2 | ORG_CODE | varchar2 | 50 | 0 | Y | N |  | 机构编码 |
| 3 | STORE_CODE | varchar2 | 50 | 0 | Y | N |  | 库房识别 |
| 4 | LOC_CODE | varchar2 | 64 | 0 | Y | N |  | 库位编码 |
| 5 | DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药品主键 |
| 6 | LOC_ID | char | 20 | 0 | Y | N |  | 库位id |

### 24. MED_FIN_DAYDETAIL（财务月结明细表）

- **表名**：`MED_FIN_DAYDETAIL`
- **中文说明**：财务月结明细表
- **字段数**：13
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | number | 20 | 0 | N | Y |  | 记录序号 |
| 2 | FIN_ID | number | 20 | 0 | Y | N |  | 月结主键 |
| 3 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构编码 |
| 4 | STORE_CODE | varchar2 | 16 | 0 | N | N |  | 库房编码 |
| 5 | SETTLE_DAY | date | 7 | 0 | N | N |  | 结账天-日期 |
| 6 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品主键 |
| 7 | STORE_QUANTITY | number | 12 | 4 | N | N | 0 | 日结数量 |
| 8 | TRADE_PRICE | number | 14 | 6 | N | N |  | 采购价 |
| 9 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 10 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 11 | IN_COST | number | 12 | 4 | N | N | 0 | 进货金额 |
| 12 | WHOLESALE_COST | number | 12 | 4 | N | N | 0 | 批发金额 |
| 13 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售金额 |

### 25. MED_FIN_DAYSETTLE（财务月结主表）

- **表名**：`MED_FIN_DAYSETTLE`
- **中文说明**：财务月结主表
- **字段数**：7
- **主键字段**：FIN_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | FIN_ID | number | 30 | 0 | N | Y |  | 月结主键 |
| 2 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构编码 |
| 3 | STORE_CODE | varchar2 | 16 | 0 | Y | N |  | 库房编码 |
| 4 | SETTLE_DAY | date | 7 | 0 | Y | N |  | 结账天-日期 |
| 5 | START_TIME | timestamp(6) | 11 | 6 | N | N |  | 起始时间 |
| 6 | END_TIME | timestamp(6) | 11 | 6 | N | N |  | 终止时间 |
| 7 | SETTLE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 结账时间 |

### 26. MED_FIN_MONTHDETAIL（财务月结明细表）

- **表名**：`MED_FIN_MONTHDETAIL`
- **中文说明**：财务月结明细表
- **字段数**：23
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | number | 20 | 0 | N | Y |  | 记录序号 |
| 2 | FIN_ID | number | 20 | 0 | Y | N |  | 月结主键 |
| 3 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构编码 |
| 4 | STORE_CODE | varchar2 | 16 | 0 | N | N |  | 库房编码 |
| 5 | SETTLE_MONTH | date | 7 | 0 | N | N |  | 结账月份 |
| 6 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品主键 |
| 7 | STORE_QUANTITY | number | 12 | 4 | N | N | 0 | 月结数量 |
| 8 | TRADE_PRICE | number | 14 | 6 | N | N |  | 采购价 |
| 9 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 10 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 11 | IN_COST | number | 12 | 4 | N | N | 0 | 进货金额 |
| 12 | WHOLESALE_COST | number | 12 | 4 | N | N | 0 | 批发金额 |
| 13 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售金额 |
| 14 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 15 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 16 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 17 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 18 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 19 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 20 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 21 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 22 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 23 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |

### 27. MED_FIN_MONTHSETTLE（财务月结主表）

- **表名**：`MED_FIN_MONTHSETTLE`
- **中文说明**：财务月结主表
- **字段数**：19
- **主键字段**：FIN_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | FIN_ID | number | 30 | 0 | N | Y |  | 月结主键 |
| 2 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构编码 |
| 3 | STORE_CODE | varchar2 | 16 | 0 | Y | N |  | 库房编码 |
| 4 | SETTLE_MONTH | date | 7 | 0 | Y | N |  | 结账月份 |
| 5 | START_TIME | timestamp(6) | 11 | 6 | N | N |  | 起始时间 |
| 6 | END_TIME | timestamp(6) | 11 | 6 | N | N |  | 终止时间 |
| 7 | SETTLE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 结账时间 |
| 8 | SETTLE_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 结账人员姓名 |
| 9 | SETTLE_OPER_CODE | varchar2 | 50 | 0 | Y | N |  | 结账人员 |
| 10 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 11 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 12 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 13 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 14 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 15 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 16 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 17 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 18 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 19 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |

### 28. MED_INIT_ACCOUNT（药库初始化建账表）

- **表名**：`MED_INIT_ACCOUNT`
- **中文说明**：药库初始化建账表
- **字段数**：35
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ID | number | 19 | 0 | N | Y |  | 主键ID |
| 2 | DRUG_ID | varchar2 | 100 | 0 | N | N |  | 药品id |
| 3 | DRUG_CODE | varchar2 | 100 | 0 | N | N |  | 药品编码 |
| 4 | DRUG_NAME | varchar2 | 100 | 0 | N | N |  | 药品名称 |
| 5 | USAGE | varchar2 | 50 | 0 | Y | N |  | 默认用法编码 |
| 6 | FREQUENCY | varchar2 | 50 | 0 | Y | N |  | 默认频次编码 |
| 7 | DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药品价格id |
| 8 | SPECS | varchar2 | 64 | 0 | Y | N |  | 药品规格 |
| 9 | PACK_UNIT_NAME | varchar2 | 50 | 0 | Y | N |  | 单位名称 |
| 10 | TRADE_PRICE | number | 14 | 4 | Y | N |  | 采购价 |
| 11 | RETAIL_PRICE | number | 14 | 4 | Y | N |  | 零售价 |
| 12 | WHOLESALE_PRICE | number | 14 | 4 | Y | N |  | 批发价 |
| 13 | STORAGE_QUANTITY | number | 12 | 4 | Y | N |  | 库存数量 |
| 14 | STORAGE_COST | number | 12 | 4 | Y | N |  | 采购金额 |
| 15 | WHOLESALE_COST | number | 12 | 4 | Y | N |  | 批发金额 |
| 16 | RETAIL_COST | number | 12 | 4 | Y | N |  | 零售金额 |
| 17 | PRODUCT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 生产日期 |
| 18 | EXPIRE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 药品效期 |
| 19 | BATCH_NO | varchar2 | 50 | 0 | Y | N |  | 药品批号 |
| 20 | LOC_CODE | varchar2 | 2000 | 0 | Y | N |  | 库位编码 |
| 21 | DRUG_LOC | varchar2 | 255 | 0 | Y | N |  | 库位 |
| 22 | STORE_CODE | varchar2 | 255 | 0 | Y | N |  | 库房识别码 |
| 23 | FACTORY_ID | number | 19 | 0 | Y | N |  | 药品厂家ID |
| 24 | FACTORY_NAME | varchar2 | 160 | 0 | Y | N |  | 厂家全名 |
| 25 | TAKE_EFFECT_FLAG | number | 1 | 0 | Y | N | 0 | 生效标记：0暂存、1生效 |
| 26 | IS_DELETED | number | 1 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 27 | CREATE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 创建者id |
| 28 | CREATE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 创建者姓名 |
| 29 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 30 | MODIFY_USER_ID | varchar2 | 30 | 0 | Y | N |  | 修改者id |
| 31 | MODIFY_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 修改者姓名 |
| 32 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 33 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 34 | DELETE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 删除人id |
| 35 | DELETE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 删除人姓名 |

### 29. MED_IN_DETAIL（采购入库明细表）

- **表名**：`MED_IN_DETAIL`
- **中文说明**：采购入库明细表
- **字段数**：40
- **主键字段**：SORT_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构ID |
| 2 | SORT_NO | varchar2 | 30 | 0 | N | Y |  | 记录序号 |
| 3 | STORE_CODE | varchar2 | 16 | 0 | N | N |  | 库房识别 |
| 4 | IN_KIND | varchar2 | 50 | 0 | N | N |  | 入库方式，MED_DICT_INTYPE.IN_KIND |
| 5 | IN_BILLNO | varchar2 | 50 | 0 | N | N |  | 入库单号,IN_BILLNO |
| 6 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品主键,MED_DICT_PRICE.DRUG_PRI |
| 7 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  | 药品批号 |
| 8 | EXPIRE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 药品效期 |
| 9 | TRADE_PRICE | number | 14 | 6 | N | N |  | 采购价 |
| 10 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 11 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 12 | IN_QUANTITY | number | 12 | 4 | N | N | 0 | 入库数量 |
| 13 | PASS_QUANTITY | number | 12 | 4 | N | N | 0 | 合格数量 |
| 14 | IN_COST | number | 12 | 4 | N | N | 0 | 进货金额合计 |
| 15 | WHOLESALE_COST | number | 12 | 4 | N | N | 0 | 批发金额 |
| 16 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售金额 |
| 17 | BILLNO | varchar2 | 32 | 0 | Y | N |  | 发票号码 |
| 18 | STORE_TYPE | number | 6 | 0 | Y | N |  | 库存性质 |
| 19 | DISCOUNT | number | 12 | 4 | Y | N |  | 折让金额 |
| 20 | CHECK_NO | varchar2 | 32 | 0 | Y | N |  | 验收单号 |
| 21 | CHECK_OPER | varchar2 | 16 | 0 | Y | N |  | 验收工号 |
| 22 | CHECK_DATE | timestamp(6) | 11 | 6 | Y | N |  | 验收日期 |
| 23 | STORE_ID | varchar2 | 50 | 0 | N | N | 0 | 库存ID，PHA_STORAGE.RECORD_NO |
| 24 | PLAN_SORTNO | number | 18 | 0 | Y | N |  | 计划识别序号 |
| 25 | NOTE_NO | varchar2 | 64 | 0 | Y | N |  | 运货单号 |
| 26 | PRODUCT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 生产日期 |
| 27 | DRUG_LOC | varchar2 | 1000 | 0 | Y | N |  | 货位编码 |
| 28 | PDA_STATE | number | 1 | 0 | Y | N | 0 | 入库状态 |
| 29 | DRUG_SERIAL | varchar2 | 255 | 0 | Y | N |  | 包装组号 |
| 30 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 31 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 32 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 33 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 34 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 35 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 36 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 37 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 38 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 39 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 40 | LOC_CODES | varchar2 | 2000 | 0 | Y | N |  | 货位编码长 |

### 30. MED_IN_MASTER（采购入库主表）

- **表名**：`MED_IN_MASTER`
- **中文说明**：采购入库主表
- **字段数**：31
- **主键字段**：IN_BILLNO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | N |  | 机构编码 |
| 2 | IN_BILLNO | varchar2 | 50 | 0 | N | Y |  | 入库单号 |
| 3 | IN_KIND | varchar2 | 50 | 0 | N | N |  | 入库方式，MED_DICT_INTYPE.IN_KIND类型 |
| 4 | PLAN_BILLNO | varchar2 | 32 | 0 | Y | N |  | 计划单号 |
| 5 | STORE_CODE | varchar2 | 16 | 0 | N | N |  | 库房编码 |
| 6 | IN_STATE | number | 1 | 0 | Y | N |  | 单据状态 0已付款 1待付款 2待验收 3部分付款 4已作废 |
| 7 | IN_DATE | timestamp(6) | 11 | 6 | Y | N |  | 入库日期 |
| 8 | IN_OPER | varchar2 | 16 | 0 | Y | N |  | 入库人 |
| 9 | SUPPLIER_CODE | varchar2 | 32 | 0 | Y | N |  | 供货商 |
| 10 | EXECUTE_OPER | varchar2 | 16 | 0 | Y | N |  | 执行人 |
| 11 | EXECUTE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 执行日期 |
| 12 | CANCELER | varchar2 | 16 | 0 | Y | N |  | 作废人 |
| 13 | CANCEL_DATE | timestamp(6) | 11 | 6 | Y | N |  | 作废日期 |
| 14 | MEMO | varchar2 | 120 | 0 | Y | N |  | 备注信息 |
| 15 | PAY_ORDER_NO | number | 18 | 0 | Y | N |  | 付款记录号 |
| 16 | NOTE_NO | varchar2 | 64 | 0 | Y | N |  | 发货单号 |
| 17 | BILLNO | varchar2 | 50 | 0 | Y | N |  | 发票号码 |
| 18 | PLAN_OPER | varchar2 | 50 | 0 | Y | N |  | 计划人 |
| 19 | CHECK_NO | varchar2 | 50 | 0 | Y | N |  | 盘点单号 |
| 20 | IN_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 入库人 |
| 21 | IN_OUT_BILLNO | varchar2 | 50 | 0 | Y | N |  | 出库单号 如药房申请发药流程，药房入库单->药库出库单 |
| 22 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 23 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 24 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 25 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 26 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 27 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 28 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 29 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 30 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 31 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |

### 31. MED_IN_PAY（财务验收付款主表）

- **表名**：`MED_IN_PAY`
- **中文说明**：财务验收付款主表
- **字段数**：21
- **主键字段**：ORG_CODE, ORDER_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | Y | '1' | 机构编码 |
| 2 | ORDER_NO | number | 18 | 0 | N | Y |  | 付款编码 |
| 3 | SUPPLIER_CODE | varchar2 | 32 | 0 | N | N |  | 供货商编码 |
| 4 | PAY_OPER | varchar2 | 16 | 0 | Y | N |  | 付款工号 |
| 5 | PAY_DATE | timestamp(6) | 11 | 6 | Y | N |  | 付款日期 |
| 6 | PAY_BILL | varchar2 | 120 | 0 | Y | N |  | 凭证号码 |
| 7 | PAY_COST | number | 12 | 2 | N | N | 0. | 付款金额 |
| 8 | PAY_METHOD | varchar2 | 80 | 0 | Y | N | '0.00' | 付款方式 |
| 9 | MEMO | varchar2 | 120 | 0 | Y | N |  | 备注信息 |
| 10 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 11 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 12 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 13 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 14 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 15 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 16 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 17 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 18 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 19 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 20 | ID | number | 19 | 0 | Y | N |  | id |
| 21 | IN_SUMCOST | number | 22 | 6 | Y | N |  | 订单总额 |

### 32. MED_IN_PAYDETAIL（财务验收付款明细表）

- **表名**：`MED_IN_PAYDETAIL`
- **中文说明**：财务验收付款明细表
- **字段数**：19
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构编码 |
| 2 | STORE_CODE | varchar2 | 16 | 0 | Y | N |  | 库房编码 |
| 3 | ORDER_NO | number | 18 | 0 | Y | N |  | 付款单号 |
| 4 | IN_BILLNO | varchar2 | 50 | 0 | Y | N |  | 入库单号 |
| 5 | IN_SUMCOST | number | 12 | 4 | N | N | 0 | 订单总额 |
| 6 | PAY_THIS | number | 12 | 4 | N | N | 0 | 本次付款 |
| 7 | PAY_READY | number | 12 | 4 | N | N | 0 | 已付金额 |
| 8 | MEMO | varchar2 | 120 | 0 | Y | N |  | 备注信息 |
| 9 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 10 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 11 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 12 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 13 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 14 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 15 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 16 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 17 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 18 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 19 | ID | number | 19 | 0 | N | Y |  | id |

### 33. MED_IN_PLAN（采购计划主表）

- **表名**：`MED_IN_PLAN`
- **中文说明**：采购计划主表
- **字段数**：34
- **主键字段**：ORG_CODE, PLAN_BILLNO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PLAN_ID | varchar2 | 50 | 0 | Y | N |  | 计划id |
| 2 | ORG_CODE | varchar2 | 32 | 0 | N | Y |  | 机构编码 |
| 3 | PLAN_BILLNO | varchar2 | 50 | 0 | N | Y |  | 计划单号 |
| 4 | STORE_CODE | varchar2 | 16 | 0 | N | N |  | 库房编码 |
| 5 | BILL_STATE | number | 1 | 0 | Y | N |  | 计划状态 |
| 6 | PLAN_DATE | timestamp(6) | 11 | 6 | Y | N |  | 计划日期 |
| 7 | PLAN_OPER | varchar2 | 16 | 0 | Y | N |  | 计划人 |
| 8 | CHECK_OPER | varchar2 | 16 | 0 | Y | N |  | 审核人 |
| 9 | CHECK_DATE | timestamp(6) | 11 | 6 | Y | N |  | 审核日期 |
| 10 | EXECUTE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 执行日期 |
| 11 | EXECUTE_OPER | varchar2 | 16 | 0 | Y | N |  | 执行人 |
| 12 | CANCEL_OPER | varchar2 | 16 | 0 | Y | N |  | 作废人 |
| 13 | CANCEL_DATE | timestamp(6) | 11 | 6 | Y | N |  | 作废日期 |
| 14 | MEMO | varchar2 | 160 | 0 | Y | N |  | 备注信息 |
| 15 | OPERATOR | varchar2 | 16 | 0 | Y | N |  | 操作人 |
| 16 | OPER_DATE | timestamp(6) | 11 | 6 | Y | N |  | 操作时间 |
| 17 | PLAN_TYPE | varchar2 | 50 | 0 | Y | N |  | 计划类型 |
| 18 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 19 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 20 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 21 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 22 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 23 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 24 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 25 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 26 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 27 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 28 | CHECK_STATE | number | 10 | 0 | Y | N | 2 | 审核状态 1 通过 2驳回 |
| 29 | CHECK_OPER_CODE | varchar2 | 50 | 0 | Y | N |  | 审核人编码 |
| 30 | EXECUTE_OPER_CODE | varchar2 | 50 | 0 | Y | N |  | 执行人编码 |
| 31 | CANCEL_OPER_CODE | varchar2 | 50 | 0 | Y | N |  | 作废人编码 |
| 32 | OPERATOR_CODE | varchar2 | 50 | 0 | Y | N |  | 操作人编码 |
| 33 | PLAN_OPER_CODE | varchar2 | 50 | 0 | Y | N |  | 计划人编号 |
| 34 | CHECK_FAIL_REASON | char | 1000 | 0 | Y | N |  | 驳回原因 |

### 34. MED_IN_PLAN_DETAIL（采购计划明细表）

- **表名**：`MED_IN_PLAN_DETAIL`
- **中文说明**：采购计划明细表
- **字段数**：19

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PDETAIL_ID | varchar2 | 50 | 0 | Y | N |  | 明细id |
| 2 | PLAN_ID | varchar2 | 50 | 0 | Y | N |  | 计划id |
| 3 | PLAN_BILLNO | varchar2 | 50 | 0 | Y | N |  | 计划单号 |
| 4 | DRUG_PRI | varchar2 | 32 | 0 | N | N |  | 药品主键 |
| 5 | REF_PRICE | number | 14 | 6 | N | N |  | 参考采购价 |
| 6 | BUY_PRICE | number | 14 | 6 | N | N |  | 计划采购价 |
| 7 | PLAN_QUANTITY | number | 12 | 4 | N | N |  | 计划采购数量 |
| 8 | CHECK_QUANTITY | number | 12 | 4 | Y | N |  | 审核采购数量 |
| 9 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 10 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 11 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 12 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N | SYSDATE | 创建日期 |
| 13 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 14 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 15 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 16 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 17 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 18 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 19 | ORDER_NO | number | 0 | -127 | Y | N |  | 药品明细号 |

### 35. MED_OUT_DETAIL（出库信息明细表）

- **表名**：`MED_OUT_DETAIL`
- **中文说明**：出库信息明细表
- **字段数**：33
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 2 | RECORD_NO | number | 30 | 0 | N | Y |  | 识别序号 |
| 3 | OUT_KIND | varchar2 | 50 | 0 | N | N |  | 出库方式类型 |
| 4 | STORE_CODE | varchar2 | 50 | 0 | N | N |  | 药库识别 |
| 5 | OUT_BILLNO | varchar2 | 32 | 0 | N | N |  | 出库单号 |
| 6 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品主键 |
| 7 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  | 药品批号 |
| 8 | EXPIRE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 药品效期 |
| 9 | WHOLESALE_PRICE | number | 14 | 6 | Y | N | 0 | 批发价格 |
| 10 | RETAIL_PRICE | number | 14 | 6 | N | N | 0 | 零售价格 |
| 11 | TRADE_PRICE | number | 14 | 6 | N | N | 0 | 采购价格 |
| 12 | REQUEST_QUANTITY | number | 12 | 4 | N | N | 0 | 申请数量 |
| 13 | SEND_QUANTITY | number | 12 | 4 | N | N | 0 | 实发数量 |
| 14 | STORE_TYPE | number | 6 | 0 | Y | N |  | 库存性质 |
| 15 | IN_COST | number | 12 | 4 | N | N | 0 | 进货金额 |
| 16 | WHOLESALE_COST | number | 12 | 4 | N | N | 0 | 批发金额 |
| 17 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售金额 |
| 18 | STORE_ID | varchar2 | 50 | 0 | N | N | 0 | 库存识别ID |
| 19 | PHA_ID | varchar2 | 50 | 0 | Y | N |  | 药房库存ID（PHA_STORAGE的主键） |
| 20 | PRODUCT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 生产日期 |
| 21 | PDA_STATE | number | 1 | 0 | Y | N | 0 | 出库状态 0：未出库 1：已出库 |
| 22 | DRUG_LOC | varchar2 | 1000 | 0 | Y | N |  | 库位 |
| 23 | CREATE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 创建人id |
| 24 | CREATE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 创建人姓名 |
| 25 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 26 | MODIFY_USER_ID | varchar2 | 30 | 0 | Y | N |  | 修改人id |
| 27 | MODIFY_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 修改人姓名 |
| 28 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改时间 |
| 29 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0否1是 |
| 30 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 31 | DELETE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 删除人id |
| 32 | DELETE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 删除人姓名 |
| 33 | DRUG_SERIAL | varchar2 | 50 | 0 | Y | N |  | 包装序列号 |

### 36. MED_OUT_MASTER（出库信息主表）

- **表名**：`MED_OUT_MASTER`
- **中文说明**：出库信息主表
- **字段数**：36
- **主键字段**：OUT_BILLNO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 2 | OUT_BILLNO | varchar2 | 32 | 0 | N | Y |  | 出库单号 |
| 3 | OUT_KIND | varchar2 | 50 | 0 | N | N |  | 出库方式类型 |
| 4 | STORE_CODE | varchar2 | 16 | 0 | N | N |  | 出库库房 |
| 5 | OUT_STATE | number | 1 | 0 | N | N | 0 | 出库状态 0：未出库 1：已出库 2:已驳回 |
| 6 | REQUEST_DATE | timestamp(6) | 11 | 6 | Y | N |  | 申请日期 |
| 7 | REQUEST_STATE | number | 1 | 0 | N | N | 0 | 申请状态 0：药房未提交 1：药房已提交 |
| 8 | OUT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 出库日期 |
| 9 | OUT_OPER | varchar2 | 16 | 0 | Y | N |  | 操作工号 |
| 10 | OUT_CHECKOPER | varchar2 | 16 | 0 | Y | N |  | 确认工号 |
| 11 | PHA_CODE | varchar2 | 16 | 0 | N | N | '0' | 申领/入库药房 |
| 12 | CHECKIN_DATE | timestamp(6) | 11 | 6 | Y | N |  | 入库日期 |
| 13 | CHECKIN_STATE | number | 1 | 0 | N | N | 0 | 入库状态 0未入库 1 已入库 |
| 14 | CHECKIN_OPER | varchar2 | 16 | 0 | Y | N |  | 入库人 |
| 15 | MEMO | varchar2 | 64 | 0 | Y | N |  | 出库备注 |
| 16 | CREATE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 创建人id |
| 17 | CREATE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 创建人姓名 |
| 18 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 19 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改人id |
| 20 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改人姓名 |
| 21 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改时间 |
| 22 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0否1是 |
| 23 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 24 | DELETE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 删除人id |
| 25 | DELETE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 删除人姓名 |
| 26 | RETURN_REASON | varchar2 | 64 | 0 | Y | N |  | 退回原因 |
| 27 | PHA_NAME | varchar2 | 50 | 0 | Y | N |  | 申领/入库药房名称 |
| 28 | RETURN_FLAG | number | 1 | 0 | Y | N | 0 | 药房申请退药标识 1 申请发药 |
| 29 | REQUEST_OPER | varchar2 | 50 | 0 | Y | N |  | 申请人 |
| 30 | REQUEST_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 申请人名称 |
| 31 | REQUEST_FLAG | number | 1 | 0 | Y | N | 0 | 申请发药标识 0 正常 1 药房申请发药 |
| 32 | OUT_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 药库出库人名称 |
| 33 | OUT_CHECKOPER_NAME | varchar2 | 50 | 0 | Y | N |  | 出库检查人姓名 |
| 34 | CHECKIN_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 药房审核人名称 |
| 35 | STORE_NAME | varchar2 | 50 | 0 | Y | N |  | 当前登录科室或药房 |
| 36 | IN_OUT_BILLNO | varchar2 | 50 | 0 | Y | N |  | 出入库单号 |

### 37. MED_PHARMACY

- **表名**：`MED_PHARMACY`
- **字段数**：4
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ID | varchar2 | 50 | 0 | N | Y |  | ID 主键 |
| 2 | NAME | varchar2 | 255 | 0 | Y | N |  | 名称 |
| 3 | CODE | varchar2 | 255 | 0 | Y | N |  | 编码 |
| 4 | PARENTID | varchar2 | 50 | 0 | Y | N |  | 父级ID |

### 38. MED_STORAGE（药品库存信息）

- **表名**：`MED_STORAGE`
- **中文说明**：药品库存信息
- **字段数**：29
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | varchar2 | 50 | 0 | N | Y |  | 记录序号 |
| 2 | STORE_CODE | varchar2 | 16 | 0 | N | N |  | 库房识别 |
| 3 | ORG_CODE | varchar2 | 32 | 0 | N | N |  | 机构编码 |
| 4 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品主键 |
| 5 | BATCH_NO | varchar2 | 50 | 0 | Y | N |  | 药品批号 |
| 6 | EXPIRE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 药品效期 |
| 7 | TRADE_PRICE | number | 14 | 6 | N | N |  | 采购价 |
| 8 | RETAIL_PRICE | number | 14 | 6 | Y | N |  | 零售价 |
| 9 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 10 | STORAGE_QUANTITY | number | 12 | 4 | Y | N |  | 库存数量 |
| 11 | STORAGE_COST | number | 12 | 4 | Y | N |  | 进货金额 |
| 12 | WHOLESALE_COST | number | 12 | 4 | Y | N |  | 批发金额 |
| 13 | RETAIL_COST | number | 12 | 4 | Y | N |  | 零售金额 |
| 14 | DRUG_LOC | varchar2 | 1000 | 0 | Y | N |  | 货位编码 双向同步，修改货位同步库存和货位管理药品的货位 |
| 15 | STORAGE_TOPLINE | number | 12 | 4 | Y | N |  | 库存报警上限 双向同步，修改上限同步库存的上限和货位下药品的上限 |
| 16 | STORAGE_LOWLINE | number | 12 | 4 | Y | N |  | 库存报警下限 双向同步，修改下限同步库存和货位的下限 |
| 17 | PRODUCT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 生产日期 |
| 18 | STORE_TYPE | number | 4 | 0 | Y | N |  | 库存性质 门户字典store_type，霉变、破损等 |
| 19 | IS_ENABLE | char | 1 | 0 | Y | N | 'Y' | 启用状态：Y启用、N禁用 |
| 20 | CREATE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 创建人id |
| 21 | CREATE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 创建人姓名 |
| 22 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 23 | MODIFY_USER_ID | varchar2 | 30 | 0 | Y | N |  | 修改人id |
| 24 | MODIFY_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 修改人名称 |
| 25 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 26 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标志 0否1是 |
| 27 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 28 | DELETE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 删除人id |
| 29 | DELETE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 删除人名称 |

### 39. MED_TRACE_RECORD（药品追溯码记录表）

- **表名**：`MED_TRACE_RECORD`
- **中文说明**：药品追溯码记录表
- **字段数**：26
- **主键字段**：RECORD_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构id |
| 2 | RECORD_ID | varchar2 | 32 | 0 | N | Y |  | 记录序号 |
| 3 | STORE_CODE | varchar2 | 32 | 0 | Y | N |  | 科室编码 |
| 4 | TRACE_BILLNO | varchar2 | 32 | 0 | Y | N |  | 追溯码对应业务单号(门诊发药对应的是处方号？) |
| 5 | DRUG_PRI | varchar2 | 32 | 0 | Y | N |  | 药品主键 |
| 6 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  | 药品批号 |
| 7 | EXPIRE_DATE | date | 7 | 0 | Y | N |  | 药品效期 |
| 8 | PRODUCT_DATE | date | 7 | 0 | Y | N |  | 生产日期 |
| 9 | STORE_ID | varchar2 | 18 | 0 | Y | N | 0 | 库存id |
| 10 | F_TRACE_CODE | varchar2 | 32 | 0 | Y | N |  | 一级追溯码 大码 |
| 11 | S_TRACE_CODE | varchar2 | 32 | 0 | Y | N |  | 二级追溯码 中码 |
| 12 | T_TRACE_CODE | varchar2 | 32 | 0 | Y | N |  | 三级追溯码 小码 |
| 13 | DRUG_ID | varchar2 | 32 | 0 | Y | N |  | 药品编码 不同厂家 药品编码相同 |
| 14 | PRICE | number | 20 | 0 | Y | N |  | 价格 |
| 15 | CREATE_USER_ID | varchar2 | 255 | 0 | Y | N |  | 创建者id |
| 16 | CREATE_USER_NAME | varchar2 | 255 | 0 | Y | N |  | 创建者姓名 |
| 17 | CREATE_TIME | date | 7 | 0 | Y | N |  | 创建日期 |
| 18 | MODIFY_USER_ID | varchar2 | 255 | 0 | Y | N |  | 修改者ID |
| 19 | MODIFY_USER_NAME | varchar2 | 255 | 0 | Y | N |  | 修改者姓名 |
| 20 | MODIFY_TIME | date | 7 | 0 | Y | N |  | 修改日期 |
| 21 | IS_DELETED | number | 2 | 0 | Y | N | 0 | 删除标识0未删除 1删除 |
| 22 | DELETE_USER_ID | varchar2 | 255 | 0 | Y | N |  | 删除id |
| 23 | DELETE_USER_NAME | varchar2 | 255 | 0 | Y | N |  | 删除人名称 |
| 24 | DELETE_TIME | date | 7 | 0 | Y | N |  | 删除时间 |
| 25 | KIND_TYPE | varchar2 | 255 | 0 | Y | N |  | 出入库类型 |
| 26 | IN_OUT_TYPE | varchar2 | 255 | 0 | Y | N |  | 出入库类型 IN 入库 OUT 出库 |

### 40. MED_TRACE_STORGE（药品追溯码库存表）

- **表名**：`MED_TRACE_STORGE`
- **中文说明**：药品追溯码库存表
- **字段数**：22
- **主键字段**：RECORD_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构id |
| 2 | RECORD_ID | varchar2 | 32 | 0 | N | Y |  | 记录序号 |
| 3 | STORE_CODE | varchar2 | 32 | 0 | Y | N |  | 科室编码 |
| 4 | DRUG_PRI | varchar2 | 32 | 0 | Y | N |  | 药品主键 |
| 5 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  | 药品批号 |
| 6 | EXPIRE_DATE | date | 7 | 0 | Y | N |  | 药品效期 |
| 7 | PRODUCT_DATE | date | 7 | 0 | Y | N |  | 生产日期 |
| 8 | STORE_ID | varchar2 | 32 | 0 | Y | N | 0 | 库存id |
| 9 | F_TRACE_CODE | varchar2 | 32 | 0 | Y | N |  | 一级追溯码 大码 |
| 10 | S_TRACE_CODE | varchar2 | 32 | 0 | Y | N |  | 二级追溯码 中码 |
| 11 | T_TRACE_CODE | varchar2 | 32 | 0 | Y | N |  | 三级追溯码 小码 |
| 12 | DRUG_ID | varchar2 | 32 | 0 | Y | N |  | 药品编码 不同厂家 药品编码相同 |
| 13 | CREATE_USER_ID | varchar2 | 255 | 0 | Y | N |  | 创建者id |
| 14 | CREATE_USER_NAME | varchar2 | 255 | 0 | Y | N |  | 创建者姓名 |
| 15 | CREATE_TIME | date | 7 | 0 | Y | N |  | 创建日期 |
| 16 | MODIFY_USER_ID | varchar2 | 255 | 0 | Y | N |  | 修改者ID |
| 17 | MODIFY_USER_NAME | varchar2 | 255 | 0 | Y | N |  | 修改者姓名 |
| 18 | MODIFY_TIME | date | 7 | 0 | Y | N |  | 修改日期 |
| 19 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识0未删除 1删除 |
| 20 | DELETE_USER_ID | varchar2 | 255 | 0 | Y | N |  | 删除id |
| 21 | DELETE_USER_NAME | varchar2 | 255 | 0 | Y | N |  | 删除人名称 |
| 22 | DELETE_TIME | date | 7 | 0 | Y | N |  | 删除时间 |

### 41. MESSAGE_CENTER（PDA消息提醒）

- **表名**：`MESSAGE_CENTER`
- **中文说明**：PDA消息提醒
- **字段数**：7

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | number | 18 | 0 | N | N |  | 记录序号 |
| 2 | STORE_CODE | varchar2 | 16 | 0 | Y | N |  | 药库编码 |
| 3 | ORG_CODE | varchar2 | 32 | 0 | Y | N |  | 机构编码 |
| 4 | MSG_TYPE | number | 1 | 0 | Y | N |  | 消息类型 |
| 5 | MSG_DATE | date | 7 | 0 | Y | N |  | 消息日期 |
| 6 | READ_FLAG | number | 1 | 0 | Y | N | 0 |  |
| 7 | CODE_NO | varchar2 | 32 | 0 | Y | N |  |  |

### 42. PHA_ALLOCAT_MASTER（药房调拨主表）

- **表名**：`PHA_ALLOCAT_MASTER`
- **中文说明**：药房调拨主表
- **字段数**：25
- **主键字段**：REQUEST_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构编码 |
| 2 | REQUEST_NO | varchar2 | 50 | 0 | N | Y |  | 调拨申请单号 |
| 3 | REQUEST_PHA | varchar2 | 16 | 0 | Y | N |  | 申请药房 |
| 4 | SEND_PHA | varchar2 | 16 | 0 | Y | N |  | 目标药房 |
| 5 | REUEST_DATE | timestamp(6) | 11 | 6 | Y | N |  | 申请日期 |
| 6 | OPER | varchar2 | 16 | 0 | Y | N |  | 操作人工号 |
| 7 | SUBMIT_FLAG | number | 1 | 0 | Y | N | 0 | 提交标志 |
| 8 | OUT_FLAG | number | 1 | 0 | Y | N | 0 | 出库标志 0 未入库 1 已入库 |
| 9 | OUT_OPER | varchar2 | 16 | 0 | Y | N |  | 出库工号 |
| 10 | OUT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 出库日期 |
| 11 | IN_FLAG | number | 1 | 0 | Y | N | 0 | 入库标志 |
| 12 | IN_OPER | varchar2 | 16 | 0 | Y | N |  | 入库人工号 |
| 13 | IN_DATE | timestamp(6) | 11 | 6 | Y | N |  | 入库日期 |
| 14 | RETURN_FLAG | number | 1 | 0 | N | N | 0 | 退药判别 0：未退药 1：已退药 |
| 15 | MEMO | varchar2 | 64 | 0 | Y | N |  | 备注信息 |
| 16 | OUT_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 出库人名称 |
| 17 | OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 操作人姓名 |
| 18 | IN_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 入库人姓名 |
| 19 | RETURN_REASON | varchar2 | 4000 | 0 | Y | N |  | 驳回原因 |
| 20 | REQUEST_PHA_NAME | varchar2 | 50 | 0 | Y | N |  | 申请药房名称 |
| 21 | SEND_PHA_NAME | varchar2 | 50 | 0 | Y | N |  | 目标药房名称 |
| 22 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 23 | CURR_STATE | number | 1 | 0 | Y | N |  | 当前状态 1 已保存 2已提交 3 审核通过（目标已出库-申请方待入库） 4 已驳回 5 已入库 |
| 24 | CREATE_USER | varchar2 | 50 | 0 | Y | N |  | 创建人 |
| 25 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建人姓名 |

### 43. PHA_ALOOCAT_DETAIL（药房调拨明细表）

- **表名**：`PHA_ALOOCAT_DETAIL`
- **中文说明**：药房调拨明细表
- **字段数**：28
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | number | 30 | 0 | N | Y |  | 记录序号 |
| 2 | ORG_CODE | varchar2 | 50 | 0 | Y | N | '1' | 机构编码 |
| 3 | REQUEST_NO | varchar2 | 50 | 0 | Y | N |  | 调拨申请单号 |
| 4 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品主键 |
| 5 | DRUG_QUANTITY | number | 12 | 4 | N | N | 0 | 申请药品数量 |
| 6 | REQUEST_PACKAGE | number | 4 | 0 | N | N | 1 | 申请药房包装 |
| 7 | REQUEST_SPECS | varchar2 | 64 | 0 | Y | N |  | 申请药房规格 |
| 8 | REQUEST_UNIT | varchar2 | 100 | 0 | Y | N |  | 申请药房单位 |
| 9 | CHECK_QUANTITY | number | 12 | 4 | N | N | 0 | 目标药房确认数量 |
| 10 | CHECK_PACKAGE | number | 4 | 0 | N | N | 1 | 目标药房确认包装 |
| 11 | CHECK_SPECS | varchar2 | 100 | 0 | Y | N |  | 目标药房确认规格 |
| 12 | CHECK_UNIT | varchar2 | 100 | 0 | Y | N |  | 目标药房确认单位 |
| 13 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  | 药品批号 |
| 14 | EXPIRE_DATE | date | 7 | 0 | Y | N |  | 药品效期 |
| 15 | PRODUCT_DATE | date | 7 | 0 | Y | N |  | 生产日期 |
| 16 | TRADE_PRICE | number | 14 | 6 | N | N |  | 调拨药房采购价 |
| 17 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 18 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 19 | STORAGE_COST | number | 12 | 4 | N | N | 0 | 进价金额 |
| 20 | WHOLESALE_COST | number | 12 | 4 | N | N | 0 | 批发金额 |
| 21 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售金额 |
| 22 | OUT_STORE_ID | varchar2 | 50 | 0 | N | N | 0 | 目标药房库存ID |
| 23 | REQUEST_STORE_ID | varchar2 | 50 | 0 | Y | N |  | 申请药房库房数量 |
| 24 | OUT_STORE_QUANTITY | number | 22 | 6 | Y | N |  | 目标药房库存数量 |
| 25 | REQUEST_STORE_QUANTITY | number | 22 | 6 | Y | N |  | 申请药房库房数量 |
| 26 | PDA_STATE | number | 1 | 0 | Y | N | 0 | 调拨状态 0未调拨 1已调拨 |
| 27 | SERIAL_DRUG_PRI | varchar2 | 255 | 0 | Y | N |  | 包装转换 ypid |
| 28 | SERIAL_DRUG_QUANTITY | number | 22 | 0 | Y | N |  | 包装转换后的药品数量 |

### 44. PHA_BALANCE（药房价格差额表（平账表））

- **表名**：`PHA_BALANCE`
- **中文说明**：药房价格差额表（平账表）
- **字段数**：30
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | varchar2 | 50 | 0 | N | Y |  | 主键 |
| 2 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 3 | PHA_CODE | varchar2 | 50 | 0 | N | N |  | 药房编码 |
| 4 | BALANCE_KIND | varchar2 | 20 | 0 | Y | N |  | 1.药库申领 2.药房调拨 3.门诊发药(退)、4 申领退库、5 住院发药(退)、9其它出库 |
| 5 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品价格ID(主键) |
| 6 | QUANTITY | number | 12 | 4 | N | N | 0 | 差额数量 |
| 7 | BALANCE_TRADE_COST | number | 12 | 4 | N | N | 0 | 差采购总额 |
| 8 | BALANCE_RECEIPT | number | 18 | 0 | N | N |  | 关联发药记录号，出入库单号，调拨单号等 |
| 9 | TRADE_PRICE | number | 14 | 6 | N | N |  | 采购价 |
| 10 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 11 | TRADE_COST | number | 12 | 4 | N | N | 0 | 采购总金额 |
| 12 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售总金额 |
| 13 | TRADE_OLDPRICE | number | 14 | 6 | N | N |  | 原采购价（处方） |
| 14 | RETAIL_OLDPRICE | number | 14 | 6 | N | N |  | 原零售价（处方） |
| 15 | RETAIL_OLDCOST | number | 12 | 4 | N | N | 0 | 原零售总价（处方） |
| 16 | TRADE_OLDCOST | number | 12 | 4 | N | N | 0 | 原采购总价（处方） |
| 17 | STORE_ID | varchar2 | 50 | 0 | N | N |  | 库存id |
| 18 | BALANCE_DATE | date | 7 | 0 | Y | N |  | 差额创建时间 |
| 19 | BALANCE_OPER | varchar2 | 16 | 0 | Y | N |  | 差额人编码 |
| 20 | CREATE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 创建者ID |
| 21 | CREATE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 创建者姓名 |
| 22 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 23 | MODIFY_USER_ID | varchar2 | 30 | 0 | Y | N |  | 修改者ID |
| 24 | MODIFY_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 修改者姓名 |
| 25 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改时间 |
| 26 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 (0: 未删除, 1: 已删除) |
| 27 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 28 | DELETE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 删除者ID |
| 29 | DELETE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 删除者姓名 |
| 30 | BALANCE_RETAIL_COST | number | 12 | 4 | N | N | 0 | 差零售总额 |

### 45. PHA_CHECK_DETAIL（药房盘点明细表）

- **表名**：`PHA_CHECK_DETAIL`
- **中文说明**：药房盘点明细表
- **字段数**：37

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | number | 22 | 0 | Y | N |  | 记录序号 |
| 2 | ORG_CODE | varchar2 | 50 | 0 | Y | N |  | 机构代码 |
| 3 | CHECK_NO | varchar2 | 50 | 0 | Y | N |  | 盘点单号 |
| 4 | PHA_CODE | varchar2 | 50 | 0 | Y | N |  | 库房编码 |
| 5 | DRUG_LOC | varchar2 | 50 | 0 | Y | N |  | 库存货位编码 |
| 6 | DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药品主键 |
| 7 | PRODUCT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 生产日期 |
| 8 | BATCH_NO | varchar2 | 50 | 0 | Y | N |  | 药品批号 |
| 9 | EXPIRE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 药品效期 |
| 10 | START_TIME | timestamp(6) | 11 | 6 | Y | N |  | 盘点开始时间 |
| 11 | START_QUANTITY | number | 22 | 4 | Y | N |  | 起始库存数量 |
| 12 | TRADE_PRICE | number | 22 | 6 | Y | N |  | 进货价格 |
| 13 | RETAIL_PRICE | number | 22 | 6 | Y | N |  | 零售价格 |
| 14 | WHOLESALE_PRICE | number | 22 | 6 | Y | N |  | 批发价格 |
| 15 | STORE_ID | varchar2 | 50 | 0 | Y | N |  | 库存识别ID |
| 16 | REAL_QUANTITY | number | 22 | 4 | Y | N |  | 实盘数量 |
| 17 | REAL_TIME | timestamp(6) | 11 | 6 | Y | N |  | 实盘完成时间 |
| 18 | REAL_STORAGE | number | 22 | 4 | Y | N |  | 实盘时库存 |
| 19 | CHECK_OPER | varchar2 | 50 | 0 | Y | N |  | 实盘人 |
| 20 | CHECK_INOUT | number | 22 | 4 | Y | N |  | 盘点期间入出数量 |
| 21 | STORAGE_COST | number | 22 | 4 | Y | N |  | 进货金额 |
| 22 | WHOLESALE_COST | number | 22 | 4 | Y | N |  | 批发金额 |
| 23 | RETAIL_COST | number | 22 | 4 | Y | N |  | 零售金额 |
| 24 | MEMO | varchar2 | 200 | 0 | Y | N |  | 备注信息 |
| 25 | ID | number | 22 | 0 | Y | N |  | id |
| 26 | PDA_STATE | number | 1 | 0 | Y | N | 0 | 盘点状态 |
| 27 | STORE_TYPE | number | 4 | 0 | Y | N |  | 库存类型 |
| 28 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 29 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 30 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 31 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 32 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 33 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 34 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 35 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 36 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 37 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |

### 46. PHA_CHECK_MASTER（药房盘点主表）

- **表名**：`PHA_CHECK_MASTER`
- **中文说明**：药房盘点主表
- **字段数**：24

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 50 | 0 | Y | N |  | 机构编码 |
| 2 | PHA_STORE | varchar2 | 50 | 0 | Y | N |  | 库房识别 |
| 3 | CHECK_NO | varchar2 | 50 | 0 | Y | N |  | 盘点单号 |
| 4 | DRUG_LOC | varchar2 | 50 | 0 | Y | N |  | 库位类别 |
| 5 | DRUG_TYPE | varchar2 | 50 | 0 | Y | N |  | 药品类别 |
| 6 | CHECK_DATE | timestamp(6) | 11 | 6 | Y | N |  | 盘点日期 |
| 7 | CHECK_OPER | varchar2 | 50 | 0 | Y | N |  | 盘点工号 |
| 8 | FINISH_OPER | varchar2 | 50 | 0 | Y | N |  | 完成工号 |
| 9 | FINISH_DATE | timestamp(6) | 11 | 6 | Y | N |  | 完成日期 |
| 10 | MZMO | char | 10 | 0 | Y | N |  | 备注信息 |
| 11 | CHECK_STATE | number | 10 | 0 | Y | N | 0 | 盘点单状态 |
| 12 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 13 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 14 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 15 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 16 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 17 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 18 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 19 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 20 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 21 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 22 | ID | number | 22 | 0 | Y | N |  | id |
| 23 | CHECK_USER_ID | varchar2 | 255 | 0 | Y | N |  | 盘点人编码 |
| 24 | CHECK_USER_NAME | varchar2 | 255 | 0 | Y | N |  | 盘点人名称 |

### 47. PHA_CLI_REQUEST_DRUG（门诊发药申请表）

- **表名**：`PHA_CLI_REQUEST_DRUG`
- **中文说明**：门诊发药申请表
- **字段数**：95
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | REQUEST_NO | varchar2 | 50 | 0 | Y | N |  | 申请单号 |
| 2 | PHA_CODE | varchar2 | 50 | 0 | Y | N |  | 药房编码 |
| 3 | PHA_NAME | varchar2 | 50 | 0 | Y | N |  | 药房名称 |
| 4 | DEPT_CODE | varchar2 | 50 | 0 | Y | N |  | 科室编码(开方) |
| 5 | DEPT_NAME | varchar2 | 50 | 0 | Y | N |  | 科室名称(开方) |
| 6 | PAT_ID | varchar2 | 50 | 0 | Y | N |  | 患者id |
| 7 | VISIT_ID | varchar2 | 50 | 0 | Y | N |  | 门诊号（就诊次数） |
| 8 | PAT_NAME | varchar2 | 50 | 0 | Y | N |  | 患者姓名 |
| 9 | PAT_SEX | number | 0 | -127 | Y | N |  | 患者性别 1男 2女 |
| 10 | PAT_BIRTHDAY | timestamp(6) | 11 | 6 | Y | N |  | 患者出生日期 |
| 11 | PRESC_NO | varchar2 | 50 | 0 | Y | N |  | 处方号 |
| 12 | PRESC_KIND | varchar2 | 50 | 0 | Y | N |  | 处方收费类型 00自费 02医保 15是工伤 10复杂病种 05统筹 08补充 03门规或大病 |
| 13 | PRESC_DETAIL_ID | varchar2 | 50 | 0 | Y | N |  | 处方明细号 |
| 14 | PRESC_CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 处方开立时间 |
| 15 | INVOICE_NO | varchar2 | 50 | 0 | Y | N |  | 收据号/发票号 |
| 16 | FEE_ID | varchar2 | 50 | 0 | Y | N |  | 费用id |
| 17 | FEE_PRICE | number | 14 | 6 | Y | N |  | 药品总费用 单价*数量 |
| 18 | FEE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 收费日期 |
| 19 | FEE_STATE | number | 0 | -127 | Y | N |  | 收费/日结 标志 0 未收费 1 已收费 |
| 20 | DOCTOR_CODE | varchar2 | 50 | 0 | Y | N |  | 医生编码(开方) |
| 21 | DOCTOR_NAME | varchar2 | 50 | 0 | Y | N |  | 医生名称(开方) |
| 22 | SPECIAL_DRUG | number | 0 | -127 | Y | N |  | 是否为特殊药品 0正常 1特殊 |
| 23 | DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药品id(药品主键) |
| 24 | DRUG_NAME | varchar2 | 50 | 0 | Y | N |  | 药品名称 |
| 25 | USAGE_CODE | varchar2 | 50 | 0 | Y | N |  | 用法编码 |
| 26 | USAGE_NAME | varchar2 | 50 | 0 | Y | N |  | 用法名称 |
| 27 | DOSAGE_CODE | varchar2 | 50 | 0 | Y | N |  | 用量编码 |
| 28 | DPSAGE_NAME | varchar2 | 50 | 0 | Y | N |  | 单次用量 例：0.5 |
| 29 | FREQUENCY_CODE | varchar2 | 50 | 0 | Y | N |  | 频次编码 |
| 30 | FREQUENCY_NAME | varchar2 | 50 | 0 | Y | N |  | 频次名称 |
| 31 | USAGE_TYPE | number | 0 | -127 | Y | N |  | 服用方式 1内服 2外用 |
| 32 | DIAGNOSE_CODE | varchar2 | 50 | 0 | Y | N |  | 诊断编码 |
| 33 | DIAGNOSE_NAME | varchar2 | 50 | 0 | Y | N |  | 诊断名称 |
| 34 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 35 | PROXY_NAME | varchar2 | 50 | 0 | Y | N |  | 代领人姓名 |
| 36 | PROXY_SEX | number | 0 | -127 | Y | N |  | 代领人性别 |
| 37 | PROXY_BIRTHDAY | date | 7 | 0 | Y | N |  | 代领人出生日期 |
| 38 | PROXY_CARDNO | varchar2 | 50 | 0 | Y | N |  | 代领人身份证号 |
| 39 | PROXY_PAT_CARDNO | varchar2 | 50 | 0 | Y | N |  | 病人身份证号 |
| 40 | SEND_QUANTITY | number | 12 | 2 | Y | N |  | 申请发药数量 |
| 41 | CLI_FLAG | varchar2 | 10 | 0 | Y | N |  | 发退标识 send 发药 return 退药 |
| 42 | SEND_DRUG_STATUS | char | 1 | 0 | Y | N |  | 发药状态 N未发 Y已发 |
| 43 | RETURN_DRUG_STATUS | char | 1 | 0 | Y | N |  | 退药状态 N 未退 Y 已退 |
| 44 | CLI_EXECUTE_TIME | date | 7 | 0 | Y | N |  | 发药/退药时间 |
| 45 | GROUP_NO | varchar2 | 50 | 0 | Y | N |  | 组套号 |
| 46 | RETURN_REASON | varchar2 | 1000 | 0 | Y | N |  | 退药原因 |
| 47 | ID | varchar2 | 50 | 0 | N | Y |  | id |
| 48 | FACTORY_CODE | varchar2 | 50 | 0 | Y | N |  | 药品生产厂商编码 |
| 49 | FACTORY_NAME | varchar2 | 50 | 0 | Y | N |  | 药品生产厂商名称 |
| 50 | SPECS | varchar2 | 50 | 0 | Y | N |  | 药品规格 |
| 51 | RETAIL_PRICE | number | 14 | 6 | Y | N |  | 药品零售价(单价) |
| 52 | DOSE | number | 12 | 4 | Y | N |  | 药品包装剂量 |
| 53 | DOSE_UNIT | varchar2 | 50 | 0 | Y | N |  | 药品剂量单位 |
| 54 | PROXY_PAT_PHONE | varchar2 | 20 | 0 | Y | N |  | 病人联系电话 |
| 55 | PROXY_PHONE | varchar2 | 20 | 0 | Y | N |  | 代领人联系电话 |
| 56 | NURSE_CELL_CODE | varchar2 | 255 | 0 | Y | N |  | 住院病区代码(住院开处方用) |
| 57 | NURSE_CELL_NAME | varchar2 | 255 | 0 | Y | N |  | 住院病区名称(住院开处方用) |
| 58 | CLI_INP_FLAG | varchar2 | 10 | 0 | Y | N |  | 处方标识：1 门诊 2住院 |
| 59 | REVIEWER_CODE | varchar2 | 50 | 0 | Y | N |  | 审核人编码 |
| 60 | REVIEWER_NAME | varchar2 | 50 | 0 | Y | N |  | 审核人名称 |
| 61 | ALLOT_CODE | varchar2 | 50 | 0 | Y | N |  | 调配人编码 |
| 62 | ALLOT_NAME | varchar2 | 50 | 0 | Y | N |  | 调配人名称 |
| 63 | CHECK_CODE | varchar2 | 50 | 0 | Y | N |  | 核对人编码 |
| 64 | CHECK_NAME | varchar2 | 50 | 0 | Y | N |  | 核对人名称 |
| 65 | DISPENSING_CODE | varchar2 | 50 | 0 | Y | N |  | 发药人编码 |
| 66 | DISPENSING_NAME | varchar2 | 50 | 0 | Y | N |  | 发药人名称 |
| 67 | BED_NUM | varchar2 | 50 | 0 | Y | N |  | 床号(住院开处方用) |
| 68 | INPATIENT_NO | varchar2 | 50 | 0 | Y | N |  | 住院流水号(住院开处方用) |
| 69 | DOCTOR_NOTE | varchar2 | 1024 | 0 | Y | N |  | 医生说明(草药药房) |
| 70 | PRESC_TYPE_CODE | varchar2 | 255 | 0 | Y | N |  | 处方类型编码 1麻精一 、 2精二 、3.儿科 、 4急诊 、 5.普通 、 6.其他 |
| 71 | PRESC_TYPE_NAME | varchar2 | 255 | 0 | Y | N |  | 处方类型名称 |
| 72 | PAT_FEE_TYPE | varchar2 | 20 | 0 | Y | N |  | 患者费别 00自费 02医保 15是工伤 10复杂病种 05统筹 08补充 03门规或大病 |
| 73 | INPUT_OPER | varchar2 | 50 | 0 | Y | N |  | 录入人编码 |
| 74 | INPUT_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 录入人名称 |
| 75 | DPSAGE_UNIT | varchar2 | 50 | 0 | Y | N |  | 单次用量单位 例：mg |
| 76 | MED_DRUG_DAYS | number | 0 | -127 | Y | N |  | 用药天数 |
| 77 | SKIN_TEST_RES | number | 0 | -127 | Y | N |  | 皮试结果 0无皮试 1阴性 2阳性 |
| 78 | SELF_PAID_RATIO | number | 0 | -127 | Y | N |  | 自付比例 百分之多少 |
| 79 | NON_DECTCOED | varchar2 | 50 | 0 | Y | N |  | 是否代煎 |
| 80 | CHA_DRUG_QUANTITY | varchar2 | 50 | 0 | Y | N |  | 中药付数 |
| 81 | WINDOW_NO | varchar2 | 50 | 0 | Y | N |  | 窗口号 |
| 82 | MACH_NO | varchar2 | 50 | 0 | Y | N |  | 自助机取号机器号码 |
| 83 | PRINT_FLAG | varchar2 | 50 | 0 | Y | N |  | 打印标志 0 未打印 1已打印 |
| 84 | PRINT_DATE | date | 7 | 0 | Y | N |  | 打印时间 |
| 85 | SEND_DRUG_SORT_NO | varchar2 | 50 | 0 | Y | N |  | 发药排队号 |
| 86 | USE_SEVEN_DETAIL | varchar2 | 50 | 0 | Y | N |  | 超7天用药说明 |
| 87 | INTERNET_BILLNO | varchar2 | 50 | 0 | Y | N |  | 互联网医院单据号 |
| 88 | RETURN_QUANTITY | number | 12 | 2 | Y | N |  | 已退数量 |
| 89 | YBPB | number | 0 | -127 | Y | N |  | 医保判别：0：自费、1：医保 |
| 90 | CARD_FLAG | char | 1 | 0 | Y | N |  | 是否自费：Y、是 |
| 91 | YSSM | varchar2 | 255 | 0 | Y | N |  | 医生说明(草药处方用) |
| 92 | INTERVENTION_FLAG | varchar2 | 5 | 0 | Y | N |  |  |
| 93 | OPERATORCODE | varchar2 | 255 | 0 | Y | N |  | 门诊处方结算人编码 |
| 94 | OPERATORNAME | varchar2 | 255 | 0 | Y | N |  | 门诊处方结算人姓名 |
| 95 | JSLX | number | 0 | -127 | Y | N |  | 结算类型：0、自费，1、市医保普通，2、省医保，3、市医保门规，4、市医保急诊，5、省医保门规，6、省内异地个账户，7、工伤 |

### 48. PHA_DETAIL_STORAGE（药房库存结存信息）

- **表名**：`PHA_DETAIL_STORAGE`
- **中文说明**：药房库存结存信息
- **字段数**：25
- **主键字段**：DETAIL_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | DETAIL_ID | varchar2 | 50 | 0 | N | Y |  |  |
| 2 | STORE_CODE | varchar2 | 16 | 0 | Y | N |  | 库房识别 |
| 3 | ORG_CODE | varchar2 | 32 | 0 | Y | N |  | 机构编码 |
| 4 | DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药品主键,MED_DICT_PRICE.DRUG_PRI |
| 5 | BATCH_NO | varchar2 | 50 | 0 | Y | N |  | 药品批号 |
| 6 | EXPIRE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 药品效期 |
| 7 | TRADE_PRICE | number | 14 | 6 | Y | N |  | 采购价 |
| 8 | RETAIL_PRICE | number | 14 | 6 | Y | N |  | 零售价 |
| 9 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 10 | STORAGE_QUANTITY | number | 12 | 4 | Y | N |  | 库存数量 |
| 11 | STORAGE_COST | number | 12 | 4 | Y | N |  | 进货金额 |
| 12 | WHOLESALE_COST | number | 12 | 4 | Y | N |  | 批发金额 |
| 13 | RETAIL_COST | number | 12 | 4 | Y | N |  | 零售金额 |
| 14 | INOUT_KIND | varchar2 | 50 | 0 | Y | N |  | 出入库方式<br>vis_pha_to_pat 门诊药房发药给患者<br>inp_pha_to_pat 住院药房发药给患者 |
| 15 | INOUT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 业务时间 |
| 16 | PRODUCT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 生产日期 |
| 17 | RECORD_NO | varchar2 | 50 | 0 | Y | N |  | 库存id |
| 18 | IN_OUT_TYPE | varchar2 | 50 | 0 | Y | N |  | 出入库标识 in 入库 out 出库 |
| 19 | TOTAL_QUANTITY | number | 0 | -127 | Y | N |  | 药品总数量(不区分批次等属性) |
| 20 | BEFORE_QUANTITY | number | 12 | 4 | N | N |  | 原来的库存数量 由此可计算出 出库或入库数量 |
| 21 | IN_QUANTITY | number | 12 | 4 | N | N |  | 入库数量 |
| 22 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 23 | TOTAL_STORAGE_COST | number | 12 | 4 | N | N |  | 库存总金额（不含批次） |
| 24 | TOTAL_WHOLESALE_COST | number | 12 | 4 | N | N |  | 库存总批发金额（不含批次） |
| 25 | TOTAL_RETAIL_COST | number | 12 | 4 | N | N |  | 库存总零售金额（不含批次） |

### 49. PHA_DICT_MEDINFO（药品字典药房药品）

- **表名**：`PHA_DICT_MEDINFO`
- **中文说明**：药品字典药房药品
- **字段数**：26
- **主键字段**：ORG_CODE, PHA_CODE, DRUG_PRI

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | Y | '1' | 机构编码 |
| 2 | PHA_CODE | varchar2 | 50 | 0 | N | Y |  | 药房编码 |
| 3 | DRUG_PRI | varchar2 | 50 | 0 | N | Y |  | 药品主键 |
| 4 | PHA_SPECS | varchar2 | 64 | 0 | Y | N |  | 药房规格 |
| 5 | PHA_UNIT | varchar2 | 16 | 0 | Y | N |  | 药房单位 |
| 6 | PHA_PACKAGE | number | 12 | 4 | Y | N |  | 药房包装 |
| 7 | PHA_TOPLINE | number | 10 | 2 | N | N | 0 | 药房高储（库存上限） |
| 8 | PHA_LOWLINE | number | 10 | 2 | N | N | 0 | 药房低储（库存下限） |
| 9 | DEL_FLAG | number | 1 | 0 | N | N | 0 | 药房作废 |
| 10 | ROUND_METHOD | number | 8 | 0 | N | N | 2 | 取整策略 |
| 11 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 12 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 13 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 14 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 15 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 16 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 17 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 18 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 19 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 20 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 21 | PHA_DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药品主键 |
| 22 | DRUG_NAME | varchar2 | 100 | 0 | Y | N |  | 药品名称 |
| 23 | DEFAULT_PACKAGE | number | 1 | 0 | Y | N | 0 | 默认包装 0非默认 1默认) |
| 24 | DISP_TYPE | varchar2 | 255 | 0 | Y | N |  | 发药类型编码 |
| 25 | DISP_TYPE_NAME | varchar2 | 255 | 0 | Y | N |  | 发药类型名字 |
| 26 | RESERVED_QUANTITY | number | 10 | 0 | Y | N | 0 | 锁定数量 |

### 50. PHA_FALSE_STORAGE（药房库存信息）

- **表名**：`PHA_FALSE_STORAGE`
- **中文说明**：药房库存信息
- **字段数**：9
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ID | varchar2 | 50 | 0 | N | Y |  | id |
| 2 | PHA_ID | varchar2 | 255 | 0 | Y | N |  | 库存id |
| 3 | REDUCE_QUANTITY | number | 12 | 2 | Y | N |  | 预扣库存数量 |
| 4 | DRUG_PRI | varchar2 | 255 | 0 | Y | N |  | 药品id |
| 5 | REQ_PRI | varchar2 | 255 | 0 | Y | N |  | 关联模块字段（处方明细号、医嘱执行单流水号等）<br>PHA_INP_REQUEST_DRUG 中的 DISP_NO |
| 6 | REQ_TYPE | number | 1 | 0 | Y | N |  | 关联类型 1处方 2医嘱 |
| 7 | REQ_TIME | timestamp(6) | 11 | 6 | Y | N |  | 申请时间 |
| 8 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 0 未删除 1 已删除 |
| 9 | DISP_NO | varchar2 | 255 | 0 | Y | N |  | PHA_INP_REQUEST_DRUG 中的 DISP_NO |

### 51. PHA_FIN_DAYDETAIL（财务月结明细表）

- **表名**：`PHA_FIN_DAYDETAIL`
- **中文说明**：财务月结明细表
- **字段数**：13
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | number | 20 | 0 | N | Y |  | 记录序号 |
| 2 | FIN_ID | number | 20 | 0 | Y | N |  | 月结id |
| 3 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构编码 |
| 4 | PHA_CODE | varchar2 | 16 | 0 | N | N |  | 库房编码 |
| 5 | SETTLE_MONTH | varchar2 | 50 | 0 | N | N |  | 结账月份 |
| 6 | DRUG_PRI | number | 20 | 0 | N | N |  | 药品主键 |
| 7 | STORE_QUANTITY | number | 12 | 4 | N | N | 0 | 月结数量 |
| 8 | TRADE_PRICE | number | 14 | 6 | N | N |  | 采购价 |
| 9 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 10 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 11 | IN_COST | number | 12 | 4 | N | N | 0 | 进货金额 |
| 12 | WHOLESALE_COST | number | 12 | 4 | N | N | 0 | 批发金额 |
| 13 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售金额 |

### 52. PHA_FIN_DAYSETTLE（财务月结主表）

- **表名**：`PHA_FIN_DAYSETTLE`
- **中文说明**：财务月结主表
- **字段数**：9
- **主键字段**：FIN_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | FIN_ID | number | 30 | 0 | N | Y |  | 月结主键 |
| 2 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构编码 |
| 3 | PHA_CODE | varchar2 | 16 | 0 | Y | N |  | 库房编码 |
| 4 | SETTLE_DAY | varchar2 | 50 | 0 | Y | N |  | 结账天-日期 |
| 5 | START_TIME | timestamp(6) | 11 | 6 | N | N |  | 起始时间 |
| 6 | END_TIME | timestamp(6) | 11 | 6 | N | N |  | 终止时间 |
| 7 | SETTLE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 结账时间 |
| 8 | SETTLE_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 结账人员名称 |
| 9 | SETTLE_OPER_CODE | varchar2 | 50 | 0 | Y | N |  | 结账人员编码 |

### 53. PHA_FIN_MONTHDETAIL（财务月结明细表）

- **表名**：`PHA_FIN_MONTHDETAIL`
- **中文说明**：财务月结明细表
- **字段数**：24
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | number | 20 | 0 | N | Y |  | 记录序号 |
| 2 | FIN_ID | number | 20 | 0 | Y | N |  | 月结id |
| 3 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构编码 |
| 4 | PHA_CODE | varchar2 | 16 | 0 | N | N |  | 库房编码 |
| 5 | SETTLE_MONTH | date | 7 | 0 | N | N |  | 结账月份 |
| 6 | DRUG_PRI | number | 20 | 0 | N | N |  | 药品主键 |
| 7 | STORE_QUANTITY | number | 12 | 4 | N | N | 0 | 月结数量 |
| 8 | TRADE_PRICE | number | 14 | 6 | N | N |  | 采购价 |
| 9 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 10 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 11 | IN_COST | number | 12 | 4 | N | N | 0 | 进货金额 |
| 12 | WHOLESALE_COST | number | 12 | 4 | N | N | 0 | 批发金额 |
| 13 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售金额 |
| 14 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 15 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 16 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 17 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 18 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 19 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 20 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 21 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 22 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 23 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 24 | MONTH_STATUS | number | 10 | 0 | Y | N |  | 月结状态0结算中1结算完成 |

### 54. PHA_FIN_MONTHSETTLE（财务月结主表）

- **表名**：`PHA_FIN_MONTHSETTLE`
- **中文说明**：财务月结主表
- **字段数**：20
- **主键字段**：FIN_ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | FIN_ID | number | 30 | 0 | N | Y |  | 月结主键 |
| 2 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' | 机构编码 |
| 3 | PHA_CODE | varchar2 | 16 | 0 | Y | N |  | 库房编码 |
| 4 | SETTLE_MONTH | date | 7 | 0 | Y | N |  | 结账月份 |
| 5 | START_TIME | timestamp(6) | 11 | 6 | N | N |  | 起始时间 |
| 6 | END_TIME | timestamp(6) | 11 | 6 | N | N |  | 终止时间 |
| 7 | SETTLE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 结账时间 |
| 8 | SETTLE_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 结账人员名称 |
| 9 | SETTLE_OPER_CODE | varchar2 | 50 | 0 | Y | N |  | 结账人员编码 |
| 10 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 11 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建者id |
| 12 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建者姓名 |
| 13 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 14 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  | 修改者id |
| 15 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 修改者姓名 |
| 16 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 17 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 删除人id |
| 18 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 删除人姓名 |
| 19 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 20 | MONTH_STATUS | number | 10 | 0 | Y | N |  | 月结状态0结算中1结算完成 |

### 55. PHA_INIT_ACCOUNT（药房初始化建账表）

- **表名**：`PHA_INIT_ACCOUNT`
- **中文说明**：药房初始化建账表
- **字段数**：35
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ID | number | 19 | 0 | N | Y |  | 主键ID |
| 2 | DRUG_ID | varchar2 | 100 | 0 | N | N |  | 药品id |
| 3 | DRUG_CODE | varchar2 | 100 | 0 | N | N |  | 药品编码 |
| 4 | DRUG_NAME | varchar2 | 100 | 0 | N | N |  | 药品名称 |
| 5 | USAGE | varchar2 | 50 | 0 | Y | N |  | 默认用法编码 |
| 6 | FREQUENCY | varchar2 | 50 | 0 | Y | N |  | 默认频次编码 |
| 7 | DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药品价格id |
| 8 | SPECS | varchar2 | 64 | 0 | Y | N |  | 药品规格 |
| 9 | PACK_UNIT_NAME | varchar2 | 50 | 0 | Y | N |  | 单位名称 |
| 10 | TRADE_PRICE | number | 14 | 4 | Y | N |  | 采购价 |
| 11 | RETAIL_PRICE | number | 14 | 4 | Y | N |  | 零售价 |
| 12 | WHOLESALE_PRICE | number | 14 | 4 | Y | N |  | 批发价 |
| 13 | STORAGE_QUANTITY | number | 12 | 4 | Y | N |  | 库存数量 |
| 14 | STORAGE_COST | number | 12 | 4 | Y | N |  | 采购金额 |
| 15 | WHOLESALE_COST | number | 12 | 4 | Y | N |  | 批发金额 |
| 16 | RETAIL_COST | number | 12 | 4 | Y | N |  | 零售金额 |
| 17 | PRODUCT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 生产日期 |
| 18 | EXPIRE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 药品效期 |
| 19 | BATCH_NO | varchar2 | 50 | 0 | Y | N |  | 药品批号 |
| 20 | LOC_CODE | varchar2 | 2000 | 0 | Y | N |  | 库位编码 |
| 21 | DRUG_LOC | varchar2 | 255 | 0 | Y | N |  | 库位 |
| 22 | STORE_CODE | varchar2 | 255 | 0 | Y | N |  | 库房识别码 |
| 23 | FACTORY_ID | number | 19 | 0 | Y | N |  | 药品厂家ID |
| 24 | FACTORY_NAME | varchar2 | 160 | 0 | Y | N |  | 厂家全名 |
| 25 | TAKE_EFFECT_FLAG | number | 1 | 0 | Y | N | 0 | 生效标记：0暂存、1生效 |
| 26 | IS_DELETED | number | 1 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 27 | CREATE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 创建者id |
| 28 | CREATE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 创建者姓名 |
| 29 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 30 | MODIFY_USER_ID | varchar2 | 30 | 0 | Y | N |  | 修改者id |
| 31 | MODIFY_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 修改者姓名 |
| 32 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 33 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 34 | DELETE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 删除人id |
| 35 | DELETE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 删除人姓名 |

### 56. PHA_INP_DISPDETAIL（住院发药明细）

- **表名**：`PHA_INP_DISPDETAIL`
- **中文说明**：住院发药明细
- **字段数**：49
- **主键字段**：ORG_CODE, RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | N | Y | '1' | 机构编码 |
| 2 | RECORD_NO | varchar2 | 50 | 0 | N | Y |  | 记录序号 |
| 3 | PHA_CODE | varchar2 | 16 | 0 | Y | N |  | 药房识别 |
| 4 | PHA_WINDOWNO | number | 4 | 0 | N | N |  | 窗口编号 |
| 5 | MED_DIS_METHOD | number | 8 | 0 | Y | N |  | 发药方式分摆药，发药，静配等，默认为0发药 |
| 6 | INP_PATID | varchar2 | 38 | 0 | N | N |  | 住院流水号 |
| 7 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品主键 |
| 8 | PRODUCT_DATE | date | 7 | 0 | Y | N |  | 生产日期 |
| 9 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  | 药品批号 |
| 10 | EXPIRE_DATE | date | 7 | 0 | Y | N |  | 药品效期 |
| 11 | TRADE_PRICE | number | 14 | 6 | N | N |  | 进价（采购价） |
| 12 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 13 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 14 | STORAGE_COST | number | 12 | 4 | N | N | 0 | 进价 总价 |
| 15 | WHOLESALE_COST | number | 12 | 4 | N | N | 0 | 批发价 总价 |
| 16 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售价 总价 |
| 17 | DRUG_QUANTITY | number | 12 | 4 | N | N | 0 | 发药数量 |
| 18 | PHA_SPECS | varchar2 | 64 | 0 | Y | N |  | 药房规格 |
| 19 | PHA_UNIT | varchar2 | 16 | 0 | Y | N |  | 药房单位 |
| 20 | PHA_PACKAGE | number | 12 | 4 | Y | N |  | 药房包装 |
| 21 | CHECK_OPER | varchar2 | 16 | 0 | Y | N |  | 确认工号 |
| 22 | CHECK_DATE | date | 7 | 0 | N | N |  | 发药日期 |
| 23 | FEE_DEPT | varchar2 | 100 | 0 | N | N | '0' | 计费科室 |
| 24 | FEE_WARD | varchar2 | 100 | 0 | N | N |  | 领药病区 |
| 25 | EXCUTE_DEPT | varchar2 | 100 | 0 | N | N | '0' | 执行科室 |
| 26 | STORE_ID | varchar2 | 50 | 0 | N | N | 0 | 库存id |
| 27 | ADVICE_ID | number | 18 | 0 | Y | N |  | 医嘱序号 |
| 28 | BABY_FLAG | number | 1 | 0 | Y | N |  | 婴儿判别 |
| 29 | FEE_ID | number | 18 | 0 | Y | N | 0 | 记费ID与住院费用表中的 主键对应 |
| 30 | FEE_DATE | date | 7 | 0 | N | N |  | 费用日期 |
| 31 | SELF_RATIO | number | 4 | 3 | Y | N | 1 | 自负比例 |
| 32 | DIS_RECORDNO | varchar2 | 100 | 0 | N | N | 0 | PHA_INP_MASTER 的 RECORD_NO |
| 33 | REQUEST_NO | varchar2 | 100 | 0 | Y | N |  | 申请单号 |
| 34 | RETURN_RECORDNO | varchar2 | 100 | 0 | Y | N |  | 退药对应的发药的记录号 recordno |
| 35 | RETURN_REQUESTNO | varchar2 | 100 | 0 | Y | N |  | 退药对应的发药的申请单号 requestno |
| 36 | RETURN_QUANTITY | number | 12 | 4 | Y | N | 0 | 已退数量 |
| 37 | PLAN_NO | varchar2 | 100 | 0 | Y | N |  | 医嘱执行计划明细号 PHA_INP_REQUEST_DRUG 中的 EXEC_SQN |
| 38 | FYLX | varchar2 | 18 | 0 | N | N | 1 | 发药类型 |
| 39 | DRUG_LOC | varchar2 | 50 | 0 | Y | N |  | 库位 |
| 40 | PDA_STATE | number | 1 | 0 | Y | N | 0 | 发药捡药状态 0未捡药 1已捡药 |
| 41 | DISP_FLAG | varchar2 | 255 | 0 | Y | N |  | send 发药 return 退药 |
| 42 | PATIENT_NAME | varchar2 | 255 | 0 | Y | N |  | 患者姓名 |
| 43 | BED_NUM | varchar2 | 255 | 0 | Y | N |  | 床号 |
| 44 | FREQUENCY_CODE | varchar2 | 255 | 0 | Y | N |  | 频次编码 |
| 45 | FREQUENCY_NAME | varchar2 | 255 | 0 | Y | N |  | 频次名称 |
| 46 | USE_NAME | varchar2 | 255 | 0 | Y | N |  | 用法名称 |
| 47 | USAGE_CODE | varchar2 | 255 | 0 | Y | N |  | 用法编码 |
| 48 | DRUG_NAME | varchar2 | 100 | 0 | Y | N |  | 药品名称 |
| 49 | DRUG_REQ_QUANTITY | number | 12 | 4 | Y | N | 0 | 住院发药申请数量 |

### 57. PHA_INP_DISPMASTER（药房发药住院记录主表）

- **表名**：`PHA_INP_DISPMASTER`
- **中文说明**：药房发药住院记录主表
- **字段数**：22
- **主键字段**：DIS_RECORDNO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | DIS_RECORDNO | number | 38 | 0 | N | Y | 0 | 发药记录单ID |
| 2 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 3 | DISP_FEE_OPER | varchar2 | 16 | 0 | Y | N |  | 发药人（发药计费工号） |
| 4 | DISP_WARD | varchar2 | 50 | 0 | Y | N |  | 领药病区 |
| 5 | DISP_TYPE | varchar2 | 10 | 0 | N | N | 1 | 发药类型 KFYCL 长期口服 KFYLL 临时口服 DSYAL 大输液 JDMAL 精神毒麻 TLDAL 统领全部 ZCYLL 中成药 JPDAL 静配 JPDCL 静配长期 JPDLL 静配临时 |
| 6 | PHA_CODE | varchar2 | 50 | 0 | Y | N |  | 药房编码 |
| 7 | MED_DIS_METHOD | number | 8 | 0 | Y | N |  | 发药方式分摆药，发药，静配等，默认为0发药 |
| 8 | ISPRINT | number | 1 | 0 | N | N | 0 | 打印判断 0：未打印 1：已打印 |
| 9 | DISP_BEGIN | date | 7 | 0 | Y | N |  | PDA捡药开始时间 |
| 10 | DISP_END | date | 7 | 0 | Y | N |  | PDA捡药完成时间 |
| 11 | DISP_OPER | varchar2 | 16 | 0 | Y | N |  | 捡药人 |
| 12 | CHECK_OPER | varchar2 | 16 | 0 | Y | N |  | 病区核对人 |
| 13 | CHECK_DATE | date | 7 | 0 | Y | N |  | 核对时间 |
| 14 | DISP_WARD_NAME | varchar2 | 50 | 0 | Y | N |  | 病区名称 |
| 15 | DISP_TYPE_NAME | varchar2 | 50 | 0 | Y | N |  | 发药类型名称 |
| 16 | DISP_FEE_OPER_NAME | varchar2 | 50 | 0 | Y | N |  | 发药人名称 |
| 17 | DISP_STATE | number | 1 | 0 | Y | N | 0 | 发药状态 |
| 18 | REQUEST_NO | varchar2 | 50 | 0 | Y | N |  | 申请单号 |
| 19 | CHECK_OPER_NAME | varchar2 | 16 | 0 | Y | N |  | 病区核对人 |
| 20 | DISP_OPER_NAME | varchar2 | 16 | 0 | Y | N |  | 捡药人 |
| 21 | DISP_SEND_TYPE | varchar2 | 255 | 0 | Y | N |  | send 发药 return 退药 |
| 22 | DISP_DATE | varchar2 | 255 | 0 | Y | N |  | 发药时间 |

### 58. PHA_INP_REQUEST_DRUG（住院发药申请）

- **表名**：`PHA_INP_REQUEST_DRUG`
- **中文说明**：住院发药申请
- **字段数**：85

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | DISP_NO | varchar2 | 50 | 0 | Y | N |  | 主键 |
| 2 | PHA_CODE | varchar2 | 50 | 0 | Y | N |  | 药房科室编号 |
| 3 | DEPT_CODE | varchar2 | 50 | 0 | Y | N |  | 住院病房科室 |
| 4 | PATIENT_NO | varchar2 | 50 | 0 | Y | N |  | 住院号 |
| 5 | INPATIENT_NO | varchar2 | 50 | 0 | Y | N |  | 住院流水号 |
| 6 | BABY_FLAG | char | 1 | 0 | Y | N | 'N' | 是否婴儿 Y是 N否 |
| 7 | HAPPEN_NO | varchar2 | 50 | 0 | Y | N |  | 婴儿序号 |
| 8 | MO_ORDER | varchar2 | 50 | 0 | Y | N |  | 医嘱流水号 |
| 9 | EXEC_SQN | varchar2 | 100 | 0 | Y | N |  | 医嘱执行的流水号 sqid |
| 10 | DISP_DATE | varchar2 | 255 | 0 | Y | N |  | 住院用药时间 |
| 11 | USAGE_CODE | varchar2 | 20 | 0 | Y | N |  | 用法字典编码 |
| 12 | USE_NAME | varchar2 | 50 | 0 | Y | N |  | 用法名称 |
| 13 | DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药品ID |
| 14 | DRUG_NAME | varchar2 | 100 | 0 | Y | N |  | 药品通用名称 |
| 15 | TRADE_NAME | varchar2 | 100 | 0 | Y | N |  | 药品价格的商品名称 |
| 16 | DRUG_SPEC | varchar2 | 100 | 0 | Y | N |  | 基本规格(最小药品单位规格) |
| 17 | MIN_UNIT_NAME | varchar2 | 100 | 0 | Y | N |  | 基本单位(最小药品单位包装单位) |
| 18 | UNITS_SPEC | varchar2 | 50 | 0 | N | N |  | 药品包装规格 |
| 19 | UNITS_NAME | varchar2 | 50 | 0 | Y | N |  | 药品包装单位 |
| 20 | DISP_QUANTITY | number | 12 | 2 | Y | N |  | 发药数量 |
| 21 | OPERATOR | varchar2 | 50 | 0 | Y | N |  | 发药人编码 |
| 22 | OPERATOR_NAME | varchar2 | 50 | 0 | Y | N |  | 发药人姓名 |
| 23 | DISP_FLAG | varchar2 | 10 | 0 | Y | N |  | send 发药 return 退药 |
| 24 | DISP_NO_OLD | varchar2 | 50 | 0 | Y | N |  | 原发药单号，退药使用 |
| 25 | VALID_STATE | number | 0 | -127 | Y | N |  | 0作废 1正常 2药房驳回 |
| 26 | SEND_DRUG_STATUS | char | 1 | 0 | Y | N | 'N' | 发药状态 N未发 Y已发 |
| 27 | RETURN_DRUG_STATUS | char | 1 | 0 | Y | N | 'N' | 退药状态 N 未退 Y 已退 |
| 28 | FREQUENCY_CODE | varchar2 | 100 | 0 | Y | N |  | 频次字典编码 |
| 29 | FREQUENCY_NAME | varchar2 | 100 | 0 | Y | N |  | 频次名称 |
| 30 | ORDER_TYPE | number | 0 | -127 | Y | N |  | 医嘱类型 1长期 2临时 |
| 31 | DOSE_MODEL_CODE | varchar2 | 50 | 0 | Y | N |  | 剂型编码 |
| 32 | DOSE_PER_UNIT | varchar2 | 50 | 0 | Y | N |  | 剂量 |
| 33 | DOSE_UNITS_CODE | varchar2 | 50 | 0 | Y | N |  | 剂量单位编码 |
| 34 | PATIENT_NAME | varchar2 | 50 | 0 | Y | N |  | 患者姓名 |
| 35 | DISP_EXECUTE_TIME | date | 7 | 0 | Y | N |  | 发药/退药时间 |
| 36 | NURSE_CELL_CODE | varchar2 | 50 | 0 | Y | N |  | 住院病区代码 |
| 37 | NURSE_CELL_NAME | varchar2 | 50 | 0 | Y | N |  | 住院病区名称 |
| 38 | BED_NUM | varchar2 | 255 | 0 | Y | N |  | 床号 |
| 39 | REQUEST_OPER | varchar2 | 255 | 0 | Y | N |  | 申请人编码 |
| 40 | REQUEST_OPER_NAME | varchar2 | 255 | 0 | Y | N |  | 申请人姓名 |
| 41 | REQUEST_NO | varchar2 | 255 | 0 | Y | N |  | 申请单号 |
| 42 | SEND_DRUG_TYPE | varchar2 | 255 | 0 | Y | N |  | 发药类型 KFYCL 长期口服 KFYLL 临时口服 DSYAL 大输液 JDMAL 精神毒麻 J2精2 TLDAL 统领全部 ZCYLL 中成药 JPDAL 静配 JPDCL 静配长期 JPDLL 静配临时 |
| 43 | SEND_DRUG_TYPE_NAME | varchar2 | 255 | 0 | Y | N |  | 发药类型 名称 |
| 44 | DOSE_UNITS_NAME | varchar2 | 50 | 0 | Y | N |  | 剂量名称 |
| 45 | FEE_ID | varchar2 | 255 | 0 | Y | N |  | 费用id 退费唯一标识 |
| 46 | RETAIL_PRICE | varchar2 | 255 | 0 | Y | N |  | 退药 零售价 |
| 47 | PRODUCT_DATE | date | 7 | 0 | Y | N |  | 退药 生产日期 |
| 48 | EXPIRE_DATE | date | 7 | 0 | Y | N |  | 退药 校期<br>退药 校期 |
| 49 | BATCH_NO | varchar2 | 255 | 0 | Y | N |  | 退药 批次号 |
| 50 | REQUEST_DATE | varchar2 | 255 | 0 | Y | N |  | 申请时间 |
| 51 | RETURN_REASON | varchar2 | 255 | 0 | Y | N |  | 退药原因（名称） |
| 52 | SPECIAL_DRUG | char | 1 | 0 | Y | N | 0 | 是否为特殊药品 0正常 1特殊 |
| 53 | PAT_ID | varchar2 | 255 | 0 | Y | N |  | 患者号 |
| 54 | PATIENT_NAME_PY | varchar2 | 255 | 0 | Y | N |  | 姓名拼音码 |
| 55 | IN_COUNT | varchar2 | 255 | 0 | Y | N |  | 住院次数 |
| 56 | ORDER_SUB_NO | varchar2 | 255 | 0 | Y | N |  | 医嘱子序号 |
| 57 | PAT_FEE_TYPE | varchar2 | 255 | 0 | Y | N |  | 患者费别 00自费 02医保 15是工伤 10复杂病种 05统筹 08补充 03门规或大病 |
| 58 | DISCHARGE_TAKING_INDICATOR | varchar2 | 255 | 0 | Y | N |  | 出院带药标志 0 不带 1出院带药 |
| 59 | USE_SEVEN_DETAIL | varchar2 | 255 | 0 | Y | N |  | 超7天用药说明 |
| 60 | REQUEST_DESCRIPTION | varchar2 | 255 | 0 | Y | N |  | 请求描述 例：某科室申请摆药某药品 |
| 61 | DISP_DRUG_DAYS | number | 0 | -127 | Y | N |  | 摆药天数 |
| 62 | LONG_ORDER_LAST_DATE | timestamp(6) | 11 | 6 | Y | N |  | 长期医嘱-末次摆药时间 |
| 63 | PAT_IDENTITY | varchar2 | 255 | 0 | Y | N |  | 患者身份 |
| 64 | URGENT_SIGN | varchar2 | 255 | 0 | Y | N |  | 加急标志 0 不加急 1 加急 |
| 65 | REVIEWER_CODE | varchar2 | 255 | 0 | Y | N |  | 审核人编码 |
| 66 | REVIEWER_NAME | varchar2 | 255 | 0 | Y | N |  | 审核人名称 |
| 67 | ALLOT_CODE | varchar2 | 255 | 0 | Y | N |  | 调配人编码 |
| 68 | ALLOT_NAME | varchar2 | 255 | 0 | Y | N |  | 调配人名称 |
| 69 | CHECK_CODE | varchar2 | 255 | 0 | Y | N |  | 核对人编码 |
| 70 | CHECK_NAME | varchar2 | 255 | 0 | Y | N |  | 核对人名称 |
| 71 | DELIVER_MEDICINE_STATE | char | 1 | 0 | Y | N | 0 | 大输液送药状态 0未送药/不需要送药（默认） 1已送药 |
| 72 | FEE_PRICE | varchar2 | 255 | 0 | Y | N |  | 药品费用总金额 |
| 73 | PAT_BIRTHDAY | varchar2 | 255 | 0 | Y | N |  | 患者出生日期 |
| 74 | PAT_SEX | varchar2 | 255 | 0 | Y | N |  | 性别 |
| 75 | PRESC_CREATE_TIME | varchar2 | 255 | 0 | Y | N |  | 医嘱处方开立时间 |
| 76 | IN_DIAGNOSE_NAME | varchar2 | 255 | 0 | Y | N |  | 入院诊断 |
| 77 | PHA_NAME | varchar2 | 255 | 0 | Y | N |  | 药房科室名称 |
| 78 | DOCTOR_NAME | varchar2 | 255 | 0 | Y | N |  | 开嘱医生 |
| 79 | DEPT_NAME | varchar2 | 255 | 0 | Y | N |  | 开嘱科室 |
| 80 | DOSE_ONCE | varchar2 | 255 | 0 | Y | N |  | 医嘱用量 |
| 81 | FLAG | varchar2 | 1 | 0 | Y | N |  | 0：未发药 1：已发药 -1：预交金不足，未发药 |
| 82 | AMOUNT_UNIT | varchar2 | 255 | 0 | Y | N |  | 数量单位 |
| 83 | COMMENT2 | varchar2 | 255 | 0 | Y | N |  | 医嘱嘱托 |
| 84 | ORDER_STOP_TIME | varchar2 | 255 | 0 | Y | N |  | 医嘱停止时间，同移动护理医嘱视图 |
| 85 | MEDICATION_STATUS | char | 1 | 0 | Y | N | 0 | 包药状态 0未包药 1已包药 |

### 59. PHA_SPECIAL_DRUG_REVIEW（特殊药品审核记录表）

- **表名**：`PHA_SPECIAL_DRUG_REVIEW`
- **中文说明**：特殊药品审核记录表
- **字段数**：40
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ID | number | 0 | -127 | N | Y |  | id |
| 2 | PRESC_DETAIL_ID | varchar2 | 255 | 0 | Y | N |  | 处方明细号 |
| 3 | PROXY_NAME | varchar2 | 50 | 0 | Y | N |  | 代领人姓名 |
| 4 | PROXY_CARDNO | varchar2 | 50 | 0 | Y | N |  | 代领人身份证号 |
| 5 | CREATE_TIME | date | 7 | 0 | Y | N |  | 创建时间 |
| 6 | PAT_NAME | varchar2 | 255 | 0 | Y | N |  | 患者姓名 |
| 7 | DRUG_NAME | varchar2 | 255 | 0 | Y | N |  | 药品名称 |
| 8 | DOSE | number | 12 | 4 | Y | N |  | 包装剂量 |
| 9 | DOSE_UNIT | varchar2 | 255 | 0 | Y | N |  | 剂量单位 |
| 10 | SEND_QUANTITY | number | 12 | 0 | Y | N |  | 申请发药数量 |
| 11 | PACK_UNIT_NAME | varchar2 | 255 | 0 | Y | N |  | 单位名称 |
| 12 | FACTORY_ABBR | varchar2 | 255 | 0 | Y | N |  | 生产厂商 |
| 13 | FEE_PRICE | number | 14 | 0 | Y | N |  | 药品总费用 |
| 14 | RETAIL_PRICE | number | 14 | 0 | Y | N |  | 零售价 |
| 15 | PAT_ID | varchar2 | 255 | 0 | Y | N |  | 患者id |
| 16 | PROXY_PHONE | varchar2 | 255 | 0 | Y | N |  | 代领人联系电话 |
| 17 | PRESC_NO | varchar2 | 255 | 0 | Y | N |  | 处方号 |
| 18 | PRESC_TYPE_CODE | varchar2 | 255 | 0 | Y | N |  | 处方类型编码 1麻精一 、 2精二 、3.儿科 、 4急诊 、 5.普通 、 6.其他 |
| 19 | PRESC_TYPE_NAME | varchar2 | 255 | 0 | Y | N |  | 处方类型名称 |
| 20 | PHA_CODE | varchar2 | 50 | 0 | Y | N |  | 药房编码 |
| 21 | REVIEWER_CODE | varchar2 | 255 | 0 | Y | N |  | 审核人编码 |
| 22 | REVIEWER_NAME | varchar2 | 255 | 0 | Y | N |  | 审核人名称 |
| 23 | PAT_SEX | varchar2 | 10 | 0 | Y | N |  | 患者性别 1男 2女 |
| 24 | PAT_BIRTHDAY | date | 7 | 0 | Y | N |  | 患者出生日期 |
| 25 | DOCTOR_CODE | varchar2 | 50 | 0 | Y | N |  | 开方医生编码 |
| 26 | DOCTOR_NAME | varchar2 | 50 | 0 | Y | N |  | 开方医生名称 |
| 27 | DEPT_CODE | varchar2 | 50 | 0 | Y | N |  | 开方科室编码 |
| 28 | DEPT_NAME | varchar2 | 50 | 0 | Y | N |  | 开方科室名称 |
| 29 | SPECS | varchar2 | 50 | 0 | Y | N |  | 药品规格 |
| 30 | USAGE_CODE | varchar2 | 50 | 0 | Y | N |  | 药品用法编码 |
| 31 | USAGE_NAME | varchar2 | 50 | 0 | Y | N |  | 药品用法名称 |
| 32 | FREQUENCY_CODE | varchar2 | 50 | 0 | Y | N |  | 药品频次编码 |
| 33 | FREQUENCY_NAME | varchar2 | 50 | 0 | Y | N |  | 药品频次名称 |
| 34 | NURSE_CELL_CODE | varchar2 | 255 | 0 | Y | N |  | 住院病区代码 |
| 35 | NURSE_CELL_NAME | varchar2 | 255 | 0 | Y | N |  | 住院病区名称 |
| 36 | BED_NUM | varchar2 | 255 | 0 | Y | N |  | 床号(住院开处方用) |
| 37 | GROUP_NO | varchar2 | 50 | 0 | Y | N |  | 组号 |
| 38 | ORDER_ID | number | 21 | 0 | Y | N |  | 特殊处方因结算异常关联条件1 |
| 39 | ORDER_ITEM_ID | number | 21 | 0 | Y | N |  | 特殊处方因结算异常关联条件2 |
| 40 | ORDER_ITEM_COST_ID | number | 21 | 0 | Y | N |  | 特殊处方因结算异常关联条件3 |

### 60. PHA_STORAGE（药房库存信息）

- **表名**：`PHA_STORAGE`
- **中文说明**：药房库存信息
- **字段数**：29
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | varchar2 | 50 | 0 | N | Y |  | 库存为主键(库存id) |
| 2 | STORE_CODE | varchar2 | 16 | 0 | Y | N |  | 库房识别 |
| 3 | ORG_CODE | varchar2 | 32 | 0 | Y | N |  | 机构编码 |
| 4 | DRUG_PRI | varchar2 | 50 | 0 | Y | N |  | 药品主键 |
| 5 | BATCH_NO | varchar2 | 50 | 0 | Y | N |  | 药品批号 |
| 6 | EXPIRE_DATE | timestamp(6) | 11 | 6 | Y | N |  | 药品效期 |
| 7 | TRADE_PRICE | number | 14 | 6 | N | N |  | 采购价 |
| 8 | RETAIL_PRICE | number | 14 | 6 | Y | N |  | 零售价 |
| 9 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 10 | STORAGE_QUANTITY | number | 12 | 4 | Y | N |  | 库存数量 |
| 11 | STORAGE_COST | number | 12 | 4 | Y | N |  | 进货金额 |
| 12 | WHOLESALE_COST | number | 12 | 4 | Y | N |  | 批发金额 |
| 13 | RETAIL_COST | number | 12 | 4 | Y | N |  | 零售金额 |
| 14 | DRUG_LOC | varchar2 | 1000 | 0 | Y | N |  | 货位编码 |
| 15 | STORAGE_TOPLINE | number | 12 | 4 | Y | N |  | 库存报警上限 |
| 16 | STORAGE_LOWLINE | number | 12 | 4 | Y | N |  | 库存报警下限 |
| 17 | PRODUCT_DATE | timestamp(6) | 11 | 6 | Y | N |  | 生产日期 |
| 18 | STORE_TYPE | number | 4 | 0 | Y | N |  | 库存性质 门户字典store_type，霉变、破损等 |
| 19 | IS_ENABLE | char | 1 | 0 | Y | N | 'Y' | 启用状态：Y启用、N禁用 |
| 20 | CREATE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 创建者id |
| 21 | CREATE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 创建者姓名 |
| 22 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建日期 |
| 23 | MODIFY_USER_ID | varchar2 | 30 | 0 | Y | N |  | 修改者id |
| 24 | MODIFY_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 修改者姓名 |
| 25 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  | 修改日期 |
| 26 | IS_DELETED | number | 10 | 0 | Y | N | 0 | 删除标识 0未删除 1已删除 |
| 27 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 删除时间 |
| 28 | DELETE_USER_ID | varchar2 | 30 | 0 | Y | N |  | 删除人id |
| 29 | DELETE_USER_NAME | varchar2 | 30 | 0 | Y | N |  | 删除人姓名 |

### 61. PHA_VISIT_DISPDETAIL（门诊发药申请详情?）

- **表名**：`PHA_VISIT_DISPDETAIL`
- **中文说明**：门诊发药申请详情?
- **字段数**：39
- **主键字段**：RECORD_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | RECORD_NO | varchar2 | 50 | 0 | N | Y |  | 主键 |
| 2 | ORG_CODE | varchar2 | 32 | 0 | N | N | '1' | 机构编码 |
| 3 | PHA_CODE | varchar2 | 50 | 0 | N | N |  | 药房编码 |
| 4 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  | 药品主键 |
| 5 | PRODUCT_DATE | date | 7 | 0 | Y | N |  | 生产日期 |
| 6 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  | 批次号 |
| 7 | EXPIRE_DATE | date | 7 | 0 | Y | N |  | 校期 |
| 8 | TRADE_PRICE | number | 14 | 6 | N | N |  | 进价 |
| 9 | RETAIL_PRICE | number | 14 | 6 | N | N |  | 零售价 |
| 10 | WHOLESALE_PRICE | number | 14 | 6 | Y | N |  | 批发价 |
| 11 | STORAGE_COST | number | 12 | 4 | N | N | 0 | 进价金额 |
| 12 | WHOLESALE_COST | number | 12 | 4 | N | N | 0 | 批发金额 |
| 13 | RETAIL_COST | number | 12 | 4 | N | N | 0 | 零售价金额 |
| 14 | DRUG_QUANTITY | number | 12 | 4 | N | N | 0 | 发药数量 |
| 15 | PHA_SPECS | varchar2 | 64 | 0 | Y | N |  | 药房规格 |
| 16 | PHA_UNIT | varchar2 | 16 | 0 | Y | N |  | 药房单位编码 |
| 17 | PHA_PACKAGE | varchar2 | 50 | 0 | Y | N |  | 药房包装数量 |
| 18 | WINDOW_NO | varchar2 | 50 | 0 | Y | N |  | 窗口号 |
| 19 | DIS_DATE | timestamp(6) | 11 | 6 | N | N |  | 发药日期 |
| 20 | PRESC_NO | varchar2 | 50 | 0 | N | N | 0 | 处方号 |
| 21 | PRESC_KIND | varchar2 | 50 | 0 | N | N |  | 处方类型 00自费 02医保 15是工伤 10复杂病种 05统筹 08补充 03门规或大病 |
| 22 | INVOICE_NO | varchar2 | 50 | 0 | Y | N |  | 发票号 |
| 23 | PRESC_DETAILID | varchar2 | 50 | 0 | N | N |  | 处方明细号码（关联PHA_CLI_REQUEST_DRUG的PRESC_DETAIL_ID） |
| 24 | PHA_ID | varchar2 | 50 | 0 | N | N | 0 | 药房库存id |
| 25 | RETURN_RECORDNO | varchar2 | 50 | 0 | Y | N |  | 退药关联记录号 |
| 26 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  | 创建人id |
| 27 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 创建人姓名 |
| 28 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 29 | SEND_FLAG | varchar2 | 6 | 0 | Y | N |  | 发药标识 send 发药 return 退药(关联PHA_CLI_REQUEST_DRUG表的CLI_FLAG) |
| 30 | REVIEWER_CODE | varchar2 | 50 | 0 | Y | N |  | 审核人编码 |
| 31 | REVIEWER_NAME | varchar2 | 50 | 0 | Y | N |  | 审核人名称 |
| 32 | ALLOT_CODE | varchar2 | 50 | 0 | Y | N |  | 调配人编码 |
| 33 | ALLOT_NAME | varchar2 | 50 | 0 | Y | N |  | 调配人名称 |
| 34 | CHECK_CODE | varchar2 | 50 | 0 | Y | N |  | 核对人编码 |
| 35 | CHECK_NAME | varchar2 | 50 | 0 | Y | N |  | 核对人名称 |
| 36 | DISPENSING_CODE | varchar2 | 50 | 0 | Y | N |  | 发药人编码 |
| 37 | DISPENSING_NAME | varchar2 | 50 | 0 | Y | N |  | 发药人名称 |
| 38 | RETURN_QUANTITY | number | 12 | 4 | Y | N |  | 退药数量 |
| 39 | CLI_INP_FLAG | varchar2 | 10 | 0 | Y | N | '1' | 处方标识：1 门诊 2 住院 |

### 62. PHA_VISIT_DISPMASTER

- **表名**：`PHA_VISIT_DISPMASTER`
- **字段数**：14
- **主键字段**：ORG_CODE, PHA_CODE, PRESC_NO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 50 | 0 | N | Y |  | 机构编码 |
| 2 | PHA_CODE | varchar2 | 50 | 0 | N | Y |  | 药房编码 |
| 3 | PRESC_NO | varchar2 | 50 | 0 | N | Y |  | 处方号 |
| 4 | PRESC_KIND | varchar2 | 50 | 0 | Y | N |  | 处方类型 |
| 5 | INVOICE_NO | varchar2 | 50 | 0 | Y | N |  | 发票号 |
| 6 | PRESC_DETAILID | varchar2 | 50 | 0 | Y | N |  | 处方明细号 |
| 7 | CHECK_STATE | number | 1 | 0 | Y | N | 0 | 发药状态 |
| 8 | CHECK_USER | varchar2 | 50 | 0 | Y | N |  | 发药人编码 |
| 9 | CHECK_USER_NAME | varchar2 | 50 | 0 | Y | N |  | 发药人名称 |
| 10 | CHECK_DATE | timestamp(6) | 11 | 6 | Y | N |  | 发药日期 |
| 11 | PHA_ID | varchar2 | 50 | 0 | Y | N |  | 药房库存id |
| 12 | RETURN_RECORDNO | varchar2 | 50 | 0 | Y | N |  | 退药主键id |
| 13 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 14 | PRESC_KIND_NAME | varchar2 | 50 | 0 | Y | N |  | 处方类型名称 |

### 63. PUB_CONFIG（系统配置表）

- **表名**：`PUB_CONFIG`
- **中文说明**：系统配置表
- **字段数**：22
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ID | varchar2 | 100 | 0 | N | Y |  | 配置主键 |
| 2 | BUSINESS_TYPE_ID | varchar2 | 100 | 0 | Y | N |  | 业务类型id |
| 3 | CONFIG_CODE | varchar2 | 100 | 0 | N | N |  | 配置名称编码 |
| 4 | CONFIG_NAME | varchar2 | 100 | 0 | N | N |  | 配置名称 |
| 5 | DISPLAY_FLAG | char | 1 | 0 | N | N | '1' | 是否显示该配置项(是否启用)0:不显示 1:显示 |
| 6 | INPUT_CODE | varchar2 | 255 | 0 | Y | N | '' | 简拼 |
| 7 | FULL_CODE | varchar2 | 255 | 0 | Y | N | '' | 全拼 |
| 8 | MEMO | varchar2 | 300 | 0 | Y | N |  | 备注 |
| 9 | SORT_ORDER | number | 0 | -127 | N | N | 1 | 显示顺序(排序) |
| 10 | CONFIG_VALUE | varchar2 | 100 | 0 | Y | N |  | 配置内容 |
| 11 | IS_DELETED | number | 1 | 0 | Y | N | 0 | 删除标示：0正常、1删除 |
| 12 | CREATE_TIME | date | 7 | 0 | Y | N |  | 创建时间 |
| 13 | MODIFY_TIME | date | 7 | 0 | Y | N |  | 修改时间 |
| 14 | DELETE_TIME | date | 7 | 0 | Y | N |  | 删除时间 |
| 15 | CREATE_USER_ID | varchar2 | 100 | 0 | Y | N |  | 创建人ID |
| 16 | CREATE_USER_NAME | varchar2 | 100 | 0 | Y | N |  | 创建人姓名 |
| 17 | MODIFY_USER_ID | varchar2 | 100 | 0 | Y | N |  | 修改人ID |
| 18 | MODIFY_USER_NAME | varchar2 | 100 | 0 | Y | N |  | 修改人姓名 |
| 19 | DELETE_USER_ID | varchar2 | 100 | 0 | Y | N |  | 删除人ID |
| 20 | DELETE_USER_NAME | varchar2 | 100 | 0 | Y | N |  | 删除人姓名 |
| 21 | COCKPIT_FLAG | varchar2 | 50 | 0 | Y | N | '0' | 驾驶舱标志：0、否 1、是 |
| 22 | DEPT_FLAG | varchar2 | 20 | 0 | Y | N |  | 科室标志：0、药库 1、门诊药房 2、住院药房 |

### 64. PUB_CONFIG_SET（系统配置选项设置表）

- **表名**：`PUB_CONFIG_SET`
- **中文说明**：系统配置选项设置表
- **字段数**：15
- **主键字段**：ID

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ID | varchar2 | 100 | 0 | N | Y |  | 主键ID |
| 2 | CONFIG_CODE | varchar2 | 100 | 0 | N | N |  | 配置编码 |
| 3 | CONFIG_SET_CODE | varchar2 | 100 | 0 | N | N |  | 配置选项编码 |
| 4 | CONFIG_SET_NAME | varchar2 | 100 | 0 | N | N |  | 配置选项内容 |
| 5 | MEMO | varchar2 | 300 | 0 | Y | N |  | 备注 |
| 6 | IS_DELETED | number | 1 | 0 | Y | N | 0 | 删除标示：0正常、1删除 |
| 7 | CREATE_TIME | date | 7 | 0 | Y | N |  | 创建时间 |
| 8 | MODIFY_TIME | date | 7 | 0 | Y | N |  | 修改时间 |
| 9 | DELETE_TIME | date | 7 | 0 | Y | N |  | 删除时间 |
| 10 | CREATE_USER_ID | varchar2 | 100 | 0 | Y | N |  | 创建人ID |
| 11 | CREATE_USER_NAME | varchar2 | 100 | 0 | Y | N |  | 创建人姓名 |
| 12 | MODIFY_USER_ID | varchar2 | 100 | 0 | Y | N |  | 修改人ID |
| 13 | MODIFY_USER_NAME | varchar2 | 100 | 0 | Y | N |  | 修改人姓名 |
| 14 | DELETE_USER_ID | varchar2 | 100 | 0 | Y | N |  | 删除人ID |
| 15 | DELETE_USER_NAME | varchar2 | 100 | 0 | Y | N |  | 删除人姓名 |

### 65. SUPPLIER_IN_DETAIL（采购入库明细）

- **表名**：`SUPPLIER_IN_DETAIL`
- **中文说明**：采购入库明细
- **字段数**：26

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | Y | N | '1' |  |
| 2 | SORT_NO | number | 22 | 0 | N | N |  |  |
| 3 | IN_KIND | varchar2 | 50 | 0 | Y | N |  |  |
| 4 | IN_BILLNO | varchar2 | 50 | 0 | N | N |  |  |
| 5 | DRUG_PRI | varchar2 | 50 | 0 | N | N |  |  |
| 6 | BATCH_NO | varchar2 | 32 | 0 | Y | N |  |  |
| 7 | EXPIRE_DATE | timestamp(6) | 11 | 6 | Y | N |  |  |
| 8 | TRADE_PRICE | number | 14 | 6 | N | N |  |  |
| 9 | IN_QUANTITY | number | 12 | 4 | N | N | 0 |  |
| 10 | PASS_QUANTITY | number | 12 | 4 | N | N | 0 |  |
| 11 | IN_COST | number | 12 | 4 | N | N | 0 |  |
| 12 | BILLNO | varchar2 | 32 | 0 | Y | N |  |  |
| 13 | DISCOUNT | number | 12 | 4 | Y | N |  |  |
| 14 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  |  |
| 15 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  |  |
| 16 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  |  |
| 17 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  |  |
| 18 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  |  |
| 19 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  |  |
| 20 | IS_DELETED | number | 10 | 0 | Y | N | 0 |  |
| 21 | DELETE_TIME | timestamp(6) | 11 | 6 | Y | N |  |  |
| 22 | DELETE_USER_ID | varchar2 | 50 | 0 | Y | N |  |  |
| 23 | DELETE_USER_NAME | varchar2 | 50 | 0 | Y | N |  |  |
| 24 | PRODUCT_DATE | timestamp(6) | 11 | 6 | Y | N |  |  |
| 25 | DRUG_LOC | varchar2 | 50 | 0 | Y | N |  |  |
| 26 | PLAN_NO | varchar2 | 50 | 0 | Y | N |  |  |

### 66. SUPPLIER_IN_MASTER（采购入库主表对象）

- **表名**：`SUPPLIER_IN_MASTER`
- **中文说明**：采购入库主表对象
- **字段数**：18
- **主键字段**：IN_BILLNO

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ORG_CODE | varchar2 | 32 | 0 | Y | N |  |  |
| 2 | IN_BILLNO | varchar2 | 50 | 0 | N | Y |  |  |
| 3 | IN_KIND | varchar2 | 50 | 0 | Y | N |  |  |
| 4 | IN_STATE | number | 1 | 0 | Y | N |  |  |
| 5 | IN_DATE | date | 7 | 0 | Y | N |  |  |
| 6 | IN_OPER | varchar2 | 16 | 0 | Y | N |  |  |
| 7 | SUPPLIER_CODE | varchar2 | 32 | 0 | Y | N |  |  |
| 8 | MEMO | varchar2 | 120 | 0 | Y | N |  |  |
| 9 | CREATE_USER_ID | varchar2 | 50 | 0 | Y | N |  |  |
| 10 | CREATE_USER_NAME | varchar2 | 50 | 0 | Y | N |  |  |
| 11 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  |  |
| 12 | MODIFY_USER_ID | varchar2 | 50 | 0 | Y | N |  |  |
| 13 | MODIFY_USER_NAME | varchar2 | 50 | 0 | Y | N |  |  |
| 14 | MODIFY_TIME | timestamp(6) | 11 | 6 | Y | N |  |  |
| 15 | NOTE_NO | varchar2 | 64 | 0 | Y | N |  |  |
| 16 | BILLNO | varchar2 | 50 | 0 | Y | N |  |  |
| 17 | PLAN_OPER | varchar2 | 50 | 0 | Y | N |  |  |
| 18 | PLAN_NO | varchar2 | 50 | 0 | Y | N |  |  |

### 67. SYSTEM_CONFIG（系统配置项）

- **表名**：`SYSTEM_CONFIG`
- **中文说明**：系统配置项
- **字段数**：7

| 编号 | 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | CONFIG_ID | varchar2 | 50 | 0 | Y | N | sys_guid() | 配置id |
| 2 | CONFIG_CODE | varchar2 | 50 | 0 | Y | N |  | 配置项编码 |
| 3 | CONFIG_NAME | varchar2 | 50 | 0 | Y | N |  | 配置名称 |
| 4 | CONFIG_DESC | varchar2 | 1000 | 0 | Y | N |  | 配置描述 |
| 5 | GROUP_NO | varchar2 | 50 | 0 | Y | N |  | 一组标识 |
| 6 | CREATE_TIME | timestamp(6) | 11 | 6 | Y | N |  | 创建时间 |
| 7 | CONFIG_VAL | varchar2 | 50 | 0 | Y | N |  |  |
