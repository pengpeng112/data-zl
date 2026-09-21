
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ADMISSION_RECORD" ("ID", "ORG_CODE", "ORG_NAME", "ADMISSION_NUM", "ADMISSION_COUNT", "ADMISSION_ID", "NAME", "SEX_CODE", "SEX_NAME", "BORN_DATE", "AGE", "AGE_MONTH", "AGE_DAY", "AGE_HOUR", "OTHER_ID_TYPE", "OTHER_ID_TYPE_NAME", "OTHER_ID_NUM", "ID_NUM", "NATION_CODE", "NATION_NAME", "MARITAL_STATUS_CODE", "MARITAL_STATUS_NAME", "BORN_PLACE", "PROVINCE", "CITY", "COUNTY", "TOWN", "VILLAGE", "HOUSE_NUM", "OCCUPATION_CODE", "OCCUPATION_NAME", "WORKING_ORG", "ADMISSION_DATE", "RECORD_TIME", "CHIEF_COMPLAINT", "PRESENT_ILLNESS", "PAST_HISTORY", "PERSONAL_HISTORY", "MARITAL_HISTORY", "FAMILY_HISTORY", "INFECTION_HISTORY", "VACCINATION_HISTORY", "SURGERY_HISTORY", "BT_HISTORY", "ALLERGY_HISTORY", "MENSTRUATION_HISTORY", "THERAPEUTIC_TREATMENT", "FOUR_DIAGNOSIS", "SIGNS", "SPECIAL_EXAM", "DEP_CODE", "DEP_NAME", "HOS_DEP_NAME", "HOS_DEP_CODE", "DOCTOR_NAME", "DOCTOR_CODE", "WARD", "SICKBED_NUM", "REPRESENTOR_NAME", "LINKMAN_RELATION_CODE", "LINKMAN_RELATION_NAME", "IS_RELIABLE", "ATTENDING_DOCTOR_NAME", "ATTENDING_DOCTOR_CODE", "CHIEF_DOCTOR_NAME", "CHIEF_DOCTOR_CODE", "SIGNATURE_DATE", "IS_INFECTIOUS", "INPATIENT_TIMES", "CASE_NUM", "ADMISSION_TYPE_CODE", "ADMISSION_TYPE_NAME", "CITIZEN_ID", "EFFECTIVE_TIME", "STATUS", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "DEI", "NODE_CODE", "SYSTEM_TIME", "CZRK_ID", "WEIGHT", "TEMPERATURE", "BREATHING_RATE", "PULSE_RATE", "PRESSURE_H", "PRESSURE_L", "PHYSICAL_CHECK", "BED_CODE", "DOC_ID_NUM", "IN_HOS_ORG_CODE", "IN_HOS_ORG_NAME", "ADMISSION_BILL_DATE", "REGISTRATION_NUMBER", "IS_BMIDO", "CAMPUS_CODE", "CAMPUS_NAME", "SOCIAL_ID", "INSU_TYPE_CODE", "INSU_TYPE_DESC", "ADM_WAY_CODE", "ADM_WAY_NAME") AS 
  select '49557032X'||'|'||t.patient_id||'|'||t.visit_id as ID,--  内码  是 机构编码+唯一主键
       '49557032X' as  ORG_CODE,--  医院组织机构代码  是 医疗机构编码
       '山东省第二人民医院' as ORG_NAME,--  医院名称  是
       pmi.inp_no as ADMISSION_NUM,-- 住院号--患者 是 住院号不能为空
    t.visit_id    ADMISSION_COUNT ,--住院次
       t.patient_id||'|'||t.visit_id   as ADMISSION_ID,--  本次住院标识号--这次住院 是 某一次住院唯一标识号
       pmi.name as NAME,--  姓名  是
       decode(pmi.sex,'男','1','女','2','未知','0','9') as SEX_CODE,--  性别代码  是 值域：0未知，1男，2女，9不明
       decode(pmi.sex,'男','男','女','女','未知','未知','不明') as SEX_NAME,--  性别  是 请按照医院内部数据填写
       pmi.date_of_birth as BORN_DATE,-- 出生日期  是 字符型改为时间类型
      CASE
    WHEN pmi.date_of_birth IS NOT NULL
     AND t.admission_date_time IS NOT NULL
    THEN GREATEST(TRUNC(MONTHS_BETWEEN(t.admission_date_time, pmi.date_of_birth) / 12), 0)
    ELSE NULL
END AS AGE,

CASE
    WHEN pmi.date_of_birth IS NOT NULL
     AND t.admission_date_time IS NOT NULL
     AND MONTHS_BETWEEN(t.admission_date_time, pmi.date_of_birth) < 12
    THEN GREATEST(TRUNC(MONTHS_BETWEEN(t.admission_date_time, pmi.date_of_birth)), 0)
    ELSE 0
END AS AGE_MONTH,

CASE
    WHEN pmi.date_of_birth IS NOT NULL
     AND t.admission_date_time IS NOT NULL
     AND MONTHS_BETWEEN(t.admission_date_time, pmi.date_of_birth) < 1
    THEN GREATEST(TRUNC(t.admission_date_time - pmi.date_of_birth), 0)
    ELSE 0
END AS AGE_DAY,

CASE
    WHEN pmi.date_of_birth IS NOT NULL
     AND t.admission_date_time IS NOT NULL
     AND (t.admission_date_time - pmi.date_of_birth) < 1
    THEN GREATEST(TRUNC(24 * (t.admission_date_time - pmi.date_of_birth)), 1)
    ELSE 0
