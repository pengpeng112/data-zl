> 类别：资产（源端用户权限模型参考）
>
> 状态：**已完成（2026-09-01 用户授权"记录人员权限关系"；关系已落平台复核草稿 id 99-101；本地证据齐）**
>
> 关联：171 号后续；sjzc 技能（`paperless_cdms_oracle_10_10_10_93` live 只读）；155 号 ECG 草稿先例

# CDMS 无纸化用户权限模型与下乡名单核对（172）

## 0. 给后续 AI 的速查（本节可直接调用）

**系统**：PAPERLESS_CDMS（无纸化病案，Oracle `10.10.10.93`，owner=CDMS；sjzc live 源码 `paperless_cdms_oracle_10_10_10_93`）

**用户-权限三层模型**（2026-09-01 实测）：

| 层 | 表 | 关键字段 | 说明 |
|---|---|---|---|
| 用户 | `CDMS.T_MSS_EMP_DICT` | `FLOGINNAME`=工号(登录名)、`FUSERNAME`=姓名、`FPWD`、`FDEPT`=6位科室码、`LASTLOGINDATE` | 业务用户全在此 |
| 权限映射 | `CDMS.T_MSS_AUTHMAPPING` | **`FID`=被授权人工号**、`FAUTHORITYID`=权限对象、`FTYPE`=类型、`FST`=0 生效、`FDATE`=配置时间、`FAUTHMAPPINGID`=32位hex GUID 主键 | 一人一行一权限 |
| 科室字典 | `CDMS.KESHID` | `AAA`=6位科室码、`BBB`=科室名 | 列名为泛型 AAA-JJJ，语义实测 |

**⚠️ 三大陷阱**（首查必踩，171 后续会话 2026-09-01 实证）：
1. `T_MSS_AUTHMAPPING.FUSER` 是**操作人**（恒为 `admin`），被授权用户在 **`FID`**——拿工号去匹配 FUSER 恒 0 行。
2. `T_MSS_EMP_DICT.FUSERSTATE` 全库 1778 行恒 `0`，**无停用语义**，不能当权限/状态位用；`AbpUsers` 表只有 admin（ABP 框架表，业务用户不在那）。
3. `T_MSS_EMP_DEPT` / `T_MSS_USERTOCATEGORY` 全库 **0 行**（未启用的空壳映射表），权限真实落点只有 AUTHMAPPING。

**权限模板**（每用户 5 行，admin 2026-09-01 为 001708/002249 现配实证）：

| FTYPE | FAUTHORITYID | 语义 |
|---|---|---|
| `0` | `a1c9192fbe31423fab2dce6f81791b88` | 角色（GUID 常量） |
| `2` | 6位科室码（=`EMP_DICT.FDEPT`=`KESHID.AAA`） | **科室权限** |
| `3` | `100005` | **人员权限**（常量） |
| `5` | `A00001` | 其他（常量） |
| `10` | `0`（个别用户 `1`，如 002339，语义待确认） | 标志位 |

`FPRIVIEGETYPE` 与 FTYPE 同值。另见 FTYPE=8 附加科室行（按需）。

**查某人权限**（sjzc live，只读）：
```sql
SELECT FTYPE, FAUTHORITYID, TO_CHAR(FDATE,'YYYY-MM-DD')
FROM CDMS.T_MSS_AUTHMAPPING WHERE FID = '<工号>' ORDER BY FTYPE
```
（注意 Oracle 大小写敏感的 ABP 表需双引号，T_MSS_* 系可直接用。）

**补权限**：源库只读红线，AI 不得直写——走系统界面「用户管理→权限配置」按 5 行模板配，或由管理员/厂商执行 `开发起步包/output_r171/cdms_grant_missing.sql`（幂等 NOT EXISTS 防重）。

## 1. 平台关系登记（已落，draft 待复核）

按 155 号 ECG 先例落 `asset.asset_relation_reviews`（**不直写正式关系**，2026-09-01 用户授权写入生产，dry-run 先行+复跑幂等实证 existing=3）：

| id | 关系 | join | confidence |
|---|---|---|---|
| 99 | CDMS.T_MSS_EMP_DICT → CDMS.T_MSS_AUTHMAPPING | FLOGINNAME = FID | C |
| 100 | CDMS.T_MSS_EMP_DICT → CDMS.KESHID | FDEPT = AAA | C |
| 101 | CDMS.T_MSS_AUTHMAPPING → CDMS.KESHID | FAUTHORITYID = AAA（仅 FTYPE='2' 行） | C |

复核草稿总数 98→101；`source_evidence` 内含陷阱与模板说明。**转正式关系需人工复核**（40 号口径）。

## 2. 2026-08 下乡名单核对结论（33 人）

- **在户且有完整权限 6 人**：闫文青 001429、张骁 001708、刘永科 002249（后两人 2026-09-01 admin 当日补配）、许国安 002339、李熙星 003847、韩云凤 003245。
- **在户但无任何权限行 24 人**：陈慧 001542、陈晓、樊琳琳、户颖慧、李小芹、李琪、刘君、刘治超、刘婷婷、齐熠颖、乔永静、沈淑文、史雪娇、宋肖、王成、王娜娜、王茹、吴玖旭、杨帆、于鹏、张成印、张双双、赵岩、赵慧(000110)——补齐 SQL 已备（§0）。
- **从未建户 3 人**：李进叶 001324（影像科 0503）、安鹏 003176（影像科 0503）、李威 002124（病理科 050202）——先界面新增用户再配权限。
- **工号存疑**：赵慧名单 001172 无记录，库内同名=000110（EMP_DICT 无身份证列无法机核，需人工确认）。

## 3. 证据索引

- 核对明细（修正版）：`开发起步包/output_r171/cdms_xiaxiang_check.json`
- 补权限 SQL（25 人×5 行幂等）：`开发起步包/output_r171/cdms_grant_missing.sql`
- 草稿导入脚本（可复跑幂等）：`开发起步包/output_r171/import_cdms_relation_reviews.py`
- 名单原件：`F:\xwechat_files\penghe1185991312_652e\msg\file\2026-08\2025年度下乡人员名单.xlsx`（微信收件，33 人含身份证/科室/工号）

## 4. 红线自检

源库全程只读（live SELECT）；生产平台写入仅 `asset_relation_reviews` 草稿层（用户明确授权"更新资产系统的关系"，走 155 先例不碰正式关系）；无凭据落盘；姓名/身份证未进日志（文档仅工号+姓名，身份证不收录）。
