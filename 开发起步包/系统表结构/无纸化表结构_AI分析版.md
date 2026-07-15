# 无纸化病案管理信息系统数据结构手册

> 转换说明：本文件由原始 `.doc` 文档转换为便于 AI 检索、分析和生成 SQL 的 Markdown 结构。字段名、字段类型、字段说明及备注均按源文档保留；源文档中可能存在重复字段、拼写错误、说明错位或缺失，本次未擅自进行业务修订。

## 文档结构

- 每个数据表单独作为二级标题。
- 字段定义统一为 `FieldName / Data Type / Description / Memo` 四列。
- `NN` 表示字段不允许为空（NOT NULL）。
- 表间关联、状态值和值域说明保留在 `Memo` 列。

## 数据表索引

共整理 **42** 张数据表。

| 序号 | 表名 | 用途/说明 |
|---:|---|---|
| 1 | `TMRDDE` | 基本信息表 |
| 2 | `T_MSS_MAIN` | 患者采集信息表 |
| 3 | `T_MSS_SCANRECORD` | 采集图片详细信息表 |
| 4 | `T_MSS_SCANRECORDHISTORY` | 图片召回备份表 |
| 5 | `T_MSS_PRINTLISTQUEUE` | 数据采集队列表 |
| 6 | `T_MSS_PRINTQUEUEDETAIL` | 数据采集队列详细表 |
| 7 | `T_MSS_ITFCONFIG` | 采集配置表（采集服务） |
| 8 | `T_MSS_COLLECTPC` | 采集配置表（模块化采集） |
| 9 | `T_MSS_COLLECTLIST` | 采集方式配置表（模块化） |
| 10 | `T_MSS_COLLECTMETHOD` | 模块化采集方法配置表 |
| 11 | `T_MSS_MAINHISTORY` | 修改病案历史信息 |
| 12 | `T_MSS_MRCONTROL` | 采集质控记录表 |
| 13 | `T_MSS_REQUESTMRD` | 病历借阅申请表 |
| 14 | `T_MSS_APPRECALL` | 病历召回申请表 |
| 15 | `TMRDOP` | 手术信息表 |
| 16 | `T_MSS_BBS` | 病历讨论记录表 |
| 17 | `T_MSS_BBSTYPEDICT` | 讨论分类维护表 |
| 18 | `T_MSS_BBSREPLY` | 图片讨论回复表 |
| 19 | `T_MSS_CATEGORY` | 病案分类表 |
| 20 | `TCTRYM` | 国家代码维护 |
| 21 | `T_MSS_CATEGORYMAPPING` | 病案分类详细表 |
| 22 | `T_MSS_CATGROUP` | 打印套餐维护表 |
| 23 | `T_MSS_GROUPLIST` | 打印套餐详细表 |
| 24 | `T_MCP_EAA_DETAIL` | 病历打印申请表 |
| 25 | `T_MCP_CER_LIST` | 病历打印人信息登记表 |
| 26 | `T_MSS_PRINTLOG` | 病历打印记录主表 |
| 27 | `T_MSS_PRINTDETAIL` | 病历打印详细记录表 |
| 28 | `T_MSS_CONFIG` | 总参数配置表 |
| 29 | `T_MSS_COLLECTLOG` | 模块化采集日志表 |
| 30 | `T_MSS_DJFL` | 单机分类配置表 |
| 31 | `T_MSS_DJJQ` | 单机分类配置表 |
| 32 | `T_MSS_DJLOG` | 单机系统采集日志 |
| 33 | `T_MSS_SHAREPATH` | 图片保存路径详细配置表 |
| 34 | `TOFFIM` | 科室维护表 |
| 35 | `T_MSS_LOG` | 操作记录表 |
| 36 | `T_MSS_CHECKCONTROL` | 自动质控数据配置表 |
| 37 | `T_MSS_CONTROLLOG` | 质控记录表 |
| 38 | `T_MSS_DJCASIGNLOG` | CA签名记录表 |
| 39 | `T_MSS_PARAM` | 保密等级配置表 |
| 40 | `T_MSS_EMP_DICT` | 用户表 |
| 41 | `T_MSS_ROLE` | 角色表 |
| 42 | `T_MSS_AUTHMAPPING` | 权限表 |

## 参数约定说明

- **NN**：NOT NULL的简写，指该字段不允许为空。

- **FieldName**：字段名。

- **Data Type**：字段数据类型。最为常见的类型有VARCHAR2（字符型）、NUMBER（数据型），DATE（日期型）等。

- **Description**：字段含义描述

- **Memo**：字段补充说明。

## `TMRDDE` — 基本信息表

