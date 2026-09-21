
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_INSPECTION_TEST" ("ID", "ORG_CODE", "ORG_NAME", "LONIC_CLASS_CODE", "LOINC_CLASS_NAME", "LOCAL_CLASS_CODE", "LOCAL_CLASS_NAME", "INSPECTION_TYPE", "REPORT_ERROR_TYPE", "REPORT_ERROR_REASON", "NAME", "OTHER_ID_TYPE", "OTHER_ID_NUM", "ID_NUM", "PATIENT_TYPE_CODE", "PATIENT_TYPE_NAME", "SEX_CODE", "SEX_NAME", "TELEPHONE", "AGE", "AGE_MONTH", "AGE_DAY", "AGE_HOUR", "VISITING_NUM", "ORDER_ID", "SICKBED_NUM", "CHARGE_TYPE_CODE", "CHARGE_TYPE_NAME", "SAMPLE_NUM", "SAMPLE_TYPE_CODE", "SAMPLE_TYPE_NAME", "APPLY_NUM", "APPLY_HOSP_CODE", "APPLY_HOSP_NAME", "APPLY_DEPT_CODE", "APPLY_DEPT_NAME", "APPLY_DATE", "APPLY_DOCTOR_CODE", "APPLY_DOCTOR_NAME", "DISEASE_CODE", "DISEASE_NAME", "INSPECT_DATE", "SAMPLE_TAKE_DATE", "SAMPLE_RECEIVE_DATE", "EXAM_METHOD", "EXAM_CODE", "EXAM_CODE_NAME", "SPECIMEN_STATE", "SPECIMEN_PLACE_CODE", "SPECIMEN_PLACE_NAME", "SPECIMEN_RISK_CODE", "SPECIMEN_RISK_NAME", "SPECIMEN_QUANTITY_CODE", "SPECIMEN_QUANTITY_NAME", "SPECIMEN_REJECT_CODE", "SPECIMEN_REJECT_NAME", "EXAM_ENGINEER_CODE", "EXAM_ENGINEER_NAME", "EXAM_DOCTOR_CODE", "EXAM_DOCTOR_NAME", "REPORT_NUM", "EXAM_DEPT_CODE", "EXAM_DEPT_NAME", "EXAM_HOSPITAL_CODE", "EXAM_HOSPITAL_NAME", "REPORT_DATE", "REPORT_DOCTOR_CODE", "REPORT_DOCTOR_NAME", "AUDIT_DATE", "AUDIT_DOCTOR_CODE", "AUDIT_DOCTOR_NAME", "IMAGE_DEVICE", "REMARK", "DIAGNOSIS_TREAT_NO", "CARD_TYPE", "CITIZEN_ID", "STATUS", "EFFECTIVE_TIME", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "DEI", "NODE_CODE", "SYSTEM_TIME", "SOURCE_CODE", "CZRK_ID", "DOCTOR_ID_NUM", "REVIEWERS_ID_NUM", "PRINT_TIME", "PRINT_PERSON", "LAB_PURPOSE", "COLLECT_PERSON", "ACCEPT_PERSON") AS 
  SELECT
    /* ===================== 基本信息 ===================== */
    SUBSTRB(TO_CHAR(m.TEST_NO), 1, 100) AS ID, -- 内码，主键

    '49557032X' AS ORG_CODE, -- 医院组织机构代码

    '山东省第二人民医院' AS ORG_NAME, -- 医院名称

    /* ===================== 检验类别 ===================== */
    CASE
        WHEN cls.LOCAL_CLASS_NAME LIKE '%血液%' THEN '01'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%输血%' THEN '01'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%放免%' THEN '02'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%PCR%' OR cls.LOCAL_CLASS_NAME LIKE '%分子%' THEN '03'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%免疫%' THEN '04'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%生化%' THEN '05'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%微量元素%' THEN '05'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%细胞%' THEN '06'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%微生物%' THEN '07'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%细菌%' THEN '07'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%肿瘤%' OR cls.LOCAL_CLASS_NAME LIKE '%自身%' THEN '08'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%化学发光%' THEN '09'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%电化发光%' THEN '09'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%发光%' THEN '09'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%体液%' THEN '12'
        ELSE '99'
    END AS LONIC_CLASS_CODE, -- 检验报告的分类的LOINC编码，按CC99.00004

    CASE
        WHEN cls.LOCAL_CLASS_NAME LIKE '%血液%' THEN '临床血液'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%输血%' THEN '临床血液'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%放免%' THEN '核医学科(同位素)检验'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%PCR%' OR cls.LOCAL_CLASS_NAME LIKE '%分子%' THEN '分子诊断学（PCR）项目'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%免疫%' THEN '临床免疫'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%生化%' THEN '临床生化'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%微量元素%' THEN '临床生化'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%细胞%' THEN '临床细胞室开展项目'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%微生物%' THEN '细菌室项目'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%细菌%' THEN '细菌室项目'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%肿瘤%' OR cls.LOCAL_CLASS_NAME LIKE '%自身%' THEN '肿瘤标志、自身'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%化学发光%' THEN '免疫等实验'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%电化发光%' THEN '免疫等实验'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%发光%' THEN '免疫等实验'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%体液%' THEN '临床体液'
        ELSE '其它'
    END AS LOINC_CLASS_NAME, -- 检验报告的分类的LOINC名称，按CC99.00004

    CASE
        WHEN cls.LOCAL_CLASS_NAME LIKE '%血液%' THEN '01'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%输血%' THEN '01'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%放免%' THEN '02'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%PCR%' OR cls.LOCAL_CLASS_NAME LIKE '%分子%' THEN '03'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%免疫%' THEN '04'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%生化%' THEN '05'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%微量元素%' THEN '05'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%细胞%' THEN '06'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%微生物%' THEN '07'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%细菌%' THEN '07'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%肿瘤%' OR cls.LOCAL_CLASS_NAME LIKE '%自身%' THEN '08'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%化学发光%' THEN '09'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%电化发光%' THEN '09'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%发光%' THEN '09'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%体液%' THEN '12'
        ELSE '99'
    END AS LOCAL_CLASS_CODE, -- 本地检验类别编码，暂按平台检验类别同步

    SUBSTRB(NVL(cls.LOCAL_CLASS_NAME, '其它'), 1, 128) AS LOCAL_CLASS_NAME, -- 本地检验类别名称

    CASE
        WHEN cls.LOCAL_CLASS_NAME LIKE '%血液%' THEN '临床血液'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%输血%' THEN '临床血液'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%放免%' THEN '核医学科(同位素)检验'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%PCR%' OR cls.LOCAL_CLASS_NAME LIKE '%分子%' THEN '分子诊断学（PCR）项目'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%免疫%' THEN '临床免疫'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%生化%' THEN '临床生化'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%微量元素%' THEN '临床生化'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%细胞%' THEN '临床细胞室开展项目'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%微生物%' THEN '细菌室项目'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%细菌%' THEN '细菌室项目'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%肿瘤%' OR cls.LOCAL_CLASS_NAME LIKE '%自身%' THEN '肿瘤标志、自身'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%化学发光%' THEN '免疫等实验'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%电化发光%' THEN '免疫等实验'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%发光%' THEN '免疫等实验'
        WHEN cls.LOCAL_CLASS_NAME LIKE '%体液%' THEN '临床体液'
        ELSE '其它'
    END AS INSPECTION_TYPE, -- 检验类别

    CAST(NULL AS VARCHAR2(10)) AS REPORT_ERROR_TYPE, -- 报告错误类型

    CAST(NULL AS VARCHAR2(500)) AS REPORT_ERROR_REASON, -- 报告错误原因描述

    /* ===================== 患者信息 ===================== */
    SUBSTRB(NVL(m.NAME, p.NAME), 1, 50) AS NAME, -- 姓名

    CAST(NULL AS VARCHAR2(2)) AS OTHER_ID_TYPE, -- 其他身份证件标识

    CAST(NULL AS VARCHAR2(18)) AS OTHER_ID_NUM, -- 其他身份证件号码

    SUBSTRB(NVL(p.ID_NO, '000000000000000000'), 1, 18) AS ID_NUM, -- 身份证件号码

    CASE
        WHEN m.SRC_TYPE_FOR_JOIN IN ('O_RCPT', 'O_NORCPT') THEN '1'
        WHEN m.SRC_TYPE_FOR_JOIN = 'I' THEN '2'
        ELSE '9'
    END AS PATIENT_TYPE_CODE, -- 病人类型代码：1门诊，2住院，9其他

    CASE
        WHEN m.SRC_TYPE_FOR_JOIN IN ('O_RCPT', 'O_NORCPT') THEN '门诊'
        WHEN m.SRC_TYPE_FOR_JOIN = 'I' THEN '住院'
        ELSE '其他'
    END AS PATIENT_TYPE_NAME, -- 病人类型

    CASE TRIM(m.SEX)
        WHEN '男' THEN '1'
        WHEN '女' THEN '2'
        WHEN '未知' THEN '0'
        WHEN '不详' THEN '9'
        WHEN '未说明' THEN '9'
        ELSE '9'
    END AS SEX_CODE, -- 性别代码

    SUBSTRB(
        CASE
            WHEN TRIM(m.SEX) IN ('男', '女', '未知', '不详', '未说明') THEN TRIM(m.SEX)
            ELSE '不明'
        END,
        1,
        20
    ) AS SEX_NAME, -- 性别

    CAST(NULL AS VARCHAR2(50)) AS TELEPHONE, -- 电话号码

    CASE
        WHEN m.AGE BETWEEN 0 AND 200 THEN m.AGE
        ELSE NULL
    END AS AGE, -- 年龄

    CAST(NULL AS NUMBER) AS AGE_MONTH, -- 年龄（月）

    CAST(NULL AS NUMBER) AS AGE_DAY, -- 年龄（天）

    CAST(NULL AS NUMBER) AS AGE_HOUR, -- 年龄（小时）

    SUBSTRB(
        CASE
            WHEN m.SRC_TYPE_FOR_JOIN = 'I' THEN
                m.PATIENT_ID_C || '|' || m.VISIT_ID_C
            WHEN m.SRC_TYPE_FOR_JOIN = 'O_RCPT' THEN
                NVL(e_or.VISIT_ID, NVL(m.RCPT_NO_C, TO_CHAR(m.TEST_NO)))
            WHEN m.SRC_TYPE_FOR_JOIN = 'O_NORCPT' THEN
                NVL(e_od.VISIT_ID, TO_CHAR(m.TEST_NO))
            ELSE
                TO_CHAR(m.TEST_NO)
        END,
        1,
        32
    ) AS VISITING_NUM, -- 门诊优先CLINIC_NO，住院PATIENT_ID|VISIT_ID

    SUBSTRB(
        CASE
            WHEN m.SRC_TYPE_FOR_JOIN IN ('O_RCPT', 'O_NORCPT') THEN
                NVL(m.RCPT_NO_C, TO_CHAR(m.TEST_NO))
            ELSE
                NVL(TO_CHAR(m.ORDER_ID), TO_CHAR(m.TEST_NO))
        END,
        1,
        50
    ) AS ORDER_ID, -- 医嘱流水号

    CAST(NULL AS VARCHAR2(20)) AS SICKBED_NUM, -- 床号

    SUBSTRB(TO_CHAR(m.CHARGE_TYPE), 1, 2) AS CHARGE_TYPE_CODE, -- 收费类别代码

    SUBSTRB(TO_CHAR(m.CHARGE_TYPE), 1, 50) AS CHARGE_TYPE_NAME, -- 收费类别

    SUBSTRB(NVL(m.SPECIMEN_NO, m.TEST_NO), 1, 20) AS SAMPLE_NUM, -- 样本号

    /* ===================== 标本类别 ===================== */
    CASE
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '血清' THEN '01'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '血浆' THEN '02'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('尿', '晨尿', '随机尿', '导管尿') THEN '03'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('血液', '血') THEN '04'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '脑脊液' THEN '05'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '精液' THEN '06'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('浆膜腔积液', '体液') THEN '07'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('穿刺液', '针抽吸物') THEN '08'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '引流液' THEN '09'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '痰' THEN '10'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('保护性导管刷', '毛刷') THEN '12'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '胸腔积液' THEN '13'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '胸水' THEN '15'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '腹水' THEN '16'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('针吸') THEN '17'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '腹穿液' THEN '19'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('囊液', '囊', '黏液囊') THEN '21'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('大便', '粪便') THEN '22'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '分泌物' THEN '24'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '前列腺液' THEN '26'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '全血' THEN '27'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '骨髓' THEN '28'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '心包积液' THEN '31'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('关节液', '关节腔液', '膝关节液', '关节') THEN '32'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('白带', '阴道拭子', '宫颈分泌', '宫颈分泌物', '子宫颈', '阴道') THEN '33'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '羊水' THEN '34'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('肺泡灌洗', '支气管肺泡灌洗液') THEN '35'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('胃液', '胃肠液') THEN '36'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '胆汁' THEN '37'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('鼻腔引流液') THEN '39'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('脓', '脓液', '伤口分泌物', '闭合性脓肿', '开放性脓肿', '脓肿', '污染伤口', '伤口', '口腔脓肿', '盆腔脓肿', '脑脓肿', '肝脓肿', '脓胸', '胸膜脓胸', '褥疮', '溃疡', '蜂窝织炎') THEN '41'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '乳汁' THEN '42'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '房水' THEN '43'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('穿刺组织') THEN '44'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('组织', '活组织', '病理标本', '手术切口', '食管', '支气管', '肺', '肝', '胰腺', '淋巴结', '牙齿', '外周导管', '导管', '导气管') THEN '45'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('咽拭子', '鼻咽', '咽喉', '口', '扁桃体', '鼻拭子', '棉拭子') THEN '48'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('耳拭子', '耳朵', '中耳', '外耳') THEN '49'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('皮屑', '皮肤', '皮肤拭子') THEN '50'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '指甲' THEN '51'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '呕吐物' THEN '52'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '静脉血' THEN '56'
        WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '动脉血' THEN '57'
        ELSE '99'
    END AS SAMPLE_TYPE_CODE, -- 标本类别代码，CC99.00006

    SUBSTRB(
        CASE
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '血清' THEN '血清'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '血浆' THEN '血浆'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('尿', '晨尿', '随机尿', '导管尿') THEN '尿'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('血液', '血') THEN '血'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '脑脊液' THEN '脑脊液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '精液' THEN '精液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('浆膜腔积液', '体液') THEN '浆膜腔积液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('穿刺液', '针抽吸物') THEN '穿刺液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '引流液' THEN '引流液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '痰' THEN '痰液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('保护性导管刷', '毛刷') THEN '毛刷'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '胸腔积液' THEN '胸腔积液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '胸水' THEN '胸水'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '腹水' THEN '腹水'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '腹穿液' THEN '腹穿液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('囊液', '囊', '黏液囊') THEN '囊液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('大便', '粪便') THEN '大便'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '分泌物' THEN '分泌物'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '全血' THEN '全血'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '骨髓' THEN '骨髓液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '心包积液' THEN '心包积液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('关节液', '关节腔液', '膝关节液', '关节') THEN '关节腔积液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('白带', '阴道拭子', '宫颈分泌', '宫颈分泌物', '子宫颈', '阴道') THEN '阴道分泌物'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('肺泡灌洗', '支气管肺泡灌洗液') THEN '支气管肺泡灌洗液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('胃液', '胃肠液') THEN '胃液、十二指肠引流液'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '胆汁' THEN '胆汁'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('脓', '脓液', '伤口分泌物', '闭合性脓肿', '开放性脓肿', '脓肿', '污染伤口', '伤口', '口腔脓肿', '盆腔脓肿', '脑脓肿', '肝脓肿', '脓胸', '胸膜脓胸', '褥疮', '溃疡', '蜂窝织炎') THEN '脓液、创面分泌物'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '乳汁' THEN '母乳'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('组织', '活组织', '病理标本', '手术切口', '食管', '支气管', '肺', '肝', '胰腺', '淋巴结', '牙齿', '外周导管', '导管', '导气管') THEN '手术切除标本（注明部位）'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('咽拭子', '鼻咽', '咽喉', '口', '扁桃体', '鼻拭子', '棉拭子') THEN '咽/口腔拭子'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('耳拭子', '耳朵', '中耳', '外耳') THEN '耳标本（拭子）'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') IN ('皮屑', '皮肤', '皮肤拭子') THEN '皮肤刮取物'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '指甲' THEN '指甲/毛发'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '呕吐物' THEN '呕吐物'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '静脉血' THEN '静脉血'
            WHEN REPLACE(TRIM(NVL(m.SPECIMEN, '其他')), '.', '') = '动脉血' THEN '动脉血'
            ELSE NVL(REPLACE(TRIM(m.SPECIMEN), '.', ''), '其他，请详述')
        END,
        1,
        50
    ) AS SAMPLE_TYPE_NAME, -- 标本类别名称

    SUBSTRB(
        CASE
            WHEN m.SRC_TYPE_FOR_JOIN IN ('O_RCPT', 'O_NORCPT') THEN
                NVL(m.RCPT_NO_C, TO_CHAR(m.TEST_NO))
            ELSE
                NVL(TO_CHAR(m.ORDER_ID), TO_CHAR(m.TEST_NO))
        END,
        1,
        20
    ) AS APPLY_NUM, -- 电子申请单编号

    /* ===================== 申请信息 ===================== */
    '49557032X' AS APPLY_HOSP_CODE, -- 检验申请机构代码

    '山东省第二人民医院' AS APPLY_HOSP_NAME, -- 检验申请机构名称

    SUBSTRB(NVL(COALESCE(d_req.QMPT_CODE, d_req.DEPT_CODE), 'D99'), 1, 32) AS APPLY_DEPT_CODE, -- 检验申请科室代码

    SUBSTRB(NVL(COALESCE(d_req.QMPT_NAME, d_req.DEPT_NAME), '未知科室'), 1, 60) AS APPLY_DEPT_NAME, -- 检验申请科室名称

    NVL(m.REQUESTED_DATE_TIME, NVL(m.SPCM_SAMPLE_DATE_TIME, NVL(m.EXECUTE_DATE, m.RESULTS_RPT_DATE_TIME))) AS APPLY_DATE, -- 申请日期

    SUBSTRB(NVL(s_apply.ID_NO, m.ORDERING_PROVIDER), 1, 32) AS APPLY_DOCTOR_CODE, -- 申请医生代码/身份证号

    SUBSTRB(NVL(s_apply.NAME, NVL(m.ORDERING_PROVIDER, '未知')), 1, 50) AS APPLY_DOCTOR_NAME, -- 申请医师签名

    SUBSTRB(dg.DISEASE_CODE, 1, 20) AS DISEASE_CODE, -- 疾病诊断编码

    SUBSTRB(NVL(dg.DISEASE_NAME, NVL(m.RELEVANT_CLINIC_DIAG, '未知')), 1, 200) AS DISEASE_NAME, -- 疾病诊断名称

    /* ===================== 检验过程 ===================== */
    NVL(
        m.EXECUTE_DATE,
        NVL(
            m.SPCM_SAMPLE_DATE_TIME,
            NVL(
                m.SPCM_RECEIVED_DATE_TIME,
                NVL(
                    m.RESULTS_RPT_DATE_TIME,
                    NVL(m.REQUESTED_DATE_TIME, COALESCE(e_i.VISIT_DATE_TIME, e_or.VISIT_DATE_TIME, e_od.VISIT_DATE_TIME, m.BUSINESS_DATE))
                )
            )
        )
    ) AS INSPECT_DATE, -- 检验日期

    m.SPCM_SAMPLE_DATE_TIME AS SAMPLE_TAKE_DATE, -- 标本采样日期时间

    NVL(
        m.SPCM_RECEIVED_DATE_TIME,
        NVL(
            m.EXECUTE_DATE,
            NVL(
                m.SPCM_SAMPLE_DATE_TIME,
                NVL(
                    m.RESULTS_RPT_DATE_TIME,
                    NVL(m.REQUESTED_DATE_TIME, COALESCE(e_i.VISIT_DATE_TIME, e_or.VISIT_DATE_TIME, e_od.VISIT_DATE_TIME, m.BUSINESS_DATE))
                )
            )
        )
    ) AS SAMPLE_RECEIVE_DATE, -- 接收标本日期时间

    CAST(NULL AS VARCHAR2(500)) AS EXAM_METHOD, -- 检验方法

    CAST(NULL AS VARCHAR2(20)) AS EXAM_CODE, -- 检验项目代码，以检验报告单项目表为主

    CAST(NULL AS VARCHAR2(36)) AS EXAM_CODE_NAME, -- 检验项目名称，以检验报告单项目表为主

    CAST(NULL AS VARCHAR2(100)) AS SPECIMEN_STATE, -- 标本状态

    CAST(NULL AS VARCHAR2(32)) AS SPECIMEN_PLACE_CODE, -- 标本采集部位

    CAST(NULL AS VARCHAR2(100)) AS SPECIMEN_PLACE_NAME, -- 标本采集部位描述

    CAST(NULL AS VARCHAR2(32)) AS SPECIMEN_RISK_CODE, -- 标本危险程度

    CAST(NULL AS VARCHAR2(100)) AS SPECIMEN_RISK_NAME, -- 标本危险程度描述

    CAST(NULL AS VARCHAR2(32)) AS SPECIMEN_QUANTITY_CODE, -- 标本质量

    CAST(NULL AS VARCHAR2(100)) AS SPECIMEN_QUANTITY_NAME, -- 标本质量描述

    CAST(NULL AS VARCHAR2(32)) AS SPECIMEN_REJECT_CODE, -- 标本拒绝原因编码

    CAST(NULL AS VARCHAR2(100)) AS SPECIMEN_REJECT_NAME, -- 标本拒绝原因描述

    /* ===================== 检验/报告人员 ===================== */
    SUBSTRB(NVL(s_report.ID_NO, s_apply.ID_NO), 1, 32) AS EXAM_ENGINEER_CODE, -- 检验技师代码

    SUBSTRB(NVL(s_report.NAME, NVL(s_apply.NAME, '未知')), 1, 50) AS EXAM_ENGINEER_NAME, -- 检验技师签名

    SUBSTRB(NVL(s_report.ID_NO, s_apply.ID_NO), 1, 32) AS EXAM_DOCTOR_CODE, -- 检验医师代码

    SUBSTRB(COALESCE(s_report.NAME, s_audit.NAME, s_apply.NAME, m.TRANSCRIPTIONIST, m.VERIFIED_BY, m.ORDERING_PROVIDER, '未知'), 1, 50) AS EXAM_DOCTOR_NAME, -- 检验医师签名

    SUBSTRB(m.TEST_NO, 1, 20) AS REPORT_NUM, -- 检验报告单编号

    SUBSTRB(NVL(COALESCE(d_perf.QMPT_CODE, d_perf.DEPT_CODE), 'D99'), 1, 32) AS EXAM_DEPT_CODE, -- 检验报告科室代码

    SUBSTRB(NVL(COALESCE(d_perf.QMPT_NAME, d_perf.DEPT_NAME), '未知科室'), 1, 60) AS EXAM_DEPT_NAME, -- 检验报告科室名称

    '49557032X' AS EXAM_HOSPITAL_CODE, -- 检验报告机构代码

    '山东省第二人民医院' AS EXAM_HOSPITAL_NAME, -- 检验报告机构名称

    NVL(
        m.RESULTS_RPT_DATE_TIME,
        NVL(
            m.EXECUTE_DATE,
            NVL(
                m.SPCM_RECEIVED_DATE_TIME,
                NVL(
                    m.SPCM_SAMPLE_DATE_TIME,
                    NVL(m.REQUESTED_DATE_TIME, COALESCE(e_i.VISIT_DATE_TIME, e_or.VISIT_DATE_TIME, e_od.VISIT_DATE_TIME, m.BUSINESS_DATE))
                )
            )
        )
    ) AS REPORT_DATE, -- 报告日期

    SUBSTRB(NVL(s_report.ID_NO, s_apply.ID_NO), 1, 32) AS REPORT_DOCTOR_CODE, -- 报告医生代码

    SUBSTRB(COALESCE(s_report.NAME, s_audit.NAME, s_apply.NAME, m.TRANSCRIPTIONIST, m.VERIFIED_BY, m.ORDERING_PROVIDER, '未知'), 1, 50) AS REPORT_DOCTOR_NAME, -- 报告医师签名

    NVL(
        m.RESULTS_RPT_DATE_TIME,
        NVL(
            m.EXECUTE_DATE,
            NVL(
                m.SPCM_RECEIVED_DATE_TIME,
                NVL(
                    m.SPCM_SAMPLE_DATE_TIME,
                    NVL(m.REQUESTED_DATE_TIME, COALESCE(e_i.VISIT_DATE_TIME, e_or.VISIT_DATE_TIME, e_od.VISIT_DATE_TIME, m.BUSINESS_DATE))
                )
            )
        )
    ) AS AUDIT_DATE, -- 审核日期时间

    SUBSTRB(NVL(s_audit.ID_NO, NVL(s_report.ID_NO, s_apply.ID_NO)), 1, 32) AS AUDIT_DOCTOR_CODE, -- 审核医生代码

    SUBSTRB(COALESCE(s_audit.NAME, s_report.NAME, s_apply.NAME, m.VERIFIED_BY, m.TRANSCRIPTIONIST, m.ORDERING_PROVIDER, '未知'), 1, 50) AS AUDIT_DOCTOR_NAME, -- 审核医师签名

    CAST(NULL AS VARCHAR2(64)) AS IMAGE_DEVICE, -- 检验设备名称

    SUBSTRB(m.MEMO, 1, 200) AS REMARK, -- 备注

    CAST(NULL AS VARCHAR2(20)) AS DIAGNOSIS_TREAT_NO, -- 诊疗编码

    CAST(NULL AS CHAR(1)) AS CARD_TYPE, -- 卡片类型

    CAST(NULL AS VARCHAR2(32)) AS CITIZEN_ID, -- 个人内码

    CAST(NULL AS VARCHAR2(32)) AS STATUS, -- 卡片状态

    NVL(
        m.RESULTS_RPT_DATE_TIME,
        NVL(
            m.EXECUTE_DATE,
            NVL(
                m.SPCM_RECEIVED_DATE_TIME,
                NVL(
                    m.SPCM_SAMPLE_DATE_TIME,
                    NVL(m.REQUESTED_DATE_TIME, COALESCE(e_i.VISIT_DATE_TIME, e_or.VISIT_DATE_TIME, e_od.VISIT_DATE_TIME, m.BUSINESS_DATE))
                )
            )
        )
    ) AS EFFECTIVE_TIME, -- 活动发生时间

    CAST(NULL AS TIMESTAMP) AS CREATED_AT, -- 创建时间

    '370104' AS DISTRICT_CODE, -- 所属行政区划

    'ADDHIS' AS EXCHANGE_TYPE, -- 交换类型

    CAST(NULL AS VARCHAR2(50)) AS DEI, -- 数据交换标识符

    CAST(NULL AS VARCHAR2(50)) AS NODE_CODE, -- 节点标识符

    CAST(SYSTIMESTAMP AS TIMESTAMP) AS SYSTEM_TIME, -- 数据上传时间戳

    CASE
        WHEN m.SRC_TYPE_FOR_JOIN IN ('O_RCPT', 'O_NORCPT') THEN '1'
        WHEN m.SRC_TYPE_FOR_JOIN = 'I' THEN '3'
        ELSE NULL
    END AS SOURCE_CODE, -- 标本来源代码：1门诊，3住院

    CAST(NULL AS VARCHAR2(36)) AS CZRK_ID, -- 常住人口ID

    SUBSTRB(NVL(s_report.ID_NO, s_apply.ID_NO), 1, 18) AS DOCTOR_ID_NUM, -- 检验人员身份证号

    SUBSTRB(NVL(s_audit.ID_NO, NVL(s_report.ID_NO, s_apply.ID_NO)), 1, 18) AS REVIEWERS_ID_NUM, -- 审核人员身份证号

    CAST(NULL AS DATE) AS PRINT_TIME, -- 报告单打印时间

    CAST(NULL AS VARCHAR2(50)) AS PRINT_PERSON, -- 报告单打印人

    CAST(NULL AS VARCHAR2(100)) AS LAB_PURPOSE, -- 检验目的

    SUBSTRB(COALESCE(s_sampler.NAME, m.SAMPLERS), 1, 50) AS COLLECT_PERSON, -- 标本采样人

    CAST(NULL AS VARCHAR2(50)) AS ACCEPT_PERSON -- 标本接收人
