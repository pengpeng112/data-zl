
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_DOC_ORDER_CHECK" ("ID", "PATIENT_ID", "ODR_GN", "ORD_SN", "ODR_TYPE", "ORD_TIME", "ORD_FRE", "STATUS_CODE", "STATUS_NAME", "ODR_CODE", "ODR_NAME", "ODR_NOTE", "DPT_CODE", "DPT_NAME", "HOS_DPT_CODE", "HOS_DPT_NAME", "DOC_IDCARD", "DOC_NAME", "ODRISU_DT", "BEGIN_TIME", "EXE_DEPT_CODE", "EXE_DEPT_NAME", "NURSE_NAME", "NUR_E_DT", "STOP_DT", "STPDOC_IDCARD", "STPDOC_NAME", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "NAME", "SEX_CODE", "ID_NUM", "ORDER_ID", "ORDER_CATEGORY_CODE", "ORDER_CATEGORY_NAME", "ORDER_DOC_CERTIFICATE_NO", "ORDER_START_TIME", "ORDER_END_TIME", "ORDER_STATUS") AS 
  select substr('49557032X' || '|' || t.patient_id || '|' || t.visit_id || '|' || t.order_no || '|' || t.order_sub_no, 1, 100) as ID,--  内码  是 主键，必填

       t.patient_id || '|' || t.visit_id as PATIENT_ID,--  住院唯一标识号 是 必填项，病人某一次住院的唯一标识

       substr(to_char(t.order_no), 1, 24) as ODR_GN,--  医嘱组号    同一组相同治疗目的得医嘱

       substr(to_char(t.order_sub_no), 1, 12) as ORD_SN,--  组内顺序号

       case
           when t.repeat_indicator = 1 then 1
           when t.repeat_indicator = 0 then 2
           else 9
       end as ODR_TYPE,--  医嘱类型代码  是 必填 1、长期，2、临时，3，出院带药9、其他

       case
           when t.repeat_indicator = 1
            and t.start_date_time is not null
           then cast(
                    least(
                        greatest(
                            round(nvl(t.stop_date_time, pv.discharge_date_time) - t.start_date_time, 2),
                            0
                        ),
                        99.99
                    ) as number(4,2)
                )
           else cast(null as number(4,2))
       end as ORD_TIME,--  执行天数    长期医嘱填，超过99.99按99.99处理

       case
           when t.repeat_indicator = 1
            and t.freq_counter is not null
            and t.freq_interval is not null
            and t.freq_interval > 0
           then cast(
                    least(
                        greatest(
                            case
                                -- 每 N 天执行 X 次：每天次数 = X / N
                                when upper(trim(t.freq_interval_unit)) in ('日', '天', 'D', 'DAY', 'DAYS')
                                then round(t.freq_counter / t.freq_interval, 2)

                                -- 每 N 小时执行 X 次：每天次数 = X * 24 / N
                                when upper(trim(t.freq_interval_unit)) in ('小时', '时', 'H', 'HOUR', 'HOURS')
                                then round(t.freq_counter * 24 / t.freq_interval, 2)

                                -- 每 N 分钟执行 X 次：每天次数 = X * 1440 / N
                                when upper(trim(t.freq_interval_unit)) in ('分钟', '分', 'MI', 'MIN', 'MINUTE', 'MINUTES')
                                then round(t.freq_counter * 1440 / t.freq_interval, 2)

                                -- 每 N 周执行 X 次：每天次数 = X / (N * 7)
                                when upper(trim(t.freq_interval_unit)) in ('周', '星期', 'W', 'WEEK', 'WEEKS')
                                then round(t.freq_counter / (t.freq_interval * 7), 2)

                                -- 每 N 月执行 X 次：每天次数 = X / (N * 30)
                                when upper(trim(t.freq_interval_unit)) in ('月', 'M', 'MONTH', 'MONTHS')
                                then round(t.freq_counter / (t.freq_interval * 30), 2)

                                else null
                            end,
                            0
                        ),
                        99.99
                    ) as number(4,2)
                )
           else cast(null as number(4,2))
       end as ORD_FRE,-- 每天执行次数    长期医嘱填，超过99.99按99.99处理

       case to_char(t.order_status)
           when '1' then '1' -- 新开：医生签名
           when '2' then '3' -- 执行：已执行
           when '3' then '3' -- 停止：按已执行历史医嘱处理
           when '4' then '4' -- 作废：医生取消
           else '3'
       end as STATUS_CODE,-- 状态代码    DMD-40

       case to_char(t.order_status)
           when '1' then '医生签名'
           when '2' then '已执行'
           when '3' then '已执行'
           when '4' then '医生取消'
           else '已执行'
       end as STATUS_NAME,-- 状态

       substr(nvl(t.order_code, to_char(t.order_no)), 1, 32) as ODR_CODE,--  医嘱编码  是 按照院内标准填写，医嘱编码为空时暂用医嘱号兜底

       substr(nvl(t.order_text, '-'), 1, 100) as ODR_NAME,--  医嘱名称  是 按照院内标准填写

       cast(null as varchar2(800)) as ODR_NOTE,--  医嘱备注说明

       substr(
           nvl(
               (select ks.qmpt_code
                  from his.dept_dict ks
                 where ks.dept_code = t.ordering_dept
                   and rownum = 1),
               t.ordering_dept
           ),
           1,
           15
       ) as DPT_CODE,--  开嘱科室编码  是 省级标准科室值域

       substr(
           nvl(
               (select ks.qmpt_name
                  from his.dept_dict ks
                 where ks.dept_code = t.ordering_dept
                   and rownum = 1),
               nvl(
                   (select ks.dept_name
                      from his.dept_dict ks
                     where ks.dept_code = t.ordering_dept
                       and rownum = 1),
                   t.ordering_dept
               )
           ),
           1,
           50
       ) as DPT_NAME,--  开嘱科室名称  是 　必填

       substr(t.ordering_dept, 1, 20) as HOS_DPT_CODE,--  院内科室编码  是

       substr(
           nvl(
               (select ks.dept_name
                  from his.dept_dict ks
                 where ks.dept_code = t.ordering_dept
                   and rownum = 1),
               t.ordering_dept
           ),
           1,
           50
       ) as HOS_DPT_NAME,--  院内科室名称  是

       nvl(
           substr(
               (select sd.id_no
                  from his.staff_dict sd
                 where sd.emp_no = t.doctor_user
                   and rownum = 1),
               1,
               18
           ),
           '000000000000000000'
       ) as DOC_IDCARD,--  开嘱医生身份证号  是

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = t.doctor_user
                   and rownum = 1),
               t.doctor
           ),
           1,
           50
       ) as DOC_NAME,--  开嘱医生姓名  是 　必填

       cast(t.start_date_time as date) as ODRISU_DT,-- 医嘱下达时间  是 开立日期

       cast(nvl(t.verify_data_time, t.start_date_time) as date) as BEGIN_TIME,--  医嘱开始执行时间  是 字符型改为时间类型

       substr(
           nvl(
               (select ks.qmpt_code
                  from his.dept_dict ks
                 where ks.dept_code = t.exec_dept_code
                   and rownum = 1),
               t.exec_dept_code
           ),
           1,
           15
       ) as EXE_DEPT_CODE,-- 执行科室编码

       substr(
           nvl(
               (select ks.qmpt_name
                  from his.dept_dict ks
                 where ks.dept_code = t.exec_dept_code
                   and rownum = 1),
               nvl(
                   (select ks.dept_name
                      from his.dept_dict ks
                     where ks.dept_code = t.exec_dept_code
                       and rownum = 1),
                   t.exec_dept_name
               )
           ),
           1,
           50
       ) as EXE_DEPT_NAME,-- 执行科室名称

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = t.nurse_user
                   and rownum = 1),
               t.nurse
           ),
           1,
           50
       ) as NURSE_NAME,--  执行护士(医生)姓名

       cast(t.verify_data_time as date) as NUR_E_DT,--  护士（医生）执行时间    字符型改为时间类型

       cast(t.stop_date_time as date) as STOP_DT,-- 医嘱停止执行时间    字符型改为时间类型

       substr(
           (select sd.id_no
              from his.staff_dict sd
             where sd.emp_no = t.stop_doctor_user
               and rownum = 1),
           1,
           18
       ) as STPDOC_IDCARD,-- 停止执行医生身份证号

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = t.stop_doctor_user
                   and rownum = 1),
               t.stop_doctor
           ),
           1,
           50
       ) as STPDOC_NAME,-- 停止执行医生姓名

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 必填

       'INSERT' as EXCHANGE_TYPE,-- 交换类型  是

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是 必填

       substr(nvl(t2.name, '-'), 1, 50) as NAME,--  患者姓名  是 通过比对国家数据集增加的数据项

       decode(t2.sex, '男', '1', '女', '2', '未知', '0', '9') as SEX_CODE,--  患者性别代码  是 值域：0未知，1男，2女，9不明，通过比对国家数据集增加的数据项

       substr(nvl(t2.id_no, '000000000000000000'), 1, 18) as ID_NUM,--  患者身份证件号码  是 全部身份证件号码填写到该字段，通过比对国家数据集增加的数据项

       substr(to_char(t.order_no) || '|' || to_char(t.order_sub_no), 1, 100) as ORDER_ID,--  医嘱流水号 是 与检查/检验表/收费相关业务表保证关联性

       substr(
           nvl(
               (select cd.国标编码
                  from cda.cda_dictionary cd
                 where cd.字典名称 = '医嘱项目类型代码'
                   and cd.院标编码 = t.order_class
                   and rownum = 1),
               '99'
           ),
           1,
           100
       ) as ORDER_CATEGORY_CODE,-- 医嘱项目大类别编码 是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               (select cd.国标名称
                  from cda.cda_dictionary cd
                 where cd.字典名称 = '医嘱项目类型代码'
                   and cd.院标编码 = t.order_class
                   and rownum = 1),
               '其他'
           ),
           1,
           100
       ) as ORDER_CATEGORY_NAME,-- 医嘱项目大类别名称 是 通过比对国家数据集增加的数据项

       substr(
           nvl(
               (select yg.practice_cert_code
                  from doc_register_emp_match yg
                 where yg.emp_no = t.doctor_user
                   and rownum = 1),
               '-'
           ),
           1,
           100
       ) as ORDER_DOC_CERTIFICATE_NO,--  医嘱开立医生执业证书编号  是 通过比对国家数据集增加的数据项

       cast(t.start_date_time as date) as ORDER_START_TIME,--  医嘱开始时间  是 所有医嘱都必须填写

       case
           when t.repeat_indicator = 1
           then cast(nvl(nvl(t.stop_date_time, pv.discharge_date_time), date '1970-01-01') as date)
           else cast(date '1970-01-01' as date)
       end as ORDER_END_TIME,--  医嘱停止时间  是 长期医嘱必填，临时医嘱填写默认值1970-01-01

       case to_char(t.order_status)
           when '4' then '2' -- 作废：无效
           else '1'          -- 新开、执行、停止：有效
       end as ORDER_STATUS -- 医嘱有效标识  1.有效；2.无效

from his.orders t
left join his.pat_master_index t2
       on t.patient_id = t2.patient_id
left join his.pat_visit pv
       on t.patient_id = pv.patient_id
      and t.visit_id = pv.visit_id
where t.order_class not in ('A', 'B')
  and pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and pv.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss') and t.ordering_dept is not null