- **表名**：`TMRDDE`
- **用途/说明**：基本信息表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FMRDID` | `VARCHAR2(15)` | 病案号 | NN |
| `FBIHID` | `VARCHAR2(15)` | 住院号 |  |
| `FBINCU` | `NUMBER` | 入院次数 |  |
| `FNAME` | `VARCHAR2(50)` | 姓名 |  |
| `FSEX` | `VARCHAR2(1)` | 性别 | 1-男2-女 |
| `FBDATE` | `DATE` | 出生日期 |  |
| `FAGE` | `NUMBER` | 年龄 |  |
| `FMARRY` | `VARCHAR2(1)` | 婚姻 |  |
| `FIDCD` | `VARCHAR2(20)` | 联系人地址 |  |
| `FWADD` | `VARCHAR2(500)` | 家庭住址 |  |
| `FIHDAT` | `DATE` | 入院时间 |  |
| `FIOFFI` | `VARCHAR2(20)` | 入院科室 | 代码，来源于表TOFFIM |
| `FODATE` | `DATE` | 出院时间 |  |
| `FOOFFI` | `VARCHAR2(20)` | 出院科别 | 代码，来源于表TOFFIM |
| `FMZZD` | `VARCHAR2(20)` | 门（急）诊诊断 |  |
| `FZRYS` | `VARCHAR2(200)` | 主（副主）任医师 |  |
| `FZZYS` | `VARCHAR2(200)` | 主治医师 |  |
| `FYJSYS` | `VARCHAR2(50)` | 研究生实习医师 |  |
| `FDATE` | `DATE` | 添加时间 |  |
| `FUSER` | `VARCHAR2(200)` | 添加人 |  |
| `FUDATE` | `DATE` | 修改日期 |  |
| `FLEVWAY` | `VARCHAR2(1)` | 离院方式 | 1医嘱离院2医嘱转院3医嘱转社区卫生服务机构4非医嘱转院5死亡9其他 |
| `FID` | `VARCHAR2(20)` | 病人唯一号 |  |
| `FZYYS` | `VARCHAR2(50)` | 住院医师 |  |
| `FPADD` | `VARCHAR2(150)` | 户口所在地 |  |
| `FMADD` | `VARCHAR2(500)` | 工作单位 |  |
| `FCHILDWEIGHT` | `VARCHAR2(100)` | 新生儿体重 |  |
| `FPATHOLOGICALDIAGNOSEID` | `VARCHAR2(100)` | 病理诊断编码 |  |
| `FPATHOLOGICALNUM` | `VARCHAR2(100)` | 病理号 |  |
| `FPATIENTSOURCE` | `VARCHAR2(100)` | 病人来源 |  |
| `FTRANSFUSIONCOST` | `VARCHAR2(100)` | 输血费 |  |
| `FISTRANSFER` | `VARCHAR2(100)` | 是否转科 |  |
| `FISSURGERY` | `VARCHAR2(100)` | 是否手术 |  |
| `FOPERATIONTYPE` | `VARCHAR2(100)` | 手术类型 |  |
| `WARDCODE` | `VARCHAR2(100)` | 病区编号 |  |
| `FSURGERYCODE` | `VARCHAR2(256)` | 手术编码 |  |
| `FLISFEE` | `VARCHAR2(100)` | 检验费用 |  |
| `FPASCFEE` | `VARCHAR2(100)` | 检查费用 |  |
| `FISAUTOPSC` | `VARCHAR2(100)` | 是否尸检 |  |
| `FICUOFFI` | `VARCHAR2(100)` | 重症监护室编码 |  |
| `FZRHS` | `VARCHAR2(100)` | 责任护士 |  |
| `FCOST` | `VARCHAR2(100)` | 住院费用 |  |
| `FGCYS` | `VARCHAR2(50)` | 管床医生 |  |
| `WARDCODEDESC` | `VARCHAR2(100)` | 病区名称 |  |
| `PATIENTID` | `VARCHAR2(50)` | 病人唯一值 |  |
| `FBARCODE` | `VARCHAR2(50)` | 条码号 |  |
| `FBEDNUMBER` | `VARCHAR2(40)` | 床号 |  |
| `FICD` | `VARCHAR2(40)` | 诊断编码 |  |
| `FICDDESC` | `VARCHAR2(40)` | 诊断描述 |  |
| `NURSESUBDATE` | `DATE` | 护士提交时间 |  |
| `NURSESUBUSER` | `VARCHAR2(50)` | 护士提交人 |  |
| `DOCTORSSUBDATE` | `DATE` | 医生提交时间 |  |
| `DOCTORSSUBUSER` | `VARCHAR2(50)` | 医生提交人 |  |
| `FSIGNER` | `VARCHAR2(50)` | 签收人 |  |
| `FSIGNDATE` | `DATE` | 签收时间 |  |
| `FBWBZ` | `NUMBER` | 病危标志 | 0：否 1：病重 2：病危 |
| `FJZKID` | `VARCHAR2(50)` | 就诊卡号 |  |
| `FEMRID` | `VARCHAR2(50)` | 电子卡号 |  |
| `FENCODEUSERID` | `VARCHAR2(40)` | 编码人ID |  |
| `FENCODEDATE` | `DATE` | 编码时间 |  |
| `FHZ` | `NUMBER` | 是否会诊 | 0：否 1：是 |
| `FQJ` | `NUMBER` | 是否抢救 | 0：否 1：是 |
| `FSYODATE` | `DATE` | 首页出院时间 |  |
| `FLXDH` | `VARCHAR2(20)` | 联系电话 |  |
| `M_PATIENT_ID` | `VARCHAR2(80)` | 档案ID |  |
| `FSXFY` | `NUMBER` | 输血反应 | 0：无 1：有 |
| `FTRANSFERINSTITUTION` | `VARCHAR2(100)` | 转入机构名称 |  |
| `FSJ` | `VARCHAR2(1)` | 尸检 | 1：是 0：否 |
| `FCINICALPATHWAY` | `VARCHAR2(5)` | 临床路径 | 1：是 0：否 |
| `FALLPRESSUREULCER` | `VARCHAR2(1)` | 跌倒压疮 | 1：是 0：否 |
| `FSALCU` | `NUMBER` | 抢救次数 |  |
| `FADMISSION` | `VARCHAR2(100)` | 入院情况 |  |
| `FCHTYP` | `VARCHAR2(500)` | 医疗付费方式 | 有创呼吸机使用时间 |
| `FZRYTJ` | `VARCHAR2(10)` | 入院途径 |  |
| `FSPECIALCAREDAYS` | `NUMBER` | 特级护理天数 |  |
| `FUNPLANNEDSECONDSURGERY` | `VARCHAR2(1)` | 非计划二次手术 |  |
| `FDIFFICYLTCASES` | `NUMBER` | 是否为疑难病例 | 1：是 0：否 |
| `FSEVERE` | `VARCHAR2(20)` | 是否重症患者 | 1：是 0：否 |
| `FTRANSFUSION` | `VARCHAR2(20)` | 是否输血 | 1：是 0：否 |
| `FAGEDESC` | `VARCHAR2(20)` | 年龄单位 |  |
| `FPATIENTID` | `VARCHAR2(20)` | 病人id |  |
| `FFC` | `VARCHAR2(100)` | 封存、解封标志 |  |
| `FGD` | `VARCHAR2(100)` | 归档标识 |  |
| `FZH` | `VARCHAR2(100)` | 召回 |  |
| `FKZR` | `VARCHAR2(50)` | 科主任 |  |
| `FGUIDANGDATE` | `DATE` | 归档时间 |  |
| `FFMZ` | `NUMBER` | 是否麻醉 | 1：是、0：否 |

## `T_MSS_MAIN` — 患者采集信息表

- **表名**：`T_MSS_MAIN`
- **用途/说明**：患者采集信息表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FMAINID` | `VARCHAR2(40)` | 唯一编号 |  |
| `FMRDID` | `VARCHAR2(40)` | 病案号 |  |
| `FBIHID` | `VARCHAR2(40)` | 住院号 |  |
| `FBINCU` | `NUMBER` | 住院次数 |  |
| `FUSER` | `VARCHAR2(50)` | 扫描人 |  |
| `FDATE` | `DATE` | 保存日期 |  |
| `FISAUDIT` | `VARCHAR2(2)` | 病案状态 | 0 待归档 1已归档 2归档未通过 3召回 4质控未通过 5封存 6医疗质控通过 7医疗质控不通过 8护理质控通过 9护理质控不通过 10质控通过 11点击完整病案 12科室已评分 13终末已评分 14医护质控通过 15系统采集不全 16系统验证不通过 |
| `FNUM` | `NUMBER` | 页数 |  |
| `FPATH` | `VARCHAR2(500)` | 保存路径 |  |
| `FAUDITOR` | `VARCHAR2(50)` | 审核人 |  |
| `FAUDITDATE` | `VARCHAR2(1)` | 审核日期 |  |
| `FISUPLOAD` | `NUMBER` | 是否上传 |  |
| `FSHAREPATHID` | `VARCHAR2(40)` | 服务器配置路径 |  |
| `FSECRECYTYPE` | `NUMBER` | 保密类型 |  |
| `FSECRECYGRADE` | `NUMBER` | 病案保密等级 | 默认值为100005不保密 |
| `FREE1` | `VARCHAR2(50)` | 条码号 |  |
| `FFILEID` | `VARCHAR2(50)` | 自动解析文件唯一标识号 住院号和 住院次数 |  |
| `FSOURCE` | `VARCHAR2(2)` | 图片来源类型 |  |
| `FNAME` | `VARCHAR2(200)` | 姓名 |  |
| `FILEDIRNAME` | `VARCHAR2(50)` | 保存文件夹名称 唯一标识 |  |
| `FODATE` | `DATE` | 出院时间 |  |
| `PATIENTID` | `VARCHAR2(50)` | 病人ID |  |
| `FOOFFI` | `VARCHAR2(50)` | 出院科室 |  |
| `FHISTORYNUM` | `NUMBER` | 修改次数 历史修改次数 |  |
| `FBBSNUM` | `NUMBER` | 讨论次数 |  |
| `NOPRINTINGCAUSE` | `VARCHAR2(50)` | 图片是否进行了旋转处理 |  |
| `CANPRINT` | `NUMBER` |  |  |
| `READDAUDIT` | `VARCHAR2(20)` | 补拍审核 | 0 驳回 1 通过 |
| `JIESUANID` | `VARCHAR2(40)` | 结算标识ID |  |
| `PICTURECHECK` | `NUMBER` |  |  |
| `OCRMACHINE` | `VARCHAR2(128)` |  |  |
| `OCRCHECK` | `NUMBER` |  |  |
| `FAPPLYUSER` | `VARCHAR2(50)` |  |  |
| `FAPPLYDATE` | `DATE` |  |  |
| `FMARK` | `VARCHAR2(50)` |  |  |
| `FREE3` | `VARCHAR2(50)` |  |  |
| `FREE2` | `VARCHAR2(50)` |  |  |
| `FPDFPATH` | `VARCHAR2(500)` | PDF上传路径 |  |
| `FNURSINGSTATUS` | `NUMBER` | 护理审核状态 |  |
| `FMEDICALSTATUS` | `NUMBER` | 医疗审核状态 |  |
| `FBARCODE` | `VARCHAR2(100)` | 条码号 |  |
| `FMRDIDREMARKS` | `VARCHAR2(100)` | 病案备注 |  |
| `FNOPRINTINGCAUSE` | `FNOPRINTINGCAUSE` | 禁止打印原因 |  |
| `FISSIGNATURE` | `NUMBER` | 签章是否完成 | 0：为完成 1：已完成 |
| `FFILEDMEDICALSTATUS` | `VARCHAR2(40)` | 终末医疗审核状态 |  |
| `FFILEDNURSINGSTATUS` | `VARCHAR2(40)` | 终末护理审核状态 |  |
| `FPAPERSTATUS` | `NUMBER` | 是否有纸质病历 |  |
| `FSIGNSHORT` | `NUMBER` | 签章优先级 | 0：最低级别 |
| `FISDEPMARK` | `NUMBER` | 科室是否评分 | 1：科室评分 0：未评分 |
| `FISALREAMARK` | `NUMBER` | 终末质控评分 | 1：终末质控评分 0：未评分 |
| `FISREWORK` | `NUMBER` | 返修状态 | 0 or null 未返修 1 已返修 |
| `FISFINALMARK` | `NUMBER` | 病案归档评分 | 1：病案归档评分 0：未评分 |
| `FISREWORKNUM` | `NUMBER` | 返修次数 |  |
| `FSIGNSDATE` | `DATE` | 签章时间 |  |
| `FSEALINGSTATUS` | `VARCHAR2(40)` | 封存状态 | 未封存:0 已封存:5 已解封:25 |
| `FCOLLECTSTATUS` | `NUMBER` | 状态 | EMR未归档:0 待采集:1 采集中:2 系统采集不全:3 系统质控未通过:4 已完成:5 |

## `T_MSS_SCANRECORD` — 采集图片详细信息表

- **表名**：`T_MSS_SCANRECORD`
- **用途/说明**：采集图片详细信息表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FMAINID` | `VARCHAR2(40)` | 唯一编号 | 与T_MSS_MAIN表FMAINID关联 |
| `FRECORDID` | `VARCHAR2(40)` | 主键 | NN |
| `FCATEGORY` | `VARCHAR2(10)` | 文件类别 | 与T-MSS_CATEGORY表FSERIALNUM关联 |
| `FFILENAME` | `VARCHAR2(500)` | 文件名称 |  |
| `FREMARK` | `VARCHAR2(2000)` | 文件详细信息 |  |
| `FSTATUS` | `VARCHAR2(2)` | 页审核状态 | 0 待归档 1已归档 2归档未通过 |
| `FNUM` | `NUMBER` | 图片数量 |  |
| `FISSECRECY` | `NUMBER` | 是否保密 |  |
| `FSOURCEFILENAME` | `VARCHAR2(225)` | 资源服务器文件名称 |  |
| `TEMPLETCODE` | `VARCHAR2(100)` | 外部文件模板编号 |  |
| `TEMPLETID` | `VARCHAR2(100)` | 外部文件模板ID |  |
| `TEMPLETIDDESC` | `VARCHAR2(100)` | 外部文件模板描述 |  |
| `CATEGORYFST` | `NUMBER` | 类别 | 0跟随模板 1手动修改的 |
| `FUSER` | `VARCHAR2(50)` | 扫描人员 |  |
| `CREATETIME` | `DATE` | 创建时间 | Sysdate |
| `OPTIONTYPE` | `NUMBER` | 选择类型 |  |
| `ISSOFTSCAN` | `NUMBER` |  |  |
| `OLDFSERIALNUM` | `VARCHAR2(10)` |  |  |
| `JIESUANID` | `VARCHAR2(40)` |  |  |
| `FISCHECK` | `VARCHAR2(2)` |  |  |
| `FPDFFILENAME` | `VARCHAR2(500)` | 对应PDF文件名 |  |
| `FSAUDITOR` | `VARCHAR2(50)` | 审核人 |  |
| `FSAUDITDATE` | `DATE` | 审核时间 |  |
| `COLLECTPCID` | `VARCHAR2(40)` | 采集服务编码 | 与T_MSS_ITFCONFIG表FID关联或者与T_MSS_COLLECTPC表COLLECTPCID关联 |

## `T_MSS_SCANRECORDHISTORY` — 图片召回备份表

- **表名**：`T_MSS_SCANRECORDHISTORY`
- **用途/说明**：图片召回备份表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FMAINID` | `VARCHAR2(40)` | 唯一编号 | 与T_MSS_MAIN表FMAINID关联 |
| `FRECORDID` | `VARCHAR2(40)` | 召回id |  |
| `FCATEGORY` | `VARCHAR2(10)` | 模块类别 |  |
| `FFILENAME` | `VARCHAR2(500)` | 文件名称 |  |
| `FREMARK` | `VARCHAR2(100)` | 文件详细信息 |  |
| `FSTATUS` | `VARCHAR2(2)` | 状态 |  |
| `FNUM` | `NUMBER` | 排序 |  |
| `FISSECRECY` | `NUMBER` | 是否安全 |  |
| `FSOURCEFILENAME` | `VARCHAR2(225)` | 源文件名字 |  |
| `FTYPE` | `NUMBER` | 类型 | 1：召回备份 2:封存备份 |

