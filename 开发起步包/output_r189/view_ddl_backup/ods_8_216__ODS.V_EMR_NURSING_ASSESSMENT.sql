
  CREATE OR REPLACE FORCE VIEW "ODS"."V_EMR_NURSING_ASSESSMENT" ("ID", "ORG_CODE", "ORG_NAME", "PAT_NAME", "PAT_SEX", "PAT_TYPE_CODE", "VISITING_NUM", "DEPT_ID", "DEPT_NAME", "APPLY_DOC_NAME", "APPLY_DOC_ID", "NURSE_NAME", "NURSE_ID_NUM", "CREATE_TIME", "SCALE_NAME", "SCALE_CODE", "SCORE_VAL", "GRADE_LVL", "EXCHANGE_TYPE", "SYSTEM_TIME") AS 
  select
       q.ID,
       q.ORG_CODE,
       q.ORG_NAME,
       q.PAT_NAME,
       q.PAT_SEX,
       q.PAT_TYPE_CODE,
       q.VISITING_NUM,
       q.DEPT_ID,
       q.DEPT_NAME,
       q.APPLY_DOC_NAME,
       q.APPLY_DOC_ID,
       q.NURSE_NAME,
       q.NURSE_ID_NUM,
       q.CREATE_TIME,
       q.SCALE_NAME,
       q.SCALE_CODE,
       q.SCORE_VAL,

       cast(
           substrb(
               case
                   when q.GRADE_TEXT in ('低危', '低风险', '无风险', '轻度') then '低危'
                   when q.GRADE_TEXT in ('中危', '中风险', '中度') then '中危'
                   when q.GRADE_TEXT in ('高危', '高风险', '有风险', '重度') then '高危'

                   /* NIHSS：分值越高风险越高 */
                   when q.SCALE_CODE = '13' then
                        case
                            when q.SCORE_VAL <= 4 then '低危'
                            when q.SCORE_VAL <= 15 then '中危'
                            else '高危'
                        end

                   /* 洼田饮水试验 / 吞咽筛查 */
                   when q.SCALE_CODE in ('14', '15', '40') then
                        case
                            when q.SCORE_VAL <= 1 then '低危'
                            when q.SCORE_VAL <= 3 then '中危'
                            else '高危'
                        end

                   /* MMSE / MoCA：分值越低风险越高 */
                   when q.SCALE_CODE = '23' then
                        case
                            when q.SCORE_VAL >= 27 then '低危'
                            when q.SCORE_VAL >= 21 then '中危'
                            else '高危'
                        end

                   /* CHA2DS2-VASc */
                   when q.SCALE_CODE = '24' then
                        case
                            when q.SCORE_VAL = 0 then '低危'
                            when q.SCORE_VAL = 1 then '中危'
                            else '高危'
                        end

                   /* HAS-BLED */
                   when q.SCALE_CODE = '25' then
                        case
                            when q.SCORE_VAL <= 2 then '低危'
                            else '高危'
                        end

                   /* 成人 NRS2002 营养风险筛查 */
                   when q.SCALE_CODE = '48' then
                        case
                            when q.SCORE_VAL < 3 then '低危'
                            else '高危'
                        end

                   /* 疼痛类 VAS/NRS/VRS/FPS-R */
                   when q.SCALE_CODE in ('54', '61', '62', '63', '64') then
                        case
                            when q.SCORE_VAL <= 3 then '低危'
                            when q.SCORE_VAL <= 6 then '中危'
                            else '高危'
                        end

                   /* GCS/FOUR/GOS：一般分值越低风险越高 */
                   when q.SCALE_CODE in ('79', '80', '81') then
                        case
                            when q.SCORE_VAL >= 13 then '低危'
                            when q.SCORE_VAL >= 9 then '中危'
                            else '高危'
                        end

                   else '低危'
               end,
               1,
               10
           ) as varchar2(10)
       ) as GRADE_LVL,--评估等级 是

       q.EXCHANGE_TYPE,
       q.SYSTEM_TIME

  from (
        select
               q1.ID,
               q1.ORG_CODE,
               q1.ORG_NAME,
               q1.PAT_NAME,
               q1.PAT_SEX,
               q1.PAT_TYPE_CODE,
               q1.VISITING_NUM,
               q1.DEPT_ID,
               q1.DEPT_NAME,
               q1.APPLY_DOC_NAME,
               q1.APPLY_DOC_ID,
               q1.NURSE_NAME,
               q1.NURSE_ID_NUM,
               q1.CREATE_TIME,
               q1.SCALE_NAME,
               q1.SCALE_CODE,

               cast(
                   round(
                       case
                           /* NIHSS：只取明确总分/评分/溶栓前评分，避免误提15min */
                           when q1.SCALE_CODE = '13' then
                                to_number(
                                    coalesce(
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            'NIHSS[[:space:]]*(总分|评分|得分)[[:space:]:：]*([0-9]{1,2})([[:space:]]*分)?',
                                            1,
                                            1,
                                            'in',
                                            2
                                        ),
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            '溶[[:space:]]*栓[[:space:]]*前[^0-9]{0,20}([0-9]{1,2})([[:space:]]*分)?',
                                            1,
                                            1,
                                            'in',
                                            1
                                        ),
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            '入[[:space:]]*院[[:space:]]*时[^0-9]{0,20}NIHSS[^0-9]{0,20}([0-9]{1,2})([[:space:]]*分)?',
                                            1,
                                            1,
                                            'in',
                                            1
                                        )
                                    )
                                )

                           /* CHA2DS2-VASc：只取明确实际得分，不取总分上限9分说明 */
                           when q1.SCALE_CODE = '24' then
                                to_number(
                                    coalesce(
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            '(CHA2DS2[-－]?VASc|CHA?DS?[-－]?VASc|CHA2DS2VASc)[^0-9]{0,80}(实际得分|患者得分|总得分|合计得分|评估得分|评分结果|评定结果)[[:space:]:：]*([0-9]{1,2})',
                                            1,
                                            1,
                                            'in',
                                            3
                                        ),
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            '(实际得分|患者得分|总得分|合计得分|评估得分|评分结果|评定结果)[[:space:]:：]*([0-9]{1,2})',
                                            1,
                                            1,
                                            'in',
                                            2
                                        )
                                    )
                                )

                           /* HAS-BLED：只取明确实际得分，不取“收缩压>160mmHg”等说明 */
                           when q1.SCALE_CODE = '25' then
                                to_number(
                                    coalesce(
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            '(HAS[- ]?BLED|HASBLED)[^0-9]{0,80}(实际得分|患者得分|总得分|合计得分|评估得分|评分结果|评定结果)[[:space:]:：]*([0-9]{1,2})',
                                            1,
                                            1,
                                            'in',
                                            3
                                        ),
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            '(实际得分|患者得分|总得分|合计得分|评估得分|评分结果|评定结果)[[:space:]:：]*([0-9]{1,2})',
                                            1,
                                            1,
                                            'in',
                                            2
                                        )
                                    )
                                )

                           /* MMSE/MoCA：只取实际得分字段，避免提取满分30分说明 */
                           when q1.SCALE_CODE = '23' then
                                to_number(
                                    coalesce(
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            '(MMSE|MoCA|MOCA|简易智能精神状态)[^0-9]{0,100}(实际得分|患者得分|总得分|合计得分|评估得分|评分结果|评定结果)[[:space:]:：]*([0-9]{1,2})',
                                            1,
                                            1,
                                            'in',
                                            3
                                        ),
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            '(实际得分|患者得分|总得分|合计得分|评估得分|评分结果|评定结果)[[:space:]:：]*([0-9]{1,2})',
                                            1,
                                            1,
                                            'in',
                                            2
                                        )
                                    )
                                )

                           /* 洼田饮水试验：优先按I-V级转1-5分 */
                           when q1.SCALE_CODE = '40' then
                                case
                                    when regexp_like(q1.CONTENT_TEXT, '(评估结果|评定结果|结果|等级|级别)[^ⅠⅡⅢⅣⅤIVX一二三四五]{0,30}(Ⅴ|V|五)[级級]', 'n') then 5
                                    when regexp_like(q1.CONTENT_TEXT, '(评估结果|评定结果|结果|等级|级别)[^ⅠⅡⅢⅣⅤIVX一二三四五]{0,30}(Ⅳ|IV|四)[级級]', 'n') then 4
                                    when regexp_like(q1.CONTENT_TEXT, '(评估结果|评定结果|结果|等级|级别)[^ⅠⅡⅢⅣⅤIVX一二三四五]{0,30}(Ⅲ|III|三)[级級]', 'n') then 3
                                    when regexp_like(q1.CONTENT_TEXT, '(评估结果|评定结果|结果|等级|级别)[^ⅠⅡⅢⅣⅤIVX一二三四五]{0,30}(Ⅱ|II|二)[级級]', 'n') then 2
                                    when regexp_like(q1.CONTENT_TEXT, '(评估结果|评定结果|结果|等级|级别)[^ⅠⅡⅢⅣⅤIVX一二三四五]{0,30}(Ⅰ|I|一)[级級]', 'n') then 1
                                    else to_number(
                                             regexp_substr(
                                                 q1.CONTENT_TEXT,
                                                 '(洼田饮水试验|吞咽)[^0-9]{0,80}(实际得分|患者得分|总得分|合计得分|评估得分|评分结果|评定结果|得分|评分)[[:space:]:：]*([1-5])',
                                                 1,
                                                 1,
                                                 'in',
                                                 3
                                             )
                                         )
                                end

                           /* 吞咽筛查 / 吞咽功能障碍评价：只取明确得分 */
                           when q1.SCALE_CODE in ('14', '15') then
                                to_number(
                                    regexp_substr(
                                        q1.CONTENT_TEXT,
                                        '(吞咽|洼田)[^0-9]{0,100}(实际得分|患者得分|总得分|合计得分|评估得分|评分结果|评定结果|得分|评分)[[:space:]:：]*([0-9]{1,2})',
                                        1,
                                        1,
                                        'in',
                                        3
                                    )
                                )

                           /* 成人NRS2002营养风险筛查：只取明确总分/合计分，0分可以保留 */
                           when q1.SCALE_CODE = '48' then
                                to_number(
                                    coalesce(
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            '(NRS2002|NRS 2002|营养风险)[^0-9]{0,120}(总分|总得分|合计得分|合计分|营养风险总分|营养风险评分|评分结果|评定结果)[[:space:]:：]*([0-9]{1,2})',
                                            1,
                                            1,
                                            'in',
                                            3
                                        ),
                                        regexp_substr(
                                            q1.CONTENT_TEXT,
                                            '(总分|总得分|合计得分|合计分|营养风险总分|营养风险评分|评分结果|评定结果)[[:space:]:：]*([0-9]{1,2})',
                                            1,
                                            1,
                                            'in',
                                            2
                                        )
                                    )
                                )

                           /* 疼痛类：只取明确实际填写字段，不取4-6分说明 */
                           when q1.SCALE_CODE in ('54', '61', '62', '63', '64') then
                                case
                                    when regexp_like(
                                             q1.CONTENT_TEXT,
                                             '(评分标准|疼痛程度|轻度疼痛|中度疼痛|重度疼痛|0[[:space:]]*[-－][[:space:]]*3|4[[:space:]]*[-－][[:space:]]*6|7[[:space:]]*[-－][[:space:]]*10)',
                                             'n'
                                         )
                                     and not regexp_like(
                                             q1.CONTENT_TEXT,
                                             '(疼痛分值|疼痛评分|疼痛得分|实际得分|患者得分|本次评分|评估分值)[[:space:]:：]*[0-9]',
                                             'n'
                                         )
                                    then null
                                    else to_number(
                                             regexp_substr(
                                                 q1.CONTENT_TEXT,
                                                 '(疼痛分值|疼痛评分|疼痛得分|实际得分|患者得分|本次评分|评估分值|NRS评分|VAS评分)[[:space:]:：]*([0-9]{1,2})',
                                                 1,
                                                 1,
                                                 'in',
                                                 2
                                             )
                                         )
                                end

                           /* GCS/FOUR/GOS：只取明确评分 */
                           when q1.SCALE_CODE in ('79', '80', '81') then
                                to_number(
                                    regexp_substr(
                                        q1.CONTENT_TEXT,
                                        '(GCS评分|GCS总分|FOUR评分|FOUR总分|GOS评分|GOS总分|总分|评分结果|评定结果)[[:space:]:：]*([0-9]{1,2})',
                                        1,
                                        1,
                                        'in',
                                        2
                                    )
                                )

                           /* 其他量表：只取明确实际得分字段 */
                           else
                                to_number(
                                    regexp_substr(
                                        q1.CONTENT_TEXT,
                                        '(实际得分|患者得分|总得分|合计得分|评估得分|评分结果|评定结果)[[:space:]:：]*([0-9]+([.][0-9]+)?)',
                                        1,
                                        1,
                                        'in',
                                        2
                                    )
                                )
                       end,
                       2
                   ) as number
               ) as SCORE_VAL,--评分数值 是

               regexp_substr(
                   q1.CONTENT_TEXT,
                   '(评估等级|风险等级|判定结果|评估结果|评分结果|评定结果|结果)[^低中高轻重有无]{0,40}(低危|中危|高危|低风险|中风险|高风险|无风险|有风险|轻度|中度|重度)',
                   1,
                   1,
                   'n',
                   2
               ) as GRADE_TEXT,--只取明确结果字段中的等级

               q1.EXCHANGE_TYPE,
               q1.SYSTEM_TIME

          from (
                select
                       b.ID,
                       b.ORG_CODE,
                       b.ORG_NAME,
                       b.PAT_NAME,
                       b.PAT_SEX,
                       b.PAT_TYPE_CODE,
                       b.VISITING_NUM,
                       b.DEPT_ID,
                       b.DEPT_NAME,
                       b.APPLY_DOC_NAME,
                       b.APPLY_DOC_ID,
                       b.NURSE_NAME,
                       b.NURSE_ID_NUM,
                       b.CREATE_TIME,

                       cast(
                           substrb(
                               case
                                   when upper(b.DOC_TITLE) like '%PSI%' then 'PSI 评分'

                                   when upper(b.DOC_TITLE) like '%APGAR%' then 'Apgar 评分'

                                   when upper(b.DOC_TITLE) like '%NIHSS%' then '美国国立卫生研究院卒中量表（NIHSS）'

                                   when upper(b.DOC_TITLE) like '%CHA2DS2%'
                                     or upper(b.DOC_TITLE) like '%CHA?DS?%'
                                     or upper(b.DOC_TITLE) like '%VASC%' then 'CHA2DS2-VASc评分表'

                                   when upper(b.DOC_TITLE) like '%HAS-BLED%'
                                     or upper(b.DOC_TITLE) like '%HASBLED%' then 'HAS-BLED 评分表'

                                   when upper(b.DOC_TITLE) like '%MMSE%'
                                     or upper(b.DOC_TITLE) like '%MOCA%'
                                     or b.DOC_TITLE like '%简易智能精神状态%' then '至少包括MMSE 和MoCA 量表（2个量表均需完成评估）'

                                   when b.DOC_TITLE like '%洼田饮水试验%'
                                     or b.CONTENT_TEXT like '%洼田饮水试验%' then '洼田饮水试验'

                                   when b.DOC_TITLE like '%洼田%'
                                     or b.DOC_TITLE like '%吞咽功能障碍%'
                                     or b.CONTENT_TEXT like '%吞咽功能障碍%' then '洼田吞咽功能障碍评价'

                                   when b.DOC_TITLE like '%吞咽困难%'
                                     or b.DOC_TITLE like '%吞咽功能筛查%' then '吞咽功能筛查工具包括洼田饮水试验'

                                   when (
                                           upper(b.DOC_TITLE) like '%BARTHEL%'
                                        or b.DOC_TITLE like '%Barthel%'
                                        or b.DOC_TITLE like '%改良Barthel%'
                                        or b.DOC_TITLE like '%日常生活能力%'
                                        )
                                        and b.DOC_TITLE not like '%巴氏腺%'
                                   then '改良 Barthel 指数评分表'

                                   when upper(b.DOC_TITLE) like '%BRUNNSTROM%' then 'Brunnstrom 分期'

                                   when upper(b.DOC_TITLE) like '%FUGL%'
                                     or upper(b.DOC_TITLE) like '%MEYER%' then 'Fugl-Meyer运动功能评分'

                                   when b.DOC_TITLE like '%失语%' then '失语症筛查表'

                                   when upper(b.DOC_TITLE) like '%NLI%'
                                     or b.DOC_TITLE like '%神经损伤平面%' then '神经损伤平面（NLI）评定'

                                   when upper(b.DOC_TITLE) like '%ASIA%'
                                     or upper(b.DOC_TITLE) like '%AIS%' then 'ASIA 损伤分级（AIS）评定（任选一个即可）'

                                   when upper(b.DOC_TITLE) like '%NRS2002%'
                                     or upper(b.DOC_TITLE) like '%NRS 2002%'
                                     or b.DOC_TITLE like '%营养风险筛查%' then '成人NRS 2002营养风险筛查表'

                                   when upper(b.DOC_TITLE) like '%STAMP%' then '儿童STAMP量表'

                                   when upper(b.DOC_TITLE) like '%PG-SGA%'
                                     or upper(b.DOC_TITLE) like '%PGSGA%' then 'PG-SGA营养评估量表'

                                   when upper(b.DOC_TITLE) like '%GCS%'
                                     or b.DOC_TITLE like '%格拉斯哥昏迷%' then '格拉斯哥昏迷量表（GCS）'

                                   when upper(b.DOC_TITLE) like '%FOUR%' then '格拉斯哥昏迷量表（GCS）或全面无反应性量表（FOUR）（任选一个即可）'

                                   when upper(b.DOC_TITLE) like '%GOS%'
                                     or b.DOC_TITLE like '%格拉斯哥结果%' then '格拉斯哥结果评估量表（GOS）'

                                   /* 疼痛类：只按标题判断，不按CONTENT_TEXT判断 */
                                   when upper(b.DOC_TITLE) like '%VAS%'
                                     or b.DOC_TITLE like '%视觉模拟%' then '视觉模拟评分量表（VAS）'

                                   when upper(b.DOC_TITLE) like '%VRS%'
                                     or b.DOC_TITLE like '%口述分级%' then '口述分级法（VRS）'

                                   when upper(b.DOC_TITLE) like '%FPS%'
                                     or b.DOC_TITLE like '%面部表情%' then '改良面部表情疼痛评估工具（FPS-R）等（任选一个即可）'

                                   when upper(b.DOC_TITLE) like '%NRS%'
                                     or b.DOC_TITLE like '%数字评分%'
                                     or b.DOC_TITLE like '%疼痛综合评估%' then '数字评分量表（NRS）'
                               end,
                               1,
                               200
                           ) as varchar2(200)
                       ) as SCALE_NAME,--评估量表名称 是

                       cast(
                           substrb(
                               case
                                   when upper(b.DOC_TITLE) like '%PSI%' then '01'

                                   when upper(b.DOC_TITLE) like '%APGAR%' then '06'

                                   when upper(b.DOC_TITLE) like '%NIHSS%' then '13'

                                   when upper(b.DOC_TITLE) like '%CHA2DS2%'
                                     or upper(b.DOC_TITLE) like '%CHA?DS?%'
                                     or upper(b.DOC_TITLE) like '%VASC%' then '24'

                                   when upper(b.DOC_TITLE) like '%HAS-BLED%'
                                     or upper(b.DOC_TITLE) like '%HASBLED%' then '25'

                                   when upper(b.DOC_TITLE) like '%MMSE%'
                                     or upper(b.DOC_TITLE) like '%MOCA%'
                                     or b.DOC_TITLE like '%简易智能精神状态%' then '23'

                                   when b.DOC_TITLE like '%洼田饮水试验%'
                                     or b.CONTENT_TEXT like '%洼田饮水试验%' then '40'

                                   when b.DOC_TITLE like '%洼田%'
                                     or b.DOC_TITLE like '%吞咽功能障碍%'
                                     or b.CONTENT_TEXT like '%吞咽功能障碍%' then '15'

                                   when b.DOC_TITLE like '%吞咽困难%'
                                     or b.DOC_TITLE like '%吞咽功能筛查%' then '14'

                                   when (
                                           upper(b.DOC_TITLE) like '%BARTHEL%'
                                        or b.DOC_TITLE like '%Barthel%'
                                        or b.DOC_TITLE like '%改良Barthel%'
                                        or b.DOC_TITLE like '%日常生活能力%'
                                        )
                                        and b.DOC_TITLE not like '%巴氏腺%'
                                   then '30'

                                   when upper(b.DOC_TITLE) like '%BRUNNSTROM%' then '32'

                                   when upper(b.DOC_TITLE) like '%FUGL%'
                                     or upper(b.DOC_TITLE) like '%MEYER%' then '33'

                                   when b.DOC_TITLE like '%失语%' then '36'

                                   when upper(b.DOC_TITLE) like '%NLI%'
                                     or b.DOC_TITLE like '%神经损伤平面%' then '43'

                                   when upper(b.DOC_TITLE) like '%ASIA%'
                                     or upper(b.DOC_TITLE) like '%AIS%' then '44'

                                   when upper(b.DOC_TITLE) like '%NRS2002%'
                                     or upper(b.DOC_TITLE) like '%NRS 2002%'
                                     or b.DOC_TITLE like '%营养风险筛查%' then '48'

                                   when upper(b.DOC_TITLE) like '%STAMP%' then '49'

                                   when upper(b.DOC_TITLE) like '%PG-SGA%'
                                     or upper(b.DOC_TITLE) like '%PGSGA%' then '52'

                                   when upper(b.DOC_TITLE) like '%GCS%'
                                     or b.DOC_TITLE like '%格拉斯哥昏迷%' then '80'

                                   when upper(b.DOC_TITLE) like '%FOUR%' then '79'

                                   when upper(b.DOC_TITLE) like '%GOS%'
                                     or b.DOC_TITLE like '%格拉斯哥结果%' then '81'

                                   /* 疼痛类：只按标题判断，不按CONTENT_TEXT判断 */
                                   when upper(b.DOC_TITLE) like '%VAS%'
                                     or b.DOC_TITLE like '%视觉模拟%' then '61'

                                   when upper(b.DOC_TITLE) like '%VRS%'
                                     or b.DOC_TITLE like '%口述分级%' then '63'

                                   when upper(b.DOC_TITLE) like '%FPS%'
                                     or b.DOC_TITLE like '%面部表情%' then '64'

                                   when upper(b.DOC_TITLE) like '%NRS%'
                                     or b.DOC_TITLE like '%数字评分%'
                                     or b.DOC_TITLE like '%疼痛综合评估%' then '62'
                               end,
                               1,
                               100
                           ) as varchar2(100)
                       ) as SCALE_CODE,--评估量表编码 是

                       b.CONTENT_TEXT,
                       b.EXCHANGE_TYPE,
                       b.SYSTEM_TIME

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
                               ) as ID,--主键 是

                               cast('49557032X' as varchar2(32)) as ORG_CODE,--医院组织机构代码 是

                               cast('山东省第二人民医院' as varchar2(70)) as ORG_NAME,--医院名称 是

                               cast(
                                   substrb(
                                       nvl(to_char(t.p_name), to_char(pmi.name)),
                                       1,
                                       32
                                   ) as varchar2(32)
                               ) as PAT_NAME,--被评估患者姓名 是

                               cast(
                                   case
                                       when trim(pmi.sex) = '男' then '1'
                                       when trim(pmi.sex) = '女' then '2'
                                       when trim(pmi.sex) in ('未知','未说明','不明') then '0'
                                       else '9'
                                   end as char(1)
                               ) as PAT_SEX,--被评估患者性别 是

                               cast('2' as char(1)) as PAT_TYPE_CODE,--被评估患者类别 是

                               cast(
                                   substrb(
                                       pv.patient_id || '|' || pv.visit_id,
                                       1,
                                       32
                                   ) as varchar2(32)
                               ) as VISITING_NUM,--被评估病人就诊号 是

                               cast(
                                   substrb(
                                       nvl(to_char(ks.qmpt_code), to_char(t.p_dept_code)),
                                       1,
                                       12
                                   ) as varchar2(12)
                               ) as DEPT_ID,--患者所在科室编码 是

                               cast(
                                   substrb(
                                       nvl(to_char(ks.qmpt_name), to_char(t.p_dept_name)),
                                       1,
                                       50
                                   ) as varchar2(50)
                               ) as DEPT_NAME,--患者所在科室名称 是

                               cast(null as varchar2(32)) as APPLY_DOC_NAME,--医生姓名；来源不确定，先置空

                               cast(null as varchar2(18)) as APPLY_DOC_ID,--医生身份证号码；来源不确定，先置空

                               cast(
                                   substrb(
                                       nvl(to_char(t1.createby), nvl(to_char(t1.modifiedby), '-')),
                                       1,
                                       32
                                   ) as varchar2(32)
                               ) as NURSE_NAME,--护士姓名；暂取创建人

                               cast(
                                   substrb(
                                       nvl(
                                           (
                                               select max(sd.id_no)
                                                 from his.staff_dict sd
                                                where to_char(sd.name) = nvl(to_char(t1.createby), to_char(t1.modifiedby))
                                                  and regexp_like(trim(to_char(sd.id_no)), '^[0-9]{17}[0-9Xx]$|^[0-9]{15}$')
                                           ),
                                           ''
                                       ),
                                       1,
                                       18
                                   ) as varchar2(18)
                               ) as NURSE_ID_NUM,--护士身份证号

                               to_char(
                                   nvl(t1.doc_title_time, nvl(t1.createon, t1.doc_create_date)),
                                   'yyyy-mm-dd hh24:mi:ss'
                               ) as CREATE_TIME,--评估时间 是

                               t1.doc_title as DOC_TITLE,

                               dbms_lob.substr(ct.段落内容, 2000, 1) as CONTENT_TEXT,--内部字段，用于识别量表和提取得分

                               cast('ADDHIS' as varchar2(10)) as EXCHANGE_TYPE,--交换类型 是

                               to_char(sysdate, 'yyyy-mm-dd hh24:mi:ss') as SYSTEM_TIME--数据上传/更新时间 是

                          from mtl.epr_inpatient_docindex t

                          inner join mtl.epr_inpatient t1
                                  on t.uhid = t1.uhid

                          inner join his.pat_master_index pmi
                                  on pmi.patient_id = t.p_clinic_id

                          inner join his.pat_visit pv
                                  on pv.patient_id = pmi.patient_id
                                 and pv.visit_id = t.p_inpatient_times
                                 and pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')
                                 and pv.discharge_date_time <  to_date('2025-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')

                          left join his.dept_dict ks
                                 on ks.dept_code = t.p_dept_code

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
                          ) ct
                            on ct.uhid = t.uhid
                           and ct.段落编号 = t1.id

                         where t1.doc_title is not null
                           and t1.doc_title not like '%巴氏腺%'
                           and (
                                   upper(t1.doc_title) like '%PSI%'
                                or upper(t1.doc_title) like '%APGAR%'
                                or upper(t1.doc_title) like '%NIHSS%'
                                or upper(t1.doc_title) like '%CHA2DS2%'
                                or upper(t1.doc_title) like '%CHA?DS?%'
                                or upper(t1.doc_title) like '%VASC%'
                                or upper(t1.doc_title) like '%HAS-BLED%'
                                or upper(t1.doc_title) like '%HASBLED%'
                                or upper(t1.doc_title) like '%MMSE%'
                                or upper(t1.doc_title) like '%MOCA%'
                                or t1.doc_title like '%简易智能精神状态%'
                                or t1.doc_title like '%吞咽困难%'
                                or t1.doc_title like '%吞咽功能筛查%'
                                or t1.doc_title like '%洼田%'
                                or upper(t1.doc_title) like '%BARTHEL%'
                                or t1.doc_title like '%Barthel%'
                                or t1.doc_title like '%改良Barthel%'
                                or t1.doc_title like '%日常生活能力%'
                                or upper(t1.doc_title) like '%BRUNNSTROM%'
                                or upper(t1.doc_title) like '%FUGL%'
                                or upper(t1.doc_title) like '%MEYER%'
                                or t1.doc_title like '%失语%'
                                or upper(t1.doc_title) like '%NLI%'
                                or t1.doc_title like '%神经损伤平面%'
                                or upper(t1.doc_title) like '%ASIA%'
                                or upper(t1.doc_title) like '%AIS%'
                                or upper(t1.doc_title) like '%NRS2002%'
                                or upper(t1.doc_title) like '%NRS 2002%'
                                or t1.doc_title like '%营养风险筛查%'
                                or upper(t1.doc_title) like '%STAMP%'
                                or upper(t1.doc_title) like '%PG-SGA%'
                                or upper(t1.doc_title) like '%PGSGA%'
                                or upper(t1.doc_title) like '%GCS%'
                                or t1.doc_title like '%格拉斯哥昏迷%'
                                or upper(t1.doc_title) like '%FOUR%'
                                or upper(t1.doc_title) like '%GOS%'
                                or t1.doc_title like '%格拉斯哥结果%'
                                or t1.doc_title like '%疼痛综合评估%'
                                or upper(t1.doc_title) like '%VAS%'
                                or upper(t1.doc_title) like '%NRS%'
                                or upper(t1.doc_title) like '%VRS%'
                                or upper(t1.doc_title) like '%FPS%'
                                or t1.doc_title like '%视觉模拟%'
                                or t1.doc_title like '%数字评分%'
                                or t1.doc_title like '%口述分级%'
                                or t1.doc_title like '%面部表情%'
                               )
                       ) b
               ) q1
       ) q
 where q.SCALE_NAME is not null
   and q.SCALE_CODE is not null
   and q.SCORE_VAL is not null
