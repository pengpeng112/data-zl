
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ICH" ("ID", "HOME_TYPE_CODE", "HOME_TYPE_NAME", "ORG_CODE", "ORG_NAME", "INPATIENT_TIMES", "CHARGE_MODE_CODE", "CHARGE_MODE_NAME", "TOTAL_AMOUNT", "CASE_NUM", "BALANCE_STATE", "ADMISSION_NUM", "ADMISSION_ID", "NAME", "SEX_CODE", "SEX_NAME", "BORN_DATE", "AGE", "AGE_MONTH", "AGE_DAY", "AGE_HOUR", "MARITAL_STATUS_CODE", "MARITAL_STATUS_NAME", "OCCUPATION_CODE", "OCCUPATION_NAME", "NATION_CODE", "NATION_NAME", "COUNTRY_CODE", "COUNTRY_NAME", "OTHER_ID_TYPE", "OTHER_ID_NAME", "OTHER_ID_NUM", "ID_NUM", "WORKING_ORG", "TEL", "LINKMAN_TEL", "WORK_TEL", "BORN_ADDRESS_PROVINCE", "BORN_ADDRESS_CITY", "BORN_ADDRESS_COUNTY", "CURRENT_ADDRESS_PROVINCE", "CURRENT_ADDRESS_CITY", "CURRENT_ADDRESS_COUNTY", "CURRENT_ADDRESS_TOWN", "CURRENT_ADDRESS_VILLAGE", "CURRENT_ADDRESS_HN", "CURRENT_ADDRESS_ZP", "HRA_ADDRESS_PROVINCE", "HRA_ADDRESS_CITY", "HRA_ADDRESS_COUNTY", "HRA_ADDRESS_TOWN", "HRA_ADDRESS_VILLAGE", "HRA_ADDRESS_HN", "HRA_ADDRESS_ZP", "WORK_ADDRESS", "WORK_ZP", "LINKMAN_ADDRESS", "LINKMAN_NAME", "RBT_CONTACT_CODE", "RBT_CONTACT_NAME", "ADMISSION_DATE", "DISCHARGE_DATE", "INPATIENT_DAY", "INJURY_CAUSE", "CASE_QUALITY_CODE", "CASE_QUALITY_NAME", "IS_AUTOPSY", "BLOOD_ABO_CODE", "BLOOD_ABO_NAME", "BLOOD_RH_CODE", "BLOOD_RH_NAME", "RECORD_DATE", "HEALTH_RECORD_CODE", "ADMISSION_TYPE_CODE", "ADMISSION_TYPE_NAME", "BIRTH_BODY_WEIGHT", "ADMISSION_BODY_WEIGHT", "PATHOLOGY_NUM", "IS_ALLERGY", "ALLERGY_N", "DISCHARGE_TYPE_CODE", "DISCHARGE_TYPE_NAME", "RECEIVE_ORG_NAME", "IS_READMISSION", "READMISSION_PURPOSE", "PRIOR_COMA_DAYS", "PRIOR_COMA_HOURS", "PRIOR_COMA_MINUTES", "AFTER_COMA_DAYS", "AFTER_COMA_HOURS", "AFTER_COMA_MINUTES", "QC_DATE", "TREATE_TYPE_CODE", "TREATE_TYPE_NAME", "PATHWAY_TYPE_CODE", "PATHWAY_TYPE_NAME", "IS_USE_HERB", "IS_USE_EQUIP", "IS_USE_TECH", "IS_DIALECTIAL_NURSING", "TOTAL_AMOUNT_STP", "SAVE_TIMES", "SAVE_SUCCESS_TIMES", "IS_DEATH", "INFUSION_REACTION_MARK", "BT_REACTION_MARK", "OPERATION_COMPLICATIONS", "IS_INFECTION", "IS_INFECTION_REPORT", "IS_CRITICAL", "IS_EMERGENCY", "DEATH_TIME", "DEATH_CAUSE", "ROOT_DEATH_CODE", "INFECTIOUSNESS_TIMES", "INSURANCE_NUM", "IN_CONDITION_CODE", "IN_CONDITION_NAME", "RED_BLOOD_CELL", "PLATELET", "PLASMA", "WHOLE_BLOOD", "OTHER_BLOOD", "DIRECTOR_CODE", "DIRECTOR_NAME", "CHIEF_PHYSICIAN_CODE", "CHIEF_PHYSICIAN_NAME", "ATTENDING_PHYSICIAN_CODE", "ATTENDING_PHYSICIAN_NAME", "RESIDENT_CODE", "RESIDENT_NAME", "NURSE_CODE", "NURSE_NAME", "REFRESHER_DOCTORS_CODE", "REFRESHER_DOCTORS_NAME", "INTERN_CODE", "INTERN_NAME", "CODER_CODE", "CODER_NAME", "CODER_IDNUM", "QCD_CODE", "QCD_NAME", "QCN_CODE", "QCN_NAME", "DEP_CODE", "DEP_NAME", "IN_WORD", "TDEP_CODE", "TDEP_NAME", "ODEP_CODE", "ODEP_NAME", "OUT_WORD", "CITIZEN_ID", "EFFECTIVE_TIME", "STATUS", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "DEI", "NODE_CODE", "CASE_ID", "CASE_ORG_CODE", "SYSTEM_TIME", "CZRK_ID", "INJURY_CAUSE_CODE", "NURSING_LEVEL_CODE", "NURSING_LEVEL_TIME", "NURSING_LEVEL_UNIT", "MAIN_DOC_NAME", "SINGLE_DISEASE_MG_CODE", "PATHWAY_COMPLETION", "QUIT_REASON", "VARIATION_CASE", "VARIATION_REASON", "JG_PROVINCE", "JG_CITY", "TDEP_CODE2", "TDEP_CODE3", "TUMOR_CODE", "MEDICAL_TEAM_NAME", "MEDICAL_PREPARATION_FLAG", "MEDICAL_DEVICE_FLAG", "MEDICAL_TECHNOLOGY_FLAG", "REFERRAL_ORG_NAME", "DIS_OUTCOME_CODE", "DIS_OUTCOME_NAME", "SFFJHZRY", "SFRJBF", "TNMZLFQ", "TYSHXYDM", "GJ", "YCHXJSY", "TJHLTS", "YJHLTS", "EJHLTS", "SJHLTS", "ZTXHS", "ZYZD", "ZYZDJBBM", "ZYZDRYBQ") AS 
  select
       cast(substrb('49557032X' || '|' || a.patient_id || '|' || a.visit_id, 1, 100) as varchar2(100)) as ID,--内码 是 主键

       cast('1' as varchar2(6)) as HOME_TYPE_CODE,--病案首页类型代码 是；1西医
       cast('西医' as varchar2(50)) as HOME_TYPE_NAME,--病案首页类型 是

       cast('49557032X' as varchar2(32)) as ORG_CODE,--医院组织机构代码 是
       cast('山东省第二人民医院' as varchar2(70)) as ORG_NAME,--医疗机构名称 是

       a.visit_id as INPATIENT_TIMES,--住院次数 是；本次住院次数取PAT_VISIT

       case regexp_replace(trim(nvl(to_char(coalesce(a.charge_type, b.charge_type)), '')), '[[:space:]]+', '')
           when '职工医保' then '10'
           when '省直医保' then '10'
           when '省内职工' then '11'
           when '省外职工' then '12'
           when '居民医保' then '20'
           when '省内居民' then '21'
           when '学生医保' then '21'
           when '儿童医保' then '21'
           when '新农合' then '21'
           when '省外居民' then '22'
           when '异地医保' then '22'
           when '贫困救助' then '40'
           when '商业医疗保险' then '50'
           when '全公费' then '60'
           when '自费' then '70'
           when '全自费' then '70'
           when '工伤' then '80'
           when '新生儿' then '99'
           when '离休医保' then '99'
           when '干部保健' then '99'
           else '99'
       end as CHARGE_MODE_CODE,--医疗付费方式代码；优先取本次住院a.CHARGE_TYPE

       cast(
           substrb(
               case regexp_replace(trim(nvl(to_char(coalesce(a.charge_type, b.charge_type)), '')), '[[:space:]]+', '')
                   when '职工医保' then '职工基本医疗保险'
                   when '省直医保' then '职工基本医疗保险'
                   when '省内职工' then '本市职工基本医疗保险'
                   when '省外职工' then '外埠职工基本医疗保险'
                   when '居民医保' then '居民基本医疗保险'
                   when '省内居民' then '本市居民基本医疗保险'
                   when '学生医保' then '本市居民基本医疗保险'
                   when '儿童医保' then '本市居民基本医疗保险'
                   when '新农合' then '本市居民基本医疗保险'
                   when '省外居民' then '外埠居民基本医疗保险'
                   when '异地医保' then '外埠居民基本医疗保险'
                   when '贫困救助' then '贫困救助'
                   when '商业医疗保险' then '商业医疗保险'
                   when '全公费' then '全公费'
                   when '自费' then '全自费'
                   when '全自费' then '全自费'
                   when '工伤' then '其他社会保险'
                   when '新生儿' then '其他'
                   when '离休医保' then '其他'
                   when '干部保健' then '其他'
                   else '其他'
               end,
               1,
               50
           ) as varchar2(50)
       ) as CHARGE_MODE_NAME,--医疗付费方式；按本院CHARGE_TYPE手工映射

       cast(nvl(a.total_costs, 0) as number(10,2)) as TOTAL_AMOUNT,--住院总费用 是

       cast(substrb(nvl(to_char(coalesce(a.inp_no, b.inp_no)), '-'), 1, 18) as varchar2(18)) as CASE_NUM,--病案号 是；优先本次住院INP_NO，主索引兜底

       '1'  as BALANCE_STATE,--是否归档；根据首页归档日期判断，需结合CATALOG_STATUS确认

       cast(substrb(to_char(coalesce(a.inp_no, b.inp_no)), 1, 20) as varchar2(20)) as ADMISSION_NUM,--住院号

       cast(substrb(a.patient_id || '|' || a.visit_id, 1, 50) as varchar2(50)) as ADMISSION_ID,--本次住院标识号 是；项目统一口径

       cast(substrb(nvl(to_char(b.name), '-'), 1, 50) as varchar2(50)) as NAME,--姓名 是；患者固定身份取主索引

       cast(decode(b.sex, '男', '1', '女', '2', '未知', '0', '9') as char(1)) as SEX_CODE,--性别代码 是

       cast(substrb(decode(b.sex, '男', '男', '女', '女', '未知', '未知', '不明'), 1, 50) as varchar2(50)) as SEX_NAME,--性别 是

       cast(b.date_of_birth as DATE) as BORN_DATE,--出生日期 是

       case
           when b.date_of_birth is not null and a.admission_date_time is not null
           then least(greatest(trunc(months_between(a.admission_date_time, b.date_of_birth) / 12), 0), 200)
           else null
       end as AGE,--年龄（岁） 是；按入院时间计算

       case
           when b.date_of_birth is not null
            and a.admission_date_time is not null
            and months_between(a.admission_date_time, b.date_of_birth) < 12
           then least(greatest(trunc(months_between(a.admission_date_time, b.date_of_birth)), 0), 11)
           else 0
       end as AGE_MONTH,--年龄（月）；不足1岁填写月龄

       case
           when b.date_of_birth is not null
            and a.admission_date_time is not null
            and months_between(a.admission_date_time, b.date_of_birth) < 1
           then least(greatest(trunc(a.admission_date_time - b.date_of_birth), 0), 30)
           else 0
       end as AGE_DAY,--年龄（天）；不足1月填写天数

       case
           when b.date_of_birth is not null
            and a.admission_date_time is not null
            and (a.admission_date_time - b.date_of_birth) < 1
           then least(greatest(trunc(24 * (a.admission_date_time - b.date_of_birth)), 1), 23)
           else 0
       end as AGE_HOUR,--年龄（小时）；不足1天最小按1小时

       case regexp_replace(trim(nvl(to_char(coalesce(a.marital_status, b.marital_status)), '')), '[[:space:]]+', '')
           when '1' then '10'
           when '未婚' then '10'
           when '2' then '20'
           when '已婚' then '20'
           when '再婚' then '20'
           when '3' then '30'
           when '丧偶' then '30'
           when '4' then '40'
           when '离婚' then '40'
           when '离异' then '40'
           else '90'
       end as MARITAL_STATUS_CODE,--婚姻状况代码；优先本次住院婚姻状态

       cast(
           substrb(
               case regexp_replace(trim(nvl(to_char(coalesce(a.marital_status, b.marital_status)), '')), '[[:space:]]+', '')
                   when '1' then '未婚'
                   when '未婚' then '未婚'
                   when '2' then '已婚'
                   when '已婚' then '已婚'
                   when '再婚' then '已婚'
                   when '3' then '丧偶'
                   when '丧偶' then '丧偶'
                   when '4' then '离婚'
                   when '离婚' then '离婚'
                   when '离异' then '离婚'
                   else '未说明的婚姻状况'
               end,
               1,
               50
           ) as varchar2(50)
       ) as MARITAL_STATUS_NAME,--婚姻状况

       cast(substrb(nvl(occ_dict.国标编码, '51'), 1, 20) as varchar2(20)) as OCCUPATION_CODE,--职业代码；先校验a.OCCUPATION有效性，再用b兜底

       cast(substrb(nvl(occ_dict.国标名称, '自由职业者'), 1, 50) as varchar2(50)) as OCCUPATION_NAME,--职业名称

       cast(
           case regexp_replace(trim(nvl(to_char(b.nation), '')), '[[:space:]]+', '')
               when '01' then '01' when '1' then '01' when '汉' then '01' when '汉族' then '01' when '汉族族' then '01'
               when '02' then '02' when '2' then '02' when '蒙古' then '02' when '蒙古族' then '02'
               when '03' then '03' when '3' then '03' when '回' then '03' when '回族' then '03'
               when '04' then '04' when '4' then '04' when '藏' then '04' when '藏族' then '04'
               when '05' then '05' when '5' then '05' when '维吾尔' then '05' when '维吾尔族' then '05'
               when '06' then '06' when '6' then '06' when '苗' then '06' when '苗族' then '06'
               when '07' then '07' when '7' then '07' when '彝' then '07' when '彝族' then '07'
               when '08' then '08' when '8' then '08' when '壮' then '08' when '壮族' then '08'
               when '09' then '09' when '9' then '09' when '布依' then '09' when '布依族' then '09'
               when '10' then '10' when '朝鲜' then '10' when '朝鲜族' then '10'
               when '11' then '11' when '满' then '11' when '满族' then '11'
               when '12' then '12' when '侗' then '12' when '侗族' then '12'
               when '13' then '13' when '瑶' then '13' when '瑶族' then '13'
               when '14' then '14' when '白' then '14' when '白族' then '14'
               when '15' then '15' when '土家' then '15' when '土家族' then '15'
               when '16' then '16' when '哈尼' then '16' when '哈尼族' then '16'
               when '17' then '17' when '哈萨克' then '17' when '哈萨克族' then '17'
               when '18' then '18' when '傣' then '18' when '傣族' then '18'
               when '19' then '19' when '黎' then '19' when '黎族' then '19'
               when '20' then '20' when '傈僳' then '20' when '傈僳族' then '20'
               when '21' then '21' when '佤' then '21' when '佤族' then '21'
               when '22' then '22' when '畲' then '22' when '畲族' then '22'
               when '23' then '23' when '高山' then '23' when '高山族' then '23'
               when '24' then '24' when '拉祜' then '24' when '拉祜族' then '24'
               when '25' then '25' when '水' then '25' when '水族' then '25'
               when '26' then '26' when '东乡' then '26' when '东乡族' then '26'
               when '27' then '27' when '纳西' then '27' when '纳西族' then '27'
               when '28' then '28' when '景颇' then '28' when '景颇族' then '28'
               when '29' then '29' when '柯尔克孜' then '29' when '柯尔克孜族' then '29' when '柯尔柯孜族' then '29'
               when '30' then '30' when '土' then '30' when '土族' then '30'
               when '31' then '31' when '达斡尔' then '31' when '达斡尔族' then '31' when '达尔族' then '31'
               when '32' then '32' when '仫佬' then '32' when '仫佬族' then '32'
               when '33' then '33' when '羌' then '33' when '羌族' then '33'
               when '34' then '34' when '布朗' then '34' when '布朗族' then '34'
               when '35' then '35' when '撒拉' then '35' when '撒拉族' then '35'
               when '36' then '36' when '毛南' then '36' when '毛南族' then '36' when '毛难族' then '36'
               when '37' then '37' when '仡佬' then '37' when '仡佬族' then '37'
               when '38' then '38' when '锡伯' then '38' when '锡伯族' then '38'
               when '39' then '39' when '阿昌' then '39' when '阿昌族' then '39'
               when '40' then '40' when '普米' then '40' when '普米族' then '40'
               when '41' then '41' when '塔吉克' then '41' when '塔吉克族' then '41'
               when '42' then '42' when '怒' then '42' when '怒族' then '42'
               when '43' then '43' when '乌孜别克' then '43' when '乌孜别克族' then '43'
               when '44' then '44' when '俄罗斯' then '44' when '俄罗斯族' then '44'
               when '45' then '45' when '鄂温克' then '45' when '鄂温克族' then '45'
               when '46' then '46' when '德昂' then '46' when '德昂族' then '46'
               when '47' then '47' when '保安' then '47' when '保安族' then '47'
               when '48' then '48' when '裕固' then '48' when '裕固族' then '48'
               when '49' then '49' when '京' then '49' when '京族' then '49'
               when '50' then '50' when '塔塔尔' then '50' when '塔塔尔族' then '50'
               when '51' then '51' when '独龙' then '51' when '独龙族' then '51'
               when '52' then '52' when '鄂伦春' then '52' when '鄂伦春族' then '52'
               when '53' then '53' when '赫哲' then '53' when '赫哲族' then '53'
               when '54' then '54' when '门巴' then '54' when '门巴族' then '54'
               when '55' then '55' when '珞巴' then '55' when '珞巴族' then '55'
               when '56' then '56' when '基诺' then '56' when '基诺族' then '56'
               else '66'
           end as varchar2(2)
       ) as NATION_CODE,--民族代码；患者固定身份取主索引

       cast(
           substrb(
               case regexp_replace(trim(nvl(to_char(b.nation), '')), '[[:space:]]+', '')
                   when '01' then '汉族' when '1' then '汉族' when '汉' then '汉族' when '汉族' then '汉族' when '汉族族' then '汉族'
                   when '02' then '蒙古族' when '2' then '蒙古族' when '蒙古' then '蒙古族' when '蒙古族' then '蒙古族'
                   when '03' then '回族' when '3' then '回族' when '回' then '回族' when '回族' then '回族'
                   when '04' then '藏族' when '4' then '藏族' when '藏' then '藏族' when '藏族' then '藏族'
                   when '05' then '维吾尔族' when '5' then '维吾尔族' when '维吾尔' then '维吾尔族' when '维吾尔族' then '维吾尔族'
                   when '06' then '苗族' when '6' then '苗族' when '苗' then '苗族' when '苗族' then '苗族'
                   when '07' then '彝族' when '7' then '彝族' when '彝' then '彝族' when '彝族' then '彝族'
                   when '08' then '壮族' when '8' then '壮族' when '壮' then '壮族' when '壮族' then '壮族'
                   when '09' then '布依族' when '9' then '布依族' when '布依' then '布依族' when '布依族' then '布依族'
                   when '10' then '朝鲜族' when '朝鲜' then '朝鲜族' when '朝鲜族' then '朝鲜族'
                   when '11' then '满族' when '满' then '满族' when '满族' then '满族'
                   when '12' then '侗族' when '侗' then '侗族' when '侗族' then '侗族'
                   when '13' then '瑶族' when '瑶' then '瑶族' when '瑶族' then '瑶族'
                   when '14' then '白族' when '白' then '白族' when '白族' then '白族'
                   when '15' then '土家族' when '土家' then '土家族' when '土家族' then '土家族'
                   when '16' then '哈尼族' when '哈尼' then '哈尼族' when '哈尼族' then '哈尼族'
                   when '17' then '哈萨克族' when '哈萨克' then '哈萨克族' when '哈萨克族' then '哈萨克族'
                   when '18' then '傣族' when '傣' then '傣族' when '傣族' then '傣族'
                   when '19' then '黎族' when '黎' then '黎族' when '黎族' then '黎族'
                   when '20' then '傈僳族' when '傈僳' then '傈僳族' when '傈僳族' then '傈僳族'
                   when '21' then '佤族' when '佤' then '佤族' when '佤族' then '佤族'
                   when '22' then '畲族' when '畲' then '畲族' when '畲族' then '畲族'
                   when '23' then '高山族' when '高山' then '高山族' when '高山族' then '高山族'
                   when '24' then '拉祜族' when '拉祜' then '拉祜族' when '拉祜族' then '拉祜族'
                   when '25' then '水族' when '水' then '水族' when '水族' then '水族'
                   when '26' then '东乡族' when '东乡' then '东乡族' when '东乡族' then '东乡族'
                   when '27' then '纳西族' when '纳西' then '纳西族' when '纳西族' then '纳西族'
                   when '28' then '景颇族' when '景颇' then '景颇族' when '景颇族' then '景颇族'
                   when '29' then '柯尔克孜族' when '柯尔克孜' then '柯尔克孜族' when '柯尔克孜族' then '柯尔克孜族' when '柯尔柯孜族' then '柯尔克孜族'
                   when '30' then '土族' when '土' then '土族' when '土族' then '土族'
                   when '31' then '达斡尔族' when '达斡尔' then '达斡尔族' when '达斡尔族' then '达斡尔族' when '达尔族' then '达斡尔族'
                   when '32' then '仫佬族' when '仫佬' then '仫佬族' when '仫佬族' then '仫佬族'
                   when '33' then '羌族' when '羌' then '羌族' when '羌族' then '羌族'
                   when '34' then '布朗族' when '布朗' then '布朗族' when '布朗族' then '布朗族'
                   when '35' then '撒拉族' when '撒拉' then '撒拉族' when '撒拉族' then '撒拉族'
                   when '36' then '毛南族' when '毛南' then '毛南族' when '毛南族' then '毛南族' when '毛难族' then '毛南族'
                   when '37' then '仡佬族' when '仡佬' then '仡佬族' when '仡佬族' then '仡佬族'
                   when '38' then '锡伯族' when '锡伯' then '锡伯族' when '锡伯族' then '锡伯族'
                   when '39' then '阿昌族' when '阿昌' then '阿昌族' when '阿昌族' then '阿昌族'
                   when '40' then '普米族' when '普米' then '普米族' when '普米族' then '普米族'
                   when '41' then '塔吉克族' when '塔吉克' then '塔吉克族' when '塔吉克族' then '塔吉克族'
                   when '42' then '怒族' when '怒' then '怒族' when '怒族' then '怒族'
                   when '43' then '乌孜别克族' when '乌孜别克' then '乌孜别克族' when '乌孜别克族' then '乌孜别克族'
                   when '44' then '俄罗斯族' when '俄罗斯' then '俄罗斯族' when '俄罗斯族' then '俄罗斯族'
                   when '45' then '鄂温克族' when '鄂温克' then '鄂温克族' when '鄂温克族' then '鄂温克族'
                   when '46' then '德昂族' when '德昂' then '德昂族' when '德昂族' then '德昂族'
                   when '47' then '保安族' when '保安' then '保安族' when '保安族' then '保安族'
                   when '48' then '裕固族' when '裕固' then '裕固族' when '裕固族' then '裕固族'
                   when '49' then '京族' when '京' then '京族' when '京族' then '京族'
                   when '50' then '塔塔尔族' when '塔塔尔' then '塔塔尔族' when '塔塔尔族' then '塔塔尔族'
                   when '51' then '独龙族' when '独龙' then '独龙族' when '独龙族' then '独龙族'
                   when '52' then '鄂伦春族' when '鄂伦春' then '鄂伦春族' when '鄂伦春族' then '鄂伦春族'
                   when '53' then '赫哲族' when '赫哲' then '赫哲族' when '赫哲族' then '赫哲族'
                   when '54' then '门巴族' when '门巴' then '门巴族' when '门巴族' then '门巴族'
                   when '55' then '珞巴族' when '珞巴' then '珞巴族' when '珞巴族' then '珞巴族'
                   when '56' then '基诺族' when '基诺' then '基诺族' when '基诺族' then '基诺族'
                   else '其他'
               end,
               1,
               50
           ) as varchar2(50)
       ) as NATION_NAME,--民族名称

       cast(substrb(nvl(country_by_code.国标编码, '156'), 1, 3) as varchar2(3)) as COUNTRY_CODE,--国籍代码；CITIZENSHIP=CN时映射156

       cast(substrb(nvl(country_by_code.国标名称, '中国'), 1, 50) as varchar2(50)) as COUNTRY_NAME,--国籍名称