## `T_MSS_PRINTLISTQUEUE` — 数据采集队列表

- **表名**：`T_MSS_PRINTLISTQUEUE`
- **用途/说明**：数据采集队列表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(40)` | 主键 | NN |
| `FMRDID` | `VARCHAR2(15)` | 病案号 | NN |
| `FBIHID` | `VARCHAR2(15)` | 住院号 |  |
| `FBINCU` | `NUMBER` | 入院次数 |  |
| `FNAME` | `VARCHAR2(200)` | 患者姓名 |  |
| `FTYPE` | `NUMBER` | 采集类型 |  |
| `FDATE` | `DATE` | 添加时间 |  |
| `FUSER` | `VARCHAR2(8)` | 添加人 |  |
| `FSOURCE` | `VARCHAR2(200)` | 队列来源 |  |
| `FST` | `NUMBER` | 状态 | 0 待采集，1正在采集， 2 采集成功，3 采集失败，4 无数据 |
| `FUPDATE` | `DATE` | 修改时间 |  |
| `FPRINTNUM` | `NUMBER` | 采集次数 |  |
| `FIHDATE` | `DATE` | 入院日期 |  |
| `FODATE` | `DATE` | 出院日期 |  |
| `PATIENTID` | `VARCHAR2(20)` | 病人唯一id |  |
| `FIOFFI` | `VARCHAR2(50)` | 入院科室 |  |
| `FOOFFI` | `VARCHAR2(50)` | 出院科室 |  |
| `OUTHOS` | `VARCHAR2(5)` | 离院方式 | 1医嘱离院2医嘱转院3医嘱转社区卫生服务机构4非医嘱转院5死亡9其他 |
| `FGUIDANGNUM` | `NUMBER` | 归档次数 |  |
| `FGUIDANGDATE` | `DATE` | 最后归档时间 |  |
| `FGUIDANGREMARK` | `VARCHAR2(300)` | 归档备注 |  |
| `FZHAOHUI` | `NUMBER` | 召回状态 | 0正常归档 1召回 |
| `FGUIDANGFST` | `NUMBER` | 归档状态 |  |
| `FMZID` | `VARCHAR2(20)` | 门诊号 |  |
| `PATIENTID2` | `VARCHAR2(40)` |  |  |
| `FJZKID` | `VARCHAR2(40)` |  |  |

## `T_MSS_PRINTQUEUEDETAIL` — 数据采集队列详细表

- **表名**：`T_MSS_PRINTQUEUEDETAIL`
- **用途/说明**：数据采集队列详细表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FQUEUEDEATILID` | `VARCHAR2(40)` | 主键 | NN |
| `FPRINTLISTQUEUEID` | `VARCHAR2(40)` | 父ID | T_MSS_PRINTLISTQUEUE表fid关联 |
| `FDATE` | `DATE` | 添加时间 |  |
| `FUSER` | `VARCHAR2(40)` | 添加人 |  |
| `FTYPE` | `NUMBER` | 模块类型 | T_MSS_ITFCONFIG表FID关联或者与T_MSS_COLLECTPC表COLLECTPCID关联 |
| `FST` | `NUMBER` | 状态 |  |
| `FCOUNT` | `NUMBER` | 应采集数量 |  |
| `FREALCOUNT` | `NUMBER` | 实际采集数量 |  |
| `FUPDATE` | `DATE` | 更新时间 |  |
| `FREMARK` | `VARCHAR2(1500)` | 备注（采集状态） |  |
| `FYXJ` | `NUMBER` | 采集优先级 |  |
| `COLLECTPCID` | `VARCHAR2(40)` | 采集服务器ID | T_MSS_ITFCONFIG表FID关联或者与T_MSS_COLLECTPC表COLLECTPCID关联 |
| `FPRINTFST` | `NUMBER` | 是否正在采集 | 0未采集 1正在采集 |
| `FPRINTNUM` | `NUMBER` | 采集次数 |  |
| `ANALYZEFST` | `NUMBER` | 解析状态 | 0未解析 1解析 |

## `T_MSS_ITFCONFIG` — 采集配置表（采集服务）

