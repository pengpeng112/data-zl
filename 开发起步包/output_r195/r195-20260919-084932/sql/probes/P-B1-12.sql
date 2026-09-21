-- probe P-B1-12 | ods_8_216 | oracle11g
-- question: CDA schema 是否有 T_JBJL；草稿引用是否有效
-- scope: 数据字典
-- note: 
SELECT OWNER, OBJECT_NAME, OBJECT_TYPE FROM ALL_OBJECTS WHERE OBJECT_NAME = 'T_JBJL'