case
    when regexp_like(trim(to_char(b.id_no)), '^[0-9]{17}[0-9Xx]$|^[0-9]{15}$')
    then '01'
    else cast(substrb(nvl(idtype_dict.国标编码, '99'), 1, 2) as varchar2(2))
end as OTHER_ID_TYPE,--其他身份证件标识；身份证号符合规则时按居民身份证

cast(
    substrb(
        case
            when regexp_like(trim(to_char(b.id_no)), '^[0-9]{17}[0-9Xx]$|^[0-9]{15}$')
            then '居民身份证'
            else nvl(idtype_dict.国标名称, '其他法定有效证件')
        end,
        1,
        12
    ) as varchar2(12)
) as OTHER_ID_NAME,--其他身份证件名称

cast(substrb(to_char(b.id_no), 1, 18) as varchar2(18)) as OTHER_ID_NUM,--其他身份证件号码

cast(substrb(nvl(to_char(b.id_no), '000000000000000000'), 1, 18) as varchar2(18)) as ID_NUM,--身份证件号码

       cast(substrb(coalesce(to_char(a.service_agency),
                             cast(b.workadd_name as varchar2(4000 char)),
                             to_char(a.unit_in_contract),
                             to_char(b.unit_in_contract)), 1, 70) as varchar2(70)) as WORKING_ORG,--工作单位名称；优先本次住院工作单位
