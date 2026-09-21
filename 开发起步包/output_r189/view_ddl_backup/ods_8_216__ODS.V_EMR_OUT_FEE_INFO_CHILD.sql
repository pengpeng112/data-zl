
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_OUT_FEE_INFO_CHILD" ("ID", "PATIENT_ID", "CHARGE_TYPE", "ODER_ITEM_NAME", "ODER_ITEM_CODE", "ODER_NAME", "ODER_CODE", "CHARGE_TNAME", "PROJ_NAME", "PROJ_CODE", "HOS_PROJ_CODE", "HOS_PROJ_NAME", "PROJ_UP", "PROJ_AMT", "PROJ_MON", "IND_PAY", "SELF_PAY", "RCD_IDCARD", "RCD_NUMBERAME", "ORD_DOC_IDCARD", "ORD_DOC_NUMBERAME", "ORD_DEP_CODE", "ORD_DEP_NAME", "RCD_DT", "INUMBERVOICE_NUMBERO", "IF_PRN", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "NAME", "SEX_CODE", "ID_NUM", "SETTLEMENT_ID", "REFERENCED_SETTLEMENT_ID", "BASE_FEE", "ACCOUNT_FEE", "OWN_FEE", "IS_REVERSED", "ITEM_SUB_NO", "ITEM_SUB_NAME", "ITEM_CODE", "ITEM_NAME", "FEE_IN", "FEE_OUT", "MAT_CODE", "MAT_NHSA_STANDARD_CODE", "RECIPE_ID", "ORDER_ID") AS 
  select substr(
           '49557032X'
           || '|' || b.rcpt_no
           || '|' || nvl(to_char(b.visit_no), '0')
           || '|' || nvl(to_char(b.item_no), '0'),
           1,
           100
       ) as ID, -- 内码，主键

  substr(nvl(c.clinic_no, a.patient_id|| a.patient_id||to_char(a.visit_date,'yyyymmdd')), 1, 18) as PATIENT_ID, -- 门诊唯一标识号

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
end as CHARGE_TYPE, -- 费用类别代码

       case
           when b.item_class in ('A', 'B') then '药品类医嘱'
           when b.item_class = 'D' then '检查类医嘱'
           when b.item_class = 'C' then '检验类医嘱'
           when b.item_class in ('F', 'G') then '手术类医嘱'
           when b.item_class in ('E', 'K', 'J') then '处置类医嘱'
           when b.item_class = 'I' then '材料类医嘱'
           when b.item_class = 'H' then '输血类医嘱'
           else '其他医嘱'
       end as ODER_ITEM_NAME, -- 医嘱项目类别名称

       case
           when b.item_class in ('A', 'B') then '1'
           when b.item_class = 'D' then '2'
           when b.item_class = 'C' then '3'
           when b.item_class in ('F', 'G') then '4'
           when b.item_class in ('E', 'K', 'J') then '5'
           when b.item_class = 'I' then '6'
           when b.item_class = 'H' then '8'
           else '99'
       end as ODER_ITEM_CODE, -- 医嘱项目类别代码

       substr(
           nvl(nvl(otc.item_name, opt.drug_name), b.item_name),
           1,
           100
       ) as ODER_NAME, -- 门诊医嘱名称

       substr(
           nvl(nvl(otc.item_code, opt.drug_code), b.item_code),
           1,
           50
       ) as ODER_CODE, -- 门诊医嘱编码

case trim(pl.mr_bill_class)
    when '01'   then '一般医疗服务费'
    when '02'   then '一般治疗操作费'
    when '03'   then '护理费'
    when '04'   then '综合医疗服务类其他费用'
    when '05'   then '病理诊断费'
    when '06'   then '实验室诊断费'
    when '07'   then '影像学诊断费'
    when '08'   then '临床诊断项目费'
    when '09'   then '非手术治疗项目费'
    when '0901' then '临床物理治疗费'
    when '10'   then '手术治疗费'
    when '1001' then '麻醉费'
    when '1002' then '手术费'
    when '1003' then '其他费'
    when '11'   then '康复费'
    when '12'   then '中医治疗费'
    when '1201' then '其他费'
    when '1202' then '其他费'
    when '13'   then '西药费'
    when '1301' then '抗菌药物费用'
    when '14'   then '中成药费'
    when '15'   then '中草药费'
    when '16'   then '血费'
    when '17'   then '白蛋白类制品费'
    when '18'   then '球蛋白类制品费'
    when '19'   then '凝血因子类制品费'
    when '20'   then '细胞因子类制品费'
    when '21'   then '检查用一次性医用材料费'
    when '22'   then '治疗用一次性医用材料费'
    when '23'   then '手术用一次性医用材料费'
    when '24'   then '其他费'
    else '其他费'