FROM
(
    SELECT /*+ NO_MERGE */
        m0.*,
        TO_CHAR(m0.PATIENT_ID) AS PATIENT_ID_C,
        TO_CHAR(m0.VISIT_ID) AS VISIT_ID_C,
        TO_CHAR(m0.RCPT_NO) AS RCPT_NO_C,

        NVL(
            m0.REQUESTED_DATE_TIME,
            NVL(
                m0.SPCM_SAMPLE_DATE_TIME,
                NVL(
                    m0.EXECUTE_DATE,
                    NVL(m0.RESULTS_RPT_DATE_TIME, m0.SPCM_RECEIVED_DATE_TIME)
                )
            )
        ) AS BUSINESS_DATE,

        CASE
            WHEN m0.VISIT_ID > 0 THEN 'I'
            WHEN m0.RCPT_NO IS NOT NULL THEN 'O_RCPT'
            WHEN m0.VISIT_ID IS NULL OR m0.VISIT_ID = 0 THEN 'O_NORCPT'
            ELSE 'X'
        END AS SRC_TYPE_FOR_JOIN
    FROM HIS.LAB_TEST_MASTER m0
    WHERE m0.RESULT_STATUS <> '1'
      AND (
            /* 住院记录按 PAT_VISIT 出院时间判断，不能在这里按检验时间过滤 */
            m0.VISIT_ID > 0

            OR

            /* 门诊/无收据门诊记录，原逻辑本身按 BUSINESS_DATE 过滤 */
            (
                NVL(
                    m0.REQUESTED_DATE_TIME,
                    NVL(
                        m0.SPCM_SAMPLE_DATE_TIME,
                        NVL(
                            m0.EXECUTE_DATE,
                            NVL(m0.RESULTS_RPT_DATE_TIME, m0.SPCM_RECEIVED_DATE_TIME)
                        )
                    )
                ) >= DATE '2021-01-01'
                AND
                NVL(
                    m0.REQUESTED_DATE_TIME,
                    NVL(
                        m0.SPCM_SAMPLE_DATE_TIME,
                        NVL(
                            m0.EXECUTE_DATE,
                            NVL(m0.RESULTS_RPT_DATE_TIME, m0.SPCM_RECEIVED_DATE_TIME)
                        )
                    )
                ) < DATE '2024-01-01'
            )
          )
) m

