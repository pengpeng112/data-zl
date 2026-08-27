> 类别：证据

# 158 凡科新HIS_SQL字典与数据流核验报告

> 状态：T1–T6 全部执行完毕（T4 中 ODS live 端点当次不可达，已用平台元数据核验替代，如实标注）
> 日期：2026-08-27
> 对象：`E:\fancyhis`（凡科/fancyinfo 新 HIS 生产节点拷贝，全程只读，未运行 Host、未解密连接串、未开监听）
> 跨仓参考：`D:\Users\Administrator\Desktop\嘉和\docs\35-fancyhis新HIS结构与逆向分析.md`（§4 15 库位/§6 JHApi/§8 日志）
> 工具（本仓库新增，无凭据）：`tools/fancyhis_sql_extract.py`（T1 字符串堆）、`tools/fancyhis_dnfile_scan.py`（T2/T3 骨架）、`tools/fancyhis_attr_extract.py`（T2/T3 CustomAttribute blob）
> 产物：`开发起步包/数据资产_新HIS逆向资产包/`——`fancyhis_sql_dictionary.json`（SQL 字典+表归类）、`fancyhis_dnfile_scan.json`（TypeDef/命名空间/http 串）、`fancyhis_attributes.json`（519 实体→表映射 + 36 条 JHApi 路由）

## 1. T1 SQL 字典（字符串堆提取）

- `Fancy.His.Micro.dll`(17MB) UTF-16LE 可打印串 5,359 条 → SQL 前缀过滤得 **124 条 SQL**（去重计次，全部带 `count` 与归一化文本）+ **52 个表 token**。
- 表归类（启发式，按 dbconfig 库位）：`SYS_*/PUB_*` → masterdb 9 个（SYS_EMPLOYEE×4、SYS_USER_DEPT、SYS_WARDAREA_WARD、PUB_ITEM_COMPARE×多、PUB_PATIENT_INJURY_TEMP…）；老 HIS 风格 12 个（PAT_VISIT×4、INP_BILL_DETAIL×3、MR_BILL_COSTS×2、V_HIS_INFECTION_EMR_MEDICAL_INFO…）；MEDREC.* 1、COMM.* 1、HIS.DIAGNOSIS 1、JHEMR.* 1；**未归类 27**（含 COUNTRY_DICT、PATS_IN_HOSPITAL、HOSPITAL_CONFIG_NEW、JMPZ_PZFY_V、OPS_SETTLE_TEST、OPS_SHEET1、B_T_REQD、B_T_POSTTRANSEVAL…，逐条在 JSON 待核列）。

## 2. T2 JHApi 数据流定案（新HIS→嘉和）

- dnfile 全量 TypeDef 11,718；JHApi 相关类型 73 个，**5 个 Refit 接口全部找到**。
- **36 条路由全部提取**（CustomAttribute blob 解出）：`IInPatientManager`→`/api/InPatient/*`（11 个：Add/Update Register·InDept·ChangeDept·Discharge、ChangeAreaBed、Cancel×3）；`IIPCOrderManager`→`/api/inPatient/*`（addMedicalOrder/diagnosisOrder/nurseOrder/otherOrder/addOrder）；`IJHPubManager`→`/api/pub/*`（Add/Update/Cancel ExamApply 等 13）；`ITermManager`→术语注册/更新路由；**`IInPatientEsbManager.SendMessage`→`POST /fancy/esb-interaction/esb/esbmsgmethod`**（ESB 单通道）。
- **Base URL 定案：`http://192.168.102.3:8002/`**（`appconfig.Prod.json → references.iThirdOpenApiManager`，JHApi 属 `References.ThirdOpenApi` 命名空间）——即新HIS→嘉和走**第三方开放平台**，**不是** 179:86 通用接口直连（回答参考文档待办#5）。
- 链路图（文字版）：
  `新HIS住院/医嘱/申请单事件 → Fancy.His.Micro(JHApi Refit) → HTTP 192.168.102.3:8002 开放平台 → 嘉和EMR(177 jhemr/179服务)`；旁路：`IInPatientEsbManager → /fancy/esb-interaction/esb/esbmsgmethod`（ESB，同 base 或开放平台转发，待联调抓包定案）。
- 附带收获：字符串堆 26 条 http 串 = 新HIS 外部依赖面（发票 10.10.8.228:8426、帆软报表 10.10.9.227:8080/webroot/decision、CA/SSO 10.10.9.162、YzyEntry 10.10.10.225:10000、帆软 IPC 报表 viewlet=/his/ipc/ 等，全量在 dnfile_scan.json）。

## 3. T3 实体→表映射（Table 特性精确解）