end as CHARGE_TNAME, -- 费用类别名称

        nvl((select VALUE_DOMAIN_name  from   CDA_VALUE_DOMAIN_MAP e where CATEGORY_CODE='DM04-001' and e.HOSPITAL_CODE=b.item_code),b.item_name)    as PROJ_NAME, -- 收费项目名称

   nvl((select VALUE_DOMAIN_CODE  from   CDA_VALUE_DOMAIN_MAP e where CATEGORY_CODE='DM04-001' and e.HOSPITAL_CODE=b.item_code),b.item_code) as PROJ_CODE, -- 收费项目编号，原 SQL 写成 PROJ_DENO，需改为 PROJ_CODE

       substr(b.item_code, 1, 20) as HOS_PROJ_CODE, -- 院内收费项目编码

       substr(b.item_name, 1, 20) as HOS_PROJ_NAME, -- 院内收费项目名称

       cast(round(nvl(b.item_price, 0), 2) as number(10, 2)) as PROJ_UP, -- 项目单价

       cast(
           round(
               case
                   when a.charge_indicator = 2 then -abs(nvl(b.amount, 0))
                   else nvl(b.amount, 0)
               end,
               2
           ) as number(10, 2)
       ) as PROJ_AMT, -- 项目数量，退费为负数

       cast(
           round(
               case
                   when a.charge_indicator = 2 then -abs(nvl(b.charges, 0))
                   else nvl(b.charges, 0)
               end,
               2
           ) as number(10, 2)
       ) as PROJ_MON, -- 项目总金额

       cast(null as number(10, 2)) as IND_PAY, -- 项目自付金额，暂无可靠来源

       cast(null as number(10, 2)) as SELF_PAY, -- 自付比例，暂无可靠来源

       substr(
           (
               select max(s.id_no)
                 from HIS.staff_dict s
                where to_char(s.id) = to_char(a.operator_no)
                   or s.emp_no = a.operator_no
           ),
           1,
           18
       ) as RCD_IDCARD, -- 收费员身份证号
       substr(
           (
               select max(s.name)
                 from HIS.staff_dict s
                where  s.emp_no = a.operator_no
           ),
           1,
           50
       ) as RCD_NUMBERAME, -- 收费员姓名

       substr(
           (
               select max(s.id_no)
                 from HIS.staff_dict s
                where s.emp_no = b.ordered_by_doctor
           ),
           1,
           18
       ) as ORD_DOC_IDCARD, -- 开单医生身份证号

       substr(
           nvl(
               (
                   select max(s.name)
                     from HIS.staff_dict s
                    where s.emp_no = b.ordered_by_doctor
               ),
               b.ordered_by_doctor
           ),
           1,
           50
       ) as ORD_DOC_NUMBERAME, -- 开单医生姓名

       substr(nvl(nvl(d.qmpt_code, d.dept_code),'-'), 1, 20) as ORD_DEP_CODE, -- 开单科室代码

       substr(nvl(nvl(d.qmpt_name, d.dept_name),'-'), 1, 20) as ORD_DEP_NAME, -- 开单科室名称

       cast(b.visit_date as date) as RCD_DT, -- 收费日期时间，目标字段为 DATE，不要 TO_CHAR

       substr(a.invoice_no, 1, 24) as INUMBERVOICE_NUMBERO, -- 发票号码

       case
           when a.invoice_no is not null then '1'
           else '0'
       end as IF_PRN, -- 是否打印发票

       '49557032X' as ORG_CODE, -- 医院组织机构代码

       '山东省第二人民医院' as ORG_NAME, -- 医院名称

       '370104' as DISTRICT_CODE, -- 所属行政区划

       'INSERT' as EXCHANGE_TYPE, -- 交换类型，必填

       cast(systimestamp as timestamp) as SYSTEM_TIME, -- 数据上传时间戳

       substr(e.name, 1, 50) as NAME, -- 患者姓名

       case trim(e.sex)
           when '男' then '1'
           when '女' then '2'
           when '未知' then '0'
           when '不详' then '9'
           when '未说明' then '9'
           else '9'
       end as SEX_CODE, -- 患者性别代码

       substr(nvl(e.id_no, '000000000000000000'), 1, 18) as ID_NUM, -- 患者身份证件号码

       substr(a.rcpt_no, 1, 100) as SETTLEMENT_ID, -- 机构收费结算流水号

       substr(a.brjsh, 1, 100) as REFERENCED_SETTLEMENT_ID, -- 医保关联结算流水号

       cast(0 as number(12, 2)) as BASE_FEE, -- 基本统筹支付金额，暂无医保拆分来源时填 0

       cast(0 as number(12, 2)) as ACCOUNT_FEE, -- 医保个人账户支付金额，暂无医保拆分来源时填 0

       cast(0 as number(12, 2)) as OWN_FEE, -- 自付金额，暂无医保拆分来源时填 0

       case
           when a.charge_indicator = 2 then '1'
           else '0'
       end as IS_REVERSED, -- 是否退费，1是0否

       substr(b.item_code, 1, 100) as ITEM_SUB_NO, -- 收费子项项目编码

       substr(b.item_name, 1, 100) as ITEM_SUB_NAME, -- 收费子项项目名称

       substr(b.insur_code, 1, 100) as ITEM_CODE, -- 医保项目代码

       substr(b.insur_name, 1, 100) as ITEM_NAME, -- 医保项目名称

       cast(0 as number(12, 2)) as FEE_IN, -- 医保内总金额，暂无医保拆分来源时填 0

       cast(0 as number(12, 2)) as FEE_OUT, -- 医保外总金额，暂无医保拆分来源时填 0
       substr(b.item_code, 1, 100) as MAT_CODE, -- 耗材编码；非耗材项目暂无独立字段，暂用收费项目编码

       substr(b.insur_code, 1, 100) as MAT_NHSA_STANDARD_CODE, -- 耗材医保贯标码

       substr(
           case
               when b.item_class in ('A', 'B')
                and b.order_id is not null
               then nvl(c.clinic_no, a.patient_id) || '|' || to_char(b.order_id)
               else nvl(c.clinic_no, a.patient_id) || '|' || b.rcpt_no
           end,
           1,
           100
       ) as RECIPE_ID, -- 处方流水号，当前按门诊号+order_id生成；如需精确关联处方主表ID需再确认处方主表规则

       substr(
           nvl(c.clinic_no, a.patient_id)
           || '|' || nvl(to_char(b.order_id), b.rcpt_no)
           || '|' || nvl(to_char(b.order_item_id), to_char(b.item_no)),
           1,
           100
       ) as ORDER_ID -- 医嘱流水号

  from HIS.outp_rcpt_master a
  join HIS.outp_bill_items b
    on b.rcpt_no = a.rcpt_no
  left join (
        select od.rcpt_no,
               max(od.clinic_no) as clinic_no
          from HIS.outp_order_desc od
         group by od.rcpt_no
       ) c
    on c.rcpt_no = a.rcpt_no

  left join (
        select tr.order_id,
               tr.order_item_id,
               max(tr.item_code) as item_code,
               max(tr.item_name) as item_name
          from HIS.outp_treat_rec tr
         group by tr.order_id,
                  tr.order_item_id
       ) otc
    on otc.order_id = b.order_id
   and otc.order_item_id = b.order_item_id

  left join (
        select pt.order_id,
               pt.order_item_id,
               max(pt.drug_code) as drug_code,
               max(pt.drug_name) as drug_name
          from HIS.outp_presc_t pt
         group by pt.order_id,
                  pt.order_item_id
       ) opt
    on opt.order_id = b.order_id
   and opt.order_item_id = b.order_item_id

  left join HIS.dept_dict d
    on d.dept_code = nvl(b.ordered_by_dept,b.ORDER_GROUP)

  left join HIS.pat_master_index e
    on e.patient_id = a.patient_id
left join (
    select pl.item_class,
           pl.item_code,
           max(pl.mr_bill_class) as mr_bill_class
      from HIS.price_list pl
     where pl.mr_bill_class is not null
     group by pl.item_class,
              pl.item_code
) pl
  on pl.item_class = b.item_class
 and pl.item_code  = b.item_code

 where a.visit_date >= date '2021-01-01' and a.visit_date < date '2025-01-01'
