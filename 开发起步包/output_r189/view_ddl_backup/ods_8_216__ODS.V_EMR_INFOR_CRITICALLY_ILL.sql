
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_INFOR_CRITICALLY_ILL" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_ID", "INFORMED_CONSENT_CODE", "INFORMED_CONSENT_NAME", "DEPT_CODE", "DEP_NAME", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "PATIENT_NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "DISEASE_CODE", "DISEASE_NAME", "SUMMARY_RESCUE", "CRITICAL_NOTICE", "CRITICAL_NOTICE_DATE", "LEGAL_REPRE_NAME", "PAT_LEGAL_REPRE_CODE", "SAP_RELATIONSHIP_NAME", "LEGAL_REPRE_SIGN_DATE", "DOC_NAME", "DOC_DATE") AS 
  select ID,
       ORG_CODE,
       ORG_NAME,
       DISTRICT_CODE,
       EXCHANGE_TYPE,
       SYSTEM_TIME,
       ADMISSION_ID,
       INFORMED_CONSENT_CODE,
       INFORMED_CONSENT_NAME,
       DEPT_CODE,
       DEP_NAME,
       AREA_NAME,
       WARD_NUM,
       SICKBED_NUM,
       PATIENT_NAME,
       SEX_CODE,
       SEX_NAME,
       AGE,
       AGE_MONTH,
       DISEASE_CODE,
       DISEASE_NAME,
       SUMMARY_RESCUE,
       CRITICAL_NOTICE,
       CRITICAL_NOTICE_DATE,
       LEGAL_REPRE_NAME,
       PAT_LEGAL_REPRE_CODE,
       SAP_RELATIONSHIP_NAME,
       LEGAL_REPRE_SIGN_DATE,
       DOC_NAME,
       DOC_DATE
  from (
        select q.*,
               row_number() over (
                   partition by q.ID
                   order by q.ID
               ) as rn
          from (
                select
                       cast(
                           substrb(
                               '49557032X' || '|' ||
                               pv.patient_id || '|' ||
                               pv.visit_id || '|' ||
                               to_char(t1.id),
                               1,
                               100
                           ) as varchar2(100)
                       ) as ID,--内码 是 主键

                       cast('49557032X' as varchar2(32)) as ORG_CODE,--医院组织机构代码 是

                       cast('山东省第二人民医院' as varchar2(70)) as ORG_NAME,--医院名称 是

                       cast('370104' as varchar2(6)) as DISTRICT_CODE,--所属行政区划 是

                       cast('ADDHIS' as varchar2(10)) as EXCHANGE_TYPE,--交换类型 是

                       to_char(sysdate, 'yyyy-mm-dd hh24:mi:ss') as SYSTEM_TIME,--数据上传时间戳 是；统一时间格式

                       cast(
                           substrb(
                               pv.patient_id || '|' || pv.visit_id,
                               1,
                               50
                           ) as varchar2(50)
                       ) as ADMISSION_ID,--住院唯一标示号 是

                       cast(
                           substrb(
                               to_char(t1.id),
                               1,
                               20
                           ) as varchar2(20)
                       ) as INFORMED_CONSENT_CODE,--知情同意书编号

                       cast('病危(重)通知书' as varchar2(200)) as INFORMED_CONSENT_NAME,--知情同意书名称

                       cast(
                           substrb(
                               nvl(to_char(ks.qmpt_code), to_char(t.p_dept_code)),
                               1,
                               50
                           ) as varchar2(50)
                       ) as DEPT_CODE,--科室代码

                       cast(
                           substrb(
                               nvl(to_char(ks.qmpt_name), to_char(t.p_dept_name)),
                               1,
                               50
                           ) as varchar2(50)
                       ) as DEP_NAME,--科室名称 是

                       cast(
                           substrb(
                               to_char(t.p_are_name),
                               1,
                               50
                           ) as varchar2(50)
                       ) as AREA_NAME,--病区名称

                       cast(null as varchar2(10)) as WARD_NUM,--病房号

                       cast(
                           substrb(
                               to_char(t.p_bedno),
                               1,
                               10
                           ) as varchar2(10)
                       ) as SICKBED_NUM,--病床号

                       cast(
                           substrb(
                               nvl(to_char(t.p_name), to_char(pmi.name)),
                               1,
                               50
                           ) as varchar2(50)
                       ) as PATIENT_NAME,--患者姓名 是

                       cast(
                           case
                               when trim(pmi.sex) = '男' then 1
                               when trim(pmi.sex) = '女' then 2
                               when trim(pmi.sex) in ('未知', '未说明', '不明') then 0
                               else 9
                           end as number(1)
                       ) as SEX_CODE,--性别代码 是

                       cast(
                           case
                               when trim(pmi.sex) = '男' then '男'
                               when trim(pmi.sex) = '女' then '女'
                               when trim(pmi.sex) in ('未知', '未说明') then '未知'
                               else '不明'
                           end as varchar2(50)
                       ) as SEX_NAME,--性别 是

                       cast(
                           case
                               when pmi.date_of_birth is not null
                                and pv.admission_date_time is not null
                               then least(
                                        greatest(
                                            trunc(
                                                months_between(
                                                    pv.admission_date_time,
                                                    pmi.date_of_birth
                                                ) / 12
                                            ),
                                            0
                                        ),
                                        200
                                    )
                               else 0
                           end as number(3)
                       ) as AGE,--年龄 是

                       cast(
                           case
                               when pmi.date_of_birth is not null
                                and pv.admission_date_time is not null
                                and months_between(pv.admission_date_time, pmi.date_of_birth) >= 0
                                and months_between(pv.admission_date_time, pmi.date_of_birth) < 12
                               then to_char(
                                        trunc(
                                            months_between(
                                                pv.admission_date_time,
                                                pmi.date_of_birth
                                            )
                                        )
                                    )
                               else '0'
                           end as varchar2(8)
                       ) as AGE_MONTH,--年龄(月)

                       cast(
                           substrb(
                               coalesce(
                                   to_char(diag_code_cd.国标编码),
                                   to_char(diag_name_cd.国标编码)
                               ),
                               1,
                               12
                           ) as varchar2(12)
                       ) as DISEASE_CODE,--疾病诊断编码

                       cast(
                           substrb(
                               coalesce(
                                   cast(diag_code_cd.国标名称 as varchar2(4000 char)),
                                   cast(diag_name_cd.国标名称 as varchar2(4000 char)),
                                   cast(dd.diagnosis_desc as varchar2(4000 char))
                               ),
                               1,
                               50
                           ) as varchar2(50)
                       ) as DISEASE_NAME,--疾病诊断名称 是

                       cast(
                           substrb(
                               case
                                   when t4.ryqk is null
                                    and t5.zdyj is null
                                    and t5.zljh is null
                                   then null
                                   else dbms_lob.substr(
                                            to_clob('一、病情概况：') ||
                                            t4.ryqk ||
                                            to_clob(chr(10) || '二、诊断依据：') ||
                                            t5.zdyj ||
                                            to_clob(chr(10) || '三、诊疗计划：') ||
                                            t5.zljh,
                                            2000,
                                            1
                                        )
                               end,
                               1,
                               2000
                           ) as varchar2(2000)
                       ) as SUMMARY_RESCUE,--病情概括及主要抢救措施

                       cast(
                           substrb(
                               nvl(
                                   (
                                       select max(
                                                  dbms_lob.substr(
                                                      ec.段落内容,
                                                      4000,
                                                      1
                                                  )
                                              ) keep (
                                                  dense_rank first
                                                  order by
                                                      dbms_lob.getlength(ec.段落内容) desc nulls last,
                                                      ec.rowid
                                              )
                                         from MTL.EMRSD_CONTENT ec
                                        where ec.uhid = t.uhid
                                          and ec.段落编号 = t1.id
                                   ),
                                   '-'
                               ),
                               1,
                               4000
                           ) as varchar2(4000)
                       ) as CRITICAL_NOTICE,--病危(重)通知内容 是

                       to_char(
                           nvl(
                               t1.doc_title_time,
                               nvl(t1.doc_create_date, t1.modifiedon)
                           ),
                           'yyyy-mm-dd hh24:mi:ss'
                       ) as CRITICAL_NOTICE_DATE,--病危(重)通知日期时间 是；统一时间格式

                       cast(
                           substrb(
                               nvl(to_char(pv.next_of_kin), '-'),
                               1,
                               50
                           ) as varchar2(50)
                       ) as LEGAL_REPRE_NAME,--法定代理人签名 是

                       cast(
                           substrb(
                               nvl(to_char(rel_cd.国标编码), '8'),
                               1,
                               2
                           ) as varchar2(2)
                       ) as PAT_LEGAL_REPRE_CODE,--法定代理人与患者的关系代码 是

                       cast(
                           substrb(
                               nvl(to_char(rel_cd.国标名称), '其它'),
                               1,
                               50
                           ) as varchar2(50)
                       ) as SAP_RELATIONSHIP_NAME,--法定代理人与患者的关系名称 是

                       to_char(
                           nvl(
                               t1.doc_create_date,
                               nvl(t1.doc_title_time, t1.modifiedon)
                           ),
                           'yyyy-mm-dd hh24:mi:ss'
                       ) as LEGAL_REPRE_SIGN_DATE,--法定代理人签名日期 是；统一时间格式

                       cast(
                           substrb(
                               nvl(to_char(t1.modifiedby), nvl(to_char(t1.createby), '-')),
                               1,
                               50
                           ) as varchar2(50)
                       ) as DOC_NAME,--医师签名 是

                       to_char(
                           nvl(
                               t1.modifiedon,
                               nvl(t1.doc_create_date, t1.doc_title_time)
                           ),
                           'yyyy-mm-dd hh24:mi:ss'
                       ) as DOC_DATE--医师签名日期时间 是；统一时间格式

                  from MTL.EPR_INPATIENT t1

                  inner join MTL.EPR_INPATIENT_DOCINDEX t
                          on t.uhid = t1.uhid

                  left join (
                        select d.uhid,
                               max(d.id) keep (
                                   dense_rank first
                                   order by
                                       nvl(d.doc_finish_date, d.doc_sign_date) desc nulls last,
                                       d.id desc
                               ) as id
                          from MTL.EPR_INPATIENT d
                         where d.doc_type_name = '出院记录'
                         group by d.uhid
                  ) t2
                    on t2.uhid = t1.uhid

                  left join (
                        select x.段落编号,
                               x.ryqk
                          from (
                                select e.段落编号,
                                       e.ryqk,
                                       row_number() over (
                                           partition by e.段落编号
                                           order by e.段落编号
                                       ) as rn
                                  from MTL.EMRSD49 e
                               ) x
                         where x.rn = 1
                  ) t4
                    on t4.段落编号 = t2.id

                  left join (
                        select d.uhid,
                               min(d.id) keep (
                                   dense_rank first
                                   order by
                                       nvl(d.doc_finish_date, d.doc_sign_date) asc nulls last,
                                       d.id asc
                               ) as id
                          from MTL.EPR_INPATIENT d
                         where d.doc_type_name = '首次病程记录'
                         group by d.uhid
                  ) t3
                    on t3.uhid = t1.uhid

                  left join (
                        select x.段落编号,
                               x.zdyj,
                               x.zljh
                          from (
                                select e.段落编号,
                                       e.zdyj,
                                       e.zljh,
                                       row_number() over (
                                           partition by e.段落编号
                                           order by e.段落编号
                                       ) as rn
                                  from MTL.EMRSD37 e
                               ) x
                         where x.rn = 1
                  ) t5
                    on t5.段落编号 = t3.id

                  inner join HIS.PAT_MASTER_INDEX pmi
                          on pmi.inp_no = t.p_inpatient_no

                  inner join HIS.PAT_VISIT pv
                          on pv.patient_id = pmi.patient_id
                         and pv.visit_id = t.p_inpatient_times

                  inner join HIS.DIAGNOSIS dd
                          on dd.patient_id = pv.patient_id
                         and dd.visit_id = pv.visit_id
                         and dd.diagnosis_type = '3'
                         and dd.diagnosis_no = '1'

                  left join (
                        select cd.院标编码,
                               max(cd.国标编码) keep (
                                   dense_rank first
                                   order by
                                       case when cd.国标编码 is not null then 1 else 2 end,
                                       cd.国标编码
                               ) as 国标编码,
                               max(cd.国标名称) keep (
                                   dense_rank first
                                   order by
                                       case when cd.国标编码 is not null then 1 else 2 end,
                                       cd.国标编码
                               ) as 国标名称
                          from CDA.CDA_DICTIONARY cd
                         where cd.字典名称 = 'ICD-10诊断编码'
                           and cd.系统标识 = 'HIS'
                         group by cd.院标编码
                  ) diag_code_cd
                    on diag_code_cd.院标编码 = dd.diagnosis_code

                  left join (
                        select cd.院标名称,
                               max(cd.国标编码) keep (
                                   dense_rank first
                                   order by
                                       case when cd.国标编码 is not null then 1 else 2 end,
                                       cd.国标编码
                               ) as 国标编码,
                               max(cd.国标名称) keep (
                                   dense_rank first
                                   order by
                                       case when cd.国标编码 is not null then 1 else 2 end,
                                       cd.国标编码
                               ) as 国标名称
                          from CDA.CDA_DICTIONARY cd
                         where cd.字典名称 = 'ICD-10诊断编码'
                           and cd.系统标识 = 'HIS'
                         group by cd.院标名称
                  ) diag_name_cd
                    on diag_name_cd.院标名称 = dd.diagnosis_desc

                  inner join HIS.DEPT_DICT ks
                          on ks.dept_code = t.p_dept_code
                         and ks.qmpt_name is not null

                  left join (
                        select cd.院标编码,
                               max(cd.国标编码) keep (
                                   dense_rank first
                                   order by
                                       case when cd.国标编码 is not null then 1 else 2 end,
                                       cd.国标编码
                               ) as 国标编码,
                               max(cd.国标名称) keep (
                                   dense_rank first
                                   order by
                                       case when cd.国标编码 is not null then 1 else 2 end,
                                       cd.国标编码
                               ) as 国标名称
                          from CDA.CDA_DICTIONARY cd
                         where cd.字典名称 = '家庭关系代码'
                         group by cd.院标编码
                  ) rel_cd
                    on rel_cd.院标编码 = pmi.relationship

                 where t1.doc_type_name in (
                           '病重（危）通知书',
                           '病危（重）通知书',
                           '病危(重)通知书'
                       )

                   and coalesce(
                           cast(diag_code_cd.国标名称 as varchar2(4000 char)),
                           cast(diag_name_cd.国标名称 as varchar2(4000 char)),
                           cast(dd.diagnosis_desc as varchar2(4000 char))
                       ) is not null
               ) q
       )
 where rn = 1