LEFT JOIN
(
    SELECT
        TO_CHAR(a.PATIENT_ID) AS PATIENT_ID,
        TO_CHAR(a.VISIT_ID) AS VISIT_ID,
        MIN(a.DISCHARGE_DATE_TIME) AS VISIT_DATE_TIME
    FROM HIS.PAT_VISIT a
    WHERE a.DISCHARGE_DATE_TIME >= DATE '2021-01-01'
      AND a.DISCHARGE_DATE_TIME <  DATE '2024-01-01'
    GROUP BY
        TO_CHAR(a.PATIENT_ID),
        TO_CHAR(a.VISIT_ID)
) e_i
    ON m.SRC_TYPE_FOR_JOIN = 'I'
   AND e_i.PATIENT_ID = m.PATIENT_ID_C
   AND e_i.VISIT_ID = m.VISIT_ID_C

LEFT JOIN
(
    SELECT
        TO_CHAR(a.PATIENT_ID) AS PATIENT_ID,
        TO_CHAR(a.RCPT_NO) AS RCPT_NO,
        MIN(TO_CHAR(a.CLINIC_NO)) AS VISIT_ID,
        MIN(a.VISIT_DATE) AS VISIT_DATE_TIME,
        COUNT(DISTINCT TO_CHAR(a.CLINIC_NO)) AS CLINIC_NO_CNT
    FROM HIS.OUTP_ORDER_DESC a
    WHERE a.VISIT_DATE >= DATE '2021-01-01'
      AND a.VISIT_DATE <  DATE '2024-01-01'
      AND a.RCPT_NO IS NOT NULL
      AND a.CLINIC_NO IS NOT NULL
    GROUP BY
        TO_CHAR(a.PATIENT_ID),
        TO_CHAR(a.RCPT_NO)
) e_or
    ON m.SRC_TYPE_FOR_JOIN = 'O_RCPT'
   AND e_or.PATIENT_ID = m.PATIENT_ID_C
   AND e_or.RCPT_NO = m.RCPT_NO_C