END AS AGE_HOUR,


       nvl((select zd.国标编码 from cda.cda_dictionary zd where zd.字典名称='身份证件类型代码' and zd.院标编码=pmi.ID_TYPE),'99') as OTHER_ID_TYPE,-- 身份证件类别代码  是 按照平台的值域进行填
       nvl((select zd.国标名称 from cda.cda_dictionary zd where zd.字典名称='身份证件类型代码' and zd.院标编码=pmi.ID_TYPE),'其他法定有效证件') as OTHER_ID_TYPE_NAME,--  身份证件类别名称  是
       pmi.id_no as OTHER_ID_NUM,--  其他身份证件号码
      nvl (pmi.id_no,'000000000000000000') as ID_NUM,--  身份证件号码  是 全部身份证件号码填写到该字段
       CASE REGEXP_REPLACE(TRIM(NVL(pmi.NATION,'')), '[[:space:]]+', '')
    WHEN '01' THEN '01' WHEN '1' THEN '01' WHEN '汉' THEN '01' WHEN '汉族' THEN '01' WHEN '汉族族' THEN '01'
    WHEN '02' THEN '02' WHEN '2' THEN '02' WHEN '蒙古' THEN '02' WHEN '蒙古族' THEN '02'
    WHEN '03' THEN '03' WHEN '3' THEN '03' WHEN '回' THEN '03' WHEN '回族' THEN '03'
    WHEN '04' THEN '04' WHEN '4' THEN '04' WHEN '藏' THEN '04' WHEN '藏族' THEN '04'
    WHEN '05' THEN '05' WHEN '5' THEN '05' WHEN '维吾尔' THEN '05' WHEN '维吾尔族' THEN '05'
    WHEN '06' THEN '06' WHEN '6' THEN '06' WHEN '苗' THEN '06' WHEN '苗族' THEN '06'
    WHEN '07' THEN '07' WHEN '7' THEN '07' WHEN '彝' THEN '07' WHEN '彝族' THEN '07'
    WHEN '08' THEN '08' WHEN '8' THEN '08' WHEN '壮' THEN '08' WHEN '壮族' THEN '08'
    WHEN '09' THEN '09' WHEN '9' THEN '09' WHEN '布依' THEN '09' WHEN '布依族' THEN '09'
    WHEN '10' THEN '10' WHEN '朝鲜' THEN '10' WHEN '朝鲜族' THEN '10'
    WHEN '11' THEN '11' WHEN '满' THEN '11' WHEN '满族' THEN '11'
    WHEN '12' THEN '12' WHEN '侗' THEN '12' WHEN '侗族' THEN '12'
    WHEN '13' THEN '13' WHEN '瑶' THEN '13' WHEN '瑶族' THEN '13'
    WHEN '14' THEN '14' WHEN '白' THEN '14' WHEN '白族' THEN '14'
    WHEN '15' THEN '15' WHEN '土家' THEN '15' WHEN '土家族' THEN '15'
    WHEN '16' THEN '16' WHEN '哈尼' THEN '16' WHEN '哈尼族' THEN '16'
    WHEN '17' THEN '17' WHEN '哈萨克' THEN '17' WHEN '哈萨克族' THEN '17'
    WHEN '18' THEN '18' WHEN '傣' THEN '18' WHEN '傣族' THEN '18'
    WHEN '19' THEN '19' WHEN '黎' THEN '19' WHEN '黎族' THEN '19'
    WHEN '20' THEN '20' WHEN '傈僳' THEN '20' WHEN '傈僳族' THEN '20'
    WHEN '21' THEN '21' WHEN '佤' THEN '21' WHEN '佤族' THEN '21'
    WHEN '22' THEN '22' WHEN '畲' THEN '22' WHEN '畲族' THEN '22'
    WHEN '23' THEN '23' WHEN '高山' THEN '23' WHEN '高山族' THEN '23'
    WHEN '24' THEN '24' WHEN '拉祜' THEN '24' WHEN '拉祜族' THEN '24'
    WHEN '25' THEN '25' WHEN '水' THEN '25' WHEN '水族' THEN '25'
    WHEN '26' THEN '26' WHEN '东乡' THEN '26' WHEN '东乡族' THEN '26'
    WHEN '27' THEN '27' WHEN '纳西' THEN '27' WHEN '纳西族' THEN '27'
    WHEN '28' THEN '28' WHEN '景颇' THEN '28' WHEN '景颇族' THEN '28'
    WHEN '29' THEN '29' WHEN '柯尔克孜' THEN '29' WHEN '柯尔克孜族' THEN '29' WHEN '柯尔柯孜族' THEN '29'
    WHEN '30' THEN '30' WHEN '土' THEN '30' WHEN '土族' THEN '30'
    WHEN '31' THEN '31' WHEN '达斡尔' THEN '31' WHEN '达斡尔族' THEN '31' WHEN '达尔族' THEN '31'
    WHEN '32' THEN '32' WHEN '仫佬' THEN '32' WHEN '仫佬族' THEN '32'
    WHEN '33' THEN '33' WHEN '羌' THEN '33' WHEN '羌族' THEN '33'
    WHEN '34' THEN '34' WHEN '布朗' THEN '34' WHEN '布朗族' THEN '34'
    WHEN '35' THEN '35' WHEN '撒拉' THEN '35' WHEN '撒拉族' THEN '35'
    WHEN '36' THEN '36' WHEN '毛南' THEN '36' WHEN '毛南族' THEN '36' WHEN '毛难族' THEN '36'
    WHEN '37' THEN '37' WHEN '仡佬' THEN '37' WHEN '仡佬族' THEN '37'
    WHEN '38' THEN '38' WHEN '锡伯' THEN '38' WHEN '锡伯族' THEN '38'
    WHEN '39' THEN '39' WHEN '阿昌' THEN '39' WHEN '阿昌族' THEN '39'
    WHEN '40' THEN '40' WHEN '普米' THEN '40' WHEN '普米族' THEN '40'
    WHEN '41' THEN '41' WHEN '塔吉克' THEN '41' WHEN '塔吉克族' THEN '41'
    WHEN '42' THEN '42' WHEN '怒' THEN '42' WHEN '怒族' THEN '42'
    WHEN '43' THEN '43' WHEN '乌孜别克' THEN '43' WHEN '乌孜别克族' THEN '43'
    WHEN '44' THEN '44' WHEN '俄罗斯' THEN '44' WHEN '俄罗斯族' THEN '44'
    WHEN '45' THEN '45' WHEN '鄂温克' THEN '45' WHEN '鄂温克族' THEN '45'
    WHEN '46' THEN '46' WHEN '德昂' THEN '46' WHEN '德昂族' THEN '46'
    WHEN '47' THEN '47' WHEN '保安' THEN '47' WHEN '保安族' THEN '47'
    WHEN '48' THEN '48' WHEN '裕固' THEN '48' WHEN '裕固族' THEN '48'
    WHEN '49' THEN '49' WHEN '京' THEN '49' WHEN '京族' THEN '49'
    WHEN '50' THEN '50' WHEN '塔塔尔' THEN '50' WHEN '塔塔尔族' THEN '50'
    WHEN '51' THEN '51' WHEN '独龙' THEN '51' WHEN '独龙族' THEN '51'
    WHEN '52' THEN '52' WHEN '鄂伦春' THEN '52' WHEN '鄂伦春族' THEN '52'
    WHEN '53' THEN '53' WHEN '赫哲' THEN '53' WHEN '赫哲族' THEN '53'
    WHEN '54' THEN '54' WHEN '门巴' THEN '54' WHEN '门巴族' THEN '54'
    WHEN '55' THEN '55' WHEN '珞巴' THEN '55' WHEN '珞巴族' THEN '55'
    WHEN '56' THEN '56' WHEN '基诺' THEN '56' WHEN '基诺族' THEN '56'
    ELSE '66'
