CREATE VIEW [dbo].[v_EMR_INSPECTION] AS
SELECT
    /* 1. 内码 */
    '49557032X' + '_' +
        ISNULL(CONVERT(varchar(50), a.reportid), '') + '_' +
        ISNULL(CONVERT(varchar(64), c.req_itemcode), '') + '_' +
        ISNULL(CONVERT(varchar(20), c.seq), '') AS ID,

    '49557032X' AS ORG_CODE,
    '山东省第二人民医院' AS ORG_NAME,

    cls_name.CLASS_CODE AS LONIC_CLASS_CODE,
    cls_name.CLASS_NAME AS LOINC_CLASS_NAME,
    CONVERT(varchar(64), d.rptunitid) AS LOCAL_CLASS_CODE,
    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(d.ResultClass)), ''), cls_name.CLASS_NAME), 128) AS LOCAL_CLASS_NAME,
    LEFT(cls_name.CLASS_NAME, 100) AS INSPECTION_TYPE,

    CAST(NULL AS varchar(10)) AS REPORT_ERROR_TYPE,
    CAST(NULL AS varchar(500)) AS REPORT_ERROR_REASON,

    LEFT(ISNULL(a.pat_name, ''), 50) AS NAME,

    /* 无明确其他证件时不重复填身份证 */
    CAST(NULL AS varchar(2)) AS OTHER_ID_TYPE,
    CAST(NULL AS varchar(18)) AS OTHER_ID_NUM,
    LEFT(NULLIF(NULLIF(LTRIM(RTRIM(a.pat_idcardno)), ''), '""'), 18) AS ID_NUM,

    /* D18 -- 病人类别 1＝门诊、2＝急诊，3＝住院，4＝体检；其他用户定义，来源于系统代码Kind=PT */
    CASE a.PAT_TYPECODE
        WHEN '1' THEN '10'
        WHEN '2' THEN '20'
        WHEN '3' THEN '50'
        WHEN '4' THEN '40'
        ELSE '10'
    END AS PATIENT_TYPE_CODE,

    CASE a.PAT_TYPECODE
        WHEN '1' THEN '门诊'
        WHEN '2' THEN '急诊'
        WHEN '3' THEN '住院'
        WHEN '4' THEN '体检'
        ELSE '门诊'
    END AS PATIENT_TYPE_NAME,

    CASE
        WHEN a.PAT_SEX IN ('1','2','9') THEN a.PAT_SEX
        WHEN a.PAT_SEX IS NULL OR LTRIM(RTRIM(a.PAT_SEX)) = '' THEN '0'
        ELSE '9'
    END AS SEX_CODE,

    CASE a.PAT_SEX
        WHEN '1' THEN '男'
        WHEN '2' THEN '女'
        WHEN '9' THEN '不明'
        ELSE '未知'
    END AS SEX_NAME,

    LEFT(ISNULL(a.pat_phone, ''), 50) AS TELEPHONE,

    CASE
        WHEN TRY_CONVERT(int, a.pat_ageyear) BETWEEN 0 AND 200 THEN TRY_CONVERT(int, a.pat_ageyear)
        ELSE NULL
    END AS AGE,
    CAST(NULL AS int) AS AGE_MONTH,
    CAST(NULL AS int) AS AGE_DAY,
    CAST(NULL AS int) AS AGE_HOUR,
LEFT(
    COALESCE(
        CASE
            WHEN a.PAT_TYPECODE IN ('1','2') THEN
                COALESCE(
                    NULLIF(LTRIM(RTRIM(a.custom1)), ''),
                    NULLIF(LTRIM(RTRIM(a.pat_no)), '')
                )
                WHEN a.PAT_TYPECODE = '3'
                 AND NULLIF(LTRIM(RTRIM(a.pat_id)), '') IS NOT NULL
                 AND NULLIF(LTRIM(RTRIM(a.inp_id)), '') IS NOT NULL THEN
                a.pat_id + '|' + a.inp_id
            WHEN a.PAT_TYPECODE = '3'
                 AND NULLIF(LTRIM(RTRIM(a.pat_id)), '') IS NOT NULL
                 AND NULLIF(LTRIM(RTRIM(a.custom1)), '') IS NOT NULL THEN
                a.pat_id + '|' + RIGHT(a.custom1, 1)

            WHEN a.PAT_TYPECODE = '4' THEN
                COALESCE(
                    NULLIF(LTRIM(RTRIM(a.custom1)), ''),
                    NULLIF(LTRIM(RTRIM(a.pat_no)), '')
                )
            ELSE NULLIF(LTRIM(RTRIM(a.pat_no)), '')
        END,
        NULLIF(LTRIM(RTRIM(a.pat_no)), ''),
        NULLIF(LTRIM(RTRIM(a.custom1)), ''),
        NULLIF(LTRIM(RTRIM(a.barcode)), ''),
        REPLACE(CONVERT(varchar(50), a.reportid), '-', '')
    ),
    32
) AS VISITING_NUM,