LEFT JOIN
(
    SELECT
        PATIENT_ID,
        VISIT_DATE,
        VISIT_ID,
        VISIT_DATE_TIME
    FROM
    (
        SELECT
            TO_CHAR(a.PATIENT_ID) AS PATIENT_ID,
            TRUNC(a.VISIT_DATE) AS VISIT_DATE,
            MIN(TO_CHAR(a.CLINIC_NO)) AS VISIT_ID,
            MIN(a.VISIT_DATE) AS VISIT_DATE_TIME,
            COUNT(DISTINCT TO_CHAR(a.CLINIC_NO)) AS CLINIC_NO_CNT
        FROM HIS.OUTP_ORDER_DESC a
        WHERE a.VISIT_DATE >= DATE '2021-01-01'
          AND a.VISIT_DATE <  DATE '2024-01-01'
          AND a.CLINIC_NO IS NOT NULL
        GROUP BY
            TO_CHAR(a.PATIENT_ID),
            TRUNC(a.VISIT_DATE)
    )
    WHERE CLINIC_NO_CNT = 1
) e_od
    ON m.SRC_TYPE_FOR_JOIN = 'O_NORCPT'
   AND e_od.PATIENT_ID = m.PATIENT_ID_C
   AND e_od.VISIT_DATE = TRUNC(m.BUSINESS_DATE)

