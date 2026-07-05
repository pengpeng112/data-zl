# -*- coding: utf-8 -*-
"""
数据资产包生成器
- 输入: 08_数据中心元数据快照.json (活元数据) + 内置已确认关系规格 (来自两份已确认 MD)
- 输出: 数据资产_资产包/ 下的 tables.csv / columns.csv / relationships.csv / catalog.json
- 同时打印校验报告 (库表/字段在活元数据中的存在性、行数)
复跑: python tools/build_asset_package.py
"""
import json, csv, os, sys

BASE = os.path.join(os.path.dirname(__file__), "..")
META = os.path.join(BASE, "08_数据中心元数据快照.json")
OUT  = os.path.join(BASE, "数据资产_资产包")
os.makedirs(OUT, exist_ok=True)

meta = json.load(open(META, encoding="utf-8"))
schemas = meta["schemas"]

def get_table(schema, table):
    return schemas.get(schema, {}).get("tables", {}).get(table)

def col_exists(schema, table, col):
    t = get_table(schema, table)
    if not t: return False
    return any(c["name"].upper() == col.upper() for c in t["columns"])

# ============ 已确认关系规格 (来自两份已确认 MD, A=字段+关联均实跑确认 B=字段确认关联需补 C=推测) ============
TABLES = [
    # schema, table, domain, grain, pk(list), confidence, note
    ("HIS","PAT_MASTER_INDEX","患者主数据","一名患者",["PATIENT_ID"],"A","患者主索引;含 INP_NO 住院号用于关联 EMR 文书"),
    ("HIS","PAT_VISIT","就诊","一名患者一次住院",["PATIENT_ID","VISIT_ID"],"A","住院就诊事实主表;出院时间常用于上报范围"),
    ("HIS","DIAGNOSIS","诊断","一次住院×一条诊断",["PATIENT_ID","VISIT_ID","DIAGNOSIS_TYPE","DIAGNOSIS_NO"],"A","DIAGNOSIS_TYPE: 2入院3出院8病理7损伤1门急诊"),
    ("HIS","DIAGNOSIS_TYPE_DICT","诊断字典","一个诊断类型",["DIAGNOSIS_TYPE_CODE"],"A","诊断类型字典"),
    ("HIS","DEPT_DICT","科室字典","一个科室",["DEPT_CODE"],"A","含院内 DEPT_CODE/NAME;QMPT 为平台标准(如有)"),
    ("HIS","STAFF_DICT","人员字典","一名职工",["EMP_NO"],"A","医师工号/姓名/身份证"),
    ("HIS","DOC_REGISTER_EMP_MATCH","人员字典","医师执业注册匹配",["EMP_NO"],"A","取医师执业证书号 PRACTICE_CERT_CODE"),
    ("HIS","PATS_IN_HOSPITAL","就诊","在院床位兜底",["PATIENT_ID","VISIT_ID"],"A","病区/床号兜底"),
    ("HIS","ORDERS","医嘱","一次住院×医嘱",["PATIENT_ID","VISIT_ID","ORDER_NO"],"B","状态1新开2执行3停止有效/4作废无效"),
    ("HIS","CLINIC_MASTER","门诊","门诊就诊主记录",["PATIENT_ID","VISIT_DATE","VISIT_NO"],"B","门诊主线"),
    ("HIS","OUTP_MR","门诊","门诊病历",[],"B","与门诊就诊关联"),
    ("HIS","OUTP_RCPT_MASTER","门诊费用","门诊收据主表",["RCPT_NO"],"B",""),
    ("HIS","OUTP_BILL_ITEMS","门诊费用","门诊收费明细",["RCPT_NO","ITEM_NO"],"B",""),
    ("HIS","INP_SETTLE_MASTER","住院费用","住院结算主表",["PATIENT_ID","VISIT_ID"],"A",""),
    ("HIS","INP_BILL_DETAIL","住院费用","住院费用明细",["PATIENT_ID","VISIT_ID"],"A","巨表(约2亿行),查询必限定"),
    ("HIS","LAB_TEST_MASTER","检验","一份检验报告",["TEST_NO"],"A","检验主表;住院 VISIT_ID 或 0/NULL=门诊"),
    ("HIS","LAB_TEST_ITEMS","检验","报告×项目",["TEST_NO","ITEM_NO"],"A","PK_LAB_TEST_ITEMS2=ORDER_ID+ORDER_ITEM_ID"),
    ("HIS","LAB_RESULT","检验","报告×项目×结果",["TEST_NO","ITEM_NO","PRINT_ORDER"],"A","约1亿行,查询必用 TEST_NO 限定"),
    ("HIS","LIS_EXAMINE_ITEM_MAP","检验","检验项目平台值域映射",[],"B",""),
    ("HIS","EXAM_MASTER","检查","一份检查",["EXAM_NO"],"A","EXAM_CLASS 存中文(CT/磁共振),非字典内码"),
    ("HIS","EXAM_REPORT","检查","检查报告",["EXAM_NO"],"A","无 PATIENT_ID,必经 EXAM_NO 关联 EXAM_MASTER"),
    ("HIS","OPERATION","手术","HIS侧手术/操作",["PATIENT_ID","VISIT_ID","OPERATION_NO"],"B","OPER_ID 全为 NULL,不要用它关联手麻"),
    ("MTL","EPR_INPATIENT_DOCINDEX","电子病历(旧)","住院文书索引",["UHID"],"A","P_INPATIENT_NO=INP_NO, P_INPATIENT_TIMES=VISIT_ID"),
    ("MTL","EPR_INPATIENT","电子病历(旧)","文书主表",["UHID","ID"],"A","DOC_TYPE_NAME like '%出院记录%' 等"),
    ("MTL","EMRSD_CONTENT","电子病历(旧)","文书段落内容",["UHID","段落编号"],"A","段落内容为 CLOB;段落编号=EPR_INPATIENT.ID"),
    ("JHEMR","JHMR_FILE_INDEX","电子病历(新)","文书索引",["FILE_UNIQUE_ID"],"A","FILE_FLAG<>'T' 有效;TOPIC like '%手术记录%'"),
    ("JHEMR","JHMR_FILE_CONTENT_DG","电子病历(新)","文书打散内容",["FILE_UNIQUE_ID"],"A","含 PATIENT_ID+VISIT_ID，可直接挂 HIS 住院"),
    ("JHEMR","JHMR_FILE_CONTENT_TEXT","电子病历(新)","文书正文",["FILE_UNIQUE_ID"],"A","MR_CONTENT 正文"),
    ("JHEMR","PAT_DIAGNOSIS","电子病历(新)","新 EMR 诊断",["PATIENT_ID","VISIT_ID"],"A","按 PATIENT_ID+VISIT_ID 挂 HIS 住院"),
    ("JHEMR","FIRST_PAGE_COSTS","电子病历(新)","病案首页费用",["PATIENT_ID","VISIT_ID"],"A","按 PATIENT_ID+VISIT_ID 挂 HIS 住院"),
    ("SM","MED_OPERATION_MASTER","手术","手术主记录",["PATIENT_ID","VISIT_ID","OPER_ID"],"A","手麻主表;不建议用 HIS.OPERATION.OPER_ID"),
    ("SM","MED_OPERATION_NAME","手术","手术操作明细",["PATIENT_ID","VISIT_ID","OPER_ID","OPERATION_NO"],"A","一台手术多条操作"),
    ("SM","MED_ANESTHESIA_PLAN","手术/麻醉","麻醉计划",["PATIENT_ID","VISIT_ID","OPER_ID"],"A","可按 PATIENT_ID+VISIT_ID+OPER_ID 挂 SM.MED_OPERATION_MASTER"),
    ("CDA","CDA_DICTIONARY","字典","院内码↔国标码映射",[],"A","被所有 V_EMR_* 依赖;ICD-10: 字典名称='ICD-10诊断编码' 系统标识='HIS'"),
    ("PORTAL_EMPI","PATIENT_INFO","患者主数据","EMPI患者主索引",[],"B","跨系统患者主索引;关联键待确认"),
    ("YDHL","MCS_ASSESS_FORM","护理","护理评估主表",[],"B","PATIENT_UID 关联 INPATIENTS;GENERATOR_TYPE='manul' IS_VALID='1'"),
    ("YDHL","INPATIENTS","护理","住院患者表",[],"B","PAT_INDEX_NO=MCS_ASSESS_FORM.PATIENT_UID"),
    ("YDHL","MCS_DOC_FORM","护理","护理文书表单",["ID"],"A","PATIENT_UID 关联 INPATIENTS"),
    ("YDHL","MCS_ASSESS_FORM_RECORD","护理","护理评估明细",["ID"],"A","FORM_ID 关联 MCS_ASSESS_FORM.ID"),
    ("PACS","PATIENTINFO","影像","PACS 患者信息",["PatientIntraID"],"A","PACS 内部患者表；与 HIS 检查无直接同键"),
    ("PACS","EXAMINFO","影像","PACS 检查主表",["ExamID"],"A","PACS 内部检查主表；ReportID 挂 REPORT"),
    ("PACS","REPORT","影像","PACS 报告",["ReportID"],"A","PACS 内部报告表"),
    ("LIS","REQ_MASTER","检验","LIS 申请主表",["BARCODE"],"A","LIS 内部申请主表"),
    ("LIS","REQ_DETAIL","检验","LIS 申请明细",["BARCODE"],"A","按 BARCODE 挂 REQ_MASTER"),
    ("LIS","LAB_REPORT","检验","LIS 报告主表",["REPORTID"],"A","REPORTID 挂 LAB_RESULT；BARCODE 与 HIS.TEST_NO 需按时间拆分"),
]