END AS     NATION_CODE,-- 民族代码    按照平台值域填写
      CASE REGEXP_REPLACE(TRIM(NVL(pmi.NATION,'')), '[[:space:]]+', '')
    WHEN '01' THEN '汉族' WHEN '1' THEN '汉族' WHEN '汉' THEN '汉族' WHEN '汉族' THEN '汉族' WHEN '汉族族' THEN '汉族'
    WHEN '02' THEN '蒙古族' WHEN '2' THEN '蒙古族' WHEN '蒙古' THEN '蒙古族' WHEN '蒙古族' THEN '蒙古族'
    WHEN '03' THEN '回族' WHEN '3' THEN '回族' WHEN '回' THEN '回族' WHEN '回族' THEN '回族'
    WHEN '04' THEN '藏族' WHEN '4' THEN '藏族' WHEN '藏' THEN '藏族' WHEN '藏族' THEN '藏族'
    WHEN '05' THEN '维吾尔族' WHEN '5' THEN '维吾尔族' WHEN '维吾尔' THEN '维吾尔族' WHEN '维吾尔族' THEN '维吾尔族'
    WHEN '06' THEN '苗族' WHEN '6' THEN '苗族' WHEN '苗' THEN '苗族' WHEN '苗族' THEN '苗族'
    WHEN '07' THEN '彝族' WHEN '7' THEN '彝族' WHEN '彝' THEN '彝族' WHEN '彝族' THEN '彝族'
    WHEN '08' THEN '壮族' WHEN '8' THEN '壮族' WHEN '壮' THEN '壮族' WHEN '壮族' THEN '壮族'
    WHEN '09' THEN '布依族' WHEN '9' THEN '布依族' WHEN '布依' THEN '布依族' WHEN '布依族' THEN '布依族'
    WHEN '10' THEN '朝鲜族' WHEN '朝鲜' THEN '朝鲜族' WHEN '朝鲜族' THEN '朝鲜族'
    WHEN '11' THEN '满族' WHEN '满' THEN '满族' WHEN '满族' THEN '满族'
    WHEN '12' THEN '侗族' WHEN '侗' THEN '侗族' WHEN '侗族' THEN '侗族'
    WHEN '13' THEN '瑶族' WHEN '瑶' THEN '瑶族' WHEN '瑶族' THEN '瑶族'
    WHEN '14' THEN '白族' WHEN '白' THEN '白族' WHEN '白族' THEN '白族'
    WHEN '15' THEN '土家族' WHEN '土家' THEN '土家族' WHEN '土家族' THEN '土家族'
    WHEN '16' THEN '哈尼族' WHEN '哈尼' THEN '哈尼族' WHEN '哈尼族' THEN '哈尼族'
    WHEN '17' THEN '哈萨克族' WHEN '哈萨克' THEN '哈萨克族' WHEN '哈萨克族' THEN '哈萨克族'
    WHEN '18' THEN '傣族' WHEN '傣' THEN '傣族' WHEN '傣族' THEN '傣族'
    WHEN '19' THEN '黎族' WHEN '黎' THEN '黎族' WHEN '黎族' THEN '黎族'
    WHEN '20' THEN '傈僳族' WHEN '傈僳' THEN '傈僳族' WHEN '傈僳族' THEN '傈僳族'
    WHEN '21' THEN '佤族' WHEN '佤' THEN '佤族' WHEN '佤族' THEN '佤族'
    WHEN '22' THEN '畲族' WHEN '畲' THEN '畲族' WHEN '畲族' THEN '畲族'
    WHEN '23' THEN '高山族' WHEN '高山' THEN '高山族' WHEN '高山族' THEN '高山族'
    WHEN '24' THEN '拉祜族' WHEN '拉祜' THEN '拉祜族' WHEN '拉祜族' THEN '拉祜族'
    WHEN '25' THEN '水族' WHEN '水' THEN '水族' WHEN '水族' THEN '水族'
    WHEN '26' THEN '东乡族' WHEN '东乡' THEN '东乡族' WHEN '东乡族' THEN '东乡族'
    WHEN '27' THEN '纳西族' WHEN '纳西' THEN '纳西族' WHEN '纳西族' THEN '纳西族'
    WHEN '28' THEN '景颇族' WHEN '景颇' THEN '景颇族' WHEN '景颇族' THEN '景颇族'
    WHEN '29' THEN '柯尔克孜族' WHEN '柯尔克孜' THEN '柯尔克孜族' WHEN '柯尔克孜族' THEN '柯尔克孜族' WHEN '柯尔柯孜族' THEN '柯尔克孜族'
    WHEN '30' THEN '土族' WHEN '土' THEN '土族' WHEN '土族' THEN '土族'
    WHEN '31' THEN '达斡尔族' WHEN '达斡尔' THEN '达斡尔族' WHEN '达斡尔族' THEN '达斡尔族' WHEN '达尔族' THEN '达斡尔族'
    WHEN '32' THEN '仫佬族' WHEN '仫佬' THEN '仫佬族' WHEN '仫佬族' THEN '仫佬族'
    WHEN '33' THEN '羌族' WHEN '羌' THEN '羌族' WHEN '羌族' THEN '羌族'
    WHEN '34' THEN '布朗族' WHEN '布朗' THEN '布朗族' WHEN '布朗族' THEN '布朗族'
    WHEN '35' THEN '撒拉族' WHEN '撒拉' THEN '撒拉族' WHEN '撒拉族' THEN '撒拉族'
    WHEN '36' THEN '毛南族' WHEN '毛南' THEN '毛南族' WHEN '毛南族' THEN '毛南族' WHEN '毛难族' THEN '毛南族'
    WHEN '37' THEN '仡佬族' WHEN '仡佬' THEN '仡佬族' WHEN '仡佬族' THEN '仡佬族'
    WHEN '38' THEN '锡伯族' WHEN '锡伯' THEN '锡伯族' WHEN '锡伯族' THEN '锡伯族'
    WHEN '39' THEN '阿昌族' WHEN '阿昌' THEN '阿昌族' WHEN '阿昌族' THEN '阿昌族'
    WHEN '40' THEN '普米族' WHEN '普米' THEN '普米族' WHEN '普米族' THEN '普米族'
    WHEN '41' THEN '塔吉克族' WHEN '塔吉克' THEN '塔吉克族' WHEN '塔吉克族' THEN '塔吉克族'
    WHEN '42' THEN '怒族' WHEN '怒' THEN '怒族' WHEN '怒族' THEN '怒族'
    WHEN '43' THEN '乌孜别克族' WHEN '乌孜别克' THEN '乌孜别克族' WHEN '乌孜别克族' THEN '乌孜别克族'
    WHEN '44' THEN '俄罗斯族' WHEN '俄罗斯' THEN '俄罗斯族' WHEN '俄罗斯族' THEN '俄罗斯族'
    WHEN '45' THEN '鄂温克族' WHEN '鄂温克' THEN '鄂温克族' WHEN '鄂温克族' THEN '鄂温克族'
    WHEN '46' THEN '德昂族' WHEN '德昂' THEN '德昂族' WHEN '德昂族' THEN '德昂族'
    WHEN '47' THEN '保安族' WHEN '保安' THEN '保安族' WHEN '保安族' THEN '保安族'
    WHEN '48' THEN '裕固族' WHEN '裕固' THEN '裕固族' WHEN '裕固族' THEN '裕固族'
    WHEN '49' THEN '京族' WHEN '京' THEN '京族' WHEN '京族' THEN '京族'
    WHEN '50' THEN '塔塔尔族' WHEN '塔塔尔' THEN '塔塔尔族' WHEN '塔塔尔族' THEN '塔塔尔族'
    WHEN '51' THEN '独龙族' WHEN '独龙' THEN '独龙族' WHEN '独龙族' THEN '独龙族'
    WHEN '52' THEN '鄂伦春族' WHEN '鄂伦春' THEN '鄂伦春族' WHEN '鄂伦春族' THEN '鄂伦春族'
    WHEN '53' THEN '赫哲族' WHEN '赫哲' THEN '赫哲族' WHEN '赫哲族' THEN '赫哲族'
    WHEN '54' THEN '门巴族' WHEN '门巴' THEN '门巴族' WHEN '门巴族' THEN '门巴族'
    WHEN '55' THEN '珞巴族' WHEN '珞巴' THEN '珞巴族' WHEN '珞巴族' THEN '珞巴族'
    WHEN '56' THEN '基诺族' WHEN '基诺' THEN '基诺族' WHEN '基诺族' THEN '基诺族'
    ELSE '其他'
