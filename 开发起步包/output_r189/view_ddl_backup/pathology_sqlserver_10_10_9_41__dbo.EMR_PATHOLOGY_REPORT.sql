CREATE VIEW [dbo].[EMR_PATHOLOGY_REPORT] AS
SELECT
    LEFT(CONVERT(VARCHAR(100), a.PathologyID), 100) AS ID, --- 内码

    '49557032X' AS ORG_CODE, --- 医院组织机构代码
    N'山东省第二人民医院' AS ORG_NAME, --- 医院名称

    CASE
        WHEN LTRIM(RTRIM(ISNULL(a.PatientTypeCode, ''))) IN ('1','2','3','9')
        THEN LTRIM(RTRIM(a.PatientTypeCode))

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
        WHEN LTRIM(RTRIM(ISNULL(a.PatientTypeCode, ''))) = '2'
          OR LTRIM(RTRIM(ISNULL(CONVERT(VARCHAR(10), a.PatientType), ''))) = '02'
          OR LTRIM(RTRIM(ISNULL(a.PatientSource, ''))) = N'住院'
          OR LTRIM(RTRIM(ISNULL(a.PATIENT_SOURCE, ''))) = N'住院'
          OR LTRIM(RTRIM(ISNULL(a.InPatientID, ''))) <> ''
        THEN N'住院'

        WHEN LTRIM(RTRIM(ISNULL(a.PatientTypeCode, ''))) = '1'
          OR LTRIM(RTRIM(ISNULL(CONVERT(VARCHAR(10), a.PatientType), ''))) = '01'
          OR LTRIM(RTRIM(ISNULL(a.PatientSource, ''))) = N'门诊'
          OR LTRIM(RTRIM(ISNULL(a.PATIENT_SOURCE, ''))) = N'门诊'
          OR (
                ISNULL(LTRIM(RTRIM(a.InPatientID)), '') = ''
            AND ISNULL(LTRIM(RTRIM(a.OutPatientID)), '') <> ''
             )
        THEN N'门诊'

        WHEN LTRIM(RTRIM(ISNULL(a.PatientTypeCode, ''))) = '3'
          OR LTRIM(RTRIM(ISNULL(a.PatientSource, ''))) = N'体检'
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
            ISNULL(
                NULLIF(LTRIM(RTRIM(a.ContactInfo)), ''),
                ISNULL(NULLIF(LTRIM(RTRIM(a.NEXT_OF_KIN_PHONE)), ''), '')
            )
        ),
        50
    ) AS TELEPHONE, --- 电话号码

    ISNULL(a.PatientAge, -999) AS AGE, --- 年龄

    CAST(NULL AS INT) AS AGE_MONTH, --- 年龄（月）
    CAST(NULL AS INT) AS AGE_DAY,   --- 年龄（天）
    CAST(NULL AS INT) AS AGE_HOUR,  --- 年龄（小时）

    LEFT(
        CASE
            /* 门诊：直接使用 VISIT_ID，不拼 PatientID */
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

            /* 住院：PatientID + '|' + 住院次数；住院次数 = VISIT_ID 去掉 InPatientID 后剩余部分 */
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

            /* 住院但 VISIT_ID 为空或无法拆分：PatientID + '|' + InPatientID 兜底 */
            WHEN NULLIF(LTRIM(RTRIM(a.PatientID)), '') IS NOT NULL
             AND NULLIF(LTRIM(RTRIM(a.InPatientID)), '') IS NOT NULL
            THEN LTRIM(RTRIM(a.PatientID)) + '|' + LTRIM(RTRIM(a.InPatientID))

            /* PatientID 为空但 InPatientID 有值：用 InPatientID 兜底，保证不空 */
            WHEN NULLIF(LTRIM(RTRIM(a.InPatientID)), '') IS NOT NULL
            THEN LTRIM(RTRIM(a.InPatientID))

            /* 门诊但 VISIT_ID 为空：用 OutPatientID 兜底 */
            WHEN NULLIF(LTRIM(RTRIM(a.OutPatientID)), '') IS NOT NULL
            THEN LTRIM(RTRIM(a.OutPatientID))

            ELSE CONVERT(VARCHAR(50), a.PathologyID)
        END,
        32
    ) AS VISITING_NUM, --- 就诊唯一标识号

    CASE
        /* 重症 / ICU */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%NICU%'
        THEN 'A29.02'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%RICU%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%EICU%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%ICU%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%重症监护%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%重症医学%'
        THEN 'A28'

        /* 呼吸 / PCCM */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%PCCM%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%pccm%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%呼吸%'
        THEN 'A03.01'

        /* 放疗 / 肿瘤 */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%放疗%'
        THEN 'A19.11'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%肿瘤%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%化疗%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%生物治疗%'
        THEN 'A19.1'

        /* 耳鼻咽喉整体 */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%耳鼻喉%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%ENT%'
        THEN 'A11'

        /* 鼻科 */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%鼻%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%变态反应%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%过敏%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%嗅觉%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%结构性鼻%'
        THEN 'A11.02'

        /* 耳科 */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%耳%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%侧颅底%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%听觉%'
        THEN 'A11.01'

        /* 咽喉 / 头颈 */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%咽喉%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%嗓音%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%小儿ENT%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%小儿耳鼻喉%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%头颈%'
        THEN 'A11.03'

        /* 妇产 / 儿科 */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%妇产%'
        THEN 'A05'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%产科%'
        THEN 'A05.02'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%妇%'
        THEN 'A05.01'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%儿科%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%小儿%'
        THEN 'A07'

        /* 普外细分 */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%肝胆%'
        THEN 'A04.01.10'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%胃肠%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%肠胃%'
        THEN 'A04.01.12'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%肛肠%'
        THEN 'A04.01.13'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%乳%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%甲乳%'
        THEN 'A04.01.14'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%甲状腺%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%甲一%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%甲二%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%甲状腺一%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%甲状腺二%'
        THEN 'A04.01.15'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%血管外%'
        THEN 'A04.01.16'

        /* 外科大类 */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%神经外%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%神外%'
        THEN 'A04.02'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%创伤%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%骨创%'
        THEN 'A04.03.10'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%脊柱%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%脊椎%'
        THEN 'A04.03.11'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%关节%'
        THEN 'A04.03.12'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%手足%'
        THEN 'A04.03.13'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%运动医学%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%运动医疗%'
        THEN 'A22'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%骨科%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%骨%'
        THEN 'A04.03'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%泌尿%'
        THEN 'A04.04'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%胸外%'
        THEN 'A04.05'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%心外%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%心血管外%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%心脏外%'
        THEN 'A04.06.10'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%烧伤%'
        THEN 'A04.07'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%整形%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%美容%'
        THEN 'A04.08'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%外科%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%外门诊%'
        THEN 'A04'

        /* 内科大类 */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%消化%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%内镜%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%胃镜%'
        THEN 'A03.02'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%神经内%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%神内%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%帕金森%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%眩晕%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%头痛%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%认知障碍%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%发作性疾病%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%神经介入%'
        THEN 'A03.03'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%心内%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%冠心病%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%心律失常%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%高血压%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%心衰%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%结构性心脏%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%结构心脏%'
        THEN 'A03.04'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%血液病%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%血液科%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%血液内科%'
        THEN 'A03.05'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%肾脏%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%血液净化%'
        THEN 'A03.06'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%内分泌%'
        THEN 'A03.07'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%风湿%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%免疫%'
        THEN 'A03.08'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%老年%'
        THEN 'A03.10'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%普通内科%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%综合内%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%内科门诊%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%内二科%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%内三科%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%内三%'
        THEN 'A03'

        /* 其他临床科室 */
        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%全科%'
        THEN 'A02'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%保健%'
        THEN 'A01'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%急诊%'
        THEN 'A20'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%感染%'
        THEN 'D73'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%康复%'
        THEN 'A21'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%疼痛%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%镇痛%'
        THEN 'A27'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%皮肤%'
        THEN 'A13.01'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%眼科%'
        THEN 'A10'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%口腔颌面%'
        THEN 'A12.02'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%口腔%'
        THEN 'A12'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%中医%'
        THEN 'A50'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%病理%'
        THEN 'A31'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%超声%'
        THEN 'A32.05'

        WHEN LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%体检%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%查体%'
          OR LTRIM(RTRIM(ISNULL(a.InspectionDepartment, ''))) LIKE N'%健康管理%'
        THEN 'A53'

        ELSE 'D99'
    END AS DEP_NUM, --- 就诊科室代码

    LEFT(ISNULL(NULLIF(LTRIM(RTRIM(a.InspectionDepartment)), ''), N'其他科室'), 50) AS DEP_NAME, --- 就诊科室名称，保留原始名称便于追溯

    LEFT(ISNULL(a.InpatientArea, ''), 60) AS AREA_NAME, --- 病区名称

    ISNULL(a.EXAM_APPLY_TIME, ISNULL(a.requestDate, a.SubmitCheckTime)) AS APPLY_TIME, --- 申请时间

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(a.ReqNoteID)), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(a.EXAM_APPLY_FLOW)), ''), '')
        ),
        50
    ) AS APPLY_ORDER_NO, --- 申请医嘱流水号

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(a.EXAM_APPLY_FLOW)), ''),
            ISNULL(
                NULLIF(LTRIM(RTRIM(a.ReqNoteID)), ''),
                ISNULL(NULLIF(LTRIM(RTRIM(a.HisID)), ''), CONVERT(VARCHAR(50), a.PathologyID))
            )
        ),
        50
    ) AS APPLY_FORM_NO, --- 申请单号

    LEFT(CONVERT(VARCHAR(50), a.PathologyID), 50) AS PATHOLOGY_NO, --- 病理号

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(a.EXAM_RPT_FLOW)), ''),
            CONVERT(VARCHAR(50), a.PathologyID)
        ),
        50
    ) AS PATHOLOGY_EXAM_NO, --- 病理检查流水号

    ISNULL(a.VerifyReportTime, ISNULL(a.ReportTime, a.ReportPrintDate)) AS EXAM_TIME, --- 检查时间

    CASE
        /* 分子 / 基因 / 精准诊疗 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PD-L1%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%程序性死亡受体%'
        THEN 'PP010026'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HPV%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%人乳头瘤病毒%'
        THEN 'PP030007'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%BRAF%'
        THEN 'PP030010'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%EGFR%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%表皮生长因子受体%'
        THEN 'PP030008'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%KRAS%'
        THEN 'PP030009'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%ALK蛋白%'
        THEN 'PP010027'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%ALK%'
        THEN 'PP030011'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%ROS1%'
        THEN 'PP030012'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%BRCA%'
        THEN 'PP030019'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%乳腺癌21基因%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%乳腺癌预后用药21基因%'
        THEN 'PP030014'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%肺癌18基因%'
        THEN 'PP030020'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%肺癌靶向%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%肺癌17基因%'
        THEN 'PP030021'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%胃肠12基因%'
        THEN 'PP030022'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%脑胶质瘤%'
        THEN 'PP030023'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%CNV%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%染色体高通量%'
        THEN 'PP030025'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%FISH%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%荧光原位杂交%'
        THEN 'PP030004'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%原位杂交%'
        THEN 'PP030001'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%脱氧核糖核酸%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%DNA%测序%'
        THEN 'PP030017'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%DT%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%精准诊疗%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%基因%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HRD%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%药物基因%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%遗传标志物%'
        THEN 'PP030018'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%RNA%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PCR%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%核酸%'
        THEN 'PP030006'

        /* 冰冻 / 快速石蜡 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%冰冻%'
        THEN 'PP010036'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%快速石蜡%'
        THEN 'PP010037'

        /* 免疫 / 特染 / 电镜 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%免疫荧光%'
        THEN 'PP010025'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%免疫组化%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%免疫组织化学%'
        THEN 'PP010024'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%特殊染色%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%TAP%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%肿瘤异常蛋白%'
        THEN 'PP010023'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%普通透射电镜%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%电镜%'
        THEN 'PP010039'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%病理体视学%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%图像分析%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%图象分析%'
        THEN 'PP010029'

        /* 细胞学 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%细胞蜡块%'
        THEN 'PP010033'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%液基薄层%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%液基超薄%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%液基细胞%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%TCT%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%ECT%'
        THEN 'PP010006'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%细针穿刺细胞学%'
        THEN 'PP010005'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%体液细胞学%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%胸腹水%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%心包积液%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%脑脊液%'
        THEN 'PP010003'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%脱落细胞学%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%非妇科脱落细胞学%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%细胞病理学%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%常规细胞学涂片%'
        THEN 'PP010007'

        /* 活检 / 手术标本 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%穿刺组织活检%'
        THEN 'PP010010'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%内镜切除标本%'
        THEN 'PP010017'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%内镜组织活检%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%内窥镜活检%'
        THEN 'PP010011'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%局部切除组织活检%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%病理活检%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%宫颈活检%'
        THEN 'PP010012'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%根治%'
        THEN 'PP010016'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%单切%'
        THEN 'PP010015'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%手术标本%'
        THEN 'PP010014'

        /* 附加收费/切片类，按病理检查兜底 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%图文病理报告%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%加收%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%白片切取%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%每增加一个部位%'
        THEN 'PP010014'

        /* MedicalAdviceName 为空时，按 MedicalRecordDB 兜底 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) = ''
         AND a.MedicalRecordDB = 20
        THEN 'PP010007'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) = ''
         AND a.MedicalRecordDB IN (22,24,25,10000,10001,10004)
        THEN 'PP030018'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) = ''
         AND a.MedicalRecordDB = 26
        THEN 'PP010023'

        ELSE 'PP010014'
    END AS PATHOLOGY_EXAM_TYPE_CODE, --- 病理诊断项目代码

    CASE
        /* 分子 / 基因 / 精准诊疗 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PD-L1%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%程序性死亡受体%'
        THEN N'程序性死亡受体-配体1(PD-L1)伴随诊断检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HPV%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%人乳头瘤病毒%'
        THEN N'人乳头瘤病毒（HPV）核酸检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%BRAF%'
        THEN N'BRAF基因突变检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%EGFR%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%表皮生长因子受体%'
        THEN N'表皮生长因子受体基因突变检测（EGFR）'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%KRAS%'
        THEN N'KRAS基因突变检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%ALK蛋白%'
        THEN N'ALK蛋白伴随诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%ALK%'
        THEN N'EML4-ALK融合基因检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%ROS1%'
        THEN N'ROS1融合基因突变检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%BRCA%'
        THEN N'BRCA1/2基因检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%乳腺癌21基因%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%乳腺癌预后用药21基因%'
        THEN N'乳腺癌21基因表达检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%肺癌18基因%'
        THEN N'肺癌18基因检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%肺癌靶向%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%肺癌17基因%'
        THEN N'肺癌靶向治疗相关基因（13个）测序'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%胃肠12基因%'
        THEN N'胃肠12基因检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%脑胶质瘤%'
        THEN N'脑胶质瘤基因检测'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%CNV%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%染色体高通量%'
        THEN N'染色体高通量测序分析(CNV)'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%FISH%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%荧光原位杂交%'
        THEN N'荧光原位杂交（FISH）三项以上（含三项）'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%原位杂交%'
        THEN N'原位杂交技术'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%脱氧核糖核酸%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%DNA%测序%'
        THEN N'脱氧核糖核酸（DNA）测序'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%DT%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%精准诊疗%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%基因%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%HRD%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%药物基因%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%遗传标志物%'
        THEN N'组织/细胞核酸（DNA/RNA）高通量测序'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%RNA%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%PCR%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%核酸%'
        THEN N'组织/细胞荧光定量（DNA/RNA）多聚酶链式反应检测'

        /* 冰冻 / 快速石蜡 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%冰冻%'
        THEN N'冰冻切片检查与诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%快速石蜡%'
        THEN N'快速石蜡切片检查与诊断（包括快速细胞病理诊断）'

        /* 免疫 / 特染 / 电镜 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%免疫荧光%'
        THEN N'免疫荧光染色诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%免疫组化%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%免疫组织化学%'
        THEN N'免疫组织化学染色诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%特殊染色%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%TAP%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%肿瘤异常蛋白%'
        THEN N'特殊染色及酶组织化学染色诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%普通透射电镜%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%电镜%'
        THEN N'普通透射电镜检查与诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%病理体视学%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%图像分析%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%图象分析%'
        THEN N'病理体视学检查与图象分析(包括流式细胞仪、显微分光光度技术等)'

        /* 细胞学 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%细胞蜡块%'
        THEN N'细胞蜡块诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%液基薄层%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%液基超薄%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%液基细胞%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%TCT%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%ECT%'
        THEN N'液基薄层细胞制片术'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%细针穿刺细胞学%'
        THEN N'细针穿刺细胞学检查与诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%体液细胞学%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%胸腹水%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%心包积液%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%脑脊液%'
        THEN N'体液细胞学检查与诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%脱落细胞学%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%非妇科脱落细胞学%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%细胞病理学%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%常规细胞学涂片%'
        THEN N'脱落细胞学检查与诊断'

        /* 活检 / 手术标本 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%穿刺组织活检%'
        THEN N'穿刺组织活检检查与诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%内镜切除标本%'
        THEN N'内镜切除标本诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%内镜组织活检%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%内窥镜活检%'
        THEN N'内镜组织活检检查与诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%局部切除组织活检%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%病理活检%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%宫颈活检%'
        THEN N'局部切除组织活检检查与诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%根治%'
        THEN N'根治手术标本'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%单切%'
        THEN N'单切手术标本'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%手术标本%'
        THEN N'手术标本检查与诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%图文病理报告%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%加收%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%白片切取%'
          OR LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) LIKE N'%每增加一个部位%'
        THEN N'手术标本检查与诊断'

        /* MedicalAdviceName 为空时，按 MedicalRecordDB 兜底 */
        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) = ''
         AND a.MedicalRecordDB = 20
        THEN N'脱落细胞学检查与诊断'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) = ''
         AND a.MedicalRecordDB IN (22,24,25,10000,10001,10004)
        THEN N'组织/细胞核酸（DNA/RNA）高通量测序'

        WHEN LTRIM(RTRIM(ISNULL(a.MedicalAdviceName, ''))) = ''
         AND a.MedicalRecordDB = 26
        THEN N'特殊染色及酶组织化学染色诊断'

        ELSE N'手术标本检查与诊断'
    END AS PATHOLOGY_EXAM_TYPE_NAME, --- 病理诊断项目名称

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(a.SPECIMEN_POSITION)), ''),
            ISNULL(
                NULLIF(LTRIM(RTRIM(a.Jcwd)), ''),
                ISNULL(NULLIF(LTRIM(RTRIM(a.Bbmc)), ''), N'未注明')
            )
        ),
        100
    ) AS SPECIMEN_SITE, --- 标本部位

    LEFT(
        CASE
            WHEN NULLIF(LTRIM(RTRIM(a.GET_TISSUE_WAY)), '') IS NOT NULL
            THEN LTRIM(RTRIM(a.GET_TISSUE_WAY))

            WHEN a.MedicalAdviceName LIKE N'%内镜%'
              OR a.MedicalAdviceName LIKE N'%胃镜%'
              OR a.MedicalAdviceName LIKE N'%肠镜%'
              OR a.InspectionDepartment LIKE N'%内镜%'
              OR a.InspectionDepartment LIKE N'%胃镜%'
              OR a.InspectionDepartment LIKE N'%肠镜%'
              OR a.Bbmc LIKE N'%胃粘膜%'
              OR a.Bbmc LIKE N'%肠粘膜%'
            THEN N'内镜活检'

            WHEN a.MedicalAdviceName LIKE N'%穿刺%'
              OR a.Bbmc LIKE N'%穿刺%'
            THEN N'穿刺'

            WHEN a.MedicalAdviceName LIKE N'%HPV%'
              OR a.MedicalAdviceName LIKE N'%液基%'
              OR a.MedicalAdviceName LIKE N'%TCT%'
              OR a.Bbmc LIKE N'%TCT%'
              OR a.Bbmc LIKE N'%HPV%'
            THEN N'宫颈采样'

            WHEN a.MedicalAdviceName LIKE N'%TAP%'
              OR a.Bbmc LIKE N'%TAP%'
            THEN N'血液'

            ELSE N'手术切除'
        END,
        50
    ) AS SPECIMEN_SOURCE, --- 标本来源

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(a.ITEM_NO)), ''),
            CONVERT(VARCHAR(50), a.PathologyID)
        ),
        50
    ) AS SPECIMEN_NO, --- 标本编号

    ISNULL(a.INVITRO_TIME, ISNULL(a.FIXED_TIME, ISNULL(a.EXAM_APPLY_TIME, a.SubmitCheckTime))) AS SPECIMEN_COLLECT_TIME, --- 标本采集时间

    ISNULL(a.SampleShrq, a.SpecRecvTime) AS SPECIMEN_RECEIVE_TIME, --- 标本接收时间

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(a.EXAM_RPT_FLOW)), ''),
            CONVERT(VARCHAR(50), a.PathologyID)
        ),
        50
    ) AS REPORT_NO, --- 报告单号

    ISNULL(a.VerifyReportTime, ISNULL(a.ReportTime, ISNULL(a.ReportPrintDate, a.Czrq))) AS REPORT_TIME, --- 报告时间

    LEFT(
        ISNULL(
            NULLIF(LTRIM(RTRIM(CONVERT(VARCHAR(200), a.ReportDelay))), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(a.ReasonForFailure)), ''), '')
        ),
        200
    ) AS REPORT_DELAY_REASON, --- 病理报告延迟原因

    CAST(NULL AS VARCHAR(20)) AS TNM_STAGE_VERSION,
    CAST(NULL AS VARCHAR(20)) AS PATHOLOGY_STAGE,
    CAST(NULL AS VARCHAR(10)) AS PT_STAGE,
    CAST(NULL AS VARCHAR(10)) AS PN_STAGE,
    CAST(NULL AS VARCHAR(10)) AS PM_STAGE,

    CASE
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Rysj))), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), a.Rysj)
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.OperativeFindings))), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), a.OperativeFindings)
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Zdyj))), '') IS NOT NULL
        THEN N'未单独记录肉眼所见，详见病理诊断结论'
        ELSE N'未描述'
    END AS GROSS_FINDING, --- 肉眼所见

    CASE
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Mcyj))), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), a.Mcyj)
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Gjsj))), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), a.Gjsj)
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Zdyj))), '') IS NOT NULL
        THEN N'未单独记录镜下所见，详见病理诊断结论'
        ELSE N'未描述'
    END AS MICROSCOPIC_FINDING, --- 镜下所见

    CASE
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Zdyj))), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), a.Zdyj)
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.OriginDiagnosisResult))), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), a.OriginDiagnosisResult)
        ELSE N'未描述'
    END AS PATHOLOGY_DIAGNOSIS, --- 病理诊断结论

    CASE
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Mcyj))), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), a.Mcyj)

        WHEN CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%免疫%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%组化%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%ER(%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%PR(%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%HER2%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%Ki-67%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%Ki67%'
        THEN CONVERT(NVARCHAR(MAX), a.Zdyj)

        ELSE CAST(NULL AS NVARCHAR(MAX))
    END AS IHC_RESULT, --- 免疫组化检测结果

    CASE
        WHEN a.MedicalRecordDB IN (22,24,25,10000,10001,10004)
          OR a.MedicalAdviceName LIKE N'%分子%'
          OR a.MedicalAdviceName LIKE N'%基因%'
          OR a.MedicalAdviceName LIKE N'%HPV%'
          OR a.MedicalAdviceName LIKE N'%PCR%'
          OR a.MedicalAdviceName LIKE N'%FISH%'
          OR a.MedicalAdviceName LIKE N'%PD-L1%'
          OR a.MedicalAdviceName LIKE N'%BRAF%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%FISH%'
          OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%FISH%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%基因%'
          OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%基因%'
        THEN '1'
        ELSE '0'
    END AS HAS_MOLECULAR_TEST, --- 有无分子检测

    CASE
        WHEN a.MedicalRecordDB IN (22,24,25,10000,10001,10004)
          OR a.MedicalAdviceName LIKE N'%分子%'
          OR a.MedicalAdviceName LIKE N'%基因%'
          OR a.MedicalAdviceName LIKE N'%HPV%'
          OR a.MedicalAdviceName LIKE N'%PCR%'
          OR a.MedicalAdviceName LIKE N'%FISH%'
          OR a.MedicalAdviceName LIKE N'%PD-L1%'
          OR a.MedicalAdviceName LIKE N'%BRAF%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%FISH%'
          OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%FISH%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%基因%'
          OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%基因%'
        THEN LEFT(
                ISNULL(
                    NULLIF(LTRIM(RTRIM(a.MedicalAdviceName)), ''),
                    CASE
                        WHEN CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%FISH%'
                          OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%FISH%'
                        THEN N'FISH检测'
                        WHEN CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%HPV%'
                          OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%HPV%'
                        THEN N'HPV检测'
                        WHEN CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%基因%'
                          OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%基因%'
                        THEN N'基因检测'
                        ELSE N'分子病理检测'
                    END
                ),
                200
             )
        ELSE CAST(NULL AS NVARCHAR(200))
    END AS MOLECULAR_TEST_METHOD, --- 分子检测项目及方法

    CASE
        WHEN a.MedicalRecordDB IN (22,24,25,10000,10001,10004)
          OR a.MedicalAdviceName LIKE N'%分子%'
          OR a.MedicalAdviceName LIKE N'%基因%'
          OR a.MedicalAdviceName LIKE N'%HPV%'
          OR a.MedicalAdviceName LIKE N'%PCR%'
          OR a.MedicalAdviceName LIKE N'%FISH%'
          OR a.MedicalAdviceName LIKE N'%PD-L1%'
          OR a.MedicalAdviceName LIKE N'%BRAF%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%FISH%'
          OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%FISH%'
          OR CONVERT(NVARCHAR(MAX), a.Zdyj) LIKE N'%基因%'
          OR CONVERT(NVARCHAR(MAX), a.Gjsj) LIKE N'%基因%'
        THEN
            CASE
                WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Gjsj))), '') IS NOT NULL
                THEN CONVERT(NVARCHAR(MAX), a.Gjsj)
                WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Zdyj))), '') IS NOT NULL
                THEN CONVERT(NVARCHAR(MAX), a.Zdyj)
                ELSE CAST(NULL AS NVARCHAR(MAX))
            END
        ELSE CAST(NULL AS NVARCHAR(MAX))
    END AS MOLECULAR_TEST_RESULT, --- 分子检测结果

    CAST(NULL AS VARCHAR(20)) AS DIFFERENTIATION_DEGREE,
    CAST(NULL AS CHAR(1)) AS VASCULAR_INVASION,
    CAST(NULL AS CHAR(1)) AS LYMPHATIC_INVASION,
    CAST(NULL AS VARCHAR(50)) AS LYMPH_NODE_METASTASIS,
    CAST(NULL AS CHAR(1)) AS LYMPHOVASCULAR_INVASION,
    CAST(NULL AS CHAR(1)) AS PERINEURAL_INVASION,

    N'已发布' AS RECORD_STATUS, --- 记录状态

    CASE
        WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.PitayaFrozenResult))), '') IS NOT NULL
        THEN CONVERT(NVARCHAR(MAX), a.PitayaFrozenResult)

        WHEN NULLIF(LTRIM(RTRIM(a.FreezingID)), '') IS NOT NULL
          OR a.IsFroze = 1
          OR a.MedicalAdviceName LIKE N'%冰冻%'
          OR CONVERT(NVARCHAR(MAX), a.Rysj) LIKE N'%冰冻%'
        THEN
            CASE
                WHEN NULLIF(LTRIM(RTRIM(CONVERT(NVARCHAR(MAX), a.Zdyj))), '') IS NOT NULL
                THEN CONVERT(NVARCHAR(MAX), a.Zdyj)
                ELSE CONVERT(NVARCHAR(MAX), a.Rysj)
            END

        ELSE CAST(NULL AS NVARCHAR(MAX))
    END AS FROZEN_SECTION_RESULT, --- 术中冰冻结果

    ISNULL(a.SendDataTime, ISNULL(a.VerifyReportTime, ISNULL(a.ReportTime, a.Czrq))) AS SYSTEM_TIME --- 数据上传时间戳

FROM dbo.Pitaya a
WHERE a.Status = 512
  AND a.VerifyReportTime >= CONVERT(DATETIME, '2021-01-01', 120)