LEFT(
    COALESCE(
        NULLIF(LTRIM(RTRIM(c.his_refcol2)), ''),
        NULLIF(LTRIM(RTRIM(c.his_recordid)), ''),
        NULLIF(LTRIM(RTRIM(a.barcode)), ''),
        CONVERT(varchar(50), a.reportid)
    ),
    50
) AS ORDER_ID,
    LEFT(ISNULL(a.REQ_BEDNO, ''), 20) AS SICKBED_NUM,

    /* charge_typeno 样例多为“自费/居民医保/职工医保”，不应放代码字段 */
    CAST(NULL AS varchar(2)) AS CHARGE_TYPE_CODE,
    LEFT(ISNULL(a.charge_typeno, ''), 50) AS CHARGE_TYPE_NAME,

    LEFT(ISNULL(a.SampleNo, ''), 20) AS SAMPLE_NUM,
  ISNULL(smp.SAMPLE_TYPE_CODE, '99') AS SAMPLE_TYPE_CODE,
LEFT(ISNULL(NULLIF(smp.SAMPLE_TYPE_NAME, ''), '其他，请详述'), 50) AS SAMPLE_TYPE_NAME,

    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(c.his_recordid)), ''), a.barcode), 20) AS APPLY_NUM,

    '49557032X' AS APPLY_HOSP_CODE,
    '山东省第二人民医院' AS APPLY_HOSP_NAME,

