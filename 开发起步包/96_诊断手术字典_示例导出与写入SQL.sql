-- =============================================================================
-- 96 诊断/手术字典：示例「导出核对」SQL + 「单行新增/单行停用」样例
-- 配套：96_临床诊断字典同步海量与HIS分析与开发步骤.md §1.0 写操作硬限制
-- 日期：2026-07-28
--
-- 硬限制（执行器必须遵守）：
--   1) 只允许：单行 INSERT；单行停用（STOP_FLAG/isstop）
--   2) 禁止：改已有业务字段；批量 UPDATE；INSERT SELECT；多行 VALUES；DELETE/DDL
--   3) 诊断医保「灰码」：海量 diagnosis_dict.ybhm = '灰码'；不写 diagnosis_contrast_dict
--
-- 连接约定：
--   [平台/PostgreSQL]  -> data_asset
--   [HIS/Oracle]       -> HIS_SOURCE（COMM）
--   [海量/Vastbase-PG] -> JHEMR_VASTBASE（database jhemr）
-- 禁止同一会话混连。
-- =============================================================================


-- #############################################################################
-- A. 平台导出：待新增诊断宽表（供人工复核；只读）
-- #############################################################################
-- [平台/PostgreSQL]
-- 说明：从字典中心拼装「院内 + 国临 + 医保」；标记灰码与是否需要对照
SELECT
    i.item_code AS local_code,
    i.item_name_cn AS local_name,
    COALESCE(i.extra->>'dict_attribute', '') AS dict_attribute,
    mn.to_item_code AS national_code,
    ni.item_name_cn AS national_name,
    mi.to_item_code AS insurance_code,
    ii.item_name_cn AS insurance_name,
    COALESCE(i.extra->>'insurance_mapping_status', '') AS insurance_mapping_status,
    CASE
        WHEN TRIM(COALESCE(mi.to_item_code, i.extra->>'insurance_raw_code', '')) = '灰码'
          OR TRIM(COALESCE(ii.item_name_cn, i.extra->>'insurance_raw_name', '')) = '灰码'
          OR COALESCE(i.extra->>'insurance_mapping_status', '') = 'source_marker_not_mapping'
        THEN 'Y'
        ELSE 'N'
    END AS is_grey_insurance,
    CASE
        WHEN TRIM(COALESCE(mi.to_item_code, i.extra->>'insurance_raw_code', '')) = '灰码'
          OR TRIM(COALESCE(ii.item_name_cn, i.extra->>'insurance_raw_name', '')) = '灰码'
          OR COALESCE(i.extra->>'insurance_mapping_status', '') = 'source_marker_not_mapping'
        THEN '灰码'   -- 下发 diagnosis_dict.ybhm
        ELSE NULL
    END AS ybhm_to_write,
    CASE
        WHEN TRIM(COALESCE(mi.to_item_code, i.extra->>'insurance_raw_code', '')) = '灰码'
          OR TRIM(COALESCE(ii.item_name_cn, i.extra->>'insurance_raw_name', '')) = '灰码'
          OR COALESCE(i.extra->>'insurance_mapping_status', '') = 'source_marker_not_mapping'
          OR TRIM(COALESCE(mi.to_item_code, '')) = ''
        THEN 'N'      -- 无有效对照：不写 diagnosis_contrast_dict
        ELSE 'Y'
    END AS write_contrast_yn,
    COALESCE(i.extra->>'special_disease_code', '') AS mtb_code,
    COALESCE(i.extra->>'special_disease_name', '') AS mtb_name,
    COALESCE(i.extra->>'low_risk_category_code', '') AS icd_low_risk_code,
    COALESCE(i.extra->>'low_risk_disease_name', '') AS icd_low_risk_name,
    COALESCE(i.extra->>'infectious_disease_name', '') AS infectious_name,
    i.status AS platform_status
