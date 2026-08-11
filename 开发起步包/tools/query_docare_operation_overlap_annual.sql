WITH staff_raw AS (
    SELECT TRIM(u.user_id) AS raw_value, u.user_id AS person_key
    FROM MEDCOMM.MED_HIS_USERS u
    WHERE u.user_id IS NOT NULL
    UNION ALL
    SELECT TRIM(u.user_name) AS raw_value, u.user_id AS person_key
    FROM MEDCOMM.MED_HIS_USERS u
    WHERE u.user_name IS NOT NULL
),
staff_map AS (
    SELECT raw_value, MIN(person_key) AS person_key
    FROM staff_raw
    WHERE raw_value IS NOT NULL
    GROUP BY raw_value
    HAVING COUNT(DISTINCT person_key) = 1
),
base_oper AS (
    SELECT
        TO_CHAR(m.start_date_time, 'YYYY') AS stat_year,
        m.patient_id,
        m.visit_id,
        m.oper_id,
        m.start_date_time,
        m.end_date_time,
        TRIM(m.surgeon) AS surgeon_raw,
        TRIM(m.anesthesia_doctor) AS anes_1_raw,
        TRIM(m.second_anesthesia_doctor) AS anes_2_raw,
        TRIM(m.third_anesthesia_doctor) AS anes_3_raw,
        m.patient_id || '|' || TO_CHAR(m.visit_id) || '|' || TO_CHAR(m.oper_id) AS oper_key
    FROM MEDSURGERY.MED_OPERATION_MASTER m
    WHERE m.start_date_time >= TO_DATE(:start_date, 'YYYY-MM-DD')
      AND m.start_date_time < TO_DATE(:end_date, 'YYYY-MM-DD')
      AND m.visit_id > 0
      AND m.start_date_time IS NOT NULL
      AND m.end_date_time IS NOT NULL
      AND m.end_date_time > m.start_date_time
      AND m.oper_status >= 35
      AND m.cancel_date_time IS NULL
),
surgeon_assign AS (
    SELECT
        b.stat_year,
        b.oper_key,
        b.start_date_time,
        b.end_date_time,
        COALESCE(s.person_key, 'RAW:' || b.surgeon_raw) AS person_key
    FROM base_oper b
    LEFT JOIN staff_map s ON s.raw_value = b.surgeon_raw
    WHERE b.surgeon_raw IS NOT NULL
),
anes_raw AS (
    SELECT stat_year, oper_key, start_date_time, end_date_time, anes_1_raw AS raw_value
    FROM base_oper
    WHERE anes_1_raw IS NOT NULL
    UNION ALL
    SELECT stat_year, oper_key, start_date_time, end_date_time, anes_2_raw AS raw_value
    FROM base_oper
    WHERE anes_2_raw IS NOT NULL
    UNION ALL
    SELECT stat_year, oper_key, start_date_time, end_date_time, anes_3_raw AS raw_value
    FROM base_oper
    WHERE anes_3_raw IS NOT NULL
),
anes_assign AS (
    SELECT DISTINCT
        a.stat_year,
        a.oper_key,
        a.start_date_time,
        a.end_date_time,
        COALESCE(s.person_key, 'RAW:' || a.raw_value) AS person_key
    FROM anes_raw a
    LEFT JOIN staff_map s ON s.raw_value = a.raw_value
),
surgeon_overlap AS (
    SELECT DISTINCT b.stat_year, b.oper_key
    FROM surgeon_assign b
    WHERE EXISTS (
        SELECT 1
        FROM surgeon_assign a
        WHERE a.stat_year = b.stat_year
          AND a.person_key = b.person_key
          AND a.oper_key <> b.oper_key
          AND (
              a.start_date_time < b.start_date_time
              OR (a.start_date_time = b.start_date_time AND a.oper_key < b.oper_key)
          )
          AND b.start_date_time < a.end_date_time
    )
),
anes_overlap AS (
    SELECT DISTINCT b.stat_year, b.oper_key
    FROM anes_assign b
    WHERE EXISTS (
        SELECT 1
        FROM anes_assign a
        WHERE a.stat_year = b.stat_year
          AND a.person_key = b.person_key
          AND a.oper_key <> b.oper_key
          AND (
              a.start_date_time < b.start_date_time
              OR (a.start_date_time = b.start_date_time AND a.oper_key < b.oper_key)
          )
          AND b.start_date_time < a.end_date_time
    )
),
denom AS (
    SELECT stat_year, COUNT(*) AS total_oper_count
    FROM base_oper
    GROUP BY stat_year
),
surgeon_num AS (
    SELECT stat_year, COUNT(*) AS surgeon_overlap_count
    FROM surgeon_overlap
    GROUP BY stat_year
),
anes_num AS (
    SELECT stat_year, COUNT(*) AS anes_overlap_count
    FROM anes_overlap
    GROUP BY stat_year
)
SELECT
    d.stat_year,
    d.total_oper_count,
    NVL(s.surgeon_overlap_count, 0) AS surgeon_overlap_count,
    ROUND(NVL(s.surgeon_overlap_count, 0) * 100 / d.total_oper_count, 4) AS surgeon_overlap_rate,
    NVL(a.anes_overlap_count, 0) AS anes_overlap_count,
    ROUND(NVL(a.anes_overlap_count, 0) * 100 / d.total_oper_count, 4) AS anes_overlap_rate
FROM denom d
LEFT JOIN surgeon_num s ON s.stat_year = d.stat_year
LEFT JOIN anes_num a ON a.stat_year = d.stat_year
ORDER BY d.stat_year