END AS     NATION_NAME,-- 民族
      CASE REGEXP_REPLACE(TRIM(NVL(pmi.MARITAL_STATUS,'')), '[[:space:]]+', '')
    WHEN '1' THEN '10'
    WHEN '未婚' THEN '10'

    WHEN '2' THEN '20'
    WHEN '已婚' THEN '20'
    WHEN '再婚' THEN '20'

    WHEN '3' THEN '30'
    WHEN '丧偶' THEN '30'

    WHEN '4' THEN '40'
    WHEN '离婚' THEN '40'
    WHEN '离异' THEN '40'

    WHEN '0' THEN '90'
    WHEN '5' THEN '90'
    WHEN '9' THEN '90'
    WHEN '其他' THEN '90'
    WHEN '' THEN '90'

    ELSE '90'
END    as MARITAL_STATUS_CODE,-- 婚姻状况代码    按照平台值域填写
      CASE REGEXP_REPLACE(TRIM(NVL(pmi.MARITAL_STATUS,'')), '[[:space:]]+', '')
    WHEN '1' THEN '未婚'
    WHEN '未婚' THEN '未婚'

    WHEN '2' THEN '已婚'
    WHEN '已婚' THEN '已婚'
    WHEN '再婚' THEN '已婚'

    WHEN '3' THEN '丧偶'
    WHEN '丧偶' THEN '丧偶'

    WHEN '4' THEN '离婚'
    WHEN '离婚' THEN '离婚'
    WHEN '离异' THEN '离婚'

    WHEN '0' THEN '未说明的婚姻状况'
    WHEN '5' THEN '未说明的婚姻状况'
    WHEN '9' THEN '未说明的婚姻状况'
    WHEN '其他' THEN '未说明的婚姻状况'
    WHEN '' THEN '未说明的婚姻状况'

    ELSE '未说明的婚姻状况'
