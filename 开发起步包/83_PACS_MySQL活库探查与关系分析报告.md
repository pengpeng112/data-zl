> 类别：证据报告

# PACS MySQL 活库探查与关系分析报告

## 1. 总体结论

- 已经由部署服务器只读连接 `10.10.10.191:3306`，数据库版本为 MySQL 8.4.0，主机标识为 `RISServer191`。
- 实例开放 10 个非系统数据库，共 494 张基础表、42 个视图、5,039 个字段、23 个已声明外键；业务主库为 `gecris`。
- `gecris` 包含患者、申请、检查、报告、报告历史、MPPS 和 PACS Study 主线：345 表、36 视图、3,732 字段、19 个外键。
- 对 10 条核心关系各取最近最多 10,000 个非空子键验证：8 条 100% 命中；检查到报告为 88.74%；PACS Study 到 RIS 检查为 96.39%。部分覆盖关系不得作为无条件强外键使用。
- 采集时发现一个视图定义自身嵌入影像访问参数，快照生成前已统一脱敏；报告和快照不保留该值。
- 本轮未写入平台资产库。源库会话强制 `TRANSACTION READ ONLY`、`READ UNCOMMITTED`、60 秒语句上限并最终 rollback，业务源库 DML/DDL 为 0。

## 2. 实例与数据库层级

平台中应按以下层级登记：

`PACS → 10.10.10.191:3306 → 数据库 → 表/视图 → 字段`

| 数据库 | 主要作用 | 表 | 视图 | 字段 | 外键列 |
|---|---|---:|---:|---:|---:|
| `gecris` | RIS/PACS 主业务库 | 345 | 36 | 3,732 | 19 |
| `iws_bi` | BI/组织权限视图 | 33 | 6 | 392 | 0 |
| `mywk` | 工作流/分发历史 | 55 | 0 | 379 | 0 |
| `hl7db` | HL7 接口 | 10 | 0 | 112 | 0 |
| `audit` | 审计 | 6 | 0 | 55 | 4 |
| `gecbroker` | 消息代理 | 6 | 0 | 104 | 0 |
| `extendnotify` | 扩展通知 | 3 | 0 | 55 | 0 |
| `knowbase` | 知识库 | 17 | 0 | 95 | 0 |
| `openjmsdb` | JMS 消息 | 7 | 0 | 29 | 0 |
| `reporting` | 报表辅助 | 12 | 0 | 86 | 0 |

这些数据库属于同一 IP/端口实例，不应按数据库名称重复创建多个一级 PACS 系统。

## 3. 主业务对象

| 对象 | 近似行数 | 作用 |
|---|---:|---|
| `gecris.PatientInfo` | 472,090 | 患者主档，主键 `PatientIntraID` |
| `gecris.OrderInfo` | 1,008,236 | 检查申请，声明外键到患者 |
| `gecris.ExamInfo` | 1,038,257 | RIS 检查主档，连接患者、申请、报告及 DICOM UID |
| `gecris.Report` | 1,017,506 | 当前报告正文与状态 |
| `gecris.ReportAction` | 932,753 | 报告操作与版本动作 |
| `gecris.ReportHistory` | 855,724 | 报告历史内容 |
| `gecris.MPPS` | 1,173,448 | 检查与 DICOM Study/Series 执行信息 |
| `gecris.pacsstudy` | 603,782 | PACS Study 索引 |
| `gecris.exam_attach_info` | 645,193 | 检查扩展信息 |

`CDR_CHECK_REPORT`、`EMR_EXAM_IMAGE_PATH`、`EMR_EXAM_IMAGE_REP`、`IMAGE_INFO`、`SERIES_INFO`、`V_RIS_ExamInfo`、`exam_info` 等视图提供了患者—检查—报告—影像的静态关系证据。

## 4. 核心关系验证

| 编号 | 子对象及字段 | 父对象及字段 | 样本 | 命中 | 结论 |
|---|---|---|---:|---:|---|
| P01 | `OrderInfo.PatientIntraID` | `PatientInfo.PatientIntraID` | 10,000 | 100% | 已声明外键，强关系 |
| P02 | `ExamInfo.PatientIntraID` | `PatientInfo.PatientIntraID` | 10,000 | 100% | 检查归属患者 |
| P03 | `ExamInfo.OrderID` | `OrderInfo.OrderID` | 10,000 | 100% | 检查对应申请 |
| P04 | `ExamInfo.ReportID` | `Report.ReportID` | 10,000 | 88.74% | 部分覆盖；可能含未成文、历史或清理差异 |
| P05 | `ReportAction.ReportID` | `Report.ReportID` | 10,000 | 100% | 报告操作归属当前报告 |
| P06 | `ReportAction.ReportHistoryID` | `ReportHistory.ReportHistoryID` | 10,000 | 100% | 报告操作关联历史版本 |
| P07 | `ReportParticipant.ReportActionID` | `ReportAction.ReportActionID` | 10,000 | 100% | 报告参与者关联操作 |
| P08 | `MPPS.ExamID` | `ExamInfo.ExamID` | 10,000 | 100% | DICOM 执行步骤关联检查 |
| P09 | `exam_attach_info.ExamID` | `ExamInfo.ExamID` | 10,000 | 100% | 检查扩展信息 |
| P10 | `pacsstudy.study_instance_uid` | `ExamInfo.StudyInstanceUID` | 10,000 | 96.39% | 部分覆盖；独立采集、历史归档或未匹配 Study 需保留 |

所有验证均为限量样本证据，不替代完整性约束。P04、P10 应标记 `partial`，不能因命名一致直接升级为 A 级强关系。

## 5. 安全与性能边界

- MySQL 实例级 `read_only` 当前为关闭状态，但本轮连接显式开启会话只读事务；没有执行任何 INSERT、UPDATE、DELETE、DDL 或存储过程。
- 只输出聚合数量和结构信息，不采集患者姓名、证件、电话、地址、报告正文或影像内容。
- 百万级业务表仅使用有界键样本；禁止后续 AI 对 `ExamInfo`、`Report`、`MPPS` 等执行无条件全表 JOIN。
- 快照中的视图 SQL 必须继续经过 URL 密码、Token 和连接串脱敏后才可进入平台或 Git。

## 6. 后续平台接入

1. 以 `10.10.10.191:3306` 建立一个物理连接，凭据只进入受控凭据存储；API 不回显密码。
2. 在连接下导入 10 个数据库和各自表、视图、字段；主业务域优先展示 `gecris`。
3. 平台库备份后先执行元数据导入 dry-run，再导入 8 条完整覆盖关系；P04、P10 保持部分关系。
4. 23 个声明外键可以作为结构关系导入，但必须与业务关系分层显示，不能把材料、配置、XDS 外键混入临床主线。
5. 与 ODS/PACS 或 HIS 检查表的跨库关系必须另行通过申请号、检查号或 Study UID 限量验证，本轮不作推断。

## 7. 证据与复现入口

- `83_PACS_MySQL元数据快照.json`
- `83_PACS_MySQL关系验证结果.json`
- `backend/scripts/harvest_pacs_mysql_readonly.py`
- `backend/scripts/verify_pacs_mysql_relationships_readonly.py`

脚本只从环境变量读取凭据；生产镜像没有增加依赖，采集使用现有镜像的一次性 `--rm` 容器。