cast(
    substrb(
        nullif(
            regexp_replace(
                coalesce(
                    to_char(a.pat_phone),
                    to_char(a.phone_number_home),
                    to_char(b.phone_number_home),
                    to_char(a.next_of_kin_phone),
                    to_char(b.next_of_kin_phone)
                ),
                '[^0-9]',
                ''
            ),
            ''
        ),
        1,
        20
    ) as varchar2(20)
) as TEL,--电话号码；清洗非数字字符

cast(
    substrb(
        nullif(
            regexp_replace(
                coalesce(
                    to_char(a.next_of_kin_phone),
                    to_char(b.next_of_kin_phone)
                ),
                '[^0-9]',
                ''
            ),
            ''
        ),
        1,
        20
    ) as varchar2(20)
) as LINKMAN_TEL,--联系人电话号码；清洗非数字字符

cast(
    substrb(
        nullif(
            regexp_replace(
                coalesce(
                    to_char(a.phone_number_business),
                    to_char(b.phone_number_business),
                    cast(b.work_tel as varchar2(4000 char))
                ),
                '[^0-9]',
                ''
            ),
            ''
        ),
        1,
        20
    ) as varchar2(20)
) as WORK_TEL,--工作单位电话号码；清洗非数字字符

       cast(substrb(cast(b.areaadd_province as varchar2(4000 char)), 1, 70) as varchar2(70)) as BORN_ADDRESS_PROVINCE,--出生地址-省；主索引出生地
       cast(substrb(cast(b.areaadd_city as varchar2(4000 char)), 1, 70) as varchar2(70)) as BORN_ADDRESS_CITY,--出生地址-市
       cast(substrb(cast(b.areaadd_county as varchar2(4000 char)), 1, 70) as varchar2(70)) as BORN_ADDRESS_COUNTY,--出生地址-县

       cast(substrb(coalesce(cast(a.pre_province as varchar2(4000 char)), cast(b.preadd_province as varchar2(4000 char))), 1, 70) as varchar2(70)) as CURRENT_ADDRESS_PROVINCE,--现住址-省；优先本次住院
       cast(substrb(coalesce(cast(a.pre_city as varchar2(4000 char)), cast(b.preadd_city as varchar2(4000 char))), 1, 70) as varchar2(70)) as CURRENT_ADDRESS_CITY,--现住址-市
       cast(substrb(coalesce(cast(a.pre_count as varchar2(4000 char)), cast(b.preadd_county as varchar2(4000 char))), 1, 70) as varchar2(70)) as CURRENT_ADDRESS_COUNTY,--现住址-县
       cast(substrb(coalesce(cast(a.pre_township as varchar2(4000 char)), cast(b.pre_township as varchar2(4000 char))), 1, 70) as varchar2(70)) as CURRENT_ADDRESS_TOWN,--现住址-乡镇街道
       cast(substrb(coalesce(to_char(a.patient_area_address), to_char(b.patient_area_address), to_char(a.mailing_address), to_char(b.mailing_address)), 1, 70) as varchar2(70)) as CURRENT_ADDRESS_VILLAGE,--现住址-村街路弄；暂放详细地址
       cast(null as varchar2(70)) as CURRENT_ADDRESS_HN,--现住址-门牌号码；暂无独立门牌字段
       cast(substrb(coalesce(to_char(a.pat_zip), to_char(a.zip_code), to_char(b.zip_code)), 1, 6) as varchar2(6)) as CURRENT_ADDRESS_ZP,--现住址邮编

       cast(substrb(cast(b.homeadd_province as varchar2(4000 char)), 1, 70) as varchar2(70)) as HRA_ADDRESS_PROVINCE,--户口地址-省
       cast(substrb(cast(b.homeadd_city as varchar2(4000 char)), 1, 70) as varchar2(70)) as HRA_ADDRESS_CITY,--户口地址-市
       cast(substrb(cast(b.homeadd_county as varchar2(4000 char)), 1, 70) as varchar2(70)) as HRA_ADDRESS_COUNTY,--户口地址-县
       cast(substrb(cast(b.homeadd_township as varchar2(4000 char)), 1, 70) as varchar2(70)) as HRA_ADDRESS_TOWN,--户口地址-乡镇
       cast(substrb(to_char(b.mailing_address), 1, 70) as varchar2(70)) as HRA_ADDRESS_VILLAGE,--户口地址-详细地址
       cast(null as varchar2(70)) as HRA_ADDRESS_HN,--户口地址-门牌号码；暂无独立门牌字段
       cast(substrb(to_char(b.zip_code), 1, 6) as varchar2(6)) as HRA_ADDRESS_ZP,--户口邮编

       cast(substrb(coalesce(to_char(a.service_agency_addr), cast(b.workadd_name as varchar2(4000 char))), 1, 200) as varchar2(200)) as WORK_ADDRESS,--工作单位地址

       cast(substrb(coalesce(to_char(a.business_zip_code), to_char(b.business_zip_code), cast(b.work_zip as varchar2(4000 char))), 1, 6) as varchar2(6)) as WORK_ZP,--工作单位地址邮编

       cast(substrb(coalesce(to_char(a.next_of_kin_addr), to_char(b.next_of_kin_addr)), 1, 200) as varchar2(200)) as LINKMAN_ADDRESS,--联系人地址；优先本次住院

       cast(substrb(coalesce(to_char(a.next_of_kin), to_char(b.next_of_kin)), 1, 50) as varchar2(50)) as LINKMAN_NAME,--联系人姓名；优先本次住院

       cast(substrb(nvl(rel_dict.国标编码, '8'), 1, 2) as varchar2(2)) as RBT_CONTACT_CODE,--联系人与患者的关系代码；按家庭关系字典

       cast(substrb(nvl(rel_dict.国标名称, '其他'), 1, 50) as varchar2(50)) as RBT_CONTACT_NAME,--联系人与患者的关系

       cast(a.admission_date_time as DATE) as ADMISSION_DATE,--入院日期 是

       cast(a.discharge_date_time as DATE) as DISCHARGE_DATE,--出院日期 是

  case
    when a.discharge_date_time is not null
     and a.admission_date_time is not null
    then greatest(
             trunc(a.discharge_date_time) - trunc(a.admission_date_time),
             0
         )
    else 0