- **表名**：`T_MSS_ITFCONFIG`
- **用途/说明**：采集配置表（采集服务）

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(40)` | 主键 | NN |
| `FSORT` | `NUMBER` | 序号 |  |
| `FTYPE` | `NUMBER` | 配置类型 | 默认为1 |
| `FNAME` | `VARCHAR2(100)` | 配置名称 |  |
| `FSERVER` | `VARCHAR2(100)` | 配置IP |  |
| `FPORT` | `VARCHAR2(10)` | 端口号 |  |
| `FDBNAME` | `VARCHAR2(100)` | 数据库名称 |  |
| `FUSER` | `VARCHAR2(100)` | 数据库用户名 |  |
| `FPWD` | `VARCHAR2(100)` | 数据库密码 | 加密 |
| `FDBTYPE` | `NUMBER` | 数据库类型 | 数据库类型1SQLserver 2Oracle |
| `FSQL` | `VARCHAR2(1500)` | 查询语句 |  |
| `FCOLLECTPCID` | `VARCHAR2(40)` | 采集方法配置映射 |  |
| `HOSPITALAREACODE` | `VARCHAR2(200)` | 所属院区 | 与FID一致 |

## `T_MSS_COLLECTPC` — 采集配置表（模块化采集）

- **表名**：`T_MSS_COLLECTPC`
- **用途/说明**：采集配置表（模块化采集）

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `COLLECTPCID` | `VARCHAR2(40)` | 主键 | NN |
| `PCNAME` | `VARCHAR2(200)` | 服务名称 |  |
| `PCIP` | `VARCHAR2(20)` | 服务器IP |  |
| `MOKUAITYPE` | `NUMBER` | 模块类型 | 值为1000时表示非模块类型值，值为0时表示无纸化自己的服务，如队列服务、解析服务等等 |
| `FHLDRUG` | `NUMBER` | 方法类型 |  |
| `FST` | `NUMBER` | 是否启用 |  |
| `RUNFST` | `NUMBER` | 监控的状态 | :0，停止；2，正常；4，异常 |
| `ADDDATE` | `DATE` | 添加时间 |  |
| `FUSER` | `VARCHAR2(10)` | 添加人 |  |
| `FSTARTTIME` | `NUMBER` | 程序执行开始时间段 |  |
| `FENDTIME` | `NUMBER` | 程序执行结束时间段 |  |
| `FNUM` | `NUMBER` | 每次采集数量 |  |
| `FREMARK` | `VARCHAR2(100)` | 备注 | 一般为服务名称 |
| `FUPDATETIME` | `DATE` | 修改时间 |  |
| `FUPDATEUSER` | `VARCHAR2(20)` | 修改人 |  |
| `PROCESSNAME` | `VARCHAR2(50)` | 进程名称 |  |
| `EXEPATH` | `VARCHAR2(200)` | 启动程序路径 |  |
| `FPRINTPATH` | `VARCHAR2(100)` | 采集保存路径 |  |
| `FUPLOADPATH` | `VARCHAR2(100)` | 采集完成改名后的路径 |  |
| `FLOGINUSER` | `VARCHAR2(20)` | 第三方程序登录用户 |  |
| `FLOGINPWD` | `VARCHAR2(100)` | 第三方登录密码 | 加密 |
| `EXECUTEPROCESSNAME` | `VARCHAR2(50)` |  |  |
| `EXECUTEPATH` | `VARCHAR2(100)` |  |  |
| `SYSTEMTYPEID` | `VARCHAR2(40)` |  |  |
| `PROTECTINTERVAL` | `INTEGER` | 守护服务异常判断时间间隔 单位:小时 |  |
| `FPCINFO` | `VARCHAR2(500)` | 主机硬件信息 |  |
| `FDOWNLOADTYPE` | `NUMBER` | 下载文件类型 | 1：文件共享 2：ftp 3:http 4:文件流 5 webservice |
| `FDOWNLOADLOGINNAME` | `VARCHAR2(50)` | 下载文件登录名称如果是webservice则为请求地址 |  |
| `FDOWNLOADPWD` | `VARCHAR2(50)` | 下载文件登录密码如果是webservice则为请求请求方法 |  |
| `RUNTIME` | `DATE` | 服务最后一次运行时间 |  |
| `FTHIRDPARTRUNFST` | `NUMBER` | 第三方状态 | 0，停止；1，正常 |
| `HOSPITALAREACODE` | `VARCHAR2(200)` | 所属院区 |  |

## `T_MSS_COLLECTLIST` — 采集方式配置表（模块化）

- **表名**：`T_MSS_COLLECTLIST`
- **用途/说明**：采集方式配置表（模块化）

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `CID` | `VARCHAR2(40)` | 主键 | NN |
| `MID` | `VARCHAR2(40)` | 外键对应T_MSS_CollectMethod |  |
| `CNAME` | `VARCHAR2(40)` | 采集系统名 |  |
| `RUNFST` | `NUMBER` | 监控的状态 | 0，停止；2，正常；4，异常 |
| `ADDDATE` | `DATE` | 添加时间 |  |
| `FSTARTTIME` | `NUMBER` | 程序执行开始时间 |  |
| `FENDTIME` | `NUMBER` | 程序执行结束时间 |  |
| `FNUM` | `NUMBER` | 每次采集数量 |  |
| `FPRINTPATH` | `VARCHAR2(100)` | 保存路径 |  |
| `FUPLOADPATH` | `VARCHAR2(100)` | 完成改名后的路径 |  |
| `FCOLOR` | `NUMBER` | 报告颜色 | 0彩色，1黑白 |
| `FCONFIG` | `VARCHAR2(4000)` | 对应采集队列详细中的FTYPE |  |
| `FISUPLOADPDF` | `NUMBER` | 是否上传PDF |  |
| `FRCZDZ` | `NUMBER` | 上传方式 |  |
| `FPDFUPLOADPATH` | `VARCHAR2(100)` | PDF上传到服务器路径 |  |
| `FISCOLLECTSAMESYSTEM` | `NUMBER` | 是否开启多个采集服务采集同一个系统 | 0不启用1启用,默认值为0 |
| `COLLECTPCID` | `VARCHAR2(40)` | 采集服务器ID |  |
| `FSERVERIP` | `VARCHAR2(20)` | 服务器IP |  |
| `FROTATIONANGLE` | `VARCHAR2(5)` | 图片旋转角度 |  |
| `FDOWNLOADTYPE` | `NUMBER` | 下载文件类型 | 1：文件共享 2：ftp 3:http 4:文件流 5 webservice |
| `FDOWNLOADLOGINNAME` | `VARCHAR2(50)` | 下载文件登录名称如果是webservice则为请求地址 |  |
| `FDOWNLOADPWD` | `VARCHAR2(50)` | 下载文件登录名称如果是webservice则为请求请求方法 |  |
| `ISUPLOADTOMRD` | `NUMBER` | 是否直接上传至MRD文件夹 |  |
| `RUNTIME` | `DATE` | 服务最后一次运行时间 |  |
| `FMATCHCATEGORYNAME` | `NUMBER` | 分类映射时只匹配第三方分类编码中的汉字 默认值为 | 0 不启用 1启用 |
| `PROTECTINTERVAL` | `VARCHAR2(100)` | 守护服务异常判断时间间隔 单位:小时 |  |
| `FPCINFO` | `VARCHAR2(500)` | 主机硬件信息 |  |
| `FYZCONFIG` | `VARCHAR2(4000)` | 验证采集数量的采集方法配置 |  |
| `FPARAMCONFIG` | `VARCHAR2(4000)` | 参数配置 |  |
| `FTHIRDPARTRUNFST` | `NUMBER` | 第三方状态 | 0，停止；1，正常 |
| `HOSPITALAREACODE` | `VARCHAR2(200)` | 所属院区 |  |
| `FOPENINCREMENTCONFIG` | `VARCHAR2(4000)` |  |  |

## `T_MSS_COLLECTMETHOD` — 模块化采集方法配置表

- **表名**：`T_MSS_COLLECTMETHOD`
- **用途/说明**：模块化采集方法配置表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `MID` | `VARCHAR2(40)` | 主键 | NN |
| `MNAME` | `VARCHAR2(40)` | 方法名称 |  |
| `MDLLNAME` | `VARCHAR2(100)` | 采集方法dll选择 |  |
| `MCLASSNAME` | `VARCHAR2(100)` | 类别代码 |  |
| `MCLASSNAME` | `VARCHAR2(400)` | 类别名称 |  |

## `T_MSS_MAINHISTORY` — 修改病案历史信息

- **表名**：`T_MSS_MAINHISTORY`
- **用途/说明**：修改病案历史信息

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FMAINID` | `FMAINID` | 唯一编号 | NN |
| `FMRDID` | `VARCHAR2(20)` | 病案号 | NN |
| `FBIHID` | `VARCHAR2(20)` | 住院号 |  |
| `FBINCU` | `NUMBER` | 住院次数 |  |
| `FUSER` | `VARCHAR2(50)` | 扫描人 |  |
| `FDATE` | `DATE` | 保存日期 |  |
| `FISAUDIT` | `VARCHAR2(2)` | 病历状态 | 0 待归档 1已归档 2归档未通过 3召回 4质控未通过 5封存 6医疗质控通过 7医疗质控不通过 8护理质控通过 9护理质控不通过 10质控通过 11点击完整病案 12科室已评分 13终末已评分 14医护质控通过 15系统采集不全 16系统验证不通过 |
| `FNUM` | `NUMBER` | 页数 |  |
| `FPATH` | `VARCHAR2(500)` | 保存路径 |  |
| `FAUDITOR` | `VARCHAR2(50)` | 审核人 |  |
| `FAUDITDATE` | `DATE` | 审核日期 |  |
| `FISUPLOAD` | `VARCHAR2(1)` | 是否上传 |  |
| `FSHAREPATHID` | `VARCHAR2(40)` | 服务器配置路径 |  |
| `FSECRECYTYPE` | `NUMBER` | 安全类别 |  |
| `FSECRECYGRADE` | `NUMBER` | 安全级别 |  |
| `FREE1` | `VARCHAR2(100)` | 扩展字段1 |  |
| `FFILEID` | `VARCHAR2(50)` | 自动解析文件唯一标识号 住院号和 住院次数 |  |
| `FSOURCE` | `VARCHAR2(2)` | 图片来源类型 |  |
| `FNAME` | `VARCHAR2(200)` | 姓名 |  |
| `FILEDIRNAME` | `VARCHAR2(50)` | 保存时使用的文件夹和文件名称 |  |
| `FODATE` | `DATE` | 出院日期 |  |
| `FREE3` | `VARCHAR2(50)` | 病案号 |  |
| `FOOFFI` | `VARCHAR2(50)` | 出院科室 |  |
| `FADDDATE` | `DATE` | 修改日期 召回日期 |  |
| `FREE2` | `VARCHAR2(50)` | 扩展字段2 |  |
| `FTYPE` | `NUMBER` | 类型 | 1：召回备份 2:封存备份 |
| `HISTORYID` | `VARCHAR2(40)` | 备份或者召回的Id |  |

## `T_MSS_MRCONTROL` — 采集质控记录表

- **表名**：`T_MSS_MRCONTROL`
- **用途/说明**：采集质控记录表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(40)` | 主键 |  |
| `FMRDID` | `VARCHAR2(40)` | 病案号 |  |
| `FBIHID` | `VARCHAR2(20)` | 住院号 |  |
| `FNAME` | `VARCHAR2(200)` | 姓名 |  |
| `FTYPE` | `VARCHAR2(10)` | 质控类型 |  |
| `FST` | `VARCHAR2(2)` | 病历状态 |  |
| `FDATE` | `DATE` | 提交时间 |  |
| `FUPDATE` | `DATE` | 修改时间 |  |
| `FREMARK` | `VARCHAR2(500)` | 备注（质控出来的问题） |  |
| `FUSER` | `VARCHAR2(10)` | 提交扫描人员 |  |
| `FDOUSER` | `VARCHAR2(10)` | 处理人员 |  |
| `FDOREMARK` | `VARCHAR2(100)` | 处理备注 |  |
| `FVALUE` | `VARCHAR2(500)` |  |  |
| `FBINCU` | `VARCHAR2(10)` | 住院次数 |  |
| `FCATEGORYID` | `VARCHAR2(40)` | 分类id |  |
| `FDOCNAME` | `VARCHAR2(128)` | 文档名称 |  |

## `T_MSS_REQUESTMRD` — 病历借阅申请表

- **表名**：`T_MSS_REQUESTMRD`
- **用途/说明**：病历借阅申请表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FREQUESTMRDID` | `VARCHAR2(40)` | 唯一值 | NN |
| `FMRDID` | `VARCHAR2(20)` | 病案号 | NN |
| `FREQUESTOR` | `VARCHAR2(20)` | 申请人 |  |
| `FREQUESTDATE` | `DATE` | 申请时间 |  |
| `FAUDITOR` | `VARCHAR2(20)` | 审核人 |  |
| `FAUDITDATE` | `DATE` | 审核时间 |  |
| `FISAUDIT` | `VARCHAR2(2)` | 审核状态 | 0 待审核，1 审批完成，5 病历科主任驳回，8 病历科主任通过， 9 病案室驳回，10 借阅撤回 |
| `FMRDCLASS` | `VARCHAR2(20)` | 病人出院科室 |  |
| `FCATEGORY` | `VARCHAR2(1000)` | 申请查阅病案类别 |  |
| `FTIMENUM` | `NUMBER` | 申请查看天数 |  |
| `FST` | `VARCHAR2(2)` | 是否过期 | 0正常 1过期 2用不过期 |
| `FTIMETYPE` | `VARCHAR2(1)` | 类别 |  |
| `FREMARK` | `VARCHAR2(255)` | 拒绝 或者同意理由 |  |
| `FAPPLYREMARK` | `VARCHAR2(255)` | 申请理由 |  |
| `FTODO` | `VARCHAR2(50)` | 催办 |  |
| `FREE1` | `VARCHAR2(50)` | 归还人 |  |
| `FREE2` | `VARCHAR2(50)` | 归还时间 |  |
| `FREE3` | `VARCHAR2(50)` | 签收人 |  |
| `FBRROWCASETYPE` | `VARCHAR2(100)` | 借阅类型 |  |
| `FTIMEAUDITNUM` | `VARCHAR2(50)` | 审核申请查看天数 |  |
| `FISPAPERBORROWS` | `VARCHAR2(2)` | 是否为纸质借阅 |  |
| `FRETURNPERSON` | `VARCHAR2(20)` |  |  |
| `FRETURNDATE` | `DATE` | 归还时间 |  |
| `FTYPE` | `NUMBER` | 借阅类型 | 0：自己借阅 1：授权借阅的 |
| `FPHONE` | `VARCHAR2(20)` | 电话 |  |
| `FRENEWSTATUS` | `NUMBER` | 续借状态 | 0：没有续借 1：已经续借 |
| `FBORROWCATEGORY` | `VARCHAR2(500)` | 借阅的分类 |  |