FROM asset.asset_dict_medical_code_items i
LEFT JOIN asset.asset_dict_medical_code_mappings mn
  ON mn.category_code = 'diagnosis'
 AND mn.from_code_set = 'diagnosis_local_clinical'
 AND mn.from_item_code = i.item_code
 AND mn.to_code_set = 'diagnosis_national_clinical_v2'
LEFT JOIN asset.asset_dict_medical_code_items ni
  ON ni.code_set_code = 'diagnosis_national_clinical_v2'
 AND ni.item_code = mn.to_item_code
LEFT JOIN asset.asset_dict_medical_code_mappings mi
  ON mi.category_code = 'diagnosis'
 AND mi.from_code_set = 'diagnosis_local_clinical'
 AND mi.from_item_code = i.item_code
 AND mi.to_code_set = 'diagnosis_insurance_v2'
LEFT JOIN asset.asset_dict_medical_code_items ii
  ON ii.code_set_code = 'diagnosis_insurance_v2'
 AND ii.item_code = mi.to_item_code
WHERE i.code_set_code = 'diagnosis_local_clinical'
  AND i.status = 'active'
ORDER BY i.item_code
LIMIT 100;


-- #############################################################################
-- B. 平台导出：待新增手术宽表（供人工复核；只读）
-- #############################################################################
-- [平台/PostgreSQL]
SELECT
    i.item_code AS local_code,
    i.item_name_cn AS local_name,
    COALESCE(i.extra->>'dict_attribute', '') AS dict_attribute,
    COALESCE(i.extra->>'operation_level', '') AS operation_level,
    COALESCE(i.extra->>'operation_category', '') AS operation_category,
    COALESCE(i.extra->>'performance_level4_flag', '') AS level4_flag,
    COALESCE(i.extra->>'performance_minimally_invasive_flag', '') AS mini_flag,
    COALESCE(i.extra->>'restricted_tech_flag', '') AS limit_flag,
    mn.to_item_code AS national_code,
    ni.item_name_cn AS national_name,
    mi.to_item_code AS insurance_code,
    ii.item_name_cn AS insurance_name,
    CASE
        WHEN TRIM(COALESCE(mi.to_item_code, '')) = '灰码'
          OR TRIM(COALESCE(ii.item_name_cn, '')) = '灰码'
        THEN 'Y'
        ELSE 'N'
    END AS is_grey_insurance,
    CASE
        WHEN TRIM(COALESCE(mi.to_item_code, '')) = '灰码'
          OR TRIM(COALESCE(ii.item_name_cn, '')) = '灰码'
          OR TRIM(COALESCE(mi.to_item_code, '')) = ''
        THEN 'N'
        ELSE 'Y'
    END AS write_contrast_yn
FROM asset.asset_dict_medical_code_items i
LEFT JOIN asset.asset_dict_medical_code_mappings mn
  ON mn.category_code = 'operation'
 AND mn.from_code_set = 'operation_local_clinical'
 AND mn.from_item_code = i.item_code
 AND mn.to_code_set = 'operation_national_clinical_v3'
LEFT JOIN asset.asset_dict_medical_code_items ni
  ON ni.code_set_code = 'operation_national_clinical_v3'
 AND ni.item_code = mn.to_item_code
LEFT JOIN asset.asset_dict_medical_code_mappings mi
  ON mi.category_code = 'operation'
 AND mi.from_code_set = 'operation_local_clinical'
 AND mi.from_item_code = i.item_code
 AND mi.to_code_set = 'operation_insurance_v2'
LEFT JOIN asset.asset_dict_medical_code_items ii
  ON ii.code_set_code = 'operation_insurance_v2'
 AND ii.item_code = mi.to_item_code
WHERE i.code_set_code = 'operation_local_clinical'
  AND i.status = 'active'
ORDER BY i.item_code
LIMIT 100;


