> 类别：当前（对接说明）

# 157 血透系统对接 PACS 获取 DR 图像技术说明

> 状态：发布给血透系统开发方自评估与联调准备
> 日期：2026-08-27
> 依据：PACS 只读探查实测（83 号 + 2026-08-27 通道核验，全部来自平台受控只读查询，源库零写入）
> 读者：血透系统开发/集成工程师。本文自包含，按"前置条件 → 数据定位 → 三条获取通道 → 自检清单"顺序阅读

---

## 0. 一页结论

PACS（gecris，数据库 10.10.10.191 MySQL）**不在数据库里存图像文件路径**，库里只存索引；DR 图像本体在 DICOM 归档服务器 `10.10.10.201:104`（AETitle=`AE_ARCH`）。要"获取 DR 图像做分析"，推荐走 **通道三（DICOM C-MOVE，拿原始 DICOM 文件）**；报告 PDF 与网页浏览另有两条捷径。三条通道 2026-08-27 均实测连通。

| 通道 | 地址 | 得到什么 | 适合场景 |
|---|---|---|---|
| ① ZFP 影像浏览 | `http://10.10.10.196:80`（HTTP 200 已验证） | 网页端查看器（零脚印） | 人工看片，不是文件接口 |
| ② iws imageServer | `http://10.10.10.191:8054`（HTTP 206/pdf 已验证） | 报告 PDF 直链 | 下载报告文档 |
| ③ DICOM 归档 | `10.10.10.201:104`，AE_ARCH，QR 型（端口开放已验证） | **原始 DR DICOM 文件** | **图像分析（推荐）** |

---

## 1. 前置条件（联调前向信息科/PACS 管理员申请）

| # | 事项 | 说明 |
|---|---|---|
| 1 | 网络放行 | 血透系统服务器需可达：`10.10.10.191:3306`（查索引，可选）、`10.10.10.201:104`（DICOM）、如需①②再放行 `10.10.10.196:80`、`10.10.10.191:8054` |
| 2 | 数据库只读账号 | 在 10.10.10.191 MySQL 上建专用账号，仅授 `gecris` 库 SELECT（涉及表见 §2.1）；禁止使用现有应用账号 |
| 3 | DICOM 目的端登记 | C-MOVE 需要在 AE_ARCH 上登记血透侧的 **AETitle + IP + Port**（C-GET 不需要登记，见 §4.3） |
| 4 | 用途与合规 | 图像用于指定分析用途；患者标识字段按院内脱敏规范处理，不得外传；采集操作避开检查高峰时段 |

---

## 2. 第一步：在数据库里定位 DR 检查与 StudyUID

### 2.1 涉及表（gecris 库）

| 表 | 用途 | 关键列 |
|---|---|---|
| `ModalityInfo` | 设备表 | `ModalityID`、`ModalityName`、`ModalityLocation`（=DICOM Modality，DR 为 `DX`） |
| `ExamInfo` | 检查主档 | `ExamID`、`ModalityID`、`PatientIntraID`、`StudyInstanceUID`、`PreExamExamDate/Time`、`ExamSatus`（'6'=已完成） |
| `MPPS` | 检查执行/DICOM 步骤 | `ExamID`、`SUID`（=本次执行的 Study UID） |
| `pacsstudy` | PACS Study 索引 | `study_instance_uid` |
| `EMR_EXAM_IMAGE_PATH`（视图） | 现成的浏览 URL | `IMAGE_SAVE_PATH`（①通道完整 URL）、`IMAGE_ID`（=ExamID） |
| `CDR_CHECK_REPORT`（视图） | 报告 PDF 直链 | `PACS_URL` |

注意两个 Study UID 变体：`ExamInfo.StudyInstanceUID`（≈`pacsstudy.study_instance_uid`）用于 DICOM 查询；`MPPS.SUID` 用于 ZFP URL。一般相同，取到后建议做一次核对。

### 2.2 已验证的查询 SQL

```sql
-- ① DR(DX) 设备清单（实测 5 台有效：150/170/178/185/187；192 是"DX退费"非设备）
SELECT ModalityID, ModalityName, modalitymodel
FROM ModalityInfo WHERE ModalityLocation = 'DX';

-- ② 按时间窗取已完成 DR 检查 + StudyInstanceUID（改日期与 ModalityID 即可）
SELECT e.ExamID,
       p.PatientID,
       e.PreExamExamDate,
       m.ModalityName,
       e.StudyInstanceUID          -- 通道③ DICOM 用
FROM ExamInfo e
JOIN ModalityInfo m ON e.ModalityID = m.ModalityID
JOIN PatientInfo p ON p.PatientIntraID = e.PatientIntraID
WHERE e.ModalityID IN (150,170,178,185,187)
  AND e.ExamSatus = '6'
  AND e.PreExamExamDate BETWEEN '2026-08-01' AND '2026-08-31';

-- ③ 通道①完整 URL（视图自带厂家服务账号，直接可开）
SELECT IMAGE_ID, IMAGE_SAVE_PATH
FROM EMR_EXAM_IMAGE_PATH
WHERE IMAGE_ID = <ExamID>;
-- 视图口径：PreExamExamDate >= '2026-01-01' 且 ExamSatus='6'

-- ④ 通道②报告 PDF 直链
SELECT PACS_URL FROM CDR_CHECK_REPORT
WHERE <按 ROWKEY/PATIENT_ID 关联你的检查>;
```

实测样例（2026-08-27，6 号检查室/西门子双板DR）：
`ExamID=1256327`，`StudyInstanceUID≈1.2.840.113619.186.808615911510.20260827165948959…`

