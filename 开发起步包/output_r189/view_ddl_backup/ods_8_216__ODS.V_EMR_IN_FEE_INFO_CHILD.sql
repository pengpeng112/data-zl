
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_IN_FEE_INFO_CHILD" ("ID", "PATIENT_ID", "PROJ_DENO", "PROJ_NAME", "HOS_PROJ_DENO", "HOS_PROJ_NAME", "FEE_CAT_CODE", "PROJ_UP", "PROJ_AMT", "PROJ_MON", "IND_PAY", "SELF_PAY", "RCD_IDCARD", "RCD_NUMBERAME", "ORD_DOC_IDCARD", "ORD_DOC_NUMBERAME", "ORD_DEP_CODE", "ORD_DEP_NAME", "HOS_DEP_CODE", "HOS_DEP_NAME", "RCD_DT", "INUMBERVOICE_NUMBERO", "IF_PRN", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "NAME", "SEX_CODE", "ID_NUM", "SETTLEMENT_ID", "INSURANCE_ID", "BASE_FEE", "ACCOUNT_FEE", "OWN_FEE", "IS_REVERSED", "REFERENCED_SETTLEMENT_ID", "CHARGE_ID", "ITEM_SUB_NO", "ITEM_SUB_NAME", "ITEM_CODE", "MEDICAL_INSURANCE_ITEM_NAME", "FEE_IN", "FEE_OUT", "RECIPE_ID", "ORDER_ID") AS 
  select substr(
           '49557032X' || '|' ||
           nvl(a.patient_id, '-') || '|' ||
           nvl(to_char(a.visit_id), '-') || '|' ||
           nvl(a.rcpt_no, '-') || '|' ||
           nvl(to_char(a.item_no), '-'),
           1,
           100
       ) as ID,-- 内码 是 主键

       substr(a.patient_id || '|' || a.visit_id, 1, 32) as PATIENT_ID,-- 住院唯一标识号 是

     nvl((select VALUE_DOMAIN_code  from   CDA_VALUE_DOMAIN_MAP e where CATEGORY_CODE='DM04-001' and e.HOSPITAL_CODE=a.item_code),a.item_code)
    PROJ_DENO,-- 收费项目明细编号 是

        nvl((select VALUE_DOMAIN_name  from   CDA_VALUE_DOMAIN_MAP e where CATEGORY_CODE='DM04-001' and e.HOSPITAL_CODE=a.item_code),a.item_name)
  as PROJ_NAME,-- 收费项目名称 是

       substr(a.item_code, 1, 100) as HOS_PROJ_DENO,-- 院内收费项目编码

       substr(a.item_name, 1, 100) as HOS_PROJ_NAME,-- 院内收费项目名称

       case trim(pl.mr_bill_class)
    when '01'   then '1'   -- 一般医疗服务费
    when '02'   then '2'   -- 一般治疗操作费
    when '03'   then '3'   -- 护理费
    when '04'   then '4'   -- 综合医疗服务类其他费用
    when '05'   then '5'   -- 病理诊断费
    when '06'   then '6'   -- 实验室诊断费
    when '07'   then '7'   -- 影像学诊断费
    when '08'   then '8'   -- 临床诊断项目费
    when '09'   then '9'   -- 非手术治疗项目费
    when '0901' then '901' -- 其中：临床物理治疗费
    when '10'   then '10'  -- 手术治疗费
    when '1001' then '101' -- 其中：麻醉费
    when '1002' then '102' -- 其中：手术费
    when '1003' then '24'  -- 治疗类：麻醉-检查，平台无细项，暂归其他费
    when '11'   then '11'  -- 康复费
    when '12'   then '12'  -- 中医治疗费
    when '1201' then '24'  -- 中医诊断费，平台无细项，暂归其他费
    when '1202' then '24'  -- 中医手术费，平台无细项，暂归其他费
    when '13'   then '13'  -- 西药费
    when '1301' then '131' -- 其中：抗菌药物费用
    when '14'   then '14'  -- 中成药费
    when '15'   then '15'  -- 中草药费
    when '16'   then '16'  -- 血费
    when '17'   then '17'  -- 白蛋白类制品费
    when '18'   then '18'  -- 球蛋白类制品费
    when '19'   then '19'  -- 凝血因子类制品费
    when '20'   then '20'  -- 细胞因子类制品费
    when '21'   then '21'  -- 检查用一次性医用材料费
    when '22'   then '22'  -- 治疗用一次性医用材料费
    when '23'   then '23'  -- 手术用一次性医用材料费
    when '24'   then '24'  -- 其他费
    else '24'
