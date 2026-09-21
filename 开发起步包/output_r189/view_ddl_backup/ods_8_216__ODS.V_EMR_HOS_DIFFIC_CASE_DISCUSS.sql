
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_HOS_DIFFIC_CASE_DISCUSS" ("ID", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME", "ADMISSION_UN_NUM", "DEP_NAME", "DEP_CODE", "AREA_NAME", "WARD_NUM", "SICKBED_NUM", "DISCUSS_DATE", "DISCUSS_ADDRESS", "HOET_NAME", "DISCUSS_PEOPLE_LIST", "DISCUSS_OPINION", "FOUR_DIAGNOSIS", "SYN_DIFFER_DES", "CH_MED_PRES_DA_CONTENT", "MEDICATION_METHOD", "HOST_OPINION", "DOC_NAME", "ATTENDING_PHYSICIAN_NAME", "CHIEF_DOCTOR_NAME") AS 
  select substr('49557032X'||'|'||t.uhid||'|'||t1.id, 1, 100) as ID,--  内码  是 主键

       '49557032X' as ORG_CODE,--  医院组织机构代码  是 必填

       '山东省第二人民医院' as ORG_NAME,--  医院名称  是 必填

       '370104' as DISTRICT_CODE,-- 所属行政区划  是 按机构所在的行政区划（区县）

       'ADDHIS' as EXCHANGE_TYPE,-- 交换类型  是 INSERT：向平台传新数据时 UPDATE：向平台更新某条数据时 DELETE：从平台删除某条数据时 ADDHIS :向平台补充历史数据

       cast(systimestamp as timestamp) as SYSTEM_TIME,-- 数据上传时间戳 是

       substr(
           nvl(ttt.patient_id||'|'||ttt.visit_id, t.p_inpatient_no||'|'||t.p_inpatient_times),
           1,
           50
       ) as ADMISSION_UN_NUM,--  住院唯一标示号 是

       nvl(
           (select ks.qmpt_name
              from his.dept_dict ks
             where ks.dept_code = t.p_dept_code
               and rownum = 1),
           t.p_dept_name
       ) as DEP_NAME,--  科室名称  是

       nvl(
           (select ks.qmpt_code
              from his.dept_dict ks
             where ks.dept_code = t.p_dept_code
               and rownum = 1),
           t.p_dept_code
       ) as DEP_CODE,--  科室代码    按平台值域填写

       t.p_Are_Name as AREA_NAME,-- 病区名称

       cast(null as varchar2(10)) as WARD_NUM,--  病房号

       substr(t.P_BEDNO, 1, 10) as SICKBED_NUM,-- 病床号

       nvl(
           case
             /* 格式1：讨论日期：2020-12-28 16：00 / 2021-03-18 18:00 */
             when regexp_substr(
                    dbms_lob.substr(t4.段落内容, 2000, 1),
                    '(讨论日期|讨论时间)[[:space:]]*[:：][[:space:]]*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2})',
                    1, 1, 'n', 2
                  ) is not null
             then to_date(
                    replace(
                      replace(
                        replace(
                          regexp_substr(
                            dbms_lob.substr(t4.段落内容, 2000, 1),
                            '(讨论日期|讨论时间)[[:space:]]*[:：][[:space:]]*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2})',
                            1, 1, 'n', 2
                          ),
                          '/', '-'
                        ),
                        '.', '-'
                      ),
                      '：', ':'
                    ),
                    'yyyy-mm-dd hh24:mi'
                  )

             /* 格式2：讨论日期：2020年12月30日 14时00分 */
             when regexp_substr(
                    dbms_lob.substr(t4.段落内容, 2000, 1),
                    '(讨论日期|讨论时间)[[:space:]]*[:：][[:space:]]*([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日[[:space:]]*[0-9]{1,2}时[0-9]{1,2}分)',
                    1, 1, 'n', 2
                  ) is not null
             then to_date(
                    replace(
                      replace(
                        replace(
                          replace(
                            replace(
                              regexp_substr(
                                dbms_lob.substr(t4.段落内容, 2000, 1),
                                '(讨论日期|讨论时间)[[:space:]]*[:：][[:space:]]*([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日[[:space:]]*[0-9]{1,2}时[0-9]{1,2}分)',
                                1, 1, 'n', 2
                              ),
                              '年', '-'
                            ),
                            '月', '-'
                          ),
                          '日', ' '
                        ),
                        '时', ':'
                      ),
                      '分', ''
                    ),
                    'yyyy-mm-dd hh24:mi'
                  )

             /* 格式3：2021-03-17 10:00 在……主持下 */
             when regexp_substr(
                    dbms_lob.substr(t4.段落内容, 2000, 1),
                    '([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2})[[:space:]]*在',
                    1, 1, 'n', 1
                  ) is not null
             then to_date(
                    replace(
                      replace(
                        replace(
                          regexp_substr(
                            dbms_lob.substr(t4.段落内容, 2000, 1),
                            '([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}[[:space:]]+[0-9]{1,2}[：:][0-9]{2})[[:space:]]*在',
                            1, 1, 'n', 1
                          ),
                          '/', '-'
                        ),
                        '.', '-'
                      ),
                      '：', ':'
                    ),
                    'yyyy-mm-dd hh24:mi'
                  )

             /* 格式4：只有日期，例如 讨论日期：2021-01-06 / 2021.04.07 */
             when regexp_substr(
                    dbms_lob.substr(t4.段落内容, 2000, 1),
                    '(讨论日期|讨论时间)[[:space:]]*[:：][[:space:]]*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2})',
                    1, 1, 'n', 2
                  ) is not null
             then to_date(
                    replace(
                      replace(
                        regexp_substr(
                          dbms_lob.substr(t4.段落内容, 2000, 1),
                          '(讨论日期|讨论时间)[[:space:]]*[:：][[:space:]]*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2})',
                          1, 1, 'n', 2
                        ),
                        '/', '-'
                      ),
                      '.', '-'
                    ),
                    'yyyy-mm-dd'
                  )

             /* 格式5：2021年3月17日下午15时 / 2021年4月26日上午11时 */
             when regexp_substr(
                    dbms_lob.substr(t4.段落内容, 2000, 1),
                    '([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日[[:space:]]*(上午|下午)?[0-9]{1,2}时)',
                    1, 1, 'n', 1
                  ) is not null
             then to_date(
                    replace(
                      replace(
                        replace(
                          replace(
                            replace(
                              regexp_replace(
                                regexp_substr(
                                  dbms_lob.substr(t4.段落内容, 2000, 1),
                                  '([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日[[:space:]]*(上午|下午)?[0-9]{1,2}时)',
                                  1, 1, 'n', 1
                                ),
                                '上午|下午',
                                ''
                              ),
                              '年', '-'
                            ),
                            '月', '-'
                          ),
                          '日', ' '
                        ),
                        '时', ':00'
                      ),
                      '分', ''
                    ),
                    'yyyy-mm-dd hh24:mi'
                  )
           end,
           cast(t1.Createon as date)
       ) as DISCUSS_DATE,--  讨论日期时间  是

       substr(
         nvl(
           t3.tldd,
           nvl(
             regexp_substr(
               dbms_lob.substr(t4.段落内容, 2000, 1),
               '讨论地点[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]+)',
               1, 1, 'n', 1
             ),
             nvl(t1.Doc_Dept_Name, t.p_dept_name) || '医生办公室'
           )
         ),
         1,
         50
       ) as DISCUSS_ADDRESS,-- 讨论地点  是

      nvl( substr(
         nvl(
           t3.Zcrxm,
           regexp_replace(
             nvl(
               regexp_substr(
                 dbms_lob.substr(t4.段落内容, 2000, 1),
                 '主持人[[:space:]]*[:：][[:space:]]*([^[:cntrl:]]{2,30})',
                 1, 1, 'n', 1
               ),
               regexp_substr(
                 dbms_lob.substr(t4.段落内容, 2000, 1),
                 '在[^，,。；;]{0,40}主持下',
                 1, 1, 'n'
               )
             ),
             '^在|的?主持下$|科主任|主任医师|副主任医师|主任|副主任|主治医师|住院医师|医师|[[:space:]。]+',
             ''
           )
         ),
         1,
         50
       ) ,t1.MODIFIEDBY) as HOET_NAME,-- 主持人姓名 是
       substr(
         nvl(
           t3.Cjtlrymd,
           nvl(
             regexp_substr(
               dbms_lob.substr(t4.段落内容, 2000, 1),
               '(参加人员|参与人员)[[:space:]]*[:：][[:space:]]*(.*?)(具体讨论意见|讨论过程|主持人小结|讨论结论|$)',
               1, 1, 'n', 2
             ),
             case
               when regexp_like(dbms_lob.substr(t4.段落内容, 2000, 1), '全科人员') then '全科人员'
               when regexp_like(dbms_lob.substr(t4.段落内容, 2000, 1), '多学科会诊|MDT') then '多学科会诊人员'
               else '-'
             end
           )
         ),
         1,
         200
       ) as DISCUSS_PEOPLE_LIST,-- 参加讨论人员名单

       nvl( substr(
         nvl(
           t3.tlyj,
           nvl(
             regexp_substr(
               dbms_lob.substr(t4.段落内容, 2000, 1),
               '(具体讨论意见|讨论过程|讨论结论如下|讨论结果如下|讨论总结如下)[[:space:]]*[:：]?[[:space:]]*(.*?)(主持人小结意见|主持人小结|主持人签名|记录医师签名|/[[:space:]]*[^/[:cntrl:]]*$|$)',
               1, 1, 'n', 2
             ),
             dbms_lob.substr(t4.段落内容, 2000, 1)
           )
         ),
         1,
         2000
       ),'-') as DISCUSS_OPINION,-- 讨论意见  是

       substr(nullif(t3.Zyszgcjg, ''), 1, 1000) as FOUR_DIAGNOSIS,--  中医“四诊”观察结果

       substr(nullif(t3.Zyszgcjg, ''), 1, 2000) as SYN_DIFFER_DES,--  辨证论治详细描述

       cast(null as varchar2(1000)) as CH_MED_PRES_DA_CONTENT,--  中药处方医嘱内容

       substr(nullif(t3.zyyyff, ''), 1, 100) as MEDICATION_METHOD,-- 中药用药方法

       substr(
         nvl(
           t3.Zcrzjyj,
           nvl(
             regexp_substr(
               dbms_lob.substr(t4.段落内容, 2000, 1),
               '主持人[[:space:]]*小[[:space:]]*结(意见)?[[:space:]]*[:：][[:space:]]*(.*?)(主持人签名|记录医师签名|/[[:space:]]*[^/[:cntrl:]]*$|$)',
               1, 1, 'n', 2
             ),
             dbms_lob.substr(t4.段落内容, 2000, 1)
           )
         ),
         1,
         2000
       ) as HOST_OPINION,--  主持人总结意见

       substr(
         nvl(
           regexp_substr(
             dbms_lob.substr(t4.段落内容, 2000, 1),
             '记录医师签名[[:space:]]*[:：][[:space:]]*([^[:cntrl:][:space:]/]+)',
             1, 1, 'n', 1
           ),
           nvl(
             regexp_substr(
               dbms_lob.substr(t4.段落内容, 2000, 1),
               '/[[:space:]]*([^/[:cntrl:][:space:]]+)[[:space:]]*$',
               1, 1, 'n', 1
             ),
             nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = nvl(t1.Modifiedby, t1.Createby)
                   and rownum = 1),
               nvl(t1.Modifiedby, t1.Createby)
             )
           )
         ),
         1,
         50
       ) as DOC_NAME,--  医师签名

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = ttt.ATTENDING_DOCTOR
                   and rownum = 1),
               ttt.ATTENDING_DOCTOR
           ),
           1,
           50
       ) as ATTENDING_PHYSICIAN_NAME,--  主治医师签名    主治医师签名

       substr(
           nvl(
               (select sd.name
                  from his.staff_dict sd
                 where sd.emp_no = ttt.Director
                   and rownum = 1),
               ttt.Director
           ),
           1,
           50
       ) as CHIEF_DOCTOR_NAME --主任医师姓名

from  mtl.EPR_INPATIENT_DOCINDEX t

left join his.pat_master_index tt
       on tt.inp_no = t.p_inpatient_no

left join his.pat_visit ttt
       on tt.patient_id = ttt.patient_id
      and t.p_inpatient_times = ttt.visit_id

inner JOIN mtl.EPR_INPATIENT t1
        on t.UHID = t1.UHID
       /*and t1.DOC_STATS = '1'*/
       and t1.doc_title like '%疑难病例%'

left join mtl.EMRSD40 T3
       ON T3.段落编号 = T1.ID

Left Join MTL.EMRSD_CONTENT t4
       On t4.UHID = t.UHID
      and t4.段落编号 = t3.段落编号

where ttt.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
  and ttt.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