- **519 个实体类带 Table 特性并解出表名**（精确映射，非猜名）。亮点：
  - 感控视图族：`FXHIS.V_EMR_ACTIVITY_INFO / V_EMR_ADMISSION_INFO / V_EMR_DISCHARGE_INFO / V_EMR_PATIENT_INFO / V_EMR_VITAL_SIGNS_RECORD / V_CrbReport`（传染病上报域）
  - `HISUSER.PLATE_EMR_PDF`（无纸化病案 PDF 表）、`report.t_itf_report`（PG ListeningReport 库位）、`SECURE_CORE`、`HrpHisHaocaiEntity`（HRP 耗材）
  - 可疑映射 1 例：`HospitalConfigNew → PAT_MASTER_INDEX`（实体名与表名不相关，疑似复制粘贴错 Table 特性，**列"有用发现"待厂商确认**）
- Repositories/Domain/Entity 命名空间类型 1,518 个；按命名空间前缀的子系统分布在 dnfile_scan.json（`namespace_roots_top`）。

## 4. T4 平台活库交叉核验（sjzc 受控只读）

| 对象 | 通道 | 结果 |
|---|---|---|
| PAT_VISIT / INP_BILL_DETAIL | DATA_CENTER columns | ✓ 存在（schema=HIS，字段级） |
| COMM.SYS_EMPLOYEE | DATA_CENTER columns | ✓ 存在（schema=COMM） |
| COMM.SYS_EMPLOYEE / MEDADM.SYS_EMPLOYEE | his_source live | ✗ ORA-00942（hisuser 源库无此 owner 副本）→ 新HIS SQL 的裸 `SYS_EMPLOYEE` 应落其 **masterdb 镜像/同义词**，与 ODS 的 COMM owner 平行，归属按 source_code 区分（正好印证 146 E5 的 source_code 隔离设计） |
| HISUSER.PLATE_EMR_PDF | his_source live | ✓ 存在（T3 映射对上活库） |
| FXHIS.V_EMR_PATIENT_INFO | his_source live | ✓ 存在（感控视图族活库可用） |
| ods_8_216 live | — | 当次 ORA-12541（端点暂不可达），已用平台元数据核验替代，非阻断 |
| report.t_itf_report / PATS_IN_HOSPITAL 等 | — | 平台未登记对应库位（ListeningReport(PG)/masterdb），列为待登记项 |

## 5. T5 值域候选（防猜测红线标注）

- IN 字面量极少（新HIS SQL 高度参数化）：仅 `IN ('2','3')` ×1（待确认）。
- 状态赋值字面量（全部 **待确认**，未与 148 值域库比对命中，禁止直接采信）：`DIAGNOSIS_TYPE='3'`、`BED_STATUS='0'`、`ORDER_STATUS='3'`。
- 字典表引用 10+（可作为取数 join 口径参考）：`ORDER_CLASS_DICT`、`DEPT_DICT`、`STAFF_DICT`、`AREA_DICT`、`NATION_DICT`、`COUNTRY_DICT`、`INP_ITEM_BATCH_DICT`、`INP_RCPT_FEE_DICT`、`MEDREC.ID_TYPE_DICT`、`COMM.OUTP_MR_DICT`。
- 通道建议：以上字面量按 149 规则进 value_domains `待确认` 桶；confirmed 维持 148 既有口径（离院方式 4/5 本轮未见新证据）。

## 6. 有用发现 Top10

1. **嘉和通道定案**：新HIS→嘉和 = HTTP `192.168.102.3:8002` 开放平台（36 路由全量提取），非 179:86；ESB 另有 `/fancy/esb-interaction/esb/esbmsgmethod` 单入口。
2. **新HIS SQL 直查老输血表**：`B_T_REQD`、`B_T_POSTTRANSEVAL`（bloodSystem 库位）——输血数据被新HIS 直接读，跨库依赖实锤。
3. **感控视图族可用**：FXHIS.V_EMR_* 6 张视图活库存在，院感/传染病取数可用替代大表直查。
4. `HISUSER.PLATE_EMR_PDF` 活库存在——病案 PDF 路径来源（可补 134 病案首页链路）。
5. **可疑 Table 特性**：`HospitalConfigNew→PAT_MASTER_INDEX` 名实不符，疑厂商复制错误。
6. 生产 SQL 含测试表：`OPS_SETTLE_TEST`、`OPS_SHEET1`（新HIS 侧卫生问题）。
7. `PUB_ITEM_COMPARE`/`PUB_ITEM_COMPARE_OIL` 高频查询（×5/×4），项目对照域热点。
8. 新HIS masterdb 与 ODS 的 `SYS_EMPLOYEE` 双轨（COMM owner 在 ODS，裸名在 masterdb），取数须按 source 区分。
9. 帆软报表嵌入：`10.10.9.227:8080/webroot/decision/view/report?viewlet=/his/ipc/`（IPC 报表实际走帆软）。
10. `report.t_itf_report`（PG）证实 ListeningReport 库位真实使用（听诊/接口报告）。

