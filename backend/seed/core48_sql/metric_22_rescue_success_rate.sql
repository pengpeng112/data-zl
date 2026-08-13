/*
指标 22：抢救成功率
分子：大抢救医嘱开立后24小时内无死亡医嘱的例次数
分母：同期大抢救总例次数
月份归属：HIS.PAT_VISIT.DISCHARGE_DATE_TIME
纳排：大抢救或院内抢救费医嘱；排除撤销医嘱；按患者、就诊、医嘱开始时间去重
*/
WITH rescue_evt AS (
    SELECT DISTINCT
        o.patient_id,
        o.visit_id,
        o.start_date_time,
        v.discharge_date_time
    FROM HIS.ORDERS o
    JOIN HIS.PAT_VISIT v
      ON v.patient_id = o.patient_id
     AND v.visit_id = o.visit_id
    WHERE o.cancel_date_time IS NULL
      AND o.start_date_time IS NOT NULL
      AND (
          INSTR(o.order_text, '大抢救') > 0
          OR INSTR(o.order_text, '院内抢救费') > 0
      )
      AND o.start_date_time >= TO_DATE(:start_time, 'YYYY-MM-DD HH24:MI:SS') - 90
      AND o.start_date_time < TO_DATE(:end_time, 'YYYY-MM-DD HH24:MI:SS')
      AND v.discharge_date_time >= TO_DATE(:start_time, 'YYYY-MM-DD HH24:MI:SS')
      AND v.discharge_date_time < TO_DATE(:end_time, 'YYYY-MM-DD HH24:MI:SS')
),
death_flag AS (
    SELECT
        r.patient_id,
        r.visit_id,
        r.start_date_time,
        MAX(
            CASE
                WHEN d.start_date_time >= r.start_date_time
                 AND d.start_date_time < r.start_date_time + 1
                THEN 1
                ELSE 0
            END
        ) AS died
    FROM rescue_evt r
    JOIN HIS.ORDERS d
      ON d.patient_id = r.patient_id
     AND d.visit_id = r.visit_id
     AND d.cancel_date_time IS NULL
     AND INSTR(d.order_text, '死亡') > 0
    GROUP BY r.patient_id, r.visit_id, r.start_date_time
)
SELECT
    '指标 22：抢救成功率' AS 指标,
    TO_CHAR(r.discharge_date_time, 'YYYY-MM') AS 月份,
    COUNT(*) - SUM(NVL(df.died, 0)) AS 分子,
    COUNT(*) AS 分母,
    '可用-docx口径(大抢救+24h内无死亡医嘱)' AS 说明
FROM rescue_evt r
LEFT JOIN death_flag df
  ON df.patient_id = r.patient_id
 AND df.visit_id = r.visit_id
 AND df.start_date_time = r.start_date_time
GROUP BY TO_CHAR(r.discharge_date_time, 'YYYY-MM')
ORDER BY 月份;