LEFT JOIN HIS.PAT_MASTER_INDEX p
    ON p.PATIENT_ID = m.PATIENT_ID

LEFT JOIN (
    SELECT dd.DEPT_CODE,
           MAX(dd.QMPT_CODE) AS QMPT_CODE,
           MAX(dd.QMPT_NAME) AS QMPT_NAME,
           MAX(dd.DEPT_NAME) AS DEPT_NAME
      FROM HIS.DEPT_DICT dd
     GROUP BY dd.DEPT_CODE
) d_req
    ON d_req.DEPT_CODE = m.ORDERING_DEPT

LEFT JOIN (
    SELECT dd.DEPT_CODE,
           MAX(dd.QMPT_CODE) AS QMPT_CODE,
           MAX(dd.QMPT_NAME) AS QMPT_NAME,
           MAX(dd.DEPT_NAME) AS DEPT_NAME
      FROM HIS.DEPT_DICT dd
     GROUP BY dd.DEPT_CODE
) d_perf
    ON d_perf.DEPT_CODE = m.PERFORMED_BY

LEFT JOIN (
    SELECT s.EMP_NO,
           MAX(s.NAME) AS NAME,
           MAX(s.ID_NO) AS ID_NO
      FROM HIS.STAFF_DICT s
     GROUP BY s.EMP_NO
) s_apply
    ON s_apply.EMP_NO = m.ORDERING_PROVIDER