end as   FEE_CAT_CODE,-- 费用归类代码 是

       cast(round(nvl(a.item_price, 0), 2) as number(10,2)) as PROJ_UP,-- 项目单价（元） 是

       cast(round(nvl(a.amount, 0), 2) as number(10,2)) as PROJ_AMT,-- 项目数量 是，退费数量可为负数

       cast(round(nvl(a.charges, 0), 2) as number(10,2)) as PROJ_MON,-- 项目总金额（元） 是

       cast(
           case
               when a.zfbl is not null
               then round(nvl(a.charges, 0) * nvl(a.zfbl, 0) / 100, 2)
               else null
           end as number(10,2)
       ) as IND_PAY,-- 项目自付金额（元）

       cast(
           case
               when a.zfbl is not null
               then round(nvl(a.zfbl, 0) / 100, 2)
               else null
           end as number(10,2)
       ) as SELF_PAY,-- 自付比例

       substr(
           (
               select max(
                          case
                              when regexp_like(upper(s.id_no), '^[0-9]{17}([0-9]|X)$')
                              then upper(s.id_no)
                          end
                      )
                 from his.staff_dict s
                where  s.emp_no = a.operator_no
           ),
           1,
           18
       ) as RCD_IDCARD,-- 收费员身份证号

       substr(
           (
               select max(s.name)
                 from his.staff_dict s
                where  s.emp_no = a.operator_no
           ),
           1,
           50
       ) as RCD_NUMBERAME,-- 收费员姓名

       substr(
           (
               select max(
                          case
                              when regexp_like(upper(s.id_no), '^[0-9]{17}([0-9]|X)$')
                              then upper(s.id_no)
                          end
                      )
                 from his.staff_dict s
                where s.name = a.order_doctor
           ),
           1,
           18
       ) as ORD_DOC_IDCARD,-- 开单医生身份证号

       substr(nvl(a.order_doctor, '-'), 1, 50) as ORD_DOC_NUMBERAME,-- 开单医生姓名 是

       substr(
           nvl(
               (
                   select max(d.qmpt_code)
                     from his.dept_dict d
                    where d.dept_code = a.ordered_by
               ),
               a.ordered_by
           ),
           1,
           20
       ) as ORD_DEP_CODE,-- 开单科室代码 是

       substr(
           nvl(
               (
                   select max(d.qmpt_name)
                     from his.dept_dict d
                    where d.dept_code = a.ordered_by
               ),
               nvl(
                   (
                       select max(d.dept_name)
                         from his.dept_dict d
                        where d.dept_code = a.ordered_by
                   ),
                   a.ordered_by
               )
           ),
           1,
           100
       ) as ORD_DEP_NAME,-- 开单科室名称 是

       substr(nvl(a.ordered_by, '-'), 1, 20) as HOS_DEP_CODE,-- 院内开立科室编码

       substr(
           nvl(
               (
                   select max(d.dept_name)
                     from his.dept_dict d
                    where d.dept_code = a.ordered_by
               ),
               a.ordered_by
           ),
           1,
           100
       ) as HOS_DEP_NAME,-- 院内开立科室名称

       cast(a.billing_date_time as date) as RCD_DT,-- 收费日期时间 是

       substr(a.rcpt_no, 1, 24) as INUMBERVOICE_NUMBERO,-- 发票号码

       case
           when a.rcpt_no is not null then '1'
           else cast(null as char(1))
       end as IF_PRN,-- 是否打印发票

       '49557032X' as ORG_CODE,-- 医院组织机构代码 是

       '山东省第二人民医院' as ORG_NAME,-- 医院名称 是

       '370104' as DISTRICT_CODE,-- 所属行政区划 是

       'INSERT' as EXCHANGE_TYPE,-- 交换类型 是

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       substr(b.name, 1, 50) as NAME,-- 患者姓名 是

       case
           when b.sex = '男' then '1'
           when b.sex = '女' then '2'
           when b.sex = '未知' then '0'
           else '9'
       end as SEX_CODE,-- 患者性别代码 是

       substr(nvl(b.id_no, '000000000000000000'), 1, 18) as ID_NUM,-- 患者身份证件号码 是

       substr(nvl(a.rcpt_no, '-'), 1, 100) as SETTLEMENT_ID,-- 收费结算流水号 是

       substr(c.brjsh, 1, 100) as INSURANCE_ID,-- 医保结算流水号

       cast(round(nvl(c.tczf, 0), 2) as number) as BASE_FEE,-- 基本统筹支付金额 是

       cast(round(nvl(c.grzhzf, 0), 2) as number) as ACCOUNT_FEE,-- 医保个人账户支付金额 是

       cast(round(nvl(c.brfdje, 0), 2) as number) as OWN_FEE,-- 个人自付金额 是

       case
           when nvl(a.amount, 0) < 0 or nvl(a.charges, 0) < 0 then '1'
           else '0'
       end as IS_REVERSED,-- 是否退费

              case
           when nvl(a.amount, 0) < 0 or nvl(a.charges, 0) < 0
           then substr(a.rcpt_no, 1, 100)
           else cast(null as varchar2(100))
       end as REFERENCED_SETTLEMENT_ID,-- 退费关联结算流水号；需要确认原退费票据字段
       substr(
           nvl(
               a.rcpt_no || '|' || to_char(a.item_no),
               to_char(a.item_no)
           ),
           1,
           100
       ) as CHARGE_ID,-- 收费流水号 是

       substr(nvl(a.item_code, '-'), 1, 100) as ITEM_SUB_NO,-- 收费子项项目编码 是

       substr(nvl(a.item_name, '-'), 1, 100) as ITEM_SUB_NAME,-- 收费子项项目名称 是

       substr(a.insur_code, 1, 100) as ITEM_CODE,-- 医保项目代码

       substr(a.insur_name, 1, 100) as MEDICAL_INSURANCE_ITEM_NAME,-- 医保项目名称

       cast(0 as number(12,2)) as FEE_IN,-- 医保内总金额

       cast(0 as number(12,2)) as FEE_OUT,-- 医保外总金额

       cast(null as varchar2(100)) as RECIPE_ID,-- 处方流水号

       substr(
           nvl(
               to_char(a.oper_code),
               nvl(a.rcpt_no, '-') || '|' || nvl(to_char(a.item_no), '-')
           ),
           1,
           100
       ) as ORDER_ID-- 医嘱流水号 是；无医嘱流水号时暂用收费流水号兜底，需要确认

from his.inp_bill_detail a

inner join his.pat_master_index b
        on a.patient_id = b.patient_id

left join his.inp_settle_master_yb c
       on c.patient_id = a.patient_id
      and c.visit_id = a.visit_id
      and c.settle_type = '结算'
left join (
    select pl.item_class,
           pl.item_code,
           max(pl.mr_bill_class) as mr_bill_class
      from HIS.price_list pl
     where pl.mr_bill_class is not null
     group by pl.item_class,
              pl.item_code
) pl
  on pl.item_class = a.item_class
 and pl.item_code  = a.item_code
where a.billing_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and a.billing_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
