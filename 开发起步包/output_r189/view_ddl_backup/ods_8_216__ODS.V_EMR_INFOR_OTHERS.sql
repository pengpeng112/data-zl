
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_INFOR_OTHERS" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_ID", "INFORMED_CONSENT_CODE", "INFORMED_CONSENT_NAME", "DEPT_CODE", "DEP_NAME", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "PATIENT_NAME", "SEX_CODE", "SEX_NAME", "AGE", "AGE_MONTH", "DISEASE_CODE", "DISEASE_NAME", "INFORMED_CONSENT", "ORG_VIEW", "PATIENT_VIEW", "PATIENT_SIGN_NAME", "LEGAL_REPRE_NAME", "PAT_LEGAL_REPRE_CODE", "SAP_RELATIONSHIP_NAME", "PATIENT_SIGN_DATE", "DOC_NAME", "DOC_DATE") AS 
  select d.ID,
       d.ORG_CODE,
       d.ORG_NAME,
       d.DISTRICT_CODE,
       d.EXCHANGE_TYPE,
       d.SYSTEM_TIME,
       d.ADMISSION_ID,
       d.INFORMED_CONSENT_CODE,
       d.INFORMED_CONSENT_NAME,
       d.DEPT_CODE,
       d.DEP_NAME,
       d.AREA_NAME,
       d.WARD_NUM,
       d.SICKBED_NUM,
       d.PATIENT_NAME,
       d.SEX_CODE,
       d.SEX_NAME,
       d.AGE,
       d.AGE_MONTH,
       d.DISEASE_CODE,
       d.DISEASE_NAME,
       d.INFORMED_CONSENT,
       d.ORG_VIEW,
       d.PATIENT_VIEW,
       d.PATIENT_SIGN_NAME,
       d.LEGAL_REPRE_NAME,
       d.PAT_LEGAL_REPRE_CODE,
       d.SAP_RELATIONSHIP_NAME,
       d.PATIENT_SIGN_DATE,
       d.DOC_NAME,
       d.DOC_DATE
  from (
        select q.*,
               row_number() over (
                   partition by q.ID
                   order by
                       case
                           when q.INFORMED_CONSENT is not null then 0
                           else 1
                       end,
                       case
                           when q.DISEASE_CODE is not null then 0
                           else 1
                       end,
                       q.DOC_DATE desc nulls last,
                       q.PATIENT_SIGN_DATE desc nulls last,
                       q.DISEASE_CODE nulls last,
                       q.DISEASE_NAME nulls last
               ) as id_rn
          from (
                select
                       /* 内码：机构编码+住院标识+文书ID */
                       '49557032X' ||
                       cast(pv.patient_id as varchar2(30)) || '|' ||
                       cast(pv.visit_id as varchar2(10)) || '|' ||
                       cast(t1.id as varchar2(40)) as ID,

                       '49557032X' as ORG_CODE,

                       '山东省第二人民医院' as ORG_NAME,

                       '370104' as DISTRICT_CODE,

                       'ADDHIS' as EXCHANGE_TYPE,

                       sysdate as SYSTEM_TIME,

                       cast(pv.patient_id as varchar2(30)) || '|' ||
                       cast(pv.visit_id as varchar2(10)) as ADMISSION_ID,

                       nvl(
                           substrb(
                               cast(t1.id as varchar2(100)),
                               1,
                               20
                           ),
                           '-'
                       ) as INFORMED_CONSENT_CODE,

                       substrb(
                           cast(t1.doc_title as varchar2(2000)),
                           1,
                           200
                       ) as INFORMED_CONSENT_NAME,

                       substrb(
                           cast(ks.qmpt_code as varchar2(2000)),
                           1,
                           50
                       ) as DEPT_CODE,

                       substrb(
                           case
                               when trim(
                                        cast(
                                            ks.qmpt_name as varchar2(2000)
                                        )
                                    ) is not null
                               then cast(
                                        ks.qmpt_name as varchar2(2000)
                                    )
                               else cast(
                                        t.p_dept_name as varchar2(2000)
                                    )
                           end,
                           1,
                           50
                       ) as DEP_NAME,

                       substrb(
                           cast(t.p_are_name as varchar2(2000)),
                           1,
                           50
                       ) as AREA_NAME,

                       cast(null as varchar2(10)) as WARD_NUM,

                       substrb(
                           cast(t.p_bedno as varchar2(2000)),
                           1,
                           10
                       ) as SICKBED_NUM,

                       substrb(
                           cast(t.p_name as varchar2(2000)),
                           1,
                           50
                       ) as PATIENT_NAME,

                       case
                           when trim(
                                    cast(pmi.sex as varchar2(20))
                                ) = '男'
                           then 1

                           when trim(
                                    cast(pmi.sex as varchar2(20))
                                ) = '女'
                           then 2

                           when trim(
                                    cast(pmi.sex as varchar2(20))
                                ) = '未知'
                           then 0

                           else 9
                       end as SEX_CODE,

                       case
                           when trim(
                                    cast(pmi.sex as varchar2(20))
                                ) = '男'
                           then '男'

                           when trim(
                                    cast(pmi.sex as varchar2(20))
                                ) = '女'
                           then '女'

                           when trim(
                                    cast(pmi.sex as varchar2(20))
                                ) = '未知'
                           then '未知'

                           else '不明'
                       end as SEX_NAME,

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
                           else null
                       end as AGE,

                       case
                           when pmi.date_of_birth is not null
                            and pv.admission_date_time is not null
                            and months_between(
                                    pv.admission_date_time,
                                    pmi.date_of_birth
                                ) >= 0
                            and months_between(
                                    pv.admission_date_time,
                                    pmi.date_of_birth
                                ) < 12
                           then to_char(
                                    least(
                                        greatest(
                                            trunc(
                                                months_between(
                                                    pv.admission_date_time,
                                                    pmi.date_of_birth
                                                )
                                            ),
                                            0
                                        ),
                                        11
                                    )
                                )

                           when pmi.date_of_birth is not null
                            and pv.admission_date_time is not null
                           then '0'

                           else null
                       end as AGE_MONTH,

                       nvl(
                           substrb(
                               cast(
                                   diag_cd.国标编码 as varchar2(2000)
                               ),
                               1,
                               12
                           ),
                           dd.diagnosis_code
                       ) as DISEASE_CODE,

                       nvl(
                           substrb(
                               cast(
                                   diag_cd.国标名称 as varchar2(2000)
                               ),
                               1,
                               50
                           ),
                           dd.diagnosis_desc
                       ) as DISEASE_NAME,

                       substrb(
                           case
                               when trim(
                                        cast(
                                            t3.content_text as varchar2(2000)
                                        )
                                    ) is not null
                               then cast(
                                        t3.content_text as varchar2(2000)
                                    )
                               else cast(
                                        t4.content_text as varchar2(2000)
                                    )
                           end,
                           1,
                           1000
                       ) as INFORMED_CONSENT,

                       cast(null as varchar2(2000)) as ORG_VIEW,

                       cast(null as varchar2(2000)) as PATIENT_VIEW,

                       cast(null as varchar2(50)) as PATIENT_SIGN_NAME,

                       nvl(
                           substrb(
                               cast(
                                   pv.next_of_kin as varchar2(2000)
                               ),
                               1,
                               50
                           ),
                           '-'
                       ) as LEGAL_REPRE_NAME,

                       nvl(
                           substrb(
                               cast(
                                   relation_map.standard_code
                                       as varchar2(2000)
                               ),
                               1,
                               2
                           ),
                           '8'
                       ) as PAT_LEGAL_REPRE_CODE,

                       nvl(
                           substrb(
                               cast(
                                   relation_map.standard_name
                                       as varchar2(2000)
                               ),
                               1,
                               50
                           ),
                           '其它'
                       ) as SAP_RELATIONSHIP_NAME,

                       t1.doc_finish_date as PATIENT_SIGN_DATE,

                       substrb(
                           cast(t1.MODIFIEDBY as varchar2(50)),
                           1,
                           50
                       ) as DOC_NAME,

                       t1.MODIFIEDON as DOC_DATE

                  from MTL.EPR_INPATIENT_DOCINDEX t

                 inner join MTL.EPR_INPATIENT t1
                         on t1.uhid = t.uhid
                        and t1.doc_type_name = '其他知情同意书'
                        and t1.doc_title in (
                               '医患协议书-新标',
                               '拒绝检查治疗告知书-新标',
                               '激素使用知情同意书',
                               '消化内镜知情同意书-新标',
                               '化疗知情同意书-新标',
                               '自动出院或转院告知书-新标',
                               '劝阻住院患者外出告知书-新标',
                               '电子纤维支气管镜检查知情同意书-新标',
                               '临床路径知情同意书-新标',
                               '使用植入类或Ⅲ级医用耗材知情同意书-新标',
                               '留置导尿知情同意书-新标',
                               '新冰冻知情同意书',
                               '留置胃管知情同意书-新标',
                               '转科、转诊（转院）知情同意书-新标',
                               '（新版）消化内镜知情同意书'
                            )

                  left join (
                       select paragraph_id,
                              content_text
                         from (
                               select x.段落编号 as paragraph_id,

                                      cast(
                                          dbms_lob.substr(
                                              x.Zqtynr,
                                              2000,
                                              1
                                          ) as varchar2(2000)
                                      ) as content_text,

                                      row_number() over (
                                          partition by x.段落编号
                                          order by
                                              dbms_lob.getlength(
                                                  x.Zqtynr
                                              ) desc nulls last,
                                              x.rowid
                                      ) as rn
                                 from MTL.EMRSD31 x
                              )
                        where rn = 1
                  ) t3
                    on t3.paragraph_id = t1.id

                  left join (
                       select uhid,
                              paragraph_id,
                              content_text
                         from (
                               select x.uhid,
                                      x.段落编号 as paragraph_id,

                                      cast(
                                          dbms_lob.substr(
                                              x.段落内容,
                                              2000,
                                              1
                                          ) as varchar2(2000)
                                      ) as content_text,

                                      row_number() over (
                                          partition by
                                              x.uhid,
                                              x.段落编号
                                          order by
                                              dbms_lob.getlength(
                                                  x.段落内容
                                              ) desc nulls last,
                                              x.rowid
                                      ) as rn
                                 from MTL.EMRSD_CONTENT x
                              )
                        where rn = 1
                  ) t4
                    on t4.uhid = t1.uhid
                   and t4.paragraph_id = t1.id

                  left join HIS.PAT_MASTER_INDEX pmi
                    on pmi.inp_no = t.p_inpatient_no

                  left join HIS.PAT_VISIT pv
                    on pv.patient_id = pmi.patient_id
                   and pv.visit_id = t.p_inpatient_times

                  left join (
                       select dept_code,
                              qmpt_code,
                              qmpt_name
                         from (
                               select cast(
                                          d.dept_code as varchar2(2000)
                                      ) as dept_code,

                                      cast(
                                          d.qmpt_code as varchar2(2000)
                                      ) as qmpt_code,

                                      cast(
                                          d.qmpt_name as varchar2(2000)
                                      ) as qmpt_name,

                                      row_number() over (
                                          partition by d.dept_code
                                          order by
                                              case
                                                  when d.qmpt_code is not null
                                                  then 0
                                                  else 1
                                              end,
                                              d.qmpt_code,
                                              d.qmpt_name
                                      ) as rn
                                 from HIS.DEPT_DICT d
                              )
                        where rn = 1
                  ) ks
                    on ks.dept_code =
                       cast(t.p_dept_code as varchar2(2000))

                  left join (
                       select patient_id,
                              visit_id,
                              diagnosis_code,
                              diagnosis_desc
                         from (
                               select d.patient_id,
                                      d.visit_id,
                                      d.diagnosis_code,
                                      d.diagnosis_desc,

                                      row_number() over (
                                          partition by
                                              d.patient_id,
                                              d.visit_id
                                          order by
                                              d.rowid
                                      ) as rn
                                 from HIS.DIAGNOSIS d
                                where d.diagnosis_type = '3'
                                  and d.diagnosis_no = '1'
                              )
                        where rn = 1
                  ) dd
                    on dd.patient_id = pv.patient_id
                   and dd.visit_id = pv.visit_id

                  left join (
                       select 院标名称,
                              院标编码,
                              国标编码,
                              国标名称
                         from (
                               select cd.院标名称,
                                      cd.院标编码,
                                      cd.国标编码,
                                      cd.国标名称,

                                      row_number() over (
                                          partition by
                                              nvl(
                                                  cd.院标编码,
                                                  cd.院标名称
                                              )
                                          order by
                                              case
                                                  when cd.国标编码 is not null
                                                  then 1
                                                  else 2
                                              end,
                                              cd.国标编码,
                                              cd.国标名称
                                      ) as rn
                                 from CDA.CDA_DICTIONARY cd
                                where cd.字典名称 =
                                      'ICD-10诊断编码'
                                  and cd.系统标识 = 'HIS'
                              )
                        where rn = 1
                  ) diag_cd
                    on (
                           diag_cd.院标编码 = dd.diagnosis_code
                        or (
                               diag_cd.院标编码 is null
                           and diag_cd.院标名称 = dd.diagnosis_desc
                           )
                       )

                  left join (
                       select local_code,
                              standard_code,
                              standard_name
                         from (
                               select cast(
                                          cd.院标编码
                                              as varchar2(2000)
                                      ) as local_code,

                                      cast(
                                          cd.国标编码
                                              as varchar2(2000)
                                      ) as standard_code,

                                      cast(
                                          cd.国标名称
                                              as varchar2(2000)
                                      ) as standard_name,

                                      row_number() over (
                                          partition by cd.院标编码
                                          order by
                                              case
                                                  when cd.国标编码 is not null
                                                  then 0
                                                  else 1
                                              end,
                                              cd.国标编码,
                                              cd.国标名称
                                      ) as rn
                                 from CDA.CDA_DICTIONARY cd
                                where cd.字典名称 = '家庭关系代码'
                              )
                        where rn = 1
                  ) relation_map
                    on relation_map.local_code =
                       cast(pmi.relationship as varchar2(2000))

                 where t1.doc_stats = '1'
               ) q
       ) d
 where d.id_rn = 1
