-- r197 S7 A2+A3 生产入库 | 单事务执行: psql -1 -v ON_ERROR_STOP=1
-- run_id=r197-20260921-s1 | recipe payload SHA-256 前16: 763f565a17ba3642 | 2026-09-21 用户批准

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s3-01_41f4e60a13e5$r197b$, $r197b$门诊费用三表链（收据-明细-开单）$r197b$, 'draft', $r197b$门诊收费$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$门诊费用三表链（收据-明细-开单）（197历史SQL摄入配方候选；主事实粒度：收据行（RCPT_NO）/ 明细行（RCPT_NO+项目序号））$r197b$, $r197b$门诊收费$r197b$,
 $r197b$["OUTP_RCPT_MASTER", "OUTP_BILL_ITEMS", "OUTP_ORDER_DESC"]$r197b$::jsonb, $r197b${"join_family_ids": ["S2F-B460DFC719", "S2F-0BF98D1B1C", "S2F-2A80F74804", "S3F:OUTP_ORDER_DESC.RCPT_NO=OUTP_RCPT_MASTER.RCPT_NO"], "dedup_strategy": "明细↔开单必须三列复合键（RCPT_NO+VISIT_NO+VISIT_DATE）；DISTINCT/MAX 不能替代键补全（重打收据同键多行会被错误去重）", "time_fields": ["VISIT_DATE", "CHARGE_DATE_TIME（以元数据为准）"]}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S3-01", "name": "门诊费用三表链（收据-明细-开单）", "domain": "门诊收费", "primary_tables": ["OUTP_RCPT_MASTER", "OUTP_BILL_ITEMS", "OUTP_ORDER_DESC"], "join_family_ids": ["S2F-B460DFC719", "S2F-0BF98D1B1C", "S2F-2A80F74804", "S3F:OUTP_ORDER_DESC.RCPT_NO=OUTP_RCPT_MASTER.RCPT_NO"], "main_fact_grain": "收据行（RCPT_NO）/ 明细行（RCPT_NO+项目序号）", "dedup_strategy": "明细↔开单必须三列复合键（RCPT_NO+VISIT_NO+VISIT_DATE）；DISTINCT/MAX 不能替代键补全（重打收据同键多行会被错误去重）", "time_fields": ["VISIT_DATE", "CHARGE_DATE_TIME（以元数据为准）"], "conservation_probe": "S3-P003：按 RCPT_NO 聚合 SUM(OUTP_BILL_ITEMS.CHARGES) 对 OUTP_RCPT_MASTER 收据总额列，差额=0 行占比；JOIN 前后行数守恒", "original_caliber": "历史语句以 RCPT_NO 单列挂明细与开单（S2 已标半键 ISS-HK）；代表：F0298 账不平(3).sql", "suggested_caliber": "明细↔开单用三列复合键；收据↔支付另按 RCP-S3-02 对账；人群按收费时间（CHARGE/CHARGE_DATE_TIME）与挂号时间（VISIT_DATE）二选一并写明口径", "risks": ["RCPT_NO-only 半键（重打/退费多行）", "门诊收据总额列名需元数据核对", "按收费时间vs挂号时间人群不同"], "evidence": [{"unit": "F0298", "file": "小孙遗产\\账不平(3).sql", "lines": [16, 22]}, {"unit": "F0134", "file": "小卢sql\\月初报表数据.sql", "lines": [230, 230]}], "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": [{"unit": "F0298", "file": "小孙遗产\\账不平(3).sql", "lines": [16, 22]}, {"unit": "F0134", "file": "小卢sql\\月初报表数据.sql", "lines": [230, 230]}], "conservation_probe": "S3-P003：按 RCPT_NO 聚合 SUM(OUTP_BILL_ITEMS.CHARGES) 对 OUTP_RCPT_MASTER 收据总额列，差额=0 行占比；JOIN 前后行数守恒"}$r197b$::jsonb, $r197b${"risks": ["RCPT_NO-only 半键（重打/退费多行）", "门诊收据总额列名需元数据核对", "按收费时间vs挂号时间人群不同"], "original_caliber": "历史语句以 RCPT_NO 单列挂明细与开单（S2 已标半键 ISS-HK）；代表：F0298 账不平(3).sql", "suggested_caliber": "明细↔开单用三列复合键；收据↔支付另按 RCP-S3-02 对账；人群按收费时间（CHARGE/CHARGE_DATE_TIME）与挂号时间（VISIT_DATE）二选一并写明口径"}$r197b$::jsonb, $r197b$41f4e60a13e5$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s3-01_41f4e60a13e5$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s3-02_5bc0925f69a2$r197b$, $r197b$门诊支付/退费金额对账$r197b$, 'draft', $r197b$门诊收费$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$门诊支付/退费金额对账（197历史SQL摄入配方候选；主事实粒度：支付流水行）$r197b$, $r197b$门诊收费$r197b$,
 $r197b$["OUTP_RCPT_MASTER", "OUTP_PAYMENTS_MONEY"]$r197b$::jsonb, $r197b${"join_family_ids": ["S3F:OUTP_PAYMENTS_MONEY.RCPT_NO=OUTP_RCPT_MASTER.RCPT_NO（PLAT 554/556+草稿7）"], "dedup_strategy": "按 RCPT_NO 聚合，不做行级 DISTINCT", "time_fields": ["收费时间（CHARGE_INDICATOR=0 过滤的收据时间语义待核）"]}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S3-02", "name": "门诊支付/退费金额对账", "domain": "门诊收费", "primary_tables": ["OUTP_RCPT_MASTER", "OUTP_PAYMENTS_MONEY"], "join_family_ids": ["S3F:OUTP_PAYMENTS_MONEY.RCPT_NO=OUTP_RCPT_MASTER.RCPT_NO（PLAT 554/556+草稿7）"], "main_fact_grain": "支付流水行", "dedup_strategy": "按 RCPT_NO 聚合，不做行级 DISTINCT", "time_fields": ["收费时间（CHARGE_INDICATOR=0 过滤的收据时间语义待核）"], "conservation_probe": "S3-P003：SUM(PAYMENT_AMOUNT)-SUM(REFUNDED_AMOUNT) 按 RCPT_NO 与收据金额对账", "original_caliber": "nvl(sum(nvl(PAYMENT_AMOUNT,0)-nvl(REFUNDED_AMOUNT,0)),0) 消费金额，WHERE CHARGE_INDICATOR=0 AND MONEY_TYPE='预交金'（F0298）", "suggested_caliber": "同口径；MONEY_TYPE/CHARGE_INDICATOR 值域无 confirmed——执行前【值域待确认】，退费/冲销方向以 TRANSACT_TYPE 类字段值域为准（待确认）", "risks": ["MONEY_TYPE/CHARGE_INDICATOR 值域未确认", "退费冲销行重复计入", "部分结算多支付方式行"], "evidence": [{"unit": "F0298", "file": "小孙遗产\\账不平(3).sql", "lines": [16, 22]}], "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": [{"unit": "F0298", "file": "小孙遗产\\账不平(3).sql", "lines": [16, 22]}], "conservation_probe": "S3-P003：SUM(PAYMENT_AMOUNT)-SUM(REFUNDED_AMOUNT) 按 RCPT_NO 与收据金额对账"}$r197b$::jsonb, $r197b${"risks": ["MONEY_TYPE/CHARGE_INDICATOR 值域未确认", "退费冲销行重复计入", "部分结算多支付方式行"], "original_caliber": "nvl(sum(nvl(PAYMENT_AMOUNT,0)-nvl(REFUNDED_AMOUNT,0)),0) 消费金额，WHERE CHARGE_INDICATOR=0 AND MONEY_TYPE='预交金'（F0298）", "suggested_caliber": "同口径；MONEY_TYPE/CHARGE_INDICATOR 值域无 confirmed——执行前【值域待确认】，退费/冲销方向以 TRANSACT_TYPE 类字段值域为准（待确认）"}$r197b$::jsonb, $r197b$5bc0925f69a2$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s3-02_5bc0925f69a2$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s3-03_01592508080d$r197b$, $r197b$住院费用×诊断/手术防放大（先聚合后挂靠）$r197b$, 'draft', $r197b$住院费用统计$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$住院费用×诊断/手术防放大（先聚合后挂靠）（197历史SQL摄入配方候选；主事实粒度：住院就诊（PATIENT_ID+VISIT_ID））$r197b$, $r197b$住院费用统计$r197b$,
 $r197b$["INP_BILL_DETAIL", "DIAGNOSIS", "OPERATION", "PAT_VISIT"]$r197b$::jsonb, $r197b${"join_family_ids": ["S2F-60FDE4D634", "S2F-4264E2FC1C", "S2F-CB3BA33251", "S2F-AF65517FED"], "dedup_strategy": "费用/支付先按 visit 聚合（相关标量子查询），再挂诊断；诊断侧 DISTINCT PATIENT_ID||VISIT_ID 只用于人群去重，不得携带 SUM", "time_fields": ["ADMISSION_DATE_TIME（人群窗）", "DISCHARGE_DATE_TIME（出院口径人群，二者不同结果）"]}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S3-03", "name": "住院费用×诊断/手术防放大（先聚合后挂靠）", "domain": "住院费用统计", "primary_tables": ["INP_BILL_DETAIL", "DIAGNOSIS", "OPERATION", "PAT_VISIT"], "join_family_ids": ["S2F-60FDE4D634", "S2F-4264E2FC1C", "S2F-CB3BA33251", "S2F-AF65517FED"], "main_fact_grain": "住院就诊（PATIENT_ID+VISIT_ID）", "dedup_strategy": "费用/支付先按 visit 聚合（相关标量子查询），再挂诊断；诊断侧 DISTINCT PATIENT_ID||VISIT_ID 只用于人群去重，不得携带 SUM", "time_fields": ["ADMISSION_DATE_TIME（人群窗）", "DISCHARGE_DATE_TIME（出院口径人群，二者不同结果）"], "conservation_probe": "S3-P002：visit 级 SUM(INP_BILL_DETAIL.COSTS) 与 INP_SETTLE_MASTER 总额列聚合对账；挂诊断前后行数不变（每 visit 恒 1 行）", "original_caliber": "F0387：先 DISTINCT PATIENT_ID||VISIT_ID 再相关子查询 SUM——注释里保留了曾把 SUM 放进诊断 JOIN 内的错误口径（负例在同一文件内）", "suggested_caliber": "人群（诊断 LIKE/编码过滤）→ DISTINCT visit → 聚合子查询取费用；一对多诊断/手术绝不与费用行直接 JOIN 后 SUM", "risks": ["诊断 LIKE '%肺炎%' 语义人群（非编码）", "同费用被多条诊断放大", "入院时间vs出院时间人群窗不同"], "evidence": [{"unit": "F0387", "file": "提取新冠患者入院信息\\...\\sql(1).txt", "lines": [24, 24]}, {"unit": "F0020", "file": "2024年出院的，自费病例中，费用大于5W的病历信息.txt", "lines": [1, 1]}], "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": [{"unit": "F0387", "file": "提取新冠患者入院信息\\...\\sql(1).txt", "lines": [24, 24]}, {"unit": "F0020", "file": "2024年出院的，自费病例中，费用大于5W的病历信息.txt", "lines": [1, 1]}], "conservation_probe": "S3-P002：visit 级 SUM(INP_BILL_DETAIL.COSTS) 与 INP_SETTLE_MASTER 总额列聚合对账；挂诊断前后行数不变（每 visit 恒 1 行）"}$r197b$::jsonb, $r197b${"risks": ["诊断 LIKE '%肺炎%' 语义人群（非编码）", "同费用被多条诊断放大", "入院时间vs出院时间人群窗不同"], "original_caliber": "F0387：先 DISTINCT PATIENT_ID||VISIT_ID 再相关子查询 SUM——注释里保留了曾把 SUM 放进诊断 JOIN 内的错误口径（负例在同一文件内）", "suggested_caliber": "人群（诊断 LIKE/编码过滤）→ DISTINCT visit → 聚合子查询取费用；一对多诊断/手术绝不与费用行直接 JOIN 后 SUM"}$r197b$::jsonb, $r197b$01592508080d$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s3-03_01592508080d$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s3-04_d895ac971466$r197b$, $r197b$药品有效价选价（价表时间窗+多价并存）$r197b$, 'draft', $r197b$价格/药库$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$药品有效价选价（价表时间窗+多价并存）（197历史SQL摄入配方候选；主事实粒度：价格行（药品+规格/厂家+单位+生效期））$r197b$, $r197b$价格/药库$r197b$,
 $r197b$["DRUG_PRICE_LIST", "PRICE_LIST", "INP_BILL_DETAIL", "OUTP_BILL_ITEMS", "INSUR_VSH_CENTER_ITEM_NEW"]$r197b$::jsonb, $r197b${"join_family_ids": ["S3F:DRUG_PRICE_LIST.DRUG_CODE+FIRM_ID+UNITS=INP_BILL_DETAIL.ITEM_CODE+ITEM_SPEC+UNITS", "S3F:DRUG_PRICE_LIST…=OUTP_BILL_ITEMS…", "S2F-797C110153"], "dedup_strategy": "同键多价必须按生效起止时间窗选唯一行；rownum=1 任取不可复现（原口径）", "time_fields": ["价表生效起止列（列名以元数据核对为准，语句未显式使用——缺口）"]}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S3-04", "name": "药品有效价选价（价表时间窗+多价并存）", "domain": "价格/药库", "primary_tables": ["DRUG_PRICE_LIST", "PRICE_LIST", "INP_BILL_DETAIL", "OUTP_BILL_ITEMS", "INSUR_VSH_CENTER_ITEM_NEW"], "join_family_ids": ["S3F:DRUG_PRICE_LIST.DRUG_CODE+FIRM_ID+UNITS=INP_BILL_DETAIL.ITEM_CODE+ITEM_SPEC+UNITS", "S3F:DRUG_PRICE_LIST…=OUTP_BILL_ITEMS…", "S2F-797C110153"], "main_fact_grain": "价格行（药品+规格/厂家+单位+生效期）", "dedup_strategy": "同键多价必须按生效起止时间窗选唯一行；rownum=1 任取不可复现（原口径）", "time_fields": ["价表生效起止列（列名以元数据核对为准，语句未显式使用——缺口）"], "conservation_probe": "S3-P005：同键价行数分布（=1 占比、>1 多价并存率）+生效时间列存在性", "original_caliber": "drug_spec||firm_id = item_spec 拼串 + units + rownum=1（F0095 医保药品统计）；医保码映射 insur_vsh_center_item_new rownum=1 同样任取", "suggested_caliber": "显式列匹配（drug_code+drug_spec+firm_id+units 各自对位，杜绝拼串）+生效时间窗过滤；同码多映射先 GROUP BY 校验唯一再取值", "risks": ["拼接键错位（FIRM_ID 对 ITEM_SPEC）", "多价并存任取行", "同码多医保映射", "CURRENT_PRICE_LIST 与 PRICE_LIST 双表身份待核"], "evidence": [{"unit": "F0095", "file": "医保药品统计sql.txt", "lines": [1, 42]}], "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": [{"unit": "F0095", "file": "医保药品统计sql.txt", "lines": [1, 42]}], "conservation_probe": "S3-P005：同键价行数分布（=1 占比、>1 多价并存率）+生效时间列存在性"}$r197b$::jsonb, $r197b${"risks": ["拼接键错位（FIRM_ID 对 ITEM_SPEC）", "多价并存任取行", "同码多医保映射", "CURRENT_PRICE_LIST 与 PRICE_LIST 双表身份待核"], "original_caliber": "drug_spec||firm_id = item_spec 拼串 + units + rownum=1（F0095 医保药品统计）；医保码映射 insur_vsh_center_item_new rownum=1 同样任取", "suggested_caliber": "显式列匹配（drug_code+drug_spec+firm_id+units 各自对位，杜绝拼串）+生效时间窗过滤；同码多映射先 GROUP BY 校验唯一再取值"}$r197b$::jsonb, $r197b$d895ac971466$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s3-04_d895ac971466$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s3-05_25be97132128$r197b$, $r197b$住院结算主档与医保对账链$r197b$, 'draft', $r197b$住院结算/医保$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$住院结算主档与医保对账链（197历史SQL摄入配方候选；主事实粒度：结算单（visit×结算序号/收据号））$r197b$, $r197b$住院结算/医保$r197b$,
 $r197b$["INP_SETTLE_MASTER", "INP_SETTLE_MASTER_YB", "SETTLE_ZY_REC", "INP_BILL_DETAIL"]$r197b$::jsonb, $r197b${"join_family_ids": ["S2F-89188944F3", "S2F-5178A77822", "S2F-F9B9C57BF3", "S2F-836F2A5926", "S3F:INP_SETTLE_MASTER.PATIENT_ID+VISIT_ID=INP_SETTLE_MASTER_YB…（草稿8；brjsh 变体=草稿30）"], "dedup_strategy": "一次住院多次结算/部分结算：按 RCPT_NO/结算号聚合，不可按 visit 直连去重", "time_fields": ["SETTLE_DATE_TIME（结算时间）vs DISCHARGE_DATE_TIME（出院时间）人群不同"]}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S3-05", "name": "住院结算主档与医保对账链", "domain": "住院结算/医保", "primary_tables": ["INP_SETTLE_MASTER", "INP_SETTLE_MASTER_YB", "SETTLE_ZY_REC", "INP_BILL_DETAIL"], "join_family_ids": ["S2F-89188944F3", "S2F-5178A77822", "S2F-F9B9C57BF3", "S2F-836F2A5926", "S3F:INP_SETTLE_MASTER.PATIENT_ID+VISIT_ID=INP_SETTLE_MASTER_YB…（草稿8；brjsh 变体=草稿30）"], "main_fact_grain": "结算单（visit×结算序号/收据号）", "dedup_strategy": "一次住院多次结算/部分结算：按 RCPT_NO/结算号聚合，不可按 visit 直连去重", "time_fields": ["SETTLE_DATE_TIME（结算时间）vs DISCHARGE_DATE_TIME（出院时间）人群不同"], "conservation_probe": "S3-P002/P007：visit 级结算总额与费用明细 SUM 对账；组合键 vs brjsh 键覆盖率对比", "original_caliber": "组合键 PATIENT_ID+VISIT_ID 直挂（多数语句）；草稿30 用 brjsh 单列", "suggested_caliber": "组合键为主键口径；brjsh 作为备选对账键须经唯一性验证；医保金额（YBFDJE 等）取自 _YB 侧并注明结算状态值域【待确认】", "risks": ["部分结算/重结算多行", "SETTLE_TYPE/结算状态值域无 confirmed", "_YB 表滞后或补录"], "evidence": [{"unit": "F0387", "file": "提取新冠患者入院信息\\...\\sql(1).txt", "lines": [24, 24]}, {"unit": "A_F0138", "file": "SQL\\2022年07月 18-24.sql", "lines": [366, 366]}], "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": [{"unit": "F0387", "file": "提取新冠患者入院信息\\...\\sql(1).txt", "lines": [24, 24]}, {"unit": "A_F0138", "file": "SQL\\2022年07月 18-24.sql", "lines": [366, 366]}], "conservation_probe": "S3-P002/P007：visit 级结算总额与费用明细 SUM 对账；组合键 vs brjsh 键覆盖率对比"}$r197b$::jsonb, $r197b${"risks": ["部分结算/重结算多行", "SETTLE_TYPE/结算状态值域无 confirmed", "_YB 表滞后或补录"], "original_caliber": "组合键 PATIENT_ID+VISIT_ID 直挂（多数语句）；草稿30 用 brjsh 单列", "suggested_caliber": "组合键为主键口径；brjsh 作为备选对账键须经唯一性验证；医保金额（YBFDJE 等）取自 _YB 侧并注明结算状态值域【待确认】"}$r197b$::jsonb, $r197b$25be97132128$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s3-05_25be97132128$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s3-06_ad331eb98b8f$r197b$, $r197b$预交金收据与账户链$r197b$, 'draft', $r197b$预交金$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$预交金收据与账户链（197历史SQL摄入配方候选；主事实粒度：预交金收据行 / 账户行）$r197b$, $r197b$预交金$r197b$,
 $r197b$["PREPAYMENT_RCPT", "PREPAYMENT_RCPT_ADD", "PREPAY_ACCT", "PREPAY_ACCT_MONEY"]$r197b$::jsonb, $r197b${"join_family_ids": ["S3F:PREPAYMENT_RCPT.RCPT_NO=PREPAYMENT_RCPT_ADD.RCPT_NO", "S3F:三列族", "S3F:CHECK_NO+BANK_CODE（判读）", "S3F:PREPAY_ACCT.ACCT_NO=PREPAY_ACCT_MONEY.ACCT_NO"], "dedup_strategy": "三键并存（RCPT_NO、RCPT_NO+PATIENT_ID+VISIT_ID、CHECK_NO+BANK_CODE）：对账场景按支票号+银行代码，患者侧按三列键", "time_fields": ["预交时间（RCPT 表时间列，元数据核对）"]}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S3-06", "name": "预交金收据与账户链", "domain": "预交金", "primary_tables": ["PREPAYMENT_RCPT", "PREPAYMENT_RCPT_ADD", "PREPAY_ACCT", "PREPAY_ACCT_MONEY"], "join_family_ids": ["S3F:PREPAYMENT_RCPT.RCPT_NO=PREPAYMENT_RCPT_ADD.RCPT_NO", "S3F:三列族", "S3F:CHECK_NO+BANK_CODE（判读）", "S3F:PREPAY_ACCT.ACCT_NO=PREPAY_ACCT_MONEY.ACCT_NO"], "main_fact_grain": "预交金收据行 / 账户行", "dedup_strategy": "三键并存（RCPT_NO、RCPT_NO+PATIENT_ID+VISIT_ID、CHECK_NO+BANK_CODE）：对账场景按支票号+银行代码，患者侧按三列键", "time_fields": ["预交时间（RCPT 表时间列，元数据核对）"], "conservation_probe": "S3-P004：三键父键重复率对比；账户余额=Σ收据-Σ退票", "original_caliber": "不同语句用不同键（单一语句只见一键）", "suggested_caliber": "按场景选键并注明；ACCT_NO 账户级聚合守恒", "risks": ["RCPT_NO 单列跨日重用风险", "退票冲销行"], "evidence": [{"unit": "A_F0138", "file": "SQL\\2022年08月 15-21.sql", "lines": [471, 471]}], "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": [{"unit": "A_F0138", "file": "SQL\\2022年08月 15-21.sql", "lines": [471, 471]}], "conservation_probe": "S3-P004：三键父键重复率对比；账户余额=Σ收据-Σ退票"}$r197b$::jsonb, $r197b${"risks": ["RCPT_NO 单列跨日重用风险", "退票冲销行"], "original_caliber": "不同语句用不同键（单一语句只见一键）", "suggested_caliber": "按场景选键并注明；ACCT_NO 账户级聚合守恒"}$r197b$::jsonb, $r197b$ad331eb98b8f$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s3-06_ad331eb98b8f$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s3-07_99accc80ba6f$r197b$, $r197b$INP_BILL_DETAIL.OPER_CODE 多义键分流挂靠$r197b$, 'draft', $r197b$住院费用明细挂靠$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$INP_BILL_DETAIL.OPER_CODE 多义键分流挂靠（197历史SQL摄入配方候选；主事实粒度：费用行）$r197b$, $r197b$住院费用明细挂靠$r197b$,
 $r197b$["INP_BILL_DETAIL", "EXAM_MASTER", "ORDERS", "OPERATION_MASTER"]$r197b$::jsonb, $r197b${"join_family_ids": ["S3F:EXAM_MASTER.EXAM_NO+PATIENT_ID+VISIT_ID=INP_BILL_DETAIL.OPER_CODE+…", "S3F:INP_BILL_DETAIL…OPER_CODE+ORDER_NO=ORDERS…APP_NO+ORDER_NO", "S2F（平台557/564 同构）：OPER_CODE=OPERATION_MASTER.OPER_ID 且 LENGTH≥8"], "dedup_strategy": "按费用类别（ITEM_CLASS/CLASS_ON_RECKONING）分流后各自挂主档，禁止不分流直连", "time_fields": ["费用时间 vs 主档业务时间各自对齐"]}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S3-07", "name": "INP_BILL_DETAIL.OPER_CODE 多义键分流挂靠", "domain": "住院费用明细挂靠", "primary_tables": ["INP_BILL_DETAIL", "EXAM_MASTER", "ORDERS", "OPERATION_MASTER"], "join_family_ids": ["S3F:EXAM_MASTER.EXAM_NO+PATIENT_ID+VISIT_ID=INP_BILL_DETAIL.OPER_CODE+…", "S3F:INP_BILL_DETAIL…OPER_CODE+ORDER_NO=ORDERS…APP_NO+ORDER_NO", "S2F（平台557/564 同构）：OPER_CODE=OPERATION_MASTER.OPER_ID 且 LENGTH≥8"], "main_fact_grain": "费用行", "dedup_strategy": "按费用类别（ITEM_CLASS/CLASS_ON_RECKONING）分流后各自挂主档，禁止不分流直连", "time_fields": ["费用时间 vs 主档业务时间各自对齐"], "conservation_probe": "S3-P006：OPER_CODE 按 ITEM_CLASS 分组的 LENGTH 分布与 EXAM_NO/TEST_NO/OPER_ID 命中率（聚合）", "original_caliber": "检查类 oper_code=exam_no；申请单 a.APP_NO=b.OPER_CODE；手术类长度≥8 对 OPER_ID——三种口径散在不同语句", "suggested_caliber": "统一分流配方：检查→EXAM_NO、检验→TEST_NO、医嘱申请→APP_NO、手术→OPER_ID（LENGTH≥8 仅为启发式不作硬规则）", "risks": ["不分流则错配/丢行", "APPOINT_NO 同为多义（检查=EXAM_NO/检验=TEST_NO）"], "evidence": [{"unit": "F0???-影像", "file": "2025年7月影像科人次…txt", "lines": [19, 32]}, {"unit": "F0???-病理", "file": "病理医保飞检数据提取.txt", "lines": [299, 322]}], "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": [{"unit": "F0???-影像", "file": "2025年7月影像科人次…txt", "lines": [19, 32]}, {"unit": "F0???-病理", "file": "病理医保飞检数据提取.txt", "lines": [299, 322]}], "conservation_probe": "S3-P006：OPER_CODE 按 ITEM_CLASS 分组的 LENGTH 分布与 EXAM_NO/TEST_NO/OPER_ID 命中率（聚合）"}$r197b$::jsonb, $r197b${"risks": ["不分流则错配/丢行", "APPOINT_NO 同为多义（检查=EXAM_NO/检验=TEST_NO）"], "original_caliber": "检查类 oper_code=exam_no；申请单 a.APP_NO=b.OPER_CODE；手术类长度≥8 对 OPER_ID——三种口径散在不同语句", "suggested_caliber": "统一分流配方：检查→EXAM_NO、检验→TEST_NO、医嘱申请→APP_NO、手术→OPER_ID（LENGTH≥8 仅为启发式不作硬规则）"}$r197b$::jsonb, $r197b$99accc80ba6f$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s3-07_99accc80ba6f$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s3-08_15b5ac243c65$r197b$, $r197b$医保中心目录映射（费用项目↔医保码）$r197b$, 'draft', $r197b$医保$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$医保中心目录映射（费用项目↔医保码）（197历史SQL摄入配方候选；主事实粒度：目录映射行）$r197b$, $r197b$医保$r197b$,
 $r197b$["INSUR_VSH_CENTER_ITEM_NEW", "OUTP_BILL_ITEMS", "INP_BILL_DETAIL", "PRICE_LIST"]$r197b$::jsonb, $r197b${"join_family_ids": ["S2F-797C110153", "S3F:INSUR_VSH_CENTER_ITEM_NEW.ITEM_CODE=OUTP_BILL_ITEMS.ITEM_CODE", "S3F:…=PRICE_LIST.ITEM_CODE"], "dedup_strategy": "同码多映射先 GROUP BY ITEM_CODE HAVING COUNT>1 检出，再决定取行规则；rownum=1 任取（原口径）不可复现", "time_fields": ["目录版本/生效时间（语句未显式处理——缺口，历史目录不自动作现行标准）"]}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S3-08", "name": "医保中心目录映射（费用项目↔医保码）", "domain": "医保", "primary_tables": ["INSUR_VSH_CENTER_ITEM_NEW", "OUTP_BILL_ITEMS", "INP_BILL_DETAIL", "PRICE_LIST"], "join_family_ids": ["S2F-797C110153", "S3F:INSUR_VSH_CENTER_ITEM_NEW.ITEM_CODE=OUTP_BILL_ITEMS.ITEM_CODE", "S3F:…=PRICE_LIST.ITEM_CODE"], "main_fact_grain": "目录映射行", "dedup_strategy": "同码多映射先 GROUP BY ITEM_CODE HAVING COUNT>1 检出，再决定取行规则；rownum=1 任取（原口径）不可复现", "time_fields": ["目录版本/生效时间（语句未显式处理——缺口，历史目录不自动作现行标准）"], "conservation_probe": "映射多值率聚合；覆盖率（明细 item_code 命中目录比例）", "original_caliber": "(select cc.ylxmbm from insur_vsh_center_item_new cc where cc.item_code=b.item_code and rownum=1)", "suggested_caliber": "先验证 ITEM_CODE 唯一性；不唯一时按目录版本列取最新并留审计", "risks": ["同码多映射", "目录版本更替", "名称类映射（HIS_DICT_NAME）碰撞"], "evidence": [{"unit": "F0095", "file": "医保药品统计sql.txt", "lines": [1, 42]}], "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": [{"unit": "F0095", "file": "医保药品统计sql.txt", "lines": [1, 42]}], "conservation_probe": "映射多值率聚合；覆盖率（明细 item_code 命中目录比例）"}$r197b$::jsonb, $r197b${"risks": ["同码多映射", "目录版本更替", "名称类映射（HIS_DICT_NAME）碰撞"], "original_caliber": "(select cc.ylxmbm from insur_vsh_center_item_new cc where cc.item_code=b.item_code and rownum=1)", "suggested_caliber": "先验证 ITEM_CODE 唯一性；不唯一时按目录版本列取最新并留审计"}$r197b$::jsonb, $r197b$15b5ac243c65$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s3-08_15b5ac243c65$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s5-01_40f80ad33979$r197b$, $r197b$检验三表链（申请-项目-结果）$r197b$, 'draft', $r197b$检验$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$检验三表链（申请-项目-结果）（197历史SQL摄入配方候选；主事实粒度：申请单(TEST_NO)→项目行(TEST_NO+ITEM_NO)→结果行(TEST_NO+ITEM_NO)）$r197b$, $r197b$检验$r197b$,
 $r197b$["LAB_TEST_MASTER", "LAB_TEST_ITEMS", "LAB_RESULT", "LAB_TEST_BATCH_MASTER"]$r197b$::jsonb, $r197b${"join_family_ids": ["S2F-BE6DDA7EB6", "S2F-42E060720B", "S2F-67F8789EE2", "S5F:*批次TEST_NO族"], "dedup_strategy": "项目级键 TEST_NO+ITEM_NO；禁止仅 TEST_NO 挂结果/项目（M:N 放大）", "time_fields": "各表业务时间列；LAB_RESULT 约 1 亿行必须 TEST_NO 子查询限定"}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S5-01", "name": "检验三表链（申请-项目-结果）", "domain": "检验", "primary_tables": ["LAB_TEST_MASTER", "LAB_TEST_ITEMS", "LAB_RESULT", "LAB_TEST_BATCH_MASTER"], "join_family_ids": ["S2F-BE6DDA7EB6", "S2F-42E060720B", "S2F-67F8789EE2", "S5F:*批次TEST_NO族"], "main_fact_grain": "申请单(TEST_NO)→项目行(TEST_NO+ITEM_NO)→结果行(TEST_NO+ITEM_NO)", "dedup_strategy": "项目级键 TEST_NO+ITEM_NO；禁止仅 TEST_NO 挂结果/项目（M:N 放大）", "time_fields": "各表业务时间列；LAB_RESULT 约 1 亿行必须 TEST_NO 子查询限定", "conservation_probe": "S5-P001", "original_caliber": "部分语句仅按 TEST_NO 连结果与项目表（放大）；外层 ROWNNUM 限行", "suggested_caliber": "先按业务键/时间窗选 TEST_NO 集合，再经 TEST_NO+ITEM_NO 项目级键连三表；结果行数=项目行数×复检因子需对账", "risks": ["LAB_RESULT 大表全扫风险（AGENTS 硬约束 3）", "单列 TEST_NO M:N 放大", "复检/多批次结果行并存"], "evidence": "F0136 药品进销存.sql / F0426 移动护理VTE数据查询.sql / A_F0138 周报 SQL 集（脱敏模板，见 s5_relation_families.json rep_locations）", "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": "F0136 药品进销存.sql / F0426 移动护理VTE数据查询.sql / A_F0138 周报 SQL 集（脱敏模板，见 s5_relation_families.json rep_locations）", "conservation_probe": "S5-P001"}$r197b$::jsonb, $r197b${"risks": ["LAB_RESULT 大表全扫风险（AGENTS 硬约束 3）", "单列 TEST_NO M:N 放大", "复检/多批次结果行并存"], "original_caliber": "部分语句仅按 TEST_NO 连结果与项目表（放大）；外层 ROWNNUM 限行", "suggested_caliber": "先按业务键/时间窗选 TEST_NO 集合，再经 TEST_NO+ITEM_NO 项目级键连三表；结果行数=项目行数×复检因子需对账"}$r197b$::jsonb, $r197b$40f80ad33979$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s5-01_40f80ad33979$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s5-02_b603a28b21a3$r197b$, $r197b$检查链（主档-项目-报告）$r197b$, 'draft', $r197b$检查$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$检查链（主档-项目-报告）（197历史SQL摄入配方候选；主事实粒度：检查单(EXAM_NO)→项目行→报告行）$r197b$, $r197b$检查$r197b$,
 $r197b$["EXAM_MASTER", "EXAM_ITEMS", "EXAM_REPORT", "EXAM_APPOINTS"]$r197b$::jsonb, $r197b${"join_family_ids": ["S2F-EE88384570", "S2F-85177FB98A", "S5F:*EXAM_ITEMS↔EXAM_REPORT族"], "dedup_strategy": "经 EXAM_NO 回主表取患者/就诊；EXAM_REPORT 无 PATIENT_ID 不可直连患者表", "time_fields": "申请/报告时间列"}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S5-02", "name": "检查链（主档-项目-报告）", "domain": "检查", "primary_tables": ["EXAM_MASTER", "EXAM_ITEMS", "EXAM_REPORT", "EXAM_APPOINTS"], "join_family_ids": ["S2F-EE88384570", "S2F-85177FB98A", "S5F:*EXAM_ITEMS↔EXAM_REPORT族"], "main_fact_grain": "检查单(EXAM_NO)→项目行→报告行", "dedup_strategy": "经 EXAM_NO 回主表取患者/就诊；EXAM_REPORT 无 PATIENT_ID 不可直连患者表", "time_fields": "申请/报告时间列", "conservation_probe": "S5-P002", "original_caliber": "EXAM_CLASS 存中文值（'CT'/'磁共振'），语句直接按中文过滤（不 join 字典——正确）", "suggested_caliber": "EXAM_NO 键链三表；检查类别按中文字面过滤；EXAM_APPOINTS 挂号侧按 VISIT_DATE+VISIT_NO（草稿 603 同构待验证）", "risks": ["EXAM_REPORT 缺 PATIENT_ID（AGENTS 硬约束 7）", "EXAM_CLASS 中文值域", "预约-执行未到检查的孤儿"], "evidence": "F0136 药品进销存.sql / F0426 移动护理VTE数据查询.sql / A_F0138 周报 SQL 集（脱敏模板，见 s5_relation_families.json rep_locations）", "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": "F0136 药品进销存.sql / F0426 移动护理VTE数据查询.sql / A_F0138 周报 SQL 集（脱敏模板，见 s5_relation_families.json rep_locations）", "conservation_probe": "S5-P002"}$r197b$::jsonb, $r197b${"risks": ["EXAM_REPORT 缺 PATIENT_ID（AGENTS 硬约束 7）", "EXAM_CLASS 中文值域", "预约-执行未到检查的孤儿"], "original_caliber": "EXAM_CLASS 存中文值（'CT'/'磁共振'），语句直接按中文过滤（不 join 字典——正确）", "suggested_caliber": "EXAM_NO 键链三表；检查类别按中文字面过滤；EXAM_APPOINTS 挂号侧按 VISIT_DATE+VISIT_NO（草稿 603 同构待验证）"}$r197b$::jsonb, $r197b$b603a28b21a3$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s5-02_b603a28b21a3$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s5-03_97a0e0a3d7b0$r197b$, $r197b$药品进销存单据链$r197b$, 'draft', $r197b$药品$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$药品进销存单据链（197历史SQL摄入配方候选；主事实粒度：单据(DOCUMENT_NO)主从 + 库存批次行(药码+规格+批号+厂家+包装规格)）$r197b$, $r197b$药品$r197b$,
 $r197b$["DRUG_IMPORT_MASTER/DETAIL", "DRUG_EXPORT_MASTER/DETAIL", "DRUG_STOCK", "DRUG_STORAGE_DEPT"]$r197b$::jsonb, $r197b${"join_family_ids": ["S5F:*DOCUMENT_NO 族群", "S5F:*五列批次键族"], "dedup_strategy": "单据主从键 DOCUMENT_NO（是否需+库房/单据类别待 S5-P003）；库存对位用五列批次键", "time_fields": "单据日期/入出库时间"}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S5-03", "name": "药品进销存单据链", "domain": "药品", "primary_tables": ["DRUG_IMPORT_MASTER/DETAIL", "DRUG_EXPORT_MASTER/DETAIL", "DRUG_STOCK", "DRUG_STORAGE_DEPT"], "join_family_ids": ["S5F:*DOCUMENT_NO 族群", "S5F:*五列批次键族"], "main_fact_grain": "单据(DOCUMENT_NO)主从 + 库存批次行(药码+规格+批号+厂家+包装规格)", "dedup_strategy": "单据主从键 DOCUMENT_NO（是否需+库房/单据类别待 S5-P003）；库存对位用五列批次键", "time_fields": "单据日期/入出库时间", "conservation_probe": "S5-P003", "original_caliber": "DOCUMENT_NO 单键连接主从并跨库房汇总", "suggested_caliber": "同库房内 DOCUMENT_NO 主从；跨库房统计时先按 STORAGE 分组再对账；批号级对位用五列键", "risks": ["DOCUMENT_NO 跨库房重复风险", "库存粒度含库房/批号（两列键放大）", "出库会诊/退药单据类别混入"], "evidence": "F0136 药品进销存.sql / F0426 移动护理VTE数据查询.sql / A_F0138 周报 SQL 集（脱敏模板，见 s5_relation_families.json rep_locations）", "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": "F0136 药品进销存.sql / F0426 移动护理VTE数据查询.sql / A_F0138 周报 SQL 集（脱敏模板，见 s5_relation_families.json rep_locations）", "conservation_probe": "S5-P003"}$r197b$::jsonb, $r197b${"risks": ["DOCUMENT_NO 跨库房重复风险", "库存粒度含库房/批号（两列键放大）", "出库会诊/退药单据类别混入"], "original_caliber": "DOCUMENT_NO 单键连接主从并跨库房汇总", "suggested_caliber": "同库房内 DOCUMENT_NO 主从；跨库房统计时先按 STORAGE 分组再对账；批号级对位用五列键"}$r197b$::jsonb, $r197b$97a0e0a3d7b0$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s5-03_97a0e0a3d7b0$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s5-04_2e3651793774$r197b$, $r197b$药价三列选价链（药码+规格+厂家）$r197b$, 'draft', $r197b$药品$r197b$, $r197b$HIS_SOURCE$r197b$, $r197b$药价三列选价链（药码+规格+厂家）（197历史SQL摄入配方候选；主事实粒度：价格行（药码+规格+厂家 [+有效期]））$r197b$, $r197b$药品$r197b$,
 $r197b$["DRUG_PRICE_LIST", "DRUG_DICT", "DRUG_NAME_DICT", "DRUG_STOCK", "DRUG_DISPENSE_REC"]$r197b$::jsonb, $r197b${"join_family_ids": ["S5F:*DRUG_*↔DRUG_PRICE_LIST 三列族群"], "dedup_strategy": "三列键+生效时间窗；列名两侧不同（PACKAGE_SPEC/DRUG_SPEC/MIN_SPEC）需映射后匹配", "time_fields": "价表生效起止（多语句未显式用——缺口）"}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S5-04", "name": "药价三列选价链（药码+规格+厂家）", "domain": "药品", "primary_tables": ["DRUG_PRICE_LIST", "DRUG_DICT", "DRUG_NAME_DICT", "DRUG_STOCK", "DRUG_DISPENSE_REC"], "join_family_ids": ["S5F:*DRUG_*↔DRUG_PRICE_LIST 三列族群"], "main_fact_grain": "价格行（药码+规格+厂家 [+有效期]）", "dedup_strategy": "三列键+生效时间窗；列名两侧不同（PACKAGE_SPEC/DRUG_SPEC/MIN_SPEC）需映射后匹配", "time_fields": "价表生效起止（多语句未显式用——缺口）", "conservation_probe": "S5-P004", "original_caliber": "药码+规格+厂家三列匹配价表，未显式限生效期，rownum=1 任取价", "suggested_caliber": "三列键+生效时间窗选价；多价并存（同键多有效行）先分布后决策；MIN_SPEC 换算语句按单位换算表处理", "risks": ["多价并存/时间窗重叠（RCP-S3-04 同族）", "规格列名不一致（PACKAGE_SPEC vs DRUG_SPEC vs MIN_SPEC）", "厂家停用改名"], "evidence": "F0136 药品进销存.sql / F0426 移动护理VTE数据查询.sql / A_F0138 周报 SQL 集（脱敏模板，见 s5_relation_families.json rep_locations）", "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": "F0136 药品进销存.sql / F0426 移动护理VTE数据查询.sql / A_F0138 周报 SQL 集（脱敏模板，见 s5_relation_families.json rep_locations）", "conservation_probe": "S5-P004"}$r197b$::jsonb, $r197b${"risks": ["多价并存/时间窗重叠（RCP-S3-04 同族）", "规格列名不一致（PACKAGE_SPEC vs DRUG_SPEC vs MIN_SPEC）", "厂家停用改名"], "original_caliber": "药码+规格+厂家三列匹配价表，未显式限生效期，rownum=1 任取价", "suggested_caliber": "三列键+生效时间窗选价；多价并存（同键多有效行）先分布后决策；MIN_SPEC 换算语句按单位换算表处理"}$r197b$::jsonb, $r197b$2e3651793774$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s5-04_2e3651793774$r197b$);