-- #############################################################################
-- C. [HIS/Oracle] 导出：目标库是否已存在（dry-run 用；只读）
-- #############################################################################
-- 诊断：按单个院内码查是否已存在（每次一个码；示例 I63.0011）
SELECT DIAGNOSIS_CODE, DIAGNOSIS_NAME, STOP_FLAG,
       DIAGNOSIS_CODE_GUO, DIAGNOSIS_NAME_GUO,
       MTB_FLAG, MTB_CODE, DIAGNOSIS_CODE_CRB, DIAGNOSIS_TYPE
FROM COMM.DIAGNOSIS_DICT
WHERE DIAGNOSIS_CODE = 'I63.0011'
  AND ROWNUM <= 5;

-- 手术：单码
SELECT OPERATION_CODE, OPERATION_NAME, STOP_FLAG,
       OPERATION_CODE_GB, OPERATION_NAME_GB, YB_CODE, YB_NAME,
       OPERATION_SCALE, OPERATION_INDICATOR, OPERATION_TYPE
FROM COMM.OPERATION_DICT
WHERE OPERATION_CODE = '00.7000x001L'
  AND ROWNUM <= 5;


-- #############################################################################
-- D. [海量/Vastbase-PG] 导出：目标库是否已存在（dry-run 用；只读）
-- #############################################################################
-- :hospital_no 为本院 hospital_no（阶段 0 探活确定）

SELECT diagnosis_code, diagnosis_name, hospital_no, isstop, iszdy,
       boh_diagnosis_code, ybhm, diagnosis_type, synchron
FROM jhemr.diagnosis_dict
WHERE diagnosis_code = 'I63.0011'
  AND hospital_no = :hospital_no
LIMIT 5;

-- 灰码样例（Excel 中 I63.800 医保列为灰码）：核对 ybhm
SELECT diagnosis_code, diagnosis_name, hospital_no, ybhm, isstop
FROM jhemr.diagnosis_dict
WHERE diagnosis_code = 'I63.800'
  AND hospital_no = :hospital_no
LIMIT 5;

-- 对照表：灰码不应有对照；有效医保才应有
SELECT classify, diagnosis_code, diagnosis_name,
       diagnosis_code_standard, diagnosis_name_standard
FROM jhemr.diagnosis_contrast_dict
WHERE diagnosis_code = 'I63.0011'
LIMIT 5;

SELECT clinic_diagnosis_name, diagnosis_code, hospital_no, serial_no, status
FROM jhemr.jhdict_icd_vs_clinic
WHERE diagnosis_code = 'I63.0011'
  AND hospital_no = :hospital_no
LIMIT 5;

SELECT operation_code, operation_name, hospital_no, isstop, iszdy,
       boh_operation_code, operation_scale, sjjxssbs, wcssbs, xzlbs
FROM jhemr.operation_dict
WHERE operation_code = '00.7000x001L'
  AND hospital_no = :hospital_no
LIMIT 5;

SELECT operation_code, operation_name, hospital_no, is_catalog, ybhm, isstop
FROM jhemr.operation_dict_code
WHERE operation_code = '00.7000x001'
  AND hospital_no = :hospital_no
LIMIT 5;

SELECT classify, operation_code, operation_name,
       operation_code_standard, operation_name_standard
FROM jhemr.operation_contrast_dict
WHERE operation_code = '00.7000x001L'
LIMIT 5;


-- #############################################################################
-- E. [HIS/Oracle] 单行新增（仅当 C 段查询 0 行时执行；禁止已存在时执行）
-- #############################################################################
-- 硬限制：VALUES 仅 1 行；禁止改已有行业务字段

-- E1 诊断新增（有效国临；非灰码示例 I63.0011）
INSERT INTO COMM.DIAGNOSIS_DICT (
    DIAGNOSIS_CODE,
    DIAGNOSIS_NAME,
    STD_INDICATOR,
    APPROVED_INDICATOR,
    CREATE_DATE,
    DIAG_INDICATOR,
    STOP_FLAG,
    DIAGNOSIS_CODE_GUO,
    DIAGNOSIS_NAME_GUO,
    DIAGNOSIS_TYPE
) VALUES (
    'I63.0011',
    '基底动脉血栓形成的急性脑梗死',
    1,
    1,
    SYSDATE,
    1,
    0,
    'I63.001',
    '基底动脉血栓形成脑梗死',
    '院内扩展'
);

