BEGIN;
-- r195 S7 生产入库 | 单事务执行: psql -1 -v ON_ERROR_STOP=1
-- run_id=r195-20260919-084932 | payload SHA-256 前16: e9bb821cc2636255 | 2026-09-20 用户批准

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD36$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$t3.段落编号 = t1.id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ADMISSION_DEAD_RECORD_TF$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\24小时内入院死亡记录_v_emr_admission_dead_record_tf.sql"], "view_names": ["ODS.V_EMR_ADMISSION_DEAD_RECORD_TF"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "2", "raw": "d2.diagnosis_type = '2'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "1", "raw": "d1.diagnosis_type = '1'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                           '-'\n                       )\n                   ),\n         "}], "fragments": ["t3.段落编号 = t1.id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD36$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD_CONTENT$r195$, $r195$UHID+段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$UHID+ID$r195$, $r195$t4.uhid = t1.uhid AND t4.段落编号 = t1.id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ADMISSION_DEAD_RECORD_TF,ODS.V_EMR_INFOR_OPERATION$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\24小时内入院死亡记录_v_emr_admission_dead_record_tf.sql", "三甲完成视图\\手术知情同意书_v_emr_infor_operation.sql"], "view_names": ["ODS.V_EMR_ADMISSION_DEAD_RECORD_TF", "ODS.V_EMR_INFOR_OPERATION"], "join_type": "JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "2", "raw": "d2.diagnosis_type = '2'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "1", "raw": "d1.diagnosis_type = '1'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                           '-'\n                       )\n                   ),\n         "}], "fragments": ["t4.uhid = t1.uhid", "t4.段落编号 = t1.id", "t4.uhid = t1.uhid"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD_CONTENT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$UHID+段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$UHID+ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT_DOCINDEX$r195$, $r195$P_INPATIENT_TIMES$r195$, $r195$t.p_inpatient_times = ttt.visit_id AND pv.visit_id = t.p_inpatient_times$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ADMISSION_DEAD_RECORD_TF,ODS.V_EMR_ADMISSION_RECORD,ODS.V_EMR_DISCHARGE_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\24小时内入院死亡记录_v_emr_admission_dead_record_tf.sql", "三甲完成视图\\一般手术记录_v_emr_opera_record.sql", "三甲完成视图\\住院医师交接班记录_v_EMR_HOS_SUCCESSION_RECORD.sql", "三甲完成视图\\入院记录(D08标）_v_EMR_ADMISSION_RECORD.sql", "三甲完成视图\\其它知情同意书_v_EMR_INFOR_OTHERS.sql", "三甲完成视图\\出院记录(D12标）_v_EMR_DISCHARGE_RECORD.sql", "三甲完成视图\\手术知情同意书_v_emr_infor_operation.sql", "三甲完成视图\\抢救记录_v_EMR_HOS_SAVE_RECORD.sql", "三甲完成视图\\死亡病历讨论记录_v_EMR_HOS_DND_RECORD.sql", "三甲完成视图\\特殊检查及特殊治疗同意书_v_emr_infor_spec_exam_treat.sql", "三甲完成视图\\电子病历汇总_V_EMR_MEDICAL_RECORD_INFO.sql", "三甲完成视图\\疑难病例讨论记录_v_EMR_HOS_DIFFIC_CASE_DISCUSS.sql", "三甲完成视图\\病危(重)通知书_v_emr_infor_critically_ill.sql", "三甲完成视图\\转科记录_v_EMR_HOS_CHANGE_MAJOR_RECORD.sql"], "view_names": ["ODS.V_EMR_ADMISSION_DEAD_RECORD_TF", "ODS.V_EMR_ADMISSION_RECORD", "ODS.V_EMR_DISCHARGE_RECORD", "ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD", "ODS.V_EMR_HOS_DIFFIC_CASE_DISCUSS", "ODS.V_EMR_HOS_DND_RECORD", "ODS.V_EMR_HOS_SAVE_RECORD", "ODS.V_EMR_HOS_SUCCESSION_RECORD", "ODS.V_EMR_INFOR_CRITICALLY_ILL", "ODS.V_EMR_INFOR_OPERATION", "ODS.V_EMR_INFOR_OTHERS", "ODS.V_EMR_INFOR_SPEC_EXAM_TREAT", "ODS.V_EMR_MEDICAL_RECORD_INFO", "ODS.V_EMR_OPERA_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "2", "raw": "d2.diagnosis_type = '2'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "1", "raw": "d1.diagnosis_type = '1'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                           '-'\n                       )\n                   ),\n         "}], "fragments": ["t.p_inpatient_times = ttt.visit_id", "pv.visit_id = t.p_inpatient_times", "pv.visit_id = t.p_inpatient_times"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT_DOCINDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$P_INPATIENT_TIMES$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DIAGNOSIS$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$ttt.patient_id = d2.patient_id AND ttt.visit_id = d2.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.EMR_DISCHARGE_RECORD_DIAGNOSIS,ODS.V_EMR_ADMISSION_DEAD_RECORD_TF,ODS.V_EMR_ADMISSION_DEAD_RECORD_TF_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\24小时内入院死亡记录_v_emr_admission_dead_record_tf.sql", "三甲完成视图\\24小时内入院死亡记录_v_emr_admission_dead_record_tf_jhemr.sql", "三甲完成视图\\住院病案首页-诊断(电子病历)(辅D09_D10标）_V_EMR_ICH_DIAGNOSIS.sql", "三甲完成视图\\入院诊断表_v_EMR_ADMISSION_DIAGNOSIS.sql", "三甲完成视图\\出院记录(D12标）_v_EMR_DISCHARGE_RECORD.sql", "三甲完成视图\\出院记录(D12标）_v_EMR_DISCHARGE_RECORD_jhemr.sql", "三甲完成视图\\出院记录-诊断(辅D12标）_EMR_DISCHARGE_RECORD_DIAGNOSIS.sql", "三甲完成视图\\病危(重)通知书_v_emr_infor_critically_ill.sql", "三甲完成视图\\病危(重)通知书_v_emr_infor_critically_ill_jhemr.sql"], "view_names": ["ODS.EMR_DISCHARGE_RECORD_DIAGNOSIS", "ODS.V_EMR_ADMISSION_DEAD_RECORD_TF", "ODS.V_EMR_ADMISSION_DEAD_RECORD_TF_JHEMR", "ODS.V_EMR_ADMISSION_DIAGNOSIS", "ODS.V_EMR_DISCHARGE_RECORD", "ODS.V_EMR_DISCHARGE_RECORD_JHEMR", "ODS.V_EMR_ICH_DIAGNOSIS", "ODS.V_EMR_INFOR_CRITICALLY_ILL", "ODS.V_EMR_INFOR_CRITICALLY_ILL_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "2", "raw": "d2.diagnosis_type = '2'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "1", "raw": "d1.diagnosis_type = '1'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                           '-'\n                       )\n                   ),\n         "}], "fragments": ["ttt.patient_id = d2.patient_id", "ttt.visit_id = d2.visit_id", "ttt.patient_id = d1.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DIAGNOSIS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$JHEMR.JHMR_FILE_CONTENT_TEXT$r195$, $r195$FILE_UNIQUE_ID$r195$, $r195$DATA_CENTER$r195$, $r195$JHEMR.JHMR_FILE_INDEX$r195$, $r195$FILE_UNIQUE_ID+ID$r195$, $r195$t4.FILE_UNIQUE_ID = t1.FILE_UNIQUE_ID AND t4.FILE_UNIQUE_ID = t1.id$r195$, $r195$195三甲视图摄入候选（partial_or_keysubset）$r195$, $r195$涉及视图: ODS.V_EMR_ADMISSION_DEAD_RECORD_TF_JHEMR,ODS.V_EMR_DISCHARGE_RECORD_JHEMR,ODS.V_EMR_INFOR_OPERATION_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\24小时内入院死亡记录_v_emr_admission_dead_record_tf_jhemr.sql", "三甲完成视图\\一般手术记录_v_emr_opera_record_jhemr.sql", "三甲完成视图\\出院记录(D12标）_v_EMR_DISCHARGE_RECORD_jhemr.sql", "三甲完成视图\\手术知情同意书_v_emr_infor_operation_jhemr.sql"], "view_names": ["ODS.V_EMR_ADMISSION_DEAD_RECORD_TF_JHEMR", "ODS.V_EMR_DISCHARGE_RECORD_JHEMR", "ODS.V_EMR_INFOR_OPERATION_JHEMR", "ODS.V_EMR_OPERA_RECORD_JHEMR"], "join_type": "JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "2", "raw": "d2.diagnosis_type = '2'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "1", "raw": "d1.diagnosis_type = '1'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                           '-'\n                       )\n                   ),\n         "}], "fragments": ["t4.FILE_UNIQUE_ID = t1.FILE_UNIQUE_ID", "t4.FILE_UNIQUE_ID = t1.id", "t4.FILE_UNIQUE_ID = t.FILE_UNIQUE_ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$JHEMR.JHMR_FILE_CONTENT_TEXT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$FILE_UNIQUE_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$JHEMR.JHMR_FILE_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$FILE_UNIQUE_ID+ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$INP_NO$r195$, $r195$DATA_CENTER$r195$, $r195$JHEMR.JHMR_FILE_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$t.PATIENT_ID = tt.inp_no AND t3.PATIENT_ID = t1.inp_no$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ADMISSION_DEAD_RECORD_TF_JHEMR,ODS.V_EMR_DISCHARGE_RECORD_JHEMR,ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\24小时内入院死亡记录_v_emr_admission_dead_record_tf_jhemr.sql", "三甲完成视图\\出院记录(D12标）_v_EMR_DISCHARGE_RECORD_jhemr.sql", "三甲完成视图\\死亡病历讨论记录_v_EMR_HOS_DND_RECORD_jhemr.sql", "三甲完成视图\\疑难病例讨论记录_v_EMR_HOS_DIFFIC_CASE_DISCUSS_jhemr.sql", "三甲完成视图\\转科记录_v_EMR_HOS_CHANGE_MAJOR_RECORD_jhemr.sql"], "view_names": ["ODS.V_EMR_ADMISSION_DEAD_RECORD_TF_JHEMR", "ODS.V_EMR_DISCHARGE_RECORD_JHEMR", "ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD_JHEMR", "ODS.V_EMR_HOS_DIFFIC_CASE_DISCUSS_JHEMR", "ODS.V_EMR_HOS_DND_RECORD_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "2", "raw": "d2.diagnosis_type = '2'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "1", "raw": "d1.diagnosis_type = '1'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                           '-'\n                       )\n                   ),\n         "}], "fragments": ["t.PATIENT_ID = tt.inp_no", "t3.PATIENT_ID = t1.inp_no", "t.PATIENT_ID = tt.inp_no"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$INP_NO$r195$,'')
    AND upper(r.to_table)=upper($r195$JHEMR.JHMR_FILE_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$JHEMR.JHMR_FILE_INDEX$r195$, $r195$VISIT_ID$r195$, $r195$t.VISIT_ID = ttt.visit_id AND pv.visit_id = t.VISIT_ID$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ADMISSION_DEAD_RECORD_TF_JHEMR,ODS.V_EMR_ADMISSION_RECORD_JHEMR,ODS.V_EMR_DISCHARGE_RECORD_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\24小时内入院死亡记录_v_emr_admission_dead_record_tf_jhemr.sql", "三甲完成视图\\一般手术记录_v_emr_opera_record_jhemr.sql", "三甲完成视图\\住院医师交接班记录_v_EMR_HOS_SUCCESSION_RECORD_jhemr.sql", "三甲完成视图\\入院记录(D08标）_v_EMR_ADMISSION_RECORD_jhemr.sql", "三甲完成视图\\其它知情同意书_v_EMR_INFOR_OTHERS_jhemr.sql", "三甲完成视图\\出院记录(D12标）_v_EMR_DISCHARGE_RECORD_jhemr.sql", "三甲完成视图\\手术知情同意书_v_emr_infor_operation_jhemr.sql", "三甲完成视图\\抢救记录_v_EMR_HOS_SAVE_RECORD_jhemr.sql", "三甲完成视图\\死亡病历讨论记录_v_EMR_HOS_DND_RECORD_jhemr.sql", "三甲完成视图\\特殊检查及特殊治疗同意书_v_emr_infor_spec_exam_treat_jhemr.sql", "三甲完成视图\\电子病历汇总_V_EMR_MEDICAL_RECORD_INFO_jhemr.sql", "三甲完成视图\\疑难病例讨论记录_v_EMR_HOS_DIFFIC_CASE_DISCUSS_jhemr.sql", "三甲完成视图\\病危(重)通知书_v_emr_infor_critically_ill_jhemr.sql", "三甲完成视图\\转科记录_v_EMR_HOS_CHANGE_MAJOR_RECORD_jhemr.sql"], "view_names": ["ODS.V_EMR_ADMISSION_DEAD_RECORD_TF_JHEMR", "ODS.V_EMR_ADMISSION_RECORD_JHEMR", "ODS.V_EMR_DISCHARGE_RECORD_JHEMR", "ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD_JHEMR", "ODS.V_EMR_HOS_DIFFIC_CASE_DISCUSS_JHEMR", "ODS.V_EMR_HOS_DND_RECORD_JHEMR", "ODS.V_EMR_HOS_SAVE_RECORD_JHEMR", "ODS.V_EMR_HOS_SUCCESSION_RECORD_JHEMR", "ODS.V_EMR_INFOR_CRITICALLY_ILL_JHEMR", "ODS.V_EMR_INFOR_OPERATION_JHEMR", "ODS.V_EMR_INFOR_OTHERS_JHEMR", "ODS.V_EMR_INFOR_SPEC_EXAM_TREAT_JHEMR", "ODS.V_EMR_MEDICAL_RECORD_INFO_JHEMR", "ODS.V_EMR_OPERA_RECORD_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "2", "raw": "d2.diagnosis_type = '2'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "1", "raw": "d1.diagnosis_type = '1'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                           '-'\n                       )\n                   ),\n         "}], "fragments": ["t.VISIT_ID = ttt.visit_id", "pv.visit_id = t.VISIT_ID", "pv.visit_id = t.VISIT_ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$JHEMR.JHMR_FILE_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD9$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$t3.段落编号 = t1.id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OPERA_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\一般手术记录_v_emr_opera_record.sql"], "view_names": ["ODS.V_EMR_OPERA_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1), (select cast(sd.name as varchar2(50))\n                                   from his.staff"}, {"kind": "rownum_limit", "raw": "rownum = 1 )),              '-')     as SURGEON_NAME, \n\n               substr(\n                   nv"}, {"kind": "rownum_limit", "raw": "rownum = 1)\n                           else cast(t3.qxhsxm as varchar2(50))\n                       e"}], "fragments": ["t3.段落编号 = t1.id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD9$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$mom.patient_id = pv.patient_id AND mom.visit_id = pv.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ANES_AFTER_RECORD,ODS.V_EMR_ANES_RECORD_MED,ODS.V_EMR_BOFORE_OPERA_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\一般手术记录_v_emr_opera_record.sql", "三甲完成视图\\一般手术记录_v_emr_opera_record_jhemr.sql", "三甲完成视图\\手术护理记录_v_emr_operation_nursing.sql", "三甲完成视图\\麻醉手术中用药记录_v_EMR_ANES_RECORD_MED.sql", "三甲完成视图\\麻醉术前访视记录_v_EMR_BOFORE_OPERA_RECORD.sql", "三甲完成视图\\麻醉术后访视记录_v_EMR_ANES_AFTER_RECORD.sql", "三甲完成视图\\麻醉知情同意书_v_emr_infor_anesthesia.sql"], "view_names": ["ODS.V_EMR_ANES_AFTER_RECORD", "ODS.V_EMR_ANES_RECORD_MED", "ODS.V_EMR_BOFORE_OPERA_RECORD", "ODS.V_EMR_INFOR_ANESTHESIA", "ODS.V_EMR_OPERATION_NURSING", "ODS.V_EMR_OPERA_RECORD", "ODS.V_EMR_OPERA_RECORD_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1), (select cast(sd.name as varchar2(50))\n                                   from his.staff"}, {"kind": "rownum_limit", "raw": "rownum = 1 )),              '-')     as SURGEON_NAME, \n\n               substr(\n                   nv"}, {"kind": "rownum_limit", "raw": "rownum = 1)\n                           else cast(t3.qxhsxm as varchar2(50))\n                       e"}], "fragments": ["mom.patient_id = pv.patient_id", "mom.visit_id = pv.visit_id", "mom.patient_id = pv.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_DIAGNOSIS_DICT$r195$, $r195$DIAGNOSIS_NAME$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$DIAG_BEFORE_OPERATION$r195$, $r195$mom.diag_before_operation = c.diagnosis_name AND mom.diag_before_operation = c.diagnosis_name$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OPERA_RECORD,ODS.V_EMR_OPERA_RECORD_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\一般手术记录_v_emr_opera_record.sql", "三甲完成视图\\一般手术记录_v_emr_opera_record_jhemr.sql"], "view_names": ["ODS.V_EMR_OPERA_RECORD", "ODS.V_EMR_OPERA_RECORD_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1), (select cast(sd.name as varchar2(50))\n                                   from his.staff"}, {"kind": "rownum_limit", "raw": "rownum = 1 )),              '-')     as SURGEON_NAME, \n\n               substr(\n                   nv"}, {"kind": "rownum_limit", "raw": "rownum = 1)\n                           else cast(t3.qxhsxm as varchar2(50))\n                       e"}], "fragments": ["mom.diag_before_operation = c.diagnosis_name", "mom.diag_before_operation = c.diagnosis_name"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$SM.MED_DIAGNOSIS_DICT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$DIAGNOSIS_NAME$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$DIAG_BEFORE_OPERATION$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD_CONTENT$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$t4.段落编号 = t1.id AND t4.段落编号=T1.ID$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ADMISSION_RECORD,ODS.V_EMR_DISCHARGE_RECORD,ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\一般手术记录_v_emr_opera_record.sql", "三甲完成视图\\入院记录(D08标）_v_EMR_ADMISSION_RECORD.sql", "三甲完成视图\\出院记录(D12标）_v_EMR_DISCHARGE_RECORD.sql", "三甲完成视图\\术前讨论与小结_v_EMR_HOS_PREOP_DISCUSS.sql", "三甲完成视图\\术后首次病程记录_v_EMR_HOS_POSTOPER_RECORD.sql", "三甲完成视图\\转科记录_v_EMR_HOS_CHANGE_MAJOR_RECORD.sql"], "view_names": ["ODS.V_EMR_ADMISSION_RECORD", "ODS.V_EMR_DISCHARGE_RECORD", "ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD", "ODS.V_EMR_HOS_POSTOPER_RECORD", "ODS.V_EMR_HOS_PREOP_DISCUSS", "ODS.V_EMR_OPERA_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1), (select cast(sd.name as varchar2(50))\n                                   from his.staff"}, {"kind": "rownum_limit", "raw": "rownum = 1 )),              '-')     as SURGEON_NAME, \n\n               substr(\n                   nv"}, {"kind": "rownum_limit", "raw": "rownum = 1)\n                           else cast(t3.qxhsxm as varchar2(50))\n                       e"}], "fragments": ["t4.段落编号 = t1.id", "t4.段落编号=T1.ID", "t5.段落编号 = t4.id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD_CONTENT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$JHEMR.JHMR_FILE_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$pmi.patient_id = t.PATIENT_ID AND t.PATIENT_ID = pmi.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ADMISSION_RECORD_JHEMR,ODS.V_EMR_HOS_SAVE_RECORD_JHEMR,ODS.V_EMR_HOS_SUCCESSION_RECORD_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\一般手术记录_v_emr_opera_record_jhemr.sql", "三甲完成视图\\住院医师交接班记录_v_EMR_HOS_SUCCESSION_RECORD_jhemr.sql", "三甲完成视图\\入院记录(D08标）_v_EMR_ADMISSION_RECORD_jhemr.sql", "三甲完成视图\\其它知情同意书_v_EMR_INFOR_OTHERS_jhemr.sql", "三甲完成视图\\手术知情同意书_v_emr_infor_operation_jhemr.sql", "三甲完成视图\\抢救记录_v_EMR_HOS_SAVE_RECORD_jhemr.sql", "三甲完成视图\\特殊检查及特殊治疗同意书_v_emr_infor_spec_exam_treat_jhemr.sql", "三甲完成视图\\电子病历汇总_V_EMR_MEDICAL_RECORD_INFO_jhemr.sql", "三甲完成视图\\病危(重)通知书_v_emr_infor_critically_ill_jhemr.sql"], "view_names": ["ODS.V_EMR_ADMISSION_RECORD_JHEMR", "ODS.V_EMR_HOS_SAVE_RECORD_JHEMR", "ODS.V_EMR_HOS_SUCCESSION_RECORD_JHEMR", "ODS.V_EMR_INFOR_CRITICALLY_ILL_JHEMR", "ODS.V_EMR_INFOR_OPERATION_JHEMR", "ODS.V_EMR_INFOR_OTHERS_JHEMR", "ODS.V_EMR_INFOR_SPEC_EXAM_TREAT_JHEMR", "ODS.V_EMR_MEDICAL_RECORD_INFO_JHEMR", "ODS.V_EMR_OPERA_RECORD_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1), (select cast(sd.name as varchar2(50))\n                                   from his.staff"}, {"kind": "rownum_limit", "raw": "rownum = 1 )),              '-')     as SURGEON_NAME, \n\n               substr(\n                   nv"}, {"kind": "rownum_limit", "raw": "rownum = 1)\n                           else cast(CAST(NULL AS VARCHAR2(4000)) as varchar2(50))\n     "}], "fragments": ["pmi.patient_id = t.PATIENT_ID", "t.PATIENT_ID = pmi.patient_id", "tt.PATIENT_ID = pmi.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$JHEMR.JHMR_FILE_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.INPATIENTS$r195$, $r195$PAT_INDEX_NO$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.MCS_DOC_FORM$r195$, $r195$PATIENT_UID$r195$, $r195$f.PATIENT_UID = p.pat_index_no AND f.PATIENT_UID = YDZD.pat_index_no$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: LUNA_MCS_SDSEY.V_EMR_CHILDBIRTH,LUNA_MCS_SDSEY.V_EMR_CRITICALLY_ILL_NURS,LUNA_MCS_SDSEY.V_EMR_DISCHARGE_ASSESSMENT$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\一般护理记录_v_EMR_GENERAL_NURSING.sql", "三甲完成视图\\出院评估与指导_v_EMR_DISCHARGE_ASSESSMENT.sql", "三甲完成视图\\病危（重）护理记录_v_EMR_CRITICALLY_ILL_NURS.sql", "三甲完成视图\\量表评估_v_emr_nursing_assessment.sql", "三甲完成视图\\阴道分娩记录_v_EMR_CHILDBIRTH.sql"], "view_names": ["LUNA_MCS_SDSEY.V_EMR_CHILDBIRTH", "LUNA_MCS_SDSEY.V_EMR_CRITICALLY_ILL_NURS", "LUNA_MCS_SDSEY.V_EMR_DISCHARGE_ASSESSMENT", "LUNA_MCS_SDSEY.V_EMR_GENERAL_NURSING", "LUNA_MCS_SDSEY.V_EMR_NURSING_ASSESSMENT"], "join_type": "JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dg.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "a.node_code  in（ '00172','00112','00115','00114','00116','K01005')\n               AND a.FORM_ID = f."}, {"kind": "status_literal", "col": "NODE_CODE", "value": "00148", "raw": "a.node_code = '00148'"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n               '无'\n           ),\n           1,\n           1000\n       ) AS CATHETER_NUR"}], "fragments": ["f.PATIENT_UID = p.pat_index_no", "f.PATIENT_UID = YDZD.pat_index_no", "f.PATIENT_UID = p.pat_index_no"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$LUNA_MCS_SDSEY.INPATIENTS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PAT_INDEX_NO$r195$,'')
    AND upper(r.to_table)=upper($r195$LUNA_MCS_SDSEY.MCS_DOC_FORM$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_UID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.MCS_DOC_FORM$r195$, $r195$TEMPLATE_CODE+ID$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.MCS_DOC_FORM_RECORDS$r195$, $r195$TEMPLATE_CODE+FORM_ID$r195$, $r195$a.template_code = f.TEMPLATE_CODE AND a.FORM_ID = f.ID$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: LUNA_MCS_SDSEY.V_EMR_CRITICALLY_ILL_NURS,LUNA_MCS_SDSEY.V_EMR_DISCHARGE_ASSESSMENT,LUNA_MCS_SDSEY.V_EMR_GENERAL_NURSING$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\一般护理记录_v_EMR_GENERAL_NURSING.sql", "三甲完成视图\\出院评估与指导_v_EMR_DISCHARGE_ASSESSMENT.sql", "三甲完成视图\\病危（重）护理记录_v_EMR_CRITICALLY_ILL_NURS.sql"], "view_names": ["LUNA_MCS_SDSEY.V_EMR_CRITICALLY_ILL_NURS", "LUNA_MCS_SDSEY.V_EMR_DISCHARGE_ASSESSMENT", "LUNA_MCS_SDSEY.V_EMR_GENERAL_NURSING"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dg.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "a.node_code  in（ '00172','00112','00115','00114','00116','K01005')\n               AND a.FORM_ID = f."}, {"kind": "status_literal", "col": "NODE_CODE", "value": "00148", "raw": "a.node_code = '00148'"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n               '无'\n           ),\n           1,\n           1000\n       ) AS CATHETER_NUR"}], "fragments": ["a.template_code = f.TEMPLATE_CODE", "a.FORM_ID = f.ID", "a.FORM_ID = f.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$LUNA_MCS_SDSEY.MCS_DOC_FORM$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$TEMPLATE_CODE+ID$r195$,'')
    AND upper(r.to_table)=upper($r195$LUNA_MCS_SDSEY.MCS_DOC_FORM_RECORDS$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$TEMPLATE_CODE+FORM_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.CONSULTATION_DOCTOR_DETAIL$r195$, $r195$CONSULTATION_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.CONSULTATION_DOCTOR_MASTER$r195$, $r195$CONSULTATION_ID$r195$, $r195$t.consultation_id = t1.consultation_id$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_CONSUL_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\会诊记录_v_EMR_HOS_CONSUL_RECORD.sql"], "view_names": ["ODS.V_EMR_HOS_CONSUL_RECORD"], "join_type": "INNER JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           nvl(t.consultation_dept, nvl(t2.dept_discharge_from, t2.dept_admission_to))\n"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           (select ks.qmpt_name\n              from his.dept_dict ks\n             where "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n       ) as DEP_NAME, \n\n       t2.discharge_ward_code as AREA_NAME, \n\n       cast(null a"}], "fragments": ["t.consultation_id = t1.consultation_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.CONSULTATION_DOCTOR_DETAIL$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$CONSULTATION_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.CONSULTATION_DOCTOR_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$CONSULTATION_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.CONSULTATION_DOCTOR_MASTER$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$t.patient_id = t2.patient_id AND t.visit_id = t2.visit_id$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_CONSUL_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\会诊记录_v_EMR_HOS_CONSUL_RECORD.sql"], "view_names": ["ODS.V_EMR_HOS_CONSUL_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           nvl(t.consultation_dept, nvl(t2.dept_discharge_from, t2.dept_admission_to))\n"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           (select ks.qmpt_name\n              from his.dept_dict ks\n             where "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n       ) as DEP_NAME, \n\n       t2.discharge_ward_code as AREA_NAME, \n\n       cast(null a"}], "fragments": ["t.patient_id = t2.patient_id", "t.visit_id = t2.visit_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.CONSULTATION_DOCTOR_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$, $r195$PATIENT_ID$r195$, $r195$t.patient_id = t2.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_DOC_ORDER_DRUG$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院医嘱信息-药品类医嘱_v_emr_doc_order_drug.sql"], "view_names": ["ODS.V_EMR_DOC_ORDER_DRUG"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               '01'\n           ),\n           1,\n           20\n       ) as ODER_ITEM_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               '药品类医嘱'\n           ),\n           1,\n           20\n       ) as ODER_ITEM_"}, {"kind": "rownum_limit", "raw": "rownum=1)  , t.order_code ), 1, 100) as ODR_CODE, \n    substr(nvl(  (select F007_CHAN_PIN_MING_CHENG"}, {"kind": "rownum_limit", "raw": "rownum=1)  , t.order_text ), 1, 100)  as DRUG_COMMON_NAME, \n\n          substr(nvl(  (select F007_CHA"}], "fragments": ["t.patient_id = t2.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.MED_DICT_BASEINFO$r195$, $r195$DRUG_ID$r195$, $r195$DATA_CENTER$r195$, $r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$, $r195$ORDER_CODE$r195$, $r195$m.drug_id=t.ORDER_CODE$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_DOC_ORDER_DRUG$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院医嘱信息-药品类医嘱_v_emr_doc_order_drug.sql"], "view_names": ["ODS.V_EMR_DOC_ORDER_DRUG"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               '01'\n           ),\n           1,\n           20\n       ) as ODER_ITEM_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               '药品类医嘱'\n           ),\n           1,\n           20\n       ) as ODER_ITEM_"}, {"kind": "rownum_limit", "raw": "rownum=1)  , t.order_code ), 1, 100) as ODR_CODE, \n    substr(nvl(  (select F007_CHAN_PIN_MING_CHENG"}, {"kind": "rownum_limit", "raw": "rownum=1)  , t.order_text ), 1, 100)  as DRUG_COMMON_NAME, \n\n          substr(nvl(  (select F007_CHA"}], "fragments": ["m.drug_id=t.ORDER_CODE"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.MED_DICT_BASEINFO$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$DRUG_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ORDER_CODE$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$t.patient_id = pv.patient_id AND t.visit_id = pv.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_DOC_ORDER_DRUG$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院医嘱信息-药品类医嘱_v_emr_doc_order_drug.sql"], "view_names": ["ODS.V_EMR_DOC_ORDER_DRUG"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               '01'\n           ),\n           1,\n           20\n       ) as ODER_ITEM_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               '药品类医嘱'\n           ),\n           1,\n           20\n       ) as ODER_ITEM_"}, {"kind": "rownum_limit", "raw": "rownum=1)  , t.order_code ), 1, 100) as ODR_CODE, \n    substr(nvl(  (select F007_CHAN_PIN_MING_CHENG"}, {"kind": "rownum_limit", "raw": "rownum=1)  , t.order_text ), 1, 100)  as DRUG_COMMON_NAME, \n\n          substr(nvl(  (select F007_CHA"}], "fragments": ["t.patient_id = pv.patient_id", "t.visit_id = pv.visit_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$CDA.CDA_DICTIONARY$r195$, $r195$院标编码+院标名称$r195$, $r195$DATA_CENTER$r195$, $r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$, $r195$ORDER_CLASS+ADMINISTRATION$r195$, $r195$cd.院标编码 = t.order_class AND cd.院标编码 = t.order_class$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_DOC_ORDER_DRUG$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院医嘱信息-药品类医嘱_v_emr_doc_order_drug.sql"], "view_names": ["ODS.V_EMR_DOC_ORDER_DRUG"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               '01'\n           ),\n           1,\n           20\n       ) as ODER_ITEM_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               '药品类医嘱'\n           ),\n           1,\n           20\n       ) as ODER_ITEM_"}, {"kind": "rownum_limit", "raw": "rownum=1)  , t.order_code ), 1, 100) as ODR_CODE, \n    substr(nvl(  (select F007_CHAN_PIN_MING_CHENG"}, {"kind": "rownum_limit", "raw": "rownum=1)  , t.order_text ), 1, 100)  as DRUG_COMMON_NAME, \n\n          substr(nvl(  (select F007_CHA"}], "fragments": ["cd.院标编码 = t.order_class", "cd.院标编码 = t.order_class", "zd.院标名称 = t.administration"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$CDA.CDA_DICTIONARY$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$院标编码+院标名称$r195$,'')
    AND upper(r.to_table)=upper($r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ORDER_CLASS+ADMINISTRATION$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.ORDERS$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$t.patient_id = t2.patient_id$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_DOC_ORDER_CHECK$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院医嘱信息-非药品类医嘱_v_EMR_doc_order_check.sql"], "view_names": ["ODS.V_EMR_DOC_ORDER_CHECK"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               t.ordering_dept\n           ),\n           1,\n           15\n       ) as DP"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               nvl(\n                   (select ks.dept_name\n                      from "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               t.ordering_dept\n           ),\n           1,\n           50\n       ) as HO"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               1,\n               18\n           ),\n           '000000000000000000'\n     "}], "fragments": ["t.patient_id = t2.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.ORDERS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.ORDERS$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$t.patient_id = pv.patient_id AND t.visit_id = pv.visit_id$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_DOC_ORDER_CHECK$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院医嘱信息-非药品类医嘱_v_EMR_doc_order_check.sql"], "view_names": ["ODS.V_EMR_DOC_ORDER_CHECK"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               t.ordering_dept\n           ),\n           1,\n           15\n       ) as DP"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               nvl(\n                   (select ks.dept_name\n                      from "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               t.ordering_dept\n           ),\n           1,\n           50\n       ) as HO"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               1,\n               18\n           ),\n           '000000000000000000'\n     "}], "fragments": ["t.patient_id = pv.patient_id", "t.visit_id = pv.visit_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.ORDERS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DEPT_DICT$r195$, $r195$DEPT_CODE$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.ORDERS$r195$, $r195$ORDERING_DEPT$r195$, $r195$ks.dept_code = t.ordering_dept$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_DOC_ORDER_CHECK$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院医嘱信息-非药品类医嘱_v_EMR_doc_order_check.sql"], "view_names": ["ODS.V_EMR_DOC_ORDER_CHECK"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               t.ordering_dept\n           ),\n           1,\n           15\n       ) as DP"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               nvl(\n                   (select ks.dept_name\n                      from "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               t.ordering_dept\n           ),\n           1,\n           50\n       ) as HO"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               1,\n               18\n           ),\n           '000000000000000000'\n     "}], "fragments": ["ks.dept_code = t.ordering_dept"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DEPT_DICT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$DEPT_CODE$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.ORDERS$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ORDERING_DEPT$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$CDA.CDA_DICTIONARY$r195$, $r195$院标编码$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.ORDERS$r195$, $r195$ORDER_CLASS$r195$, $r195$cd.院标编码 = t.order_class AND cd.院标编码 = t.order_class$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_DOC_ORDER_CHECK$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院医嘱信息-非药品类医嘱_v_EMR_doc_order_check.sql"], "view_names": ["ODS.V_EMR_DOC_ORDER_CHECK"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               t.ordering_dept\n           ),\n           1,\n           15\n       ) as DP"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               nvl(\n                   (select ks.dept_name\n                      from "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               t.ordering_dept\n           ),\n           1,\n           50\n       ) as HO"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               1,\n               18\n           ),\n           '000000000000000000'\n     "}], "fragments": ["cd.院标编码 = t.order_class", "cd.院标编码 = t.order_class"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$CDA.CDA_DICTIONARY$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$院标编码$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.ORDERS$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ORDER_CLASS$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD41$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$T3.段落编号 = T1.ID$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_SUCCESSION_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院医师交接班记录_v_EMR_HOS_SUCCESSION_RECORD.sql"], "view_names": ["ODS.V_EMR_HOS_SUCCESSION_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "date_window", "raw": "pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "date_window", "raw": "pv.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "in_subset", "raw": "t1.doc_title in ('交班记录')"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           x.p_dept_code\n       ) as DEPT_CODE, \n\n       nvl(\n           (select ks.qmp"}], "fragments": ["T3.段落编号 = T1.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD41$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DEPT_DICT$r195$, $r195$DEPT_CODE$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$DEPT_ADMISSION_TO+DEPT_DISCHARGE_$r195$, $r195$adm_dept.dept_code = a.dept_admission_to AND dis_dept.dept_code = a.dept_discharge_$r195$, $r195$195三甲视图摄入候选（partial_or_keysubset）$r195$, $r195$涉及视图: ODS.V_EMR_ICH$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院病案首页(电子病历)(D09_D10标）_v_emr_ich.sql"], "view_names": ["ODS.V_EMR_ICH"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "in_subset", "raw": "occ_dict.院标编码 =\n          case\n              when regexp_replace(trim(to_char(a.occupation)), '[[:space:]]+', '') in\n                   ('11','13','17','21','24','27','31','37','51','54','70','80','90"}], "fragments": ["adm_dept.dept_code = a.dept_admission_to", "dis_dept.dept_code = a.dept_discharge_"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DEPT_DICT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$DEPT_CODE$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$DEPT_ADMISSION_TO+DEPT_DISCHARGE_$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.OPERATION$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$pv.patient_id = o.patient_id AND pv.visit_id = o.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ICH_OPERATION$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院病案首页-手术(电子病历)(辅D09_D10标）_v_emr_ich_operation.sql"], "view_names": ["ODS.V_EMR_ICH_OPERATION"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["pv.patient_id = o.patient_id", "pv.visit_id = o.visit_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.OPERATION$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.OPERATION$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$pmi.patient_id = o.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ICH_OPERATION$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院病案首页-手术(电子病历)(辅D09_D10标）_v_emr_ich_operation.sql"], "view_names": ["ODS.V_EMR_ICH_OPERATION"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [], "fragments": ["pmi.patient_id = o.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.OPERATION$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DIAGNOSIS$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$pmi.patient_id = a.patient_id AND t.patient_id = t2.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.EMR_DISCHARGE_RECORD_DIAGNOSIS,ODS.V_EMR_ADMISSION_DIAGNOSIS,ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院病案首页-诊断(电子病历)(辅D09_D10标）_V_EMR_ICH_DIAGNOSIS.sql", "三甲完成视图\\入院诊断表_v_EMR_ADMISSION_DIAGNOSIS.sql", "三甲完成视图\\出院记录-诊断(辅D12标）_EMR_DISCHARGE_RECORD_DIAGNOSIS.sql", "三甲完成视图\\死亡病历讨论记录_v_EMR_HOS_DND_RECORD.sql", "三甲完成视图\\死亡病历讨论记录_v_EMR_HOS_DND_RECORD_jhemr.sql", "三甲完成视图\\转科记录_v_EMR_HOS_CHANGE_MAJOR_RECORD.sql", "三甲完成视图\\转科记录_v_EMR_HOS_CHANGE_MAJOR_RECORD_jhemr.sql"], "view_names": ["ODS.EMR_DISCHARGE_RECORD_DIAGNOSIS", "ODS.V_EMR_ADMISSION_DIAGNOSIS", "ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD", "ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD_JHEMR", "ODS.V_EMR_HOS_DND_RECORD", "ODS.V_EMR_HOS_DND_RECORD_JHEMR", "ODS.V_EMR_ICH_DIAGNOSIS"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "null_filter", "raw": "trim(to_char(d.diagnosis_desc)) is not null\n                               )\n                       )\n                   end,\n                   '-'\n "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n                   ),\n                   ''\n               ),\n               '-'\n       "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n                   ),\n                   ''\n               ),\n               '-'\n       "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n                   ),\n                   ''\n               ),\n               nvl(nullif("}], "fragments": ["pmi.patient_id = a.patient_id", "t.patient_id = t2.patient_id", "t.patient_id = t2.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DIAGNOSIS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.INP_BILL_DETAIL$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$a.patient_id = b.patient_id AND b.PATIENT_ID = p.PATIENT_ID$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_CONSUMABLES,ODS.V_EMR_IN_FEE_INFO_CHILD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院费用明细表_v_EMR_IN_FEE_INFO_CHILD.sql", "三甲完成视图\\高值耗材使用记录_V_EMR_CONSUMABLES.sql"], "view_names": ["ODS.V_EMR_CONSUMABLES", "ODS.V_EMR_IN_FEE_INFO_CHILD"], "join_type": "INNER JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "SETTLE_TYPE", "value": "结算", "raw": "c.settle_type = '结算'"}, {"kind": "status_literal", "col": "CATEGORY_CODE", "value": "DM04-001", "raw": "CATEGORY_CODE='DM04-001'"}, {"kind": "status_literal", "col": "CLASS_ON_MR", "value": "材料", "raw": "b.CLASS_ON_MR = '材料'"}, {"kind": "date_window", "raw": "b.BILLING_DATE_TIME >= DATE '2021-01-01'"}], "fragments": ["a.patient_id = b.patient_id", "b.PATIENT_ID = p.PATIENT_ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.INP_BILL_DETAIL$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.INP_BILL_DETAIL$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.INP_SETTLE_MASTER_YB$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$c.patient_id = a.patient_id AND c.visit_id = a.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_IN_FEE_INFO_CHILD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\住院费用明细表_v_EMR_IN_FEE_INFO_CHILD.sql"], "view_names": ["ODS.V_EMR_IN_FEE_INFO_CHILD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "SETTLE_TYPE", "value": "结算", "raw": "c.settle_type = '结算'"}, {"kind": "status_literal", "col": "CATEGORY_CODE", "value": "DM04-001", "raw": "CATEGORY_CODE='DM04-001'"}], "fragments": ["c.patient_id = a.patient_id", "c.visit_id = a.visit_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.INP_BILL_DETAIL$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.INP_SETTLE_MASTER_YB$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD34$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$T3.段落编号=T1.ID$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ADMISSION_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\入院记录(D08标）_v_EMR_ADMISSION_RECORD.sql"], "view_names": ["ODS.V_EMR_ADMISSION_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [], "fragments": ["T3.段落编号=T1.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD34$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.INPATIENTS$r195$, $r195$PAT_INDEX_NO$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.MCS_ASSESS_FORM$r195$, $r195$PATIENT_UID$r195$, $r195$f.PATIENT_UID = YDZD.pat_index_no$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: LUNA_MCS_SDSEY.V_EMR_ADMISSION_ASSESSMENT$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\入院评估记录_V_EMR_ADMISSION_ASSESSMENT.sql"], "view_names": ["LUNA_MCS_SDSEY.V_EMR_ADMISSION_ASSESSMENT"], "join_type": "JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "ASSESS_CODE", "value": "Z01028", "raw": "a.assess_code = 'Z01028'"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           1,\n           20\n       ) AS ADMISSION_TYPE,  \n\n       diag_dict.std_code  A"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           0\n       ) AS WEIGHT,  \n\n       NVL(\n           (SELECT ROUND(TO_NUMBER(REGE"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           0\n       ) AS BREATHING_RATE,  \n\n       NVL(\n           (SELECT ROUND(TO_NUM"}], "fragments": ["f.PATIENT_UID = YDZD.pat_index_no"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$LUNA_MCS_SDSEY.INPATIENTS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PAT_INDEX_NO$r195$,'')
    AND upper(r.to_table)=upper($r195$LUNA_MCS_SDSEY.MCS_ASSESS_FORM$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_UID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.DIAGNOSIS_BASY$r195$, $r195$VISIT_ID$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.INPATIENTS$r195$, $r195$SERIES$r195$, $r195$dg.VISIT_ID = YDZD.SERIES$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: LUNA_MCS_SDSEY.V_EMR_ADMISSION_ASSESSMENT$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\入院评估记录_V_EMR_ADMISSION_ASSESSMENT.sql"], "view_names": ["LUNA_MCS_SDSEY.V_EMR_ADMISSION_ASSESSMENT"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "ASSESS_CODE", "value": "Z01028", "raw": "a.assess_code = 'Z01028'"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           1,\n           20\n       ) AS ADMISSION_TYPE,  \n\n       diag_dict.std_code  A"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           0\n       ) AS WEIGHT,  \n\n       NVL(\n           (SELECT ROUND(TO_NUMBER(REGE"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           0\n       ) AS BREATHING_RATE,  \n\n       NVL(\n           (SELECT ROUND(TO_NUM"}], "fragments": ["dg.VISIT_ID = YDZD.SERIES"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$LUNA_MCS_SDSEY.DIAGNOSIS_BASY$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$LUNA_MCS_SDSEY.INPATIENTS$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$SERIES$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.MCS_ASSESS_FORM$r195$, $r195$ID$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.MCS_ASSESS_FORM_RECORD$r195$, $r195$FORM_ID$r195$, $r195$a.FORM_ID = f.ID AND a.FORM_ID = f.ID$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: LUNA_MCS_SDSEY.V_EMR_ADMISSION_ASSESSMENT$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\入院评估记录_V_EMR_ADMISSION_ASSESSMENT.sql"], "view_names": ["LUNA_MCS_SDSEY.V_EMR_ADMISSION_ASSESSMENT"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "ASSESS_CODE", "value": "Z01028", "raw": "a.assess_code = 'Z01028'"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           1,\n           20\n       ) AS ADMISSION_TYPE,  \n\n       diag_dict.std_code  A"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           0\n       ) AS WEIGHT,  \n\n       NVL(\n           (SELECT ROUND(TO_NUMBER(REGE"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           0\n       ) AS BREATHING_RATE,  \n\n       NVL(\n           (SELECT ROUND(TO_NUM"}], "fragments": ["a.FORM_ID = f.ID", "a.FORM_ID = f.ID", "a.FORM_ID = f.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$LUNA_MCS_SDSEY.MCS_ASSESS_FORM$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$ID$r195$,'')
    AND upper(r.to_table)=upper($r195$LUNA_MCS_SDSEY.MCS_ASSESS_FORM_RECORD$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$FORM_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$INFECTION_SURVEILLANCE$r195$, $r195$C##NIS5.INFECTION$r195$, $r195$CASEID$r195$, $r195$INFECTION_SURVEILLANCE$r195$, $r195$C##NIS5.OVERALL$r195$, $r195$CASEID$r195$, $r195$o.caseid = i.caseid$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: c##fxpt.emr_infection_information_register$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\医院感染信息登记表_EMR_INFECTION_INFORMATION_REGISTER.sql"], "view_names": ["c##fxpt.emr_infection_information_register"], "join_type": "INNER JOIN", "blocks": [0], "qualifiers": [], "fragments": ["o.caseid = i.caseid"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$C##NIS5.INFECTION$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$CASEID$r195$,'')
    AND upper(r.to_table)=upper($r195$C##NIS5.OVERALL$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$CASEID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$INFECTION_SURVEILLANCE$r195$, $r195$C##NIS5.OPERATION_SOURCE$r195$, $r195$CASEID$r195$, $r195$INFECTION_SURVEILLANCE$r195$, $r195$C##NIS5.OVERALL$r195$, $r195$CASEID$r195$, $r195$os.caseid = o.caseid$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: c##fxpt.emr_infection_information_register$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\医院感染信息登记表_EMR_INFECTION_INFORMATION_REGISTER.sql"], "view_names": ["c##fxpt.emr_infection_information_register"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [], "fragments": ["os.caseid = o.caseid"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$C##NIS5.OPERATION_SOURCE$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$CASEID$r195$,'')
    AND upper(r.to_table)=upper($r195$C##NIS5.OVERALL$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$CASEID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HRP$r195$, $r195$HRPSEY656.BD_PSNDOC$r195$, $r195$PK_PSNDOC$r195$, $r195$HRP$r195$, $r195$HRPSEY656.HI_PSNJOB$r195$, $r195$PK_PSNDOC$r195$, $r195$bd_psndoc.pk_psndoc = hi_psnjob.pk_psndoc$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: HRPSEY656.EMR_HOS_PRACTITIONER$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\医院执业人员信息表_EMR_HOS_PRACTITIONER.sql"], "view_names": ["HRPSEY656.EMR_HOS_PRACTITIONER"], "join_type": "LEFT OUTER JOIN", "blocks": [0], "qualifiers": [], "fragments": ["bd_psndoc.pk_psndoc = hi_psnjob.pk_psndoc"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HRPSEY656.BD_PSNDOC$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PK_PSNDOC$r195$,'')
    AND upper(r.to_table)=upper($r195$HRPSEY656.HI_PSNJOB$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PK_PSNDOC$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HRP$r195$, $r195$HRPSEY656.BD_PSNCL$r195$, $r195$PK_PSNCL$r195$, $r195$HRP$r195$, $r195$HRPSEY656.HI_PSNJOB$r195$, $r195$PK_PSNCL$r195$, $r195$hi_psnjob.pk_psncl = psncl.pk_psncl$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: HRPSEY656.EMR_HOS_PRACTITIONER$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\医院执业人员信息表_EMR_HOS_PRACTITIONER.sql"], "view_names": ["HRPSEY656.EMR_HOS_PRACTITIONER"], "join_type": "LEFT OUTER JOIN", "blocks": [0], "qualifiers": [], "fragments": ["hi_psnjob.pk_psncl = psncl.pk_psncl"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HRPSEY656.BD_PSNCL$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PK_PSNCL$r195$,'')
    AND upper(r.to_table)=upper($r195$HRPSEY656.HI_PSNJOB$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PK_PSNCL$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HRP$r195$, $r195$HRPSEY656.HI_PSNJOB$r195$, $r195$PK_DEPT$r195$, $r195$HRP$r195$, $r195$HRPSEY656.ORG_DEPT$r195$, $r195$PK_DEPT$r195$, $r195$hi_psnjob.pk_dept = dept.pk_dept$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: HRPSEY656.EMR_HOS_PRACTITIONER$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\医院执业人员信息表_EMR_HOS_PRACTITIONER.sql"], "view_names": ["HRPSEY656.EMR_HOS_PRACTITIONER"], "join_type": "LEFT OUTER JOIN", "blocks": [0], "qualifiers": [], "fragments": ["hi_psnjob.pk_dept = dept.pk_dept"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HRPSEY656.HI_PSNJOB$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PK_DEPT$r195$,'')
    AND upper(r.to_table)=upper($r195$HRPSEY656.ORG_DEPT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PK_DEPT$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HRP$r195$, $r195$HRPSEY656.BD_PSNDOC$r195$, $r195$SEX$r195$, $r195$HRP$r195$, $r195$HRPSEY656.MD_ENUMVALUE$r195$, $r195$VALUE$r195$, $r195$enumvalue.value = bd_psndoc.sex$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: HRPSEY656.EMR_HOS_PRACTITIONER$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\医院执业人员信息表_EMR_HOS_PRACTITIONER.sql"], "view_names": ["HRPSEY656.EMR_HOS_PRACTITIONER"], "join_type": "LEFT OUTER JOIN", "blocks": [0], "qualifiers": [], "fragments": ["enumvalue.value = bd_psndoc.sex"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HRPSEY656.BD_PSNDOC$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$SEX$r195$,'')
    AND upper(r.to_table)=upper($r195$HRPSEY656.MD_ENUMVALUE$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$VALUE$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HRP$r195$, $r195$HRPSEY656.BD_DEFDOC$r195$, $r195$PK_DEFDOC$r195$, $r195$HRP$r195$, $r195$HRPSEY656.HI_PSNDOC_EDU$r195$, $r195$EDUCATION+PK_DEGREE$r195$, $r195$hi_psndoc_edu.education = a.pk_defdoc AND hi_psndoc_edu.pk_degree = b.pk_defdoc$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: HRPSEY656.EMR_HOS_PRACTITIONER$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\医院执业人员信息表_EMR_HOS_PRACTITIONER.sql"], "view_names": ["HRPSEY656.EMR_HOS_PRACTITIONER"], "join_type": "LEFT OUTER JOIN", "blocks": [0], "qualifiers": [], "fragments": ["hi_psndoc_edu.education = a.pk_defdoc", "hi_psndoc_edu.pk_degree = b.pk_defdoc"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HRPSEY656.BD_DEFDOC$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PK_DEFDOC$r195$,'')
    AND upper(r.to_table)=upper($r195$HRPSEY656.HI_PSNDOC_EDU$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$EDUCATION+PK_DEGREE$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HIS_SOURCE$r195$, $r195$EXAM.EXAM_APPOINTS$r195$, $r195$VISIT_DATE+VISIT_NO$r195$, $r195$HIS_SOURCE$r195$, $r195$HISUSER.CLINIC_MASTER$r195$, $r195$VISIT_DATE+VISIT_NO$r195$, $r195$a.VISIT_DATE = b.VISIT_DATE AND a.VISIT_NO   = b.VISIT_NO$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: V_EMR_EXAM_IMAGE_REP$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\影像诊断报告(D07标）_V_EMR_EXAM_IMAGE_REP.sql"], "view_names": ["V_EMR_EXAM_IMAGE_REP"], "join_type": "INNER JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "SRC_TYPE_FOR_JOIN", "value": "I", "raw": "m.SRC_TYPE_FOR_JOIN = 'I'"}, {"kind": "status_literal", "col": "SRC_TYPE_FOR_JOIN", "value": "O", "raw": "m.SRC_TYPE_FOR_JOIN = 'O'"}, {"kind": "status_literal", "col": "SRC_TYPE_FOR_JOIN", "value": "O", "raw": "m.SRC_TYPE_FOR_JOIN = 'O'"}, {"kind": "status_literal", "col": "SRC_TYPE_FOR_JOIN", "value": "O", "raw": "m.SRC_TYPE_FOR_JOIN = 'O'"}], "fragments": ["a.VISIT_DATE = b.VISIT_DATE", "a.VISIT_NO   = b.VISIT_NO"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$EXAM.EXAM_APPOINTS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$VISIT_DATE+VISIT_NO$r195$,'')
    AND upper(r.to_table)=upper($r195$HISUSER.CLINIC_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$VISIT_DATE+VISIT_NO$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_SCHEDULE$r195$, $r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$, $r195$a.patient_id = a1.patient_id AND a.visit_id   = a1.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ANES_AFTER_RECORD,ODS.V_EMR_BOFORE_OPERA_RECORD,ODS.V_EMR_OPERATION_NURSING$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\手术护理记录_v_emr_operation_nursing.sql", "三甲完成视图\\麻醉术前访视记录_v_EMR_BOFORE_OPERA_RECORD.sql", "三甲完成视图\\麻醉术后访视记录_v_EMR_ANES_AFTER_RECORD.sql"], "view_names": ["ODS.V_EMR_ANES_AFTER_RECORD", "ODS.V_EMR_BOFORE_OPERA_RECORD", "ODS.V_EMR_OPERATION_NURSING"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           (select hd.qmpt_name\n              from his.dept_dict hd\n             where "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n         ),\n         1,\n         50\n       ) as DEPT_NAME, \n\n       substr(\n         nvl"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           p.dept_admission_to\n         ),\n         1,\n         20\n       ) as DEPT_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           p.discharge_ward_code\n         ),\n         1,\n         50\n       ) as WARD_N"}], "fragments": ["a.patient_id = a1.patient_id", "a.visit_id   = a1.visit_id", "a.oper_id    = a1.oper_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_SCHEDULE$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_ANESTHESIA_PLAN$r195$, $r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$, $r195$a.patient_id = e3.patient_id AND a.visit_id   = e3.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ANESTHESIA_RECORD,ODS.V_EMR_ANES_AFTER_RECORD,ODS.V_EMR_BOFORE_OPERA_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\手术护理记录_v_emr_operation_nursing.sql", "三甲完成视图\\麻醉手术记录_v_EMR_ANESTHESIA_RECORD.sql", "三甲完成视图\\麻醉术前访视记录_v_EMR_BOFORE_OPERA_RECORD.sql", "三甲完成视图\\麻醉术后访视记录_v_EMR_ANES_AFTER_RECORD.sql", "三甲完成视图\\麻醉知情同意书_v_emr_infor_anesthesia.sql"], "view_names": ["ODS.V_EMR_ANESTHESIA_RECORD", "ODS.V_EMR_ANES_AFTER_RECORD", "ODS.V_EMR_BOFORE_OPERA_RECORD", "ODS.V_EMR_INFOR_ANESTHESIA", "ODS.V_EMR_OPERATION_NURSING"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           v.dept_admission_to\n         ),\n         1,\n         20\n       ) as DEPT_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           (select hd.dept_name\n              from his.dept_dict hd\n             where "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n         ),\n         1,\n         50\n       ) as DEPT_NAME, \n\n       substr(\n         nvl"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           v.discharge_ward_code\n         ),\n         1,\n         50\n       ) as WARD_N"}], "fragments": ["a.patient_id = e3.patient_id", "a.visit_id   = e3.visit_id", "a.oper_id    = e3.oper_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$SM.MED_ANESTHESIA_PLAN$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD46$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$t3.段落编号 = t1.id AND T4.段落编号 = T1.ID$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_PREOP_DISCUSS,ODS.V_EMR_INFOR_OPERATION$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\手术知情同意书_v_emr_infor_operation.sql", "三甲完成视图\\术前讨论与小结_v_EMR_HOS_PREOP_DISCUSS.sql"], "view_names": ["ODS.V_EMR_HOS_PREOP_DISCUSS", "ODS.V_EMR_INFOR_OPERATION"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(cast(t.p_dept_code as varchar2(50)), '-')\n                  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '8'\n                   ),\n                   1,\n                "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '其他'\n                   ),\n                   1,\n               "}], "fragments": ["t3.段落编号 = t1.id", "T4.段落编号 = T1.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD46$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$PATIENT_ID$r195$, $r195$mom.patient_id = p.patient_id AND mom.patient_id = p.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INFOR_OPERATION,ODS.V_EMR_INFOR_OPERATION_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\手术知情同意书_v_emr_infor_operation.sql", "三甲完成视图\\手术知情同意书_v_emr_infor_operation_jhemr.sql"], "view_names": ["ODS.V_EMR_INFOR_OPERATION", "ODS.V_EMR_INFOR_OPERATION_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(cast(t.p_dept_code as varchar2(50)), '-')\n                  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '8'\n                   ),\n                   1,\n                "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '其他'\n                   ),\n                   1,\n               "}], "fragments": ["mom.patient_id = p.patient_id", "mom.patient_id = p.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT_DOCINDEX$r195$, $r195$P_INPATIENT_TIMES$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$VISIT_ID$r195$, $r195$mom.visit_id = t.p_inpatient_times$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INFOR_OPERATION$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\手术知情同意书_v_emr_infor_operation.sql"], "view_names": ["ODS.V_EMR_INFOR_OPERATION"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(cast(t.p_dept_code as varchar2(50)), '-')\n                  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '8'\n                   ),\n                   1,\n                "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '其他'\n                   ),\n                   1,\n               "}], "fragments": ["mom.visit_id = t.p_inpatient_times"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EPR_INPATIENT_DOCINDEX$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$P_INPATIENT_TIMES$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$JHEMR.JHMR_FILE_INDEX$r195$, $r195$VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$VISIT_ID$r195$, $r195$mom.visit_id = t.VISIT_ID$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INFOR_OPERATION_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\手术知情同意书_v_emr_infor_operation_jhemr.sql"], "view_names": ["ODS.V_EMR_INFOR_OPERATION_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(cast(t.DEPT_CODE as varchar2(50)), '-')\n                   )"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '8'\n                   ),\n                   1,\n                "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '其他'\n                   ),\n                   1,\n               "}], "fragments": ["mom.visit_id = t.VISIT_ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$JHEMR.JHMR_FILE_INDEX$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD44$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$T3.段落编号 = T1.ID$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_SAVE_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\抢救记录_v_EMR_HOS_SAVE_RECORD.sql"], "view_names": ["ODS.V_EMR_HOS_SAVE_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "date_window", "raw": "pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "date_window", "raw": "pv.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           z.p_dept_code\n       ) as DEPT_CODE, \n\n       nvl(\n           (select dd.qmp"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           z.p_dept_name\n       ) as DEP_NAME, \n\n       z.p_are_name as AREA_NAME, \n\n  "}], "fragments": ["T3.段落编号 = T1.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD44$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT_DOCINDEX$r195$, $r195$P_CLINIC_ID+P_INPATIENT_TIMES$r195$, $r195$pv.patient_id = t.p_clinic_id AND pv.visit_id = t.p_inpatient_times$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_PREOP_DISCUSS$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\术前讨论与小结_v_EMR_HOS_PREOP_DISCUSS.sql"], "view_names": ["ODS.V_EMR_HOS_PREOP_DISCUSS"], "join_type": "INNER JOIN", "blocks": [0], "qualifiers": [{"kind": "date_window", "raw": "pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "date_window", "raw": "pv.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "in_subset", "raw": "t1.doc_type_name in ('术前小结', '术前讨论')"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_Dept_Name\n       ) as DEP_NAME, \n\n       nvl(\n           (select ks.qmpt"}], "fragments": ["pv.patient_id = t.p_clinic_id", "pv.visit_id = t.p_inpatient_times"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT_DOCINDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$P_CLINIC_ID+P_INPATIENT_TIMES$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD47$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$T3.段落编号 = T1.ID$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_PREOP_DISCUSS$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\术前讨论与小结_v_EMR_HOS_PREOP_DISCUSS.sql"], "view_names": ["ODS.V_EMR_HOS_PREOP_DISCUSS"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "date_window", "raw": "pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "date_window", "raw": "pv.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "in_subset", "raw": "t1.doc_type_name in ('术前小结', '术前讨论')"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_Dept_Name\n       ) as DEP_NAME, \n\n       nvl(\n           (select ks.qmpt"}], "fragments": ["T3.段落编号 = T1.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD47$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.OPERATION$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT_DOCINDEX$r195$, $r195$P_CLINIC_ID+P_INPATIENT_TIMES$r195$, $r195$o.patient_id = t.p_clinic_id AND o.visit_id = t.p_inpatient_times$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_PREOP_DISCUSS$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\术前讨论与小结_v_EMR_HOS_PREOP_DISCUSS.sql"], "view_names": ["ODS.V_EMR_HOS_PREOP_DISCUSS"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "date_window", "raw": "pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "date_window", "raw": "pv.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "in_subset", "raw": "t1.doc_type_name in ('术前小结', '术前讨论')"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_Dept_Name\n       ) as DEP_NAME, \n\n       nvl(\n           (select ks.qmpt"}], "fragments": ["o.patient_id = t.p_clinic_id", "o.visit_id = t.p_inpatient_times"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.OPERATION$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT_DOCINDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$P_CLINIC_ID+P_INPATIENT_TIMES$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT_DOCINDEX$r195$, $r195$P_CLINIC_ID+P_INPATIENT_TIMES$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$mom.patient_id = t.p_clinic_id AND mom.visit_id = t.p_inpatient_times$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_PREOP_DISCUSS$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\术前讨论与小结_v_EMR_HOS_PREOP_DISCUSS.sql"], "view_names": ["ODS.V_EMR_HOS_PREOP_DISCUSS"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "date_window", "raw": "pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "date_window", "raw": "pv.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "in_subset", "raw": "t1.doc_type_name in ('术前小结', '术前讨论')"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_Dept_Name\n       ) as DEP_NAME, \n\n       nvl(\n           (select ks.qmpt"}], "fragments": ["mom.patient_id = t.p_clinic_id", "mom.visit_id = t.p_inpatient_times"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EPR_INPATIENT_DOCINDEX$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$P_CLINIC_ID+P_INPATIENT_TIMES$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$JHEMR.JHMR_FILE_INDEX$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$pv.patient_id = t.PATIENT_ID AND pv.visit_id = t.VISIT_ID$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_PREOP_DISCUSS_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\术前讨论与小结_v_EMR_HOS_PREOP_DISCUSS_jhemr.sql"], "view_names": ["ODS.V_EMR_HOS_PREOP_DISCUSS_JHEMR"], "join_type": "INNER JOIN", "blocks": [0], "qualifiers": [{"kind": "date_window", "raw": "pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "date_window", "raw": "pv.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "in_subset", "raw": "t1.TOPIC in ('术前小结', '术前讨论')"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.DEPT_CODE\n       ) as DEP_NAME, \n\n       nvl(\n           (select ks.qmpt_c"}], "fragments": ["pv.patient_id = t.PATIENT_ID", "pv.visit_id = t.VISIT_ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$JHEMR.JHMR_FILE_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.OPERATION$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$JHEMR.JHMR_FILE_INDEX$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$o.patient_id = t.PATIENT_ID AND o.visit_id = t.VISIT_ID$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_PREOP_DISCUSS_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\术前讨论与小结_v_EMR_HOS_PREOP_DISCUSS_jhemr.sql"], "view_names": ["ODS.V_EMR_HOS_PREOP_DISCUSS_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "date_window", "raw": "pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "date_window", "raw": "pv.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "in_subset", "raw": "t1.TOPIC in ('术前小结', '术前讨论')"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.DEPT_CODE\n       ) as DEP_NAME, \n\n       nvl(\n           (select ks.qmpt_c"}], "fragments": ["o.patient_id = t.PATIENT_ID", "o.visit_id = t.VISIT_ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.OPERATION$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$JHEMR.JHMR_FILE_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$JHEMR.JHMR_FILE_INDEX$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$mom.patient_id = t.PATIENT_ID AND mom.visit_id = t.VISIT_ID$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_PREOP_DISCUSS_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\术前讨论与小结_v_EMR_HOS_PREOP_DISCUSS_jhemr.sql"], "view_names": ["ODS.V_EMR_HOS_PREOP_DISCUSS_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "date_window", "raw": "pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "date_window", "raw": "pv.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "in_subset", "raw": "t1.TOPIC in ('术前小结', '术前讨论')"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.DEPT_CODE\n       ) as DEP_NAME, \n\n       nvl(\n           (select ks.qmpt_c"}], "fragments": ["mom.patient_id = t.PATIENT_ID", "mom.visit_id = t.VISIT_ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$JHEMR.JHMR_FILE_INDEX$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.CLINIC_ITEM_DICT$r195$, $r195$ITEM_CODE$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.LAB_TEST_ITEMS$r195$, $r195$ITEM_CODE$r195$, $r195$cid.ITEM_CODE = lti.ITEM_CODE AND b.ITEM_CODE = li.ITEM_CODE$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INSPECTION_ALLERGY_TEST,ODS.V_EMR_INSPECTION_TEST$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\检验报告-药敏子表_V_EMR_INSPECTION_ALLERGY_TEST.sql", "三甲完成视图\\检验报告单(D18)_V_EMR_INSPECTION_TEST.sql"], "view_names": ["ODS.V_EMR_INSPECTION_ALLERGY_TEST", "ODS.V_EMR_INSPECTION_TEST"], "join_type": "INNER JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "RESULT_STATUS", "value": "4", "raw": "ltm.RESULT_STATUS = '4'"}, {"kind": "null_filter", "raw": "NULLIF(TRIM(lr.REPORT_ITEM_NAME), '') IS NOT NULL"}, {"kind": "null_filter", "raw": "NULLIF(TRIM(lr.RESULT), '') IS NOT NULL"}, {"kind": "status_literal", "col": "SRC_TYPE_FOR_JOIN", "value": "I", "raw": "m.SRC_TYPE_FOR_JOIN = 'I'"}], "fragments": ["cid.ITEM_CODE = lti.ITEM_CODE", "b.ITEM_CODE = li.ITEM_CODE"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.CLINIC_ITEM_DICT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$ITEM_CODE$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.LAB_TEST_ITEMS$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ITEM_CODE$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.LAB_RESULT$r195$, $r195$ITEM_NO$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.LAB_TEST_ITEMS$r195$, $r195$ITEM_NO$r195$, $r195$lti.ITEM_NO = lr.ITEM_NO$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INSPECTION_ITEM_TEST$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\检验报告单-项目(辅D06标）_V_EMR_INSPECTION_ITEM_TEST.sql"], "view_names": ["ODS.V_EMR_INSPECTION_ITEM_TEST"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "SRC_TYPE_FOR_JOIN", "value": "I", "raw": "m.SRC_TYPE_FOR_JOIN = 'I'"}, {"kind": "status_literal", "col": "SRC_TYPE_FOR_JOIN", "value": "O_RCPT", "raw": "m.SRC_TYPE_FOR_JOIN = 'O_RCPT'"}, {"kind": "status_literal", "col": "SRC_TYPE_FOR_JOIN", "value": "O_NORCPT", "raw": "m.SRC_TYPE_FOR_JOIN = 'O_NORCPT'"}, {"kind": "date_window", "raw": "a.DISCHARGE_DATE_TIME >= DATE '2021-01-01'"}], "fragments": ["lti.ITEM_NO = lr.ITEM_NO"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.LAB_RESULT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$ITEM_NO$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.LAB_TEST_ITEMS$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ITEM_NO$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD51$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$T3.段落编号 = T1.ID$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_DND_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\死亡病历讨论记录_v_EMR_HOS_DND_RECORD.sql"], "view_names": ["ODS.V_EMR_HOS_DND_RECORD"], "join_type": "INNER JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "ddd.diagnosis_type = '3'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dddd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_dept_code\n       ) as DEP_CODE, \n\n       t.P_ARE_NAME as AREA_NAME, \n\n  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                '^[0-9]+$'\n              )\n         then to_number(\n                (se"}], "fragments": ["T3.段落编号 = T1.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD51$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD51$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD_CONTENT$r195$, $r195$段落编号$r195$, $r195$t4.段落编号 = t3.段落编号$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_DND_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\死亡病历讨论记录_v_EMR_HOS_DND_RECORD.sql"], "view_names": ["ODS.V_EMR_HOS_DND_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "ddd.diagnosis_type = '3'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dddd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_dept_code\n       ) as DEP_CODE, \n\n       t.P_ARE_NAME as AREA_NAME, \n\n  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                '^[0-9]+$'\n              )\n         then to_number(\n                (se"}], "fragments": ["t4.段落编号 = t3.段落编号"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD51$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EMRSD_CONTENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$段落编号$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DIAGNOSIS$r195$, $r195$VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT_DOCINDEX$r195$, $r195$P_INPATIENT_TIMES$r195$, $r195$t.P_INPATIENT_TIMES = ddd.visit_id AND t.P_INPATIENT_TIMES = dddd.visit_id$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD,ODS.V_EMR_HOS_DND_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\死亡病历讨论记录_v_EMR_HOS_DND_RECORD.sql", "三甲完成视图\\转科记录_v_EMR_HOS_CHANGE_MAJOR_RECORD.sql"], "view_names": ["ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD", "ODS.V_EMR_HOS_DND_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "ddd.diagnosis_type = '3'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dddd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_dept_code\n       ) as DEP_CODE, \n\n       t.P_ARE_NAME as AREA_NAME, \n\n  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                '^[0-9]+$'\n              )\n         then to_number(\n                (se"}], "fragments": ["t.P_INPATIENT_TIMES = ddd.visit_id", "t.P_INPATIENT_TIMES = dddd.visit_id", "d.visit_id = t.p_inpatient_times"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DIAGNOSIS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT_DOCINDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$P_INPATIENT_TIMES$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DIAGNOSIS$r195$, $r195$VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$JHEMR.JHMR_FILE_INDEX$r195$, $r195$VISIT_ID$r195$, $r195$t.VISIT_ID = ddd.visit_id AND t.VISIT_ID = dddd.visit_id$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD_JHEMR,ODS.V_EMR_HOS_DND_RECORD_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\死亡病历讨论记录_v_EMR_HOS_DND_RECORD_jhemr.sql", "三甲完成视图\\转科记录_v_EMR_HOS_CHANGE_MAJOR_RECORD_jhemr.sql"], "view_names": ["ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD_JHEMR", "ODS.V_EMR_HOS_DND_RECORD_JHEMR"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "ddd.diagnosis_type = '3'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dddd.diagnosis_type = '3'"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.DEPT_CODE\n       ) as DEP_CODE, \n\n       t.DEPT_CODE as AREA_NAME, \n\n     "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                '^[0-9]+$'\n              )\n         then to_number(\n                (se"}], "fragments": ["t.VISIT_ID = ddd.visit_id", "t.VISIT_ID = dddd.visit_id", "d.visit_id = t.VISIT_ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DIAGNOSIS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$JHEMR.JHMR_FILE_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$CDA.CDA_DICTIONARY$r195$, $r195$院标编码$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$RELATIONSHIP$r195$, $r195$cd.院标编码 = pmi.relationship AND cd.院标编码 = pmi.relationship$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INFOR_ANESTHESIA,ODS.V_EMR_INFOR_SPEC_EXAM_TREAT,ODS.V_EMR_INFOR_SPEC_EXAM_TREAT_JHEMR$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\特殊检查及特殊治疗同意书_v_emr_infor_spec_exam_treat.sql", "三甲完成视图\\特殊检查及特殊治疗同意书_v_emr_infor_spec_exam_treat_jhemr.sql", "三甲完成视图\\麻醉知情同意书_v_emr_infor_anesthesia.sql"], "view_names": ["ODS.V_EMR_INFOR_ANESTHESIA", "ODS.V_EMR_INFOR_SPEC_EXAM_TREAT", "ODS.V_EMR_INFOR_SPEC_EXAM_TREAT_JHEMR"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "in_subset", "raw": "t1.doc_title in (\n                       '消化内镜知情同意书-新标',\n                       '电子纤维支气管镜检查知情同意书-新标',\n                       '术中冰冻切片检查知情同意书-新标',\n                       '骨髓穿刺/活检术知情同意书-新标',"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(cast(t.p_dept_code as varchar2(50)), '-')\n                  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '8'\n                   ),\n                   1,\n                "}], "fragments": ["cd.院标编码 = pmi.relationship", "cd.院标编码 = pmi.relationship", "cd.院标编码 = pmi.relationship"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$CDA.CDA_DICTIONARY$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$院标编码$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$RELATIONSHIP$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD40$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$T3.段落编号 = T1.ID$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_DIFFIC_CASE_DISCUSS$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\疑难病例讨论记录_v_EMR_HOS_DIFFIC_CASE_DISCUSS.sql"], "view_names": ["ODS.V_EMR_HOS_DIFFIC_CASE_DISCUSS"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_dept_name\n       ) as DEP_NAME, \n\n       nvl(\n           (select ks.qmpt"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_dept_code\n       ) as DEP_CODE, \n\n       t.p_Are_Name as AREA_NAME, \n\n  "}], "fragments": ["T3.段落编号 = T1.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD40$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD40$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD_CONTENT$r195$, $r195$段落编号$r195$, $r195$t4.段落编号 = t3.段落编号$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_DIFFIC_CASE_DISCUSS$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\疑难病例讨论记录_v_EMR_HOS_DIFFIC_CASE_DISCUSS.sql"], "view_names": ["ODS.V_EMR_HOS_DIFFIC_CASE_DISCUSS"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_dept_name\n       ) as DEP_NAME, \n\n       nvl(\n           (select ks.qmpt"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           t.p_dept_code\n       ) as DEP_CODE, \n\n       t.p_Are_Name as AREA_NAME, \n\n  "}], "fragments": ["t4.段落编号 = t3.段落编号"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD40$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EMRSD_CONTENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$段落编号$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.INPATIENTS$r195$, $r195$PAT_INDEX_NO$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.MCS_ORDER_SCHEDULE$r195$, $r195$PATIENT_UID$r195$, $r195$WSFL.PATIENT_UID = YDZD.pat_index_no$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: LUNA_MCS_SDSEY.V_EMR_IN_OUT_AMOUNT$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\病危（重）护理记录-出入量记录_v_EMR_IN_OUT_AMOUNT.sql"], "view_names": ["LUNA_MCS_SDSEY.V_EMR_IN_OUT_AMOUNT"], "join_type": "JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dg.diagnosis_type = '3'"}, {"kind": "status_literal", "col": "VITALSIGN_TYPE", "value": "1014", "raw": "A.vitalsign_type = '1014'"}, {"kind": "null_filter", "raw": "A.vitalsign_nval1 IS NOT NULL"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           0\n       ) AS WEIGHT,  \n\n       SUBSTRB(\n           NVL(\n               TO_C"}], "fragments": ["WSFL.PATIENT_UID = YDZD.pat_index_no"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$LUNA_MCS_SDSEY.INPATIENTS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PAT_INDEX_NO$r195$,'')
    AND upper(r.to_table)=upper($r195$LUNA_MCS_SDSEY.MCS_ORDER_SCHEDULE$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_UID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.INPATIENTS$r195$, $r195$PAT_INDEX_NO$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.MCS_VITAL_INFO$r195$, $r195$PATIENT_UID$r195$, $r195$A.PATIENT_UID = YDZD.Pat_Index_No$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: LUNA_MCS_SDSEY.V_EMR_IN_OUT_AMOUNT$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\病危（重）护理记录-出入量记录_v_EMR_IN_OUT_AMOUNT.sql"], "view_names": ["LUNA_MCS_SDSEY.V_EMR_IN_OUT_AMOUNT"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dg.diagnosis_type = '3'"}, {"kind": "status_literal", "col": "VITALSIGN_TYPE", "value": "1014", "raw": "A.vitalsign_type = '1014'"}, {"kind": "null_filter", "raw": "A.vitalsign_nval1 IS NOT NULL"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           0\n       ) AS WEIGHT,  \n\n       SUBSTRB(\n           NVL(\n               TO_C"}], "fragments": ["A.PATIENT_UID = YDZD.Pat_Index_No"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$LUNA_MCS_SDSEY.INPATIENTS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PAT_INDEX_NO$r195$,'')
    AND upper(r.to_table)=upper($r195$LUNA_MCS_SDSEY.MCS_VITAL_INFO$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_UID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$PLAN_PATIENTPRESCRIPTION$r195$, $r195$TREATMENTID+TENANTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_TREATMENT$r195$, $r195$ID+TENANTID$r195$, $r195$t."Id" = pp0."TreatmentId" AND t."TenantId" = pp0."TenantId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["t.\"Id\" = pp0.\"TreatmentId\"", "t.\"TenantId\" = pp0.\"TenantId\"", "t.\"Id\" = pp0.\"TreatmentId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$PLAN_PATIENTPRESCRIPTION$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$TREATMENTID+TENANTID$r195$,'')
    AND upper(r.to_table)=upper($r195$TREATMENT_TREATMENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID+TENANTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_BEFORESIGNS$r195$, $r195$TREATMENTID+TENANTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_TREATMENT$r195$, $r195$ID+TENANTID$r195$, $r195$t."Id" = bs0."TreatmentId" AND t."TenantId" = bs0."TenantId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["t.\"Id\" = bs0.\"TreatmentId\"", "t.\"TenantId\" = bs0.\"TenantId\"", "t.\"Id\" = bs0.\"TreatmentId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$TREATMENT_BEFORESIGNS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$TREATMENTID+TENANTID$r195$,'')
    AND upper(r.to_table)=upper($r195$TREATMENT_TREATMENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID+TENANTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_AFTERSIGNS$r195$, $r195$TREATMENTID+TENANTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_TREATMENT$r195$, $r195$ID+TENANTID$r195$, $r195$t."Id" = afs0."TreatmentId" AND t."TenantId" = afs0."TenantId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["t.\"Id\" = afs0.\"TreatmentId\"", "t.\"TenantId\" = afs0.\"TenantId\"", "t.\"Id\" = afs0.\"TreatmentId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$TREATMENT_AFTERSIGNS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$TREATMENTID+TENANTID$r195$,'')
    AND upper(r.to_table)=upper($r195$TREATMENT_TREATMENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID+TENANTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$AUXILIARY_MATERIALINFOMATION$r195$, $r195$ID+TENANTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$PLAN_PATIENTPRESCRIPTIONMATERIAL$r195$, $r195$MATERIALID+TENANTID$r195$, $r195$mi."Id" = ppm."MaterialId" AND mi."TenantId" = ppm."TenantId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["mi.\"Id\" = ppm.\"MaterialId\"", "mi.\"TenantId\" = ppm.\"TenantId\"", "mi.\"Id\" = ppm.\"MaterialId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$AUXILIARY_MATERIALINFOMATION$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$ID+TENANTID$r195$,'')
    AND upper(r.to_table)=upper($r195$PLAN_PATIENTPRESCRIPTIONMATERIAL$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$MATERIALID+TENANTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_DURINGSYMPTOM$r195$, $r195$TREATMENTID+TENANTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_TREATMENT$r195$, $r195$ID+TENANTID$r195$, $r195$t."Id" = s."TreatmentId" AND t."TenantId" = s."TenantId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["t.\"Id\" = s.\"TreatmentId\"", "t.\"TenantId\" = s.\"TenantId\"", "t.\"Id\" = s.\"TreatmentId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$TREATMENT_DURINGSYMPTOM$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$TREATMENTID+TENANTID$r195$,'')
    AND upper(r.to_table)=upper($r195$TREATMENT_TREATMENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID+TENANTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_BEFORECHECK$r195$, $r195$TREATMENTID+TENANTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_TREATMENT$r195$, $r195$ID+TENANTID$r195$, $r195$t."Id" = bc0."TreatmentId" AND t."TenantId" = bc0."TenantId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["t.\"Id\" = bc0.\"TreatmentId\"", "t.\"TenantId\" = bc0.\"TenantId\"", "t.\"Id\" = bc0.\"TreatmentId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$TREATMENT_BEFORECHECK$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$TREATMENTID+TENANTID$r195$,'')
    AND upper(r.to_table)=upper($r195$TREATMENT_TREATMENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID+TENANTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$REGISTER_PATIENTINFOMATION$r195$, $r195$ID+TENANTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_TREATMENT$r195$, $r195$PATIENTID+TENANTID$r195$, $r195$p."Id" = t."PatientId" AND p."TenantId" = t."TenantId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [], "fragments": ["p.\"Id\" = t.\"PatientId\"", "p.\"TenantId\" = t.\"TenantId\"", "p.\"Id\" = t.\"PatientId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$REGISTER_PATIENTINFOMATION$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$ID+TENANTID$r195$,'')
    AND upper(r.to_table)=upper($r195$TREATMENT_TREATMENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENTID+TENANTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$ORGAN_EMPLOYEE$r195$, $r195$ID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$REGISTER_PATIENTINFOMATION$r195$, $r195$RESPONSIBILITYNURSEID$r195$, $r195$primary_emp."Id" = p."ResponsibilityNurseId" AND primary_emp."Id" = p."ResponsibilityNurseId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [], "fragments": ["primary_emp.\"Id\" = p.\"ResponsibilityNurseId\"", "primary_emp.\"Id\" = p.\"ResponsibilityNurseId\"", "primary_emp.\"Id\" = p.\"ResponsibilityNurseId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$ORGAN_EMPLOYEE$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$ID$r195$,'')
    AND upper(r.to_table)=upper($r195$REGISTER_PATIENTINFOMATION$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$RESPONSIBILITYNURSEID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_DURINGSIGNS$r195$, $r195$TREATMENTID+TENANTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_TREATMENT$r195$, $r195$ID+TENANTID$r195$, $r195$t."Id" = ds."TreatmentId" AND t."TenantId" = ds."TenantId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["t.\"Id\" = ds.\"TreatmentId\"", "t.\"TenantId\" = ds.\"TenantId\"", "t.\"Id\" = ds.\"TreatmentId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$TREATMENT_DURINGSIGNS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$TREATMENTID+TENANTID$r195$,'')
    AND upper(r.to_table)=upper($r195$TREATMENT_TREATMENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID+TENANTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_DURINGPARAM$r195$, $r195$TENANTID+TREATMENTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_DURINGSYMPTOM$r195$, $r195$TENANTID+TREATMENTID$r195$, $r195$s."TenantId" = dp."TenantId" AND s."TreatmentId" = dp."TreatmentId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["s.\"TenantId\" = dp.\"TenantId\"", "s.\"TreatmentId\" = dp.\"TreatmentId\"", "s.\"TenantId\" = dp.\"TenantId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$TREATMENT_DURINGPARAM$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$TENANTID+TREATMENTID$r195$,'')
    AND upper(r.to_table)=upper($r195$TREATMENT_DURINGSYMPTOM$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$TENANTID+TREATMENTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$ORDER_PATIENTDAYORDER$r195$, $r195$ID+TENANTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$ORDER_PATIENTDAYORDERDEAL$r195$, $r195$PATIENTDAYORDERID+TENANTID$r195$, $r195$porder."Id" = orderdeal."PatientDayOrderId" AND porder."TenantId" = orderdeal."TenantId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["porder.\"Id\" = orderdeal.\"PatientDayOrderId\"", "porder.\"TenantId\" = orderdeal.\"TenantId\"", "porder.\"Id\" = orderdeal.\"PatientDayOrderId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$ORDER_PATIENTDAYORDER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$ID+TENANTID$r195$,'')
    AND upper(r.to_table)=upper($r195$ORDER_PATIENTDAYORDERDEAL$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENTDAYORDERID+TENANTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$ORDER_PATIENTDAYORDERDEAL$r195$, $r195$TREATMENTID+TENANTID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$TREATMENT_TREATMENT$r195$, $r195$ID+TENANTID$r195$, $r195$treatment."Id" = orderdeal."TreatmentId" AND treatment."TenantId" = orderdeal."TenantId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "JOIN", "blocks": [0], "qualifiers": [], "fragments": ["treatment.\"Id\" = orderdeal.\"TreatmentId\"", "treatment.\"TenantId\" = orderdeal.\"TenantId\"", "treatment.\"Id\" = orderdeal.\"TreatmentId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$ORDER_PATIENTDAYORDERDEAL$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$TREATMENTID+TENANTID$r195$,'')
    AND upper(r.to_table)=upper($r195$TREATMENT_TREATMENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID+TENANTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$ORDER_PATIENTDAYORDER$r195$, $r195$OPERATORID+CREATORID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$ORGAN_EMPLOYEE$r195$, $r195$ID$r195$, $r195$order_doctor."Id" = porder."OperatorId" AND create_doctor."Id" = porder."CreatorId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [], "fragments": ["order_doctor.\"Id\" = porder.\"OperatorId\"", "create_doctor.\"Id\" = porder.\"CreatorId\"", "order_doctor.\"Id\" = porder.\"OperatorId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$ORDER_PATIENTDAYORDER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$OPERATORID+CREATORID$r195$,'')
    AND upper(r.to_table)=upper($r195$ORGAN_EMPLOYEE$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$ORDER_PATIENTDAYORDERDEAL$r195$, $r195$OPERATORID$r195$, $r195$HISTORY_UNRESOLVED$r195$, $r195$ORGAN_EMPLOYEE$r195$, $r195$ID$r195$, $r195$exec_nurse."Id" = orderdeal."OperatorId" AND exec_nurse."Id" = orderdeal."OperatorId"$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: v_EMR_BLOOD_DIALY_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\血透治疗医嘱明细_v_EMR_BLOOD_DIALY_ORDER.sql", "三甲完成视图\\血透治疗记录_v_EMR_BLOOD_DIALY_RECORD.sql", "三甲完成视图\\血透治疗过程记录_v_EMR_BLOOD_DIALY_DETAIL.sql"], "view_names": ["v_EMR_BLOOD_DIALY_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [], "fragments": ["exec_nurse.\"Id\" = orderdeal.\"OperatorId\"", "exec_nurse.\"Id\" = orderdeal.\"OperatorId\"", "exec_nurse.\"Id\" = orderdeal.\"OperatorId\""]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$ORDER_PATIENTDAYORDERDEAL$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$OPERATORID$r195$,'')
    AND upper(r.to_table)=upper($r195$ORGAN_EMPLOYEE$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EMRSD42$r195$, $r195$段落编号$r195$, $r195$DATA_CENTER$r195$, $r195$MTL.EPR_INPATIENT$r195$, $r195$ID$r195$, $r195$T3.段落编号 = T1.ID$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\转科记录_v_EMR_HOS_CHANGE_MAJOR_RECORD.sql"], "view_names": ["ODS.V_EMR_HOS_CHANGE_MAJOR_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "date_window", "raw": "pv.discharge_date_time >= to_date('2021-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "date_window", "raw": "pv.discharge_date_time <  to_date('2026-01-01 00:00:00', 'yyyy-mm-dd hh24:mi:ss')"}, {"kind": "status_literal", "col": "DOC_TYPE_NAME", "value": "转科记录", "raw": "t1.doc_type_name = '转科记录'"}, {"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "d.diagnosis_type = '3'"}], "fragments": ["T3.段落编号 = T1.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$MTL.EMRSD42$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$段落编号$r195$,'')
    AND upper(r.to_table)=upper($r195$MTL.EPR_INPATIENT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.ADT_LOG$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$b.patient_id = a.patient_id AND b.visit_id = a.visit_id$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_REFERRAL_HOS_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\转诊_院纪录（转出记录）_v_EMR_REFERRAL_HOS_RECORD.sql"], "view_names": ["ODS.V_EMR_REFERRAL_HOS_RECORD"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               a.attending_doctor\n           ),\n           1,\n           50\n       ) as"}], "fragments": ["b.patient_id = a.patient_id", "b.visit_id = a.visit_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.ADT_LOG$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$SX.B_T_REACTIONS$r195$, $r195$SQLSH$r195$, $r195$DATA_CENTER$r195$, $r195$SX.B_T_REQD$r195$, $r195$SQLSH$r195$, $r195$tr.sqlsh = r.sqlsh$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INFOR_TRANS_BLOOD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\输血治疗同意书_v_EMR_INFOR_TRANS_BLOOD.sql"], "view_names": ["ODS.V_EMR_INFOR_TRANS_BLOOD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [], "fragments": ["tr.sqlsh = r.sqlsh"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$SX.B_T_REACTIONS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$SQLSH$r195$,'')
    AND upper(r.to_table)=upper($r195$SX.B_T_REQD$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$SQLSH$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SX.B_T_REQD$r195$, $r195$HZBS+ZYCS$r195$, $r195$tr.hzbs = p.patient_id AND tr.zycs = p.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INFOR_TRANS_BLOOD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\输血治疗同意书_v_EMR_INFOR_TRANS_BLOOD.sql"], "view_names": ["ODS.V_EMR_INFOR_TRANS_BLOOD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [], "fragments": ["tr.hzbs = p.patient_id", "tr.zycs = p.visit_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SX.B_T_REQD$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$HZBS+ZYCS$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.STAFF_DICT$r195$, $r195$TITLE$r195$, $r195$DATA_CENTER$r195$, $r195$ODS.TITLE_DICT$r195$, $r195$TITLE_NAME$r195$, $r195$sd.title = td.title_name$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊_急诊就诊记录(D02标）_v_EMR_OUTPATIENT_RECORD.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "null_filter", "raw": "x.returned_date is null"}, {"kind": "rownum_limit", "raw": "rownum = 1\n                )\n           then '2'\n           else '1'\n       end as FALG_FIRST_VISIT,"}, {"kind": "null_filter", "raw": "x.returned_date is null"}, {"kind": "rownum_limit", "raw": "rownum = 1\n                )\n           then '复诊'\n           else '初诊'\n       end as FALG_FIRST_VISI"}], "fragments": ["sd.title = td.title_name"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.STAFF_DICT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$TITLE$r195$,'')
    AND upper(r.to_table)=upper($r195$ODS.TITLE_DICT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$TITLE_NAME$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.CLINIC_MASTER$r195$, $r195$VISIT_DATE+VISIT_NO+PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.OUTP_MR_DIAG_DESC$r195$, $r195$VISIT_DATE+VISIT_NO+PATIENT_ID$r195$, $r195$a.visit_date = b.visit_date AND a.visit_no = b.visit_no$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_DIAG$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊_急诊就诊诊断表_v_EMR_OUTPATIENT_DIAG.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_DIAG"], "join_type": "JOIN", "blocks": [0, 1], "qualifiers": [{"kind": "date_window", "raw": "a.visit_date >= DATE '2021-01-01'"}, {"kind": "date_window", "raw": "a.visit_date <  DATE '2026-01-01'\n                       ) q\n\n                  LEFT JOIN (\n                        SELECT TO_CHAR(cd.院标编码) AS match_value,\n                               MAX(TO_CHAR(c"}, {"kind": "null_filter", "raw": "cd.院标编码 IS NOT NULL"}, {"kind": "date_window", "raw": "a.visit_date >= DATE '2021-01-01'"}], "fragments": ["a.visit_date = b.visit_date", "a.visit_no = b.visit_no", "a.patient_id = b.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.CLINIC_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$VISIT_DATE+VISIT_NO+PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.OUTP_MR_DIAG_DESC$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$VISIT_DATE+VISIT_NO+PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.OUTP_MR_DIAG_DESC$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$a.patient_id = pmi.patient_id AND a.patient_id = pmi.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_DIAG$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊_急诊就诊诊断表_v_EMR_OUTPATIENT_DIAG.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_DIAG"], "join_type": "JOIN", "blocks": [0, 1], "qualifiers": [{"kind": "date_window", "raw": "a.visit_date >= DATE '2021-01-01'"}, {"kind": "date_window", "raw": "a.visit_date <  DATE '2026-01-01'\n                       ) q\n\n                  LEFT JOIN (\n                        SELECT TO_CHAR(cd.院标编码) AS match_value,\n                               MAX(TO_CHAR(c"}, {"kind": "null_filter", "raw": "cd.院标编码 IS NOT NULL"}, {"kind": "date_window", "raw": "a.visit_date >= DATE '2021-01-01'"}], "fragments": ["a.patient_id = pmi.patient_id", "a.patient_id = pmi.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.OUTP_MR_DIAG_DESC$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.CLINIC_MASTER$r195$, $r195$CLINIC_NO$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DRUG_PRESC_MASTER$r195$, $r195$CLINIC_NO$r195$, $r195$a.clinic_no = d.clinic_no$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_RECIPE$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊处方(D03_D04标）_v_EMR_OUTPATIENT_RECIPE.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_RECIPE"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               case when pmi.id_no is not null then '01' else '99' end\n           ),\n  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               case when pmi.id_no is not null then '居民身份证' else '其他法定有效证件' end\n       "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               d.visit_dept\n           ),\n           1,\n           20\n       ) as DEP_C"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               nvl(\n                   (select ks.dept_name\n                      from "}], "fragments": ["a.clinic_no = d.clinic_no"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.CLINIC_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$CLINIC_NO$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.DRUG_PRESC_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$CLINIC_NO$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DRUG_PRESC_MASTER$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$a.patient_id = pmi.patient_id AND pmi.patient_id = a.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_RECIPE,ODS.V_EMR_OUTPATIENT_RECIPE_ITEM$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊处方(D03_D04标）_v_EMR_OUTPATIENT_RECIPE.sql", "三甲完成视图\\门诊处方明细(辅D03_D04标）_v_EMR_OUTPATIENT_RECIPE_ITEM.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_RECIPE", "ODS.V_EMR_OUTPATIENT_RECIPE_ITEM"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               case when pmi.id_no is not null then '01' else '99' end\n           ),\n  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               case when pmi.id_no is not null then '居民身份证' else '其他法定有效证件' end\n       "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               d.visit_dept\n           ),\n           1,\n           20\n       ) as DEP_C"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               nvl(\n                   (select ks.dept_name\n                      from "}], "fragments": ["a.patient_id = pmi.patient_id", "pmi.patient_id = a.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DRUG_PRESC_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DRUG_DICT$r195$, $r195$DRUG_CODE$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DRUG_PRESC_DETAIL$r195$, $r195$DRUG_CODE$r195$, $r195$dp.drug_code = b.drug_code$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_RECIPE$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊处方(D03_D04标）_v_EMR_OUTPATIENT_RECIPE.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_RECIPE"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               case when pmi.id_no is not null then '01' else '99' end\n           ),\n  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               case when pmi.id_no is not null then '居民身份证' else '其他法定有效证件' end\n       "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               d.visit_dept\n           ),\n           1,\n           20\n       ) as DEP_C"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               nvl(\n                   (select ks.dept_name\n                      from "}], "fragments": ["dp.drug_code = b.drug_code"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DRUG_DICT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$DRUG_CODE$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.DRUG_PRESC_DETAIL$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$DRUG_CODE$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$CDA.CDA_DICTIONARY$r195$, $r195$院标编码$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$ID_TYPE$r195$, $r195$zd.院标编码 = pmi.id_type AND zd.院标编码 = pmi.id_type$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_RECIPE,ODS.V_EMR_OUTPATIENT_REGISTER$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊处方(D03_D04标）_v_EMR_OUTPATIENT_RECIPE.sql", "三甲完成视图\\门诊挂号(D01标）_v_EMR_OUTPATIENT_REGISTER.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_RECIPE", "ODS.V_EMR_OUTPATIENT_REGISTER"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               case when pmi.id_no is not null then '01' else '99' end\n           ),\n  "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               case when pmi.id_no is not null then '居民身份证' else '其他法定有效证件' end\n       "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               d.visit_dept\n           ),\n           1,\n           20\n       ) as DEP_C"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               nvl(\n                   (select ks.dept_name\n                      from "}], "fragments": ["zd.院标编码 = pmi.id_type", "zd.院标编码 = pmi.id_type", "zd.院标编码 = b.id_type"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$CDA.CDA_DICTIONARY$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$院标编码$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ID_TYPE$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DRUG_PRESC_DETAIL$r195$, $r195$PRESC_DATE+PRESC_NO$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DRUG_PRESC_MASTER$r195$, $r195$PRESC_DATE+PRESC_NO$r195$, $r195$t.presc_date = a.presc_date AND t.presc_no   = a.presc_no$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_RECIPE_ITEM$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊处方明细(辅D03_D04标）_v_EMR_OUTPATIENT_RECIPE_ITEM.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_RECIPE_ITEM"], "join_type": "JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "CATEGORY_CODE", "value": "CC99.00203", "raw": "v.category_code = 'CC99.00203'"}, {"kind": "null_filter", "raw": "(\n                              pl.stop_date IS NULL\n                              OR pl.stop_date >= a.presc_date\n                          )\n       "}], "fragments": ["t.presc_date = a.presc_date", "t.presc_no   = a.presc_no"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DRUG_PRESC_DETAIL$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PRESC_DATE+PRESC_NO$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.DRUG_PRESC_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PRESC_DATE+PRESC_NO$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.CLINIC_MASTER$r195$, $r195$CLINIC_NO+PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DRUG_PRESC_MASTER$r195$, $r195$CLINIC_NO+PATIENT_ID$r195$, $r195$d.clinic_no  = a.clinic_no AND d.patient_id = a.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_RECIPE_ITEM$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊处方明细(辅D03_D04标）_v_EMR_OUTPATIENT_RECIPE_ITEM.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_RECIPE_ITEM"], "join_type": "JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "CATEGORY_CODE", "value": "CC99.00203", "raw": "v.category_code = 'CC99.00203'"}, {"kind": "null_filter", "raw": "(\n                              pl.stop_date IS NULL\n                              OR pl.stop_date >= a.presc_date\n                          )\n       "}], "fragments": ["d.clinic_no  = a.clinic_no", "d.patient_id = a.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.CLINIC_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$CLINIC_NO+PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.DRUG_PRESC_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$CLINIC_NO+PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DRUG_PRESC_DETAIL$r195$, $r195$DRUG_CODE$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.MED_DICT_BASEINFO$r195$, $r195$DRUG_ID$r195$, $r195$m.drug_id = t.drug_code$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_RECIPE_ITEM$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊处方明细(辅D03_D04标）_v_EMR_OUTPATIENT_RECIPE_ITEM.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_RECIPE_ITEM"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "CATEGORY_CODE", "value": "CC99.00203", "raw": "v.category_code = 'CC99.00203'"}, {"kind": "null_filter", "raw": "(\n                              pl.stop_date IS NULL\n                              OR pl.stop_date >= a.presc_date\n                          )\n       "}], "fragments": ["m.drug_id = t.drug_code"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DRUG_PRESC_DETAIL$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$DRUG_CODE$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.MED_DICT_BASEINFO$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$DRUG_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$, $r195$HOSPITAL_CODE$r195$, $r195$DATA_CENTER$r195$, $r195$PORTAL_USER.PORTAL_SYS_DICT$r195$, $r195$DICT_CODE$r195$, $r195$v.hospital_code = p.dict_code$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_RECIPE_ITEM$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊处方明细(辅D03_D04标）_v_EMR_OUTPATIENT_RECIPE_ITEM.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_RECIPE_ITEM"], "join_type": "JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "CATEGORY_CODE", "value": "CC99.00203", "raw": "v.category_code = 'CC99.00203'"}, {"kind": "null_filter", "raw": "(\n                              pl.stop_date IS NULL\n                              OR pl.stop_date >= a.presc_date\n                          )\n       "}], "fragments": ["v.hospital_code = p.dict_code"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$HOSPITAL_CODE$r195$,'')
    AND upper(r.to_table)=upper($r195$PORTAL_USER.PORTAL_SYS_DICT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$DICT_CODE$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DRUG_PRESC_DETAIL$r195$, $r195$DRUG_CODE+FIRM_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DRUG_PRICE_LIST$r195$, $r195$DRUG_CODE+FIRM_ID$r195$, $r195$pl.drug_code = t.drug_code AND pl.firm_id = t.firm_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_RECIPE_ITEM$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊处方明细(辅D03_D04标）_v_EMR_OUTPATIENT_RECIPE_ITEM.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_RECIPE_ITEM"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "CATEGORY_CODE", "value": "CC99.00203", "raw": "v.category_code = 'CC99.00203'"}, {"kind": "null_filter", "raw": "(\n                              pl.stop_date IS NULL\n                              OR pl.stop_date >= a.presc_date\n                          )\n       "}], "fragments": ["pl.drug_code = t.drug_code", "pl.firm_id = t.firm_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DRUG_PRESC_DETAIL$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$DRUG_CODE+FIRM_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.DRUG_PRICE_LIST$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$DRUG_CODE+FIRM_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.CLINIC_MASTER$r195$, $r195$VISIT_DEPT$r195$, $r195$DATA_CENTER$r195$, $r195$SHUNNENG.APPOINTINFOVIEW$r195$, $r195$DEPTID$r195$, $r195$aa.deptid = a.visit_dept$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUTPATIENT_REGISTER$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门诊挂号(D01标）_v_EMR_OUTPATIENT_REGISTER.sql"], "view_names": ["ODS.V_EMR_OUTPATIENT_REGISTER"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n               case when b.id_no is not null then '01' else '99' end\n           ),\n    "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               case when b.id_no is not null then '居民身份证' else '其他法定有效证件' end\n         "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n               a.visit_dept\n           ),\n           1,\n           20\n       ) as STD_D"}, {"kind": "date_window", "raw": "to_date(aa.registertime, 'yyyy-mm-dd hh24:mi:ss') >= a.registering_date - 7"}], "fragments": ["aa.deptid = a.visit_dept"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.CLINIC_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$VISIT_DEPT$r195$,'')
    AND upper(r.to_table)=upper($r195$SHUNNENG.APPOINTINFOVIEW$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$DEPTID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.OUTP_RCPT_MASTER$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_MASTER_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$a.patient_id = b.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUT_FEE_INFO_MAIN$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门（急）诊费用信息主表_v_EMR_out_fee_info_main.sql"], "view_names": ["ODS.V_EMR_OUT_FEE_INFO_MAIN"], "join_type": "JOIN", "blocks": [0], "qualifiers": [{"kind": "null_filter", "raw": "pl.mr_bill_class is not null"}, {"kind": "null_filter", "raw": "(\n                                          pl.stop_date is null\n                                       or obi.visit_date < pl.stop_date\n             "}], "fragments": ["a.patient_id = b.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.OUTP_RCPT_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_MASTER_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.OUTP_BILL_ITEMS$r195$, $r195$ITEM_CLASS+ITEM_CODE$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PRICE_LIST$r195$, $r195$ITEM_CLASS+ITEM_CODE$r195$, $r195$pl.item_class = obi.item_class AND pl.item_code  = obi.item_code$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUT_FEE_INFO_MAIN$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门（急）诊费用信息主表_v_EMR_out_fee_info_main.sql"], "view_names": ["ODS.V_EMR_OUT_FEE_INFO_MAIN"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "null_filter", "raw": "pl.mr_bill_class is not null"}, {"kind": "null_filter", "raw": "(\n                                          pl.stop_date is null\n                                       or obi.visit_date < pl.stop_date\n             "}], "fragments": ["pl.item_class = obi.item_class", "pl.item_code  = obi.item_code"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.OUTP_BILL_ITEMS$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$ITEM_CLASS+ITEM_CODE$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PRICE_LIST$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ITEM_CLASS+ITEM_CODE$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.OUTP_RCPT_MASTER$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$, $r195$PATIENT_ID$r195$, $r195$e.patient_id = a.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_OUT_FEE_INFO_CHILD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\门（急）诊费用明细表_v_EMR_OUT_FEE_INFO_CHILD.sql"], "view_names": ["ODS.V_EMR_OUT_FEE_INFO_CHILD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "CATEGORY_CODE", "value": "DM04-001", "raw": "CATEGORY_CODE='DM04-001'"}], "fragments": ["e.patient_id = a.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.OUTP_RCPT_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$ODS.CDA_VALUE_DOMAIN_MAP$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.MCS_DOC_FORM$r195$, $r195$PATIENT_UID+ID$r195$, $r195$MOBILE_NURSING$r195$, $r195$LUNA_MCS_SDSEY.MCS_DOC_FORM_RECORDS$r195$, $r195$PATIENT_UID+FORM_ID$r195$, $r195$a.patient_uid = WSFL.Patient_Uid AND a.patient_uid = WSFL.Patient_Uid$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: LUNA_MCS_SDSEY.V_EMR_CHILDBIRTH$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\阴道分娩记录_v_EMR_CHILDBIRTH.sql"], "view_names": ["LUNA_MCS_SDSEY.V_EMR_CHILDBIRTH"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "DIAGNOSIS_TYPE", "value": "3", "raw": "dg.diagnosis_type = '3'"}, {"kind": "status_literal", "col": "TEMPLATE_CODE", "value": "742", "raw": "a.template_code = '742'"}, {"kind": "status_literal", "col": "NODE_CODE", "value": "00005", "raw": "a.node_code = '00005'"}, {"kind": "rownum_limit", "raw": "ROWNUM = 1),\n           0\n       ) AS BIRTH_TIMES,  \n\n       NVL(\n           (SELECT TO_NUMBER(REGEX"}], "fragments": ["a.patient_uid = WSFL.Patient_Uid", "a.patient_uid = WSFL.Patient_Uid", "a.FORM_ID = WSFL.ID"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$LUNA_MCS_SDSEY.MCS_DOC_FORM$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_UID+ID$r195$,'')
    AND upper(r.to_table)=upper($r195$LUNA_MCS_SDSEY.MCS_DOC_FORM_RECORDS$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_UID+FORM_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.DEPT_DICT$r195$, $r195$DEPT_CODE$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.INP_BILL_DETAIL$r195$, $r195$DEPT_CODE$r195$, $r195$b.DEPT_CODE = d.DEPT_CODE$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_CONSUMABLES$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\高值耗材使用记录_V_EMR_CONSUMABLES.sql"], "view_names": ["ODS.V_EMR_CONSUMABLES"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "status_literal", "col": "CLASS_ON_MR", "value": "材料", "raw": "b.CLASS_ON_MR = '材料'"}, {"kind": "date_window", "raw": "b.BILLING_DATE_TIME >= DATE '2021-01-01'"}, {"kind": "date_window", "raw": "b.BILLING_DATE_TIME < DATE '2026-01-01'"}], "fragments": ["b.DEPT_CODE = d.DEPT_CODE"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.DEPT_DICT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$DEPT_CODE$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.INP_BILL_DETAIL$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$DEPT_CODE$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_ANESTHESIA_EVENT$r195$, $r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$, $r195$mae.patient_id = b.patient_id AND mae.visit_id   = b.visit_id$r195$, $r195$195三甲视图摄入候选（candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ANES_RECORD_MED$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\麻醉手术中用药记录_v_EMR_ANES_RECORD_MED.sql"], "view_names": ["ODS.V_EMR_ANES_RECORD_MED"], "join_type": "JOIN", "blocks": [0], "qualifiers": [{"kind": "in_subset", "raw": "mae.item_class in ('2','3','C')"}, {"kind": "null_filter", "raw": "mae.item_name is not null"}, {"kind": "null_filter", "raw": "mae.start_time is not null"}, {"kind": "null_filter", "raw": "mae.dosage is not null"}], "fragments": ["mae.patient_id = b.patient_id", "mae.visit_id   = b.visit_id", "mae.oper_id    = b.oper_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$SM.MED_ANESTHESIA_EVENT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_ANESTHESIA_PLAN$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$a.patient_id = v.patient_id AND a.visit_id   = v.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ANESTHESIA_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\麻醉手术记录_v_EMR_ANESTHESIA_RECORD.sql"], "view_names": ["ODS.V_EMR_ANESTHESIA_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           v.dept_admission_to\n         ),\n         1,\n         20\n       ) as DEPT_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           (select hd.dept_name\n              from his.dept_dict hd\n             where "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n         ),\n         1,\n         50\n       ) as DEPT_NAME, \n\n       substr(\n         nvl"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           v.discharge_ward_code\n         ),\n         1,\n         50\n       ) as WARD_N"}], "fragments": ["a.patient_id = v.patient_id", "a.visit_id   = v.visit_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_ANESTHESIA_PLAN$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$CDA.CDA_DICTIONARY$r195$, $r195$院标名称$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$OPERATION_NAME+ANESTHESIA_METHOD$r195$, $r195$cd.院标名称 = b.operation_name AND cd.院标名称 = b.operation_name$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ANESTHESIA_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\麻醉手术记录_v_EMR_ANESTHESIA_RECORD.sql"], "view_names": ["ODS.V_EMR_ANESTHESIA_RECORD"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           v.dept_admission_to\n         ),\n         1,\n         20\n       ) as DEPT_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           (select hd.dept_name\n              from his.dept_dict hd\n             where "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n         ),\n         1,\n         50\n       ) as DEPT_NAME, \n\n       substr(\n         nvl"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           v.discharge_ward_code\n         ),\n         1,\n         50\n       ) as WARD_N"}], "fragments": ["cd.院标名称 = b.operation_name", "cd.院标名称 = b.operation_name", "cd.院标名称 = b.anesthesia_method"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$CDA.CDA_DICTIONARY$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$院标名称$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$OPERATION_NAME+ANESTHESIA_METHOD$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_CUSTOM_DATA$r195$, $r195$VISIT_ID+OPER_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$VISIT_ID+OPER_ID$r195$, $r195$sq.visit_id   = b.visit_id AND sq.oper_id    = b.oper_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ANESTHESIA_RECORD,ODS.V_EMR_BOFORE_OPERA_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\麻醉手术记录_v_EMR_ANESTHESIA_RECORD.sql", "三甲完成视图\\麻醉术前访视记录_v_EMR_BOFORE_OPERA_RECORD.sql"], "view_names": ["ODS.V_EMR_ANESTHESIA_RECORD", "ODS.V_EMR_BOFORE_OPERA_RECORD"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           v.dept_admission_to\n         ),\n         1,\n         20\n       ) as DEPT_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           (select hd.dept_name\n              from his.dept_dict hd\n             where "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n         ),\n         1,\n         50\n       ) as DEPT_NAME, \n\n       substr(\n         nvl"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           v.discharge_ward_code\n         ),\n         1,\n         50\n       ) as WARD_N"}], "fragments": ["sq.visit_id   = b.visit_id", "sq.oper_id    = b.oper_id", "sq.visit_id   = b.visit_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$SM.MED_CUSTOM_DATA$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$VISIT_ID+OPER_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$VISIT_ID+OPER_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$PATIENT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_PAT_MASTER_INDEX$r195$, $r195$PATIENT_ID$r195$, $r195$a.patient_id = b.patient_id AND a.patient_id = b.patient_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_ANES_AFTER_RECORD,ODS.V_EMR_BOFORE_OPERA_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\麻醉术前访视记录_v_EMR_BOFORE_OPERA_RECORD.sql", "三甲完成视图\\麻醉术后访视记录_v_EMR_ANES_AFTER_RECORD.sql"], "view_names": ["ODS.V_EMR_ANES_AFTER_RECORD", "ODS.V_EMR_BOFORE_OPERA_RECORD"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           (select hd.qmpt_name\n              from his.dept_dict hd\n             where "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n         ),\n         1,\n         50\n       ) as DEPT_NAME, \n\n       substr(\n         nvl"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           p.dept_admission_to\n         ),\n         1,\n         20\n       ) as DEPT_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           p.discharge_ward_code\n         ),\n         1,\n         50\n       ) as WARD_N"}], "fragments": ["a.patient_id = b.patient_id", "a.patient_id = b.patient_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_PAT_MASTER_INDEX$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$CDA.CDA_DICTIONARY$r195$, $r195$院标名称$r195$, $r195$DATA_CENTER$r195$, $r195$HIS.PAT_VISIT$r195$, $r195$BLOOD_TYPE+BLOOD_TYPE_RH$r195$, $r195$cd.院标名称 = p.blood_type AND cd.院标名称 = p.blood_type_rh$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_BOFORE_OPERA_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\麻醉术前访视记录_v_EMR_BOFORE_OPERA_RECORD.sql"], "view_names": ["ODS.V_EMR_BOFORE_OPERA_RECORD"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           (select hd.qmpt_name\n              from his.dept_dict hd\n             where "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n         ),\n         1,\n         50\n       ) as DEPT_NAME, \n\n       substr(\n         nvl"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           p.dept_admission_to\n         ),\n         1,\n         20\n       ) as DEPT_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           p.discharge_ward_code\n         ),\n         1,\n         50\n       ) as WARD_N"}], "fragments": ["cd.院标名称 = p.blood_type", "cd.院标名称 = p.blood_type_rh"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$CDA.CDA_DICTIONARY$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$院标名称$r195$,'')
    AND upper(r.to_table)=upper($r195$HIS.PAT_VISIT$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$BLOOD_TYPE+BLOOD_TYPE_RH$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$CDA.CDA_DICTIONARY$r195$, $r195$院标名称$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$OPERATION_NAME$r195$, $r195$cd.院标名称 = a.operation_name$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_BOFORE_OPERA_RECORD$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\麻醉术前访视记录_v_EMR_BOFORE_OPERA_RECORD.sql"], "view_names": ["ODS.V_EMR_BOFORE_OPERA_RECORD"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "rownum_limit", "raw": "rownum = 1),\n           (select hd.qmpt_name\n              from his.dept_dict hd\n             where "}, {"kind": "rownum_limit", "raw": "rownum = 1)\n         ),\n         1,\n         50\n       ) as DEPT_NAME, \n\n       substr(\n         nvl"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           p.dept_admission_to\n         ),\n         1,\n         20\n       ) as DEPT_COD"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n           p.discharge_ward_code\n         ),\n         1,\n         50\n       ) as WARD_N"}], "fragments": ["cd.院标名称 = a.operation_name"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$CDA.CDA_DICTIONARY$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$院标名称$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$OPERATION_NAME$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_SCHEDULE$r195$, $r195$PATIENT_ID+VISIT_ID+SCHEDULE_ID$r195$, $r195$mos.patient_id = mom.patient_id AND mos.visit_id = mom.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INFOR_ANESTHESIA$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\麻醉知情同意书_v_emr_infor_anesthesia.sql"], "view_names": ["ODS.V_EMR_INFOR_ANESTHESIA"], "join_type": "LEFT JOIN", "blocks": [0], "qualifiers": [{"kind": "null_filter", "raw": "(\n              to_char(o.operation_no) = to_char(mom.oper_id)\n\n           or (\n                  o.operating_date is not null\n              and nvl(m"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(cast(pv.dept_discharge_from as varchar2(50)), '-')\n         "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '-'\n                   ),\n                   1,\n                "}], "fragments": ["mos.patient_id = mom.patient_id", "mos.visit_id = mom.visit_id", "mos.schedule_id = mom.oper_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID+OPER_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_SCHEDULE$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID+SCHEDULE_ID$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$CDA.CDA_DICTIONARY$r195$, $r195$院标名称$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$ANESTHESIA_METHOD$r195$, $r195$cd.院标名称 = mom.anesthesia_method$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INFOR_ANESTHESIA$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\麻醉知情同意书_v_emr_infor_anesthesia.sql"], "view_names": ["ODS.V_EMR_INFOR_ANESTHESIA"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "null_filter", "raw": "(\n              to_char(o.operation_no) = to_char(mom.oper_id)\n\n           or (\n                  o.operating_date is not null\n              and nvl(m"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(cast(pv.dept_discharge_from as varchar2(50)), '-')\n         "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '-'\n                   ),\n                   1,\n                "}], "fragments": ["cd.院标名称 = mom.anesthesia_method"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$CDA.CDA_DICTIONARY$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$院标名称$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$ANESTHESIA_METHOD$r195$,'')
);