INSERT INTO asset.asset_relation_recipes
(recipe_id, recipe_name, status, domain, source_system, description, business_domain,
 primary_tables, joins, ai_readable, imported_from, version, is_active, recipe_json,
 evidence_summary, risk_summary, content_hash, created_by, created_at)
SELECT $r197b$R197_rcp-s5-05_dd6120af7e14$r197b$, $r197b$移动护理 VTE 表单链$r197b$, 'draft', $r197b$护理$r197b$, $r197b$MOBILE_NURSING$r197b$, $r197b$移动护理 VTE 表单链（197历史SQL摄入配方候选；主事实粒度：住院(pat_index_no)→表单(form.patient_uid)→记录(records.form_id)）$r197b$, $r197b$护理$r197b$,
 $r197b$["INPATIENTS", "MCS_DOC_FORM", "MCS_DOC_FORM_RECORDS", "MCS_ORDER_SCHEDULE"]$r197b$::jsonb, $r197b${"join_family_ids": ["S5F:*INPATIENTS↔MCS_DOC_FORM 族", "S5F:*MCS_DOC_FORM↔RECORDS 族"], "dedup_strategy": "form.id=records.form_id 主从；患者链 pat_index_no=patient_uid（平台 45/46 已 verified）", "time_fields": "表单创建/评估时间"}$r197b$::jsonb, true, 'r197_intake', 1, false, $r197b${"recipe_id": "RCP-S5-05", "name": "移动护理 VTE 表单链", "domain": "护理", "primary_tables": ["INPATIENTS", "MCS_DOC_FORM", "MCS_DOC_FORM_RECORDS", "MCS_ORDER_SCHEDULE"], "join_family_ids": ["S5F:*INPATIENTS↔MCS_DOC_FORM 族", "S5F:*MCS_DOC_FORM↔RECORDS 族"], "main_fact_grain": "住院(pat_index_no)→表单(form.patient_uid)→记录(records.form_id)", "dedup_strategy": "form.id=records.form_id 主从；患者链 pat_index_no=patient_uid（平台 45/46 已 verified）", "time_fields": "表单创建/评估时间", "conservation_probe": "S5-P005", "original_caliber": "三表直连统计评估条目数", "suggested_caliber": "同次住院同模板多次评估先按 (pat_index_no, template_code, 评估时间) 去重再计数；跨次住院按住院次分段", "risks": ["同次住院重复评估粒度", "模板/节点值域未确认", "源实例（移动护理 Oracle vs ods_ydhl 镜像）执行身份待核"], "evidence": "F0136 药品进销存.sql / F0426 移动护理VTE数据查询.sql / A_F0138 周报 SQL 集（脱敏模板，见 s5_relation_families.json rep_locations）", "governance_state": "local_draft_only（配方平台草稿提交在 S7，经人工审核）", "run_id": "r197-20260921-s1"}$r197b$::jsonb,
 $r197b${"run_id": "r197-20260921-s1", "evidence": "F0136 药品进销存.sql / F0426 移动护理VTE数据查询.sql / A_F0138 周报 SQL 集（脱敏模板，见 s5_relation_families.json rep_locations）", "conservation_probe": "S5-P005"}$r197b$::jsonb, $r197b${"risks": ["同次住院重复评估粒度", "模板/节点值域未确认", "源实例（移动护理 Oracle vs ods_ydhl 镜像）执行身份待核"], "original_caliber": "三表直连统计评估条目数", "suggested_caliber": "同次住院同模板多次评估先按 (pat_index_no, template_code, 评估时间) 去重再计数；跨次住院按住院次分段"}$r197b$::jsonb, $r197b$dd6120af7e14$r197b$, 'ai:r197-intake', now()
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_relation_recipes x WHERE x.recipe_id = $r197b$R197_rcp-s5-05_dd6120af7e14$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$COMM$r197b$, $r197b$OPERATION_DICT$r197b$, $r197b$OPERATION_SCALE$r197b$, $r197b$一$r197b$, $r197b$一级手术（观察值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q21）；历史目录不自动作现行诊疗标准$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$COMM$r197b$ AND x.table_name=$r197b$OPERATION_DICT$r197b$
    AND x.column_name=$r197b$OPERATION_SCALE$r197b$ AND x.code=$r197b$一$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$COMM$r197b$, $r197b$OPERATION_DICT$r197b$, $r197b$OPERATION_SCALE$r197b$, $r197b$二$r197b$, $r197b$二级手术（观察值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q21）；历史目录不自动作现行诊疗标准$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$COMM$r197b$ AND x.table_name=$r197b$OPERATION_DICT$r197b$
    AND x.column_name=$r197b$OPERATION_SCALE$r197b$ AND x.code=$r197b$二$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$COMM$r197b$, $r197b$OPERATION_DICT$r197b$, $r197b$OPERATION_SCALE$r197b$, $r197b$三$r197b$, $r197b$三级手术（观察值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q21）；历史目录不自动作现行诊疗标准$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$COMM$r197b$ AND x.table_name=$r197b$OPERATION_DICT$r197b$
    AND x.column_name=$r197b$OPERATION_SCALE$r197b$ AND x.code=$r197b$三$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$COMM$r197b$, $r197b$OPERATION_DICT$r197b$, $r197b$OPERATION_SCALE$r197b$, $r197b$四$r197b$, $r197b$四级手术（观察值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q21）；历史目录不自动作现行诊疗标准$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$COMM$r197b$ AND x.table_name=$r197b$OPERATION_DICT$r197b$
    AND x.column_name=$r197b$OPERATION_SCALE$r197b$ AND x.code=$r197b$四$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$COMM$r197b$, $r197b$OPERATION_DICT$r197b$, $r197b$OPERATION_SCALE$r197b$, $r197b$一 $r197b$, $r197b$带尾随空格的变体（trap：='一' 精确比较会漏掉该行）$r197b$, $r197b$trap$r197b$, $r197b$与 '一' 并存；统计一级手术需 trim 或 IN 两种写法；另有 NULL 值行存在$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$COMM$r197b$ AND x.table_name=$r197b$OPERATION_DICT$r197b$
    AND x.column_name=$r197b$OPERATION_SCALE$r197b$ AND x.code=$r197b$一 $r197b$ AND x.domain_kind=$r197b$trap$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$COMM$r197b$, $r197b$OPERATION_DICT$r197b$, $r197b$STOP_FLAG$r197b$, $r197b$0$r197b$, $r197b$STOP_FLAG 取值 0（活库观察，语义待人工确认）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q21$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$COMM$r197b$ AND x.table_name=$r197b$OPERATION_DICT$r197b$
    AND x.column_name=$r197b$STOP_FLAG$r197b$ AND x.code=$r197b$0$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$COMM$r197b$, $r197b$OPERATION_DICT$r197b$, $r197b$STOP_FLAG$r197b$, $r197b$1$r197b$, $r197b$STOP_FLAG 取值 1（活库观察，语义待人工确认；DEPT_DICT 同名列有第三个取值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q21/Q06$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$COMM$r197b$ AND x.table_name=$r197b$OPERATION_DICT$r197b$
    AND x.column_name=$r197b$STOP_FLAG$r197b$ AND x.code=$r197b$1$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$心电图$r197b$, $r197b$检查类别：心电图（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$心电图$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$B超$r197b$, $r197b$检查类别：B超（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$B超$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$CT$r197b$, $r197b$检查类别：CT（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$CT$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$磁共振$r197b$, $r197b$检查类别：磁共振（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$磁共振$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$X线$r197b$, $r197b$检查类别：X线（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$X线$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$肺功能$r197b$, $r197b$检查类别：肺功能（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$肺功能$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$听力检查$r197b$, $r197b$检查类别：听力检查（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$听力检查$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$消化内镜$r197b$, $r197b$检查类别：消化内镜（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$消化内镜$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$支气管镜$r197b$, $r197b$检查类别：支气管镜（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$支气管镜$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$脑电图$r197b$, $r197b$检查类别：脑电图（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$脑电图$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$肌电图$r197b$, $r197b$检查类别：肌电图（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$肌电图$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$数字胃肠$r197b$, $r197b$检查类别：数字胃肠（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$数字胃肠$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$乳腺钼靶$r197b$, $r197b$检查类别：乳腺钼靶（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$乳腺钼靶$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$牙片室$r197b$, $r197b$检查类别：牙片室（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$牙片室$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$一氧化氮$r197b$, $r197b$检查类别：一氧化氮（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$一氧化氮$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$儿童肺功能$r197b$, $r197b$检查类别：儿童肺功能（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$儿童肺功能$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$EXAM$r197b$, $r197b$EXAM_MASTER$r197b$, $r197b$EXAM_CLASS$r197b$, $r197b$动态血压$r197b$, $r197b$检查类别：动态血压（中文字面值）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 活库观察（Q26）；AGENTS 硬约束 5：过滤按中文，不 join 字典$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$EXAM$r197b$ AND x.table_name=$r197b$EXAM_MASTER$r197b$
    AND x.column_name=$r197b$EXAM_CLASS$r197b$ AND x.code=$r197b$动态血压$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$INPBILL$r197b$, $r197b$INP_BILL_DETAIL$r197b$, $r197b$ITEM_CLASS$r197b$, $r197b$A$r197b$, $r197b$费用类别 A（活库观察，语义待人工确认）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q15 共观察到 12 个类别（本批证据快照含 9 个字面）$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$INPBILL$r197b$ AND x.table_name=$r197b$INP_BILL_DETAIL$r197b$
    AND x.column_name=$r197b$ITEM_CLASS$r197b$ AND x.code=$r197b$A$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$INPBILL$r197b$, $r197b$INP_BILL_DETAIL$r197b$, $r197b$ITEM_CLASS$r197b$, $r197b$B$r197b$, $r197b$费用类别 B（活库观察，语义待人工确认）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q15 共观察到 12 个类别（本批证据快照含 9 个字面）$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$INPBILL$r197b$ AND x.table_name=$r197b$INP_BILL_DETAIL$r197b$
    AND x.column_name=$r197b$ITEM_CLASS$r197b$ AND x.code=$r197b$B$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$INPBILL$r197b$, $r197b$INP_BILL_DETAIL$r197b$, $r197b$ITEM_CLASS$r197b$, $r197b$C$r197b$, $r197b$费用类别 C（活库观察，语义待人工确认）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q15 共观察到 12 个类别（本批证据快照含 9 个字面）$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$INPBILL$r197b$ AND x.table_name=$r197b$INP_BILL_DETAIL$r197b$
    AND x.column_name=$r197b$ITEM_CLASS$r197b$ AND x.code=$r197b$C$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$INPBILL$r197b$, $r197b$INP_BILL_DETAIL$r197b$, $r197b$ITEM_CLASS$r197b$, $r197b$D$r197b$, $r197b$费用类别 D（活库观察，语义待人工确认）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q15 共观察到 12 个类别（本批证据快照含 9 个字面）$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$INPBILL$r197b$ AND x.table_name=$r197b$INP_BILL_DETAIL$r197b$
    AND x.column_name=$r197b$ITEM_CLASS$r197b$ AND x.code=$r197b$D$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$INPBILL$r197b$, $r197b$INP_BILL_DETAIL$r197b$, $r197b$ITEM_CLASS$r197b$, $r197b$H$r197b$, $r197b$费用类别 H（活库观察，语义待人工确认）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q15 共观察到 12 个类别（本批证据快照含 9 个字面）$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$INPBILL$r197b$ AND x.table_name=$r197b$INP_BILL_DETAIL$r197b$
    AND x.column_name=$r197b$ITEM_CLASS$r197b$ AND x.code=$r197b$H$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$INPBILL$r197b$, $r197b$INP_BILL_DETAIL$r197b$, $r197b$ITEM_CLASS$r197b$, $r197b$I$r197b$, $r197b$费用类别 I（活库观察，语义待人工确认）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q15 共观察到 12 个类别（本批证据快照含 9 个字面）$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$INPBILL$r197b$ AND x.table_name=$r197b$INP_BILL_DETAIL$r197b$
    AND x.column_name=$r197b$ITEM_CLASS$r197b$ AND x.code=$r197b$I$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$INPBILL$r197b$, $r197b$INP_BILL_DETAIL$r197b$, $r197b$ITEM_CLASS$r197b$, $r197b$J$r197b$, $r197b$费用类别 J（活库观察，语义待人工确认）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q15 共观察到 12 个类别（本批证据快照含 9 个字面）$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$INPBILL$r197b$ AND x.table_name=$r197b$INP_BILL_DETAIL$r197b$
    AND x.column_name=$r197b$ITEM_CLASS$r197b$ AND x.code=$r197b$J$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$INPBILL$r197b$, $r197b$INP_BILL_DETAIL$r197b$, $r197b$ITEM_CLASS$r197b$, $r197b$K$r197b$, $r197b$费用类别 K（活库观察，语义待人工确认）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q15 共观察到 12 个类别（本批证据快照含 9 个字面）$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$INPBILL$r197b$ AND x.table_name=$r197b$INP_BILL_DETAIL$r197b$
    AND x.column_name=$r197b$ITEM_CLASS$r197b$ AND x.code=$r197b$K$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$INPBILL$r197b$, $r197b$INP_BILL_DETAIL$r197b$, $r197b$ITEM_CLASS$r197b$, $r197b$Q$r197b$, $r197b$费用类别 Q（活库观察，语义待人工确认）$r197b$, $r197b$enum$r197b$, $r197b$197 S6 Q15 共观察到 12 个类别（本批证据快照含 9 个字面）$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$INPBILL$r197b$ AND x.table_name=$r197b$INP_BILL_DETAIL$r197b$
    AND x.column_name=$r197b$ITEM_CLASS$r197b$ AND x.code=$r197b$Q$r197b$ AND x.domain_kind=$r197b$enum$r197b$);