-- E2 手术新增（单行）
INSERT INTO COMM.OPERATION_DICT (
    OPERATION_CODE,
    OPERATION_NAME,
    OPERATION_SCALE,
    STD_INDICATOR,
    APPROVED_INDICATOR,
    CREATE_DATE,
    OPERATION_INDICATOR,
    STOP_FLAG,
    OPERATION_CODE_GB,
    OPERATION_NAME_GB,
    YB_CODE,
    YB_NAME,
    FOUR_MERIT_STATUS,
    MIN_MERIT_STATUS,
    LIMIT_STATUS,
    OPERATION_TYPE
) VALUES (
    '00.7000x001L',
    '左侧髋关节假体翻修术',
    '四',
    1,
    1,
    SYSDATE,
    '0',
    0,
    '00.7000x001',
    '全髋关节假体翻修术',
    '00.7000x001',
    '全髋关节假体翻修术',
    1,
    0,
    0,
    '院内扩展'
);


-- #############################################################################
-- F. [HIS/Oracle] 单行停用（唯一允许的 UPDATE 形态；WHERE 单码）
-- #############################################################################
-- 禁止：WHERE DIAGNOSIS_CODE IN (...)；禁止改 DIAGNOSIS_NAME 等

UPDATE COMM.DIAGNOSIS_DICT
SET STOP_FLAG = 1
WHERE DIAGNOSIS_CODE = 'I63.0011'
  AND STOP_FLAG = 0;

UPDATE COMM.OPERATION_DICT
SET STOP_FLAG = 1
WHERE OPERATION_CODE = '00.7000x001L'
  AND STOP_FLAG = 0;


-- #############################################################################
-- G. [海量/Vastbase-PG] 单行新增 — 诊断
-- #############################################################################

-- G1 有效医保对照示例：diagnosis_dict（ybhm 不写灰码）
INSERT INTO jhemr.diagnosis_dict (
    diagnosis_code,
    diagnosis_name,
    std_indicator,
    approved_indicator,
    create_date,
    synchron,
    isstop,
    iszdy,
    hospital_no,
    boh_diagnosis_code,
    diagnosis_type,
    ybhm
) VALUES (
    'I63.0011',
    '基底动脉血栓形成的急性脑梗死',
    1,
    1,
    CURRENT_TIMESTAMP,
    1,
    0,
    1,
    :hospital_no,
    'I63.001',
    '院内扩展',
    NULL
);

-- G2 灰码示例（I63.800）：ybhm='灰码'；本段之后不得再 INSERT contrast
INSERT INTO jhemr.diagnosis_dict (
    diagnosis_code,
    diagnosis_name,
    std_indicator,
    approved_indicator,
    create_date,
    synchron,
    isstop,
    iszdy,
    hospital_no,
    boh_diagnosis_code,
    diagnosis_type,
    ybhm
) VALUES (
    'I63.800',
    '脑梗死，其他的',
    1,
    1,
    CURRENT_TIMESTAMP,
    1,
    0,
    1,
    :hospital_no,
    'I63.800',
    '院内扩展',
    '灰码'
);

-- G3 仅非灰码且 write_contrast_yn=Y 时：单行对照
INSERT INTO jhemr.diagnosis_contrast_dict (
    classify,
    diagnosis_code,
    diagnosis_name,
    diagnosis_code_standard,
    diagnosis_name_standard
) VALUES (
    '医保2.0',
    'I63.0011',
    '基底动脉血栓形成的急性脑梗死',
    'I63.001',
    '基底动脉血栓形成脑梗死'
);
-- 注意：I63.800 灰码 -> 禁止执行类似 INSERT 到 diagnosis_contrast_dict