## `T_MSS_APPRECALL` — 病历召回申请表

- **表名**：`T_MSS_APPRECALL`
- **用途/说明**：病历召回申请表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(40)` | 主键 | NN |
| `FMAINID` | `VARCHAR2(40)` | 病历唯一号 | 与main表FMAINID一致 |
| `FBIHID` | `VARCHAR2(20)` | 住院号 |  |
| `FBINCU` | `NUMBER` | 住院次数 |  |
| `PATIENTID` | `VARCHAR2(20)` | 病人ID |  |
| `FMRDID` | `VARCHAR2(20)` | 病案号 |  |
| `FREQUESTOR` | `VARCHAR2(20)` | 申请人 |  |
| `FREQUESTDATE` | `DATE` | 申请时间 |  |
| `FAUDITOR` | `VARCHAR2(20)` | 审核人 |  |
| `FAUDITDATE` | `DATE` | 审核时间 |  |
| `FST` | `VARCHAR2(1)` | 申请状态 | 0：已申请；1：已同意；2：不同意 |
| `FSTATUS` | `VARCHAR2(1)` | 执行状态 | 0：未执行；1：已执行； |
| `FUPDATE` | `DATE` | 执行时间 |  |
| `FAPPLYREMARK` | `VARCHAR2(255)` | 申请理由 |  |
| `FREMARK` | `VARCHAR2(255)` | 拒绝 或者同意理由 |  |

## `TMRDOP` — 手术信息表

- **表名**：`TMRDOP`
- **用途/说明**：手术信息表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FMRDID` | `VARCHAR2(15)` | 病案号 |  |
| `FSEQ` | `NUMBER` | 序号 |  |
| `FOPID` | `VARCHAR2(15)` | 手术编码 |  |
| `FOPDAT` | `DATE` | 手术日期 |  |
| `FOPDOC` | `VARCHAR2(20)` | 手术医师 |  |
| `FOPFZ1` | `VARCHAR2(20)` | 辅助医生1 |  |
| `FOPFZ2` | `VARCHAR2(20)` | 辅助医师2 |  |
| `FMZTH` | `VARCHAR2(6)` | 麻醉方式 |  |
| `FYHTYP` | `VARCHAR2(6)` | 愈合等级 | 0 其他 1 甲 2 乙 3 丙 4 无 |
| `FMZYS` | `VARCHAR2(20)` | 麻醉医师 |  |
| `FQUCD1` | `VARCHAR2(10)` | 查询1 |  |
| `FQUCD2` | `VARCHAR2(10)` | 查询2 |  |
| `FCUT` | `VARCHAR2(2)` | 切口 | Ⅰ类(无菌) 2Ⅱ类(沾染) 3 Ⅲ类(感染) 4 无切口 |
| `FOPLEV` | `VARCHAR2(1)` | 手术级别 |  |
| `FDESC_DOC` | `VARCHAR2(200)` | 医生手术描述 |  |
| `FOP_BFZ` | `VARCHAR2(50)` | 手术并发症 |  |
| `FASA` | `VARCHAR2(50)` | 手术ASA |  |
| `FIS_PLAN` | `NUMBER` | 是否重返手术室 |  |
| `FZYSS` | `VARCHAR2(1)` | 是否主要手术 |  |
| `FZYCZ` | `VARCHAR2(1)` | 是否主要操作 |  |
| `FZQSS` | `VARCHAR2(1)` | 择期手术 |  |
| `FOPDAT_S` | `DATE` | 手术开始时间 |  |
| `FOPDAT_E` | `DATE` | 手术结束时间 |  |
| `FGYDAT` | `DATE` | 术前预防性抗菌药物给药时间 |  |
| `FMZDAT_S` | `DATE` | 麻醉开始时间 |  |
| `FMZDAT_E` | `DATE` | 麻醉结束时间 |  |
| `FMZASA` | `VARCHAR2(1)` | 麻醉asa |  |
| `FCUT_PLACE` | `VARCHAR2(50)` | 切口部位 |  |
| `FCUT_QJ` | `VARCHAR2(10)` | 切口情节程度 |  |
| `FNNIS` | `VARCHAR2(1)` | NNIS分级 |  |
| `FIS_PLAN_T` | `VARCHAR2(50)` | 重返手术室目的 |  |
| `FSSBWGR` | `VARCHAR2(1)` | 手术部位感染 | 1：是 2否 |
| `FSSBFZ` | `VARCHAR2(1)` | 手术并发症 |  |
| `FIS_PLAN_MD` | `VARCHAR2(100)` | 重返手术室目的 |  |
| `FOPOFFI` | `VARCHAR2(20)` | 手术所属科室 |  |
| `FS01` | `VARCHAR2(20)` | 是否术前0.5-2小时内预防用抗菌药 |  |
| `FS02` | `VARCHAR2(20)` | 清洁手术围术期预防用抗菌药天数 |  |
| `FS03` | `VARCHAR2(20)` | 非预期的二次手术 |  |
| `FS04` | `VARCHAR2(20)` | 麻醉并发症 |  |
| `FS05` | `VARCHAR2(20)` | 术中异物遗留 |  |
| `FS06` | `VARCHAR2(20)` | 手术并发症名称 |  |
| `FS07` | `VARCHAR2(20)` | 手术部位 |  |
| `FS08` | `VARCHAR2(20)` | 备用 |  |
| `FS09` | `VARCHAR2(20)` | 备用 |  |

## `T_MSS_BBS` — 病历讨论记录表

- **表名**：`T_MSS_BBS`
- **用途/说明**：病历讨论记录表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FBBSID` | `VARCHAR2(40)` | 评论ID |  |
| `FTITLE` | `VARCHAR2(50)` | 标题 |  |
| `FRECORDID` | `VARCHAR2(40)` | 对应图片ID |  |
| `FUSERID` | `VARCHAR2(50)` | 评论人ID |  |
| `FUSER` | `VARCHAR2(50)` | 评论人 |  |
| `FDATE` | `DATE` | 添加日期 |  |
| `FUDATE` | `DATE` | 修改日期 |  |
| `FTYPE` | `VARCHAR2(50)` | 类型 |  |
| `FST` | `VARCHAR2(10)` | 状态 | 显示不显示 删除等 |
| `FREPLYCOUNT` | `NUMBER` | 回复数量 |  |
| `FCONTENT` | `VARCHAR2(225)` | 内容 |  |
| `FMAINID` | `VARCHAR2(40)` | 主表ID |  |
| `FTYPENAME` | `VARCHAR2(100)` | 类型名 |  |
| `FDISCUSSTYPE` | `NUMBER` | 问题类型 | 1：医生 2：护士 |
| `FBBSTYPE` | `NUMBER` | 讨论类型 | 1：报告内容问题 2：病案完整性问题 |

## `T_MSS_BBSTYPEDICT` — 讨论分类维护表

- **表名**：`T_MSS_BBSTYPEDICT`
- **用途/说明**：讨论分类维护表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(40)` | 唯一号 | NN |
| `FTYPENAME` | `VARCHAR2(50)` | 分类描述 |  |
| `FTYPECODE` | `VARCHAR2(50)` | 分类查询码 | 一般是拼音码 |
| `FTYPE` | `VARCHAR2(50)` | 讨论错误分类 | 1、报告内容问题2、病历完整性问题 |
| `FST` | `NUMBER` |  |  |
| `FPINYIN` | `VARCHAR2(50)` |  |  |
| `FPARENTID` | `VARCHAR2(40)` | 上级标题ID |  |

## `T_MSS_BBSREPLY` — 图片讨论回复表

- **表名**：`T_MSS_BBSREPLY`
- **用途/说明**：图片讨论回复表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FREPLYID` | `VARCHAR2(40)` | 回复ID | NN |
| `FBBSID` | `VARCHAR2(40)` | 主题ID |  |
| `FUSERID` | `VARCHAR2(50)` | 用户ID |  |
| `FUSER` | `VARCHAR2(50)` | 用户名称 |  |
| `FCONTENT` | `VARCHAR2(1000)` | 回复内容 |  |
| `FREPLYDATE` | `DATE` | 回复时间 |  |
| `FUDATE` | `DATE` | 修改时间 |  |
| `TYPE` | `VARCHAR2(10)` | 类型 |  |
| `FST` | `VARCHAR2(10)` | 状态 |  |

## `T_MSS_CATEGORY` — 病案分类表

- **表名**：`T_MSS_CATEGORY`
- **用途/说明**：病案分类表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(6)` | 编码 | NN |
| `FDESC` | `VARCHAR2(30)` | 描述 |  |
| `FQUN` | `VARCHAR2(8)` | 查询编码 | 一般是拼音码 |
| `FST` | `VARCHAR2(1)` | 状态 |  |
| `FQUN2` | `VARCHAR2(8)` | 查询编码2 |  |