ISNULL(cs.APPLY_DEPT_CODE, 'A69') AS APPLY_DEPT_CODE,
       LEFT(ISNULL(NULLIF(LTRIM(RTRIM(dept.deptname)), ''), '待人工确认'), 60) AS APPLY_DEPT_NAME,

    TRY_CONVERT(datetime, a.req_dt) AS APPLY_DATE,

    /* 标准说明为医生身份证号，但源表多数是工号；优先身份证，缺失时保留工号 */
    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(doc.idcardno)), ''), a.REQ_DOCNO), 32) AS APPLY_DOCTOR_CODE,
    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(doc.DoctorName)), ''), '体检'), 50) AS APPLY_DOCTOR_NAME,

    LEFT(ISNULL(a.pat_diag_icd, ''), 20) AS DISEASE_CODE,
    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(a.pat_diag)), ''), '健康查体'), 200) AS DISEASE_NAME,

    COALESCE(
        TRY_CONVERT(datetime, a.test_dt),
        TRY_CONVERT(datetime, a.SampleDate),
        TRY_CONVERT(datetime, a.report_dt)
    ) AS INSPECT_DATE,

    COALESCE(
        TRY_CONVERT(datetime, a.sampled_dt),
        TRY_CONVERT(datetime, b.sampled_dt)
    ) AS SAMPLE_TAKE_DATE,

    COALESCE(
        TRY_CONVERT(datetime, a.Recieve_dt),
        TRY_CONVERT(datetime, b.recieve_dt),
        TRY_CONVERT(datetime, a.report_dt)
    ) AS SAMPLE_RECEIVE_DATE,

    LEFT(ISNULL(lr.testmethod, ''), 500) AS EXAM_METHOD,
    LEFT(ISNULL(c.req_itemcode, ''), 20) AS EXAM_CODE,
    LEFT(ISNULL(c.req_itemname, ''), 36) AS EXAM_CODE_NAME,

    CAST(NULL AS varchar(100)) AS SPECIMEN_STATE,
    CAST(NULL AS varchar(32)) AS SPECIMEN_PLACE_CODE,
    CAST(NULL AS varchar(100)) AS SPECIMEN_PLACE_NAME,
    CAST(NULL AS varchar(32)) AS SPECIMEN_RISK_CODE,
    CAST(NULL AS varchar(100)) AS SPECIMEN_RISK_NAME,
    CAST(NULL AS varchar(32)) AS SPECIMEN_QUANTITY_CODE,
    CAST(NULL AS varchar(100)) AS SPECIMEN_QUANTITY_NAME,

    reject_map.SPECIMEN_REJECT_CODE AS SPECIMEN_REJECT_CODE,
    reject_map.SPECIMEN_REJECT_NAME AS SPECIMEN_REJECT_NAME,

    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(a.input_user)), ''), NULLIF(LTRIM(RTRIM(a.report_user)), '')), 32) AS EXAM_ENGINEER_CODE,
    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(input_user.username)), ''), NULLIF(LTRIM(RTRIM(report_user.username)), '')), 50) AS EXAM_ENGINEER_NAME,

    CASE
        WHEN a.report_user = 'admin' THEN '00942'
        ELSE LEFT(ISNULL(NULLIF(LTRIM(RTRIM(a.report_user)), ''), NULLIF(LTRIM(RTRIM(a.input_user)), '')), 32)
    END AS EXAM_DOCTOR_CODE,

    LEFT(
        CASE
            WHEN a.report_user = 'admin' THEN '尹慧'
            ELSE ISNULL(NULLIF(LTRIM(RTRIM(report_user.username)), ''), ISNULL(NULLIF(LTRIM(RTRIM(input_user.username)), ''), '尹慧'))
        END,
        50
    ) AS EXAM_DOCTOR_NAME,

    /* reportid 原值可能超过20，去横杠后多数可控制在20位内；仍建议跑下方唯一性核查 */
    LEFT(REPLACE(CONVERT(varchar(50), a.reportid), '-', ''), 20) AS REPORT_NUM,

    'A30' AS EXAM_DEPT_CODE,
    '医学检验科' AS EXAM_DEPT_NAME,
    '49557032X' AS EXAM_HOSPITAL_CODE,
    '山东省第二人民医院' AS EXAM_HOSPITAL_NAME,

    COALESCE(
        TRY_CONVERT(datetime, a.report_dt),
        TRY_CONVERT(datetime, a.rechk_dt)
    ) AS REPORT_DATE,

    CASE
        WHEN a.report_user = 'admin' THEN '00942'
        ELSE LEFT(ISNULL(NULLIF(LTRIM(RTRIM(a.report_user)), ''), NULLIF(LTRIM(RTRIM(a.input_user)), '')), 32)
    END AS REPORT_DOCTOR_CODE,

    LEFT(
        CASE
            WHEN a.report_user = 'admin' THEN '尹慧'
            ELSE ISNULL(NULLIF(LTRIM(RTRIM(report_user.username)), ''), ISNULL(NULLIF(LTRIM(RTRIM(input_user.username)), ''), '尹慧'))
        END,
        50
    ) AS REPORT_DOCTOR_NAME,

    COALESCE(
        TRY_CONVERT(datetime, a.rechk_dt),
        TRY_CONVERT(datetime, a.report_dt)
    ) AS AUDIT_DATE,

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(a.rechk_user)), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(a.report_user)), ''), '00942')
        ),
        32
    ) AS AUDIT_DOCTOR_CODE,

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(rechk_user.username)), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(report_user.username)), ''), '尹慧')
        ),
        50
    ) AS AUDIT_DOCTOR_NAME,

    CAST(NULL AS varchar(64)) AS IMAGE_DEVICE,
    LEFT(ISNULL(a.report_comm, ''), 200) AS REMARK,
    LEFT(ISNULL(a.pat_diag_icd, ''), 20) AS DIAGNOSIS_TREAT_NO,

    CAST(NULL AS char(1)) AS CARD_TYPE,
    CAST(NULL AS varchar(32)) AS CITIZEN_ID,
    CAST(NULL AS varchar(32)) AS STATUS,

    COALESCE(
        TRY_CONVERT(datetime, a.Report_DT),
        TRY_CONVERT(datetime, a.report_dt),
        TRY_CONVERT(datetime, a.rechk_dt)
    ) AS EFFECTIVE_TIME,

    CAST(NULL AS datetime) AS CREATED_AT,

    '370104' AS DISTRICT_CODE,
    'INSERT' AS EXCHANGE_TYPE,
    CAST(NULL AS varchar(50)) AS DEI,
    CAST(NULL AS varchar(50)) AS NODE_CODE,
    GETDATE() AS SYSTEM_TIME,

    /* 标本来源：1门诊，2急诊，3住院，4体检 */
    CASE a.pat_typecode
        WHEN '1' THEN '1'
        WHEN '2' THEN '2'
        WHEN '3' THEN '3'
        WHEN '4' THEN '4'
        ELSE '1'
    END AS SOURCE_CODE,

    CAST(NULL AS varchar(36)) AS CZRK_ID,

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(input_user.idcardno)), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(report_user.idcardno)), ''), NULLIF(LTRIM(RTRIM(doc.idcardno)), ''))
        ),
        18
    ) AS DOCTOR_ID_NUM,

    LEFT(NULLIF(LTRIM(RTRIM(rechk_user.idcardno)), ''), 18) AS REVIEWERS_ID_NUM,

    TRY_CONVERT(date, a.LastPrint_DT) AS PRINT_TIME,
    CAST(NULL AS varchar(50)) AS PRINT_PERSON,

    LEFT(ISNULL(a.req_reason, ''), 100) AS LAB_PURPOSE,

    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(b.sampled_user)), ''), NULLIF(LTRIM(RTRIM(a.sampled_user)), '')), 50) AS COLLECT_PERSON,
    LEFT(ISNULL(b.recieve_user, ''), 50) AS ACCEPT_PERSON