INSERT INTO asset.asset_relation_reviews
(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,
 join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)
SELECT $r195$r195_intake$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_CUSTOM_DATA$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$DATA_CENTER$r195$, $r195$SM.MED_OPERATION_MASTER$r195$, $r195$PATIENT_ID+VISIT_ID$r195$, $r195$mcd.patient_id = mom.patient_id AND mcd.visit_id = mom.visit_id$r195$, $r195$195三甲视图摄入候选（recipe_candidate）$r195$, $r195$涉及视图: ODS.V_EMR_INFOR_ANESTHESIA$r195$, $r195$C$r195$, 'draft', $r195${"run_id": "r195-20260919-084932", "parser": "heuristic_v1", "source_files": ["三甲完成视图\\麻醉知情同意书_v_emr_infor_anesthesia.sql"], "view_names": ["ODS.V_EMR_INFOR_ANESTHESIA"], "join_type": "WHERE", "blocks": [0], "qualifiers": [{"kind": "null_filter", "raw": "(\n              to_char(o.operation_no) = to_char(mom.oper_id)\n\n           or (\n                  o.operating_date is not null\n              and nvl(m"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(cast(pv.dept_discharge_from as varchar2(50)), '-')\n         "}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       nvl(\n                           (select cast(ks.dept_name as var"}, {"kind": "rownum_limit", "raw": "rownum = 1),\n                       '-'\n                   ),\n                   1,\n                "}], "fragments": ["mcd.patient_id = mom.patient_id", "mcd.visit_id = mom.visit_id"]}$r195$, now()
WHERE NOT EXISTS (
  SELECT 1 FROM asset.asset_relation_reviews r
  WHERE r.relation_scope = $r195$r195_intake$r195$
    AND upper(r.from_table)=upper($r195$SM.MED_CUSTOM_DATA$r195$) AND coalesce(r.from_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
    AND upper(r.to_table)=upper($r195$SM.MED_OPERATION_MASTER$r195$) AND coalesce(r.to_columns,'')=coalesce($r195$PATIENT_ID+VISIT_ID$r195$,'')
);


ROLLBACK;
