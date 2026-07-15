> 类别：证据报告

# 超声内镜 SQL Server 多库活库探查与关系分析报告

## 1. 结论

- 已以只读方式连通 `10.10.10.161:1433`。实例为 SQL Server 2012（11.0.2100.60），旧协议兼容需使用 TDS 7.0。
- 同一 IP/端口应在平台中登记为一个物理数据库实例，实例下保留 6 个业务数据库：`MedcareUS`、`MedcareES`、`AnyImage`、`AnyImageSLES`、`PacsServer`、`MdcArchiveBrowse`，不得拆成 6 个一级业务系统。
- 共采集 766 张表、59 个视图、10,697 个字段；活库未声明外键。因此本报告中的关系分为“限量数据验证关系”和“视图 SQL 静态线索”，不能冒充数据库外键。
- 超声预约到报告、患者到检查、PACS 检查/序列/影像、归档患者/检查/明细等 10 条关系，在每条最多 10,000 个非空键的样本中均为 100% 命中。
- 内镜预约表的 `AccessionNo` 当前无非空样本，不能据此确认它与报告库 `AccessNo` 的关系。对其他候选字段的在线组合试探曾触发 60 秒超时，已停止，不以超时结果推断关系。
- 本轮只生成本地证据和可复现脚本，未导入平台资产库；业务源库 DML/DDL 为 0。

## 2. 数据库资产范围

| 数据库 | 主要角色 | 表 | 视图 | 字段 | 代表对象 |
|---|---|---:|---:|---:|---|
| `MedcareUS` | 超声预约与基础配置 | 49 | 2 | 472 | `dbo.预约登记`（411,317 行） |
| `MedcareES` | 内镜预约与基础配置 | 43 | 5 | 698 | `dbo.预约登记`（57,124 行） |
| `AnyImage` | 超声/内镜患者、检查与报告 | 389 | 38 | 6,195 | `grid.BHosCheckUS`（922,579 行）、`grid.BHosPatient`（662,065 行） |
| `AnyImageSLES` | 内镜患者、检查与报告支线 | 222 | 14 | 2,717 | `grid.BHosCheckES`（156,700 行）、`grid.BHosPatient`（120,446 行） |
| `PacsServer` | 检查、序列和影像对象 | 46 | 0 | 447 | `grid.BHosStudy`（847,841 行）、`BHosSeries`（18,042,954 行）、`BHosImages`（18,049,709 行） |
| `MdcArchiveBrowse` | 归档患者与检查索引 | 17 | 0 | 168 | `dbo.BPatientIndex`（295,933 行）、`BExamIndex`（561,801 行）、`BExamDetail`（616,702 行） |

建议平台资源层级固定为：

`超声内镜系统 → 10.10.10.161:1433 → 数据库 → Schema → 表/视图 → 字段`

其中超声、内镜、PACS、归档是同一物理实例内的业务模块或数据库，不应在“业务系统”一级按名称重复展示。

## 3. 已验证关系

| 编号 | 子对象与键 | 父对象与键 | 样本 | 命中率 | 结论 |
|---|---|---|---:|---:|---|
| U01 | `MedcareUS.dbo.预约登记.AccessNo` | `AnyImage.grid.BHosCheckUS.AccessNo` | 10,000 | 100% | 超声预约到检查报告主线 |
| A01 | `AnyImage.grid.BHosCheckUS.MID` | `AnyImage.grid.BHosPatient.ID` | 10,000 | 100% | 超声检查归属患者 |
| A02 | `AnyImage.grid.BHosCheckES.MID` | `AnyImage.grid.BHosPatient.ID` | 10,000 | 100% | AnyImage 内镜检查归属患者 |
| S01 | `AnyImageSLES.grid.BHosCheckES.MID` | `AnyImageSLES.grid.BHosPatient.ID` | 10,000 | 100% | SLES 内镜检查归属患者 |
| P01 | `PacsServer.grid.BHosSeries.StudyID` | `PacsServer.grid.BHosStudy.ID` | 10,000 | 100% | 检查到序列 |
| P02 | `PacsServer.grid.BHosImages.StudyID` | `PacsServer.grid.BHosStudy.ID` | 10,000 | 100% | 影像到检查 |
| P03 | `PacsServer.grid.BHosImages.SeriesID` | `PacsServer.grid.BHosSeries.ID` | 10,000 | 100% | 影像到序列 |
| M01 | `MdcArchiveBrowse.dbo.BExamIndex.MID` | `BPatientIndex.ID` | 10,000 | 100% | 归档检查到患者 |
| M02 | `MdcArchiveBrowse.dbo.BExamDetail.ExamID` | `BExamIndex.ID` | 10,000 | 100% | 归档明细到检查 |
| M03 | `MdcArchiveBrowse.dbo.BExamDetail.MID` | `BPatientIndex.ID` | 10,000 | 100% | 归档明细到患者 |

验证采用 `READ UNCOMMITTED`、`WITH (NOLOCK)`、`TOP (10000)`、5 秒锁等待上限和只读回滚。结果仅证明限定样本中的键覆盖，不等同于数据库约束。

## 4. 内镜关系的保留意见

`MedcareES.dbo.预约登记.AccessionNo` 对 `AnyImageSLES.grid.BHosCheckES.AccessNo` 和 `AnyImage.grid.BHosCheckES.AccessNo` 的两项检查均无非空子键，属于“无可验证样本”，不是关系不成立，也不能标记为已验证。

快照中的 `EMR_EXAM_IMAGE_PATH`、`EMR_EXAM_IMAGE_REP`、`exam_info`、`PT_Report_ES`、`T_ITF_ES`、`grid.BHosViewApplyInfoES`、`grid.BHosViewCheckESRpt` 等视图表明报告业务实际使用 `AccessNo`、`PatientID1`、`HISID1`、`InPatNo`、`VisitID` 等键。后续应先解析这些视图的完整 SQL，再在夜间对单一候选键做有索引、可超时中止的验证；禁止在生产时段枚举字段并扫大表。

## 5. 平台接入建议

1. 建立一个物理连接端点，以 `host + port` 作为端点去重依据；凭据只写受控凭据存储，读取接口只返回是否已配置。
2. 在端点下登记 6 个数据库，再按真实 Schema 展开。`AnyImage`、`AnyImageSLES`、`PacsServer` 的核心表位于 `grid`，不可错误登记为 `dbo`。
3. 先导入元数据，再分级导入本报告 10 条已验证关系；E01/E02 仅作为负证据留档，不进入强关系图谱。
4. `BHosSeries`、`BHosImages` 等千万级表只采目录元数据；关系复验必须由小样本键驱动，禁止全表扫描。
5. 正式导入平台前先备份平台库、执行 dry-run、检查稳定节点 ID 冲突，并保证源库连接器继续拒绝 DML/DDL。

## 6. 复现文件

- 元数据快照：`82_超声内镜SQLServer多库元数据快照.json`
- 关系验证结果：`82_超声内镜SQLServer关系验证结果.json`
- 元数据采集脚本：`backend/scripts/harvest_ultrasound_endoscopy_sqlserver_readonly.py`
- 关系验证脚本：`backend/scripts/verify_ultrasound_endoscopy_relationships_readonly.py`

连接凭据未写入上述文件，运行时仅从环境变量读取。探查使用一次性容器和临时驱动文件，未修改生产 API 镜像。