end as INPATIENT_DAY,--实际住院天数 是；按出入院日期自然日差计算

       cast(null as varchar2(1000)) as INJURY_CAUSE,--损伤和中毒外部原因；暂无明确来源

       cast(decode(a.mr_quality, '甲', '1', '乙', '2', '丙', '3', '1') as char(1)) as CASE_QUALITY_CODE,--病案质量代码 是
       cast(substrb(nvl(to_char(a.mr_quality), '甲'), 1, 50) as varchar2(50)) as CASE_QUALITY_NAME,--病案质量 是

       cast(decode(a.autopsy_indicator, 1, '1', 2, '0', '0') as char(1)) as IS_AUTOPSY,--死亡患者尸检

       cast(substrb(nvl(abo_dict.国标编码, '5'), 1, 1) as char(1)) as BLOOD_ABO_CODE,--ABO血型代码
       cast(substrb(nvl(abo_dict.国标名称, '不详'), 1, 50) as varchar2(50)) as BLOOD_ABO_NAME,--ABO血型
       cast(substrb(nvl(rh_dict.国标编码, '3'), 1, 1) as char(1)) as BLOOD_RH_CODE,--RH血型代码
       cast(substrb(nvl(rh_dict.国标名称, '不详'), 1, 50) as varchar2(50)) as BLOOD_RH_NAME,--RH血型

       cast(nvl(a.catalog_date, a.admission_date_time) as DATE) as RECORD_DATE,--病案记录日期；优先编目日期

       cast(substrb(to_char(b.healthy_card_no), 1, 18) as varchar2(18)) as HEALTH_RECORD_CODE,--健康卡号

       cast(substrb(nvl(adm_type_dict.国标编码, '9'), 1, 1) as char(1)) as ADMISSION_TYPE_CODE,--入院途径代码；优先本次住院PATIENT_CLASS

       cast(substrb(nvl(adm_type_dict.国标名称, '其他'), 1, 50) as varchar2(50)) as ADMISSION_TYPE_NAME,--入院途径

       cast(a.weight_birth as number) as BIRTH_BODY_WEIGHT,--新生儿出生体重

       case when to_char(a.newborn) = '1' then cast(a.body_weight as number) else cast(null as number) end as ADMISSION_BODY_WEIGHT,--新生儿入院体重；仅新生儿填写

       cast(substrb(to_char(a.pathology_no), 1, 18) as varchar2(18)) as PATHOLOGY_NUM,--病理号

       cast(case when a.alergy_drugs is not null or a.allergy_history is not null then '1' else '0' end as char(1)) as IS_ALLERGY,--药物过敏标志 是

       cast(substrb(coalesce(to_char(a.alergy_drugs), to_char(a.allergy_history)), 1, 50) as varchar2(50)) as ALLERGY_N,--过敏药物名称

       cast(substrb(nvl(discharge_type_dict.国标编码, '9'), 1, 1) as char(1)) as DISCHARGE_TYPE_CODE,--离院方式代码 是

       cast(substrb(nvl(discharge_type_dict.国标名称, '其他'), 1, 50) as varchar2(50)) as DISCHARGE_TYPE_NAME,--离院方式名称 是

       cast(substrb(coalesce(to_char(a.entrance_hospital), to_char(a.referral_hospital), to_char(a.trans_hospital)), 1, 70) as varchar2(70)) as RECEIVE_ORG_NAME,--拟接收医疗机构名称；离院方式2、3时关注

       cast(decode(a.plan_31_admission, '1', '0', '2', '1', '0') as char(1)) as IS_READMISSION,--是否有出院31天内再住院计划；1无2有转换为0/1

       cast(substrb(to_char(a.reason_31_admission), 1, 600) as varchar2(600)) as READMISSION_PURPOSE,--再住院目的

       a.coma_times_b0 as PRIOR_COMA_DAYS,--入院前昏迷天数
       a.coma_times_b1 as PRIOR_COMA_HOURS,--入院前昏迷小时数
       a.coma_times_b2 as PRIOR_COMA_MINUTES,--入院前昏迷分钟数
       a.coma_times_a0 as AFTER_COMA_DAYS,--入院后昏迷天数
       a.coma_times_a1 as AFTER_COMA_HOURS,--入院后昏迷小时数
       a.coma_times_a2 as AFTER_COMA_MINUTES,--入院后昏迷分钟数

       cast(nvl(a.date_of_control_quality, nvl(a.catalog_date, a.docum_date)) as DATE) as QC_DATE,--质控日期 是；优先质控日期

       cast(substrb(decode(a.treat_method, '1', '1', '2', '3', '3', '2', '4', '1.2'), 1, 3) as varchar2(3)) as TREATE_TYPE_CODE,--治疗类别代码

       cast(substrb(decode(a.treat_method, '1', '中医', '2', '西医', '3', '中西医', '4', '民族医'), 1, 50) as varchar2(50)) as TREATE_TYPE_NAME,--治疗类别

       cast(substrb(to_char(a.clinical_pathway_type), 1, 1) as char(1)) as PATHWAY_TYPE_CODE,--实施临床路径代码

       cast(substrb(decode(a.clinical_pathway_type, '1', '中医', '2', '西医', '3', '否'), 1, 50) as varchar2(50)) as PATHWAY_TYPE_NAME,--实施临床路径

       cast(case when to_char(a.hosp_made_medicine_indicator) = '1' then '1'
                 when to_char(a.hosp_made_medicine_indicator) = '2' then '0'
                 else null end as char(1)) as IS_USE_HERB,--使用医疗机构中药制剂

       cast(case when to_char(a.chinese_medicine_device) = '1' then '1'
                 when to_char(a.chinese_medicine_device) = '2' then '0'
                 else null end as char(1)) as IS_USE_EQUIP,--使用中医诊疗设备

       cast(case when to_char(a.chinese_medicine_technology) = '1' then '1'
                 when to_char(a.chinese_medicine_technology) = '2' then '0'
                 else null end as char(1)) as IS_USE_TECH,--使用中医诊疗技术

       cast(case when to_char(a.dialectical_care) = '1' then '1'
                 when to_char(a.dialectical_care) = '2' then '0'
                 else null end as char(1)) as IS_DIALECTIAL_NURSING,--辨证施护

       cast(a.zffy as number(10,2)) as TOTAL_AMOUNT_STP,--住院总费用-自付金额

       nvl(a.emer_treat_times, 0) as SAVE_TIMES,--住院患者抢救次数 是
       nvl(a.esc_emer_times, 0) as SAVE_SUCCESS_TIMES,--住院患者抢救成功次数 是

       cast(case when a.death_date_time is not null then '1' else '0' end as char(1)) as IS_DEATH,--死亡标识

       cast(case when nvl(a.infusion_react_times, 0) > 0 then '1' else '0' end as char(1)) as INFUSION_REACTION_MARK,--输液反应标志

       cast(case
                when nvl(a.blood_tran_times, 0) = 0 then '3'
                when nvl(a.blood_tran_react_times, 0) > 0 then '1'
                else '0'
            end as char(1)) as BT_REACTION_MARK,--输血反应标志；3未输

       cast(null as char(1)) as OPERATION_COMPLICATIONS,--手术并发症标识；暂无明确来源

       cast(case when to_char(a.zymosis_indicator) in ('1', '2') then '1' else '0' end as char(1)) as IS_INFECTION,--传染病标识；1已报/2未报均视为有传染病

       cast(case when to_char(a.zymosis_indicator) = '1' then '1' else '0' end as char(1)) as IS_INFECTION_REPORT,--传染病报告上报标识

       cast(case when nvl(a.critical_cond_days, 0) > 0 or to_char(a.serious_indicator) = '1' then '1' else '0' end as char(1)) as IS_CRITICAL,--危重标识

       cast(case when to_char(a.ictus_indicator) = '1' then '1' else '0' end as char(1)) as IS_EMERGENCY,--急症标识；使用住院期间急症标志

       cast(a.death_date_time as date) as DEATH_TIME,--死亡日期时间
       cast(substrb(to_char(a.death_reason), 1, 128) as varchar2(128)) as DEATH_CAUSE,--死亡原因
         cast(
    case
        when a.death_date_time is not null then     cast(substrb(nvl(main_diag_code_cd.国标编码, nvl(main_diag_name_cd.国标编码, main_diag.diagnosis_code)), 1, 100) as varchar2(100))
        else null
    end as varchar2(128)
) as ROOT_DEATH_CODE,--死亡根本原因诊断代码；暂无根本死因来源，暂不填

       cast(null as number(5)) as INFECTIOUSNESS_TIMES,--感染次数；暂无明确来源

       cast(substrb(coalesce(to_char(a.insurance_no), to_char(b.insurance_no), to_char(b.insur_card_no), to_char(b.medical_no)), 1, 128) as varchar2(128)) as INSURANCE_NUM,--医疗保险号；优先本次住院

       cast(decode(a.pat_adm_condition, '1', '1', '2', '2', '3', '3', '4') as char(1)) as IN_CONDITION_CODE,--入院情况代码

       cast(substrb(decode(a.pat_adm_condition, '1', '危重', '2', '急诊', '3', '一般', '其他'), 1, 20) as varchar2(20)) as IN_CONDITION_NAME,--入院情况名称

       cast(null as number(12,2)) as RED_BLOOD_CELL,--输红细胞量；暂无拆分来源
       cast(null as number(12,2)) as PLATELET,--输血小板量；暂无拆分来源
       cast(null as number(12,2)) as PLASMA,--输血浆量；暂无拆分来源
       cast(null as number(12,2)) as WHOLE_BLOOD,--输全血量；暂无拆分来源
       cast(null as number(12,2)) as OTHER_BLOOD,--输其他血制品量；暂无拆分来源

       cast(substrb(to_char(a.director), 1, 32) as varchar2(32)) as DIRECTOR_CODE,--科主任代码；当前保留职工号
       cast(substrb(to_char(director_sd.name), 1, 50) as varchar2(50)) as DIRECTOR_NAME,--科主任签名

       cast(substrb(to_char(a.chief_doctor), 1, 32) as varchar2(32)) as CHIEF_PHYSICIAN_CODE,--主任医师代码
       cast(substrb(to_char(chief_sd.name), 1, 50) as varchar2(50)) as CHIEF_PHYSICIAN_NAME,--主任医师签名

       cast(substrb(to_char(a.attending_doctor), 1, 32) as varchar2(32)) as ATTENDING_PHYSICIAN_CODE,--主治医师代码
       cast(substrb(to_char(attending_sd.name), 1, 50) as varchar2(50)) as ATTENDING_PHYSICIAN_NAME,--主治医师签名

       cast(substrb(to_char(a.doctor_in_charge), 1, 32) as varchar2(32)) as RESIDENT_CODE,--住院医师代码；使用经治医师
       cast(substrb(to_char(resident_sd.name), 1, 50) as varchar2(50)) as RESIDENT_NAME,--住院医师签名

       cast(substrb(to_char(a.duty_nurse), 1, 32) as varchar2(32)) as NURSE_CODE,--责任护士代码
       cast(substrb(to_char(nurse_sd.name), 1, 50) as varchar2(50)) as NURSE_NAME,--责任护士签名

       cast(substrb(to_char(a.advanced_studies_doctor), 1, 32) as varchar2(32)) as REFRESHER_DOCTORS_CODE,--进修医师代码
       cast(substrb(to_char(refresher_sd.name), 1, 50) as varchar2(50)) as REFRESHER_DOCTORS_NAME,--进修医师签名

       cast(substrb(to_char(a.practice_doctor), 1, 32) as varchar2(32)) as INTERN_CODE,--实习医师代码
       cast(substrb(to_char(intern_sd.name), 1, 50) as varchar2(50)) as INTERN_NAME,--实习医师签名

       cast(substrb(to_char(a.cataloger), 1, 32) as varchar2(32)) as CODER_CODE,--编码员代码
       cast(substrb(to_char(coder_sd.name), 1, 50) as varchar2(50)) as CODER_NAME,--编码员签名
       cast(substrb(to_char(coder_sd.id_no), 1, 50) as varchar2(50)) as CODER_IDNUM,--编码员身份证号

       cast(substrb(to_char(a.doctor_of_control_quality), 1, 32) as varchar2(32)) as QCD_CODE,--质控医师代码
       cast(substrb(to_char(qcd_sd.name), 1, 50) as varchar2(50)) as QCD_NAME,--质控医师签名

       cast(substrb(to_char(a.nurse_of_control_quality), 1, 32) as varchar2(32)) as QCN_CODE,--质控护士代码
       cast(substrb(to_char(qcn_sd.name), 1, 50) as varchar2(50)) as QCN_NAME,--质控护士签名

       cast(substrb(nvl(adm_dept.qmpt_code, a.dept_admission_to), 1, 20) as varchar2(20)) as DEP_CODE,--入院科别代码 是
       cast(substrb(nvl(adm_dept.qmpt_name, adm_dept.dept_name), 1, 50) as varchar2(50)) as DEP_NAME,--入院科别名称 是

       cast(substrb(to_char(a.adt_room_no), 1, 50) as varchar2(50)) as IN_WORD,--入院病房

       cast(null as varchar2(50)) as TDEP_CODE,--转科科别代码；暂无明确来源
       cast(null as varchar2(50)) as TDEP_NAME,--转科科别；暂无明确来源

       cast(substrb(nvl(dis_dept.qmpt_code, a.dept_discharge_from), 1, 50) as varchar2(50)) as ODEP_CODE,--出院科别代码 是
       cast(substrb(nvl(dis_dept.qmpt_name, dis_dept.dept_name), 1, 50) as varchar2(50)) as ODEP_NAME,--出院科别 是

       cast(substrb(to_char(a.ddt_room_no), 1, 50) as varchar2(50)) as OUT_WORD,--出院病房

       cast(null as varchar2(32)) as CITIZEN_ID,--个人内码；平台自动生成
       cast(null as date) as EFFECTIVE_TIME,--活动发生时间；暂无明确来源
       cast(null as varchar2(32)) as STATUS,--卡片状态；平台自动生成
       cast(a.admission_date_time as DATE) as CREATED_AT,--创建时间；暂取入院时间

       cast('370104' as varchar2(6)) as DISTRICT_CODE,--所属行政区划 是
       cast('ADDHIS' as varchar2(10)) as EXCHANGE_TYPE,--交换类型 是

       cast(null as varchar2(50)) as DEI,--数据交换标识符
       cast(null as varchar2(50)) as NODE_CODE,--节点标识符
       cast(substrb(to_char(a.inp_serial_no), 1, 50) as varchar2(50)) as CASE_ID,--院内病案标识码；使用住院流水号
       cast('49557032X' as varchar2(50)) as CASE_ORG_CODE,--病案所属机构编码
       cast(sysdate as DATE) as SYSTEM_TIME,--数据上传时间戳 是
       cast(null as varchar2(36)) as CZRK_ID,--常住人口ID

       sszd_diag.diagnosis_code  as INJURY_CAUSE_CODE,--损伤中毒外部原因疾病编码；暂无明确来源

       cast(null as char(1)) as NURSING_LEVEL_CODE,--护理等级代码；不从护理天数反推
       cast(null as number) as NURSING_LEVEL_TIME,--护理等级时间
       cast(null as varchar2(50)) as NURSING_LEVEL_UNIT,--护理等级单位

       cast(substrb(to_char(resident_sd.name), 1, 50) as varchar2(50)) as MAIN_DOC_NAME,--主诊医师签名；暂取经治医师

       cast(null as char(1)) as SINGLE_DISEASE_MG_CODE,--实施单病种管理标志代码；暂无明确来源

       cast(substrb(coalesce(to_char(a.clinical_pathway_finished),
                             case when to_char(a.clinical_pathway_finish) = '1' then '1'
                                  when to_char(a.clinical_pathway_finish) = '2' then '2'
                             end), 1, 1) as char(1)) as PATHWAY_COMPLETION,--临床路径完成情况代码

       cast(null as char(1)) as QUIT_REASON,--退出原因代码；a.QUIT_REASON可能为文本，暂不强转代码

       cast(decode(a.clinical_pathway_variation, '1', '2', '2', '1') as char(1)) as VARIATION_CASE,--变异情况代码；1否2是转换为1有2无

       cast(substrb(to_char(a.variation_reason), 1, 800) as varchar2(800)) as VARIATION_REASON,--变异原因

       cast(substrb(cast(b.district_provinc as varchar2(4000 char)), 1, 70) as varchar2(70)) as JG_PROVINCE,--籍贯-省
       cast(substrb(cast(b.district_city as varchar2(4000 char)), 1, 70) as varchar2(70)) as JG_CITY,--籍贯-市

       cast(null as varchar2(50)) as TDEP_CODE2,--转科科别代码2；暂无明确来源
       cast(null as varchar2(50)) as TDEP_CODE3,--转科科别代码3；暂无明确来源

       bl_diag.diagnosis_code as TUMOR_CODE,--肿瘤学编码；暂无明确来源

       cast(substrb(to_char(cdoctor_leader_sd.name), 1, 50) as varchar2(50)) as MEDICAL_TEAM_NAME,--医疗组长签名

       cast(case when to_char(a.hosp_made_medicine_indicator) = '1' then '1'
                 when to_char(a.hosp_made_medicine_indicator) = '2' then '0'
                 else null end as char(1)) as MEDICAL_PREPARATION_FLAG,--使用医疗机构中药制剂标志

       cast(case when to_char(a.chinese_medicine_device) = '1' then '1'
                 when to_char(a.chinese_medicine_device) = '2' then '0'
                 else null end as char(1)) as MEDICAL_DEVICE_FLAG,--使用中医诊疗设备标志

       cast(case when to_char(a.chinese_medicine_technology) = '1' then '1'
                 when to_char(a.chinese_medicine_technology) = '2' then '0'
                 else null end as char(1)) as MEDICAL_TECHNOLOGY_FLAG,--使用中医诊疗技术标志

       cast(substrb(coalesce(to_char(a.referral_hospital), to_char(a.entrance_hospital), to_char(a.trans_hospital)), 1, 70) as varchar2(70)) as REFERRAL_ORG_NAME,--转诊医疗机构名称

       cast(substrb(nvl(outcome_dict.国标编码, '9'), 1, 1) as char(1)) as DIS_OUTCOME_CODE,--出院转归代码 是；暂用出院方式映射转归
       cast(substrb(nvl(outcome_dict.国标名称, '其他'), 1, 10) as varchar2(10)) as DIS_OUTCOME_NAME,--出院转归 是

       cast(decode(a.plan_31_admission, '1', '2', '2', '1', '2') as char(1)) as SFFJHZRY,--是否非计划再入院；1是2否，按31天计划字段转换

       cast(case when to_char(a.daysurgery_indicator) = '1' then '1' else '2' end as char(1)) as SFRJBF,--是否为日间病房；1是2否

       cast(substrb(decode(a.tumor_stage, '0', '1', '1', '2', '2', '3', '3', '4', '4', '5', '9', '6'), 1, 1) as char(1)) as TNMZLFQ,--TNM/肿瘤分期

       cast(substrb(cast(b.social_code as varchar2(4000 char)), 1, 100) as varchar2(100)) as TYSHXYDM,--统一社会信用代码

       cast(substrb(nvl(country_by_code.国标编码, '156'), 1, 100) as varchar2(100)) as GJ,--国籍代码

       cast(nvl(a.breath_mach_times,0) + nvl(a.breath_mach_time2,0) + round(nvl(a.breath_mach_time3,0) / 60, 2) as number(12,2)) as YCHXJSY,--有创呼吸机使用时长；小时

       cast(substrb(to_char(a.spec_level_nurs_days), 1, 100) as varchar2(100)) as TJHLTS,--特级护理天数
       cast(substrb(to_char(a.first_level_nurs_days), 1, 100) as varchar2(100)) as YJHLTS,--一级护理天数
       cast(substrb(to_char(a.second_level_nurs_days), 1, 100) as varchar2(100)) as EJHLTS,--二级护理天数
       cast(substrb(to_char(a.third_level_nurs_days), 1, 100) as varchar2(100)) as SJHLTS,--三级护理天数

       cast(null as varchar2(100)) as ZTXHS,--自体血回输；暂无明确来源

       cast(substrb(nvl(main_diag_code_cd.国标名称, nvl(main_diag_name_cd.国标名称, main_diag.diagnosis_desc)), 1, 100) as varchar2(100)) as ZYZD,--出院诊断-主要诊断名称

       cast(substrb(nvl(main_diag_code_cd.国标编码, nvl(main_diag_name_cd.国标编码, main_diag.diagnosis_code)), 1, 100) as varchar2(100)) as ZYZDJBBM,--出院诊断-主要诊断疾病编码

       cast(substrb(to_char(a.pat_adm_condition), 1, 100) as varchar2(100)) as ZYZDRYBQ--出院诊断-主要诊断入院病情代码；暂无诊断表对应字段，暂用PAT_VISIT入院病情