FROM lab_report a WITH (NOLOCK)
INNER JOIN req_master b WITH (NOLOCK)
    ON a.barcode = b.barcode
INNER JOIN req_detail c WITH (NOLOCK)
    ON c.barcode = a.barcode
   AND (
          c.reportid = a.reportid
          OR (
                NULLIF(LTRIM(RTRIM(CONVERT(varchar(50), c.reportid))), '') IS NULL
                AND EXISTS (
                    SELECT 1
                    FROM lab_result m WITH (NOLOCK)
                    WHERE m.reportid = a.reportid
                      AND m.req_itemcode = c.req_itemcode
                )
             )
       )
INNER JOIN lab_rptunit d WITH (NOLOCK)
    ON a.rptunitid = d.rptunitid
LEFT JOIN dc_dept dept WITH (NOLOCK)
    ON dept.deptno = a.req_deptno
LEFT JOIN dc_doctor doc WITH (NOLOCK)
    ON doc.doctorno = a.REQ_DOCNO
LEFT JOIN secsysuser input_user WITH (NOLOCK)
    ON input_user.userno = a.input_user
LEFT JOIN secsysuser report_user WITH (NOLOCK)
    ON report_user.userno = a.report_user
LEFT JOIN secsysuser rechk_user WITH (NOLOCK)
    ON rechk_user.userno = a.rechk_user

OUTER APPLY (
    SELECT TOP (1)
        m.testmethod
    FROM lab_result m WITH (NOLOCK)
    WHERE m.reportid = a.reportid
      AND m.req_itemcode = c.req_itemcode
    ORDER BY m.seq
) lr

CROSS APPLY (
    SELECT
        CASE
            WHEN d.RptComm5 = 'POCT' THEN '01'
            WHEN LTRIM(RTRIM(ISNULL(d.RptComm5, ''))) IN
                 ('01','02','03','04','05','06','07','08','09','10','11','12','13','14','99')
                THEN LTRIM(RTRIM(d.RptComm5))
            WHEN LTRIM(RTRIM(ISNULL(d.RptComm5, ''))) = '1' THEN '99'
            WHEN d.ResultClass LIKE '%急查生化%' THEN '10'
            WHEN d.ResultClass LIKE '%生化%' THEN '05'
            WHEN d.ResultClass LIKE '%临检%' THEN '01'
            WHEN d.ResultClass LIKE '%血液%' THEN '01'
            WHEN d.ResultClass LIKE '%凝血%' THEN '01'
            WHEN d.ResultClass LIKE '%输血%' THEN '01'
            WHEN d.ResultClass LIKE '%分子%' THEN '03'
            WHEN d.ResultClass LIKE '%PCR%' THEN '03'
            WHEN d.ResultClass LIKE '%免疫%' THEN '04'
            WHEN d.ResultClass LIKE '%细菌%' THEN '07'
            WHEN d.ResultClass LIKE '%流式%' THEN '06'
            WHEN d.ResultClass LIKE '%体液%' THEN '12'
            WHEN d.ResultClass LIKE '%便常规%' THEN '12'
            WHEN d.ResultClass LIKE '%分泌物%' THEN '12'
            WHEN d.ResultClass LIKE '%其他%' THEN '99'
            ELSE '99'
        END AS CLASS_CODE
) cls_code