INSERT INTO asset.asset_column_value_domains
(system_code, source_code, schema_name, table_name, column_name, code, meaning, domain_kind, note, status, conflict_status, created_at)
SELECT $r197b$HIS_SOURCE$r197b$, $r197b$his_source_10_10_10_15$r197b$, $r197b$INPBILL$r197b$, $r197b$INP_BILL_DETAIL$r197b$, $r197b$OPER_CODE$r197b$, $r197b$多义键$r197b$, $r197b$OPER_CODE 按 ITEM_CLASS 分流：检查类=EXAM_NO、检验类=TEST_NO/APPOINT_NO、手术类=OPER_ID（LENGTH≥8 见 D 类）$r197b$, $r197b$trap$r197b$, $r197b$ISS-S3-OPERMULTI + S6 Q15/Q33 证据；禁止不分类别直接单列挂靠$r197b$, 'pending', 'none', now()
FROM (SELECT 1) guard
WHERE NOT EXISTS (SELECT 1 FROM asset.asset_column_value_domains x
  WHERE x.system_code=$r197b$HIS_SOURCE$r197b$ AND x.source_code=$r197b$his_source_10_10_10_15$r197b$ AND x.schema_name=$r197b$INPBILL$r197b$ AND x.table_name=$r197b$INP_BILL_DETAIL$r197b$
    AND x.column_name=$r197b$OPER_CODE$r197b$ AND x.code=$r197b$多义键$r197b$ AND x.domain_kind=$r197b$trap$r197b$);