END   as MARITAL_STATUS_NAME,-- 婚姻状况
       pmi.BIRTH_PLACE as BORN_PLACE,--  出生地
       pmi.PREADD_PROVINCE as PROVINCE,--  居住地址-省（自治区、直辖市）
       pmi.PREADD_CITY as CITY,--  居住地址-市（地区、州）
       pmi.PREADD_COUNTY as COUNTY,--  居住地址-县（区）
       '' as TOWN,--  居住地址-乡（镇、街道办事处）
       '' as VILLAGE,-- 居住地址-村(街、路、弄等）
       pmi.Mailing_Address as HOUSE_NUM,-- 居住地址-门牌号码 是
       nvl((select zd.国标编码 from cda.cda_dictionary zd where zd.字典名称='职业代码' and zd.院标编码=pmi.OCCUPATION),'51') as OCCUPATION_CODE,-- 职业代码    按照平台值域填写
       nvl((select zd.国标名称 from cda.cda_dictionary zd where zd.字典名称='职业代码' and zd.院标编码=pmi.OCCUPATION),'自由职业者') as OCCUPATION_NAME,-- 职业
      pmi.UNIT_IN_CONTRACT  as WORKING_ORG,-- 单位名称
       t.admission_date_time as ADMISSION_DATE,--  入院时间  是
      CASE
    WHEN SUBSTR(
           REPLACE(REPLACE(
             REGEXP_SUBSTR(
               DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
               '记录[[:space:]]*日期[[:space:]]*[:：][[:space:]]*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}:[0-9]{2})',
               1, 1, 'n', 1
             ),
           '/', '-'), '.', '-'),
         1, 16) IS NOT NULL
     AND REGEXP_LIKE(
           SUBSTR(
             REPLACE(REPLACE(
               REGEXP_SUBSTR(
                 DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
                 '记录[[:space:]]*日期[[:space:]]*[:：][[:space:]]*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}:[0-9]{2})',
                 1, 1, 'n', 1
               ),
             '/', '-'), '.', '-'),
           1, 16),
           '^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}[[:space:]]+([01]?[0-9]|2[0-3]):[0-5][0-9]$'
         )
    THEN TO_DATE(
           SUBSTR(
             REPLACE(REPLACE(
               REGEXP_SUBSTR(
                 DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
                 '记录[[:space:]]*日期[[:space:]]*[:：][[:space:]]*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}:[0-9]{2})',
                 1, 1, 'n', 1
               ),
             '/', '-'), '.', '-'),
           1, 16),
           'yyyy-mm-dd hh24:mi'
         )
    ELSE t.ADMISSION_DATE_TIME
END AS RECORD_TIME,-- 记录时间    字符型改为时间类型
       NVL(
         NULLIF(TRIM(SUBSTR(NVL(DBMS_LOB.SUBSTR(t3.zs,1000,1),
           REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '主诉', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '主诉', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '主  诉', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '主  诉', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '主     诉', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '主     诉', 1, 1)
                ELSE 1
            END
        ),
             '主[[:space:]]*诉[[:space:]]*[:：][[:space:]]*(.*?)(现[[:space:]]*病[[:space:]]*史[[:space:]]*[:：])',
             1,1,'n',1)
         ),1,1000)),''),
         '-'
       ) as CHIEF_COMPLAINT,-- 主诉  是
       NVL(
         NULLIF(TRIM(SUBSTR(NVL(DBMS_LOB.SUBSTR(t3.xbs,1000,1),
           REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '现病史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '现病史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '现 病 史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '现 病 史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '现  病  史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '现  病  史', 1, 1)
                ELSE 1
            END
        ),
             '现[[:space:]]*病[[:space:]]*史[[:space:]]*[:：][[:space:]]*(.*?)(既[[:space:]]*往[[:space:]]*史[[:space:]]*[:：])',
             1,1,'n',1)
         ),1,1000)),''),
         '-'
       ) as PRESENT_ILLNESS,-- 现病史 是
       NVL(
         NULLIF(TRIM(SUBSTR(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1)
                ELSE 1
            END
        ),
           '既[[:space:]]*往[[:space:]]*史[[:space:]]*[:：][[:space:]]*(.*?)(个人史、婚育史|个人史|月经及婚育史|婚育史|家族史|体[[:space:]]*格[[:space:]]*检[[:space:]]*查)',
           1,1,'n',1),1,1000)),''),
         '-'
       ) as PAST_HISTORY,--  既往史（包括外伤） 是
       NVL(
         NULLIF(TRIM(SUBSTR(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '个人史、婚育史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '个人史、婚育史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '个人史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '个人史', 1, 1)
                ELSE 1
            END
        ),
           '(个人史、婚育史|个人史)[[:space:]]*[:：][[:space:]]*(.*?)(月经及婚育史|婚育史|家族史|体[[:space:]]*格[[:space:]]*检[[:space:]]*查)',
           1,1,'n',2),1,1000)),''),
         '-'
       ) as PERSONAL_HISTORY,--  个人史 是
       NVL(
         NULLIF(TRIM(SUBSTR(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '月经及婚育史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '月经及婚育史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '婚育史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '婚育史', 1, 1)
                ELSE 1
            END
        ),
           '(个人史、婚育史|月经及婚育史|婚育史)[[:space:]]*[:：][[:space:]]*(.*?)(家族史|体[[:space:]]*格[[:space:]]*检[[:space:]]*查)',
           1,1,'n',2),1,1000)),''),
         '-'
       ) as MARITAL_HISTORY,-- 婚育史 是
       NVL(
         NULLIF(TRIM(SUBSTR(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '家族史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '家族史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '家 族 史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '家 族 史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '家  族  史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '家  族  史', 1, 1)
                ELSE 1
            END
        ),
           '家[[:space:]]*族[[:space:]]*史[[:space:]]*[:：][[:space:]]*(.*?)(体[[:space:]]*格[[:space:]]*检[[:space:]]*查|辅[[:space:]]*助[[:space:]]*检[[:space:]]*查|初步诊断|入院诊断|病史记录属实)',
           1,1,'n',1),1,1000)),''),
         '-'
       ) as FAMILY_HISTORY,--  家族史 是
       NVL(
         NULLIF(TRIM(SUBSTR(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1)
                ELSE 1
            END
        ),
           '([^。；;[:cntrl:]]*传染病史[^。；;[:cntrl:]]*[。；;]?)',
           1,1,'n',1),1,1000)),''),
         '-'
       ) as INFECTION_HISTORY,-- 传染病史  是
       NVL(
         NULLIF(TRIM(SUBSTR(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1)
                ELSE 1
            END
        ),
           '(预防接种史[[:space:]]*[:：]?[[:space:]]*[^。；;[:cntrl:]]*[。；;]?)',
           1,1,'n',1),1,1000)),''),
         '-'
       ) as VACCINATION_HISTORY,-- 预防接种史 是
       NVL(
         NULLIF(TRIM(SUBSTR(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1)
                ELSE 1
            END
        ),
           '([^。；;[:cntrl:]]*手术[^。；;[:cntrl:]]*史[^。；;[:cntrl:]]*[。；;]?)',
           1,1,'n',1),1,1000)),''),
         '-'
       ) as SURGERY_HISTORY,-- 手术史 是
       NVL(
         NULLIF(TRIM(SUBSTR(NVL(DBMS_LOB.SUBSTR(t3.sxs,1000,1),
           REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1)
                ELSE 1
            END
        ),
             '([^。；;[:cntrl:]]*输血史[^。；;[:cntrl:]]*[。；;]?)',
             1,1,'n',1)
         ),1,1000)),''),
         '-'
       ) as BT_HISTORY,--  输血史 是
       NVL(
         NULLIF(TRIM(SUBSTR(NVL(DBMS_LOB.SUBSTR(t3.gms,1000,1),
           REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1)
                ELSE 1
            END
        ),
             '([^。；;[:cntrl:]]*(过敏史|药物过敏|食物及药物过敏)[^。；;[:cntrl:]]*[。；;]?)',
             1,1,'n',1)
         ),1,1000)),''),
         '-'
       ) as ALLERGY_HISTORY,-- 过敏史 是
       NVL(
         NULLIF(TRIM(SUBSTR(NVL(t3.yjs,
           REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '月经及婚育史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '月经及婚育史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '婚育史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '婚育史', 1, 1)
                ELSE 1
            END
        ),
             '(月经及婚育史|月经史)[[:space:]]*[:：][[:space:]]*(.*?)(家族史|体[[:space:]]*格[[:space:]]*检[[:space:]]*查)',
             1,1,'n',2)
         ),1,1000)),''),
         '-'
       ) as MENSTRUATION_HISTORY,--  月经史 是
       t3.zzzf as THERAPEUTIC_TREATMENT,-- 治则治法
       nvl(t3.zyszgcjg,'-') as FOUR_DIAGNOSIS,--  中医“四诊”观察结果
       NVL(
         NULLIF(TRIM(SUBSTR(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1)
                ELSE 1
            END
        ),
           '体[[:space:]]*格[[:space:]]*检[[:space:]]*查[[:space:]]*(.*?)(专科情况|专科检查|辅[[:space:]]*助[[:space:]]*检[[:space:]]*查|初步诊断|入院诊断)',
           1,1,'n',1),1,1000)),''),
         '-'
       ) as SIGNS,-- 体征  是
       NVL(
         NULLIF(TRIM(SUBSTR(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '专科情况', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '专科情况', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '专科检查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '专科检查', 1, 1)
                ELSE 1
            END
        ),
           '(专科情况|专科检查)[[:space:]]*[:：]?[[:space:]]*(.*?)(辅[[:space:]]*助[[:space:]]*检[[:space:]]*查|初步诊断|入院诊断)',
           1,1,'n',2),1,1000)),''),
         '-'
       ) as SPECIAL_EXAM,--  专项检查
       (select qmpt_code from his.dept_dict where dept_code = nvl(t.dept_discharge_from,t.DEPT_ADMISSION_TO))   as DEP_CODE,--  科室代码  是 按照平台值域填写
       (select ks.qmpt_name from his.dept_dict ks where ks.dept_code=nvl(t.dept_discharge_from,t.DEPT_ADMISSION_TO)) as DEP_NAME,--  科室名称  是


       (select ks.dept_name from his.dept_dict ks where ks.dept_code=nvl(t.dept_discharge_from,t.DEPT_ADMISSION_TO)) as HOS_DEP_NAME,-- 院内科室名称 是
       nvl(t.dept_discharge_from,t.DEPT_ADMISSION_TO) as HOS_DEP_CODE,-- 院内科室代码 是
         (select yg.name from his.staff_dict yg where yg.emp_no=t.ATTENDING_DOCTOR) as DOCTOR_NAME,-- 医师姓名
       t.ATTENDING_DOCTOR as DOCTOR_CODE,-- 医生代码


       nvl(t.Discharge_Ward_Code,(select aa.WARD_CODE from his.pats_in_hospital aa where aa.patient_id=t.patient_id and aa.visit_id=t.visit_id)) as WARD,--  病室（区） 是
       nvl(t.DISCHARGE_BED_NO,(select aa.bed_no from his.pats_in_hospital aa where aa.patient_id=t.patient_id and aa.visit_id=t.visit_id)) as SICKBED_NUM,-- 床号  是
       NVL(
         NULLIF(TRIM(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
           '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',
           1,1,'n',1)),''),
         '-'
       ) as REPRESENTOR_NAME,--  病史陈述者姓名
    CASE
  /* 0 本人或户主：如“本人”“患者本人”“本人及配偶”，优先按本人处理 */
  WHEN REGEXP_LIKE(
         REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
           '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),
         '本人|患者本人'
       ) THEN '0'

  /* 1 配偶 */
  WHEN REGEXP_LIKE(
         REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
           '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),
         '配偶|丈夫|妻子|妻|夫|老伴|爱人'
       ) THEN '1'

  /* 2 子 */
  WHEN REGEXP_LIKE(
         REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
           '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),
         '儿子|之子|其子|患儿父亲|父亲陪同'
       ) THEN '2'

  /* 3 女 */
  WHEN REGEXP_LIKE(
         REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
           '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),
         '女儿|之女|其女'
       ) THEN '3'

  /* 4 孙子、孙女、外孙子、外孙女 */
  WHEN REGEXP_LIKE(
         REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
           '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),
         '孙子|孙女|外孙|外孙子|外孙女'
       ) THEN '4'

  /* 5 父母 */
  WHEN REGEXP_LIKE(
         REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
           '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),
         '父亲|母亲|父母|患儿母亲|患儿父亲'
       ) THEN '5'

  /* 6 祖父母或外祖父母 */
  WHEN REGEXP_LIKE(
         REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
           '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),
         '祖父|祖母|爷爷|奶奶|外祖父|外祖母|外公|外婆'
       ) THEN '6'

  /* 7 兄、弟、姐、妹 */
  WHEN REGEXP_LIKE(
         REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
           '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),
         '哥哥|弟弟|姐姐|妹妹|兄|弟|姐|妹|兄弟|姐妹'
       ) THEN '7'

  /* 8 其它：家属、亲属、陪人等不明确关系 */
  WHEN REGEXP_LIKE(
         REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
           '病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),
         '家属|亲属|陪人|陪护|监护人|朋友|同事|单位|邻居'
       ) THEN '8'

  ELSE '8'