from his.pat_visit a

left join his.pat_master_index b
       on b.patient_id = a.patient_id

left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = '职业代码'
     group by to_char(院标编码)
) occ_dict
       on occ_dict.院标编码 =
          case
              when regexp_replace(trim(to_char(a.occupation)), '[[:space:]]+', '') in
                   ('11','13','17','21','24','27','31','37','51','54','70','80','90')
              then regexp_replace(trim(to_char(a.occupation)), '[[:space:]]+', '')
              when regexp_replace(trim(to_char(b.occupation)), '[[:space:]]+', '') in
                   ('11','13','17','21','24','27','31','37','51','54','70','80','90')
              then regexp_replace(trim(to_char(b.occupation)), '[[:space:]]+', '')
              when regexp_replace(trim(to_char(a.occupation)), '[[:space:]]+', '') = '工人' then '24'
              when regexp_replace(trim(to_char(b.occupation)), '[[:space:]]+', '') = '工人' then '24'
              else '51'
          end

left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = '国籍代码'
     group by to_char(院标编码)
) country_by_code
       on country_by_code.院标编码 = upper(trim(to_char(b.citizenship)))

left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = '身份证件类型代码'
     group by to_char(院标编码)
) idtype_dict
       on idtype_dict.院标编码 =
          case
              when regexp_like(trim(to_char(b.id_type)), '^[0-9]$')
              then '0' || trim(to_char(b.id_type))
              else trim(to_char(b.id_type))
          end

