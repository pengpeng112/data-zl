
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_MEDICAL_RECORD_INFO" ("ID", "PATIENT_TYPE", "VISTING_NUM", "MED_TYPE", "MED_NOTE", "CREATE_TIME", "CREATE_DOC_ID", "CREATE_DOC", "LAST_TIME", "LAST_DOC_ID", "LAST_DOC", "ARCHIVE_TIME", "ORG_CODE", "ORG_NAME", "DISTRICT_CODE", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  select
       cast(
           substrb(
               '49557032X' || '|' ||
               pv.patient_id || '|' ||
               pv.visit_id || '|' ||
               nvl(to_char(t1.id), '-'),
               1,
               100
           ) as varchar2(100)
       ) as ID,--内码 是 主键；机构码|患者ID|住院次数|文书ID，避免同次住院多文书重复

       cast('2' as char(1)) as PATIENT_TYPE,--门急诊/住院标志 是；1门急诊，2住院

       cast(
           substrb(
               pv.patient_id || '|' || pv.visit_id,
               1,
               32
           ) as varchar2(32)
       ) as VISTING_NUM,--就诊标识号 是

      cast(
    case
        /* 1 入院记录类：只匹配明细值域，不返回大类1 */
        when t1.doc_type_name like '%24小时内入院死亡记录%' then '103'
        when t1.doc_type_name like '%24小时内入出院记录%' then '102'
        when t1.doc_type_name like '%再次入院记录%'
          or t1.doc_type_name like '%多次入院记录%' then '101'
        when t1.doc_type_name = '入院记录'
          or t1.doc_type_name like '%入院病历%' then '100'
        when t1.doc_type_name like '%其他入院记录%' then '104'

        /* 2 病程记录类：只匹配明细值域，不返回大类2 */
        when t1.doc_type_name like '%术后首次病程记录%' then '214'
        when t1.doc_type_name like '%首次病程记录%' then '201'
        when t1.doc_type_name like '%日常病程记录%' then '202'
        when t1.doc_type_name like '%上级医师查房记录%'
          or t1.doc_type_name like '%上级查房记录%' then '203'
        when t1.doc_type_name like '%疑难病例讨论%' then '204'
        when t1.doc_type_name like '%交接班记录%'
          or t1.doc_type_name like '%交（接）班记录%'
          or t1.doc_type_name like '%患者转科护理交接单%'
          or t1.doc_type_name like '%手术患者交接记录单%'
          or t1.doc_type_name like '%孕产妇出入产房交接记录单%' then '205'
        when t1.doc_type_name like '%转科记录%'
          or t1.doc_type_name like '%转入记录%' then '206'
        when t1.doc_type_name like '%阶段小结%' then '207'
        when t1.doc_type_name like '%抢救记录%' then '208'
        when t1.doc_type_name like '%有创诊疗操作记录%'
          or t1.doc_type_name like '%检查记录%'
          or t1.doc_type_name like '%治疗记录%' then '209'
        when t1.doc_type_name like '%会诊记录%'
          or t1.doc_type_name like '%护理会诊申请单%' then '210'
        when t1.doc_type_name like '%术前小结%' then '211'
        when t1.doc_type_name like '%术前讨论%' then '212'
        when t1.doc_type_name like '%手术记录%'
          or t1.doc_type_name like '%剖宫产记录%'
          or t1.doc_type_name like '%分娩记录%'
          or t1.doc_type_name like '%自然分娩记录%' then '213'
        when t1.doc_type_name like '%麻醉术前访视记录%' then '215'
        when t1.doc_type_name = '麻醉记录'
          or t1.doc_type_name like '%麻醉记录%' then '216'
        when t1.doc_type_name like '%手术安全核查记录%'
          or t1.doc_type_name like '%安全核查表%' then '217'
        when t1.doc_type_name like '%手术清点记录%' then '218'
        when t1.doc_type_name like '%麻醉术后访视记录%' then '219'
        when t1.doc_type_name like '%出院记录%'
          or t1.doc_type_name like '%出院小结%' then '220'
        when t1.doc_type_name = '死亡记录'
          or t1.doc_type_name like '%死亡记录%' then '221'
        when t1.doc_type_name like '%死亡病例讨论记录%' then '222'
        when t1.doc_type_name like '%病重（病危）患者护理记录%'
          or t1.doc_type_name like '%危重患者护理记录单%'
          or t1.doc_type_name like '%危重患者记录单%' then '223'

        /* 3 知情同意书类：只匹配明细值域，不返回大类3 */
        when t1.doc_type_name like '%手术知情同意书%'
          or t1.doc_type_name like '%手术同意书%' then '301'
        when t1.doc_type_name like '%PICC穿刺知情同意书%'
          or t1.doc_type_name like '%治疗类知情同意书%'
          or t1.doc_type_name like '%输血同意书%' then '302'
        when t1.doc_type_name like '%用药类知情同意书%'
          or t1.doc_type_name like '%特殊药品及材料使用同意书%' then '303'
        when t1.doc_type_name like '%检查类知情同意书%' then '304'
        when t1.doc_type_name like '%其他知情同意书%'
          or t1.doc_type_name like '%护理知情告知书%'
          or t1.doc_type_name like '%病重（危）通知书%'
          or t1.doc_type_name like '%病危（重）通知书%'
          or t1.doc_type_name like '%病危(重)通知书%'
          or t1.doc_type_name like '%医患沟通记录%' then '305'

        /* 其余护理、宣教、评估、证明、量表等暂无明确明细值域，暂归其他病程记录 */
        when t1.doc_type_name like '%护理记录%'
          or t1.doc_type_name like '%健康宣教%'
          or t1.doc_type_name like '%教育计划%'
          or t1.doc_type_name like '%评估%'
          or t1.doc_type_name like '%评分%'
          or t1.doc_type_name like '%筛查%'
          or t1.doc_type_name like '%出入量记录单%'
          or t1.doc_type_name like '%翻身记录单%'
          or t1.doc_type_name like '%生命体征记录单%'
          or t1.doc_type_name like '%微量血糖监测记录单%'
          or t1.doc_type_name like '%基础代谢率记录单%'
          or t1.doc_type_name like '%疼痛%'
          or t1.doc_type_name like '%证明%'
          or t1.doc_type_name like '%诊断证明%'
          or t1.doc_type_name like '%住院患者证明%' then '224'

        /* 未匹配到的住院文书，默认其他病程记录 */
        else '224'
    end as varchar2(3)
) as MED_TYPE,--病历类型 是；按平台明细值域转换，不使用大类1/2/3

       case
           when t4.段落内容 is not null then t4.段落内容
           else to_clob('-')
       end as MED_NOTE,--病历内容 是；CLOB字段，不再截取2000字

       to_char(t1.doc_create_date, 'yyyy-mm-dd hh24:mi:ss') as CREATE_TIME,--创建时间 是；统一时间格式

       cast(
           substrb(
               nvl(
                   (
                       select max(sd.id_no)
                         from his.staff_dict sd
                        where to_char(sd.name) = to_char(t1.createby)
                          and regexp_like(trim(to_char(sd.id_no)), '^[0-9]{17}[0-9Xx]$|^[0-9]{15}$')
                   ),
                   ''
               ),
               1,
               18
           ) as varchar2(18)
       ) as CREATE_DOC_ID,--创建医生身份证号；能匹配则取HIS.STAFF_DICT.ID_NO

       cast(
           substrb(
               nvl(to_char(t1.createby), '-'),
               1,
               50
           ) as varchar2(50)
       ) as CREATE_DOC,--创建医生姓名 是

       to_char(
           nvl(t1.modifiedon, t1.doc_create_date),
           'yyyy-mm-dd hh24:mi:ss'
       ) as LAST_TIME,--最后修改时间 是；统一时间格式

       cast(
           substrb(
               nvl(
                   (
                       select max(sd.id_no)
                         from his.staff_dict sd
                        where to_char(sd.name) = to_char(t1.modifiedby)
                          and regexp_like(trim(to_char(sd.id_no)), '^[0-9]{17}[0-9Xx]$|^[0-9]{15}$')
                   ),
                   ''
               ),
               1,
               18
           ) as varchar2(18)
       ) as LAST_DOC_ID,--最后修改医生身份证号；能匹配则取HIS.STAFF_DICT.ID_NO

       cast(
           substrb(
               nvl(to_char(t1.modifiedby), nvl(to_char(t1.createby), '-')),
               1,
               50
           ) as varchar2(50)
       ) as LAST_DOC,--最后修改医生姓名 是

     to_char(
    case
        when pv.docum_date is not null
         and pv.docum_date >= date '1900-01-01'
        then pv.docum_date

        when t1.doc_finish_date is not null
         and t1.doc_finish_date >= date '1900-01-01'
        then t1.doc_finish_date

        when t1.doc_sign_date is not null
         and t1.doc_sign_date >= date '1900-01-01'
        then t1.doc_sign_date

        when t1.modifiedon is not null
         and t1.modifiedon >= date '1900-01-01'
        then t1.modifiedon

        else t1.doc_create_date
    end,
    'yyyy-mm-dd hh24:mi:ss'
) as ARCHIVE_TIME,--归档日期 是；过滤0001-01-01等无效日期

       cast('49557032X' as varchar2(32)) as ORG_CODE,--医院组织机构代码 是

       cast('山东省第二人民医院' as varchar2(70)) as ORG_NAME,--医院名称 是

       cast('370104' as varchar2(6)) as DISTRICT_CODE,--所属行政区划 是

       cast('ADDHIS' as varchar2(10)) as EXCHANGE_TYPE,--交换类型 是

       to_char(sysdate, 'yyyy-mm-dd hh24:mi:ss') as SYSTEM_TIME--数据上传时间戳 是；统一时间格式

  from mtl.epr_inpatient_docindex t

  inner join  mtl.epr_inpatient t1
          on t.uhid = t1.uhid

  left join (
        select uhid,
               段落编号,
               段落内容
          from (
                select ec.uhid,
                       ec.段落编号,
                       ec.段落内容,
                       row_number() over (
                           partition by ec.uhid, ec.段落编号
                           order by dbms_lob.getlength(ec.段落内容) desc nulls last,
                                    ec.rowid
                       ) as rn
                  from mtl.emrsd_content ec
               )
         where rn = 1
       ) t4
    on t4.uhid = t.uhid
   and t4.段落编号 = t1.id

  inner join his.pat_master_index pmi
          on pmi.inp_no = t.p_inpatient_no

  inner join his.pat_visit pv
          on pv.patient_id = pmi.patient_id
         and pv.visit_id = t.p_inpatient_times

 where t1.doc_type_name is not null