END    as LINKMAN_RELATION_CODE,-- 病史陈述者关系代码   按照平台的值域进行填写
       CASE
         WHEN REGEXP_LIKE(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),'病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),'本人') THEN '本人'
         WHEN REGEXP_LIKE(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),'病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),'配偶|妻|夫') THEN '配偶'
         WHEN REGEXP_LIKE(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),'病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),'母亲|患儿母亲') THEN '母亲'
         WHEN REGEXP_LIKE(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),'病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),'父亲|患儿父亲') THEN '父亲'
         WHEN REGEXP_LIKE(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),'病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),'家属') THEN '家属'
         ELSE NVL(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),'病史陈述者[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',1,1,'n',1),'-')
       END as LINKMAN_RELATION_NAME,-- 病史陈述者关系
       CASE WHEN DBMS_LOB.INSTR(t4.段落内容,'病史记录属实',1,1) > 0 THEN '1' ELSE '' END as IS_RELIABLE,-- 陈述内容可靠标志

       (select yg.name from his.staff_dict yg where yg.emp_no=t.ATTENDING_DOCTOR) as ATTENDING_DOCTOR_NAME,-- 主治医师姓名  是
     nvl(  (select id_no from his.staff_dict e where e.emp_no = t.ATTENDING_DOCTOR) ,'000000000000000000')  as ATTENDING_DOCTOR_CODE,-- 主治医生代码  是
       (select yg.name from his.staff_dict yg where yg.emp_no=t.practice_doctor_of_graduate) as CHIEF_DOCTOR_NAME,-- 主任医师姓名
       (select id_no from his.staff_dict e where e.emp_no = t.practice_doctor_of_graduate)  as CHIEF_DOCTOR_CODE,-- 主任医生代码
       t1.DOC_TITLE_TIME as SIGNATURE_DATE,--  签名日期时间
       CASE
         WHEN REGEXP_LIKE(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1)
                ELSE 1
            END
        ), '(否认[^。；;]*(传染病|肝炎|结核|新冠)|无[^。；;]*(传染病|肝炎|结核|新冠))') THEN '0'
         WHEN REGEXP_LIKE(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既往史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既 往 史', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '既  往  史', 1, 1)
                ELSE 1
            END
        ), '(病毒性肝炎|结核|新冠肺炎|传染病史[[:space:]]*[:：][[:space:]]*有)') THEN '1'
         ELSE ''
       END as IS_INFECTIOUS,-- 患者传染性标志
       t.visit_id as INPATIENT_TIMES,-- 住院次数  是 必须为正整数
       pmi.inp_no as CASE_NUM,--  病案号 是
       nvl((select zd.国标编码 from cda.cda_dictionary zd where zd.字典名称='入院途径代码' and zd.院标编码=pmi.PATIENT_CLASS),'9') as ADMISSION_TYPE_CODE,-- 入院途径代码  是
       nvl((select zd.国标名称 from cda.cda_dictionary zd where zd.字典名称='入院途径代码' and zd.院标编码=pmi.PATIENT_CLASS),'其他') as ADMISSION_TYPE_NAME,-- 入院途径  是
       pmi.id_no as CITIZEN_ID,--  个人内码
      CASE
    WHEN SUBSTR(
           REPLACE(REPLACE(
             REGEXP_SUBSTR(
               DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
               '记录[[:space:]]*日期[[:space:]]*[:：][[:space:]]*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}:[0-9]{2})',
               1, 1, 'n', 1
             ),
           '/', '-'), '.', '-'),
         1, 16) IS NOT NULL
     AND REGEXP_LIKE(
           SUBSTR(
             REPLACE(REPLACE(
               REGEXP_SUBSTR(
                 DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
                 '记录[[:space:]]*日期[[:space:]]*[:：][[:space:]]*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}:[0-9]{2})',
                 1, 1, 'n', 1
               ),
             '/', '-'), '.', '-'),
           1, 16),
           '^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}[[:space:]]+([01]?[0-9]|2[0-3]):[0-5][0-9]$'
         )
    THEN TO_DATE(
           SUBSTR(
             REPLACE(REPLACE(
               REGEXP_SUBSTR(
                 DBMS_LOB.SUBSTR(t4.段落内容, 1000, 1),
                 '记录[[:space:]]*日期[[:space:]]*[:：][[:space:]]*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}:[0-9]{2})',
                 1, 1, 'n', 1
               ),
             '/', '-'), '.', '-'),
           1, 16),
           'yyyy-mm-dd hh24:mi'
         )
    ELSE t.ADMISSION_DATE_TIME