## 7. 对平台 HIS SQL 的完善与修订建议（用户问项）

1. **新增可用资产**：把 `FXHIS.V_EMR_*` 感控视图族、`HISUSER.PLATE_EMR_PDF` 纳入 ODS/HIS_SOURCE 取数口径（活库已验证），院感/病案 PDF 类查询优先走视图。
2. **关系候选摄取**：T1 SQL 中的跨表 join（如 PATS_IN_HOSPITAL↔PAT_VISIT、B_T_REQD 链）走 `sql-relation-intake` 技能入平台复核 draft（本轮证据=新HIS 生产 SQL，等级高于猜名）。
3. **值域补录**：§5 字面量与字典表清单提交 value_domains 待确认通道；ORDER_STATUS/DIAGNOSIS_TYPE 语义需厂商或活库 COUNT 验证后定 confirmed。
4. **修订口径**：既有查询资产凡引用裸 `SYS_EMPLOYEE`/`PAT_VISIT` 的，标注库位双轨（ODS.COMM vs 新HIS masterdb vs HisRead），配合 table API 的 `source_code` 参数防串库。
5. **嘉和排障入口**：入出转/医嘱/申请单"没到嘉和"先查 `192.168.102.3:8002` 开放平台侧（36 路由清单已入库），再查嘉和 177 库落库。

## 8. 红线遵守

E:\fancyhis 全程只读（仅读 DLL/配置文件字节）；未运行 Fancy.His.Host.exe；未提取 DES 密钥/未解密任何连接串；平台核验仅 SELECT 且限量（存在性探测 ROWNUM<=1）；患者明细零导出（本报告无患者数据）；未写任何业务源库；嘉和仓库未写入（回流由用户决定）。

## 9. BLOCKED / 待办

| 项 | 状态 |
|---|---|
| ODS live(ods_8_216) 当次 12541 | 端点暂不可达，元数据已核验；下次可用时补一条存在性 live 即可 |
| ListeningReport(PG)/masterdb 等新HIS 专属库位 | 平台未登记，无法活库核验（按 §4 记录） |
| ESB base 归属（同 8002 或独立） | 需联调抓包/日志定案（参考文档 §8 日志格式可查） |
| 未归类 27 表 + 状态字面量语义 | 待厂商确认或后续活库 COUNT 核验 |

---

## 10. §7 建议落地记录（2026-08-27 二次处理）

| 建议 | 处理结果 |
|---|---|
| 感控视图族/PLATE_EMR_PDF 入取数口径 | ✅ 活库列级核验完成（V_EMR_PATIENT_INFO 33 列/ADMISSION 19/DISCHARGE 18/ACTIVITY 32/VITAL_SIGNS_RECORD 20 + V_CRBREPORT；键含 PATIENT_ID+SERIAL_NUMBER）；已沉淀进 `.agents/skills/hisuser-readonly-sql/SKILL.md`（含"勿用 _copy1 备份副本"警示——本次新发现 FXHIS 下每张视图均有 _copy1） |
| 关系候选摄取 | ✅ 局部完成：124 条 SQL 的别名限定等值 join 仅抽得 **4 条边**（SYS_USER_DEPT.USERID=SYS_USER.ID、STAFF_DICT.ID=CASHER_NO_REC.USER_ID、INPUT_NODRUG_LIST.PERFORMED_BY=SYS_DEPARTMENT.DEPTCODE、INPUT_NODRUG_LIST.ITEM_CLASS=BILL_ITEM_CLASS_DICT.CLASS_CODE，存 `relation_candidates.json`）——多数 SQL 为动态拼接无法静态抽 join。**不入平台 draft**：对端表属新HIS masterdb（平台未登记），按 plan139 口径记跨系统待验证证据，待 masterdb 登记后再走 sql-relation-intake |
| 值域补录 | ⏸ 平台侧：候选已在 §5（3 状态字面量+10 字典表）；value_domains.json 为平台导出视图勿手改（149 红线），正式入库需平台值域写通道，列为待授权待办 |
| 防串库修订 | ✅ `.agents/skills/ods-readonly-sql/SKILL.md` 增"库位双轨警示"（SYS_EMPLOYEE ODS=COMM vs 新HIS masterdb；PAT_VISIT 同类），要求带 owner+source_code |
| 嘉和排障入口 | ✅ 已在 §2/§7（8002 开放平台 36 路由清单在 fancyhis_attributes.json） |