-- G4 jhdict_icd_vs_clinic 单行（serial_no 由程序取 MAX+1 后绑定，禁止子查询并发写法进执行器）
INSERT INTO jhemr.jhdict_icd_vs_clinic (
    clinic_diagnosis_name,
    diagnosis_code,
    status,
    hospital_no,
    serial_no,
    diagnosis_desc
) VALUES (
    '基底动脉血栓形成的急性脑梗死',
    'I63.0011',
    0,
    :hospital_no,
    :serial_no,
    '基底动脉血栓形成脑梗死'
);


-- #############################################################################
-- H. [海量/Vastbase-PG] 单行新增 — 手术三表
-- #############################################################################

INSERT INTO jhemr.operation_dict (
    operation_code,
    operation_name,
    operation_scale,
    std_indicator,
    approved_indicator,
    create_date,
    synchron,
    isstop,
    iszdy,
    hospital_no,
    boh_operation_code,
    sjjxssbs
) VALUES (
    '00.7000x001L',
    '左侧髋关节假体翻修术',
    '四',
    1,
    1,
    CURRENT_TIMESTAMP,
    1,
    0,
    1,
    :hospital_no,
    '00.7000x001',
    '1'
);

INSERT INTO jhemr.operation_dict_code (
    operation_code,
    operation_name,
    operation_scale,
    std_indicator,
    approved_indicator,
    create_date,
    synchron,
    isstop,
    iszdy,
    hospital_no,
    is_catalog,
    boh_operation_code
) VALUES (
    '00.7000x001',
    '全髋关节假体翻修术',
    '四',
    1,
    1,
    CURRENT_TIMESTAMP,
    1,
    0,
    0,
    :hospital_no,
    1,
    '00.7000x001'
);

-- 非灰码才写对照
INSERT INTO jhemr.operation_contrast_dict (
    classify,
    operation_name,
    operation_code,
    operation_name_standard,
    operation_code_standard
) VALUES (
    '医保2.0',
    '左侧髋关节假体翻修术',
    '00.7000x001L',
    '全髋关节假体翻修术',
    '00.7000x001'
);


-- #############################################################################
-- I. [海量/Vastbase-PG] 单行停用（唯一允许的 UPDATE）
-- #############################################################################

UPDATE jhemr.diagnosis_dict
SET isstop = 1,
    last_update_date = CURRENT_TIMESTAMP
WHERE diagnosis_code = 'I63.0011'
  AND hospital_no = :hospital_no
  AND isstop = 0;

UPDATE jhemr.operation_dict
SET isstop = 1
WHERE operation_code = '00.7000x001L'
  AND hospital_no = :hospital_no
  AND isstop = 0;

UPDATE jhemr.operation_dict_code
SET isstop = 1
WHERE operation_code = '00.7000x001'
  AND hospital_no = :hospital_no
  AND isstop = 0;


-- #############################################################################
-- J. 负向示例（执行器必须拒绝 — 仅文档说明，不要执行）
-- #############################################################################
-- 禁止批量停用：
-- UPDATE COMM.DIAGNOSIS_DICT SET STOP_FLAG=1 WHERE DIAGNOSIS_CODE IN ('A','B');
-- 禁止改名：
-- UPDATE COMM.DIAGNOSIS_DICT SET DIAGNOSIS_NAME='x' WHERE DIAGNOSIS_CODE='I63.0011';
-- 禁止多行插入：
-- INSERT INTO ... VALUES (...), (...);
-- 禁止灰码写对照：
-- INSERT INTO jhemr.diagnosis_contrast_dict ... I63.800 ...

-- =============================================================================
-- 复核检查清单
-- =============================================================================
-- [ ] A/B 平台导出列是否够用（灰码 is_grey_insurance / ybhm_to_write / write_contrast_yn）
-- [ ] G2 灰码 INSERT 含 ybhm='灰码' 且无 G3 对照
-- [ ] 所有写语句均为单行；停用 WHERE 为单码 + hospital_no
-- [ ] 无业务字段 UPDATE
-- [ ] HIS / 海量 / 平台 SQL 已分库标注
-- =============================================================================
