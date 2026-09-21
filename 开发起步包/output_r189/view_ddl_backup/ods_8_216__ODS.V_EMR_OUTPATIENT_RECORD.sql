
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_OUTPATIENT_RECORD" ("ID", "OUTPATIENT_NUM", "NAME", "CZRK_ID", "ID_NUM", "OTHER_CARD_CODE", "OTHER_CARD_NO", "CLINIC_EMERGENCY_MARK_CODE", "FALG_FIRST_VISIT", "FALG_FIRST_VISIT_NAME", "CHIEF_COMPLAINT", "MEDICAL_HISTORY", "EXAMINATION_RECORD", "TCM_WM_MARK_CODE", "TCM_WM_MARK_NAME", "ADMIN_ILLNESS_CODE", "ADMIN_ILLNESS_NAME", "OTHER_ILLNESS_CODE", "OTHER_ILLNESS_NAME", "DIAGNOSIS_SUGGESTION", "DIAGNOSIS_ALL_COST", "SELF_ALL_COST", "ORG_CODE", "ORG_NAME", "TREATMENT_SECTION_CODE", "TREATMENT_SECTION_NAME", "TREATMENT_DOC_ID_NUM", "TREATMENT_DOC_ID_NAME", "TREATMENT_DATE", "DISTRICT_CODE", "SYSTEM_TIME", "EXCHANGE_TYPE", "TREATMENT", "REGISTRATION_NUMBER", "IS_BMIDO", "CAMPUS_CODE", "CAMPUS_NAME", "MARRIAGE", "NATIONALITY", "PROFESSION", "EDU_BACKGROUND", "NATION_CODE", "EMERGENCY_LEVEL", "INSU_TYPE_CODE", "INSU_TYPE_NAME", "PHYSICIAN_CERTIFICATE_NO", "PHYSICIAN_TITLE", "PERMANENT_PROVINCE", "PERMANENT_CITY", "PERMANENT_COUNTY", "PERMANENT_TOWN") AS 
  select substr(
           '49557032X' || '|' ||
           nvl(t.clinic_no, '-') || '|' ||
           nvl(a.patient_id, '-') || '|' ||
           to_char(a.visit_date, 'yyyymmdd') || '|' ||
           nvl(to_char(a.visit_no), '-') || '|' ||
           nvl(to_char(a.ordinal), '-'),
           1,
           100
       ) as ID,-- 内码 是 主键

       substr(nvl(t.clinic_no, t.patient_id||to_char(t.visit_date,'yyyymmdd')), 1, 18)
           as OUTPATIENT_NUM,-- 本次门诊标识符

       substr(nvl(pmi.name, a.patient_id), 1, 50)
           as NAME,-- 姓名

       cast(null as varchar2(36))
           as CZRK_ID,-- 常住人口ID

       substr(pmi.id_no, 1, 18)
           as ID_NUM,-- 身份证号码

       cast(null as char(11))
           as OTHER_CARD_CODE,-- 其他证件类别代码

       cast(null as varchar2(18))
           as OTHER_CARD_NO,-- 其他证件号码

       case
           when t.clinic_type = '留观' then '3'
           when t.clinic_type like '%急诊%' then '1'
           else '2'
       end as CLINIC_EMERGENCY_MARK_CODE,-- 门诊/急诊标志代码

       /*
        * 保留原初复诊判断逻辑。
        * 建议通过CLINIC_MASTER复合索引优化。
        */
       case
           when t.clinic_type = '留观' then '3'
           when exists (
                    select 1
                      from his.clinic_master x
                     where x.patient_id = t.patient_id
                       and x.returned_date is null
                       and x.registering_date < t.registering_date
                       and rownum = 1
                )
           then '2'
           else '1'
       end as FALG_FIRST_VISIT,-- 初复诊标志代码

       case
           when t.clinic_type = '留观' then '留观'
           when exists (
                    select 1
                      from his.clinic_master x
                     where x.patient_id = t.patient_id
                       and x.returned_date is null
                       and x.registering_date < t.registering_date
                       and rownum = 1
                )
           then '复诊'
           else '初诊'
       end as FALG_FIRST_VISIT_NAME,-- 初复诊标志名称

       substr(nvl(a.illness_desc, '未记录'), 1, 2000)
           as CHIEF_COMPLAINT,-- 主诉记录

       substr(nvl(a.anamnesis, '未记录'), 1, 2000)
           as MEDICAL_HISTORY,-- 病史

       substr(a.body_exam, 1, 2000)
           as EXAMINATION_RECORD,-- 体格检查记录

       case
           when a.cdiag is not null then '1'
           else '2'
       end as TCM_WM_MARK_CODE,-- 中医/西医诊断类型

       case
           when a.cdiag is not null then '中医'
           else '西医'
       end as TCM_WM_MARK_NAME,-- 中医/西医诊断类型名称

       /*
        * 原SQL中四次查询OUTP_MR_DIAG_DESC和CDA_DICTIONARY，
        * 现改为下方DG内联视图一次汇总。
        */
       substr(dg.admin_illness_code, 1, 50)         as ADMIN_ILLNESS_CODE,-- 主要诊断疾病代码

       cast(
           substrb(
               coalesce(
                   dg.admin_illness_name,
                   nullif(trim(to_char(a.diag_desc)), ''),
                   '-'
               ),
               1,
               100
           ) as varchar2(100)
       ) as ADMIN_ILLNESS_NAME,-- 主要诊断疾病名称

       substr(dg.other_illness_code, 1, 50)
           as OTHER_ILLNESS_CODE,-- 其他诊断疾病代码1

       cast(
           substrb(
               dg.other_illness_name,
               1,
               100
           ) as varchar2(100)
       ) as OTHER_ILLNESS_NAME,-- 其他诊断疾病名称1

       substr(a.advice, 1, 1000)
           as DIAGNOSIS_SUGGESTION,-- 治疗处理意见

       cast(nvl(e.total_costs, 0) as number(10, 2))
           as DIAGNOSIS_ALL_COST,-- 诊疗总费用

       cast(null as number(10, 2))
           as SELF_ALL_COST,-- 个人支付诊疗费用

       '49557032X'
           as ORG_CODE,-- 就诊医疗机构编码

       '山东省第二人民医院'
           as ORG_NAME,-- 就诊医疗机构名称

       substr(
           nvl(
               (
                   select d.qmpt_code
                     from his.dept_dict d
                    where d.dept_code = t.visit_dept
                      and rownum = 1
               ),
               t.visit_dept
           ),
           1,
           20
       ) as TREATMENT_SECTION_CODE,-- 就诊科室编码

       cast(
           substrb(
               coalesce(
                   (
                       select max(to_char(d.qmpt_name))
                         from his.dept_dict d
                        where d.dept_code = t.visit_dept
                   ),
                   (
                       select max(to_char(d.dept_name))
                         from his.dept_dict d
                        where d.dept_code = t.visit_dept
                   ),
                   to_char(t.visit_dept),
                   '-'
               ),
               1,
               50
           ) as varchar2(50)
       ) as TREATMENT_SECTION_NAME,-- 就诊科室名称

       substr(
           (
               select max(
                          case
                              when regexp_like(
                                       upper(c.id_no),
                                       '^[0-9]{17}([0-9]|X)$'
                                   )
                              then upper(c.id_no)
                          end
                      )
                 from his.staff_dict c
                where c.emp_no = a.doctor_no
           ),
           1,
           18
       ) as TREATMENT_DOC_ID_NUM,-- 就诊医师身份证号

       substr(
           nvl(
               (
                   select c.name
                     from his.staff_dict c
                    where c.emp_no = a.doctor_no
                      and rownum = 1
               ),
               nvl(a.doctor, a.doctor_no)
           ),
           1,
           50
       ) as TREATMENT_DOC_ID_NAME,-- 就诊医师姓名

       cast(nvl(t.registering_date, a.illness_date) as date)
           as TREATMENT_DATE,-- 就诊日期和时间

       '370104'
           as DISTRICT_CODE,-- 所属行政区划

       cast(systimestamp as timestamp)
           as SYSTEM_TIME,-- 数据上传时间戳

       'INSERT'
           as EXCHANGE_TYPE,-- 交换类型

       substr(nvl(a.operation_record, '未记录'), 1, 2000)
           as TREATMENT,-- 处置

       '49557032X'
           as REGISTRATION_NUMBER,-- 医疗机构执业许可证登记号

       '1'
           as IS_BMIDO,-- 是否基本医保定点机构

       '49557032X'
           as CAMPUS_CODE,-- 院区代码

       '山东省第二人民医院'
           as CAMPUS_NAME,-- 院区名称

       case regexp_replace(
                trim(nvl(pmi.marital_status, '')),
                '[[:space:]]+',
                ''
            )
           when '1'    then '10'
           when '未婚' then '10'

           when '2'    then '20'
           when '已婚' then '20'
           when '再婚' then '20'

           when '3'    then '30'
           when '丧偶' then '30'

           when '4'    then '40'
           when '离婚' then '40'
           when '离异' then '40'

           when '0'    then '90'
           when '5'    then '90'
           when '9'    then '90'
           when '其他' then '90'
           when ''     then '90'

           else '90'
       end as MARRIAGE,-- 婚姻状况

       case regexp_replace(
                trim(nvl(pmi.nation, '')),
                '[[:space:]]+',
                ''
            )
           when '01' then '01'
           when '1' then '01'
           when '汉' then '01'
           when '汉族' then '01'
           when '汉族族' then '01'

           when '02' then '02'
           when '2' then '02'
           when '蒙古' then '02'
           when '蒙古族' then '02'

           when '03' then '03'
           when '3' then '03'
           when '回' then '03'
           when '回族' then '03'

           when '04' then '04'
           when '4' then '04'
           when '藏' then '04'
           when '藏族' then '04'

           when '05' then '05'
           when '5' then '05'
           when '维吾尔' then '05'
           when '维吾尔族' then '05'

           when '06' then '06'
           when '6' then '06'
           when '苗' then '06'
           when '苗族' then '06'

           when '07' then '07'
           when '7' then '07'
           when '彝' then '07'
           when '彝族' then '07'

           when '08' then '08'
           when '8' then '08'
           when '壮' then '08'
           when '壮族' then '08'

           when '09' then '09'
           when '9' then '09'
           when '布依' then '09'
           when '布依族' then '09'

           when '10' then '10'
           when '朝鲜' then '10'
           when '朝鲜族' then '10'

           when '11' then '11'
           when '满' then '11'
           when '满族' then '11'

           when '12' then '12'
           when '侗' then '12'
           when '侗族' then '12'

           when '13' then '13'
           when '瑶' then '13'
           when '瑶族' then '13'

           when '14' then '14'
           when '白' then '14'
           when '白族' then '14'

           when '15' then '15'
           when '土家' then '15'
           when '土家族' then '15'

           when '16' then '16'
           when '哈尼' then '16'
           when '哈尼族' then '16'

           when '17' then '17'
           when '哈萨克' then '17'
           when '哈萨克族' then '17'

           when '18' then '18'
           when '傣' then '18'
           when '傣族' then '18'

           when '19' then '19'
           when '黎' then '19'
           when '黎族' then '19'

           when '20' then '20'
           when '傈僳' then '20'
           when '傈僳族' then '20'

           when '21' then '21'
           when '佤' then '21'
           when '佤族' then '21'

           when '22' then '22'
           when '畲' then '22'
           when '畲族' then '22'

           when '23' then '23'
           when '高山' then '23'
           when '高山族' then '23'

           when '24' then '24'
           when '拉祜' then '24'
           when '拉祜族' then '24'

           when '25' then '25'
           when '水' then '25'
           when '水族' then '25'

           when '26' then '26'
           when '东乡' then '26'
           when '东乡族' then '26'

           when '27' then '27'
           when '纳西' then '27'
           when '纳西族' then '27'

           when '28' then '28'
           when '景颇' then '28'
           when '景颇族' then '28'

           when '29' then '29'
           when '柯尔克孜' then '29'
           when '柯尔克孜族' then '29'
           when '柯尔柯孜族' then '29'

           when '30' then '30'
           when '土' then '30'
           when '土族' then '30'

           when '31' then '31'
           when '达斡尔' then '31'
           when '达斡尔族' then '31'
           when '达尔族' then '31'

           when '32' then '32'
           when '仫佬' then '32'
           when '仫佬族' then '32'

           when '33' then '33'
           when '羌' then '33'
           when '羌族' then '33'

           when '34' then '34'
           when '布朗' then '34'
           when '布朗族' then '34'

           when '35' then '35'
           when '撒拉' then '35'
           when '撒拉族' then '35'

           when '36' then '36'
           when '毛南' then '36'
           when '毛南族' then '36'
           when '毛难族' then '36'

           when '37' then '37'
           when '仡佬' then '37'
           when '仡佬族' then '37'

           when '38' then '38'
           when '锡伯' then '38'
           when '锡伯族' then '38'

           when '39' then '39'
           when '阿昌' then '39'
           when '阿昌族' then '39'

           when '40' then '40'
           when '普米' then '40'
           when '普米族' then '40'

           when '41' then '41'
           when '塔吉克' then '41'
           when '塔吉克族' then '41'

           when '42' then '42'
           when '怒' then '42'
           when '怒族' then '42'

           when '43' then '43'
           when '乌孜别克' then '43'
           when '乌孜别克族' then '43'

           when '44' then '44'
           when '俄罗斯' then '44'
           when '俄罗斯族' then '44'

           when '45' then '45'
           when '鄂温克' then '45'
           when '鄂温克族' then '45'

           when '46' then '46'
           when '德昂' then '46'
           when '德昂族' then '46'

           when '47' then '47'
           when '保安' then '47'
           when '保安族' then '47'

           when '48' then '48'
           when '裕固' then '48'
           when '裕固族' then '48'

           when '49' then '49'
           when '京' then '49'
           when '京族' then '49'

           when '50' then '50'
           when '塔塔尔' then '50'
           when '塔塔尔族' then '50'

           when '51' then '51'
           when '独龙' then '51'
           when '独龙族' then '51'

           when '52' then '52'
           when '鄂伦春' then '52'
           when '鄂伦春族' then '52'

           when '53' then '53'
           when '赫哲' then '53'
           when '赫哲族' then '53'

           when '54' then '54'
           when '门巴' then '54'
           when '门巴族' then '54'

           when '55' then '55'
           when '珞巴' then '55'
           when '珞巴族' then '55'

           when '56' then '56'
           when '基诺' then '56'
           when '基诺族' then '56'

           else '66'
       end as NATIONALITY,-- 民族

       nvl(
           (
               select zd.国标编码
                 from cda.cda_dictionary zd
                where zd.字典名称 = '职业代码'
                  and zd.院标编码 = pmi.occupation
                  and rownum = 1
           ),
           '51'
       ) as PROFESSION,-- 职业

       cast(null as varchar2(20))
           as EDU_BACKGROUND,-- 学历

       case
           when trim(pmi.citizenship) in (
                    '中国', '中国籍', '中华人民共和国', 'CHN', 'CN'
                )
           then '156'

           when trim(pmi.citizenship) in (
                    '美国', '美国籍', '美利坚合众国', 'USA', 'US'
                )
           then '840'

           when trim(pmi.citizenship) in (
                    '日本', '日本籍', 'JPN', 'JP'
                )
           then '392'

           when trim(pmi.citizenship) in (
                    '韩国', '韩国籍', '大韩民国', 'KOR', 'KR'
                )
           then '410'

           when trim(pmi.citizenship) in (
                    '朝鲜', '朝鲜籍', 'PRK', 'KP'
                )
           then '408'

           when trim(pmi.citizenship) in (
                    '英国', '英国籍', 'GBR', 'UK', 'GB'
                )
           then '826'

           when trim(pmi.citizenship) in (
                    '俄罗斯', '俄罗斯籍', '俄国', 'RUS', 'RU'
                )
           then '643'

           when trim(pmi.citizenship) in (
                    '加拿大', '加拿大籍', 'CAN', 'CA'
                )
           then '124'

           when trim(pmi.citizenship) in (
                    '澳大利亚', '澳大利亚籍', 'AUS', 'AU'
                )
           then '036'

           when trim(pmi.citizenship) in (
                    '德国', '德国籍', 'DEU', 'DE'
                )
           then '276'

           when trim(pmi.citizenship) in (
                    '法国', '法国籍', 'FRA', 'FR'
                )
           then '250'

           when trim(pmi.citizenship) in (
                    '新加坡', '新加坡籍', 'SGP', 'SG'
                )
           then '702'

           when trim(pmi.citizenship) in (
                    '马来西亚', '马来西亚籍', 'MYS', 'MY'
                )
           then '458'

           when trim(pmi.citizenship) in (
                    '泰国', '泰国籍', 'THA', 'TH'
                )
           then '764'

           when trim(pmi.citizenship) in (
                    '越南', '越南籍', 'VNM', 'VN'
                )
           then '704'

           when trim(pmi.citizenship) in (
                    '印度', '印度籍', 'IND', 'IN'
                )
           then '356'

           when trim(pmi.citizenship) in (
                    '菲律宾', '菲律宾籍', 'PHL', 'PH'
                )
           then '608'

           when trim(pmi.citizenship) in (
                    '印度尼西亚', '印尼', '印度尼西亚籍', 'IDN', 'ID'
                )
           then '360'

           else null
       end as NATION_CODE,-- 国籍

       cast(null as varchar2(20))
           as EMERGENCY_LEVEL,-- 急诊分级

       substr(
           case
               when t.insur_jg in ('370100', '379902', '379903')
                and t.rqlb = 'A'
               then '11'

               when t.insur_jg in ('370100', '379902', '379903')
                and t.rqlb = 'B'
               then '21'

               when t.insur_jg = '370000'
                and t.rqlb = 'A'
               then '12'

               when t.insur_jg = '370000'
                and t.rqlb = 'B'
               then '22'

               else '70'
           end,
           1,
           20
       ) as INSU_TYPE_CODE,-- 医保类别编码

       substr(
           case
               when t.insur_jg in ('370100', '379902', '379903')
                and t.rqlb = 'A'
               then '本市职工基本医疗保险'

               when t.insur_jg in ('370100', '379902', '379903')
                and t.rqlb = 'B'
               then '本市居民基本医疗保险'

               when t.insur_jg = '370000'
                and t.rqlb = 'A'
               then '外埠职工基本医疗保险'

               when t.insur_jg = '370000'
                and t.rqlb = 'B'
               then '外埠居民基本医疗保险'

               else '全自费'
           end,
           1,
           100
       ) as INSU_TYPE_NAME,-- 医保类别名称

         nvl(   substr(
           nvl(
               nullif(
                   trim(
                       (
                           select yg.practice_cert_code
                             from doc_register_emp_match yg
                            where yg.emp_no = a.doctor_no
                              and rownum = 1
                       )
                   ),
                   ''
               ),
               '-'
           ),
           1,
           100
       ) ,'-')  as PHYSICIAN_CERTIFICATE_NO,-- 接诊医生执业证书编号

        nvl(    substr(
           nvl(
               (
                   select td.drg_code
                     from his.staff_dict sd
                     left join title_dict td
                            on sd.title = td.title_name
                    where sd.emp_no = a.doctor_no
                      and rownum = 1
               ),
               '-'
           ),
           1,
           100
       ),'-')  as PHYSICIAN_TITLE,-- 接诊医生职称

         nvl(    substr(
           coalesce(
               nullif(
                   cast(trim(pmi.preadd_province) as varchar2(100)),
                   ''
               ),
               (
                   select cast(max(md.municipal_name) as varchar2(100))
                     from municipal_dict md
                    where md.municipal_code =
                          substr(pmi.id_no, 1, 2) || '0000'
                      and md.type = '省'
               ),
               '-'
           ),
           1,
           100
       ) ,'-') as PERMANENT_PROVINCE,-- 常住地址-省

        nvl(     substr(
           coalesce(
               nullif(
                   cast(trim(pmi.preadd_city) as varchar2(100)),
                   ''
               ),
               (
                   select cast(max(md.municipal_name) as varchar2(100))
                     from municipal_dict md
                    where md.municipal_code =
                          substr(pmi.id_no, 1, 4) || '00'
                      and md.type = '市'
               ),
               '-'
           ),
           1,
           100
       ),'-')  as PERMANENT_CITY,-- 常住地址-市

         nvl(    substr(
           coalesce(
               nullif(
                   cast(trim(pmi.preadd_county) as varchar2(100)),
                   ''
               ),
               (
                   select cast(max(md.municipal_name) as varchar2(100))
                     from municipal_dict md
                    where md.municipal_code =
                          substr(pmi.id_no, 1, 6)
                      and md.type = '县'
               ),
               '-'
           ),
           1,
           100
       ),'-')  as PERMANENT_COUNTY,-- 常住地址-县

    nvl(   substr(
           coalesce(
               nullif(
                   cast(trim(pmi.patient_area_address) as varchar2(100)),
                   ''
               ),
               '-'
           ),
           1,
           100
       ),'-') as PERMANENT_TOWN-- 常住地址-乡镇

  /*
   * 先过滤CLINIC_MASTER的日期和退号状态，
   * 减少后续参与连接的数据量。
   */
  from (
        select cm.*
          from his.clinic_master cm
         where cm.returned_date is null
           and cm.registering_date >= date '2021-01-01'
           and cm.registering_date <  date '2025-01-01'
       ) t

  /*
   * ORDINAL='1'提前过滤。
   * 日期关联改为范围判断，等价于：
   * TRUNC(A.VISIT_DATE)=TRUNC(T.VISIT_DATE)
   */
  inner join (
        select mr.*
          from his.outp_mr mr
         where mr.ordinal = '1'
       ) a
          on a.patient_id = t.patient_id
         and a.visit_no   = t.visit_no
         and a.visit_date >= trunc(t.visit_date)
         and a.visit_date <  trunc(t.visit_date) + 1

  inner join his.pat_master_index pmi
          on pmi.patient_id = a.patient_id

  /*
   * 费用汇总保留原口径：
   * 患者+收费日期汇总未退费记录。
   *
   * 增加2021-2025日期条件，不改变结果，
   * 因为主查询只关联该范围内的就诊日期。
   */
  left join (
        select r.patient_id,
               trunc(r.visit_date) as rcpt_date,
               sum(nvl(r.total_costs, 0)) as total_costs
          from his.outp_rcpt_master r
         where r.refunded_rcpt_no is null
           and r.visit_date >= date '2021-01-01'
           and r.visit_date <  date '2025-01-01'
         group by r.patient_id,
                  trunc(r.visit_date)
       ) e
         on e.patient_id = t.patient_id
        and e.rcpt_date  = trunc(t.registering_date)

  /*
   * 一次性取得主诊断、其他诊断的编码和名称，
   * 替代原SQL中的四个相关子查询。
   */
  left join (
        select d.patient_id,
               d.visit_no,
               d.visit_date,

               nvl(
                   max(
                       case
                           when to_char(d.item_no) = '1'
                           then dict.gb_code_any
                       end
                   ),
                   max(
                       case
                           when to_char(d.item_no) = '1'
                           then to_char(d.diag_code)
                       end
                   )
               ) as admin_illness_code,

               nvl(
                   max(
                       case
                           when to_char(d.item_no) = '1'
                           then dict.gb_name_prefix
                       end
                   ),
                   max(
                       case
                           when to_char(d.item_no) = '1'
                           then to_char(d.diag_desc)
                       end
                   )
               ) as admin_illness_name,

               nvl(
                   max(
                       case
                           when to_char(d.item_no) = '2'
                           then dict.gb_code_any
                       end
                   ),
                   max(
                       case
                           when to_char(d.item_no) = '2'
                           then to_char(d.diag_code)
                       end
                   )
               ) as other_illness_code,

               nvl(
                   max(
                       case
                           when to_char(d.item_no) = '2'
                           then dict.gb_name_any
                       end
                   ),
                   max(
                       case
                           when to_char(d.item_no) = '2'
                           then to_char(d.diag_desc)
                       end
                   )
               ) as other_illness_name

          from his.outp_mr_diag_desc d
          left join (
                select cd.院标编码,

                       max(
                           case
                               when cd.字典名称 like '%ICD-10%'
                               then to_char(cd.国标编码)
                           end
                       ) as gb_code_any,

                       max(
                           case
                               when cd.字典名称 like 'ICD-10%'
                               then to_char(cd.国标名称)
                           end
                       ) as gb_name_prefix,

                       max(
                           case
                               when cd.字典名称 like '%ICD-10%'
                               then to_char(cd.国标名称)
                           end
                       ) as gb_name_any

                  from cda.cda_dictionary cd
                 where cd.系统标识 = 'HIS'
                   and cd.字典名称 like '%ICD-10%'
                 group by cd.院标编码
               ) dict
            on dict.院标编码 = d.diag_code

         where to_char(d.item_no) in ('1', '2')

         group by d.patient_id,
                  d.visit_no,
                  d.visit_date
       ) dg
         on dg.patient_id = t.patient_id
        and dg.visit_no   = t.visit_no
        and dg.visit_date = a.visit_date