SQL 写作注意：PACS 侧连接层使用参数格式化时 `LIKE '%x%'` 的 `%` 需转义，尽量用 `INSTR(col,'x')>0` 替代。

---

## 3. 通道①：ZFP 影像浏览（人工看片用）

- URL 形态（由 `EMR_EXAM_IMAGE_PATH.IMAGE_SAVE_PATH` 拼好）：

```
http://10.10.10.196/ZFP?mode=proxy#view&un=administrator&pw=<厂家内置令牌>&study_instance_uid=<MPPS.SUID>
```

- 令牌为 PACS 厂家存在库内视图里的服务账号凭据，**不要抄进代码/文档**，运行时从视图读取；
- 返回 HTML 查看器页（实测 200，2KB 零脚印前端），适合浏览器嵌入，**不是文件下载接口**；
- `#view` 是 URL fragment，编程访问时需按 `mode=proxy%23view` 处理。

## 4. 通道②：iws imageServer 报告 PDF（文档下载用）

- 直链来自 `CDR_CHECK_REPORT.PACS_URL`，形态：

```
http://10.10.10.191:8054/iws/imageServer/report/<yyyymmdd>/<ExamID>/<uuid>.pdf
```

- 实测支持 Range（HTTP 206，application/pdf），可直接：

```bash
curl -o report.pdf "http://10.10.10.191:8054/iws/imageServer/report/20260827/1256344/<uuid>.pdf"
```

- 只包含报告文档，**不是原始影像**。

## 5. 通道③（推荐）：DICOM 归档 C-QUERY / C-MOVE 拉原始 DR 图像

归档节点：`10.10.10.201:104`，AETitle `AE_ARCH`，`PACS_HOST_INFO.storageType='QR'`（支持查询/检索）。

### 5.1 dcm4che 命令行（联调自测最快）

```bash
# 连通性：C-ECHO
echoscu -c 1 -aet BLOODDIALYSIS 10.10.10.201 104

# C-FIND：按 StudyInstanceUID 找 Series
findscu -c -aet BLOODDIALYSIS -W \
  -k QueryRetrieveLevel=SERIES \
  -k StudyInstanceUID=<StudyInstanceUID> \
  -k SeriesInstanceUID -k Modality -k SeriesNumber \
  10.10.10.201 104

# C-MOVE：把整个 Study 拉到本机（需先在 AE_ARCH 登记你的 AET/IP/Port）
movescu -c -aet BLOODDIALYSIS -aem BLOODDIALYSIS \
  -k QueryRetrieveLevel=STUDY -k StudyInstanceUID=<StudyInstanceUID> \
  --store-tls=false 10.10.10.201 104
```

### 5.2 Python（pynetdicom + pydicom）

```python
from pynetdicom import AE, QueryRetrieveLevel
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind, StudyRootQueryRetrieveInformationModelMove

ae = AE(ae_title=b"BLOODDIALYSIS")
ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

ds = {
    "QueryRetrieveLevel": QueryRetrieveLevel.STUDY,
    "StudyInstanceUID": "<StudyInstanceUID>",
    "PatientID": None, "StudyDate": None, "Modality": None,
}
assoc = ae.associate("10.10.10.201", 104, ae_title=b"AE_ARCH")
if assoc.is_established:
    responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)
    for status, identifier in responses:
        if status and identifier:
            print(identifier.get("StudyInstanceUID", ""), identifier.get("Modality", ""))
    assoc.release()
```

- **C-MOVE** 需在归档侧登记目的端 AETitle/IP/Port（前置条件 #3）；若不便登记，可协商 **C-GET**（连接反向建立，无需预先登记）；
- 拉到的是 `.dcm` 原始文件（含原始像素），适合 AI/定量分析；
- DR 图像量不大（每检查数幅～数十幅），按检查逐个拉取即可，勿做全库 MOVE。

---

## 6. 血透侧自检清单（联调前逐项打勾）

- [ ] `telnet 10.10.10.201 104` 通（DICOM 通道）
- [ ] `echoscu` C-ECHO AE_ARCH 成功（或 pynetdicom associate 成功）
- [ ] （如用①②）`curl -I http://10.10.10.196:80` 与 `curl -r 0-1024 -I http://10.10.10.191:8054/...` 通
- [ ] 只读 DB 账号到手，§2.2 SQL-② 能查出目标 StudyInstanceUID
- [ ] C-FIND 按 StudyInstanceUID 命中 Series 且 Modality=DX
- [ ] C-MOVE/C-GET 单检查试拉成功，pydicom 能读 `PixelData`
- [ ] 患者标识脱敏与用途限定已确认

## 7. 边界与红线

- 只读：对 10.10.10.191 数据库仅 SELECT；对 10.10.10.201 仅 DICOM 查询/检索，**禁止 C-STORE 到归档、禁止删除/改动**；
- 厂家内置令牌（ZFP URL 内）不得写入血透系统代码库或日志；
- 批量拉取安排在非高峰时段，单次按检查粒度，避免影响归档服务；
- 图像与患者信息仅限约定分析用途，输出物按院内脱敏规范处理。

## 8. 联调对接人

- 数据/通道口径支持：数据资产管理侧（本仓库维护方）
- DICOM 目的端登记、防火墙放行：信息科 / PACS 管理员
- 通道实测记录：2026-08-27（ZFP 200 / imageServer 206 pdf / 104 端口开放），凭据与令牌不在本文出现
