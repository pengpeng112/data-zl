
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_OUTPATIENT_REGISTER" ("ID", "ORG_CODE", "ORG_NAME", "OUTPATIENT_NUM", "CASE_NUM", "NAME", "SEX_CODE", "SEX_NAME", "BORN_DATE", "FLAG_LOCAL", "AGE", "AGE_MONTH", "AGE_DAY", "AGE_HOUR", "HEALTH_CARD_NUM", "HEALTH_RECORD_NUM", "INSURANCE_NUM", "ID_NUM", "OTHER_ID_TYPE", "OTHER_ID_TYPE_NAME", "OTHER_ID_NUM", "PATIENT_ADDR", "PROVINCE", "CITY", "COUNTY", "TOWN", "VILLAGE", "HOUSE_NUM", "WORKING_ORG", "LINKMAN_RELATION", "LINKMAN", "TEL", "LINKMAN_TEL", "CHARGE_TYPE_CODE", "CHARGE_TYPE_NAME", "REG_TYPE_CODE", "REG_TYPE_NAME", "STD_DEPT_CODE", "DEP_CODE", "DEP_NAME", "HOS_DEP_CODE", "HOS_DEP_NAME", "DOCTOR_CODE", "DOCTOR_NAME", "REG_DATE", "FLAG_REFUND", "FLAG_VISIT", "FALG_FIRST_VISIT", "FLAG_REF", "CASHIER_ID", "CASHIER_NAME", "CITIZEN_ID", "EFFECTIVE_TIME", "STATUS", "DISTRICT_CODE", "EXCHANGE_TYPE", "DEI", "NODE_CODE", "ID_TYPE", "SYSTEM_TIME", "CZRK_ID", "DOC_ID_NUM", "OUTPATIENT_CODE", "REGISTER_TYPE", "REGISTER_TYPE_NAME", "REGISTER_FEE", "REGISTER_DATE", "APP_DATE", "REG_FEE") AS 
  select substr(
           '49557032X' || '|' ||
           nvl(a.clinic_no, a.patient_id || '|' || to_char(a.registering_date, 'yyyymmddhh24miss')),
           1,
           100
       ) as ID,-- 内码 是 主键

       '49557032X' as ORG_CODE,-- 医院组织机构代码 是 必填

       '山东省第二人民医院' as ORG_NAME,-- 医院名称 是 必填，填写标准医院名称

       substr(nvl(a.clinic_no, a.patient_id||to_char(a.visit_date,'yyyymmdd')), 1, 18) as OUTPATIENT_NUM,-- 本次门诊标识号 是 必填，唯一

       substr(a.patient_id, 1, 20) as CASE_NUM,-- 病历号

       substr(nvl(a.name, b.name), 1, 50) as NAME,-- 姓名 是 必填，病人的姓名

       decode(
           b.sex,
           '男', '1',
           '女', '2',
           '未知', '0',
           decode(a.sex, '1', '1', '男', '1', '2', '2', '女', '2', '未知', '0', '9')
       ) as SEX_CODE,-- 性别代码 是 值域：0未知，1男，2女，9不明

       decode(
           b.sex,
           '男', '男',
           '女', '女',
           '未知', '未知',
           decode(a.sex, '1', '男', '2', '女', '男', '男', '女', '女', '未知', '未知', '不明')
       ) as SEX_NAME,-- 性别 是

      nvl(cast(b.date_of_birth as date), date '1900-01-01') as BORN_DATE,-- 出生日期  as BORN_DATE,-- 出生日期 是 字符型改为时间类型

       cast(null as char(1)) as FLAG_LOCAL,-- 本地户籍标识 1:是 0否

       case
           when b.date_of_birth is not null
            and a.registering_date is not null
            and a.registering_date >= b.date_of_birth
           then least(greatest(trunc(months_between(a.registering_date, b.date_of_birth) / 12), 0), 200)
           when a.age is not null
           then least(greatest(a.age, 0), 200)
           else cast(null as number)
       end as AGE,-- 年龄 是 范围在0-200之间，不足1周岁填0

       case
           when b.date_of_birth is not null
            and a.registering_date is not null
            and a.registering_date >= b.date_of_birth
           then least(greatest(mod(trunc(months_between(a.registering_date, b.date_of_birth)), 12), 0), 11)
           else cast(null as number)
       end as AGE_MONTH,-- 年龄（月）

       case
           when b.date_of_birth is not null
            and a.registering_date is not null
            and a.registering_date >= b.date_of_birth
           then least(
                    greatest(
                        trunc(
                            a.registering_date -
                            add_months(
                                b.date_of_birth,
                                trunc(months_between(a.registering_date, b.date_of_birth))
                            )
                        ),
                        0
                    ),
                    30
                )
           else cast(null as number)
       end as AGE_DAY,-- 年龄（天）

       case
           when b.date_of_birth is not null
            and a.registering_date is not null
            and a.registering_date >= b.date_of_birth
           then least(
                    greatest(
                        trunc(
                            24 * (
                                (
                                    a.registering_date -
                                    add_months(
                                        b.date_of_birth,
                                        trunc(months_between(a.registering_date, b.date_of_birth))
                                    )
                                )
                                -
                                trunc(
                                    a.registering_date -
                                    add_months(
                                        b.date_of_birth,
                                        trunc(months_between(a.registering_date, b.date_of_birth))
                                    )
                                )
                            )
                        ),
                        0
                    ),
                    23
                )
           else cast(null as number)
       end as AGE_HOUR,-- 年龄（小时）

       cast(null as varchar2(32)) as HEALTH_CARD_NUM,-- 健康卡号

       cast(null as varchar2(32)) as HEALTH_RECORD_NUM,-- 健康档案号

       cast(null as varchar2(32)) as INSURANCE_NUM,-- 医疗保险号

       substr(nvl(b.id_no, '000000000000000000'), 1, 18) as ID_NUM,-- 身份证件号 是 患者身份证件号码

       substr(
           nvl(
               (select zd.国标编码
                  from cda.cda_dictionary zd
                 where zd.字典名称 = '身份证件类型代码'
                   and zd.院标编码 = b.id_type
                   and rownum = 1),
               case when b.id_no is not null then '01' else '99' end
           ),
           1,
           11
       ) as OTHER_ID_TYPE,-- 身份证件标识代码 是

       substr(
           nvl(
               (select zd.国标名称
                  from cda.cda_dictionary zd
                 where zd.字典名称 = '身份证件类型代码'
                   and zd.院标编码 = b.id_type
                   and rownum = 1),
               case when b.id_no is not null then '居民身份证' else '其他法定有效证件' end
           ),
           1,
           100
       ) as OTHER_ID_TYPE_NAME,-- 其他身份标识名称 是

       cast(null as varchar2(64)) as OTHER_ID_NUM,-- 其他身份号码

       cast(null as varchar2(100)) as PATIENT_ADDR,-- 患者现住址

       substr(
           (select pd.municipal_name
              from municipal_dict pd
             where pd.municipal_code = substr(b.id_no, 1, 2) || '0000'
               and pd.type = '省'
               and rownum = 1),
           1,
           70
       ) as PROVINCE,-- 居住地址-省

       substr(
           (select md.municipal_name
              from municipal_dict md
             where md.municipal_code = substr(b.id_no, 1, 4) || '00'
               and md.type = '市'
               and rownum = 1),
           1,
           70
       ) as CITY,-- 居住地址-市

       substr(
           (select dd.municipal_name
              from municipal_dict dd
             where dd.municipal_code = substr(b.id_no, 1, 6)
               and dd.type = '县'
               and rownum = 1),
           1,
           70
       ) as COUNTY,-- 居住地址-县（区）

       cast(null as varchar2(70)) as TOWN,-- 居住地址-乡镇街道

       cast(null as varchar2(70)) as VILLAGE,-- 居住地址-村街路弄

       cast(null as varchar2(70)) as HOUSE_NUM,-- 居住地址-门牌号码

       cast(null as varchar2(70)) as WORKING_ORG,-- 工作单位名称

       cast(null as varchar2(2)) as LINKMAN_RELATION,-- 联系人关系

       substr(b.next_of_kin, 1, 50) as LINKMAN,-- 联系人姓名

       substr(b.phone_number_home, 1, 20) as TEL,-- 本人电话

       substr(b.next_of_kin_phone, 1, 20) as LINKMAN_TEL,-- 联系人电话

       cast(null as varchar2(2)) as CHARGE_TYPE_CODE,-- 收费类别代码

       cast(null as varchar2(50)) as CHARGE_TYPE_NAME,-- 收费类别名称

       case
           when trim(a.clinic_type) in ('便民', '便民门诊') then '1'

           when trim(a.clinic_type) in (
               '普通号',
               '普通号中',
               '普通二',
               '主治医师',
               '优抚'
           ) then '2'

           when trim(a.clinic_type) in (
               '专家号主',
               '专家主',
               '专家主中',
               '专家主二',
               '专家副中',
               '专家副二',
               '专家号副',
               '知名专家',
               '知名专一',
               '知名专二',
               '知名专三',
               '知名专四',
               '知名专五'
           ) then '3'

           when trim(a.clinic_type) in ('急诊号', '急诊绿通')
             or trim(a.clinic_type) like '急诊%' then '4'

           when trim(a.clinic_type) = '留观' then '5'

           when trim(a.clinic_type) in (
               '义诊号',
               '免费号',
               '核酸检测',
               '高端门诊'
           ) then '9'

           else '9'
       end as REG_TYPE_CODE,-- 挂号类别代码 是 值域：1便民门诊，2普通门诊，3专家门诊，4急诊，5留观，9其他

       case
           when trim(a.clinic_type) in ('便民', '便民门诊') then '便民门诊'

           when trim(a.clinic_type) in (
               '普通号',
               '普通号中',
               '普通二',
               '主治医师',
               '优抚'
           ) then '普通门诊'

           when trim(a.clinic_type) in (
               '专家号主',
               '专家主',
               '专家主中',
               '专家主二',
               '专家副中',
               '专家副二',
               '专家号副',
               '知名专家',
               '知名专一',
               '知名专二',
               '知名专三',
               '知名专四',
               '知名专五'
           ) then '专家门诊'

           when trim(a.clinic_type) in ('急诊号', '急诊绿通')
             or trim(a.clinic_type) like '急诊%' then '急诊'

           when trim(a.clinic_type) = '留观' then '留观'

           else '其他'
       end as REG_TYPE_NAME,-- 挂号类别名称 是

       substr(
           nvl(
               (select dept.qmpt_code
                  from his.dept_dict dept
                 where dept.dept_code = a.visit_dept
                   and rownum = 1),
               a.visit_dept
           ),
           1,
           20
       ) as STD_DEPT_CODE,-- 标准科室编码

    nvl( substr(
           nvl(
               (select dept.qmpt_code
                  from his.dept_dict dept
                 where dept.dept_code = a.visit_dept
                   and rownum = 1),
               a.visit_dept
           ),
           1,
           20
       ),'-') as DEP_CODE,-- 就诊科室编号 是

         nvl(   substr(
           nvl(
               (select dept.qmpt_name
                  from his.dept_dict dept
                 where dept.dept_code = a.visit_dept
                   and rownum = 1),
               nvl(
                   (select dept.dept_name
                      from his.dept_dict dept
                     where dept.dept_code = a.visit_dept
                       and rownum = 1),
                   a.visit_dept
               )
           ),
           1,
           50
       ),'-') as DEP_NAME,-- 就诊科室名称 是

        nvl(  substr(a.visit_dept, 1, 20) ,'-') as HOS_DEP_CODE,-- 院内科室编码 是

        nvl(  substr(
           nvl(
               (select dept.dept_name
                  from his.dept_dict dept
                 where dept.dept_code = a.visit_dept
                   and rownum = 1),
               a.visit_dept
           ),
           1,
           50
       ),'-') as HOS_DEP_NAME,-- 院内科室名称 是

    nvl( a.doctor,'-')  as DOCTOR_CODE,-- 医生代码 是

      nvl( substr(
           nvl(
               (select s.name
                  from his.staff_dict s
                 where s.emp_no = a.doctor
                   and rownum = 1),
               a.doctor
           ),
           1,
           50
       ),'-')  as DOCTOR_NAME,-- 医生姓名 是

       cast(
           nvl(
               (
                   select min(to_date(aa.registertime, 'yyyy-mm-dd hh24:mi:ss'))
                     from shunneng.appointinfoview aa
                    where aa.sfzh = b.id_no
                      and aa.deptid = a.visit_dept
                      and regexp_like(aa.registertime, '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$')
                      and to_date(aa.registertime, 'yyyy-mm-dd hh24:mi:ss') >= a.registering_date - 7
                      and to_date(aa.registertime, 'yyyy-mm-dd hh24:mi:ss') <  a.registering_date
               ),
               a.registering_date
           ) as date
       ) as REG_DATE,-- 挂号日期 是；预约号取预约操作时间，无预约记录取挂号时间

       case
           when a.returned_date is null then '0'
           else '1'
       end as FLAG_REFUND,-- 退号标志 是 1是0否

       case
           when a.returned_date is not null then '0'
           else '1'
       end as FLAG_VISIT,-- 是否就诊标识

       case
           when a.clinic_type = '留观' then '3'
           when exists (
                    select 1
                      from his.clinic_master x
                     where x.patient_id = a.patient_id
                       and x.registering_date < a.registering_date
                       and rownum = 1
                )
           then '2'
           else '1'
       end as FALG_FIRST_VISIT,-- 初复诊标识 是 1初诊，2复诊，3留观

       cast(null as char(1)) as FLAG_REF,-- 是否转诊

       cast(null as varchar2(18)) as CASHIER_ID,-- 收费人代码

       cast(null as varchar2(50)) as CASHIER_NAME,-- 收费人名称

       cast(null as varchar2(32)) as CITIZEN_ID,-- 个人内码

       cast(a.registering_date as date) as EFFECTIVE_TIME,-- 活动发生时间

       cast(null as varchar2(32)) as STATUS,-- 卡片状态

       '370104' as DISTRICT_CODE,-- 所属行政区划 是

       'INSERT' as EXCHANGE_TYPE,-- 交换类型 是

       cast(null as varchar2(50)) as DEI,-- 数据交换标识符

       cast(null as varchar2(50)) as NODE_CODE,-- 节点标识符

       cast(null as varchar2(2)) as ID_TYPE,-- 身份证件类型 16版字段，重复，请忽略

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       cast(null as varchar2(36)) as CZRK_ID,-- 常住人口ID

       substr(
           (select s.id_no
              from his.staff_dict s
             where s.emp_no = a.doctor
               and rownum = 1),
           1,
           18
       ) as DOC_ID_NUM,-- 就诊医师身份证号

       case
           when trim(a.clinic_type) = '留观' then '3'
           when trim(a.clinic_type) in ('急诊号', '急诊绿通')
             or trim(a.clinic_type) like '急诊%' then '1'
           else '2'
       end as OUTPATIENT_CODE,-- 门诊/急诊标志

       case
           when exists (
                    select 1
                      from shunneng.appointinfoview aa
                     where aa.sfzh = b.id_no
                       and aa.deptid = a.visit_dept
                       and regexp_like(aa.registertime, '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$')
                       and to_date(aa.registertime, 'yyyy-mm-dd hh24:mi:ss') >= a.registering_date - 7
                       and to_date(aa.registertime, 'yyyy-mm-dd hh24:mi:ss') <  a.registering_date
                )
           then '2.3'
           else '1'
       end as REGISTER_TYPE,-- 挂号途径 是 1现场，2.3医疗机构预约

       case
           when exists (
                    select 1
                      from shunneng.appointinfoview aa
                     where aa.sfzh = b.id_no
                       and aa.deptid = a.visit_dept
                       and regexp_like(aa.registertime, '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$')
                       and to_date(aa.registertime, 'yyyy-mm-dd hh24:mi:ss') >= a.registering_date - 7
                       and to_date(aa.registertime, 'yyyy-mm-dd hh24:mi:ss') <  a.registering_date
                )
           then '医疗机构预约'
           else '现场挂号'
       end as REGISTER_TYPE_NAME,-- 挂号途径名称 是

       cast(
           least(
               greatest(round(nvl(a.clinic_charge, 0), 2), 0),
               9999.99
           ) as number(6,2)
       ) as REGISTER_FEE,-- 挂号费用

       cast(a.registering_date as date) as REGISTER_DATE,-- 预约挂号时间 是；无号源就诊时间字段时暂用实际挂号/就诊时间

       cast(a.registering_date as date) as APP_DATE,-- 诊疗时间 是；无叫诊时间来源时暂用挂号时间

       cast(round(nvl(a.clinic_charge, 0), 2) as number) as REG_FEE-- 挂号费/医事服务费 是

from his.clinic_master a
left join his.pat_master_index b
       on a.patient_id = b.patient_id
where a.registering_date >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and a.registering_date <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')  and  substr(
           '49557032X' || '|' ||
           nvl(a.clinic_no, a.patient_id || '|' || to_char(a.registering_date, 'yyyymmddhh24miss')),
           1,
           100
       )  not in ('49557032X|2023122539994','49557032X|2023022024877') and nvl(a.name, b.name) is not null
       --and a.RETURNED_DATE  is null
       and substr(a.visit_dept, 1, 20)  is not null