LEFT JOIN (
    SELECT s.EMP_NO,
           MAX(s.NAME) AS NAME,
           MAX(s.ID_NO) AS ID_NO
      FROM HIS.STAFF_DICT s
     GROUP BY s.EMP_NO
) s_report
    ON s_report.EMP_NO = m.TRANSCRIPTIONIST

LEFT JOIN (
    SELECT s.EMP_NO,
           MAX(s.NAME) AS NAME,
           MAX(s.ID_NO) AS ID_NO
      FROM HIS.STAFF_DICT s
     GROUP BY s.EMP_NO
) s_audit
    ON s_audit.EMP_NO = m.VERIFIED_BY

LEFT JOIN (
    SELECT s.EMP_NO,
           MAX(s.NAME) AS NAME,
           MAX(s.ID_NO) AS ID_NO
      FROM HIS.STAFF_DICT s
     GROUP BY s.EMP_NO
) s_sampler
    ON s_sampler.EMP_NO = m.SAMPLERS

LEFT JOIN (
    SELECT li.TEST_NO,
           MAX(b.EXPAND2) AS LOCAL_CLASS_NAME
      FROM HIS.LAB_TEST_ITEMS li
      LEFT JOIN HIS.CLINIC_ITEM_DICT b
        ON b.ITEM_CODE = li.ITEM_CODE
     GROUP BY li.TEST_NO
) cls
    ON cls.TEST_NO = m.TEST_NO