left join (
    select to_char(院标名称) as 院标名称,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = 'ABO血型代码'
     group by to_char(院标名称)
) abo_dict
       on abo_dict.院标名称 = to_char(a.blood_type)

left join (
    select to_char(院标名称) as 院标名称,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = 'RH血型代码'
     group by to_char(院标名称)
) rh_dict
       on rh_dict.院标名称 = to_char(a.blood_type_rh)

left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = '入院途径代码'
     group by to_char(院标编码)
) adm_type_dict
       on adm_type_dict.院标编码 = to_char(coalesce(a.patient_class, b.patient_class))

left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = '家庭关系代码'
     group by to_char(院标编码)
) rel_dict
       on rel_dict.院标编码 = to_char(coalesce(a.relationship, b.relationship))

left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = '离院方式代码'
     group by to_char(院标编码)
) discharge_type_dict
       on discharge_type_dict.院标编码 = to_char(a.discharge_disposition)

left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = '转归方式代码'
     group by to_char(院标编码)
) outcome_dict
       on outcome_dict.院标编码 = to_char(a.discharge_disposition)

left join (
    select d.patient_id,
           d.visit_id,
           max(to_char(d.diagnosis_code)) keep (dense_rank first order by d.diagnosis_no) as diagnosis_code,
           max(to_char(d.diagnosis_desc)) keep (dense_rank first order by d.diagnosis_no) as diagnosis_desc
      from his.diagnosis d
     where d.diagnosis_type = '3'
       and d.diagnosis_no = '1'
     group by d.patient_id,
              d.visit_id
) main_diag
       on main_diag.patient_id = a.patient_id
      and main_diag.visit_id = a.visit_id