CROSS APPLY (
    SELECT
        cls_code.CLASS_CODE AS CLASS_CODE,
        CASE cls_code.CLASS_CODE
            WHEN '01' THEN '临床血液'
            WHEN '02' THEN '核医学科(同位素)检验'
            WHEN '03' THEN '分子诊断学（PCR）项目'
            WHEN '04' THEN '临床免疫'
            WHEN '05' THEN '临床生化'
            WHEN '06' THEN '临床细胞室开展项目'
            WHEN '07' THEN '细菌室项目'
            WHEN '08' THEN '肿瘤标志、自身'
            WHEN '09' THEN '免疫等实验'
            WHEN '10' THEN '急诊生化(干化学)'
            WHEN '12' THEN '临床体液'
            ELSE '其它'
        END AS CLASS_NAME
) cls_name
CROSS APPLY (
    SELECT
        CASE LTRIM(RTRIM(REPLACE(ISNULL(a.Specimen_NAME, ''), '"', '')))
            WHEN '血液' THEN '14'
            WHEN '血清' THEN '14'
            WHEN '静脉血' THEN '56'
            WHEN '静脉血.' THEN '56'
            WHEN '末梢血' THEN '58'
            WHEN '尿' THEN '03'
            WHEN '尿液' THEN '03'
            WHEN '晨尿' THEN '03'
            WHEN '中段尿' THEN '03'
            WHEN '随机尿' THEN '03'
            WHEN '导管尿' THEN '03'
            WHEN '大便' THEN '22'
            WHEN '粪便' THEN '22'
            WHEN '痰' THEN '10'
            WHEN '痰液' THEN '10'
            WHEN '咽拭子' THEN '48'
            WHEN '鼻拭子' THEN '48'
            WHEN '鼻咽' THEN '48'
            WHEN '肛拭子' THEN '48'
            WHEN '耳拭子' THEN '49'
            WHEN '眼拭子' THEN '49'
            WHEN '肺泡灌洗' THEN '35'
            WHEN '肺泡灌洗液' THEN '35'
            WHEN '支气管肺泡灌洗液' THEN '35'
            WHEN '骨髓' THEN '28'
            WHEN '骨髓液' THEN '28'
            WHEN '白带' THEN '33'
            WHEN '阴道分泌物' THEN '33'
            WHEN '阴道拭子' THEN '33'
            WHEN '皮肤' THEN '50'
            WHEN '脑脊液' THEN '05'
            WHEN '分泌物' THEN '24'
            WHEN '宫颈分泌物' THEN '24'
            WHEN '眼内分泌物' THEN '24'
            WHEN '眼外分泌物' THEN '24'
            WHEN '前列腺液' THEN '24'
            WHEN '脓液' THEN '24'
            WHEN '脓' THEN '24'
            WHEN '伤口分泌物' THEN '24'
            WHEN '穿刺液' THEN '08'
            WHEN '胸水' THEN '08'
            WHEN '胸膜液' THEN '08'
            WHEN '腹水' THEN '08'
            WHEN '心包积液' THEN '08'
            WHEN '引流液' THEN '08'
            WHEN '关节液' THEN '08'
            WHEN '关节腔液' THEN '08'
            WHEN '膝关节液' THEN '08'
            WHEN '鞘膜腔液' THEN '08'
            WHEN '胃肠液' THEN '36'
            WHEN '胃液' THEN '36'
            WHEN '胆汁' THEN '36'
            WHEN '组织' THEN '44'
            WHEN '活组织' THEN '44'
            WHEN '病理标本' THEN '44'
            ELSE '99'
        END AS SAMPLE_TYPE_CODE,

        CASE LTRIM(RTRIM(REPLACE(ISNULL(a.Specimen_NAME, ''), '"', '')))
            WHEN '血液' THEN '血液'
            WHEN '血清' THEN '血液'
            WHEN '静脉血' THEN '静脉血'
            WHEN '静脉血.' THEN '静脉血'
            WHEN '末梢血' THEN '末梢血'
            WHEN '尿' THEN '尿'
            WHEN '尿液' THEN '尿'
            WHEN '晨尿' THEN '尿'
            WHEN '中段尿' THEN '尿'
            WHEN '随机尿' THEN '尿'
            WHEN '导管尿' THEN '尿'
            WHEN '大便' THEN '大便'
            WHEN '粪便' THEN '大便'
            WHEN '痰' THEN '痰液'
            WHEN '痰液' THEN '痰液'
            WHEN '咽拭子' THEN '咽/口腔拭子'
            WHEN '鼻拭子' THEN '咽/口腔拭子'
            WHEN '鼻咽' THEN '咽/口腔拭子'
            WHEN '肛拭子' THEN '咽/口腔拭子'
            WHEN '耳拭子' THEN '耳标本（拭子）'
            WHEN '眼拭子' THEN '耳标本（拭子）'
            WHEN '肺泡灌洗' THEN '支气管肺泡灌洗液'
            WHEN '肺泡灌洗液' THEN '支气管肺泡灌洗液'
            WHEN '支气管肺泡灌洗液' THEN '支气管肺泡灌洗液'
            WHEN '骨髓' THEN '骨髓液'
            WHEN '骨髓液' THEN '骨髓液'
            WHEN '白带' THEN '阴道分泌物'
            WHEN '阴道分泌物' THEN '阴道分泌物'
            WHEN '阴道拭子' THEN '阴道分泌物'
            WHEN '皮肤' THEN '皮肤刮取物'
            WHEN '脑脊液' THEN '脑脊液'
            WHEN '分泌物' THEN '分泌物'
            WHEN '宫颈分泌物' THEN '分泌物'
            WHEN '眼内分泌物' THEN '分泌物'
            WHEN '眼外分泌物' THEN '分泌物'
            WHEN '前列腺液' THEN '分泌物'
            WHEN '脓液' THEN '分泌物'
            WHEN '脓' THEN '分泌物'
            WHEN '伤口分泌物' THEN '分泌物'
            WHEN '穿刺液' THEN '穿刺液'
            WHEN '胸水' THEN '穿刺液'
            WHEN '胸膜液' THEN '穿刺液'
            WHEN '腹水' THEN '穿刺液'
            WHEN '心包积液' THEN '穿刺液'
            WHEN '引流液' THEN '穿刺液'
            WHEN '关节液' THEN '穿刺液'
            WHEN '关节腔液' THEN '穿刺液'
            WHEN '膝关节液' THEN '穿刺液'
            WHEN '鞘膜腔液' THEN '穿刺液'
            WHEN '胃肠液' THEN '胃液、十二指肠引流液'
            WHEN '胃液' THEN '胃液、十二指肠引流液'
            WHEN '胆汁' THEN '胃液、十二指肠引流液'
            WHEN '组织' THEN '穿刺组织（注明部位）'
            WHEN '活组织' THEN '穿刺组织（注明部位）'
            WHEN '病理标本' THEN '穿刺组织（注明部位）'
            ELSE ISNULL(NULLIF(LTRIM(RTRIM(a.Specimen_NAME)), ''), '其他，请详述')
        END AS SAMPLE_TYPE_NAME
) smp