END     as EFFECTIVE_TIME,--  活动发生时间
       '1' as STATUS,--  卡片状态
       SYSDATE as CREATED_AT,--  创建时间
       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）
       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS：向平台补充历史遗漏数据
       '' as DEI,-- 数据交换标识符
       '' as NODE_CODE,-- 节点标识符
       sysdate as SYSTEM_TIME,-- 数据上传时间戳 是 填写数据上传时间
       pmi.id_no as CZRK_ID,-- 常住人口ID
       TO_NUMBER(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1)
                ELSE 1
            END
        ),
         '(体重|WT|Wt|weight)[[:space:]]*[:：]?[[:space:]]*([0-9]{1,3}([.][0-9]+)?)',
         1,1,'in',2)) as WEIGHT,--  体重（kg）
       TO_NUMBER(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1)
                ELSE 1
            END
        ),
         'T[[:space:]]*[:：][[:space:]]*([0-9]{1,2}([.][0-9]+)?)',
         1,1,'in',1)) as TEMPERATURE,-- 体温（℃）
       TO_NUMBER(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1)
                ELSE 1
            END
        ),
         '(^|[[:space:]])R[[:space:]]*[:：][[:space:]]*R?([0-9]{1,3})',
         1,1,'in',2)) as BREATHING_RATE,--  呼吸频率?
       TO_NUMBER(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1)
                ELSE 1
            END
        ),
         '(^|[[:space:]])P[[:space:]]*[:：][[:space:]]*([0-9]{1,3})',
         1,1,'in',2)) as PULSE_RATE,--  脉率（次/分）
       TO_NUMBER(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1)
                ELSE 1
            END
        ),
         'B[pP][[:space:]]*[:：][[:space:]]*([0-9]{2,3})[[:space:]]*/[[:space:]]*[0-9]{2,3}',
         1,1,'in',1)) as PRESSURE_H,--  收缩压（mmHg）
       TO_NUMBER(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1)
                ELSE 1
            END
        ),
         'B[pP][[:space:]]*[:：][[:space:]]*[0-9]{2,3}[[:space:]]*/[[:space:]]*([0-9]{2,3})',
         1,1,'in',1)) as PRESSURE_L,--  舒张压（mmHg）
       NVL(
         NULLIF(TRIM(SUBSTR(REGEXP_SUBSTR(DBMS_LOB.SUBSTR(t4.段落内容, 1000,
            CASE
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体格检查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体   格   检   查', 1, 1)
                WHEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1) > 0 THEN DBMS_LOB.INSTR(t4.段落内容, '体 格 检 查', 1, 1)
                ELSE 1
            END
        ),
           '体[[:space:]]*格[[:space:]]*检[[:space:]]*查[[:space:]]*(.*?)(专科情况|专科检查|辅[[:space:]]*助[[:space:]]*检[[:space:]]*查|初步诊断|入院诊断)',
           1,1,'n',1),1,1000)),''),
         '-'
       ) as PHYSICAL_CHECK,--  体格检查
       nvl(t.DISCHARGE_BED_NO,(select aa.bed_no from his.pats_in_hospital aa where aa.patient_id=t.patient_id and aa.visit_id=t.visit_id)) as BED_CODE,--  床位代码  是
       (select id_no from his.staff_dict e where e.emp_no = t.ATTENDING_DOCTOR) as DOC_ID_NUM,--  医师身份证号码
       '49557032X' as IN_HOS_ORG_CODE,-- 入院医疗机构编号
       '山东省第二人民医院' as IN_HOS_ORG_NAME,-- 入院医疗机构名称
