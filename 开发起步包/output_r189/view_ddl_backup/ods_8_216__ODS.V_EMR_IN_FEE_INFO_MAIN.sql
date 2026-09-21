
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_IN_FEE_INFO_MAIN" ("ID", "PATIENT_ID", "TOTAL_FEE", "INUMBERD_PAY", "YB_PAY", "TC_PAY", "GWY_PAY", "DB_PAY", "MZJZ_PAY", "QT_PAY", "PAY_MODE", "PAY_MODE_NAME", "SO_CARD", "ID_NUM", "ORG_CODE", "ORG_NAME", "EXCHANGE_TYPE", "SYSTEM_TIME", "DISTRICT_CODE") AS 
  select substr('49557032X' || '|' || b.patient_id || '|' || b.visit_id, 1, 100) as ID,-- 内码 是 主键

       substr(b.patient_id || '|' || b.visit_id, 1, 32) as PATIENT_ID,-- 住院唯一标识号 是

       cast(round(nvl(b.payments, 0), 2) as number(10,2)) as TOTAL_FEE,-- 总费用（元） 是

       cast(round(nvl(yb.brfdje, nvl(b.payments, 0)), 2) as number(10,2)) as INUMBERD_PAY,-- 自付金额（元） 是

       cast(round(nvl(yb.ybfdje, 0), 2) as number(10,2)) as YB_PAY,-- 医保报销费用 是

       cast(round(nvl(yb.tczf, 0), 2) as number(10,2)) as TC_PAY,-- 统筹基金支付 是

       cast(round(nvl(yb.gwybz, 0), 2) as number(10,2)) as GWY_PAY,-- 公务员基金支付 是

       cast(round(nvl(yb.dbbzje, 0), 2) as number(10,2)) as DB_PAY,-- 大病基金支付 是

       cast(round(nvl(yb.mzbzje, 0), 2) as number(10,2)) as MZJZ_PAY,-- 民政救助支付 是

       cast(round(nvl(yb.qttczf, 0), 2) as number(10,2)) as QT_PAY,-- 其他基金支付 是
       substr(
           case
               when nvl(yb.tczf, 0) > 0
                 or nvl(yb.ybfdje, 0) > 0
                 or nvl(yb.gwybz, 0) > 0
                 or nvl(yb.dbbzje, 0) > 0
                 or nvl(yb.mzbzje, 0) > 0
                 or nvl(yb.qttczf, 0) > 0
               then '07'
               else '99'
           end,
           1,
           2
       ) as PAY_MODE,-- 费用支付方式代码

       substr(
           case
               when nvl(yb.tczf, 0) > 0
                 or nvl(yb.ybfdje, 0) > 0
                 or nvl(yb.gwybz, 0) > 0
                 or nvl(yb.dbbzje, 0) > 0
                 or nvl(yb.mzbzje, 0) > 0
                 or nvl(yb.qttczf, 0) > 0
               then '统筹金'
               else '其他'
           end,
           1,
           26
       ) as PAY_MODE_NAME,-- 费用支付方式名称

       cast(null as varchar2(25)) as SO_CARD,-- 社保卡号码

       cast(null as varchar2(18)) as ID_NUM,-- 社会保障号

       '49557032X' as ORG_CODE,-- 医院组织机构编码 是

       '山东省第二人民医院' as ORG_NAME,-- 医院名称 是

       'INSERT' as EXCHANGE_TYPE,-- 交换类型 是

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       '370104' as DISTRICT_CODE-- 所属行政区划 是

from (
        select s.patient_id,
               s.visit_id,
               sum(nvl(s.payments, 0)) as payments
          from his.inp_settle_master s
         where s.transact_type = '正常'
         group by s.patient_id,
                  s.visit_id
     ) b

left join (
        select y.patient_id,
               y.visit_id,
               sum(nvl(y.brfdje, 0)) as brfdje,
               sum(nvl(y.ybfdje, 0)) as ybfdje,
               sum(nvl(y.tczf, 0)) as tczf,
               sum(nvl(y.gwybz, 0)) as gwybz,
               sum(nvl(y.dbbzje, 0)) as dbbzje,
               sum(nvl(y.mzbzje, 0)) as mzbzje,
               sum(nvl(y.qttczf, 0)) as qttczf
          from his.inp_settle_master_yb y
         where y.settle_type = '结算'
         group by y.patient_id,
                  y.visit_id
     ) yb
       on b.patient_id = yb.patient_id
      and b.visit_id = yb.visit_id

left join his.pat_visit pv
       on b.patient_id = pv.patient_id
      and b.visit_id = pv.visit_id
      where pv.discharge_date_time>= date '2021-01-01'
           and  pv.discharge_date_time  <  date '2025-01-01'