CROSS APPLY (
    SELECT
        CASE
            WHEN dept.deptname LIKE '%健康管理%' OR dept.deptname LIKE '%体检%' THEN 'A53'
            WHEN dept.deptname LIKE '%核酸采样%' OR dept.deptname LIKE '%微生物实验室%' OR dept.deptname LIKE '%检验%' THEN 'A30'
            WHEN dept.deptname LIKE '%输血%' THEN 'D74'
            WHEN dept.deptname LIKE '%急诊%' THEN 'A20'
            WHEN dept.deptname LIKE '%儿童发热门诊%' THEN 'A03.11.01.01'
            WHEN dept.deptname LIKE '%发热门诊%' THEN 'A03.11.01'
            WHEN dept.deptname LIKE '%耳%' OR dept.deptname LIKE '%鼻%' OR dept.deptname LIKE '%咽喉%' THEN 'A11'
            WHEN dept.deptname LIKE '%眼%' THEN 'A10'
            WHEN dept.deptname LIKE '%口腔%' THEN 'A12'
            WHEN dept.deptname LIKE '%皮肤%' THEN 'A13'
            WHEN dept.deptname LIKE '%中医%' THEN 'A50'
            WHEN dept.deptname LIKE '%康复%' OR dept.deptname LIKE '%针灸%' THEN 'A21'
            WHEN dept.deptname LIKE '%放疗%' THEN 'A19.11'
            WHEN dept.deptname LIKE '%肿瘤%' OR dept.deptname LIKE '%化疗%' THEN 'A19.1'
            WHEN dept.deptname LIKE '%疼痛%' OR dept.deptname LIKE '%镇痛%' THEN 'A27'
            WHEN dept.deptname LIKE '%重症%' OR dept.deptname LIKE '%ICU%' OR dept.deptname LIKE '%RICU%' THEN 'A28'
            WHEN dept.deptname LIKE '%职业中毒%' OR dept.deptname LIKE '%中毒%' THEN 'A23.01'
            WHEN dept.deptname LIKE '%职业病%' THEN 'A23'
            WHEN dept.deptname LIKE '%感染%' OR dept.deptname LIKE '%肠道%' OR dept.deptname LIKE '%肝病%' THEN 'D73'
            WHEN dept.deptname LIKE '%呼吸%' OR dept.deptname LIKE '%PCCM%' THEN 'A03.01'
            WHEN dept.deptname LIKE '%消化%' OR dept.deptname LIKE '%内镜%' THEN 'A03.02'
            WHEN dept.deptname LIKE '%神经内%' THEN 'A03.03'
            WHEN dept.deptname LIKE '%心内%' OR dept.deptname LIKE '%冠心%' OR dept.deptname LIKE '%高血压%' OR dept.deptname LIKE '%心衰%' THEN 'A03.04'
            WHEN dept.deptname LIKE '%血液%' THEN 'A03.05'
            WHEN dept.deptname LIKE '%肾%' OR dept.deptname LIKE '%透析%' THEN 'A03.06'
            WHEN dept.deptname LIKE '%内分泌%' THEN 'A03.07'
            WHEN dept.deptname LIKE '%风湿%' OR dept.deptname LIKE '%免疫%' THEN 'A03.08'
            WHEN dept.deptname LIKE '%老年%' THEN 'A03.10'
            WHEN dept.deptname LIKE '%内科%' OR dept.deptname LIKE '%便民%' OR dept.deptname LIKE '%全科%' OR dept.deptname LIKE '%门规%' OR dept.deptname LIKE '%留观%' THEN 'A03'
            WHEN dept.deptname LIKE '%肝胆%' THEN 'A04.01.10'
            WHEN dept.deptname LIKE '%胃肠%' THEN 'A04.01.12'
            WHEN dept.deptname LIKE '%肛肠%' THEN 'A04.01.13'
            WHEN dept.deptname LIKE '%乳腺%' THEN 'A04.01.14'
            WHEN dept.deptname LIKE '%甲状腺%' THEN 'A04.01.15'
            WHEN dept.deptname LIKE '%血管%' OR dept.deptname LIKE '%介入%' THEN 'A04.01.16'
            WHEN dept.deptname LIKE '%神经外%' THEN 'A04.02'
            WHEN dept.deptname LIKE '%骨%' OR dept.deptname LIKE '%脊柱%' OR dept.deptname LIKE '%关节%' THEN 'A04.03'
            WHEN dept.deptname LIKE '%泌尿%' THEN 'A04.04'
            WHEN dept.deptname LIKE '%胸外%' THEN 'A04.05'
            WHEN dept.deptname LIKE '%心外%' THEN 'A04.06.10'
            WHEN dept.deptname LIKE '%整形%' OR dept.deptname LIKE '%烧伤%' THEN 'A04.08'
            WHEN dept.deptname LIKE '%外科%' THEN 'A04'
            WHEN dept.deptname LIKE '%妇科%' THEN 'A05.01'
            WHEN dept.deptname LIKE '%妇产%' OR dept.deptname LIKE '%产科%' THEN 'A05'
            WHEN dept.deptname LIKE '%儿保%' THEN 'A09'
            WHEN dept.deptname LIKE '%小儿%' OR dept.deptname LIKE '%儿科%' OR dept.deptname LIKE '%儿童%' THEN 'A07'
            WHEN dept.deptname LIKE '%手术室%' OR dept.deptname LIKE '%麻醉%' THEN 'A26'
            WHEN dept.deptname IS NULL THEN NULL
            ELSE 'A69'
        END AS APPLY_DEPT_CODE
) cs