t.Admission_Date_Time as ADMISSION_BILL_DATE,-- 开具住院票时间 是 yyyymmdd hh24miss
'49557032X' as REGISTRATION_NUMBER,-- 医疗机构执业许可证登记号  是 通过比对国家数据集增加的数据项
'1' as IS_BMIDO,--  是否基本医保定点机构  是 通过比对国家数据集增加的数据项
'49557032X' as CAMPUS_CODE,-- 院区代码  是 通过比对国家数据集增加的数据项
'山东省第二人民医院' as CAMPUS_NAME,-- 院区名称  是 通过比对国家数据集增加的数据项
pmi.id_no as SOCIAL_ID,-- 社保卡号    通过比对国家数据集增加的数据项
nvl((select zd.国标编码 from cda.cda_dictionary zd where zd.字典名称='医疗付费方式代码' and zd.院标名称=t.CHARGE_TYPE),'99') as INSU_TYPE_CODE,--  医保类别编码  是 通过比对国家数据集增加的数据项
nvl((select zd.国标名称 from cda.cda_dictionary zd where zd.字典名称='医疗付费方式代码' and zd.院标名称=t.CHARGE_TYPE),'其他') as INSU_TYPE_DESC,--  医保类别名称  是 通过比对国家数据集增加的数据项
nvl((select zd.国标编码 from cda.cda_dictionary zd where zd.字典名称='入院途径代码' and zd.院标编码=pmi.PATIENT_CLASS),'9') as ADM_WAY_CODE,--  入院途径编码  是 通过比对国家数据集增加的数据项
nvl((select zd.国标名称 from cda.cda_dictionary zd where zd.字典名称='入院途径代码' and zd.院标编码=pmi.PATIENT_CLASS),'其他') as ADM_WAY_NAME -- 入院途径名称  是 通过比对国家数据集增加的数据项
from his.pat_visit t
LEFT JOIN his.PAT_MASTER_INDEX pmi ON t.PATIENT_ID = pmi.PATIENT_ID
left join mtl.EPR_INPATIENT_DOCINDEX tt on tt.P_INPATIENT_NO=pmi.inp_no and tt.P_INPATIENT_TIMES=t.visit_id --患者信息
LEFT JOIN mtl.EPR_INPATIENT t1 on tt.UHID=t1.UHID
left join mtl.EMRSD34 T3 ON T3.段落编号=T1.ID
Join MTL.EMRSD_CONTENT t4 On t4.UHID=tt.UHID and t4.段落编号=T1.ID

where  (t1.DOC_TYPE_NAME like '%入院记录%' or t1.doc_title  like '%入院记录%' )   and t.discharge_date_time>=to_date('2021-01-01','yyyy-mm-dd')
and t.discharge_date_time<to_date('2025-01-01','yyyy-mm-dd')
