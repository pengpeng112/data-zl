CREATE VIEW [dbo].[EMR_MOLECULAR_PATHOLOGY_REPORT] AS
SELECT
    LEFT(CONVERT(VARCHAR(100), a.PathologyID), 100) AS ID, --- 内码

    '49557032X' AS ORG_CODE, --- 医院组织机构代码；如分子病理平台要求 YLV21051，可改回
    N'山东省第二人民医院' AS ORG_NAME, --- 医院名称

    CASE
        WHEN LTRIM(RTRIM(ISNULL(CONVERT(VARCHAR(10), a.PatientType), ''))) IN ('1','2','3','9')
        THEN LTRIM(RTRIM(CONVERT(VARCHAR(10), a.PatientType)))

        WHEN LTRIM(RTRIM(ISNULL(CONVERT(VARCHAR(10), a.PatientType), ''))) = '02'
          OR LTRIM(RTRIM(ISNULL(a.PatientSource, ''))) = N'住院'
          OR LTRIM(RTRIM(ISNULL(a.PATIENT_SOURCE, ''))) = N'住院'
          OR LTRIM(RTRIM(ISNULL(a.InPatientID, ''))) <> ''
        THEN '2'

        WHEN LTRIM(RTRIM(ISNULL(CONVERT(VARCHAR(10), a.PatientType), ''))) = '01'
          OR LTRIM(RTRIM(ISNULL(a.PatientSource, ''))) = N'门诊'
          OR LTRIM(RTRIM(ISNULL(a.PATIENT_SOURCE, ''))) = N'门诊'
          OR (
                ISNULL(LTRIM(RTRIM(a.InPatientID)), '') = ''
            AND ISNULL(LTRIM(RTRIM(a.OutPatientID)), '') <> ''
             )
        THEN '1'

        WHEN LTRIM(RTRIM(ISNULL(a.PatientSource, ''))) = N'体检'
          OR LTRIM(RTRIM(ISNULL(a.PATIENT_SOURCE, ''))) = N'体检'
        THEN '3'

        ELSE '9'
    END AS PATIENT_TYPE_CODE, --- 病人类型代码

    CASE
        WHEN LTRIM(RTRIM(ISNULL(CONVERT(VARCHAR(10), a.PatientType), ''))) = '02'
          OR LTRIM(RTRIM(ISNULL(a.PatientSource, ''))) = N'住院'
          OR LTRIM(RTRIM(ISNULL(a.PATIENT_SOURCE, ''))) = N'住院'
          OR LTRIM(RTRIM(ISNULL(a.InPatientID, ''))) <> ''
        THEN N'住院'

        WHEN LTRIM(RTRIM(ISNULL(CONVERT(VARCHAR(10), a.PatientType), ''))) = '01'
          OR LTRIM(RTRIM(ISNULL(a.PatientSource, ''))) = N'门诊'
          OR LTRIM(RTRIM(ISNULL(a.PATIENT_SOURCE, ''))) = N'门诊'
          OR (
                ISNULL(LTRIM(RTRIM(a.InPatientID)), '') = ''
            AND ISNULL(LTRIM(RTRIM(a.OutPatientID)), '') <> ''
             )
        THEN N'门诊'

        WHEN LTRIM(RTRIM(ISNULL(a.PatientSource, ''))) = N'体检'
          OR LTRIM(RTRIM(ISNULL(a.PATIENT_SOURCE, ''))) = N'体检'
        THEN N'体检'

        ELSE N'其他'
    END AS PATIENT_TYPE_NAME, --- 病人类型描述

    CAST(NULL AS VARCHAR(11)) AS OTHER_ID_TYPE, --- 其他身份证件标识
    CAST(NULL AS VARCHAR(18)) AS OTHER_ID_NUM,  --- 其他身份证件号码

    CASE
        WHEN NULLIF(LTRIM(RTRIM(ISNULL(a.IdentityCard, ''))), '') IS NOT NULL
         AND LEN(LTRIM(RTRIM(a.IdentityCard))) <= 18
        THEN LEFT(LTRIM(RTRIM(a.IdentityCard)), 18)
        ELSE NULL
    END AS ID_NUM, --- 身份证件号码

    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(a.PatientName)), ''), N'未知'), 50) AS NAME, --- 姓名

    CASE
        WHEN LTRIM(RTRIM(ISNULL(a.PatientSexCode, ''))) IN ('0','1','2','9')
        THEN LTRIM(RTRIM(a.PatientSexCode))
        WHEN REPLACE(LTRIM(RTRIM(ISNULL(a.PatientSex, ''))), '.', '') LIKE N'男%'
        THEN '1'
        WHEN REPLACE(LTRIM(RTRIM(ISNULL(a.PatientSex, ''))), '.', '') LIKE N'女%'
        THEN '2'
        WHEN LTRIM(RTRIM(ISNULL(a.PatientSex, ''))) = ''
        THEN '0'
        ELSE '9'
    END AS SEX_CODE, --- 性别代码

    CASE
        WHEN LTRIM(RTRIM(ISNULL(a.PatientSexCode, ''))) = '1'
          OR REPLACE(LTRIM(RTRIM(ISNULL(a.PatientSex, ''))), '.', '') LIKE N'男%'
        THEN N'男'
        WHEN LTRIM(RTRIM(ISNULL(a.PatientSexCode, ''))) = '2'
          OR REPLACE(LTRIM(RTRIM(ISNULL(a.PatientSex, ''))), '.', '') LIKE N'女%'
        THEN N'女'
        WHEN LTRIM(RTRIM(ISNULL(a.PatientSexCode, ''))) = '0'
          OR LTRIM(RTRIM(ISNULL(a.PatientSex, ''))) = ''
        THEN N'未知'
        ELSE N'不明'
    END AS SEX_NAME, --- 性别

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(a.Mobile)), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(a.ContactInfo)), ''), '')
        ),
        50
    ) AS TELEPHONE, --- 电话号码

    ISNULL(a.PatientAge, -999) AS AGE, --- 年龄（岁）

    CAST(NULL AS INT) AS AGE_MONTH,
    CAST(NULL AS INT) AS AGE_DAY,
    CAST(NULL AS INT) AS AGE_HOUR,

    LEFT(
        CASE
            /* 门诊：直接使用 VISIT_ID */
            WHEN (
                    LTRIM(RTRIM(ISNULL(a.PatientSource, ''))) = N'门诊'
                 OR LTRIM(RTRIM(ISNULL(a.PATIENT_SOURCE, ''))) = N'门诊'
                 OR (
                        ISNULL(LTRIM(RTRIM(a.InPatientID)), '') = ''
                    AND ISNULL(LTRIM(RTRIM(a.OutPatientID)), '') <> ''
                    )
                 )
             AND NULLIF(LTRIM(RTRIM(CONVERT(VARCHAR(50), a.VISIT_ID))), '') IS NOT NULL
            THEN LTRIM(RTRIM(CONVERT(VARCHAR(50), a.VISIT_ID)))

            /* 住院：PatientID + '|' + 住院次数 */
            WHEN NULLIF(LTRIM(RTRIM(a.PatientID)), '') IS NOT NULL
             AND NULLIF(LTRIM(RTRIM(CONVERT(VARCHAR(50), a.VISIT_ID))), '') IS NOT NULL
             AND NULLIF(LTRIM(RTRIM(a.InPatientID)), '') IS NOT NULL
             AND LEFT(
                    LTRIM(RTRIM(CONVERT(VARCHAR(50), a.VISIT_ID))),
                    LEN(LTRIM(RTRIM(a.InPatientID)))
                 ) = LTRIM(RTRIM(a.InPatientID))
             AND LEN(LTRIM(RTRIM(CONVERT(VARCHAR(50), a.VISIT_ID)))) > LEN(LTRIM(RTRIM(a.InPatientID)))
            THEN
                LTRIM(RTRIM(a.PatientID))
                + '|'
                +
                SUBSTRING(
                    LTRIM(RTRIM(CONVERT(VARCHAR(50), a.VISIT_ID))),
                    LEN(LTRIM(RTRIM(a.InPatientID))) + 1,
                    50
                )

            WHEN NULLIF(LTRIM(RTRIM(a.PatientID)), '') IS NOT NULL
             AND NULLIF(LTRIM(RTRIM(a.InPatientID)), '') IS NOT NULL
            THEN LTRIM(RTRIM(a.PatientID)) + '|' + LTRIM(RTRIM(a.InPatientID))

            WHEN NULLIF(LTRIM(RTRIM(a.InPatientID)), '') IS NOT NULL
            THEN LTRIM(RTRIM(a.InPatientID))

            WHEN NULLIF(LTRIM(RTRIM(a.OutPatientID)), '') IS NOT NULL
            THEN LTRIM(RTRIM(a.OutPatientID))

            ELSE CONVERT(VARCHAR(50), a.PathologyID)
        END,
        32
    ) AS VISITING_NUM, --- 就诊号

    CASE
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%乳%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%甲乳%'
        THEN 'A04.01.14'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%胃肠%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%肠胃%'
        THEN 'A04.01.12'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%消化%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%内镜%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%胃镜%'
        THEN 'A03.02'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%甲状腺%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%甲一%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%甲二%'
        THEN 'A04.01.15'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%肝胆%'
        THEN 'A04.01.10'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%肛肠%'
        THEN 'A04.01.13'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%妇产%'
        THEN 'A05'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%妇%'
        THEN 'A05.01'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%产科%'
        THEN 'A05.02'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%胸外%'
        THEN 'A04.05'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%泌尿%'
        THEN 'A04.04'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%神经外%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%神外%'
        THEN 'A04.02'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%肿瘤%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%化疗%'
        THEN 'A19.1'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%病理%'
        THEN 'A31'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%体检%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%查体%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%健康管理%'
        THEN 'A53'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%门诊%'
        THEN 'D99'

        ELSE 'D99'
    END AS DEP_NUM, --- 就诊科室代码

    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(a.InspectionDepartment)), ''), N'其他科室'), 50) AS DEP_NAME, --- 就诊科室名称

    LEFT(ISNULL(a.InpatientArea, ''), 60) AS AREA_NAME, --- 病区名称

    a.SubmitCheckTime AS APPLY_TIME, --- 申请时间

    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(a.ReqNoteID)), ''), ''), 50) AS APPLY_ORDER_NO, --- 申请医嘱流水号

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(a.ReqNoteID)), ''),
            CONVERT(VARCHAR(50), a.PathologyID)
        ),
        50
    ) AS APPLY_FORM_NO, --- 申请单号

    LEFT(CONVERT(VARCHAR(50), a.PathologyID), 50) AS MOLECULAR_PATHOLOGY_NO, --- 分子病理号

    LEFT(CONVERT(VARCHAR(50), a.PathologyID), 50) AS TEST_SERIAL_NO, --- 检测流水号

    ISNULL(a.SpecRecvTime, ISNULL(a.SubmitCheckTime, a.VerifyReportTime)) AS TEST_TIME, --- 检测时间

    LEFT(
        CASE
            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%血液版%'
              OR LTRIM(RTRIM(ISNULL(a.Bbmc, ''))) LIKE N'%血%'
            THEN N'外周血'

            WHEN LTRIM(RTRIM(ISNULL(a.Bbmc, ''))) LIKE N'%骨髓%'
            THEN N'骨髓'

            WHEN LTRIM(RTRIM(ISNULL(a.Bbmc, ''))) LIKE N'%胸水%'
              OR LTRIM(RTRIM(ISNULL(a.Bbmc, ''))) LIKE N'%腹水%'
              OR LTRIM(RTRIM(ISNULL(a.Bbmc, ''))) LIKE N'%胸腹水%'
            THEN N'胸腹水'

            WHEN LTRIM(RTRIM(ISNULL(a.Bbmc, ''))) LIKE N'%脑脊液%'
            THEN N'脑脊液'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%TCT%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%液基%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HPV%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%细胞%'
            THEN N'细胞涂片'

            WHEN LTRIM(RTRIM(ISNULL(a.Bblx, ''))) <> ''
            THEN LEFT(LTRIM(RTRIM(a.Bblx)), 50)

            ELSE N'石蜡组织'
        END,
        50
    ) AS SPECIMEN_TYPE, --- 标本类型

    CASE
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%FISH%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%荧光原位杂交%'
          OR a.MedicalRecordDB IN (24,25)
        THEN N'FISH'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PD-L1%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%程序性死亡受体%'
        THEN N'IHC'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%精准诊疗%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HRD%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%21基因%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%多基因%'
        THEN N'NGS'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%DNA%测序%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%脱氧核糖核酸%'
        THEN N'Sanger'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PCR%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%核酸%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HPV%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%BRAF%'
          OR a.MedicalRecordDB IN (22,10000,10001,10004)
        THEN N'qPCR'

        ELSE N'其他'
    END AS TEST_PLATFORM, --- 检测平台

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(a.MedicalAdviceName)), ''),
            CASE
                WHEN a.MedicalRecordDB IN (22,10004) THEN N'人乳头瘤病毒（HPV）核酸检测'
                WHEN a.MedicalRecordDB IN (24,25) THEN N'荧光原位杂交（FISH）检测'
                WHEN a.MedicalRecordDB IN (10000,10001) THEN N'分子病理基因检测'
                ELSE N'分子病理检测'
            END
        ),
        200
    ) AS TEST_ITEM, --- 检测项目

    LEFT(
        CASE
            WHEN a.MedicalRecordDB IN (24,25)
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%FISH%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%荧光原位杂交%'
            THEN N'荧光原位杂交技术'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PD-L1%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%程序性死亡受体%'
            THEN N'免疫组织化学染色诊断'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%精准诊疗%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HRD%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%21基因%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%多基因%'
            THEN N'高通量测序'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%DNA%测序%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%脱氧核糖核酸%'
            THEN N'DNA测序'

            WHEN a.MedicalRecordDB IN (22,10000,10001,10004)
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HPV%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PCR%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%核酸%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%BRAF%'
            THEN N'实时荧光定量PCR法'

            ELSE N'其他'
        END,
        200
    ) AS TEST_METHOD, --- 检测方法

    CASE
        WHEN NULLIF(LTRIM(RTRIM(a.MedicalAdviceName)), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), N'检测项目：' + LTRIM(RTRIM(a.MedicalAdviceName)))

        WHEN a.MedicalRecordDB IN (22,10004)
        THEN CONVERT(NVARCHAR(MAX), N'检测内容：人乳头瘤病毒（HPV）相关核酸检测')

        WHEN a.MedicalRecordDB IN (24,25)
        THEN CONVERT(NVARCHAR(MAX), N'检测内容：荧光原位杂交（FISH）相关检测')

        WHEN a.MedicalRecordDB IN (10000,10001)
        THEN CONVERT(NVARCHAR(MAX), N'检测内容：分子病理基因检测')

        ELSE CONVERT(NVARCHAR(MAX), N'检测内容：分子病理检测')
    END AS TEST_CONTENT, --- 检测内容

    CASE
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Gjsj))), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), a.Gjsj)
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Zdyj))), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), a.Zdyj)
        ELSE CONVERT(NVARCHAR(MAX), N'未描述')
    END AS TEST_RESULT, --- 检测结果

    CASE
        WHEN a.MedicalRecordDB IN (24,25)
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%FISH%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%荧光原位杂交%'
        THEN 'PP030004'

        WHEN a.MedicalRecordDB IN (22,10004)
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HPV%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%人乳头瘤病毒%'
        THEN 'PP030007'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PD-L1%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%程序性死亡受体%'
        THEN 'PP010026'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%BRAF%'
        THEN 'PP030010'

        WHEN a.MedicalRecordDB IN (10000,10001)
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%基因%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%精准诊疗%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HRD%'
        THEN 'PP030018'

        ELSE 'PP030018'
    END AS PATHOLOGY_EXAM_TYPE_CODE, --- 病理诊断项目代码

    CASE
        WHEN a.MedicalRecordDB IN (24,25)
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%FISH%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%荧光原位杂交%'
        THEN N'荧光原位杂交（FISH）三项以上（含三项）'

        WHEN a.MedicalRecordDB IN (22,10004)
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HPV%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%人乳头瘤病毒%'
        THEN N'人乳头瘤病毒（HPV）核酸检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PD-L1%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%程序性死亡受体%'
        THEN N'程序性死亡受体-配体1(PD-L1)伴随诊断检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%BRAF%'
        THEN N'BRAF基因突变检测'

        WHEN a.MedicalRecordDB IN (10000,10001)
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%基因%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%精准诊疗%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HRD%'
        THEN N'组织/细胞核酸（DNA/RNA）高通量测序'

        ELSE N'组织/细胞核酸（DNA/RNA）高通量测序'
    END AS PATHOLOGY_EXAM_TYPE_NAME, --- 病理诊断项目名称

    LEFT(CONVERT(VARCHAR(50), a.PathologyID), 50) AS REPORT_NO, --- 报告单号

    a.VerifyReportTime AS REPORT_TIME, --- 报告时间

    CAST(NULL AS VARCHAR(200)) AS REPORT_DELAY_REASON,

    CAST(NULL AS VARCHAR(50)) AS EXON,
    CAST(NULL AS VARCHAR(100)) AS LOCUS,

    LEFT(
        CASE
            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PD-L1%'
              OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%PD-L1%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%PD-L1%'
            THEN N'CD274'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%BRAF%'
              OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%BRAF%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%BRAF%'
            THEN N'BRAF'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%EGFR%'
              OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%EGFR%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%EGFR%'
            THEN N'EGFR'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%KRAS%'
              OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%KRAS%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%KRAS%'
            THEN N'KRAS'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%ALK%'
              OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%ALK%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%ALK%'
            THEN N'ALK'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%ROS1%'
              OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%ROS1%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%ROS1%'
            THEN N'ROS1'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HER2%'
              OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%HER2%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%HER2%'
              OR a.MedicalRecordDB IN (24,25)
            THEN N'ERBB2'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HPV%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%人乳头瘤病毒%'
              OR a.MedicalRecordDB IN (22,10004)
            THEN N'HPV'

            WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%多基因%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%精准诊疗%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HRD%'
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%21基因%'
            THEN N'多基因'

            ELSE N'未明确'
        END,
        50
    ) AS GENE_NAME, --- 检测基因

    CAST(NULL AS VARCHAR(50)) AS TRANSCRIPT_ID,
    CAST(NULL AS VARCHAR(100)) AS NUCLEOTIDE_CHANGE,
    CAST(NULL AS VARCHAR(100)) AS AMINO_ACID_CHANGE,
    CAST(NULL AS VARCHAR(20)) AS ALLELE_FREQUENCY,

    LEFT(
        CASE
            WHEN a.MedicalRecordDB IN (24,25)
              OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%FISH%'
              OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%融合%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%融合%'
            THEN N'融合'

            WHEN CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%扩增%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%扩增%'
            THEN N'扩增'

            WHEN CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%缺失%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%缺失%'
            THEN N'缺失'

            WHEN CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%突变%'
              OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%突变%'
            THEN N'错义突变'

            ELSE N'其他'
        END,
        50
    ) AS VARIANT_TYPE, --- 变异类型

    CAST(NULL AS VARCHAR(200)) AS VARIANT_INTERPRETATION,
    CAST(NULL AS VARCHAR(50)) AS GENOTYPE,

    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(a.Bbmc)), ''), N'未注明'), 100) AS SAMPLING_SITE, --- 取材部位

    CAST(NULL AS VARCHAR(20)) AS SEQUENCING_DEPTH,
    CAST(NULL AS VARCHAR(50)) AS TUMOR_MUTATION_BURDEN,

    N'已发布' AS RECORD_STATUS,

    a.VerifyReportTime AS SYSTEM_TIME

FROM dbo.Pitaya a
WHERE a.Status = 512
  AND a.VerifyReportTime >= CONVERT(DATETIME, '2021-01-01', 120)
  AND (
        a.MedicalRecordDB IN (22,24,25,10000,10001,10004)
     OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%基因%'
     OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HPV%'
     OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%FISH%'
     OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PCR%'
     OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PD-L1%'
     OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%精准诊疗%'
     OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HRD%'
     OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%BRAF%'
     OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%核酸%'
     OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%测序%'
  )
