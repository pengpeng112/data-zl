-- r197 S7 生产入库 | 单事务执行: psql -1 -v ON_ERROR_STOP=1
-- run_id=r197-20260921-s1 | payload SHA-256 前16: 690a0a7b10e68224 | 2026-09-21 用户批准

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$CLASS_ON_RECKONING$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.RECK_ITEM_CLASS_DICT$r197$, $r197$CLASS_CODE$r197$, $r197$d.class_on_reckoning = r.class_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：INP_BILL_DETAIL:N → RECK_ITEM_CLASS_DICT:1; 条件：【值域待确认】PERFORMED_BY = ×3；【值域待确认】CLASS_ON_RECKONING = ×2；【值域待确认】WARDCODE = ×2；【值域待确认】CLASS_NAME LIKE ×1；【值域待确认】PERFORMED_BY LIKE ×1；【值域待确认】OPERATOR_NO = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-3EC0DE462A", "stage": "S2", "statements": 111, "templates": 106, "files": ["2023.6-7神经外手术材料费使用明细.txt", "3个科室4月份每名患者的手术材料物料使用明细（包括姓名住院号耗材名称数量价格）.txt", "z住院材料费.txt", "中医科中草药开单收入.txt", "医生.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLASS_ON_RECKONING$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.RECK_ITEM_CLASS_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLASS_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$PATIENT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.PAT_MASTER_INDEX$r197$, $r197$PATIENT_ID$r197$, $r197$d.patient_id = p.patient_id$r197$, $r197$197历史SQL摄入候选（partial；验证：passed_in_scope）$r197$, $r197$粒度：患者级; 基数：INP_BILL_DETAIL:N → PAT_MASTER_INDEX:1; 条件：【值域待确认】CLASS_ON_RECKONING = ×2；【值域待确认】OPERATOR_NO <> ×2；【值域待确认】BED_NO > ×2；【值域待确认】BED_NO < ×2；【值域待确认】SUBJ_CODE = ×1；【值域待确认】CLASS_NAME LIKE ×1；【值域待确认】PERFORMED_BY = ×1；【值域待确认】DEPT_NAME LIKE ×1；【值域待确认】DEPT_NAME = ×1; 风险：half_key$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-C90B6003D8", "stage": "S2", "statements": 64, "templates": 62, "files": ["2022春节期间耳鼻喉开单手术费明细.txt", "2023.6-7神经外手术材料费使用明细.txt", "3个科室4月份每名患者的手术材料物料使用明细（包括姓名住院号耗材名称数量价格）.txt", "住院门诊费用明细消化内镜中心.txt", "使用“一次性等离子刀头门诊及住院患者的信息：门诊及住院患者的姓名、性别、年龄、ID住院号、联系电话、住址.txt"], "intake_state": "partial", "validation_state": "passed_in_scope", "validation_note": "PAT_MASTER_INDEX.PATIENT_ID 唯一，行级 N:1 成立；visit 口径聚合需回 PAT_VISIT（Q02/Q07 侧证）", "probe_uids": ["Q02"], "risk_tags": ["half_key"], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.PAT_MASTER_INDEX$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$CLASS_ON_RECKONING$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.RECK_ITEM_CLASS_DICT$r197$, $r197$CLASS_CODE$r197$, $r197$e.class_code = t.class_on_reckoning$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：OUTP_BILL_ITEMS:N → RECK_ITEM_CLASS_DICT:1; 条件：【值域待确认】PERFORMED_BY LIKE ×1；【值域待确认】CLASS_ON_RECKONING = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-82947C72C9", "stage": "S2", "statements": 30, "templates": 29, "files": ["小卢sql\\财务科数据.sql", "执行科室为血液净化护理单元的开单科室收费情况.txt", "执行科室为：眩晕疾病科，临床听力学中心，听觉电生理研究室，助听与听力康复中心不同核算分类下的金额.txt", "病理医保飞检数据提取.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLASS_ON_RECKONING$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.RECK_ITEM_CLASS_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLASS_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$VISIT_DATE+VISIT_NO$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_TREAT_REC$r197$, $r197$VISIT_DATE+VISIT_NO$r197$, $r197$CLINIC_MASTER.VISIT_DATE = OUTP_TREAT_REC.VISIT_DATE AND CLINIC_MASTER.VISIT_NO = OUTP_TREAT_REC.VISIT_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：门诊挂号级; 基数：OUTP_TREAT_REC:N → CLINIC_MASTER:1（按 VISIT_DATE+VISIT_NO）; 条件：【值域待确认】EXAM_CLASS = ×24；ITEM_NAME LIKE ×1（值域已确认：免疫组织化学染色诊断,免疫组织化学染色诊断（液盖膜涡流混匀法加收））；【值域待确认】CHARGE_INDICATOR = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-190AFAC505", "stage": "S2", "statements": 27, "templates": 11, "files": ["发展运营部：月初上报指标.txt"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "CLINIC 侧 (VISIT_DATE,VISIT_NO) 唯一（Q03）；SERIAL_NO 单列 0.6% 复用（Q11）", "probe_uids": ["Q03", "Q11"], "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OUTP_TREAT_REC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$SUBJ_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.TALLY_SUBJECT_DICT$r197$, $r197$SUBJ_CODE$r197$, $r197$A.SUBJ_CODE = B.SUBJ_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：OUTP_BILL_ITEMS:N → TALLY_SUBJECT_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-891B95F49D", "stage": "S2", "statements": 11, "templates": 10, "files": ["小卢sql\\药品进销存.sql", "小卢sql\\财务科数据.sql", "小孙遗产\\药品库存.sql", "小王sql记录\\月底药库20240307 最终版.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$SUBJ_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.TALLY_SUBJECT_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$SUBJ_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$SUBJ_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.TALLY_SUBJECT_DICT$r197$, $r197$SUBJ_CODE$r197$, $r197$INP_BILL_DETAIL.SUBJ_CODE = TALLY_SUBJECT_DICT.SUBJ_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：INP_BILL_DETAIL:N → TALLY_SUBJECT_DICT:1; 条件：【值域待确认】OPERATION_NO = ×2; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-678B3B21E2", "stage": "S2", "statements": 9, "templates": 7, "files": ["小卢sql\\药品进销存.sql", "小卢sql\\财务科数据.sql", "小孙遗产\\药品库存.sql", "小王sql记录\\药库取数sql20240201.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$SUBJ_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.TALLY_SUBJECT_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$SUBJ_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DOCTOR_GROUP$r197$, $r197$DOCTOR_USER$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$DOCTOR_USER$r197$, $r197$dg.doctor_user = t.doctor_user$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：INP_BILL_DETAIL:N → DOCTOR_GROUP:1; 条件：【值域待确认】CLASS_ON_RECKONING = ×2; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-C77ABA45F2", "stage": "S2", "statements": 7, "templates": 7, "files": ["绩效办提取语句\\提取语句\\1-每月第一波数据提取\\介入工作量分类汇总（含术者，开单医生所在科室）.txt", "绩效办提取语句\\提取语句\\3-节假日数据提取\\1-新入院病人收入明细  汇总.txt", "绩效办提取语句\\提取语句\\3-节假日数据提取\\10-按四个手术室及介入科、产房所报手术名单提取产生的收入明细中的手术费、麻醉费、治疗费、其他治疗费明细.txt", "绩效办提取语句\\提取语句\\3-节假日数据提取\\5-耳鼻喉住院开单报表中的手术费  明细.txt", "绩效办提取语句\\提取语句\\3-节假日数据提取\\9-按四个手术室及介入科所报手术名单提取产生的收入明细.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DOCTOR_GROUP$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DOCTOR_USER$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DOCTOR_USER$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$CLINIC_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_ORDER_DESC$r197$, $r197$CLINIC_NO$r197$, $r197$b.clinic_no = c.clinic_no$r197$, $r197$197历史SQL摄入候选（partial；验证：passed_in_scope）$r197$, $r197$粒度：门诊挂号级; 基数：OUTP_ORDER_DESC:N → CLINIC_MASTER:1（按 CLINIC_NO）; 条件：【值域待确认】CLINIC_LABEL LIKE ×3；【值域待确认】SPECIALIZED = ×3; 风险：half_key$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-BDCE2A3160", "stage": "S2", "statements": 6, "templates": 5, "files": ["A_F0138::SQL\\2022年02月 8-13.sql", "A_F0138::SQL\\2023年01月 09-15.sql", "病理医保飞检数据提取.txt"], "intake_state": "partial", "validation_state": "passed_in_scope", "validation_note": "CLINIC_NO 近窗唯一，单列在本窗可用（Q03）", "probe_uids": ["Q03"], "risk_tags": ["half_key"], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLINIC_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_ORDER_DESC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLINIC_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.CONSULTATION_DOCTOR_DETAIL$r197$, $r197$CONSULTATION_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.CONSULTATION_DOCTOR_MASTER$r197$, $r197$CONSULTATION_ID$r197$, $r197$m.consultation_id = d.consultation_id$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-4A1529052D", "stage": "S2", "statements": 5, "templates": 5, "files": ["A_F0138::SQL\\2022年07月 25-31.sql", "会诊数据.txt", "绩效办提取语句\\提取语句\\常用其他提取\\会诊信息.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$ORDADM.CONSULTATION_DOCTOR_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CONSULTATION_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.CONSULTATION_DOCTOR_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CONSULTATION_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.MARITAL_STATUS_DICT$r197$, $r197$MARITAL_STATUS_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.PAT_MASTER_INDEX$r197$, $r197$MARITAL_STATUS$r197$, $r197$ms.marital_status_code =  p.marital_status$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：PAT_MASTER_INDEX:N → MARITAL_STATUS_DICT:1; 条件：DIAGNOSIS_TYPE = ×3（值域已确认：1,2,3,7）；【值域待确认】DIAGNOSIS_NO = ×3; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-C0E9E1112A", "stage": "S2", "statements": 5, "templates": 3, "files": ["心内科随访数据.txt", "糖尿病数据提取\\提取语句\\住院病人信息.txt", "糖尿病数据提取\\提取语句\\门诊病人信息.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.MARITAL_STATUS_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$MARITAL_STATUS_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.PAT_MASTER_INDEX$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$MARITAL_STATUS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$OPERATOR_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.STAFF_DICT$r197$, $r197$ID$r197$, $r197$a.operator_no=b.id$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度（含停用/重用代码风险）; 基数：INP_BILL_DETAIL:N → STAFF_DICT:1; 条件：【值域待确认】EMP_NO = ×2；【值域待确认】OPERATOR_NO <> ×2；【值域待确认】BED_NO > ×2；【值域待确认】BED_NO < ×2; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-447C413169", "stage": "S2", "statements": 4, "templates": 3, "files": ["A_F0526::护理项目（病房、门诊、急诊转费、保健病房、产房、内镜）\\耳鼻喉保健病房工作量提取sql.txt", "人事科职称数据提取sql(1).txt", "绩效办提取语句\\提取语句\\1-每月第一波数据提取\\护理项目（病房、门诊、急诊转费、保健病房、产房、内镜）\\耳鼻喉保健病房工作量提取sql.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$OPERATOR_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.STAFF_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_ORDERS$r197$, $r197$VISIT_DATE+VISIT_NO+SERIAL_NO$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_TREAT_REC$r197$, $r197$VISIT_DATE+VISIT_NO+SERIAL_NO$r197$, $r197$OUTP_ORDERS.VISIT_DATE = OUTP_TREAT_REC.VISIT_DATE AND OUTP_ORDERS.VISIT_NO = OUTP_TREAT_REC.VISIT_NO AND OUTP_ORDERS.SERIAL_NO = OUTP_TREAT_REC.SERIAL_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-DB7BD1C6F6", "stage": "S2", "statements": 4, "templates": 1, "files": ["小卢sql\\检验科费用项目.sql"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "三列键 SERIAL_NO 组 0.6% 复用（Q11，量级可忽略但非零）", "probe_uids": ["Q11"], "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$HIS.OUTP_ORDERS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO+SERIAL_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OUTP_TREAT_REC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO+SERIAL_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.NATION_DICT$r197$, $r197$NATION_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.PAT_MASTER_INDEX$r197$, $r197$NATION$r197$, $r197$nation_dict.nation_code = p.nation$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：PAT_MASTER_INDEX:N → NATION_DICT:1; 条件：【值域待确认】REPORT_ITEM_NAME LIKE ×16；DIAGNOSIS_TYPE = ×4（值域已确认：1,2,3,7）；【值域待确认】DIAGNOSIS_NO = ×4；【值域待确认】DIAGNOSIS_DESC LIKE ×4；【值域待确认】DIAG_DESC LIKE ×4; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-00E1F5934D", "stage": "S2", "statements": 4, "templates": 2, "files": ["糖尿病数据提取\\提取语句\\住院病人信息.txt", "糖尿病数据提取\\提取语句\\门诊病人信息.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.NATION_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$NATION_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.PAT_MASTER_INDEX$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$NATION$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.OPERATION$r197$, $r197$PATIENT_ID+VISIT_ID+OPERATION_NO$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OPERATION_MASTER$r197$, $r197$PATIENT_ID+VISIT_ID+OPER_ID$r197$, $r197$om.patient_id = o.patient_id AND om.visit_id = o.visit_id AND om.oper_id = o.operation_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：DIAGNOSIS_TYPE = ×1（值域已确认：1,2,3,7）; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-5B7458DD64", "stage": "S2", "statements": 3, "templates": 3, "files": ["111111111.sql", "2020.1-3头颈外科和嗓音疾病科手术数据.txt", "鼻科住院手术数据.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$MEDREC.OPERATION$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+OPERATION_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OPERATION_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+OPER_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_MR_DIAG_DESC$r197$, $r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$, $r197$a.patient_id=b.patient_id AND a.visit_date=b.visit_date AND a.visit_no=b.visit_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：门诊挂号级; 基数：OUTP_MR_DIAG_DESC:N → CLINIC_MASTER:1（按 PATIENT_ID+VISIT_DATE+VISIT_NO）; 条件：【值域待确认】VISIT_DEPT = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-50040F7BC3", "stage": "S2", "statements": 3, "templates": 3, "files": ["创建表及导库.sql", "医疗部三甲评审指标.txt", "医疗部数据指标提取.txt"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "CLINIC 侧三列键唯一（Q03）；子表侧单列 VISIT_NO 38% 重复须用三列（Q10）", "probe_uids": ["Q03", "Q10"], "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OUTP_MR_DIAG_DESC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$LAB.LAB_TEST_MASTER$r197$, $r197$TEST_NO$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_TREAT_REC$r197$, $r197$APPOINT_NO$r197$, $r197$a.test_no = s.appoint_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ITEM_CODE = ×2；【值域待确认】PERFORMED_BY = ×1；【值域待确认】CHARGE_ITEM_CODE LIKE ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-5CB74852EF", "stage": "S2", "statements": 3, "templates": 3, "files": ["创建表及导库.sql", "病理医保飞检数据提取.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$LAB.LAB_TEST_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$TEST_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OUTP_TREAT_REC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$APPOINT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$PATIENT_ID+CLINIC_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_ORDER_DESC$r197$, $r197$PATIENT_ID+CLINIC_NO$r197$, $r197$ood.patient_id = c.patient_id AND ood.clinic_no = c.clinic_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：门诊挂号级; 基数：OUTP_ORDER_DESC:N → CLINIC_MASTER:1（按 PATIENT_ID+CLINIC_NO）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-E256C47346", "stage": "S2", "statements": 3, "templates": 3, "files": ["医疗部数据指标提取.txt", "药学部三级医院评审指标数据需要提取相关内容.txt", "门诊工作量按病人明细.txt"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "CLINIC_NO 唯一（Q03）", "probe_uids": ["Q03"], "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+CLINIC_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_ORDER_DESC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+CLINIC_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$VISIT_DATE+VISIT_NO+CLINIC_LABEL+VISIT_TIME_DESC$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_RETURNED_ACCT$r197$, $r197$VISIT_DATE+VISIT_NO+CLINIC_LABEL+TIME_DESC$r197$, $r197$A.VISIT_DATE = B.VISIT_DATE AND A.VISIT_NO = B.VISIT_NO AND A.CLINIC_LABEL = B.CLINIC_LABEL AND A.VISIT_TIME_DESC = B.TIME_DESC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：门诊挂号级; 基数：CLINIC_RETURNED_ACCT:N → CLINIC_MASTER:1（按 VISIT_DATE+VISIT_NO+CLINIC_LABEL+VISIT_TIME_DESC）; 条件：【值域待确认】DEPT_NAME LIKE ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-6B88D353D7", "stage": "S2", "statements": 3, "templates": 2, "files": ["A_F0138::SQL\\2022年08月 01-07.sql", "小王sql记录\\门诊开单费用明细.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO+CLINIC_LABEL+VISIT_TIME_DESC$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPADM.CLINIC_RETURNED_ACCT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO+CLINIC_LABEL+TIME_DESC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.PATS_IN_HOSPITAL$r197$, $r197$PATIENT_ID$r197$, $r197$ORDERS.PATIENT_ID = PATS_IN_HOSPITAL.PATIENT_ID$r197$, $r197$197历史SQL摄入候选（partial；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ORDER_STATUS = ×9；【值域待确认】REPEAT_INDICATOR = ×6；【值域待确认】ORDER_CLASS = ×1；【值域待确认】ORDER_CLASS <> ×1; 风险：half_key$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-2C9FE1D3B6", "stage": "S2", "statements": 3, "templates": 3, "files": ["A_F0138::SQL\\2022年03月 21-27.sql", "A_F0138::SQL\\2022年03月 28-03.sql", "A_F0138::SQL\\2022年08月 01-07.sql"], "intake_state": "partial", "validation_state": "passed_in_scope", "validation_note": "在院表 PATIENT_ID 唯一（Q04），行级成立", "probe_uids": ["Q04"], "risk_tags": ["half_key"], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$INPADM.PATS_IN_HOSPITAL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.BED_REC$r197$, $r197$WARD_CODE+BED_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.PATS_IN_HOSPITAL$r197$, $r197$WARD_CODE+BED_NO$r197$, $r197$AA.WARD_CODE = PATS_IN_HOSPITAL.WARD_CODE AND BED_REC.BED_NO = PATS_IN_HOSPITAL.BED_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-86227FC71B", "stage": "S2", "statements": 3, "templates": 3, "files": ["A_F0138::SQL\\2022年05月 23-29.sql", "A_F0138::SQL\\2022年08月 22-28.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPADM.BED_REC$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$WARD_CODE+BED_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$INPADM.PATS_IN_HOSPITAL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$WARD_CODE+BED_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.MR_ON_LINE$r197$, $r197$VISIT_ID+PATIENT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.PATS_IN_HOSPITAL$r197$, $r197$VISIT_ID+PATIENT_ID$r197$, $r197$PATS_IN_HOSPITAL.VISIT_ID = MR_ON_LINE.VISIT_ID AND PATS_IN_HOSPITAL.PATIENT_ID = MR_ON_LINE.PATIENT_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】REQUEST_DOCTOR_ID = ×3；【值域待确认】LEND_INDICATOR = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-FB7AC774E3", "stage": "S2", "statements": 3, "templates": 3, "files": ["A_F0138::SQL\\2022年05月 23-29.sql", "A_F0138::SQL\\2022年08月 22-28.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$MEDREC.MR_ON_LINE$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$VISIT_ID+PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$INPADM.PATS_IN_HOSPITAL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$VISIT_ID+PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.PAT_VISIT$r197$, $r197$DEPT_ADMISSION_TO+CONSULTING_DOCTOR$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.WAIT_BED_PATS_NEW$r197$, $r197$DEPT_WAITING_FOR+USER_NAME$r197$, $r197$a.dept_waiting_for = d.dept_admission_to AND a.user_name = d.consulting_doctor$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：患者级（缺 VISIT_ID，半键疑点）; 基数：WAIT_BED_PATS_NEW:N → PAT_VISIT:1（按 DEPT_ADMISSION_TO+CONSULTING_DOCTOR）; 条件：; 风险：name_join_high_risk,semantic_suspect; CONSULTING_DOCTOR(工号?)=USER_NAME(用户名?) 跨域等值，高风险$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-7034281A87", "stage": "S2", "statements": 2, "templates": 1, "files": ["入院患者就诊大杨门诊sql.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["name_join_high_risk", "semantic_suspect"], "notes": "CONSULTING_DOCTOR(工号?)=USER_NAME(用户名?) 跨域等值，高风险"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$MEDREC.PAT_VISIT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DEPT_ADMISSION_TO+CONSULTING_DOCTOR$r197$,'')
    AND upper(r.to_table)=upper($r197$INPADM.WAIT_BED_PATS_NEW$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DEPT_WAITING_FOR+USER_NAME$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.BILL_ITEM_CLASS_DICT$r197$, $r197$CLASS_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$ITEM_CLASS$r197$, $r197$r.class_code = a.item_class$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：INP_BILL_DETAIL:N → BILL_ITEM_CLASS_DICT:1; 条件：【值域待确认】TRANSACT_TYPE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-CAC61346F1", "stage": "S2", "statements": 2, "templates": 2, "files": ["创建表及导库.sql", "病理医保飞检数据提取.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.BILL_ITEM_CLASS_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLASS_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CLASS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_SETTLE_MASTER_YB$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.SETTLE_ZY_REC$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$S.PATIENT_ID = ismy.PATIENT_ID AND S.VISIT_ID = ismy.VISIT_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-F9B9C57BF3", "stage": "S2", "statements": 2, "templates": 1, "files": ["医保结算人员信息.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_SETTLE_MASTER_YB$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.SETTLE_ZY_REC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$VISIT_DATE+VISIT_NO$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_MR$r197$, $r197$VISIT_DATE+VISIT_NO$r197$, $r197$a.visit_date = b.visit_date AND a.visit_no = b.visit_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：门诊挂号级; 基数：OUTP_MR:N → CLINIC_MASTER:1（按 VISIT_DATE+VISIT_NO）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-B5154A7469", "stage": "S2", "statements": 2, "templates": 2, "files": ["A_F0138::SQL\\2022年09月 26-02.sql", "取门诊诊断人数.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OUTP_MR$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_RCPT_MASTER$r197$, $r197$OPERATOR_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.STAFF_DICT$r197$, $r197$ID$r197$, $r197$t.operator_no = sd.id$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度（含停用/重用代码风险）; 基数：OUTP_RCPT_MASTER:N → STAFF_DICT:1; 条件：【值域待确认】CHARGE_INDICATOR = ×2; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-D3EDFB4370", "stage": "S2", "statements": 2, "templates": 1, "files": ["常用\\结算中心：山东省改善医疗服务监测系统.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPBILL.OUTP_RCPT_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$OPERATOR_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.STAFF_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_INDEX$r197$, $r197$CLINIC_LABEL$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$CLINIC_LABEL$r197$, $r197$cm.clinic_label = ci.clinic_label$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：门诊挂号级; 基数：CLINIC_INDEX:N → CLINIC_MASTER:1（按 CLINIC_LABEL）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-FD2673AB7B", "stage": "S2", "statements": 2, "templates": 2, "files": ["A_F0138::SQL\\2022年05月 09-15.sql", "按号别提取门诊科室工作量.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_INDEX$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLINIC_LABEL$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLINIC_LABEL$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_MR$r197$, $r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$, $r197$om.patient_id = cm.patient_id AND om.visit_date = cm.visit_date AND om.visit_no = cm.visit_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：门诊挂号级; 基数：OUTP_MR:N → CLINIC_MASTER:1（按 PATIENT_ID+VISIT_DATE+VISIT_NO）; 条件：【值域待确认】DIAG_DESC LIKE ×3; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-D89F991E47", "stage": "S2", "statements": 2, "templates": 2, "files": ["按诊断和年龄范围提取1岁以下病人信息.txt", "鼻科门诊随访.txt"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "三列键唯一（Q03）", "probe_uids": ["Q03"], "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OUTP_MR$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PATIENT_CLASS_DICT$r197$, $r197$PATIENT_CLASS_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.PAT_VISIT$r197$, $r197$PATIENT_CLASS$r197$, $r197$patient_class_dict.patient_class_code = v.patient_class$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：PAT_VISIT:N → PATIENT_CLASS_DICT:1; 条件：【值域待确认】REPORT_ITEM_NAME LIKE ×8；DIAGNOSIS_TYPE = ×4（值域已确认：1,2,3,7）；【值域待确认】DIAGNOSIS_NO = ×4；【值域待确认】DIAGNOSIS_DESC LIKE ×4; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-A5790F6F3E", "stage": "S2", "statements": 2, "templates": 1, "files": ["糖尿病数据提取\\提取语句\\住院登记.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.PATIENT_CLASS_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_CLASS_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.PAT_VISIT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_CLASS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$ITEM_CLASS$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.ORDER_CLASS_DICT$r197$, $r197$ORDER_CLASS_CODE$r197$, $r197$order_class_dict.order_class_code = ibd.item_class$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：INP_BILL_DETAIL:N → ORDER_CLASS_DICT:1; 条件：【值域待确认】REPORT_ITEM_NAME LIKE ×8；DIAGNOSIS_TYPE = ×4（值域已确认：1,2,3,7）；【值域待确认】DIAGNOSIS_NO = ×4；【值域待确认】DIAGNOSIS_DESC LIKE ×4; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-7F2DBC5ADB", "stage": "S2", "statements": 2, "templates": 1, "files": ["糖尿病数据提取\\提取语句\\住院费用.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CLASS$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.ORDER_CLASS_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ORDER_CLASS_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$ITEM_CODE$r197$, $r197$drug_price_list.drug_code = obi.item_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：OUTP_BILL_ITEMS:N → DRUG_PRICE_LIST:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-802768F217", "stage": "S2", "statements": 2, "templates": 1, "files": ["糖尿病数据提取\\提取语句\\门诊费用.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.BILL_ITEM_CLASS_DICT$r197$, $r197$CLASS_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$ITEM_CLASS$r197$, $r197$obi.item_class = bi.class_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：OUTP_BILL_ITEMS:N → BILL_ITEM_CLASS_DICT:1; 条件：【值域待确认】REPORT_ITEM_NAME LIKE ×8；【值域待确认】DIAG_DESC LIKE ×4; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-7D4F63EBE3", "stage": "S2", "statements": 2, "templates": 1, "files": ["糖尿病数据提取\\提取语句\\门诊费用.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.BILL_ITEM_CLASS_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLASS_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CLASS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_ORDER_DESC$r197$, $r197$PATIENT_ID+ORDERED_BY_DEPT$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.WAIT_BED_PATS_NEW$r197$, $r197$PATIENT_ID+CLINIC_DEPT$r197$, $r197$ood.patient_id = wb.patient_id AND ood.ordered_by_dept = wb.clinic_dept$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-16574BB093", "stage": "S2", "statements": 2, "templates": 2, "files": ["绩效办提取语句\\提取语句\\常用其他提取\\急诊工作量.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPBILL.OUTP_ORDER_DESC$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+ORDERED_BY_DEPT$r197$,'')
    AND upper(r.to_table)=upper($r197$INPADM.WAIT_BED_PATS_NEW$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+CLINIC_DEPT$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.PATS_IN_HOSPITAL$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$C.PATIENT_ID = A.PATIENT_ID AND C.VISIT_ID = A.VISIT_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】REPEAT_INDICATOR = ×2；【值域待确认】PATIENT_ID = ×1；【值域待确认】ORDER_STATUS = ×1；【值域待确认】WARD_CODE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-1A98B5707E", "stage": "S2", "statements": 2, "templates": 2, "files": ["A_F0138::SQL\\2022年03月 14-20.sql", "A_F0138::SQL\\2022年12月 26-31.sql"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "ORDERS↔PATS_IN_HOSPITAL 组合键；在院表 PATIENT_ID 唯一（Q04）", "probe_uids": ["Q02", "Q04"], "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$INPADM.PATS_IN_HOSPITAL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.MEDICAL_CARD_MEMO$r197$, $r197$CARD_TYPE$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.MEDICAL_CARD_TYPE_DICT$r197$, $r197$TYPE_CODE$r197$, $r197$A.CARD_TYPE = B.TYPE_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：MEDICAL_CARD_MEMO:N → MEDICAL_CARD_TYPE_DICT:1; 条件：【值域待确认】ACCOUNT_STATUS = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-F909187A90", "stage": "S2", "statements": 2, "templates": 2, "files": ["A_F0138::SQL\\2022年08月 22-28.sql", "A_F0138::SQL\\2022年12月 05-11.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$MEDREC.MEDICAL_CARD_MEMO$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CARD_TYPE$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.MEDICAL_CARD_TYPE_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$TYPE_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DEPT_DICT$r197$, $r197$DEPT_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DEPT_VS_WARD$r197$, $r197$WARD_CODE$r197$, $r197$v.ward_code=c.dept_code$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：semantic_suspect; 病区码≠科室码：DEPT_VS_WARD 同时含 DEPT_CODE 与 WARD_CODE 两列，JOIN 走 WARD_CODE 语义存疑（可能是历史错误或刻意按病区计数）$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-78EA534A94", "stage": "S2", "statements": 1, "templates": 1, "files": ["sql.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["semantic_suspect"], "notes": "病区码≠科室码：DEPT_VS_WARD 同时含 DEPT_CODE 与 WARD_CODE 两列，JOIN 走 WARD_CODE 语义存疑（可能是历史错误或刻意按病区计数）"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DEPT_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DEPT_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.DEPT_VS_WARD$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$WARD_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_MR_DIAG_DESC$r197$, $r197$VISIT_DATE+VISIT_NO$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_TREAT_REC$r197$, $r197$VISIT_DATE+VISIT_NO$r197$, $r197$aa.visit_date = bb.visit_date AND aa.visit_no = bb.visit_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】VISIT_ID > ×1；【值域待确认】DIAG_DESC LIKE ×1；ITEM_NAME LIKE ×1（值域已确认：免疫组织化学染色诊断,免疫组织化学染色诊断（液盖膜涡流混匀法加收））; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-A70D3EBC14", "stage": "S2", "statements": 1, "templates": 1, "files": ["产科甲功.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$HIS.OUTP_MR_DIAG_DESC$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OUTP_TREAT_REC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$VISIT_DATE+PATIENT_ID$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_MR_DIAG_DESC$r197$, $r197$VISIT_DATE+PATIENT_ID$r197$, $r197$cm.visit_date = omd.visit_date AND cm.patient_id = omd.patient_id$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：门诊挂号级; 基数：OUTP_MR_DIAG_DESC:N → CLINIC_MASTER:1（按 VISIT_DATE+PATIENT_ID）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-55ACB4FC9A", "stage": "S2", "statements": 1, "templates": 1, "files": ["公卫上报指标.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$VISIT_DATE+PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OUTP_MR_DIAG_DESC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$VISIT_DATE+PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_PAYMENTS_MONEY$r197$, $r197$RCPT_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_SETTLE_MASTER$r197$, $r197$RCPT_NO$r197$, $r197$ipm.rcpt_no = ism.rcpt_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】TRANSACT_TYPE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-54DDF3090C", "stage": "S2", "statements": 1, "templates": 1, "files": ["国家医保局数据筛查.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_PAYMENTS_MONEY$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$RCPT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.INP_SETTLE_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$RCPT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$RCPT_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_SETTLE_MASTER$r197$, $r197$RCPT_NO$r197$, $r197$ibd.rcpt_no = ism.rcpt_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-836F2A5926", "stage": "S2", "statements": 1, "templates": 1, "files": ["国家医保局数据筛查.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$RCPT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.INP_SETTLE_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$RCPT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$VISIT_DATE+VISIT_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_PAYMENTS_MONEY$r197$, $r197$VISIT_DATE+VISIT_NO$r197$, $r197$CLINIC_MASTER.VISIT_DATE = CLINIC_PAYMENTS_MONEY.VISIT_DATE AND CLINIC_MASTER.VISIT_NO =CLINIC_PAYMENTS_MONEY.VISIT_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：门诊挂号级; 基数：CLINIC_PAYMENTS_MONEY:N → CLINIC_MASTER:1（按 VISIT_DATE+VISIT_NO）; 条件：【值域待确认】PATIENT_ID = ×1；【值域待确认】MONEY_TYPE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-11CEA3F43C", "stage": "S2", "statements": 1, "templates": 1, "files": ["小孙遗产\\账不平(3).sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPADM.CLINIC_PAYMENTS_MONEY$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$VISIT_DATE+VISIT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_VS_CHARGE$r197$, $r197$CHARGE_ITEM_CODE+CHARGE_ITEM_CLASS$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$ITEM_CODE+ITEM_CLASS$r197$, $r197$cc.charge_item_code = l.item_code AND cc.charge_item_class = l.item_class$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-80190A1266", "stage": "S2", "statements": 1, "templates": 1, "files": ["按处置表取计价项目.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.CLINIC_VS_CHARGE$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CHARGE_ITEM_CODE+CHARGE_ITEM_CLASS$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE+ITEM_CLASS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$ITEM_CODE$r197$, $r197$ib.item_code = pr.item_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：INP_BILL_DETAIL:N → PRICE_LIST:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-BB4AF449D7", "stage": "S2", "statements": 1, "templates": 1, "files": ["提取病人费用20万以上费用明细.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.MR_BILL_CLASS_DICT$r197$, $r197$MR_BILL_CLASS_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$MR_BILL_CLASS$r197$, $r197$pr.mr_bill_class = mb.mr_bill_class_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：DIAGNOSIS_TYPE = ×2（值域已确认：1,2,3,7）；【值域待确认】DIAGNOSIS_NO = ×2；【值域待确认】OPERATION_NO = ×2；【值域待确认】MR_BILL_CLASS_CODE LIKE ×2; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-D16F6274AC", "stage": "S2", "statements": 1, "templates": 1, "files": ["提取病人费用20万以上费用明细.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.MR_BILL_CLASS_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$MR_BILL_CLASS_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$MR_BILL_CLASS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.PREPAYMENT_RCPT$r197$, $r197$OPERATOR_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.STAFF_DICT$r197$, $r197$ID$r197$, $r197$a.operator_no=d.id$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度（含停用/重用代码风险）; 基数：PREPAYMENT_RCPT:N → STAFF_DICT:1; 条件：【值域待确认】VISIT_ID > ×1；【值域待确认】DEPT_CODE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-FF689C8E0E", "stage": "S2", "statements": 1, "templates": 1, "files": ["流调\\交费退费.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.PREPAYMENT_RCPT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$OPERATOR_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.STAFF_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$OPERATOR$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.STAFF_DICT$r197$, $r197$ID$r197$, $r197$a.operator = c.id$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度（含停用/重用代码风险）; 基数：CLINIC_MASTER:N → STAFF_DICT:1; 条件：【值域待确认】DEPT_CODE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-7E158DBE85", "stage": "S2", "statements": 1, "templates": 1, "files": ["流调\\窗口挂号.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$OPERATOR$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.STAFF_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_MR$r197$, $r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_MR_DIAG_DESC$r197$, $r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$, $r197$om.patient_id = omd.patient_id AND om.visit_date = omd.visit_date AND om.visit_no = omd.visit_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】DIAG_DESC LIKE ×4; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-B6C23A8ACC", "stage": "S2", "statements": 1, "templates": 1, "files": ["消化内一科sql.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$HIS.OUTP_MR$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OUTP_MR_DIAG_DESC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_DATE+VISIT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$ITEM_CODE$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.INSUR_VSH_CENTER_ITEM_NEW$r197$, $r197$ITEM_CODE$r197$, $r197$aa.item_code=a.item_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：INP_BILL_DETAIL:N → INSUR_VSH_CENTER_ITEM_NEW:1; 条件：【值域待确认】TRANSACT_TYPE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-797C110153", "stage": "S2", "statements": 1, "templates": 1, "files": ["病理医保飞检数据提取.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.INSUR_VSH_CENTER_ITEM_NEW$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$DOCTOR$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.STAFF_DICT$r197$, $r197$USER_NAME$r197$, $r197$s.user_name = c.DOCTOR$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：字典取值维度（含停用/重用代码风险）; 基数：CLINIC_MASTER:N → STAFF_DICT:1; 条件：【值域待确认】CHARGE_INDICATOR = ×1；【值域待确认】就诊类型 = ×1; 风险：name_join_high_risk,semantic_suspect; 姓名型 JOIN：计划 §6 明确只作高风险证据$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-BCB9A63C52", "stage": "S2", "statements": 1, "templates": 1, "files": ["病理医保飞检数据提取.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["name_join_high_risk", "semantic_suspect"], "notes": "姓名型 JOIN：计划 §6 明确只作高风险证据"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DOCTOR$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.STAFF_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$USER_NAME$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DOCTOR_GROUP$r197$, $r197$ORDER_GROUP$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OPERATION_MASTER$r197$, $r197$DEPT_STAYED$r197$, $r197$om.dept_stayed = dg.order_group$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：OPERATION_MASTER:N → DOCTOR_GROUP:1; 条件：【值域待确认】OPER_ID = ×1；【值域待确认】OPERATION_NO = ×1；【值域待确认】PERFORMED_BY = ×1; 风险：semantic_suspect; 医生组→住院科室等值连接，语义可疑（组代码与科室代码非同域）$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-C1F7CEF65A", "stage": "S2", "statements": 1, "templates": 1, "files": ["绩效办提取语句\\提取语句\\1-每月第一波数据提取\\介入工作量分类汇总（含术者，开单医生所在科室）.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["semantic_suspect"], "notes": "医生组→住院科室等值连接，语义可疑（组代码与科室代码非同域）"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DOCTOR_GROUP$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ORDER_GROUP$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OPERATION_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DEPT_STAYED$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.ADT_LOG$r197$, $r197$ACTION$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PATIENT_STATUS_CHG_DICT$r197$, $r197$PATIENT_STATUS_CHG_CODE$r197$, $r197$al.action = ps.patient_status_chg_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：ADT_LOG:N → PATIENT_STATUS_CHG_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-A4FCF1023F", "stage": "S2", "statements": 1, "templates": 1, "files": ["绩效办提取语句\\提取语句\\其他数据提取\\2024年元旦假期（2023.12.30-2024.1.1）出院患者记录.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$HIS.ADT_LOG$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ACTION$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PATIENT_STATUS_CHG_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_STATUS_CHG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$ORDER_CODE$r197$, $r197$oo.order_code = dd.drug_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：ORDERS:N → DRUG_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-3B0F594FB5", "stage": "S2", "statements": 1, "templates": 1, "files": ["门诊住院抗菌药物处方信息.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ORDER_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DOCT_DRUG_PRESC_MASTER$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.PATS_IN_HOSPITAL$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$PATS_IN_HOSPITAL.PATIENT_ID = DOCT_DRUG_PRESC_MASTER.PATIENT_ID AND PATS_IN_HOSPITAL.VISIT_ID = DOCT_DRUG_PRESC_MASTER.VISIT_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】DISPENSARY = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-7C3491FAB2", "stage": "S2", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年02月 14-27.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DOCT_DRUG_PRESC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$INPADM.PATS_IN_HOSPITAL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.AREA_DICT$r197$, $r197$AREA_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.PAT_VISIT$r197$, $r197$PATIENT_AREA$r197$, $r197$O.PATIENT_AREA = XZZ.AREA_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：PAT_VISIT:N → AREA_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-6078311B11", "stage": "S2", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年04月 11-17.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.AREA_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$AREA_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.PAT_VISIT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_AREA$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_INDEX$r197$, $r197$CLINIC_TYPE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_TYPE_SETTING$r197$, $r197$CLINIC_TYPE$r197$, $r197$CLINIC_INDEX.CLINIC_TYPE = CLINIC_TYPE_SETTING.CLINIC_TYPE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：CLINIC_INDEX:N → CLINIC_TYPE_SETTING:1; 条件：【值域待确认】CHARGE_ITEM = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-4AB467630E", "stage": "S2", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年05月 09-15.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_INDEX$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLINIC_TYPE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.CLINIC_TYPE_SETTING$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLINIC_TYPE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.MEDICAL_CARD_MEMO$r197$, $r197$CARD_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.MEDICAL_CARD_VS_IDNO$r197$, $r197$CARD_NO$r197$, $r197$A.CARD_NO = B.CARD_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-FA29D8E7F7", "stage": "S2", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年05月 23-29.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$MEDREC.MEDICAL_CARD_MEMO$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CARD_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.MEDICAL_CARD_VS_IDNO$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CARD_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.ADT_LOG$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.MR_ON_LINE$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$ADT_LOG.PATIENT_ID = MR_ON_LINE.PATIENT_ID AND ADT_LOG.VISIT_ID = MR_ON_LINE.VISIT_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】DEPT_CODE = ×4；【值域待确认】REQUEST_DOCTOR_ID = ×1；【值域待确认】ACTION = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-68463732FB", "stage": "S2", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年08月 22-28.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$HIS.ADT_LOG$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.MR_ON_LINE$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DOCTOR_GROUP$r197$, $r197$DOCTOR_USER$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.STAFF_DICT$r197$, $r197$USER_NAME$r197$, $r197$B.USER_NAME = A.DOCTOR_USER$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：name_join_high_risk,semantic_suspect; 姓名型 JOIN：只作高风险证据$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-35D425985E", "stage": "S2", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年11月 14-20.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["name_join_high_risk", "semantic_suspect"], "notes": "姓名型 JOIN：只作高风险证据"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DOCTOR_GROUP$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DOCTOR_USER$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.STAFF_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$USER_NAME$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$PATIENT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.MEDICAL_CARD_MEMO$r197$, $r197$PATIENT_ID$r197$, $r197$D.PATIENT_ID = A.PATIENT_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：门诊挂号级; 基数：MEDICAL_CARD_MEMO:N → CLINIC_MASTER:1（按 PATIENT_ID）; 条件：【值域待确认】ACCOUNT_STATUS <> ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-1C9DF9CFDD", "stage": "S2", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年12月 05-11.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.MEDICAL_CARD_MEMO$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_DETAIL$r197$, $r197$PRESC_NO+PRESC_DATE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_MASTER$r197$, $r197$PRESC_NO+PRESC_DATE$r197$, $r197$B.PRESC_NO = C.PRESC_NO AND B.PRESC_DATE = C.PRESC_DATE$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-A4F3F1FA73", "stage": "S2", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年12月 05-11.sql"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "两列键（Q31）", "probe_uids": ["Q31"], "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_PRESC_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PRESC_NO+PRESC_DATE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PRESC_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PRESC_NO+PRESC_DATE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DOCT_DRUG_PRESC_DETAIL$r197$, $r197$PRESC_DATE+PRESC_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DOCT_DRUG_PRESC_MASTER$r197$, $r197$PRESC_DATE+PRESC_NO$r197$, $r197$DOCT_DRUG_PRESC_DETAIL.PRESC_DATE = DOCT_DRUG_PRESC_MASTER.PRESC_DATE AND DOCT_DRUG_PRESC_DETAIL.PRESC_NO = DOCT_DRUG_PRESC_MASTER.PRESC_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（手术/结算/床位等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】PRESC_STATUS = ×1；【值域待确认】PAYMENTS < ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S2F-915DEA9EFE", "stage": "S2", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年12月 05-11.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DOCT_DRUG_PRESC_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PRESC_DATE+PRESC_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DOCT_DRUG_PRESC_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PRESC_DATE+PRESC_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_ITEM_DICT$r197$, $r197$ITEM_CLASS+ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_VS_CHARGE$r197$, $r197$CLINIC_ITEM_CLASS+CLINIC_ITEM_CODE$r197$, $r197$a.ITEM_CLASS = b.clinic_item_class AND a.ITEM_CODE = b.clinic_item_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-7EEAFF05AE", "stage": "S3", "statements": 3, "templates": 2, "files": ["A_F0138::SQL\\2022年10月 31-06.sql", "小王sql记录\\检验外送sql.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.CLINIC_ITEM_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CLASS+ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.CLINIC_VS_CHARGE$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLINIC_ITEM_CLASS+CLINIC_ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_ITEM_DICT$r197$, $r197$ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_VS_CHARGE$r197$, $r197$CLINIC_ITEM_CODE$r197$, $r197$a.item_code = b.clinic_item_code$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：half_key; 同表对存在 ITEM_CLASS+ITEM_CODE 组合族：单列 ITEM_CODE 为半键（跨类目重码风险），见 ISS-S3-HK。；半键：同表对组合族 CLINIC_ITEM_DICT:ITEM_CLASS+ITEM_CODE=CLINIC_VS_CHARGE:CLINIC_ITEM_CLASS+CLINIC_ITEM_CODE$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-98E525FBE7", "stage": "S3", "statements": 3, "templates": 3, "files": ["检验科价表.txt", "现行计费项目总表.txt", "超声科所有检查项目（医嘱名称）及收费明细.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": "同表对存在 ITEM_CLASS+ITEM_CODE 组合族：单列 ITEM_CODE 为半键（跨类目重码风险），见 ISS-S3-HK。；半键：同表对组合族 CLINIC_ITEM_DICT:ITEM_CLASS+ITEM_CODE=CLINIC_VS_CHARGE:CLINIC_ITEM_CLASS+CLINIC_ITEM_CODE"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.CLINIC_ITEM_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.CLINIC_VS_CHARGE$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLINIC_ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS_COSTS$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$, $r197$o.patient_id = c.patient_id AND o.visit_id = c.visit_id AND o.order_no = c.order_no AND o.order_sub_no = c.order_sub_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ORDER_TEXT LIKE ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-C4039F391C", "stage": "S3", "statements": 3, "templates": 2, "files": ["A_F0138::SQL\\2022年11月 14-20.sql", "糖尿病数据提取\\提取语句\\住院医嘱.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS_COSTS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_VS_CHARGE$r197$, $r197$CHARGE_ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$ITEM_CODE$r197$, $r197$PRICE_LIST.ITEM_CODE = b.CHARGE_ITEM_CODE$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：half_key; 半键：同表对组合族 CLINIC_VS_CHARGE:CHARGE_ITEM_CODE+CHARGE_ITEM_CLASS=PRICE_LIST:ITEM_CODE+ITEM_CLASS$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-9C28994D16", "stage": "S3", "statements": 2, "templates": 1, "files": ["小王sql记录\\检验外送sql.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": "半键：同表对组合族 CLINIC_VS_CHARGE:CHARGE_ITEM_CODE+CHARGE_ITEM_CLASS=PRICE_LIST:ITEM_CODE+ITEM_CLASS"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.CLINIC_VS_CHARGE$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CHARGE_ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_ITEM_NAME_DICT$r197$, $r197$ITEM_CLASS+ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_VS_CHARGE$r197$, $r197$CLINIC_ITEM_CLASS+CLINIC_ITEM_CODE$r197$, $r197$b.clinic_item_class = c.item_class AND b.clinic_item_code = c.item_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ITEM_STATUS <> ×4；【值域待确认】EXPAND3 = ×2; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-E7DE652B19", "stage": "S3", "statements": 2, "templates": 1, "files": ["小王sql记录\\检验外送sql.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.CLINIC_ITEM_NAME_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CLASS+ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.CLINIC_VS_CHARGE$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLINIC_ITEM_CLASS+CLINIC_ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$ORDER_CLASS$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.ORDER_CLASS_DICT$r197$, $r197$ORDER_CLASS_CODE$r197$, $r197$o.order_class = e.order_class_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：ORDERS:N → ORDER_CLASS_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-E65D6CED98", "stage": "S3", "statements": 2, "templates": 1, "files": ["糖尿病数据提取\\提取语句\\住院医嘱.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ORDER_CLASS$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.ORDER_CLASS_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ORDER_CLASS_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_ITEM_CLASS_DICT$r197$, $r197$CLASS_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS_COSTS$r197$, $r197$ITEM_CLASS$r197$, $r197$c.item_class = q.class_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：ORDERS_COSTS:N → CLINIC_ITEM_CLASS_DICT:1; 条件：【值域待确认】REPORT_ITEM_NAME LIKE ×8；DIAGNOSIS_TYPE = ×4（值域已确认：1,2,3,7,8）；【值域待确认】DIAGNOSIS_NO = ×4；【值域待确认】DIAGNOSIS_DESC LIKE ×4; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-0F3B49513D", "stage": "S3", "statements": 2, "templates": 1, "files": ["糖尿病数据提取\\提取语句\\住院医嘱.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.CLINIC_ITEM_CLASS_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLASS_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS_COSTS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CLASS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_ITEM_NAME_DICT$r197$, $r197$ITEM_CLASS+ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$ITEM_CLASS+ITEM_CODE$r197$, $r197$PRICE_LIST.ITEM_CLASS = PRICE_ITEM_NAME_DICT.ITEM_CLASS AND PRICE_LIST.ITEM_CODE = PRICE_ITEM_NAME_DICT.ITEM_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ITEM_CLASS = ×1；【值域待确认】AS_ITEMCLASS = ×1; 风险：; ；别名判读补充 +1（2022年10月 L557 原文截断但双列等值意图明确）$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-C21F072F9B", "stage": "S3", "statements": 3, "templates": 2, "files": ["A_F0138::SQL\\2022年10月 24-30.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": "；别名判读补充 +1（2022年10月 L557 原文截断但双列等值意图明确）"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.PRICE_ITEM_NAME_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CLASS+ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CLASS+ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.PREPAY_ACCT$r197$, $r197$ACCT_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.PREPAY_ACCT_MONEY$r197$, $r197$ACCT_NO$r197$, $r197$PREPAY_ACCT.ACCT_NO = PREPAY_ACCT_MONEY.ACCT_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】INP_FLAG = ×1；【值域待确认】MONEY_TYPE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-00F35490BC", "stage": "S3", "statements": 2, "templates": 2, "files": ["A_F0138::SQL\\2022年11月 28-04.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.PREPAY_ACCT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ACCT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.PREPAY_ACCT_MONEY$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ACCT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$ITEM_CODE$r197$, $r197$d.item_code = ddd.drug_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：INP_BILL_DETAIL:N → DRUG_DICT:1; 条件：【值域待确认】DISCHARGE_TAKING_INDICATOR = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-B8DD5D167D", "stage": "S3", "statements": 1, "templates": 1, "files": ["2023年2季度全院及各科室抗菌药物出院带药情况，包括科室，出院带药抗菌药物名称、规格、单位、数量、人次数、药费、总用量.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$EXAM.EXAM_MASTER$r197$, $r197$EXAM_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$APPOINT_NO$r197$, $r197$obi.appoint_no = em.exam_no$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】VISIT_ID = ×1; 风险：multipurpose_business_key; APPOINT_NO 多义键·检查方向（=EXAM_NO，平台 559/15 同构）；检验方向=TEST_NO。按 ITEM_CLASS 分流。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-6971C4D4A3", "stage": "S3", "statements": 1, "templates": 1, "files": ["2025年7月影像科人次，包含收费类别、检查时间、病人姓名、ID号、住院号、身份证号、收费金额.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["multipurpose_business_key"], "notes": "APPOINT_NO 多义键·检查方向（=EXAM_NO，平台 559/15 同构）；检验方向=TEST_NO。按 ITEM_CLASS 分流。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$EXAM.EXAM_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$EXAM_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$APPOINT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$EXAM.EXAM_MASTER$r197$, $r197$EXAM_NO+PATIENT_ID+VISIT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$OPER_CODE+PATIENT_ID+VISIT_ID$r197$, $r197$ibd.oper_code = em.exam_no AND ibd.patient_id = em.patient_id AND ibd.visit_id = em.visit_id$r197$, $r197$197历史SQL摄入候选（partial；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】VISIT_ID > ×1; 风险：multipurpose_business_key; OPER_CODE 多义键·检查方向（=EXAM_NO）：成立前提为费用行是检查类；手术类费用 OPER_CODE=OPERATION_MASTER.OPER_ID（平台 557/564，LENGTH≥8）。必须带费用类别限定，见 RCP-S3-07。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-8CF8B4B39E", "stage": "S3", "statements": 1, "templates": 1, "files": ["2025年7月影像科人次，包含收费类别、检查时间、病人姓名、ID号、住院号、身份证号、收费金额.txt"], "intake_state": "partial", "validation_state": "passed_in_scope", "validation_note": "检查类 OPER_CODE 分流证据（Q15：非空率高；ITEM_CLASS 身份值域待确认）", "probe_uids": ["Q15"], "risk_tags": ["multipurpose_business_key"], "notes": "OPER_CODE 多义键·检查方向（=EXAM_NO）：成立前提为费用行是检查类；手术类费用 OPER_CODE=OPERATION_MASTER.OPER_ID（平台 557/564，LENGTH≥8）。必须带费用类别限定，见 RCP-S3-07。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$EXAM.EXAM_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$EXAM_NO+PATIENT_ID+VISIT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$OPER_CODE+PATIENT_ID+VISIT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$CLASS_ON_INP_RCPT$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.INP_RCPT_FEE_DICT$r197$, $r197$FEE_CLASS_CODE$r197$, $r197$i.class_on_inp_rcpt=v.fee_class_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：INP_BILL_DETAIL:N → INP_RCPT_FEE_DICT:1; 条件：【值域待确认】INP_NO = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-4E0A7CB9FE", "stage": "S3", "statements": 1, "templates": 1, "files": ["sql.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLASS_ON_INP_RCPT$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.INP_RCPT_FEE_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$FEE_CLASS_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.INSUR_VSH_CENTER_ITEM_NEW$r197$, $r197$ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$ITEM_CODE$r197$, $r197$cc.item_code=b.item_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：OUTP_BILL_ITEMS:N → INSUR_VSH_CENTER_ITEM_NEW:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-21C1208636", "stage": "S3", "statements": 1, "templates": 1, "files": ["医保药品统计sql.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$HIS.INSUR_VSH_CENTER_ITEM_NEW$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$DRUG_CODE+FIRM_ID+UNITS$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$ITEM_CODE+ITEM_SPEC+UNITS$r197$, $r197$bb.drug_code = b.item_code AND bb.firm_id = b.item_spec AND bb.units = b.units$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：OUTP_BILL_ITEMS:N → DRUG_PRICE_LIST:1; 条件：; 风险：concat_key,price_pick_rownum; 同 RCP-S3-04：拼接键+rownum=1 任取价格行，建议改显式列+生效时间窗。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-FF1623FE72", "stage": "S3", "statements": 1, "templates": 1, "files": ["医保药品统计sql.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["concat_key", "price_pick_rownum"], "notes": "同 RCP-S3-04：拼接键+rownum=1 任取价格行，建议改显式列+生效时间窗。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+FIRM_ID+UNITS$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE+ITEM_SPEC+UNITS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_ORDERS$r197$, $r197$CLINIC_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_ORDER_DESC$r197$, $r197$CLINIC_NO$r197$, $r197$f.CLINIC_NO=c.CLINIC_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：; 门诊号直连（无 VISIT_DATE 组合）：挂号流水重用风险低于 RCPT_NO 单列，但组合 VISIT_DATE 更稳；S6 与三列族联合验证。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-C4FDA97470", "stage": "S3", "statements": 1, "templates": 1, "files": ["影像科明细数据提取.docx"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": "门诊号直连（无 VISIT_DATE 组合）：挂号流水重用风险低于 RCPT_NO 单列，但组合 VISIT_DATE 更稳；S6 与三列族联合验证。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$HIS.OUTP_ORDERS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLINIC_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_ORDER_DESC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLINIC_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$ORDER_ID$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.OUTP_ORDERS$r197$, $r197$ORDER_ID$r197$, $r197$f.ORDER_ID=a.ORDER_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-73E9BAF540", "stage": "S3", "statements": 1, "templates": 1, "files": ["影像科明细数据提取.docx"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ORDER_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$HIS.OUTP_ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ORDER_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$SUBJ_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.TALLY_SUBJECT_DICT$r197$, $r197$SUBJ_CODE$r197$, $r197$tsd.subj_code = pl.subj_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-7D08A9E399", "stage": "S3", "statements": 1, "templates": 1, "files": ["所有现行价表，药品、耗材、诊疗项目明细.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$SUBJ_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.TALLY_SUBJECT_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$SUBJ_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$LAB.LAB_TEST_ITEMS$r197$, $r197$TEST_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$APPOINT_NO$r197$, $r197$lt.test_no = a.appoint_no$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：multipurpose_business_key; APPOINT_NO 多义键·检验方向（=TEST_NO，平台 559/568 同构）；检查方向=EXAM_NO。按 ITEM_CLASS 分流，见 RCP-S3-07。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-F5C0C8EDAE", "stage": "S3", "statements": 1, "templates": 1, "files": ["检验科、病理科、输血科排除外送总费用.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["multipurpose_business_key"], "notes": "APPOINT_NO 多义键·检验方向（=TEST_NO，平台 559/568 同构）；检查方向=EXAM_NO。按 ITEM_CLASS 分流，见 RCP-S3-07。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$LAB.LAB_TEST_ITEMS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$TEST_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$APPOINT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_ITEM_CLASS_DICT$r197$, $r197$CLASS_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_ITEM_DICT$r197$, $r197$ITEM_CLASS$r197$, $r197$d.class_code = a.item_class$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ITEM_STATUS = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-9193379481", "stage": "S3", "statements": 1, "templates": 1, "files": ["现行计费项目总表.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.CLINIC_ITEM_CLASS_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLASS_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.CLINIC_ITEM_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CLASS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.INSUR_VSH_CENTER_ITEM_NEW$r197$, $r197$ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$ITEM_CODE$r197$, $r197$aa.item_code=pl.item_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-7FDFCCAC38", "stage": "S3", "statements": 1, "templates": 1, "files": ["病理医保飞检数据提取.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$HIS.INSUR_VSH_CENTER_ITEM_NEW$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.BILL_ITEM_CLASS_DICT$r197$, $r197$CLASS_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$CLASS_ON_RECKONING$r197$, $r197$r.class_code = pl.class_on_reckoning$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-3F30DA6B47", "stage": "S3", "statements": 1, "templates": 1, "files": ["病理医保飞检数据提取.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.BILL_ITEM_CLASS_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLASS_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLASS_ON_RECKONING$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$PATIENT_ID+VISIT_ID+OPER_CODE+ORDER_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID+VISIT_ID+APP_NO+ORDER_NO$r197$, $r197$a.patient_id=b.patient_id AND a.visit_id=b.visit_id AND a.APP_NO=b.OPER_CODE AND a.ORDER_NO=b.ORDER_NO$r197$, $r197$197历史SQL摄入候选（partial；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：multipurpose_business_key; OPER_CODE 多义键·医嘱申请方向（=APP_NO，病理医保飞检语句证据）；ORDER_NO 对齐补齐序号。同列第三身份=OPER_ID，见 RCP-S3-07。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-D8F12989E0", "stage": "S3", "statements": 1, "templates": 1, "files": ["病理医保飞检数据提取.txt"], "intake_state": "partial", "validation_state": "passed_in_scope", "validation_note": "四列键挂医嘱 APP_NO（Q15/Q33 侧证）", "probe_uids": ["Q15", "Q33"], "risk_tags": ["multipurpose_business_key"], "notes": "OPER_CODE 多义键·医嘱申请方向（=APP_NO，病理医保飞检语句证据）；ORDER_NO 对齐补齐序号。同列第三身份=OPER_ID，见 RCP-S3-07。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+OPER_CODE+ORDER_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+APP_NO+ORDER_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$ORDER_CODE$r197$, $r197$b.ITEM_CODE=a.ORDER_CODE$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：semantic_suspect; ITEM_CODE 与 ORDER_CODE 跨域等值：仅药品/特定医嘱类别下可能同域；不按 ORDER_CLASS/ITEM_CLASS 分流会错配，S6 探针验证。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-C548CAAE32", "stage": "S3", "statements": 1, "templates": 1, "files": ["病理医保飞检数据提取.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["semantic_suspect"], "notes": "ITEM_CODE 与 ORDER_CODE 跨域等值：仅药品/特定医嘱类别下可能同域；不按 ORDER_CLASS/ITEM_CLASS 分流会错配，S6 探针验证。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ORDER_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_ITEM_DICT$r197$, $r197$ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.EXAM_RPT_PATTERN$r197$, $r197$DESCRIPTION_CODE$r197$, $r197$exam.description_code = a.item_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：EXAM_RPT_PATTERN:N → CLINIC_ITEM_DICT:1; 条件：【值域待确认】EXAM_CLASS = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-5020B1B11D", "stage": "S3", "statements": 1, "templates": 1, "files": ["超声科所有检查项目（医嘱名称）及收费明细.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.CLINIC_ITEM_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.EXAM_RPT_PATTERN$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DESCRIPTION_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$ITEM_CODE$r197$, $r197$PRICE_LIST.ITEM_CODE = OUTP_BILL_ITEMS.ITEM_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：OUTP_BILL_ITEMS:N → PRICE_LIST:1; 条件：; 风险：; ；别名判读补充 +1（2022年07月 L57 相关子查询重复书写 6 次同一等值（模板计数 1））$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-A7C9381FA2", "stage": "S3", "statements": 2, "templates": 1, "files": ["A_F0138::SQL\\2022年07月 18-24.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": "；别名判读补充 +1（2022年07月 L57 相关子查询重复书写 6 次同一等值（模板计数 1））"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.PREPAYMENT_RCPT$r197$, $r197$RCPT_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.PREPAYMENT_RCPT_ADD$r197$, $r197$RCPT_NO$r197$, $r197$PREPAYMENT_RCPT.RCPT_NO = PREPAYMENT_RCPT_ADD.RCPT_NO$r197$, $r197$197历史SQL摄入候选（partial；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ACCT_NO = ×1; 风险：half_key; 半键：同表对组合族 PREPAYMENT_RCPT:RCPT_NO+PATIENT_ID+VISIT_ID=PREPAYMENT_RCPT_ADD:RCPT_NO+PATIENT_ID+VISIT_ID$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-5FF4CF0E1A", "stage": "S3", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年07月 25-31.sql"], "intake_state": "partial", "validation_state": "passed_in_scope", "validation_note": "预交金 RCPT_NO 0 重复、ADD 三列键 0 重复（Q14b 样本 20000/10917 组）", "probe_uids": ["Q14b"], "risk_tags": ["half_key"], "notes": "半键：同表对组合族 PREPAYMENT_RCPT:RCPT_NO+PATIENT_ID+VISIT_ID=PREPAYMENT_RCPT_ADD:RCPT_NO+PATIENT_ID+VISIT_ID"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.PREPAYMENT_RCPT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$RCPT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.PREPAYMENT_RCPT_ADD$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$RCPT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$ITEM_CODE+ITEM_CLASS+ITEM_NAME$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_ITEM_NAME_DICT$r197$, $r197$ITEM_CODE+ITEM_CLASS+ITEM_NAME$r197$, $r197$INP_BILL_DETAIL.ITEM_CODE = PRICE_ITEM_NAME_DICT.ITEM_CODE AND INP_BILL_DETAIL.ITEM_CLASS = PRICE_ITEM_NAME_DICT.ITEM_CLASS AND INP_BILL_DETAIL.ITEM_NAME = PRICE_ITEM_NAME_DICT.ITEM_NAME$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：INP_BILL_DETAIL:N → PRICE_ITEM_NAME_DICT:1; 条件：【值域待确认】ITEM_CLASS = ×2；【值域待确认】VISIT_ID = ×1; 风险：name_join_high_risk$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-3904B0E814", "stage": "S3", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年10月 24-30.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["name_join_high_risk"], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CODE+ITEM_CLASS+ITEM_NAME$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_ITEM_NAME_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE+ITEM_CLASS+ITEM_NAME$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_ITEM_NAME_DICT$r197$, $r197$ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$ITEM_CODE$r197$, $r197$PRICE_LIST.ITEM_CODE = PRICE_ITEM_NAME_DICT.ITEM_CODE$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：half_key; 半键：同表对组合族 PRICE_ITEM_NAME_DICT:ITEM_CLASS+ITEM_CODE=PRICE_LIST:ITEM_CLASS+ITEM_CODE$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-C8B128DDC1", "stage": "S3", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年10月 24-30.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": "半键：同表对组合族 PRICE_ITEM_NAME_DICT:ITEM_CLASS+ITEM_CODE=PRICE_LIST:ITEM_CLASS+ITEM_CODE"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.PRICE_ITEM_NAME_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_ITEM_DICT$r197$, $r197$ITEM_CLASS+ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_ITEM_NAME_DICT$r197$, $r197$ITEM_CLASS+ITEM_CODE$r197$, $r197$CLINIC_ITEM_DICT.ITEM_CLASS(+) = PRICE_ITEM_NAME_DICT.ITEM_CLASS AND CLINIC_ITEM_DICT.ITEM_CODE(+) = PRICE_ITEM_NAME_DICT.ITEM_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ITEM_CLASS = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-24FCB0CB0D", "stage": "S3", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年10月 24-30.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.CLINIC_ITEM_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ITEM_CLASS+ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.PRICE_ITEM_NAME_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CLASS+ITEM_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.OFFICIAL_DRUG_CATALOG$r197$, $r197$CONSTRAINED_LEVEL$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.OFFICIAL_DRUG_CATALOG_CLASS$r197$, $r197$CLASS_CODE$r197$, $r197$O.CONSTRAINED_LEVEL = C.CLASS_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-CE3037882E", "stage": "S3", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年10月 24-30.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.OFFICIAL_DRUG_CATALOG$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CONSTRAINED_LEVEL$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.OFFICIAL_DRUG_CATALOG_CLASS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CLASS_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.PREPAYMENT_RCPT$r197$, $r197$RCPT_NO+PATIENT_ID+VISIT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.PREPAYMENT_RCPT_ADD$r197$, $r197$RCPT_NO+PATIENT_ID+VISIT_ID$r197$, $r197$a.rcpt_no = c.rcpt_no AND a.patient_id = c.patient_id AND a.visit_id = c.visit_id$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】PATIENT_ID = ×1；【值域待确认】BANK LIKE ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-F2E3960562", "stage": "S3", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年11月 07-13.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": ""}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.PREPAYMENT_RCPT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$RCPT_NO+PATIENT_ID+VISIT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.PREPAYMENT_RCPT_ADD$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$RCPT_NO+PATIENT_ID+VISIT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.PREPAY_ACCT$r197$, $r197$OPERATOR_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.STAFF_DICT$r197$, $r197$ID$r197$, $r197$A.OPERATOR_NO = B.ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度（含停用/重用代码风险）; 基数：PREPAY_ACCT:N → STAFF_DICT:1; 条件：; 风险：; STAFF_DICT.ID 为工号备用键（S2F-D3EDFB4370 同类）；EMP_NO 为主键口径。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-6E9E76D915", "stage": "S3", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年11月 28-04.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": "STAFF_DICT.ID 为工号备用键（S2F-D3EDFB4370 同类）；EMP_NO 为主键口径。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.PREPAY_ACCT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$OPERATOR_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.STAFF_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$HIS.BED_TRANS_LOG$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.PAT_VISIT$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：住院就诊级; 基数：BED_TRANS_LOG:N → PAT_VISIT:1（按 PATIENT_ID+VISIT_ID）; 条件：; 风险：judgment_resolved; 别名 A/TT 人工判读：床位转移日志按住院万能键挂 PAT_VISIT；新增事实表 BED_TRANS_LOG 入族 RF-INPATIENT-VISIT 模式。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-C752F8DA70", "stage": "S3", "statements": 1, "templates": 1, "files": ["SQL\\2022年04月 11-17.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["judgment_resolved"], "notes": "别名 A/TT 人工判读：床位转移日志按住院万能键挂 PAT_VISIT；新增事实表 BED_TRANS_LOG 入族 RF-INPATIENT-VISIT 模式。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$HIS.BED_TRANS_LOG$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.PAT_VISIT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.PREPAYMENT_RCPT_ADD$r197$, $r197$CHECK_NO+BANK_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.PREPAYMENT_RCPT$r197$, $r197$CHECK_NO+BANK_CODE$r197$, $r197$$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：judgment_resolved; 别名 A/B 人工判读：支票号+银行代码对账键，与 RCPT_NO 族并存（三种键并行，见 RCP-S3-06）；S3-P004 唯一性探针。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-57AB79EC21", "stage": "S3", "statements": 1, "templates": 1, "files": ["SQL\\2022年08月 15-21.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["judgment_resolved"], "notes": "别名 A/B 人工判读：支票号+银行代码对账键，与 RCPT_NO 族并存（三种键并行，见 RCP-S3-06）；S3-P004 唯一性探针。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.PREPAYMENT_RCPT_ADD$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CHECK_NO+BANK_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.PREPAYMENT_RCPT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CHECK_NO+BANK_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$OUTP_RCPT_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_RCPT_MASTER$r197$, $r197$RCPT_NO$r197$, $r197$$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：judgment_resolved; 别名 A 人工判读：住院明细的门诊收据号字段挂门诊收据主档（住院期间门诊收费场景）；字段级语义需 S6 元数据核对。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-5D3D14EBA1", "stage": "S3", "statements": 1, "templates": 1, "files": ["SQL\\2022年09月 26-02.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["judgment_resolved"], "notes": "别名 A 人工判读：住院明细的门诊收据号字段挂门诊收据主档（住院期间门诊收费场景）；字段级语义需 S6 元数据核对。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$OUTP_RCPT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_RCPT_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$RCPT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.PRICE_LIST$r197$, $r197$PERFORMED_BY$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DEPT_DICT$r197$, $r197$DEPT_CODE$r197$, $r197$$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：judgment_resolved,truncated_raw; 原文残缺（…= COMM.DEPT_DICT 少列名），按意图判读 PERFORMED_BY=DEPT_CODE：价表执行科室字段；待核标记，S6 元数据核对后定稿。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S3F-3862E450B1", "stage": "S3", "statements": 1, "templates": 1, "files": ["SQL\\2022年10月 24-30.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["judgment_resolved", "truncated_raw"], "notes": "原文残缺（…= COMM.DEPT_DICT 少列名），按意图判读 PERFORMED_BY=DEPT_CODE：价表执行科室字段；待核标记，S6 元数据核对后定稿。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.PRICE_LIST$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PERFORMED_BY$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.DEPT_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DEPT_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$, $r197$DOCUMENT_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_MASTER$r197$, $r197$DOCUMENT_NO$r197$, $r197$t.document_no = s.document_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】EXPORT_CLASS = ×4；【值域待确认】STORAGE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-57E6B624A0", "stage": "S5", "statements": 11, "templates": 6, "files": ["创建表及导库.sql", "小卢sql\\药品进销存.sql", "小孙遗产\\药品库存.sql", "小王sql记录\\药房药品出库会诊报表sql.txt"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "覆盖窗 1863 单 0 重复+主从 200/200（Q27c/Q28c）；表停更 2025-07-05 已标注", "probe_uids": ["Q27c", "Q28c"], "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DOCUMENT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$DRUG_USER.DRUG_EXPORT_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DOCUMENT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$YDHL.MCS_DOC_FORM$r197$, $r197$ID$r197$, $r197$DATA_CENTER$r197$, $r197$YDHL.MCS_DOC_FORM_RECORDS$r197$, $r197$FORM_ID$r197$, $r197$a.id=b.form_id$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：mobile_nursing_chain; 护理表单-记录主从键（form.id=records.form_id）：平台草稿 574/663 同构（draft≠正式）。模板/节点值域与重复评估粒度待 S5-P005 验证。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-2A342EA32E", "stage": "S5", "statements": 10, "templates": 6, "files": ["移动护理VTE数据查询.sql"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "500/500 表单有记录（Q35）；重复评估 22.5% 实证入 RCP-S5-05", "probe_uids": ["Q35"], "risk_tags": ["mobile_nursing_chain"], "notes": "护理表单-记录主从键（form.id=records.form_id）：平台草稿 574/663 同构（draft≠正式）。模板/节点值域与重复评估粒度待 S5-P005 验证。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$YDHL.MCS_DOC_FORM$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ID$r197$,'')
    AND upper(r.to_table)=upper($r197$YDHL.MCS_DOC_FORM_RECORDS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$FORM_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_IMPORT_DETAIL$r197$, $r197$DOCUMENT_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_IMPORT_MASTER$r197$, $r197$DOCUMENT_NO$r197$, $r197$t.document_no = s.document_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】QUANTITY <> ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-567E60F5C7", "stage": "S5", "statements": 7, "templates": 6, "files": ["创建表及导库.sql", "小卢sql\\药品进销存.sql", "小孙遗产\\药品库存.sql", "小王sql记录\\月底药品库存sql.txt", "小王sql记录\\月底药库20240307 最终版.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$DRUG_USER.DRUG_IMPORT_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DOCUMENT_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$DRUG_USER.DRUG_IMPORT_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DOCUMENT_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$DRUG_CODE+DRUG_SPEC+FIRM_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STOCK_LOG_NEW$r197$, $r197$DRUG_CODE+PACKAGE_SPEC+FIRM_ID$r197$, $r197$A.DRUG_CODE = AA.DRUG_CODE AND A.PACKAGE_SPEC = AA.DRUG_SPEC AND A.FIRM_ID = AA.FIRM_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_STOCK_LOG_NEW:N → DRUG_PRICE_LIST:1; 条件：【值域待确认】QUANTITY <> ×5; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-6D51708E12", "stage": "S5", "statements": 5, "templates": 3, "files": ["小卢sql\\药品进销存.sql", "小孙遗产\\药品库存.sql", "小王sql记录\\药库取数sql20240201.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+FIRM_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STOCK_LOG_NEW$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+PACKAGE_SPEC+FIRM_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_DETAIL_TEMP$r197$, $r197$PRESC_DATE+PRESC_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_MASTER_TEMP$r197$, $r197$PRESC_DATE+PRESC_NO$r197$, $r197$DRUG_PRESC_MASTER_TEMP.PRESC_DATE =
               DRUG_PRESC_DETAIL_TEMP.PRESC_DATE AND DRUG_PRESC_MASTER_TEMP.PRESC_NO =
               DRUG_PRESC_DETAIL_TEMP.PRESC_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：temp_worktable; 处方临时表对（PHARMACY schema 已定位）与正式表同键型：临时表是否留存历史/全量待核；与 S2F-A4F3F1FA73（正式表对）分开建族。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-55C917604B", "stage": "S5", "statements": 5, "templates": 4, "files": ["小卢sql\\药品进销存.sql", "小孙遗产\\药品库存.sql", "小王sql记录\\月底药库20240307 最终版.txt", "小王sql记录\\药房明细sql.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["temp_worktable"], "notes": "处方临时表对（PHARMACY schema 已定位）与正式表同键型：临时表是否留存历史/全量待核；与 S2F-A4F3F1FA73（正式表对）分开建族。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_PRESC_DETAIL_TEMP$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PRESC_DATE+PRESC_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PRESC_MASTER_TEMP$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PRESC_DATE+PRESC_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_NAME_DICT$r197$, $r197$DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$DRUG_CODE$r197$, $r197$C.DRUG_CODE = D.DRUG_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_NAME_DICT:N → DRUG_PRICE_LIST:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-58FB18210F", "stage": "S5", "statements": 5, "templates": 5, "files": ["A_F0138::SQL\\2022年09月 05-11.sql", "A_F0138::SQL\\结余留用-可用.sql", "药房结余留用.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_NAME_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS_EXECUTE_DETAILS$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$, $r197$ORDERS.PATIENT_ID = ORDERS_EXECUTE_DETAILS.PATIENT_ID AND ORDERS.VISIT_ID = ORDERS_EXECUTE_DETAILS.VISIT_ID AND ORDERS.ORDER_NO = ORDERS_EXECUTE_DETAILS.ORDER_NO AND ORDERS.ORDER_SUB_NO = ORDERS_EXECUTE_DETAILS.ORDER_SUB_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】REPEAT_INDICATOR = ×4；【值域待确认】VISIT_ID = ×1；【值域待确认】ORDER_NO = ×1；【值域待确认】ORDER_CLASS = ×1；【值域待确认】BED_NO > ×1；【值域待确认】BED_NO < ×1; 风险：; 医嘱↔执行明细四列键：平台草稿 14（PHA_CLI_REQUEST_DRUG↔ORDERS 四列）同构键型；执行明细的执行粒度（一嘱多执行）在统计台次/频次时需注意。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-F8FAA6C79C", "stage": "S5", "statements": 5, "templates": 5, "files": ["A_F0138::SQL\\2022年08月 08-14.sql", "A_F0138::SQL\\2022年08月 29-04.sql", "A_F0138::SQL\\2023年01月 02-08.sql", "A_F0138::SQL\\2023年01月 09-15.sql"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "四列键 736 行/159 键，一嘱多执行 avg 4.6 实证（Q33）", "probe_uids": ["Q33"], "risk_tags": [], "notes": "医嘱↔执行明细四列键：平台草稿 14（PHA_CLI_REQUEST_DRUG↔ORDERS 四列）同构键型；执行明细的执行粒度（一嘱多执行）在统计台次/频次时需注意。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS_EXECUTE_DETAILS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$, $r197$DRUG_CODE+DRUG_SPEC+BATCH_NO+FIRM_ID+PACKAGE_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STOCK$r197$, $r197$DRUG_CODE+DRUG_SPEC+BATCH_NO+FIRM_ID+PACKAGE_SPEC$r197$, $r197$DRUG_EXPORT_DETAIL.DRUG_CODE = DRUG_STOCK.DRUG_CODE AND DRUG_EXPORT_DETAIL.DRUG_SPEC = DRUG_STOCK.DRUG_SPEC AND DRUG_EXPORT_DETAIL.BATCH_NO = DRUG_STOCK.BATCH_NO AND DRUG_EXPORT_DETAIL.FIRM_ID = DRUG_STOCK.FIRM_ID AND DRUG_EXPORT_DETAIL.PACKAGE_SPEC = DRUG_STOCK.PACKAGE_SPEC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：batch_level_key; 出库明细↔库存五列批次键（药码+规格+批号+厂家+包装规格）：药品批次级对位的强键表达（F0136 药品进销存）；批号维度使粒度到批，S5-P003 验证唯一性。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-09818A1214", "stage": "S5", "statements": 4, "templates": 1, "files": ["小卢sql\\药品进销存.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["batch_level_key"], "notes": "出库明细↔库存五列批次键（药码+规格+批号+厂家+包装规格）：药品批次级对位的强键表达（F0136 药品进销存）；批号维度使粒度到批，S5-P003 验证唯一性。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+BATCH_NO+FIRM_ID+PACKAGE_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STOCK$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+BATCH_NO+FIRM_ID+PACKAGE_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$DRUG_EXPORT_DETAIL.DRUG_CODE = DRUG_DICT.DRUG_CODE AND DRUG_EXPORT_DETAIL.DRUG_SPEC = DRUG_DICT.DRUG_SPEC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_EXPORT_DETAIL:N → DRUG_DICT:1; 条件：【值域待确认】STORAGE = ×4; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-FFEF7998D3", "stage": "S5", "statements": 4, "templates": 1, "files": ["小卢sql\\药品进销存.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$EXAM.EXAM_MASTER$r197$, $r197$PATIENT_ID+VISIT_ID+EXAM_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID+VISIT_ID+APP_NO$r197$, $r197$o.patient_id = em.patient_id AND o.visit_id = em.visit_id AND o.app_no = em.exam_no$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】REPORT_ITEM_NAME LIKE ×16；【值域待确认】ORDER_SUB_NO = ×4；DIAGNOSIS_TYPE = ×4（值域已确认：1,2,3,7,8）；【值域待确认】DIAGNOSIS_NO = ×4；【值域待确认】DIAGNOSIS_DESC LIKE ×4；【值域待确认】DIAG_DESC LIKE ×4; 风险：; 检查申请挂医嘱三列键（EXAM_NO=APP_NO）：住院检查-医嘱对位的完整表达；与 S2F-90361056DF（门诊 EXAM_NO=APPOINT_NO）构成两套申请号口径。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-EFFC080BB2", "stage": "S5", "statements": 4, "templates": 2, "files": ["糖尿病数据提取\\提取语句\\住院检查报告.txt", "糖尿病数据提取\\提取语句\\门诊检查报告.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": "检查申请挂医嘱三列键（EXAM_NO=APP_NO）：住院检查-医嘱对位的完整表达；与 S2F-90361056DF（门诊 EXAM_NO=APPOINT_NO）构成两套申请号口径。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$EXAM.EXAM_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+EXAM_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+APP_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_DETAIL$r197$, $r197$DRUG_CODE+PACKAGE_SPEC+FIRM_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$DRUG_CODE+DRUG_SPEC+FIRM_ID$r197$, $r197$B.DRUG_CODE = D.DRUG_CODE AND B.PACKAGE_SPEC = D.DRUG_SPEC AND B.FIRM_ID = D.FIRM_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_PRESC_DETAIL:N → DRUG_PRICE_LIST:1; 条件：【值域待确认】STD_INDICATOR = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-5429C07ADC", "stage": "S5", "statements": 4, "templates": 4, "files": ["A_F0138::SQL\\2022年09月 05-11.sql", "A_F0138::SQL\\结余留用-可用.sql", "A_F0138::SQL\\结余留用.sql", "药房结余留用.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_PRESC_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+PACKAGE_SPEC+FIRM_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+FIRM_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_IMPORT_DETAIL$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STOCK$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$DRUG_STOCK.DRUG_CODE = DRUG_IMPORT_DETAIL.DRUG_CODE AND DRUG_STOCK.DRUG_SPEC = DRUG_IMPORT_DETAIL.DRUG_SPEC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-39A21CC6DC", "stage": "S5", "statements": 4, "templates": 3, "files": ["A_F0138::SQL\\2022年08月 01-07.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$DRUG_USER.DRUG_IMPORT_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STOCK$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_REC$r197$, $r197$DRUG_CODE+DRUG_SPEC+FIRM_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$DRUG_CODE+DRUG_SPEC+FIRM_ID$r197$, $r197$E.DRUG_CODE = F.DRUG_CODE AND E.DRUG_SPEC = F.DRUG_SPEC AND E.FIRM_ID = F.FIRM_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_DISPENSE_REC:N → DRUG_PRICE_LIST:1; 条件：【值域待确认】STD_INDICATOR = ×5；【值域待确认】TYPE = ×3; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-0BF471B7F7", "stage": "S5", "statements": 3, "templates": 3, "files": ["A_F0138::SQL\\2022年09月 05-11.sql", "A_F0138::SQL\\结余留用.sql", "药房结余留用.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_DISPENSE_REC$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+FIRM_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+FIRM_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DOCT_DRUG_PRESC_MASTER$r197$, $r197$PRESC_NO+PATIENT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$CURRENT_PRESC_NO+PATIENT_ID$r197$, $r197$t.presc_no = a.current_presc_no AND t.patient_id = a.patient_id$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：; 医生站处方↔医嘱按 处方号+患者 对位（CURRENT_PRESC_NO）：医嘱-处方对位链的处方侧表达；两列键跨患者唯一性待验证。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-B20ED6ACFC", "stage": "S5", "statements": 2, "templates": 2, "files": ["创建表及导库.sql", "病理医保飞检数据提取.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": "医生站处方↔医嘱按 处方号+患者 对位（CURRENT_PRESC_NO）：医嘱-处方对位链的处方侧表达；两列键跨患者唯一性待验证。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DOCT_DRUG_PRESC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PRESC_NO+PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$CURRENT_PRESC_NO+PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.CLINIC_VS_CHARGE$r197$, $r197$CLINIC_ITEM_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$ORDER_CODE$r197$, $r197$cc.clinic_item_code = a.order_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：ORDERS:N → CLINIC_VS_CHARGE:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-9750A16A8F", "stage": "S5", "statements": 2, "templates": 2, "files": ["创建表及导库.sql", "病理医保飞检数据提取.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.CLINIC_VS_CHARGE$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$CLINIC_ITEM_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ORDER_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_REC$r197$, $r197$DRUG_CODE$r197$, $r197$DRUG_DISPENSE_REC.DRUG_CODE = D.DRUG_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_DISPENSE_REC:N → DRUG_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-82AAEAEC9E", "stage": "S5", "statements": 2, "templates": 2, "files": ["A_F0138::SQL\\2022年09月 26-02.sql", "抗菌办查询医嘱开具（非处方）的抗菌药信息.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_DISPENSE_REC$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.DIAGNOSIS$r197$, $r197$TREAT_RESULT$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.TREATING_RESULT_DICT$r197$, $r197$TREATING_RESULT_CODE$r197$, $r197$treating_result_dict.treating_result_code = d.treat_result$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】REPORT_ITEM_NAME LIKE ×8；DIAGNOSIS_TYPE = ×4（值域已确认：1,2,3,7,8）；【值域待确认】DIAGNOSIS_NO = ×4；【值域待确认】DIAGNOSIS_DESC LIKE ×4; 风险：; 诊断治疗结果挂 TREATING_RESULT_DICT：TREAT_RESULT 为 confirmed 值域列；注意与离院方式字典陷阱的区别（ISS-S3-TRAP-DDD：DISCHARGE_DISPOSITION_DICT 是治疗结果字典，不能给离院方式取名——本族挂的正是治疗结果本身，方向正确）。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-D01C5207CF", "stage": "S5", "statements": 2, "templates": 1, "files": ["糖尿病数据提取\\提取语句\\住院诊断.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": "诊断治疗结果挂 TREATING_RESULT_DICT：TREAT_RESULT 为 confirmed 值域列；注意与离院方式字典陷阱的区别（ISS-S3-TRAP-DDD：DISCHARGE_DISPOSITION_DICT 是治疗结果字典，不能给离院方式取名——本族挂的正是治疗结果本身，方向正确）。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$MEDREC.DIAGNOSIS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$TREAT_RESULT$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.TREATING_RESULT_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$TREATING_RESULT_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_DETAIL$r197$, $r197$DRUG_CODE$r197$, $r197$dpd.drug_code = dd.drug_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_PRESC_DETAIL:N → DRUG_DICT:1; 条件：【值域待确认】TITLE LIKE ×1; 风险：half_key; 处方明细挂药字典单列药码：药码+规格两列版同批并存（#DRUG_DICT.DRUG_CODE+DRUG_SPEC=DRUG_PRESC_DETAIL）；一码多规格时单列放大。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-C3192AFD7A", "stage": "S5", "statements": 2, "templates": 2, "files": ["门诊住院抗菌药物处方信息.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": "处方明细挂药字典单列药码：药码+规格两列版同批并存（#DRUG_DICT.DRUG_CODE+DRUG_SPEC=DRUG_PRESC_DETAIL）；一码多规格时单列放大。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PRESC_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$EXAM.EXAM_MASTER$r197$, $r197$PATIENT_LOCAL_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$EXAM.EXAM_PAT_MI$r197$, $r197$PATIENT_LOCAL_ID$r197$, $r197$EXAM_PAT_MI.PATIENT_LOCAL_ID = EXAM_MASTER.PATIENT_LOCAL_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】VISIT_ID = ×2; 风险：exam_local_patient_index,half_key; 检查本地患者索引链：EXAM_PAT_MI（HIS/EXAM 已定位）PATIENT_LOCAL_ID 对位；两列版（+LOCAL_ID_CLASS）独立成族。检查患者身份与 PAT_MASTER_INDEX.PATIENT_ID 的映射关系待核。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-FC41ABDDDA", "stage": "S5", "statements": 2, "templates": 2, "files": ["A_F0138::SQL\\2022年08月 29-04.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["exam_local_patient_index", "half_key"], "notes": "检查本地患者索引链：EXAM_PAT_MI（HIS/EXAM 已定位）PATIENT_LOCAL_ID 对位；两列版（+LOCAL_ID_CLASS）独立成族。检查患者身份与 PAT_MASTER_INDEX.PATIENT_ID 的映射关系待核。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$EXAM.EXAM_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_LOCAL_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$EXAM.EXAM_PAT_MI$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_LOCAL_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.EXP_NAME_DICT$r197$, $r197$EXP_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.EXP_PRICE_LIST$r197$, $r197$EXP_CODE$r197$, $r197$EXP_NAME_DICT.EXP_CODE = EXP_PRICE_LIST.EXP_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】FIRM_ID = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-83CEF7EB9E", "stage": "S5", "statements": 2, "templates": 2, "files": ["A_F0138::SQL\\2022年09月 26-02.sql", "A_F0138::SQL\\2022年10月 03-16.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.EXP_NAME_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$EXP_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.EXP_PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$EXP_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.EXP_DICT$r197$, $r197$EXP_CODE+EXP_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.EXP_PRICE_LIST$r197$, $r197$EXP_CODE+EXP_SPEC$r197$, $r197$EXP_DICT.EXP_CODE = EXP_PRICE_LIST.EXP_CODE AND EXP_DICT.EXP_SPEC = EXP_PRICE_LIST.EXP_SPEC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-579A0CB0A2", "stage": "S5", "statements": 2, "templates": 2, "files": ["A_F0138::SQL\\2022年10月 24-30.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.EXP_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$EXP_CODE+EXP_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.EXP_PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$EXP_CODE+EXP_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$PATIENT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_MASTER$r197$, $r197$PATIENT_ID$r197$, $r197$mm.patient_id = cm.patient_id$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：门诊挂号级; 基数：DRUG_PRESC_MASTER:N → CLINIC_MASTER:1（按 PATIENT_ID）; 条件：【值域待确认】CLINIC_LABEL LIKE ×1；【值域待确认】PRESC_SOURCE = ×1; 风险：half_key; 门诊挂号挂门诊处方仅按 PATIENT_ID：同患者多次就诊的挂号×处方交叉放大。平台草稿 650/655 用 clinic_no（挂号流水）为正确方向；医嘱对位另有 TEST_NO=APPOINT_NO/EXAM_NO=APPOINT_NO 族。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-D6CA335877", "stage": "S5", "statements": 1, "templates": 1, "files": ["三级医院指标数据提取\\药学部sql.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": "门诊挂号挂门诊处方仅按 PATIENT_ID：同患者多次就诊的挂号×处方交叉放大。平台草稿 650/655 用 clinic_no（挂号流水）为正确方向；医嘱对位另有 TEST_NO=APPOINT_NO/EXAM_NO=APPOINT_NO 族。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PRESC_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_IMPORT_DETAIL$r197$, $r197$DRUG_CODE$r197$, $r197$b.drug_code = s.drug_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_IMPORT_DETAIL:N → DRUG_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-37CFA5B5D7", "stage": "S5", "statements": 1, "templates": 1, "files": ["创建表及导库.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$DRUG_USER.DRUG_IMPORT_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_IMPORT_MASTER$r197$, $r197$STORAGE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STORAGE_DEPT$r197$, $r197$STORAGE_CODE$r197$, $r197$t.storage = a.storage_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】STORAGE_TYPE = ×1；【值域待确认】ACCOUNT_INDICATOR = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-4B81FD6A45", "stage": "S5", "statements": 1, "templates": 1, "files": ["创建表及导库.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$DRUG_USER.DRUG_IMPORT_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$STORAGE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STORAGE_DEPT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$STORAGE_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$, $r197$DRUG_CODE$r197$, $r197$b.drug_code = s.drug_code$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_EXPORT_DETAIL:N → DRUG_DICT:1; 条件：; 风险：half_key$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-BC645BBC63", "stage": "S5", "statements": 1, "templates": 1, "files": ["创建表及导库.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_MASTER$r197$, $r197$STORAGE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STORAGE_DEPT$r197$, $r197$STORAGE_CODE$r197$, $r197$t.storage = a.storage_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】STORAGE_TYPE = ×1；【值域待确认】ACCOUNT_INDICATOR = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-E84B2B06DC", "stage": "S5", "statements": 1, "templates": 1, "files": ["创建表及导库.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$DRUG_USER.DRUG_EXPORT_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$STORAGE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STORAGE_DEPT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$STORAGE_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_PRE$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$, $r197$ORDERS.PATIENT_ID = DRUG_DISPENSE_PRE.PATIENT_ID AND ORDERS.VISIT_ID = DRUG_DISPENSE_PRE.VISIT_ID AND ORDERS.ORDER_NO = DRUG_DISPENSE_PRE.ORDER_NO AND ORDERS.ORDER_SUB_NO = DRUG_DISPENSE_PRE.ORDER_SUB_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】VISIT_ID = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-9757449C01", "stage": "S5", "statements": 1, "templates": 1, "files": ["小孙遗产\\日常问题.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_DISPENSE_PRE$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPADM.CLINIC_MASTER$r197$, $r197$PATIENT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$LAB.LAB_TEST_MASTER$r197$, $r197$PATIENT_ID$r197$, $r197$a.patient_id = b.patient_id$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：门诊挂号级; 基数：LAB_TEST_MASTER:N → CLINIC_MASTER:1（按 PATIENT_ID）; 条件：; 风险：half_key; 门诊挂号挂检验申请仅按 PATIENT_ID（放大模式同上）。门诊检验正确业务键 = LAB_TEST_MASTER.TEST_NO = OUTP_TREAT_REC.APPOINT_NO（S2F-5CB74852EF）。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-FEBB0999F9", "stage": "S5", "statements": 1, "templates": 1, "files": ["小王sql记录\\便民数据提取-2023-10-08.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": "门诊挂号挂检验申请仅按 PATIENT_ID（放大模式同上）。门诊检验正确业务键 = LAB_TEST_MASTER.TEST_NO = OUTP_TREAT_REC.APPOINT_NO（S2F-5CB74852EF）。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$OUTPADM.CLINIC_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$LAB.LAB_TEST_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DEPT_DICT$r197$, $r197$DEPT_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_MASTER$r197$, $r197$STORAGE$r197$, $r197$AA.DEPT_CODE = A.STORAGE$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：字典取值维度（含停用/重用代码风险）; 基数：DRUG_EXPORT_MASTER:N → DEPT_DICT:1; 条件：; 风险：cross_dict_domain,dict_semantics_pending; 出库单库房代码(STORAGE)挂 DEPT_DICT：库房正字典为 DRUG_STORAGE_DEPT（同语句群 #36/#38/#49 用 STORAGE_CODE）；库房编码空间与科室编码重叠时 DEPT_DICT 挂靠可误取名。保留待核。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-D6CC6E5FC6", "stage": "S5", "statements": 1, "templates": 1, "files": ["小王sql记录\\药房药品出库会诊报表sql.txt"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["cross_dict_domain", "dict_semantics_pending"], "notes": "出库单库房代码(STORAGE)挂 DEPT_DICT：库房正字典为 DRUG_STORAGE_DEPT（同语句群 #36/#38/#49 用 STORAGE_CODE）；库房编码空间与科室编码重叠时 DEPT_DICT 挂靠可误取名。保留待核。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DEPT_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DEPT_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$DRUG_USER.DRUG_EXPORT_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$STORAGE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$, $r197$DRUG_CODE+PACKAGE_SPEC+PACKAGE_UNITS+FIRM_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$DRUG_CODE+DRUG_SPEC+UNITS+FIRM_ID$r197$, $r197$BB.DRUG_CODE = B.DRUG_CODE AND BB.DRUG_SPEC = B.PACKAGE_SPEC AND BB.UNITS = B.PACKAGE_UNITS AND BB.FIRM_ID = B.FIRM_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_EXPORT_DETAIL:N → DRUG_PRICE_LIST:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-155FD309A4", "stage": "S5", "statements": 1, "templates": 1, "files": ["小王sql记录\\药房药品出库会诊报表sql.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+PACKAGE_SPEC+PACKAGE_UNITS+FIRM_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+UNITS+FIRM_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE+DRUG_SPEC+UNITS$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$, $r197$DRUG_CODE+DRUG_SPEC+UNITS$r197$, $r197$B.DRUG_CODE = C.DRUG_CODE AND B.DRUG_SPEC = C.DRUG_SPEC AND B.UNITS = C.UNITS$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_EXPORT_DETAIL:N → DRUG_DICT:1; 条件：【值域待确认】DRUG_INDICATOR = ×3；【值域待确认】ACCOUNT_RECEIVABLE > ×3; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-04DD382FAE", "stage": "S5", "statements": 1, "templates": 1, "files": ["小王sql记录\\药房药品出库会诊报表sql.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+UNITS$r197$,'')
    AND upper(r.to_table)=upper($r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+UNITS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$EXAM.EXAM_MASTER$r197$, $r197$EXAM_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$OPER_CODE$r197$, $r197$IBD.OPER_CODE = em.EXAM_NO$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】OPER_TYPE = ×1；【值域待确认】VISIT_ID > ×1; 风险：half_key,oper_code_multi_identity; 检查号挂住院费用 OPER_CODE 的单列版：OPER_CODE 多义键检查类身份（ISS-S3-OPERMULTI；三列完整版 S3F-8CF8B4B39E 为 +PATIENT_ID+VISIT_ID）。EXAM_NO 若全院唯一则单列可行但缺患者隔离；建议按费用类别分流后用三列键。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-3E64FB7320", "stage": "S5", "statements": 1, "templates": 1, "files": ["影像科明细数据提取.docx"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key", "oper_code_multi_identity"], "notes": "检查号挂住院费用 OPER_CODE 的单列版：OPER_CODE 多义键检查类身份（ISS-S3-OPERMULTI；三列完整版 S3F-8CF8B4B39E 为 +PATIENT_ID+VISIT_ID）。EXAM_NO 若全院唯一则单列可行但缺患者隔离；建议按费用类别分流后用三列键。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$EXAM.EXAM_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$EXAM_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$OPER_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_REC$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$, $r197$DRUG_DISPENSE_REC.PATIENT_ID = ORDERS.PATIENT_ID AND DRUG_DISPENSE_REC.VISIT_ID = ORDERS.VISIT_ID AND DRUG_DISPENSE_REC.ORDER_NO = ORDERS.ORDER_NO AND DRUG_DISPENSE_REC.ORDER_SUB_NO = ORDERS.ORDER_SUB_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-9CA85187E2", "stage": "S5", "statements": 1, "templates": 1, "files": ["抗菌办查询医嘱开具（非处方）的抗菌药信息.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_DISPENSE_REC$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_DETAIL$r197$, $r197$PRESC_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_MASTER$r197$, $r197$PRESC_NO$r197$, $r197$dpd.presc_no = dpm.presc_no$r197$, $r197$197历史SQL摄入候选（partial；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ORDER_STATUS <> ×1; 风险：half_key; 处方明细挂主档仅按 PRESC_NO 单列：完整键为 PRESC_NO+PRESC_DATE（S2F-A4F3F1FA73，S5 又补 23 条语句证据）。跨日处方号复用即错挂。S5-P006 验证单列放大。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-DC6165C54E", "stage": "S5", "statements": 1, "templates": 1, "files": ["抗菌药物出院患者总例数统计\\sql.txt"], "intake_state": "partial", "validation_state": "passed_in_scope", "validation_note": "本窗 PRESC_NO 0 复用（Q31）——单列本窗可用，跨日理论风险未观测", "probe_uids": ["Q31"], "risk_tags": ["half_key"], "notes": "处方明细挂主档仅按 PRESC_NO 单列：完整键为 PRESC_NO+PRESC_DATE（S2F-A4F3F1FA73，S5 又补 23 条语句证据）。跨日处方号复用即错挂。S5-P006 验证单列放大。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_PRESC_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PRESC_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PRESC_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PRESC_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$DATA_CENTER$r197$, $r197$YDHL.MCS_ORDER_SCHEDULE$r197$, $r197$WARD_CODE$r197$, $r197$DATA_CENTER$r197$, $r197$YDHL.WARDS$r197$, $r197$WARD_CODE$r197$, $r197$oms.ward_code = c.ward_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-6F156FC2B7", "stage": "S5", "statements": 1, "templates": 1, "files": ["护理夜间工作量.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$YDHL.MCS_ORDER_SCHEDULE$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$WARD_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$YDHL.WARDS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$WARD_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STOCK$r197$, $r197$STORAGE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STORAGE_DEPT$r197$, $r197$STORAGE_CODE$r197$, $r197$a.storage = b.storage_code$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-8D31D65915", "stage": "S5", "statements": 1, "templates": 1, "files": ["提取价表SQL.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_STOCK$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$STORAGE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STORAGE_DEPT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$STORAGE_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE+DRUG_SPEC+UNITS$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STOCK$r197$, $r197$DRUG_CODE+DRUG_SPEC+UNITS$r197$, $r197$a.drug_code = c.drug_code AND a.drug_spec = c.drug_spec AND a.units = c.units$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_STOCK:N → DRUG_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-91FCC96E1F", "stage": "S5", "statements": 1, "templates": 1, "files": ["提取价表SQL.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+UNITS$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STOCK$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+UNITS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.EXP_PRICE_LIST$r197$, $r197$EXP_CODE+FIRM_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$OUTPBILL.OUTP_BILL_ITEMS$r197$, $r197$ITEM_CODE+ITEM_SPEC$r197$, $r197$ep.exp_code = a.item_code AND ep.firm_id = a.item_spec$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ITEM_CLASS = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-C048B5E8F8", "stage": "S5", "statements": 1, "templates": 1, "files": ["高值耗材医保占比.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.EXP_PRICE_LIST$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$EXP_CODE+FIRM_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$OUTPBILL.OUTP_BILL_ITEMS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE+ITEM_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.EXP_PRICE_LIST$r197$, $r197$EXP_CODE+FIRM_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$ITEM_CODE+ITEM_SPEC$r197$, $r197$ep.exp_code = aa.item_code AND ep.firm_id = aa.item_spec$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】ITEM_CLASS = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-9328386622", "stage": "S5", "statements": 1, "templates": 1, "files": ["高值耗材医保占比.txt"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.EXP_PRICE_LIST$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$EXP_CODE+FIRM_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ITEM_CODE+ITEM_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$VISIT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.PATS_IN_HOSPITAL$r197$, $r197$VISIT_ID$r197$, $r197$PATS_IN_HOSPITAL.VISIT_ID = ORDERS.VISIT_ID$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：cross_patient_collision,half_key; 仅 VISIT_ID 单列连接 ORDERS↔PATS_IN_HOSPITAL：不同患者同 VISIT_ID 直接串号（住院万能键缺 PATIENT_ID）。同语句群已有完整键族 S2F-320B0458DF/S2F-1A98B5707E。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-AC0D6652C7", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年02月 14-27.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["cross_patient_collision", "half_key"], "notes": "仅 VISIT_ID 单列连接 ORDERS↔PATS_IN_HOSPITAL：不同患者同 VISIT_ID 直接串号（住院万能键缺 PATIENT_ID）。同语句群已有完整键族 S2F-320B0458DF/S2F-1A98B5707E。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$VISIT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$INPADM.PATS_IN_HOSPITAL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$VISIT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$ORDER_SUB_NO+ORDER_NO+VISIT_ID+PATIENT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS_COSTS$r197$, $r197$ORDER_SUB_NO+ORDER_NO+VISIT_ID+PATIENT_ID$r197$, $r197$ORDERS_COSTS.ORDER_SUB_NO(+) = ORDERS.ORDER_SUB_NO AND ORDERS_COSTS.ORDER_NO(+) = ORDERS.ORDER_NO AND ORDERS_COSTS.VISIT_ID(+) = ORDERS.VISIT_ID AND ORDERS_COSTS.PATIENT_ID(+) = ORDERS.PATIENT_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】BILLING_ATTR = ×2；【值域待确认】REPEAT_INDICATOR = ×1；【值域待确认】WARD_CODE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-F0EC7628AA", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年02月 14-27.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$ORDER_SUB_NO+ORDER_NO+VISIT_ID+PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS_COSTS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ORDER_SUB_NO+ORDER_NO+VISIT_ID+PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DEPT_VS_WARD$r197$, $r197$DEPT_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_PRE$r197$, $r197$ORDERED_BY$r197$, $r197$DRUG_DISPENSE_PRE.ORDERED_BY = DEPT_VS_WARD.DEPT_CODE$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_DISPENSE_PRE:N → DEPT_VS_WARD:1; 条件：; 风险：dict_semantics_pending; 摆药单开单科室(ORDERED_BY)挂 DEPT_VS_WARD（科室-病区对照表）而非 DEPT_DICT：若 ORDERED_BY 实为病区代码则成立，若为科室代码应挂 DEPT_DICT（S2 已有族）。语义待核。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-ABF2F6C279", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年02月 14-27.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["dict_semantics_pending"], "notes": "摆药单开单科室(ORDERED_BY)挂 DEPT_VS_WARD（科室-病区对照表）而非 DEPT_DICT：若 ORDERED_BY 实为病区代码则成立，若为科室代码应挂 DEPT_DICT（S2 已有族）。语义待核。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DEPT_VS_WARD$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DEPT_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_DISPENSE_PRE$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$ORDERED_BY$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_PRE$r197$, $r197$OPER_BATCH_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_REQ$r197$, $r197$OPER_BATCH_NO$r197$, $r197$DRUG_DISPENSE_PRE.OPER_BATCH_NO = DRUG_DISPENSE_REQ.OPER_BATCH_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-710F585ED1", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年02月 14-27.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_DISPENSE_PRE$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$OPER_BATCH_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_DISPENSE_REQ$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$OPER_BATCH_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PROVIDE_APPLICATION$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$DRUG_PROVIDE_APPLICATION.DRUG_CODE = DRUG_DICT.DRUG_CODE AND DRUG_PROVIDE_APPLICATION.DRUG_SPEC = DRUG_DICT.DRUG_SPEC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_PROVIDE_APPLICATION:N → DRUG_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-22DADEED18", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年02月 28-06.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PROVIDE_APPLICATION$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PROVIDE_APPLICATION$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STOCK$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$DRUG_PROVIDE_APPLICATION.DRUG_CODE = DRUG_STOCK.DRUG_CODE AND DRUG_PROVIDE_APPLICATION.DRUG_SPEC = DRUG_STOCK.DRUG_SPEC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】FLAG = ×2；【值域待确认】APPLICANT_STORAGE = ×1；【值域待确认】RECEIVER = ×1；【值域待确认】PROVIDE_STORAGE = ×1；【值域待确认】STORAGE = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-B1AC8D3067", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年02月 28-06.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_PROVIDE_APPLICATION$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STOCK$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_REC$r197$, $r197$DISPENSARY+DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENS_PROPERTY$r197$, $r197$DISPENSARY+DRUG_CODE$r197$, $r197$DRUG_DISPENSE_REC.DISPENSARY = DRUG_DISPENS_PROPERTY.DISPENSARY AND DRUG_DISPENSE_REC.DRUG_CODE = DRUG_DISPENS_PROPERTY.DRUG_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】DISPENSING_PROPERTY = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-A84F244F96", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年02月 8-13.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_DISPENSE_REC$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DISPENSARY+DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_DISPENS_PROPERTY$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DISPENSARY+DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$, $r197$QUANTITY+DRUG_SPEC+DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PROVIDE_APPLICATION$r197$, $r197$QUANTITY+DRUG_SPEC+DRUG_CODE$r197$, $r197$DRUG_EXPORT_DETAIL.QUANTITY = DRUG_PROVIDE_APPLICATION.QUANTITY AND DRUG_EXPORT_DETAIL.DRUG_SPEC = DRUG_PROVIDE_APPLICATION.DRUG_SPEC AND DRUG_EXPORT_DETAIL.DRUG_CODE = DRUG_PROVIDE_APPLICATION.DRUG_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】PROVIDE_STORAGE = ×2；【值域待确认】DOCUMENT_NO = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-D569E00977", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年03月 14-20.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$QUANTITY+DRUG_SPEC+DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PROVIDE_APPLICATION$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$QUANTITY+DRUG_SPEC+DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$, $r197$DRUG_SPEC+DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PROVIDE_APPLICATION$r197$, $r197$DRUG_SPEC+DRUG_CODE$r197$, $r197$DRUG_EXPORT_DETAIL.DRUG_SPEC = DRUG_PROVIDE_APPLICATION.DRUG_SPEC AND DRUG_EXPORT_DETAIL.DRUG_CODE = DRUG_PROVIDE_APPLICATION.DRUG_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】PROVIDE_STORAGE = ×2；【值域待确认】DOCUMENT_NO = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-AA125F5559", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年03月 14-20.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_SPEC+DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PROVIDE_APPLICATION$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_SPEC+DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$, $r197$DRUG_CODE+DRUG_SPEC+FIRM_ID+QUANTITY$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PROVIDE_APPLICATION$r197$, $r197$DRUG_CODE+DRUG_SPEC+FIRM_ID+QUANTITY$r197$, $r197$DRUG_EXPORT_DETAIL.DRUG_CODE = DRUG_PROVIDE_APPLICATION.DRUG_CODE AND DRUG_EXPORT_DETAIL.DRUG_SPEC = DRUG_PROVIDE_APPLICATION.DRUG_SPEC AND DRUG_EXPORT_DETAIL.FIRM_ID = DRUG_PROVIDE_APPLICATION.FIRM_ID AND DRUG_EXPORT_DETAIL.QUANTITY = DRUG_PROVIDE_APPLICATION.QUANTITY$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】APPLICANT_STORAGE = ×1；【值域待确认】DOCUMENT_NO = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-5AE8B0A597", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年03月 21-27.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$DRUG_USER.DRUG_EXPORT_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+FIRM_ID+QUANTITY$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PROVIDE_APPLICATION$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+FIRM_ID+QUANTITY$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_SPEC+DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$DRUG_SPEC+DRUG_CODE$r197$, $r197$DRUG_DICT.DRUG_SPEC = DRUG_PRICE_LIST.DRUG_SPEC AND DRUG_DICT.DRUG_CODE = DRUG_PRICE_LIST.DRUG_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-BF863C6D6B", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年08月 08-14.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_SPEC+DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_SPEC+DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STOCK$r197$, $r197$DRUG_CODE$r197$, $r197$DRUG_STOCK.DRUG_CODE = DRUG_DICT.DRUG_CODE$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_STOCK:N → DRUG_DICT:1; 条件：; 风险：half_key$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-7A9A5FB37B", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年08月 22-28.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STOCK$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STOCK$r197$, $r197$DRUG_SPEC$r197$, $r197$DRUG_DICT.DRUG_SPEC = DRUG_STOCK.DRUG_SPEC$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_STOCK:N → DRUG_DICT:1; 条件：; 风险：half_key$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-654F6FE714", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年08月 22-28.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STOCK$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$DRUG_CODE+MIN_SPEC+FIRM_ID+DRUG_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STOCK$r197$, $r197$DRUG_CODE+DRUG_SPEC+FIRM_ID+PACKAGE_SPEC$r197$, $r197$DRUG_STOCK.DRUG_CODE = C.DRUG_CODE AND DRUG_STOCK.DRUG_SPEC = C.MIN_SPEC AND DRUG_STOCK.FIRM_ID = C.FIRM_ID AND DRUG_STOCK.PACKAGE_SPEC = C.DRUG_SPEC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_STOCK:N → DRUG_PRICE_LIST:1; 条件：【值域待确认】SUPPLY_INDICATOR = ×1; 风险：price_effective_gap,unit_conversion_risk; 价表↔库存按最小规格换算对齐（DRUG_SPEC=MIN_SPEC、PACKAGE_SPEC=DRUG_SPEC 交叉）：单位换算语义，且语句未显式用价表生效期（有效期缺口与 RCP-S3-04 同族）。S5-P004 验证多价并存。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-D8F81B64AE", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年08月 22-28.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["price_effective_gap", "unit_conversion_risk"], "notes": "价表↔库存按最小规格换算对齐（DRUG_SPEC=MIN_SPEC、PACKAGE_SPEC=DRUG_SPEC 交叉）：单位换算语义，且语句未显式用价表生效期（有效期缺口与 RCP-S3-04 同族）。S5-P004 验证多价并存。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+MIN_SPEC+FIRM_ID+DRUG_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STOCK$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+FIRM_ID+PACKAGE_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_PRE$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO$r197$, $r197$ORDERS.PATIENT_ID = DRUG_DISPENSE_PRE.PATIENT_ID AND ORDERS.VISIT_ID = DRUG_DISPENSE_PRE.VISIT_ID AND ORDERS.ORDER_NO = DRUG_DISPENSE_PRE.ORDER_NO$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】OPER_BATCH_NO LIKE ×1; 风险：half_key; 摆药单挂医嘱三列缺 ORDER_SUB_NO：成组医嘱/多子行时放大。完整四列键族见同批 DRAFT:14 同构（ORDERS↔ORDERS_EXECUTE_DETAILS/ORDERS_COSTS 四列）。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-635760EBAB", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年08月 22-28.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": "摆药单挂医嘱三列缺 ORDER_SUB_NO：成组医嘱/多子行时放大。完整四列键族见同批 DRAFT:14 同构（ORDERS↔ORDERS_EXECUTE_DETAILS/ORDERS_COSTS 四列）。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_DISPENSE_PRE$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$EXAM.EXAM_MASTER$r197$, $r197$PATIENT_LOCAL_ID+LOCAL_ID_CLASS$r197$, $r197$HIS_SOURCE$r197$, $r197$EXAM.EXAM_PAT_MI$r197$, $r197$PATIENT_LOCAL_ID+LOCAL_ID_CLASS$r197$, $r197$EXAM_MASTER.PATIENT_LOCAL_ID = EXAM_PAT_MI.PATIENT_LOCAL_ID AND EXAM_MASTER.LOCAL_ID_CLASS = EXAM_PAT_MI.LOCAL_ID_CLASS$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】PERFORMED_BY = ×1；【值域待确认】CHARGE_TYPE LIKE ×1; 风险：exam_local_patient_index; 检查本地患者索引两列版（+证件类别）：键更完整，S5-P002 一并验证覆盖率。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-5E5767D1DB", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年08月 29-04.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["exam_local_patient_index"], "notes": "检查本地患者索引两列版（+证件类别）：键更完整，S5-P002 一并验证覆盖率。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$EXAM.EXAM_MASTER$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_LOCAL_ID+LOCAL_ID_CLASS$r197$,'')
    AND upper(r.to_table)=upper($r197$EXAM.EXAM_PAT_MI$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_LOCAL_ID+LOCAL_ID_CLASS$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPBILL.INP_BILL_DETAIL$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$LAB.LAB_TEST_MASTER$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$INP_BILL_DETAIL.PATIENT_ID(+) = LAB_TEST_MASTER.PATIENT_ID AND INP_BILL_DETAIL.VISIT_ID(+) = LAB_TEST_MASTER.VISIT_ID$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】SPECIMEN <> ×1；【值域待确认】VISIT_ID > ×1；【值域待确认】BILLING_INDICATOR = ×1; 风险：cross_theme,oper_code_multi_identity; 住院费用按 visit 键挂检验主档（outer）：费用挂检验的规范路径是 OPER_CODE 按费用类别分流（RCP-S3-07；检验类 OPER_CODE=APPOINT_NO 关系待 S5-P008 覆盖核验），visit 直连会把同次住院全部费用行×检验申请行放大。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-83EA9907EA", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年08月 29-04.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["cross_theme", "oper_code_multi_identity"], "notes": "住院费用按 visit 键挂检验主档（outer）：费用挂检验的规范路径是 OPER_CODE 按费用类别分流（RCP-S3-07；检验类 OPER_CODE=APPOINT_NO 关系待 S5-P008 覆盖核验），visit 直连会把同次住院全部费用行×检验申请行放大。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPBILL.INP_BILL_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$LAB.LAB_TEST_MASTER$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$DRUG_CODE+DRUG_SPEC+FIRM_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_STOCK$r197$, $r197$DRUG_CODE+PACKAGE_SPEC+FIRM_ID$r197$, $r197$B.DRUG_CODE = A.DRUG_CODE AND B.DRUG_SPEC = A.PACKAGE_SPEC AND B.FIRM_ID = A.FIRM_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_STOCK:N → DRUG_PRICE_LIST:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-2F56B5102B", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年09月 19-25.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC+FIRM_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_STOCK$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+PACKAGE_SPEC+FIRM_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_NAME_DICT$r197$, $r197$DRUG_CODE$r197$, $r197$D.DRUG_CODE = C.DRUG_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_NAME_DICT:N → DRUG_DICT:1; 条件：【值域待确认】DRUG_INDICATOR = ×2；【值域待确认】SUPPLY_INDICATOR = ×1；【值域待确认】QUANTITY > ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-B99E6BD99E", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年09月 19-25.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.DRUG_NAME_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_REC$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO$r197$, $r197$ORDERS.PATIENT_ID = DRUG_DISPENSE_REC.PATIENT_ID AND ORDERS.VISIT_ID = DRUG_DISPENSE_REC.VISIT_ID AND ORDERS.ORDER_NO = DRUG_DISPENSE_REC.ORDER_NO$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】PATIENT_ID = ×1；【值域待确认】VISIT_ID = ×1; 风险：half_key; 同上：摆药记录三列版缺 ORDER_SUB_NO。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-9F3095B783", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年10月 03-16.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": "同上：摆药记录三列版缺 ORDER_SUB_NO。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_DISPENSE_REC$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.EXP_DICT$r197$, $r197$EXP_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.EXP_NAME_DICT$r197$, $r197$EXP_CODE$r197$, $r197$EXP_DICT.EXP_CODE = EXP_NAME_DICT.EXP_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-79264C1422", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年10月 24-30.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.EXP_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$EXP_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.EXP_NAME_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$EXP_CODE$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_DETAIL_TEMP$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$DRUG_DICT.DRUG_CODE = DRUG_PRESC_DETAIL_TEMP.DRUG_CODE AND DRUG_DICT.DRUG_SPEC = DRUG_PRESC_DETAIL_TEMP.DRUG_SPEC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_PRESC_DETAIL_TEMP:N → DRUG_DICT:1; 条件：【值域待确认】PRESC_NO = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-67F4C2968F", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年10月 24-30.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PRESC_DETAIL_TEMP$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DOCT_DRUG_PRESC_DETAIL$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$DRUG_DICT.DRUG_CODE = DOCT_DRUG_PRESC_DETAIL.DRUG_CODE AND DRUG_DICT.DRUG_SPEC = DOCT_DRUG_PRESC_DETAIL.DRUG_SPEC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DOCT_DRUG_PRESC_DETAIL:N → DRUG_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-8958129949", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年10月 24-30.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DOCT_DRUG_PRESC_DETAIL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$LAB.LAB_RESULT$r197$, $r197$TEST_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$LAB.LAB_TEST_ITEMS$r197$, $r197$TEST_NO$r197$, $r197$LAB_RESULT.TEST_NO = LAB_TEST_ITEMS.TEST_NO$r197$, $r197$197历史SQL摄入候选（partial；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：; 风险：amplification_risk,half_key; LAB_RESULT（结果行，TEST_NO×ITEM_NO 粒度）按 TEST_NO 单列挂 LAB_TEST_ITEMS（项目行，同粒度）：单列连接退化为 M:N，每申请单结果行×项目行交叉放大。正确项目级键 = TEST_NO+ITEM_NO（S2F-67F8789EE2，本批再补 2 条）。S5-P001 对比两键行数放大。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-F004BB9BB0", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年10月 31-06.sql"], "intake_state": "partial", "validation_state": "passed_in_scope", "validation_note": "本窗单列 TEST_NO 连接未放大（项目≈1/申请，Q24）——Panel 场景仍建议两列键", "probe_uids": ["Q24"], "risk_tags": ["amplification_risk", "half_key"], "notes": "LAB_RESULT（结果行，TEST_NO×ITEM_NO 粒度）按 TEST_NO 单列挂 LAB_TEST_ITEMS（项目行，同粒度）：单列连接退化为 M:N，每申请单结果行×项目行交叉放大。正确项目级键 = TEST_NO+ITEM_NO（S2F-67F8789EE2，本批再补 2 条）。S5-P001 对比两键行数放大。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$LAB.LAB_RESULT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$TEST_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$LAB.LAB_TEST_ITEMS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$TEST_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS_ANTI_DRUG$r197$, $r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$, $r197$ORDERS.PATIENT_ID = ORDERS_ANTI_DRUG.PATIENT_ID AND ORDERS.VISIT_ID = ORDERS_ANTI_DRUG.VISIT_ID AND ORDERS.ORDER_NO = ORDERS_ANTI_DRUG.ORDER_NO AND ORDERS.ORDER_SUB_NO = ORDERS_ANTI_DRUG.ORDER_SUB_NO$r197$, $r197$197历史SQL摄入候选（candidate；验证：passed_in_scope）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】EXPERT_FLAG = ×1; 风险：; 抗菌药物医嘱表四列键（F0367 抗菌药物统计）：与 ORDERS_EXECUTE_DETAILS/ORDERS_COSTS 同键型。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-AB4C2AA3D7", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2022年11月 21-26.sql"], "intake_state": "candidate", "validation_state": "passed_in_scope", "validation_note": "7 行命中（Q33，样本小但成立）", "probe_uids": ["Q33"], "risk_tags": [], "notes": "抗菌药物医嘱表四列键（F0367 抗菌药物统计）：与 ORDERS_EXECUTE_DETAILS/ORDERS_COSTS 同键型。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$ORDADM.ORDERS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$,'')
    AND upper(r.to_table)=upper($r197$ORDADM.ORDERS_ANTI_DRUG$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID+ORDER_NO+ORDER_SUB_NO$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$ORDADM.ORDERS_EXECUTE_DETAILS$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.PATS_IN_HOSPITAL$r197$, $r197$PATIENT_ID+VISIT_ID$r197$, $r197$PATS_IN_HOSPITAL.PATIENT_ID = ORDERS_EXECUTE_DETAILS.PATIENT_ID AND PATS_IN_HOSPITAL.VISIT_ID = ORDERS_EXECUTE_DETAILS.VISIT_ID$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】REPEAT_INDICATOR = ×1; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-6D34594CB9", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\2023年01月 09-15.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$ORDADM.ORDERS_EXECUTE_DETAILS$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$INPADM.PATS_IN_HOSPITAL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID+VISIT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.PATS_IN_HOSPITAL$r197$, $r197$PATIENT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.PRE_DISCHGED_PATS$r197$, $r197$PATIENT_ID$r197$, $r197$PATS_IN_HOSPITAL.PATIENT_ID = PRE_DISCHGED_PATS.PATIENT_ID$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：事实间关联（收费/结算/手术/字典对照等）; 基数：待验证（方向按证据语句保留）; 条件：【值域待确认】DISPENSARY = ×1；【值域待确认】ORDER_CLASS = ×1; 风险：half_key; 预出院患者表挂 PATIENT_ID 单列：同患者历史多次住院是否清理需核（若表保留历史住院则放大）。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-9EF4214B31", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\医嘱摆药SQL.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": "预出院患者表挂 PATIENT_ID 单列：同患者历史多次住院是否清理需核（若表保留历史住院则放大）。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPADM.PATS_IN_HOSPITAL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$INPADM.PRE_DISCHGED_PATS$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_DICT$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_PRESC_DETAIL$r197$, $r197$DRUG_CODE+DRUG_SPEC$r197$, $r197$B.DRUG_CODE = F.DRUG_CODE AND B.DRUG_SPEC = F.DRUG_SPEC$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_PRESC_DETAIL:N → DRUG_DICT:1; 条件：; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-D2BC6F1F4D", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\可用.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$COMM.DRUG_DICT$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
    AND upper(r.to_table)=upper($r197$PHARMACY.DRUG_PRESC_DETAIL$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$DRUG_CODE+DRUG_SPEC$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$INPADM.PATS_IN_HOSPITAL$r197$, $r197$PATIENT_ID$r197$, $r197$HIS_SOURCE$r197$, $r197$MEDREC.PAT_VISIT$r197$, $r197$PATIENT_ID$r197$, $r197$C.PATIENT_ID = D.PATIENT_ID$r197$, $r197$197历史SQL摄入候选（partial；验证：not_run）$r197$, $r197$粒度：患者级（缺 VISIT_ID，半键疑点）; 基数：PATS_IN_HOSPITAL:N → PAT_VISIT:1（按 PATIENT_ID）; 条件：【值域待确认】AS_TOXIN = ×2；【值域待确认】AS_FORM = ×2；【值域待确认】PRESC_SOURCE = ×1；【值域待确认】AS_DRUGCODE = ×1；【值域待确认】AS_ORDERED_BY = ×1; 风险：half_key; 在院表挂住院主档缺 VISIT_ID：同患者多次住院全部命中。完整键族 S2F-8949408577（+VISIT_ID）已有。$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-6EB49E7BE9", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\可用.sql"], "intake_state": "partial", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": ["half_key"], "notes": "在院表挂住院主档缺 VISIT_ID：同患者多次住院全部命中。完整键族 S2F-8949408577（+VISIT_ID）已有。"}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$INPADM.PATS_IN_HOSPITAL$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
    AND upper(r.to_table)=upper($r197$MEDREC.PAT_VISIT$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$PATIENT_ID$r197$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r197$r197_intake$r197$, $r197$HIS_SOURCE$r197$, $r197$PHARMACY.DRUG_DISPENSE_REC$r197$, $r197$FIRM_ID+DRUG_SPEC+DRUG_CODE$r197$, $r197$HIS_SOURCE$r197$, $r197$COMM.DRUG_PRICE_LIST$r197$, $r197$FIRM_ID+DRUG_SPEC+DRUG_CODE$r197$, $r197$E.FIRM_ID = F.FIRM_ID AND E.DRUG_SPEC = F.DRUG_SPEC AND E.DRUG_CODE = F.DRUG_CODE$r197$, $r197$197历史SQL摄入候选（candidate；验证：not_run）$r197$, $r197$粒度：字典取值维度; 基数：DRUG_DISPENSE_REC:N → DRUG_PRICE_LIST:1; 条件：【值域待确认】STD_INDICATOR = ×2; 风险：$r197$, $r197$C$r197$, 'draft', $r197${"run_id": "r197-20260921-s1", "relation_id": "S5F-2FBB4EFCCD", "stage": "S5", "statements": 1, "templates": 1, "files": ["A_F0138::SQL\\结余留用-可用.sql"], "intake_state": "candidate", "validation_state": "not_run", "validation_note": null, "probe_uids": null, "risk_tags": [], "notes": null}$r197$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r197$r197_intake$r197$
    AND upper(r.from_table)=upper($r197$PHARMACY.DRUG_DISPENSE_REC$r197$) AND coalesce(r.from_columns,'')=coalesce($r197$FIRM_ID+DRUG_SPEC+DRUG_CODE$r197$,'')
    AND upper(r.to_table)=upper($r197$COMM.DRUG_PRICE_LIST$r197$) AND coalesce(r.to_columns,'')=coalesce($r197$FIRM_ID+DRUG_SPEC+DRUG_CODE$r197$,'')
);

INSERT INTO asset.asset_govern_audit_logs
(module, entity_type, entity_ref, action, before_data, after_data, operator, reason, created_at)
VALUES (
  $r197$relation_intake$r197$,
  $r197$asset_relation_reviews$r197$,
  $r197$r197-20260921-s1$r197$,
  $r197$batch_insert_draft$r197$,
  '{"before": {"r197_intake_rows": 0, "total_reviews": 674}}'::jsonb,
  '{"after": {"insert_expected": 167, "payload_sha256_prefix": "690a0a7b10e68224", "source": "197号董哥历史SQL关系核验", "backup": "/opt/data-asset/backup/data_asset_pre_r197_20260921.dump", "backup_sha256_prefix": "f12a47cce3021230"}}'::jsonb,
  $r197$ai:r197-intake$r197$,
  $r197$用户2026-09-21批准S7生产入库：167条r197_intake草稿，单事务，批次级撤销=DELETE WHERE relation_scope=r197_intake$r197$,
  now());

DO $$
DECLARE n int; t int;
BEGIN
  SELECT count(*) INTO n FROM asset.asset_relation_reviews WHERE relation_scope = 'r197_intake';
  SELECT count(*) INTO t FROM asset.asset_relation_reviews;
  IF n <> 167 OR t <> 841 THEN
    RAISE EXCEPTION 'r197_intake 行数守卫失败: scope=% (期望167) total=% (期望841)，事务回滚', n, t;
  END IF;
END $$;