备注：系统定义。预定义56种民族。

## `TCTRYM` — 国家代码维护

- **表名**：`TCTRYM`
- **用途/说明**：国家代码维护

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FSERIALNUM` | `VARCHAR2(20)` | 编码 | NN |
| `FDESC` | `VARCHAR2(200)` | 描述 |  |
| `FSTATUS` | `VARCHAR2(10)` | 状态: | 0：显示，1：不显示 |
| `FSHORTCUTKEY` | `VARCHAR2(100)` | 快捷键 |  |
| `FSLDESC` | `VARCHAR2(200)` | 描述简写 |  |
| `FPSERIALNUM` | `VARCHAR2(30)` | 父节点编码 |  |
| `KEYWORD` | `VARCHAR2(1000)` | 关键词 |  |
| `FPRINTST` | `VARCHAR2(10)` |  |  |
| `LIMIT` | `NUMBER` | 限制 |  |
| `REQUIRED` | `NUMBER` |  |  |
| `ROATE` | `VARCHAR2(2)` |  |  |
| `PRINTKEY` | `NUMBER` |  |  |
| `PRINTCOLOR` | `NUMBER` |  |  |
| `OCRKEY` | `VARCHAR2(500)` |  |  |
| `OCRZZ` | `VARCHAR2(200)` |  |  |
| `OCRTYPE` | `VARCHAR2(200)` |  |  |
| `LOWLIMIT` | `NUMBER` | 分类下限值设定 |  |
| `FCHECK` | `VARCHAR2(1)` |  |  |
| `FSHOOTBUTTONSERT` | `INTEGER` | 拍摄按钮排序 |  |
| `HOSPITALAREACODE` | `VARCHAR2(200)` | 所属院区 |  |
| `FCATEGORY` | `VARCHAR2(200)` | 分类类别 | 1 采集, 2拍摄 ,3 共有 |

## `T_MSS_CATEGORYMAPPING` — 病案分类详细表

- **表名**：`T_MSS_CATEGORYMAPPING`
- **用途/说明**：病案分类详细表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(40)` | 唯一号 | NN |
| `FSERIALNUM` | `VARCHAR2(100)` | 序列号 |  |
| `FDESC` | `VARCHAR2(200)` | 描述 |  |
| `FOUTSERIALNUM` | `VARCHAR2(100)` | 映射序列号 |  |
| `FOUTDESC` | `VARCHAR2(200)` | 描述 |  |
| `FST` | `CHAR(1)` | 分类是否启用 | :值为0是禁用，其他值皆是启用，且值为4时表示此分类为其他分类 |
| `FISLIKEMATCH` | `NUMBER` | 是否启用模糊匹配 | 0不启用1启用 默认值为0 |
| `FLIKEMATCHORDERNUM` | `NUMBER` | 模糊匹配排序值 |  |
| `FISUSEDMAPPINGNAME` | `NUMBER` | 是否使用映射表中FOUTDESC字段值命名文件 1启用 0不启用(即使用第三方视图中分类名称命名) 默认值为0 | 1启用 0不启用(即使用第三方视图） |
| `FTYPE` | `VARCHAR2(10)` | 类型 |  |
| `HOSPITALAREACODE` | `VARCHAR2(200)` | 所属院区 |  |

## `T_MSS_CATGROUP` — 打印套餐维护表

- **表名**：`T_MSS_CATGROUP`
- **用途/说明**：打印套餐维护表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FCATGROUPID` | `VARCHAR2(40)` | 主键 | NN |
| `FDESC` | `VARCHAR2(100)` | 分类名称 |  |
| `FNUM` | `NUMBER` |  |  |
| `FCOMMENTS` | `VARCHAR2(200)` | 备注 |  |
| `FUSER` | `VARCHAR2(20)` | 添加人 |  |
| `FLIMIT` | `NUMBER(1)` |  |  |
| `FTYPE` | `INTEGER` |  | 0打印事由1套餐2两者共用不区分 |
| `ISHOSPITALAREAID` | `VARCHAR2(200)` | 所属院区 |  |

## `T_MSS_GROUPLIST` — 打印套餐详细表

- **表名**：`T_MSS_GROUPLIST`
- **用途/说明**：打印套餐详细表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FGROUPLISTID` | `VARCHAR2(40)` | 唯一号 | NN |
| `FCATGROUPID` | `VARCHAR2(40)` | 子键 | 与T_MSS_CATGROUP表FCATGROUPID关联 |
| `FSERIALNUM` | `VARCHAR2(10)` | 编码 |  |
| `FDESC` | `VARCHAR2(200)` | 描述 | NN |
| `FPAGE` | `VARCHAR2(200)` |  |  |

## `T_MCP_EAA_DETAIL` — 病历打印申请表

- **表名**：`T_MCP_EAA_DETAIL`
- **用途/说明**：病历打印申请表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FMCP_EAA_ID` | `VARCHAR2(20)` | 复印审批流水号 | NN |
| `FM_TYPE` | `VARCHAR2(4)` | 病案类型案 | (0、历史病1出院病人2在院病人) |
| `FPID` | `VARCHAR2(20)` | 病案ID与病案主索引的FPID一致 |  |
| `FMRDID` | `VARCHAR2(20)` | 病案号 |  |
| `FBIHID` | `VARCHAR2(20)` | 住院号 |  |
| `FBINCU` | `NUMBER` | 住院次数 |  |
| `FNAME` | `VARCHAR2(200)` | 病人姓名 |  |
| `FSEX` | `VARCHAR2(4)` | 性别 |  |
| `FAGE` | `NUMBER` | 年龄 |  |
| `FCERT_TYPE` | `VARCHAR2(4)` | 患者证件类型 |  |
| `FCERT_CODE` | `VARCHAR2(30)` | 患者证件号码 |  |
| `FCERT_ID` | `VARCHAR2(20)` | 患者证件编号 来自证件表 |  |
| `FODATE` | `DATE` | 出院日期 |  |
| `FODEPT` | `VARCHAR2(50)` | 出院科室 |  |
| `FODIAG_ICD` | `VARCHAR2(20)` | 出院诊断名称(ICD) |  |
| `FODIAG` | `VARCHAR2(200)` | 出院诊断名称(汉字) |  |
| `FMCP_USER` | `VARCHAR2(50)` | 复印者 |  |
| `FMCP_DEPT` | `VARCHAR2(30)` | 复印者部门 |  |
| `FMCP_RES` | `VARCHAR2(400)` | 复印事由 来自用途 |  |
| `FMCERT_TYPE` | `VARCHAR2(4)` | 复印者证件类型 |  |
| `FMCERT_CODE` | `VARCHAR2(30)` | 复印者证件号码 |  |
| `FMCERT_ID` | `VARCHAR2(20)` | 复印者证件编号 |  |
| `FMCP_RELA` | `VARCHAR2(50)` | 与患者关系 |  |
| `FMCP_DATE` | `DATE` | 申请日期 |  |
| `FMCP_TEL` | `VARCHAR2(30)` | 复印人联系电话 |  |
| `FEAA_USER_ID` | `VARCHAR2(20)` | 审批人ID |  |
| `FEAA_USER_NAME` | `VARCHAR2(50)` | 审批人姓名 |  |
| `FEAA_USER_DATE` | `DATE` | 审批日期 |  |
| `FIUSER_ID` | `VARCHAR2(20)` | 操作人 |  |
| `FMEMO` | `VARCHAR2(50)` | 备注 |  |
| `FMCP_LIST` | `VARCHAR2(500)` | 复印内容列表 |  |
| `FMCP_PROC` | `VARCHAR2(10)` | 当前流程 | (1、申请2、已复印，3、申请驳回,4、审核通过) |
| `FST` | `VARCHAR2(1)` | 伪删除 |  |
| `FCN_PORT` | `NUMBER` | 复印份数 |  |
| `FCN_PIE` | `NUMBER` | 复印张数 |  |
| `FPRICE` | `NUMBER` | 单价 |  |
| `FAMT` | `NUMBER` | 金额 |  |
| `FPCLASSID` | `VARCHAR2(10)` | 收费类型 |  |
| `FOP_USER_ID` | `VARCHAR2(20)` | 复印操作人 |  |
| `FEMS` | `VARCHAR2(1)` | 是否ems寄送 |  |
| `FMCP_NODE` | `VARCHAR2(20)` | 复印机器 |  |
| `FPAID` | `NUMBER` | 实收 |  |
| `FCHANGE` | `NUMBER` | 找零 |  |
| `FREJECT_RES` | `VARCHAR2(1000)` | 驳回理由 |  |
| `FDEPOSIT` | `NUMBER` | 押金 |  |
| `FORDER` | `NUMBER` | 预约天数 |  |
| `FREC_DATE` | `DATE` | 领取日期 |  |
| `FPIDLIST` | `VARCHAR2(200)` | 多住院号复印 |  |
| `FMCP_CONTENT` | `VARCHAR2(4000)` | 数字化病案打印内容 |  |
| `FMCP_FP0` | `VARCHAR2(200)` | 备用字段 | 0 证件扫描费用 |
| `FMCP_FP1` | `VARCHAR2(200)` | 备用字段 | 1 退费标识 |
| `FMCP_FP2` | `VARCHAR2(500)` | 备用字段2 |  |
| `FMCP_FP3` | `VARCHAR2(1000)` | 备用字段3 |  |
| `FMCP_FP4` | `VARCHAR2(1000)` | 备用字段4 |  |
| `FMCP_RESNUM` | `NUMBER` |  |  |

## `T_MCP_CER_LIST` — 病历打印人信息登记表

- **表名**：`T_MCP_CER_LIST`
- **用途/说明**：病历打印人信息登记表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FCER_ID` | `VARCHAR2(20)` | 证件流水编号 |  |
| `FC_TYPE` | `VARCHAR2(6)` | 证件类型 |  |
| `FC_CODE` | `VARCHAR2(30)` | 证件号码 |  |
| `FNAME` | `VARCHAR2(200)` | 姓名 |  |
| `FSEX` | `VARCHAR2(10)` | 性别 |  |
| `FNATION` | `VARCHAR2(20)` | 民族 |  |
| `FBDATE` | `VARCHAR2(20)` | 生日 |  |
| `FADD` | `VARCHAR2(200)` | 地址 |  |
| `FGRANT_DEPT` | `VARCHAR2(50)` | 签发机关 |  |
| `FB_UL` | `VARCHAR2(20)` | 身份证有效期从 |  |
| `FE_UL` | `VARCHAR2(20)` | 身份证有效期至 |  |
| `FPHOTO` | `BLOB` | 照片 |  |
| `FTYPE` | `VARCHAR2(20)` | 类型 |  |
| `FST` | `VARCHAR2(1)` |  |  |
| `FPATH` | `VARCHAR2(4000)` | 扫描件存储路径 |  |

## `T_MSS_PRINTLOG` — 病历打印记录主表

- **表名**：`T_MSS_PRINTLOG`
- **用途/说明**：病历打印记录主表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `CHAR(32)` | 唯一编号 | NN |
| `FMRDID` | `VARCHAR2(20)` | 病案号 |  |
| `FPRINTPAGEINDEX` | `VARCHAR2(4000)` | 打印页码 |  |
| `FPRINTCOUNT` | `NUMBER` | 打印页数 |  |
| `FPRINTER` | `VARCHAR2(50)` | 打印人 操作者 |  |
| `FPRINTDATE` | `DATE` | 打印时间 |  |
| `FBIHID` | `VARCHAR2(20)` | 住院号 |  |
| `FBINCU` | `NUMBER` | 住院次数 |  |
| `FSERIALNUM` | `VARCHAR2(20)` | 打印流水号 |  |
| `FUNIT` | `VARCHAR2(50)` | 打印者单位 |  |
| `FREASON` | `VARCHAR2(100)` | 打印事由 |  |
| `FAUDITOR` | `VARCHAR2(40)` | 审核人 |  |
| `FCOPIES` | `NUMBER` | 份数 |  |
| `FCOST` | `NUMBER` | 金额 |  |
| `FPRICE` | `NUMBER` | 单价 |  |
| `FPRICEMODE` | `VARCHAR2(1)` | 费用收取方式 0 表示按页 1表示按份 |  |
| `FNAME` | `VARCHAR2(200)` | 病人姓名 |  |
| `FIDCARD` | `VARCHAR2(20)` | 身份证号 |  |
| `FODATE` | `DATE` | 出院时间 |  |
| `FREMARK` | `VARCHAR2(200)` | 备注 |  |
| `FDYR` | `VARCHAR2(50)` | 打印人 谁来打印的 |  |
| `FCATGROUPID` | `VARCHAR2(32)` | 套餐ID |  |
| `FDESC` | `VARCHAR2(100)` | 套餐描述 |  |
| `FRELATIONSHIP` | `VARCHAR2(100)` | 打印人和患者的关系 |  |
| `FHZIDCARD` | `VARCHAR2(20)` | 患者身份证号码 |  |
| `FSEX` | `VARCHAR2(20)` | 患者性别 |  |
| `FIP` | `VARCHAR2(50)` | ip地址 |  |
| `FMAC` | `VARCHAR2(50)` | mac地址 |  |
| `FPRINTTYPE` | `NUMBER` | 打印类型 | 0：窗口打印 1：自助机打印 |
| `PRINTTYPE` | `NUMBER` | 打印类型印 | 0：导出 1：无纸化客户端打印:2：自助机打印:3：微病案打 |

## `T_MSS_PRINTDETAIL` — 病历打印详细记录表

- **表名**：`T_MSS_PRINTDETAIL`
- **用途/说明**：病历打印详细记录表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FPRINTDETAILID` | `VARCHAR2(40)` | 打印明细 | NN |
| `FPRINTLOGID` | `VARCHAR2(40)` |  |  |
| `FFILENAME` | `VARCHAR2(500)` | 图片名称 |  |

## `T_MSS_CONFIG` — 总参数配置表

- **表名**：`T_MSS_CONFIG`
- **用途/说明**：总参数配置表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FCONFIGID` | `VARCHAR2(50)` | 唯一编号 |  |
| `FTYPE` | `VARCHAR2(200)` | 类型 | NN |
| `FVALUE` | `VARCHAR2(4000)` | 值 |  |
| `FCONTENT` | `VARCHAR2(400)` | 备注 |  |
| `DATATYPE` | `INTEGER` | 参数类型1 文本 2 开关 |  |
| `HOSPITALAREACODE` | `VARCHAR2(200)` | 所属院区 |  |

## `T_MSS_COLLECTLOG` — 模块化采集日志表

- **表名**：`T_MSS_COLLECTLOG`
- **用途/说明**：模块化采集日志表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `LID` | `VARCHAR2(40)` | 主键 | NN |
| `CID` | `VARCHAR2(40)` | 外键对应T_MSS_CollectList |  |
| `FCONTENT` | `VARCHAR2(2000)` | 日志内容 |  |
| `FDATE` | `VARCHAR2(100)` | 记录时间 |  |
| `FOPERATION` | `VARCHAR2(100)` | 记录类型 |  |
| `FSYS` | `NUMBER` | 枚举编号 |  |
| `FCOMPUTERNAME` | `VARCHAR2(50)` | 服务计算机名 |  |
| `FCOMPUTERIP` | `VARCHAR2(100)` | 服务计算机IP |  |
| `FBIHID` | `VARCHAR2(20)` | 住院号 |  |
| `FBINCU` | `NUMBER` | 住院次数 |  |
| `PATIENTID` | `VARCHAR2(20)` | 唯一号 |  |

## `T_MSS_DJFL` — 单机分类配置表

- **表名**：`T_MSS_DJFL`
- **用途/说明**：单机分类配置表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FFLID` | `VARCHAR2(50)` | 分类ID | NN |
| `FFLDESC` | `VARCHAR2(100)` | 分类描述 |  |
| `FGLID` | `VARCHAR2(50)` | 关联机器ID |  |
| `FFLQC` | `VARCHAR2(100)` |  |  |
| `FCATEGORYID` | `VARCHAR2(50)` | T_MSS_Category表中的分类ID | NN |
| `FIMAGETYPE` | `NUMBER` | 0黑白,1彩色 |  |

## `T_MSS_DJJQ` — 单机分类配置表

- **表名**：`T_MSS_DJJQ`
- **用途/说明**：单机分类配置表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FJQID` | `VARCHAR2(50)` | 机器ID | NN |
| `FJQDESC` | `VARCHAR2(100)` | 机器描述 |  |
| `FJQBZ` | `VARCHAR2(100)` | 备注 |  |
| `FJQHISCATE` | `VARCHAR2(100)` |  |  |

## `T_MSS_DJLOG` — 单机系统采集日志

- **表名**：`T_MSS_DJLOG`
- **用途/说明**：单机系统采集日志

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(40)` | 唯一号 | NN |
| `FJQID` | `VARCHAR2(40)` | 打印机器ID |  |
| `FPOSTION` | `VARCHAR2(100)` | 机器位置 |  |
| `FIP` | `VARCHAR2(20)` | 机器IP |  |
| `FADDDATE` | `DATE` | 打印上传时间 |  |
| `FREPORTCATEGORY` | `VARCHAR2(10)` | 报告分类 |  |
| `FREPORTDESC` | `VARCHAR2(50)` | 报告描述分类描述 |  |
| `FPRINTUSER` | `VARCHAR2(50)` | 打印人 |  |
| `FPATIENTID` | `VARCHAR2(20)` | 病人ID |  |
| `FNAME` | `VARCHAR2(200)` | 病人姓名 |  |
| `FTYPE` | `VARCHAR2(5)` | 操作类型 |  |
| `FILENAME` | `VARCHAR2(100)` | 文件名 |  |

## `T_MSS_SHAREPATH` — 图片保存路径详细配置表

- **表名**：`T_MSS_SHAREPATH`
- **用途/说明**：图片保存路径详细配置表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FSHAREPATHID` | `VARCHAR2(40)` | 主键 |  |
| `FPATH` | `VARCHAR2(1000)` | 共享目录 |  |
| `FUSERNAME` | `VARCHAR2(100)` | 用户名 |  |
| `FPWD` | `VARCHAR2(100)` | pwd |  |
| `FSERVERIP` | `VARCHAR2(100)` | 服务器地址 |  |
| `FSHAREFOLDER` | `VARCHAR2(100)` | 图片保存共享文件夹名称 |  |
| `FBAKPATH` | `VARCHAR2(500)` |  |  |
| `FPORT` | `NUMBER` | 端口号 |  |
| `ISUSING` | `NUMBER` | 正在使用标志 | ,1：正在使用;0及其他 暂未使用 |
| `HOSPITALAREACODE` | `VARCHAR2(200)` | 所属院区 |  |
| `FWEBNAME` | `VARCHAR2(100)` | 网站名称 |  |

## `TOFFIM` — 科室维护表

- **表名**：`TOFFIM`
- **用途/说明**：科室维护表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FOFFN` | `VARCHAR2(40)` | 编码 | 中医ICD编码NN |
| `FDESC` | `VARCHAR2(100)` | 描述 |  |
| `FQUN` | `VARCHAR2(20)` | 查询编码 |  |
| `FBETO` | `VARCHAR2(20)` | 所属 |  |
| `FREG` | `VARCHAR2(1)` | 是否挂号科室 |  |
| `FCHAD` | `NUMBER` | 诊疗费 |  |
| `FREF1` | `VARCHAR2(30)` | 参考1 |  |
| `FTYPE` | `VARCHAR2(4)` | 类型 | I:病区 O: 门诊T:医疗 |
| `FST` | `VARCHAR2(1)` | 状态 |  |
| `FBQNT` | `NUMBER` | 床位数 |  |
| `FQUN2` | `VARCHAR2(20)` | 查询编码2 |  |
| `FCODE` | `VARCHAR2(8)` | 对应标准代码 |  |
| `FDOC` | `NUMBER` | 医生数 |  |
| `FNUR` | `NUMBER` | 护士数量 |  |
| `FOTH` | `NUMBER` | 其他人数 |  |
| `FSOFFI` | `VARCHAR2(6)` |  |  |
| `FKZR` | `VARCHAR2(20)` | 科室主任 |  |
| `FCOCOD` | `VARCHAR2(24)` | 医院名称 |  |
| `FSORT` | `VARCHAR2(15)` | 排序号 |  |
| `HOSPITALAREACODE` | `VARCHAR2(200)` | 所属院区 |  |

## `T_MSS_LOG` — 操作记录表

- **表名**：`T_MSS_LOG`
- **用途/说明**：操作记录表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FLOGID` | `VARCHAR2(40)` | 主键 | NN |
| `FEMPID` | `VARCHAR2(100)` | 用户 |  |
| `FCONTENT` | `VARCHAR2(1000)` | 日志内容 |  |
| `FDATE` | `DATE` | 发生时间 |  |
| `FOPERATION` | `VARCHAR2(50)` | 操作 |  |
| `FSYS` | `VARCHAR2(2)` | 系统 |  |
| `HOSPITALAREACODE` | `VARCHAR2(50)` | 所属院区 |  |

> 备注：源文档此处未提供进一步说明。

## `T_MSS_CHECKCONTROL` — 自动质控数据配置表

- **表名**：`T_MSS_CHECKCONTROL`
- **用途/说明**：自动质控数据配置表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(40)` |  | NN |
| `FCHECKID` | `VARCHAR2(50)` | 检查ID 如果按科室 则是科室编码 |  |
| `FCHECKCONTENT` | `VARCHAR2(1024)` | 检查内容 如某科室必须包含 001@1 类别@页码 |  |
| `FCHECKDESC` | `VARCHAR2(50)` | 检查描述 |  |
| `FTYPE` | `NUMBER` | 检查类型 |  |
| `FST` | `NUMBER` | 该项状态 启用 停用 |  |
| `FNUM` | `NUMBER` | 序号 |  |

## `T_MSS_CONTROLLOG` — 质控记录表

- **表名**：`T_MSS_CONTROLLOG`
- **用途/说明**：质控记录表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(32)` | 唯一编号 | NN |
| `FMRDID` | `VARCHAR2(20)` | 病案号 | NN |
| `FCONTROLER` | `VARCHAR2(50)` | 质控人 |  |
| `FCONTROLDATE` | `DATE` | 质控时间 |  |
| `FBIHID` | `VARCHAR2(20)` | 住院号 |  |
| `FBINCU` | `NUMBER` | 住院次数 |  |
| `FCONTROLTYPE` | `VARCHAR2(2)` | 质控类型 | 1已归档 6医疗质控通过 7医疗质控不通过 8护理质控通过 9护理质控不通过 4 质控未通过 10 质控通过 50 召回申请 51 召回通过 52 召回驳回 60封存申请 61封存通过 62封存驳回 63 撤销 64 解封 65 文件备份成 66 解封申请通过 |
| `FODATE` | `DATE` | 出院时间 |  |
| `FNAME` | `VARCHAR2(200)` | 病人姓名 |  |

## `T_MSS_DJCASIGNLOG` — CA签名记录表

- **表名**：`T_MSS_DJCASIGNLOG`
- **用途/说明**：CA签名记录表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(40)` | 唯一号 | NN |
| `FILENAME` | `VARCHAR2(100)` | 文件名 |  |
| `FSIGNVALUE` | `VARCHAR2(4000)` | 数字签名值 |  |
| `FTIMESTAMP` | `VARCHAR2(4000)` | 时间戳 |  |
| `FPDFNAME` | `VARCHAR2(100)` | 文件所属PDF文件名称 |  |
| `FUSERNAME` | `VARCHAR2(40)` | CA用户名 |  |
| `FUSERCERT` | `VARCHAR2(4000)` | 用户证书 |  |
| `FSIGNDATE` | `DATE` | 签名时间 |  |

## `T_MSS_PARAM` — 保密等级配置表

- **表名**：`T_MSS_PARAM`
- **用途/说明**：保密等级配置表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FID` | `VARCHAR2(10)` | 参数编号 | NN |
| `FNAME` | `VARCHAR2(500)` | 参数名称 |  |
| `FPARENTID` | `VARCHAR2(10)` | 参数类型 |  |
| `FSYSID` | `VARCHAR2(2)` | 公用参数 |  |
| `FPAGEID` | `VARCHAR2(50)` | 页面编码 |  |
| `FDESC` | `VARCHAR2(1000)` | 参数描述 |  |
| `FISLAST` | `VARCHAR2(1)` | 是否最后一层 | 为1表示最后一层 |
| `FSORT` | `NUMBER` | 排序号 |  |
| `FISACTIVE` | `VARCHAR2(1)` | 是否启用 |  |
| `FISMODIFY` | `VARCHAR2(1)` | 是否可编辑 |  |
| `FISDISPLAY` | `VARCHAR2(1)` | 是否显示 |  |
| `FMODIFYID` | `VARCHAR2(50)` | 最后修改人 |  |
| `FMODIFYDATE` | `DATE` | 最后修改时间 |  |
| `FQUN` | `VARCHAR2(100)` | 拼音码 |  |

## `T_MSS_EMP_DICT` — 用户表

- **表名**：`T_MSS_EMP_DICT`
- **用途/说明**：用户表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FLOGINNAME` | `VARCHAR2(50)` | 登录名 | NN |
| `FUSERNAME` | `VARCHAR2(50)` | 用户姓名 |  |
| `FPWD` | `VARCHAR2(50)` | 密码 |  |
| `FPOSITION` | `VARCHAR2(30)` | 职位 |  |
| `FDEPT` | `VARCHAR2(30)` | 部门 |  |
| `FROLEID` | `VARCHAR2(40)` | 权限编号 |  |
| `FSYSID` | `VARCHAR2(1)` | 用户权限类型 | 0客户端权限1网页端权限2客户端和网页端权限 |
| `FROLECONTENT` | `VARCHAR2(2000)` | 权限内容 |  |
| `FISAUDIT` | `VARCHAR2(1)` | 是否有审核权限 0 无 1 有 |  |
| `FFREE1` | `VARCHAR2(100)` | 扩充字段1 |  |
| `FFREE2` | `VARCHAR2(100)` | 扩充字段2 |  |
| `FFREE3` | `VARCHAR2(100)` | 扩充字段3 |  |
| `FFREE4` | `VARCHAR2(100)` | 扩充字段4 |  |
| `FPAGEROLE` | `VARCHAR2(40)` | 页面权限编号 |  |
| `FISSEARCHALL` | `VARCHAR2(2)` | 权限 | 是否可以查询全部病案 0不可以 1可以 |
| `FCHANGEDATE` | `DATE` |  |  |
| `FLASTDATE` | `DATE` |  |  |
| `FLASETDATE` | `DATE` |  |  |
| `FUSERTYPE` | `NUMBER` | 用户类型 | 1：医生 2：护士 0：其他 |
| `FUSERSTATE` | `NUMBER` | 用户状态 | 1:锁定 0：不锁定 |
| `HOSPITALAREACODE` | `VARCHAR2(200)` | 所属院区 |  |
| `LOGINERRORCOUNT` | `VARCHAR2(10)` | 登录失败次数 |  |
| `LASTLOGINDATE` | `DATE` | 最后登录时间 |  |
| `PHONE_NO_HOME` | `VARCHAR2(100)` | 电话 |  |

## `T_MSS_ROLE` — 角色表

- **表名**：`T_MSS_ROLE`
- **用途/说明**：角色表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FROLE_NO` | `VARCHAR2(40)` | 主键 | NN |
| `FROLE_NAME` | `VARCHAR2(40)` | 描述 |  |
| `FROLE_CONTENT` | `VARCHAR2(2000)` |  |  |
| `FREMARK` | `VARCHAR2(50)` | 备注 |  |
| `HOSPITALAREACODE` | `VARCHAR2(200)` | 所属院区 |  |

## `T_MSS_AUTHMAPPING` — 权限表

- **表名**：`T_MSS_AUTHMAPPING`
- **用途/说明**：权限表

| FieldName | Data Type | Description | Memo |
|---|---|---|---|
| `FAUTHMAPPINGID` | `VARCHAR2(40)` |  | NN |
| `FID` | `VARCHAR2(100)` | 对应类型的ID 如角色 科室 部门 根据类型定位ID类型 |  |
| `FAUTHORITYID` | `VARCHAR2(40)` | 对应权限ID |  |
| `FTYPE` | `VARCHAR2(50)` | ID类型 |  |
| `FDATE` | `DATE` | 添加时间 |  |
| `FUSER` | `VARCHAR2(200)` | 添加人 |  |
| `FST` | `VARCHAR2(10)` | 状态 |  |
| `FUPDATEUSER` | `VARCHAR2(50)` | 修改人 |  |
| `FUPDATE` | `DATE` | 修改日期 |  |
| `FPRIVIEGETYPE` | `VARCHAR2(10)` | 权限类型 |  |
| `FAUTHMAPPINGID` | `VARCHAR2(40)` |  |  |
| `FID` | `VARCHAR2(100)` | 对应类型的ID 如角色 科室 部门 根据类型定位ID类型 |  |