CROSS APPLY (
    SELECT NULLIF(LTRIM(RTRIM(b.reject_reason)), '') AS REJECT_REASON
) reject_src

CROSS APPLY (
    SELECT
        CASE
            WHEN reject_src.REJECT_REASON IS NULL THEN NULL
            WHEN reject_src.REJECT_REASON LIKE '%类型%' OR reject_src.REJECT_REASON LIKE '%类别%' OR reject_src.REJECT_REASON LIKE '%标本错误%' THEN '1'
            WHEN reject_src.REJECT_REASON LIKE '%容器%' OR reject_src.REJECT_REASON LIKE '%试管%' OR reject_src.REJECT_REASON LIKE '%管子%' THEN '2'
            WHEN reject_src.REJECT_REASON LIKE '%采集量%' OR reject_src.REJECT_REASON LIKE '%量少%' OR reject_src.REJECT_REASON LIKE '%量不足%' OR reject_src.REJECT_REASON LIKE '%不足%' THEN '3'
            WHEN reject_src.REJECT_REASON LIKE '%凝集%' OR reject_src.REJECT_REASON LIKE '%凝固%' OR reject_src.REJECT_REASON LIKE '%凝块%' THEN '4'
            WHEN reject_src.REJECT_REASON LIKE '%溶血%' THEN '5'
            WHEN reject_src.REJECT_REASON LIKE '%标识%' OR reject_src.REJECT_REASON LIKE '%条码%' OR reject_src.REJECT_REASON LIKE '%标签%' OR reject_src.REJECT_REASON LIKE '%姓名%' THEN '6'
            WHEN reject_src.REJECT_REASON LIKE '%储存%' OR reject_src.REJECT_REASON LIKE '%保存%' OR reject_src.REJECT_REASON LIKE '%放置%' THEN '7'
            WHEN reject_src.REJECT_REASON LIKE '%损坏%' OR reject_src.REJECT_REASON LIKE '%破损%' OR reject_src.REJECT_REASON LIKE '%漏%' THEN '8'
            WHEN reject_src.REJECT_REASON LIKE '%温度%' OR reject_src.REJECT_REASON LIKE '%冷藏%' OR reject_src.REJECT_REASON LIKE '%冰冻%' THEN '9'
            WHEN reject_src.REJECT_REASON LIKE '%时间过长%' OR reject_src.REJECT_REASON LIKE '%超时%' OR reject_src.REJECT_REASON LIKE '%送检时间%' THEN '10'
            WHEN reject_src.REJECT_REASON LIKE '%时机%' OR reject_src.REJECT_REASON LIKE '%采集时间%' THEN '11'
            WHEN reject_src.REJECT_REASON LIKE '%微生物%' AND reject_src.REJECT_REASON LIKE '%污染%' THEN '12'
            WHEN reject_src.REJECT_REASON LIKE '%血培养%' AND reject_src.REJECT_REASON LIKE '%污染%' THEN '13'
            ELSE '99'
        END AS SPECIMEN_REJECT_CODE,
        CASE
            WHEN reject_src.REJECT_REASON IS NULL THEN NULL
            WHEN reject_src.REJECT_REASON LIKE '%类型%' OR reject_src.REJECT_REASON LIKE '%类别%' OR reject_src.REJECT_REASON LIKE '%标本错误%' THEN '标本类型错误'
            WHEN reject_src.REJECT_REASON LIKE '%容器%' OR reject_src.REJECT_REASON LIKE '%试管%' OR reject_src.REJECT_REASON LIKE '%管子%' THEN '标本容器错误'
            WHEN reject_src.REJECT_REASON LIKE '%采集量%' OR reject_src.REJECT_REASON LIKE '%量少%' OR reject_src.REJECT_REASON LIKE '%量不足%' OR reject_src.REJECT_REASON LIKE '%不足%' THEN '标本采集量错误'
            WHEN reject_src.REJECT_REASON LIKE '%凝集%' OR reject_src.REJECT_REASON LIKE '%凝固%' OR reject_src.REJECT_REASON LIKE '%凝块%' THEN '抗凝标本凝集'
            WHEN reject_src.REJECT_REASON LIKE '%溶血%' THEN '标本溶血'
            WHEN reject_src.REJECT_REASON LIKE '%标识%' OR reject_src.REJECT_REASON LIKE '%条码%' OR reject_src.REJECT_REASON LIKE '%标签%' OR reject_src.REJECT_REASON LIKE '%姓名%' THEN '标本标识错误'
            WHEN reject_src.REJECT_REASON LIKE '%储存%' OR reject_src.REJECT_REASON LIKE '%保存%' OR reject_src.REJECT_REASON LIKE '%放置%' THEN '标本检验前储存不适当'
            WHEN reject_src.REJECT_REASON LIKE '%损坏%' OR reject_src.REJECT_REASON LIKE '%破损%' OR reject_src.REJECT_REASON LIKE '%漏%' THEN '标本运输途中损坏'
            WHEN reject_src.REJECT_REASON LIKE '%温度%' OR reject_src.REJECT_REASON LIKE '%冷藏%' OR reject_src.REJECT_REASON LIKE '%冰冻%' THEN '标本运输温度不适当'
            WHEN reject_src.REJECT_REASON LIKE '%时间过长%' OR reject_src.REJECT_REASON LIKE '%超时%' OR reject_src.REJECT_REASON LIKE '%送检时间%' THEN '标本运输时间过长'
            WHEN reject_src.REJECT_REASON LIKE '%时机%' OR reject_src.REJECT_REASON LIKE '%采集时间%' THEN '标本采集时机不正确'
            WHEN reject_src.REJECT_REASON LIKE '%微生物%' AND reject_src.REJECT_REASON LIKE '%污染%' THEN '微生物标本污染'
            WHEN reject_src.REJECT_REASON LIKE '%血培养%' AND reject_src.REJECT_REASON LIKE '%污染%' THEN '血培养标本污染'
            ELSE '其他，请详述'
        END AS SPECIMEN_REJECT_NAME
) reject_map

WHERE a.rptunitid <> 50
  AND NULLIF(LTRIM(RTRIM(a.barcode)), '') IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(a.pat_name)), '') IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(a.pat_sex)), '') IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(a.specimen_name)), '') IS NOT NULL
  AND a.rechk_dt IS NOT NULL
  AND a.rechk_dt >= '20210101'
  AND a.rechk_dt <  '20250101'
  AND EXISTS (
      SELECT 1
      FROM lab_result m WITH (NOLOCK)
      WHERE m.reportid = a.reportid
        AND m.req_itemcode = c.req_itemcode
  )
  AND a.pat_name NOT LIKE '%测试%'