left join (
    select to_char(院标编码) as 院标编码,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = 'ICD-10诊断编码'
       and 系统标识 = 'HIS'
     group by to_char(院标编码)
) main_diag_code_cd
       on main_diag_code_cd.院标编码 = main_diag.diagnosis_code

left join (
    select to_char(院标名称) as 院标名称,
           max(to_char(国标编码)) as 国标编码,
           max(to_char(国标名称)) as 国标名称
      from cda.cda_dictionary
     where 字典名称 = 'ICD-10诊断编码'
       and 系统标识 = 'HIS'
     group by to_char(院标名称)
) main_diag_name_cd
       on main_diag_name_cd.院标名称 = main_diag.diagnosis_desc

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) director_sd
       on director_sd.emp_no = a.director

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) chief_sd
       on chief_sd.emp_no = a.chief_doctor

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) attending_sd
       on attending_sd.emp_no = a.attending_doctor

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) resident_sd
       on resident_sd.emp_no = a.doctor_in_charge

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) nurse_sd
       on nurse_sd.emp_no = a.duty_nurse

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) refresher_sd
       on refresher_sd.emp_no = a.advanced_studies_doctor

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) intern_sd
       on intern_sd.emp_no = a.practice_doctor

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) coder_sd
       on coder_sd.emp_no = a.cataloger

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) qcd_sd
       on to_char(qcd_sd.emp_no) = to_char(a.doctor_of_control_quality)

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) qcn_sd
       on qcn_sd.emp_no = a.nurse_of_control_quality