INSERT INTO asset.asset_govern_audit_logs
(module, entity_type, entity_ref, action, before_data, after_data, operator, reason, created_at)
VALUES (
  $r197b$relation_intake$r197b$,
  $r197b$asset_relation_recipes+asset_column_value_domains$r197b$,
  $r197b$r197-20260921-s1$r197b$,
  $r197b$batch_insert_draft$r197b$,
  '{"before": {"recipes": 65, "vd_pending": 128}}'::jsonb,
  '{"after": {"recipes_draft_expected": 13, "vd_pending_expected": 34, "payload_recipe_sha256_prefix": "763f565a17ba3642", "vd_candidates": "S6 observed evidence, AI never confirms"}}'::jsonb,
  $r197b$ai:r197-intake$r197b$,
  $r197b$用户2026-09-21批准S7 A2配方draft×13与A3值域pending候选（仅证据，确认人工）$r197b$,
  now());

DO $$
DECLARE r int; p int; c int;
BEGIN
  SELECT count(*) INTO r FROM asset.asset_relation_recipes;
  SELECT count(*) INTO p FROM asset.asset_column_value_domains WHERE status='pending';
  SELECT count(*) INTO c FROM asset.asset_relation_recipes WHERE imported_from='r197_intake';
  IF r <> 78 OR p <> 162 OR c <> 13 THEN
    RAISE EXCEPTION 'A2/A3 守卫失败: recipes=% (期望78) vd_pending=% (期望162) r197_recipes=% (期望13)，事务回滚', r, p, c;
  END IF;
END $$;
