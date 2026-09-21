-- probe P-B1-04 | ods_8_216 | oracle11g
-- question: 同一字典名称+院内编码是否存在多映射（多映射会导致 JOIN 放大）
-- scope: 字典全表（小表）
-- note: 列名以平台当前元数据为准执行前核对（历史称谓可能为 字典名称/院内编码）
SELECT 字典名称_col, 院内编码_col, COUNT(*) n
FROM (SELECT DICT_NAME 字典名称_col, HOSPITAL_CODE 院内编码_col FROM CDA.CDA_DICTIONARY)
GROUP BY 字典名称_col, 院内编码_col HAVING COUNT(*) > 1