left join (
    select emp_no, max(name) as name, max(id_no) as id_no
      from his.staff_dict
     group by emp_no
) cdoctor_leader_sd
       on cdoctor_leader_sd.emp_no = a.cdoctor_leader

left join his.dept_dict adm_dept
       on adm_dept.dept_code = a.dept_admission_to

left join his.dept_dict dis_dept
       on dis_dept.dept_code = a.dept_discharge_from


left join (
    select d.patient_id,
           d.visit_id,
           max(to_char(d.diagnosis_code)) keep (dense_rank first order by d.diagnosis_no) as diagnosis_code,
           max(to_char(d.diagnosis_desc)) keep (dense_rank first order by d.diagnosis_no) as diagnosis_desc
      from his.diagnosis d
     where d.diagnosis_type = '7'
       and d.diagnosis_no = '1'
     group by d.patient_id,
              d.visit_id
) bl_diag
       on bl_diag.patient_id = a.patient_id
      and bl_diag.visit_id = a.visit_id




left join (
    select d.patient_id,
           d.visit_id,
           max(to_char(d.diagnosis_code)) keep (dense_rank first order by d.diagnosis_no) as diagnosis_code,
           max(to_char(d.diagnosis_desc)) keep (dense_rank first order by d.diagnosis_no) as diagnosis_desc
      from his.diagnosis d
     where d.diagnosis_type = '8'
       and d.diagnosis_no = '1'
     group by d.patient_id,
              d.visit_id
) sszd_diag
       on sszd_diag.patient_id = a.patient_id
      and sszd_diag.visit_id = a.visit_id
where a.discharge_date_time >= date '2021-01-01'
  and a.discharge_date_time <  date '2025-01-01'
