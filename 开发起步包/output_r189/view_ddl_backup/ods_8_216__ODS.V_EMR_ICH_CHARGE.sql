
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_ICH_CHARGE" ("ID", "ICH_ID", "CHARGE_TYPE_CODE", "CHARGE_TYPE", "CHARGE_AMOUNT", "CREATED_AT", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ORG_CODE", "ORG_NAME", "ADMISSION_ID", "NAME", "SEX_CODE", "ID_NUM") AS 
  select
       cast(
           substrb(
               '49557032X' || '|' || o.patient_id || '|' || o.visit_id || '|' || r.charge_type_code,
               1,
               100
           ) as varchar2(100)
       ) as ID,--内码 是 主键；机构码|患者ID|住院次数|费用分类代码，避免重复

       cast(
           substrb(
               '49557032X' || '|' || o.patient_id || '|' || o.visit_id,
               1,
               100
           ) as varchar2(100)
       ) as ICH_ID,--病案首页内码 是；必须与EMR_ICH.ID一致

       cast(substrb(r.charge_type_code, 1, 6) as varchar2(6)) as CHARGE_TYPE_CODE,--住院费用-分类代码 是；CC99.00092

       cast(substrb(r.charge_type_name, 1, 32) as varchar2(32)) as CHARGE_TYPE,--住院费用-分类 是

       cast(round(nvl(r.costs, 0), 2) as number(9,2)) as CHARGE_AMOUNT,--住院费用-金额（元/人民币） 是

       cast(nvl(o.discharge_date_time, o.admission_date_time) as timestamp) as CREATED_AT,--创建时间

       cast('370104' as varchar2(6)) as DISTRICT_CODE,--所属行政区划 是

       cast('ADDHIS' as varchar2(10)) as EXCHANGE_TYPE,--交换类型 是

       cast(systimestamp as timestamp) as SYSTEM_TIME,--数据上传时间戳 是

       cast('49557032X' as varchar2(32)) as ORG_CODE,--医院组织机构代码 是

       cast('山东省第二人民医院' as varchar2(70)) as ORG_NAME,--医院名称 是

       cast(
           substrb(
               o.patient_id || '|' || o.visit_id,
               1,
               20
           ) as varchar2(20)
       ) as ADMISSION_ID,--本次住院标识号 是

       cast(substrb(nvl(to_char(pmi.name), '无名氏'), 1, 50) as varchar2(50)) as NAME,--姓名 是

       cast(
           decode(pmi.sex, '男', '1', '女', '2', '未知', '0', '9')
           as char(1)
       ) as SEX_CODE,--性别代码 是；0未知，1男，2女，9不明

       cast(
           substrb(
               nvl(to_char(pmi.id_no), '000000000000000000'),
               1,
               18
           ) as varchar2(18)
       ) as ID_NUM--身份证件号码 是

  from his.pat_visit o

  left join his.pat_master_index pmi
    on pmi.patient_id = o.patient_id

  join (
        select x.patient_id,
               x.visit_id,
               x.charge_type_code,
               x.charge_type_name,
               sum(nvl(x.costs, 0)) as costs
          from (
                select r.patient_id,
                       r.visit_id,

                       decode(
                           to_char(r.mr_bill_class),
                           '01',   '1',
                           '02',   '2',
                           '03',   '3',
                           '04',   '4',
                           '05',   '5',
                           '06',   '6',
                           '07',   '7',
                           '08',   '8',
                           '09',   '9',
                           '0901', '901',
                           '10',   '10',
                           '1001', '101',
                           '1002', '102',
                           '1003', '10',
                           '11',   '11',
                           '12',   '12',
                           '1202', '12',
                           '13',   '13',
                           '1301', '131',
                           '14',   '14',
                           '15',   '15',
                           '16',   '16',
                           '17',   '17',
                           '18',   '18',
                           '19',   '19',
                           '20',   '20',
                           '21',   '21',
                           '22',   '22',
                           '23',   '23',
                           '24',   '24',
                           '其他', '24',
                           '其他费', '24',
                           to_char(r.mr_bill_class)
                       ) as charge_type_code,--费用分类代码；1003归并10，1202归并12

                       decode(
                           to_char(r.mr_bill_class),
                           '01',   '一般医疗服务费',
                           '02',   '一般治疗操作费',
                           '03',   '护理费',
                           '04',   '综合医疗服务类其他费用',
                           '05',   '病理诊断费',
                           '06',   '实验室诊断费',
                           '07',   '影像学诊断费',
                           '08',   '临床诊断项目费',
                           '09',   '非手术治疗项目费',
                           '0901', '其中临床物理治疗费',
                           '10',   '手术治疗费',
                           '1001', '其中麻醉费',
                           '1002', '其中手术费',
                           '1003', '手术治疗费',
                           '11',   '康复费',
                           '12',   '中医治疗费',
                           '1202', '中医治疗费',
                           '13',   '西药费',
                           '1301', '其中抗菌药物费用',
                           '14',   '中成药费',
                           '15',   '中草药费',
                           '16',   '血费',
                           '17',   '白蛋白类制品费',
                           '18',   '球蛋白类制品费',
                           '19',   '凝血因子类制品费',
                           '20',   '细胞因子类制品费',
                           '21',   '检查用一次性医用材料费',
                           '22',   '治疗用一次性医用材料费',
                           '23',   '手术用一次性医用材料费',
                           '24',   '其他费',
                           '其他', '其他费',
                           '其他费', '其他费',
                           to_char(r.mr_bill_class)
                       ) as charge_type_name,--费用分类名称

                       r.costs
                  from his.mr_bill_costs r
                 where r.mr_bill_class is not null
               ) x
         where x.charge_type_code in
               ('1','2','3','4','5','6','7','8','9','901',
                '10','101','102','11','12','13','131','14','15',
                '16','17','18','19','20','21','22','23','24')
         group by x.patient_id,
                  x.visit_id,
                  x.charge_type_code,
                  x.charge_type_name
       ) r
    on r.patient_id = o.patient_id
   and r.visit_id = o.visit_id

 where o.discharge_date_time >= date '2021-01-01'
   and o.discharge_date_time <  date '2025-01-01'