# from(schema,table,cols) -> to(schema,table,cols) : join, cardinality, confidence, domain, note
RELS = [
    ("HIS","PAT_VISIT",["PATIENT_ID"],"HIS","PAT_MASTER_INDEX",["PATIENT_ID"],"PAT_VISIT.PATIENT_ID=PAT_MASTER_INDEX.PATIENT_ID","many-to-one","A","就诊","患者基本信息"),
    ("HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"HIS","DIAGNOSIS",["PATIENT_ID","VISIT_ID"],"PAT_VISIT.PATIENT_ID=DIAGNOSIS.PATIENT_ID AND PAT_VISIT.VISIT_ID=DIAGNOSIS.VISIT_ID","one-to-many","A","诊断",""),
    ("HIS","PAT_VISIT",["DEPT_ADMISSION_TO"],"HIS","DEPT_DICT",["DEPT_CODE"],"PAT_VISIT.DEPT_ADMISSION_TO=DEPT_DICT.DEPT_CODE","many-to-one","A","就诊","入院科室"),
    ("HIS","PAT_VISIT",["DEPT_DISCHARGE_FROM"],"HIS","DEPT_DICT",["DEPT_CODE"],"PAT_VISIT.DEPT_DISCHARGE_FROM=DEPT_DICT.DEPT_CODE","many-to-one","A","就诊","出院科室"),
    ("HIS","PAT_VISIT",["DOCTOR_IN_CHARGE"],"HIS","STAFF_DICT",["EMP_NO"],"PAT_VISIT.DOCTOR_IN_CHARGE=STAFF_DICT.EMP_NO","many-to-one","A","就诊","主管医师"),
    ("HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"HIS","PATS_IN_HOSPITAL",["PATIENT_ID","VISIT_ID"],"PATIENT_ID+VISIT_ID","one-to-one","A","就诊","病区床号兜底"),
    ("HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"HIS","INP_SETTLE_MASTER",["PATIENT_ID","VISIT_ID"],"PATIENT_ID+VISIT_ID","one-to-many","A","住院费用",""),
    ("HIS","INP_SETTLE_MASTER",["PATIENT_ID","VISIT_ID"],"HIS","INP_BILL_DETAIL",["PATIENT_ID","VISIT_ID"],"PATIENT_ID+VISIT_ID","one-to-many","A","住院费用",""),
    ("HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"HIS","ORDERS",["PATIENT_ID","VISIT_ID"],"PATIENT_ID+VISIT_ID","one-to-many","B","医嘱",""),
    ("HIS","CLINIC_MASTER",["RCPT_NO"],"HIS","OUTP_RCPT_MASTER",["RCPT_NO"],"CLINIC_MASTER->OUTP_RCPT_MASTER","one-to-many","B","门诊费用","门诊主线"),
    ("HIS","OUTP_RCPT_MASTER",["RCPT_NO"],"HIS","OUTP_BILL_ITEMS",["RCPT_NO"],"OUTP_RCPT_MASTER.RCPT_NO=OUTP_BILL_ITEMS.RCPT_NO","one-to-many","B","门诊费用",""),
    ("HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"SM","MED_OPERATION_MASTER",["PATIENT_ID","VISIT_ID"],"PATIENT_ID+VISIT_ID","one-to-many","A","手术","手麻主表"),
    ("SM","MED_OPERATION_MASTER",["PATIENT_ID","VISIT_ID","OPER_ID"],"SM","MED_OPERATION_NAME",["PATIENT_ID","VISIT_ID","OPER_ID"],"PATIENT_ID+VISIT_ID+OPER_ID","one-to-many","A","手术","一台手术多条操作"),
    ("HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"HIS","EXAM_MASTER",["PATIENT_ID","VISIT_ID"],"PATIENT_ID+VISIT_ID","one-to-many","A","检查",""),
    ("HIS","EXAM_MASTER",["EXAM_NO"],"HIS","EXAM_REPORT",["EXAM_NO"],"EXAM_MASTER.EXAM_NO=EXAM_REPORT.EXAM_NO","one-to-one","A","检查","报告无PATIENT_ID"),
    ("HIS","PAT_VISIT",["PATIENT_ID"],"HIS","LAB_TEST_MASTER",["PATIENT_ID","TEST_NO"],"PAT_VISIT.PATIENT_ID=LAB_TEST_MASTER.PATIENT_ID AND (VISIT_ID 相同 OR 0/NULL 按门诊)","one-to-many","A","检验","住院+同患者门诊检验"),
    ("HIS","LAB_TEST_MASTER",["TEST_NO"],"HIS","LAB_TEST_ITEMS",["TEST_NO"],"TEST_NO","one-to-many","A","检验",""),
    ("HIS","LAB_TEST_ITEMS",["TEST_NO","ITEM_NO"],"HIS","LAB_RESULT",["TEST_NO","ITEM_NO"],"TEST_NO+ITEM_NO","one-to-many","A","检验",""),
    ("HIS","LAB_TEST_MASTER",["TEST_NO"],"HIS","LAB_RESULT",["TEST_NO"],"TEST_NO","one-to-many","A","检验",""),
    ("HIS","DIAGNOSIS",["DIAGNOSIS_CODE"],"CDA","CDA_DICTIONARY",["院标编码"],"CDA_DICTIONARY.字典名称='ICD-10诊断编码' AND 系统标识='HIS' AND 院标编码=DIAGNOSIS.DIAGNOSIS_CODE","many-to-one","A","诊断","ICD-10 标准化;关联前按院标编码聚合防爆行"),
    ("HIS","DIAGNOSIS",["DIAGNOSIS_TYPE"],"HIS","DIAGNOSIS_TYPE_DICT",["DIAGNOSIS_TYPE_CODE"],"DIAGNOSIS.DIAGNOSIS_TYPE=DIAGNOSIS_TYPE_DICT.DIAGNOSIS_TYPE_CODE","many-to-one","A","诊断",""),
    ("HIS","PAT_MASTER_INDEX",["INP_NO"],"MTL","EPR_INPATIENT_DOCINDEX",["P_INPATIENT_NO","P_INPATIENT_TIMES"],"PAT_MASTER_INDEX.INP_NO=EPR_INPATIENT_DOCINDEX.P_INPATIENT_NO AND PAT_VISIT.VISIT_ID=P_INPATIENT_TIMES","one-to-many","A","电子病历(旧)",""),
    ("MTL","EPR_INPATIENT_DOCINDEX",["UHID"],"MTL","EPR_INPATIENT",["UHID"],"UHID","one-to-many","A","电子病历(旧)",""),
    ("MTL","EPR_INPATIENT",["UHID","ID"],"MTL","EMRSD_CONTENT",["UHID","段落编号"],"UHID AND EPR_INPATIENT.ID=EMRSD_CONTENT.段落编号","one-to-many","A","电子病历(旧)",""),
    ("JHEMR","JHMR_FILE_INDEX",["FILE_UNIQUE_ID"],"JHEMR","JHMR_FILE_CONTENT_TEXT",["FILE_UNIQUE_ID"],"FILE_UNIQUE_ID","one-to-one","A","电子病历(新)",""),
    ("JHEMR","JHMR_FILE_INDEX",["DEPT_CODE"],"HIS","DEPT_DICT",["DEPT_CODE"],"DEPT_CODE","many-to-one","B","电子病历(新)",""),
    ("HIS","PAT_VISIT",["DOCTOR_IN_CHARGE"],"HIS","DOC_REGISTER_EMP_MATCH",["EMP_NO"],"EMP_NO","many-to-one","A","就诊","医师执业证书号"),
    ("YDHL","MCS_ASSESS_FORM",["PATIENT_UID"],"YDHL","INPATIENTS",["PAT_INDEX_NO"],"MCS_ASSESS_FORM.PATIENT_UID=INPATIENTS.PAT_INDEX_NO","many-to-one","A","护理",""),
    ("MTL","EPR_INPATIENT_DOCINDEX",["P_CLINIC_ID","P_INPATIENT_TIMES"],"HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"EPR_INPATIENT_DOCINDEX.P_CLINIC_ID=PAT_VISIT.PATIENT_ID AND TO_CHAR(P_INPATIENT_TIMES)=TO_CHAR(VISIT_ID)","many-to-one","A","电子病历(旧)","候选关系验证后提升"),
    ("MTL","EMRSD_CONTENT",["UHID"],"MTL","EPR_INPATIENT_DOCINDEX",["UHID"],"UHID","many-to-one","A","电子病历(旧)","段落内容可直接追溯文书索引"),
    ("SM","MED_ANESTHESIA_PLAN",["PATIENT_ID","VISIT_ID","OPER_ID"],"SM","MED_OPERATION_MASTER",["PATIENT_ID","VISIT_ID","OPER_ID"],"PATIENT_ID+VISIT_ID+OPER_ID","many-to-one","A","手术/麻醉","麻醉计划挂手术主记录"),
    ("MTL","EPR_INPATIENT_DOCINDEX",["P_DEPT_CODE"],"HIS","DEPT_DICT",["DEPT_CODE"],"EPR_INPATIENT_DOCINDEX.P_DEPT_CODE=DEPT_DICT.DEPT_CODE","many-to-one","A","电子病历(旧)","旧 EMR 文书科室"),
    ("HIS","OPERATION",["PATIENT_ID","VISIT_ID"],"HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"PATIENT_ID+VISIT_ID","many-to-one","A","手术","HIS 侧手术可挂住院，但不可与 SM 手术一一对应"),
    ("HIS","CLINIC_MASTER",["VISIT_DEPT"],"HIS","DEPT_DICT",["DEPT_CODE"],"CLINIC_MASTER.VISIT_DEPT=DEPT_DICT.DEPT_CODE","many-to-one","A","门诊","门诊就诊科室"),
    ("SM","MED_OPERATION_MASTER",["PATIENT_ID"],"HIS","PAT_MASTER_INDEX",["PATIENT_ID"],"MED_OPERATION_MASTER.PATIENT_ID=PAT_MASTER_INDEX.PATIENT_ID","many-to-one","A","手术","手麻患者主索引"),
    ("JHEMR","JHMR_FILE_INDEX",["PATIENT_ID","VISIT_ID"],"HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"JHMR_FILE_INDEX.PATIENT_ID=PAT_VISIT.PATIENT_ID AND TO_CHAR(JHMR_FILE_INDEX.VISIT_ID)=TO_CHAR(PAT_VISIT.VISIT_ID)","many-to-one","A","电子病历(新)","新 EMR 文书索引挂 HIS 住院"),
    ("JHEMR","JHMR_FILE_CONTENT_DG",["PATIENT_ID","VISIT_ID"],"HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"JHMR_FILE_CONTENT_DG.PATIENT_ID=PAT_VISIT.PATIENT_ID AND TO_CHAR(JHMR_FILE_CONTENT_DG.VISIT_ID)=TO_CHAR(PAT_VISIT.VISIT_ID)","many-to-one","A","电子病历(新)","新 EMR 文书打散内容挂 HIS 住院"),
    ("JHEMR","PAT_DIAGNOSIS",["PATIENT_ID","VISIT_ID"],"HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"PAT_DIAGNOSIS.PATIENT_ID=PAT_VISIT.PATIENT_ID AND TO_CHAR(PAT_DIAGNOSIS.VISIT_ID)=TO_CHAR(PAT_VISIT.VISIT_ID)","many-to-one","A","电子病历(新)","新 EMR 诊断挂 HIS 住院"),
    ("JHEMR","FIRST_PAGE_COSTS",["PATIENT_ID","VISIT_ID"],"HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"FIRST_PAGE_COSTS.PATIENT_ID=PAT_VISIT.PATIENT_ID AND TO_CHAR(FIRST_PAGE_COSTS.VISIT_ID)=TO_CHAR(PAT_VISIT.VISIT_ID)","many-to-one","A","电子病历(新)","病案首页费用挂 HIS 住院"),
    ("PACS","EXAMINFO",["PatientIntraID"],"PACS","PATIENTINFO",["PatientIntraID"],"EXAMINFO.PatientIntraID=PATIENTINFO.PatientIntraID","many-to-one","A","影像","PACS 内部患者-检查关系；注意 Oracle 大小写引号列"),
    ("PACS","EXAMINFO",["ReportID"],"PACS","REPORT",["ReportID"],"EXAMINFO.ReportID=REPORT.ReportID","many-to-one","A","影像","PACS 内部检查-报告关系，少量缺报告孤儿"),
    ("LIS","REQ_DETAIL",["BARCODE"],"LIS","REQ_MASTER",["BARCODE"],"REQ_DETAIL.BARCODE=REQ_MASTER.BARCODE","many-to-one","A","检验","LIS 内部申请明细挂申请主表"),
    ("LIS","REQ_MASTER",["REPORT_ID"],"LIS","LAB_REPORT",["REPORTID"],"REQ_MASTER.REPORT_ID=LAB_REPORT.REPORTID","many-to-one","A","检验","LIS 申请主表挂报告主表"),
    ("YDHL","INPATIENTS",["MRN","SERIES"],"HIS","PAT_VISIT",["PATIENT_ID","VISIT_ID"],"INPATIENTS.MRN=PAT_MASTER_INDEX.INP_NO AND INPATIENTS.SERIES=PAT_VISIT.VISIT_ID","many-to-one","A","护理","经 HIS.PAT_MASTER_INDEX.INP_NO 桥接 HIS 住院；不要用 YDHL.PATIENT_ID"),
    ("YDHL","MCS_ASSESS_FORM",["PATIENT_UID"],"YDHL","INPATIENTS",["PAT_INDEX_NO"],"MCS_ASSESS_FORM.PATIENT_UID=INPATIENTS.PAT_INDEX_NO","many-to-one","A","护理","护理评估主表挂移动护理住院患者"),
    ("YDHL","MCS_DOC_FORM",["PATIENT_UID"],"YDHL","INPATIENTS",["PAT_INDEX_NO"],"MCS_DOC_FORM.PATIENT_UID=INPATIENTS.PAT_INDEX_NO","many-to-one","A","护理","护理文书主表挂移动护理住院患者"),
    ("YDHL","MCS_ASSESS_FORM_RECORD",["FORM_ID"],"YDHL","MCS_ASSESS_FORM",["ID"],"MCS_ASSESS_FORM_RECORD.FORM_ID=MCS_ASSESS_FORM.ID","many-to-one","A","护理","护理评估明细挂评估主表"),
]

# ============ 校验 ============
print("="*70)
print("校验报告: 已确认库表 vs 活元数据(08)")
print("="*70)
missing_tables = []
for schema, table, domain, grain, pk, conf, note in TABLES:
    t = get_table(schema, table)
    if not t:
        missing_tables.append(f"{schema}.{table}")
        print(f"  [缺失] {schema}.{table:28s} <- 不在 8.216 活元数据中(外部系统?)")
    else:
        nrows = t["num_rows_stats"]
        missing_cols = [c for c in pk if not col_exists(schema, table, c)]
        flag = "" if not missing_cols else f"  [PK字段缺失:{','.join(missing_cols)}]"
        print(f"  [存在] {schema}.{table:28s} 行数(统计)={nrows:>12} 列数={len(t['columns']):>3}{flag}")
print(f"\n校验: {len(TABLES)}张已确认表, 其中 {len(TABLES)-len(missing_tables)} 在8.216中, {len(missing_tables)} 不在({','.join(missing_tables) if missing_tables else '无'})")

# ============ 输出 tables.csv (全量865表 + 已确认表追加 domain/grain/pk) ============
curated = {(s,t):(d,g,pk,conf,n) for s,t,d,g,pk,conf,n in TABLES}
with open(os.path.join(OUT,"tables.csv"),"w",encoding="utf-8-sig",newline="") as f:
    w=csv.writer(f); w.writerow(["schema","table","comment","row_count_stats","column_count","domain","grain","pk","confidence","note","source"])
    for s,sd in schemas.items():
        for t,td in sd["tables"].items():
            cu = curated.get((s,t))
            w.writerow([s,t,td["comment"],td["num_rows_stats"],len(td["columns"]),
                        cu[0] if cu else "", cu[1] if cu else "", "|".join(cu[2]) if cu else "",
                        cu[3] if cu else "", cu[4] if cu else "", "curated" if cu else "metadata"])

# ============ 输出 columns.csv (全量字段数据字典) ============
with open(os.path.join(OUT,"columns.csv"),"w",encoding="utf-8-sig",newline="") as f:
    w=csv.writer(f); w.writerow(["schema","table","column_id","column","data_type","length","nullable","comment"])
    for s,sd in schemas.items():
        for t,td in sd["tables"].items():
            for i,c in enumerate(td["columns"],1):
                w.writerow([s,t,i,c["name"],c["type"],c["length"],"Y" if c["nullable"] else "N",c["comment"]])

# ============ 数据库实测验证摘要（来自 10_关系验证报告.md） ============
# 说明：validation_level 是用于资产系统导入的实测等级；confidence 仍保留原“已确认文档”置信度。
VALIDATION = {
    1:  ("A+", "verified", "total=575487; orphan=3; orphan_rate=0.0005%", "数据库全量验证：患者主索引关系成立"),
    2:  ("A+", "verified", "total=3330051; orphan=210; orphan_rate=0.0063%", "数据库全量验证：诊断挂住院关系成立"),
    3:  ("A+", "verified", "total=575487; orphan=1", "数据库全量验证：入院科室关系成立"),
    4:  ("A+", "verified", "total=575487; orphan=0", "数据库全量验证：出院科室关系成立"),
    5:  ("A",  "verified", "total=575487; orphan=3193; orphan_rate=0.55%", "主管医师可关联 STAFF_DICT，存在少量历史/离职/编码孤儿"),
    6:  ("A+", "verified", "total=1216; orphan=3", "床位兜底关系成立"),
    7:  ("A+", "verified", "total=622182; orphan=52; orphan_rate=0.0084%", "住院结算关系成立"),
    8:  ("B",  "bounded",  "detail_rows=768942; matched_visit_keys=1996/2000", "INP_BILL_DETAIL 巨表；用 2000 个住院键限定验证，键关系可用，禁止全表扫描"),
    9:  ("B",  "bounded",  "order_rows=130734; matched_visit_keys=1999/2000", "ORDERS 巨表；用 2000 个住院键限定验证，键关系可用"),
    10: ("not_tested", "not_tested", "", "门诊主线未在本轮验证，需单独按门诊键复核"),
    11: ("not_tested", "not_tested", "", "门诊费用明细未在本轮验证，需单独按 RCPT_NO 复核"),
    12: ("A",  "verified", "total=138551; orphan=406; orphan_rate=0.29%", "手麻主记录可挂住院，少量历史孤儿"),
    13: ("A",  "verified", "total=144894; orphan=96; orphan_rate=0.066%", "手术主从关系成立"),
    14: ("C",  "needs_split", "total=3415127; orphan=1402517; orphan_rate=41.1%", "EXAM_MASTER 混合住院/门诊/体检/历史来源；仅住院子集可按 PATIENT_ID+VISIT_ID 挂 PAT_VISIT"),
    15: ("A+", "verified", "total=1336893; orphan=55; EXAM_REPORT.PATIENT_ID column=0", "检查报告必须经 EXAM_NO 关联 EXAM_MASTER"),
    16: ("C",  "needs_split", "total=9142446; visit_null_or_zero=3339952; exact_visit_match=5800092; nonzero_visit_unmatched=2402", "LAB_TEST_MASTER 需拆住院检验与 VISIT_ID=0/NULL 的门诊/其他检验"),
    17: ("A",  "verified", "total=9610054; orphan=1710; orphan_rate=0.018%", "LAB_TEST_ITEMS 按 TEST_NO 挂 LAB_TEST_MASTER 成立"),
    18: ("B",  "bounded",  "result_rows=22721; matched_test_no=1367/2000", "LAB_RESULT 巨表；用 2000 个 TEST_NO 限定验证，TEST_NO 关系可用，禁止全表扫描"),
    19: ("B",  "bounded",  "result_rows=22721; matched_test_no=1367/2000", "LAB_RESULT 巨表；用 2000 个 TEST_NO 限定验证，TEST_NO 关系可用，禁止全表扫描"),
    20: ("A",  "sample_verified", "sample_rows=50000; mapped_rows=47091; map_rate=94.18%", "ICD-10 映射可用，但需保留未命中回退 HIS 原始编码/名称"),
    21: ("not_tested", "not_tested", "", "DIAGNOSIS_TYPE_DICT 未在本轮单独验证，可按字典小表后续补验"),
    22: ("A",  "verified", "total=239863; orphan=817; orphan_rate=0.34%", "旧 EMR 文书索引可通过住院号挂患者"),
    23: ("A+", "sample_verified", "sample_rows=50000; orphan=0", "旧 EMR 文书主表按 UHID 可挂 DOCINDEX"),
    24: ("A",  "sample_verified", "sample_rows=50000; orphan=29; orphan_rate=0.058%", "旧 EMR 段落内容按 UHID+段落编号可挂文书主表"),
    25: ("A",  "verified", "total=1149248; orphan=1051; orphan_rate=0.092%", "新 EMR 内部文书索引与正文关系成立"),
    26: ("not_tested", "not_tested", "", "JHEMR 文书按 DEPT_CODE 关联科室未在本轮验证；JHEMR 到住院键仍未确认"),
    27: ("external", "missing_in_8216", "", "HIS.DOC_REGISTER_EMP_MATCH 在 8.216 缺失，仅 HIS 生产库，待接入生产库验证"),
    28: ("B",  "sample_verified", "sample_rows=200000; orphan=0", "移动护理评估按 PATIENT_UID=PAT_INDEX_NO 抽样成立"),
    29: ("A",  "verified", "total=239863; orphan=2876; orphan_rate=1.20%", "旧 EMR 文书索引可按 P_CLINIC_ID+P_INPATIENT_TIMES 直连住院，少量历史孤儿"),
    30: ("A+", "sample_verified", "sample_rows=100000; orphan=1", "旧 EMR 段落内容可按 UHID 直接追溯文书索引"),
    31: ("A",  "verified", "total=132818; orphan=1052; orphan_rate=0.79%", "麻醉计划可按 PATIENT_ID+VISIT_ID+OPER_ID 挂手术主记录"),
    32: ("A+", "verified", "total=239863; orphan=0", "旧 EMR 文书科室可直接挂 HIS 科室字典"),
    33: ("A+", "verified", "total=528729; orphan=16", "HIS 侧手术可按 PATIENT_ID+VISIT_ID 挂住院；但不可与 SM 手术一一对应"),
    34: ("A+", "verified", "total=5704241; orphan=0", "门诊就诊科室强关系"),
    35: ("A",  "verified", "total=138551; orphan=267; orphan_rate=0.19%", "手麻手术主记录可挂 HIS 患者主索引"),
    36: ("A+", "verified", "total=1140268; matched=1139718; orphan=550; orphan_rate=0.048%", "新 EMR 文书索引按 PATIENT_ID+VISIT_ID 可挂 HIS 住院"),
    37: ("A+", "verified", "total=2902663; matched=2900782; orphan=1881; orphan_rate=0.065%", "新 EMR 文书打散内容按 PATIENT_ID+VISIT_ID 可挂 HIS 住院"),
    38: ("A+", "verified", "total=787965; matched=787694; orphan=271; orphan_rate=0.034%", "新 EMR 诊断按 PATIENT_ID+VISIT_ID 可挂 HIS 住院"),
    39: ("A+", "verified", "total=103318; matched=103287; orphan=31; orphan_rate=0.030%", "病案首页费用按 PATIENT_ID+VISIT_ID 可挂 HIS 住院"),
    40: ("A+", "verified", "total=1219575; matched=1219575; orphan=0", "PACS 内部患者-检查关系成立"),
    41: ("B",  "verified", "total=1219575; matched=1149006; orphan=70569; orphan_rate=5.79%", "PACS 内部检查-报告关系可用，但存在较多无报告/历史孤儿"),
    42: ("A+", "verified", "total=3085565; matched=3085562; orphan=3", "LIS 申请明细按 BARCODE 挂申请主表成立"),
    43: ("A+", "verified", "total=2784257; key_nonnull=2113642; matched=2113467; orphan=175", "LIS 申请主表按 REPORT_ID 挂报告主表成立；未出报告记录 REPORT_ID 为空"),
    44: ("A",  "verified", "total=276199; matched=274279; orphan=1920; orphan_rate=0.70%", "移动护理住院患者通过 MRN=HIS.INP_NO + SERIES=VISIT_ID 挂 HIS 住院；YDHL.PATIENT_ID 不是 HIS.PATIENT_ID"),
    45: ("A+", "verified", "total=2550149; matched=2550139; orphan=10", "移动护理评估主表按 PATIENT_UID 挂 INPATIENTS 成立"),
    46: ("A+", "verified", "total=11987629; matched=11987601; orphan=28", "移动护理文书主表按 PATIENT_UID 挂 INPATIENTS 成立"),
    47: ("A+", "verified", "total=41832099; matched=41832099; orphan=0", "移动护理评估明细按 FORM_ID 挂评估主表成立"),
}

# ============ 输出 relationships.csv (已确认关联 + 数据库实测验证) ============
with open(os.path.join(OUT,"relationships.csv"),"w",encoding="utf-8-sig",newline="") as f:
    w=csv.writer(f); w.writerow(["id","domain","from_table","from_columns","to_table","to_columns","join_condition","cardinality","confidence","validation_level","validation_status","validation_metrics","note","validation_note"])
    for i,(fs,ft,fc,ts,tt,tc,join,card,conf,dom,note) in enumerate(RELS,1):
        vlevel, vstatus, vmetrics, vnote = VALIDATION.get(i, ("not_tested", "not_tested", "", "未在本轮验证"))
        w.writerow([i,dom,f"{fs}.{ft}","|".join(fc),f"{ts}.{tt}","|".join(tc),join,card,conf,vlevel,vstatus,vmetrics,note,vnote])

# ============ 输出 catalog.json (组合, 便于程序读取) ============
catalog = {
  "meta": {"source_meta":"08_数据中心元数据快照.json","relation_validation":"10_关系验证报告.md / 10_关系验证结果.json","generated_by":"tools/build_asset_package.py",
           "note":"tables/columns 来自活元数据(全量);relationships 为已确认关系，并追加数据库实测验证等级"},
  "tables":[ {"schema":s,"table":t,"comment":get_table(s,t)["comment"] if get_table(s,t) else "",
              "row_count_stats": (get_table(s,t) or {}).get("num_rows_stats",-1),
              **{"domain":d,"grain":g,"pk":pk,"confidence":conf,"note":n}}
             for s,t,d,g,pk,conf,n in TABLES],
  "relationships":[{"id":i,"domain":dom,"from":f"{fs}.{ft}","from_columns":fc,"to":f"{ts}.{tt}",
                    "to_columns":tc,"join":join,"cardinality":card,"confidence":conf,
                    "validation_level":VALIDATION.get(i, ("not_tested","not_tested","","未在本轮验证"))[0],
                    "validation_status":VALIDATION.get(i, ("not_tested","not_tested","","未在本轮验证"))[1],
                    "validation_metrics":VALIDATION.get(i, ("not_tested","not_tested","","未在本轮验证"))[2],
                    "note":note,
                    "validation_note":VALIDATION.get(i, ("not_tested","not_tested","","未在本轮验证"))[3]}
                   for i,(fs,ft,fc,ts,tt,tc,join,card,conf,dom,note) in enumerate(RELS,1)],
}
json.dump(catalog, open(os.path.join(OUT,"catalog.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"\n生成完成 -> {OUT}")
print("  tables.csv       (全量表清单 + 已确认 domain/grain/pk)")
print("  columns.csv      (全量字段数据字典)")
print("  relationships.csv(已确认关联关系)")
print("  catalog.json     (已确认表+关系, 结构化)")