LEFT JOIN (
    SELECT x.PATIENT_ID,
           x.VISIT_ID,
           MAX(x.DIAGNOSIS_CODE) KEEP (
               DENSE_RANK FIRST ORDER BY
               CASE x.DIAGNOSIS_TYPE
                   WHEN '3' THEN 1
                   WHEN '2' THEN 2
                   WHEN '1' THEN 3
                   ELSE 9
               END,
               NVL(x.DIAGNOSIS_NO, 999)
           ) AS DISEASE_CODE,
           MAX(x.DIAGNOSIS_DESC) KEEP (
               DENSE_RANK FIRST ORDER BY
               CASE x.DIAGNOSIS_TYPE
                   WHEN '3' THEN 1
                   WHEN '2' THEN 2
                   WHEN '1' THEN 3
                   ELSE 9
               END,
               NVL(x.DIAGNOSIS_NO, 999)
           ) AS DISEASE_NAME
      FROM HIS.DIAGNOSIS x
     GROUP BY x.PATIENT_ID,
              x.VISIT_ID
) dg
    ON m.SRC_TYPE_FOR_JOIN = 'I'
   AND dg.PATIENT_ID = m.PATIENT_ID
   AND dg.VISIT_ID = m.VISIT_ID

WHERE m.RESULT_STATUS <>'1'
  AND (
        (
            m.SRC_TYPE_FOR_JOIN = 'I'
            AND e_i.PATIENT_ID IS NOT NULL
        )
        OR
        (
            m.SRC_TYPE_FOR_JOIN = 'O_RCPT'
            AND m.BUSINESS_DATE >= DATE '2021-01-01'
            AND m.BUSINESS_DATE <  DATE '2024-01-01'
        )
        OR
        (
            m.SRC_TYPE_FOR_JOIN = 'O_NORCPT'
            AND e_od.PATIENT_ID IS NOT NULL
            AND m.BUSINESS_DATE >= DATE '2021-01-01'
            AND m.BUSINESS_DATE <  DATE '2024-01-01'
        )
      )
