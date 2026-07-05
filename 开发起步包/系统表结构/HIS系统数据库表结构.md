文档编号: 天健—0000—0601—DSM

天健 医院信息系统

数据结构手册

版本1.0.15（第15稿）

天健 HIS工程部

二００六年一月十八日

编写更新记录:

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 26%" />
<col style="width: 11%" />
<col style="width: 17%" />
<col style="width: 23%" />
</colgroup>
<tbody>
<tr class="odd">
<td>版本号</td>
<td><p>作者</p>
<p>日期</p></td>
<td><p>评审者</p>
<p>日期</p></td>
<td><p>批准者</p>
<p>日期</p></td>
<td>说　明</td>
</tr>
<tr class="even">
<td><p>1.0.0</p>
<p>第4稿</p></td>
<td><p>薛万国</p>
<p>1996.6.24</p></td>
<td></td>
<td></td>
<td>由各分系统负责人设计，薛万国修改、审核、定稿</td>
</tr>
<tr class="odd">
<td><p>1.0.0</p>
<p>第5稿</p></td>
<td><p>薛万国</p>
<p>1996.8.22</p></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td><p>1.0.0</p>
<p>第6稿</p></td>
<td><p>薛万国</p>
<p>1996.10.10</p></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td><p>1.0.0</p>
<p>第7稿</p></td>
<td><p>薛万国</p>
<p>1997.05.23</p></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td><p>1.0.0</p>
<p>第8稿</p></td>
<td><p>薛万国</p>
<p>1997.09.04</p></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td><p>1.0.0</p>
<p>第9稿</p></td>
<td><p>薛万国</p>
<p>1998.03.25</p></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td><p>1.0.0</p>
<p>第10稿</p></td>
<td><p>薛万国</p>
<p>1998.06.24</p></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td><p>1.0.0</p>
<p>第11稿</p></td>
<td><p>薛万国</p>
<p>1999.07.16</p></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td><p>1.0.0</p>
<p>第12稿</p></td>
<td><p>薛万国</p>
<p>2000.10.16</p></td>
<td></td>
<td></td>
<td>修改药品、门诊病人管理结构，增医生站设备、输血管理结构</td>
</tr>
<tr class="odd">
<td><p>1.0.0</p>
<p>第13稿</p></td>
<td><p>薛万国</p>
<p>2001.05.23</p></td>
<td></td>
<td></td>
<td>修改医嘱、病案流通、药品结构</td>
</tr>
<tr class="even">
<td><p>1.0.0</p>
<p>第14稿</p></td>
<td><p>陈 飞</p>
<p>2004.12.14</p></td>
<td></td>
<td></td>
<td>全新整理</td>
</tr>
<tr class="odd">
<td><p>1.0.0</p>
<p>第15稿</p></td>
<td><p>张爱玲</p>
<p>2006.01.18</p></td>
<td></td>
<td></td>
<td>全新整理</td>
</tr>
<tr class="even">
<td><p>1.0.0</p>
<p>第15稿</p></td>
<td><p>测试组</p>
<p>2006.03.01</p></td>
<td></td>
<td></td>
<td>门诊医生站,住院病案管理</td>
</tr>
<tr class="odd">
<td><p>1.0.0</p>
<p>第15稿</p></td>
<td><p>张爱玲</p>
<p>2006.05.10</p></td>
<td></td>
<td></td>
<td><p>护士站，门诊，摆药</p>
<p>新增部分字段</p></td>
</tr>
<tr class="even">
<td><p>1.0.0</p>
<p>第15稿</p></td>
<td><p>张爱玲</p>
<p>2006.08.21</p></td>
<td></td>
<td></td>
<td>门诊，护士站，新增表</td>
</tr>
<tr class="odd">
<td><p>1.0.0</p>
<p>第15稿</p></td>
<td><p>张爱玲</p>
<p>2006.10.18</p></td>
<td></td>
<td></td>
<td>价表，护士站，新增字段，新增表</td>
</tr>
</tbody>
</table>

说明: 全部用红字标识的表及字段-----未使用状态

全部用蓝字标识的表及字段------新增且在用状态

用蓝字标识的表字段------新增且在用状态

黑字标识的表字段------在用状态

目录

公共部分

1\. 人员属性 [18](#人员属性)

1.1 性别字典 SEX_DICT [18](#性别字典-sex_dict)

1.2 婚姻状况字典 MARITAL_STATUS_DICT [18](#婚姻状况字典-marital_status_dict)

1.3 民族字典 NATION_DICT [18](#民族字典-nation_dict)

1.4 血型字典 BLOOD_TYPE_DICT [18](#血型字典-blood_type_dict)

1.5 职业分类字典 OCCUPATION_DICT [18](#职业分类字典-occupation_dict)

1.6 身份字典 IDENTITY_DICT [19](#身份字典-identity_dict)

1.7 军种字典 ARMED_SERVICES_DICT [19](#军种字典-armed_services_dict)

1.8 勤务字典 DUTY_DICT [19](#勤务字典-duty_dict)

1.9 费别字典 CHARGE_TYPE_DICT [19](#费别字典-charge_type_dict)

1.10 病人来源字典 PATIENT_SOURCE_DICT [20](#病人来源字典-patient_source_dict)

1.11 入院方式字典 PATIENT_CLASS_DICT [20](#入院方式字典-patient_class_dict)

1.12 出院方式字典 DISCHARGE_DISPOSITION_DICT [20](#出院方式字典-discharge_disposition_dict)

1.13 病情状态字典 PATIENT_STATUS_DICT [20](#病情状态字典-patient_status_dict)

1.14 住院目的字典 ADMISSION_CAUSE_DICT [20](#住院目的字典-admission_cause_dict)

1.15 工作人员字典 STAFF_DICT [21](#工作人员字典-staff_dict)

1.16 用户记录 USERS(修改为试图) [21](#用户记录-users修改为试图)

1.17 技术职务字典 TITLE_DICT [22](#技术职务字典-title_dict)

1.18 工作类别字典 JOB_CLASS_DICT [22](#工作类别字典-job_class_dict)

1.19 社会关系字典 RELATIONSHIP_DICT [22](#社会关系字典-relationship_dict)

1.20 医生职务字典 DOCTOR_TITLE_DICT [22](#医生职务字典-doctor_title_dict)

1.21 入院病情字典 PAT_ADM_CONDITION_DICT [22](#入院病情字典-pat_adm_condition_dict)

1.22 工作组类字典 STAFF_GROUP_CLASS_DICT [22](#工作组类字典-staff_group_class_dict)

1.23 工作组字典 STAFF_GROUP_DICT [23](#工作组字典-staff_group_dict)

1.24 工作人员分组情况 STAFF_VS_GROUP [23](#工作人员分组情况-staff_vs_group)

1.25 费别与身份对照关系 CHARGE_TYPE_VS_IDENTITY [23](#费别与身份对照关系-charge_type_vs_identity)

1.26 医生核算组DOCTOR_GROUP(新增) [24](#医生核算组doctor_group新增)

1.27 挂号模式字典REGIST_MODE_DICT(新增) [24](#挂号模式字典regist_mode_dict新增)

1.28 分娩结果数据字典BIRTH_RESULT_DICT(新增) [24](#分娩结果数据字典birth_result_dict新增)

1.29 分娩方式数据字典BIRTH_TYPE_DICT(新增) [24](#分娩方式数据字典birth_type_dict新增)

1.30 家庭信息表 FAMILY_DICT [24](#家庭信息表-family_dict)

1.31 简易字典代码 META_DATA [25](#简易字典代码-meta_data)

2\. 国家、地区、单位及其属性 [25](#国家地区单位及其属性)

2.1 国家及地区字典 COUNTRY_DICT [25](#国家及地区字典-country_dict)

2.2 行政区字典 AREA_DICT [26](#行政区字典-area_dict)

2.3 医院基本情况 HOSPITAL_CONFIG [26](#医院基本情况-hospital_config)

2.4 合同单位记录 UNIT_IN_CONTRACT [26](#合同单位记录-unit_in_contract)

2.5 合同单位人员分类情况 STAFF_IN_CONTRACT [27](#合同单位人员分类情况-staff_in_contract)

2.6 科室字典 DEPT_DICT [27](#科室字典-dept_dict)

2.7 临床科室配置情况 CLINICAL_DEPT_CONFIG [27](#临床科室配置情况-clinical_dept_config)

2.8 临床科室与病房（区）对照 DEPT_VS_WARD [28](#临床科室与病房区对照-dept_vs_ward)

2.9 单位性质字典 UNIT_TYPE_DICT [28](#单位性质字典-unit_type_dict)

2.10 科室临床属性字典 DEPT_CLINIC_ATTR_DICT [28](#科室临床属性字典-dept_clinic_attr_dict)

2.11 科室门诊住院属性字典 DEPT_OI_ATTR_DICT [28](#科室门诊住院属性字典-dept_oi_attr_dict)

2.12 科室内外科属性字典 DEPT_IS_ATTR_DICT [28](#科室内外科属性字典-dept_is_attr_dict)

2.13 营养室字典 DIET_PROVIDER_DICT [29](#营养室字典-diet_provider_dict)

2.14 ADDRESS_detailed_DICT 详细地址字典 [29](#address_detailed_dict-详细地址字典)

2.15 大单位字典 TOP_UNIT_DICT [29](#大单位字典-top_unit_dict)

3\. 医疗工作 [30](#医疗工作)

3.1 门诊专科字典 SPECIAL_CLINIC_DICT [30](#门诊专科字典-special_clinic_dict)

3.2 检查号类别字典 LOCAL_ID_CLASS_DICT [30](#检查号类别字典-local_id_class_dict)

3.3 检查类别字典 EXAM_CLASS_DICT [30](#检查类别字典-exam_class_dict)

3.4 检查子类字典 EXAM_SUBCLASS_DICT [30](#检查子类字典-exam_subclass_dict)

3.5 号类字典CLINIC_TYPE_DICT [31](#号类字典clinic_type_dict)

3.6 号类设置表 CLINIC_TYPE_SETTING [31](#号类设置表-clinic_type_setting)

3.7 检查结果状态字典EXAM_RESULT_STATUS_DICT [32](#检查结果状态字典exam_result_status_dict)

3.8 病人状态变化字典 PATIENT_STATUS_CHG_DICT [32](#病人状态变化字典-patient_status_chg_dict)

3.9 时间段字典 TIME_INTERVAL_DICT [32](#时间段字典-time_interval_dict)

3.10 病案质量字典 MR_QUALITY_DICT [32](#病案质量字典-mr_quality_dict)

3.11 病案价值字典 MR_VALUE_DICT [32](#病案价值字典-mr_value_dict)

3.12 病案状态字典 MR_STATUS_DICT [33](#病案状态字典-mr_status_dict)

3.13 病案类别字典 MR_CLASS_DICT [33](#病案类别字典-mr_class_dict)

3.14 病案复印登记表 [33](#病案复印登记表)

3.15 床位状态字典 BED_STATUS_DICT [33](#床位状态字典-bed_status_dict)

3.16 床位类型字典 BED_TYPE_DICT [34](#床位类型字典-bed_type_dict)

3.17 床位等级字典 BED_CLASS_DICT [34](#床位等级字典-bed_class_dict)

3.18 床位编制类型字典 BED_APPROVED_TYPE_DICT [34](#床位编制类型字典-bed_approved_type_dict)

3.19 病案内容分类字典 MR_COMP_CLASS_DICT [34](#病案内容分类字典-mr_comp_class_dict)

3.20 空调类型字典AIRCONDITION_CLASS_DICT(新增) [34](#空调类型字典aircondition_class_dict新增)

3.21 床位与空调类型对照表BED_VS_AIRCONDITION(新增) [35](#床位与空调类型对照表bed_vs_aircondition新增)

3.22 医生说明字典DOCTOR_EXPLAIN_DICT(新增) [35](#医生说明字典doctor_explain_dict新增)

3.23 DEPT_CODE_VS_FACTID(新增) [35](#dept_code_vs_factid新增)

3.24 护理类型字典NURSE_TEMPERATURE_CLASS_DICT(新增) [35](#护理类型字典nurse_temperature_class_dict新增)

3.25 护理项目字典NURSE_TEMPERATURE_ITEM_DICT(新增) [35](#护理项目字典nurse_temperature_item_dict新增)

3.26 诊室字典ROOM_DICT(不使用) [36](#诊室字典room_dict不使用)

4\. 疾病诊断与医疗操作 [37](#疾病诊断与医疗操作)

4.1 疾病字典 DIAGNOSIS_DICT [37](#疾病字典-diagnosis_dict)

4.2 手术操作字典 OPERATION_DICT [37](#手术操作字典-operation_dict)

4.3 检查诊断字典 EXAM_DIAG_DICT [37](#检查诊断字典-exam_diag_dict)

4.4 中医诊断关系表 CDIAG_ITEM_DICT [38](#中医诊断关系表-cdiag_item_dict)

4.5 诊断类别字典 DIAGNOSIS_TYPE_DICT [38](#诊断类别字典-diagnosis_type_dict)

4.6 诊断对照组字典 DIAG_COMP_GROUP_DICT [38](#诊断对照组字典-diag_comp_group_dict)

4.7 临床诊疗项目字典 CLINIC_ITEM_DICT [38](#临床诊疗项目字典-clinic_item_dict)

4.8 临床诊疗项目操作日志表 CLINIC_OPER_LOG [39](#临床诊疗项目操作日志表-clinic_oper_log)

4.9 检查项目字典 EXAM_ITEM_DICT [40](#检查项目字典-exam_item_dict)

4.10 检验项目字典 LAB_ITEM_DICT [40](#检验项目字典-lab_item_dict)

4.11 治疗操作项目字典 TREAT_ITEM_DICT [40](#治疗操作项目字典-treat_item_dict)

4.12 护理项目字典 NURSING_DICT [40](#护理项目字典-nursing_dict)

4.13 膳食项目字典 DIET_DICT [40](#膳食项目字典-diet_dict)

4.14 临床诊疗项目名称字典 CLINIC_ITEM_NAME_DICT [40](#临床诊疗项目名称字典-clinic_item_name_dict)

4.15 检验项目名称字典 LAB_ITEM_NAME_DICT [41](#检验项目名称字典-lab_item_name_dict)

4.16 治疗操作名称字典 TREAT_ITEM_NAME_DICT [41](#治疗操作名称字典-treat_item_name_dict)

4.17 护理等级字典 NURSING_CLASS_DICT [41](#护理等级字典-nursing_class_dict)

4.18 手术等级字典 OPERATION_SCALE_DICT [42](#手术等级字典-operation_scale_dict)

4.19 给药途径字典ADMINISTRATION_DICT [42](#给药途径字典administration_dict)

4.20 麻醉方法字典 ANAESTHESIA_DICT [42](#麻醉方法字典-anaesthesia_dict)

4.21 医嘱状态字典 ORDER_STATUS_DICT [42](#医嘱状态字典-order_status_dict)

4.22 剂量单位字典 DOSAGE_UNITS_DICT [43](#剂量单位字典-dosage_units_dict)

4.23 医嘱执行频率字典 PERFORM_FREQ_DICT [43](#医嘱执行频率字典-perform_freq_dict)

4.24 医嘱执行缺省时间表 PERFORM_DEFAULT_SCHEDULE [43](#医嘱执行缺省时间表-perform_default_schedule)

4.25 辅助诊断项目字典 ANCI_EXAM_ITEM_DICT [43](#辅助诊断项目字典-anci_exam_item_dict)

4.26 辅助治疗项目字典 ANCI_TREAT_ITEM_DICT [44](#辅助治疗项目字典-anci_treat_item_dict)

4.27 检验单定义 LAB_SHEET_MASTER [44](#检验单定义-lab_sheet_master)

4.28 检验单项目定义 LAB_SHEET_ITEMS [44](#检验单项目定义-lab_sheet_items)

4.29 检查报告模板 EXAM_RPT_PATTERN [45](#检查报告模板-exam_rpt_pattern)

4.30 治疗结果字典 TREATING_RESULT_DICT [45](#治疗结果字典-treating_result_dict)

4.31 切口愈合情况字典 HEAL_DICT [46](#切口愈合情况字典-heal_dict)

4.32 诊断符合情况字典 DIAG_CORR_DICT [46](#诊断符合情况字典-diag_corr_dict)

4.33 时间单位字典 TIME_UNITS_DICT [46](#时间单位字典-time_units_dict)

4.34 计量单位字典 MEASURES_DICT [46](#计量单位字典-measures_dict)

4.35 星期字典 DAY_OF_WEEK_DICT [47](#星期字典-day_of_week_dict)

4.36 诊疗项目分类字典 CLINIC_ITEM_CLASS_DICT [47](#诊疗项目分类字典-clinic_item_class_dict)

4.37 标本字典 SPECIMAN_DICT [47](#标本字典-speciman_dict)

4.38 检验报告项目字典 LAB_REPORT_ITEM_DICT [47](#检验报告项目字典-lab_report_item_dict)

4.39 检验结果模板字典 LAB_LIST_RESULT_DICT [48](#检验结果模板字典-lab_list_result_dict)

4.40 检验申请项目与报告项目对照 LAB_ORDER_VS_REPORT [48](#检验申请项目与报告项目对照-lab_order_vs_report)

4.41 切口等级字典 WOUND_GRADE_DICT [48](#切口等级字典-wound_grade_dict)

4.42 检验项目与分类对照 LAB_ITEM_VS_CLASS [48](#检验项目与分类对照-lab_item_vs_class)

4.43 检验项目类别字典 LAB_ITEM_CLASS_DICT [49](#检验项目类别字典-lab_item_class_dict)

4.44 检验报告项目与申请项目对照 LAB_REPORT_VS_ORDER [49](#检验报告项目与申请项目对照-lab_report_vs_order)

4.45 药物过敏严重程度字典 DRUG_ALERGY_SEVERITY_DICT(不使用) [49](#药物过敏严重程度字典-drug_alergy_severity_dict不使用)

4.46 合理用药相关表MDC_DRUG_MATCH_RESULT(不使用) [49](#合理用药相关表mdc_drug_match_result不使用)

4.47 合理用药相关表MDC_ROUTE_MATCH_RESULT(不使用) [50](#合理用药相关表mdc_route_match_result不使用)

4.48 MEDCARD_PRIVILEGE_DICT(不使用) [50](#medcard_privilege_dict不使用)

4.49 QUALITY_GRAND_DICT(不使用) [50](#quality_grand_dict不使用)

5\. 药品物资 [51](#药品物资)

5.1 药品字典 DRUG_DICT [51](#药品字典-drug_dict)

5.2 药品名称字典 DRUG_NAME_DICT [51](#药品名称字典-drug_name_dict)

5.3 药品价格 DRUG_PRICE_LIST [52](#药品价格-drug_price_list)

5.4 公费用药目录 OFFICIAL_DRUG_CATALOG [53](#公费用药目录-official_drug_catalog)

5.5 药品入库分类字典 DRUG_IMPORT_CLASS_DICT [53](#药品入库分类字典-drug_import_class_dict)

5.6 药品出库分类字典 DRUG_EXPORT_CLASS_DICT [53](#药品出库分类字典-drug_export_class_dict)

5.7 药品处方属性字典 DRUG_PRESC_ATTR_DICT [53](#药品处方属性字典-drug_presc_attr_dict)

5.8 药品摆药类别字典 DRUG_DISP_PROPERTY_DICT [53](#药品摆药类别字典-drug_disp_property_dict)

5.9 药品供应商目录 DRUG_SUPPLIER_CATALOG [54](#药品供应商目录-drug_supplier_catalog)

5.10 药品毒理分类字典 DRUG_TOXI_PROPERTY_DICT [54](#药品毒理分类字典-drug_toxi_property_dict)

5.11 药品剂型字典 DRUG_FORM_DICT [54](#药品剂型字典-drug_form_dict)

5.12 药品类别字典 DRUG_CLASS_DICT [54](#药品类别字典-drug_class_dict)

5.13 药品编码描述 DRUG_CODING_RULE [55](#药品编码描述-drug_coding_rule)

5.14 药品信息 DRUG_INFO [55](#药品信息-drug_info)

5.15 药品相互作用 DRUG_INCOMPATIBILITY [55](#药品相互作用-drug_incompatibility)

5.16 药品用量信息COMM.drug_rational_dosage(新增) [55](#药品用量信息comm.drug_rational_dosage新增)

5.17 中标价格类别TENDER_PRICE_CLASS(新增) [56](#中标价格类别tender_price_class新增)

5.18 中标药品字典TENDER_DRUG_DICT(新增) [56](#中标药品字典tender_drug_dict新增)

5.19 货位名称LOCATION(新增) [57](#货位名称location新增)

5.20 设备字典EQUIP_DICT [57](#设备字典equip_dict)

5.21 设备制造商字典EQUIP_MANUFACTURE_DICT [57](#设备制造商字典equip_manufacture_dict)

5.22 设备名称字典EQUIP_NAME_DICT [57](#设备名称字典equip_name_dict)

5.23 EQUIP_VS_FEE_DICT [57](#equip_vs_fee_dict)

5.24 消耗品编码规则EXP_CODING_RULE [58](#消耗品编码规则exp_coding_rule)

5.25 消耗品字典EXP_DICT [58](#消耗品字典exp_dict)

5.26 消耗品币值字典EXP_FUND_ITEM_DICT [58](#消耗品币值字典exp_fund_item_dict)

5.27 消耗品名称字典EX_NAME_DICT [58](#消耗品名称字典exp_name_dict)

5.28 消耗品属性字典EXPP_PROPERTY_DICT [59](#消耗品属性字典exp_property_dict)

5.29 消耗品价表EXP_PRICE_LIST [59](#消耗品价表exp_price_list)

5.30 消耗品打包模板明细记录 [59](#消耗品打包模板明细记录)

5.31 供应商字典EXP_SUPPLIER_CATALOG [60](#供应商字典exp_supplier_catalog)

5.32 经费来源字典FUND_SOURCE_DICT [60](#经费来源字典fund_source_dict)

5.33 公费用药目录OFFICIAL_DRUG_CATALOG(新增) [60](#公费用药目录official_drug_catalog新增)

5.34 公费用药目录限制级别字典OFFICIAL_DRUG_CATALOG_CLASS(新增) [61](#公费用药目录限制级别字典official_drug_catalog_class新增)

5.35 过敏药品字典 ALERGY_DRUGS_DICT [61](#过敏药品字典-alergy_drugs_dict)

5.36 质控反馈信息字典QC_MSG_DICT [61](#质控反馈信息字典qc_msg_dict)

6\. 费用 [62](#费用)

6.1 价表 PRICE_LIST [62](#价表-price_list)

6.2 当前价表 CURRENT_PRICE_LIST [63](#当前价表-current_price_list)

6.3 价表项目分类与其他分类对照表 ITEM_CLASS_VS_OTHER_CLASS [64](#价表项目分类与其他分类对照表-item_class_vs_other_class)

6.4 价表项目名称字典 PRICE_ITEM_NAME_DICT [64](#价表项目名称字典-price_item_name_dict)

6.5 计价单位字典 BILL_UNITS_DICT [64](#计价单位字典-bill_units_dict)

6.6 收费系数字典 CHARGE_PRICE_SCHEDULE [65](#收费系数字典-charge_price_schedule)

6.7 价表项目执行科室 PERFORM_DEPT [65](#价表项目执行科室-perform_dept)

6.8 临床诊疗项目与价表项目对照表 CLINIC_VS_CHARGE [65](#临床诊疗项目与价表项目对照表-clinic_vs_charge)

6.9 医嘱附加计价项目字典 EXTRA_COSTS_DICT [66](#医嘱附加计价项目字典-extra_costs_dict)

6.10 价表项目分类字典 BILL_ITEM_CLASS_DICT [66](#价表项目分类字典-bill_item_class_dict)

6.11 病案首页费用分类字典 MR_FEE_CLASS_DICT [66](#病案首页费用分类字典-mr_fee_class_dict)

6.12 门诊收据费用分类字典 OUTP_RCPT_FEE_DICT [66](#门诊收据费用分类字典-outp_rcpt_fee_dict)

6.13 住院收据费用分类字典 INP_RCPT_FEE_DICT [67](#住院收据费用分类字典-inp_rcpt_fee_dict)

6.14 核算项目分类字典 RECK_ITEM_CLASS_DICT [67](#核算项目分类字典-reck_item_class_dict)

6.15 会计科目字典 TALLY_SUBJECT_DICT [67](#会计科目字典-tally_subject_dict)

6.16 支付方式字典 PAY_WAY_DICT [67](#支付方式字典-pay_way_dict)

6.17 预交金操作类型字典 PREPAY_TRANS_TYPE_DICT [68](#预交金操作类型字典-prepay_trans_type_dict)

6.18 结算操作类型字典 SETTLE_TRANS_TYPE_DICT [68](#结算操作类型字典-settle_trans_type_dict)

6.19 支票标识字典 CHECK_LABEL_DICT [68](#支票标识字典-check_label_dict)

6.20 收费特殊项目字典 CHARGE_SPECIAL_ITEM_DICT [68](#收费特殊项目字典-charge_special_item_dict)

6.21 收费特殊项目排斥字典 CHARGE_SPECIAL_EXCEPT_DICT [69](#收费特殊项目排斥字典-charge_special_except_dict)

6.22 收费部门分组字典 BILLING_GROUP_DICT [70](#收费部门分组字典-billing_group_dict)

6.23 费用模板主记录 BILL_PATTERN_MASTER [70](#费用模板主记录-bill_pattern_master)

6.24 费用模板明细记录 BILL_PATTERN_DETAIL [70](#费用模板明细记录-bill_pattern_detail)

6.25 特殊号别价格字典SPECIAL_CLINIC_PRICE(不使用) [71](#特殊号别价格字典special_clinic_price不使用)

6.26 号类收费设置表 CLINIC_TYPE_CHARGE_DICT(新增) [71](#号类收费设置表-clinic_type_charge_dict新增)

6.27 挂号支付方式字典REGIST_PAY_DICT [71](#挂号支付方式字典regist_pay_dict)

6.28 治疗类别字典CURE_CLASS_DICT(不使用) [71](#治疗类别字典cure_class_dict不使用)

6.29 币种字典MONEY_DICT [71](#币种字典money_dict)

6.30 OUTP_RCPT_FEE_FACTDICT [72](#outp_rcpt_fee_factdict)

6.31 OUTP_RCPT_FEE_VS_FACTCODE [72](#outp_rcpt_fee_vs_factcode)

6.32 PAY_STYLE_DICT [72](#pay_style_dict)

7\. 系统维护 [73](#系统维护)

7.1 病人标识号引用表 PATIENT_ID_REF [73](#病人标识号引用表-patient_id_ref)

7.2 应用程序记录 APPLICATIONS [73](#应用程序记录-applications)

7.3 应用程序权限记录 APP_GRANTS [73](#应用程序权限记录-app_grants)

7.4 联机帮助信息 HELP_MSG [73](#联机帮助信息-help_msg)

7.5 字典信息 METADICT [74](#字典信息-metadict)

7.6 计算机站点 CLIENT_INSTALLATION [74](#计算机站点-client_installation)

7.7 组表SECURITY_GROUPINGS [74](#组表security_groupings)

7.8 组对应的权限表 SECURITY_INFO [74](#组对应的权限表-security_info)

7.9 用户信息表 SECURITY_USERS [75](#用户信息表-security_users)

7.10 SECURITY_APPS [75](#security_apps)

7.11 控件模板表 SECURITY_TEMPLATE [75](#控件模板表-security_template)

7.12 应用角色APP_ROLES [75](#应用角色app_roles)

7.13 应用参数表信息APP_CONFIGER_BASEINFO(新增) [75](#应用参数表信息app_configer_baseinfo新增)

7.14 应用参数设置表APP_CONFIGER_PARAMETER(新增) [76](#应用参数设置表app_configer_parameter新增)

7.15 AUTO_SETTING(不使用) [76](#auto_setting不使用)

7.16 自动生成ID表AUTO_SETTING_ID [76](#自动生成id表auto_setting_id)

7.17 密码字典KEY_DICT [77](#密码字典key_dict)

7.18 表字段解释说明TABLE_COLUMNS_SET [77](#表字段解释说明table_columns_set)

7.19 表角色解释说明TABLE_ROLE_SET [77](#表角色解释说明table_role_set)

7.20 表同义词解释说明TABLE_SYNONYM_SET [77](#表同义词解释说明table_synonym_set)

7.21 组权限表 SECURITY_INFO_PRG [78](#组权限表-security_info_prg)

7.22 数据窗口界面控制显示表 DATAWINDOW_UI_CONTROL [78](#数据窗口界面控制显示表-datawindow_ui_control)

8\. 输入法 [78](#输入法)

8.1 输入码类型 input_type [78](#输入码类型-input_type)

8.2 输入法配置 INPUT_SETTING [78](#输入法配置-input_setting)

8.3 输入法配置表 OUTER_CODING_CONFIG [79](#输入法配置表-outer_coding_config)

8.4 输入码表 OUTER_CODE_DICT [80](#输入码表-outer_code_dict)

8.5 层次输入法定义 CLASS_CODING_CONFIG [80](#层次输入法定义-class_coding_config)

8.6 分层编码描述 CLASS_CODING_RULE [80](#分层编码描述-class_coding_rule)

8.7 词库生成规则表OUTER_GENERATION [81](#词库生成规则表outer_generation)

8.8 模块与词库对照表OUTER_APP_USE [81](#模块与词库对照表outer_app_use)

8.9 INPUT_CODE_DICT [81](#input_code_dict)

8.10 MESSAGES [81](#messages)

9\. 病案 [83](#病案)

9.1 病人主索引 PAT_MASTER_INDEX [83](#病人主索引-pat_master_index)

9.2 病人住院主记录 PAT_VISIT [84](#病人住院主记录-pat_visit)

9.3 病人在科记录 TRANSFER [89](#病人在科记录-transfer)

9.4 诊断记录 DIAGNOSIS [90](#诊断记录-diagnosis)

9.5 门诊诊断记录 CLINIC_DIAGNOSIS [90](#门诊诊断记录-clinic_diagnosis)

9.6 主要诊断 FINAL_CHIEF_DIAGNOSIS [90](#主要诊断-final_chief_diagnosis)

9.7 诊断分类记录 DIAGNOSTIC_CATEGORY [91](#诊断分类记录-diagnostic_category)

9.8 手术记录 OPERATION [91](#手术记录-operation)

9.9 诊断对照记录 DIAG_COMPARING [92](#诊断对照记录-diag_comparing)

9.10 住院病人费用记录 MEDICAL_COSTS [92](#住院病人费用记录-medical_costs)

9.11 病人输血记录 BLOOD_TRANSFUSION [92](#病人输血记录-blood_transfusion)

9.12 病人过敏药物记录 ALERGY_DRUGS(不使用) [93](#病人过敏药物记录-alergy_drugs不使用)

9.13 主索引合并记录 PMI_MERGED_LOG [93](#主索引合并记录-pmi_merged_log)

9.14 病案记录 MR_REC [93](#病案记录-mr_rec)

9.15 病案追踪日志 MR_TRACE_LOG [94](#病案追踪日志-mr_trace_log)

9.16 病案索引 MR_INDEX [94](#病案索引-mr_index)

9.17 病历文件索引 MR_FILE_INDEX [95](#病历文件索引-mr_file_index)

9.18 联机病历描述MR_ON_LINE [96](#联机病历描述mr_on_line)

9.19 病历模板索引 MR_TEMPLET_INDEX [96](#病历模板索引-mr_templet_index)

9.20 病历模板选择MR_TEMPLET_SELECTION [97](#病历模板选择mr_templet_selection)

9.21 当前病历路径描述MR_WORK_PATH [97](#当前病历路径描述mr_work_path)

9.22 病案纸张描述MR_PAPER_DESC [97](#病案纸张描述mr_paper_desc)

9.23 医疗质量问题分类字典QA_EVENT_TYPE_DICT [97](#医疗质量问题分类字典qa_event_type_dict)

9.24 修改姓名记录表PAT_MASTER_RENAME_LOG (新增) [98](#修改姓名记录表pat_master_rename_log-新增)

9.25 卡地址描述表MEDCARD_ADDRESS_REC(新增) [98](#卡地址描述表medcard_address_rec新增)

9.26 医疗卡门诊就医系统运行配置表MEDCARD_CONFIG(新增) [98](#医疗卡门诊就医系统运行配置表medcard_config新增)

9.27 医疗卡类型字典MEDICAL_CARD_TYPE_DICT(新增) [99](#医疗卡类型字典medical_card_type_dict新增)

9.28 医疗卡说明MEDICAL_CARD_MEMO(新增) [99](#医疗卡说明medical_card_memo新增)

9.29 医疗卡变更日志MEDICAL_CARD_LOG(新增) [99](#医疗卡变更日志medical_card_log新增)

9.30 新生儿记录表NEWBORN_REC(新增) [100](#新生儿记录表newborn_rec新增)

9.31 OPER_SETTLE_CARD [102](#oper_settle_card)

9.32 PATIENT_CARD_INFO [102](#patient_card_info)

9.33 住院号取消日志INP_CANCEL_LOG(新增) [103](#住院号取消日志inp_cancel_log新增)

9.34 病案复印记录MR_COPY_REC [103](#病案复印记录mr_copy_rec)

9.35 卫统科室字典STAT_DEPT_DICT [103](#卫统科室字典stat_dept_dict)

9.36 卫统费用对照STAT_VS_FEE_CLASS [103](#卫统费用对照stat_vs_fee_class)

9.37 卫统5代码字典MR_WT5_DICT [103](#卫统5代码字典mr_wt5_dict)

9.38 卫统5代码字典与HIS字典对照MR_HIS_VS_WT5 [104](#卫统5代码字典与his字典对照mr_his_vs_wt5)

9.39 卫统5接口表mr_wt5_interface [104](#卫统5接口表mr_wt5_interface)

9.40 病案存放位置字典 mr_location_dict [107](#统计病种字典-mr_report_diag)

10\. 门诊病人管理 [108](#门诊病人管理)

10.1 门诊号别定义CLINIC_INDEX [108](#门诊号别定义clinic_index)

10.2 门诊安排记录 CLINIC_SCHEDULE [108](#门诊安排记录-clinic_schedule)

10.3 门诊号表 CLINIC_FOR_REGIST [108](#门诊号表-clinic_for_regist)

10.4 门诊预约记录 CLINIC_APPOINTS [109](#门诊预约记录-clinic_appoints)

10.5 就诊记录 CLINIC_MASTER [110](#就诊记录-clinic_master)

10.6 特殊挂号费价表SPECIAL_REGIST_PRICE(不使用) [111](#特殊挂号费价表special_regist_price不使用)

10.7 诊疗费价表CLINIC_PRICE [111](#诊疗费价表clinic_price)

10.8 请求提供病案队列MR_REQUEST_QUEUE [112](#请求提供病案队列mr_request_queue)

10.9 挂号结帐主记录REGIST_ACCT_MASTER [112](#挂号结帐主记录regist_acct_master)

10.10 挂号结帐明细REGIST_ACCT_DETAIL [112](#挂号结帐明细regist_acct_detail)

10.11 挂号结帐金额分类 REGIST_ACCT_MONEY [112](#挂号结帐金额分类regist_acct_money)

10.12 请求提供病案队列备份MR_REQUEST_QUEUE_BACKUP [113](#请求提供病案队列备份mr_request_queue_backup)

10.13 CLINIC_MASTER_DAYNUMBER_TEMP(不使用) [113](#clinic_master_daynumber_temp不使用)

10.14 门诊挂号退号记录CLINIC_RETURNED_ACCT [113](#门诊挂号退号记录clinic_returned_acct)

10.15 待诊病人信息outp_counseled_clipat（针对174医院） [114](#待诊病人信息outp_counseled_clipat针对174医院)

10.16 已分诊的特诊病人outp_counseled_exampat（针对174医院） [115](#已分诊的特诊病人outp_counseled_exampat针对174医院)

10.17 分诊台管理科室outp_counsel_dept（针对174医院） [115](#分诊台管理科室outp_counsel_dept针对174医院)

10.18 分诊台管理医生 outp_counsel_doctor （针对174医院） [115](#分诊台管理医生-outp_counsel_doctor-针对174医院)

10.19 分诊台安排OUTP_COUNSEL_NODE_DICT [116](#分诊台安排outp_counsel_node_dict)

10.20 OUTP_COUNSEL_PATIENT_SOURCE(不使用) [116](#outp_counsel_patient_source不使用)

10.21 分诊优先原因字典outp_counsel_priority（针对174医院） [116](#分诊优先原因字典outp_counsel_priority针对174医院)

10.22 分诊台与队列对照OUTP_COUNSEL_QUEUE [117](#分诊台与队列对照outp_counsel_queue)

10.23 医生呼叫消息outp_counsel_request_info [117](#医生呼叫消息outp_counsel_request_info)

10.24 分诊台队列管理outp_queue_dict [117](#分诊台队列管理outp_queue_dict)

10.25 队列序号记录表outp_queue_sequence（针对174医院） [117](#队列序号记录表outp_queue_sequence针对174医院)

10.26 发票重打日志REGIST_REPRINT_LOG [118](#发票重打日志regist_reprint_log)

11\. 门诊医生 [118](#门诊医生)

11.1 门诊病历记录OUTP_MR [118](#门诊病历记录outp_mr)

11.2 门诊病人体征信息Pat_soma \_chatacter [119](#门诊病人体征信息pat_soma-_chatacter)

11.3 中药模板主记录 CDRUG_PROJECT_MASTER [119](#中药模板主记录-cdrug_project_master)

11.4 中药模板明细记录 CDRUG_PROJECT_ITEMS [120](#中药模板明细记录-cdrug_project_items)

11.5 门诊医嘱主记录OUTP_ORDERS [120](#门诊医嘱主记录outp_orders)

11.6 处方医嘱明细记录OUTP_PRESC [121](#处方医嘱明细记录outp_presc)

11.7 检查治疗医嘱明细记录OUTP_TREAT_REC [122](#检查治疗医嘱明细记录outp_treat_rec)

11.8 治疗方案模板主记录TREAT_PROJECT_MASTER [122](#治疗方案模板主记录treat_project_master)

11.9 治疗方案模板明细TREAT_PROJECT_ITEMS [123](#治疗方案模板明细treat_project_items)

11.10 门诊医嘱主记录队列OUTP_ORDERS_T [123](#门诊医嘱主记录队列outp_orders_t)

11.11 处方医嘱队列OUTP_PRESC_T [124](#处方医嘱队列outp_presc_t)

11.12 检查治疗医嘱队列OUTP_TREAT_REC_T [124](#检查治疗医嘱队列outp_treat_rec_t)

11.13 诊室候诊排队记录OUTP_WAIT_QUEUE [125](#诊室候诊排队记录outp_wait_queue)

11.14 门诊医生值班安排 OUTP_DOCTOR_SCHEDULE [125](#门诊医生值班安排-outp_doctor_schedule)

11.15 门诊医生坐诊日志OUTP_DOCTOR_REGIST [126](#门诊医生坐诊日志outp_doctor_regist)

11.16 门诊医生检查主记录EXAM_MASTER_OUTP(不使用) [126](#门诊医生检查主记录exam_master_outp不使用)

11.17 门诊医生检查项目记录EXAM_ITEMS_OUTP(不使用) [127](#门诊医生检查项目记录exam_items_outp不使用)

11.18 门诊病历诊断记录OUTP_MR_DIAG_DESC [127](#门诊病历诊断记录outp_mr_diag_desc)

11.19 门诊病历模板制作OUTP_MR_ITEMSELECT [127](#门诊病历模板制作outp_mr_itemselect)

11.20 门诊病历模板选择OUTP_MR_ITEMCHOOSE [127](#门诊病历模板选择outp_mr_itemchoose)

11.21 门诊医生收费明细OUTP_ORDERS_COSTS [127](#门诊医生收费明细outp_orders_costs)

11.22 队列序号记录表outp_queue_sequence（针对174医院） [129](#队列序号记录表outp_queue_sequence针对174医院-1)

11.23 门诊医生会诊主索引OUTP_CONSULTATION_MASTER(新增) [129](#门诊医生会诊主索引outp_consultation_master新增)

11.24 门诊医生会诊明细OUTP_CONSULTATION_DETAIL (新增) [130](#门诊医生会诊明细outp_consultation_detail新增)

11.25 公共模板索引字典 model_project_dict (新增) [130](#公共模板索引字典-model_project_dict-新增)

11.26 门诊住院公共模板 model_items （新增） [130](#门诊住院公共模板-model_items-新增)

11.27 公共模板项目选择model_items_select (新增) [131](#公共模板项目选择model_items_select-新增)

12\. 住院病人管理 [131](#住院病人管理)

12.1 等床病人记录 WAIT_BED_PATS [131](#等床病人记录-wait_bed_pats)

12.2 床位记录 BED_REC [132](#床位记录-bed_rec)

12.3 在院病人记录 PATS_IN_HOSPITAL [133](#在院病人记录-pats_in_hospital)

12.4 病人入出转及状态变化日志 ADT_LOG [135](#病人入出转及状态变化日志-adt_log)

**12.5** 转科病人记录 PATS_IN_TRANSFERRING [135](#转科病人记录-pats_in_transferring)

**12.6** 准备出院病人记录 PRE_DISCHGED_PATS [135](#准备出院病人记录-pre_dischged_pats)

12.7 借床日志表LEND_BED_LOG(新增) [136](#借床日志表lend_bed_log新增)

12.8 经管医生记录ORDERS_GROUP_REC(新增) [136](#经管医生记录orders_group_rec新增)

12.9 病案质控日志MEDICAL_QC_LOG [136](#病案质控日志medical_qc_log)

12.10 质控信息病人信息表MEDICAL_QC_MSG [137](#质控信息病人信息表medical_qc_msg)

13\. 医嘱 [138](#医嘱)

13.1 医嘱 ORDERS [138](#医嘱-orders)

13.2 医嘱计价项目 ORDERS_COSTS [140](#医嘱计价项目-orders_costs)

13.3 医嘱执行表orders_execute [141](#医嘱执行表orders_execute)

13.4 病人体症记录 VITAL_SIGNS_REC [142](#病人体症记录-vital_signs_rec)

13.5 医嘱记录单影象 ORDERS_SHEET_IMAGE [143](#医嘱记录单影象-orders_sheet_image)

13.6 医生医嘱 DOCTOR_ORDERS(不使用) [143](#医生医嘱-doctor_orders不使用)

13.7 成组医嘱模板主记录GROUP_ORDER_MASTER [145](#成组医嘱模板主记录group_order_master)

13.8 成组医嘱模板明细GROUP_ORDER_ITEMS [146](#成组医嘱模板明细group_order_items)

13.9 医生级医嘱模板对应表GROUP_ORDER_SELECTION(新增) [146](#医生级医嘱模板对应表group_order_selection新增)

13.10 会诊子表CONSULTATION_DOCTOR_DETAIL(新增) [146](#会诊子表consultation_doctor_detail新增)

13.11 会诊主表CONSULTATION_DOCTOR_MASTER(新增) [147](#会诊主表consultation_doctor_master新增)

13.12 治疗申请表CURE_APPOINTS(不使用) [147](#治疗申请表cure_appoints不使用)

13.13 治疗方案记录CURE_PROJECT(不使用) [147](#治疗方案记录cure_project不使用)

13.14 治疗报告单CURE_REPORT(不使用) [148](#治疗报告单cure_report不使用)

13.15 特殊治疗明细SPECIALTIES_CURE_DETAIL(不使用) [148](#特殊治疗明细specialties_cure_detail不使用)

13.16 特殊治疗主记录SPECIALTIES_CURE_MASTER(不使用) [148](#特殊治疗主记录specialties_cure_master不使用)

14\. 检查 [150](#检查)

14.1 检查病人主索引 EXAM_PAT_MI [150](#检查病人主索引-exam_pat_mi)

14.2 检查预约记录 EXAM_APPOINTS [151](#检查预约记录exam_appoints)

14.3 检查主记录 EXAM_MASTER [153](#检查主记录exam_master)

14.4 检查项目记录 EXAM_ITEMS [155](#检查项目记录-exam_items)

14.5 检查报告 EXAM_REPORT [156](#检查报告-exam_report)

14.6 检查图象索引 EXAM_IMAGE_INDEX [156](#检查图象索引-exam_image_index)

14.7 检查随访记录 EXAM_INQUIRY [157](#检查随访记录-exam_inquiry)

14.8 检查工作时间安排 EXAM_WORKING_PLAN [158](#检查工作时间安排-exam_working_plan)

14.9 检查时间间隔 EXAM_INTERVAL [158](#检查时间间隔-exam_interval)

14.10 检查病人时间安排 EXAM_SCHEDULE [159](#检查病人时间安排-exam_schedule)

14.11 检查分组字典 EXAM_GROUP_DICT [159](#检查分组字典-exam_group_dict)

14.12 检查计价项目 EXAM_BILL_ITEMS [159](#检查计价项目-exam_bill_items)

14.13 BACKUP_PATIENT [160](#backup_patient)

14.14 BACKUP_STUDY [160](#backup_study)

14.15 EMP_DICT [161](#emp_dict)

14.16 EXAM_SUBDEPT_DICT [161](#exam_subdept_dict)

14.17 MODALITY_VS_LOCAL_ID_CLASS [161](#modality_vs_local_id_class)

14.18 PACSPATIENT [161](#pacspatient)

14.19 PACSSTUDY [162](#pacsstudy)

14.20 PACSUPDATE [162](#pacsupdate)

14.21 PBCATCOL [162](#pbcatcol)

14.22 PBCATEDT [163](#pbcatedt)

14.23 PBCATFMT [163](#pbcatfmt)

14.24 PBCATTBL [163](#pbcattbl)

14.25 PBCATVLD [164](#pbcatvld)

14.26 STOREUID [164](#storeuid)

14.27 SUBSERVER_VS_DEPT [164](#subserver_vs_dept)

14.28 TSMARCHIVE [164](#tsmarchive)

14.29 EXAM_USER [165](#exam_user)

15\. 检验 [166](#检验)

15.1 检验主记录 LAB_TEST_MASTER [166](#检验主记录-lab_test_master)

15.2 检验项目 LAB_TEST_ITEMS [167](#检验项目-lab_test_items)

15.3 检验结果 LAB_RESULT [168](#检验结果-lab_result)

15.4 检验仪器检验项目配置 INSTRUMENT_CONFIG [168](#检验仪器检验项目配置-instrument_config)

15.5 检验联机仪器字典INSTRUMENT_DICT [169](#检验联机仪器字典instrument_dict)

15.6 检验联机采集数据 ONLINE_DATA （1.0版使用，已过时） [170](#检验联机采集数据-online_data-1.0版使用已过时)

15.7 计算公式字典 FORMULAR_DICT [170](#计算公式字典-formular_dict)

15.8 标注字典 SYMBOL_DICT [170](#标注字典-symbol_dict)

15.9 检验工作量日统计 LAB_DEPT_TEST_DAY （1.0版使用，已过时） [171](#检验工作量日统计-lab_dept_test_day-1.0版使用已过时)

15.10 检验工作量月统计 LAB_DEPT_TEST_MONTH （1.0版使用，已过时） [171](#检验工作量月统计-lab_dept_test_month-1.0版使用已过时)

15.11 临时检验结果 LAB_RESULT_TEMP [171](#临时检验结果-lab_result_temp)

15.12 检验结果描述与结果值对照表 LAB_RESULT_TYPE_VS_VALUES [172](#检验结果描述与结果值对照表-lab_result_type_vs_values)

15.13 质控参数 QUALITY_CON_PARAMETER_LIST（1.0版使用，已过时） [172](#质控参数-quality_con_parameter_list1.0版使用已过时)

15.14 质控数据 QUALITY_CON_LIST（1.0版使用，已过时） [173](#质控数据-quality_con_list1.0版使用已过时)

15.15 审核 EXAM（1.0版使用，已过时） [173](#审核-exam1.0版使用已过时)

15.16 质控标本记录QC_SPECIMENS [173](#质控标本记录qc_specimens)

15.17 质控标本参数QC_SPECIMEN_PARAMETERS [173](#质控标本参数qc_specimen_parameters)

15.18 质控结果QC_SPECIMEN_RESULT [174](#质控结果qc_specimen_result)

16\. 药品管理 [175](#药品管理)

16.1 新药发布NEW_DRUG_MESSAGE(新增) [175](#新药发布new_drug_message新增)

16.2 药品编码停用日志DRUG_STOP_LOG(新增) [175](#药品编码停用日志drug_stop_log新增)

16.3 药品库存定义 DRUG_STORAGE_PROFILE [175](#药品库存定义-drug_storage_profile)

16.4 药品库存 DRUG_STOCK [176](#药品库存-drug_stock)

16.5 盘点表 drug_inventory_check(新增) [177](#盘点表-drug_inventory_check新增)

16.6 药品盘点表DRUG_INVENTORY_BALANCE(徐州二院使用) [177](#药品盘点表drug_inventory_balance徐州二院使用)

16.7 库存盘点货位 DRUG_STOCK_LOCATION(新增) [178](#库存盘点货位-drug_stock_location新增)

16.8 药品入库主记录 DRUG_IMPORT_MASTER [179](#药品入库主记录-drug_import_master)

16.9 药品入库明细记录 DRUG_IMPORT_DETAIL [179](#药品入库明细记录-drug_import_detail)

16.10 药品出库主记录 DRUG_EXPORT_MASTER [181](#药品出库主记录-drug_export_master)

16.11 药品出库明细记录 DRUG_EXPORT_DETAIL [181](#药品出库明细记录-drug_export_detail)

16.12 药品发放申请 DRUG_PROVIDE_APPLICATION [182](#药品发放申请-drug_provide_application)

16.13 药品发放通知 DRUG_PROVIDE_NOTICE [183](#药品发放通知-drug_provide_notice)

16.14 药品结转记录 DRUG_STOCK_BALANCE [183](#药品结转记录-drug_stock_balance)

16.15 采购信息表 buy_drug_plan(新增) [184](#采购信息表-buy_drug_plan新增)

16.16 药品调价记录 drug_price_modify(新增) [185](#药品调价记录-drug_price_modify新增)

16.17 药品调价盈亏表 drug_price_modify_profit(新增) [185](#药品调价盈亏表-drug_price_modify_profit新增)

16.18 药品总账DRUG_LEDGER(新增) [186](#药品总账drug_ledger新增)

16.19 凭证号生成字典VOUCHER_NO_CREATE_DICT(新增) [186](#凭证号生成字典voucher_no_create_dict新增)

16.20 药品库存单位字典 DRUG_STORAGE_DEPT [187](#药品库存单位字典-drug_storage_dept)

16.21 药品库存单位库房字典 DRUG_SUB_STORAGE_DICT [187](#药品库存单位库房字典-drug_sub_storage_dict)

16.22 特殊管理药品目录 MANAGED_DRUG_CATALOG [188](#特殊管理药品目录-managed_drug_catalog)

16.23 特殊管理药品类别字典 MANAGED_DRUG_CLASS_DICT [188](#特殊管理药品类别字典-managed_drug_class_dict)

16.24 药局药品分装记录 DRUG_PACKAGES [188](#药局药品分装记录-drug_packages)

16.25 药品处方主记录 DRUG_PRESC_MASTER [188](#药品处方主记录-drug_presc_master)

16.26 药品处方明细记录 DRUG_PRESC_DETAIL [190](#药品处方明细记录-drug_presc_detail)

16.27 待发药处方主记录 DRUG_PRESC_MASTER_TEMP [191](#待发药处方主记录-drug_presc_master_temp)

16.28 待发药处方明细记录 DRUG_PRESC_DETAIL_TEMP [192](#待发药处方明细记录-drug_presc_detail_temp)

16.29 待发药住院处方主记录DOCT_DRUG_PRESC_MASTER(新增) [193](#待发药住院处方主记录doct_drug_presc_master新增)

16.30 待发药住院处方明细记录DOCT_DRUG_PRESC_DETAIL(新增) [194](#待发药住院处方明细记录doct_drug_presc_detail新增)

16.31 领药单主记录DRUG_APPLICATION_LIST_MASTER(新增) [194](#领药单主记录drug_application_list_master新增)

16.32 领药单明细记录DRUG_APPLICATION_LIST_DETAIL(新增) [195](#领药单明细记录drug_application_list_detail新增)

16.33 摆药记录 DRUG_DISPENSE_REC [195](#摆药记录-drug_dispense_rec)

16.34 摆药请求 DRUG_DISPENSE_REQ [196](#摆药请求-drug_dispense_req)

16.35 预摆药表 DRUG_DISPENSE_PRE [196](#预摆药表-drug_dispense_pre)

16.36 药品摆药分类定义 DRUG_DISPENS_PROPERTY [197](#药品摆药分类定义-drug_dispens_property)

16.37 协定处方主表BINDING_PRESC_MASTER(新增) [198](#协定处方主表binding_presc_master新增)

16.38 协定处方子表BINDING_PRESC_DETAIL(新增) [198](#协定处方子表binding_presc_detail新增)

16.39 用户与协定处方关系表BINDING_PRESC_SELECTION [198](#用户与协定处方关系表binding_presc_selection)

16.40 药品采购记录DRUG_PURCHASE(不使用) [198](#药品采购记录drug_purchase不使用)

16.41 药品采购计划 DRUG_PURCHASE_PLAN(新增) [199](#药品采购计划-drug_purchase_plan新增)

16.42 制剂字典 PREPARATION_DICT [200](#制剂字典-preparation_dict)

16.43 制剂配制规范 PREPARATION_OPERATING_RULE [200](#制剂配制规范-preparation_operating_rule)

16.44 制剂处方 PREPARATION_PRESC [200](#制剂处方-preparation_presc)

16.45 制剂成本 PREPARATION_COST [201](#制剂成本-preparation_cost)

16.46 制剂配制记录 PREPARATION_MASTER [201](#制剂配制记录-preparation_master)

16.47 制剂配制投料记录 PREPARATION_RAW_MATERIAL [201](#制剂配制投料记录-preparation_raw_material)

16.48 制剂配制问题记录 PREPARATION_PROBLEM [202](#制剂配制问题记录-preparation_problem)

16.49 制剂检验记录 PREPARATION_TEST [202](#制剂检验记录-preparation_test)

16.50 制剂价表 PREPARATION_PRICE_LIST [202](#制剂价表-preparation_price_list)

16.51 制剂原料字典 RAW_MATERIAL_DICT(新增) [203](#制剂原料字典-raw_material_dict新增)

16.52 包装材料字典 PACKAGE_MATERIAL_DICT(新增) [203](#包装材料字典-package_material_dict新增)

16.53 制剂处方等级字典 PRESC_STANDARD_DICT(新增) [203](#制剂处方等级字典-presc_standard_dict新增)

16.54 制剂类别等级字典 PRESC_CLASS_DICT(新增) [203](#制剂类别等级字典-presc_class_dict新增)

16.55 制剂用法字典 PREPARATION_ADMIN_DICT [204](#制剂用法字典-preparation_admin_dict)

16.56 制剂成本类别字典 PREPARATION_COST_CLASS_DICT [204](#制剂成本类别字典-preparation_cost_class_dict)

16.57 制剂成本项目字典 PREPARATION_COST_ITEM_DICT [204](#制剂成本项目字典-preparation_cost_item_dict)

16.58 制剂室配置表 PREPARATION_DEPT_DESC [204](#制剂室配置表-preparation_dept_desc)

17\. 门诊收费 [205](#门诊收费)

17.1 门诊医疗收据记录 OUTP_RCPT_MASTER [205](#门诊医疗收据记录-outp_rcpt_master)

17.2 门诊病人支付方式记录 OUTP_PAYMENTS_MONEY [205](#门诊病人支付方式记录-outp_payments_money)

17.3 开单记录 OUTP_ORDER_DESC [206](#开单记录-outp_order_desc)

17.4 门诊病人诊疗费用项目 OUTP_BILL_ITEMS [206](#门诊病人诊疗费用项目-outp_bill_items)

17.5 门诊收费结帐主记录 OUTP_ACCT_MASTER [207](#门诊收费结帐主记录-outp_acct_master)

17.6 门诊收费结帐明细记录 OUTP_ACCT_DETAIL [208](#门诊收费结帐明细记录-outp_acct_detail)

17.7 门诊收费结帐金额分类 OUTP_ACCT_MONEY [208](#门诊收费结帐金额分类-outp_acct_money)

17.8 门诊医疗收据记录备份 OUTP_RCPT_MASTER_BACK [209](#门诊医疗收据记录备份-outp_rcpt_master_back)

17.9 开单记录备份 OUTP_ORDER_DESC_BACK [209](#开单记录备份-outp_order_desc_back)

17.10 门诊病人诊疗费用项目备份 OUTP_BILL_ITEMS_BACK [209](#门诊病人诊疗费用项目备份-outp_bill_items_back)

17.11 门诊病人支付方式记录备份 OUTP_PAYMENTS_MONEY_BACK [210](#门诊病人支付方式记录备份-outp_payments_money_back)

17.12 CHARGE_REDUCE_MASTER(不使用) [210](#charge_reduce_master不使用)

17.13 CHARGE_REDUCE_DETAIL(不使用) [211](#charge_reduce_detail不使用)

17.14 OPERATOR_CHECK_USE(不使用) [211](#operator_check_use不使用)

17.15 门诊病人诊疗费用项目预存OUTP_BILL_ITEMS_TEMP [211](#门诊病人诊疗费用项目预存outp_bill_items_temp)

17.16 开单记录预存OUTP_ORDER_DESC_TEMP [212](#开单记录预存outp_order_desc_temp)

17.17 发票作废记录OUTP_REFUND_INVOICE [212](#发票作废记录outp_refund_invoice)

17.18 RCPT_VS_CHECK(不使用) [212](#rcpt_vs_check不使用)

18\. 住院病人收费 [214](#住院病人收费)

18.1 住院病人费用明细记录 INP_BILL_DETAIL [214](#住院病人费用明细记录-inp_bill_detail)

18.2 调剂帐户表（inpbill.relief_accounts） [215](#调剂帐户表inpbill.relief_accounts)

18.3 待计价病人 NEED_BILLING_PATS(不使用) [216](#待计价病人-need_billing_pats不使用)

18.4 预交金记录 PREPAYMENT_RCPT [216](#预交金记录-prepayment_rcpt)

18.5 住院病人结算主记录 INP_SETTLE_MASTER [217](#住院病人结算主记录-inp_settle_master)

18.6 住院病人结算明细记录 INP_SETTLE_DETAIL [218](#住院病人结算明细记录-inp_settle_detail)

18.7 住院病人支付方式记录 INP_PAYMENTS_MONEY [218](#住院病人支付方式记录-inp_payments_money)

18.8 医嘱划价检查记录 INP_BILL_CHECKED(不使用) [218](#医嘱划价检查记录-inp_bill_checked不使用)

18.9 欠费病人记录 UNSETTLE_REC [219](#欠费病人记录-unsettle_rec)

18.10 住院收费结帐记录 INP_ACCT_MASTER [219](#住院收费结帐记录-inp_acct_master)

18.11 住院收费结帐明细记录 INP_ACCT_DETAIL [220](#住院收费结帐明细记录-inp_acct_detail)

18.12 住院收费结帐金额分类 INP_ACCT_MONEY [220](#住院收费结帐金额分类-inp_acct_money)

18.13 预交金结帐记录 PREPAY_ACCT [220](#预交金结帐记录-prepay_acct)

18.14 预交金结帐金额分类 PREPAY_ACCT_MONEY [221](#预交金结帐金额分类-prepay_acct_money)

18.15 住院病人伙食费明细 INP_DIET_COSTS [221](#住院病人伙食费明细-inp_diet_costs)

18.16 收款员号表 CASHER_NO_REC [222](#收款员号表-casher_no_rec)

18.17 收款员工作日志 CASHER_WORKING_LOG [222](#收款员工作日志-casher_working_log)

18.18 自动计价科室配置 BILL_DEPT_CONFIG [222](#自动计价科室配置-bill_dept_config)

18.19 自动计价杂费项目 BILL_MISC_ITEM [222](#自动计价杂费项目bill_misc_item)

18.20 自动计价杂费特殊项目BILL_MISC_ITEM_PATCH(新增) [222](#自动计价杂费特殊项目bill_misc_item_patch新增)

18.21 病人可透支额INP_OVERDRAFT_REG_MASTER(新增) [223](#病人可透支额inp_overdraft_reg_master新增)

18.22 透支记录明细INP_OVERDRAFT_REG_DETAIL(新增) [223](#透支记录明细inp_overdraft_reg_detail新增)

18.23 养老颐养者生活费用明细记录 LIVE_BILL_DETAIL [223](#养老颐养者生活费用明细记录-live_bill_detail)

18.24 INP_BILL_DETAIL_BACK [225](#inp_bill_detail_back)

19\. 收费帐目 [227](#收费帐目)

19.1 支票根记录 STUB_CHECK_REC [227](#支票根记录-stub_check_rec)

19.2 记帐凭单主记录 TALLY_MASTER(新增) [227](#记帐凭单主记录-tally_master新增)

19.3 记帐凭单明细记录 TALLY_DETAIL [227](#记帐凭单明细记录-tally_detail)

19.4 记帐凭单中支票记录 TALLY_CHECK_REC [228](#记帐凭单中支票记录-tally_check_rec)

19.5 记帐凭单中支票根记录 TALLY_STUB_REC [228](#记帐凭单中支票根记录-tally_stub_rec)

19.6 汇款收据记录 REMIT_REC [228](#汇款收据记录-remit_rec)

19.7 会计科目摘要字典 TALLY_SUMMARY_DICT [228](#会计科目摘要字典-tally_summary_dict)

19.8 收费帐务序号表 ACCT_SNO [229](#收费帐务序号表-acct_sno)

19.9 卫生经济分系统配置表 ECON_DESC [229](#卫生经济分系统配置表-econ_desc)

19.10 科室与记帐部门对照字典 DEPT_VS_CLASS_FOR_ACCT [229](#科室与记帐部门对照字典-dept_vs_class_for_acct)

19.11 （科室）记帐部门字典 DEPT_CLASS_FOR_ACCT_DICT [229](#科室记帐部门字典-dept_class_for_acct_dict)

19.12 生成医疗收支月报表模板 ECON_REPORT_PATTERN [230](#生成医疗收支月报表模板-econ_report_pattern)

19.13 转记账业务分类字典TALLY_CLASS_DICT(新增) [230](#转记账业务分类字典tally_class_dict新增)

19.14 医疗收入转记账业务对照表HIS_SUBJ_VS_ACCT_SUBJ (新增) [230](#医疗收入转记账业务对照表his_subj_vs_acct_subj-新增)

19.15 医疗收入记账记录ACCT_VS_TALLY_REC [231](#医疗收入记账记录acct_vs_tally_rec)

19.16 应收住院医药费记账缓存表INPBILL_ACCT_REC [231](#应收住院医药费记账缓存表inpbill_acct_rec)

19.17 应收医药费核查记录INPBILL_ACCT_CHECK [232](#应收医药费核查记录inpbill_acct_check)

19.18 军队应收辅助账目统计记录表INP_OUTP_COSTS_REC(不使用) [233](#军队应收辅助账目统计记录表inp_outp_costs_rec不使用)

19.19 记账主记录TALLY_MASTER_ACCT [233](#记账主记录tally_master_acct)

19.20 记账明细记录TALLY_DETAIL_ACCT [233](#记账明细记录tally_detail_acct)

19.21 欠费登记表ARREAR_REC [234](#欠费登记表arrear_rec)

19.22 回收明细表RECLAIM_REC [235](#回收明细表reclaim_rec)

19.23 欠费记账主记录ARREAR_TALLY_MASTER(不使用) [235](#欠费记账主记录arrear_tally_master不使用)

19.24 欠费记账明细记录ARREAR_TALLY_DETAIL(不使用) [235](#欠费记账明细记录arrear_tally_detail不使用)

19.25 军队应收辅助项目统计INP_OUTP_FREE_COSTS [235](#军队应收辅助项目统计inp_outp_free_costs)

19.26 报表名称字典REPORT_CODE_DICT [235](#报表名称字典report_code_dict)

19.27 报表对应会计科目字典REPORT_ITEM_DICT [236](#报表对应会计科目字典report_item_dict)

19.28 药品转记账接口表DRUG_MATERIAL_VS_ACCT [236](#药品转记账接口表drug_material_vs_acct)

19.29 DRUG_MATERIAL_TALLY_REC [236](#drug_material_tally_rec)

19.30 发票分配记录INVOICE_MANAGE_REC [237](#发票分配记录invoice_manage_rec)

19.31 欠费回收支付记录RECLAIM_MONEY [237](#欠费回收支付记录reclaim_money)

20\. 医务统计用数据中间库 [238](#医务统计用数据中间库)

20.1 门诊工作量月统计记录 QU_OUTP_CLINIC_NUM [238](#门诊工作量月统计记录-qu_outp_clinic_num)

20.2 急诊工作月统计记录 QU_EMERGENCY_NUM [238](#急诊工作月统计记录-qu_emergency_num)

20.3 住院科室工作效率月统计记录 QU_EFFCIENCY_DEPT [238](#住院科室工作效率月统计记录-qu_effciency_dept)

20.4 住院科室工作效率月统计记录 DEPT_EFFCIENCY [239](#住院科室工作效率月统计记录-dept_effciency)

20.5 科室治疗质量月统计记录 QU_THERAPY_QLTY_DEPT [239](#科室治疗质量月统计记录-qu_therapy_qlty_dept)

20.6 手术科室数质量月统计记录 QU_OPERATION_DEPT [240](#手术科室数质量月统计记录-qu_operation_dept)

20.7 科室医疗管理质量月统计记录 QU_MANAGE_QLTY_DEPT [241](#科室医疗管理质量月统计记录-qu_manage_qlty_dept)

20.8 独立核算科室医疗收入月统计记录 QU_ACCOUNT_INDEP [241](#独立核算科室医疗收入月统计记录-qu_account_indep)

20.9 核算项目医疗收入月统计记录 QU_ACCOUNT_ITEM [241](#核算项目医疗收入月统计记录-qu_account_item)

20.10 特诊检查工作量月统计记录 QU_EXAM_DEPT [242](#特诊检查工作量月统计记录-qu_exam_dept)

20.11 检验工作量月统计记录 QU_TEST_DEPT [242](#检验工作量月统计记录-qu_test_dept)

20.12 辅诊辅疗工作量月统计记录 QU_ASST_TREAT_DEPT [242](#辅诊辅疗工作量月统计记录-qu_asst_treat_dept)

20.13 医院等级评审质量指标完成情况统计记录 QU_QUALITY_COMPLETED [243](#医院等级评审质量指标完成情况统计记录-qu_quality_completed)

20.14 医院医疗工作计划完成情况统计记录 QU_PLAN_COMPLETED [243](#医院医疗工作计划完成情况统计记录-qu_plan_completed)

20.15 门诊综合数据月统计记录 QU_OUTP_SYNTHESIZE [243](#门诊综合数据月统计记录-qu_outp_synthesize)

20.16 住院科室工作负荷月统计记录 QU_LOAD_DEPT [243](#住院科室工作负荷月统计记录-qu_load_dept)

20.17 住院科室床位使用情况月统计记录 QU_DEPT_BED_REC [244](#住院科室床位使用情况月统计记录-qu_dept_bed_rec)

20.18 临床医疗工作计划指标 PLAN_INDEX [244](#临床医疗工作计划指标-plan_index)

20.19 医技科室工作数量计划指标 ASST_PLAN_INDEX [244](#医技科室工作数量计划指标-asst_plan_index)

20.20 科室门诊工作量日统计记录 DEPT_OUTP_NUM_DAY [244](#科室门诊工作量日统计记录-dept_outp_num_day)

20.21 急诊工作日统计记录 EMERGENCY_DAY [245](#急诊工作日统计记录-emergency_day)

20.22 科室伤病员流动日统计记录 DEPT_ADT_DAY [245](#科室伤病员流动日统计记录-dept_adt_day)

20.23 科室伤病员流动日统计记录 DEPT_ADT [246](#科室伤病员流动日统计记录-dept_adt)

20.24 空床日统计记录 DEPT_EMPTY_BED [246](#空床日统计记录-dept_empty_bed)

20.25 特诊检查工作量日统计记录 DEPT_EXAM_DAY [246](#特诊检查工作量日统计记录-dept_exam_day)

20.26 检验工作量日统计记录 DEPT_TEST_DAY [247](#检验工作量日统计记录-dept_test_day)

20.27 辅诊辅疗工作量日统计记录 DEPT_ASST_DAY [247](#辅诊辅疗工作量日统计记录-dept_asst_day)

20.28 住院科室工作负荷日统计记录 DEPT_LOAD_DAY [247](#住院科室工作负荷日统计记录-dept_load_day)

20.29 医疗事故差错记录 ACCIDENT_REC [248](#医疗事故差错记录-accident_rec)

20.30 医疗工作计划名称字典 PLAN_NAME_DICT [248](#医疗工作计划名称字典-plan_name_dict)

20.31 医院等级评审质量指标标准 QUALITY_INDEX_STANDARD [248](#医院等级评审质量指标标准-quality_index_standard)

20.32 住院病人疾病分类统计类目字典 DISE_CLASS_STAT_DICT [248](#住院病人疾病分类统计类目字典-dise_class_stat_dict)

20.33 单病种查询条件字典 DISE_QUERY_CONDITION [249](#单病种查询条件字典-dise_query_condition)

20.34 事故差错类型字典 ACCI_TYPE_DICT [249](#事故差错类型字典-acci_type_dict)

20.35 事故差错等级字典 ACCI_CLASS_DICT [249](#事故差错等级字典-acci_class_dict)

20.36 事故差错原因字典 ACCI_REASON_DICT [249](#事故差错原因字典-acci_reason_dict)

20.37 事故差错后果字典 ACCI_RESULTED_DICT [249](#事故差错后果字典-acci_resulted_dict)

20.38 特殊统计病种字典 SPECIAL_DISE_DICT [249](#特殊统计病种字典-special_dise_dict)

20.39 节假日字典HOLIDAY_DICT [250](#节假日字典holiday_dict)

20.40 STAT_CONFIG [250](#stat_config)

20.41 统计科室字典STAT_DEPT_DICT [250](#统计科室字典stat_dept_dict)

20.42 STAT_DEPT_MODIFYFIX [250](#stat_dept_modifyfix)

20.43 统计条件STAT_OPERCLASS_CONDITION [251](#统计条件stat_operclass_condition)

20.44 统计报表用付费方式STAT_VS_CHARGE_TYPE [251](#统计报表用付费方式stat_vs_charge_type)

20.45 统计报表用费用类别STAT_VS_FEE_CLASS [251](#统计报表用费用类别stat_vs_fee_class)

20.46 [251](#section-1)

公共部分

# 人员属性

## 性别字典 SEX_DICT

|          |               |      |      |                    |
|----------|---------------|------|------|--------------------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明               |
| 序号     | SERIAL_NO     | N    | 1    | 反映性别的排列顺序 |
| 性别代码 | SEX_CODE      | C    | 1    | 可选               |
| 性别名称 | SEX_NAME      | C    | 4    |                    |
| 输入码   | INPUT_CODE    | C    | 8    |                    |
| 五笔码   | INPUT_CODE_WB | C    | 8    |                    |

注释：本系统定义。

## 婚姻状况字典 MARITAL_STATUS_DICT

|              |                     |      |      |                    |
|--------------|---------------------|------|------|--------------------|
| 中文名称     | 字段名              | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO           | N    | 1    | 反映项目的排列顺序 |
| 婚姻状况代码 | MARITAL_STATUS_CODE | C    | 1    | 可选               |
| 婚姻状况名称 | MARITAL_STATUS_NAME | C    | 4    |                    |
| 输入码       | INPUT_CODE          | C    | 8    |                    |

注释：本系统定义。

## 民族字典 NATION_DICT

|          |               |      |      |                    |
|----------|---------------|------|------|--------------------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明               |
| 序号     | SERIAL_NO     | N    | 2    | 反映项目的排列顺序 |
| 民族代码 | NATION_CODE   | C    | 2    | 可选               |
| 民族名称 | NATION_NAME   | C    | 10   |                    |
| 输入码   | INPUT_CODE    | C    | 8    |                    |
| 五笔码   | INPUT_CODE_WB | C    | 8    |                    |

注释：本系统定义。

## 血型字典 BLOOD_TYPE_DICT

|          |                 |      |      |                    |
|----------|-----------------|------|------|--------------------|
| 中文名称 | 字段名          | 类型 | 长度 | 说明               |
| 序号     | SERIAL_NO       | N    | 1    | 反映项目的排列顺序 |
| 血型代码 | BLOOD_TYPE_CODE | C    | 1    | 可选               |
| 血型名称 | BLOOD_TYPE_NAME | C    | 2    |                    |

注释：本系统定义。

## 职业分类字典 OCCUPATION_DICT

|              |                 |      |      |                    |
|--------------|-----------------|------|------|--------------------|
| 中文名称     | 字段名          | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO       | N    | 2    | 反映项目的排列顺序 |
| 职业分类代码 | OCCUPATION_CODE | C    | 2    |                    |
| 职业分类名称 | OCCUPATION_NAME | C    | 20   |                    |
| 输入码       | INPUT_CODE      | C    | 8    |                    |
|              |                 |      |      |                    |
|              |                 |      |      |                    |

注释：本系统定义。

## 身份字典 IDENTITY_DICT

|              |                    |      |      |                                     |
|--------------|--------------------|------|------|-------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                |
| 序号         | SERIAL_NO          | N    | 2    |                                     |
| 身份代码     | IDENTITY_CODE      | C    | 1    | 可选                                |
| 身份名称     | IDENTITY_NAME      | C    | 10   |                                     |
| 输入码       | INPUT_CODE         | C    | 8    |                                     |
| 优先标志     | PRIORITY_INDICATOR | N    | 1    | 0-普通 1-优先表示是否优先就诊和住院 |
| 军人标志     | MILITARY_INDICATOR | N    | 1    | 0-地方 1-军人                       |
| 五笔码       | INPUT_CODE_WB      | C    | 8    |                                     |

注释：用户定义。

主键：序号。

## 军种字典 ARMED_SERVICES_DICT

|          |                     |      |      |                    |
|----------|---------------------|------|------|--------------------|
| 中文名称 | 字段名              | 类型 | 长度 | 说明               |
| 序号     | SERIAL_NO           | N    | 1    | 反映项目的排列顺序 |
| 军种代码 | ARMED_SERVICES_CODE | C    | 1    |                    |
| 军种名称 | ARMED_SERVICES_NAME | C    | 4    |                    |
| 输入码   | INPUT_CODE          | C    | 8    |                    |

注释：本系统定义。

## 勤务字典 DUTY_DICT

|          |            |      |      |                    |
|----------|------------|------|------|--------------------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明               |
| 序号     | SERIAL_NO  | N    | 1    | 反映项目的排列顺序 |
| 勤务代码 | DUTY_CODE  | C    | 1    |                    |
| 勤务名称 | DUTY_NAME  | C    | 4    |                    |
| 输入码   | INPUT_CODE | C    | 8    |                    |

注释：本系统定义。

## 费别字典 CHARGE_TYPE_DICT

|                  |                        |      |      |                                        |
|------------------|------------------------|------|------|----------------------------------------|
| 字段中文名称     | 字段名                 | 类型 | 长度 | 说明                                   |
| 序号             | SERIAL_NO              | N    | 2    |                                        |
| 费别代码         | CHARGE_TYPE_CODE       | C    | 1    | 可选                                   |
| 费别名称         | CHARGE_TYPE_NAME       | C    | 8    |                                        |
| 享受优惠价格标志 | CHARGE_PRICE_INDICATOR | N    | 1    | 0-适用标准价格 1-适用优惠价格 2-外宾价 |
| 五笔码           | INPUT_CODE_WB          | C    | 8    |                                        |

注释：用户定义。

主键：序号。

## 病人来源字典 PATIENT_SOURCE_DICT

|              |                     |      |      |                    |
|--------------|---------------------|------|------|--------------------|
| 中文名称     | 字段名              | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO           | N    | 1    | 反映项目的排列顺序 |
| 病人来源代码 | PATIENT_SOURCE_CODE | C    | 1    |                    |
| 病人来源名称 | PATIENT_SOURCE_NAME | C    | 4    |                    |
| 输入码       | INPUT_CODE          | C    | 8    |                    |

注释：本系统定义。

## 入院方式字典 PATIENT_CLASS_DICT

|              |                    |      |      |                    |
|--------------|--------------------|------|------|--------------------|
| 中文名称     | 字段名             | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO          | N    | 1    | 反映项目的排列顺序 |
| 病人类别代码 | PATIENT_CLASS_CODE | C    | 1    |                    |
| 病人类别名称 | PATIENT_CLASS_NAME | C    | 4    |                    |
| 输入码       | INPUT_CODE         | C    | 8    |                    |

注释：本系统定义。

## 出院方式字典 DISCHARGE_DISPOSITION_DICT

|              |                            |      |      |                    |
|--------------|----------------------------|------|------|--------------------|
| 中文名称     | 字段名                     | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO                  | N    | 1    | 反映项目的排列顺序 |
| 出院方式代码 | DISCHARGE_DISPOSITION_CODE | C    | 1    |                    |
| 出院方式名称 | DISCHARGE_DISPOSITION_NAME | C    | 4    |                    |
| 输入码       | INPUT_CODE                 | C    | 8    |                    |

注释：本系统定义。

## 病情状态字典 PATIENT_STATUS_DICT

|              |                     |      |      |                    |
|--------------|---------------------|------|------|--------------------|
| 中文名称     | 字段名              | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO           | N    | 1    | 反映项目的排列顺序 |
| 病情状态代码 | PATIENT_STATUS_CODE | C    | 1    |                    |
| 病情状态名称 | PATIENT_STATUS_NAME | C    | 4    |                    |
| 输入码       | INPUT_CODE          | C    | 8    |                    |

注释：本系统定义。

## 住院目的字典 ADMISSION_CAUSE_DICT

|              |                      |      |      |                    |
|--------------|----------------------|------|------|--------------------|
| 中文名称     | 字段名               | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO            | N    | 1    | 反映项目的排列顺序 |
| 住院目的代码 | ADMISSION_CAUSE_CODE | C    | 1    |                    |
| 住院目的名称 | ADMISSION_CAUSE_NAME | C    | 8    |                    |
| 输入码       | INPUT_CODE           | C    | 8    |                    |

注释：本系统定义。

## 工作人员字典 STAFF_DICT

|              |               |      |      |                                                                        |
|--------------|---------------|------|------|------------------------------------------------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                                                                   |
| 科室代码     | DEPT_CODE     | C    | 8    | 工作人员所在科室                                                       |
| 姓名         | NAME          | C    | 8    | 工作人员姓名                                                           |
| 输入码       | INPUT_CODE    | C    | 8    | 姓名的输入码                                                           |
| 人员编号     | EMP_NO        | C    | 10   | 每个人分配一个唯一的标识号                                             |
| 工作类别     | JOB           | C    | 8    | 医生、护士、技术员等，本系统定义，见1.18工作类别字典                   |
| 职称         | TITLE         | C    | 10   | 工作人员的职称，如主任医师、主治医师等，本系统定义，见1.17技术职务字典 |
| 本系统用户名 | USER_NAME     | C    | 16   | 如果是本系统用户，则为用户名，否则为空                                 |
| 五笔码       | INPUT_CODE_WB | C    | 8    |                                                                        |
| 工作人员ID   | id            | c    | 4    | 工作人员ID                                                             |
| 密码         | password      | c    | 225  | 密码                                                                   |
| 创建日期     | create_date   | date |      |                                                                        |

注释：此表用于记录工作人员简要情况，被整个系统所使用。

主键：id

索引：本系统用户名

## 用户记录 USERS(修改为试图)

|              |              |      |      |                                                                            |
|--------------|--------------|------|------|----------------------------------------------------------------------------|
| 字段中文名称 | 字段名       | 类型 | 长度 | 说明                                                                       |
| 数据库用户名 | DB_USER      | C    | 16   | 本系统为每个最终用户在数据库管理系统级建立一个用户，用户名在整个系统中唯一 |
| 用户标识     | US_ID        | C    | 4    | 每个用户分配一个唯一标识号                                                 |
| 用户姓名     | USER_NAME    | C    | 8    | 用户姓名                                                                   |
| 用户单位     | USER_DEPT    | C    | 8    | 用户所在科室的代码，由用户定义，见2.6科室字典                              |
| 建立日期     | CREATE_DATE  | D    |      | 建立本用户的日期                                                           |
|              | TIB_ROWGUID  | C    | 32   |                                                                            |
|              | TIB_FLOWGUID | C    | 32   |                                                                            |

注释：此表描述本系统的用户的各种属性，是对数据库本身用户管理的一个补充。本系统通过数据库系统本身的用户管理机制对用户访问数据库进行控制，通过用户名，将这些补充属性与数据库用户关联在一起。本表的记录由本系统设置的用户控制子系统建立和修改。

## 技术职务字典 TITLE_DICT

|              |            |      |      |                    |
|--------------|------------|------|------|--------------------|
| 中文名称     | 字段名     | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO  | N    | 3    | 反映项目的排列顺序 |
| 技术职务代码 | TITLE_CODE | C    | 3    |                    |
| 技术职务名称 | TITLE_NAME | C    | 26   |                    |
| 输入码       | INPUT_CODE | C    | 8    |                    |

注释：本系统定义。

## 工作类别字典 JOB_CLASS_DICT

|              |                |      |      |                    |
|--------------|----------------|------|------|--------------------|
| 中文名称     | 字段名         | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO      | N    | 2    | 反映项目的排列顺序 |
| 工作类别代码 | JOB_CLASS_CODE | C    | 2    |                    |
| 工作类别名称 | JOB_CLASS_NAME | C    | 8    |                    |
| 输入码       | INPUT_CODE     | C    | 8    |                    |

注释：本系统定义。

## 社会关系字典 RELATIONSHIP_DICT

|              |                   |      |      |                    |
|--------------|-------------------|------|------|--------------------|
| 中文名称     | 字段名            | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO         | N    | 2    | 反映项目的排列顺序 |
| 社会关系代码 | RELATIONSHIP_CODE | C    | 2    |                    |
| 社会关系名称 | RELATIONSHIP_NAME | C    | 10   |                    |
| 输入码       | INPUT_CODE        | C    | 8    |                    |

注释：本系统定义。

## 医生职务字典 DOCTOR_TITLE_DICT

|          |            |      |      |                    |
|----------|------------|------|------|--------------------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明               |
| 序号     | SERIAL_NO  | N    | 1    | 反映项目的排列顺序 |
| 职务代码 | TITLE_CODE | C    | 1    | 唯一               |
| 职务名称 | TITLE_NAME | C    | 10   |                    |
| 输入码   | INPUT_CODE | C    | 8    |                    |

注释：本系统定义。

## 入院病情字典 PAT_ADM_CONDITION_DICT

|              |                    |      |      |                    |
|--------------|--------------------|------|------|--------------------|
| 中文名称     | 字段名             | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO          | N    | 1    | 反映项目的排列顺序 |
| 病情状态代码 | PAT_CONDITION_CODE | C    | 1    |                    |
| 病情状态名称 | PAT_CONDITION_NAME | C    | 4    |                    |
| 输入码       | INPUT_CODE         | C    | 8    |                    |

注释：本系统定义。

## 工作组类字典 STAFF_GROUP_CLASS_DICT

|          |             |      |      |                                                                                |
|----------|-------------|------|------|--------------------------------------------------------------------------------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明                                                                           |
| 序号     | SERIAL_NO   | N    | 1    | 反映项目的排列顺序                                                             |
| 组类     | GROUP_CLASS | C    | 16   | 反映分组原则，一个组类下有根据该原则划分的多个组。如病区护士组类、病区医生组类 |

注释：此表定义了系统中设定的组类，系统定义。

主键：组类

## 工作组字典 STAFF_GROUP_DICT

|          |             |      |      |                                                                                                                            |
|----------|-------------|------|------|----------------------------------------------------------------------------------------------------------------------------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明                                                                                                                       |
| 组类     | GROUP_CLASS | C    | 16   | 反映分组原则，一个组类下有根据该原则划分的多个组。如病区护士组类、病区医生组类                                             |
| 组代码   | GROUP_CODE  | C    | 8    | 为每个组分配一个代码，在一个组类内部，组代码唯一；在组类之间，不要求组代码唯一。组代码在应用中，可以对应科室码、护理单元码 |
| 组名     | GROUP_NAME  | C    | 20   | 为每个组分配一个名称。如病区护士组类下的消化科病区组                                                                       |
| 输入码   | INPUT_CODE  | C    | 8    | 每个组对应的输入码                                                                                                         |

注释：一个工作人员物理上只能属于一个行政单位，而不同的应用程序在选取工作人员时，对同一个工作人员的归属有不同的要求。通过组定义了逻辑上的单位，允许一个人属于多个不同的组。组由用户定义。

主键：组类、组代码

## 工作人员分组情况 STAFF_VS_GROUP

|          |             |      |      |                            |
|----------|-------------|------|------|----------------------------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明                       |
| 组类     | GROUP_CLASS | C    | 16   | 为工作组字典中定义的组类   |
| 组代码   | GROUP_CODE  | C    | 8    | 为工作组字典中定义的组代码 |
| 人员编号 | EMP_NO      | C    | 10   | 属于该组的工作人员编号     |

注释：此表定义了工作人员所属于的组。

主键：组类、组代码、人员编号

索引：人员编号

## 费别与身份对照关系 CHARGE_TYPE_VS_IDENTITY

|          |                    |      |      |                              |
|----------|--------------------|------|------|------------------------------|
| 中文名称 | 字段名             | 类型 | 长度 | 说明                         |
| 费别     | CHARGE_TYPE        | C    | 8    | 见1.9费别字典                |
| 身份序号 | IDENTITY_SERIAL_NO | N    | 2    | 反映一种费别所对应的身份排序 |
| 身份     | IDENTITY           | C    | 10   | 见1.6身份字典                |

注释：此表定义病人的费别与身份之间的兼容关系。一种费别可以对应多种身份，多种身份之间由身份序号确定其排列次序。

主键：费别、身份序号

## 医生核算组DOCTOR_GROUP(新增)

|            |                  |      |      |                                      |
|------------|------------------|------|------|--------------------------------------|
| 中文名称   | 字段名           | 类型 | 长度 | 说明                                 |
| 医生代码   | DOCTOR_USER      | C    | 16   |                                      |
| 部门代码   | DEPT_CODE        | C    | 8    |                                      |
| 医生核算组 | ORDER_GROUP      | C    | 8    |                                      |
| 医生名     | DOCTOR           | C    | 8    |                                      |
| 输入码     | INPUT_CODE       | C    | 8    |                                      |
| 上级医生   | SUPER_DOCTOR_ID  | Var  | 16   | 相应的（医师）代码值。，而不是姓名。 |
| 主任医生   | PARENT_DOCTOR_ID | Var  | 16   | 相应的（医师）代码值。，而不是姓名。 |

## 挂号模式字典REGIST_MODE_DICT(新增)

|          |           |      |      |                             |
|----------|-----------|------|------|-----------------------------|
| 中文名称 | 字段名    | 类型 | 长度 | 说明                        |
| 代码     | MODE_CODE | C    | 1    | 例                          |
| 挂号方式 | MODE_NAME | C    | 16   | 例 窗口挂号、预约、网上预约 |

## 分娩结果数据字典BIRTH_RESULT_DICT(新增)

|              |                   |      |      |                      |
|--------------|-------------------|------|------|----------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                 |
| 顺序号       | SERIAL_NO         | N    | 3    | 这个表的主键         |
| 分娩结果代码 | BIRTH_RESULT_CODE | C    | 1    | 代码                 |
| 分娩结果     | BIRTH_RESULT      | C    | 10   | 分娩结果：足月，畸形 |
| 输入法代码   | Input_code        | C    | 15   |                      |

## 分娩方式数据字典BIRTH_TYPE_DICT(新增)

|              |                      |      |      |                              |
|--------------|----------------------|------|------|------------------------------|
| 字段中文名称 | 字段名               | 类型 | 长度 | 说明                         |
| 顺序号       | SERIAL_NO            | N    | 3    | 这个表的主键                 |
| 分娩方式代码 | BIRTH\_ QUOMODO_CODE | C    | 1    | 代码                         |
| 分娩方式     | BIRTH_QUOMODO        | C    | 10   | 分娩方式：剖腹产，顺产，钳产 |
| 输入法代码   | Input_code           | C    | 15   |                              |

## 家庭信息表 FAMILY_DICT

|                |                    |          |          |                                                                |
|----------------|--------------------|----------|----------|----------------------------------------------------------------|
| **字段中文名** | **字段名**         | **类型** | **长度** | **说明**                                                       |
| 病人标识号     | PATIENT_ID         | C        | 10       | 病人唯一标识号，可以由用户赋予具体的含义，如：病案号，门诊号等 |
| 身份           | IDENTITY           | C        | 10       | 与患者间确立的身份关系                                         |
| 姓名           | NAME               | C        | 8        | 病人的亲属姓名                                                 |
| 出生日期       | DATE_OF_BIRTH      | D        |          |                                                                |
| 证件类型       | ID \_TYPE          | C        | 10       |                                                                |
| 证件号码       | ID_NO              | C        | 18       |                                                                |
| 性别           | SEX                | C        | 4        | 男、女、未知，本系统定义，见1.1性别字典                        |
| 工作单位       | BUSINESS_UNIT      | C        | 16       |                                                                |
| 单位地址       | BUSINESS_ADDR      | C        | 40       |                                                                |
| 移动电话       | MOBILE_PHONE       | C        | 16       |                                                                |
| 固定电话       | PHONE              | C        | 16       |                                                                |
| 传真           | FAX                |          | 20       |                                                                |
| 电子信箱       | E_MAIL             | C        | 40       |                                                                |
| 与患者关系     | RELATIONSHIP       | C        | 8        | 夫妻、父子等，使用代码，见1.19社会关系字典                     |
| 信用卡号       | CARD_NO            | C        | 18       |                                                                |
| 信用卡类型     | CARD_TYPE          | C        | 10       |                                                                |
| 保险公司       | INSURANCE\_ AGENCY | C        | 40       |                                                                |

主键：病人标识号,身份

## 简易字典代码 META_DATA

|            |               |      |      |      |
|------------|---------------|------|------|------|
| 字段中文名 | 字段名        | 类型 | 长度 | 说明 |
| 字典名     | TABLE_NAME    | C    | 30   |      |
| 代码       | CodeID        | C    | 20   |      |
| 名称       | CodeName      | C    | 40   |      |
| 备注       | Remark        | C    | 60   |      |
| 拼音码     | Input_code    | C    | 20   |      |
| 五笔码     | Input_code_wb | C    | 20   |      |

主健：TABLE_NAME,CODEID

# 国家、地区、单位及其属性

## 国家及地区字典 COUNTRY_DICT

|          |               |      |      |                    |
|----------|---------------|------|------|--------------------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明               |
| 序号     | SERIAL_NO     | N    | 3    | 反映项目的排列顺序 |
| 国家代码 | COUNTRY_CODE  | C    | 2    |                    |
| 国家简称 | COUNTRY_NAME  | C    | 28   |                    |
| 输入码   | INPUT_CODE    | C    | 8    |                    |
| 五笔码   | INPUT_CODE_WB | V    | 8    |                    |

注释：本系统定义。

## 行政区字典 AREA_DICT

|          |               |      |      |                               |
|----------|---------------|------|------|-------------------------------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明                          |
| 序号     | SERIAL_NO     | N    | 4    | 反映项目的排列顺序            |
| 地区代码 | AREA_CODE     | C    | 6    | 使用层次码，每2位表示一个层次 |
| 地区名称 | AREA_NAME     | C    | 34   |                               |
| 输入码   | INPUT_CODE    | C    | 8    |                               |
| 五笔码   | INPUT_CODE_WB | C    | 8    |                               |

注释：本系统定义。

## 医院基本情况 HOSPITAL_CONFIG

|            |                  |      |      |                                        |
|------------|------------------|------|------|----------------------------------------|
| 中文名称   | 字段名           | 类型 | 长度 | 说明                                   |
| 医院名称   | HOSPITAL         | C    | 40   | 医院全称，不为空                       |
| 系统授权码 | AUTHORIZED_KEY   | C    | 8    | 根据医院名称按照加密算法计算得到的密码 |
| 医院代码   | UNIT_CODE        | C    | 11   | 为国家或军队单位编码                   |
| 地理位置   | LOCATION         | C    | 6    | 为国家行政区划编码，见2.2行政区字典    |
| 通信地址   | MAILING_ADDRESS  | C    | 80   |                                        |
| 邮政编码   | ZIP_CODE         | C    | 6    |                                        |
| 编制床位数 | APPROVED_BED_NUM | N    | 4    |                                        |
| 验证码     | VERIFY_KEY       | C    | 10   |                                        |

注释：此表用于医院信息系统的配置。每个系统只有一行，由系统安装时生成。由各个应用程序在用户登录时校验用户合法性以及提取医院名称等时使用。

## 合同单位记录 UNIT_IN_CONTRACT

|              |                      |      |      |                                                  |
|--------------|----------------------|------|------|--------------------------------------------------|
| 字段中文名称 | 字段名               | 类型 | 长度 | 说明                                             |
| 合同单位代码 | UNIT_CODE            | C    | 11   | 合同单位唯一标识，非空，由用户定义               |
| 合同单位名称 | UNIT_NAME            | C    | 40   |                                                  |
| 输入码       | INPUT_CODE           | C    | 8    |                                                  |
| 单位地址     | ADDRESS              | C    | 40   |                                                  |
| 单位性质     | UNIT_TYPE            | C    | 1    | 使用代码，用户定义，见2.9单位性质字典            |
| 隶属单位     | SUBORDINATE_TO       | C    | 11   | 为进行统计而划分的隶属关系，使用代码，由用户定义 |
| 就医距离     | DISTANCE_TO_HOSPITAL | N    | 4,1  | 以公里为单位，说明合同单位与本医院的距离         |
| 在编人数     | REGULAR_NUM          | N    | 4    |                                                  |
| 非编人数     | TEMP_NUM             | N    | 4    |                                                  |
| 离退休人数   | RETIRED_NUM          | N    | 4    |                                                  |
| 五笔码       | INPUT_CODE_WB        | C    | 8    |                                                  |

说明：此表反映本医院医疗保障对象的简要情况，在本院用于医疗工作统计，对上级统计部门提供本院的保障任务数据。本表在系统开始运行时由门诊业务管理子系统录入。

主键：合同单位代码。

## 合同单位人员分类情况 STAFF_IN_CONTRACT

|              |           |      |      |                                         |
|--------------|-----------|------|------|-----------------------------------------|
| 字段中文名称 | 字段名    | 类型 | 长度 | 说明                                    |
| 合同单位代码 | UNIT_CODE | C    | 11   | 由合同单位记录定义的单位代码            |
| 身份         | IDENTITY  | C    | 10   | 使用规范名称，由用户定义，见1.6身份字典 |
| 人数         | STAFF_NUM | N    | 4    | 对应该身份的人数                        |

注释：此表反映合同单位各类人员按身份分布情况，用于统计。本表在系统开始运行时由门诊业务管理子系统录入。

主键：合同单位代码、身份。

## 科室字典 DEPT_DICT

|                  |                     |      |      |                                                                                    |
|------------------|---------------------|------|------|------------------------------------------------------------------------------------|
| 字段中文名称     | 字段名              | 类型 | 长度 | 说明                                                                               |
| 序号             | SERIAL_NO           | N    | 3    | 此序号反映了科室的排列顺序                                                         |
| 科室代码         | DEPT_CODE           | C    | 8    | 使用层次代码，由用户定义                                                           |
| 科室名称         | DEPT_NAME           | C    | 20   | 科室的正式名称                                                                     |
| 科室简称或别名   | DEPT_ALIAS          | C    | 20   |                                                                                    |
| 临床科室属性     | CLINIC_ATTR         | N    | 1    | 描述本科室属于临床、辅诊、护理单元、机关、其他，本系统定义，见2.10科室临床属性字典 |
| 门诊住院科室标志 | OUTP_OR_INP         | N    | 1    | 描述本科室属于门诊或住院科室，本系统定义，见2.11科室门诊住院属性字典               |
| 内外科标志       | INTERNAL_OR_SERGERY | N    | 1    | 如果是临床科室，则区分内外科，本系统定义，见2.12科室内外科属性字典                 |
| 输入码           | INPUT_CODE          | C    | 8    |                                                                                    |
| 部门详细说明     | POSITION            | C    | 40   |                                                                                    |
|                  | SIGN                | C    | 1    |                                                                                    |
| 五笔码           | INPUT_CODE_WB       | C    | 8    |                                                                                    |
| 摆药累积属性     | DISPENSing_cumulate | N    | 1    | 是否参与摆药累积:0-否 1-是                                                         |
| 虚拟药柜         | Virtual_cabinet     | N    | 1    | 是否参与虚拟药柜管理:0-否 1-是                                                     |

注释：此表描述全医院各科室的配置及其属性，由系统管理程序负责维护。各系统使用。

## 临床科室配置情况 CLINICAL_DEPT_CONFIG

|              |                      |      |      |                        |
|--------------|----------------------|------|------|------------------------|
| 字段中文名称 | 字段名               | 类型 | 长度 | 说明                   |
| 科室代码     | DEPT_CODE            | C    | 8    | 最小统计单位的临床科室 |
| 床位数       | BED_NUMBER           | N    | 4    |                        |
| 主任医师数   | CHIEF_PHYSICIAN_NUM  | N    | 2    |                        |
| 主治医师数   | ATTENDING_DOCTOR_NUM | N    | 2    |                        |
| 住院医师数   | RESIDENT_NUM         | N    | 2    |                        |
| 护士数       | NURSE_NUM            | N    | 2    |                        |

注释：此表用于生成医疗效率指标。所指科室为最小统计单位的临床科室，它不同于病房，可以是一个病房中的一部分。该表不包含非最小统计单位的临床科室。

## 临床科室与病房（区）对照 DEPT_VS_WARD

|              |           |      |      |                        |
|--------------|-----------|------|------|------------------------|
| 字段中文名称 | 字段名    | 类型 | 长度 | 说明                   |
| 科室代码     | DEPT_CODE | C    | 8    | 最小统计单位的临床科室 |
| 病房代码     | WARD_CODE | C    | 8    |                        |

注释：一个病房为一个护理单元，科室是行政和统计单位。一个病房可以包含多个科室。

## 单位性质字典 UNIT_TYPE_DICT

|              |                |      |      |                    |
|--------------|----------------|------|------|--------------------|
| 中文名称     | 字段名         | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO      | N    | 1    | 反映项目的排列顺序 |
| 单位性质代码 | UNIT_TYPE_CODE | C    | 1    |                    |
| 单位性质名称 | UNIT_TYPE_NAME | C    | 16   |                    |
| 输入码       | INPUT_CODE     | C    | 8    |                    |

注释：此表用于描述合同单位的性质，如野战部队、机关、院校等。用户定义。

## 科室临床属性字典 DEPT_CLINIC_ATTR_DICT

|              |                  |      |      |                    |
|--------------|------------------|------|------|--------------------|
| 中文名称     | 字段名           | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO        | N    | 1    | 反映项目的排列顺序 |
| 临床属性代码 | CLINIC_ATTR_CODE | N    | 1    |                    |
| 临床属性名称 | CLINIC_ATTR_NAME | C    | 8    |                    |
| 输入码       | INPUT_CODE       | C    | 8    |                    |

注释：本系统定义。

## 科室门诊住院属性字典 DEPT_OI_ATTR_DICT

|                  |              |      |      |                    |
|------------------|--------------|------|------|--------------------|
| 中文名称         | 字段名       | 类型 | 长度 | 说明               |
| 序号             | SERIAL_NO    | N    | 1    | 反映项目的排列顺序 |
| 门诊住院属性代码 | OI_ATTR_CODE | N    | 1    |                    |
| 门诊住院属性名称 | OI_ATTR_NAME | C    | 8    |                    |
| 输入码           | INPUT_CODE   | C    | 8    |                    |

注释：本系统定义。

## 科室内外科属性字典 DEPT_IS_ATTR_DICT

|                |              |      |      |                    |
|----------------|--------------|------|------|--------------------|
| 中文名称       | 字段名       | 类型 | 长度 | 说明               |
| 序号           | SERIAL_NO    | N    | 1    | 反映项目的排列顺序 |
| 内外科属性代码 | IS_ATTR_CODE | N    | 1    |                    |
| 内外科属性名称 | IS_ATTR_NAME | C    | 8    |                    |
| 输入码         | INPUT_CODE   | C    | 8    |                    |

注释：本系统定义。

## 营养室字典 DIET_PROVIDER_DICT

|            |              |      |      |      |
|------------|--------------|------|------|------|
| 中文名称   | 字段名       | 类型 | 长度 | 说明 |
| 营养室代码 | SECTION_CODE | C    | 1    |      |
| 营养室名称 | SECTION_NAME | C    | 16   |      |

注释：用户定义。

## ADDRESS_detailed_DICT 详细地址字典

|              |                       |      |      |      |
|--------------|-----------------------|------|------|------|
| 中文名称     | 字段名                | 类型 | 长度 | 说明 |
| 序号         | serial_no             | Var2 | 20   |      |
| 详细地址代码 | Detailed_address_CODE | Var2 | 20   |      |
| 详细地址名称 | Detailed_address_NAME | Var2 | 50   |      |
| 拼音码       | INPUT_CODE            | Var2 | 25   |      |
| 五笔码       | INPUT_CODE_WB         | Var2 | 25   |      |

## 大单位字典 TOP_UNIT_DICT

|            |               |      |      |                  |
|------------|---------------|------|------|------------------|
| 中文名称   | 字段名        | 类型 | 长度 | 说明             |
| 序号       | SERIAL_NO     | N    | 1    | 反映单位排列顺序 |
| 大单位代码 | TOP_UNIT_CODE | C    | 1    |                  |
| 大单位名称 | TOP_UNIT_NAME | C    | 16   |                  |

注释：用户定义。

#  医疗工作

## 门诊专科字典 SPECIAL_CLINIC_DICT

|          |                     |      |      |                    |
|----------|---------------------|------|------|--------------------|
| 中文名称 | 字段名              | 类型 | 长度 | 说明               |
| 序号     | SERIAL_NO           | N    | 2    | 反映项目的排列顺序 |
| 专科代码 | SPECIAL_CLINIC_CODE | C    | 2    |                    |
| 专科名称 | SPECIAL_CLIINC_NAME | C    | 16   |                    |
| 输入码   | INPUT_CODE          | C    | 8    |                    |

注释：专科指专门诊治某类疾病的专科。用户定义。

## 检查号类别字典 LOCAL_ID_CLASS_DICT

|                |                     |      |      |                    |
|----------------|---------------------|------|------|--------------------|
| 中文名称       | 字段名              | 类型 | 长度 | 说明               |
| 序号           | SERIAL_NO           | N    | 2    | 反映项目的排列顺序 |
| 检查号类别代码 | LOCAL_ID_CLASS_CODE | C    | 1    |                    |
| 检查号类别名称 | LOCAL_ID_CLASS_NAME | C    | 6    |                    |
| 输入码         | INPUT_CODE          | C    | 8    |                    |

注释：允许一所医院存在多种特定的检查（病案）号，本表反映所有存在的需要管理的这种局部病案。用户定义。

## 检查类别字典 EXAM_CLASS_DICT

|                  |                  |      |      |                                  |
|------------------|------------------|------|------|----------------------------------|
| 中文名称         | 字段名           | 类型 | 长度 | 说明                             |
| 序号             | SERIAL_NO        | N    | 2    | 反映项目的排列顺序               |
| 检查类别代码     | EXAM_CLASS_CODE  | C    | 1    |                                  |
| 检查类别名称     | EXAM_CLASS_NAME  | C    | 6    |                                  |
| 输入码           | INPUT_CODE       | C    | 8    |                                  |
| 检查部门代码     | PERFORM_BY       | C    | 10   | 填写后选择检验项目后自动填写部门 |
| 打印单样式       | PRINT_STYLE      | C    | 6    | 样式单代码为ＣＴ、放射、病理等   |
| 是否按样式单打印 | SPECIALTIES_DEPT | N    | 1    | 1：按样式单打印                  |
|                  | LOACAL_ID_CLASS  | C    | 5    |                                  |

注释：用户定义。

## 检查子类字典 EXAM_SUBCLASS_DICT

|              |                    |      |      |                    |
|--------------|--------------------|------|------|--------------------|
| 中文名称     | 字段名             | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO          | N    | 2    | 反映项目的排列顺序 |
| 检查类别名称 | EXAM_CLASS_NAME    | C    | 6    |                    |
| 检查子类名称 | EXAM_SUBCLASS_NAME | C    | 8    |                    |
| 输入码       | INPUT_CODE         | C    | 8    |                    |

注释：用户定义。

## 号类字典CLINIC_TYPE_DICT

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 27%" />
<col style="width: 11%" />
<col style="width: 10%" />
<col style="width: 30%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>序号</td>
<td>SERIAL_NO</td>
<td>N</td>
<td>2</td>
<td>反映排列顺序</td>
</tr>
<tr class="odd">
<td>号类</td>
<td>CLINIC_TYPE</td>
<td>C</td>
<td>8</td>
<td>唯一标识门诊的挂号费等级</td>
</tr>
<tr class="even">
<td>挂号费</td>
<td>PRICE</td>
<td>N</td>
<td>5,2</td>
<td></td>
</tr>
<tr class="odd">
<td>号类名称</td>
<td>CLINIC_TYPE_NAME</td>
<td>VARCHAR2</td>
<td>20</td>
<td></td>
</tr>
<tr class="even">
<td>号类代码</td>
<td>CLINIC_TYPE_CODE</td>
<td>VARCHAR2</td>
<td>10</td>
<td></td>
</tr>
<tr class="odd">
<td>收费项目</td>
<td>CHARGE_ITEM</td>
<td>VARCHAR2</td>
<td>20</td>
<td><p>挂号费</p>
<p>诊疗费</p>
<p>其它费</p></td>
</tr>
<tr class="even">
<td>价表项目</td>
<td>PRICE_ITEM</td>
<td>VARCHAR2</td>
<td>20</td>
<td></td>
</tr>
</tbody>
</table>

注释：此表定义了门诊挂号的收费种类，用户定义。

主键：号类。

## 号类设置表 CLINIC_TYPE_SETTING

|              |                 |          |      |      |
|--------------|-----------------|----------|------|------|
| 字段中文名称 | 字段名          | 类型     | 长度 | 说明 |
| 号类         | CLINIC_TYPE     | VARCHAR2 | 8    |      |
| 就诊类别     | REGIST_TYPE     | VAR2     | 8    |      |
| 费用类别     | CHARGE_ITEM     | VARCHAR2 | 20   |      |
| 计算类型     | CALCULATE_TYPE  | VARCHAR2 | 1    |      |
| 计算值       | CALCULATE_VALUE | N        | 4,2  |      |
| 价表项目     | PRICE_ITEM      | VARCHAR2 | 20   |      |

主键：CLINIC_TYPE, REGIST_TYPE, CHARGE_ITEM

医嘱类别字典ORDER_CLASS_DICT

|              |           |                  |      |      |      |
|--------------|-----------|------------------|------|------|------|
| 字段中文名称 |           | 字段名           | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO |                  | N    | 2    |      |
| 医嘱类别代码 |           | ORDER_CLASS_CODE | C    | 1    | 唯一 |
| 医嘱类别名称 |           | ORDER_CLASS_NAME | C    | 8    |      |
| 输入码       |           | INPUT_CODE       | C    | 8    |      |

注释：此表反映了从临床角度对医嘱的分类，用于医嘱录入及执行单的生成。本系统定义。

## 检查结果状态字典EXAM_RESULT_STATUS_DICT

|                  |                         |      |      |      |
|------------------|-------------------------|------|------|------|
| 字段中文名称     | 字段名                  | 类型 | 长度 | 说明 |
| 序号             | SERIAL_NO               | N    | 1    |      |
| 检查结果状态代码 | EXAM_RESULT_STATUS_CODE | C    | 1    |      |
| 检查结果状态名称 | EXAM_RESULT_STATUS_NAME | C    | 8    |      |
| 输入码           | INPUT_CODE              | C    | 8    |      |

注释：此表定义了检查检验申请从申请到出报告过程经历的各个状态。本系统定义。

## 病人状态变化字典 PATIENT_STATUS_CHG_DICT

|                  |                         |      |      |      |
|------------------|-------------------------|------|------|------|
| 字段中文名称     | 字段名                  | 类型 | 长度 | 说明 |
| 序号             | SERIAL_NO               | N    | 2    |      |
| 病人状态变化代码 | PATIENT_STATUS_CHG_CODE | C    | 1    |      |
| 病人状态变化名称 | PATIENT_STATUS_CHG_NAME | C    | 8    |      |
| 输入码           | INPUT_CODE              | C    | 8    |      |

注释：本表定义了需要记录的病人入出转及病情状态，本系统定义。

## 时间段字典 TIME_INTERVAL_DICT

|              |                    |      |      |      |
|--------------|--------------------|------|------|------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO          | N    | 1    |      |
| 时间段代码   | TIME_INTERVAL_CODE | C    | 1    |      |
| 时间段名称   | TIME_INTERVAL_NAME | C    | 4    |      |
| 输入码       | INPUT_CODE         | C    | 8    |      |

注释：本系统定义。

## 病案质量字典 MR_QUALITY_DICT

|              |                 |      |      |      |     |
|--------------|-----------------|------|------|------|-----|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明 |     |
| 序号         | SERIAL_NO       | N    | 1    |      |     |
| 病案质量代码 | MR_QUALITY_CODE | C    | 1    |      |     |
| 病案质量名称 | MR_QUALITY_NAME | C    | 2    |      |     |
| 输入码       | INPUT_CODE      | C    | 8    |      |     |

注释：本系统定义。

## 病案价值字典 MR_VALUE_DICT

|              |               |      |      |      |
|--------------|---------------|------|------|------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO     | N    | 1    |      |
| 病案价值代码 | MR_VALUE_CODE | C    | 1    |      |
| 病案价值名称 | MR_VALUE_NAME | C    | 4    |      |
| 输入码       | INPUT_CODE    | C    | 8    |      |

注释：本系统定义。

## 病案状态字典 MR_STATUS_DICT

|              |                |      |      |      |
|--------------|----------------|------|------|------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO      | N    | 1    |      |
| 病案状态代码 | MR_STATUS_CODE | C    | 1    |      |
| 病案状态名称 | MR_STATUS_NAME | C    | 4    |      |
| 输入码       | INPUT_CODE     | C    | 8    |      |

注释：本系统定义。

## 病案类别字典 MR_CLASS_DICT

|              |               |      |      |                                                  |
|--------------|---------------|------|------|--------------------------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                                             |
| 序号         | SERIAL_NO     | N    | 1    | 反映项目排列顺序                                 |
| 类别代码     | MR_CLASS_CODE | C    | 1    |                                                  |
| 类别名称     | MR_CLASS_NAME | C    | 8    |                                                  |
| 病案号名称   | MR_NO_NAME    | C    | 16   | 用于描述该类病案号的专用名，如：门诊号、住院号等 |
| 输入码       | INPUT_CODE    | C    | 8    |                                                  |

注释：此表用于定义病案类别，如：门诊病历、住院病历、X光片、CT片等等。

主键：类别代码。

## 病案复印登记表

|            |               |      |      |                                                                                  |
|------------|---------------|------|------|----------------------------------------------------------------------------------|
| 中文名称   | 字段名        | 类型 | 长度 | 说明                                                                             |
| 病案类别   | Mr_class      | C    | 20   |                                                                                  |
| 病案号     | Mr_no         | C    | 20   |                                                                                  |
| 复印对象   | Copy_object   | C    | 1    | 1-医生 2-病人                                                                    |
| 复印内容   | Copy_content  | C    | 200  |                                                                                  |
| 复印科室   | Copy_dept     | C    | 8    | 复印对象是医生得时候，该字段为医生所在的科室；复印对象是病人得时候，该字段为空。 |
| 复印人     | Copy_man      | C    | 20   | 医生或病人的姓名                                                                 |
| 复印份数   | Copy_share    | N    | 5    |                                                                                  |
| 复印原因   | Copy_reason   | C    | 200  | 文字描述原因                                                                     |
| 复印时间   | Copy_date     | D    |      |                                                                                  |
| 复印经手人 | Copy_released | C    | 20   |                                                                                  |

primary key (mr_class,mr_no,copy_date)

## 床位状态字典 BED_STATUS_DICT

|              |                 |      |      |                    |
|--------------|-----------------|------|------|--------------------|
| 中文名称     | 字段名          | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO       | N    | 1    | 反映项目的排列顺序 |
| 床位状态代码 | BED_STATUS_CODE | C    | 1    |                    |
| 床位状态名称 | BED_STATUS_NAME | C    | 6    |                    |
| 输入码       | INPUT_CODE      | C    | 8    |                    |

注释：本系统定义。

## 床位类型字典 BED_TYPE_DICT

|              |               |      |      |                    |
|--------------|---------------|------|------|--------------------|
| 中文名称     | 字段名        | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO     | N    | 1    | 反映项目的排列顺序 |
| 床位类型代码 | BED_TYPE_CODE | C    | 1    |                    |
| 床位类型名称 | BED_TYPE_NAME | C    | 6    |                    |
| 输入码       | INPUT_CODE    | C    | 8    |                    |

注释：此表定义床位的男女床属性，本系统定义

## 床位等级字典 BED_CLASS_DICT

|              |                |      |      |                    |
|--------------|----------------|------|------|--------------------|
| 中文名称     | 字段名         | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO      | N    | 1    | 反映项目的排列顺序 |
| 床位等级代码 | BED_CLASS_CODE | C    | 2    |                    |
| 床位等级名称 | BED_CLASS_NAME | C    | 10   |                    |
| 输入码       | INPUT_CODE     | C    | 8    |                    |

注释：用户定义。

## 床位编制类型字典 BED_APPROVED_TYPE_DICT

|                  |                        |      |      |                    |
|------------------|------------------------|------|------|--------------------|
| 中文名称         | 字段名                 | 类型 | 长度 | 说明               |
| 序号             | SERIAL_NO              | N    | 1    | 反映项目的排列顺序 |
| 床位编制类型代码 | BED_APPROVED_TYPE_CODE | C    | 1    |                    |
| 床位编制类型名称 | BED_APPROVED_TYPE_NAME | C    | 4    |                    |
| 输入码           | INPUT_CODE             | C    | 8    |                    |

注释：本系统定义。

## 病案内容分类字典 MR_COMP_CLASS_DICT

|              |            |      |      |      |
|--------------|------------|------|------|------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO  | N    | 1    |      |
| 类别代码     | COMP_CLASS | C    | 1    |      |
| 类别名称     | COMP_NAME  | C    | 8    |      |
| 输入码       | INPUT_CODE | C    | 8    |      |

注释：此表用于定义病案中信息内容类别，如：首页、医嘱、病程等等。

主键：类别代码

## 空调类型字典AIRCONDITION_CLASS_DICT(新增)

|              |                         |      |      |      |
|--------------|-------------------------|------|------|------|
| 中文名称     | 字段名                  | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO               | N    | 2    |      |
| 空调类型代码 | AIRCONDITION_CLASS_CODE | C    | 20   |      |
| 空调类型名称 | AIRCONDITION_CLASS_NAME | C    | 100  |      |
| 输入码       | INPUT_CODE              | C    | 8    |      |

## 床位与空调类型对照表BED_VS_AIRCONDITION(新增)

|              |                         |      |      |      |
|--------------|-------------------------|------|------|------|
| 中文名称     | 字段名                  | 类型 | 长度 | 说明 |
| 床位类型代码 | BED_CLASS_CODE          | C    | 20   |      |
| 空调类型代码 | AIRCONDITION_CLASS_CODE | C    | 20   |      |

## 医生说明字典DOCTOR_EXPLAIN_DICT(新增)

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
| 部门代码 | DEPT_CODE     | C    | 8    |      |
| 说明     | EXPLAIN_TEXT  | C    | 80   |      |
| 输入码   | INPUT_CODE    | C    | 8    |      |
| 录入用户 | ENTERED_USER  | C    | 16   |      |
| 录入日期 | ENTERED_DATE  | D    |      |      |
| 五笔码   | INPUT_CODE_WB | C    | 8    |      |

## DEPT_CODE_VS_FACTID(新增)

|          |             |      |      |      |
|----------|-------------|------|------|------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明 |
|          | DEPT_CODE   | C    | 8    |      |
|          | DEPT_FACTID | N    | 4    |      |

## 护理类型字典NURSE_TEMPERATURE_CLASS_DICT(新增)

|              |            |      |      |      |
|--------------|------------|------|------|------|
| 中文名称     | 字段名     | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO  | N    | 1    |      |
| 护理类型代码 | CLASS_CODE | C    | 1    |      |
| 护理类型名称 | CLASS_NAME | C    | 50   |      |

## 护理项目字典NURSE_TEMPERATURE_ITEM_DICT(新增)

|              |             |          |      |      |
|--------------|-------------|----------|------|------|
| 中文名称     | 字段名      | 类型     | 长度 | 说明 |
| 护理类型代码 | CLASS_CODE  | C        | 1    |      |
| 护理项目代码 | VITAL_CODE  | C        | 4    |      |
| 护理项目     | VITAL_SIGNS | C        | 16   |      |
| 单位         | UNIT        | C        | 8    |      |
| 科室代码     | DEPT_CODE   | varchar2 | 8    |      |

主键： class_code,vital_code,dept_code

## <span class="smallcaps">诊室字典</span>ROOM_DICT(不使用)

|          |             |      |      |      |
|----------|-------------|------|------|------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明 |
|          | ROOM_CODE   | C    | 8    |      |
|          | ROOM_NAME   | C    | 40   |      |
|          | DEPT_CODE   | C    | 8    |      |
|          | ROOM_TYPE   | N    | 1    |      |
|          | SIMPLE_NAME | C    | 8    |      |

#  疾病诊断与医疗操作

## 疾病字典 DIAGNOSIS_DICT

|              |                    |      |      |                                                         |
|--------------|--------------------|------|------|---------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                                    |
| 诊断代码     | DIAGNOSIS_CODE     | C    | 16   | 非空，使用ICD9，用户定义                                |
| 诊断名称     | DIAGNOSIS_NAME     | C    | 100  | 非空                                                    |
| 正名标志     | STD_INDICATOR      | N    | 1    | 1-正名 0-别名，每种疾病即每个诊断代码有且只能有一个正名 |
| 标准化标志   | APPROVED_INDICATOR | N    | 1    | 1-已标准化 0-临时项目                                   |
| 创建日期     | CREATE_DATE        | D    | 7    | 创建该诊断的日期                                        |
| 输入码       | INPUT_CODE         | C    | 8    | 推荐使用拼音词头                                        |
|              | HEALTH_LEVEL       | C    | 2    |                                                         |
|              | INFECT_INDICATOR   | N    | 1    |                                                         |
| 五笔码       | INPUT_CODE_WB      | C    | 8    |                                                         |
| 诊断类别     | DIAGNOSIS_DICT     | N    | 1    |                                                         |
| 内码1        | nm1                | Var2 | 6    |                                                         |
| 内码2        | Nm2                | Var2 | 2    |                                                         |

注释：此表定义了疾病分类编码及其对应的疾病名称，为全系统所用。用户定义，由病案编目子系统负责维护。长期在线保存。

主键：诊断名称

索引：诊断代码

## 手术操作字典 OPERATION_DICT

|              |                    |      |      |                                                         |
|--------------|--------------------|------|------|---------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                                    |
| 手术操作代码 | OPERATION_CODE     | C    | 8    | 非空，使用ICD9CM，用户定义                              |
| 手术操作名称 | OPERATION_NAME     | C    | 40   | 非空                                                    |
| 手术等级     | OPERATION_SCALE    | C    | 2    | 使用规范名称，见4.16手术等级字典                        |
| 正名标志     | STD_INDICATOR      | N    | 1    | 1-正名 0-别名，每种手术即每个手术代码有且只能有一个正名 |
| 标准化标志   | APPROVED_INDICATOR | N    | 1    | 1-已标准化 0-临时项目                                   |
| 创建日期     | CREATE_DATE        | D    | 7    | 创建该诊断的日期                                        |
| 输入码       | INPUT_CODE         | C    | 8    | 推荐使用拼音词头                                        |
| 五笔码       | INPUT_CODE_WB      | C    | 8    |                                                         |
| 内码2        | nm2                | Var2 | 2    |                                                         |

注释：此表手术分类代码及其对应的手术名称，为全系统所用。用户定义，由病案编目子系统负责维护。

主键：手术操作名称

索引：手术操作代码

## 检查诊断字典 EXAM_DIAG_DICT

|          |                |      |      |                                                                                                       |
|----------|----------------|------|------|-------------------------------------------------------------------------------------------------------|
| 中文名称 | 字段名         | 类型 | 长度 | 说明                                                                                                  |
| 检查类别 | EXAM_CLASS     | C    | 6    | 区分检验、各类检查，使用代码，非空，取值：超声,CT,MRI,放射,病理,心电图，本系统定义，见3.3检查类别字典 |
| 检查子类 | EXAM_SUB_CLASS | C    | 8    | 区分一种检查类下的各子类，如超声类下的腹部、心脏、妇产等子类，可为空，本系统定义，见3.4检查子类字典   |
| 诊断名称 | DIAG_NAME      | C    | 40   |                                                                                                       |
| 诊断代码 | DIAG_CODE      | C    | 8    |                                                                                                       |
| 输入码   | INPUT_CODE     | C    | 8    | 推荐使用拼音词头                                                                                      |

注释：检查诊断用语不同于入出院诊断，故此设置此表。用户定义。

## 中医诊断关系表 CDIAG_ITEM_DICT

|              |             |      |      |      |
|--------------|-------------|------|------|------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明 |
| 诊断代码     | CDIAG_CODE  | Var  | 16   |      |
| 症形         | SYMPTOM     | Var  | 50   |      |
| 治则         | DISPOSITION | Var  | 50   |      |

Primary:CDIAG_CODE, SYMPTOM

## 诊断类别字典 DIAGNOSIS_TYPE_DICT

|              |                     |      |      |      |
|--------------|---------------------|------|------|------|
| 字段中文名称 | 字段名              | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO           | N    | 1    |      |
| 诊断类别代码 | DIAGNOSIS_TYPE_CODE | C    | 1    |      |
| 诊断类别名称 | DIAGNOSIS_TYPE_NAME | C    | 20   |      |
| 输入码       | INPUT_CODE          | C    | 8    |      |

注释：本系统定义。

## 诊断对照组字典 DIAG_COMP_GROUP_DICT

|                |                      |      |      |      |
|----------------|----------------------|------|------|------|
| 字段中文名称   | 字段名               | 类型 | 长度 | 说明 |
| 序号           | SERIAL_NO            | N    | 1    |      |
| 诊断对照组代码 | DIAG_COMP_GROUP_CODE | C    | 1    |      |
| 诊断对照组名称 | DIAG_COMP_GROUP_NAME | C    | 32   |      |
| 输入码         | INPUT_CODE           | C    | 8    |      |

注释：本表定义了病案首页中需要填写的各种诊断对照组，由编目子系统使用。本系统定义。

## 临床诊疗项目字典 CLINIC_ITEM_DICT

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 30%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 35%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>项目分类</td>
<td>ITEM_CLASS</td>
<td>C</td>
<td>1</td>
<td>如药品、检查、检验、治疗、护理等。见4.34诊疗项目分类字典。</td>
</tr>
<tr class="odd">
<td>项目代码</td>
<td>ITEM_CODE</td>
<td>C</td>
<td>20</td>
<td>该代码是从临床角度对诊疗项目分配的唯一代码，由用户定义</td>
</tr>
<tr class="even">
<td>项目名称</td>
<td>ITEM_NAME</td>
<td>C</td>
<td>100</td>
<td>唯一，为此项目的标准名称</td>
</tr>
<tr class="odd">
<td>输入码</td>
<td>INPUT_CODE</td>
<td>C</td>
<td>8</td>
<td>该项目的输入码</td>
</tr>
<tr class="even">
<td>标本</td>
<td>Expand1</td>
<td>V</td>
<td>100</td>
<td>标本数据调用SPECIMAN_DICT</td>
</tr>
<tr class="odd">
<td>试管</td>
<td>Expand2</td>
<td>v</td>
<td>100</td>
<td>试管数据调用lab_item_class_dict</td>
</tr>
<tr class="even">
<td>科室</td>
<td>Expand3</td>
<td>v</td>
<td>100</td>
<td></td>
</tr>
<tr class="odd">
<td>频次</td>
<td>Expand4</td>
<td>v</td>
<td>100</td>
<td></td>
</tr>
<tr class="even">
<td>医嘱属性</td>
<td>Expand5</td>
<td>v</td>
<td>100</td>
<td><p>医嘱的长期，临时属性</p>
<p>0是临时医嘱，1是长期医嘱</p></td>
</tr>
<tr class="odd">
<td>启用时间</td>
<td>START_DATE</td>
<td>DATE</td>
<td></td>
<td>如果启用时间小于等于系统时间或者为空，则表该诊疗项目启用</td>
</tr>
<tr class="even">
<td>停用时间</td>
<td>STOP_DATE</td>
<td>DATE</td>
<td></td>
<td>如果停止时间小于等于系统时间，则表明是停用。如果在未来某一个时间内停止，或者为空，则表明还是未做停止标志，以启用时间为准来判断启用否</td>
</tr>
<tr class="odd">
<td>项目状态</td>
<td>ITEM_STATUS</td>
<td>V</td>
<td></td>
<td>项目状态 0 或 null 表示正在使用,'1'停止</td>
</tr>
</tbody>
</table>

注释：本表反映了从临床角度收集的各种诊断治疗项目，用于各应用系统之间数据交换以及自动划价。该表记录的诊疗项目包括：药品、检查、检验、治疗、手术、护理、膳食等。如果收费价表项目按找临床诊疗项目来定义，则收费项目代码可以与诊疗项目代码保持一致；否则，收费价表项目可以另行编码。用户定义。

## 临床诊疗项目操作日志表 CLINIC_OPER_LOG

|                  |                  |      |                        |                  |
|------------------|------------------|------|------------------------|------------------|
| 中文名称         | 字段名           | 类型 | 长度                   | 说明             |
| 操作时间         | OPER_DATE        | DATE | 记录当前操作发生的时间 |                  |
| 项目类型         | ITEM_CLASS       | v    | 1                      | 诊疗项目的分类   |
| 项目代码         | ITEM_CODE        | v    | 20                     |                  |
| 项目名称         | ITEM_NAME        | v    | 100                    |                  |
| 操作类型         | OPER_TYPE        | v    | 10                     | 启用，停用       |
| 操作人姓名       | OPERATOR_NAME    | v    | 20                     | 记录下是谁操作的 |
| 客户端操作机器名 | CLINIC_HOST_NAME | v    | 30                     |                  |

主健：OPER_DATE, ITEM_CODE

## 检查项目字典 EXAM_ITEM_DICT

为临床诊疗项目字典中检查项目的视图。除不包含项目类别字段外，其他与原表相同。

|          |            |      |      |      |
|----------|------------|------|------|------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 项目代码 | ITEM_CODE  | C    | 20   |      |
| 项目名称 | ITEM_NAME  | C    | 100  |      |
| 输入码   | INPUT_CODE | C    | 8    |      |

## 检验项目字典 LAB_ITEM_DICT

为临床诊疗项目字典中检验项目的视图。除不包含项目类别字段外，其他与原表相同。

|          |            |      |      |      |
|----------|------------|------|------|------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 项目代码 | ITEM_CODE  | C    | 20   |      |
| 项目名称 | ITEM_NAME  | C    | 100  |      |
| 输入码   | INPUT_CODE | C    | 8    |      |

## 治疗操作项目字典 TREAT_ITEM_DICT

为临床诊疗项目字典中治疗操作项目的视图。除不包含项目类别字段外，其他与原表相同。

|          |            |      |      |      |
|----------|------------|------|------|------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 项目代码 | ITEM_CODE  | C    | 20   |      |
| 项目名称 | ITEM_NAME  | C    | 100  |      |
| 输入码   | INPUT_CODE | C    | 8    |      |

## 护理项目字典 NURSING_DICT

为临床诊疗项目字典中护理项目的视图。除不包含项目类别字段外，其他与原表相同。

|          |            |      |      |      |
|----------|------------|------|------|------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 项目代码 | ITEM_CODE  | C    | 20   |      |
| 项目名称 | ITEM_NAME  | C    | 100  |      |
| 输入码   | INPUT_CODE | C    | 8    |      |

## 膳食项目字典 DIET_DICT

为临床诊疗项目字典中膳食项目的视图。除不包含项目类别字段外，其他与原表相同。

|          |            |      |      |      |
|----------|------------|------|------|------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 项目代码 | ITEM_CODE  | C    | 20   |      |
| 项目名称 | ITEM_NAME  | C    | 100  |      |
| 输入码   | INPUT_CODE | C    | 8    |      |

## 临床诊疗项目名称字典 CLINIC_ITEM_NAME_DICT

<table>
<colgroup>
<col style="width: 17%" />
<col style="width: 32%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 35%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>项目分类</td>
<td>ITEM_CLASS</td>
<td>C</td>
<td>1</td>
<td>对应临床诊疗项目分类</td>
</tr>
<tr class="odd">
<td>项目名称</td>
<td>ITEM_NAME</td>
<td>C</td>
<td>100</td>
<td>每个项目可以有多个名称，在一类项目中，名称必须唯一</td>
</tr>
<tr class="even">
<td>项目代码</td>
<td>ITEM_CODE</td>
<td>C</td>
<td>20</td>
<td>该名称对应的诊疗项目代码，该代码是从临床角度分配的唯一代码</td>
</tr>
<tr class="odd">
<td>正名标志</td>
<td>STD_INDICATOR</td>
<td>N</td>
<td>1</td>
<td>1-正名 0-别名，每个项目只能有一个正名</td>
</tr>
<tr class="even">
<td>输入码</td>
<td>INPUT_CODE</td>
<td>C</td>
<td>8</td>
<td>推荐使用拼音词头</td>
</tr>
<tr class="odd">
<td>五笔码</td>
<td>INPUT_CODE_WB</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>标本</td>
<td>Expand1</td>
<td>V</td>
<td>100</td>
<td>标本数据调用SPECIMAN_DICT</td>
</tr>
<tr class="odd">
<td>试管</td>
<td>Expand2</td>
<td>v</td>
<td>100</td>
<td>试管数据调用lab_item_class_dict</td>
</tr>
<tr class="even">
<td>科室</td>
<td>Expand3</td>
<td>v</td>
<td>100</td>
<td></td>
</tr>
<tr class="odd">
<td>频次</td>
<td>Expand4</td>
<td>v</td>
<td>100</td>
<td></td>
</tr>
<tr class="even">
<td>医嘱属性</td>
<td>Expand5</td>
<td>v</td>
<td>100</td>
<td><p>医嘱的长期，临时属性</p>
<p>0是临时医嘱，1是长期医嘱</p></td>
</tr>
</tbody>
</table>

注释：此表是临床诊疗项目字典的辅助表，反映了一个项目的各种名称。用于临床项目的输入，如医嘱录入等场合。用户定义。

## 检验项目名称字典 LAB_ITEM_NAME_DICT

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
| 项目名称 | ITEM_NAME     | C    | 100  |      |
| 项目代码 | ITEM_CODE     | C    | 20   |      |
|          | STD_INDICATOR | N    | 1    |      |

为临床诊疗项目名称字典中检验项目的视图。除不包含项目类别字段外，其他与原表相同。

## 治疗操作名称字典 TREAT_ITEM_NAME_DICT

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
| 治疗名称 | ITEM_NAME     | C    | 100  |      |
| 代码     | ITEM_CODE     | C    | 20   |      |
| 是否正名 | STD_INDICATOR | N    | 1    |      |
| 输入码   | INPUT_CODE    | C    | 8    |      |

为临床诊疗项目名称字典中治疗操作项目的视图。除不包含项目类别字段外，其他与原表相同。

## 护理等级字典 NURSING_CLASS_DICT

|              |                    |      |      |     |                                                                         |
|--------------|--------------------|------|------|-----|-------------------------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 |     | 说明                                                                    |
| 序号         | SERIAL_NO          | N    |      | 1   | 此序号反映了项目的排列顺序                                              |
| 护理等级代码 | NURSING_CLASS_CODE | C    |      | 1   |                                                                         |
| 护理等级名称 | NURSING_CLASS_NAME | C    |      | 8   |                                                                         |
| 输入码       | INPUT_CODE         | C    |      | 8   |                                                                         |
| 显示的颜色值 | NURSING_SHOW_COLOR | N    |      | 10  | 以rgb三原色值为准,在床头卡和图例色上显示,以后在程序中直接读出来并且显示 |
| 颜色名称     | COLOR_NAME         | V    |      | 10  |                                                                         |

注释：此表定义了临床使用的各护理等级。本系统定义。

## 手术等级字典 OPERATION_SCALE_DICT

|              |                      |      |      |                            |
|--------------|----------------------|------|------|----------------------------|
| 字段中文名称 | 字段名               | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO            | N    | 1    | 此序号反映了项目的排列顺序 |
| 手术等级代码 | OPERATION_SCALE_CODE | C    | 1    |                            |
| 手术等级名称 | OPERATION_SCALE_NAME | C    | 2    |                            |
| 输入码       | INPUT_CODE           | C    | 8    |                            |

注释：本系统定义。

## 给药途径字典ADMINISTRATION_DICT

|              |                     |      |      |      |
|--------------|---------------------|------|------|------|
| 字段中文名称 | 字段名              | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO           | N    | 2    |      |
| 给药途径代码 | ADMINISTRATION_CODE | C    | 2    |      |
| 给药途径名称 | ADMINISTRATION_NAME | C    | 16   |      |
| 输入码       | INPUT_CODE          | C    | 8    |      |

注释：用户定义。

## 麻醉方法字典 ANAESTHESIA_DICT

|              |                    |      |      |      |
|--------------|--------------------|------|------|------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO          | N    | 2    |      |
| 麻醉方法代码 | ANAESTHESIA \_CODE | C    | 1    |      |
| 麻醉方法名称 | ANAESTHESIA \_NAME | C    | 16   |      |
| 输入码       | INPUT_CODE         | C    | 8    |      |

注释：用户定义。

## 医嘱状态字典 ORDER_STATUS_DICT

|              |                   |      |      |      |
|--------------|-------------------|------|------|------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO         | N    | 1    |      |
| 医嘱状态代码 | ORDER_STATUS_CODE | C    | 1    |      |
| 医嘱状态名称 | ORDER_STATUS_NAME | C    | 8    |      |
| 输入码       | INPUT_CODE        | C    | 8    |      |

注释：此表定义疗医嘱从录入到校对、执行、停止经历的各个状态。本系统定义。

## 剂量单位字典 DOSAGE_UNITS_DICT

|              |                  |     |      |      |                                |
|--------------|------------------|-----|------|------|--------------------------------|
| 字段中文名称 | 字段名           |     | 类型 | 长度 | 说明                           |
| 序号         | SERIAL_NO        |     | N    | 3    | 此序号反映了项目的排列顺序     |
| 剂量单位     | DOSAGE_UNITS     |     | C    | 8    |                                |
| 基准单位     | BASE_UNITS       | C   |      | 8    |                                |
| 换算系数     | CONVERSION_RATIO | N   |      | 12,6 | 反映本单位与基准单位的换算比率 |
| 输入码       | INPUT_CODE       |     | C    | 8    |                                |

注释：此表定义了医嘱中使用的药品的剂量单位。本系统定义。

## 医嘱执行频率字典 PERFORM_FREQ_DICT

|              |                     |      |      |                                                        |
|--------------|---------------------|------|------|--------------------------------------------------------|
| 字段中文名称 | 字段名              | 类型 | 长度 | 说明                                                   |
| 序号         | SERIAL_NO           | N    | 3    | 此序号反映了频率项目的排列顺序                         |
| 执行频率描述 | FREQ_DESC           | C    | 16   | 执行频率的固定描述，如TID、3/日等，非空，唯一          |
| 频率次数     | FREQ_COUNTER        | N    | 2    | 执行频率的次数部分                                     |
| 频率间隔     | FREQ_INTERVAL       | N    | 2    | 执行频率的间隔部分                                     |
| 频率间隔单位 | FREQ_INTERVAL_UNITS | C    | 4    | 如日等，使用规范名称，本系统定义，见表4.31时间单位字典 |

注释：此表用于描述常用的执行频率描述与具体的执行次数的对应关系，用于医嘱录入时确定格式化的执行次数描述以及医嘱的计价。用户定义。

## 医嘱执行缺省时间表 PERFORM_DEFAULT_SCHEDULE

|                  |                  |      |      |                                               |
|------------------|------------------|------|------|-----------------------------------------------|
| 字段中文名称     | 字段名           | 类型 | 长度 | 说明                                          |
| 序号             | SERIAL_NO        | N    | 3    | 此序号反映了频率项目的排列顺序                |
| 执行频率描述     | FREQ_DESC        | C    | 16   | 执行频率的固定描述，如TID、3/日等，非空，唯一 |
| 给药途径和方法   | ADMINISTRATION   | C    | 16   | 医嘱的具体执行时间与给药途径和方法有关        |
| 缺省的执行时间表 | DEFAULT_SCHEDULE | C    | 16   | 执行的具体时间，如3/日对应8-12-6等。          |

注释：此表用于描述执行频率和给药途径与执行时间表的关系。用于医嘱录入时自动生成执行时间。

## 辅助诊断项目字典 ANCI_EXAM_ITEM_DICT

|              |                |      |      |                                      |
|--------------|----------------|------|------|--------------------------------------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明                                 |
| 项目编码     | DIAG_EXAM_CODE | C    | 8    |                                      |
| 项目名称     | DIAG_EXAM_NAME | C    | 40   |                                      |
| 项目计量单位 | COUNT_UNIT     | C    | 8    | 指明辅助诊断工作量的计量单位，如人次 |
| 输入码       | INPUT_CODE     | C    | 8    |                                      |

注释：本表定义了医院中参与辅诊工作量统计的项目，由医务统计子系统使用。数据量在数百条左右。用户定义。

## 辅助治疗项目字典 ANCI_TREAT_ITEM_DICT

|              |                 |      |      |                                          |
|--------------|-----------------|------|------|------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                     |
| 项目编码     | DIAG_TREAT_CODE | C    | 8    |                                          |
| 项目名称     | DIAG_TREAT_NAME | C    | 40   |                                          |
| 项目计量单位 | COUNT_UNIT      | C    | 8    | 指明辅助治疗项目工作量的计量单位，如人次 |
| 输入码       | INPUT_CODE      | C    | 8    |                                          |

注释：本表定义了医院中参与辅助治疗工作量统计的项目，由医务统计子系统使用。数据量在数百条左右。用户定义。

## 检验单定义 LAB_SHEET_MASTER

|                |                   |      |      |                                                                                                                    |
|----------------|-------------------|------|------|--------------------------------------------------------------------------------------------------------------------|
| 字段中文名称   | 字段名            | 类型 | 长度 | 说明                                                                                                               |
| 检验单唯一标识 | LAB_SHEET_ID      | C    | 4    | 每张定义的检验单有一唯一标识号                                                                                     |
| 检验科室       | PERFORMED_BY      | C    | 8    | 检验科室代码                                                                                                       |
| 检验单名称     | SHEET_TITLE       | C    | 40   | 每张检验单有一个反映检验项目类别的名称，如血液生化检验申请单                                                       |
| 价表项目类别   | CHARGE_ITEM_CLASS | C    | 1    | 对应价表项目的类别                                                                                                 |
| 价表项目代码   | CHARGE_ITEM_CODE  | C    | 10   | 按赵检验单计价时，对应的价表项目代码。此项目为空时，所定义的检验单按照申请项目进行累计计价。否则，按照检验单计价。 |
| 规格           | CHARGE_ITEM_SPEC  | C    | 20   | 对应价表项目中的规格。                                                                                             |

注释：此表用于描述系统定义了固定格式的检验单单头。检验单一般按相关项目分类，一张检验单的所有项目必须属于一个检验科室。用户定义。

## 检验单项目定义 LAB_SHEET_ITEMS

|                    |                   |      |      |                                               |
|--------------------|-------------------|------|------|-----------------------------------------------|
| 字段中文名称       | 字段名            | 类型 | 长度 | 说明                                          |
| 检验单唯一标识     | LAB_SHEET_ID      | C    | 4    | 每张定义的检验单有一唯一标识号                |
| 检验项目序号       | LAB_ITEM_NO       | N    | 2    | 在一张检验单内部唯一                          |
| 检验项目代码       | LAB_ITEM_CODE     | C    | 10   | 由用户定义，见4.8检验项目字典                 |
| 检验项目名称       | LAB_ITEM_NAME     | C    | 40   |                                               |
| 对应的收费项目分类 | CHARGE_ITEM_CLASS | C    | 1    | 价表定义的项目分类代码，见6.8价表项目分类字典 |
| 对应的收费项目代码 | CHARGE_ITEM_CODE  | C    | 10   | 价表定义的收费项目代码，见6.1价表             |

注释：此表反映检验单所包含的检验项目。用户定义。

## 检查报告模板 EXAM_RPT_PATTERN

|                |                  |      |      |                                                                                                                                |
|----------------|------------------|------|------|--------------------------------------------------------------------------------------------------------------------------------|
| 中文名称       | 字段名           | 类型 | 长度 | 说明                                                                                                                           |
| 检查类别       | EXAM_CLASS       | C    | 6    | 区分化验、各类检查等，使用代码，非空，取值可以为超声,CT,MRI,放射,病理,心电图等，本系统定义，见3.3检查类别字典                  |
| 检查子类       | EXAM_SUB_CLASS   | C    | 8    | 区分一种检查类下的各子类，如超声类下的腹部、心脏、妇产等子类，本系统定义，见3.4检查子类字典                                    |
| 描述项目       | DESC_ITEM        | C    | 20   | 将报告单抽象为几个描述项目，如临床症状、检查所见、印象、建议等，此字段反映以下的模板内容属于哪一个项目。项目由本系统定义，见表 |
| 描述名称       | DESC_NAME        | C    | 20   | 指定以下的描述内容为哪方面描述，如检查所见中的CT检查正常，它对应具体的描述内容                                                 |
| 描述           | DESCRIPTION      | C    | 800  | 模板的描述内容，为常用短语或句子                                                                                               |
| 描述代码       | DESCRIPTION_CODE | C    | 20   | 为每个描述分配一个代码，如果描述内容为检查项目时，可为收费项目代码                                                             |
| 描述名称输入码 | INPUT_CODE       | C    | 8    | 为描述名称对应的输入码，如汉语拼音词头，由用户定义                                                                             |

注释：此表用于对各种检查报告中的常用描述建立一个模板库。将一个报告分成若干个描述项目，每个描述项目根据检查结果有多种描述，每种描述对应此表中一条记录。检查类别、检查子类、描述项目、描述名称一起构成描述记录的唯一标识。在医生书写报告时，只要指定以上四项或输入时指定的输入码，即可以取得描述内容。如果必要，在报告中可以对提取的标准描述正文再行修改。用户定义。

此表的内容，由各检查化验科室的医生录入和修改。

## 治疗结果字典 TREATING_RESULT_DICT

|              |                      |      |      |                            |
|--------------|----------------------|------|------|----------------------------|
| 字段中文名称 | 字段名               | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO            | N    | 1    | 此序号反映了项目的排列顺序 |
| 治疗结果代码 | TREATING_RESULT_CODE | C    | 1    |                            |
| 治疗结果名称 | TREATING_RESULT_NAME | C    | 4    | 如治愈、好转、死亡等。     |
| 输入码       | INPUT_CODE           | C    | 8    |                            |

注释：本表定义了病案首页中使用的诊断治疗结果的各种取值。本系统定义。

## 切口愈合情况字典 HEAL_DICT

|                  |            |      |      |              |
|------------------|------------|------|------|--------------|
| 字段中文名称     | 字段名     | 类型 | 长度 | 说明         |
| 序号             | SERIAL_NO  | N    | 1    |              |
| 切口愈合情况代码 | HEAL_CODE  | C    | 1    |              |
| 切口愈合情况名称 | HEAL_NAME  | C    | 2    | 如甲、乙等。 |
| 输入码           | INPUT_CODE | C    | 8    |              |

注释：本表定义了病案首页中使用的手术切口愈合情况的取值种类。本系统定义。

## 诊断符合情况字典 DIAG_CORR_DICT

|                  |                |      |      |                        |
|------------------|----------------|------|------|------------------------|
| 字段中文名称     | 字段名         | 类型 | 长度 | 说明                   |
| 序号             | SERIAL_NO      | N    | 1    |                        |
| 诊断符合情况代码 | DIAG_CORR_CODE | C    | 1    |                        |
| 诊断符合情况名称 | DIAG_CORR_NAME | C    | 6    | 如符合、不符、无对照等 |
| 输入码           | INPUT_CODE     | C    | 8    |                        |

注释：本表定义了病案首页中使用的诊断符合情况取值种类。本系统定义。

## 时间单位字典 TIME_UNITS_DICT

|              |                 |      |      |                  |
|--------------|-----------------|------|------|------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明             |
| 序号         | SERIAL_NO       | N    | 1    |                  |
| 时间单位代码 | TIME_UNITS_CODE | C    | 1    |                  |
| 时间单位名称 | TIME_UNITS_NAME | C    | 4    | 如天、小时、分等 |
| 输入码       | INPUT_CODE      | C    | 8    |                  |

注释：此表定义医嘱使用的时间单位，本系统定义。

## 计量单位字典 MEASURES_DICT

|              |                  |      |      |                                |
|--------------|------------------|------|------|--------------------------------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明                           |
| 序号         | SERIAL_NO        | N    | 2    |                                |
| 计量单位类别 | MEASURES_CLASS   | C    | 10   | 如重量、容量、包装、时间等     |
| 计量单位代码 | MEASURES_CODE    | C    | 3    |                                |
| 计量单位名称 | MEASURES_NAME    | C    | 8    |                                |
| 基准单位     | BASE_UNITS       | C    | 8    |                                |
| 换算系数     | CONVERSION_RATIO | N    | 12,6 | 反映本单位与基准单位的换算比率 |
| 输入码       | INPUT_CODE       | C    | 8    |                                |

注释：此表定义药品使用的各种计量单位，本系统定义。

主键：计量单位类别、计量单位名称。

## 星期字典 DAY_OF_WEEK_DICT

|              |            |      |      |                            |
|--------------|------------|------|------|----------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO  | N    | 1    | 此序号反映了项目的排列顺序 |
| 天           | DAY_NO     | N    | 1    | 0~6，分别对应日~六         |
| 记号         | DAY_SYMBOL | C    | 2    | 日，一~六                  |

注释：本系统定义。

## 诊疗项目分类字典 CLINIC_ITEM_CLASS_DICT

|              |            |      |      |                            |
|--------------|------------|------|------|----------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO  | N    | 1    | 此序号反映了项目的排列顺序 |
| 项目类别代码 | CLASS_CODE | C    | 1    |                            |
| 项目类别名称 | CLASS_NAME | C    | 10   |                            |
| 输入码       | INPUT_CODE | C    | 8    | 推荐使用拼音词头           |

注释：本系统定义。

## 标本字典 SPECIMAN_DICT

|              |               |      |      |                               |
|--------------|---------------|------|------|-------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                          |
| 序号         | SERIAL_NO     | N    | 2    | 此序号反映了项目的排列顺序    |
| 标本代码     | SPECIMAN_CODE | C    | 2    |                               |
| 标本名称     | SPECIMAN_NAME | C    | 8    |                               |
| 输入码       | INPUT_CODE    | C    | 8    | 推荐使用拼音词头              |
| 科室代码     | DEPT_CODE     | C    | 8    | 使用标本的科室，见2.6科室字典 |

注释：本系统定义。

## 检验报告项目字典 LAB_REPORT_ITEM_DICT

|                |                |      |      |                                                                                                            |
|----------------|----------------|------|------|------------------------------------------------------------------------------------------------------------|
| 字段中文名称   | 字段名         | 类型 | 长度 | 说明                                                                                                       |
| 序号           | SERIAL_NO      | N    | 4    | 此序号反映了项目的排列顺序                                                                                 |
| 项目代码       | ITEM_CODE      | C    | 20   |                                                                                                            |
| 项目名称       | ITEM_NAME      | C    | 100  |                                                                                                            |
| 结果类型       | RESULT_TYPE    | C    | 8    | 反映标注、阴阳弱、药敏、描述等                                                                             |
| 正常值下限     | LOWER_LIMIT    | N    | 9,3  | 不受其他条件影响的正常值，如果受其他条件影响，则为空。对固定正常值，与正常值上限相同。对不限制下限，为空。 |
| 正常值上限     | UPPER_LIMIT    | N    | 9,3  | 不受其他条件影响的正常值，如果受其他条件影响，则为空。对固定正常值，与正常值下限相同。对不限制上限，为空。 |
| 正常值单位     | UNITS          | C    | 8    | 可以为复合单位                                                                                             |
| 正常值打印内容 | PRINT_CONTEXT  | C    | 80   |                                                                                                            |
| 最小增量       | MINI_INCREMENT | N    | 6,3  |                                                                                                            |
| 正常值备注     | NOTES          | C    | 40   | 用于存放有条件的正常值，正文描述                                                                           |
| 缺省值         | DEFAULT_VALUE  | C    | 20   | 检验结果的缺省值                                                                                           |
| 输入码         | INPUT_CODE     | C    | 8    | 推荐使用拼音词头                                                                                           |

注释：用户定义。

## 检验结果模板字典 LAB_LIST_RESULT_DICT

|              |                  |      |      |                                            |
|--------------|------------------|------|------|--------------------------------------------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明                                       |
| 报告项目代码 | REPORT_ITEM_CODE | C    | 10   | 代码对应检验报告项目字典                   |
| 结果序号     | RESULT_NO        | N    | 4    | 每个序号对应同一个报告项目代码中的一个结果 |
| 检验结果     | RESULT_VALUE     | C    | 20   | 结果的内容                                 |
| 输入码       | INPUT_CODE       | C    | 8    | 对应结果值的输入码                         |

注释：此表用于描述列表类型结果的所有可能的内容。软件在处理这类检验项目时，从本表中选取结果填入检验结果表中。用户定义。

## 检验申请项目与报告项目对照 LAB_ORDER_VS_REPORT

|              |                  |      |      |                                    |
|--------------|------------------|------|------|------------------------------------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明                               |
| 序号         | SERIAL_NO        | N    | 2    | 此序号反映了项目的排列顺序         |
| 申请项目代码 | ORDER_ITEM_CODE  | C    | 10   | 为临床诊疗项目字典中定义的检验项目 |
| 报告项目代码 | REPORT_ITEM_CODE | C    | 10   | 为检验报告项目字典中定义的项目     |

注释：此表用于建立检验申请项目与报告项目之间的对照。申请项目可以为复合项目，因此一个申请项目可以对应多个报告项目。如果申请项目已经为独立的项目，则它对照到自身；如果申请项目的结果项目不确定，它也对照到自身。每个申请项目至少在本对照表中有一条记录。用户定义。

## 切口等级字典 WOUND_GRADE_DICT

|              |                  |      |      |                            |
|--------------|------------------|------|------|----------------------------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO        | N    | 1    | 此序号反映了项目的排列顺序 |
| 切口等级代码 | WOUND_GRADE_CODE | C    | 1    |                            |
| 切口等级名称 | WOUND_GRADE_NAME | C    | 2    | 如I、II等                  |
| 输入码       | INPUT_CODE       | C    | 8    |                            |

注释：此表定义手术的切口等级，本系统定义。

## 检验项目与分类对照 LAB_ITEM_VS_CLASS

|              |            |      |      |                                |
|--------------|------------|------|------|--------------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                           |
| 项目类别     | ITEM_CLASS | C    | 8    | 检验项目所属类别，使用中文     |
| 项目代码     | ITEM_CODE  | C    | 20   | 为检验申请项目字典中定义的项目 |

注释：此表用于检验项目分类，为检验系统的录入及统计提供方便。如生化类、临检类、微生物类等。用户定义。

主键：项目代码。

## 检验项目类别字典 LAB_ITEM_CLASS_DICT

|              |            |      |      |                            |
|--------------|------------|------|------|----------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO  | N    | 2    | 此序号反映了项目的排列顺序 |
| 类别代码     | CLASS_CODE | C    | 8    |                            |
| 类别名称     | CLASS_NAME | C    | 8    |                            |

注释：此表用于定义检验项目类别，如生化类、临检类、微生物类等。用户定义。

主键：类别代码。

## 检验报告项目与申请项目对照 LAB_REPORT_VS_ORDER

|                  |                    |      |      |                                            |
|------------------|--------------------|------|------|--------------------------------------------|
| 字段中文名称     | 字段名             | 类型 | 长度 | 说明                                       |
| 科室代码         | DEPT_CODE          | C    | 8    | 使用科室，见2.6科室字典                    |
| 检验报告项目代码 | REPORT_ITEM_CODE   | C    | 10   | 报告项目对应的代码，见4.36检验报告项目字典 |
| 标本             | SPECIMEN           | C    | 8    | 使用标准描述，如血、尿等                   |
| 优先标志         | PRIORITY_INDICATOR | N    | 1    | 反映此申请的紧急程度。0-普通 1-紧急        |
| 仪器编号         | INSTRUMENT_ID      | C    | 8    | 同检验仪器检验项目配置中定义的仪器编号     |
| 申请项目代码     | ITEM_CODE          | C    | 20   | 检验项目代码，见4.8检验项目字典            |

注释：此表通常在使用自动检验仪器时使用，用于一个报告项目在不同条件下对应多个申请项目时，从报告查找符合条件的申请项目。此表在系统初始化时是可选择的，如果报告项目无法根据本表确定申请项目记录，则程序需要提供手工选择的处理功能。用户定义。

主键：科室代码、检验报告代码、标本、优先标志、仪器编号。

## 药物过敏严重程度字典 DRUG_ALERGY_SEVERITY_DICT(不使用)

|              |               |      |      |                            |
|--------------|---------------|------|------|----------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO     | N    | 2    | 此序号反映了项目的排列顺序 |
| 严重程度代码 | SEVERITY_CODE | C    | 2    |                            |
| 严重程度名称 | SEVERITY_NAME | C    | 8    |                            |
| 输入码       | INPUT_CODE    | C    | 8    | 推荐使用拼音词头           |

注释：此表用于定义发生药物过敏症状的严重程度。用户定义。

主键：严重程度代码。

## 合理用药相关表MDC_DRUG_MATCH_RESULT(不使用)

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
|          | SUSER_ID      | C    | 32   |      |
|          | SUSER_UNIT    | C    | 32   |      |
|          | SSYS_NAME     | C    | 255  |      |
|          | SSYS_TYPE     | C    | 32   |      |
|          | SSTRENGTH     | C    | 32   |      |
|          | SSYS_UNIT     | C    | 32   |      |
|          | SUNITRATE     | C    | 32   |      |
|          | SMATCH_USER   | C    | 24   |      |
|          | SMATCH_TIME   | C    | 19   |      |
|          | SHAS_HIS_INFO | C    | 8    |      |

## 合理用药相关表MDC_ROUTE_MATCH_RESULT(不使用)

|          |             |      |      |      |
|----------|-------------|------|------|------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明 |
|          | SUSER_ID    | C    | 32   |      |
|          | SSYS_NAME   | C    | 40   |      |
|          | SMATCH_USER | C    | 24   |      |
|          | SMATCH_TIME | C    | 19   |      |

## MEDCARD_PRIVILEGE_DICT(不使用)

|          |                     |      |      |      |
|----------|---------------------|------|------|------|
| 中文名称 | 字段名              | 类型 | 长度 | 说明 |
|          | SERIAL_NO           | N    | 3    |      |
|          | PRIVILEGE_ITEM_CODE | C    | 2    |      |
|          | PRIVILEGE_ITEM_NAME | C    | 10   |      |
|          | PRIVILEGE_FLAG      | C    | 1    |      |
|          | PRIVILEGE_PERCENT   | N    | 5,2  |      |
|          | PRIVILEGE_MONEY     | N    | 5,2  |      |

## QUALITY_GRAND_DICT(不使用)

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
|          | SERIAL_NO     | N    | 2    |      |
|          | CODE          | C    | 2    |      |
|          | QUALITY_GRAND | C    | 10   |      |
|          | MEMO          | C    | 100  |      |

#  药品物资

## 药品字典 DRUG_DICT

|              |                  |      |      |                                                                              |
|--------------|------------------|------|------|------------------------------------------------------------------------------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明                                                                         |
| 药品代码     | DRUG_CODE        | C    | 10   | 药品名（含剂型）的唯一标识，与药品规格一起构成一种药品（含规格）的标识       |
| 药品名称     | DRUG_NAME        | C    | 40   | 药品的标准名称                                                               |
| 规格         | DRUG_SPEC        | C    | 20   | 反映药品的含量信息，如25mg                                                   |
| 单位         | UNITS            | C    | 8    | 对应剂型及规格的最小单位，如片、支等，使用规范名称，见4.32计量单位字典       |
| 剂型         | DRUG_FORM        | C    | 10   | 如针剂、片剂等，使用规范描述，见剂型字典                                     |
| 毒理分类     | TOXI_PROPERTY    | C    | 10   | 按药品的毒理分类，如普通、毒麻、精神等，使用规范名称，本系统定义，见毒理字典 |
| 最小单位剂量 | DOSE_PER_UNIT    | N    | 8,3  | 每一最小不可分包装单位所含剂量，如每片、每支的剂量                           |
| 剂量单位     | DOSE_UNITS       | C    | 8    | 剂量的单位，如mg、ml等                                                       |
| 药品类别标志 | DRUG_INDICATOR   | N    | 1    | 反映是否药品及何类药品：1-西药2-中草药 3-中成药5-辅料 6-试剂 9-其它          |
| 输入码       | INPUT_CODE       | C    | 8    |                                                                              |
| OTC类型      | OTC              | C    | 10   |                                                                              |
| 限制等级     | LIMIT_CLASS      | C    | 4    | 医生开药限制等级,特级，一级，二级，三级，四级                                |
| 停药标志     | Stop_flag        | c    | 1    | 1-停药                                                                       |
| 录入日期     | ENTERED_DATETIME | D    |      |                                                                              |

注释：此表定义了医院所使用的每一种药品。

主键：药品代码、规格、药品类别标志。

备注：药品类别标志不应该作为主键之一，因为药品类别不同，则药品代码必然不同，否则就是药品代码编码原则不合理；而且药品字典此种需要和其他表频繁关联的基础类表，主键列数目不易偏多，否则会造成结构上的冗余（只要用药的表都要至少包含其主键列）；

## 药品名称字典 DRUG_NAME_DICT

|              |               |      |      |                      |
|--------------|---------------|------|------|----------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                 |
| 药品代码     | DRUG_CODE     | C    | 10   | 由药品字典定义的代码 |
| 药品名称     | DRUG_NAME     | C    | 40   |                      |
| 正名标志     | STD_INDICATOR | N    | 1    | 0-别名 1-正名        |
| 输入码       | INPUT_CODE    | C    | 8    |                      |
| 五笔码       | INPUT_CODE_WB | C    | 8    |                      |

注释：此表反映了药品的各种名称与标准名称及编码的对应关系。

## 药品价格 DRUG_PRICE_LIST

|                        |                    |      |      |                                                       |
|------------------------|--------------------|------|------|-------------------------------------------------------|
| 字段中文名称           | 字段名             | 类型 | 长度 | 说明                                                  |
| 药品代码               | DRUG_CODE          | C    | 10   | 由药品字典定义的代码                                  |
| 规格                   | DRUG_SPEC          | C    | 20   | 反映药品的含量以及包装                                |
| 厂家标识               | FIRM_ID            | C    | 10   | 反映生产厂家                                          |
| 单位                   | UNITS              | C    | 8    | 对应剂型及规格，使用规范名称，见4.32计量单位字典      |
| 市场批发价             | TRADE_PRICE        | N    | 10,4 | 药库采购药品时的市场定价                              |
| 市场零售价             | RETAIL_PRICE       | N    | 10,4 | 药品零售时的市场定价                                  |
| 包装数量               | AMOUNT_PER_PACKAGE | N    | 5    | 指单位包装中所含最小单位数量。如果已为最小单位，则为1 |
| 最小单位规格           | MIN_SPEC           | C    | 20   | 反映最小单位药品含量，与药品字典中定义规格同          |
| 最小单位               | MIN_UNITS          | C    | 8    | 对应最小单位规格的单位，如片                          |
| 起用日期               | START_DATE         | D    |      | 该价格的起用日期，执行日期含起用日期当天              |
| 停止日期               | STOP_DATE          | D    |      | 该价格的停止执行日期，执行日期含停止日期当天          |
| 备注                   | MEMOS              | C    | 500  | 记录价格来源等信息                                    |
| 对应的住院收据费用分类 | Class_on_inp_rcpt  | c    | 1    |                                                       |
| 对应的门诊收据费用分类 | Class_on_outp_rcpt | c    | 1    | Reference OUTP_RCPT_FEE_DICT.FEE_CLASS_CODE           |
| 对应的核算项目分类     | Class_on_reckoning | c    | 3    |                                                       |
| 对应的会计科目         | Subj_code          | c    | 4    |                                                       |
| 对应的病案首页费用分类 | Class_on_mr        | c    | 4    |                                                       |
| 最高限价               | HLIMIT_PRICE       | N    | 10,4 |                                                       |
| 价格类别               | PRICE_CLASS        | C    | 4    | 存名称，甲乙类                                        |
| 批准文号               | PASS_NO            | C    | 30   |                                                       |
| GMP标识                | GMP                | N    | 1    | 0-否，1-是                                            |
| 变更备注               | changed_memo       | V2   | 500  | 调价或停止备注.不会清掉原来的备注说明                 |

注释：此表定义每一种药品的价格，除了按药品字典定义的每种规格药品定价外，该表中可以对不同包装的药品进行定价。在规格字段中可以包含包装信息，如：25mg\*24。也就是说，这里的“规格”不同于药品字典中的“规格”。对同种药品不同厂家，可以定义不同的价格。该价表包含了价格的历史信息，同种规格的同种药品只能有一个当前有效价。

主键：药品代码、规格、厂家标识、起用日期。

## 公费用药目录 OFFICIAL_DRUG_CATALOG

|              |                   |      |      |                                                                                      |
|--------------|-------------------|------|------|--------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                                                                                 |
| 费别         | CHARGE_TYPE       | C    | 8    | 公费药品适用的费别                                                                   |
| 药品代码     | DRUG_CODE         | C    | 20   | 由药品字典定义的代码                                                                 |
| 规格         | DRUG_SPEC         | C    | 20   | 价表中对应药品的规格，“\*”表示不限规格                                               |
| 限制级别     | CONSTRAINED_LEVEL | C    | 10   | 反映公费用药范围限制信息，0-无限制，1-需部分负担，2-限适应症，3-限适应症且需部分负担 |
| 备注         | MEMO              | C    | 255  |                                                                                      |
| 注册商标     | TRADEMARK         | C    | 20   |                                                                                      |
| 类型         | typex             | V2   | 10   |                                                                                      |

注释：此表定义了公费用药目录。不同的费别可以对应不同的用药目录。对一种药品不限制规格的情况，规格可以使用“\*”。对于部分规格受限（如进口）的情况，公费用药需要在目录中指明具体规格。

主键：费别、类别.药品代码、规格.类型。Charge_type,Item_class,Drug_code,Drug_spec,typex

## 药品入库分类字典 DRUG_IMPORT_CLASS_DICT 

|              |                 |      |      |                    |
|--------------|-----------------|------|------|--------------------|
| 字段中文名   | 字段名          | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO       | N    | 2    | 反映项目的排列顺序 |
| 入库分类     | IMPORT_CLASS    | C    | 8    | 使用中文名称       |
| 统计用类别名 | statistic_class | V    | 16   | 进行统计查询       |

注释：此表定义了入库药品的来源分类，用户定义。

主键：入库分类

## 药品出库分类字典 DRUG_EXPORT_CLASS_DICT 

|              |                 |      |      |                    |
|--------------|-----------------|------|------|--------------------|
| 字段中文名   | 字段名          | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO       | N    | 2    | 反映项目的排列顺序 |
| 出库分类     | EXPORT_CLASS    | C    | 8    | 使用中文名称       |
| 统计用类别名 | statistic_class | V    | 16   | 进行统计查询       |

注释：此表定义了出库药品的来源分类，用户定义。

主键：出库分类

## 药品处方属性字典 DRUG_PRESC_ATTR_DICT

|              |                 |      |      |                    |
|--------------|-----------------|------|------|--------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO       | N    | 2    | 反映项目的排列顺序 |
| 属性代码     | PRESC_ATTR_CODE | C    | 1    |                    |
| 属性名称     | PRESC_ATTR_NAME | C    | 8    |                    |

注释：此表定义药品处方的属性，用户定义。

主键：属性名称

## 药品摆药类别字典 DRUG_DISP_PROPERTY_DICT

|              |                      |      |      |                                                                           |
|--------------|----------------------|------|------|---------------------------------------------------------------------------|
| 字段中文名称 | 字段名               | 类型 | 长度 | 说明                                                                      |
| 序号         | SERIAL_NO            | N    | 2    | 反映项目的排列次序                                                        |
| 摆药类别     | DISPENSING_PROPERTY  | C    | 10   |                                                                           |
| 对应给药途径 | DRUG_ADMINISTRATIONS | C    | 256  | 该类别药品医嘱中可能的给药途径。多种给药途径之间以“;”分隔。用于摆药时参考 |

注释：此表定义药品摆药时的分类，如：口服、针剂、大输液等。用户定义。

主键：摆药类别

## 药品供应商目录 DRUG_SUPPLIER_CATALOG

|              |                |      |      |                                        |
|--------------|----------------|------|------|----------------------------------------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明                                   |
| 厂商标识     | SUPPLIER_ID    | C    | 10   | 唯一标识一个厂商                       |
| 厂商         | SUPPLIER       | C    | 40   | 厂商全称                               |
| 厂商类别     | SUPPLIER_CLASS | C    | 8    | 用于反映厂商的性质，如生产厂、批发商等 |
| 输入码       | INPUT_CODE     | C    | 8    |                                        |
| 备注         | MEMO           | C    | 100  |                                        |
| 注册商标     | TRADEMARK      | C    | 20   |                                        |
| 五笔输入码   | INPUT_CODE_WB  | C    | 8    |                                        |

注释：此表定义了药品供应厂商，由药品管理分系统使用。用户定义。

主键：厂商标识

## 药品毒理分类字典 DRUG_TOXI_PROPERTY_DICT 

|              |            |      |      |                    |
|--------------|------------|------|------|--------------------|
| 字段中文名   | 字段名     | 类型 | 长度 | 说明               |
| 序号         | SERIAL_NO  | N    | 2    | 反映项目的排列次序 |
| 毒理分类代码 | TOXI_CODE  | C    | 2    |                    |
| 毒理分类名称 | TOXI_NAME  | C    | 10   |                    |
| 输入码       | INPUT_CODE | C    | 8    |                    |

注释：此表定义药品毒理分类。用户定义。

主键：毒理分类名称。

## 药品剂型字典 DRUG_FORM_DICT 

|            |            |      |      |                    |
|------------|------------|------|------|--------------------|
| 字段中文名 | 字段名     | 类型 | 长度 | 说明               |
| 序号       | SERIAL_NO  | N    | 2    | 反映项目的排列次序 |
| 剂型代码   | FORM_CODE  | C    | 2    | 唯一标识一种剂型   |
| 剂型名称   | FORM_NAME  | C    | 10   |                    |
| 输入码     | INPUT_CODE | C    | 8    |                    |

注释：此表定义药品剂型。用户定义。

主键：剂型代码。

## 药品类别字典 DRUG_CLASS_DICT

|              |            |      |      |              |
|--------------|------------|------|------|--------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明         |
| 类别代码     | CLASS_CODE | C    | 10   | 药品层次代码 |
| 类别名称     | CLASS_NAME | C    | 40   |              |

注释：此表定义药品的分类，包括各层分类，类之间的关系由药品编码描述表定义。

主键：类别代码

## 药品编码描述 DRUG_CODING_RULE

|              |             |      |      |                               |
|--------------|-------------|------|------|-------------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                          |
| 编码级       | CODE_LEVEL  | N    | 1    | 反映编码层数，从1开始依次排列 |
| 级长         | LEVEL_WIDTH | N    | 2    | 此级编码位数                  |
| 级名         | CLASS_NAME  | C    | 8    | 此级编码名称，如：大类、小类  |

注释：此表定义药品编码的分层结构。

主键：编码级

## 药品信息 DRUG_INFO

|              |                  |      |      |                        |
|--------------|------------------|------|------|------------------------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明                   |
| 药品代码     | DRUG_CODE        | C    | 8    | 反映药品剂型以外的名称 |
| 药品名称     | DRUG_NAME        | C    | 40   | 剂型以外的名称         |
| 药品英文名称 | DRUG_E_NAME      | C    | 40   |                        |
| 药理作用     | ACTION           | C    | 2000 |                        |
| 适用症       | INDICATION       | C    | 2000 |                        |
| 用法用量     | DOSAGE           | C    | 2000 |                        |
| 制剂         | FORM             | C    | 2000 |                        |
| 药代动力学   | PHARMACOKINETICS | C    | 2000 |                        |
| 不良反应     | ADVERSE_REACTION | C    | 2000 |                        |
| 注意事项     | ATTENTION        | C    | 2000 |                        |
| 禁忌         | CONTRAINDICATION | C    | 2000 |                        |

注释：此表记录了药品使用信息。

主键：药品代码

## 药品相互作用 DRUG_INCOMPATIBILITY

|              |             |      |      |                                                   |
|--------------|-------------|------|------|---------------------------------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                                              |
| 药品A代码    | DRUG_A_CODE | C    | 20   | 与药品B之间有相互作用，由药品信息表定义的药品代码 |
| 药品B代码    | DRUG_B_CODE | C    | 20   | 由药品信息表定义的药品代码                        |
| 相互作用描述 | DESCRIPTION | C    | 2000 |                                                   |

注释：此表记录了药品相互作用对。要检索两个药品是否有相互作用，需要将两个药品分别按药品A和药品B检索。

主键：药品A代码、药品B代码

## 药品用量信息COMM.drug_rational_dosage(新增)

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 31%" />
<col style="width: 6%" />
<col style="width: 8%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>药品代码</td>
<td>DRUG_CODE</td>
<td>C</td>
<td>20</td>
<td>药品名（含剂型）的唯一标识，与药品规格一起构成一种药品（含规格）的标识</td>
</tr>
<tr class="odd">
<td>规格</td>
<td>DRUG_SPEC</td>
<td>C</td>
<td>20</td>
<td>由药品字典定义的规格</td>
</tr>
<tr class="even">
<td>剂量单位</td>
<td>DOSE_UNITS</td>
<td>C</td>
<td>8</td>
<td>剂量的单位，如mg、ml等</td>
</tr>
<tr class="odd">
<td>最小单位剂量</td>
<td>DOSE_PER_UNIT</td>
<td>N</td>
<td>8,3</td>
<td><p>每一最小不可分包装单位所含剂量，如每片、每支的剂量;</p>
<p>药品的最小剂量表示药品在使用过程中的最小使用单位所含的药品的含量，定义药品的剂量为了其他系统做药品数量转换使用的。</p></td>
</tr>
<tr class="even">
<td>单次最大用量</td>
<td>Max_dosage</td>
<td>N</td>
<td>12,2</td>
<td>单个处方最大开药剂量</td>
</tr>
<tr class="odd">
<td>给药途径和方法</td>
<td>ADMINISTRATION</td>
<td>C</td>
<td>16</td>
<td>规范描述，是判断生成何种治疗单的依据，本系统定义，见4.17给药途径字典</td>
</tr>
<tr class="even">
<td>执行频率描述</td>
<td>FREQUENCY</td>
<td>c</td>
<td>16</td>
<td>执行频率描述</td>
</tr>
<tr class="odd">
<td>频率次数</td>
<td>FREQ_COUNTER</td>
<td>N</td>
<td>2</td>
<td>执行频率的次数部分</td>
</tr>
<tr class="even">
<td>频率间隔</td>
<td>FREQ_INTERVAL</td>
<td>N</td>
<td>2</td>
<td>执行频率的间隔部分</td>
</tr>
<tr class="odd">
<td>频率间隔单位</td>
<td>FREQ_INTERVAL_UNIT</td>
<td>C</td>
<td>4</td>
<td>使用标准描述，本系统定义，见4.31时间单位字典</td>
</tr>
<tr class="even">
<td>门诊处方最大用药天数</td>
<td>max_outp_abidance</td>
<td>N</td>
<td>3,0</td>
<td></td>
</tr>
</tbody>
</table>

主键：药品代码, 规格

## 中标价格类别TENDER_PRICE_CLASS(新增)

|                  |                  |      |      |      |
|------------------|------------------|------|------|------|
| 中文名称         | 字段名           | 类型 | 长度 | 说明 |
| 中标价格类别编码 | PRICE_CLASS_CODE | N    | 1    |      |
| 价格类别名称     | PRICE_CLASS_NAME | C    | 4    |      |
| 备注             | MEMO             | C    | 100  |      |

## 中标药品字典TENDER_DRUG_DICT(新增)

|            |                     |      |      |      |
|------------|---------------------|------|------|------|
| 中文名称   | 字段名              | 类型 | 长度 | 说明 |
| 药品代码   | DRUG_CODE           | C    | 20   |      |
| 招标批号   | ORDER_BATCH         | C    | 4    |      |
| 中标序号   | TENDER_NO           | N    | 4    |      |
| 包装规格   | PACK_SPEC           | C    | 20   |      |
| 生产厂商   | FIRM_ID             | C    | 10   |      |
| 中标价     | TENDER_PRICE        | N    | 10,4 |      |
| 中标零售价 | TENDER_RETAIL_PRICE | N    | 10,4 |      |
| 最高零售价 | HIGH_PRICE          | N    | 10,4 |      |
| 供应商     | SUPPLIER            | C    | 10   |      |
| 停用标识   | STOP_FLAG           | N    | 1    |      |

## 货位名称LOCATION(新增)

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
| 货位编码 | LOCATION_CODE | C    | 5    |      |
| 货位名称 | LOCATION_NAME | C    | 20   |      |
| 库房     | STORAGE       | C    | 8    |      |
| 说明     | MEMO          | C    | 100  |      |

## 设备字典EQUIP_DICT

|          |             |      |      |      |
|----------|-------------|------|------|------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明 |
| 设备代码 | EQUIP_CODE  | C    | 10   |      |
| 设备名称 | EQUIP_NAME  | C    | 40   |      |
| 规格     | EQUIP_SPEC  | C    | 20   |      |
| 制造商   | EQUIP_MODEL | C    | 20   |      |
| 单位     | EQUIP_UNIT  | C    | 8    |      |
| 类别     | EQUIP_TYPE  | C    | 8    |      |

主键：EQUIP_CODE，EQUIP_NAME，EQUIP_SPEC，EQUIP_MODEL

## 设备制造商字典EQUIP_MANUFACTURE_DICT

|            |             |      |      |      |
|------------|-------------|------|------|------|
| 中文名称   | 字段名      | 类型 | 长度 | 说明 |
| 顺序号     | SERIAL_NO   | N    | 2    |      |
| 产品       | MANUFACTURE | C    | 40   |      |
| 厂家       | FIRM_ID     | C    | 10   |      |
| 输入法代码 | INPUT_CODE  | C    | 10   |      |

主键：厂家

## 设备名称字典EQUIP_NAME_DICT

|              |               |      |      |      |
|--------------|---------------|------|------|------|
| 中文名称     | 字段名        | 类型 | 长度 | 说明 |
| 设备代码     | EQUIP_CODE    | C    | 10   |      |
| 设备名称     | EQUIP_NAME    | C    | 40   |      |
| 标准名称标志 | STD_INDICATOR | N    | 1    |      |
| 输入码       | INPUT_CODE    | C    | 10   |      |

主键：EQUIP_CODE

## EQUIP_VS_FEE_DICT

|          |                   |      |      |      |
|----------|-------------------|------|------|------|
| 中文名称 | 字段名            | 类型 | 长度 | 说明 |
|          | TYPE_NO           | C    | 3    |      |
|          | SERIAL_NO         | C    | 6    |      |
|          | EQUIP_NAME        | C    | 40   |      |
|          | EQUIP_FEE_CODE    | C    | 10   |      |
|          | EQUIP_FEE_NAME    | C    | 40   |      |
|          | PERFORMED_BY      | C    | 10   |      |
|          | PERFORMED_BY_NAME | C    | 20   |      |
|          | FEE_CLASS         | C    | 4    |      |

## 消耗品编码规则EXP_CODING_RULE

|          |             |      |      |      |
|----------|-------------|------|------|------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明 |
| 编码等级 | CODE_LEVEL  | N    | 1    |      |
| 等级宽度 | LEVEL_WIDTH | N    | 2    |      |
| 等级名称 | CLASS_NAME  | C    | 8    |      |

主键：编码等级

## 消耗品字典EXP_DICT

|                        |                        |      |      |                      |
|------------------------|------------------------|------|------|----------------------|
| 中文名称               | 字段名                 | 类型 | 长度 | 说明                 |
| 消耗品代码             | EXP_CODE               | C    | 20   |                      |
| 消耗品名称             | EXP_NAME               | C    | 100  |                      |
| 规格                   | EXP_SPEC               | C    | 20   |                      |
| 单位                   | UNITS                  | C    | 8    |                      |
| 类别                   | EXP_FORM               | C    | 10   |                      |
| 属性                   | TOXI_PROPERTY          | C    | 10   |                      |
| 单位剂量               | DOSE_PER_UNIT          | N    | 8,3  |                      |
| 剂量单位               | DOSE_UNITS             | C    | 8    |                      |
| 输入码                 | INPUT_CODE             | C    | 8    |                      |
| 标志（是否为全院产品） | EXP_INDICATOR          | N    | 1    | 全院产品为1，否则为2 |
| 库房代码               | STORAGE_CODE           | C    | 10   |                      |
| 是否是包               | single_group_indicator | V2   | 1    |                      |

主键：消耗品代码，消耗品名称

## 消耗品币值字典EXP_FUND_ITEM_DICT

|          |           |      |      |      |
|----------|-----------|------|------|------|
| 中文名称 | 字段名    | 类型 | 长度 | 说明 |
| 顺序号   | SERIAL_NO | N    | 2    |      |
| 币值     | FUND_ITEM | C    | 10   |      |

主键：币值

## 消耗品名称字典EXP_NAME_DICT

|              |               |      |      |      |
|--------------|---------------|------|------|------|
| 中文名称     | 字段名        | 类型 | 长度 | 说明 |
| 消耗品代码   | EXP_CODE      | C    | 20   |      |
| 消耗品名称   | EXP_NAME      | C    | 100  |      |
| 标准名称标志 | STD_INDICATOR | N    | 1    |      |
| 输入码       | INPUT_CODE    | C    | 8    |      |
| 五笔输入码   | INPUT_CODE_WB | C    | 8    |      |

主键：消耗品代码，消耗品名称

## 消耗品属性字典EXP_PROPERTY_DICT

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
| 属性代码 | Toxi_Code     | C    | 2    |      |
| 属性名称 | Toxi_PROPERTY | C    | 10   |      |
| 拼音码   | Input_Code    | C    | 8    |      |
| 五笔码   | Input_Code_WB | C    | 8    |      |

主键：Toxi_Code

## 消耗品价表EXP_PRICE_LIST

|              |                    |      |      |      |
|--------------|--------------------|------|------|------|
| 中文名称     | 字段名             | 类型 | 长度 | 说明 |
| 消耗品代码   | EXP_CODE           | C    | 20   |      |
| 规格         | EXP_SPEC           | C    | 20   |      |
| 厂商         | FIRM_ID            | C    | 10   |      |
| 单位         | UNITS              | C    | 8    |      |
| 批发价       | TRADE_PRICE        | N    | 10,4 |      |
| 零售价       | RETAIL_PRICE       | N    | 10,4 |      |
| 包装数量     | AMOUNT_PER_PACKAGE | N    | 5    |      |
| 最小规格     | MIN_SPEC           | C    | 20   |      |
| 最小单位     | MIN_UNITS          | C    | 8    |      |
| 住院收据代码 | CLASS_ON_INP_RCPT  | C    | 1    |      |
| 门诊收据代码 | CLASS_ON_OUTP_RCPT | C    | 1    |      |
| 核算代码     | CLASS_ON_RECKONING | C    | 3    |      |
| 会计代码     | SUBJ_CODE          | C    | 4    |      |
| 病案代码     | CLASS_ON_MR        | C    | 4    |      |
| 启用时间     | START_DATE         | D    |      |      |
| 停止时间     | STOP_DATE          | D    |      |      |
| 备注         | MEMOS              | C    | 20   |      |
| 最高零售价   | MAX_RETAIL_PRICE   | N    | 10,4 |      |
| 物价编码     | material_code      | C    | 20   |      |

主键：消耗品代码，规格，厂商，启用时间

## 消耗品打包模板明细记录

|                |                  |      |      |      |
|----------------|------------------|------|------|------|
| 中文名称       | 字段名           | 类型 | 长度 | 说明 |
| 消耗品大项代码 | EXP_CODE         | V2   | 20   |      |
| 大项规格       | EXP_spec         | V2   | 20   |      |
| 大项标志       | EXP_indicator    | n    | 1    |      |
| 小项代码       | SINGLE_CODE      | V2   | 20   |      |
| 小项规格       | single_spec      | V2   | 20   |      |
| 小项标志       | single_indicator | n    | 1    |      |
| 数量           | AMOUNT           | n    | 6,2  |      |
| 回收标志       | DOC_STATUS       | V2   | 1    |      |

Pk : (EXP_CODE,exp_spec,exp_indicator,SINGLE_CODE,single_spec,single_indicator)

## 供应商字典EXP_SUPPLIER_CATALOG

|                  |                     |      |      |      |
|------------------|---------------------|------|------|------|
| 中文名称         | 字段名              | 类型 | 长度 | 说明 |
| 厂商代码         | SUPPLIER_ID         | C    | 10   |      |
| 厂商             | SUPPLIER            | C    | 40   |      |
| 厂商类型         | SUPPLIER_CLASS      | C    | 8    |      |
| 厂商地址         | SUPPLIER_ADDRES     | v    | 100  |      |
| 厂商邮编         | SUPPLIER_postalcode | v    | 6    |      |
| 法人姓名         | Artificial_person   | V    | 20   |      |
| 联系电话         | linkphone           | v    | 20   |      |
| 营业执照号       | Licence_no          | v    | 20   |      |
| 营业执照期限     | Licence_date        | date |      |      |
| 生产经营许可证号 | Permit_no           | v    | 20   |      |
| 医疗器械注册证号 | Register_no         | v    | 20   |      |
| 注册证期限       | Register_date       | date |      |      |
| 美国或欧洲号     | FDA_or_CE_NO        | v    | 20   |      |
| 截止日期         | FDA_or_CE_date      | v    | 20   |      |
| 其它证号         | Other_NO            | V    | 20   |      |
| 其它日期         | Other_date          | date |      |      |
| 备注             | MEMO                | C    | 100  |      |
| 输入码           | INPUT_CODE          | C    | 8    |      |
| 五笔输入码       | INPUT_CODE_WB       | C    | 8    |      |

主键：厂商代码

## 经费来源字典FUND_SOURCE_DICT

|              |             |      |      |      |
|--------------|-------------|------|------|------|
| 中文名称     | 字段名      | 类型 | 长度 | 说明 |
| 顺序号       | SERIAL_NO   | N    | 2    |      |
| 代码         | CODE        | C    | 2    |      |
| 经费来源名称 | FUND_SOURCE | C    | 10   |      |
| 备注         | MEMO        | C    | 100  |      |

主键：代码

## 公费用药目录OFFICIAL_DRUG_CATALOG(新增)

|          |                   |      |      |      |
|----------|-------------------|------|------|------|
| 中文名称 | 字段名            | 类型 | 长度 | 说明 |
| 费用类别 | CHARGE_TYPE       | N    | 1    |      |
| 药品编码 | DRUG_CODE         | C    | 10   |      |
| 药品规格 | DRUG_SPEC         | C    | 20   |      |
| 限制级别 | CONSTRAINED_LEVEL |      |      |      |
| 备注     | MEMO              |      |      |      |
| 注册商标 | TRADEMARK         |      |      |      |

主键：费用类别,药品编码,药品规格

## 公费用药目录限制级别字典OFFICIAL_DRUG_CATALOG_CLASS(新增)

|          |            |      |      |      |
|----------|------------|------|------|------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 序号     | SERIAL_NO  | N    | 1    |      |
| 编码     | CLASS_CODE | C    | 10   |      |
| 名称     | CLASS_NAME | C    | 20   |      |

主键：CLASS_CODE

## 过敏药品字典 ALERGY_DRUGS_DICT

|            |                   |      |      |      |
|------------|-------------------|------|------|------|
| 中文名称   | 字段名            | 类型 | 长度 | 说明 |
| 过敏药代码 | ALERGY_DRUGS_CODE | VAR2 | 20   |      |
| 过敏药名称 | ALERGY_DRUGS_NAME | VAR2 | 50   |      |
| 拼音码     | INPUT_CODE        | VAR2 | 25   |      |
| 五笔码     | INPUT_CODE_WB     | VAR2 | 25   |      |

PRIMARY KEY (ALERGY_DRUGS_NAME)

## 质控反馈信息字典QC_MSG_DICT

|              |               |      |      |                                |
|--------------|---------------|------|------|--------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                           |
| 序号         | SERIAL_NO     | N    | 4    | 质量信息编号                   |
| 分类         | QC_MSG_CODE   | C    | 4    | 问题类别描述                   |
| 信息         | QA_EVENT_TYPE | C    | 16   | 信息名称                       |
| 扣分         | MESSAGE       | C    | 80   | 质量扣分                       |
| 输入码       | SCORE         | N    | 2    |                                |
|              | INPUT_CODE    | C    | 8    |                                |
| 扣分类型     | SCORE_TYPE    | C    | 1    | 例在院和出院病例打分的标准不同 |

注释：此表用于定义质量反馈信息的问题说明。

主键：序号

#  费用

## 价表 PRICE_LIST

|                        |                    |      |      |                                                                                                                                              |
|------------------------|--------------------|------|------|----------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称           | 字段名             | 类型 | 长度 | 说明                                                                                                                                         |
| 项目分类               | ITEM_CLASS         | C    | 1    | 本系统定义，见6.10价表项目分类字典。非空                                                                                                     |
| 项目代码               | ITEM_CODE          | C    | 20   | 非空                                                                                                                                         |
| 项目名称               | ITEM_NAME          | C    | 100  | 项目的标准名称。非空                                                                                                                         |
| 项目规格               | ITEM_SPEC          | C    | 50   | 药品规格、器械材料规格                                                                                                                       |
| 单位                   | UNITS              | C    | 8    | 指计价单位，如：’片’，’针’，’人次’，’部位’等。见6.4计价单位字典                                                                              |
| 价格                   | PRICE              | N    | 9,3  | 标准价格，可对应全费价。非空                                                                                                                 |
| 优惠价格               | PREFER_PRICE       | N    | 9,3  | 可对应自费价。非空                                                                                                                           |
| 外宾价格               | FOREIGNER_PRICE    | N    | 9,3  |                                                                                                                                              |
| 执行科室               | PERFORMED_BY       | C    | 8    | 执行科室代码,当为\*时，表示有两个以上执行科室，如一个检查项目。当为空时，表示为各科都执行的项目，如静滴等普通治疗项目。                      |
| 费别屏蔽标志           | FEE_TYPE_MASK      | N    | 1    | 通常情况下，按照费别，各种项目统一原则收费或优惠。特殊项目不按费别收费。此项为1表示此收费项目不考虑费别按规定价格收费，0表示按费别收费。非空 |
| 对应的住院收据费用分类 | CLASS_ON_INP_RCPT  | C    | 1    | 此项目对住院病人在收据中应归属的费用类别；非空；见6.13住院收据费用分类字典；使用代码。                                                       |
| 对应的门诊收据费用分类 | CLASS_ON_OUTP_RCPT | C    | 1    | 此项目对门诊病人在收据中应归属的费用类别，见6.12门诊收据费用分类字典；非空；使用代码。                                                       |
| 对应的核算项目分类     | CLASS_ON_RECKONING | C    | 10   | 此项目在经济核算中应归属的费用类别；非空；见6.14核算项目分类字典；使用代码。                                                                 |
| 对应的会计科目         | SUBJ_CODE          | C    | 3    | 此项目收入归属的会计科目；非空；见6.15会计科目字典，使用代码。                                                                               |
| 对应的病案首页费用分类 | CLASS_ON_MR        | C    | 4    | 此项目对应住院病人在病案首页中应归属的费用类别；非空；使用规范名称，见6.11病案首页费用分类字典。                                             |
| 备注                   | MEMO               | C    | 40   | 用于定价条件说明                                                                                                                             |
| 起用日期               | START_DATE         | D    |      | 执行日期含起用日期当天                                                                                                                       |
| 停止日期               | STOP_DATE          | D    |      | 执行日期含停止日期当天                                                                                                                       |
| 操作员                 | OPERATOR           | C    | 8    | 操作员姓名                                                                                                                                   |
| 录入日期及时间         | ENTER_DATE         | D    |      | 非空                                                                                                                                         |
|                        | HIGH_PRICE         | N    | 10,4 |                                                                                                                                              |
| 物价码                 | material_code      | c    | 20   |                                                                                                                                              |
| 价格变更原因           | Changed_memo       | v    | 40   | 价格变更原因包括调价和停用等都可以录入保存原因';                                                                                             |

注释：所有收费项目的价格全部存放在此表中，包括药品、检查、化验、手术、治疗、材料等。此表记录了价格的变动历史，每次调价，都停止该项目的原有价格，重新生成一条新的价格记录。价格记录只能追加，不能删除和修改。用户定义，由价表管理子系统负责维护。

主键：项目分类、项目代码、项目规格、单位、起用日期。

上述价表中包含了历史价格，为便于使用，系统定义当前价表视图，条件为

SYSDATE \>= start_date AND ( SYSDATE \< stop_date OR stop_date IS NULL )

## 当前价表 CURRENT_PRICE_LIST

|                        |                    |      |      |                      |
|------------------------|--------------------|------|------|----------------------|
| 字段中文名称           | 字段名             | 类型 | 长度 | 说明                 |
| 项目分类               | ITEM_CLASS         | C    | 1    | 所有字段均对应原名称 |
| 项目代码               | ITEM_CODE          | C    | 20   |                      |
| 项目名称               | ITEM_NAME          | C    | 100  |                      |
| 项目规格               | ITEM_SPEC          | C    | 50   |                      |
| 单位                   | UNITS              | C    | 8    |                      |
| 价格                   | PRICE              | N    | 9,3  |                      |
| 优惠价格               | PREFER_PRICE       | N    | 9,3  |                      |
| 外宾价格               | FOREIGNER_PRICE    | N    | 9,3  |                      |
| 执行科室               | PERFORMED_BY       | C    | 8    |                      |
| 费别屏蔽标志           | FEE_TYPE_MASK      | N    | 1    |                      |
| 对应的住院收据费用分类 | CLASS_ON_INP_RCPT  | C    | 1    |                      |
| 对应的门诊收据费用分类 | CLASS_ON_OUTP_RCPT | C    | 1    |                      |
| 对应的核算项目分类     | CLASS_ON_RECKONING | C    | 10   |                      |
| 对应的会计科目         | SUBJ_CODE          | C    | 3    |                      |
| 对应的病案首页费用分类 | CLASS_ON_MR        | C    | 4    |                      |
| 备注                   | MEMO               | C    | 40   |                      |
| 操作员                 | OPERATOR           | C    | 8    |                      |
| 录入日期及时间         | ENTER_DATE         | D    |      |                      |

## 价表项目分类与其他分类对照表 ITEM_CLASS_VS_OTHER_CLASS

|                        |                    |      |      |                    |
|------------------------|--------------------|------|------|--------------------|
| 字段中文名称           | 字段名             | 类型 | 长度 | 说明               |
| 项目分类               | ITEM_CLASS         | C    | 1    | ITEM_CLASS         |
| 项目代码               | ITEM_CODE          | C    | 20   | ITEM_CODE          |
| 对应的住院收据费用分类 | CLASS_ON_INP_RCPT  | C    | 1    | CLASS_ON_INP_RCPT  |
| 对应的门诊收据费用分类 | CLASS_ON_OUTP_RCPT | C    | 1    | CLASS_ON_OUTP_RCPT |
| 对应的核算项目分类     | CLASS_ON_RECKONING | C    | 10   | CLASS_ON_RECKONING |
| 对应的会计科目         | SUBJ_CODE          | C    | 3    | SUBJ_CODE          |
| 对应的病案首页费用分类 | CLASS_ON_MR        | C    | 4    | CLASS_ON\_ MR      |

## 价表项目名称字典 PRICE_ITEM_NAME_DICT

|              |               |      |      |                                             |
|--------------|---------------|------|------|---------------------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                                        |
| 项目分类     | ITEM_CLASS    | C    | 1    | 对应于价表项目的分类，见6.8价表项目分类字典 |
| 项目名称     | ITEM_NAME     | C    | 100  | 每个价表项目可有多个名称或别名              |
| 项目代码     | ITEM_CODE     | C    | 20   | 该名称对应的价表项目代码                    |
| 正名标志     | STD_INDICATOR | N    | 1    | 1-正名 0-别名，每个项目只能有一个正名       |
| 输入码       | INPUT_CODE    | C    | 8    | 推荐使用拼音词头                            |
| 停用标记     | STOP_FLAG     | N    | 1    |                                             |
| 五笔码       | INPUT_CODE_WB | C    | 8    |                                             |

注释：此表收集了价表项目的各种名称，用于价表项目输入，如价表管理和门诊收费等直接按价表项目输入的场合。这些名称如同价表项目一样，可能不同于临床操作的名称。用户定义。

主键：项目分类、项目代码。

## 计价单位字典 BILL_UNITS_DICT

|              |                 |      |      |                                |
|--------------|-----------------|------|------|--------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                           |
| 序号         | SERIAL_NO       | N    | 2    | 此序号反映了项目分类的排列次序 |
| 计价单位代码 | BILL_UNITS_CODE | C    | 2    | 非空                           |
| 计价单位名称 | BILL_UNITS_NAME | C    | 8    | 如人次、片、支、部位等。       |
| 输入码       | INPUT_CODE      | C    | 8    |                                |

注释：本系统定义。

主键：计价单位名称。

## 收费系数字典 CHARGE_PRICE_SCHEDULE

|                      |                          |      |      |                                           |
|----------------------|--------------------------|------|------|-------------------------------------------|
| 字段中文名称         | 字段名                   | 类型 | 长度 | 说明                                      |
| 费别                 | CHARGE_TYPE              | C    | 8    | 根据需要定义。见1.9费别字典。非空         |
| 收费系数分子         | PRICE_COEFF_NUMERATOR    | N    | 2    | 非空                                      |
| 收费系数分母         | PRICE_COEFF_DENOMINATOR  | N    | 2    | 非空                                      |
| 适用特殊收费项目标志 | CHARGE_SPECIAL_INDICATOR | N    | 1    | 该费别是否适用特殊收费项目0-不适用 1-适用 |

注释：此表反映不同费别各种费用的优惠系数。用户定义。

主键：费别。

## 价表项目执行科室 PERFORM_DEPT

|              |              |      |      |                                           |
|--------------|--------------|------|------|-------------------------------------------|
| 字段中文名称 | 字段名       | 类型 | 长度 | 说明                                      |
| 价表项目分类 | ITEM_CLASS   | C    | 1    | 非空                                      |
| 价表项目代码 | ITEM_CODE    | C    | 20   | 非空                                      |
| 执行科室     | PERFORMED_BY | C    | 8    | 使用代码，由用户定义，见2.6科室字典。非空 |

注释：此表反映价表项目与执行科室之间的关系。允许一个项目对应有多个执行科室。通过本表，可为用户输入执行科室时，提供选择方便。用户定义。

内容长期保存。

## 临床诊疗项目与价表项目对照表 CLINIC_VS_CHARGE

|                  |                   |      |      |                                                                              |
|------------------|-------------------|------|------|------------------------------------------------------------------------------|
| 字段中文名称     | 字段名            | 类型 | 长度 | 说明                                                                         |
| 临床诊疗项目类别 | CLINIC_ITEM_CLASS | C    | 1    | 见表4.34                                                                     |
| 临床诊疗项目代码 | CLINIC_ITEM_CODE  | C    | 10   |                                                                              |
| 对应价表项目序号 | CHARGE_ITEM_NO    | N    | 2    | 每个临床诊疗项目对应的价表项目从1开始顺序排列                                |
| 对应价表项目分类 | CHARGE_ITEM_CLASS | C    | 1    | 如果此项与价表项目代码为空，表示该操作不收费                                 |
| 对应价表项目代码 | CHARGE_ITEM_CODE  | C    | 20   |                                                                              |
| 对应价表项目规格 | CHARGE_ITEM_SPEC  | C    | 50   | 若此项为空，表示规格不确定                                                   |
| 对应价表项目数量 | AMOUNT            | N    | 4    | 一个临床项目可以需要多个同样的价表项目，如材料。当此项为空时，表示由用户确定 |
| 对应价表项目单位 | UNITS             | C    | 8    | 上述数量对应的单位                                                           |
| 后台记费规则     | BACKBILL_RULE     | var  | 10   | 将增加一个默认后台划价规则，为后台划价提供划价记费依据                       |

注释：此表用于描述医嘱中涉及的临床操作与收费价表项目之间的对应关系，用于医嘱的自动划价。该表中记录的临床诊疗项目包括药品、检查、治疗、护理、膳食等各种类别。每个临床诊疗项目可以对应多个不同的收费项目。对不收费的项目，在该表中保留一条记录，其对应的收费项目为空。如果医嘱中的某个临床项目在此表中得不到对应，表示需要手工划价。对应关系由划价员搜集确定。用户定义。

此表内容长期保存。

主键：临床诊疗项目类别、临床诊疗项目代码、对应价表项目序号。

## 医嘱附加计价项目字典 EXTRA_COSTS_DICT

|              |                  |      |      |      |
|--------------|------------------|------|------|------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明 |
|              | ORDER_CONT       | C    | 40   |      |
|              | EXTRA_ITEM_NO    | N    | 2    |      |
|              | EXTRA_ITEM_CLASS | C    | 1    |      |
|              | EXTRA_ITEM_CODE  | C    | 10   |      |
|              | EXTRA_ITEM_SPEC  | C    | 20   |      |

此表已取消。

## 价表项目分类字典 BILL_ITEM_CLASS_DICT

|              |            |      |      |                                |
|--------------|------------|------|------|--------------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                           |
| 序号         | SERIAL_NO  | N    | 2    | 此序号反映了项目分类的排列次序 |
| 项目分类代码 | CLASS_CODE | C    | 1    | 非空                           |
| 项目分类名称 | CLASS_NAME | C    | 10   | 非空                           |
| 输入码       | INPUT_CODE | C    | 8    |                                |

注释：将所有的收费项目分为固定的类别，本系统定义。

## 病案首页费用分类字典 MR_FEE_CLASS_DICT

|              |                   |      |      |                      |
|--------------|-------------------|------|------|----------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                 |
| 序号         | SERIAL_NO         | N    | 2    | 说明此费用的排列顺序 |
| 费用分类代码 | MR_FEE_CLASS_CODE | C    | 1    |                      |
| 费用分类名称 | MR_FEE_CLASS_NAME | C    | 4    |                      |
| 输入码       | INPUT_CODE        | C    | 8    |                      |
| 费用分类描述 | MR_FEE_CLASS_DESC | var  | 50   |                      |

注释：此表根据病案首页在住院收费子系统中设置。用户定义。

主键：费用分类代码。

## 门诊收据费用分类字典 OUTP_RCPT_FEE_DICT

|              |                |      |      |                                      |
|--------------|----------------|------|------|--------------------------------------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明                                 |
| 序号         | SERIAL_NO      | N    | 2    | 此序号反映了费用分类在收据中排列顺序 |
| 费用分类代码 | FEE_CLASS_CODE | C    | 1    | 门诊收据分类代码，由用户定义         |
| 费用分类名称 | FEE_CLASS_NAME | C    | 10   |                                      |
| 输入码       | INPUT_CODE     | C    | 8    |                                      |

注释：此表用于定义门诊医疗收据中的费用分类。用户定义。

主键：费用分类代码。

## 住院收据费用分类字典 INP_RCPT_FEE_DICT

|              |                |      |      |                                        |
|--------------|----------------|------|------|----------------------------------------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明                                   |
| 序号         | SERIAL_NO      | N    | 2    | 此序号反映了费用分类在收据中排列的次序 |
| 费用分类代码 | FEE_CLASS_CODE | C    | 1    | 非空                                   |
| 费用分类名称 | FEE_CLASS_NAME | C    | 10   | 非空                                   |
| 输入码       | INPUT_CODE     | C    | 8    |                                        |

注释：此表用于定义收据中费用项目，用户定义。

主键：项目分类代码。

## 核算项目分类字典 RECK_ITEM_CLASS_DICT

|              |            |      |      |                            |
|--------------|------------|------|------|----------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO  | N    | 2    | 此序号反映了项目的排列次序 |
| 项目分类代码 | CLASS_CODE | C    | 10   | 非空                       |
| 项目分类名称 | CLASS_NAME | C    | 16   | 非空                       |
| 输入码       | INPUT_CODE | C    | 8    |                            |

注释：在经济核算时，需要将收入（或支出）按需要分类。此表记录其分类情况。用户定义。

主键：项目分类代码。

## 会计科目字典 TALLY_SUBJECT_DICT

|              |            |      |      |                            |
|--------------|------------|------|------|----------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO  | N    | 3    | 此序号反映了科目的排列次序 |
| 科目代码     | SUBJ_CODE  | C    | 4    | 非空                       |
| 科目名称     | SUBJ_NAME  | C    | 16   | 非空                       |
| 输入码       | INPUT_CODE | C    | 8    |                            |

注释：此表用于定义会计记帐中使用的科目种类。用户定义。

主键：科目代码。

## 支付方式字典 PAY_WAY_DICT

|                  |                   |      |      |                                                                |
|------------------|-------------------|------|------|----------------------------------------------------------------|
| 字段中文名称     | 字段名            | 类型 | 长度 | 说明                                                           |
| 序号             | SERIAL_NO         | N    | 1    | 此序号反映了项目的排列次序                                     |
| 支付方式代码     | PAY_WAY_CODE      | C    | 1    | 非空                                                           |
| 支付方式名称     | PAY_WAY_NAME      | C    | 8    | 非空                                                           |
| 记帐标志         | ACCTING_INDICATOR | N    | 1    | 反映该支付方式是否作为实收款进入会计记帐0-不进入记帐1-进入记帐 |
| 门诊病人适用标志 | OUTP_INDICATOR    | N    | 1    | 该支付方式是否适用于门诊病人0-不适用 1-适用                    |
| 住院病人适用标志 | INP_INDICATOR     | N    | 1    | 该支付方式是否适用于住院病人0-不适用 1-适用                    |
| 输入码           | INPUT_CODE        | C    | 8    |                                                                |
| 挂号使用标志     | REGIST_INDICATOR  | N    | 1    |                                                                |

注释：用户定义。

主键：支付方式名称。

## 预交金操作类型字典 PREPAY_TRANS_TYPE_DICT

|              |                    |      |      |                            |
|--------------|--------------------|------|------|----------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO          | N    | 1    | 此序号反映了项目的排列次序 |
| 操作类型代码 | TRANSACT_TYPE_CODE | C    | 1    |                            |
| 操作类型名称 | TRANSACT_TYPE_NAME | C    | 4    |                            |
| 输入码       | INPUT_CODE         | C    | 8    |                            |

注释：本系统定义。

## 结算操作类型字典 SETTLE_TRANS_TYPE_DICT

|              |                    |      |      |                            |
|--------------|--------------------|------|------|----------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO          | N    | 1    | 此序号反映了项目的排列次序 |
| 操作类型代码 | TRANSACT_TYPE_CODE | C    | 1    |                            |
| 操作类型名称 | TRANSACT_TYPE_NAME | C    | 4    |                            |
| 输入码       | INPUT_CODE         | C    | 8    |                            |

注释：本系统定义。

## 支票标识字典 CHECK_LABEL_DICT

|              |                  |      |      |                            |
|--------------|------------------|------|------|----------------------------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明                       |
| 序号         | SERIAL_NO        | N    | 1    | 此序号反映了项目的排列次序 |
| 支票标识代码 | CHECK_LABEL_CODE | C    | 1    |                            |
| 支票标识名称 | CHECK_LABEL_NAME | C    | 4    |                            |
| 输入码       | INPUT_CODE       | C    | 8    |                            |

注释：本系统定义。

## 收费特殊项目字典 CHARGE_SPECIAL_ITEM_DICT

|              |                        |      |      |                                                                                                            |
|--------------|------------------------|------|------|------------------------------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名                 | 类型 | 长度 | 说明                                                                                                       |
| 费别         | CHARGE_TYPE            | C    | 8    |                                                                                                            |
| 项目类别     | ITEM_CLASS             | C    | 1    | 按价表项目类别分类，使用代码，见6.8价表项目分类字典                                                        |
| 项目代码     | ITEM_CODE              | C    | 20   | 指价表定义的收费项目代码，可以使用统配符’\*’表示项目类别定义的所有项目                                     |
| 项目规格     | ITEM_SPEC              | C    | 50   | 指价表定义的收费项目规格，可以使用统配符’\*’表示某一项目的所有规格                                         |
| 收费系数分子 | PROPORTION_NUMERATOR   | N    | 3    | 由该系数的分子与分母之比确定此项目的应收费                                                                 |
| 收费系数分母 | PROPORTION_DENOMINATOR | N    | 3    |                                                                                                            |
| 免除最高限额 | FREE_LIMIT             | N    | 8,2  | 由标准价格减去本限额确定此项目的应收费。如果为空，应收费按上述比例计算；如果不为空，应收费按实际免除额计算 |

注释：此表用于定义不能按费别系数字典规定的正常系数收费的项目，与收费特殊项目排斥字典定义互补。在收费特殊项目排斥字典中定义的项目，计算方法优先；不在其中定义的项目，在本表中规定的项目，按本表执行；如果收费项目在本表中也不存在，按费别系数字典规定的系数执行。当项目为一类项目时，项目代码或项目规格使用统配符表示。记录之间定义的项目范围不允许有交叉或重复。

主键：费别、项目类别、项目代码、项目规格。

## 收费特殊项目排斥字典 CHARGE_SPECIAL_EXCEPT_DICT

|              |                        |      |      |                                                                                                            |
|--------------|------------------------|------|------|------------------------------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名                 | 类型 | 长度 | 说明                                                                                                       |
| 费别         | CHARGE_TYPE            | C    | 8    |                                                                                                            |
| 项目类别     | ITEM_CLASS             | C    | 1    | 按价表项目类别分类，使用代码，见6.8价表项目分类字典                                                        |
| 项目代码     | ITEM_CODE              | C    | 20   | 指价表定义的收费项目代码，可以使用统配符’\*’表示项目类别定义的所有项目                                     |
| 项目规格     | ITEM_SPEC              | C    | 50   | 指价表定义的收费项目规格，可以使用统配符’\*’表示某一项目的所有规格                                         |
| 收费系数分子 | PROPORTION_NUMERATOR   | N    | 3    | 由该系数的分子与分母之比确定此项目的应收费                                                                 |
| 收费系数分母 | PROPORTION_DENOMINATOR | N    | 3    |                                                                                                            |
| 免除最高限额 | FREE_LIMIT             | N    | 8,2  | 由标准价格减去本限额确定此项目的应收费。如果为空，应收费按上述比例计算；如果不为空，应收费按实际免除额计算 |

注释：此表用于定义特殊项目中计算方法例外情况，与收费特殊项目定义互补，本表定义计算方法优先。当项目为一类项目时，项目代码或项目规格使用统配符表示。记录之间定义的项目范围不允许有交叉或重复。

主键：费别、项目类别、项目代码、项目规格。

## 收费部门分组字典 BILLING_GROUP_DICT

|              |                 |      |      |                              |
|--------------|-----------------|------|------|------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                         |
| 序号         | SERIAL_NO       | N    | 2    | 反映部门排列的次序           |
| 部门代码     | GROUP_CODE      | C    | 8    |                              |
| 部门名称     | GROUP_NAME      | C    | 20   |                              |
| 起始窗口号   | START_WINDOW_NO | C    | 2    | 该部门使用的收费窗口号最小值 |
| 截止窗口号   | STOP_WINDOW_NO  | C    | 2    | 该部门使用的收费窗口号最大值 |

注释：当医院包含独立统计的多个收费部门时，通过统一排列的收费窗口号区间予以划分。此表记录了收费部门分组与收费窗口号的对应关系。各部门窗口号区间不允许交叉。用户定义。

主键：序号。

## 费用模板主记录 BILL_PATTERN_MASTER

|              |               |      |      |                                                  |
|--------------|---------------|------|------|--------------------------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                                             |
| 序号         | SERIAL_NO     | N    | 4    | 反映部门排列的次序                               |
| 模板名称     | PATTERN_NAME  | C    | 40   | 唯一标识一个模板，可以为检验单名称、计价单名称等 |
| 输入码       | INPUT_CODE    | C    | 8    |                                                  |
| 五笔码       | INPUT_CODE_WB | C    | 8    |                                                  |
| 部门代码     | DEPT_CODE     | C    | 8    |                                                  |

注释：对于成组的收费项目，定义一个模板，便于收费人员快速录入一组项目。该表与费用模板明细记录一起构成模板定义。用户定义。

主键：模板名称,部门代码。

## 费用模板明细记录 BILL_PATTERN_DETAIL

|              |              |      |      |                                                  |
|--------------|--------------|------|------|--------------------------------------------------|
| 字段中文名称 | 字段名       | 类型 | 长度 | 说明                                             |
| 模板名称     | PATTERN_NAME | C    | 40   | 唯一标识一个模板，可以为检验单名称、计价单名称等 |
| 项目序号     | ITEM_NO      | N    | 3    | 唯一标识一个模板内的项目                         |
| 项目分类     | ITEM_CLASS   | C    | 1    | 价表定义的项目分类代码，见6.8价表项目分类字典    |
| 项目代码     | ITEM_CODE    | C    | 20   | 价表项目代码                                     |
| 项目规格     | ITEM_SPEC    | C    | 50   |                                                  |
| 单位         | UNITS        | C    | 8    | 计价单位                                         |
| 数量         | AMOUNT       | N    | 6,2  | 默认数量                                         |
| 执行科室     | PERFORMED_BY | C    | 8    | 该项目的实际执行科室                             |
| 部门代码     | Dept_code    | c    | 8    |                                                  |

注释：此表为费用模板的项目定义。用户定义。

主键：模板名称、项目序号,部门代码。

## 特殊号别价格字典SPECIAL_CLINIC_PRICE(不使用)

|          |             |      |      |      |
|----------|-------------|------|------|------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明 |
|          | CLINIC_TYPE | C    | 8    |      |
|          | PRICE       | N    | 5,2  |      |

## 号类收费设置表 CLINIC_TYPE_CHARGE_DICT(新增)

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 29%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 35%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>号类</td>
<td>CLINIC_TYPE</td>
<td>V2</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>就诊类别</td>
<td>REGIST_TYPE</td>
<td>V2</td>
<td>8</td>
<td><p>初诊</p>
<p>复诊</p>
<p>急诊</p></td>
</tr>
<tr class="even">
<td>费用类别</td>
<td>CHARGE_ITEM</td>
<td>V2</td>
<td>20</td>
<td><p>挂号费</p>
<p>诊疗费</p>
<p>其它费</p></td>
</tr>
<tr class="odd">
<td>计算类型</td>
<td>CALCULATE_TYPE</td>
<td>V2</td>
<td>1</td>
<td><p>0 按金额</p>
<p>1 按比例（%）</p></td>
</tr>
<tr class="even">
<td>计算值</td>
<td>CALCULATE_VALUE</td>
<td>N</td>
<td>4,2</td>
<td></td>
</tr>
</tbody>
</table>

主键:此表主键为号类.就诊类别.费用类别

## 挂号支付方式字典REGIST_PAY_DICT

|                |           |      |      |                          |
|----------------|-----------|------|------|--------------------------|
| 中文名称       | 字段名    | 类型 | 长度 | 说明                     |
| 代码           | CARD_CODE | C    | 1    |                          |
| 名称           | CARD_NAME | C    | 16   |                          |
| 是否需要交现金 | PAY_MONEY | C    | 1    | 1确认拿号时交现金，0不交 |

注释：此表定义支付卡类型，用户定义。

## 治疗类别字典CURE_CLASS_DICT(不使用)

|          |                 |      |      |      |
|----------|-----------------|------|------|------|
| 中文名称 | 字段名          | 类型 | 长度 | 说明 |
|          | CURE_CLASS_CODE | C    | 1    |      |
|          | CURE_CLASS_NAME | C    | 6    |      |
|          | INPUT_CODE      | C    | 8    |      |
|          | CURE_DEPT       | C    | 10   |      |

## 币种字典MONEY_DICT

|          |           |      |      |      |
|----------|-----------|------|------|------|
| 中文名称 | 字段名    | 类型 | 长度 | 说明 |
|          | SERIAL_NO | N    | 2    |      |
|          | CODE      | C    | 2    |      |
|          | CURRENCY  | C    | 10   |      |
|          | MEMO      | C    | 100  |      |

## OUTP_RCPT_FEE_FACTDICT

|          |              |      |      |      |
|----------|--------------|------|------|------|
| 中文名称 | 字段名       | 类型 | 长度 | 说明 |
|          | FEE_FACTCODE | C    | 4    |      |
|          | FEE_FACTNAME | C    | 50   |      |

## OUTP_RCPT_FEE_VS_FACTCODE

|          |                |      |      |      |
|----------|----------------|------|------|------|
| 中文名称 | 字段名         | 类型 | 长度 | 说明 |
|          | FEE_CLASS_CODE | C    | 4    |      |
|          | FEE_FACTCODE   | C    | 4    |      |

## PAY_STYLE_DICT

|          |           |      |      |      |
|----------|-----------|------|------|------|
| 中文名称 | 字段名    | 类型 | 长度 | 说明 |
|          | SERIAL_NO | N    | 2    |      |
|          | CODE      | C    | 2    |      |
|          | PAY_STYLE | C    | 10   |      |
|          | MEMO      | C    | 100  |      |

#  系统维护

## 病人标识号引用表 PATIENT_ID_REF

|              |                     |      |      |                                            |
|--------------|---------------------|------|------|--------------------------------------------|
| 字段中文名称 | 字段名              | 类型 | 长度 | 说明                                       |
| 序号         | SERIAL_NO           | N    | 3    | 反映引用表在将来修改病人标识号时的修改次序 |
| 表名         | TABLE_NAME          | C    | 32   |                                            |
| 字段名       | COLUMN_NAME         | C    | 32   | 病人标识号的字段名                         |
| 相关字段名   | RELATED_COLUMN_NAME | C    | 32   | 指改动病人标识号，需要修改的其他字段       |
| 操作类型     | OPER_TYPE           | C    | 1    | U-直接更新 D-删除该记录                    |

注释：此表用于说明与病人标识号有关的表与字段信息，由数据库管理员负责初始化和维护，此表信息长期在线保存。

## 应用程序记录 APPLICATIONS

|              |             |      |      |                        |
|--------------|-------------|------|------|------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                   |
| 应用程序名   | APPLICATION | C    | 16   | 统一分配的应用程序名称 |
| 程序描述     | DESCRIPTION | C    | 80   | 程序功能描述           |

注释：本表记录需由系统集中授权管理的应用程序。

## 应用程序权限记录 APP_GRANTS

|              |             |      |      |                                                                            |
|--------------|-------------|------|------|----------------------------------------------------------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                                                                       |
| 应用程序名   | APPLICATION | C    | 16   | 本系统为每个需要进行用户使用权限控制的程序统一分配一个唯一的名字           |
| 用户标识     | USER_ID     | C    | 4    | 用户记录中分配的用户标识，该用户对对应的应用程序拥有用户权限字段定义的权限 |
| 用户权限     | CAPABILITY  | C    | 30   | 用户拥有的权限等级，由系统管理员根据每个应用程序开发者要求分别设置         |

注释：本表描述应用程序与用户之间的权限关系。本系统通过本表提供应用程序的访问控制机制，用于对数据库提供的数据访问控制进行补充，两者一起构成本系统的安全机制。应用程序通过此表设置的权限在程序中自行校验。不要求所有的应用程序都进行用户访问控制，仅需要进行控制的程序才使用此表。本表记录由系统管理员通过用户控制子系统建立和修改。

## 联机帮助信息 HELP_MSG

|              |             |      |      |                                                                              |
|--------------|-------------|------|------|------------------------------------------------------------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                                                                         |
| 应用程序名   | APPLICATION | C    | 16   | 每个应用程序使用一个唯一的名字                                               |
| 窗口号       | WINDOW_ID   | C    | 16   | 帮助信息所对应的窗口或屏幕。在一个应用程序内部使用唯一的窗口号来标识每个窗口 |
| 帮助信息     | MESSAGES    | C    | 32K  | 关于窗口的操作说明，正文格式                                                 |

注释：本表定义了以窗口为中心的帮助信息，供各应用程序使用。

## 字典信息 METADICT

|              |                   |      |      |              |
|--------------|-------------------|------|------|--------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明         |
| 字典名       | TABLE_NAME        | C    | 30   | 字典表名     |
| 字典描述     | TABLE_DESCRIPTION | C    | 30   | 字典内容说明 |

注释：此表定义了系统中所包含的各类字典，由字典维护程序使用。

## 计算机站点 CLIENT_INSTALLATION

|              |             |      |      |                                                              |
|--------------|-------------|------|------|--------------------------------------------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                                                         |
| 机器名       | CLIENT_NAME | C    | 32   | 客户机在网络上分配的名字，唯一标识一台机器，与IP地址一一对应 |
| IP地址       | IP_ADDRESS  | C    | 32   | 该机器使用的IP地址                                           |
| 应用程序     | APPLICATION | C    | 16   | 该机器运行的主要应用程序，见7.2应用程序记录                  |
|              |             |      |      |                                                              |
| 科室         | LOCATION    | C    | 8    | 该机器安装的科室代码                                         |
| 注册时间     | REG_TIME    | date |      | (程序一登陆后写入                                            |
| 在线标志     | USEING_FLAG | Var2 |      | Y,在线，N 不在线（）                                         |

注释：此表记录了系统安装的计算机站点。

主键：机器名,科室

## 组表SECURITY_GROUPINGS

|          |             |      |      |          |
|----------|-------------|------|------|----------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明     |
| 组名     | GROUP_NAME  | C    | 16   | Not null |
| 应用程序 | APPLICATION | V2   | 16   |          |
| 备注     | MEMO        | V2   | 200  |          |
|          | USER_NAME   | C    | 16   |          |

## 组对应的权限表 SECURITY_INFO

|            |              |      |      |      |
|------------|--------------|------|------|------|
| 中文名称   | 字段名       | 类型 | 长度 | 说明 |
| 应用程序   | APPLICATIONG | V2   | 32   |      |
| 窗口，菜单 | WINDOW       | C    | 64   |      |
| 控件       | CONTROL      | C    | 128  |      |
| 组名       | GROUP_NAME   | V2   | 16   |      |
| 状态       | STATUS       | C    | 1    |      |

**primarykey** (APPLICATION,WINDOW,CONTROL,GROUP_NAME)

## 用户信息表 SECURITY_USERS

|            |              |      |      |          |
|------------|--------------|------|------|----------|
| 中文名称   | 字段名       | 类型 | 长度 | 说明     |
| 系统名称   | NAME         | C    | 16   | Not null |
| 用户姓名   | DESCRIPTION  | C    | 32   | Not null |
|            | PRIORITY     | N    | 22   |          |
|            | USER_TYPE    | N    | 22   |          |
| 组名       | Group_Name   | V2   | 16   |          |
| 应用程序名 | Applicationg | V2   | 32   |          |

## SECURITY_APPS

|          |             |      |      |      |
|----------|-------------|------|------|------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明 |
|          | APPLICATION | C    | 32   |      |
|          | DESCRIPTION | C    | 64   |      |

**primarykey** (APPLICATION)

## 控件模板表 SECURITY_TEMPLATE

|              |                |      |      |      |
|--------------|----------------|------|------|------|
| 中文名称     | 字段名         | 类型 | 长度 | 说明 |
| 应用程序     | APPLICATION    | V2   | 32   |      |
| 窗口 菜单    | WINDOW         | V2   | 64   |      |
| 控件         | CONTROL        | V2   | 256  |      |
| 控件汉字名称 | DESCRIPTION    | V2   | 254  |      |
| 控件类型     | OBJECT_TYPE    | V2   | 24   |      |
| 控件的上一级 | CONTROL_parent | V2   | 256  |      |
| 序号         | Item_no        | n    |      |      |
| 备注         | MEMO           | V2   | 256  |      |

**primarykey** (APPLICATION,WINDOW,CONTROL,ITEM_NO)

## 应用角色APP_ROLES

|          |             |      |      |      |
|----------|-------------|------|------|------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明 |
| 模块名称 | APPLICATION | C    | 16   |      |
| 角色     | ROLE        | C    | 32   |      |

## 应用参数表信息APP_CONFIGER_BASEINFO(新增)

|            |                 |      |      |                            |
|------------|-----------------|------|------|----------------------------|
| 中文名称   | 字段名          | 类型 | 长度 | 说明                       |
| 模块名称   | APP_NAME        | C    | 10   | 反映每个子系统的应用名称   |
| 编号       | PARAMETER_NO    | N    | 3    | 反映每个应用的参数顺序     |
| 参数名称   | PARAMETER_NAME  | C    | 100  | 针对每个应用的具体参数名称 |
| 设置参数值 | PARAINIT_VALUE  | C    | 500  | 每个参数的初始值           |
| 全部参数   | PARAMETER_SCOPE | C    | 500  | 每个参数的取值范围         |
| 说明       | EXPLANATION     | C    | 500  | 每个参数的解释说明         |

系统定义表

（注释：此表用于记录整个系统和每个应用需要配置的参数及其取值范围

主键： app_name, parameter_no, parameter_name

## 应用参数设置表APP_CONFIGER_PARAMETER(新增)

|            |                 |      |      |                            |
|------------|-----------------|------|------|----------------------------|
| 中文名称   | 字段名          | 类型 | 长度 | 说明                       |
| 模块名称   | APP_NAME        | C    | 10   | 反映每个子系统的应用名称   |
| 部门代码   | DEPT_CODE       | C    | 8    | 此参数适用的科室单元       |
| 操作员号   | EMP_NO          | C    | 10   | 对应staff_dict中emp_no字段 |
| 参数名称   | PARAMETER_NAME  | C    | 100  | 针对每个应用的具体参数名称 |
| 设置参数值 | PARAMETER_VALUE | C    | 500  | 每个参数的初始值           |
| 位置       | position        | c    | 20   | 各个站点                   |

各个子系统配置后填写

主键：app_name, dept_code, emp_no,parameter_name

## AUTO_SETTING(不使用)

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
| ID号     | ID            | N    | 22   |      |
|          | MODULE        | C    | 20   |      |
|          | TYPE_NAME     | C    | 20   |      |
|          | TYPE_SETTING1 | C    | 10   |      |
|          | TYPE_VALUE1   | N    | 22   |      |
|          | TYPE_LENGTH1  | N    | 22   |      |
|          | TYPE_UPGRADE1 | N    | 22   |      |
|          | TYPE_SETTING2 | C    | 10   |      |
|          | TYPE_VALUE2   | N    | 22   |      |
|          | TYPE_LENGTH2  | N    | 22   |      |
|          | TYPE_UPGRADE2 | N    | 22   |      |

## 自动生成ID表AUTO_SETTING_ID

|                     |                     |          |      |      |
|---------------------|---------------------|----------|------|------|
| 中文名称            | 字段名              | 类型     | 长度 | 说明 |
| 序号                | SERIAL_NO           | N        | 22   |      |
| 类型名称            | TYPE_NAME           | C        | 20   |      |
| 病人ID开头变量      | ID_START_VALUE      | C        | 10   |      |
| 当前变量            | ID_CURRENTLY_VALUE  | N        | 22   |      |
| 变量长度            | ID_LENGTH           | N        | 22   |      |
| 是否自动升位        | ID_UPGRADE          | N        | 22   |      |
| 住院号开头变量      | INP_START_VALUE     | C        | 10   |      |
| 当前变量            | INP_CURRENTLY_VALUE | N        | 22   |      |
| 变量长度            | INP_LENGTH          | N        | 22   |      |
| 是否自动升位        | INP_UPGRADE         | N        | 22   |      |
| ID前头自定义SQL     | ID_SQL              | VARCHAR2 | 500  |      |
| 住院号前头自定义SQL | INP_SQL             | VARCHAR2 | 500  |      |

主键：serial_no

## 密码字典KEY_DICT

|          |              |      |      |      |
|----------|--------------|------|------|------|
| 中文名称 | 字段名       | 类型 | 长度 | 说明 |
| 程序代码 | PRODUCT_CODE | C    | 30   |      |
| 程序名称 | PRODUCT_NAME | C    | 30   |      |
| 密码     | KEY          | C    | 255  |      |

## 表字段解释说明TABLE_COLUMNS_SET

|          |                |      |      |      |
|----------|----------------|------|------|------|
| 中文名称 | 字段名         | 类型 | 长度 | 说明 |
| 所有者   | OWNER          | C    | 30   |      |
| 表名称   | TABLE_NAME     | C    | 30   |      |
| 字段名称 | COLUMN_NAME    | C    | 30   |      |
| 类型     | DATA_TYPE      | C    | 106  |      |
| 长度     | DATA_LENGTH    | N    | 22   |      |
| 描述     | DATA_PRECISION | N    | 22   |      |
| 范围     | DATA_SCALE     | N    | 22   |      |
| 非空     | NULLABLE       | C    | 1    |      |
| ID号     | COLUMN_ID      | N    | 22   |      |

## 表角色解释说明TABLE_ROLE_SET

|          |            |      |      |      |
|----------|------------|------|------|------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 角色名   | ROLE       | C    | 30   |      |
| 所有者   | OWNER      | C    | 30   |      |
| 表名称   | TABLE_NAME | C    | 30   |      |
| 权限     | PRIVILEGE  | C    | 40   |      |

## 表同义词解释说明TABLE_SYNONYM_SET

|          |         |      |      |      |
|----------|---------|------|------|------|
| 中文名称 | 字段名  | 类型 | 长度 | 说明 |
| 同义词名 | SYNAME  | C    | 30   |      |
| 创建者   | CREATER | C    | 30   |      |
| 表名称   | TNAME   | C    | 30   |      |
| 表类型   | TABTYPE | C    | 20   |      |

## 组权限表 SECURITY_INFO_PRG

|            |             |      |      |     |      |
|------------|-------------|------|------|-----|------|
| 中文名称   | 字段名      | 类型 | 长度 |     | 说明 |
| 应用程序名 | APPLICATION | V2   | 32   |     |      |
| 权限值     | RIGHT       | V2   | 64   |     |      |
| 组名       | GROUP_NAME  | V2   | 16   |     |      |
| 状态       | STATUS      | C    | 1    |     |      |

## 

## 数据窗口界面控制显示表 DATAWINDOW_UI_CONTROL

|                  |                     |          |      |                                                         |
|------------------|---------------------|----------|------|---------------------------------------------------------|
| 中文名           | 字段名              | 类型     | 长度 | 说明                                                    |
| 备注             | APP_NAME            | VARCHAR2 | 10   | 应用程序代码 \*代表所有应用                             |
| 科室             | DEPT_CODEO          | VARCHAR2 | 8    | '适用科室,\*代表全部'                                   |
| 人员代码         | EMP_NO              | VARCHAR2 | 10   | '适用人员\*代表全部'                                    |
| 布局名称         | layer_name          | VARCHAR2 | 128  | 布局名称，识别某种布局                                  |
| 显示风格存储类型 | STORAGE_TYPE        | VARCHAR2 |      | 显示风格存储类型: xml ,datasource,txt                   |
| 数据窗口类型     | processing_TYPE     | Number   | 2    | 数据窗口类型 1 表格 2 freeFrom 同datawindow的定义一样。 |
| 备注             | MEMO                | VARCHAR2 | 64   | 备注                                                    |
| 保存时间         | ENTER_DATE          | date     |      | 保存时间                                                |
| 布局描述         | DATAOBJECT_LAYER_DS | LONG RAW |      | 可以是语法，也可以是xml内容，同样也可以是文本内容       |

**primarykey**APP_NAME,layer_name, DEPT_CODE, EMP_NO

# 输入法

## 输入码类型 input_type

|                |            |      |      |          |
|----------------|------------|------|------|----------|
| 字段中文名称   | 字段名     | 类型 | 长度 | 说明     |
| 输入码类型代码 | INPUT_CODE | Var  | 2    | Not null |
| 输入码类型名称 | INPUT_NAME | Var  | 12   | Not null |

PRIMARY KEY (INPUT_CODE)

## 输入法配置 INPUT_SETTING

|              |             |      |      |                       |
|--------------|-------------|------|------|-----------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                  |
|              | DICT_TYPE   | Var  | 100  | 字典类型              |
|              | DATA_TABLE  | Var  | 100  | 表/视图               |
|              | DATA_COL    | Var  | 100  | 字段                  |
|              | INPUT_CODE  | Var  | 2    | 输入码类型字段        |
|              | DATA_TITLE  | Var  | 100  | 显示标题              |
|              | FLAG_SHOW   | Var  | 1    | 是否显示DEFAULT 'Y'   |
|              | SHOW_SORT   | n    |      | 显示顺序位            |
|              | FLAG_ISNAME | var  | 2    | 是否名称列DEFAULT 'N' |
|              | RESULT_SORT | n    |      | 对应结果顺序DEFAULT 0 |
|              | SHOW_WIDTH  | n    | 4    | 显示宽度              |

PRIMARY KEY (DICT_TYPE, DATA_COL)

## 输入法配置表 OUTER_CODING_CONFIG

|                |                     |      |      |                                                                                                                                                                                                                  |
|----------------|---------------------|------|------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称   | 字段名              | 类型 | 长度 | 说明                                                                                                                                                                                                             |
| 项目标识       | TOPIC               | C    | 8    | 为每种输入项目内容指定一个唯一标识，如对西药、检验、诊断分配不同的标识，该标识同时用于应用程序配置文件中输入法节的KEY值。由系统统一定义。                                                                        |
| 项目类别       | ITEM_CLASS          | C    | 4    | 指输入法针对的输入项目内容类别，如西药、检验、诊断等。该字段仅起到提示作用，并不唯一标识项目内容。如：治疗价表项目和治疗临床项目其类别可都为治疗。每类项目可以对应不同的输入方法。使用规范描述，本系统定义，见表 |
| 输入法         | CODING_SCHM         | C    | 4    | 输入方法的名称，用户定义，如拼音、角码等，与项目标识一起构成输入法配置的唯一索引                                                                                                                                 |
| 输入码长度     | OUTER_CODE_LENGTH   | N    | 2    | 输入词库文件中输入码字段的长度                                                                                                                                                                                   |
| 正文长度       | TEXT_LENGTH         | N    | 3    | 输入词库文件中项目正文字段的长度                                                                                                                                                                                 |
| 标准内码长度   | STD_CODE_LENGTH     | N    | 2    | 输入词库文件中项目对应的标准编码长度                                                                                                                                                                             |
| 输入词库文件名 | DICT_FILE_NAME      | C    | 16   | 该输入法使用的词库文件名称，不包括路径                                                                                                                                                                           |
| 更新日期及时间 | LAST_UPDT_DATE_TIME | D    |      | 输入词库文件的更新日期                                                                                                                                                                                           |

注释：此表反映整个系统使用的词库方式输入方法。允许一类项目使用多种输入方法，各类项目之间可以使用不同的输入法。每类项目的每种输入方法对应一个规定格式的输入词库文件。此表由系统管理员配置，由项目维护程序修改词库的更新日期。

## 输入码表 OUTER_CODE_DICT

|              |             |      |      |                                    |
|--------------|-------------|------|------|------------------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                               |
| 项目标识     | TOPIC       | C    | 8    | 对应于输入法配置表中的项目标识     |
| 项目名称     | ITEM_NAME   | C    | 40   | 输入项目的内容                     |
| 项目代码     | ITEM_CODE   | C    | 16   | 项目对应的标准代码                 |
| 输入法       | CODING_SCHM | C    | 4    | 输入法配置中规定的本类项目的输入法 |
| 输入码       | OUTER_CODE  | C    | 16   | 该项目名称对应的该种输入法的输入码 |

注释：此表维护整个系统所有使用词库方式输入的项目的各种输入法对应的输入码。由各自的项目维护程序负责更新。由该表可以生成各种输入词库文件。

## 层次输入法定义 CLASS_CODING_CONFIG

|                      |                   |      |      |                                                                                            |
|----------------------|-------------------|------|------|--------------------------------------------------------------------------------------------|
| 字段中文名称         | 字段名            | 类型 | 长度 | 说明                                                                                       |
| 输入项目             | ITEM              | C    | 8    | 标识输入内容类别，如药品、诊断等                                                           |
| 编码级数             | CODE_LEVEL        | N    | 1    | 代码分层总数                                                                               |
| 逐层编码表名         | WIZARD_TABLE_NAME | C    | 32   | 含逐层编码的数据库表名，当分层编码数据与底层编码数据同在一表中时，该表名与底层数据表名相同 |
| 逐层编码表代码字段名 | WIZARD_CODE_FIELD | C    | 32   | 表中项目层次代码字段名                                                                     |
| 逐层编码表名称字段名 | WIZARD_NAME_FIELD | C    | 32   | 表中项目中文名称字段名                                                                     |
| 逐层编码表过滤条件   | WIZARD_FILTER     | C    | 64   | 表中记录的过滤条件，比如项目类别限制                                                       |
| 底层数据表名         | DATA_TABLE_NAME   | C    | 32   | 含底层编码的数据库表名                                                                     |
| 底层数据表代码字段名 | DATA_CODE_FIELD   | C    | 32   | 表中项目层次代码字段名                                                                     |
| 底层数据表名称字段名 | DATA_NAME_FIELD   | C    | 32   | 表中项目中文名字段名                                                                       |
| 底层编码表过滤条件   | DATA_FILTER       | C    | 64   | 表中记录的过滤条件，比如项目类别限制                                                       |

注释：层次输入法需要定义数据的来源、代码的分层方法等，此表定义了使用层次输入法的项目以及数据来源。每种项目对应一条记录。代码的分层方法即编码原则由分层编码描述表定义。

主键：输入项目。

## 分层编码描述 CLASS_CODING_RULE

|              |             |      |      |                                  |
|--------------|-------------|------|------|----------------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                             |
| 输入项目     | ITEM        | C    | 8    | 由层次输入码定义表定义的输入项目 |
| 编码级       | CODE_LEVEL  | N    | 1    | 编码的第几层，从1开始依次排列    |
| 级长         | LEVEL_WIDTH | N    | 2    | 该级的长度                       |

注释：此表为分层输入法中输入码的编码规则，是层次输入法定义的明细。

主键：输入项目、编码级。

## 词库生成规则表OUTER_GENERATION

|                |                  |      |      |                                                               |
|----------------|------------------|------|------|---------------------------------------------------------------|
| 中文名称       | 字段名           | 类型 | 长度 | 说明                                                          |
| 输入词库文件名 | DICT_FILE_NAME   | C    | 16   |                                                               |
| 资料表名称     | DATA_TABLE_NAME  | C    | 32   |                                                               |
| 输入字段       | DATA_INPUT_FIELD | C    | 32   |                                                               |
| 代码字段       | DATA_CODE_FIELD  | C    | 32   |                                                               |
| 名称字段       | DATA_NAME_FIELD  | C    | 32   |                                                               |
| 过滤条件       | DATA_FILTER      | C    | 128  |                                                               |
| 生成规则       | UPDT_METHOD      | N    | 3    | 0：由上面字段组合sql读取数据，10直接在DICT_TXT_FILE中读取资料 |
| 保存词库内容   | DICT_TXT_FILE    | L    |      |                                                               |
| 五笔码字段名   | INPUT_CODE_WB    | C    | 32   |                                                               |

## 模块与词库对照表OUTER_APP_USE

|                |                |      |      |      |
|----------------|----------------|------|------|------|
| 中文名称       | 字段名         | 类型 | 长度 | 说明 |
| 模块名称       | APPLICATION    | C    | 16   |      |
| 输入词库文件名 | DICT_FILE_NAME | C    | 16   |      |

## INPUT_CODE_DICT

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
|          | ITEM_CODE     | V2   | 10   |      |
|          | ITEM_NAME     | V2   | 10   |      |
|          | INPUT_CODE    | V2   | 5    |      |
|          | INPUT_CODE_WB | V2   | 5    |      |
|          | INPUT_CODE1   | V2   | 5    |      |
|          | INPUT_CODE2   | V2   | 5    |      |
|          | MEMO          | V2   | 10   |      |

## MESSAGES

|          |                  |         |      |      |
|----------|------------------|---------|------|------|
| 中文名称 | 字段名           | 类型    | 长度 | 说明 |
|          | MSGID            | C       | 40   |      |
|          | MSGTITLE         | C       | 255  |      |
|          | MSGTEXT          | C       | 255  |      |
|          | MSGICON          | C       | 12   |      |
|          | MSGBUTTON        | C       | 17   |      |
|          | MSGDEFAULTBUTTON | INTEGER | 22,0 |      |
|          | MSGSEVERITY      | INTEGER | 22,0 |      |
|          | MSGPRINT         | C       | 1    |      |
|          | MSGUSERINPUT     | C       | 1    |      |

#  病案

## 病人主索引 PAT_MASTER_INDEX

|                  |                       |          |      |                                                                                                                                                             |
|------------------|-----------------------|----------|------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称     | 字段名                | 类型     | 长度 | 说明                                                                                                                                                        |
| 病人标识号       | PATIENT_ID            | C        | 10   | 病人唯一标识号，可以由用户赋予具体的含义，如：病案号，门诊号等                                                                                              |
| 住院号           | INP_NO                | C        | 10   | 可选的病人标识，可为空                                                                                                                                      |
| 姓名             | NAME                  | C        | 20   | 病人姓名                                                                                                                                                    |
| 姓名拼音         | NAME_PHONETIC         | C        | 16   | 病人姓名拼音，大写，字间用一个空格分隔，超长截断                                                                                                            |
| 性别             | SEX                   | C        | 4    | 男、女、未知，本系统定义，见1.1性别字典                                                                                                                     |
| 出生日期         | DATE_OF_BIRTH         | D        |      |                                                                                                                                                             |
| 出生地           | BIRTH_PLACE           | C        | 6    | 指定省市县，使用代码，见2.2行政区字典                                                                                                                       |
| 国籍             | CITIZENSHIP           | C        | 2    | 使用国家代码，见2.1国家及地区字典                                                                                                                           |
| 民族             | NATION                | C        | 10   | 民族规范名称，见1.3民族字典                                                                                                                                 |
| 身份证号         | ID_NO                 | C        | 18   |                                                                                                                                                             |
| 身份             | IDENTITY              | C        | 10   | 由身份登记子系统生成，住院登记子系统在办理入院时更新。使用规范名称，由用户定义，见1.6身份字典                                                               |
| 费别             | CHARGE_TYPE           | C        | 8    | 由身份登记子系统生成，住院登记子系统在办理入院时更新。使用规范名称，由用户定义，见1.9费别字典                                                               |
| 合同单位         | UNIT_IN_CONTRACT      | C        | 11   | 如果病人所在单位为本医院的合同单位或体系单位，则使用代码，否则为空。由身份登记子系统生成，住院登记子系统在办理入院时更新。代码由用户定义，见2.4合同单位记录 |
| 通信地址         | MAILING_ADDRESS       | C        | 40   | 指永久通信地址                                                                                                                                              |
| 邮政编码         | ZIP_CODE              | C        | 6    | 对应通信地址的邮政编码                                                                                                                                      |
| 籍贯             | NATIVE_PLACE          | C        |      |                                                                                                                                                             |
| 家庭电话号码     | PHONE_NUMBER_HOME     | C        | 16   |                                                                                                                                                             |
| 单位电话号码     | PHONE_NUMBER_BUSINESS | C        | 16   |                                                                                                                                                             |
| 联系人姓名       | NEXT_OF_KIN           | C        | 8    | 病人的亲属姓名                                                                                                                                              |
| 与联系人关系     | RELATIONSHIP          | C        | 2    | 夫妻、父子等，使用代码，见1.19社会关系字典                                                                                                                  |
| 联系人地址       | NEXT_OF_KIN_ADDR      | C        | 40   |                                                                                                                                                             |
| 联系人邮政编码   | NEXT_OF_KIN_ZIP_CODE  | C        | 6    |                                                                                                                                                             |
| 联系人电话号码   | NEXT_OF_KIN_PHONE     | C        | 16   |                                                                                                                                                             |
| 上次就诊日期     | LAST_VISIT_DATE       | D        | 7    | 由挂号与预约子系统根据就诊记录填写                                                                                                                          |
| 重要人物标志     | VIP_INDICATOR         | N        | 1    | 1-VIP 0-非VIP                                                                                                                                               |
| 建卡日期         | CREATE_DATE           | D        | 7    |                                                                                                                                                             |
| 操作员           | OPERATOR              | C        | 8    | 最后修改本记录的操作员姓名                                                                                                                                  |
| 医疗体系病人标志 | SERVICE_AGENCY        | C        | 40   |                                                                                                                                                             |
| 单位邮编         | business_zip_code     | C        | 6    |                                                                                                                                                             |
| 照片             | photo                 | Long raw |      |                                                                                                                                                             |
| 入院来源         | PATIENT_CLASS         | C        |      | 使用代码，门诊、急诊、转入等，见1.11入院方式字典                                                                                                            |
| 学历             | degree                | C        | 10   | 见学历字典                                                                                                                                                  |
| 种族             | race                  | C        | 10   | 见种族字典                                                                                                                                                  |
| 宗教             | religion              | C        | 16   | 见宗教字典                                                                                                                                                  |
| 母语             | Mother_language       | C        | 16   | 见语言字典                                                                                                                                                  |
| 第二外语         | Foreign_language      | C        | 16   | 所能接受的服务语言,见语言字典                                                                                                                               |
| 证件类型         | ID_type               | C        | 10   | 见证件类型字典                                                                                                                                              |
| 会员号           | Vip_no                | C        | 18   |                                                                                                                                                             |
| 英文名字         | e_name                | var      | 100  | 住院登记、身份登记、主索引录入时增加英文名字。                                                                                                              |

注释：此表描述所有在院注册的病人的基本信息，被整个医院信息系统所共享。由身份登记子系统录入。

此表信息需长期在线保存，如果使用挂号子系统，则此表的数据增长量与每日的初诊病人数相一致。如果医院每日门诊量为1000，其中1/4为初诊病人，则每日数据增长量约为250条，每年约为80,000条。

主键：病人标识号。

## 病人住院主记录 PAT_VISIT

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 32%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>病人标识</td>
<td>PATIENT_ID</td>
<td>C</td>
<td>10</td>
<td>非空</td>
</tr>
<tr class="odd">
<td>病人本次住院标识</td>
<td>VISIT_ID</td>
<td>N</td>
<td>2</td>
<td>病人每次住院，分配一个不同的标识，与病人标识一起，构成一个病人一次住院的唯一标识。可使用住院次数的绝对值或相对值</td>
</tr>
<tr class="even">
<td>入院科室</td>
<td>DEPT_ADMISSION_TO</td>
<td>C</td>
<td>8</td>
<td>按统计要求的科室代码，见2.6科室字典</td>
</tr>
<tr class="odd">
<td>入院日期及时间</td>
<td>ADMISSION_DATE_TIME</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td>出院科室</td>
<td>DEPT_DISCHARGE_FROM</td>
<td>C</td>
<td>8</td>
<td>按统计要求的科室代码，见2.6科室字典</td>
</tr>
<tr class="odd">
<td>出院日期及时间</td>
<td>DISCHARGE_DATE_TIME</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td>职业</td>
<td>OCCUPATION</td>
<td>C</td>
<td>1</td>
<td>使用代码，见1.5职业分类字典</td>
</tr>
<tr class="odd">
<td>婚姻状况</td>
<td>MARITAL_STATUS</td>
<td>C</td>
<td>4</td>
<td>已婚、未婚、离婚、丧偶，使用规范名称，本系统定义，见1.2婚姻状况字典</td>
</tr>
<tr class="even">
<td>身份</td>
<td>IDENTITY</td>
<td>C</td>
<td>10</td>
<td>使用规范名称，见1.6身份字典</td>
</tr>
<tr class="odd">
<td>军种</td>
<td>ARMED_SERVICES</td>
<td>C</td>
<td>4</td>
<td>军兵种，本系统定义，见1.7军种字典</td>
</tr>
<tr class="even">
<td>勤务</td>
<td>DUTY</td>
<td>C</td>
<td>4</td>
<td>海勤、空勤，本系统定义，见1.7勤务字典</td>
</tr>
<tr class="odd">
<td>隶属大单位</td>
<td>TOP_UNIT</td>
<td>C</td>
<td>1</td>
<td>军队病人所属大单位，见大单位字典</td>
</tr>
<tr class="even">
<td>费别</td>
<td>SERVICE_SYSTEM_INDICATOR</td>
<td>N</td>
<td>1</td>
<td>使用规范名称，见1.9费别字典</td>
</tr>
<tr class="odd">
<td>合同单位</td>
<td>UNIT_IN_CONTRACT</td>
<td>C</td>
<td>11</td>
<td>病人所属的体系单位代码，用户定义，见2.4合同单位记录</td>
</tr>
<tr class="even">
<td>医保类别</td>
<td>CHARGE_TYPE</td>
<td>C</td>
<td>8</td>
<td>如果此病人为医保病人，则记录反映本次住院支付方案的医保类别</td>
</tr>
<tr class="odd">
<td>在职标志</td>
<td>WORKING_STATUS</td>
<td>N</td>
<td>1</td>
<td>0-在职 1-离休 2-退休</td>
</tr>
<tr class="even">
<td>工作单位</td>
<td>INSURANCE_TYPE</td>
<td>C</td>
<td>16</td>
<td></td>
</tr>
<tr class="odd">
<td>医疗保险号</td>
<td>INSURANCE_NO</td>
<td>C</td>
<td>18</td>
<td>如果此病人为医保病人，则记录其保险号</td>
</tr>
<tr class="even">
<td>医疗体系病人标志</td>
<td>SERVICE_AGENCY</td>
<td>C</td>
<td>40</td>
<td>对军队病人0-非体系病人，1-体系病人；其它病人为空</td>
</tr>
<tr class="odd">
<td>通信地址</td>
<td>MAILING_ADDRESS</td>
<td>C</td>
<td>40</td>
<td></td>
</tr>
<tr class="even">
<td>邮政编码</td>
<td>ZIP_CODE</td>
<td>C</td>
<td>6</td>
<td></td>
</tr>
<tr class="odd">
<td>联系人姓名</td>
<td>NEXT_OF_KIN</td>
<td>C</td>
<td>8</td>
<td>病人的亲属姓名</td>
</tr>
<tr class="even">
<td>与联系人关系</td>
<td>RELATIONSHIP</td>
<td>C</td>
<td>2</td>
<td>夫妻、父子等，使用代码，见1.19社会关系字典</td>
</tr>
<tr class="odd">
<td>联系人地址</td>
<td>NEXT_OF_KIN_ADDR</td>
<td>C</td>
<td>40</td>
<td></td>
</tr>
<tr class="even">
<td>联系人邮政编码</td>
<td>NEXT_OF_KIN_ZIPCODE</td>
<td>C</td>
<td>6</td>
<td></td>
</tr>
<tr class="odd">
<td>联系人电话</td>
<td>NEXT_OF_KIN_PHONE</td>
<td>C</td>
<td>16</td>
<td></td>
</tr>
<tr class="even">
<td>入院方式</td>
<td>PATIENT_CLASS</td>
<td>C</td>
<td>1</td>
<td>使用代码，门诊、急诊、转入等，见1.11入院方式字典</td>
</tr>
<tr class="odd">
<td>住院目的</td>
<td>ADMISSION_CAUSE</td>
<td>C</td>
<td>8</td>
<td>使用规范名称，治疗、查体、计划生育等，见1.14住院目的字典</td>
</tr>
<tr class="even">
<td>接诊日期</td>
<td>CONSULTING_DATE</td>
<td>D</td>
<td>7</td>
<td>指门诊接诊日期</td>
</tr>
<tr class="odd">
<td>入院病情</td>
<td>PAT_ADM_CONDITION</td>
<td>C</td>
<td>1</td>
<td>使用代码, 危、急、一般，见1.21入院病情字典</td>
</tr>
<tr class="even">
<td>门诊医师</td>
<td>CONSULTING_DOCTOR</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>办理住院者</td>
<td>ADMITTED_BY</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>抢救次数</td>
<td>EMER_TREAT_TIMES</td>
<td>N</td>
<td>2</td>
<td>由病房入出转子系统填入</td>
</tr>
<tr class="odd">
<td>抢救成功次数</td>
<td>ESC_EMER_TIMES</td>
<td>N</td>
<td>2</td>
<td>由病房入出转子系统填入</td>
</tr>
<tr class="even">
<td>病重天数</td>
<td>SERIOUS_COND_DAYS</td>
<td>N</td>
<td>4</td>
<td>病重累计天数</td>
</tr>
<tr class="odd">
<td>病危天数</td>
<td>CRITICAL_COND_DAYS</td>
<td>N</td>
<td>4</td>
<td>病危累计天数</td>
</tr>
<tr class="even">
<td>ICU天数</td>
<td>ICU_DAYS</td>
<td>N</td>
<td>4</td>
<td>病人住ICU的累计天数</td>
</tr>
<tr class="odd">
<td>CCU天数</td>
<td>CCU_DAYS</td>
<td>N</td>
<td>4</td>
<td>病人住CCU的累计天数</td>
</tr>
<tr class="even">
<td>特别护理天数</td>
<td>SPEC_LEVEL_NURS_DAYS</td>
<td>N</td>
<td>4</td>
<td>由病房入出转子系统填入</td>
</tr>
<tr class="odd">
<td>一级护理天数</td>
<td>FIRST_LEVEL_NURS_DAYS</td>
<td>N</td>
<td>4</td>
<td>由病房入出转子系统填入</td>
</tr>
<tr class="even">
<td>二级护理天数</td>
<td>SECOND_LEVEL_NURS_DAYS</td>
<td>N</td>
<td>4</td>
<td>由病房入出转子系统填入</td>
</tr>
<tr class="odd">
<td>尸检标识</td>
<td>AUTOPSY_INDICATOR</td>
<td>N</td>
<td>1</td>
<td>1-尸检 0-否</td>
</tr>
<tr class="even">
<td>血型</td>
<td>BLOOD_TYPE</td>
<td>C</td>
<td>2</td>
<td>由病房入出转子系统填入。使用规范名称, 见1.4血型字典</td>
</tr>
<tr class="odd">
<td>Rh血型</td>
<td>BLOOD_TYPE_RH</td>
<td>C</td>
<td>1</td>
<td>取值：+、-</td>
</tr>
<tr class="even">
<td>输液反应次数</td>
<td>INFUSION_REACT_TIMES</td>
<td>N</td>
<td>2</td>
<td></td>
</tr>
<tr class="odd">
<td>输血次数</td>
<td>BLOOD_TRAN_TIMES</td>
<td>N</td>
<td>2</td>
<td>由病房入出转子系统填入</td>
</tr>
<tr class="even">
<td>输血总量</td>
<td>BLOOD_TRAN_VOL</td>
<td>N</td>
<td>5</td>
<td>单位：毫升。由病房入出转子系统填入</td>
</tr>
<tr class="odd">
<td>输血反应次数</td>
<td>BLOOD_TRAN_REACT_TIMES</td>
<td>N</td>
<td>2</td>
<td>由病房入出转子系统填入</td>
</tr>
<tr class="even">
<td>发生褥疮次数</td>
<td>DECUBITAL_ULCER_TIMES</td>
<td>N</td>
<td>2</td>
<td></td>
</tr>
<tr class="odd">
<td>过敏药物</td>
<td>ALERGY_DRUGS</td>
<td>C</td>
<td>80</td>
<td>过敏药物名称，正文描述，可为多项，若没有，则为空</td>
</tr>
<tr class="even">
<td>不良反应药物</td>
<td>ADVERSE_REACTION_DRUGS</td>
<td>C</td>
<td>80</td>
<td>不良反应药物名称，正文描述，若没有，则为空</td>
</tr>
<tr class="odd">
<td>病案价值</td>
<td>MR_VALUE</td>
<td>C</td>
<td>4</td>
<td>使用规范名称，见3.11病案价值字典</td>
</tr>
<tr class="even">
<td>病案质量</td>
<td>MR_QUALITY</td>
<td>C</td>
<td>2</td>
<td>使用规范名称，见3.10病案质量字典</td>
</tr>
<tr class="odd">
<td>随诊标志</td>
<td>FOLLOW_INDICATOR</td>
<td>N</td>
<td>1</td>
<td>使用代码, 1-随诊 0-不随诊</td>
</tr>
<tr class="even">
<td>随诊期限</td>
<td>FOLLOW_INTERVAL</td>
<td>N</td>
<td>2</td>
<td></td>
</tr>
<tr class="odd">
<td>随诊期限单位</td>
<td>FOLLOW_INTERVAL_UNITS</td>
<td>C</td>
<td>2</td>
<td>年、月</td>
</tr>
<tr class="even">
<td>科主任</td>
<td>DIRECTOR</td>
<td>C</td>
<td>8</td>
<td>由病房入出转子系统填入</td>
</tr>
<tr class="odd">
<td>主治医师</td>
<td>ATTENDING_DOCTOR</td>
<td>C</td>
<td>8</td>
<td>由病房入出转子系统填入</td>
</tr>
<tr class="even">
<td>经治医师</td>
<td>DOCTOR_IN_CHARGE</td>
<td>C</td>
<td>8</td>
<td>由病房入出转子系统填入</td>
</tr>
<tr class="odd">
<td>出院方式</td>
<td>DISCHARGE_DISPOSITION</td>
<td>C</td>
<td>1</td>
<td>使用代码, 正常、转院、死亡等。见1.12出院方式字典</td>
</tr>
<tr class="even">
<td>总费用</td>
<td>TOTAL_COSTS</td>
<td>N</td>
<td>10,2</td>
<td>按价表计算得到的开销，由住院收费子系统填写</td>
</tr>
<tr class="odd">
<td>实付费用</td>
<td>TOTAL_PAYMENTS</td>
<td>N</td>
<td>10,2</td>
<td>实际支付费用，由住院收费子系统填写</td>
</tr>
<tr class="even">
<td>编目日期</td>
<td>CATALOG_DATE</td>
<td>D</td>
<td>7</td>
<td>进行ICD分类或录入日期</td>
</tr>
<tr class="odd">
<td>编目人</td>
<td>CATALOGER</td>
<td>C</td>
<td>8</td>
<td>进行ICD分类的人员姓名</td>
</tr>
<tr class="even">
<td>HbsAg</td>
<td>HBSAG_INDICATOR</td>
<td>N</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td>HCV-Ab</td>
<td>HCV_AB_INDICATOR</td>
<td>N</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td>HIV_AB</td>
<td>HIV_AB_INDICATOR</td>
<td>N</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td>主任医师</td>
<td>CHIEF_DOCTOR</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>进修医师</td>
<td>ADVANCED_STUDIES_DOCTOR</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>研究生实习医师</td>
<td>PRACTICE_DOCTOR_OF_GRADUATE</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>实习医师</td>
<td>PRACTICE_DOCTOR</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>质控医师</td>
<td>DOCTOR_OF_CONTROL_QUALITY</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>质控护士</td>
<td>NURSE_OF_CONTROL_QUALITY</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>质控日期</td>
<td>DATE_OF_CONTROL_QUALITY</td>
<td>D</td>
<td>7</td>
<td></td>
</tr>
<tr class="even">
<td>是否为本院第一例</td>
<td>FIRST_CASE_INDICATOR</td>
<td>N</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td>三级护理天数</td>
<td>THIRD_LEVEL_NURS_DAYS</td>
<td>N</td>
<td>4</td>
<td></td>
</tr>
<tr class="even">
<td>X线号</td>
<td>X_EXAM_NO</td>
<td>C</td>
<td>10</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>TREATED_IN_OTHERS_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>TREAT_METHOD</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>HOSP_MADE_MEDICINE_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>PATHOLOGY_NO</td>
<td>C</td>
<td>10</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>UPPER_DOCTOR_GUIDE_EFFECT</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>EMER_TREAT_METHOD</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>ICTUS_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>DIFFICULTY_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>FROM_OTHER_PLACE_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>SUSPICION_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>CHINESE_MEDICINE_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>OPERATION_SCALE</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>DIAGNOSIS_CORRECTNESS</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>TREAT_METHOD_CORRECTNESS</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>PRESCRIPTION_CORRECTNESS</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>MR_COMPLETE_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>MEDICAL_TERM_CORRECTNESS</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>PPER_DOCTOR_GUIDE_EFFECT</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>TREAT_METHOD_JUDGEMENT</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>DUTY_NURSE</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>死亡原因</td>
<td>DEATH_REASON</td>
<td>C</td>
<td>40</td>
<td></td>
</tr>
<tr class="even">
<td>死亡时间</td>
<td>DEATH_DATE_TIME</td>
<td>D</td>
<td>7</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>SCIENCE_RESEARCH_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>FIRST_OPERATION_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>FIRST_TREATMENT_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>FIRST_EXAMINATION_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>FIRST_DIAGNOSIS_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>INFUSION_REACT_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>SERIOUS_INDICATOR</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td>入院病室</td>
<td>ADT_ROOM_NO</td>
<td>C</td>
<td>4</td>
<td></td>
</tr>
<tr class="odd">
<td>出院病室</td>
<td>DDT_ROOM_NO</td>
<td>C</td>
<td>4</td>
<td></td>
</tr>
<tr class="even">
<td>感染类别</td>
<td>INFECT_INDICATOR</td>
<td>N</td>
<td>1</td>
<td>0未感染，1院内感染，2社区感染，3其它感染，4已登记，5已上报，6已确认</td>
</tr>
<tr class="odd">
<td>健康等级</td>
<td>HEALTH_LEVEL</td>
<td>C</td>
<td>2</td>
<td><p>见公共代码表COMM_CODE_DICT</p>
<p>SUPER_CODE = 01</p></td>
</tr>
<tr class="even">
<td>诊断错漏</td>
<td>MR_INFECT_REPORT</td>
<td>C</td>
<td>4</td>
<td>00已查，10首页漏报，01感染漏报，11首页感染漏报 0000未定义</td>
</tr>
<tr class="odd">
<td>是否新生儿</td>
<td>NEWBORN</td>
<td>C</td>
<td>1</td>
<td>1：是新生儿</td>
</tr>
<tr class="even">
<td>三级护理天数</td>
<td>THIRD_LEVEL_NURSE_DAYS</td>
<td>N</td>
<td>4</td>
<td>与前面的THIRD_LEVEL_NURS_DAYS重复，病案用的为前面的字段。</td>
</tr>
<tr class="odd">
<td>保险地区</td>
<td>INSURANCE_AERA</td>
<td>C</td>
<td>16</td>
<td></td>
</tr>
<tr class="even">
<td>体重</td>
<td>BODY_WEIGHT</td>
<td>N</td>
<td>4,1</td>
<td></td>
</tr>
<tr class="odd">
<td>身高</td>
<td>BODY_HEIGHT</td>
<td>N</td>
<td>4,1</td>
<td></td>
</tr>
<tr class="even">
<td>输液次数</td>
<td>INFUSION_TRAN_TIMES</td>
<td>N</td>
<td>2</td>
<td>2006-06-26 RDB添加</td>
</tr>
<tr class="odd">
<td>首页归档人员</td>
<td>DOCUM_PERSON</td>
<td>V2</td>
<td>20</td>
<td></td>
</tr>
<tr class="even">
<td>科研病历</td>
<td>SCIENCE_RESEARCH_INDICATOR</td>
<td>C</td>
<td>1</td>
<td>1-是，2-否</td>
</tr>
<tr class="odd">
<td>手术为本院第一例</td>
<td>FIRST_OPERATION_INDICATOR</td>
<td>C</td>
<td>1</td>
<td>1-是，2-否</td>
</tr>
<tr class="even">
<td>治疗为本院第一例</td>
<td>FIRST_TREATMENT_INDICATOR</td>
<td>C</td>
<td>1</td>
<td>1-是，2-否</td>
</tr>
<tr class="odd">
<td>检查为本院第一例</td>
<td>FIRST_EXAMINATION_INDICATOR</td>
<td>C</td>
<td>1</td>
<td>1-是，2-否</td>
</tr>
<tr class="even">
<td>诊断为本院第一例</td>
<td>FIRST_DIAGNOSIS_INDICATOR</td>
<td>C</td>
<td>1</td>
<td>1-是，2-否</td>
</tr>
<tr class="odd">
<td>整理者</td>
<td>MR_BINDER</td>
<td>V2</td>
<td>10</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td></td>
<td></td>
<td></td>
<td></td>
</tr>
</tbody>
</table>

注释：本表描述病人住院记录，是病案首页的主记录，每次住院生成一条，由住院登记子系统在住院处办理入院手续时生成。病房分系统填入在院期间的治疗信息。在线长期保存。

日数据增长量=医院日平均入院病人数。

## 病人在科记录 TRANSFER

|                  |                     |      |      |                                                                                   |
|------------------|---------------------|------|------|-----------------------------------------------------------------------------------|
| 字段中文名称     | 字段名              | 类型 | 长度 | 说明                                                                              |
| 病人标识         | PATIENT_ID          | C    | 10   | 非空                                                                              |
| 病人本次住院标识 | VISIT_ID            | N    | 2    | 非空                                                                              |
| 所在科室         | DEPT_STAYED         | C    | 8    | 科室编码，见2.6科室字典                                                           |
| 入科日期及时间   | ADMISSION_DATE_TIME | D    |      |                                                                                   |
| 出科日期及时间   | DISCHARGE_DATE_TIME | D    |      |                                                                                   |
| 转向科室         | DEPT_TRANSFERED_TO  | C    | 8    | 如果病人转向其他科室，为转向科室的编码，见2.6科室字典，若为正常出院或转院，则为空 |
| 经治医师         | DOCTOR_IN_CHARGE    | C    | 8    | 在本科的经治医师                                                                  |

注释：本表记录病人在院期间的就诊科室。一个病人在院期间可能有多个就诊科室。入科时，由病房入出转子系统创建该病人的在科记录，出科时，记录出科时间。长期在线保存.每个住院病人至少一条在科记录，数据增长量应在住院记录数的1~2倍之间。

## 诊断记录 DIAGNOSIS

|                  |                      |      |      |                                                     |
|------------------|----------------------|------|------|-----------------------------------------------------|
| 字段中文名称     | 字段名               | 类型 | 长度 | 说明                                                |
| 病人标识         | PATIENT_ID           | C    | 10   | 非空                                                |
| 病人本次住院标识 | VISIT_ID             | N    | 2    | 非空                                                |
| 诊断类别         | DIAGNOSIS_TYPE       | C    | 1    | 反映入院、出院、门诊、病理诊断等，见4.5诊断类别字典 |
| 诊断序号         | DIAGNOSIS_NO         | N    | 2    | 依重要次序，由小到大排列                            |
| 诊断             | DIAGNOSIS_DESC       | C    | 80   | 医生诊断描述。由病房管理分系统录入。                |
| 诊断日期         | DIAGNOSIS_DATE       | D    |      | 确定本诊断的日期                                    |
| 治疗天数         | TREAT_DAYS           | N    | 3,0  | 本疾病的治疗天数                                    |
| 治疗结果         | TREAT_RESULT         | C    | 4    | 使用规范名称, 好转、治愈等，见4.28治疗结果字典      |
| 手术治疗标志     | OPER_TREAT_INDICATOR | N    | 1    | 此诊断是否采取手术治疗，0-非手术治疗，1-手术治疗    |

注释：本表描述医生为病人所下的各种诊断，包括门诊诊断、入院诊断、出院诊断、病理诊断等，每种诊断可以有多个，按重要程度次序排列。本表数据由病房管理分系统负责录入。以1000张床位，每年出院1万名病人，每人平均3条诊断计，每年的数据增长量约为3万条。长期在线保存。

## 门诊诊断记录 CLINIC_DIAGNOSIS

|              |                      |      |      |      |
|--------------|----------------------|------|------|------|
| 字段中文名称 | 字段名               | 类型 | 长度 | 说明 |
|              | PATIENT_ID           | C    | 10   |      |
|              | VISIT_ID             | N    | 2    |      |
|              | DIAGNOSIS_NO         | N    | 2    |      |
|              | DIAGNOSIS_DESC       | C    | 80   |      |
|              | DIAGNOSIS_DATE       | D    | 7    |      |
|              | TREAT_DAYS           | N    | 4    |      |
|              | TREAT_RESULT         | C    | 4    |      |
|              | OPER_TREAT_INDICATOR | N    | 1    |      |

此表为诊断记录的门诊诊断部分的视图。除无诊断类别字段外，其他字段与诊断记录相同。

## 主要诊断 FINAL_CHIEF_DIAGNOSIS

此表为诊断记录的出院（最后）第一诊断的视图。

|                  |                      |      |      |                          |
|------------------|----------------------|------|------|--------------------------|
| 字段中文名称     | 字段名               | 类型 | 长度 | 说明                     |
| 病人标识         | PATIENT_ID           | C    | 10   | 对应PATIENT_ID           |
| 病人本次住院标识 | VISIT_ID             | N    | 2    | 对应VISIT_ID             |
| 诊断序号         | DIAGNOSIS_NO         | N    | 2    | 对应DIAGNOSIS_NO         |
| 诊断             | DIAGNOSIS_DESC       | C    | 80   | 对应DIAGNOSIS_DESC       |
| 诊断日期         | DIAGNOSIS_DATE       | D    |      | 对应DIAGNOSIS_DATE       |
| 治疗天数         | TREAT_DAYS           | N    | 3,0  | 对应TREAT_DAYS           |
| 治疗结果         | TREAT_RESULT         | C    | 4    | 对应TREAT_RESULT         |
| 手术治疗标志     | OPER_TREAT_INDICATOR | N    | 1    | 对应OPER_TREAT_INDICATOR |

## 诊断分类记录 DIAGNOSTIC_CATEGORY

|                  |                |      |      |                         |
|------------------|----------------|------|------|-------------------------|
| 字段中文名称     | 字段名         | 类型 | 长度 | 说明                    |
| 病人标识         | PATIENT_ID     | C    | 10   | 非空                    |
| 病人本次住院标识 | VISIT_ID       | N    | 2    | 非空                    |
| 诊断类别         | DIAGNOSIS_TYPE | C    | 1    | 见4.4诊断类别字典       |
| 诊断序号         | DIAGNOSIS_NO   | N    | 2    | 同诊断记录中诊断的序号  |
| 诊断代码         | DIAGNOSIS_CODE | C    | 16   | 使用ICD9，见4.1疾病字典 |
|                  | CODE_NUM       | N    | 22,0 |                         |

注释：此表为诊断编目所设，由病案编目子系统录入。医生所下的每个诊断可以从不同的角度赋予多个分类编码。如肿瘤，既可以按部位编码，也可以按形态学编码。数据的增长量略大于诊断记录的增长量。长期在线保存。

## 手术记录 OPERATION

|                  |                    |      |      |                                                          |
|------------------|--------------------|------|------|----------------------------------------------------------|
| 字段中文名称     | 字段名             | 类型 | 长度 | 说明                                                     |
| 病人标识         | PATIENT_ID         | C    | 10   | 非空                                                     |
| 病人本次住院标识 | VISIT_ID           | N    | 2    | 非空                                                     |
| 手术序号         | OPERATION_NO       | N    | 2    | 一个病人多次手术按时间顺序，从1开始，从小到大排列        |
| 手术名称         | OPERATION_DESC     | C    | 100  | 医生所开手术名称正文                                     |
| 手术编码         | OPERATION_CODE     | C    | 10   | 由编目子系统填入，使用ICD9CM，见4.2手术操作字典          |
| 切口等级         | HEAL               | C    | 2    | 手术的切口等级，使用名称，本系统定义，见4.36切口等级字典 |
| 切口愈合情况     | WOUND_GRADE        | C    | 2    | 使用名称，本系统定义，见4.29切口愈合情况字典             |
| 手术日期         | OPERATING_DATE     | D    |      |                                                          |
| 麻醉方法         | ANAESTHESIA_METHOD | C    | 16   | 使用规范名称，见4.18麻醉方法字典                         |
| 手术医师         | OPERATOR           | C    | 8    | 医师姓名                                                 |
| 第一助手         | FIRST_ASSISTANT    | C    | 8    |                                                          |
| 第二助手         | SECOND_ASSISTANT   | C    | 8    |                                                          |
| 麻醉医师         | ANESTHESIA_DOCTOR  | C    | 8    |                                                          |

注释：此表记录病人在院期间手术情况。由医生填入手术名称，由编目子系统填入手术分类代码。以1000张床位，每年出院1万名病人，每人平均0.3条手术计，每年的数据增长量约为3000条。长期在线保存。

## 诊断对照记录 DIAG_COMPARING

|                  |                     |      |      |                                                         |
|------------------|---------------------|------|------|---------------------------------------------------------|
| 字段中文名称     | 字段名              | 类型 | 长度 | 说明                                                    |
| 病人标识         | PATIENT_ID          | C    | 10   | 非空                                                    |
| 病人本次住院标识 | VISIT_ID            | N    | 2    | 非空                                                    |
| 诊断对照组       | DIAG_COMPARE_GROUP  | C    | 1    | 病案首页规定的诊断对照组，使用代码，见4.5诊断对照组字典 |
| 诊断符合情况     | DIAG_CORRESPONDENCE | C    | 1    | 使用代码，见4.30诊断符合情况字典                        |

注释：此表用于反映医疗诊断质量，以便进行医疗统计。由病案编目子系统填入。长期在线保存。以1000张床位，每年出院1万名病人，每人5条诊断对照计，每年的数据增长量约为5万条。

## 住院病人费用记录 MEDICAL_COSTS

|                  |            |      |      |                                                                 |
|------------------|------------|------|------|-----------------------------------------------------------------|
| 字段中文名称     | 字段名     | 类型 | 长度 | 说明                                                            |
| 病人标识         | PATIENT_ID | C    | 10   | 非空                                                            |
| 病人本次住院标识 | VISIT_ID   | N    | 2    | 非空                                                            |
| 费用分类         | FEE_TYPE   | C    | 4    | 使用规范名称,病案首页规定的费用类别，见6.11病案首页费用分类字典 |
| 费用             | COSTS      | N    | 10,2 | 按价表计算得到的实际开销                                        |

注释：此表反映病人住院期间医疗总开销。由住院收费子系统在病人出院时填写。以1000张床位，每年出院1万名病人，每人平均5类费用计，每年的数据增长量约为5万条。长期在线保存。

## 病人输血记录 BLOOD_TRANSFUSION

|                    |                 |      |      |                          |
|--------------------|-----------------|------|------|--------------------------|
| 字段中文名称       | 字段名          | 类型 | 长度 | 说明                     |
| 病人标识           | PATIENT_ID      | C    | 10   | 非空                     |
| 病人本次住院标识   | VISIT_ID        | N    | 2    | 病人一次住院的唯一标识。 |
| 全血               | WHOLE_BLOOD     | N    | 5    | 单位：毫升               |
| 红细胞悬液         | RED_CELL        | N    | 5    | 单位：毫升               |
| 去白细胞红细胞悬液 | PURE_RED_CELL   | N    | 5    | 单位：毫升               |
| 血小板             | PLATELET        | N    | 3    | 单位：袋                 |
| 冷沉淀             | CRYOAGGLUTININ  | N    | 5    | 单位：IU                 |
| 血浆               | PLASMA          | N    | 5    | 单位：毫升               |
| 自身输血           | AUTOTRANSFUSION | N    | 5    | 单位：毫升               |
|                    | OTHERS          | N    | 5    |                          |

注释：此表为病人一次住院用各种成份血的详细记录。

主键：病人标识号、病人本次住院标识。

## 病人过敏药物记录 ALERGY_DRUGS(不使用)

|                  |             |      |      |                                                      |
|------------------|-------------|------|------|------------------------------------------------------|
| 字段中文名称     | 字段名      | 类型 | 长度 | 说明                                                 |
| 病人标识         | PATIENT_ID  | C    | 10   | 非空                                                 |
| 过敏药物名称     | DRUG_NAME   | C    | 40   | 可以是一个具体的药品名称，也可以是一类药物名称，非空 |
| 过敏药物代码     | DRUG_CODE   | C    | 10   | 对应过敏药物名称的代码                               |
| 过敏反应严重程度 | SEVERITY    | C    | 8    | 反映过敏的严重程度，使用标准名称                     |
| 记录时间         | ENTER_DATE  | D    |      | 记录该过敏药物的时间                                 |
| 记录者           | RECORDED_BY | C    | 8    | 记录者姓名                                           |

注释：此表用于记录一个病人所有曾经过敏药物，不区分住院次数。

主键：病人标识号、过敏药物名称。

## 主索引合并记录 PMI_MERGED_LOG

|                    |              |      |      |                                  |
|--------------------|--------------|------|------|----------------------------------|
| 字段中文名称       | 字段名       | 类型 | 长度 | 说明                             |
| 被合并的病人标识号 | PID_MERGED   | C    | 10   | 合并后，此标识号在主索引中被取消 |
| 保留的病人标识号   | PID_RETAINED | C    | 10   |                                  |
| 合并日期           | MERGED_DATE  | D    |      |                                  |
| 操作员             | OPERATOR     | C    | 8    | 操作员姓名                       |

注释：此表用于记录一个病人重复主索引的合并日志。当以后存在有合并前病人标识的数据时，可通过本表查到该病人新的标识号。此表信息长期在线保存。

主键：被合并的病人标识号、保留的病人标识号、合并日期。

## 病案记录 MR_REC

|              |                    |      |      |                                                                                  |
|--------------|--------------------|------|------|----------------------------------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                                                             |
| 病案类别     | MR_CLASS           | C    | 1    | 非空，见病案分类字典                                                             |
| 病案号       | MR_NO              | C    | 10   | 非空                                                                             |
| 病案属性     | MR_ATTR            | C    | 1    | 用于区分已归档和未归档病案，1—已归档，0—未归档                                   |
| 病人标识号   | PATIENT_ID         | C    | 10   | 非空，建立病案者必须有主索引信息                                                 |
| 建立病案日期 | MR_CREATE_DATE     | D    |      |                                                                                  |
| 最后借出日期 | LAST_BORROWED_DATE | D    |      | 最后一次借出日期，新建病案未借出时为空                                           |
| 最后归还日期 | LAST_RETURNED_DATE | D    |      | 最后一次归还日期，新建病案时为空                                                 |
| 当前位置     | CURRENT_LOCATION   | C    | 8    | 病案当前所在单位代码                                                             |
| 病案存放位置 | STORE_LOCATION     | C    | 8    | 病案库所在单位代码                                                               |
| 当前病案状态 | MR_STATUS          | C    | 1    | 反映本病案在库、借出、丢失、预约、新建，使用代码，本系统定义，见3.12病案状态字典 |

注释：此表用于描述病人的物理病案，每个病人可以有多类物理病案，每类病案由其病案号唯一标识。各类病案记录的生成由相应的业务系统负责。

主键：病案类别、病案号。

索引：病人ID。

## 病案追踪日志 MR_TRACE_LOG

|              |                    |      |      |                                                  |
|--------------|--------------------|------|------|--------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                             |
| 病案类别     | MR_CLASS           | C    | 1    |                                                  |
| 病案号       | MR_NO              | C    | 10   |                                                  |
| 流通性质     | TRANSFER_ATTR      | C    | 8    | 反映本次流通的类型，如：借出、归档、入库、流通等 |
| 流出科室     | RELEASED_DEPT      | C    | 8    | 病案流出科室代码                                 |
| 流入科室     | ACCEPTED_DEPT      | C    | 8    | 病案流入科室代码                                 |
| 流出时间     | RELEASED_DATE_TIME | D    |      |                                                  |
| 经手人       | RELEASED_BY        | C    | 8    | 经手人姓名                                       |
| 接收人       | ACCEPTED_BY        | C    | 8    | 接收人或借阅人姓名                               |
| 备注         | MEMO               | C    | 40   | 对病案作详细说明，比如：归档时，病案丢失原因，   |

注释：此表描述病案交接记录，通过交接过程，记录病案的整个流动过程。该记录由流出科室在病案流出时生成。

主键：病案类别、病案号、流出时间、流通性质。

## 病案索引 MR_INDEX

|              |                       |      |      |                                                        |
|--------------|-----------------------|------|------|--------------------------------------------------------|
| 字段中文名称 | 字段名                | 类型 | 长度 | 说明                                                   |
| 病人ID       | PATIENT_ID            | C    | 10   | 与住院标识一起构成一个病人一次住院即一份病历的唯一标识 |
| 住院标识     | VISIT_ID              | N    | 2    |                                                        |
| 病案状态     | MR_STATUS             | C    | 1    | 反映病案的存贮状态：O-工作C-关闭 A-归档 F-脱机         |
| 卷标         | STORAGE_VOLUME_LABEL  | C    | 32   | 指明存储介质，如1#光盘                                 |
| 访问路径     | ACCESS_PATH           | C    | 40   | 病案由离线变为在线后的访问路径。如果为脱机，则为空     |
| 最近访问时间 | LAST_ACCESS_DATE_TIME | D    |      |                                                        |
| 提交病历医生 | LAST_ACCESS_USER      | VAR2 | 20   | 提交病历医生                                           |

注释：此表用于描述所有病案记录的存贮状态。针对每次住院记录生成一条。

主键：病人ID、住院标识

## 病历文件索引 MR_FILE_INDEX

|                      |                       |      |      |                                                                                 |
|----------------------|-----------------------|------|------|---------------------------------------------------------------------------------|
| 字段中文名称         | 字段名                | 类型 | 长度 | 说明                                                                            |
| 病人ID               | PATIENT_ID            | C    | 10   | 与住院标识一起构成一个病人一次住院的唯一标识                                    |
| 住院标识             | VISIT_ID              | N    | 2    |                                                                                 |
| 文件序号             | FILE_NO               | N    | 2    | 一个病人的一次住院范围内，所使用的文件从1开始依次排序                           |
| 文件名               | FILE_NAME             | C    | 16   | 病历文件的文件名，不包含路径信息                                                |
| 主题                 | TOPIC                 | C    | 40   | 每个病历文件可以赋予一个主题，用于显示文件内容                                  |
| 创建者姓名           | CREATOR_NAME          | C    | 8    | 创建该文件的用户姓名                                                            |
| 创建者ID             | CREATOR_ID            | C    | 16   | 创建该文件的用户系统分配的ID                                                    |
| 创建时间             | CREATE_DATE_TIME      | D    |      |                                                                                 |
| 最后修改时间         | LAST_MODIFY_DATE_TIME | D    |      | 该文件的最后修改时间(经治医师签名时间)                                          |
|                      | FILE_MODIFY_DATE_TIME | D    |      |                                                                                 |
|                      | FLAG                  | C    | 1    |                                                                                 |
| 文件标识             | FILE_FLAG             | c    | 1    | 大于0为新医生工作站所写病历文件                                                 |
| 文件属性             | FILE_ATTR             | C    | 1    | T为临时文件1为经治医生签名 2上级医生签名 3 主任医生签名                         |
| 打印标志             | PRINT_FLAG            | C    | 1    |                                                                                 |
| 病历代码             | MR_CODE               | C    | 12   |                                                                                 |
| 审签者姓名           | PARENT_NAME           | C    | 8    |                                                                                 |
| 审签者ID             | PARENT_ID             | C    | 16   |                                                                                 |
| 文件修改时间         | MODIFY_DATE_TIME      | date |      | 上级医师修改和审签时间                                                          |
| 电子病历索引文件标志 | epr_index             | Var2 | 20   | 该号可由时间(年月日小时分秒)合成的串来代替,从而可以利用原来的时间列实现平滑升级 |

注释：此表记录了一个病人一次住院所使用的病历文件。由医生在创建新的病历文件时建立新记录，每次修改病历内容，记录响应文件的修改时间。

主键：病人ID、住院标识、文件序号

## 联机病历描述MR_ON_LINE

|              |                   |      |      |                                                                                                                      |
|--------------|-------------------|------|------|----------------------------------------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                                                                                                                 |
| 病人ID       | PATIENT_ID        | C    | 10   | 与住院标识一起构成一个病人一次住院即一份病历的唯一标识                                                               |
| 住院标识     | VISIT_ID          | N    | 22,0 |                                                                                                                      |
| 病历状态     | STATUS            | C    | 1    | 0-未归档病历，1-历史病历，\*-病历转移状态                                                                            |
| 请求医生     | REQUEST_DOCTOR_ID | C    | 16   | 该份病历的主管医生。当病人在院时，应为该病人的主管医生；当病人出院后，如果该病人的病历申请为回顾病历，则为请求医生。 |
| 请求时间     | REQUEST_DATE_TIME | D    |      | 对在院病人，为医生建立病历的时间；对回顾病历，为情况联机的时间。                                                     |
|              | SUPER_DOCTOR_ID   | C    | 16   |                                                                                                                      |
|              | PARENT_DOCTOR_ID  | C    | 16   |                                                                                                                      |

注释：此表描述了所有当前关心的病历。当前关心的病历包括：在院病人、出院未归档病人、个人请求的回顾病历。系统管理的病历单位为病人的一次住院记录。

主键：请求医生、病人ID、住院标识

索引：病人ID、住院标识

## 病历模板索引 MR_TEMPLET_INDEX

|              |                       |      |      |                                                |
|--------------|-----------------------|------|------|------------------------------------------------|
| 字段中文名称 | 字段名                | 类型 | 长度 | 说明                                           |
| 模板标识     | TEMPLET_ID            | C    | 6    | 模板唯一标识                                   |
| 模板文件名   | TEMPLET_FILE_NAME     | C    | 16   | 模板文件的文件名，不含路径信息                 |
| 存取路径     | ACCESS_PATH           | C    | 40   | 存取模板的路径                                 |
| 主题         | TOPIC                 | C    | 40   | 反映该模板内容的分类的说明                     |
| 所属科室     | DEPT_CODE             | C    | 8    | 模板所属（定义与使用）的科室代码，公用模板为\* |
| 创建者       | CREATOR_ID            | C    | 16   | 创建该模板的用户标识                           |
| 创建时间     | CREATE_DATE_TIME      | D    |      |                                                |
| 最后修改时间 | LAST_MODIFY_DATE_TIME | D    |      |                                                |
| 允许访问权   | PERMISSION            | C    | 1    | 该模板访问权：公开、专科、个人                 |

注释：此表用于描述病历模板。病历模板可以定义为公共模板、科室模板和个人模板。

主键：模板标识。

## 病历模板选择MR_TEMPLET_SELECTION

|              |            |      |      |                                                  |
|--------------|------------|------|------|--------------------------------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                                             |
| 用户         | USER_NAME  | C    | 16   | 数据库用户名                                     |
| 模板标识     | TEMPLET_ID | C    | 6    | 选用的模板标识，由病历模板索引定义对应的模板文件 |

注释：此表用于描述医生选用的病历模板，包括公用、科室、个人三类。

主键：用户、模板标识

## 当前病历路径描述MR_WORK_PATH

|                      |              |      |      |                                |
|----------------------|--------------|------|------|--------------------------------|
| 字段中文名称         | 字段名       | 类型 | 长度 | 说明                           |
| 病历文件路径         | MR_PATH      | C    | 40   | 当前病历存放路径               |
| 病历模板路径         | TEMPLET_PATH | C    | 40   | 病历模板文件存放路径           |
| 访问文件服务用户     | FILE_USER    | C    | 16   | 存取病历文件使用的文件服务用户 |
| 访问文件服务用户口令 | FILE_PWD     | C    | 16   | 对应上述用户的口令             |
| 文件服务器IP地址     | IP_ADDR      | C    | 64   | 提供文件服务的服务器IP地址     |

注释：此表用于配置当前可用病历的存放路径及其他访问文件的配置参数，该表只有一条记录。

主键：病历文件路径

## 病案纸张描述MR_PAPER_DESC

|              |               |      |      |                                        |
|--------------|---------------|------|------|----------------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                                   |
| 纸张大小     | PAPER_SIZE    | C    | 16   | 纸张规格名称，如A4、LETTER等           |
| 纸张高度     | HEIGHT        | N    | 3,1  | 单位cm                                 |
| 纸张宽度     | WIDTH         | N    | 3,1  | 单位cm                                 |
| 装订位置     | BIND_POSITION | C    | 4    | 上或左，与此相关的是默认的上和左偏移量 |
| 左偏移量     | LEFT_MARGIN   | N    | 2,1  | 从纸张左边计算的版心偏移，单位cm       |
| 上偏移量     | TOP_MARGIN    | N    | 2,1  | 从纸张顶边计算的版心偏移，单位cm       |
| 医嘱单行数   | ORDER_LINES   | N    | 2    | 医嘱记录单中打印医嘱行数               |

注释：此表描述了可用的纸张及打印规格选择。系统默认的左和上偏移量，用户可以修改。

主键：纸张大小、装订位置

## 医疗质量问题分类字典QA_EVENT_TYPE_DICT

|          |            |      |      |                    |
|----------|------------|------|------|--------------------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明               |
| 序号     | SERIAL_NO  | N    | 4    | 反映项目的排列顺序 |
| 问题分类 | EVENT_TYPE | C    | 16   | 问题类别描述       |
| 输入码   | INPUT_CODE | C    | 8    |                    |

注释：此表用于定义医疗质量控制中发现的质量问题类别，用户定义。

主键：问题分类。

## 修改姓名记录表PAT_MASTER_RENAME_LOG (新增)

|            |                     |      |      |      |
|------------|---------------------|------|------|------|
| 中文名称   | 字段名              | 类型 | 长度 | 说明 |
| 修改时间   | ENTER_DATE          | D    | 7    | 非空 |
| 病人ID     | PATIENT_ID          | C    | 10   | 非空 |
| 性别       | SEX                 | C    | 4    |      |
| 修改后姓名 | NAME                | C    | 20   |      |
| 入院日期   | ADMISSION_DATE_TIME | D    | 7    |      |
| 入院科室   | DEPT_ADMISSION_TO   | C    | 8    |      |
| 旧姓名     | OLD_NAME            | C    | 8    |      |
| 修改原因   | REASON              | C    | 30   |      |
| 操作员     | OPERATOR            | C    | 4    |      |

## 卡地址描述表MEDCARD_ADDRESS_REC(新增)

|              |              |      |      |                                                                          |
|--------------|--------------|------|------|--------------------------------------------------------------------------|
| 字段中文名称 | 字段名       | 类型 | 长度 | 说明                                                                     |
| 项目         | ITEM_NAME    | C    | 20   | 采用汉字描述，目前支持姓名、过敏、既往诊断、血型、病人ID、卡号等六个项目 |
| 开始地址     | ITEM_ADDRESS | N    | 4    | 采用10进制描述                                                           |
| 长度         | ITEM_LENGTH  | N    | 2    |                                                                          |

主键：项目

## 医疗卡门诊就医系统运行配置表MEDCARD_CONFIG(新增)

|                  |                      |      |      |        |
|------------------|----------------------|------|------|--------|
| 字段中文名称     | 字段名               | 类型 | 长度 | 说明   |
| 医院代码         | HOSPITAL_CODE        | C    | 16   |        |
| 打印交款退款凭证 | PRINT_PREPAY         | N    | 1    | 1-打印 |
| 打印医疗消费清单 | PRINT_BILL_DETAIL    | N    | 1    | 1-打印 |
| 读卡校验密码标志 | CHECK_READ_PWD       | N    | 1    | 1-校验 |
| 4428卡初始密码   | DEFAULT_PWD_4428     | C    | 9    |        |
| 4442卡初始密码   | DEFAULT_PWD_4442     | C    | 9    |        |
| 医疗卡有效期     | CARD_EXPIRATION_DATE | D    |      |        |

主键：医院代码

注释：系统配置表，只有一条记录。

## 医疗卡类型字典MEDICAL_CARD_TYPE_DICT(新增)

|              |            |      |      |                              |
|--------------|------------|------|------|------------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                         |
| 序号         | SERIAL_NO  | N    | 2    |                              |
| 类型编码     | TYPE_CODE  | C    | 2    |                              |
| 类型名称     | TYPE_NAME  | C    | 10   | 比如本院卡、健康卡、体检卡等 |
| 输入码       | INPUT_CODE | C    | 8    |                              |

主键：类型名称

## 医疗卡说明MEDICAL_CARD_MEMO(新增)

|              |                 |      |      |                                                                |
|--------------|-----------------|------|------|----------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                           |
| 病人标识号   | PATIENT_ID      | C    | 10   | 病人唯一标识号，可以由用户赋予具体的含义，如：病案号，门诊号等 |
| 卡号         | CARD_NO         | C    | 18   |                                                                |
| 卡类型       | CARD_TYPE       | C    | 10   |                                                                |
| 有效期限     | EXPIRATION_DATE | D    |      | 系统默认医疗卡年度有效，医院每年进行年审。                     |
| 状态         | ACCOUNT_STATUS  | N    | 1    | 0-可用 1-挂起 2-注销                                           |
| 过敏药物     | ALERGY_DRUGS    | C    | 80   |                                                                |
| 既往诊断1    | DIAG1           | C    | 40   |                                                                |
| 既往诊断2    | DIAG2           | C    | 40   |                                                                |
| 既往诊断3    | DIAG3           | C    | 40   |                                                                |
| 血型         | BLOOD_TYPE      | C    | 2    |                                                                |
| 帐户密码     | ACCOUNT_PWD     | C    | 32   | 采用加密算法实现，初始取卡号的后六位作为初始密码               |
| 充值收据号   | RCPT_NO         | C    | 8    | 对应预交金记录的收据号                                         |
| 是否已经充值 | FLAG            | N    | 1    | 1-已经充值，2-未使用，0-非充值卡                               |

注释：当前有效状态下，只允许一张医疗卡可用。

主键：卡号

## 医疗卡变更日志MEDICAL_CARD_LOG(新增)

|                |              |      |      |                  |
|----------------|--------------|------|------|------------------|
| 字段中文名称   | 字段名       | 类型 | 长度 | 说明             |
| 卡号           | CARD_NO      | C    | 18   |                  |
| 医疗卡变更日期 | CHANGE_DATE  | D    |      |                  |
| 医疗卡变更原因 | CHANGE_CAUSE | C    | 40   | 如：遗失、过期等 |
| 操作员         | OPERATOR     | C    | 8    |                  |
| 输入日期       | ENTER_DATE   | D    |      |                  |

主键：卡号、医疗卡变更日期

## 新生儿记录表NEWBORN_REC(新增)

|                     |                         |          |      |                                                        |
|---------------------|-------------------------|----------|------|--------------------------------------------------------|
| 中文名称            | 字段名                  | 类型     | 长度 | 说明                                                   |
| 姓名                | NAME                    | C        | 8    | 是否应该更长一些                                       |
| 性别                | SEX                     | C        | 4    |                                                        |
| 出生日期            | DATE_OF_BIRTH           | D        |      | 精确到分                                               |
| 出生地（省）        | BIRTH_PLACE_PROVINCE    | C        | 30   |                                                        |
| 出生地（市）        | BIRTH_PLACE_CITY        | C        | 30   |                                                        |
| 出生地（县/区）     | BIRTH_PLACE_COUNTY      | C        | 30   | 县或区                                                 |
| 出生地（乡）        | BIRTH_PLACE_TOWNSHIP    | C        | 30   |                                                        |
| 出生孕周            | GESTATION_WEEK          | N        | 2    |                                                        |
| 健康状况            | HEALTH_STATUS           | C        | 4    | 良好、一般、差                                         |
| 体重                | WEIGHT                  | N        | 4    | 单位：克                                               |
| 身长                | HEIGHT                  | N        | 2    | 单位：厘米                                             |
| 分娩方式            | BIRTH_QUOMODO           | C        | 1    | 剖腹产，顺产，钳产，参见分娩方式数据字典BIRTH_QUO_DICT |
| 分娩结果            | BIRTH_RESULT            | C        | 1    | 足月，畸形，参见分娩结果数据字典BIRTH_QUO_DICT         |
| 母亲年龄            | AGE_OF_MOTHER           | N        | 2    |                                                        |
| 母亲国籍            | CITIZENSHIP \_OF_MOTHER | C        | 2    | 国家代码，见国家字典                                   |
| 母亲民族            | NATION_OF_MOTHER        | C        | 10   |                                                        |
| 母亲身份证号        | ID_NO_OF_MOTHER         | C        | 18   |                                                        |
| 父亲姓名            | NAME \_OF_FATHER        | C        | 8    |                                                        |
| 父亲年龄            | AGE_OF_FATHER           | N        | 2    |                                                        |
| 父亲国籍            | CITIZENSHIP \_OF_FATHER | C        | 2    | 国家代码，见国家字典                                   |
| 父亲民族            | NATION_OF_FATHER        | C        | 10   |                                                        |
| 父亲身份证号        | ID_NO_OF_FATHER         | C        | 18   |                                                        |
| 家庭住址            | HOME_ADDRESS            | C        | 40   |                                                        |
| 出生地点分类        | TYPE_OF_PLACE           | C        | 20   | 医院、妇幼保健院、家庭、其它                           |
| 接生机构名称        | NAME_OF_FACILITY        | C        | 40   |                                                        |
| 出生证编号          | BIRTH_CERTIFICATION_NO  | C        | 10   |                                                        |
| 签发日期            | DATE_OF_ISSUE           | D        |      |                                                        |
| 婴儿ID              | PATIENT_ID              | C        | 10   |                                                        |
| 母亲ID              | PATIENT_ID_OF_MOTHER    | C        | 10   |                                                        |
| 母亲visit_id        | VISIT_ID_OF_MOTHER      |          |      |                                                        |
| 录入人              | OPERATOR                | C        | 8    |                                                        |
| 录入日期            | ENTER_DATE              | D        |      |                                                        |
| 疫苗1               | DRUG1                   | C        | 20   |                                                        |
| 疫苗2               | DRUG2                   | C        | 20   |                                                        |
| 说明                | MEMO\_                  | C        | 500  |                                                        |
| 长期医嘱宽度        | Bearing_date            | date     | 2    | 分娩时间                                               |
| 全产程几小时        | FULL_BEARING_HOUR       | number   | 3    | 全产程几小时,不能有小数，小数另外有一列                |
| 全产程多少分钟      | FULL_BEARING_MINU       | number   | 2    | 大于0而小于60分钟                                      |
| 第一产程            | FIRST_BEARING           | number   | 2    | 第一产程                                               |
| 第二产程            | SECOND_BEARING          | number   | 2    | 第二产程                                               |
| 第三产程            | THIRD_BEARING           | number   | 2    | 第三产程                                               |
| 第四产程            | fourth_BEARING          | number   | 2    | 第四产程                                               |
| 出生胎方位          | FETUS_TREND             | VARCHAR2 | 20   | 胎方位                                                 |
| APGAR_REC 评分      | APGAR_REC               | number   | 5,2  | APGAR_REC 评分                                         |
| 新生儿疾病诊断1名称 | NEWBORN_BUG1_NAME       | VARCHAR2 | 20   | 新生儿疾病诊断1名称                                    |
| 新生儿疾病诊断2名称 | NEWBORN_BUG2_NAME       | VARCHAR2 | 20   | 新生儿疾病诊断2名称                                    |
| 新生儿疾病诊断3名称 | NEWBORN_BUG3_NAME       | VARCHAR2 | 20   | 新生儿疾病诊断3名称                                    |
| 出生体重            | WEIGHT_BIRTH            | n        | 4    |                                                        |
| 入院体重            | WEIGHT_INP              | n        | 4    |                                                        |
| 产后出血量          | After_BIRTH_Blood       | N        | 4    |                                                        |
| 分娩时间            | Bearing_date            | date     |      |                                                        |
| 全产程几小时        | FULL_BEARING_HOUR       | n        | 3    |                                                        |
| 全产程多少分钟      | FULL_BEARING_MINU       | n        | 2    |                                                        |
| 第一产程            | FIRST_BEARING           | n        | 2    |                                                        |
| 第二产程            | SECOND_BEARING          | n        | 2    |                                                        |
| 第三产程            | THIRD_BEARING           | n        | 2    |                                                        |
| 第四产程            | fourth_BEARING          | n        | 2    |                                                        |
| 出生胎方位          | FETUS_TREND             | V2       | 20   |                                                        |
| APGAR_REC 评分      | APGAR_REC               | n        | 5,2  |                                                        |
| 新生儿疾病诊断1名称 | NEWBORN_BUG1_NAME       | V2       | 20   |                                                        |
| 新生儿疾病诊断2名称 | NEWBORN_BUG2_NAME       | V2       | 20   |                                                        |
| 新生儿疾病诊断3名称 | NEWBORN_BUG3_NAME       | V2       | 20   |                                                        |
|                     |                         |          |      |                                                        |

## OPER_SETTLE_CARD

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
|          | OPERATOR      | C    | 16   |      |
|          | START_DATE    | D    | 7    |      |
|          | END_DATE      | D    | 7    |      |
|          | NUM_NEW       | N    | 8    |      |
|          | MONEY_NEW     | N    | 10,2 |      |
|          | NUM_REP       | N    | 8    |      |
|          | MONEY_REP     | N    | 10,2 |      |
|          | NUM_ADD       | N    | 8    |      |
|          | MONEY_ADD     | N    | 10,2 |      |
|          | NUM_BACK      | N    | 8    |      |
|          | MONEY_BACK    | N    | 10,2 |      |
|          | NUM_OFF       | N    | 8    |      |
|          | MONEY_OFF     | N    | 10,2 |      |
|          | START_BALANCE | N    | 10,2 |      |
|          | TURNED_MONEY  | N    | 10,2 |      |
|          | END_BALANCE   | N    | 10,2 |      |
|          | NEXT_OPERATOR | C    | 16   |      |
|          | SHIFT_DATE    | D    |      |      |

## PATIENT_CARD_INFO

|          |                |      |      |      |
|----------|----------------|------|------|------|
| 中文名称 | 字段名         | 类型 | 长度 | 说明 |
|          | CARD_NO        | C    | 18   |      |
|          | NAME           | C    | 8    |      |
|          | CARD_PASS      | C    | 16   |      |
|          | CARD_TYPE_NO   | C    | 2    |      |
|          | REGISTER_DATE  | D    |      |      |
|          | EXPIRE_DATE    | D    |      |      |
|          | CARD_STATUS_NO | C    | 1    |      |
|          | CARD_CENTER_NO | C    | 8    |      |
|          | OPERATOR       | C    | 16   |      |
|          | PATIENT_ID     | C    | 10   |      |
|          | ACCT_BALANCE   | N    | 10,2 |      |
|          | ACCT_OCCUPY    | N    | 10,2 |      |
|          | TOTAL_CONSUMED | N    | 10,2 |      |

## 住院号取消日志INP_CANCEL_LOG(新增)

|                |            |                |        |        |          |          |
|----------------|------------|----------------|--------|--------|----------|----------|
| **字段中文名** | **字段名** | **类型(长度)** | **PK** | **FK** | **Null** | **说明** |
| INP_NO         | 住院号     | VARCHAR2 (10)  | Y      |        |          |          |
| DB_USER        | 用户编码   | VARCHAR2 (8)   |        |        |          |          |

## 病案复印记录MR_COPY_REC

|              |               |      |      |                                                                                  |
|--------------|---------------|------|------|----------------------------------------------------------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                                                                             |
| 病案类别     | MR_CLASS      | C    | 1    |                                                                                  |
| 病案号       | MR_NO         | C    | 10   |                                                                                  |
| 复印对象     | Copy_Object   | C    | 1    | 1 医生，2病人                                                                    |
| 复印内容     | Copy_Content  | C    | 200  |                                                                                  |
| 复印科室     | Dept_Code     | C    | 8    | 复印对象是医生得时候，该字段为医生所在的科室；复印对象是病人得时候，该字段为空。 |
| 复印人       | Copy_Man      | C    | 20   | 病人或医生姓名                                                                   |
| 复印份数     | Copy_Share    | N    | 5    |                                                                                  |
| 复印原因     | Copy_Reason   | C    | 200  | 文字描述原因                                                                     |
| 复印时间     | Copy_Date     | D    |      |                                                                                  |
| 复印经手人   | Copy_released | C    | 20   |                                                                                  |

## 卫统科室字典STAT_DEPT_DICT

|              |                |      |      |      |
|--------------|----------------|------|------|------|
| 中文名称     | 字段名         | 类型 | 长度 | 说明 |
| 统计科室代码 | STAT_DEPT_CODE | C    | 8    |      |
| 统计科室名称 | STAT_DEPT_NAME | C    | 20   |      |
| 显示序号     | REMARK         | C    | 20   |      |
|              | INPUT_CODE     | VAR2 | 20   |      |
|              | INPUT_CODE_WEB | VAR2 | 20   |      |

## 卫统费用对照STAT_VS_FEE_CLASS

|          |           |      |      |      |
|----------|-----------|------|------|------|
| 中文名称 | 字段名    | 类型 | 长度 | 说明 |
| 统计代码 | STAT_CODE | C    | 2    |      |
| 统计名称 | STAT_NAME | C    | 10   |      |
| 费用代码 | FEE_CODE  | C    | 1    |      |
| 费用名称 | FEE_NAME  | C    | 4    |      |
| 备注     | REMARK    | C    | 20   |      |

## 卫统5代码字典MR_WT5_DICT

|           |               |      |      |      |
|-----------|---------------|------|------|------|
| 中文名称  | 字段名        | 类型 | 长度 | 说明 |
| 卫统5类别 | WT5_TYPE      | C    | 2    |      |
| 卫统5代码 | WT5_CODE      | C    | 16   |      |
| 卫统5名称 | WT5_NAME      | C    | 40   |      |
| 备注      | REMARK        | C    | 60   |      |
| 拼音码    | INPUT_CODE    | C    | 20   |      |
| 五笔码    | INPUT_CODE_WB | C    | 20   |      |

## 卫统5代码字典与HIS字典对照MR_HIS_VS_WT5

|           |           |      |      |      |
|-----------|-----------|------|------|------|
| 中文名称  | 字段名    | 类型 | 长度 | 说明 |
| 对照类别  | STAT_CODE | C    | 2    |      |
| 卫统5代码 | WT5_CODE  | C    | 16   |      |
| HIS代码   | HIS_CODE  | C    | 16   |      |
| 备注      | REMARK    | C    | 60   |      |

主键：对照类别，卫统5代码，HIS代码

## 卫统5接口表mr_wt5_interface

|                                |           |       |      |                                                                           |
|--------------------------------|-----------|-------|------|---------------------------------------------------------------------------|
| 中文名称                       | 字段名    | 类型  | 长度 | 说明                                                                      |
| 数据年份:                      | Sjnf      | C     | 4    |                                                                           |
| 行政区划代码:                  | Xzqh      | C     | 6    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 组织机构代码:                  | Jgdm      | C     | 9    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 医疗付款方式:                  | s0101     | C     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 住院次数:                      | s0102     | C     | 2    |                                                                           |
| 病案号:                        | s0103     | C     | 15   | not null                                                                  |
| 姓名                           | s0108     | C     | 20   |                                                                           |
| 性别:                          | s0104     | C     | 1    |                                                                           |
| 出生日期：                     | s0109     | date  |      |                                                                           |
| 年龄（岁）:                    | s0105     | N     | 3    |                                                                           |
| 婚姻状况:                      | s0106     | C     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 职业代码:                      | s0107     | C     | 2    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 民族                           | s0110     | C     | 20   |                                                                           |
| 身份证                         | s0111     | C     | 18   |                                                                           |
| 工作单位地址                   | s0112     | C     | 80   |                                                                           |
| 户口地址                       | s0113     | C     | 80   |                                                                           |
| 户口地址邮政编码               | s011301   | C     | 6    |                                                                           |
| 联系人姓名                     | s0114     | C     | 20   |                                                                           |
| 联系人地址                     | s011401   | C     | 80   |                                                                           |
| 联系人电话                     | s011402   | C     | 30   |                                                                           |
| 入院日期:                      | s0201     | date  |      | YYYYMMDD not null                                                         |
| 入院科别代码:                  | s0202     | C     | 4    | &&&&&&&&&&&&&&&&需要对照 not null                                         |
| 出院日期:                      | s0301     | date  |      | YYYYMMDD                                                                  |
| 出院科别代码:                  | s0302     | C     | 4    | &&&&&&&&&&&&&&&&需要对照 not null                                         |
| 入院时情况:                    | s0401     | C     | 1    | &&&&&&&&&&&&&&&&需要对照 not null                                         |
| 入院诊断（ICD－10）:           | s0402     | C     | 10   |                                                                           |
| 入院诊断名称                   | s040200   | C     | 80   |                                                                           |
| 入院后确诊日期:                | s0403     | date  |      | YYYYMMDD                                                                  |
| 出院时主要诊断（ICD－10）:     | s0501     | C     | 10   | not null                                                                  |
| 出院诊断名称                   | s050100   | C     | 80   | not null                                                                  |
| 治疗结果:                      | s050101   | C     | 1    | &&&&&&&&&&&&&&&&需要对照 not null                                         |
| 出院时其它诊断1（ICD－10）:    | s0502     | C     | 10   |                                                                           |
| 出院诊断名称1                  | s050200   | C     | 80   |                                                                           |
| 治疗结果:                      | s050201   | C     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 出院时其它诊断2（ICD－10）:    | s0506     | C     | 10   |                                                                           |
| 出院诊断名称2                  | s050600   | C     | 80   |                                                                           |
| 治疗结果:                      | s050601   | C     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 出院时其它诊断3（ICD－10）:    | s0507     | C     | 10   |                                                                           |
| 出院诊断名称3                  | s050700   | C     | 80   |                                                                           |
| 治疗结果:                      | s050701   | C     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 出院时其它诊断4（ICD－10）:    | s0508     | C     | 10   |                                                                           |
| 出院诊断名称4                  | s050800   | C     | 80   |                                                                           |
| 治疗结果:                      | s050801   | C     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 出院时其它诊断5（ICD－10）:    | s0509     | C     | 10   |                                                                           |
| 出院诊断名称5                  | s050900   | C     | 80   |                                                                           |
| 治疗结果:                      | s050901   | C     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 出院时其它诊断6（ICD－10）:    | s0510     | C     | 10   |                                                                           |
| 出院诊断名称6                  | s051000   | C     | 80   |                                                                           |
| 治疗结果:                      | s051001   | C     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 出院时其它诊断7（ICD－10）:    | s0511     | C     | 10   |                                                                           |
| 出院诊断名称7                  | s051100   | C     | 80   |                                                                           |
| 治疗结果:                      | s051101   | C     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 医院感染名称（ICD－10）:       | s0503     | C     | 10   |                                                                           |
| 医院感染名称                   | s050300   | C     | 80   |                                                                           |
| 治疗结果:                      | s050301   | C     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 病理诊断（ICD-10）             | s0518     | C     | 10   |                                                                           |
| 病理名称                       | s051801   | C     | 80   |                                                                           |
| 损伤和中毒外部原因（ICD－10）: | s0504     | C     | 10   |                                                                           |
| 损伤和中毒外部原因名称:        | s050401   | C     | 80   |                                                                           |
| 手术编码1(ICD－9－CM3):        | s0505     | C     | 10   |                                                                           |
| 手术日期                       | s050500   | date  |      | YYYYMMDD                                                                  |
| 手术操作名称1                  | s050501   | C     | 80   |                                                                           |
| 手术操作医师                   | s050502   | C     | 20   |                                                                           |
| Ⅰ助                            | s05050201 | C     | 20   |                                                                           |
| Ⅱ助                            | s05050202 | C     | 20   |                                                                           |
| 麻醉方式                       | s050503   | C     | 20   |                                                                           |
| 切口愈合                       | s050504   | n(1)  | 1    |                                                                           |
| 麻醉医师                       | s050505   | C(20) | 20   |                                                                           |
| 手术编码2(ICD－9－CM3):        | s0512     | C(10) | 10   |                                                                           |
| 手术日期                       | s051200   | date  |      | YYYYMMDD                                                                  |
| 手术操作名称2                  | s051201   | C     | 80   |                                                                           |
| 手术操作医师                   | s051202   | C     | 20   |                                                                           |
| Ⅰ助                            | s05120201 | C     | 20   |                                                                           |
| Ⅱ助                            | s05120202 | C     | 20   |                                                                           |
| 麻醉方式                       | s051203   | C     | 20   |                                                                           |
| 切口愈合                       | s051204   | n(1)  | 1    |                                                                           |
| 麻醉医师                       | s051205   | C(20) | 20   |                                                                           |
| 手术编码3(ICD－9－CM3):        | s0513     | C(10) |      |                                                                           |
| 手术日期                       | s051300   | date  |      | YYYYMMDD                                                                  |
| 手术操作名称3                  | s051301   | C     | 80   |                                                                           |
| 手术操作医师                   | s051302   | C     | 20   |                                                                           |
| Ⅰ助                            | s05130201 | C     | 20   |                                                                           |
| Ⅱ助                            | s05130202 | C     | 20   |                                                                           |
| 麻醉方式                       | s051303   | C     | 20   |                                                                           |
| 切口愈合                       | s051304   | n(1)  | 1    |                                                                           |
| 麻醉医师                       | s051305   | C     | 20   |                                                                           |
| 手术编码4(ICD－9－CM3):        | s0514     | C     | 10   |                                                                           |
| 手术日期                       | s051400   | date  |      | YYYYMMDD                                                                  |
| 手术操作名称4                  | s051401   | C     | 80   |                                                                           |
| 手术操作医师                   | s051402   | C     | 20   |                                                                           |
| Ⅰ助                            | s05140201 | C     | 20   |                                                                           |
| Ⅱ助                            | s05140202 | C     | 20   |                                                                           |
| 麻醉方式                       | s051403   | C     | 20   |                                                                           |
| 切口愈合                       | s051404   | N     | 1    |                                                                           |
| 麻醉医师                       | s051405   | C     | 20   |                                                                           |
| 手术编码5(ICD－9－CM3):        | s0515     | C     | 10   |                                                                           |
| 手术日期                       | s051500   | date  |      | YYYYMMDD                                                                  |
| 手术操作名称5                  | s051501   | C     | 80   |                                                                           |
| 手术操作医师                   | s051502   | C     | 20   |                                                                           |
| Ⅰ助                            | s05150201 | C     | 20   |                                                                           |
| Ⅱ助                            | s05150202 | C     | 20   |                                                                           |
| 麻醉方式                       | s051503   | C     | 20   |                                                                           |
| 切口愈合                       | s051504   | N     | 1    |                                                                           |
| 麻醉医师                       | s051505   | C     | 20   |                                                                           |
| 抢救次数                       | s0516     | N     | 2    |                                                                           |
| 抢救成功次数                   | s051601   | N     | 2    |                                                                           |
| 住院费用总计:                  | n0601     | N     | 12,2 |                                                                           |
| 床位费:                        | n060101   | N     | 12,2 |                                                                           |
| 护理费:                        | n060102   | N     | 12,2 |                                                                           |
| 西药费:                        | n060103   | N     | 12,2 |                                                                           |
| 中成药费:                      | n06010401 | N     | 12,2 |                                                                           |
| 中草药费                       | n06010402 | N     | 12,2 |                                                                           |
| 放射费                         | n060110   | N     | 12,2 |                                                                           |
| 化验费:                        | n060105   | N     | 12,2 |                                                                           |
| 输氧费                         | n060111   | N     | 12,2 |                                                                           |
| 输血                           | n060112   | N     | 12,2 |                                                                           |
| 诊察费:                        | n060106   | N     | 12,2 |                                                                           |
| 手术费:                        | n060107   | N     | 12,2 |                                                                           |
| 接生费                         | n060113   | N     | 12,2 |                                                                           |
| 检查费:                        | n060108   | N     | 12,2 |                                                                           |
| 麻醉费                         | n060114   | N     | 12,2 |                                                                           |
| 婴儿费                         | n060115   | N     | 12,2 |                                                                           |
| 陪床费                         | n060116   | N     | 12,2 |                                                                           |
| 治疗费                         | n060117   | N     | 12,2 |                                                                           |
| 调温费                         | n060118   | N     | 12,2 |                                                                           |
| 其他费用:                      | n060109   | N     | 12,2 |                                                                           |
| 血型编码:                      | n0701     | N     | 1    | &&&&&&&&&&&&&&&&需要对照                                                  |
| 红细胞:                        | n070201   | N     | 4    |                                                                           |
| 血小板:                        | n070202   | N     | 4    |                                                                           |
| 血浆:                          | n070203   | N     | 4    |                                                                           |
| 全血:                          | n070204   | N     | 4    |                                                                           |
| 其它:                          | n070205   | N     | 4    |                                                                           |
| 机构名称:                      | Jgmc      | C     | 80   |                                                                           |
| 填报人                         | m01       | C     | 20   |                                                                           |
| 填报日期                       | m02       | date  |      | YYYYMMDD                                                                  |
| 交易流水号                     | Trade_NO  | C     | 20   | HIS生成，格式为：医疗机构代码（8左对齐）+医院流水号（12右对齐）中间补零。 |
| IC卡号/手册号                  | ICCARD_NO | C     | 12   | 医保卡号或医保本号。                                                      |
| 出院诊断统计码                 | 133       | Nm1   | C    | 20                                                                        |
| 30种疾病统计码                 | 134       | Nm2   | C    | 20                                                                        |
| 内码3                          | 135       | Nm3   | C    | 20                                                                        |
| 内码4                          | 136       | Nm4   | C    | 20                                                                        |
| 内码5                          | 137       | Nm5   | C    | 20                                                                        |
| 机构名称:                      | 138       | Jgmc  | C    | 80                                                                        |

##  统计病种字典 MR_REPORT_DIAG

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 14%" />
<col style="width: 15%" />
<col style="width: 8%" />
<col style="width: 41%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>类别</td>
<td>SFRM</td>
<td>C</td>
<td>20</td>
<td>0-内科 1-外科 2-妇产科 3-儿科</td>
</tr>
<tr class="odd">
<td>序号</td>
<td>NSEQ</td>
<td>N</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td>病种名称</td>
<td>STXT</td>
<td>C</td>
<td>500</td>
<td>对参与统计的一类疾病的名称</td>
</tr>
<tr class="odd">
<td>编码条件</td>
<td>SEXP</td>
<td>C</td>
<td>100</td>
<td>对应上述ICD-10编码生成的WHERE子句条件</td>
</tr>
<tr class="even">
<td>分类</td>
<td>STYPE</td>
<td>C</td>
<td>3</td>
<td>191（173），30，50三种值</td>
</tr>
<tr class="odd">
<td>状态</td>
<td>BST</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td>科室</td>
<td>SDEPT</td>
<td>C</td>
<td>100</td>
<td>儿科，妇产科，眼科，内科，外科，传染科，耳鼻喉科，精神科</td>
</tr>
<tr class="odd">
<td>代码</td>
<td>SCODE</td>
<td>C</td>
<td>6</td>
<td><p>用于生成卫统5的dbf文件时产生nm1和nm2的依据</p>
<p>2007-06-29 冉德兵添加该字段</p></td>
</tr>
</tbody>
</table>

## 病案存放位置字典 mr_location_dict

|          |                  |      |      |      |
|----------|------------------|------|------|------|
| 中文名称 | 字段名           | 类型 | 长度 | 说明 |
| 病案类别 | mr_class         | VAR2 | 10   |      |
| 存放位置 | mr_location_name | VAR2 | 20   |      |
| 输入码   | input_code       | VAR2 | 10   |      |
|          |                  |      |      |      |

# 门诊病人管理

## 门诊号别定义CLINIC_INDEX

|              |                 |      |      |                                                               |
|--------------|-----------------|------|------|---------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                          |
| 号别         | CLINIC_LABEL    | C    | 16   | 将不同专科的号看作不同的类别，为每种号分配一个唯一标识        |
| 门诊科室     | CLINIC_DEPT     | C    | 8    | 使用科室代码，用户定义，见2.6科室字典                         |
| 医生         | DOCTOR          | C    | 8    | 医生姓名。当该门诊指定具体医生时使用，不用时，为空            |
| 医生职称     | DOCTOR_TITLE    | C    | 1    | 使用代码，本系统定义，见1.20医生职务字典                      |
| 号类         | CLINIC_TYPE     | C    | 8    | 标识该门诊的挂号费等级，如：普通、专家等，见3.5门诊号类别字典 |
| 输入码       | INPUT_CODE      | C    | 8    |                                                               |
| 门诊科室地址 | CLINIC_POSITION | C    | 20   |                                                               |
|              | CLINIC_INDEX    | C    | 8    |                                                               |

注释：此表定义了医院所开设的门诊种类，一个种类的门诊需要设立一种号别。

主键：号别。

## 门诊安排记录 CLINIC_SCHEDULE

|              |                     |      |      |                                                         |
|--------------|---------------------|------|------|---------------------------------------------------------|
| 字段中文名称 | 字段名              | 类型 | 长度 | 说明                                                    |
| 号别         | CLINIC_LABEL        | C    | 16   | 门诊号别定义中规定的号别，反映门诊种类                  |
| 星期         | DAY_OF_WEEK         | N    | 1    | 非空，0~6分别表示星期日一~六，见4.33星期字典            |
| 门诊时间描述 | TIME_DESC           | C    | 8    | 反映该号别的开放时间，如：上午、下午等，见3.9时间段字典 |
| 限号数       | REGISTRATION_LIMITS | N    | 3    | 若为0，则不限号                                         |
| 限预约号数   | APPOINTMENT_LIMITS  | N    | 3    | 若为0，则不限号                                         |

注释：此表以周为描述单位，反映每日门诊出诊安排情况。由该表可以生成每日的实际号表记录。

主键：号别、星期、门诊时间描述。

## 门诊号表 CLINIC_FOR_REGIST

|              |                     |      |      |                                                         |
|--------------|---------------------|------|------|---------------------------------------------------------|
| 字段中文名称 | 字段名              | 类型 | 长度 | 说明                                                    |
| 门诊日期     | CLINIC_DATE         | D    |      | 指对应号别就诊开始日期                                  |
| 号别         | CLINIC_LABEL        | C    | 16   | 门诊号别定义中规定的号别，反映门诊种类                  |
| 门诊时间描述 | TIME_DESC           | C    | 8    | 反映该号别的开放时间，如：上午、下午等，见3.9时间段字典 |
| 限号数       | REGISTRATION_LIMITS | N    | 3    | 若为0，则不限号                                         |
| 限预约号数   | APPOINTMENT_LIMITS  | N    | 3    | 若为0，则不限号                                         |
| 当前号       | CURRENT_NO          | N    | 3    | 该号别当前可用号                                        |
| 当日已挂号数 | REGISTRATION_NUM    | N    | 3    | 当日已挂号数，挂号加1，退号减1                          |
| 已预约号数   | APPOINTMENT_NUM     | N    | 3    | 已预约号数，预约加1                                     |
| 挂号费标准   | REGIST_PRICE        | N    | 5,2  |                                                         |

注释：此表为已开放挂号的门诊号表。在允许挂某个日期的门诊号之前，应将该日的号表登记到本表中，一个日期门诊结束后，该日期的号表删除。一个门诊日期的一个号别可以区分不同的时间段分别记录号表。

主键：门诊日期、号别、门诊时间描述。

## 门诊预约记录 CLINIC_APPOINTS

|              |                   |      |      |                              |
|--------------|-------------------|------|------|------------------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                         |
| 就诊日期     | VISIT_DATE_APPTED | D    |      | 非空                         |
| 号别         | CLINIC_LABEL      | C    | 16   | 为门诊出诊安排表中定义的号别 |
| 病人标识号   | PATIENT_ID        | C    | 10   | 预约病人的标识，非空         |
| 预约就诊时间 | VISIT_TIME_APPTED | C    | 5    | 同号表门诊时间描述           |
| 何日预约     | APPT_MADE_DATE    | D    |      | 进行预约的日期               |
| 预约模式     | MODE_CODE         | C    | 1    |                              |
| 卡名         | CARD_NAME         | C    | 16   |                              |
| 卡号         | CARD_NO           | C    | 20   |                              |
| 流水号       | SERIAL_NO         | N    | 3    |                              |
| 姓名         | NAME              | C    | 20   |                              |
| 性别         | SEX               | C    | 4    |                              |
| 年龄         | AGE               | N    | 16   |                              |
| 身份         | IDENTITY          | C    | 10   |                              |
| 费别         | CHARGE_TYPE       | C    | 16   |                              |
| 保险号码     | INSURANCE_NO      | C    | 18   |                              |
| 保险类型     | INSURANCE_TYPE    | C    | 16   |                              |
| 合同单位     | UNIT_IN_CONTRACT  | C    | 11   |                              |
| 姓名拼音码   | NAME_PHONETIC     | C    | 16   |                              |

注释：此表反映门诊就诊预约病人情况。要求所有预约病人必须有病人主索引记录。病人预约时，生成一条记录，来院就诊确认后，将该记录删除，在门诊就诊记录表中生成门诊就诊记录。如果病人已预约但未就诊，在经过适当的处理后，将记录删除。

主键：就诊日期、号别、病人标识号、预约就诊时间。

## 就诊记录 CLINIC_MASTER

|              |                       |      |      |                                                                                                 |
|--------------|-----------------------|------|------|-------------------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名                | 类型 | 长度 | 说明                                                                                            |
| 就诊日期     | VISIT_DATE            | D    |      | 非空                                                                                            |
| 就诊序号     | VISIT_NO              | N    | 5    | 非空，每天从1开始递增，为病人每次挂号分配一个序号，该序号与就诊日期一起，构成一次就诊的唯一标识 |
| 号别         | CLINIC_LABEL          | C    | 16   | 对应门诊号表主记录定义的号别                                                                    |
| 就诊时间描述 | VISIT_TIME_DESC       | C    | 8    | 同号表门诊时间描述                                                                              |
| 号码         | SERIAL_NO             | N    | 3    | 一个号别下的序号                                                                                |
| 病人标识 号  | PATIENT_ID            | C    | 10   | 对已建立主索引的病人使用，对无主索引的病人为空                                                  |
| 姓名         | NAME                  | C    | 20   | 病人姓名                                                                                        |
| 姓名拼音     | NAME_PHONETIC         | C    | 16   | 病人姓名拼音，大写，字间用一个空格分隔，超长截断                                                |
| 性别         | SEX                   | C    | 4    | 使用规范描述，见1.1性别字典                                                                     |
| 年龄         | AGE                   | N    | 3    |                                                                                                 |
| 身份         | IDENTITY              | C    | 10   | 使用规范名称，用户定义，见1.6身份字典                                                           |
| 费别         | CHARGE_TYPE           | C    | 8    | 使用规范名称，用户定义，见1.9费别字典                                                           |
| 医保类别     | INSURANCE_TYPE        | C    | 16   | 如果此病人为医保病人，则记录反映本次住院支付方案的医保类别                                      |
| 医疗保险号   | INSURANCE_NO          | C    | 18   | 如果此病人为医保病人，则记录其保险号                                                            |
| 合同单位     | UNIT_IN_CONTRACT      | C    | 11   | 也称体系单位，使用代码，用户定义，见2.4合同单位记录                                             |
| 号类         | CLINIC_TYPE           | C    | 8    | 标识该门诊的挂号费等级，如：普通、专家等，见3.5门诊号类别字典                                   |
| 初诊标志     | FIRST_VISIT_INDICATOR | N    | 1    | 1-初诊 0-复诊                                                                                   |
| 就诊科室     | VISIT_DEPT            | C    | 8    | 科室代码，用户定义，见2.6科室字典                                                               |
| 就诊专科     | VISIT_SPECIAL_CLINIC  | C    | 16   | 指就诊科室下所设的某一专科，可空                                                                |
| 医生         | DOCTOR                | C    | 8    | 在就诊专家门诊时，为专家姓名，可空                                                              |
| 提供病案标志 | MR_PROVIDE_INDICATOR  | N    | 1    | 1--需提供 0--不提供                                                                             |
| 挂号状态     | REGISTRATION_STATUS   | N    | 1    | 反映从预约到就诊的状态变化。0-预约 1-已确认（已取号） 2-就诊                                    |
| 挂号日期     | REGISTERING_DATE      | D    | 7    | 发生预约或挂号的日期                                                                            |
| 症状         | SYMPTOM               | C    | 40   |                                                                                                 |
| 挂号费       | REGIST_FEE            | N    | 5,2  |                                                                                                 |
| 诊疗费       | CLINIC_FEE            | N    | 5,2  |                                                                                                 |
| 其它费       | OTHER_FEE             | N    | 5,2  |                                                                                                 |
| 实收费用     | CLINIC_CHARGE         | N    | 5,2  |                                                                                                 |
| 挂号员       | OPERATOR              | C    | 8    |                                                                                                 |
| 退号日期     | RETURNED_DATE         | D    |      | 发生退号时使用                                                                                  |
| 退号挂号员   | RETURNED_OPERATOR     | C    | 8    | 发生退号时使用                                                                                  |
| 挂号模式     | MODE_CODE             | C    | 1    |                                                                                                 |
| 卡名         | CARD_NAME             | C    | 16   |                                                                                                 |
| 卡号         | CARD_NO               | C    | 20   |                                                                                                 |
| 结帐时间     | ACCT_DATE_TIME        | D    |      |                                                                                                 |
| 结帐号码     | ACCT_NO               | C    | 6    |                                                                                                 |
| 支付方式     | PAY_WAY               | C    | 8    |                                                                                                 |
| 病案传送否   | MR_PROVIDED_INDICATOR | N    | 1    |                                                                                                 |
| 发票号码     | INVOICE_NO            | C    | 20   |                                                                                                 |
| 门诊号       | clinic_no             | V2   | 13   |                                                                                                 |

注释：此表反映病人一次就诊或挂号的基本信息，挂号时产生，由病人门诊的后续环节如：收费、取药等使用。病人完成整个门诊流程，待门诊业务统计完成后，即可删除挂号记录。

允许提前挂号，即提前拿号和交费（不同于预约）。

主键：就诊日期、就诊序号。

## 特殊挂号费价表SPECIAL_REGIST_PRICE(不使用)

|              |             |      |      |                                                   |
|--------------|-------------|------|------|---------------------------------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                                              |
| 号类         | CLINIC_TYPE | C    | 8    | 特殊化的号类，与费别一起定义特殊挂号费            |
| 费别         | CHARGE_TYPE | C    | 8    | 特殊化的费别，与号类一起定义特殊挂号费,见费别字典 |
| 挂号费       | PRICE       | N    | 5,2  |                                                   |

注释：此表描述了与号类字典中定义不同的挂号费，特殊挂号费由号类和费别联合确定。

主键：号类、费别。

## 诊疗费价表CLINIC_PRICE

|              |             |      |      |                |
|--------------|-------------|------|------|----------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明           |
| 费别         | CHARGE_TYPE | C    | 8    | 费别确定诊疗费 |
| 诊疗费       | PRICE       | N    | 5,2  |                |

注释：此表定义门诊诊疗费标准，诊疗费由费别确定。

主键：费别。

## 请求提供病案队列MR_REQUEST_QUEUE

|              |                   |      |      |                                |
|--------------|-------------------|------|------|--------------------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                           |
| 病人标识 号  | PATIENT_ID        | C    | 10   | 等待提供病案的病人ID           |
| 病案送往科室 | DESTINATION_DEPT  | C    | 8    | 病人就诊需要送往病案的科室代码 |
| 挂号时间     | REGISTRATION_DATE | D    | 7    |                                |
| 时间描述     | TIME_DESC         | C    | 8    |                                |
| 序列号       | SERIAL            | N    | 3    |                                |
|              | MR_LOCATION       | C    | 8    |                                |
| 号别         | CLINIC_LABEL      | C    | 16   |                                |

注释：此表记录门诊挂号后需要提供病历的病人队列。

主键：病人标识号。

## 挂号结帐主记录REGIST_ACCT_MASTER

|          |                   |      |      |            |
|----------|-------------------|------|------|------------|
| 中文名称 | 字段名            | 类型 | 长度 | 说明       |
| 结帐号   | ACCT_NO           | C    | 6    | 结帐序列号 |
| 操作员   | OPERATOR_NO       | C    | 8    | 结帐人     |
| 日期     | ACCT_DATE         | D    |      | 结帐日期   |
| 挂号数   | REGIST_NUM        | N    | 16,2 |            |
| 退号数   | REFUND_NUM        | N    | 16,2 |            |
| 退费数   | REFUND_AMOUNT     | N    | 16,2 |            |
| 总费用   | TOTAL_COSTS       | N    | 16,2 |            |
| 总收入   | TOTAL_INCOMES     | N    | 16,2 |            |
| 记帐日期 | TALLY_DATE        | D    |      |            |
| 填表日期 | FULFILL_DATE_TIME | D    |      |            |

主键：结帐号、日期

## 挂号结帐明细REGIST_ACCT_DETAIL

|              |                 |      |      |                      |
|--------------|-----------------|------|------|----------------------|
| 中文名称     | 字段名          | 类型 | 长度 | 说明                 |
| 结帐号       | ACCT_NO         | C    | 6    | 结帐序列号           |
| 费用帐目分类 | TALLY_FEE_CLASS | C    | 4    | 表tally_subject_dict |
| 费用         | COSTS           | N    | 10,2 |                      |
| 收入         | INCOME          | N    | 10,2 |                      |

主键：结帐号、费用帐目分类

## 挂号结帐金额分类REGIST_ACCT_MONEY

|          |                 |      |      |              |
|----------|-----------------|------|------|--------------|
| 中文名称 | 字段名          | 类型 | 长度 | 说明         |
| 结帐号   | ACCT_NO         | C    | 6    | 结帐序列号   |
| 金额类别 | MONEY_TYPE      | C    | 8    | 如现金、支票 |
| 数额     | INCOME_AMOUNT   | N    | 10,2 |              |
| 退数额   | REFUNDED_AMOUNT | N    | 10,2 |              |

主键：结帐号、金额类别

## 请求提供病案队列备份MR_REQUEST_QUEUE_BACKUP

|              |                   |      |      |      |
|--------------|-------------------|------|------|------|
| 中文名称     | 字段名            | 类型 | 长度 | 说明 |
| 病人标识号   | PATIENT_ID        | C    | 10   |      |
| 病案送往科室 | DESTINATION_DEPT  | C    | 8    |      |
| 挂号时间     | REGISTRATION_DATE | D    |      |      |
| 时间描述     | TIME_DESC         | C    | 8    |      |
| 序列号       | SERIAL            | N    | 3    |      |
|              | MR_LOCATION       | C    | 8    |      |
| 号别         | CLINIC_LABEL      | C    | 16   |      |

结构与MR_REQUEST_QUEUE相同

## CLINIC_MASTER_DAYNUMBER_TEMP(不使用)

目前没有用到

|          |                 |      |      |      |
|----------|-----------------|------|------|------|
| 中文名称 | 字段名          | 类型 | 长度 | 说明 |
|          | VISIT_DATE      | D    |      |      |
|          | VISIT_NO        | N    | 5    |      |
|          | DAYNUMBER       | N    | 1    |      |
|          | DAY_OF_WEEK     | C    | 10   |      |
|          | VISIT_DEPT      | C    | 8    |      |
|          | CLINIC_LABEL    | C    | 16   |      |
|          | VISIT_TIME_DESC | C    | 8    |      |
|          | REGIST_FEE      | N    | 5,2  |      |
|          | CLINIC_FEE      | N    | 5,2  |      |

## 门诊挂号退号记录CLINIC_RETURNED_ACCT

|          |                   |      |      |              |
|----------|-------------------|------|------|--------------|
| 中文名称 | 字段名            | 类型 | 长度 | 说明         |
| 就诊时间 | VISIT_DATE        | D    |      | 挂号日期     |
| 就诊序号 | VISIT_NO          | N    | 5    | 挂号序号     |
| 号别     | CLINIC_LABEL      | C    | 16   |              |
| 时间     | TIME_DESC         | C    | 8    |              |
| ID号     | PATIENT_ID        | C    | 10   |              |
| 姓名     | PATIENT_NAME      | C    | 20   |              |
| 挂号费   | REGIST_FEE        | N    | 16,2 |              |
| 诊疗费   | CLINIC_FEE        | N    | 16,2 |              |
| 其他费   | OTHER_FEE         | N    | 16,2 |              |
|          | CLINIC_CHARGE     | N    | 16,2 |              |
| 操作员   | OPERATOR          | C    | 8    |              |
| 退号日期 | RETURNED_DATE     | D    |      |              |
| 退号员   | RETURNED_OPERATOR | C    | 8    |              |
| 结帐号   | ACCT_NO           | C    | 8    |              |
| 结帐日期 | ACCT_DATE_TIME    | D    |      |              |
| 流水号   | SERIAL_NO         | N    | 3    |              |
|          | RE_FLAG           | C    | 1    |              |
| 支付方式 | PAY_WAY           | C    | 8    | 如现金、支票 |
| 发票号码 | INVOICE_NO        | C    | 20   |              |

主键：就诊时间、就诊序号

## 待诊病人信息outp_counseled_clipat（针对174医院）

|              |                     |      |      |                                                                                                        |
|--------------|---------------------|------|------|--------------------------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名              | 类型 | 长度 | 说明                                                                                                   |
| 就诊时间     | VISIT_DATE          | D    |      | 挂号日期                                                                                               |
| 就诊序号     | VISIT_NO            | N    | 4    | 挂号序号                                                                                               |
| 挂号序号     | QUEUE_SEQUENCE      | N    | 3,0  | 实际是挂号序号                                                                                         |
| 队列名       | QUEUE_NAME          | C    | 16   | 实际是挂号号别clinic_label                                                                             |
| 号类         | CLINIC_TYPE         | C    | 8    | 挂号号类                                                                                               |
| 挂号科室     | REGISTER_DEPT       | C    | 8    | 挂号科室                                                                                               |
| 挂号时间     | REGISTER_DATE       | D    |      | 挂号时间                                                                                               |
| 医生         | Doctor              | C    | 8    | 开始为挂号时号别对应的医生，                                                                           |
| 医生编码     | Doctor_no           | C    | 16   | 分诊到医生后分诊后修改为所分到医生的编码（outp_doctor_regist表中doctor_no）;                           |
| 病人Id       | Patient_id          | C    | 10   | 病人ID号，来自挂号                                                                                     |
| 姓名         | Name                | C    | 8    | 病人姓名，来自挂号                                                                                     |
| 分诊处理状态 | counseled_indicator | N    | 1    | 0未分诊1已分诊 2已叫号                                                                                 |
| 分诊台编号   | COUNSEL \_NO        | C    | 8    | 分诊台的唯一标识号                                                                                     |
| 分诊人员     | Counsel_operator    | C    | 8    | 姓名                                                                                                   |
| 分诊时间     | Counsel_date        | D    |      |                                                                                                        |
| 诊室编码     | Room_code           | C    | 8    | 分诊到医生后，对应outp_doctor_regist表当天的room_code                                                  |
| 诊室名称     | Room_name           | C    | 40   | 分诊后屏幕显示使用rowscopy不可以使用下拉数据窗，考虑速度不使用过多表连接，所以，虽然有编码，还有名称。 |
| 分诊序号     | Wait_sequence       | N    | 5    | 病人所属分诊台分配的等待序号                                                                           |
| 优先级别     | Priority_grade      | N    | 2    | 默认99                                                                                                 |
| 优先原因     | Priority_reason     | C    | 20   |                                                                                                        |
| 体检标志     | Phyexam_flag        | N    | 1    | 1－指体检病人                                                                                          |

主键：就诊序号+就诊时间

索引：就诊序号+就诊时间

注释：本记录由分诊挂号时产生，分诊后填写与分诊有关的内容，门诊医生接诊后删除。

## 已分诊的特诊病人outp_counseled_exampat（针对174医院）

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 29%" />
<col style="width: 8%" />
<col style="width: 6%" />
<col style="width: 36%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>申请号</td>
<td>EXAM_NO</td>
<td>C</td>
<td>10</td>
<td>来源于exam_appoints</td>
</tr>
<tr class="odd">
<td>检查类别</td>
<td>EXAM_CLASS</td>
<td>C</td>
<td>6</td>
<td>来源于exam_appoints</td>
</tr>
<tr class="even">
<td>病人ID</td>
<td>PATIENT_ID</td>
<td>C</td>
<td>10</td>
<td>来源于exam_appoints</td>
</tr>
<tr class="odd">
<td>姓名</td>
<td>Name</td>
<td>C</td>
<td>8</td>
<td>来源于exam_appoints</td>
</tr>
<tr class="even">
<td>执行科室</td>
<td>Performed_by</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>诊室编码</td>
<td>Room_code</td>
<td>C</td>
<td>8</td>
<td>叫号后返填实际的呼叫诊室编码，《叫号》系统配置的实际诊室编码</td>
</tr>
<tr class="even">
<td>诊室名称</td>
<td>Room_name</td>
<td>C</td>
<td>40</td>
<td>叫号后返填实际的呼叫诊室名称。《叫号》系统配置的实际诊室编码对应的诊室名称。</td>
</tr>
<tr class="odd">
<td>分诊台编码</td>
<td>Counsel_no</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>分诊人</td>
<td>Counsel_operator</td>
<td>C</td>
<td>8</td>
<td>分诊操作员</td>
</tr>
<tr class="odd">
<td>分诊时间</td>
<td>Counsel_date</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td>等待序号</td>
<td>Wait_sequence</td>
<td>N</td>
<td>5,1</td>
<td>下一个等于当前最大号加1</td>
</tr>
<tr class="odd">
<td>当前状态</td>
<td>Worked_indicator</td>
<td>N</td>
<td>1</td>
<td><p>1－已分诊，2－已叫号，</p>
<p>3特诊完成</p></td>
</tr>
<tr class="even">
<td>优先级别</td>
<td>Priority_grade</td>
<td>N</td>
<td>2</td>
<td></td>
</tr>
<tr class="odd">
<td>优先原因</td>
<td>Priority_reason</td>
<td>C</td>
<td>20</td>
<td></td>
</tr>
<tr class="even">
<td>体检标志</td>
<td>Phyexam_flag</td>
<td>N</td>
<td>1</td>
<td>1－指体检病人</td>
</tr>
</tbody>
</table>

主键：申请号

## 分诊台管理科室outp_counsel_dept（针对174医院）

|              |                |      |      |                          |
|--------------|----------------|------|------|--------------------------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明                     |
| 分诊台编号   | COUNSEL \_NO   | C    | 8    | 分诊台的唯一标识号       |
| 科室编码     | Dept_code      | C    | 8    | 分诊台管理科室编码       |
| 开始分诊序号 | Begin_sequence | N    | 5    | 本诊室分诊病人的开始序号 |

> 主键：分诊台编号、诊室编码

## 分诊台管理医生 outp_counsel_doctor （针对174医院）

|              |                |      |      |                                                            |
|--------------|----------------|------|------|------------------------------------------------------------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明                                                       |
| 分诊台编码   | COUNSEL_NO     | C    | 8    | outp_counsel_node_dict分诊台编号对应                       |
| 医生编码     | DOCTOR_NO      | C    | 16   | Db_user                                                    |
| 诊室         | Room_code      | C    | 8    | 坐诊诊室编码                                               |
| 分诊起始序号 | BEGIN_SEQUENCE | N    | 5    | 同一分诊台管理的不同医生可以设置不同起始号，以免叫号混乱。 |

主键：分诊台编码 医生编码

注释：每个分诊台管理的医生

## 分诊台安排OUTP_COUNSEL_NODE_DICT

|              |                     |      |      |                          |
|--------------|---------------------|------|------|--------------------------|
| 中文名称     | 字段名              | 类型 | 长度 | 说明                     |
| 分诊台编号   | COUNSEL_NO          | C    | 8    |                          |
| 分诊台名称   | COUNSEL_NAME        | C    | 32   | 分诊台的名称             |
| 分诊方式     | COUNSEL_MODE        | N    | 1    | 0－自动分诊；1－主动分诊 |
| 是否自动选择 | AUTO_ASSIGN_PATIENT | N    | 1    | 0自动选择1主动选择       |
| 分诊台状态   | COUNSEL_STATE       | N    | 1    |                          |

## OUTP_COUNSEL_PATIENT_SOURCE(不使用)

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
|          | VISIT_DATE    | D    |      |      |
|          | VISIT_NO      | N    | 8    |      |
|          | PATIENT_ID    | C    | 10   |      |
|          | SERIAL_NO     | N    | 3    |      |
|          | NAME          | C    | 20   |      |
|          | SEX           | C    | 4    |      |
|          | IDENTITY      | C    | 10   |      |
|          | CHARGE_TYPE   | C    | 8    |      |
|          | CLINIC_LABEL  | C    | 16   |      |
|          | REGISTER_DATE | D    | 7    |      |
|          | REGISTER_DEPT | C    | 8    |      |
|          | STATUS        | N    | 1    |      |

## 分诊优先原因字典outp_counsel_priority（针对174医院）

|              |                 |      |      |                |
|--------------|-----------------|------|------|----------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明           |
| 编号         | Serial_no       | N    | 2    | 标示优先级高低 |
| 优先原因     | Priority_reason | C    | 20   |                |

主键：编号

## 分诊台与队列对照OUTP_COUNSEL_QUEUE

|            |                     |      |      |                          |
|------------|---------------------|------|------|--------------------------|
| 中文名称   | 字段名              | 类型 | 长度 | 说明                     |
| 分诊台编号 | COUNSEL_NO          | C    | 8    |                          |
| 队列名     | QUEUE_NAME          | C    | 20   | 一个队列对应一个多个号别 |
| 号别       | CLINIC_LABEL        | C    | 16   | 即挂号的号别             |
| 病人最大数 | MAX_LIMITED_PATIENT | N    | 3    |                          |

主键：分诊台编号，队列名，号别

## 医生呼叫消息outp_counsel_request_info

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 29%" />
<col style="width: 8%" />
<col style="width: 6%" />
<col style="width: 36%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>序号</td>
<td>SERIAL_NO</td>
<td>N</td>
<td>4</td>
<td>消息序号，序号发生器产生</td>
</tr>
<tr class="odd">
<td>分诊台编号</td>
<td>COUNSEL _NO</td>
<td>C</td>
<td>8</td>
<td>分诊台的唯一标识号</td>
</tr>
<tr class="even">
<td>信息类型</td>
<td>REQUEST_TYPE</td>
<td>N</td>
<td>1</td>
<td>1申请，2退诊，3声音呼叫,4一般消息</td>
</tr>
<tr class="odd">
<td>医生</td>
<td>DOCTOR</td>
<td>C</td>
<td>8</td>
<td>医生姓名。</td>
</tr>
<tr class="even">
<td>医生编码</td>
<td>Doctor_no</td>
<td>C</td>
<td>16</td>
<td>进行呼叫的医生编码，对于174应该为staff_dict.emp_no</td>
</tr>
<tr class="odd">
<td>医生诊室</td>
<td>Room_address</td>
<td>C</td>
<td>40</td>
<td>叫号系统配置的物理房间号</td>
</tr>
<tr class="even">
<td>队列名称</td>
<td>QUEUE_NAME</td>
<td>C</td>
<td>16</td>
<td>医生所在队列</td>
</tr>
<tr class="odd">
<td>呼叫内容</td>
<td>REQUEST_BODY</td>
<td>C</td>
<td>200</td>
<td>呼叫内容</td>
</tr>
<tr class="even">
<td>呼叫时间</td>
<td>REQUEST_TIME</td>
<td>D</td>
<td></td>
<td>呼叫时间，default sysdate</td>
</tr>
<tr class="odd">
<td>消息去向</td>
<td>MESSAGE_DIRECTION</td>
<td>N</td>
<td>1</td>
<td><ol type="1">
<li><p>分诊台发给医生站</p></li>
<li><p>医生站发给分诊台</p></li>
</ol></td>
</tr>
</tbody>
</table>

主键：呼叫时间、序号

## 分诊台队列管理outp_queue_dict

|              |                 |      |      |                                                            |
|--------------|-----------------|------|------|------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                       |
| 分诊台编号   | COUNSEL \_NO    | C    | 8    | 分诊台的唯一标识号                                         |
| 队列名称     | QUEUE \_NAME    | C    | 16   | 分诊台管理队列的名称，和门诊医生的出诊队列一样对应挂号号别 |
| 号别位置     | CLINIC_POSITION | var  | 20   |                                                            |

注释：此表定义了分诊台所管理的队列情况，由用户定义。

主键：分诊台编号，队列名称。

## 队列序号记录表outp_queue_sequence（针对174医院）

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 30%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 35%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>队列编码</td>
<td>queue_code</td>
<td>C</td>
<td>8</td>
<td><p>1．分诊到科室可以为科室编码</p>
<p>2．分诊到诊室可以为诊室编码</p>
<p>3．如果分诊到医生，不需要使用此表（可以在医生每天的出诊记录中记录序号。）</p></td>
</tr>
<tr class="odd">
<td>分诊日期</td>
<td>Counsel_date</td>
<td>D</td>
<td></td>
<td>yyyy－mm－dd</td>
</tr>
<tr class="even">
<td>当前序号</td>
<td>Counsel_sequence</td>
<td>N</td>
<td>5</td>
<td><p>每天每个分诊台从1开始,</p>
<p>或是每个科(诊)室从自己诊室的起始序号开始</p></td>
</tr>
<tr class="odd">
<td>已分诊人数</td>
<td>Counseled_num</td>
<td>N</td>
<td>3</td>
<td>队列当天的已分诊人数</td>
</tr>
</tbody>
</table>

主键：队列编号、分诊日期、当前序号

> 说明：每天每个分诊台进行分诊给病人分配序号时查询此表，取自己分诊诊室当天当前的序号加1。

## 发票重打日志REGIST_REPRINT_LOG

|          |                  |      |      |                  |
|----------|------------------|------|------|------------------|
| 中文名称 | 字段名           | 类型 | 长度 | 说明             |
| 操作员   | REPRINT_OPERATOR | C    | 8    | 即操作员         |
| 重打日期 | REPRINT_DATETIME | D    |      |                  |
| 老发票号 | OLD_INVOICE      | C    | 20   |                  |
| 新发票号 | NEW_INVOICE      | C    | 20   |                  |
| ID号     | PATIENT_ID       | C    | 10   |                  |
| 姓名     | PATIENT_NAME     | C    | 8    |                  |
| 就诊时间 | VISIT_DATE       | D    |      | 挂号日期         |
| 就诊序号 | VISIT_NO         | N    | 5    | 挂号序号         |
|          | REGISTERING_DATE | D    |      | 目前不知道有何用 |
| 应收     | COSTS            | N    | 5,2  |                  |
| 实收     | CHARGES          | N    | 5,2  |                  |

主键：操作员、重打日期、就诊时间、就诊序号

# 门诊医生

## 门诊病历记录OUTP_MR

|            |                  |      |      |                                  |
|------------|------------------|------|------|----------------------------------|
| 中文名称   | 字段名           | 类型 | 长度 | 说明                             |
| 病人标识号 | PATIENT_ID       | C    | 10   | 病人ID号，即建立病人主索引的号码 |
| 就诊时间   | VISIT_DATE       | D    |      | 挂号的时间                       |
| 就诊序号   | VISIT_NO         | N    | 4    | 挂号的序号                       |
| 主诉       | ILLNESS_DESC     | C    | 200  |                                  |
| 既往史     | ANAMNESIS        | C    | 80   |                                  |
| 家族史     | FAMILY_ILL       | C    | 80   |                                  |
| 婚姻史     | MARRITAL         | C    | 4    |                                  |
| 个人史     | INDIVIDUAL       | C    | 80   |                                  |
| 月经史     | MENSES           | C    | 80   |                                  |
| 简要病史   | MED_HISTORY      | C    | 2000 |                                  |
| 查体       | BODY_EXAM        | C    | 1000 |                                  |
| 诊断       | DIAG_DESC        | C    | 160  |                                  |
| 嘱咐       | ADVICE           | C    | 600  |                                  |
| 医生       | DOCTOR           | C    | 8    |                                  |
| 顺序号     | ORDINAL          | N    | 2    |                                  |
| 手术记录   | OPERATION_RECORD | C    | 2000 | 文字记录病人手术信息             |
| 病程记录   | MEDICAL_RECORD   | C    | 2000 | 文字记录病人病程记录             |
| 中医诊断   | CDIAG            | var  | 160  |                                  |
| 发病日期   | ILLNESS_DATE     | date |      |                                  |
| 婚孕史     | MATERNITY        | V2   | 20   |                                  |

注释：病人每次就诊产生一条记录。

主键：就诊时间，就诊序号, 顺序号。

## 门诊病人体征信息Pat_soma \_chatacter

|          |                    |              |      |      |
|----------|--------------------|--------------|------|------|
| 中文名称 | 字段名             | 类型         | 长度 | 说明 |
| 就诊日期 | visit_date         | datetime     |      |      |
| 就诊序号 | Visit_no           | Number(5)    | 5    |      |
| 病人ID   | Patient_id         | Varchar2(20) | 20   |      |
| 检查时间 | Exam_date          | datetime     |      |      |
| 体重     | Weight             | N            | 4,1  |      |
| 身高     | Stature            | N            | 4,1  |      |
| 体温     | Temperature        | N            | 4,1  |      |
| 收缩压   | Bloodpressureh     | N            | 3    |      |
| 舒张压   | Bloodpressurel     | N            | 3    |      |
| 脉搏     | Pulse              | N            | 3    |      |
| 呼吸频率 | Breath_frequency   | N            | 3    |      |
| 头围     | HEAD_CIRCUMFERENCE | NUMBER       | 3,1  |      |
| 囟门     | FONTANELLE_MEASURE | NUMBER       | 3,1  |      |

主键： 就诊日期,就诊序号,病人ID,检查时间

## 中药模板主记录 CDRUG_PROJECT_MASTER

|              |                  |          |      |                                      |
|--------------|------------------|----------|------|--------------------------------------|
| 中文名       | 字段名           | 类型     | 长度 | 说明                                 |
| 模版号       | Treat_project_id | Number   | 6    | 中药模版序号                         |
| 创建医师     | creator          | Varchar2 | 16   | 创建医师                             |
| 创建医师科室 | dept_code        | Varchar2 | 8    | 创建医师所属科室                     |
| 适用范围     | flag             | Varchar2 | 1    | 模版适用范围，1-全院，2-科室，3-个人 |
| 用药途径     | administration   | Varchar2 | 16   |                                      |
| 用药频次     | frequency        | Varchar2 | 16   |                                      |
| 付数         | repetition       | Number   | 2    |                                      |
| 模版输入码   | input_code       | Varchar2 | 10   |                                      |
| 中文名称     | 字段名           | 类型     | 长度 | 说明                                 |
| 模板名称     | TITLE            | v        | 20   |                                      |

主健：模版号、创建医师

## 中药模板明细记录 CDRUG_PROJECT_ITEMS

|              |                  |          |      |                                      |
|--------------|------------------|----------|------|--------------------------------------|
| 字段中文名   | 字段名           | 类型     | 长度 | 说明                                 |
| 模版号       | Treat_project_id | Number   | 6    | 中药模版序号                         |
| 创建医师     | creator          | Varchar2 | 16   | 创建医师                             |
| 创建医师科室 | dept_code        | Varchar2 | 8    | 创建医师所属科室                     |
| 适用范围     | flag             | Varchar2 | 1    | 模版适用范围，1-全院，2-科室，3-个人 |
| 用药途径     | administration   | Varchar2 | 16   |                                      |
| 用药频次     | frequency        | Varchar2 | 16   |                                      |
| 付数         | repetition       | Number   | 2    |                                      |
| 模版输入码   | input_code       | Varchar2 | 10   |                                      |
| 中文名称     | 字段名           | 类型     | 长度 | 说明                                 |
| 模板名称     | TITLE            | v        | 20   |                                      |

Primary :模版号、创建医师、项目号

## 门诊医嘱主记录OUTP_ORDERS

|            |            |      |      |                                                                                                                                          |
|------------|------------|------|------|------------------------------------------------------------------------------------------------------------------------------------------|
| 中文名称   | 字段名     | 类型 | 长度 | 说明                                                                                                                                     |
| 病人标识号 | PATIENT_ID | C    | 10   | 病人ID号                                                                                                                                 |
| 就诊日期   | VISIT_DATE | D    |      | 挂号的时间                                                                                                                               |
| 就诊序号   | VISIT_NO   | N    | 4    | 挂号的序号                                                                                                                               |
| 流水号     | SERIAL_NO  | C    | 10   | 每次开单的流水号                                                                                                                         |
| 开单科室   | ORDERED_BY | C    | 8    |                                                                                                                                          |
| 开单医生   | DOCTOR     | C    | 8    |                                                                                                                                          |
| 开单日期   | ORDER_DATE | D    |      |                                                                                                                                          |
| 医生代码   | Doctor_no  | Var  | 16   | Db_name                                                                                                                                  |
| 护士登录名 | Nurse      | V2   | 16   | 现在在导诊中，护士可以录入治疗材料等。所以要加一列表明是护士录入的。如果是医生站录入的，则为空，如果是其它地方录入的，则为使用者的登录名 |

注释：病人一次门诊产生一条记录。

主键：流水号。

## 处方医嘱明细记录OUTP_PRESC

|            |                    |      |      |                                |
|------------|--------------------|------|------|--------------------------------|
| 中文名称   | 字段名             | 类型 | 长度 | 说明                           |
| 就诊日期   | VISIT_DATE         | D    |      | 挂号的日期                     |
| 就诊序号   | VISIT_NO           | N    | 4    | 挂号的序号                     |
| 流水号     | SERIAL_NO          | C    | 10   | 每次开单的流水号               |
| 处方序号   | PRESC_NO           | N    | 5    | 本次就诊的处方号               |
| 项目序号   | ITEM_NO            | N    | 2    | 本次就诊的项目顺序号           |
| 项目类别   | ITEM_CLASS         | C    | 1    | A为西药 B为草药                |
| 药名编码   | DRUG_CODE          | C    | 20   |                                |
| 药品名称   | DRUG_NAME          | C    | 100  |                                |
| 药品规格   | DRUG_SPEC          | C    | 20   |                                |
| 厂家标识   | FIRM_ID            | C    | 10   |                                |
| 单位       | UNITS              | C    | 8    |                                |
| 数量       | AMOUNT             | N    | 8,4  |                                |
| 一次用量   | DOSAGE             | N    | 8,4  |                                |
| 用量单位   | DOSAGE_UNITS       | C    | 8    |                                |
| 用药途径   | ADMINISTRATION     | C    | 16   | 对应comm..administration_dict  |
| 频次       | FREQUENCY          | C    | 16   |                                |
| 自备标记   | PROVIDED_INDICATOR | N    | 1    | 是否为自备药 ，0为不是，1为是  |
| 计价金额   | COSTS              | N    | 10,4 |                                |
| 实收费用   | CHARGES            | N    | 10,4 |                                |
| 收费标记   | CHARGE_INDICATOR   | N    | 1    | 是否已收费。0为未收费，1已收费 |
| 摆药药局   | DISPENSARY         | C    | 8    |                                |
| 付数       | REPETITION         | N    | 2    | 即中药的剂数                   |
| 医嘱组别   | ORDER_NO           | N    | 2    |                                |
| 子医嘱组别 | SUB_ORDER_NO       | N    | 2    |                                |
| 医嘱说明   | FREQ_DETAIL        | C    | 80   | 医生对该药品的说明             |
| 取药标志   | GETDRUG_FLAG       | C    | 2    | 1取药，2不取药                 |

主键：流水号、项目序号

## 检查治疗医嘱明细记录OUTP_TREAT_REC

|            |                  |      |      |                                  |
|------------|------------------|------|------|----------------------------------|
| 中文名称   | 字段名           | 类型 | 长度 | 说明                             |
| 就诊日期   | VISIT_DATE       | D    |      | 挂号的日期                       |
| 就诊序号   | VISIT_NO         | N    | 4    | 挂号的序号                       |
| 流水号     | SERIAL_NO        | C    | 10   | 每次开单的流水号                 |
| 项目序号   | ITEM_NO          | N    | 2    | 本次就诊的处置序号               |
| 项目类别   | ITEM_CLASS       | C    | 1    | 诊疗处置类别如C为化验D为检查等   |
| 项目编码   | ITEM_CODE        | C    | 20   |                                  |
| 项目名称   | ITEM_NAME        | C    | 100  |                                  |
| 项目规格   | ITEM_SPEC        | C    | 50   |                                  |
| 单位       | UNITS            | C    | 8    |                                  |
| 数量       | AMOUNT           | N    | 4    |                                  |
| 频次       | FREQUENCY        | C    | 16   |                                  |
| 执行科室   | PERFORMED_BY     | C    | 8    |                                  |
| 计价费用   | COSTS            | N    | 8,2  |                                  |
| 实收费用   | CHARGES          | N    | 8,2  |                                  |
| 收费标记   | CHARGE_INDICATOR | N    | 1    | 是否已收费。0为未收费，1已收费   |
| 申请号     | APPOINT_NO       | C    | 10   | 如果支持检验检查模块则填申请号码 |
| 申请明细号 | APPOINT_ITEM_NO  | N    | 2    |                                  |
| 医嘱说明   | FREQ_DETAIL      | C    | 80   |                                  |

> 注释：病人就诊过程中产生的检查治疗多条。

主键：流水号、项目序号

## 治疗方案模板主记录TREAT_PROJECT_MASTER

|                          |                  |      |      |                                   |
|--------------------------|------------------|------|------|-----------------------------------|
| 中文名称                 | 字段名           | 类型 | 长度 | 说明                              |
| 治疗模板标识             | TREAT_PROJECT_ID | C    | 6    | 唯一标识模板                      |
| 标题                     | TITLE            | C    | 40   |                                   |
| 科室                     | DEPT_CODE        | C    | 8    |                                   |
| 诊断描述                 | ADVICE           | C    | 600  |                                   |
| 建议                     | DIAGNOSIS        | C    | 80   |                                   |
| 创建者                   | CREATOR          | C    | 16   |                                   |
| 子标题                   | SUB_TITLE        | C    | 40   |                                   |
| 处置处方模版『适用范围』 | PROJECT_TYPE     | V2   | 1    | 有3种适用范围：处方、处置、通用； |

> 注释：此表为治疗方案模板的主记录,用于定义各种常规治疗方案模板，以便于用户输入治疗方案。该模板分别由各自科室定义与使用。

主键：治疗方案模板标识。

## 治疗方案模板明细TREAT_PROJECT_ITEMS

|              |                  |      |      |                                  |
|--------------|------------------|------|------|----------------------------------|
| 中文名称     | 字段名           | 类型 | 长度 | 说明                             |
| 治疗模板标识 | TREAT_PROJECT_ID | C    | 6    | 唯一标识模板                     |
| 序号         | ITEM_NO          | N    | 2    | 该治疗方案中医嘱的序号           |
| 医嘱类别     | ORDER_CLASS      | C    | 1    | 为药疗、检查、检验、处置、手术等 |
| 医嘱内容     | ORDER_TEXT       | C    | 80   | 描述医嘱的内容                   |
| 医嘱代码     | ORDER_CODE       | C    | 10   |                                  |
| 数量         | AMOUNT           | N    | 4    | 可以是药品的剂量、检查处置的次数 |
| 产商         | FIRM_ID          | C    | 10   |                                  |
| 单次用量     | DOSAGE           | N    | 8,4  |                                  |
| 单次用量单位 | DOSAGE_UNITS     | C    | 8    |                                  |
| 规格         | SPEC             | C    | 20   |                                  |
| 发药单位     | UNITS            | C    | 16   | 对应上面的数量的单位             |
| 给药途径     | ADMINISTRATION   | C    | 16   | 如为药品，描述用药方法           |
| 执行频率描述 | FREQUENCY        | C    | 16   | 执行的频度的描述                 |
| 执行科室     | PERFORMED_BY     | C    | 8    |                                  |
| 处方号       | ORDER_NO         | N    | 2    |                                  |
| 子处方号     | SUB_ORDER_NO     | N    | 2    |                                  |
| 医嘱说明     | FREQ_DETAIL      | C    | 80   |                                  |

注释：此表为治疗方案模板主记录的明细记录，包含了方案中各医嘱的主要内容。

主键：治疗方案模板标识、序号

## 门诊医嘱主记录队列OUTP_ORDERS_T

|            |            |      |      |      |
|------------|------------|------|------|------|
| 中文名称   | 字段名     | 类型 | 长度 | 说明 |
| 病人标识号 | PATIENT_ID | C    | 10   |      |
| 就诊日期   | VISIT_DATE | D    |      |      |
| 就诊序号   | VISIT_NO   | N    | 4    |      |
| 流水号     | SERIAL_NO  | C    | 10   |      |
| 开单科室   | ORDERED_BY | C    | 8    |      |
| 开单医生   | DOCTOR     | C    | 8    |      |
| 开单日期   | ORDER_DATE | D    |      |      |
| 医生代码   | doctor_no  | VAR  | 16   |      |

注释：病人一次门诊产生一条记录。字段的说明与OUTP_ORDERS相同

主键：流水号。

## 处方医嘱队列OUTP_PRESC_T

|              |                    |      |      |                                    |
|--------------|--------------------|------|------|------------------------------------|
| 中文名称     | 字段名             | 类型 | 长度 | 说明                               |
| 就诊日期     | VISIT_DATE         | D    |      |                                    |
| 就诊序号     | VISIT_NO           | N    | 24   |                                    |
| 流水号       | SERIAL_NO          | C    | 10   |                                    |
| 处方序号     | PRESC_NO           | N    | 5    |                                    |
| 项目序号     | ITEM_NO            | N    | 2    |                                    |
| 项目类别     | ITEM_CLASS         | C    | 1    |                                    |
| 药名编码     | DRUG_CODE          | C    | 20   |                                    |
| 药品名称     | DRUG_NAME          | C    | 100  |                                    |
| 药品规格     | DRUG_SPEC          | C    | 20   |                                    |
| 厂家标识     | FIRM_ID            | C    | 10   |                                    |
| 单位         | UNITS              | C    | 8    |                                    |
| 数量         | AMOUNT             | N    | 8,4  |                                    |
| 一次用量     | DOSAGE             | N    | 8,4  |                                    |
| 一次用量单位 | DOSAGE_UNITS       | C    | 8    |                                    |
| 用药途径     | ADMINISTRATION     | C    | 16   |                                    |
| 频次         | FREQUENCY          | C    | 16   |                                    |
| 自备标记     | PROVIDED_INDICATOR | N    | 1    |                                    |
| 收费标记     | CHARGE_INDICATOR   | N    | 1    |                                    |
| 摆药药局     | DISPENSARY         | C    | 8    |                                    |
| 付数         | REPETITION         | N    | 2    |                                    |
| 医嘱组别     | ORDER_NO           | N    | 2    |                                    |
| 子医嘱组别   | SUB_ORDER_NO       | N    | 2    |                                    |
| 取药标志     | GETDRUG_FLAG       | C    | 2    |                                    |
| 配药人       | dispensation_by    | Var2 | 20   |                                    |
| 配药日期     | dispensation_date  | date |      |                                    |
| 状态         | status             | N    | 1    | 审核摆药功能,0 or null 录入 1-审核 |

字段的说明与OUTP_presc相同

主键：流水号、项目序号

## 检查治疗医嘱队列OUTP_TREAT_REC_T

|            |                  |      |      |      |
|------------|------------------|------|------|------|
| 中文名称   | 字段名           | 类型 | 长度 | 说明 |
| 就诊日期   | VISIT_DATE       | D    |      |      |
| 就诊序号   | VISIT_NO         | N    | 4    |      |
| 流水号     | SERIAL_NO        | C    | 10   |      |
| 项目序号   | ITEM_NO          | N    | 2    |      |
| 项目类别   | ITEM_CLASS       | C    | 1    |      |
| 项目编码   | ITEM_CODE        | C    | 20   |      |
| 项目名称   | ITEM_NAME        | C    | 100  |      |
| 项目规格   | ITEM_SPEC        | C    | 50   |      |
| 单位       | UNITS            | C    | 8    |      |
| 数量       | AMOUNT           | N    | 4    |      |
| 频次       | FREQUENCY        | C    | 16   |      |
| 执行科室   | PERFORMED_BY     | C    | 8    |      |
| 收费标记   | CHARGE_INDICATOR | N    | 1    |      |
| 申请号     | APPOINT_NO       | C    | 10   |      |
| 申请明细号 | APPOINT_ITEM_NO  | N    | 2    |      |

字段的说明与OUTP_TREAT_REC相同

主键：流水号、项目序号。

## 诊室候诊排队记录OUTP_WAIT_QUEUE

|              |                  |      |      |                                                                             |
|--------------|------------------|------|------|-----------------------------------------------------------------------------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明                                                                        |
| 就诊时间     | VISIT_DATE       | D    |      | 挂号的日期                                                                  |
| 就诊序号     | VISIT_NO         | N    | 4    | 挂号的序号                                                                  |
| 排队序号     | QUEUE_SEQUENCE   | N    | 3    | 排队序号                                                                    |
| 分诊处名     | CONSULATION_NAME | C    | 8    | 分诊台名称                                                                  |
| 队列名       | QUEUE_NAME       | C    | 20   | 即挂号号别                                                                  |
| 就诊科室     | REGISTER_DEPT    | C    | 8    |                                                                             |
| 就诊日期     | REGISTER_DATE    | D    |      |                                                                             |
| 已处理标志   | WORKED_INDICATOR | N    | 1    | 用来区分该候诊病人是否已处理，由医生接诊后将此标志置为1。定期将此类记录删除 |
| 接诊医生     | DOCTOR           | C    | 8    |                                                                             |
| 分诊人       | DOCTOR_NO        | C    | 16   |                                                                             |
| 分诊台编号   | COUNSEL_NO       | C    | 32   |                                                                             |
| 等待顺序     | WAIT_SEQUENCE    | N    | 4    |                                                                             |

> 注释：本记录由分诊挂号时产生，门诊医生接诊后定期删除。
>
> 主键：分诊科室，诊室名，排队序号，就诊日期注释：本记录由分诊挂号时产生，门诊医生接诊后定期删除。

## 门诊医生值班安排 OUTP_DOCTOR_SCHEDULE

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 38%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 26%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>坐诊科室</td>
<td>CLINIC_DEPT</td>
<td>C</td>
<td>8</td>
<td>即dept_dict字典</td>
</tr>
<tr class="odd">
<td>坐诊医生</td>
<td>DOCTOR</td>
<td>C</td>
<td>8</td>
<td>医生姓名</td>
</tr>
<tr class="even">
<td>星期几</td>
<td>DAY_OF_WEEK</td>
<td>N</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td>时间段</td>
<td>CLINIC_DURATION</td>
<td>C</td>
<td>8</td>
<td>如上午、下午等</td>
</tr>
<tr class="even">
<td>队列名</td>
<td>QUEUE_NAME</td>
<td>C</td>
<td>20</td>
<td>不支持分诊时就是号别名</td>
</tr>
<tr class="odd">
<td>分诊台编号</td>
<td>COUNSEL_NO</td>
<td>C</td>
<td>8</td>
<td>可以为空</td>
</tr>
<tr class="even">
<td>数据库用户名</td>
<td>DOCTOR_NO</td>
<td>C</td>
<td>16</td>
<td>数据库用户名</td>
</tr>
<tr class="odd">
<td>是否经过分诊台分诊后才能看到病人</td>
<td>AUTO_ASSIGN_PATIENT</td>
<td>C</td>
<td>1</td>
<td><p>0为经过分诊台分诊，</p>
<p>1为不经过分诊台分诊</p></td>
</tr>
</tbody>
</table>

注释：主键 坐诊科室, 星期几, 时间段, 数据库用户名,队列名

## 门诊医生坐诊日志OUTP_DOCTOR_REGIST

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 31%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>分诊台编号</td>
<td>COUNSEL_NO</td>
<td>C</td>
<td>8</td>
<td>0-内科 1-外科 2-妇产科 3-儿科</td>
</tr>
<tr class="odd">
<td>诊室代码</td>
<td>CLINIC_DEPT</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>数据库用户代码</td>
<td>DOCTOR_NO</td>
<td>C</td>
<td>16</td>
<td></td>
</tr>
<tr class="odd">
<td>用户名称</td>
<td>DOCTOR</td>
<td>C</td>
<td>8</td>
<td>医生姓名</td>
</tr>
<tr class="even">
<td>坐诊日期</td>
<td>COUNSEL_DATE</td>
<td>D</td>
<td>Y</td>
<td>具体的日期</td>
</tr>
<tr class="odd">
<td>时间段</td>
<td>CLINIC_DURATION</td>
<td>C</td>
<td>8</td>
<td>如上午、下午</td>
</tr>
<tr class="even">
<td>队列名</td>
<td>QUEUE_NAME</td>
<td>C</td>
<td>20</td>
<td></td>
</tr>
<tr class="odd">
<td>是否经过分诊台分诊后才能看到病人</td>
<td>AUTO_ASSIGN_PATIENT</td>
<td>C</td>
<td>1</td>
<td><p>0为经过分诊台分诊，</p>
<p>1为不经过分诊台分诊</p></td>
</tr>
<tr class="even">
<td>签到否</td>
<td>SIGN_INDICATOR</td>
<td>C</td>
<td>1</td>
<td>0或NULL表示未签到，1为已签到</td>
</tr>
<tr class="odd">
<td>签到时间</td>
<td>SING_TIME</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td>下班否</td>
<td>LEAVE_INDICATOR</td>
<td>C</td>
<td>1</td>
<td>0或NULL表示未下班，1为已下班</td>
</tr>
<tr class="odd">
<td>下班时间</td>
<td>LEAVE_TIME</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td>已分诊人数</td>
<td>COUNSELED_NUM</td>
<td>N</td>
<td>4,0</td>
<td></td>
</tr>
<tr class="odd">
<td>坐诊地址</td>
<td>ADDRESS</td>
<td>C</td>
<td>40</td>
<td></td>
</tr>
<tr class="even">
<td>最大顺序号</td>
<td>MAX_SEQUENCE</td>
<td>N</td>
<td>4,1</td>
<td>（针对174医院）</td>
</tr>
<tr class="odd">
<td>下一个分诊序号</td>
<td>NEXT_SEQUENCE</td>
<td>N</td>
<td>5</td>
<td>队列中下一个病人序号（针对174医院）</td>
</tr>
<tr class="even">
<td>诊室</td>
<td>ROOM_CODE</td>
<td>C</td>
<td>8</td>
<td>坐诊诊室编码（针对174医院）</td>
</tr>
</tbody>
</table>

- 主键：数据库用户代码、坐诊日期、时间段

## 门诊医生检查主记录EXAM_MASTER_OUTP(不使用)

|          |        |      |      |      |
|----------|--------|------|------|------|
| 中文名称 | 字段名 | 类型 | 长度 | 说明 |
|          |        |      |      |      |

## 门诊医生检查项目记录EXAM_ITEMS_OUTP(不使用)

|          |        |      |      |      |
|----------|--------|------|------|------|
| 中文名称 | 字段名 | 类型 | 长度 | 说明 |
|          |        |      |      |      |

## 门诊病历诊断记录OUTP_MR_DIAG_DESC

|              |            |      |      |                                              |
|--------------|------------|------|------|----------------------------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                                         |
| 病人标识号   | PATIENT_ID | C    | 10   | 病人ID号                                     |
| 就诊时间     | VISIT_DATE | D    |      | 挂号的日期时间，由挂号预约系统提供           |
| 就诊序号     | VISIT_NO   | N    | 4    | 唯一标识一天内的某次就诊，由挂号预约系统提供 |
| 序号         | ITEM_NO    | n    | 3    | 记录流水号                                   |
| 诊断类型     | DIAG_TYPE  | C    | 8    | 如初步诊断，印象，诊断                       |
| 诊断代码     | DIAG_CODE  | C    | 60   | Diagnosis_dict表                             |
| 诊断名称     | DIAG_DESC  | C    | 160  | Diagnosis_dict表                             |

主键：就诊时间，就诊序号, 诊断名称。

## 门诊病历模板制作OUTP_MR_ITEMSELECT

|                |                      |      |      |                                     |
|----------------|----------------------|------|------|-------------------------------------|
| 字段中文名称   | 字段名               | 类型 | 长度 | 说明                                |
| 模板标志       | ITEM_PROJECT         | C    | 30   | 如主述，过去史等                    |
| 模板标志子索引 | SUB_ITEM_PROJECT     | c    | 30   | 一般为1                             |
| 模板属性       | FLAG                 | c    | 1    | 1为全院公共2为本科室公共3为个人所有 |
| 制作人         | OPERATOR_NO          | C    | 16   |                                     |
| 模板内容       | ITEM_PROJECT_CONTENT | C    | 1000 |                                     |

## 门诊病历模板选择OUTP_MR_ITEMCHOOSE

|                |                      |      |      |                  |
|----------------|----------------------|------|------|------------------|
| 字段中文名称   | 字段名               | 类型 | 长度 | 说明             |
| 模板标志       | ITEM_PROJECT         | C    | 30   | 如主述，过去史等 |
| 模板标志子索引 | SUB_ITEM_PROJECT     | c    | 30   | 一般为1          |
| 所有者         | OPERATOR_NO          | C    | 16   |                  |
| 模板内容       | ITEM_PROJECT_CONTENT | C    | 1000 |                  |

## 门诊医生收费明细OUTP_ORDERS_COSTS

|              |                    |      |      |                                                               |
|--------------|--------------------|------|------|---------------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                                          |
| ID号         | PATIENT_ID         | C    | 10   | 病人的主索引号                                                |
| 就诊日期     | VISIT_DATE         | D    |      | 挂号的时间                                                    |
| 就诊序号     | VISIT_NO           | N    | 4    | 挂号的序号                                                    |
| 流水号       | SERIAL_NO          | C    | 10   |                                                               |
| 诊疗项目类别 | ORDER_CLASS        | C    | 1    |                                                               |
| 医嘱号       | ORDER_NO           | N    | 2    |                                                               |
| 子医嘱号     | ORDER_SUB_NO       | N    | 2    |                                                               |
| 顺序号       | ITEM_NO            | N    | 2    | 药品一律为1，处置类如果有多个收费项目则为流水号1，2，3否则为1 |
| 收费项目类别 | ITEM_CLASS         | C    | 1    |                                                               |
| 项目名称     | ITEM_NAME          | C    | 40   |                                                               |
| 项目代码     | ITEM_CODE          | C    | 10   |                                                               |
| 项目规格     | ITEM_SPEC          | C    | 20   |                                                               |
| 单位         | UNITS              | C    | 8    | 见计量单位字典                                                |
| 付数         | REPETITION         | N    | 2    | 即中药的剂数                                                  |
| 数量         | AMOUNT             | N    | 8    | 对应于上面的规格、单位的药品总的数量                          |
| 录入科室     | ORDERED_BY_DEPT    | C    | 8    |                                                               |
| 录入医生     | ORDERED_BY_DOCTOR  | C    | 8    |                                                               |
| 执行科室     | PERFORMED_BY       | C    | 8    |                                                               |
| 收费项目分类 | CLASS_ON_RCPT      | C    | 1    |                                                               |
| 计价金额     | COSTS              | N    | 10,4 | 按标准价格计算得到的费用                                      |
| 实收费用     | CHARGES            | N    | 10,4 | 考虑费别等因素后的实际支付费用                                |
| 收据号码     | RCPT_NO            | C    | 8    |                                                               |
|              | Bill_desc_no       |      |      | 目前暂时未用到                                                |
|              | Bill_item_no       |      |      | 目前暂时未用到                                                |
| 收费标记     | CHARGE_INDICATOR   | N    | 1    | 1-已收费，0-未收费                                            |
| 核算项目分类 | class_on_reckoning | C    | 10   | Reck_item_class_dict表                                        |
| 会计科目     | subj_code          | C    | 3    | Tally_subject_dict表                                          |
| 收费系数     | price_quotiety     | N    | 7,4  |                                                               |
| 单价         | item_price         | N    | 10,4 |                                                               |
| 项目收费日期 | BILL_DATE          | date |      |                                                               |
| 项目收费编号 | BILL_NO            | n    | 5    |                                                               |

主键：流水号、诊疗项目类别、医嘱号，顺序号

## 队列序号记录表outp_queue_sequence（针对174医院）

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 30%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 35%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>队列编码</td>
<td>queue_code</td>
<td>C</td>
<td>8</td>
<td><p>1．分诊到科室可以为科室编码</p>
<p>2．分诊到诊室可以为诊室编码</p>
<p>3．如果分诊到医生，不需要使用此表（可以在医生每天的出诊记录中记录序号。）</p></td>
</tr>
<tr class="odd">
<td>分诊日期</td>
<td>Counsel_date</td>
<td>D</td>
<td></td>
<td>yyyy－mm－dd</td>
</tr>
<tr class="even">
<td>当前序号</td>
<td>Counsel_sequence</td>
<td>N</td>
<td>5</td>
<td><p>每天每个分诊台从1开始,</p>
<p>或是每个科(诊)室从自己诊室的起始序号开始</p></td>
</tr>
<tr class="odd">
<td>已分诊人数</td>
<td>Counseled_num</td>
<td>N</td>
<td>3</td>
<td>队列当天的已分诊人数</td>
</tr>
</tbody>
</table>

主键：队列编号、分诊日期、当前序号

说明：每天每个分诊台进行分诊给病人分配序号时查询此表，取自己分诊诊室当天当前的序号加1。

## 门诊医生会诊主索引OUTP_CONSULTATION_MASTER(新增)

|              |                           |      |      |                                   |
|--------------|---------------------------|------|------|-----------------------------------|
| 字段中文名称 | 字段名                    | 类型 | 长度 | 说明                              |
| 就诊时间     | VISIT_DATE                | D    |      | 挂号的时间                        |
| 就诊序号     | VISIT_NO                  | N    | 4    | 挂号的序号                        |
| ID号         | PATIENT_ID                | C    | 10   | 病人的主索引号                    |
| 会诊序号     | CONSULTATION_ID           | N    | 3    | 针对该挂号病人作的第几次会诊      |
| 会诊类型     | CONSULTATION_TYPE         | N    | 1    | 1为普通会诊2为紧急会诊3为其他会诊 |
| 会诊说明     | CONSULTATION_EXPLAIN      | C    | 200  |                                   |
| 会诊请求时间 | APPLY_DATE_TIME           | D    |      |                                   |
| 会诊结束时间 | END_DATE_TIME             | D    |      |                                   |
| 会诊人       | CONSULTATION_APPLY_DOCTOR | C    | 16   | 数据库的用户名                    |

主键：就诊时间，就诊序号，会诊序号

## 门诊医生会诊明细OUTP_CONSULTATION_DETAIL(新增)

|              |                     |      |      |                                  |
|--------------|---------------------|------|------|----------------------------------|
| 字段中文名称 | 字段名              | 类型 | 长度 | 说明                             |
| 就诊时间     | VISIT_DATE          | D    |      | 挂号的时间                       |
| 就诊序号     | VISIT_NO            | N    | 4    | 挂号的序号                       |
| ID号         | PATIENT_ID          | C    | 10   | 病人的主索引号                   |
| 会诊序号     | CONSULTATION_ID     | N    | 3    | 针对该挂号病人作的第几次会诊     |
| 会诊子序号   | SUB_ID              | N    | 3    | 每次会诊的子顺序号               |
| 会诊科室     | CONSULTATION_DEPT   | C    | 8    | 要请求会诊的科室                 |
| 会诊医生     | CONSULTATION_DOCTOR | C    | 16   | 要请求会诊的医生（数据库用户名） |
| 录入请求时间 | APPLY_DATE_TIME     | D    |      |                                  |
| 会诊意见     | CONSULTATION_IDEA   | C    | 200  |                                  |
| 提交时间     | COMMIT_DATE_TIME    | D    |      |                                  |
| 提交否       | CONSULTATION_COMMIT | N    | 1    | 1为已经提交                      |

主键：就诊时间，就诊序号，会诊序号,会诊子序号

## 公共模板索引字典 model_project_dict (新增)

|                  |                   |          |          |                                            |
|------------------|-------------------|----------|----------|--------------------------------------------|
| **字段中文名**   | **字段名**        | **类型** | **长度** | **说明**                                   |
| 项目序号         | Serial_no         | Number   |          | **关键字**                                 |
| 模板类型字段名称 | Item_project      | Varchar2 | 20       | 记录模板使用表字段名称                     |
| 模板字段显示名称 | Project_name      | Varchar2 | 20       | 记录模板使用表字段显示名称                 |
| 住院住院标识     | Inp_outp_flag     | Char     | 1        | 标识记录适用于住院、门诊，1--住院，0--门诊 |
| 使用接口         | Interface_support | Varchar2 | 20       | 字段适用模块                               |

**主键：Serial_no，项目序号**

## 门诊住院公共模板 model_items （新增）

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 22%" />
<col style="width: 14%" />
<col style="width: 14%" />
<col style="width: 28%" />
</colgroup>
<tbody>
<tr class="odd">
<td><strong>字段中文名</strong></td>
<td><strong>字段名</strong></td>
<td><strong>类型</strong></td>
<td><strong>长度</strong></td>
<td><strong>说明</strong></td>
</tr>
<tr class="even">
<td>模板类型</td>
<td>Item_project</td>
<td>Varchar2</td>
<td></td>
<td>项目类型</td>
</tr>
<tr class="odd">
<td>模板类型子索引</td>
<td>Sub_item_project</td>
<td>Varchar2</td>
<td>20</td>
<td>模板项目调用时的标识索引</td>
</tr>
<tr class="even">
<td>适用范围</td>
<td>flag</td>
<td>char</td>
<td>20</td>
<td>项目适用范围：1-公共，2-科室，3-个人</td>
</tr>
<tr class="odd">
<td>项目内容</td>
<td>Item_project_content</td>
<td>Varchar2</td>
<td>1</td>
<td>项目实际内容</td>
</tr>
<tr class="even">
<td>项目用户</td>
<td>Operator_no</td>
<td>Varchar2</td>
<td>20</td>
<td>项目录入用户登陆用户名称</td>
</tr>
<tr class="odd">
<td>科室</td>
<td>Dept_code</td>
<td>Varchar2</td>
<td></td>
<td>用户所在科室</td>
</tr>
<tr class="even">
<td>住院门诊标识</td>
<td>Outp_inp_flag</td>
<td>Varchar2</td>
<td></td>
<td>标识记录适用于住院、门诊，1--住院，0--门诊</td>
</tr>
<tr class="odd">
<td>适用接口</td>
<td>Interface_support</td>
<td>Varchar2</td>
<td></td>
<td><p>适用接口，如：门诊病历(outp_mr</p>
<p>)等</p></td>
</tr>
<tr class="even">
<td>输入码</td>
<td>Input_code</td>
<td>Varchar2</td>
<td></td>
<td>项目拼音头输入码，</td>
</tr>
<tr class="odd">
<td>五笔输入码</td>
<td>Input_code_wb</td>
<td>Varchar2</td>
<td></td>
<td>项目其它规则输入码</td>
</tr>
</tbody>
</table>

**主键：item_project，sub_item_project，flag，item_project_content，operator_no，dept_code**

## 公共模板项目选择model_items_select (新增)

<table>
<colgroup>
<col style="width: 22%" />
<col style="width: 22%" />
<col style="width: 14%" />
<col style="width: 6%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr class="odd">
<td><strong>字段中文名</strong></td>
<td><strong>字段名</strong></td>
<td><strong>类型</strong></td>
<td><strong>长度</strong></td>
<td><strong>说明</strong></td>
</tr>
<tr class="even">
<td>模板类型</td>
<td>Item_project</td>
<td>Varchar2</td>
<td></td>
<td>项目类型</td>
</tr>
<tr class="odd">
<td>模板类型子索引</td>
<td>Sub_item_project</td>
<td>Varchar2</td>
<td>20</td>
<td>模板项目调用时的标识索引</td>
</tr>
<tr class="even">
<td>适用范围</td>
<td>flag</td>
<td>char</td>
<td>20</td>
<td>项目适用范围：1-公共，2-科室，3-个人</td>
</tr>
<tr class="odd">
<td>项目内容</td>
<td>Item_project_content</td>
<td>Varchar2</td>
<td>1</td>
<td>项目实际内容</td>
</tr>
<tr class="even">
<td>项目用户</td>
<td>Operator_no</td>
<td>Varchar2</td>
<td>20</td>
<td>项目录入用户登陆用户名称</td>
</tr>
<tr class="odd">
<td>住院门诊标识</td>
<td>Outp_inp_flag</td>
<td>Varchar2</td>
<td></td>
<td>标识记录适用于住院、门诊，1--住院，0--门诊</td>
</tr>
<tr class="even">
<td>适用接口</td>
<td>Interface_support</td>
<td>Varchar2</td>
<td></td>
<td><p>适用接口，如：门诊病历(outp_mr</p>
<p>)等</p></td>
</tr>
</tbody>
</table>

**主键：无**

# 住院病人管理

## 等床病人记录 WAIT_BED_PATS

|                  |                   |      |      |                                                                      |
|------------------|-------------------|------|------|----------------------------------------------------------------------|
| 字段中文名称     | 字段名            | 类型 | 长度 | 说明                                                                 |
| 病人等床序号     | WAIT_NO           | N    | 4    | 为等床病人分配的临时唯一标识号，非空                                 |
| 病人标识         | PATIENT_ID        | C    | 10   | 等床病人如果已建立主索引记录，则此项为该病人的唯一标识号，否则，为空 |
| 姓名             | NAME              | C    | 20   | 病人姓名                                                             |
| 姓名拼音         | NAME_PHONETIC     | C    | 16   | 病人姓名拼音，字间用一个空格分隔，超长截断                           |
| 性别             | SEX               | C    | 4    | 男、女、未知，见1.1性别字典                                          |
| 出生日期         | DATE_OF_BIRTH     | D    |      |                                                                      |
| 出生地           | BIRTH_PLACE       | C    | 6    | 指定省市县，使用代码，见2.2行政区字典                                |
| 身份             | IDENTITY          | C    | 10   | 使用规范名称，见1.6身份字典                                          |
| 费别             | CHARGE_TYPE       | C    | 8    | 使用规范名称，见1.9费别字典                                          |
| 通信地址         | MAILING_ADDRESS   | C    | 40   |                                                                      |
| 邮政编码         | ZIP_CODE          | C    | 6    | 对应通信地址的邮政编码                                               |
| 联系人           | CONTACT_PERSON    | C    | 8    | 联系人姓名                                                           |
| 联系电话         | PHONE_NUMBER      | C    | 16   |                                                                      |
| 门诊诊断         | CLINIC_DIAGNOSIS  | C    | 40   | 诊断描述                                                             |
| 病情             | PATIENT_CONDITION | C    | 1    | 使用代码，本系统定义，见1.21入院病情字典                             |
| 等床科室         | DEPT_WAITING_FOR  | C    | 8    | 床位单独管理的临床科室代码                                           |
| 接诊医生         | CONSULTING_DOCTOR | C    | 8    | 医生姓名                                                             |
| 登记日期         | REGISTERING_DATE  | D    |      | 等床登记日期                                                         |
| 最近一次通知日期 | LAST_NOTING_DATE  | D    |      | 通知入院日期                                                         |
| 通知次数         | NOTIFY_TIMES      | N    | 2    | 通知入院次数                                                         |
| 医疗体系病人标志 | SERVICE_AGENCY    | C    | 40   |                                                                      |
| 电话或邮件地址   | PHONE_NUMBER_MAIL | C    | 16   |                                                                      |
| 备注             | NOTICE            | C    | 80   |                                                                      |

注释：此表描述等床病人信息，为住院登记子系统所用。由预约登记生成，在病人作完入院登记手续后立即删除或定期手工删除。

## 床位记录 BED_REC

|                      |                    |      |      |                                                                  |
|----------------------|--------------------|------|------|------------------------------------------------------------------|
| 字段中文名称         | 字段名             | 类型 | 长度 | 说明                                                             |
| 病房（护理单元）代码 | WARD_CODE          | C    | 8    | 病床所在病房代码，见2.6科室字典                                  |
| 床号                 | BED_NO             | N    | 3    | 一个病房内部床位的唯一标识                                       |
| 床标号               | BED_LABEL          | C    | 8    | 床号的描述，用于显示                                             |
| 房间                 | ROOM_NO            | C    | 4    | 病床所在的房间号                                                 |
| 所属科室代码         | DEPT_CODE          | C    | 8    | 为统计科室代码，一个病房的床位可以分属于不同的科室               |
| 床位编制类型         | BED_APPROVED_TYPE  | C    | 1    | 在编、非编、加床等，见3.17床位编制类型字典                       |
| 床位类型             | BED_SEX_TYPE       | C    | 1    | 反映该床对病人性别的限制。见3.15床位类型字典                     |
| 床位等级             | BED_CLASS          | C    | 20   | 表示床位的收费等级，如2人间、3人间，使用代码，见3.17床位等级字典 |
| 床位状态             | BED_STATUS         | C    | 1    | 床位的占用状态，使用代码，见3.15床位状态字典                     |
| 借床标志             | LEND_ATTR          | C    | 1    |                                                                  |
| 借床科室             | LEND_BED_NO        | N    | 3    |                                                                  |
| 借床部门             | LEND_BED_DEPT      | C    | 8    |                                                                  |
| 借床护理单元         | LEND_BED_WARD      | C    | 8    |                                                                  |
| 是否锁住床位         | LOCK_STATUS        | C    | 1    |                                                                  |
| 锁床位操作员         | LOCK_OPERATOR      | C    | 8    |                                                                  |
| 空调类型             | AIRCONDITION_CLASS | C    | 20   |                                                                  |
| 病人ID               | Patient_id         | c    | 10   |                                                                  |

注释：本表反映一个医院的病床设置情况，由病房入出转子系统增删改。一张病床由所在病房和床号唯一标识。为了便于医疗统计，设置病床所属科室属性。

该表数据量与医院的床位数相一致，需长期保存。

## 在院病人记录 PATS_IN_HOSPITAL

|                    |                        |      |      |                                                                                                                                                                                            |
|--------------------|------------------------|------|------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称       | 字段名                 | 类型 | 长度 | 说明                                                                                                                                                                                       |
| 病人标识号         | PATIENT_ID             | C    | 10   | 非空                                                                                                                                                                                       |
| 病人本次住院标识   | VISIT_ID               | N    | 2    | 非空                                                                                                                                                                                       |
| 所在病房代码       | WARD_CODE              | C    | 8    | 病人住院登记后，将该字段置为空，在入科时，将该字段置为本病房代码，转科时，由转出科室将该代码置为空                                                                                         |
| 所在科室代码       | DEPT_CODE              | C    | 8    | 病人住院所属科室的代码。用于区分一个病房包含多个科室的床位的情况。病人住院登记后，将该字段置为空，在入科分配床位时，根据床位属性将该字段置为所在科室代码，转科时，由转出科室将该代码置为空 |
| 床号               | BED_NO                 | N    | 3    | 当入院处理时可为空                                                                                                                                                                         |
| 入院日期及时间     | ADMISSION_DATE_TIME    | D    | 7    | 由住院登记系统填入                                                                                                                                                                         |
| 入科日期及时间     | ADM_WARD_DATE_TIME     | D    | 7    | 指病人入当前所在病房的日期及时间，由病房入出转子系统填入，转科时置为空                                                                                                                     |
| 主要诊断           | DIAGNOSIS              | C    | 80   | 截止当前确定的主要诊断，正文描述。初始时，由住院登记子系统录入                                                                                                                             |
| 病情状态           | PATIENT_CONDITION      | C    | 1    | 病人危重情况，使用代码，见1.13病情状态字典                                                                                                                                                 |
| 护理等级           | NURSING_CLASS          | C    | 1    | 使用代码，见4.15护理等级字典                                                                                                                                                               |
| 经治医生           | DOCTOR_IN_CHARGE       | C    | 8    | 当前的经治医生姓名                                                                                                                                                                         |
| 手术日期           | OPERATING_DATE         | D    |      | 已进行最后一次手术的日期                                                                                                                                                                   |
| 计价截止日期及时间 | BILLING_DATE_TIME      | D    |      | 最近一次计价的日期，在该日期之间已发生的各种医疗费用已记帐                                                                                                                                 |
| 预交金余额         | PREPAYMENTS            | N    | 10,2 | 扣除已结算费用后病人的预交金金额（未扣除未结算部分）                                                                                                                                       |
| 累计未结费用       | TOTAL_COSTS            | N    | 10,2 | 病人未结算部分的费用。如果病人未进行中途结算，则为本次住院总费用。按正常价表计算得到                                                                                                       |
| 优惠后未结费用     | TOTAL_CHARGES          | N    | 10,2 | 按病人费别优惠后累计未结费用                                                                                                                                                               |
| 经济担保人         | GUARANTOR              | C    | 8    | 在住院登记时指定本病人的经济担保人                                                                                                                                                         |
| 经济担保人所在单位 | GUARANTOR_ORG          | C    | 40   | 正文描述                                                                                                                                                                                   |
| 经济担保人联系电话 | GUARANTOR_PHONE_NUM    | C    | 16   |                                                                                                                                                                                            |
| 上次划价检查日期   | BILL_CHECKED_DATE_TIME | D    |      | 最近一次划价审核的日期，每次由住院收费程序人工审核后更新                                                                                                                                   |
| 出院结算标记       | SETTLED_INDICATOR      | N    | 1    | 0-未进行出院结算 1-已进行出院结算入院时，由住院登记子系统将该字段置为0；出院结算时，由住院收费子系统将该字段置为1。                                                                        |
| 借床床位号         | LEND_BED_NO            | N    | 3    |                                                                                                                                                                                            |
| 床位科室代码       | BED_DEPT_CODE          | C    | 8    |                                                                                                                                                                                            |
| 床位护理单元       | BED_WARD_CODE          | C    | 8    |                                                                                                                                                                                            |
| 借床科室           | DEPT_CODE_LEND         | C    | 8    |                                                                                                                                                                                            |
| 借床标志           | LEND_INDICATOR         | N    | 1    |                                                                                                                                                                                            |
| 是否新生儿         | IS_NEWBORN             | N    | 1    |                                                                                                                                                                                            |

注释：此表反映所有在院病人的简要情况。病人入院时，由入院登记子系统生成，在病房修改，病人出院后对应的记录即删除。

本表的数据量与医院的床位数相当。

主键：病人标识号。

索引：所在病房代码、床号

> 所在科室代码

## 病人入出转及状态变化日志 ADT_LOG

|                  |               |      |      |                                                                                       |
|------------------|---------------|------|------|---------------------------------------------------------------------------------------|
| 字段中文名称     | 字段名        | 类型 | 长度 | 说明                                                                                  |
| 病房代码         | WARD_CODE     | C    | 8    | 病人所在病房代码                                                                      |
| 科室代码         | DEPT_CODE     | C    | 8    | 病人所属统计科室代码                                                                  |
| 记录日期及时间   | LOG_DATE_TIME | D    |      | 记录日志日期及时间亦即变化发生日期及时间                                              |
| 病人标识号       | PATIENT_ID    | C    | 10   | 状态发生改变的病人                                                                    |
| 病人本次住院标识 | VISIT_ID      | N    | 2    | 非空                                                                                  |
| 变化             | ACTION        | C    | 1    | 反映发生的入／出／转动作或病情状态变化，使用代码，由本系统定义，见3.8病人状态变化字典 |
| 办理人           | Operator_no   | var  | 10   |                                                                                       |

注释：此表用于记录病人在病房流动及病人病情变化的历史，以便为医疗统计提供任一统计区间的流动情况。其数据由病房入出转子系统在进行入出转操作及改变病人病情的同时生成。

该表的数据可以在病人出院且在流动情况统计区间已过去后删除。典型地，表中数据需保留一年。

如果平均每个病人生成3条变化记录，以1000张床位、平均住院日为20天计，每年的数据增长量为 365 / 20 \* 1000 \* 3，约为54,000条。

## 转科病人记录 PATS_IN_TRANSFERRING

|                |                       |      |      |                      |
|----------------|-----------------------|------|------|----------------------|
| 字段中文名称   | 字段名                | 类型 | 长度 | 说明                 |
| 病人标识号     | PATIENT_ID            | C    | 10   | 非空                 |
| 转出科室       | DEPT_TRANSFERRED_FROM | C    | 8    | 指最小统计科室的代码 |
| 转向科室       | DEPT_TRANSFERRED_TO   | C    | 8    | 指最小统计科室的代码 |
| 转出日期及时间 | TRANSFER_DATE_TIME    | D    |      |                      |

注释：此表用于记录正处于转科状态的病人。所谓转科状态是指转出科室已进行了转出处理，但转入科室尚未进行入科处理时病人所处的状态。此表相当于一个转科病人缓冲区，记录由入出转子系统在转出病人时生成，由转入科室在病人入科时删除。入院处看作转科处理，转出科室为空，转向科室为入院科室。

## 准备出院病人记录 PRE_DISCHGED_PATS

|                |                            |      |      |                        |
|----------------|----------------------------|------|------|------------------------|
| 字段中文名称   | 字段名                     | 类型 | 长度 | 说明                   |
| 病人标识号     | PATIENT_ID                 | C    | 10   | 非空                   |
| 预计出院日期   | DISCHARGE_DATE_EXPCTED     | D    |      |                        |
| 做出预计的时间 | CREATE_DATE_TIME           | D    |      | 创建本记录的时间       |
| 出院方式       | DISCHARGE_DISPOSITION_NAME | Var2 | 10   | 是储存的名称，不是代码 |

注释：此表用于记录将要出院的病人。此记录可为住院处提前了解空床提供方便，也可为住院收费处提前为病人结算提供方便。此记录由病房入出转子系统录入，在病人出院时或取消出院时删除。

此表的规模不超过在院病人数。

## 借床日志表LEND_BED_LOG(新增)

|              |                 |      |      |      |
|--------------|-----------------|------|------|------|
| 中文名称     | 字段名          | 类型 | 长度 | 说明 |
| 护理单元     | WARD_CODE       | C    | 8    |      |
| 借床起始日期 | LEND_START_DATE | D    |      |      |
| 病人ID       | PATIENT_ID      | C    | 10   |      |
| 住院次数     | VISIT_ID        | N    | 2    |      |
| 部门代码     | DEPT_CODE       | C    | 8    |      |
| 借床护理单元 | LEND_WARD_CODE  | C    | 8    |      |
| 借床科室代码 | LEND_DEPT_CODE  | C    | 8    |      |
| 借床结束日期 | LEND_END_DATE   | D    |      |      |

## 经管医生记录ORDERS_GROUP_REC(新增)

|            |                  |      |      |                                      |
|------------|------------------|------|------|--------------------------------------|
| 中文名称   | 字段名           | 类型 | 长度 | 说明                                 |
| 病人ID     | PATIENT_ID       | C    | 10   |                                      |
| 住院次数   | VISIT_ID         | N    | 2    |                                      |
| 科室代码   | DEPT_CODE        | C    | 8    |                                      |
| 核算组代码 | ORDER_GROUP      | C    | 8    |                                      |
| 经治医生   | ORDER_DOCTOR     | C    | 8    |                                      |
| 医生代码   | DOCTOR_USER      | C    | 16   |                                      |
| 上级医生   | SUPER_DOCTOR_ID  | Var  | 16   | 相应的（医师）代码值。，而不是姓名。 |
| 主任医生   | PARENT_DOCTOR_ID | Var  | 16   | 相应的（医师）代码值。，而不是姓名。 |
|            |                  |      |      |                                      |

## 病案质控日志MEDICAL_QC_LOG

|                  |             |      |      |      |
|------------------|-------------|------|------|------|
| 中文名称         | 字段名      | 类型 | 长度 | 说明 |
| 病人ID           | PATIENT_ID  | C    | 10   |      |
| 就诊号           | VISIT_ID    | N    | 2    |      |
| 检查科室         | DEPT_STAYED | C    | 8    |      |
| 检查日期         | CHECK_DATE  | D    |      |      |
| 检查者           | CHECKED_BY  | C    | 8    |      |
| 检查者的数据库名 | DB_USER     | C    | 16   |      |

## 质控信息病人信息表MEDICAL_QC_MSG

|                  |                  |      |      |                                            |
|------------------|------------------|------|------|--------------------------------------------|
| 中文名称         | 字段名           | 类型 | 长度 | 说明                                       |
| 病人标识号       | PATIENT_ID       | C    | 10   | 标识质控信息所针对的病人                   |
| 病人本次住院标识 | VISIT_ID         | N    | 2    | 非空                                       |
| 病人所在科室     | DEPT_STAYED      | C    | 8    | 病人所在科室                               |
| 病人经治医师     | DOCTOR_IN_CHARGE | C    | 8    | 主管该病人，对该质量事件负责的医生         |
| 质量问题分类     | QA_EVENT_TYPE    | C    | 16   | 反映问题所属类别，见质量问题分类字典       |
| 质量信息编号     | QC_MSG_CODE      | C    | 4    |                                            |
| 反馈信息         | MESSAGE          | C    | 80   | 由控制者反馈给医生或科室的信息体，自由描述 |
| 发出者           | ISSUED_BY        | C    | 8    | 质量控制者姓名                             |
| 发出时间         | ISSUED_DATE_TIME | D    |      | 发出该信息的日期及时间                     |
| 信息状态         | MSG_STATUS       | N    | 1    | 反馈信息从发出到确认的状态变化             |
| 信息确认时间     | ASK_DATE_TIME    | D    |      | 接收者收到信息后确认的时间                 |
|                  | DB_USER          | C    | 16   |                                            |
| 审批意见         | IDEA             | C    | 30   |                                            |
| 审批时间         | IDEA_DATE        | D    |      |                                            |

注释：此表用于记录质量控制机构对医疗过程及病案记录中发生的质量时间的反馈信息。反馈信息关联到每个病人或每份病案。反馈信息由事件类别与信息体描述。

主键：病人标识号、病人本次住院表识、发出时间。

#  医嘱

## 医嘱 ORDERS

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 31%" />
<col style="width: 0%" />
<col style="width: 2%" />
<col style="width: 5%" />
<col style="width: 7%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td colspan="3">类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>病人标识号</td>
<td>PATIENT_ID</td>
<td colspan="3">C</td>
<td>10</td>
<td>非空</td>
</tr>
<tr class="odd">
<td>病人本次住院标识</td>
<td>VISIT_ID</td>
<td colspan="3">N</td>
<td>2</td>
<td>非空</td>
</tr>
<tr class="even">
<td>医嘱序号</td>
<td>ORDER_NO</td>
<td colspan="3">N</td>
<td>4</td>
<td>一个病人的所有医嘱独立分配序号，按时间顺序，从小到大排序</td>
</tr>
<tr class="odd">
<td>医嘱子序号</td>
<td>ORDER_SUB_NO</td>
<td colspan="3">N</td>
<td>2</td>
<td>用于标识成组医嘱中的各医嘱项目，对独立的医嘱，为1，在成组医嘱内部，从1开始顺序排列</td>
</tr>
<tr class="even">
<td>长期医嘱标志</td>
<td>REPEAT_INDICATOR</td>
<td colspan="3">N</td>
<td>1</td>
<td>本医嘱是否长期医嘱，使用代码，1-长期，0-临时</td>
</tr>
<tr class="odd">
<td>医嘱类别</td>
<td>ORDER_CLASS</td>
<td colspan="3">C</td>
<td>1</td>
<td>指定药疗、处置、护理、膳食、其它等类别，使用代码，见3.6医嘱类别字典</td>
</tr>
<tr class="even">
<td>医嘱正文</td>
<td colspan="2">ORDER_TEXT</td>
<td colspan="2">C</td>
<td>200</td>
<td>医嘱内容</td>
</tr>
<tr class="odd">
<td>医嘱代码</td>
<td colspan="2">ORDER_CODE</td>
<td colspan="2">C</td>
<td>20</td>
<td>从临床角度对各类医嘱的每个项目分配一个代码，用于各系统间数据交换。如药品代码，检验项目代码等</td>
</tr>
<tr class="even">
<td>药品一次使用剂量</td>
<td colspan="2">DOSAGE</td>
<td colspan="2">N</td>
<td>8,4</td>
<td></td>
</tr>
<tr class="odd">
<td>剂量单位</td>
<td colspan="2">DOSAGE_UNITS</td>
<td colspan="2">C</td>
<td>8</td>
<td>规范描述，本系统定义，见4.20剂量单位字典</td>
</tr>
<tr class="even">
<td>给药途径和方法</td>
<td colspan="2">ADMINISTRATION</td>
<td colspan="2">C</td>
<td>16</td>
<td>规范描述，是判断生成何种治疗单的依据，本系统定义，见4.17给药途径字典</td>
</tr>
<tr class="odd">
<td>持续时间</td>
<td colspan="3">DURATION</td>
<td>N</td>
<td>2</td>
<td>一次执行的持续时间</td>
</tr>
<tr class="even">
<td>持续时间单位</td>
<td colspan="3">DURATION_UNITS</td>
<td>C</td>
<td>4</td>
<td>使用规范描述，本系统定义，见4.31时间单位字典</td>
</tr>
<tr class="odd">
<td>起始日期及时间</td>
<td colspan="3">START_DATE_TIME</td>
<td>D</td>
<td></td>
<td>本医嘱起始日期及时间</td>
</tr>
<tr class="even">
<td>停止日期及时间</td>
<td colspan="3">STOP_DATE_TIME_UNIT</td>
<td>D</td>
<td></td>
<td>本医嘱停止日期及时间</td>
</tr>
<tr class="odd">
<td>执行频率描述</td>
<td colspan="3">FREQUENCY</td>
<td>C</td>
<td>16</td>
<td>使用固定或固定格式的描述，如：3/日、TID，每xx分xx次，用户定义，见4.21医嘱执行频率字典</td>
</tr>
<tr class="even">
<td>频率次数</td>
<td colspan="3">FREQ_COUNTER</td>
<td>N</td>
<td>2</td>
<td>执行频率的次数部分</td>
</tr>
<tr class="odd">
<td>频率间隔</td>
<td colspan="3">FREQ_INTERVAL</td>
<td>N</td>
<td>2</td>
<td>执行频率的间隔部分</td>
</tr>
<tr class="even">
<td>频率间隔单位</td>
<td colspan="3">FREQ_INTERVAL_UNIT</td>
<td>C</td>
<td>4</td>
<td>使用标准描述，本系统定义，见4.31时间单位字典</td>
</tr>
<tr class="odd">
<td>执行时间详细描述</td>
<td colspan="3">FREQ_DETAIL</td>
<td>C</td>
<td>80</td>
<td>医嘱执行的详细时间表，用于对执行频率的补充，如：执行频率为3/日，补充为饭前执行或直接指定时间</td>
</tr>
<tr class="even">
<td>护士执行时间</td>
<td colspan="3">PERFORM_SCHEDULE</td>
<td>C</td>
<td>16</td>
<td>如：对3/日的时间表为8-12-6，由护士填入</td>
</tr>
<tr class="odd">
<td>执行结果</td>
<td colspan="3">PERFORM_RESULT</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>开医嘱科室</td>
<td colspan="3">ORDERING_DEPT</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>开医嘱医生</td>
<td colspan="3">DOCTOR</td>
<td>C</td>
<td>8</td>
<td>医生姓名</td>
</tr>
<tr class="even">
<td>停医嘱医生</td>
<td colspan="3">STOP_DOCTOR</td>
<td>C</td>
<td>8</td>
<td>停止本医嘱的医生姓名</td>
</tr>
<tr class="odd">
<td>开医嘱校对护士</td>
<td colspan="3">NURSE</td>
<td>C</td>
<td>8</td>
<td>医嘱开始时校对护士姓名</td>
</tr>
<tr class="even">
<td>停医嘱校对护士</td>
<td colspan="3">STOP_NURSE</td>
<td>C</td>
<td>8</td>
<td>医嘱停止时校对护士姓名</td>
</tr>
<tr class="odd">
<td>开医嘱录入日期及时间</td>
<td colspan="3">ENTER_DATE_TIME</td>
<td>D</td>
<td></td>
<td>开医嘱录入的日期及时间</td>
</tr>
<tr class="even">
<td>停医嘱录入日期及时间</td>
<td colspan="3">STOP_ORDER_DATE_TIME</td>
<td>D</td>
<td></td>
<td>开医嘱录入的日期及时间</td>
</tr>
<tr class="odd">
<td>医嘱状态</td>
<td colspan="3">ORDER_STATUS</td>
<td>C</td>
<td>1</td>
<td>反映医嘱的执行状态，如新开、校对、执行、停止等，使用代码，见4.19医嘱状态字典</td>
</tr>
<tr class="even">
<td>药品计价属性</td>
<td colspan="3">DRUG_BILLING_ATTR</td>
<td>N</td>
<td>1</td>
<td>反映药品是否计价，0-正常，1-自带药</td>
</tr>
<tr class="odd">
<td>计价属性</td>
<td colspan="3">BILLING_ATTR</td>
<td>N</td>
<td>1</td>
<td>反映本条医嘱计价方面的信息。0-正常计价 1-自带药 2-需手工计价 3-不计价。由护士录入医嘱时，根据医嘱内容确定。</td>
</tr>
<tr class="even">
<td>最后一次执行日期及时间</td>
<td colspan="3">LAST_PERFORM_DATE_TIME</td>
<td>D</td>
<td></td>
<td>对长期药品医嘱，由临床药局摆药时，将摆药的截止日期自动填入</td>
</tr>
<tr class="odd">
<td>最后一次计价日期及时间</td>
<td colspan="3">LAST_ACCTING_DATE_TIME</td>
<td>D</td>
<td></td>
<td>后台划价程序对本医嘱最近一次划价日期及时间。初始录入医嘱时，为空，由后台划价程序在每次划价后更新。</td>
</tr>
<tr class="even">
<td>对应处方号</td>
<td colspan="3">CURRENT_PRESC_NO</td>
<td>N</td>
<td>5</td>
<td></td>
</tr>
<tr class="odd">
<td>医生代码</td>
<td colspan="3">DOCTOR_USER</td>
<td>C</td>
<td>16</td>
<td></td>
</tr>
<tr class="even">
<td>校对时间</td>
<td colspan="3">VERIFY_DATA_TIME</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td>医嘱本打印标志</td>
<td colspan="3">ORDER_PRINT_INDICATOR</td>
<td>N</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td>转抄时间</td>
<td colspan="3">PROCESSION_DATE_TIME</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td>转抄护士</td>
<td colspan="3">PROCESSION_NURSE</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>停止医嘱转抄时间</td>
<td colspan="3">STOP_PROCESSION_DATE_TIME</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td>停止医嘱转抄护士</td>
<td colspan="3">STOP_PROCESSION_NURSE</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>作废时间</td>
<td colspan="3">CANCEL_DATE-TIME</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td>作废医生</td>
<td colspan="3">CANCEL-DOCTOR</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>检验申请号</td>
<td colspan="3">App_no</td>
<td>varchar2</td>
<td>20</td>
<td></td>
</tr>
<tr class="odd">
<td>是否需要手工调整执行单</td>
<td colspan="3">Is_adjust</td>
<td>N</td>
<td>1</td>
<td>需要调整为1，执行单医嘱为红色显示</td>
</tr>
<tr class="even">
<td>执行单生成日期</td>
<td colspan="3">CONVERSION_DATE_TIME</td>
<td>D</td>
<td></td>
<td>根据此记录判断此条医嘱是否被生成执行单</td>
</tr>
<tr class="odd">
<td>续静滴途径名</td>
<td colspan="3">CONTINUE_ORDER_NO</td>
<td>Var2</td>
<td>20</td>
<td>输入续静滴途径名</td>
</tr>
<tr class="even">
<td>停止医嘱标志</td>
<td colspan="3">stop_flag</td>
<td>Var2</td>
<td>21</td>
<td>使用F4停医嘱时标志为1</td>
</tr>
<tr class="odd">
<td>适应症标志</td>
<td colspan="3">ADAPT_SYMPTOM_INDICATE</td>
<td>n</td>
<td>1</td>
<td><ol type="1">
<li><p>适应症药品</p></li>
</ol>
<p>0．非适应症</p></td>
</tr>
</tbody>
</table>

注释：此表为在院病人医嘱表，该表面向已执行医嘱，兼顾临床需要和计价需要，兼顾药疗医嘱和其他类别的医嘱，其模型支持成组医嘱和父子医嘱。该表医嘱由病房分系统生成。

医嘱在病人出院，且完成相关统计后，将其转移到历史表中。典型地，需保留一年。

以每病人每日新开2条医嘱、1000张床位的医院计，每日新增医嘱2000条，每年新增700,000条。

## 医嘱计价项目 ORDERS_COSTS

|                  |              |      |      |                                                                                                                                              |
|------------------|--------------|------|------|----------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称     | 字段名       | 类型 | 长度 | 说明                                                                                                                                         |
| 病人标识号       | PATIENT_ID   | C    | 10   | 非空                                                                                                                                         |
| 病人本次住院标识 | VISIT_ID     | N    | 2    | 非空                                                                                                                                         |
| 医嘱序号         | ORDER_NO     | N    | 4    | 一个病人的所有医嘱独立分配序号，按时间顺序，从小到大排序                                                                                     |
| 医嘱子序号       | ORDER_SUB_NO | N    | 2    | 如果此计价项目对应一条医嘱明细记录，如药品，则此字段为对应的医嘱子序号；如果此项目不对应一条具体的医嘱明细记录，如为附加操作，则此字段为空。 |
| 计价项目序号     | ITEM_NO      | N    | 2    | 在一条医嘱内部唯一，从1开始顺序排列。                                                                                                        |
| 计价项目类别     | ITEM_CLASS   | C    | 1    | 价表项目类别，使用代码，见6.8价表项目分类字典                                                                                                |
| 计价项目名称     | ITEM_NAME    | C    | 100  | 此名称或者从医嘱内容中复制，或者由护士录入                                                                                                   |
| 计价项目代码     | ITEM_CODE    | C    | 20   | 项目对应的价表项目代码，如果计价项目不能对应到价表项目，则为空                                                                               |
| 计价项目规格     | ITEM_SPEC    | C    | 50   | 对药品，为本药品实际使用的规格，由护士或药局根据摆药结果而定                                                                                 |
| 计价单位         | UNITS        | C    | 8    | 从价表中自动提取                                                                                                                             |
| 数量             | AMOUNT       | N    | 8,4  | 项目数量。对药品，由一次使用剂量按对应使用规格转换得到的一次用药数量                                                                         |
| 累计数量         | TOTAL_AMOUNT | N    | 10,4 | 对长期医嘱为本项目的累计数量                                                                                                                 |
| 本项目累计费用   | COSTS        | N    | 8,2  | 对长期医嘱为各次执行费用之和，由后台计价程序填入                                                                                             |

注释：该表用于描述一条医嘱对应的各种收费项目，一条记录由医嘱号和项目序号唯一标识，医嘱子序号仅起关联作用。收费项目在录入医嘱时，根据医嘱内容自动生成，或由护士根据医嘱的具体执行信息，在录入医嘱时手工指定。如静滴医嘱，需要计药品费、静滴操作费、输液器费、注射器费等。这些计价项目，由后台计价程序对医嘱计价时使用。

此表数据的保留时间同医嘱主记录。

此表的规模略大于医嘱明细记录。

## 医嘱执行表orders_execute

|                  |                         |      |     |      |                                                                                                               |
|------------------|-------------------------|------|-----|------|---------------------------------------------------------------------------------------------------------------|
| 字段中文名称     | 字段名                  | 类型 |     | 长度 | 说明                                                                                                          |
| 执行医嘱生成时间 | CONVERSION_DATE_TIME    | D    |     |      | 医嘱执行的日期                                                                                                |
| 病人标识号       | PATIENT_ID              | C    |     | 10   | 非空                                                                                                          |
| 病人本次住院标识 | VISIT_ID                | N    |     | 2    | 非空                                                                                                          |
| 医嘱序号         | ORDER_NO                | N    |     | 4    | 一个病人的所有医嘱独立分配序号，按时间顺序，从小到大排序                                                      |
| 医嘱子序号       | ORDER_SUB_NO            | N    |     | 2    | 用于标识成组医嘱中的各医嘱项目，对独立的医嘱，为1，在成组医嘱内部，从1开始顺序排列                            |
| 医嘱默认执行时间 | ORDERS_PERFORM_SCHEDULE | C    |     | 16   | 每天的执行时间，从PERFORM_SCHEDULE转换来，如PERFORM_SCHEDULE值为9-14-20，那生成3条记录，分别执行时间为9,14,20 |
| 长期医嘱标志     | REPEAT_INDICATOR        | N    |     | 1    | 本医嘱是否长期医嘱，使用代码，1-长期，0-临时                                                                  |
| 医嘱类别         | ORDER_CLASS             | C    |     | 1    | 指定药疗、处置、护理、膳食、其它等类别，使用代码，见3.6医嘱类别字典                                           |
| 医嘱正文         | ORDER_TEXT              |      | C   | 80   | 医嘱内容                                                                                                      |
| 医嘱代码         | ORDER_CODE              |      | C   | 10   | 从临床角度对各类医嘱的每个项目分配一个代码，用于各系统间数据交换。如药品代码，检验项目代码等                  |
| 药品一次使用剂量 | DOSAGE                  |      | N   | 8,4  |                                                                                                               |
| 剂量单位         | DOSAGE_UNITS            |      | C   | 8    | 规范描述，本系统定义，见4.20剂量单位字典                                                                      |
| 给药途径和方法   | ADMINISTRATION          |      | C   | 16   | 规范描述，是判断生成何种治疗单的依据，本系统定义，见4.17给药途径字典                                          |
| 持续时间         | DURATION                | N    |     | 2    | 一次执行的持续时间                                                                                            |
| 持续时间单位     | DURATION_UNITS          | C    |     | 4    | 使用规范描述，本系统定义，见4.31时间单位字典                                                                  |
| 执行频率描述     | FREQUENCY               | C    |     | 16   | 使用固定或固定格式的描述，如：3/日、TID，每xx分xx次，用户定义，见4.21医嘱执行频率字典                         |
| 频率次数         | FREQ_COUNTER            | N    |     | 2    | 执行频率的次数部分                                                                                            |
| 频率间隔         | FREQ_INTERVAL           | N    |     | 2    | 执行频率的间隔部分                                                                                            |
| 频率间隔单位     | FREQ_INTERVAL_UNIT      | C    |     | 4    | 使用标准描述，本系统定义，见4.31时间单位字典                                                                  |
| 执行时间详细描述 | FREQ_DETAIL             | C    |     | 16   | 医嘱执行的详细时间表，用于对执行频率的补充，如：执行频率为3/日，补充为饭前执行或直接指定时间                  |
| 护士执行时间     | PERFORM_SCHEDULE        | C    |     | 16   | 当次的执行时间。                                                                                              |
| 执行结果         | PERFORM_RESULT          | C    |     | 8    |                                                                                                               |
| 药品计价属性     | DRUG_BILLING_ATTR       | N    |     | 1    | 反映药品是否计价，0-正常，1-自带药                                                                            |
| 药品摆药时间     | DRUG_DATE_TIME          | N    |     | 1    | 记录该条执行单的摆药时间。                                                                                    |
| 计价属性         | BILLING_ATTR            | N    |     | 1    | 反映本条医嘱计价方面的信息。0-正常计价 1-自带药 2-需手工计价 3-不计价。由护士录入医嘱时，根据医嘱内容确定。   |
| 医嘱执行生成护士 | CONVERSION_NURSE        | C    |     | 8    | 医嘱写入执行表的护士。                                                                                        |
| 医嘱执行时间     | EXECUTE_DATE_TIME       | D    |     |      | 当前医嘱执行时间                                                                                              |
| 医嘱执行护士     | EXECUTE_NURSE           | C    |     | 8    | 当前医嘱执行护士。                                                                                            |
| 实收金额         | CHARGE                  | N    |     | 8,2  | 本医嘱的执行后实收金额。                                                                                      |
| 计价金额         | COSTS                   | N    |     | 8,2  | 本医嘱的执行后计价金额。                                                                                      |
| 是否执行         | IS_EXECUTE              | N    |     | 1    | 执行为1，没执行为0                                                                                            |

说明:医嘱执行单是护士进行医嘱执行时首先进行生成医嘱执行单,数据写入此表中!

## 病人体症记录 VITAL_SIGNS_REC

|                  |                     |      |      |                                                            |
|------------------|---------------------|------|------|------------------------------------------------------------|
| 字段中文名称     | 字段名              | 类型 | 长度 | 说明                                                       |
| 病人标识号       | PATIENT_ID          | C    | 10   | 非空                                                       |
| 病人本次住院标识 | VISIT_ID            | N    | 2    | 非空                                                       |
| 记录日期         | RECORDING_DATE      | D    |      |                                                            |
| 时间点           | TIME_POINT          | D    |      | 每日记录有固定的时间点，此处为时间，取24小时制             |
| 记录项目         | VITAL_SIGNS         | C    | 16   | 记录病人体症项目名称，如体温、脉搏等，允许用户临时增加项目 |
| 项目数值         | VITAL_SIGNS_VALUES  | N    | 6,2  | 老系统用                                                   |
| 项目单位         | UNITS               | C    | 8    | 如千克、次、度等                                           |
| 类别代码         | CLASS_CODE          | C    | 1    |                                                            |
| 项目代码         | VITAL_CODE          | C    | 4    |                                                            |
| 项目数值         | VITAL_SIGNS_CVALUES | C    | 60   | 新系统用                                                   |

注释：本表用于描述病人体温单数据，即护理记录。每日每个病人有多个时间检查点，每次记录多个项目，每个时间点的每个项目连同项目名称、项目数值构成一条记录。该结构允许记录项目的变化。

由护士每日通过护士工作站录入。

此表数据的保留时间同医嘱主记录。

以每个病人记录3个项目、每日4个时间点、1000张床位计，每日该表的数据增长量为12,000条，每年的增长量为4,500,000条。

## 医嘱记录单影象 ORDERS_SHEET_IMAGE

|                          |                  |      |      |                           |
|--------------------------|------------------|------|------|---------------------------|
| 字段中文名称             | 字段名           | 类型 | 长度 | 说明                      |
| 病人标识号               | PATIENT_ID       | C    | 10   | 非空                      |
| 病人本次住院标识         | VISIT_ID         | N    | 2    | 非空                      |
| 医嘱记录单类型           | ORDER_SHEET_TYPE | N    | 1    | 0-长期医嘱 1-临时医嘱     |
| 页号                     | PAGE_NO          | N    | 2    | 医嘱记录单页号            |
| 行号                     | LINE_NO          | N    | 2    | 一页中的行号              |
| 该打印行对应的医嘱序号   | ORDER_NO         | N    | 4    |                           |
| 该打印行对应的医嘱子序号 | ORDER_SUB_NO     | N    | 2    |                           |
| 是否停止医嘱             | STOP_ORDER       | N    | 1    | 1已经打印停止医嘱,默认为0 |

注释：此表用于打印的记录医嘱记录单硬拷贝的详细内容，以便在续打、重打医嘱时，能准确复原原打印状态。

此表数据的保留时间同医嘱主记录。

此表数据的规模同医嘱明细记录。

## 医生医嘱 DOCTOR_ORDERS(不使用)

|                    |                       |      |     |      |                                                                                              |
|--------------------|-----------------------|------|-----|------|----------------------------------------------------------------------------------------------|
| 字段中文名称       | 字段名                | 类型 |     | 长度 | 说明                                                                                         |
| 病人标识号         | PATIENT_ID            | C    |     | 10   | 非空                                                                                         |
| 病人本次住院标识   | VISIT_ID              | N    |     | 2    | 非空                                                                                         |
| 医嘱序号           | ORDER_NO              | N    |     | 4    | 一个病人的所有医嘱独立分配序号，按时间顺序，从小到大排序                                     |
| 医嘱子序号         | ORDER_SUB_NO          | N    |     | 2    | 用于标识成组医嘱中的各医嘱项目，对独立的医嘱，为1，在成组医嘱内部，从1开始顺序排列           |
| 新开停止医嘱标志   | START_DATE_TIME       | D    |     |      | 表示该医嘱是起始医嘱或是停止医嘱，0-新起始医嘱，1-停止医嘱                                   |
| 医嘱开始生效时间   | START_STOP_INDICATOR  | N    |     | 1    | 医生指定的医嘱开始或停止生效的日期及时间                                                     |
| 长期医嘱标志       | REPEAT_INDICATOR      | N    |     | 1    | 本医嘱是否长期医嘱，使用代码，1-长期，0-临时                                                 |
| 医嘱类别           | ORDER_CLASS           | C    |     | 1    | 指定药疗、处置、护理、膳食、其它等类别，使用代码，见3.6医嘱类别字典                          |
| 医嘱正文           | ORDER_TEXT            |      | C   | 100  | 医嘱内容                                                                                     |
| 医嘱代码           | ORDER_CODE            |      | C   | 20   | 从临床角度对各类医嘱的每个项目分配一个代码，用于各系统间数据交换。如药品代码，检验项目代码等 |
| 药品一次使用剂量   | DOSAGE                |      | N   | 8,4  |                                                                                              |
| 剂量单位           | DOSAGE_UNITS          |      | C   | 8    | 规范描述，本系统定义，见4.20剂量单位字典                                                     |
| 给药途径和方法     | ADMINISTRATION        |      | C   | 16   | 规范描述，是判断生成何种治疗单的依据，本系统定义，见4.17给药途径字典                         |
| 持续时间           | DURATION              | N    |     | 2    | 一次执行的持续时间                                                                           |
| 持续时间单位       | DURATION_UNITS        | C    |     | 4    | 使用规范描述，本系统定义，见4.31时间单位字典                                                 |
| 执行频率描述       | FREQUENCY             | C    |     | 16   | 使用固定或固定格式的描述，如：3/日、TID，每xx分xx次，用户定义，见4.21医嘱执行频率字典        |
| 频率次数           | FREQ_COUNTER          | N    |     | 2    | 执行频率的次数部分                                                                           |
| 频率间隔           | FREQ_INTERVAL         | N    |     | 2    | 执行频率的间隔部分                                                                           |
| 频率间隔单位       | FREQ_INTERVAL_UNIT    | C    |     | 4    | 使用标准描述，本系统定义，见4.31时间单位字典                                                 |
| 执行时间详细描述   | FREQ_DETAIL           | C    |     | 80   | 医嘱执行的详细时间表，用于对执行频率的补充，如：执行频率为3/日，补充为饭前执行或直接指定时间 |
| 开医嘱科室         | ORDERING_DEPT         | C    |     | 8    |                                                                                              |
| 开医嘱医生         | DOCTOR                | C    |     | 8    | 医生姓名                                                                                     |
| 校对护士           | NURSE                 | C    |     | 8    | 护士姓名                                                                                     |
| 医嘱状态           | ORDER_STATUS          | C    |     | 1    | 反映医嘱的执行状态，如新开、提交等，使用代码，见4.19医嘱状态字典                             |
| 下达医嘱日期及时间 | ENTER_DATE_TIME       | D    |     |      | 下医嘱或录入的日期及时间                                                                     |
| 处理日期及时间     | PROCESSING_DATE_TIME  | D    |     |      | 护士处理本医嘱的时间，未处理时，为空                                                         |
| 药品计价属性       | DRUG_BILLING_ATTR     | N    |     | 1    | 反映药品是否计价，0-正常，1-自带药                                                           |
| 计价属性           | BILLING_ATTR          | N    |     | 1    | 反映本条医嘱计价方面的信息。0-正常计价 1-自带药 2-需手工计价 3-不计价。                      |
| 医嘱本打印标志     | ORDER_PRINT_INDICATOR | N    |     | 1    | 表示该医嘱是否已打印医嘱本，0-未打印，1-已打印                                               |
| 相关医嘱号         | RELATED_ORDER_NO      | N    |     | 4    | 本医嘱与护士处理后的医嘱记录单上的医嘱号                                                     |
| 相关医嘱子号       | RELATED_ORDER_SUB_NO  | N    |     | 2    | 本医嘱与护士处理后的医嘱记录单上的医嘱子号                                                   |
| 医生代码           | DOCTOR_USER           | C    |     | 16   |                                                                                              |

注释：此表为医生下达医嘱的记录，面向医嘱本，该表中医嘱处理并执行后，生成医嘱记录单，兼顾药疗医嘱和其他类别的医嘱，其模型支持成组医嘱和父子医嘱。该表医嘱由医生工作站生成。

医嘱在病人出院，且完成相关统计后，将其转移到历史表中。典型地，需保留一年。

以每病人每日新开2条医嘱、1000张床位的医院计，每日新增医嘱2000条，每年新增700,000条。

## 成组医嘱模板主记录GROUP_ORDER_MASTER

|              |                       |      |      |                      |
|--------------|-----------------------|------|------|----------------------|
| 字段中文名称 | 字段名                | 类型 | 长度 | 说明                 |
| 医嘱模板标识 | GROUP_ORDER_ID        | C    | 6    | 唯一标识模板         |
| 模板名称     | TITLE                 | C    | 20   |                      |
| 所属科室     | DEPT_CODE             | C    | 8    | 定义该模板的科室代码 |
| 建立者代码   | CREATOR_ID            | C    | 16   |                      |
| 建立日期     | CREATE_DATE_TIME      | D    |      |                      |
| 最后修改日期 | LAST_MODIFY_DATE_TIME | D    |      |                      |
| 级别         | PERMISSION            | C    | 1    | 0:科室1:个人2:公用   |
| 输入码       | INPUT_CODE            | C    | 8    |                      |

注释：此表用于定义成组医嘱的模板，以便于用户输入成组医嘱。该模板分别由各自科室定义与使用。

主键：医嘱模板标识。

## 成组医嘱模板明细GROUP_ORDER_ITEMS

|                  |                    |      |      |                                           |
|------------------|--------------------|------|------|-------------------------------------------|
| 字段中文名称     | 字段名             | 类型 | 长度 | 说明                                      |
| 医嘱模板标识     | GROUP_ORDER_ID     | C    | 6    |                                           |
| 医嘱序号         | ITEM_NO            | N    | 2    | 该组医嘱中该医嘱的序号                    |
| 子号             | ITEM_SUB_NO        | N    | 1    | 如果医嘱中包含复合医嘱，则为子医嘱序号    |
| 长期医嘱标志     | REPEAT_INDICATOR   | N    | 1    | 该医嘱是否为长期医嘱0-临时医嘱 1-长期医嘱 |
| 医嘱类别         | ORDER_CLASS        | C    | 1    | 同医嘱表中的医嘱类别，见3.6医嘱类别字典   |
| 医嘱内容         | ORDER_TEXT         | C    | 80   | 同医嘱表中的医嘱内容                      |
| 医嘱代码         | ORDER_CODE         | C    | 10   | 同医嘱表中的医嘱代码                      |
| 药品一次使用剂量 | DOSAGE             | N    | 8,4  | 同医嘱表                                  |
| 剂量单位         | DOSAGE_UNITS       | C    | 8    | 同医嘱表                                  |
| 给药途径和方法   | ADMINISTRATION     | C    | 16   | 同医嘱表                                  |
| 执行频率描述     | FREQUENCY          | C    | 16   | 同医嘱表                                  |
| 频率次数         | FREQ_COUNTER       | N    | 2    | 同医嘱表                                  |
| 频率间隔         | FREQ_INTERVAL      | N    | 2    | 同医嘱表                                  |
| 频率间隔单位     | FREQ_INTERVAL_UNIT | C    | 4    | 同医嘱表                                  |
| 医生说明         | FREQ_DETAIL        | C    | 80   | 同医嘱表                                  |
| 计价规则         | DRUG_BILLING_ATTR  | n    | 1    |                                           |

注释：此表为成组医嘱模板主记录的明细记录，包含了医嘱的主要内容。

主键：医嘱模板标识、序号、子号。

## 医生级医嘱模板对应表GROUP_ORDER_SELECTION(新增)

|              |                |      |      |      |
|--------------|----------------|------|------|------|
| 中文名称     | 字段名         | 类型 | 长度 | 说明 |
| 医生代码     | USER_NAME      | C    | 16   |      |
| 医嘱模板标识 | GROUP_ORDER_ID | C    | 6    |      |

## 会诊子表CONSULTATION_DOCTOR_DETAIL(新增)

|              |                     |      |      |      |
|--------------|---------------------|------|------|------|
| 中文名称     | 字段名              | 类型 | 长度 | 说明 |
| 序号         | CONSULTATION_ID     | N    |      |      |
| 会诊ID       | SUB_ID              | N    |      |      |
| 会诊部门     | CONSULTATION_DEPT   | C    | 8    |      |
| 会诊医生     | CONSULTATION_DOCTOR | C    | 8    |      |
| 会诊诊断时间 | AFFIRM_DATE_TIME    | D    |      |      |
| 提交时间     | COMMIT_DATE_TIME    | D    |      |      |
| 会诊意见     | CONSULTATION_IDEA   | C    | 2000 |      |
| 是否指定     | DEPT_ASSIGN         | N    | 1    |      |
| 会诊提交标志 | CONSULTATION_COMMIT | N    | 1    |      |

## 会诊主表CONSULTATION_DOCTOR_MASTER(新增)

|              |                           |      |      |      |
|--------------|---------------------------|------|------|------|
| 中文名称     | 字段名                    | 类型 | 长度 | 说明 |
| 序号         | CONSULTATION_ID           | N    | 22   |      |
| 病人ID       | PATIENT_ID                | C    | 10   |      |
| 住院次数     | VISIT_ID                  | N    | 22   |      |
| 会诊类型     | CONSULTATION_TYPE         | N    | 22   |      |
| 会诊说明     | CONSULTATION_EXPLAIN      | C    | 200  |      |
| 起始时间     | APPLY_DATE_TIME           | D    |      |      |
| 结束时间     | END_DATE_TIME             | D    |      |      |
| 开会诊单时间 | CONSULTATION_DATE_TIME    | D    |      |      |
| 开会诊单医生 | CONSULTATION_APPLY_DOCTOR | C    | 8    |      |

## 治疗申请表CURE_APPOINTS(不使用)

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
|          | APPOINTS_ID   | N    | 22   |      |
|          | PATIENT_ID    | C    | 10   |      |
|          | VISIT_ID      | N    | 2    |      |
|          | CURE_CLASS    | C    | 6    |      |
|          | CURE_DEPT     | C    | 8    |      |
|          | PATIENT_SOURC | C    | 1    |      |
|          | SUMMARY       | C    | 400  |      |
|          | CLINIC        | C    | 400  |      |
|          | REQ_DATE_TIME | D    |      |      |
|          | REQ_DEPT      | C    | 8    |      |
|          | REQ_DOCTOR    | C    | 8    |      |
|          | REQ_MEMO      | C    | 200  |      |
|          | NOT_AFFIRM    | C    | 50   |      |
|          | STATUS        | N    | 1    |      |

## 治疗方案记录CURE_PROJECT(不使用)

|          |                  |      |      |      |
|----------|------------------|------|------|------|
| 中文名称 | 字段名           | 类型 | 长度 | 说明 |
|          | CURE_ID          | N    | 22   |      |
|          | CURE_CYC         | N    | 2    |      |
|          | CURE_DATE_NUMBER | N    | 2    |      |
|          | CURE_START_DATE  | D    |      |      |
|          | CURE_END_DATE    | D    |      |      |
|          | CURE_WAY         | C    | 200  |      |
|          | DOCTOR_ID        | C    | 8    |      |
|          | DOCTOR_DATE_TIME | D    |      |      |

## 治疗报告单CURE_REPORT(不使用)

|          |                 |      |      |      |
|----------|-----------------|------|------|------|
| 中文名称 | 字段名          | 类型 | 长度 | 说明 |
|          | CURE_ID         | N    | 22   |      |
|          | REPORT_DATE     | D    |      |      |
|          | DESCRIPTION     | C    | 1000 |      |
|          | CURE_IMPRESSION | C    | 200  |      |
|          | CURE_RESULT     | C    | 1000 |      |
|          | ADVICE          | C    | 1000 |      |
|          | MEMO            | C    | 100  |      |
|          | DOCTOR_ID       | C    | 8    |      |

## 特殊治疗明细SPECIALTIES_CURE_DETAIL(不使用)

|          |                  |      |      |      |
|----------|------------------|------|------|------|
| 中文名称 | 字段名           | 类型 | 长度 | 说明 |
|          | TREAT_ID         | N    | 22   |      |
|          | CURE_ID          | N    | 22   |      |
|          | CURE_START_DATE  | D    |      |      |
|          | CURE_END_DATE    | D    |      |      |
|          | CURE_APPARATUS   | C    | 20   |      |
|          | CURE_RESULT      | C    | 10   |      |
|          | CURE_DESCRIPTION | C    | 1000 |      |
|          | CURE_IMPRESSION  | C    | 200  |      |
|          | CURE_MEMO        | C    | 100  |      |
|          | DOCTOR_ID        | C    | 8    |      |
|          | NURSE_ID         | C    | 8    |      |

## 特殊治疗主记录SPECIALTIES_CURE_MASTER(不使用)

|          |                  |      |      |      |
|----------|------------------|------|------|------|
| 中文名称 | 字段名           | 类型 | 长度 | 说明 |
|          | CURE_ID          | N    | 22   |      |
|          | PATIENT_ID       | C    | 10   |      |
|          | VISIT_ID         | N    | 2    |      |
|          | STATUS           | N    | 1    |      |
|          | DEPT_CODE        | C    | 8    |      |
|          | CURE_DATE_TIME   | D    |      |      |
|          | START_DATE_TIME  | D    |      |      |
|          | COMMIT_DATE_TIME | D    |      |      |
|          | CURE_DOCTOR      | C    | 8    |      |
|          | CURE_CLASS       | C    | 8    |      |

#  检查

## 检查病人主索引 EXAM_PAT_MI

|              |                  |      |      |                                                                                                       |
|--------------|------------------|------|------|-------------------------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明                                                                                                  |
| 检查号类别   | LOCAL_ID_CLASS   | C    | 1    | 每种检查，允许使用各自本地的标识号，如：超声号、X光号，本字段用于区分不同类型的本地标识号，由用户定义 |
| 检查标识号   | PATIENT_LOCAL_ID | C    | 10   | 如：超声号、X光号，与检查标识号类别一起构成检查主索引的唯一标识                                       |
| 病人标识号   | PATIENT_ID       | C    | 10   | 不要求申请的病人必须具备主索引，但对具有主索引的病人使用此项，以便与其他系统的医疗数据关联            |
| 姓名         | NAME             | C    | 20   | 病人姓名，非空                                                                                        |
| 姓名拼音     | NAME_PHONETIC    | C    | 16   | 病人姓名拼音，大写，字间用一个空格分隔，超长截断                                                      |
| 性别         | SEX              | C    | 4    | 病人性别，男、女、未知等，1.1性别字典                                                                 |
| 出生日期     | DATE_OF_BIRTH    | D    |      | 病人出生日期                                                                                          |
| 出生地       | BIRTH_PLACE      | C    | 6    | 使用代码，见2.2行政区字典                                                                             |
| 身份         | IDENTITY         | C    | 10   | 使用规范名称，如：师以上、团以下、战士、免费职工、家属、地方其他等，见1.6身份字典                     |
| 费别         | CHARGE_TYPE      | C    | 8    | 使用规范名称，如：免费、包干、军半费、军全费、公费、自费、其他等，见1.9费别字典                       |
| 通信地址     | MAILING_ADDRESS  | C    | 40   |                                                                                                       |
| 邮政编码     | ZIP_CODE         | C    | 6    | 数字型字符                                                                                            |
| 联系电话     | PHONE_NUMBER     | C    | 16   |                                                                                                       |

注释：此表用于反映病人各种检查本地标识信息。本表的信息与病人主索引有一定的重复，但通过本表的设置，使得检查系统与其他系统相对独立，可以不依赖于病人主索引信息，这有利于满足辅诊科室社会化服务的模型。从电子病历角度来看，通过本表，可以查得一个病人各种相关标识号。如果病人具备主索引信息，在提取病人检查信息时，可以不通过本表，直接与检查记录关联。

不要求所有的检查都使用本表，特别是不建立病人本地档案的系统，可以不使用本表，而直接使用病人主索引（确保所有的病人有主索引）。

在病人建立各种检查档案时（预约时仅建立预约记录，不分配标识号，故不创建该记录），由特检分系统建立该记录。

## 检查预约记录EXAM_APPOINTS

|                  |                   |      |      |                                                                                                                                                  |
|------------------|-------------------|------|------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称     | 字段名            | 类型 | 长度 | 说明                                                                                                                                             |
| 申请序号         | EXAM_NO           | C    | 10   | 每个检查申请在整个系统范围内，用该序号唯一标识，序号可采用集中分配方式，序号的组成可由申请日期加上一个顺序号或使用累计序号                       |
| 病人标识号       | PATIENT_ID        | C    | 10   | 不要求申请的病人必须具备主索引，但对具有主索引的病人使用此项                                                                                     |
| 住院标识         | VISIT_ID          | N    | 2    | 对在院病人适用                                                                                                                                   |
| 检查号类别       | LOCAL_ID_CLASS    | C    | 1    | 每种检查，允许使用各自本地的标识号，如：超声号、X光号，本字段用于区分不同类型的本地标识号，由用户定义                                            |
| 检查标识号       | PATIENT_LOCAL_ID  | C    | 10   | 如：超声号、X光号，与检查标识号类别一起构成检查主索引的唯一标识                                                                                  |
| 姓名             | NAME              | C    | 20   | 病人姓名，非空                                                                                                                                   |
| 姓名拼音         | NAME_PHONETIC     | C    | 16   | 病人姓名拼音，大写，字间用一个空格分隔，超长截断                                                                                                 |
| 性别             | SEX               | C    | 4    | 病人性别，男、女、未知等，见1.1性别字典                                                                                                          |
| 出生日期         | DATE_OF_BIRTH     | D    |      | 病人出生日期                                                                                                                                     |
| 出生地           | BIRTH_PLACE       | C    | 6    | 或称为籍贯，使用代码，本系统定义，见2.2行政区字典                                                                                                |
| 身份             | IDENTITY          | C    | 10   | 使用规范名称，如：师以上、团以下、战士等，用户定义，见1.6身份字典                                                                                |
| 费别             | CHARGE_TYPE       | C    | 8    | 使用规范名称，如：公费、自费、其他等，用户定义，见1.9费别字典                                                                                    |
| 通信地址         | MAILING_ADDRESS   | C    | 40   |                                                                                                                                                  |
| 邮政编码         | ZIP_CODE          | C    | 6    | 数字型字符                                                                                                                                       |
| 联系电话         | PHONE_NUMBER      | C    | 16   |                                                                                                                                                  |
| 检查类别         | EXAM_CLASS        | C    | 6    | 区分各类检查，使用规范名称，用户定义，见3.3检查类别字典                                                                                          |
| 检查子类         | EXAM_SUB_CLASS    | C    | 8    | 区分一种检查类别下的各子类，如超声类下的腹部、心脏、妇产等子类，使用规范名称，用户定义，见3.4检查子类字典                                        |
| 临床症状         | CLIN_SYMP         | C    | 400  | 正文描述                                                                                                                                         |
| 体征             | PHYS_SIGN         | C    | 400  | 正文描述                                                                                                                                         |
| 相关化验结果     | RELEVANT_LAB_TEST | C    | 200  | 正文描述                                                                                                                                         |
| 其他诊断         | RELEVANT_DIAG     | C    | 400  | 依靠其他检查手段得到的有关诊断                                                                                                                   |
| 临床诊断         | CLIN_DIAG         | C    | 80   | 主要临床诊断，正文描述                                                                                                                           |
| 检查方式         | EXAM_MODE         | C    | 1    | 描述检查的场所，本系统定义，A=病房 B=检查科室                                                                                                    |
| 检查分组         | EXAM_GROUP        | C    | 16   | 用于标识预约排队队列。每个队列称为一个检查组。它可能是一台仪器对应多个检查项目构成的排队队列，也可能是多台仪器对应一个检查项目构成的一个排队队列 |
| 执行科室         | PERFORMED_BY      | C    | 8    | 使用代码，用户定义，见2.6科室字典                                                                                                                |
| 病人来源         | PATIENT_SOURCE    | C    | 1    | 门诊、病房、外来，使用代码，见1.10病人来源字典                                                                                                   |
| 外来医疗单位名称 | FACILITY          | C    | 20   | 当病人为外来时，使用此字段表示病人所在医院或医疗机构名称。当病人来自本院时，留空                                                                 |
| 申请日期及时间   | REQ_DATE_TIME     | D    |      | 提出此申请的日期及时间                                                                                                                           |
| 申请科室         | REQ_DEPT          | C    | 8    | 使用代码，用户定义，见2.6科室字典                                                                                                                |
| 申请医生         | REQ_PHYSICIAN     | C    | 8    | 医生姓名                                                                                                                                         |
| 申请备注         | REQ_MEMO          | C    | 60   | 由申请者输入与申请有关的需另外说明的问题                                                                                                         |
| 预约日期及时间   | SCHEDULED_DATE    | D    |      | 此字段由执行科室根据预约安排填写，病理检查该日期为接受                                                                                           |
| 注意事项         | NOTICE            | C    | 400  | 此字段由执行科室填写，填入与申请项目有关的、病人需注意的事项。该项与预约日期及时间一起构成对检查申请的答复。                                     |
| 费用             | COSTS             | N    | 8,2  | 按标准价格计算得到的费用，由执行科室划价后填入                                                                                                   |
| 应收费用         | CHARGES           | N    | 8,2  | 考虑费别因素后，计算得到的费用，由执行科室划价后填入                                                                                             |
| 申请医生用户名   | DOCTOR_USER       | C    | 16   |                                                                                                                                                  |
|                  | WORKED_INDICATOR  | N    | 1    | 该字段在检查预约、报告子系统中未使用。                                                                                                           |
| 计价标记         | BILLING_INDICATOR | N    | 1    | 0-未计价 1-已计价，由收费程序使用                                                                                                                |

注释：此表用于反映病人预约情况，对需要预约的检查使用。由申请者（如病房）或执行科室将病人的预约申请录入，当执行检查时，由特检分系统将该病人的预约记录删除，同时建立病人检查主索引（需要时），生成检查主记录。对于已预约但未执行的检查预约记录，过一段时间后，由系统自动将其删除。

不要求所有的检查必须经过预约，此时，由申请者直接将申请记入检查主记录。

## 检查主记录EXAM_MASTER

|                    |                     |      |      |                                                                                                                                                                         |
|--------------------|---------------------|------|------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称       | 字段名              | 类型 | 长度 | 说明                                                                                                                                                                    |
| 申请序号           | EXAM_NO             | C    | 10   | 每个检查申请的唯一标识，在整个系统范围内唯一。序号可采用集中分配方式，序号的组成可由申请日期加上一个顺序号或使用累计序号                                                |
| 检查号类别         | LOCAL_ID_CLASS      | C    | 1    | 每种检查，允许使用各自本地的标识号，如：超声号、X光号，本字段用于区分不同类型的本地标识号，由用户定义                                                                   |
| 检查标识号         | PATIENT_LOCAL_ID    | C    | 10   | 如：超声号、X光号，与检查标识号类别一起构成检查主索引的唯一标识                                                                                                         |
| 病人标识号         | PATIENT_ID          | C    | 10   | 不要求申请的病人必须具备主索引，但对具有主索引的病人使用此项                                                                                                            |
| 病人本次住院标识   | VISIT_ID            | N    | 2    | 对住院病人使用此项，门诊或外来病人可为空                                                                                                                                |
| 姓名               | NAME                | C    | 20   | 病人姓名，非空                                                                                                                                                          |
| 性别               | SEX                 | C    | 4    | 病人性别，本系统定义，见1.1性别字典                                                                                                                                     |
| 出生日期           | DATE_OF_BIRTH       | D    |      | 病人出生日期                                                                                                                                                            |
| 检查类别           | EXAM_CLASS          | C    | 6    | 区分各类检查，使用规范名称，用户定义，见3.3检查类别字典                                                                                                                 |
| 检查子类           | EXAM_SUB_CLASS      | C    | 8    | 区分一种检查类下的各子类，如超声类下的腹部、心脏、妇产等子类，使用规范名称，用户定义，见3.4检查子类字典                                                                 |
| 标本收到日期及时间 | SPM_RECVED_DATE     | D    |      | 此项由执行科室填入                                                                                                                                                      |
| 临床症状           | CLIN_SYMP           | C    | 400  | 正文描述                                                                                                                                                                |
| 体征               | PHYS_SIGN           | C    | 400  | 正文描述                                                                                                                                                                |
| 相关化验结果       | RELEVANT_LAB_TEST   | C    | 200  | 正文描述                                                                                                                                                                |
| 其他诊断           | RELEVANT_DIAG       | C    | 400  | 依靠其他检查手段得到的有关诊断                                                                                                                                          |
| 临床诊断           | CLIN_DIAG           | C    | 80   | 主要临床诊断，正文描述                                                                                                                                                  |
| 检查方式           | EXAM_MODE           | C    | 1    | 描述检查的场所，本系统定义，使用代码，A=病房 B=检查科室                                                                                                                 |
| 检查分组           | EXAM_GROUP          | C    | 16   | 用于标识预约排队队列。每个队列称为一个检查组。它可能是一台仪器对应多个检查项目构成的排队队列，也可能是多台仪器对应一个检查项目构成的一个排队队列                        |
| 使用仪器           | DEVICE              | C    | 20   | 指检查所使用的仪器名称和型号                                                                                                                                            |
| 执行科室           | PERFORMED_BY        | C    | 8    | 使用代码，用户定义，见2.6科室字典                                                                                                                                       |
| 病人来源           | PATIENT_SOURCE      | C    | 1    | 门诊、病房、外来，使用代码，见1.10病人来源字典                                                                                                                          |
| 外来医疗单位名称   | FACILITY            | C    | 20   | 当病人为外来时，使用此字段表示病人所在医院或医疗机构名称。当病人来自本院时，留空                                                                                        |
| 申请日期及时间     | REQ_DATE_TIME       | D    |      | 提出此申请的日期及时间                                                                                                                                                  |
| 申请科室           | REQ_DEPT            | C    | 8    | 使用代码，用户定义，见2.6科室字典                                                                                                                                       |
| 申请医生           | REQ_PHYSICIAN       | C    | 8    | 医生姓名                                                                                                                                                                |
| 申请备注           | REQ_MEMO            | C    | 60   | 由申请者输入与申请有关的需另外说明的问题                                                                                                                                |
| 预约日期及时间     | SCHEDULED_DATE_TIME | D    |      | 此字段由执行科室根据预约安排填写                                                                                                                                        |
| 注意事项           | NOTICE              | C    | 400  | 此字段由执行科室填写，填入与申请项目有关需注意的事项。该项与预约日期及时间一起构成对检查申请的答复。                                                                    |
| 检查日期及时间     | EXAM_DATE_TIME      | D    |      | 实际执行检查的日期及时间                                                                                                                                                |
| 报告日期及时间     | REPORT_DATE_TIME    | D    |      | 医生确认报告的日期及时间                                                                                                                                                |
| 操作者             | TECHNICIAN          | C    | 8    | 操作的技术人员姓名                                                                                                                                                      |
| 报告者             | REPORTER            | C    | 8    | 确认报告的医生姓名                                                                                                                                                      |
| 检查结果状态       | RESULT_STATUS       | C    | 1    | 反映申请的执行情况，如：收到申请、已执行、初步报告、确认报告等，初始时，由申请方填入，以后根据检查的执行情况，由执行者修改，使用代码，本系统定义，见3.7检查结果状态字典 |
| 费用               | COSTS               | N    | 8,2  | 按标准价格计算得到的本检查的费用，由执行科室划价后填入                                                                                                                  |
| 应收费用           | CHARGES             | N    | 8,2  | 考虑费别因素后，计算得到的本检查的费用，由执行科室划价后填入                                                                                                            |
| 计价标志           | CHARGE_INDICATOR    | N    | 22,0 | 0-未计价 1-已计价，由收费系统或者检查系统在计费后填入                                                                                                                   |
| 病人费用类别       | CHARGE_TYPE         | C    | 8    |                                                                                                                                                                         |
| 身份               | IDENTITY            | C    | 10   |                                                                                                                                                                         |
| 报告状态           | RPTSTATUS           | C    | 50   | Pacs                                                                                                                                                                    |
| 打印状态           | PRINT_STATUS        | C    | 50   | Pacs                                                                                                                                                                    |
| 检查子科室         | EXAM_SUBDEPT        | C    | 10   |                                                                                                                                                                         |
| 确认医师           | CONFIRM_DOCT        | C    | 8    |                                                                                                                                                                         |
| 学习号             | STUDY_UID           | C    | 128  | Pacs                                                                                                                                                                    |

注释：此表记录病人各种检查的发生及执行情况，是电子病历中检查信息的主索引。当执行检查时，将检查预约记录中的信息转入本表中，或者在执行时录入。当检查完成后，将此表中各种执行信息填入。

收费系统可根据本表中结果状态，选择不同的计价时间点，如预约时或报告确认后等。计价后，将计价标志置位。

主键：申请序号。

索引：病人 ID；

检查号类别、检查标识号；

检查日期及时间、检查类别

## 检查项目记录 EXAM_ITEMS

|              |                   |      |      |                                                                                  |
|--------------|-------------------|------|------|----------------------------------------------------------------------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                                                                             |
| 申请序号     | EXAM_NO           | C    | 10   | 在检查申请记录中分配的唯一标识                                                   |
| 项目序号     | EXAM_ITEM_NO      | N    | 2    | 按医生开单的项目顺序，从1排列                                                    |
| 检查项目     | EXAM_ITEM         | C    | 100  | 描述具体的检查项目，超声为具体检查项目，放射类检查称为检查部位，病理称为标本部位 |
| 项目代码     | EXAM_ITEM_CODE    | C    | 20   | 检查项目对应的代码，可为空，由用户定义，见4.7检查项目字典                        |
| 费用         | COSTS             | N    | 8,2  | 按标准价格计算得到的本项目的费用，由执行科室划价后填入                           |
| 计价标记     | BILLING_INDICATOR | N    | 1    | 0-未计价 1-已计价，由收费程序使用                                                |

注释：此表描述检查的具体项目，是检查申请和检查主记录的明细记录。每个检查所包含的项目在申请预约时生成，未进行的申请随着申请的删除，其对应的检查项目也被删除。

主键：申请序号、检查项目。

## 检查报告 EXAM_REPORT

|                |                |      |      |                                                                                                                  |
|----------------|----------------|------|------|------------------------------------------------------------------------------------------------------------------|
| 字段中文名称   | 字段名         | 类型 | 长度 | 说明                                                                                                             |
| 申请序号       | EXAM_NO        | C    | 10   | 在检查申请记录中分配的唯一标识                                                                                   |
| 检查参数       | EXAM_PARA      | C    | 1000 | 检查过程中记录的有关内容                                                                                         |
| 检查所见       | DESCRIPTION    | C    | 2000 |                                                                                                                  |
| 印象           | IMPRESSION     | C    | 2000 |                                                                                                                  |
| 建议           | RECOMMENDATION | C    | 2000 |                                                                                                                  |
| 是否阳性       | IS_ABNORMAL    | C    | 1    | 1-阳性，即检查可能有病变，其他为阴性                                                                             |
| 使用仪器       | DEVICE         | C    | 20   |                                                                                                                  |
| 报告中图象编号 | USE_IMAGE      | C    | 15   | 如果报告涉及到图象，则此处给出图象的引用索引，格式：XXX(报告中的第一幅图对应该检查中第XXX幅图象，依次类推)，YYY… |
| 备注           | MEMO           | C    | 2000 | 可以放各种检查的互相参考内容                                                                                     |

注释：此表描述检查报告内容，由检查执行科室生成。

主键：申请序号。

## 检查图象索引 EXAM_IMAGE_INDEX

|                  |            |      |      |                                                                     |
|------------------|------------|------|------|---------------------------------------------------------------------|
| 字段中文名称     | 字段名     | 类型 | 长度 | 说明                                                                |
| 申请序号         | EXAM_NO    | C    | 10   | 由检查申请记录定义的唯一标识                                        |
| 病人ID           | PATIENT_ID | C    | 10   |                                                                     |
| 检查类型         | EXAM_CLASS | C    | 2    | 区分不同类型的检查，使用代码，按DICOM3 定义，如：CR、CT、MR、NM、US |
| 图象文件类型     | IMAGE_TYPE | C    | 3    | 反映图象文件的存贮格式，系统定义，如：BMP、NMA、AVI、DCM等          |
| 图象所在介质卷号 | VOLUME_ID  | C    | 40   | 本图象所在的介质卷号，在一定程度上可以称为图象所在的路径            |
| 图象文件名称     | FILE_NAME  | C    | 256  | 图象文件名，不含路径。                                              |

注释：此表用于描述包含有图象内容的检查报告中图象部分的所在地。每次检查，可以对应多幅图象。

## 检查随访记录 EXAM_INQUIRY

|                    |                   |      |      |                                                                                                                  |
|--------------------|-------------------|------|------|------------------------------------------------------------------------------------------------------------------|
| 字段中文名称       | 字段名            | 类型 | 长度 | 说明                                                                                                             |
| 申请序号           | EXAM_NO           | C    | 10   | 在检查申请记录中分配的唯一标识，在此代表待随访的检查信息                                                         |
| 手术日期           | OPER_DATE         | D    |      |                                                                                                                  |
| 手术诊断           | OPER_DIAGNOSIS    | C    | 60   | 待随访的检查所对应的手术诊断                                                                                     |
| 手术诊断医生       | OPER_DIAG_DOCTOR  | C    | 8    | 上述手术诊断的主刀医生                                                                                           |
| 与手术诊断符合情况 | ACCORD_WITH_OPER  | C    | 1    | 原诊断与对应的手术诊断的符合情况，此结果基本可以反映原检查的正确性，使用代码，见4.30诊断符合情况字典             |
| 病理号             | PATH_NO           | C    | 10   | 与原检查对应的病理诊断的编号，它唯一确定该病理诊断                                                               |
| 病理诊断           | PATH_DIAGNOSIS    | C    | 60   | 待随访的检查所对应的病理诊断                                                                                     |
| 病理诊断医生       | PATH_DIAG_DOCTOR  | C    | 8    | 上述病理诊断的医生                                                                                               |
| 与病理诊断符合情况 | ACCORD_WITH_PATH  | C    | 1    | 原诊断与对应的病理诊断的符合情况，此结果反映原检查的正确性，使用代码，见4.30诊断符合情况字典                     |
| 最后诊断           | FINAL_DIAGNOSIS   | C    | 60   | 通过待随访的检查原诊断、对应的手术诊断及对应的病理诊断给出的诊断，该诊断与原诊断进行比较，则能确定原诊断的正确性 |
| 与最后诊断符合情况 | ACCORD_WITH_FINAL | C    | 1    | 原诊断与最后诊断的符合情况，使用代码，见4.30诊断符合情况字典                                                     |
| 随访日期及时间     | INQU_DATE_TIME    | D    |      | 进行随访的日期及时间                                                                                             |
| 随访医生           | INQU_DOCTOR       | C    | 8    | 进行随访的医生，一般为原检查医生                                                                                 |
| 备注               | MEMO              | C    | 40   | 随访需特别说明的问题                                                                                             |

注释：此表反映检查诊断与手术、病理诊断的符合情况，由检查科室用于局部科研目的。其数据由检查科室录入。

## 检查工作时间安排 EXAM_WORKING_PLAN

|              |                 |      |      |                                                                                                                                                  |
|--------------|-----------------|------|------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                                                                                                             |
| 检查类别     | EXAM_CLASS      | C    | 6    | 区分化验、各类检查等，使用代码，非空，取值：超声,CT,MRI,放射,病理,心电图，本系统定义，见3.3检查类别字典                                          |
| 检查分组     | EXAM_GROUP      | C    | 16   | 用于标识预约排队队列。每个队列称为一个检查组。它可能是一台仪器对应多个检查项目构成的排队队列，也可能是多台仪器对应一个检查项目构成的一个排队队列 |
| 星期         | DAY_OF_THE_WEEK | C    | 1    | 非空，0、1…6分别代表星期日、一…六，见4.33星期字典                                                                                                |
| 上午起始时间 | MORN_BEGIN      | C    | 5    | 取值：00:00-23:59                                                                                                                                |
| 上午结束时间 | MORN_END        | C    | 5    | 取值：00:00-23:59,\>MORN_BEGIN                                                                                                                   |
| 下午起始时间 | NOON_BEGIN      | C    | 5    | 取值：00:00-23:59                                                                                                                                |
| 下午结束时间 | NOON_END        | C    | 5    | 取值：00:00-23:59,\>NOON_BEG                                                                                                                     |

注释：此表用于描述需预约的各检查科室的工作时间。时间表以周为单位。该时间表用于病人预约。

## 检查时间间隔 EXAM_INTERVAL

|              |            |      |      |                                                                                                                                                  |
|--------------|------------|------|------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                                                                                                                                             |
| 检查类别     | EXAM_CLASS | C    | 6    | 区分化验、各类检查等，使用代码，非空，取值：超声,CT,MRI,放射,病理,心电图等，本系统定义，见3.3检查类别字典                                        |
| 检查分组     | EXAM_GROUP | C    | 16   | 用于标识预约排队队列。每个队列称为一个检查组。它可能是一台仪器对应多个检查项目构成的排队队列，也可能是多台仪器对应一个检查项目构成的一个排队队列 |
| 每人间隔     | INTERVAL   | N    | 3    | 执行一次检查所需要的日期及时间，或称二人检查之间的日期及时间间隔，单位：分钟                                                                     |
| 人数         | NUM_OF_PAT | N    | 2    | 该日期及时间间隔内可以预约的人数                                                                                                                 |

注释：该表反映各种检查所需的时间，为预约病人提供方便。

## 检查病人时间安排 EXAM_SCHEDULE

|                |                     |      |      |                                                                                                                                                  |
|----------------|---------------------|------|------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称   | 字段名              | 类型 | 长度 | 说明                                                                                                                                             |
| 序号           | SERIAL_NO           | C    | 5    | 唯一标识一次预约，在各类检查范围内唯一                                                                                                           |
| 检查类别       | EXAM_CLASS          | C    | 6    | 非空，取值：超声、CT、MRI、放射、病理、心电图等，见3.3检查类别字典                                                                               |
| 检查分组       | EXAM_GROUP          | C    | 16   | 用于标识预约排队队列。每个队列称为一个检查组。它可能是一台仪器对应多个检查项目构成的排队队列，也可能是多台仪器对应一个检查项目构成的一个排队队列 |
| 预约日期及时间 | SCHEDULED_DATE_TIME | D    |      | 非空                                                                                                                                             |
| 申请序号       | EXAM_NO             | C    | 10   | 已预约病人的申请序号，通过该号，与病人的申请信息关联起来                                                                                         |
| 预约状态       | STATUS              | C    | 1    | 0-空闲 1-占用，其他-不预约或机器故障等                                                                                                           |

注释：该表动态反映各种检查时间段内病人分布情况。

## 检查分组字典 EXAM_GROUP_DICT

|              |            |      |      |                                                                          |
|--------------|------------|------|------|--------------------------------------------------------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                                                                     |
| 序号         | SERIAL_NO  | C    | 2    |                                                                          |
| 检查组       | EXAM_GROUP | C    | 16   | 所设立的检查排队队列，可以是一台仪器，也可以是多台仪器构成的一个检查队列 |
| 检查类别     | EXAM_CLASS | C    | 6    | 该组的检查项目对应的分类                                                 |

注释：本表定义整个系统的检查排队队列。检查预约时用于指定排队队列。

## 检查计价项目 EXAM_BILL_ITEMS

|                  |                    |      |      |                                                                                                                                     |
|------------------|--------------------|------|------|-------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称     | 字段名             | 类型 | 长度 | 说明                                                                                                                                |
| 申请序号         | EXAM_NO            | C    | 10   | 在检查申请记录中分配的唯一标识                                                                                                      |
| 项目序号         | EXAM_ITEM_NO       | N    | 2    | 与检查项目记录中的项目序号对应                                                                                                      |
| 计价项目序号     | CHARGE_ITEM_NO     | N    | 2    | 对应申请项目的计价项目序号，从1开始排列                                                                                             |
| 病人标识号       | PATIENT_ID         | C    | 10   | 对于简易病历为空                                                                                                                    |
| 病人本次住院标识 | VISIT_ID           | N    | 2    | 对门诊病人为空                                                                                                                      |
| 项目类别         | ITEM_CLASS         | C    | 1    | 按价表项目分类，使用代码，见6.8价表项目分类字典。非空                                                                               |
| 项目名称         | ITEM_NAME          | C    | 100  | 项目的正文描述                                                                                                                      |
| 项目代码         | ITEM_CODE          | C    | 20   | 对应于价表中的项目代码，当不能对应到具体的项目时，代码为’\*’                                                                        |
| 项目规格         | ITEM_SPEC          | C    | 50   | 指药品的规格或材料的规格。                                                                                                          |
| 数量             | AMOUNT             | N    | 6,2  |                                                                                                                                     |
| 单位             | UNITS              | C    | 8    | 如片、瓶、人次等，本系统定义，见计价单位字典                                                                                        |
| 开单科室         | ORDERED_BY         | C    | 8    | 手术申请科室代码，见2.6科室字典，指独立统计科室，非空                                                                               |
| 执行科室         | PERFORMED_BY       | C    | 8    | 手术室代码，见2.6科室字典，非空                                                                                                     |
| 费用             | COSTS              | N    | 8,2  | 按价表中标准价格计算得到的费用。非空                                                                                                |
| 应收费用         | CHARGES            | N    | 8,2  | 考虑病人费别或特殊优惠后病人应交的费用。对公费病人，为0。对特殊的不按费别收费的项目，为应收费用。此项手术分系统置空，由收费系统填入 |
| 计价日期及时间   | BILLING_DATE_TIME  | D    |      | 生成本计价项目的日期，非空                                                                                                          |
| 计价员号         | OPERATOR_NO        | C    | 4    | 为录入者的用户号。当为后台划价程序生成时，为一特殊的用户号                                                                          |
| 划价确认标志     | VERIFIED_INDICATOR | N    | 1    | 划价数据确认后，即对外生效，不可修改。0-未确认 1-已确认                                                                             |

说明：此表为检查划价的工作表。对住院人病划价确认后，该病人的检查费用数据转入住院病人费用明细表中。

## BACKUP_PATIENT

|          |        |      |      |      |
|----------|--------|------|------|------|
| 中文名称 | 字段名 | 类型 | 长度 | 说明 |
|          | PID    | C    | 40   |      |
|          | NC     | C    | 40   |      |
|          | SX     | C    | 4    |      |
|          | BR     | D    |      |      |

- Pacs 使用

## BACKUP_STUDY

|          |             |      |      |      |
|----------|-------------|------|------|------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明 |
|          | SUID        | C    | 80   |      |
|          | PID         | C    | 40   |      |
|          | SID         | C    | 65   |      |
|          | SDATE       | D    |      |      |
|          | MODALITY    | C    | 12   |      |
|          | BKID        | C    | 24   |      |
|          | SERSUM      | N    | 22   |      |
|          | IMGSUM      | N    | 22   |      |
|          | TOTLESIZE   | N    | 22   |      |
|          | BACKUP_TIME | D    | 7    |      |

- Pacs 使用

## EMP_DICT

|          |           |      |      |      |
|----------|-----------|------|------|------|
| 中文名称 | 字段名    | 类型 | 长度 | 说明 |
|          | EMP_ID    | C    | 6    |      |
|          | EMP_NAME  | C    | 8    |      |
|          | EMP_DEPT  | C    | 30   |      |
|          | USER_PRIV | C    | 20   |      |

- Pacs 使用

## EXAM_SUBDEPT_DICT

|          |            |      |      |      |
|----------|------------|------|------|------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明 |
|          | SUBDEPT    | C    | 10   |      |
|          | INPUT_CODE | C    | 6    |      |

- Pacs 使用

## MODALITY_VS_LOCAL_ID_CLASS

|          |                     |      |      |      |
|----------|---------------------|------|------|------|
| 中文名称 | 字段名              | 类型 | 长度 | 说明 |
|          | MODALITY            | C    | 10   |      |
|          | LOCAL_ID_CLASS_CODE | C    | 10   |      |

- Pacs 使用

## PACSPATIENT

|          |         |      |      |      |
|----------|---------|------|------|------|
| 中文名称 | 字段名  | 类型 | 长度 | 说明 |
|          | PID     | C    | 40   |      |
|          | NC      | C    | 40   |      |
|          | SX      | C    | 6    |      |
|          | BR      | D    |      |      |
|          | PATDESC | C    | 255  |      |

- Pacs 使用

## PACSSTUDY

|          |             |      |      |      |
|----------|-------------|------|------|------|
| 中文名称 | 字段名      | 类型 | 长度 | 说明 |
|          | SUID        | C    | 128  |      |
|          | HOSTCODE    | C    | 8    |      |
|          | PID         | C    | 40   |      |
|          | SID         | C    | 24   |      |
|          | AID         | C    | 24   |      |
|          | SDATE       | D    |      |      |
|          | MODALITY    | C    | 12   |      |
|          | BODYPART    | C    | 32   |      |
|          | SERSUM      | C    | 8    |      |
|          | IMGSUM      | C    | 8    |      |
|          | TOTLESIZE   | C    | 20   |      |
|          | STATUSFLAGS | C    | 8    |      |
|          | DISKID      | C    | 32   |      |
|          | DDATE       | D    |      |      |
|          | STUDYDESC   | C    | 255  |      |
|          | BKID        | C    | 128  |      |

- Pacs 使用

## PACSUPDATE

|          |        |      |      |      |
|----------|--------|------|------|------|
| 中文名称 | 字段名 | 类型 | 长度 | 说明 |
|          | SUID   | C    | 80   |      |

- Pacs 使用

## PBCATCOL

|          |          |      |      |      |
|----------|----------|------|------|------|
| 中文名称 | 字段名   | 类型 | 长度 | 说明 |
|          | PBC_TNAM | C    | 30   |      |
|          | PBC_TID  | N    | 22,0 |      |
|          | PBC_OWNR | C    | 30   |      |
|          | PBC_CNAM | C    | 30   |      |
|          | PBC_CID  | N    | 22,0 |      |
|          | PBC_LABL | C    | 254  |      |
|          | PBC_LPOS | N    | 22,0 |      |
|          | PBC_HDR  | C    | 254  |      |
|          | PBC_HPOS | N    | 22,0 |      |
|          | PBC_JTFY | N    | 22,0 |      |
|          | PBC_MASK | C    | 31   |      |
|          | PBC_CASE | N    | 22,0 |      |
|          | PBC_HGHT | N    | 22,0 |      |
|          | PBC_WDTH | N    | 22,0 |      |
|          | PBC_PTRN | C    | 31   |      |
|          | PBC_BMAP | C    | 1    |      |
|          | PBC_INIT | C    | 254  |      |
|          | PBC_CMNT | C    | 254  |      |
|          | PBC_EDIT | C    | 31   |      |
|          | PBC_TAG  | C    | 254  |      |

## PBCATEDT

|          |          |      |      |      |
|----------|----------|------|------|------|
| 中文名称 | 字段名   | 类型 | 长度 | 说明 |
|          | PBE_NAME | C    | 30   |      |
|          | PBE_EDIT | C    | 254  |      |
|          | PBE_TYPE | N    | 22,0 |      |
|          | PBE_CNTR | N    | 22,0 |      |
|          | PBE_SEQN | N    | 22,0 |      |
|          | PBE_FLAG | N    | 22,0 |      |
|          | PBE_WORK | C    | 32   |      |

## PBCATFMT

|          |          |      |      |      |
|----------|----------|------|------|------|
| 中文名称 | 字段名   | 类型 | 长度 | 说明 |
|          | PBF_NAME | C    | 30   |      |
|          | PBF_FRMT | C    | 254  |      |
|          | PBF_TYPE | N    | 22,0 |      |
|          | PBF_CNTR | N    | 22,0 |      |

## PBCATTBL

|          |          |      |      |      |
|----------|----------|------|------|------|
| 中文名称 | 字段名   | 类型 | 长度 | 说明 |
|          | PBT_TNAM | C    | 30   |      |
|          | PBT_TID  | N    | 22,0 |      |
|          | PBT_OWNR | C    | 30   |      |
|          | PBD_FHGT | N    | 22,0 |      |
|          | PBD_FWGT | N    | 22,0 |      |
|          | PBD_FITL | C    | 1    |      |
|          | PBD_FUNL | C    | 1    |      |
|          | PBD_FCHR | N    | 22,0 |      |
|          | PBD_FPTC | N    | 22,0 |      |
|          | PBD_FFCE | C    | 18   |      |
|          | PBH_FHGT | N    | 22,0 |      |
|          | PBH_FWGT | N    | 22,0 |      |
|          | PBH_FITL | C    | 1    |      |
|          | PBH_FUNL | C    | 1    |      |
|          | PBH_FCHR | N    | 22,0 |      |
|          | PBH_FPTC | N    | 22,0 |      |
|          | PBH_FFCE | C    | 18   |      |
|          | PBL_FHGT | N    | 22,0 |      |
|          | PBL_FWGT | N    | 22,0 |      |
|          | PBL_FITL | C    | 1    |      |
|          | PBL_FUNL | C    | 1    |      |
|          | PBL_FCHR | N    | 22,0 |      |
|          | PBL_FPTC | N    | 22,0 |      |
|          | PBL_FFCE | C    | 18   |      |
|          | PBT_CMNT | C    | 254  |      |

## PBCATVLD

|          |          |      |      |      |
|----------|----------|------|------|------|
| 中文名称 | 字段名   | 类型 | 长度 | 说明 |
|          | PBV_NAME | C    | 30   |      |
|          | PBV_VALD | C    | 254  |      |
|          | PBV_TYPE | N    | 22,0 |      |
|          | PBV_CNTR | N    | 22,0 |      |
|          | PBV_MSG  | C    | 254  |      |

## STOREUID

|          |           |      |      |      |
|----------|-----------|------|------|------|
| 中文名称 | 字段名    | 类型 | 长度 | 说明 |
|          | STUDY_UID | C    | 80   |      |
|          | STUDYDATE | D    |      |      |

- Pacs 使用

## SUBSERVER_VS_DEPT

|          |                    |      |      |      |
|----------|--------------------|------|------|------|
| 中文名称 | 字段名             | 类型 | 长度 | 说明 |
|          | DEPT_CODE          | C    | 10   |      |
|          | SECOND_SERVER_NAME | C    | 20   |      |

- Pacs 使用

## TSMARCHIVE

|          |              |      |      |      |
|----------|--------------|------|------|------|
| 中文名称 | 字段名       | 类型 | 长度 | 说明 |
|          | HL_NAME      | C    | 255  |      |
|          | LL_NAME      | C    | 255  |      |
|          | OBJECT_ID    | C    | 20   |      |
|          | ARCHIVE_DATE | D    |      |      |

## EXAM_USER

|          |            |      |      |      |
|----------|------------|------|------|------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明 |
|          | USER_ID    | C    | 10   |      |
|          | USER_NAME  | C    | 20   |      |
|          | USER_PWD   | C    | 10   |      |
|          | USER_DEPT  | C    | 10   |      |
|          | USER_GROUP | C    | 10   |      |
|          | USER_MODA  | C    | 10   |      |
|          | USER_Priv  | N    | 8    |      |

- Pacs 使用

#  检验

## 检验主记录 LAB_TEST_MASTER 

|                    |                         |      |      |                                                                                                                                                                         |
|--------------------|-------------------------|------|------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称       | 字段名                  | 类型 | 长度 | 说明                                                                                                                                                                    |
| 申请序号           | TEST_NO                 | C    | 10   | 每个检验申请在整个系统范围内唯一标识                                                                                                                                    |
| 优先标志           | PRIORITY_INDICATOR      | N    | 1    | 反映此申请的紧急程度。0-普通 1-紧急                                                                                                                                     |
| 病人标识号         | PATIENT_ID              | C    | 10   | 对无主索引的病人可为空                                                                                                                                                  |
| 本次住院标识       | VISIT_ID                | N    | 2    | 对门诊病人为空                                                                                                                                                          |
| 工作单号           | WORKING_ID              | C    | 6    | 检验科室为内部管理而给每个申请分配的标识号，在整个系统范围及同一科室不同日期的申请间并不唯一                                                                            |
| 执行日期           | EXECUTE_DATE            | D    |      | 准备执行日期                                                                                                                                                            |
| 姓名               | NAME                    | C    | 20   | 病人姓名，考虑到门诊病人或外医疗单位来的病人可能没有主索引                                                                                                              |
| 姓名拼音           | NAME_PHONETIC           | C    | 16   | 大写，字间用一空格间隔，超长截断                                                                                                                                        |
| 费别               | CHARGE_TYPE             | C    | 8    | 使用规范名称，由用户定义，见1.9费别字典                                                                                                                                 |
| 性别               | SEX                     | C    | 4    | 使用规范名称，本系统定义，见1.14性别字典                                                                                                                                |
| 年龄               | AGE                     | N    | 3    |                                                                                                                                                                         |
| 检验目的           | TEST_CAUSE              | C    | 8    | 正文描述，如查体等                                                                                                                                                      |
| 临床诊断           | RELEVANT_CLINIC_DIAG    | C    | 80   | 诊断正文                                                                                                                                                                |
| 标本               | SPECIMEN                | C    | 8    | 使用标准描述，如血、尿等                                                                                                                                                |
| 标本说明           | NOTES_FOR_SPCM          | C    | 16   | 标本采集的条件说明，如饭前、饭后一小时等。自由格式，由医生开检验单时说明                                                                                                |
| 标本采样日期及时间 | SPCM_RECEIVED_DATE_TIME | D    |      | 由开单科室或执行科室填入                                                                                                                                                |
| 标本收到日期及时间 | SPCM_SAMPLE_DATE_TIME   | D    |      | 由执行科室填入                                                                                                                                                          |
| 申请日期及时间     | REQUESTED_DATE_TIME     | D    |      | 医生开检验单的时间                                                                                                                                                      |
| 申请科室           | ORDERING_DEPT           | C    | 8    | 科室代码，用户定义，如果为病房发出的申请，则为病房代码（非临床科室代码）                                                                                                |
| 申请医生           | ORDERING_PROVIDER       | C    | 8    | 医生姓名                                                                                                                                                                |
| 执行科室           | PERFORMED_BY            | C    | 8    | 检验科室代码                                                                                                                                                            |
| 结果状态           | RESULT_STATUS           | C    | 1    | 反映申请的执行情况，如：收到标本、已执行、初步报告、确认报告等，初始时，由申请方填入，以后根据检查的执行情况，由执行者修改，使用代码，本系统定义，见3.7检查结果状态字典 |
| 报告日期及时间     | RESULTS_RPT_DATE_TIME   | D    |      | 出结果报告的日期及时间                                                                                                                                                  |
| 报告者             | TRANSCRIPTIONIST        | C    | 8    | 报告签发者或检验操作者                                                                                                                                                  |
| 校对者             | VERIFIED_BY             | C    | 8    | 结果校对者                                                                                                                                                              |
| 费用               | COSTS                   | N    | 8,2  | 本检验单按价表中标准价格计算得到的总费用，由执行科室或后台划价程序填入                                                                                                  |
| 应收费用           | CHARGES                 | N    | 8,2  | 考虑费别因素后，计算得到的本检验单的总费用，由执行科室或后台划价程序填入                                                                                                |
| 计价标志           | BILLING_INDICATOR       | N    | 1    | 0-未计价 1-已计价，由收费程序使用                                                                                                                                       |
| 打印标志           | PRINT_INDICATOR         | N    | 1    | 0-未打印 1-已打印，由检验科室打印检验报告时使用                                                                                                                         |
|                    | SUBJECT                 | C    | 40   |                                                                                                                                                                         |
| 送检容器条码       | CONTAINER_CARRIER       | v    | 20   | 送检的标本的试管条码                                                                                                                                                    |

注释：此表描述每张检验申请单。一个检验申请与一个标本必须一一对应。此表记录由开单程序生成（病房或门诊或检验科室），由检验科室修改。

以1000张床位计，每天全院的检验申请约为2000件。每月的数据增长量约为6万条。

主键：申请序号

## 检验项目 LAB_TEST_ITEMS 

|              |                   |      |      |                                   |
|--------------|-------------------|------|------|-----------------------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                              |
| 申请序号     | TEST_NO           | C    | 10   | 对应检验申请主记录中的申请序号    |
| 项目序号     | ITEM_NO           | N    | 2    | 按医生开单的项目顺序，从1排列     |
| 项目名称     | ITEM_NAME         | C    | 100  | 检验项目名称                      |
| 项目代码     | ITEM_CODE         | C    | 20   | 检验项目代码，见4.8检验项目字典   |
| 计价标志     | BILLING_INDICATOR | n    | 1    | 0-未计价 1-已计价，由收费程序使用 |

注释：此表反映检验申请单的检验项目，是检验申请的明细记录。

如果平均一个申请包含3个检验项目，则每月的数据增长量为18万条。

主键：申请序号、项目序号

## 检验结果 LAB_RESULT

|                  |                    |      |      |                                                                                                        |
|------------------|--------------------|------|------|--------------------------------------------------------------------------------------------------------|
| 字段中文名称     | 字段名             | 类型 | 长度 | 说明                                                                                                   |
| 申请序号         | TEST_NO            | C    | 10   | 对应检验申请主记录中的申请序号                                                                         |
| 项目序号         | ITEM_NO            | N    | 2    | 对应检验项目中的项目序号                                                                               |
| 打印序号         | PRINT_ORDER        | N    | 4    | 反映该报告项目在打印报告单时排列的次序，与检验报告项目字典序号保持一致，在一个检验申请内部，可能不连续 |
| 检验报告项目名称 | REPORT_ITEM_NAME   | C    | 40   | 此名称可能不同于申请项目名称                                                                           |
| 检验报告项目代码 | REPORT_ITEM_CODE   | C    | 10   | 报告项目对应的代码，见4.36检验报告项目字典                                                             |
| 检验结果值       | RESULT             | C    | 20   | 正文描述，可以是定性描述，也可以是定量数值，对于没有值的项目不使用此字段                               |
| 检验结果单位     | UNITS              | C    | 8    | 对检验结果为数值型的项目使用此字段                                                                     |
| 结果正常标志     | ABNORMAL_INDICATOR | C    | 1    | 结果正常与否标志，N-正常 L-低 H-高                                                                     |
| 仪器编号         | INSTRUMENT_ID      | C    | 8    | 同检验仪器检验项目配置中定义的仪器编号，手工输入结果时为“手工”                                         |
| 检验日期及时间   | RESULT_DATE_TIME   | D    |      | 结果产生的日期和时间。自动采集结果时由采集计算机生成，手工填写结果时由录入处理的计算机生成。           |
|                  | PRINT_CONTEXT      | C    | 80   |                                                                                                        |

注释：此表用于记录检验结果。一个检验申请项目可以对应多个检验结果，如细菌培养可以培养出多种细菌，对复合项目，采用类似处理方法。

以平均每个申请项目1.5个结果计，每月的数据增长量为24万条。

主键：申请序号、项目序号、打印序号

## 检验仪器检验项目配置 INSTRUMENT_CONFIG 

|                  |                      |      |      |                                                                        |
|------------------|----------------------|------|------|------------------------------------------------------------------------|
| 字段中文名称     | 字段名               | 类型 | 长度 | 说明                                                                   |
| 仪器编号         | INSTRUMENT_ID        | C    | 8    | 用于记录产生检验结果的仪器设备序号，设备从1开始排序                    |
| 仪器项目代码     | INSTRUMENT_ITEM_CODE | C    | 8    | 检验仪器中定义的检验项目代码，该代码与检验报告项目字典中定义的代码不同 |
| 检验报告项目代码 | REPORT_ITEM_CODE     | C    | 10   | 检验报告项目字典中定义的代码                                           |
| 检测校正值       | DEVIATION            | N    | 6,2  | 仪器误差校正                                                           |

注释：此表用于反映检验仪器内部设定的项目与外部系统定义的项目之间的对照关系。

主键：仪器编号、仪器项目代码

## 检验联机仪器字典INSTRUMENT_DICT 

|                      |               |      |      |                                                                  |
|----------------------|---------------|------|------|------------------------------------------------------------------|
| 字段中文名称         | 字段名        | 类型 | 长度 | 说明                                                             |
| 仪器代号             | INST_ID       | C    | 8    | 唯一标识一台仪器                                                 |
| 仪器名称             | INST_NAME     | C    | 40   |                                                                  |
| 仪器编号             | INST_NO       | C    | 10   |                                                                  |
| 双工标志             | DUPLEX_FLAG   | N    | 5    |                                                                  |
| 稀释标志             | DILUTE_FLAG   | C    | 1    |                                                                  |
| 自动入库标志         | AUTOIN_FLAG   | C    | 1    |                                                                  |
| 通讯口号             | COMM_PORT     | C    | 6    | 记录通讯口的设备号                                               |
| 波特率               | BAUD_RATE     | N    | 10   |                                                                  |
| 数据位               | BYTE_SIZE     | N    | 5    |                                                                  |
| 校验类型             | PARITY        | N    | 5    | 0-无校验1-奇校验 2-偶校验 3-标记 4-间隔                          |
| 停止位               | STOP_BITS     | N    | 5    | 0-1位1-1.5位                                                     |
| 传送使用XON/XOFF     | F_OUTX        | N    | 5    | 0-不使用 1-使用                                                  |
| 接收使用XON/XOFF     | F_INX         | N    | 5    | 0-不使用 1-使用                                                  |
| 流硬件控制           | F_HARDWARE    | N    | 5    |                                                                  |
| 传送队列大小         | TX_QUEUESIZE  | N    | 10   |                                                                  |
| 接收队列大小         | RX_QUEUESIZE  | N    | 10   |                                                                  |
| XON阀值              | XON_LIM       | N    | 10   |                                                                  |
| XOFF阀值             | XOFF_LIM      | N    | 10   |                                                                  |
| XON字符              | XON_CHAR      | C    | 1    |                                                                  |
| XOFF字符             | XOFF_CHAR     | C    | 1    |                                                                  |
| 错误替代字符         | ERROR_CHAR    | C    | 1    |                                                                  |
| 监控事件字符         | EVENT_CHAR    | C    | 1    |                                                                  |
| 接口程序             | DRIVER_PROG   | C    | 128  |                                                                  |
| 接口程序优先级       | PRIORITY      | N    | 5    |                                                                  |
| 运行状态             | SERV_STATUS   | C    | 1    | 反映当前工作状态，由采集程序修改R-正在运行 S-停止运行 N-停止使用 |
| 仪器分类字母         | ITEM_TYPE     | C    | 1    |                                                                  |
| 仪器制造厂家         | FACTORY       | C    | 40   |                                                                  |
| 仪器说明             | DESCRIPTION   | C    | 40   |                                                                  |
| 联机日期             | CONNECT_DATE  | D    |      |                                                                  |
| 与仪器相联主机名称   | COMPUTER_NAME | C    | 8    |                                                                  |
| 自动装入联机接口程序 | AUTO_LOAD     | N    | 5    |                                                                  |

注释：此表用于描述每个联机仪器所占的通讯口、协议以及所使用的接口程序。

## 检验联机采集数据 ONLINE_DATA （1.0版使用，已过时） 

|              |                |      |      |                                                                                              |
|--------------|----------------|------|------|----------------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明                                                                                         |
| 序号         | SERIAL_NO      | N    | 5    | 唯一标识一个中间结果，由序号发生器生成                                                       |
| 仪器代号     | INST_ID        | C    | 8    | 生成该结果的仪器代号，对应检验联机仪器字典定义的仪器代号                                     |
| 样本号       | SAMPLE_ID      | N    | 5    | 传送结果的样本号                                                                             |
| 项目标识     | ITEM_ID        | C    | 8    | 传送结果的检验项目标识                                                                       |
| 检验结果     | ASSAY_RESULT   | C    | 20   |                                                                                              |
| 检验日期     | ASSAY_DATE     | D    |      |                                                                                              |
| 样本类型     | SAMPLE_TYPE    | N    | 5    | 反映是正常样本或急诊或质控等                                                                 |
| 结果状态     | RESULT_STATUS  | N    | 5    | 0-结果可信 1-结果不可信                                                                      |
| 状态注解     | STATUS_COMMENT | C    | 8    | 存放结果不可信时的错误代码或结果可信时反映结果是否超值字符，如：N—正常、H—超上限、L—超下限等 |

注释：此表为仪器传送结果的中间库。

## 计算公式字典 FORMULAR_DICT 

|                   |                 |      |      |                                  |
|-------------------|-----------------|------|------|----------------------------------|
| 字段中文名称      | 字段名          | 类型 | 长度 | 说明                             |
| 序号              | SERIAL_NO       | N    | 3    | 标识公式顺序                     |
| 结果项目代码      | COMPUTED_CODE   | C    | 10   | 需通过计算得到最终结果的项目代码 |
| 参加计算项目代码1 | COMPUTING_CODE1 | C    | 10   | 参与计算的中间结果项目代码       |
| 参加计算项目代码2 | COMPUTING_CODE2 | C    | 10   | 参与计算的中间结果项目代码       |
| 参加计算项目代码3 | COMPUTING_CODE3 | C    | 10   | 参与计算的中间结果项目代码       |
| 参加计算项目代码4 | COMPUTING_CODE4 | C    | 10   | 参与计算的中间结果项目代码       |
| 参加计算项目代码5 | COMPUTING_CODE5 | C    | 10   | 参与计算的中间结果项目代码       |
| 计算公式          | FORMULAR        | C    | 40   |                                  |

## 标注字典 SYMBOL_DICT 

|              |             |      |      |                                                            |
|--------------|-------------|------|------|------------------------------------------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                                                       |
| 序号         | SERIAL_NO   | N    | 5    | 反映项目的排列顺序                                         |
| 项目代码     | ITEM_CODE   | C    | 10   | 需要根据数值结果标注的项目                                 |
| 文字结果     | SYMBOL      | C    | 40   | 在对应的数值结果区间内标注的文字，存放结果为：阴性、红色等 |
| 上限值       | UPPER_LIMIT | N    | 9,3  | 数值结果的区间上限                                         |
| 下限值       | LOWER_LIMIT | N    | 9,3  | 数值结果的区间下限                                         |

注释：此表建立了数值结果与文字标注之间的对应关系。

## 检验工作量日统计 LAB_DEPT_TEST_DAY （1.0版使用，已过时） 

|              |                    |      |      |      |
|--------------|--------------------|------|------|------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明 |
| 统计数据日期 | ST_DATE            | D    |      |      |
| 检验项目代码 | ITEM_CODE          | C    | 10   |      |
| 检验项目名称 | ITEM_NAME          | C    | 40   |      |
|              | ASSAY_DEPT_CODE    | C    | 8    |      |
|              | ORDERING_DEPT_CODE | C    | 8    |      |
|              | COMPLETED_NUM      | N    | 4    |      |
|              | OUTP_OR_INP        | N    | 1    |      |

注释：此表为检验工作量日统计表，以开单科室、执行科室和项目为统计单位。

主键：统计数据日期、开单科室、执行科室、检验项目代码。

## 检验工作量月统计 LAB_DEPT_TEST_MONTH （1.0版使用，已过时）

|              |                    |      |      |      |
|--------------|--------------------|------|------|------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明 |
| 统计数据月份 | ST_MONTH           | C    | 6    |      |
| 检验项目代码 | ITEM_CODE          | C    | 10   |      |
| 检验项目名称 | ITEM_NAME          | C    | 40   |      |
|              | ASSAY_DEPT_CODE    | C    | 8    |      |
|              | ORDERING_DEPT_CODE | C    | 8    |      |
|              | COMPLETED_NUM      | N    | 4    |      |
|              | OUTP_OR_INP        | N    | 1    |      |

注释：此表为检验工作量日统计表，以开单科室、执行科室和项目为统计单位。

主键：统计数据月份、开单科室、执行科室、检验项目代码。

## 临时检验结果 LAB_RESULT_TEMP

|                  |                    |      |      |                                                                                                        |
|------------------|--------------------|------|------|--------------------------------------------------------------------------------------------------------|
| 字段中文名称     | 字段名             | 类型 | 长度 | 说明                                                                                                   |
| 工作单号         | WORKING_ID         | C    | 6    | 检验科室为内部管理而给每个申请分配的标识号，在整个系统范围及同一科室不同日期的申请间并不唯一           |
| 项目序号         | ITEM_NO            | N    | 2    | 对应检验项目中的项目序号                                                                               |
| 打印序号         | PRINT_ORDER        | N    | 4    | 反映该报告项目在打印报告单时排列的次序，与检验报告项目字典序号保持一致，在一个检验申请内部，可能不连续 |
| 检验报告项目名称 | REPORT_ITEM_NAME   | C    | 40   | 此名称可能不同于申请项目名称                                                                           |
| 检验报告项目代码 | REPORT_ITEM_CODE   | C    | 10   | 报告项目对应的代码，见4.36检验报告项目字典                                                             |
| 检验结果值       | RESULT             | C    | 20   | 正文描述，可以是定性描述，也可以是定量数值，对于没有值的项目不使用此字段                               |
| 检验结果单位     | UNITS              | C    | 8    | 对检验结果为数值型的项目使用此字段                                                                     |
| 结果正常标志     | ABNORMAL_INDICATOR | C    | 1    | 结果正常与否标志，N-正常 L-低 H-高                                                                     |
| 仪器编号         | INSTRUMENT_ID      | C    | 8    | 同检验仪器检验项目配置中定义的仪器编号                                                                 |
| 检验日期及时间   | RESULT_DATE_TIME   | D    |      | 结果产生的日期和时间。由采集计算机生成。                                                               |

注释：此表用于记录检验申请还未录入，仪器已将结果做出来的样本。软件将结果写入结果这个表中，在检验申请录入时由软件将本表中结果通过检验申请号与检验申请关联。

主键：工作单号，项目序号，检验日期及时间

## 检验结果描述与结果值对照表 LAB_RESULT_TYPE_VS_VALUES

|              |              |      |      |      |
|--------------|--------------|------|------|------|
| 字段中文名称 | 字段名       | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO    | N    | 4    |      |
| 结果类型     | RESULT_TYPE  | C    | 8    |      |
| 结果值       | RESULT_VALUE | C    | 20   |      |
| 输入码       | INPUT_CODE   | C    | 8    |      |

## 质控参数 QUALITY_CON_PARAMETER_LIST（1.0版使用，已过时）

|              |            |      |      |      |
|--------------|------------|------|------|------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 质控项目代码 | ITEM_CODE  | C    | 10   |      |
| 年           | QC_YEAR    | N    | 4    |      |
| 月           | QC_MONTH   | N    | 2    |      |
| 仪器代码     | INST       | C    | 6    |      |
| 光径         | METHOD     | C    | 6    |      |
| 方法         | WAVELENGTH | C    | 6    |      |
| 质控均值1    | XB1        | N    | 8,2  |      |
| 质控均值2    | XB2        | N    | 8,2  |      |
| 质控均值3    | XB3        | N    | 8,2  |      |
| 质控CD       | SD1        | N    | 8,2  |      |
| 质控SD       | SD2        | N    | 8,2  |      |
| 质控SD       | SD3        | N    | 8,2  |      |
| 质控CV       | CV1        | N    | 6,2  |      |
| 质控CV       | CV2        | N    | 6,2  |      |
| 质控CV       | CV3        | N    | 6,2  |      |
|              | BATCH_NO1  | C    | 8    |      |
|              | BATCH_NO2  | C    | 8    |      |
|              | BATCH_NO3  | C    | 8    |      |

## 质控数据 QUALITY_CON_LIST（1.0版使用，已过时）

|              |                |      |      |      |
|--------------|----------------|------|------|------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明 |
| 质控项目代码 | ITEM_CODE      | C    | 10   |      |
| 操作者号     | OPERATOR       | C    | 10   |      |
| 质控日期     | QC_DATE        | D    |      |      |
| 质控值       | CONTROL_RESULT | N    | 8,2  |      |
| 质控号       | CONTROL_NO     | N    | 5    |      |

## 审核 EXAM（1.0版使用，已过时）

|              |            |      |      |      |
|--------------|------------|------|------|------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 项目代码1    | ITEM-CODE1 | C    | 10   |      |
| 项目代码2    | ITEM-CODE2 | C    | 10   |      |
| 项目代码3    | ITEM-CODE1 | C    | 10   |      |
| 项目代码4    | ITEM-CODE2 | C    | 10   |      |
| 项目代码5    | ITEM-CODE1 | C    | 10   |      |
| X            | X          | N    | 1    |      |
| Y            | Y          | N    | 1    |      |
| 审核表达式   | CONDITION  | C    | 40   |      |
| 序号         | SERIAL-NO  | N    | 6    |      |
| 审核名称     | DESC-EXAM  | C    | 40   |      |
| 审核分类     | ESAM-CLASS | C    | 20   |      |

## 质控标本记录QC_SPECIMENS

|              |                   |      |      |                                                                          |
|--------------|-------------------|------|------|--------------------------------------------------------------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                                                                     |
| 标本ID号     | QC_SPECIMEN_ID    | C    | 10   | 质控标本的唯一标识，使用标本批号                                         |
| 标本入库时间 | QC_STOCK_DATETIME | D    |      | 质控标本入库时间                                                         |
| 标本类型     | QC_SPECIMEN_TYPE  | C    | 1    | 描述质控标本按检测结果参数高低的分类：N—中值标本，H—高值标本，L—低值标本 |
| 标本说明     | QC_SPECIMEN_NOTES | C    | 20   |                                                                          |

注释：此表记录检验科室所使用的质控标本信息。

主键：标本ID号。

## 质控标本参数QC_SPECIMEN_PARAMETERS

|                        |                |      |      |                                                        |
|------------------------|----------------|------|------|--------------------------------------------------------|
| 字段中文名称           | 字段名         | 类型 | 长度 | 说明                                                   |
| 标本ID号               | QC_SPECIMEN_ID | C    | 10   | 质控标本的唯一标识，使用标本批号                       |
| 参数项目名称           | ITEM_NAME      | C    | 40   | 标本对应的质控检测项目名称                             |
| 参数项目代码           | ITEM_CODE      | C    | 10   | 标本对应的质控检测项目代码，与报告项目字典定义代码一致 |
| 质控标本对应的靶值     | QC_SPECIMEN_XD | C    | 10   | 质控标本标称的靶值                                     |
| 质控标本对应的标准差   | QC_SPECIMEN_SD | C    | 10   | 质控标本标称的标准差                                   |
| 质控标本对应的变异系数 | QC_SPECIMEN_CV | C    | 10   | 质控标本标称的变异系数                                 |

注释：此表记录质控标本标称的相关参数

主键：标本ID号、参数项目代码

## 质控结果QC_SPECIMEN_RESULT

|              |                   |      |      |                                |
|--------------|-------------------|------|------|--------------------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                           |
| 仪器ID       | INSTRUMENT_ID     | C    | 10   | 由仪器定义字典定义             |
| 质控标本ID号 | QC_SPECIMEN_ID    | C    | 10   | 对应质控标本记录定义的标本ID号 |
| 检测时间     | EXECUTE_DATE_TIME | D    |      |                                |
| 检测项目代码 | ITEM_CODE         | C    | 10   | 来源于报告项目字典             |
| 检测序号     | ITEM_NO           | N    | 2    |                                |
| 检测结果     | RESULT            | C    | 20   |                                |
| 结果单位     | UNITS             | C    | 8    |                                |
| 操作员号     | OPERATOR_NO       | C    | 4    |                                |

注释：此表用于存放质控结果

主键：仪器ID、质控标本ID号、检测时间、检测项目代码、检测序号

药品

# 药品管理

## 新药发布NEW_DRUG_MESSAGE(新增)

|          |                  |      |      |      |
|----------|------------------|------|------|------|
| 中文名称 | 字段名           | 类型 | 长度 | 说明 |
| 药品编码 | DRUG_CODE        | C    | 20   |      |
| 药理作用 | ACTION           | C    | 2000 |      |
| 适用症   | INDICATION       | C    | 2000 |      |
| 注意事项 | DOSAGE           | C    | 2000 |      |
| 用法用量 | CONTRAINDICATION | C    | 2000 |      |
| 禁忌     | ATTENTION        | C    | 2000 |      |
| 发布日期 | RELEASE_DATE     | D    |      |      |

主键：drug_code

备注：

## 药品编码停用日志DRUG_STOP_LOG(新增)

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
| 药品编码 | DRUG_CODE     | C    | 20   |      |
| 变更日期 | CHANGE_DATE   | D    |      |      |
| 变更原因 | CHANGE_REASON | C    | 50   |      |
| 变更人   | CHANGE_OPER   | C    | 8    |      |
| 变更标志 | CHANGE_FLAG   | N    | 1    |      |

主键：DRUG_CODE,CHANGE_DATE

## 药品库存定义 DRUG_STORAGE_PROFILE

|              |                    |      |      |                                                  |
|--------------|--------------------|------|------|--------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                             |
| 库房         | STORAGE            | C    | 8    | 库房代码，见库存单位字典                         |
| 药品代码     | DRUG_CODE          | C    | 20   | 由药品字典定义的代码                             |
| 规格         | DRUG_SPEC          | C    | 20   | 由药品字典定义的规格                             |
| 单位         | UNITS              | C    | 8    | 对应剂型及规格，使用规范名称，见4.32计量单位字典 |
| 常规包装数量 | AMOUNT_PER_PACKAGE | N    | 5    | 使用规范名称，常规包装包含的数量                 |
| 常规包装单位 | PACKAGE_UNITS      | C    | 8    | 见4.32计量单位字典                               |
| 高位水平     | UPPER_LEVEL        | N    | 6    | 库存水平限制，以上述包装计，达到该限制时停止采购 |
| 低位水平     | LOW_LEVEL          | N    | 6    | 库存水平限制，以上述包装计，低于该限制时开始采购 |
| 货位         | LOCATION           | C    | 8    |                                                  |
| 存放库房     | SUPPLIER           | C    | 10   |                                                  |
| 存放库房     | SUB_STORAGE        | C    | 8    | 该药品对应的库存管理单位内的存放库房             |

注释：此表定义各药品库房每种药品的库存水平。同一库房同种规格的药品只能有一条记录，不同的库房可以有相同的药品。

主键：药品代码、规格、库房、常规包装数量。

## 药品库存 DRUG_STOCK

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 31%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>库存管理单位</td>
<td>STORAGE</td>
<td>C</td>
<td>8</td>
<td>库房代码，见库存单位字典</td>
</tr>
<tr class="odd">
<td>药品代码</td>
<td>DRUG_CODE</td>
<td>C</td>
<td>20</td>
<td>由药品字典定义的代码</td>
</tr>
<tr class="even">
<td>规格</td>
<td>DRUG_SPEC</td>
<td>C</td>
<td>20</td>
<td>由药品字典定义的规格</td>
</tr>
<tr class="odd">
<td>单位</td>
<td>UNITS</td>
<td>C</td>
<td>8</td>
<td>对应剂型及规格，使用规范名称，见4.32计量单位字典</td>
</tr>
<tr class="even">
<td>批号</td>
<td>BATCH_NO</td>
<td>C</td>
<td>16</td>
<td>使用“XX/XX/XXXXXX”</td>
</tr>
<tr class="odd">
<td>有效期</td>
<td>EXPIRE_DATE</td>
<td>D</td>
<td></td>
<td>药品的有效截止日期</td>
</tr>
<tr class="even">
<td>厂家标识</td>
<td>FIRM_ID</td>
<td>C</td>
<td>10</td>
<td>反映生产厂家，见药品生产厂家字典</td>
</tr>
<tr class="odd">
<td>包装规格</td>
<td>PACKAGE_SPEC</td>
<td>C</td>
<td>20</td>
<td>反映药品含量及包装信息，如0.25g*30</td>
</tr>
<tr class="even">
<td>进货价</td>
<td>PURCHASE_PRICE</td>
<td>N</td>
<td>10,4</td>
<td>购买价，以包装单位记单价</td>
</tr>
<tr class="odd">
<td>折扣</td>
<td>DISCOUNT</td>
<td>N</td>
<td>5,2</td>
<td>该药品购入时的折扣率。百分数，只记录数值部分</td>
</tr>
<tr class="even">
<td>数量</td>
<td>QUANTITY</td>
<td>N</td>
<td>12,2</td>
<td>以包装规格及包装单位所计的现库存数量，每次出库，该数量核减</td>
</tr>
<tr class="odd">
<td>包装单位</td>
<td>PACKAGE_UNITS</td>
<td>C</td>
<td>8</td>
<td>对应包装规格的计量单位，可使用任一级管理上方便的包装</td>
</tr>
<tr class="even">
<td>内含包装1</td>
<td>SUB_PACKAGE_1</td>
<td>N</td>
<td>12,2</td>
<td>上述一个包装单位中包含的小包装数量，为空或1表示为无此级包装</td>
</tr>
<tr class="odd">
<td>内含包装1单位</td>
<td>SUB_PACKAGE_UNITS_1</td>
<td>C</td>
<td>8</td>
<td>对应内含包装1的单位</td>
</tr>
<tr class="even">
<td>内含包装1规格</td>
<td>SUB_PACKAGE_SPEC_1</td>
<td>C</td>
<td>20</td>
<td>对应内含包装1的规格</td>
</tr>
<tr class="odd">
<td>内含包装2</td>
<td>SUB_PACKAGE_2</td>
<td>N</td>
<td>12,2</td>
<td>内含包装1中包含的小包装数量，为空或1表示为无此级包装</td>
</tr>
<tr class="even">
<td>内含包装2单位</td>
<td>SUB_PACKAGE_UNITS_2</td>
<td>C</td>
<td>8</td>
<td>对应内含包装2的单位</td>
</tr>
<tr class="odd">
<td>内含包装2规格</td>
<td>SUB_PACKAGE_SPEC_2</td>
<td>C</td>
<td>20</td>
<td>对应内含包装2的规格</td>
</tr>
<tr class="even">
<td>存放库房</td>
<td>SUB_STORAGE</td>
<td>C</td>
<td>8</td>
<td>一个库存管理单位内的存放库房</td>
</tr>
<tr class="odd">
<td>货位</td>
<td>LOCATION</td>
<td>C</td>
<td>20</td>
<td>描述存放该批药品的位置，自由描述</td>
</tr>
<tr class="even">
<td>入库单号</td>
<td>DOCUMENT_NO</td>
<td>C</td>
<td>10</td>
<td>该药品对应的入库单号，当多次入库的药品合并记录时，该项为空</td>
</tr>
<tr class="odd">
<td>供应标志</td>
<td>SUPPLY_INDICATOR</td>
<td>N</td>
<td>1</td>
<td><p>反映该药品当前是否可供使用，0-不可供 1-可供</p>
<p>（不可供只是对处方和摆药而言，是对病人的，不限制内部流动，直接的出入库操作不受此限制）</p></td>
</tr>
</tbody>
</table>

注释：此表描述了各库存单位药品的库存情况。库存单位可以是药库、门诊药局、临床药局，每类库存单位可以有多个，通过库存管理单位代码反映。药品可以视需要管理到不同的批次，也可以忽略批次而将同一种药品作为一条记录。药品的数量以包装单位计，对多层包装，记录各层包装的换算。库存记录在入库时生成，当库存为0后，可以删除。

主键：库存管理单位，药品代码、规格、批号、厂家标识、包装规格

备注：当库存为0后，可以删除，那么此批号的进价就找不到了，涉及进价的查询和统计就会受到影响；

## 盘点表 drug_inventory_check(新增)

<table style="width:100%;">
<colgroup>
<col style="width: 20%" />
<col style="width: 31%" />
<col style="width: 6%" />
<col style="width: 8%" />
<col style="width: 32%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>库存管理单位</td>
<td>STORAGE</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>盘点年月</td>
<td>CHECK_YEAR_MONTH</td>
<td>DATE</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td>药品代码</td>
<td>DRUG_CODE</td>
<td>C</td>
<td>20</td>
<td></td>
</tr>
<tr class="odd">
<td>厂家标识</td>
<td>FIRM_ID</td>
<td>C</td>
<td>10</td>
<td></td>
</tr>
<tr class="even">
<td>包装规格</td>
<td>DRUG_SPEC</td>
<td>C</td>
<td>20</td>
<td>对应 DRUG_IMPORT_DETAIL .PACKAGE_SPEC</td>
</tr>
<tr class="odd">
<td>批号</td>
<td>BATCH_NO</td>
<td>C</td>
<td>16</td>
<td></td>
</tr>
<tr class="even">
<td>最小单位规格</td>
<td>MIN_SPEC</td>
<td>C</td>
<td>20</td>
<td>对应DRUG_DICT.DRUG_SPEC</td>
</tr>
<tr class="odd">
<td>单位</td>
<td>UNITS</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>最小单位</td>
<td>MIN_UNITS</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>存放库房</td>
<td>SUB_STORAGE</td>
<td>C</td>
<td>10</td>
<td>该药品对应的库存管理单位内的存放库房</td>
</tr>
<tr class="even">
<td>帐面数量</td>
<td>ACCOUNT_QUANTITY</td>
<td>N</td>
<td>12,2</td>
<td></td>
</tr>
<tr class="odd">
<td>实际数量</td>
<td>ACTUAL_QUANTITY</td>
<td>N</td>
<td>12,2</td>
<td></td>
</tr>
<tr class="even">
<td>市场批发价</td>
<td>TRADE_PRICE</td>
<td>N</td>
<td>10,4</td>
<td></td>
</tr>
<tr class="odd">
<td>市场零售价</td>
<td>RETAIL_PRICE</td>
<td>N</td>
<td>10,4</td>
<td></td>
</tr>
<tr class="even">
<td></td>
<td>REC_STATUS</td>
<td>N</td>
<td>1</td>
<td>0-暂时保存 1-最终保存</td>
</tr>
<tr class="odd">
<td>更改库存标志</td>
<td>Change_flag</td>
<td>N</td>
<td>1</td>
<td><p>未更改，1-更改</p>
<p>(实现更改过库存不能再更改库存，加一个标志位)</p></td>
</tr>
</tbody>
</table>

主键：盘点年月，库存管理单位，药品代码，包装规格，厂家标识，批号，最小单位规格

## 药品盘点表DRUG_INVENTORY_BALANCE(徐州二院使用)

|            |                  |      |      |      |
|------------|------------------|------|------|------|
| 字段中文名 | 字段名           | 类型 | 长度 | 说明 |
|            | STORAGE          | C    | 8    |      |
|            | SUB_STORAGE      | C    | 10   |      |
|            | YEAR_MONTH       | D    |      |      |
|            | DRUG_CODE        | C    | 20   |      |
|            | DRUG_SPEC        | C    | 20   |      |
|            | UNITS            | C    | 8    |      |
|            | FIRM_ID          | C    | 10   |      |
|            | BATCH_NO         | C    | 16   |      |
|            | PACKAGE_SPEC     | C    | 20   |      |
|            | PACKAGE_UNITS    | C    | 8    |      |
|            | INITIAL_QUANTITY | N    | 12,2 |      |
|            | INITIAL_MONEY    | N    | 10,2 |      |
|            | IMPORT_QUANTITY  | N    | 12,2 |      |
|            | IMPORT_MONEY     | N    | 10,2 |      |
|            | EXPORT_QUANTITY  | N    | 12,2 |      |
|            | EXPORT_MONEY     | N    | 10,2 |      |
|            | INVENTORY        | N    | 12,2 |      |
|            | INVENTORY_MONEY  | N    | 10,2 |      |
|            | PROFIT           | N    | 10,2 |      |
|            | ACTUAL_QUANTITY  | N    | 12,2 |      |
|            | ACTUAL_PRICE     | N    | 10,4 |      |
|            | TRADE_PRICE      | N    | 10,4 |      |
|            | RETAIL_PRICE     | N    | 10,4 |      |
|            | REC_STATUS       | N    | 1    |      |

注释：徐州二院用

主键：storage,year_month,drug_code,drug_spec,frim_id,package_spec

## 库存盘点货位 DRUG_STOCK_LOCATION(新增)

|                |                       |      |      |                          |
|----------------|-----------------------|------|------|--------------------------|
| 字段中文名     | 字段名                | 类型 | 长度 | 说明                     |
| 库存管理单位   | STORAGE               | C    | 8    | 库房代码，见库存单位字典 |
| 药品代码       | DRUG_CODE             | C    | 10   | 由药品字典定义的代码     |
| 规格           | DRUG_SPEC             | C    | 20   | 由药品字典定义的规格     |
| 单位           | units                 |      |      |                          |
| 批号           | BATCH_NO              | C    | 16   | XX/XX/XXXXXX             |
| 厂家标识       | FIRM_ID               | C    | 10   |                          |
| 包装规格       | PACKAGE_SPEC          | C    | 20   |                          |
| 盘点货位       | CHECK_LOCATION        | C    | 5    | 见货位字典               |
| 有效期         | Expire_date           | date |      |                          |
| 进货价         | Purchase_price        | n    | 10,4 |                          |
| 折扣           | Discount              | n    | 5,2  |                          |
| 数量           | Quantity              | n    | 12,2 |                          |
| 包装单位       | Package_units         | c    | 8    |                          |
| 内含包装1      | Sub_package_1         | n    | 12,2 |                          |
| 内含包装1单位  | Sub_package_units_1   | c    | 8    |                          |
| 内含包装1规格  | Sub_package_spec_1    | c    | 20   |                          |
| 内含包装2      | Sub_package_2         | n    | 12,2 |                          |
| 内含包装2单位  | Sub_package_units_2   | c    | 8    |                          |
| 内含包装2规格  | Sub_package_spec_2    | c    | 20   |                          |
| 存放库房       | Sub_storage           | c    | 8    |                          |
| 货位           | location              | c    | 20   |                          |
| 入库单号       | Document_no           | c    | 10   |                          |
| 供应标志       | Supply_indicator      | n    | 1,0  |                          |
| 货位数量       | LOCATION_QUANTITY     | N    | 12,2 | 见货位表                 |
| 序号           | LOCATION_NO           | N    | 3    | 09.03新加,相当于小货位   |
| 拆零数量       | Residual_quantity     | n    | 12,2 |                          |
| 自定义包装数量 | Otherpack_quantity    | n    | 12,2 |                          |
| 自定义包装系数 | Account_per_otherpack | c    | 10   |                          |

注释：此表是在库存表的基础上加盘点货位、货位数量字段生成。--去掉库存表中其他字段，在程序中已经不用那些字段了。

## 药品入库主记录 DRUG_IMPORT_MASTER

|              |                    |      |      |                                                                    |
|--------------|--------------------|------|------|--------------------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                                               |
| 入库单号     | DOCUMENT_NO        | C    | 10   | 唯一标识一次入库                                                   |
| 库存管理单位 | STORAGE            | C    | 8    | 入库单位代码，见库存单位字典                                       |
| 入库日期     | IMPORT_DATE        | D    |      |                                                                    |
| 供货方       | SUPPLIER           | C    | 40   | 见供货单位字典                                                     |
| 应付款       | ACCOUNT_RECEIVABLE | N    | 10,2 | 该批药品的总应付款（含附加费）                                     |
| 已付款       | ACCOUNT_PAYED      | N    | 10,2 | 该批药品的已付款                                                   |
| 附加费       | ADDITIONAL_FEE     | N    | 8,2  | 该批药品的附加费，如运杂费                                         |
| 入库类别     | IMPORT_CLASS       | C    | 8    | 反映药品来源，如：购入、退货等                                     |
| 存放库房     | SUB_STORAGE        | C    | 8    | 一个库存管理单位内的存放库房，一张入库单只能对应一个库房           |
| 记帐标志     | ACCOUNT_INDICATOR  | N    | 1    | 记帐后入库记录不能修改，作为记帐确认标志。0-未记帐 1-已记帐 2-作废 |
| 备注         | MEMOS              | C    | 20   |                                                                    |
| 录入者       | OPERATOR           | C    | 8    | 录入者姓名                                                         |
| 上账日期     | ACCT_DATE          | D    |      |                                                                    |
| 上帐人       | ACCT_OPERATOR      | C    | 8    | 上帐者姓名                                                         |
| 凭证号       | VOUCHER_NO         | C    | 9    |                                                                    |
| 上账标志     | FLAG               | N    | 1    | 0-未上帐，1-上帐                                                   |
| 上帐日期     | TALLY_DATE         | D    |      |                                                                    |

注释：此表是药品的入库记录。所有库存单位的入库单都保存在本表中，包括药库、门诊药局、临床药局，每类库存单位可以有多个，通过库存管理单位代码反映。一个入库批次是同一供货方同一批次到达的药品，一个入库批次可以包含多张发票。

主键：入库单号。

备注：ACCOUNT_RECEIVABLE= ADDITIONAL_FEE+sum(DRUG\_ IMPORT_DETAIL.purchase_price\* DRUG\_ IMPORT_DETAIL.quantity)

## 药品入库明细记录 DRUG_IMPORT_DETAIL

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 31%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>入库单号</td>
<td>DOCUMENT_NO</td>
<td>C</td>
<td>10</td>
<td>由药品入库主记录定义的入库单号</td>
</tr>
<tr class="odd">
<td>项目序号</td>
<td>ITEM_NO</td>
<td>N</td>
<td>4</td>
<td>标识一个入库单内各项目顺序</td>
</tr>
<tr class="even">
<td>药品代码</td>
<td>DRUG_CODE</td>
<td>C</td>
<td>20</td>
<td>由药品字典定义的代码</td>
</tr>
<tr class="odd">
<td>规格</td>
<td>DRUG_SPEC</td>
<td>C</td>
<td>20</td>
<td>由药品字典定义的规格</td>
</tr>
<tr class="even">
<td>单位</td>
<td>UNITS</td>
<td>C</td>
<td>8</td>
<td>对应剂型及规格，使用规范名称，见4.32计量单位字典</td>
</tr>
<tr class="odd">
<td>批号</td>
<td>BATCH_NO</td>
<td>C</td>
<td>16</td>
<td>使用“XX/XX/XXXXXX”</td>
</tr>
<tr class="even">
<td>有效期</td>
<td>EXPIRE_DATE</td>
<td>D</td>
<td></td>
<td>药品的有效截止日期</td>
</tr>
<tr class="odd">
<td>厂家标识</td>
<td>FIRM_ID</td>
<td>C</td>
<td>10</td>
<td>反映生产厂家，见药品生产厂家字典</td>
</tr>
<tr class="even">
<td>进货价</td>
<td>PURCHASE_PRICE</td>
<td>N</td>
<td>10,4</td>
<td>实际购买价，以包装单位记单价</td>
</tr>
<tr class="odd">
<td>折扣</td>
<td>DISCOUNT</td>
<td>N</td>
<td>5,2</td>
<td>该药品购入时的折扣率。百分数，只记录数值部分</td>
</tr>
<tr class="even">
<td>零售价</td>
<td>RETAIL_PRICE</td>
<td>N</td>
<td>10,4</td>
<td>入库当时的零售价，以包装单位记单价</td>
</tr>
<tr class="odd">
<td>包装规格</td>
<td>PACKAGE_SPEC</td>
<td>C</td>
<td>20</td>
<td>反映药品含量及包装信息，如0.25g*30</td>
</tr>
<tr class="even">
<td>数量</td>
<td>QUANTITY</td>
<td>N</td>
<td>12,2</td>
<td>以包装单位所计的数量</td>
</tr>
<tr class="odd">
<td>包装单位</td>
<td>PACKAGE_UNITS</td>
<td>C</td>
<td>8</td>
<td>计量单位，可使用任一级管理上方便的包装</td>
</tr>
<tr class="even">
<td>内含包装1</td>
<td>SUB_PACKAGE_1</td>
<td>N</td>
<td>12,2</td>
<td>上述一个包装单位中包含的小包装数量，为空或1表示为无此级包装</td>
</tr>
<tr class="odd">
<td>内含包装1单位</td>
<td>SUB_PACKAGE_UNITS_1</td>
<td>C</td>
<td>8</td>
<td>对应内含包装1的单位</td>
</tr>
<tr class="even">
<td>内含包装1规格</td>
<td>SUB_PACKAGE_SPEC_1</td>
<td>C</td>
<td>20</td>
<td>对应内含包装1的规格</td>
</tr>
<tr class="odd">
<td>内含包装2</td>
<td>SUB_PACKAGE_2</td>
<td>N</td>
<td>12,2</td>
<td>内含包装1中包含的小包装数量，为空或1表示为无此级包装</td>
</tr>
<tr class="even">
<td>内含包装2单位</td>
<td>SUB_PACKAGE_UNITS_2</td>
<td>C</td>
<td>8</td>
<td>对应内含包装2的单位</td>
</tr>
<tr class="odd">
<td>内含包装2规格</td>
<td>SUB_PACKAGE_SPEC_2</td>
<td>C</td>
<td>20</td>
<td>对应内含包装2的规格</td>
</tr>
<tr class="even">
<td>发票号</td>
<td>INVOICE_NO</td>
<td>C</td>
<td>10</td>
<td><p>该药品对应供货发票号;</p>
<p>如果是批量入库，发票号为对方出库单号</p></td>
</tr>
<tr class="odd">
<td>发票日期</td>
<td>INVOICE_DATE</td>
<td>D</td>
<td></td>
<td><p>该药品对应供货发票的开票日期；</p>
<p>如果是批量入库，发票日期为对方出库日期</p></td>
</tr>
<tr class="even">
<td>发票付款标志</td>
<td>invoice_sign</td>
<td>N</td>
<td>1</td>
<td>//0-未付款 1-已付款</td>
</tr>
<tr class="odd">
<td>批发价</td>
<td>Trade_price</td>
<td>N</td>
<td>10,4</td>
<td></td>
</tr>
<tr class="even">
<td>入库后库存数</td>
<td>inventory</td>
<td>N</td>
<td>12,2</td>
<td></td>
</tr>
<tr class="odd">
<td>备注</td>
<td>Memo</td>
<td>N</td>
<td>20</td>
<td></td>
</tr>
<tr class="even">
<td>招标批号</td>
<td>ORDER_BATCH</td>
<td>C</td>
<td>4</td>
<td></td>
</tr>
<tr class="odd">
<td></td>
<td>Voucher_no</td>
<td>C</td>
<td>9</td>
<td></td>
</tr>
<tr class="even">
<td>中标序号</td>
<td>TENDER_NO</td>
<td>N</td>
<td>4</td>
<td></td>
</tr>
</tbody>
</table>

注释：此表为药品入库主记录的明细记录，描述了入库的每一种药品。

主键：入库单号、项目序号。

备注：

## 药品出库主记录 DRUG_EXPORT_MASTER

|              |                    |      |      |                                                                    |
|--------------|--------------------|------|------|--------------------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                                               |
| 出库单号     | DOCUMENT_NO        | C    | 10   | 唯一标识一次出库                                                   |
| 库存管理单位 | STORAGE            | C    | 8    | 出库单位代码，见库存单位字典                                       |
| 出库日期     | EXPORT_DATE        | D    |      |                                                                    |
| 收货方       | RECEIVER           | C    | 40   |                                                                    |
| 应付款       | ACCOUNT_RECEIVABLE | N    | 10,2 | 该批药品的总应付款（含附加费）                                     |
| 已付款       | ACCOUNT_PAYED      | N    | 10,2 | 该批药品的已付款                                                   |
| 附加费       | ADDITIONAL_FEE     | N    | 8,2  | 该批药品的附加费，如运杂费                                         |
| 出库类别     | EXPORT_CLASS       | C    | 8    | 反映药品去向，如药局领药等                                         |
| 存放库房     | SUB_STORAGE        | C    | 8    | 一个库存管理单位内的存放库房，一张出库单只能对应一个库房           |
| 记帐标志     | ACCOUNT_INDICATOR  | N    | 1    | 记帐后入库记录不能修改，作为记帐确认标志。0-未记帐 1-已记帐 2-作废 |
| 备注         | MEMOS              | C    | 20   |                                                                    |
| 录入者       | OPERATOR           | C    | 8    | 录入者姓名                                                         |
| 上账日期     | ACCT_DATE          | D    |      |                                                                    |
| 上帐人       | ACCT_OPERATOR      | C    | 8    | 上帐者姓名                                                         |
| 凭证号       | VOUCHER_NO         | C    | 9    |                                                                    |
| 上账标志     | FLAG               | N    | 1    | 0-未上帐，1-上帐                                                   |

注释：此表是药品的出库记录。所有库存单位的出库单都保存在本表中，包括药库、门诊药局、临床药局，每类库存单位可以有多个，通过库存管理单位代码反映。

主键：出库单号。

备注：ACCOUNT_RECEIVABLE= ADDITIONAL_FEE+sum(DRUG_EXPORT_DETAIL.purchase_price\* DRUG_EXPORT_DETAIL.quantity)

## 药品出库明细记录 DRUG_EXPORT_DETAIL

|               |                     |      |      |                                                             |
|---------------|---------------------|------|------|-------------------------------------------------------------|
| 字段中文名称  | 字段名              | 类型 | 长度 | 说明                                                        |
| 出库单号      | DOCUMENT_NO         | C    | 10   | 由药品出库主记录定义的入库单号                              |
| 项目序号      | ITEM_NO             | N    | 4    | 标识一个入库单内各项目顺序                                  |
| 药品代码      | DRUG_CODE           | C    | 20   | 由药品字典定义的代码                                        |
| 规格          | DRUG_SPEC           | C    | 20   | 由药品字典定义的规格                                        |
| 单位          | UNITS               | C    | 8    | 对应剂型及规格，使用规范名称，见4.32计量单位字典            |
| 批号          | BATCH_NO            | C    | 16   | 使用“XX/XX/XXXXXX”                                          |
| 有效期        | EXPIRE_DATE         | D    |      | 药品的有效截止日期                                          |
| 厂家标识      | FIRM_ID             | C    | 10   | 反映生产厂家，见药品生产厂家字典                            |
| 相关入库单号  | IMPORT_DOCUMENT_NO  | C    | 10   | 该药品入库时赋予的入库单号，用于与库存药品关联              |
| 出库价        | PURCHASE_PRICE      | N    | 10,4 | 以包装单位记单价                                            |
| 零售价        | RETAIL_PRICE        | N    | 10,4 | 出库当时的零售价，以包装单位记单价                          |
| 包装规格      | PACKAGE_SPEC        | C    | 20   | 反映药品含量及包装信息，如0.25g\*30                         |
| 数量          | QUANTITY            | N    | 12,2 | 以包装单位所计的数量                                        |
| 包装单位      | PACKAGE_UNITS       | C    | 8    | 计量单位，可使用任一级管理上方便的包装                      |
| 内含包装1     | SUB_PACKAGE_1       | N    | 12,2 | 上述一个包装单位中包含的小包装数量，为空或1表示为无此级包装 |
| 内含包装1单位 | SUB_PACKAGE_UNITS_1 | C    | 8    | 对应内含包装1的单位                                         |
| 内含包装1规格 | SUB_PACKAGE_SPEC_1  | C    | 20   | 对应内含包装1的规格                                         |
| 内含包装2     | SUB_PACKAGE_2       | N    | 12,2 | 内含包装1中包含的小包装数量，为空或1表示为无此级包装        |
| 内含包装2单位 | SUB_PACKAGE_UNITS_2 | C    | 8    | 对应内含包装2的单位                                         |
| 内含包装2规格 | SUB_PACKAGE_SPEC_2  | C    | 20   | 对应内含包装2的规格                                         |
| 批发价        | Trade_price         | N    | 10,4 |                                                             |
| 出库后库存数  | Inventory           | N    | 12,2 |                                                             |

注释：此表为药品出库主记录的明细记录，描述了出库的每一种药品。

主键：出库单号、项目序号。

## 药品发放申请 DRUG_PROVIDE_APPLICATION

|              |                     |      |      |                                                   |
|--------------|---------------------|------|------|---------------------------------------------------|
| 字段中文名称 | 字段名              | 类型 | 长度 | 说明                                              |
| 请领库房     | APPLICANT_STORAGE   | C    | 8    | 提出申请者库房代码，见库存单位字典                |
| 发放库房     | PROVIDE_STORAGE     | C    | 8    | 药品发放者库房代码，见库存单位字典                |
| 项目序号     | ITEM_NO             | N    | 4    | 一个申请者的所有申请药品排序                      |
| 药品代码     | DRUG_CODE           | C    | 20   | 由药品字典定义的代码                              |
| 规格         | DRUG_SPEC           | C    | 20   | 由药品字典定义的规格                              |
| 包装规格     | PACKAGE_SPEC        | C    | 20   | 反映药品含量及包装信息，如0.25g\*30               |
| 数量         | QUANTITY            | N    | 12,2 | 以包装单位所计的数量                              |
| 包装单位     | PACKAGE_UNITS       | C    | 8    | 对应包装规格的单位                                |
| 申请日期     | ENTER_DATE_TIME     | D    |      |                                                   |
| 厂家标识     | FIRM_ID             | C    | 10   |                                                   |
| 批号         | batch_no            | var  | 16   |                                                   |
| 未发数量     | no_provide_quantity | N    |      | 记录药品申请单中没有发放的药品的数量,在出库时填写 |
| 出库单号     | DOCUMENT_NO         | VAR  | 10   | 记录药品申请单出库时的出库单据号，在出库时填写    |

注释：此表为药局与药库之间药品请领的中间表。

主键：请领库房、项目序号。

## 药品发放通知 DRUG_PROVIDE_NOTICE

|              |                   |      |      |                                    |
|--------------|-------------------|------|------|------------------------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                               |
| 发放库房     | PROVIDE_STORAGE   | C    | 8    | 药品发放者库房代码，见库存单位字典 |
| 请领库房     | APPLICANT_STORAGE | C    | 8    | 请领者库房代码，见库存单位字典     |
| 出库单号     | DOCUMENT_NO       | C    | 10   | 对应出库库房出库单                 |

注释：此表为药局与药库之间药品发放的中间表。

主键：发放库房、出库单号。

## 药品结转记录 DRUG_STOCK_BALANCE

|                      |                          |      |       |                                                                  |
|----------------------|--------------------------|------|-------|------------------------------------------------------------------|
| 字段中文名称         | 字段名                   | 类型 | 长度  | 说明                                                             |
| 库房管理单位         | STORAGE                  | C    | 8     | 库房代码，见库存单位字典                                         |
| 年月                 | YEAR_MONTH               | D    |       | 结转期间                                                         |
| 药品代码             | DRUG_CODE                | C    | 20    | 由药品字典定义的代码                                             |
| 规格                 | DRUG_SPEC                | C    | 20    | 由药品字典定义的规格                                             |
| 厂家标识             | FIRM_ID                  | C    | 10    | 反映生产厂家，见药品生产厂家字典                                 |
| 包装规格             | PACKAGE_SPEC             | C    | 20    | 反映药品含量及包装信息，如0.25g\*30                              |
| 包装单位             | PACKAGE_UNITS            | C    | 8     | 计量单位                                                         |
| 期初数               | INITIAL_QUANTITY         | N    | 12,2  | 上一结转期间的库存数                                             |
| 期初金额             | INITIAL_MONEY            | N    | 10,2  | 上一结转期间的库存金额，为各批次库存数按入库价计算的累计金额     |
| 入库数量             | IMPORT_QUANTITY          | N    | 12,2  | 本统计期间的累计入库数，以包装单位计                             |
| 入库金额             | IMPORT_MONEY             | N    | 10,2  | 本统计期间的累计入库金额，为各入库批次数量按入库价计算的累计金额 |
| 出库数量             | EXPORT_QUANTITY          | N    | 12,2  | 本统计期间的累计出库数，以包装单位计                             |
| 出库金额             | EXPORT_MONEY             | N    | 10,2  | 本统计期间的累计出库金额，为各出库批次数量按出库价计算的累计金额 |
| 处方消耗数量         | EXPORT_PRESC_QUANTITY    | N    | 12，2 | 本统计期间处方消耗数量                                           |
| 处方消耗金额         | EXPORT_presc_MONEY       | N    | 10，2 | 本统计期间处方消耗金额                                           |
| 摆药消耗数量         | EXPORT_disp_QUANTITY     | N    | 12，2 | 本统计期间摆药消耗数量                                           |
| 摆药消耗金额         | EXPORT_disp_MONEY        | N    | 10，2 | 本统计期间摆药消耗金额                                           |
| 返库数量             | EXPORT_back_quantity     | N    | 12,2  | 本统计期间返回数量                                               |
| 返库金额             | EXPORT_back_MONEY        | N    | 10，2 | 本统计期间返回金额                                               |
| 报损数量             | Export_loss_quantity     | N    | 12，2 | 本统计期间报损数量                                               |
| 报损金额             | EXPORT_loss_MONEY        | N    | 10，2 | 本统计期间报损金额                                               |
| 结存库存数量         | INVENTORY                | N    | 12,2  | 截至统计期末的库存数                                             |
| 结存库存金额         | INVENTORY_MONEY          | N    | 10,2  | 截至统计期末的库存金额，为各批次库存数按入库价计算的累计金额     |
| 出库药品出入盈亏     | PROFIT                   | N    | 10,2  | 出库药品的出与入差价金额，当亏损时为负数                         |
| 存放库房             | SUB_STORAGE              | C    | 8     | DRUG_SUB_STORAGE_DICT. SUB_STORAGE                               |
| 期初金额_进价        | Initial_money_purchase   | N    | 10,2  | 以进价计算的期初金额                                             |
| 入库金额_进价        | IMPORT_MONEY_purchase    | N    | 10,2  | 以进价计算的入库价                                               |
| 出库金额_进价        | EXPORT_MONEY_purchase    | N    | 10,2  | 以进价计算的出库价                                               |
| 期末金额_进价        | INVENTORY_MONEY_purchase | N    | 10,2  | 以进价计算的期末金额                                             |
| 操作日期             | operate_date             | date |       |                                                                  |
| 操作员               | operator                 | var  | 20    |                                                                  |
| 处方盈亏             | Presc_profit             | N    | 10，2 |                                                                  |
| 月结时间区间（左区间 | begin_date               | date |       |                                                                  |
| 月结时间区间（右区间 | end_date                 | date |       |                                                                  |

注释：此表为统计中间表，描述了库存单位的流动及库存情况。

主键：月份、库房管理单位，药品代码、药品规格、厂家标识、包装规格。

## 采购信息表 buy_drug_plan(新增)

|              |                 |      |      |                                                                              |
|--------------|-----------------|------|------|------------------------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                                         |
| 采购单据号   | BUY_ID          | C    | 12   | 日期+4位流水号                                                               |
| 采购单序号   | BUY_NO          | N    | 4    |                                                                              |
| 药品代码     | DRUG_CODE       | C    | 20   | 药品名（含剂型）的唯一标识，与药品规格一起构成一种药品（含规格）的标识       |
| 药品名称     | DRUG_NAME       | C    | 100  | 药品的标准名称                                                               |
| 规格         | DRUG_SPEC       | C    | 20   | 反映药品的含量信息，如25mg                                                   |
| 单位         | UNITS           | C    | 8    | 对应剂型及规格的最小单位，如片、支等，使用规范名称，见4.32计量单位字典       |
| 剂型         | DRUG_FORM       | C    | 10   | 如针剂、片剂等，使用规范描述，见剂型字典                                     |
| 毒理分类     | TOXI_PROPERTY   | C    | 10   | 按药品的毒理分类，如普通、毒麻、精神等，使用规范名称，本系统定义，见毒理字典 |
| 最小单位剂量 | DOSE_PER_UNIT   | N    | 8,3  | 每一最小不可分包装单位所含剂量，如每片、每支的剂量                           |
| 剂量单位     | DOSE_UNITS      | C    | 8    | 剂量的单位，如mg、ml等                                                       |
| 药品类别标志 | DRUG_INDICATOR  | N    | 1    | 反映是否药品及何类药品：1-药品 2-中草药 3-原料 4-化学试剂 5-敷料 9-其它      |
| 输入码       | INPUT_CODE      | C    | 8    |                                                                              |
| 计划数量     | WANT_NUMBER     | N    | 12,2 |                                                                              |
| 仓管员       | STORER          | C    | 8    | 最好编码，但工程都存名称，统一存名称                                         |
| 采购数量     | STOCK_NUMBER    | N    | 12,2 |                                                                              |
| 采购供应商   | STOCK_SUPPLIER  | C    | 10   | 厂商标识                                                                     |
| 采购员       | BUYER           | C    | 8    |                                                                              |
| 审核数量     | CHECK_NUMBER    | N    | 12,2 |                                                                              |
| 审核供应商   | CHECK_SUPPLIER  | C    | 10   |                                                                              |
| 审核员       | CHECKER         | C    | 8    |                                                                              |
| 执行标志     | FLAG            | N    | 1    | 0-未执行，1-执行2-采购员执行,9-需审批09.03                                   |
| 包装规格     | PACK_SPEC       | C    | 20   | 09.03                                                                        |
| 包装单位     | PACK_UNIT       | C    | 8    | 09.03                                                                        |
| 厂商         | FIRM_ID         | C    | 10   | 09.17加                                                                      |
| 进货价       | PURCHASE_PRICE  | N    | 10,4 | 09.17加                                                                      |
| 库存管理单位 | STORAGE         | C    | 8    |                                                                              |
| 已执行数量   | executed_number | N    | 12,2 |                                                                              |
| 入库单据号   | import_document | VAR2 | 50   | 入库单据号,以分号间隔                                                        |

此表在药品基本信息的基础上增加了采购信息

主键：药品采购单据号,采购单序号

## 药品调价记录 drug_price_modify(新增)

|                  |                       |      |      |                         |
|------------------|-----------------------|------|------|-------------------------|
| 中文名称         | 字段名                | 类型 | 长度 | 说明                    |
| 药品代码         | DRUG_CODE             | C    | 10   | 由药品字典定义的代码    |
| 包装规格         | DRUG_SPEC             | C    | 20   |                         |
| 厂家标识         | FIRM_ID               | C    | 10   | 反映生产厂家            |
| 包装单位         | UNITS                 | C    | 8    |                         |
| 最小规格         | MIN_SPEC              | C    | 20   | 对应DRUG_DICT.drug_spec |
| 最小单位         | MIN_UNITS             | C    | 8    | 对应DRUG_DICT.units     |
| 原市场批发价     | ORIGINAL_TRADE_PRICE  | N    | 10,4 |                         |
| 现市场批发价     | CURRENT_TRADE_PRICE   | N    | 10,4 |                         |
| 原市场零售价     | ORIGINAL_RETAIL_PRICE | N    | 10,4 |                         |
| 现市场零售价     | CURRENT_RETAIL_PRICE  | N    | 10,4 |                         |
| 调价通知生效日期 | NOTICE_EFFICIENT_DATE | D    |      |                         |
| 调价实际生效日期 | ACTUAL_EFFICIENT_DATE | D    |      |                         |
| 调价依据         | MODIFY_CREDENTIAL     | C    | 50   |                         |
| 录入者姓名       | operator              | var  | 20   |                         |

主键：药品代码、包装规格、厂家标识、调价通知生效日期

注释：此表记录药品调价情况，如果调价文件中包含药品基本信息以外的药品，需首先在药品基本信息表中建立该药品的记录。

> 数据增长量约为每月60条。

## 药品调价盈亏表 drug_price_modify_profit(新增)

|                                |                       |      |      |                          |
|--------------------------------|-----------------------|------|------|--------------------------|
| 中文名称                       | 字段名                | 类型 | 长度 | 说明                     |
| 库房编码                       | STORAGE               | C    | 8    | 库房代码，见库存单位字典 |
| 药品代码                       | DRUG_CODE             | C    | 20   | 发生调价的药品代码       |
| 包装规格                       | DRUG_SPEC             | C    | 20   |                          |
| 厂家标识                       | FIRM_ID               | C    | 10   | 反映生产厂家             |
| 包装单位                       | UNITS                 | C    | 8    |                          |
| 调价时库存数                   | QUANTITY              | N    | 12,2 |                          |
| 原市场批发价                   | ORIGINAL_TRADE_PRICE  | N    | 10,4 |                          |
| 现市场批发价                   | CURRENT_TRADE_PRICE   | N    | 10,4 |                          |
| 批发价盈亏                     | TRADE_PRICE_PROFIT    | N    | 12,2 |                          |
| 原市场零售价                   | ORIGINAL_RETAIL_PRICE | N    | 10,4 |                          |
| 现市场零售价                   | CURRENT_RETAIL_PRICE  | N    | 10,4 |                          |
| 零售价盈亏金额                 | RETAIL_PRICE_PROFIT   | N    | 12,2 |                          |
| 调价实际生效日期               | ACTUAL_EFFICIENT_DATE | D    |      | 非空                     |
| 盈亏项目序号                   | Profit_item_no        | N    | 3,0  |                          |
| 类型                           | typex                 | N    | 1,0  | 0,null-调价 1-处方       |
| 处方日期                       | presc_date            | DATE |      |                          |
| 处方号                         | presc_no              | N    | 5,0  |                          |
| 项目序号                       | ITEM_NO               | N    | 2,0  |                          |
| 调价盈亏出入库单据部分的单据号 | document_no           | Var2 | 10   |                          |

主键：库房、药品代码、包装规格、厂家标识、调价实际生效日期、 Profit_item_no

注释：此表记录每次调价的盈亏情况。

> 数据增长量约为每月60条。

## 药品总账DRUG_LEDGER(新增)

为实现总账的功能，需要增加表：

|              |              |      |      |                |
|--------------|--------------|------|------|----------------|
| 字段中文名称 | 字段名       | 类型 | 长度 | 说明           |
| 库存单位     | STORAGE      | C    | 8    |                |
| 日期         | ACCT_DATE    | D    |      |                |
| 凭证号       | VOUCHER_NO   | C    | 9    | 应该是明细帐号 |
| 子库房       | SUB_STORAGE  | C    | 8    |                |
| 摘要         | SUMMARY      | C    | 40   | 对方单位名称。 |
| 入库金额     | IMPORT_MONEY | N    | 12,2 |                |
| 差价金额     | DIFF_MONEY   | N    | 12,2 |                |
| 出库金额     | EXPORT_MONEY | N    | 12,2 |                |
| 结存金额     | REMA_MONEY   | N    | 12,2 |                |

主键：STORAGE, ACCT_DATE, VOUCHER_NO, SUB_STORAGE

备注：在统计明细账时，入账的自动在此表中插入一条记录，其中的差价金额=零售价-入库价，结存金额=上条记录的结存+入库+差价-出库。其中的出库金额指的是零售价的。窗口应支持在总账插入一条记录来平帐。初始化时也如此输入一条记录。窗口应有一个时间点选择，可以检索打印在此点之后的总帐。

## 凭证号生成字典VOUCHER_NO_CREATE_DICT(新增)

|                |                  |      |      |                                               |
|----------------|------------------|------|------|-----------------------------------------------|
| 字段中文名     | 字段名           | 类型 | 长度 | 说明                                          |
| 库存单位代码   | STORAGE          | C    | 8    | 单位代码                                      |
| 库房           | SUB_STORAGE      | C    | 8    |                                               |
| 入凭证前缀     | IMPORT_NO_PREFIX | C    | 7    | 此前缀与入凭证号一起构成入凭证号：例如R030923 |
| 入凭证流水号   | IMPORT_NO_AVA    | N    | 2    | 可用的流水号                                  |
| 出凭证单号前缀 | EXPORT_NO_PREFIX | C    | 7    | 类似入，例如:C030923                          |
| 出凭证流水号   | EXPORT_NO_AVA    | N    | 2    | 可用的流水号                                  |

注释：为满足凭证号的生成问题

几种情况：

当表中没有该科室的数据时，插入一条2000年01月01的。

当表中的数据是今天的时，将此数取出，设为凭单的号，在程序的设置成功后，将此号加1设到此表中，

保存。

当表中的数据不是今天的时，生成一个返回的数据。在程序的设置中将此数据更新到此表中。

*每个子库房独立使用自己的单据系列*

主键：库存单位代码、库房

## 药品库存单位字典 DRUG_STORAGE_DEPT 

|                  |                    |      |      |                                                                            |
|------------------|--------------------|------|------|----------------------------------------------------------------------------|
| 字段中文名       | 字段名             | 类型 | 长度 | 说明                                                                       |
| 单位代码         | STORAGE_CODE       | C    | 8    | 唯一标识一个库存单位，可使用单位代码                                       |
| 单位名称         | STORAGE_NAME       | C    | 20   |                                                                            |
| 单位性质         | STORAGE_TYPE       | C    | 8    | 标识药库、门诊药局、临床药局等                                             |
| 付款单前缀       | Disburse_no_prefix | C    | 6    | 为该库存单位供货的上游库存单位代码，为空时表示该库存单位为顶层单位或不确定 |
| 当前付款单号     | Disburse_no_ava    | N    | 4    |                                                                            |
| 出库单可用流水号 | Export_no_ava      | N    | 4    |                                                                            |
| 出库单号前缀     | Export_no_prefix   | C    | 6    |                                                                            |
| 入库单可用流水号 | Import_no_ava      | N    | 4    |                                                                            |
| 入库单号前缀     | Import_no_prefix   | C    | 6    |                                                                            |

注释：此表定义了具有药品库存管理功能的单位，用户定义。

主键：单位代码

## 药品库存单位库房字典 DRUG_SUB_STORAGE_DICT 

|                  |                  |      |      |                                      |
|------------------|------------------|------|------|--------------------------------------|
| 字段中文名       | 字段名           | 类型 | 长度 | 说明                                 |
| 库存单位代码     | STORAGE_CODE     | C    | 8    | 唯一标识一个库存单位，可使用单位代码 |
| 库房             | SUB_STORAGE      | C    | 8    |                                      |
| 入库单号前缀     | IMPORT_NO_PREFIX | C    | 6    | 此前缀与入库单流水号一起构成入库单号 |
| 入库单可用流水号 | IMPORT_NO_AVA    | N    | 4    | 当前可用流水号                       |
| 出库单号前缀     | EXPORT_NO_PREFIX | C    | 6    | 此前缀与出库单流水号一起构成出库单号 |
| 出库单可用流水号 | EXPORT_NO_AVA    | N    | 4    | 当前可用流水号                       |

注释：此表定义了每个药品库存管理单位包含的存放库房，用户定义。

主键：库存单位代码、库房

说明：PREFIX+ AVA= document_no (入/出库单号，最大长度为10)

## 特殊管理药品目录 MANAGED_DRUG_CATALOG 

|              |               |      |      |                                              |
|--------------|---------------|------|------|----------------------------------------------|
| 字段中文名   | 字段名        | 类型 | 长度 | 说明                                         |
| 库存管理单位 | STORAGE       | C    | 8    | 库房代码，见库存单位字典                     |
| 管理类别     | MANAGED_CLASS | C    | 10   | 对限制管理的药品分类，见特殊管理药品类别字典 |
| 药品代码     | DRUG_CODE     | C    | 20   | 纳入该管理类别的特殊药品代码                 |
| 药品规格     | DRUG_SPEC     | C    | 20   | 由药品字典定义的规格                         |
| 厂家标识     | FIRM_ID       | C    | 10   |                                              |

注释：此表定义各库存单位需要特殊管理的药品，如：贵重药、自费药、试验药等，用于相关的统计表中。

> 每个库存单位可以定义各自的管理目录，管理目录可以分为不同的类别，一个药可以属于多个类别。
>
> 药品需要标识到厂家，不同规格、不同厂家的药品可以具有不同的管理特征。

主键：库存管理单位、管理类别、药品代码、药品规格、厂家标识

## 特殊管理药品类别字典 MANAGED_DRUG_CLASS_DICT 

|            |               |      |      |                  |
|------------|---------------|------|------|------------------|
| 字段中文名 | 字段名        | 类型 | 长度 | 说明             |
| 序号       | SERIAL_NO     | N    | 2    | 反映项目排列顺序 |
| 管理类别   | MANAGED_CLASS | C    | 10   | 特殊管理类别名称 |

注释：此表定义了设置的特殊药品管理类别名称，用户定义。

主键：管理类别

## 药局药品分装记录 DRUG_PACKAGES

|              |                    |      |      |                                                                                             |
|--------------|--------------------|------|------|---------------------------------------------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                                                                        |
| 药房         | DISPENSARY         | C    | 8    | 药房的单位代码                                                                              |
| 药品代码     | DRUG_CODE          | C    | 20   | 由药品字典定义的代码                                                                        |
| 规格         | DRUG_SPEC          | C    | 20   | 由药品字典定义的规格                                                                        |
| 单位         | DRUG_UNITS         | C    | 8    | 对应药品规格的单位                                                                          |
| 厂商标识     | FIRM_ID            | C    | 10   | 反映生产厂家，见药品生产厂家字典                                                            |
| 包装规格     | PACKAGE_SPEC       | C    | 20   | 对应药品库存的规格，反映药品含量及包装信息，如0.25g\*30                                     |
| 包装单位     | PACKAGE_UNITS      | C    | 8    | 对应包装规格的单位，如瓶、包等，使用规范描述，见4.3.2计量单位字典                           |
| 每分装数量   | NUMBER_PER_PACKAGE | N    | 5,2  | 每个发放单位即分装包含的包装单位药品的数量。如：每包12片。当发放单位与包装单位相同时，为1。 |
| 供应标志     | SUPPLY_INDICATOR   | N    | 1    | 反映该药品当前是否可供使用，0-不可供 1-可供                                                 |

注释：此表用于反映门诊药局供应药品的每个发放单位即分装情况，为门诊收费提供信息。

主键：药房、药品代码、包装规格、厂商标识。

## 药品处方主记录 DRUG_PRESC_MASTER

|              |                            |          |      |                                                              |
|--------------|----------------------------|----------|------|--------------------------------------------------------------|
| 字段中文名称 | 字段名                     | 类型     | 长度 | 说明                                                         |
| 处方日期     | PRESC_DATE                 | D        |      | 与处方序号一起构成一张处方的唯一标识                         |
| 处方号       | PRESC_NO                   | N        | 5    | 在一个日期内唯一                                             |
| 发药药局     | DISPENSARY                 | C        | 8    | 库存单位代码，见库存单位字典                                 |
| 病人标识号   | PATIENT_ID                 | C        | 10   | 对有主索引记录的病人使用                                     |
| 姓名         | NAME                       | C        | 20   |                                                              |
| 姓名拼音     | NAME_PHONETIC              | C        | 16   | 病人姓名拼音，大写，字间用一个空格分隔，超长截断             |
| 身份         | IDENTITY                   | C        | 10   | 使用规范名称，由用户定义，见1.6身份字典                      |
| 费别         | CHARGE_TYPE                | C        | 8    | 使用规范名称，由用户定义，见1.9费别字典                      |
| 病人合同单位 | UNIT_IN_CONTRACT           | C        | 11   | 合同单位代码，见2.4合同单位字典                              |
| 处方类别     | PRESC_TYPE                 | N        | 1    | 0=西药 1=中药                                                |
| 处方属性     | PRESC_ATTR                 | C        | 8    | 反映处方用户定义的属性，如：贵重药、麻醉药等，见处方属性字典 |
| 处方来源     | PRESC_SOURCE               | N        | 1    | 标识处方是从门诊而来或是从住院而来。0-门诊 1-住院 2-其它     |
| 剂数         | REPETITION                 | N        | 2    | 缺省为1，中药处方时可大于1                                   |
| 费用         | COSTS                      | N        | 10,4 | 本处方按标准价格计算得到的总费用                             |
| 实付费用     | PAYMENTS                   | N        | 10,4 | 本处方考虑费别等因素后的实际支付费用                         |
| 开单科室     | ORDERED_BY                 | C        | 8    | 使用代码，由用户定义，见2.6科室字典                          |
| 开方医生     | PRESCRIBED_BY              | C        | 8    | 开方医生姓名                                                 |
| 录方人       | ENTERED_BY                 | C        | 8    | 录入者姓名                                                   |
| 发药人       | DISPENSING_PROVIDER        | C        | 8    | 发药者姓名                                                   |
| 每剂煎几份   | Count_per_repetition       | N        | 2    |                                                              |
| 录入日期     | ENTERED_DATETIME           | D        |      |                                                              |
| 发药日期     | DISPENSING_DATETIME        | D        |      |                                                              |
| 备注         | MEMO                       | C        | 100  |                                                              |
| 子库房       | SUB_STORAGE                | C        | 8    |                                                              |
| 退药标志     | FLAG                       | N        | 1    | 1-正常 2-退药                                                |
| 医生         | DOCTOR_USER                | C        | 16   |                                                              |
| 审核         | VERIFY_BY                  | C        | 8    |                                                              |
| 出院带药标志 | DISCHARGE_TAKING_INDICATOR | N        | 1    |                                                              |
| 住院次数     | visit_id                   | n        | 2,0  |                                                              |
| 是否代煎     | decoction                  | n        | 1,0  |                                                              |
| 收据号       | Rcpt_no                    | Varchar2 | 20   | 标识这条记录对应的收据号                                     |
| 原处方日期   | original_presc_date        | date     |      | 退药时，记录被退的处方日期                                   |
| 原处方号     | original_presc_no          | number   | 5    | 退药时，记录被退的处方号，与原处方日期形成一个查询原处方条件 |
| 退费处方号   | return_visit_no1           | n        | 5    | 最近一次退费处方号                                           |
| 退费处方日期 | return_visit_date1         | date     |      | 最近一次退费处方日期                                         |
|              | Clinic_no                  | V2       | 13   | 增加挂号标识                                                 |
| 发药批号     | BATCH_PROVIDE_NO           | V2       | 20   | 批量发药号                                                   |

注释：该表与药品处方明细记录一起构成处方记录，此表为处方主记录，描述每张处方的一般信息。药局发药时（或者门诊收费时），从门诊收费信息中生成。如果日门诊量为1,000人次，则每月增加3万条记录。

主键：处方日期、处方序号。

备注：DRUG_PRESC_MASTER.costs=sum(DRUG_PRESC_DETAIL.costs \* DRUG_PRESC_MASTER.REPETITION)

处方明细记录中有字段“administration”，是记录使用方法的；

处方主记录中有字段“memo”，可记录整副药的用法（如中药）；

## 药品处方明细记录 DRUG_PRESC_DETAIL

|              |                |          |      |                                               |
|--------------|----------------|----------|------|-----------------------------------------------|
| 字段中文名称 | 字段名         | 类型     | 长度 | 说明                                          |
| 处方日期     | PRESC_DATE     | D        |      | 与处方序号一起构成一张处方的唯一标识          |
| 处方号       | PRESC_NO       | N        | 5    |                                               |
| 项目序号     | ITEM_NO        | N        | 2    | 按处方标识分组排序                            |
| 药品代码     | DRUG_CODE      | C        | 20   | 由用户定义，见5.2药品字典                     |
| 药品规格     | DRUG_SPEC      | C        | 20   | 由药品字典定义的规格                          |
| 药品名称     | DRUG_NAME      | C        | 100  |                                               |
| 厂商标识     | FIRM_ID        | C        | 10   | 反映生产厂家，见药品生产厂家字典              |
| 包装规格     | PACKAGE_SPEC   | C        | 20   | 反映药品含量及包装信息，如0.25g\*30           |
| 单位         | PACKAGE_UNITS  | C        | 8    | 如瓶、包等，使用规范描述，见4.3.2计量单位字典 |
| 数量         | QUANTITY       | N        | 6,2  | 以分装为单位的数量，如2包                     |
| 费用         | COSTS          | N        | 10,4 | 按标准价格计算得到的费用                      |
| 实付费用     | PAYMENTS       | N        | 10,4 | 考虑费别等因素后的实际支付费用                |
| 医嘱序号     | Order_no       | n        | 4    |                                               |
| 医嘱子序号   | Order_sub_no   | n        | 2    |                                               |
| 用法         | administration | varchar2 | 16   |                                               |
| 退药标志     | flag           | n        | 1    | 1,null-正常 2-退药                            |
| 单次剂量     | dosage_each    | n        | 10,4 |                                               |
| 剂量单位     | dosage_units   | varchar2 | 8    |                                               |
| 频次         | frequency      | varchar2 | 16   |                                               |
| 医生说明     | freq_detail    | varchar2 | 80   |                                               |
| 药品批号     | BATCH_NO       | varchar2 | 16   |                                               |
| 结存数       | inventory      | N        | 12,2 |                                               |

注释：每张处方可包含多条药品记录。根据经验，每张处方平均为2~3种药品。该表记录保留的时间与门诊收据主记录相同。

主键：处方日期、处方号、项目序号。

## 待发药处方主记录 DRUG_PRESC_MASTER_TEMP

|                  |                        |      |      |                                                              |
|------------------|------------------------|------|------|--------------------------------------------------------------|
| 字段中文名称     | 字段名                 | 类型 | 长度 | 说明                                                         |
| 处方日期         | PRESC_DATE             | D    |      | 与处方序号一起构成一张处方的唯一标识                         |
| 处方号           | PRESC_NO               | N    | 5    | 在一个日期内唯一                                             |
| 发药药局         | DISPENSARY             | C    | 8    | 库存单位代码，见库存单位字典                                 |
| 发药队列号       | QUEUE_ID               | C    | 2    | 后台发药队列                                                 |
| 处理状态         | STATUS                 | N    | 1    | 此处方从发出到处理完毕的各个状态                             |
| 病人标识号       | PATIENT_ID             | C    | 10   | 对有主索引记录的病人使用                                     |
| 姓名             | NAME                   | C    | 20   |                                                              |
| 姓名拼音         | NAME_PHONETIC          | C    | 16   | 病人姓名拼音，大写，字间用一个空格分隔，超长截断             |
| 身份             | IDENTITY               | C    | 10   | 使用规范名称，由用户定义，见1.6身份字典                      |
| 费别             | CHARGE_TYPE            | C    | 8    | 使用规范名称，由用户定义，见1.9费别字典                      |
| 病人合同单位     | UNIT_IN_CONTRACT       | C    | 11   | 合同单位代码，见2.4合同单位字典                              |
| 处方类别         | PRESC_TYPE             | N    | 1    | 0=西药 1=中药                                                |
| 处方属性         | PRESC_ATTR             | C    | 8    | 反映处方用户定义的属性，如：贵重药、麻醉药等，见处方属性字典 |
| 处方来源         | PRESC_SOURCE           | N    | 1    | 标识处方是从门诊而来或是从住院而来。0-门诊 1-住院 2-其它     |
| 剂数             | REPETITION             | N    | 2    | 缺省为1，中药处方时可大于1                                   |
| 费用             | COSTS                  | N    | 10,4 | 本处方按标准价格计算得到的总费用                             |
| 实付费用         | PAYMENTS               | N    | 10,4 | 本处方考虑费别等因素后的实际支付费用                         |
| 开单科室         | ORDERED_BY             | C    | 8    | 使用代码，由用户定义，见2.6科室字典                          |
| 开方医生         | PRESCRIBED_BY          | C    | 8    | 开方医生姓名                                                 |
| 录方人           | ENTERED_BY             | C    | 8    | 录入者姓名                                                   |
| 费用类别         | CHARGE_INDICATOR       | N    | 1    |                                                              |
| 收据号           | RCPT_NO                | C    | 8    |                                                              |
| 性别             | SEX                    | C    | 4    |                                                              |
| 年龄             | AGE                    | N    | 3    |                                                              |
| 每剂煎几副       | COUNT_PER_REPETITION   | N    | 2    |                                                              |
| 录入日期         | ENTERED_DATETIME       | D    |      |                                                              |
| 发药日期         | DISPENSING_DATETIME    | D    |      |                                                              |
| 备注             | MEMO                   | C    | 100  |                                                              |
| 调剂者           | DISPENSING_PROVIDER    | C    | 8    |                                                              |
| 带药标志         | DISCG_TAKING_INDICATOR | N    | 1    |                                                              |
| 病人本次住院标识 | VISIT_ID               | N    | 4    |                                                              |
| 医生             | DOCTOR_USER            | C    | 16   |                                                              |
| 是否代煎         | decoction              | n    | 1.0  |                                                              |
|                  | clinic_no              | V2   | 13   | 增加挂号标识                                                 |

注释：此表用于记录已开单或已收费但尚未发药的处方，由门诊收费或将来的门诊医生工作站录入，发药后，由门诊药局将对应的处方删除。

主键：处方日期、处方号。

## 待发药处方明细记录 DRUG_PRESC_DETAIL_TEMP

|              |                |              |      |                                               |
|--------------|----------------|--------------|------|-----------------------------------------------|
| 字段中文名称 | 字段名         | 类型         | 长度 | 说明                                          |
| 处方日期     | PRESC_DATE     | D            |      | 与处方序号一起构成一张处方的唯一标识          |
| 处方号       | PRESC_NO       | N            | 5    |                                               |
| 项目序号     | ITEM_NO        | N            | 2    | 按处方标识分组排序                            |
| 药品代码     | DRUG_CODE      | C            | 20   | 由用户定义，见5.2药品字典                     |
| 药品规格     | DRUG_SPEC      | C            | 20   | 由药品字典定义的规格                          |
| 药品名称     | DRUG_NAME      | C            | 100  |                                               |
| 厂商标识     | FIRM_ID        | C            | 10   | 反映生产厂家，见药品生产厂家字典              |
| 包装规格     | PACKAGE_SPEC   | C            | 20   | 反映药品含量及包装信息，如0.25g\*30           |
| 单位         | PACKAGE_UNITS  | C            | 8    | 如瓶、包等，使用规范描述，见4.3.2计量单位字典 |
| 数量         | QUANTITY       | N            | 6,2  | 以分装为单位的数量，如2包                     |
| 费用         | COSTS          | N            | 10,4 | 按标准价格计算得到的费用                      |
| 实付费用     | PAYMENTS       | N            | 10,4 | 考虑费别等因素后的实际支付费用                |
| 用法         | ADMINISTRATION | C            | 16   |                                               |
| 医嘱序号     | ORDER_NO       | N            | 4    |                                               |
|              | ITEM_SNO       | N            | 2    |                                               |
| 医嘱子序号   | ORDER_SUB_NO   | N            | 2    |                                               |
| 使用剂量     | dosage_each    | N            | 10,4 |                                               |
| 剂量单位     | dosage_units   | varchar2(8)  |      |                                               |
| 频次         | frequency      | varchar2(16) |      |                                               |
| 医生说明     | freq_detail    | varchar2(80) |      |                                               |
| 药品批号     | BATCH_NO       | varchar2     | 16   |                                               |

注释：此表为待发药处方的明细记录，由门诊收费或将来的门诊医生工作站录入，发药后，由门诊药局将其删除。

主键：处方日期、处方号、项目序号。

## 待发药住院处方主记录DOCT_DRUG_PRESC_MASTER(新增)

|              |                            |      |      |            |
|--------------|----------------------------|------|------|------------|
| 字段中文名   | 字段名                     | 类型 | 长度 | 说明       |
| 处方日期     | PRESC_DATE                 | D    |      |            |
| 处方号       | Presc_no                   | N    | 5,0  |            |
| 发药药局     | DISPENSARY                 | C    | 8    |            |
| 病人ID       | PATIENT_ID                 | C    | 10   |            |
| 住院次数     | VISIT_ID                   | N    | 2    |            |
| 姓名         | NAME                       | C    | 20   |            |
| 姓名拼音码   | NAME_PHONETIC              | C    | 16   |            |
| 身份         | IDENTITY                   | C    | 10   |            |
| 费别         | CHARGE_TYPE                | C    | 8    |            |
| 合同单位     | UNIT_IN_CONTRACT           | C    | 11   |            |
| 处方类型     | PRESC_TYPE                 | N    | 1    | 0西药1中药 |
| 处方属性     | PRESC_ATTR                 | C    | 8    |            |
| 处方来源     | PRESC_SOURCE               | N    | 1    |            |
| 出院带药标志 | DISCHARGE_TAKING_INDICATOR | N    | 1    | 1出院带药  |
| 处方名       | BINDING_PRESC_TITLE        | C    | 40   |            |
| 剂数         | REPETITION                 | N    | 2    |            |
| 每剂份数     | COUNT_PER_REPETITION       | N    | 2    |            |
| 计价金额     | COSTS                      | N    | 10,4 |            |
| 应收金额     | PAYMENTS                   | N    | 10,4 |            |
| 开单科室     | ORDERED_BY                 | C    | 8    |            |
| 执行人代码   | PRESCRIBED_BY              | C    | 8    |            |
| 确认人代码   | ENTERED_BY                 | C    | 8    |            |
| 处方状态     | PRESC_STATUS               | N    | 1    |            |
| 确认人名称   | DISPENSING_PROVIDER        | C    | 8    |            |
| 说明         | USAGE                      | C    | 50   |            |
| 是否代煎     | DECOCTION                  | N    | 1    |            |
| 医生代码     | DOCTOR_USER                | C    | 16   |            |
| 是否重打     | NEWLY_PRINT                | C    | 1    |            |
| 诊断名称     | DIAGNOSIS_NAME             | v    | 100  |            |

主键：处方日期、处方号。

## 待发药住院处方明细记录DOCT_DRUG_PRESC_DETAIL(新增)

|              |                    |          |      |      |
|--------------|--------------------|----------|------|------|
| 中文名称     | 字段名             | 类型     | 长度 | 说明 |
| 处方日期     | PRESC_DATE         | DATE     |      | 非空 |
| 处方号       | PRESC_NO           | NUMBER   | 4    | 非空 |
| 项目序号     | ITEM_NO            | NUMBER   | 2    | 非空 |
| 医嘱序号     | ORDER_NO           | NUMBER   | 4    |      |
| 医嘱子序号   | ORDER_SUB_NO       | NUMBER   | 2    |      |
| 药品编码     | DRUG_CODE          | VARCHAR2 | 20   |      |
| 药品         | DRUG_SPEC          | VARCHAR2 | 20   |      |
| 药名         | DRUG_NAME          | VARCHAR2 | 100  |      |
| 生产厂商     | FIRM_ID            | VARCHAR2 | 10   |      |
| 包装规格     | PACKAGE_SPEC       | VARCHAR2 | 20   |      |
| 包装单位     | PACKAGE_UNITS      | VARCHAR2 | 8    |      |
| 数量         | QUANTITY           | NUMBER   | 6,2  |      |
| 剂量         | DOSAGE             | NUMBER   | 12,4 |      |
| 剂量单位     | DOSAGE_UNITS       | VARCHAR2 | 8    |      |
| 用法         | ADMINISTRATION     | VARCHAR2 | 16   |      |
| 费用         | COSTS              | NUMBER   | 10,4 |      |
| 已付费用     | PAYMENTS           | NUMBER   | 10,4 |      |
| 备注         | MEMO               | VARCHAR2 | 50   |      |
| 每包装数量   | AMOUNT_PER_PACKAGE | NUMBER   | 5    |      |
| 执行频率描述 | FREQUENCY          | VARCHAR2 | 16   |      |
| 单次剂量     | DOSAGE_EACH        | NUMBER   | 8,4  |      |
| 医嘱说明     | FREQ_DETAIL        | VARCHAR2 | 80   |      |
| 药品批号     | BATCH_NO           | varchar2 | 16   |      |

主键：处方日期、处方号、项目序号。

## 领药单主记录DRUG_APPLICATION_LIST_MASTER(新增)

|            |                      |      |       |      |
|------------|----------------------|------|-------|------|
| 字段中文名 | 字段名               | 类型 | 长度  | 说明 |
| 申请日期   | LIST_DATE            | D    |       |      |
| 申请号     | LIST_no              | N    | 105,0 |      |
| 发药药局   | DISPENSARY           | C    | 8     |      |
| 录入日期   | enter_date           | C    |       |      |
| 处方申请者 | DISPENSARY_provider  | N    | 8     |      |
| 护理标识   | NURSE_INDICATOR      | C    | 1     |      |
| 确认标识   | DISPENSARY_INDICATOR | C    | 1     |      |
| 申请科室   | ORDERED_BY           | C    | 8     |      |

主键: LIST_NO "LIST_DATE" DATE,

## 领药单明细记录DRUG_APPLICATION_LIST_DETAIL(新增)

|          |               |          |      |      |
|----------|---------------|----------|------|------|
| 中文名称 | 字段名        | 类型     | 长度 | 说明 |
| 领药日期 | LIST_DATE     | DATE     |      | 非空 |
| 领药单号 | LIST_NO       | VARCHAR2 | 10   | 非空 |
| 项目序号 | ITEM_NO       | NUMBER   | 3    | 非空 |
| 项目类别 | item_class    | VARCHAR2 | 10   |      |
| 病人ID   | Patient_id    | VARCHAR2 | 10   |      |
| 访问次数 | Visit_id      | NUMBER   | 2    |      |
| 药品代码 | Drug_code     | VARCHAR2 | 20   |      |
| 药品规格 | DRUG_SPEC     | VARCHAR2 | 20   |      |
| 药名名称 | DRUG_NAME     | VARCHAR2 | 100  |      |
| 生产厂商 | FIRM_ID       | VARCHAR2 | 10   |      |
| 包装规格 | PACKAGE_SPEC  | VARCHAR2 | 20   |      |
| 包装单位 | PACKAGE_UNITS | VARCHAR2 | 8    |      |
| 数量     | QUANTITY      | NUMBER   | 6,2  |      |
| 计价金额 | costs         | NUMBER   | 10,4 |      |
| 实收金额 | charges       | NUMBER   | 10,4 |      |

## 摆药记录 DRUG_DISPENSE_REC 

|                |                       |          |      |                                              |
|----------------|-----------------------|----------|------|----------------------------------------------|
| 字段中文名     | 字段名                | 类型     | 长度 | 说明                                         |
| 调配药房       | DISPENSARY            | C        | 8    | 由库存单位字典定义的药房的单位代码           |
| 摆药日期及时间 | DISPENSING_DATE_TIME  | D        |      |                                              |
| 申请科室       | ORDERED_BY            | C        | 8    | 下医嘱的科室代码                             |
| 病人标识号     | PATIENT_ID            | C        | 10   |                                              |
| 本次住院标识   | VISIT_ID              | N        | 2    |                                              |
| 医嘱序号       | ORDER_NO              | N        | 4    | 生成本摆药记录的医嘱序号                     |
| 医嘱子序号     | ORDER_SUB_NO          | N        | 2    | 生成本摆药记录的医嘱子序号                   |
| 药品代码       | DRUG_CODE             | C        | 20   | 根据病房医嘱得到                             |
| 药品规格       | DRUG_SPEC             | C        | 20   | 实际摆药使用的药品规格，是包装规格           |
| 单位           | DRUG_UNITS            | C        | 8    |                                              |
| 厂家标识       | FIRM_ID               | C        | 10   | 反映生产厂家，见药品生产厂家字典             |
| 摆药数量       | DISPENSE_AMOUNT       | N        | 6,2  | 以上述计量单位计算的数量                     |
| 调剂者         | DISPENSING_PROVIDER   | C        | 8    | 调剂者姓名                                   |
| 费用           | COSTS                 | N        | 10,4 | 按标准价格计算得到的费用，由后台划价程序填入 |
| 应收费用       | CHARGES               | N        | 10,4 | 考虑费别后应收的费用，由后台划价程序填入     |
| 计价标志       | CHARGE_INDICATOR      | N        | 1    | 0-未计价 1-已计价由后台划价程序使用          |
| 累积剂量       | cumulate_dosage       | V        | 8    | 参与累积剂量                                 |
| 累积剂量单位   | cumulate_dosage_units | V        | 8    | 参与累积剂量单位                             |
| 药品批号       | BATCH_NO              | varchar2 | 16   |                                              |
| 结存数         | inventory             | n        | 12,2 |                                              |

注释：此表记录病人的摆药情况，它反映了药品的实际消耗。由临床药局子系统或病房摆药时生成。

> 以1000张床位计，若每个病人每天使用5种药品，则每天增加5000条记录，每月增加150,000条记录。

主键：病人ID、病人本次住院标识、医嘱序号、医嘱子序号、摆药日期及时间

## 摆药请求 DRUG_DISPENSE_REQ

|                |                           |      |      |                                                            |
|----------------|---------------------------|------|------|------------------------------------------------------------|
| 字段中文名称   | 字段名                    | 类型 | 长度 | 说明                                                       |
| 护理单元       | WARD                      | C    | 8    | 请求摆药的护理单元代码                                     |
| 执行药局       | DISPENSARY                | C    | 8    | 对应该护理单元提供摆药服务的由库存单位字典定义的药局代码， |
| 提出时间       | POST_DATE_TIME            | D    |      |                                                            |
| 收到标志       | RECEIVE_INDICATOR         | n    | 1    |                                                            |
| 结束日期       | FINISH_DATE_TIME          | d    |      |                                                            |
|                | FETCH_INDICATOR           | n    | 1    |                                                            |
| 请求描述       | REQUEST_DESC              | c    | 400  |                                                            |
| 序号           | ITEM_NO                   | n    | 2,0  |                                                            |
| 床号           | BED_NO                    | Var2 | 200  |                                                            |
| 长期医嘱标志   | REPEAT_INDICATOR          | N    | 1,0  |                                                            |
| 摆药类别       | DISPENSING_PROPERTY       | var  | 200  |                                                            |
| 摆药天数       | dispense_days number(2,0) | N    | 2,0  |                                                            |
| 摆药日期及时间 | DISPENSING_DATE_TIME      | DATE |      |                                                            |
| 结存数         | inventory                 | n    | 12,2 |                                                            |
| 预摆药批号     | OPER_BATCH_NO             | VAR2 | 20   |                                                            |
|                |                           |      |      |                                                            |

注释：此表是病房与药局之间的摆药申请通知表，病房提出摆药申请时，写入此表，药局接受后删除。

PRIMARY KEY (WARD, DISPENSARY, ITEM_NO, POST_DATE_TIME);

## 预摆药表 DRUG_DISPENSE_PRE

|                          |                          |      |      |                                              |
|--------------------------|--------------------------|------|------|----------------------------------------------|
| 字段中文名               | 字段名                   | 类型 | 长度 | 说明                                         |
| 预摆药批号               | OPER_BATCH_no            | 才   | 20   |                                              |
| 预摆药批内序号           | OPER_item_no             | n    | 5    |                                              |
| 调配药房                 | DISPENSARY               | C    | 8    | 由库存单位字典定义的药房的单位代码           |
| 预摆药日期及时间         | DISPENSING_DATE_TIME_PRE | D    |      |                                              |
| 开单科室                 | ORDERED_BY               | C    | 8    | 下医嘱的科室代码                             |
| 病人标识号               | PATIENT_ID               | C    | 10   |                                              |
| 本次住院标识             | VISIT_ID                 | N    | 2    |                                              |
| 医嘱序号                 | ORDER_NO                 | N    | 4    | 生成本摆药记录的医嘱序号                     |
| 医嘱子序号               | ORDER_SUB_NO             | N    | 2    | 生成本摆药记录的医嘱子序号                   |
| 药品代码                 | DRUG_CODE                | C    | 20   | 根据病房医嘱得到                             |
| 药品规格                 | DRUG_SPEC                | C    | 20   | 由药品字典定义的规格                         |
| 包装规格                 | PACKAGE_SPEC             | C    | 20   | 实际摆药使用的药品规格，是包装规格           |
| 单位                     | DRUG_UNITS               | C    | 8    |                                              |
| 厂家标识                 | FIRM_ID                  | C    | 10   | 反映生产厂家，见药品生产厂家字典             |
| 批号                     | BATCH_NO                 | C    | 16   | 使用“XX/XX/XXXXXX”                           |
| 摆药数量                 | DISPENSE_AMOUNT          | N    | 6,2  | 以上述计量单位计算的数量                     |
| 预摆药人                 | operator                 | C    | 8    | 预摆药人姓名                                 |
| 应收费用                 | COSTS                    | N    | 10,4 | 按标准价格计算得到的费用，由后台划价程序填入 |
| 实收费用                 | CHARGES                  | N    | 10,4 | 考虑费别后应收的费用，由后台划价程序填入     |
| 参与累积剂量             | cumulate_dosage          | n    | 8,4  | 每次摆药时产生                               |
| 累积量单位               | CUMULATE_DOSAGE_UNITS    | c    | 8    |                                              |
| 虚拟药柜累积量           | VCABINET_QUANTITY        | n    | 8,4  |                                              |
| 本次摆药具体日期时间列表 | PREFORM_DATETIME_LIST    | C    | 2000 | 本次摆药具体日期时间列表                     |
| 医嘱的执行时间是否明确   | PREFORM_DATETIME_FLAG    | N    | 1    | 医嘱的执行时间是否明确                       |
| 标志                     | flag                     | c    | 1    | 0-未处理 1-已处理                            |
| 最后一次摆药时间         | last_perform_date_time   | d    |      | 和医嘱表中的一致                             |

主键：预摆药批号, 预摆药批内序号

## 药品摆药分类定义 DRUG_DISPENS_PROPERTY

|              |                     |      |      |                                                                    |
|--------------|---------------------|------|------|--------------------------------------------------------------------|
| 字段中文名称 | 字段名              | 类型 | 长度 | 说明                                                               |
| 调配药房     | DISPENSARY          | C    | 8    | 由库存单位字典定义的药房的单位代码                                 |
| 药品代码     | DRUG_CODE           | C    | 20   | 由药品字典定义的用户定义的代码                                     |
| 摆药类别     | DISPENSING_PROPERTY | C    | 10   | 定义药品摆药时的分类，如：口服、针剂、大输液等，见药品摆药类别字典 |
| 药品规格     | drug_spec           | V    | 20   | 默认的药品剂型\*                                                   |
| 摆药累积     | DISPENSING_cumulate | N    | 1    | 摆药累积属性                                                       |
| 可分割否     | Separable           | N    | 1    | 0-不可分割；1-可以分割                                             |
| 虚拟药柜     | Virtual_cabinet     | N    | 1    | 设置虚拟药柜管理                                                   |

注释：此表反映各药局根据摆药工作的需要对药品的分类。各药局对药品的分类可以不同。

主键：调配药房、药品代码、药品规格。

## 协定处方主表BINDING_PRESC_MASTER(新增)

|              |                       |      |      |      |
|--------------|-----------------------|------|------|------|
| 字段中文名称 | 字段名                | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO             | N    | 4    |      |
| 协定处方号   | PRESC_ID              | N    | 4    |      |
| 协定处方名   | TOPIC                 | C    | 40   |      |
| 处方类型     | PRESC_TYPE            | N    | 1    |      |
| 说明         | USAGE                 | C    | 50   |      |
| 部门代码     | DEPT_CODE             | C    | 8    |      |
| 建立者代码   | CREATOR_ID            | C    | 16   |      |
| 建立日期     | CREATE_DATE_TIME      | D    |      |      |
| 最后修改日期 | LAST_MODIFY_DATE_TIME | D    |      |      |
| 权限         | PERMISSION            | C    | 1    |      |
| 输入码       | INPUT_CODE            | C    | 8    |      |

注释：

主键：PRESC_ID

## 协定处方子表BINDING_PRESC_DETAIL(新增)

|              |                |      |      |      |
|--------------|----------------|------|------|------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明 |
| 协定处方号   | PRESC_ID       | N    | 4    |      |
| 序号         | ITEM_NO        | N    | 3    |      |
| 药品代码     | DRUG_CODE      | C    | 20   |      |
| 药品名称     | DRUG_NAME      | C    | 100  |      |
| 包装规格     | PACKAGE_SPEC   | C    | 20   |      |
| 包装单位     | PACKAGE_UNITS  | C    | 8    |      |
| 厂商         | FIRM_ID        | C    | 10   |      |
| 数量         | QUANTITY       | N    | 6,2  |      |
| 剂量         | DOSAGE         | N    | 8,4  |      |
| 剂量单位     | DOSAGE_UNITS   | C    | 8    |      |
| 途径         | ADMINISTRATION | C    | 16   |      |

注释：

主键：PRESC_ID, ITEM_NO

## 用户与协定处方关系表BINDING_PRESC_SELECTION

|            |           |      |      |      |
|------------|-----------|------|------|------|
| 中文名称   | 字段名    | 类型 | 长度 | 说明 |
| 用户代码   | USER_NAME | C    | 16   |      |
| 协定处方号 | PRESC_ID  | N    | 4    |      |

注释：

主键：USER_NAME, PRESC_ID

## 药品采购记录DRUG_PURCHASE(不使用)

|          |                 |      |      |      |
|----------|-----------------|------|------|------|
| 中文名称 | 字段名          | 类型 | 长度 | 说明 |
|          | STORAGE         | C    | 8    |      |
|          | PLAN_DATE       | D    |      |      |
|          | DRUG_CODE       | C    | 20   |      |
|          | DRUG_SPEC       | C    | 20   |      |
|          | UNITS           | C    | 8    |      |
|          | FIRM_ID         | C    | 10   |      |
|          | PACKAGE_SPEC    | C    | 20   |      |
|          | PACKAGE_UNITS   | C    | 8    |      |
|          | EXPORT_QUANTITY | N    | 12,2 |      |
|          | STOCK_QUANTITY  | N    | 12,2 |      |
|          | PLAN_QUANTITY   | N    | 12,2 |      |
|          | TRADE_PRICE     | N    | 10,4 |      |
|          | SUB_STORAGE     | C    | 8    |      |
|          | LOCATION        | C    | 8    |      |

备注：好象已不用了

## 药品采购计划 DRUG_PURCHASE_PLAN(新增)

|              |                |      |      |                                                  |
|--------------|----------------|------|------|--------------------------------------------------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明                                             |
| 采购计划号   | PLAN_NO        | C    | 6    | 唯一标识一次采购计划，自动生成                   |
| 库存管理单位 | STORAGE        | C    | 8    | 生成该计划的库房代码，见库存单位字典             |
| 项目序号     | ITEM_NO        | N    | 4    | 一次采购计划内的药品项目序号                     |
| 药品代码     | DRUG_CODE      | C    | 10   | 待采购的药品，由药品字典定义的代码               |
| 规格         | DRUG_SPEC      | C    | 20   | 待采购的药品规格，由药品字典定义的规格           |
| 单位         | UNITS          | C    | 8    | 对应剂型及规格，使用规范名称，见4.32计量单位字典 |
| 包装规格     | PACKAGE_SPEC   | C    | 20   | 反映药品含量及包装信息，如0.25g\*30              |
| 包装单位     | PACKAGE_UNITS  | C    | 8    | 对应包装规格的计量单位                           |
| 计划采购数量 | QUANTITY       | N    | 12,2 | 以包装规格及包装单位所计的计划采购数量           |
| 厂家标识     | FIRM_ID        | C    | 10   | 计划采购药品的生产厂家，见药品生产厂家字典       |
| 进货价       | PURCHASE_PRICE | N    | 10,4 | 计划购买价，以包装单位记单价                     |
| 供货商       | SUPPLIER       | C    | 40   | 计划供货商，见供货单位字典                       |
| 生成计划日期 | PLANING_DATE   | D    |      |                                                  |
| 备注         | MEMOS          | C    | 20   |                                                  |

注释：此表记录了药品的采购计划。

主键：采购计划号、项目序号。

## 制剂字典 PREPARATION_DICT

|            |                        |      |      |                                                    |
|------------|------------------------|------|------|----------------------------------------------------|
| 字段中文名 | 字段名                 | 类型 | 长度 | 说明                                               |
| 制剂代码   | PREPARATION_CODE       | C    | 10   | 一种制剂的唯一标识                                 |
| 制剂名称   | PREPARATION_NAME       | C    | 40   | 制剂标准中文名称                                   |
| 拉丁名     | PREPARATION_LATIN_NAME | C    | 40   |                                                    |
| 制剂剂型   | FORM                   | C    | 10   | 使用规范名称，见剂型字典                           |
| 制剂类别   | CLASS                  | C    | 10   | 如：普通制剂、灭菌制剂等，使用规范名称，见         |
| 制剂用法   | ADMINISTRATION         | C    | 10   | 指给药途径，使用规范名称，见用法字典               |
| 作用与用途 | ACTION                 | C    | 100  | 药理作用描述                                       |
| 用法与用量 | USAGE_AND_DOSAGE       | C    | 100  | 用法用量描述                                       |
| 性状       | PROPERTIES             | C    | 200  | 外观性状描述                                       |
| 鉴别方法   | IDENTIFICATION_METHOD  | C    | 400  | 质量鉴别方法描述                                   |
| 储藏       | STORAGE_CONDITION      | C    | 100  | 储藏条件                                           |
| 有效期     | VALID_PERIOD           | N    | 2    | 有效期间                                           |
| 有效期单位 | VALID_PERIOD_UNITS     | C    | 8    |                                                    |
| 标准等级   | PRESC_STANDARD_LEVEL   | C    | 10   | 反映制剂处方的标准审批等级，如：标准制剂、非标制剂 |
| 处方来源   | PRESC_CRITERION        | C    | 60   | 记录处方出处                                       |

注释：此表定义了系统管理的制剂范围。

主键：制剂代码。

## 制剂配制规范 PREPARATION_OPERATING_RULE

|            |                  |      |      |                    |
|------------|------------------|------|------|--------------------|
| 字段中文名 | 字段名           | 类型 | 长度 | 说明               |
| 制剂代码   | PREPARATION_CODE | C    | 10   | 一种制剂的唯一标识 |
| 制剂规格   | PREPARATION_SPEC | C    | 20   | 反映制剂的含量信息 |
| 制剂单位   | UNITS            | C    | 8    | 对应规格的包装单位 |
| 含量标准   | CONTENT          | C    | 200  | 含量描述           |
| 处方全量   | PRESC_AMOUNT     | N    | 6,2  | 一个配置单位数量   |
| 全量单位   | PRESC_UNITS      | C    | 10   |                    |
| 制备方法   | MAKING_METHOD    | C    | 400  | 方法描述           |
| 备注       | MEMO             | C    | 40   |                    |
| 录入者     | ENTERED_BY       | C    | 8    |                    |
| 录入日期   | ENTER_DATE       | D    |      |                    |

注释：此表定义制剂的配置规范信息，与制剂处方表一起构成一种规格制剂的配置规范。

主键：制剂代码、制剂规格。

## 制剂处方 PREPARATION_PRESC

|            |                   |      |      |                                          |
|------------|-------------------|------|------|------------------------------------------|
| 字段中文名 | 字段名            | 类型 | 长度 | 说明                                     |
| 制剂代码   | PREPARATION_CODE  | C    | 10   | 一种制剂的唯一标识                       |
| 制剂规格   | PREPARATION_SPEC  | C    | 20   | 反映制剂的含量信息                       |
| 原料序号   | RAW_MATERIAL_NO   | N    | 2    | 处方中原料的排列顺序                     |
| 原料代码   | RAW_MATERIAL_CODE | C    | 10   |                                          |
| 原料名称   | RAW_MATERIAL_NAME | C    | 40   |                                          |
| 原料数量   | AMOUNT            | N    | 6,2  | 制剂配制规范中指定的制剂全量所需原料数量 |
| 单位       | UNITS             | C    | 8    |                                          |

注释：此表定义制剂所需各种原料配方信息，与制剂配制规范表一起构成一种规格制剂的配置规范。

主键：制剂代码、制剂规格、原料代码。

## 制剂成本 PREPARATION_COST

|              |                  |      |      |                                      |
|--------------|------------------|------|------|--------------------------------------|
| 字段中文名   | 字段名           | 类型 | 长度 | 说明                                 |
| 制剂代码     | PREPARATION_CODE | C    | 10   | 一种制剂的唯一标识                   |
| 制剂规格     | PREPARATION_SPEC | C    | 20   | 反映制剂的含量信息                   |
| 成本项目序号 | ITEM_NO          | N    | 2    |                                      |
| 成本项目名称 | COST_ITEM        | C    | 40   |                                      |
| 成本项目规格 | ITEM_SPEC        | C    | 20   |                                      |
| 成本项目单位 | UNITS            | C    | 8    |                                      |
| 成本项目单价 | PRICE            | N    | 8,2  |                                      |
| 成本项目数量 | QUANTITY         | N    | 8,2  | 按制剂规范定义的全量所需成本项目数量 |
| 成本类别     | COST_CLASS       | C    | 10   | 反映成本内容，如：原料、人工等       |

注释：此表记录按制剂规范生产全量所涉及的所有成本项目及数量，用于制剂定价。

主键：制剂代码、制剂规格、成本项目序号。

## 制剂配制记录 PREPARATION_MASTER

|              |                   |      |      |                    |
|--------------|-------------------|------|------|--------------------|
| 字段中文名   | 字段名            | 类型 | 长度 | 说明               |
| 制剂代码     | PREPARATION_CODE  | C    | 10   | 一种制剂的唯一标识 |
| 制剂规格     | PREPARATION_SPEC  | C    | 20   | 反映制剂的含量信息 |
| 生产批号     | BATCH_NO          | C    | 16   |                    |
| 配制日期     | PREPARATION_DATE  | D    |      |                    |
| 计划生产数量 | PLANED_QUANTITY   | N    | 8,2  |                    |
| 实际生产数量 | FINISHED_QUANTITY | N    | 8,2  |                    |
| 配制人       | OPERATOR          | C    | 8    |                    |
| 复核人       | CHECKER           | C    | 8    |                    |
| 备注         | MEMO              | C    | 40   |                    |
| 录入者       | ENTERED_BY        | C    | 8    | 录入者姓名         |
| 录入日期     | ENTER_DATE        | D    |      |                    |

注释：此表是制剂配制情况的主记录，与制剂配制投料表与制剂配制操作记录一起构成了每批制剂的配置生产记录。

主键：制剂代码、制剂规格、生产批号。

## 制剂配制投料记录 PREPARATION_RAW_MATERIAL

|            |                   |      |      |                      |
|------------|-------------------|------|------|----------------------|
| 字段中文名 | 字段名            | 类型 | 长度 | 说明                 |
| 制剂代码   | PREPARATION_CODE  | C    | 10   | 一种制剂的唯一标识   |
| 制剂规格   | PREPARATION_SPEC  | C    | 20   | 反映制剂的含量信息   |
| 生产批号   | BATCH_NO          | C    | 16   |                      |
| 原料序号   | RAW_MATERIAL_NO   | N    | 2    | 处方中原料的排列顺序 |
| 原料代码   | RAW_MATERIAL_CODE | C    | 10   |                      |
| 原料名称   | RAW_MATERIAL_NAME | C    | 40   |                      |
| 原料数量   | AMOUNT            | N    | 8,2  |                      |
| 单位       | UNITS             | C    | 8    |                      |

注释：此表记录每批次制剂实际投料情况。

主键：制剂代码、制剂规格、生产批号、原料代码。

## 制剂配制问题记录 PREPARATION_PROBLEM

|            |                  |      |      |                          |
|------------|------------------|------|------|--------------------------|
| 字段中文名 | 字段名           | 类型 | 长度 | 说明                     |
| 制剂代码   | PREPARATION_CODE | C    | 10   | 一种制剂的唯一标识       |
| 制剂规格   | PREPARATION_SPEC | C    | 20   | 反映制剂的含量信息       |
| 生产批号   | BATCH_NO         | C    | 16   |                          |
| 问题序号   | PROBLEM_NO       | N    | 2    | 一个批次内发生的问题顺序 |
| 发生问题   | PROBLEM          | C    | 40   | 问题描述                 |
| 变化情况   | PROCESS          | C    | 100  | 问题的变化过程           |
| 处理结果   | RESULT           | C    | 100  |                          |
| 录入者     | ENTERED_BY       | C    | 8    |                          |
| 录入时间   | ENTER_DATE       | D    |      |                          |

注释：此表记录制剂配制过程中发生的问题及处理情况。

主键：制剂代码、制剂规格、生产批号、问题序号。

## 制剂检验记录 PREPARATION_TEST

|              |                  |      |      |                    |
|--------------|------------------|------|------|--------------------|
| 字段中文名   | 字段名           | 类型 | 长度 | 说明               |
| 制剂代码     | PREPARATION_CODE | C    | 10   | 一种制剂的唯一标识 |
| 制剂规格     | PREPARATION_SPEC | C    | 20   | 反映制剂的含量信息 |
| 生产批号     | BATCH_NO         | C    | 16   |                    |
| 组号         | GROUP_NO         | N    | 1    |                    |
| 检验报告号码 | TEST_REPORT_NO   | C    | 16   |                    |
| 检验结果     | TEST_RESULT      | C    | 8    |                    |
| 检验单位     | TEST_DEPT        | C    | 40   |                    |

注释：此表记录每批次中每组制剂的检验结果。

主键：制剂代码、制剂规格、生产批号、组号。

## 制剂价表 PREPARATION_PRICE_LIST

|            |                  |      |      |                    |
|------------|------------------|------|------|--------------------|
| 字段中文名 | 字段名           | 类型 | 长度 | 说明               |
| 制剂代码   | PREPARATION_CODE | C    | 10   | 一种制剂的唯一标识 |
| 制剂规格   | PREPARATION_SPEC | C    | 20   | 反映制剂的含量信息 |
| 单位       | UNITS            | C    | 8    | 每包装单位         |
| 批发价     | WHOLE_SALE_PRICE | N    | 10,4 |                    |
| 零售价     | RETAIL_PRICE     | N    | 10,4 |                    |
| 起用日期   | START_DATE       | D    |      |                    |
| 停止日期   | STOP_DATE        | D    |      |                    |

注释：此表定义每一品种制剂价格，其中包含了历史价格，同一制剂当前只能有一种有效价格。

主键：制剂代码、制剂规格、起用日期。

## 制剂原料字典 RAW_MATERIAL_DICT(新增)

|              |               |      |      |                    |
|--------------|---------------|------|------|--------------------|
| 字段中文名   | 字段名        | 类型 | 长度 | 说明               |
| 原料项目代码 | MATERIAL_CODE | C    | 10   | 原料项目的唯一标识 |
| 原料项目名称 | MATERIAL_NAME | C    | 40   |                    |
| 原料项目规格 | MATERIAL_SPEC | C    | 20   |                    |
| 单位         | UNITS         | C    | 8    | 对应规格的计量单位 |
| 输入码       | INPUT_CODE    | C    | 8    |                    |
|              | INPUT_CODE_WB | C    | 8    |                    |

注释：此表定义制剂所涉及的原料，用户定义。

主键：原料项目代码、原料项目规格。

## 包装材料字典 PACKAGE_MATERIAL_DICT(新增)

|              |               |      |      |                    |
|--------------|---------------|------|------|--------------------|
| 字段中文名   | 字段名        | 类型 | 长度 | 说明               |
| 材料项目代码 | MATERIAL_CODE | C    | 10   | 原料项目的唯一标识 |
| 材料项目名称 | MATERIAL_NAME | C    | 40   |                    |
| 材料项目规格 | MATERIAL_SPEC | C    | 20   |                    |
| 单位         | UNITS         | C    | 8    | 对应规格的计量单位 |
| 输入码       | INPUT_CODE    | C    | 8    |                    |
|              | INPUT_CODE_WB | C    | 8    |                    |

注释：此表定义制剂所涉及的包装材料，用户定义。

主键：包装材料项目代码、包装材料项目规格。

## 制剂处方等级字典 PRESC_STANDARD_DICT(新增)

|              |               |      |      |      |
|--------------|---------------|------|------|------|
| 字段中文名   | 字段名        | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO     | N    | 2    |      |
| 处方标准代码 | STANDARD_CODE | C    | 1    |      |
| 处方标准名称 | STANDARD_NAME | C    | 10   |      |
| 输入码       | INPUT_CODE    | C    | 8    |      |

注释：此表定义制剂处方的标准等级，用户定义。

主键：处方标准代码。

## 制剂类别等级字典 PRESC_CLASS_DICT(新增)

|              |            |      |      |      |
|--------------|------------|------|------|------|
| 字段中文名   | 字段名     | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO  | N    | 2    |      |
| 制剂类别代码 | CLASS_CODE | C    | 1    |      |
| 制剂类别名称 | CLASS_NAME | C    | 10   |      |
| 输入码       | INPUT_CODE | C    | 8    |      |

注释：此表定义制剂类别，如：普通制剂、灭菌制剂、生物制剂、中药制剂等，用户定义。

主键：制剂类别代码。

## 制剂用法字典 PREPARATION_ADMIN_DICT

|              |                     |      |      |      |
|--------------|---------------------|------|------|------|
| 字段中文名   | 字段名              | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO           | N    | 2    |      |
| 制剂用法代码 | ADMINISTRATION_CODE | C    | 1    |      |
| 制剂用法名称 | ADMINISTRATION_NAME | C    | 10   |      |
| 输入码       | INPUT_CODE          | C    | 8    |      |

注释：此表定义制剂用法，如：内服制剂、外用制剂等，用户定义。

主键：制剂用法代码。

## 制剂成本类别字典 PREPARATION_COST_CLASS_DICT

|              |                 |      |      |      |
|--------------|-----------------|------|------|------|
| 字段中文名   | 字段名          | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO       | N    | 2    |      |
| 成本类别代码 | COST_CLASS_CODE | C    | 1    |      |
| 成本类别名称 | COST_CLASS_NAME | C    | 10   |      |
| 输入码       | INPUT_CODE      | C    | 8    |      |

注释：此表定义制剂成本类别，如：原辅料、包装物等，用户定义。

主键：成本类别代码。

## 制剂成本项目字典 PREPARATION_COST_ITEM_DICT

|              |                 |      |      |                        |
|--------------|-----------------|------|------|------------------------|
| 字段中文名   | 字段名          | 类型 | 长度 | 说明                   |
| 序号         | SERIAL_NO       | N    | 2    |                        |
| 成本项目名称 | COST_ITEM_NAME  | C    | 40   |                        |
| 成本项目类别 | COST_ITEM_CLASS | C    | 10   | 成本项目对应的成本类别 |
| 输入码       | INPUT_CODE      | C    | 8    |                        |

注释：此表定义了所有参与制剂成本的项目，用户定义。

主键：成本项目名称。

## 制剂室配置表 PREPARATION_DEPT_DESC

|              |                    |      |      |                                  |
|--------------|--------------------|------|------|----------------------------------|
| 字段中文名   | 字段名             | 类型 | 长度 | 说明                             |
| 科室代码     | DEPT_CODE          | C    | 8    | 见科室字典定义的科室代码         |
| 科室名称     | DEPT_NAME          | C    | 40   |                                  |
| 负责人       | LEADER             | C    | 8    | 负责人姓名                       |
| 制剂定价公式 | PRICE_CALC_FUMULAR | C    | 100  | 按成本定价公式                   |
| 批零差率%    | RETAIL_PRICE_RATE  | N    | 2    | 零售价在批发价基础上的加价率     |
| 月结点       | ACCOUNTING_POINT   | N    | 2    | 月结区间从上月的该日到本月的该日 |

注释：此表是制剂系统的配置表，只包含一条记录。

主键：科室代码。

# 门诊收费

## 门诊医疗收据记录 OUTP_RCPT_MASTER

|               |                     |      |      |                                                  |     |
|---------------|---------------------|------|------|--------------------------------------------------|-----|
| 字段中文名称  | 字段名              | 类型 | 长度 | 说明                                             |     |
| 收据号        | RCPT_NO             | C    | 20   | 收据的唯一标识，由门诊收费子系统内部分配         |     |
| 病人标识号    | PATIENT_ID          | C    | 10   | 对有主索引记录的病人使用                         |     |
| 姓名          | NAME                | C    | 20   |                                                  |     |
| 姓名拼音      | NAME_PHONETIC       | C    | 16   | 病人姓名拼音，大写，字间用一个空格分隔，超长截断 |     |
| 身份          | IDENTITY            | C    | 10   | 使用规范名称，由用户定义，见1.6身份字典          |     |
| 费别          | CHARGE_TYPE         | C    | 8    | 使用规范名称，由用户定义，见1.9费别字典          |     |
| 合同单位      | UNIT_IN_CONTRACT    | C    | 11   | 合同单位代码，见2.4合同单位字典                  |     |
| 就诊日期      | VISIT_DATE          | D    |      |                                                  |     |
| 总费用        | TOTAL_COSTS         | N    | 8,2  | 按标准价格计算得到的费用                         |     |
| 应收费        | TOTAL_CHARGES       | N    | 8,2  | 考虑费别因素后，实际应收费用                     |     |
| 收款员        | OPERATOR_NO         | C    | 4    | 收款员号                                         |     |
| 交费标志      | CHARGE_INDICATOR    | N    | 1    | 0-正常交费1-欠费 2-已退费                        |     |
| 退费收据号    | REFUNDED_RCPT_NO    | C    | 20   | 如果此记录为退费记录，则本字段为所退的收据号     |     |
| 结帐序号      | ACCT_NO             | C    | 6    | 为包含本收据的收款员结帐号                       |     |
| 打印操作员    | PRINTED_OPERATOR_NO | C    | 4    |                                                  |     |
| 打印日期      | PRINTED_DATE        | D    |      |                                                  |     |
| 刷卡标志      | CARD_FLAG           | C    | 1    |                                                  |     |
| 打印收据号码  | PRINTED_RCPT_NO     | C    | 20   |                                                  |     |
| 交费/挂号标志 | FLAG                | C    | 4    |                                                  |     |
| 发票印刷号码  | INVOICE_NO          | C    | 20   | 使用发票管理时，记录打印的发票的印刷号码         |     |

注释：此表用于描述门诊病人医疗费用。欠费、退费记录及公免费病人费用记录也作为一张收据记入此表中。此表由门诊收费子系统使用。数据增长量略大于门诊人次。如果日门诊量为1,000人次，则每月增加3万条记录以上。本表数据保留的时间应考虑退费和查询收据的需要，一般在3个月以上。

主键：收据号。

## 门诊病人支付方式记录 OUTP_PAYMENTS_MONEY

|              |                 |      |      |                                                                |
|--------------|-----------------|------|------|----------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                           |
| 收据号       | RCPT_NO         | C    | 20   | 标识一次付费                                                   |
| 金额类型     | MONEY_TYPE      | C    | 20   | 标识付费方法，如：现金、支票、医保等，见支付方式字典           |
| 支付序号     | PAYMENT_NO      | N    | 2    | 反映各种金额类型的支付顺序                                     |
| 数额         | PAYMENT_AMOUNT  | N    | 8,2  |                                                                |
| 退数额       | REFUNDED_AMOUNT | N    | 8,2  | 如：支票方式支付，支票方式退余额。支付数额减退数额即为实付数额 |
| 预交金号     | prepay_no       | c    | 10   |                                                                |

注释：此表对病人付费的方法和数量进行详细描述。一次就诊付费可以使用多种付费方法。

主键：收据号、金额类型。

## 开单记录 OUTP_ORDER_DESC

|                |                   |      |      |                                                                                                                                                                  |
|----------------|-------------------|------|------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 字段中文名称   | 字段名            | 类型 | 长度 | 说明                                                                                                                                                             |
| 就诊日期       | VISIT_DATE        | D    |      |                                                                                                                                                                  |
| 就诊序号       | VISIT_NO          | N    | 5    | 该序号与就诊日期一起构成一次就诊的唯一标识。当收费项目由收费处录入时，该序号内部自动生成；当收费程序与挂号程序或由药局录入项目或分散划价时，从其他系统复制而来。 |
| 病人标识号     | PATIENT_ID        | C    | 10   | 对有主索引记录的病人使用                                                                                                                                         |
| 药品处方标志   | PRESC_INDICATOR   | N    | 1    | 0-该单不含药品，1-该单含西药处方，2-该单含中药处方                                                                                                               |
| 开单科室       | ORDERED_BY_DEPT   | C    | 8    | 使用代码，由用户定义，见2.6科室字典。非空                                                                                                                        |
| 开单医生       | ORDERED_BY_DOCTOR | C    | 8    |                                                                                                                                                                  |
| 收据号         | RCPT_NO           | C    | 20   | 该开单记录包含的收费项目所对应的收据号                                                                                                                           |
|                | VISIT_ID          | N    | 4    | 该字段没有用到                                                                                                                                                   |
| 打印收据号     | PRINTED_RCPT_NO   | C    | 20   |                                                                                                                                                                  |
| 医生核算组代码 | ORDER_GROUP       | c    | 8    | 便于按核算组进行费用统计                                                                                                                                         |
| 门诊号         | Clinic_no         | V2   | 13   |                                                                                                                                                                  |

注释：此表描述门诊病人一次就诊开单情况，即从同一个医生一次开单记录。该信息用于科室核算，是门诊费用项目的主记录。多次开单记录可以对应到一个收据记录。当收费项目由门诊收费录入时，该记录在录入划价过程中生成；当采用分散划价模式或使用门诊医生工作站时，该记录在诊室或执行科室生成，由门诊收费使用。当门诊收费按处方录入时，也可以每张物理的处方对应一个开单记录。

数据增长量与门诊人次基本相同。如果日门诊量为1,000人次，则每月增加3万条记录。

主键：就诊日期、就诊序号。

## 门诊病人诊疗费用项目 OUTP_BILL_ITEMS

|              |                    |      |      |                                                                      |
|--------------|--------------------|------|------|----------------------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                                                 |
| 就诊日期     | VISIT_DATE         | D    |      | 与就诊号一起构成一次就诊标识                                         |
| 就诊序号     | VISIT_NO           | N    | 5    |                                                                      |
| 收据号       | RCPT_NO            | C    | 20   | 可选，由收费系统填入                                                 |
| 序号         | ITEM_NO            | N    | 2    | 按就诊日期及就诊号分组排序                                           |
| 价表项目分类 | ITEM_CLASS         | C    | 1    | 该项目对应价表的分类，使用代码，由本系统定义，见6.10价表项目分类字典 |
| 收据项目分类 | CLASS_ON_RCPT      | C    | 1    | 该收费项目所属收据项目分类代码，用户定义，见6.12门诊收据费用分类字典 |
| 项目代码     | ITEM_CODE          | C    | 20   | 用户定义，见6.1价表                                                  |
| 项目名称     | ITEM_NAME          | C    | 100  | 防止项目代码变化而保留                                               |
| 项目规格     | ITEM_SPEC          | C    | 50   | 可为材料的规格或项目的定价条件                                       |
| 数量         | AMOUNT             | N    | 6,2  | 当为检查检验项目时，一般为1，当为材料等项目时，可大于1。             |
| 单位         | UNITS              | C    | 8    | 为项目的计量单位，如人次                                             |
| 执行科室     | PERFORMED_BY       | C    | 8    | 科室代码，用户定义，见2.6科室字典                                    |
| 费用         | COSTS              | N    | 8,2  | 按价表计算得到的费用                                                 |
| 应付费用     | CHARGES            | N    | 8,2  | 考虑费别等因素后的实际应支付费用                                     |
| 确定操作员   | CONFIRMED_OPERATOR | C    | 8    |                                                                      |
| 确定时间     | CONFIRMED_DATETIME | D    |      |                                                                      |
| 发票号码     | INVOICE_NO         | C    | 20   |                                                                      |
| 标志         | FLAG               | N    | 8    |                                                                      |
| 付数         | REPETITION         | N    | 2    |                                                                      |
| 核算科目     | CLASS_ON_RECKONING | C    | 10   |                                                                      |
| 会计科目     | SUBJ_CODE          | C    | 3    |                                                                      |
| 优惠比率     | PRICE_QUOTIETY     | N    | 7,4  |                                                                      |
| 单价         | ITEM_PRICE         | N    | 10,4 |                                                                      |
| 处方组号     | ORDER_NO           | N    | 2    |                                                                      |
| 处方子组号   | SUB_ORDER_NO       | N    | 2    |                                                                      |
| 打印收据号   | PRINTED_RCPT_NO    | C    | 20   |                                                                      |
| 出库单号     | Document_no        | V2   | 10   |                                                                      |

注释：本表为门诊病人费用的明细记录。每次就诊约产生3项费用。

主键：就诊日期、就诊序号、序号。

## 门诊收费结帐主记录 OUTP_ACCT_MASTER

|              |                    |      |      |                                                          |
|--------------|--------------------|------|------|----------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                                     |
| 结帐序号     | ACCT_NO            | C    | 6    | 每次收款员结帐的唯一标识                                 |
| 收款员号     | OPERATOR_NO        | C    | 4    |                                                          |
| 结帐日期     | ACCT_DATE          | D    |      | 非空                                                     |
| 最小收据序号 | MIN_RCPT_NO        | C    | 20   | 一般情况下此次结帐涉及的收据的序号是连续的，此处为最小号 |
| 最大收据序号 | MAX_RCPT_NO        | C    | 20   | 此处为收据的最大号                                       |
| 收据张数     | RCPTS_NUM          | N    | 4    | 含退费收据，不含免费人次数                               |
| 免费人次     | FREE_OF_CHARGE_NUM | N    | 4    | 实付费用为0的人次数                                      |
| 退费收据张数 | REFUND_NUM         | N    | 4    |                                                          |
| 退费金额     | REFUND_AMOUNT      | N    | 10,2 |                                                          |
| 总费用       | TOTAL_COSTS        | N    | 10,2 | 按标准价格计算得到的累计费用                             |
| 总收入       | TOTAL_INCOMES      | N    | 10,2 | 实收费用累计                                             |
| 记帐日期     | TALLY_DATE         | D    |      | 记入会计帐目中的日期                                     |

注释：此表记录门诊收款员结帐情况，是收款员向会计交帐的凭证。每次结帐生成一条记录。如果每天有10个收款员工作，则一般有10条左右记录生成。每月的数据增长量约为3,000条。

主键：结帐序号。

## 门诊收费结帐明细记录 OUTP_ACCT_DETAIL

|              |                 |      |      |                                                                  |
|--------------|-----------------|------|------|------------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                             |
| 结帐序号     | ACCT_NO         | C    | 6    | 门诊医疗收据结帐主记录中对应的结帐序号                           |
| 费用帐目分类 | TALLY_FEE_CLASS | C    | 4    | 会计帐目中规定的费用分类，使用代码，用户定义，见6.13会计科目字典 |
| 费用         | COSTS           | N    | 10,2 | 按标准价格计算得到的累计费用                                     |
| 收入         | INCOME          | N    | 10,2 | 该项费用的合计收入                                               |

注释：此表为门诊医疗收据结帐的明细项目。每次结帐生成的记录数约为费用分类数。若分8类，则每月数据增长量约为24,000条。

主键：结帐序号、费用帐目分类。

## 门诊收费结帐金额分类 OUTP_ACCT_MONEY

|              |                 |      |      |                                                                |
|--------------|-----------------|------|------|----------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                           |
| 结帐序号     | ACCT_NO         | C    | 6    | 标识一次结帐                                                   |
| 金额类别     | MONEY_TYPE      | C    | 8    | 标识收入金额种类，如：现金、支票、医保等，见支付方式字典       |
| 数额         | INCOME_AMOUNT   | N    | 10,2 |                                                                |
| 退数额       | REFUNDED_AMOUNT | N    | 10,2 | 如：支票方式支付，支票方式退余额。支付数额减退数额即为实收数额 |

注释：此表对门诊收费结帐的金额种类进行描述。

主键：结帐序号、金额类别。

## 门诊医疗收据记录备份 OUTP_RCPT_MASTER_BACK

|            |                     |      |      |      |
|------------|---------------------|------|------|------|
| 字段中文名 | 字段名              | 类型 | 长度 | 说明 |
|            | RCPT_NO             | C    | 20   |      |
|            | PATIENT_ID          | C    | 10   |      |
|            | NAME                | C    | 20   |      |
|            | NAME_PHONETIC       | C    | 16   |      |
|            | IDENTITY            | C    | 10   |      |
|            | CHARGE_TYPE         | C    | 8    |      |
|            | UNIT_IN_CONTRACT    | C    | 11   |      |
|            | VISIT_DATE          | D    |      |      |
|            | TOTAL_COSTS         | N    | 8,2  |      |
|            | TOTAL_CHARGES       | N    | 8,2  |      |
|            | OPERATOR_NO         | C    | 4    |      |
|            | CHARGE_INDICATOR    | N    | 1    |      |
|            | REFUNDED_RCPT_NO    | C    | 20   |      |
|            | ACCT_NO             | C    | 6    |      |
|            | PRINTED_OPERATOR_NO | C    | 4    |      |
|            | PRINTED_DATE        | D    |      |      |
|            | CARD_FLAG           | C    | 1    |      |
|            | PRINTED_RCPT_NO     |      |      |      |
|            | FLAG                | C    | 4    |      |
|            | INVOICE_NO          | C    | 20   |      |

结构同门诊医疗收据记录（OUTP_RCPT_MASTER），用于该表数据备份时临时存放被备份的数据。

## 开单记录备份 OUTP_ORDER_DESC_BACK

|            |                   |      |      |      |
|------------|-------------------|------|------|------|
| 字段中文名 | 字段名            | 类型 | 长度 | 说明 |
|            | VISIT_DATE        | D    |      |      |
|            | VISIT_NO          | N    | 5    |      |
|            | PATIENT_ID        | C    | 10   |      |
|            | ORDERED_BY_DEPT   | C    | 8    |      |
|            | ORDERED_BY_DOCTOR | C    | 8    |      |
|            | RCPT_NO           | C    | 20   |      |

结构同开单记录（OUTP_ORDER_DESC），用于该表数据备份时临时存放被备份的数据。

## 门诊病人诊疗费用项目备份 OUTP_BILL_ITEMS_BACK

|            |                 |      |      |      |
|------------|-----------------|------|------|------|
| 字段中文名 | 字段名          | 类型 | 长度 | 说明 |
|            | VISIT_DATE      | D    |      |      |
|            | VISIT_NO        | N    | 5    |      |
|            | RCPT_NO         | C    | 20   |      |
|            | ITEM_NO         | N    | 2    |      |
|            | ITEM_CLASS      | C    | 1    |      |
|            | CLASS_ON_RCPT   | C    | 1    |      |
|            | ITEM_CODE       | C    | 10   |      |
|            | ITEM_NAME       | C    | 40   |      |
|            | ITEM_SPEC       | C    | 20   |      |
|            | AMOUNT          | N    | 6,2  |      |
|            | UNITS           | C    | 8    |      |
|            | PERFORMED_BY    | C    | 8    |      |
|            | COSTS           | N    | 8,2  |      |
|            | CHARGES         | N    | 8,2  |      |
|            | INVOICE_NO      | C    | 20   |      |
|            | FLAG            | N    | 8    |      |
|            | REPETITION      | N    | 2    |      |
|            | ORDER_NO        | N    | 2    |      |
|            | SUB_ORDER_NO    | N    | 2    |      |
|            | PRINTED_RCPT_NO | C    | 20   |      |

结构同门诊病人诊疗费用项目（OUTP_BILL_ITEMS），用于该表数据备份时临时存放被备份的数据。

## 门诊病人支付方式记录备份 OUTP_PAYMENTS_MONEY_BACK

|            |                 |      |      |      |
|------------|-----------------|------|------|------|
| 字段中文名 | 字段名          | 类型 | 长度 | 说明 |
|            | RCPT_NO         | C    | 20   |      |
|            | PAYMENT_NO      | N    | 2    |      |
|            | MONEY_TYPE      | C    | 8    |      |
|            | PAYMENT_AMOUNT  | N    | 8,2  |      |
|            | REFUNDED_AMOUNT | N    | 8,2  |      |

结构同门诊病人支付方式记录（OUTP_PAYMENTS_MONEY_BACK），用于该表数据备份时临时存放被备份的数据。

## CHARGE_REDUCE_MASTER(不使用)

该表一直没有用到

|            |                 |      |      |      |
|------------|-----------------|------|------|------|
| 字段中文名 | 字段名          | 类型 | 长度 | 说明 |
|            | SERIAL_NO       | N    | 5    |      |
|            | RCPT_NO         | C    | 8    |      |
|            | PATIENT_ID      | C    | 2    |      |
|            | VISIT_ID        | N    | 2    |      |
|            | NAME            | C    | 20   |      |
|            | CHARGE_TYPE     | C    | 8    |      |
|            | UNIT            | C    | 40   |      |
|            | CARD_NO         | C    | 18   |      |
|            | REDUCE_AMOUNT   | N    | 8,2  |      |
|            | REDUCE_CAUSE    | C    | 40   |      |
|            | RATIFIER        | C    | 8    |      |
|            | UNDERTAKER      | C    | 8    |      |
|            | UNDERTAKER_UNIT | C    | 40   |      |
|            | OPER_NO         | C    | 4    |      |
|            | OPER_NAME       | C    | 8    |      |
|            | OPER_DATE_TIME  | D    |      |      |

## CHARGE_REDUCE_DETAIL(不使用)

该表一直没有用到

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
|          | SERIAL_NO     | N    | 5    |      |
|          | RCPT_NO       | C    | 8    |      |
|          | ITEM_NO       | N    | 6    |      |
|          | REDUCE_AMOUNT | N    | 8,2  |      |

## OPERATOR_CHECK_USE(不使用)

该表一直没有用到

|          |                  |      |      |      |
|----------|------------------|------|------|------|
| 中文名称 | 字段名           | 类型 | 长度 | 说明 |
|          | OPERATOR_NO      | C    | 8    |      |
|          | CHECK_START      | N    | 8    |      |
|          | CURRENT_CHECK_NO | N    | 8    |      |
|          | CHECK_END        | N    | 8    |      |
|          | START_DATE_TIME  | D    |      |      |
|          | END_DATE_TIME    | D    |      |      |

## 门诊病人诊疗费用项目预存OUTP_BILL_ITEMS_TEMP

|            |                    |      |      |      |
|------------|--------------------|------|------|------|
| 字段中文名 | 字段名             | 类型 | 长度 | 说明 |
|            | VISIT_DATE         | D    |      |      |
|            | VISIT_NO           | N    | 5    |      |
|            | RCPT_NO            | C    | 20   |      |
|            | ITEM_NO            | N    | 2    |      |
|            | ITEM_CLASS         | C    | 1    |      |
|            | CLASS_ON_RCPT      | C    | 1    |      |
|            | ITEM_CODE          | C    | 10   |      |
|            | ITEM_NAME          | C    | 40   |      |
|            | ITEM_SPEC          | C    | 20   |      |
|            | AMOUNT             | N    | 6,2  |      |
|            | UNITS              | C    | 8    |      |
|            | PERFORMED_BY       | C    | 8    |      |
|            | COSTS              | N    | 8,2  |      |
|            | CHARGES            | N    | 8,2  |      |
|            | REPETITION         | N    | 2    |      |
|            | CLASS_ON_RECKONING | C    | 10   |      |
|            | SUBJ_CODE          | C    | 3    |      |
|            | PRICE_QUOTIETY     | N    | 7,4  |      |
|            | ITEM_PRICE         | N    | 10,4 |      |

结构同门诊病人诊疗费用项目（OUTP_BILL_ITEMS）

## 开单记录预存OUTP_ORDER_DESC_TEMP

|          |                   |      |      |      |
|----------|-------------------|------|------|------|
| 中文名称 | 字段名            | 类型 | 长度 | 说明 |
|          | VISIT_DATE        | D    |      |      |
|          | VISIT_NO          | N    | 5    |      |
|          | PATIENT_ID        | C    | 10   |      |
|          | PRESC_INDICATOR   | N    | 1    |      |
|          | ORDERED_BY_DEPT   | C    | 8    |      |
|          | ORDERED_BY_DOCTOR | C    | 8    |      |
|          | VISIT_DATE_OLD    | D    |      |      |
|          | VISIT_NO_OLD      | N    | 5    |      |
|          | NAME              | C    | 20   |      |
|          | CHARGE_TYPE       | C    | 8    |      |
|          | CHARGE_INDICATOR  | N    | 1    |      |
|          | RCPT_NO           | C    | 20   |      |
|          | Clinic_no         | v    | 13   |      |

结构同开单记录（OUTP_ORDER_DESC）类似

## 发票作废记录OUTP_REFUND_INVOICE

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
| 作废日期 | REFUND_DATE   | D    |      |      |
| 标志     | FLAG          | C    | 1    |      |
| 操作员   | OPERATOR_NO   | C    | 4    |      |
| 发票号码 | INVOICE_NO    | C    | 20   |      |
| 发票标志 | INVOICE_FLAG  | C    | 1    |      |
| 备注     | REFUND_REMARK | C    | 50   |      |

主键：作废日期，发票号码

## RCPT_VS_CHECK(不使用)

该表一直没有用到

|          |              |      |      |      |
|----------|--------------|------|------|------|
| 中文名称 | 字段名       | 类型 | 长度 | 说明 |
|          | SERIAL_NO    | N    | 1    |      |
|          | RCPT_NO      | C    | 8    |      |
|          | CHECK_NO     | N    | 8    |      |
|          | AMOUNT       | N    | 8,2  |      |
|          | CHECK_OPER   | C    | 8    |      |
|          | IO_INDICATOR | C    | 1    |      |
|          | ACCT_NO      | C    | 6    |      |
|          | RECK_NUM     | N    | 2    |      |
|          | VISIT_DATE   | D    |      |      |

#  住院病人收费

## 住院病人费用明细记录 INP_BILL_DETAIL

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 31%" />
<col style="width: 7%" />
<col style="width: 7%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>病人标识</td>
<td>PATIENT_ID</td>
<td>C</td>
<td>10</td>
<td>非空</td>
</tr>
<tr class="odd">
<td>病人本次住院标识</td>
<td>VISIT_ID</td>
<td>N</td>
<td>2</td>
<td>非空</td>
</tr>
<tr class="even">
<td>费用项目序号</td>
<td>ITEM_NO</td>
<td>N</td>
<td>6</td>
<td>一个病人的费用项目的唯一标识</td>
</tr>
<tr class="odd">
<td>项目类别</td>
<td>ITEM_CLASS</td>
<td>C</td>
<td>1</td>
<td>按价表项目分类，使用代码，见6.10价表项目分类字典。非空</td>
</tr>
<tr class="even">
<td>项目名称</td>
<td>ITEM_NAME</td>
<td>C</td>
<td>100</td>
<td>项目的正文描述</td>
</tr>
<tr class="odd">
<td>项目代码</td>
<td>ITEM_CODE</td>
<td>C</td>
<td>20</td>
<td>非空</td>
</tr>
<tr class="even">
<td>项目规格</td>
<td>ITEM_SPEC</td>
<td>C</td>
<td>50</td>
<td>指药品的规格或材料的规格。</td>
</tr>
<tr class="odd">
<td>数量</td>
<td>AMOUNT</td>
<td>N</td>
<td>6,2</td>
<td></td>
</tr>
<tr class="even">
<td>单位</td>
<td>UNITS</td>
<td>C</td>
<td>8</td>
<td>如片、瓶、人次等，本系统定义，见计价单位字典</td>
</tr>
<tr class="odd">
<td>开单科室</td>
<td>ORDERED_BY</td>
<td>C</td>
<td>8</td>
<td>科室代码，见2.6科室字典，用于核算，指独立核算科室，可不同于病房。非空</td>
</tr>
<tr class="even">
<td>执行科室</td>
<td>PERFORMED_BY</td>
<td>C</td>
<td>8</td>
<td>科室代码，见2.6科室字典，用于核算，指独立核算科室。非空</td>
</tr>
<tr class="odd">
<td>费用</td>
<td>COSTS</td>
<td>N</td>
<td>10,4</td>
<td>按价表中标准价格计算得到的费用。非空</td>
</tr>
<tr class="even">
<td>应收费用</td>
<td>CHARGES</td>
<td>N</td>
<td>10,4</td>
<td>考虑病人费别或特殊优惠以及特殊收费项目后病人应交的费用。非空</td>
</tr>
<tr class="odd">
<td>计价日期及时间</td>
<td>BILLING_DATE_TIME</td>
<td>D</td>
<td></td>
<td>生成本计价项目的日期。非空</td>
</tr>
<tr class="even">
<td>计价员号</td>
<td>OPERATOR_NO</td>
<td>C</td>
<td>4</td>
<td>为录入者的用户号。当为后台划价程序生成时，为一特殊的用户号</td>
</tr>
<tr class="odd">
<td>对应的结算序号</td>
<td>RCPT_NO</td>
<td>C</td>
<td>8</td>
<td>病人结算前，该字段为空；结算后，填入结算序号。允许病人中途结算交费，本项费用对应到结算记录</td>
</tr>
<tr class="even">
<td>住院收据分类</td>
<td>CLASS_ON_INP_RCPT</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td>会计科目分类</td>
<td>SUBJ_CODE</td>
<td>C</td>
<td>3</td>
<td></td>
</tr>
<tr class="even">
<td>病案首页分类</td>
<td>CLASS_ON_MR</td>
<td>C</td>
<td>4</td>
<td></td>
</tr>
<tr class="odd">
<td>项目标准单价</td>
<td>ITEM_PRICE</td>
<td>N</td>
<td>10,4</td>
<td></td>
</tr>
<tr class="even">
<td>收费系数</td>
<td>PRICE_QUOTIETY</td>
<td>N</td>
<td>7,4</td>
<td></td>
</tr>
<tr class="odd">
<td>出院带药标志</td>
<td>DISCHARGE_TAKING_INDICATOR</td>
<td>N</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td>护理单元</td>
<td>WARD_CODE</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>核算项目分类</td>
<td>CLASS_ON_RECKONING</td>
<td>C</td>
<td>10</td>
<td></td>
</tr>
<tr class="even">
<td>开单医生核算组</td>
<td>ORDER_GROUP</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>开单医生姓名</td>
<td>ORDER_DOCTOR</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>执行医生核算组</td>
<td>PERFORM_GROUP</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>执行医生</td>
<td>PERFORM_DOCTOR</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>转储时间</td>
<td>CONVEY_DATE</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td>医生代码</td>
<td>DOCTOR_USER</td>
<td>C</td>
<td>16</td>
<td></td>
</tr>
<tr class="even">
<td>医保传送标志</td>
<td>TRANS_FLAG</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td>备注</td>
<td>memo</td>
<td>c</td>
<td>128</td>
<td>记录护士计价时的备注</td>
</tr>
<tr class="even">
<td>适应症标志</td>
<td>ADAPT_SYMPTOM_INDICATE</td>
<td>n</td>
<td>1</td>
<td><p>1.适应症药品</p>
<p>0．非适应症</p></td>
</tr>
<tr class="odd">
<td>出库单号</td>
<td>Document_no</td>
<td>V2</td>
<td>10</td>
<td>消耗品的出库单据号(后台划价或者计价录入后，相应的消耗品生成出库单)</td>
</tr>
<tr class="even">
<td>操作类型</td>
<td>Oper_type</td>
<td>c</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td>操作编码</td>
<td>Oper_code</td>
<td>c</td>
<td>14</td>
<td></td>
</tr>
</tbody>
</table>

注释：此表是住院病人费用的聚集地，在各个诊疗环节发生的费用分别由后台划价程序或各自的系统填入到此表中，在病人出院结帐时和科室核算时使用。

费用明细记录在病人出院后保留一段时间（如6个月）用于查询，之后将从此表中删除。

## 调剂帐户表（inpbill.relief_accounts）

<table>
<colgroup>
<col style="width: 19%" />
<col style="width: 30%" />
<col style="width: 7%" />
<col style="width: 6%" />
<col style="width: 35%" />
</colgroup>
<tbody>
<tr class="odd">
<td>中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>序号</td>
<td>SERIAL_NO</td>
<td>N</td>
<td>4</td>
<td>主键</td>
</tr>
<tr class="odd">
<td>帐户编号</td>
<td>ACCT_NO</td>
<td>C</td>
<td>13</td>
<td>一个单位允许有多个帐户</td>
</tr>
<tr class="even">
<td>单位编号</td>
<td>UNIT_CODE</td>
<td>C</td>
<td>11</td>
<td>合同单位编号</td>
</tr>
<tr class="odd">
<td>记帐类型</td>
<td>ACCT_TYPE</td>
<td>8</td>
<td>2</td>
<td><ul>
<li><p>开户</p></li>
<li><p>增加（增加个人带来的基金、或其它收入）</p></li>
<li><p>支出（为个人调剂到个人预交金、或其它支出）</p></li>
<li><p>转入（由其它帐户调剂来）</p></li>
<li><p>转出（调剂到其它单位帐户）</p></li>
</ul></td>
</tr>
<tr class="even">
<td>记帐金额</td>
<td>ACCT_MONEY</td>
<td>N</td>
<td>(10,2)</td>
<td></td>
</tr>
<tr class="odd">
<td>帐户余额</td>
<td>BALANCE</td>
<td>N</td>
<td>(10,2)</td>
<td>这个余额是此记录记帐后的余额</td>
</tr>
<tr class="even">
<td>摘要</td>
<td>DIGEST</td>
<td>C</td>
<td>50</td>
<td>可记录记帐的对象等</td>
</tr>
<tr class="odd">
<td>记帐时间</td>
<td>ACCT_DATE</td>
<td>DATE</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td>记帐人</td>
<td>ACCT_OPERATOR</td>
<td>C</td>
<td>20</td>
<td></td>
</tr>
<tr class="odd">
<td>申请人</td>
<td>proposer</td>
<td>C</td>
<td>20</td>
<td></td>
</tr>
<tr class="even">
<td colspan="5"><p>期初金额：等于上一区间的最后一个记录的“帐户余额”；</p>
<p>期末金额：等于待查区间的最后一个记录的“帐户余额”；</p></td>
</tr>
</tbody>
</table>

Primary : SERIAL_NO

可建立调剂基金的单位来自于合同单位；在建立病人主索引时，需要维护合适的合同单位。

重要的关联表：合同单位UNIT_IN_CONTRACT

## 待计价病人 NEED_BILLING_PATS(不使用)

|                    |                   |      |      |                                    |
|--------------------|-------------------|------|------|------------------------------------|
| 字段中文名称       | 字段名            | 类型 | 长度 | 说明                               |
| 病人标识           | PATIENT_ID        | C    | 10   | 非空                               |
| 病人本次住院标识   | VISIT_ID          | N    | 2    | 非空                               |
| 计价截止日期及时间 | BILLING_DATE_TIME | D    |      | 指该病人已经计过价的最后日期及时间 |
| 本次计价完成标志   | BILLED_INDICATOR  | N    | 1    | 0-待计价 1-已计价                  |

注释：此表用于记录准备出院需最后划价的病人。住院病人在院期间的费用，每天由后台划价程序定时计价，定时计价之后到病人出院之间发生的费用需单独计价。本表的记录由出院准备程序根据预出院病人记录生成，完成计价后将本次计价完成标志置位。病人出院结帐后，此记录即可删除。

（此表没有被利用）

## 预交金记录 PREPAYMENT_RCPT

|                    |                  |      |      |                                                                                          |
|--------------------|------------------|------|------|------------------------------------------------------------------------------------------|
| 字段中文名称       | 字段名           | 类型 | 长度 | 说明                                                                                     |
| 病人标识           | PATIENT_ID       | C    | 10   | 非空                                                                                     |
| 预交金收据号       | RCPT_NO          | C    | 8    | 非空。用于唯一标识一次预交金支付操作                                                     |
| 金额               | AMOUNT           | N    | 9,2  | 非空。当支付预交金时，为支付金额的负数                                                   |
| 支付方式           | PAY_WAY          | C    | 8    | 非空。现金、支票、汇票等，由用户定义，见6.16支付方式字典                                 |
| 开户银行           | BANK             | C    | 30   | 当预交金以支票方式支付时，为付款方的开户银行，其他情况下为空                             |
| 支票号             | CHECK_NO         | C    | 16   | 当预交金以支票方式支付时的支票号，其他情况下为空                                         |
| 操作类型           | TRANSACT_TYPE    | C    | 4    | 标识本次预交金操作时交费、退费、结算或作废等，本系统定义，见6.17预交金操作类型字典。非空 |
| 操作日期           | TRANSACT_DATE    | D    |      | 非空                                                                                     |
| 收款员号           | OPERATOR_NO      | C    | 4    | 非空                                                                                     |
| 退费收据号         | REFUNDED_RCPT_NO | C    | 8    | 如果此记录为退费记录，则本字段为所退的收据号                                             |
| 预交金结帐序号     | ACCT_NO          | C    | 6    | 对收款员，预交金单独结帐。此处为包含本次操作的预交金结帐记录中的序号                     |
| 银行地址           | ADDR             | C    | 40   |                                                                                          |
| 支票号             | CHECK_NO         | C    | 40   |                                                                                          |
| 银行帐号           | BANK_CODE        | C    | 30   |                                                                                          |
| 住院次数           | VISIT_ID         | N    | 2    |                                                                                          |
| 费用结算号         | SETTLED_NO       | C    | 8    | 费用结算时，当使用了预交金，将结算号计入此列                                             |
| 使用的预交金收据号 | USED_RCPT_NO     | C    | 8    | 交款外的操作，均要记录所使用的（交款的）预交金收据号                                     |
| 使用标志           | USED_FLAG        | C    | 1    | 交款时计0，被使用后计1                                                                   |

注释：此表用于记录病人预交金的收付情况。每次存取，在此表中形成一条记录。

病人出院一个月，如果其对应的预交金收据记录的金额之和为零，则该病人的预交金记录将被删除。

主键：预交金收据号。

## 住院病人结算主记录 INP_SETTLE_MASTER

|                  |                  |      |      |                                                                                                    |
|------------------|------------------|------|------|----------------------------------------------------------------------------------------------------|
| 字段中文名称     | 字段名           | 类型 | 长度 | 说明                                                                                               |
| 收据号           | RCPT_NO          | C    | 8    | 非空，结算的唯一标识                                                                               |
| 病人标识         | PATIENT_ID       | C    | 10   | 非空                                                                                               |
| 病人本次住院标识 | VISIT_ID         | N    | 2    | 非空                                                                                               |
| 结算日期         | SETTLING_DATE    | D    |      | 非空                                                                                               |
| 总费用           | COSTS            | N    | 9,2  | 按价表中标准价格计算得到的病人累计费用                                                             |
| 应交费用         | CHARGES          | N    | 9,2  | 考虑费别因素计算得到的病人实际应交费用                                                             |
| 实交费用         | PAYMENTS         | N    | 9,2  | 病人实际交纳费用。一般情况下应与应交费用相等；在减免情况下，小于应交费用                           |
| 减免原因         | REDUCED_CAUSE    | C    | 30   | 当病人费用被减免时，用于记录减免原因，其他情况下为空。使用正文描述，可记录原因，批准人姓名，日期等 |
| 结算操作类型     | TRANSACT_TYPE    | C    | 4    | 正常、退费、作废。见6.16结算操作类型字典。非空                                                     |
| 退费收据号       | REFUNDED_RCPT_NO | C    | 8    | 如果此记录为退费记录，则本字段为所退的收据号                                                       |
| 收款员号         | OPERATOR_NO      | C    | 4    | 非空                                                                                               |
| 结帐序号         | ACCT_NO          | C    | 6    | 对应包含本次结算的收款员结帐记录中的序号，结帐时填入                                               |
| 新生儿标志       | NEWBORN          | C    | 1    |                                                                                                    |
| 发票号           | INVOICE_NO       | C    | 20   | 使用发票管理是计入该列印刷发票号码                                                                 |
| 结算类型名称     | SETTLE_TYPE_NAME | C    | 20   | 如：中结全结、出院全结等                                                                           |

注释：此表用于描述住院病人结算情况。病人每次结算交费，生成一条记录。当发生退费或由于打印等原因造成收据作废时，也生成一条记录。

病人出院六个月，其所对应的记录将从此表中删除并备份到磁带上，其中减免病人的记录长期保存。

主键：收据号。

## 住院病人结算明细记录 INP_SETTLE_DETAIL

|                  |                |      |      |                                  |
|------------------|----------------|------|------|----------------------------------|
| 字段中文名称     | 字段名         | 类型 | 长度 | 说明                             |
| 收据序号         | RCPT_NO        | C    | 8    | 非空                             |
| 收据费用分类名称 | FEE_CLASS_NAME | C    | 8    | 非空，见6.11住院收据费用分类字典 |
| 费用             | COSTS          | N    | 9,2  | 按价表计算得到的费用             |
| 实交费用         | PAYMENTS       | N    | 9,2  | 非空                             |

注释：此表为病人结算的费用分类记录。

在备份删除住院病人结算主记录表的数据时，同时备份删除本表中的数据。

## 住院病人支付方式记录 INP_PAYMENTS_MONEY

|              |                 |      |      |                                                                |
|--------------|-----------------|------|------|----------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                           |
| 收据号       | RCPT_NO         | C    | 8    | 标识一次付费                                                   |
| 金额类型     | MONEY_TYPE      | C    | 8    | 标识付费方法，如：现金、支票、医保等，见支付方式字典           |
| 支付序号     | PAYMENT_NO      | N    | 2    | 反映各种金额类型的支付顺序                                     |
| 数额         | PAYMENT_AMOUNT  | N    | 9,2  |                                                                |
| 退数额       | REFUNDED_AMOUNT | N    | 9,2  | 如：支票方式支付，支票方式退余额。支付数额减退数额即为实付数额 |

注释：此表对病人付费的方法和数量进行详细描述。一次就诊付费可以使用多种付费方法。

主键：收据号、金额类型。

## 医嘱划价检查记录 INP_BILL_CHECKED(不使用)

|                    |                      |      |      |                          |
|--------------------|----------------------|------|------|--------------------------|
| 字段中文名称       | 字段名               | 类型 | 长度 | 说明                     |
| 病人标识           | PATIENT_ID           | C    | 10   | 非空                     |
| 病人本次住院标识   | VISIT_ID             | N    | 2    |                          |
| 上次检查日期及时间 | LAST_CHECK_DATE_TIME | D    |      | 最后一次检查的日期及时间 |

注释：此表为收款员对病人医嘱划价检查的工作记录。首次对一个病人进行划价检查时生成，出院结帐时删除。

## 欠费病人记录 UNSETTLE_REC

|                  |                       |      |      |                             |
|------------------|-----------------------|------|------|-----------------------------|
| 字段中文名称     | 字段名                | 类型 | 长度 | 说明                        |
| 病人标识         | PATIENT_ID            | C    | 10   | 非空                        |
| 病人本次住院标识 | VISIT_ID              | N    | 2    |                             |
| 病人姓名         | NAME                  | C    | 20   | 非空                        |
| 所在科室         | DEPT_NAME             | C    | 20   | 非空                        |
| 费别             | CHARGE_TYPE_NAME      | C    | 8    | 使用规范名称，见1.9费别字典 |
| 通信地址         | MAILING_ADDRESS       | C    | 40   |                             |
| 工作单位         | UNIT_OF_WORK          | C    | 40   |                             |
| 家庭电话号码     | PHONE_NUMBER_HOME     | C    | 16   |                             |
| 单位电话号码     | PHONE_NUMBER_BUSINESS | C    | 16   |                             |
| 医疗费总额       | TOTAL_COST            | N    | 10,2 | 指应付的未结费用总额，非空  |
| 预交金总额       | PREPAYMENTS           | N    | 10,2 | 指欠费时预交金的余额，非空  |
| 担保人           | GUARANTOR             | C    | 8    | 非空                        |
| 担保人单位       | UNIT_OF_GUARANTOR     | C    | 20   | 非空                        |
| 登记人           | OPERATOR              | C    | 8    | 非空                        |
| 登记日期         | ENTER_DATE            | D    |      | 非空                        |
|                  | UNSETTLE_CAUSE        | C    | 40   |                             |

注释：此表记录欠费出院病人，当病人结清费用后删除对应的记录。

主键：病人标识、病人本次住院标识。

## 住院收费结帐记录 INP_ACCT_MASTER

|              |                    |      |      |                                                                |
|--------------|--------------------|------|------|----------------------------------------------------------------|
| 字段中文名称 | 字段名             | 类型 | 长度 | 说明                                                           |
| 结帐序号     | ACCT_NO            | C    | 6    | 非空                                                           |
| 收款员号     | OPERATOR_NO        | C    | 4    | 非空                                                           |
| 结帐日期     | ACCT_DATE          | D    |      | 非空                                                           |
| 最小收据序号 | MIN_RCPT_NO        | C    | 8    | 一般情况下此次结帐涉及的收据的序号是连续的，此处为最小号。非空 |
| 最大收据序号 | MAX_RCPT_NO        | C    | 8    | 此处为收据的最大号。非空                                       |
| 收据张数     | RCPTS_NUM          | N    | 4    | 含退费收据和作废收据，不含免费人次数。非空                     |
| 免费人次     | FREE_OF_CHARGE_NUM | N    | 4    | 实交费用为0的人次数                                            |
| 退费收据张数 | REFUNDED_NUM       | N    | 4    | 非空                                                           |
| 作废收据张数 | INVALID_NUM        | N    | 4    | 非空                                                           |
| 总费用       | TOTAL_COSTS        | N    | 10,2 | 按标准价格计算得到的累计费用                                   |
| 总收入       | TOTAL_INCOMES      | N    | 10,2 | 非空                                                           |
| 记帐日期     | TALLY_DATE         | D    |      | 记入会计帐目中的日期，由会计将该次结帐所交款入帐时填入。       |

注释：此表记录收款员医疗收入部分结帐情况，也是收款员向会计交帐的凭证。每次结帐生成一条记录。

主键：结帐序号。

## 住院收费结帐明细记录 INP_ACCT_DETAIL

|              |           |      |      |                                                                    |
|--------------|-----------|------|------|--------------------------------------------------------------------|
| 字段中文名称 | 字段名    | 类型 | 长度 | 说明                                                               |
| 结帐序号     | ACCT_NO   | C    | 6    | 住院收费结帐主记录中对应的结帐序号。非空                           |
| 科目代码     | SUBJ_CODE | C    | 4    | 会计帐目中规定的科目，使用代码，用户定义，见6.13会计科目字典。非空 |
| 费用         | COSTS     | N    | 10,2 | 按标准价格计算得到的累计费用                                       |
| 收入         | INCOME    | N    | 10,2 | 非空                                                               |

注释：此表为住院收费结帐记录的明细记录。一次结帐包含多种类别的收入。每种收入对应一条记录。

主键：结帐序号、科目代码。

## 住院收费结帐金额分类 INP_ACCT_MONEY

|              |                 |      |      |                                                                |
|--------------|-----------------|------|------|----------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                           |
| 结帐序号     | ACCT_NO         | C    | 6    | 标识一次结帐                                                   |
| 金额类别     | MONEY_TYPE      | C    | 8    | 标识收入金额种类，如：现金、支票、医保等，见支付方式字典       |
| 数额         | INCOME_AMOUNT   | N    | 10,2 |                                                                |
| 退数额       | REFUNDED_AMOUNT | N    | 10,2 | 如：支票方式支付，支票方式退余额。支付数额减退数额即为实收数额 |

注释：此表对住院收费结帐的金额种类进行描述。

主键：结帐序号、金额类别。

## 预交金结帐记录 PREPAY_ACCT

|              |               |      |      |                                                        |
|--------------|---------------|------|------|--------------------------------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                                                   |
| 结帐序号     | ACCT_NO       | C    | 6    | 非空                                                   |
| 收款员号     | OPERATOR_NO   | C    | 4    | 非空                                                   |
| 结帐日期     | ACCT_DATE     | D    |      | 非空                                                   |
| 最小收据号   | MIN_RCPT_NO   | C    | 8    |                                                        |
| 最大收据号   | MAX_RCPT_NO   | C    | 8    |                                                        |
| 收据张数     | RCPTS_NUM     | N    | 4    |                                                        |
| 退费张数     | REFUNDED_NUM  | N    | 4    |                                                        |
| 作废张数     | INVALID_NUM   | N    | 4    |                                                        |
| 总收入       | TOTAL_INCOMES | N    | 10,2 | 非空                                                   |
| 记帐日期     | TALLY_DATE    | D    |      | 记入会计帐目中的日期，由会计将本次结帐的收入入帐时填入 |

注释：此表用于反映病人预交金收入情况，是收款员向会计交帐的凭证。每次结帐生成一条记录。

当记帐序号不为空且结帐日期超过6个月，相应的数据将被备份到磁带上并删除。

主键：结帐序号。

## 预交金结帐金额分类 PREPAY_ACCT_MONEY

|              |                 |      |      |                                                                |
|--------------|-----------------|------|------|----------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                                           |
| 结帐序号     | ACCT_NO         | C    | 6    | 标识一次结帐                                                   |
| 金额类别     | MONEY_TYPE      | C    | 8    | 标识收入金额种类，如：现金、支票、医保等，见支付方式字典       |
| 数额         | INCOME_AMOUNT   | N    | 10,2 |                                                                |
| 退数额       | REFUNDED_AMOUNT | N    | 10,2 | 如：支票方式支付，支票方式退余额。支付数额减退数额即为实收数额 |

注释：此表对预交金结帐的金额种类进行描述。

主键：结帐序号、金额类别。

## 住院病人伙食费明细 INP_DIET_COSTS

|                  |                   |      |      |                                               |
|------------------|-------------------|------|------|-----------------------------------------------|
| 字段中文名称     | 字段名            | 类型 | 长度 | 说明                                          |
| 病人标识号       | PATIENT_ID        | C    | 10   | 非空                                          |
| 病人本次住院标识 | VISIT_ID          | N    | 2    | 非空                                          |
| 项目序号         | ITEM_NO           | N    | 4    | 标识病人一次住院的多次费用，从1开始，逐次递增 |
| 费用             | COSTS             | N    | 9,2  |                                               |
| 营养室           | DIET_PROVIDER     | C    | 1    | 提供膳食的营养室代码，见2.13营养室字典        |
| 计价日期及时间   | BILLING_DATE_TIME | D    |      | 生成本计价项目的日期及时间                    |
| 计价员号         | OPERATOR_NO       | C    | 4    |                                               |
| 对应的结算序号   | RCPT_NO           | C    | 8    | 对应病人结算记录序号                          |

注释：此表用于记录病人伙食费情况。病人每次住院可以有多条记录，既适应累计后记入的情况，也适应单次记入的情况。

主键：病人标识、病人本次住院标识、项目序号。

## 收款员号表 CASHER_NO_REC

|              |            |      |      |                        |
|--------------|------------|------|------|------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                   |
| 本地号       | LOCAL_NO   | C    | 4    | 收费系统使用的收款员号 |
| 用户标识     | USER_ID    | C    | 4    | 系统统一定义的用户标识 |
|              | GATH_LEVEL | C    | 1    |                        |
|              | LEVELS     | C    | 1    |                        |

注释：此表用于描述收费系统内部定义收款员的号与系统全局定义的统一的用户标识之间的对应关系。

## 收款员工作日志 CASHER_WORKING_LOG

|                |                |      |      |                          |
|----------------|----------------|------|------|--------------------------|
| 字段中文名称   | 字段名         | 类型 | 长度 | 说明                     |
| 收款员号       | OPER_NO        | C    | 4    | 收费系统使用的收款员号   |
| 收款员姓名     | OPER_NAME      | C    | 8    |                          |
| 记录日期及时间 | OPER_DATE_TIME | D    |      | 指动作发生的日期及时间   |
| 记录内容       | CONTENTS       | C    | 200  | 指动作内容，由开发者决定 |

注释：此表用于住院收费系统记录收款员重要的操作，如作废收据等。

主键：收款员号、记录日期及时间。

## 自动计价科室配置 BILL_DEPT_CONFIG

|              |           |      |      |                        |
|--------------|-----------|------|------|------------------------|
| 字段中文名称 | 字段名    | 类型 | 长度 | 说明                   |
| 科室代码     | DEPT_CODE | C    | 8    | 实行自动计价的科室代码 |

注释：此表用于记录实行住院病人后台自动计价的科室，由后台划价程序选取计价病人时使用。

主键：科室代码。（后台划价并未使用到）

## 自动计价杂费项目BILL_MISC_ITEM

|              |            |      |      |                  |
|--------------|------------|------|------|------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明             |
| 序号         | ITEM_NO    | N    | 3    | 项目的排列顺序   |
| 项目类别     | ITEM_CLASS | C    | 1    | 杂费价表项目类别 |
| 项目代码     | ITEM_CODE  | C    | 8    | 杂费价表项目代码 |
| 项目规格     | ITEM_SPEC  | C    | 20   | 杂费价表项目规格 |

注释：此表用于记录对每个病人按天收取的固定费用项目（杂费），比如：诊疗费、空调费等。要求这类项目必须在价表中有对应的项目，并且同一项目在价表中仅有一条记录（即只有一种规格）。这些项目由后台划价程序计价时使用。

主键：项目类别、项目代码、项目规格。

## 自动计价杂费特殊项目BILL_MISC_ITEM_PATCH(新增)

|          |            |      |      |                     |
|----------|------------|------|------|---------------------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明                |
| 科室代码 | DEPT_CODE  | C    | 8    |                     |
| 项目类别 | ITEM_CLASS | C    | 1    |                     |
| 项目代码 | ITEM_CODE  | C    | 20   |                     |
| 项目名称 | ITEM_NAME  | C    | 100  |                     |
| 项目规格 | ITEM_SPEC  | C    | 50   |                     |
| 项目单位 | UNITS      | C    | 8    |                     |
| 病人id   | PATIENT_ID | V2   | 20   | 默认值是\* 所有病人 |
| 住院次数 | VISIT_ID   | n    |      | 默认值是 0 所有病人 |

注释：此表用于记录指定科室对病人按天收取的固定费用项目

后台划价时根据 patient_id ,visit_id 进行划价

## 病人可透支额INP_OVERDRAFT_REG_MASTER(新增)

|              |                         |      |      |      |
|--------------|-------------------------|------|------|------|
| 中文名称     | 字段名                  | 类型 | 长度 | 说明 |
| 病人ID       | PATIENT_ID              | C    | 10   |      |
| 住院次数     | VISIT_ID                | N    | 2    |      |
|              | UNLIMITED_INDICATOR     | N    | 1    |      |
| 透支金额合计 | TOTAL_SANCTIFIED_AMOUNT | N    | 10,2 |      |

该表记录病人一次住院的可透支额

## 透支记录明细INP_OVERDRAFT_REG_DETAIL(新增)

|                |                   |      |      |      |
|----------------|-------------------|------|------|------|
| 中文名称       | 字段名            | 类型 | 长度 | 说明 |
| 病人ID         | PATIENT_ID        | C    | 10   |      |
| 住院次数       | VISIT_ID          | N    | 2    |      |
| 明细序号       | REG_SUB_NO        | N    | 2    |      |
| 透支金额       | SANCTIFIED_AMOUNT | N    | 10,2 |      |
| 透支性质       | SANCTIFIED_ATTR   | C    | 8    |      |
|                | SANCTIFIER        | C    | 16   |      |
| 担保人         | GUARANTOR         | C    | 16   |      |
| 担保人身份证号 | GRARANTOR_ID_NO   | C    | 18   |      |
| 担保人单位     | UNIT_OF_GUARANTOR | C    | 30   |      |
| 操作员         | OPERATOR          | C    | 16   |      |
| 输入日期       | ENTERED_DATE      | D    |      |      |
| 取消日期       | DISABLED_DATE     | D    |      |      |
| 支票号码       | CHECK_NO          | C    | 30   |      |

透支记录明细

## 养老颐养者生活费用明细记录 LIVE_BILL_DETAIL

<table>
<colgroup>
<col style="width: 15%" />
<col style="width: 34%" />
<col style="width: 7%" />
<col style="width: 8%" />
<col style="width: 33%" />
</colgroup>
<tbody>
<tr class="odd">
<td>字段中文名称</td>
<td>字段名</td>
<td>类型</td>
<td>长度</td>
<td>说明</td>
</tr>
<tr class="even">
<td>病人标识</td>
<td>PATIENT_ID</td>
<td>C</td>
<td>10</td>
<td>非空</td>
</tr>
<tr class="odd">
<td>病人本次住院标识</td>
<td>VISIT_ID</td>
<td>N</td>
<td>2</td>
<td>非空</td>
</tr>
<tr class="even">
<td>费用项目序号</td>
<td>ITEM_NO</td>
<td>N</td>
<td>6</td>
<td>一个病人的费用项目的唯一标识</td>
</tr>
<tr class="odd">
<td>项目类别</td>
<td>ITEM_CLASS</td>
<td>C</td>
<td>1</td>
<td>按价表项目分类，使用代码，见6.10价表项目分类字典。非空</td>
</tr>
<tr class="even">
<td>项目名称</td>
<td>ITEM_NAME</td>
<td>C</td>
<td>100</td>
<td>项目的正文描述</td>
</tr>
<tr class="odd">
<td>项目代码</td>
<td>ITEM_CODE</td>
<td>C</td>
<td>20</td>
<td>非空</td>
</tr>
<tr class="even">
<td>项目规格</td>
<td>ITEM_SPEC</td>
<td>C</td>
<td>50</td>
<td>指药品的规格或材料的规格。</td>
</tr>
<tr class="odd">
<td>数量</td>
<td>AMOUNT</td>
<td>N</td>
<td>6,2</td>
<td></td>
</tr>
<tr class="even">
<td>单位</td>
<td>UNITS</td>
<td>C</td>
<td>8</td>
<td>如片、瓶、人次等，本系统定义，见计价单位字典</td>
</tr>
<tr class="odd">
<td>开单科室</td>
<td>ORDERED_BY</td>
<td>C</td>
<td>8</td>
<td>科室代码，见2.6科室字典，用于核算，指独立核算科室，可不同于病房。非空</td>
</tr>
<tr class="even">
<td>执行科室</td>
<td>PERFORMED_BY</td>
<td>C</td>
<td>8</td>
<td>科室代码，见2.6科室字典，用于核算，指独立核算科室。非空</td>
</tr>
<tr class="odd">
<td>费用</td>
<td>COSTS</td>
<td>N</td>
<td>10,4</td>
<td>按价表中标准价格计算得到的费用。非空</td>
</tr>
<tr class="even">
<td>应收费用</td>
<td>CHARGES</td>
<td>N</td>
<td>10,4</td>
<td>考虑病人费别或特殊优惠以及特殊收费项目后病人应交的费用。非空</td>
</tr>
<tr class="odd">
<td>计价日期及时间</td>
<td>BILLING_DATE_TIME</td>
<td>D</td>
<td></td>
<td>生成本计价项目的日期。非空</td>
</tr>
<tr class="even">
<td>计价员号</td>
<td>OPERATOR_NO</td>
<td>C</td>
<td>4</td>
<td>为录入者的用户号。当为后台划价程序生成时，为一特殊的用户号</td>
</tr>
<tr class="odd">
<td>对应的结算序号</td>
<td>RCPT_NO</td>
<td>C</td>
<td>8</td>
<td>病人结算前，该字段为空；结算后，填入结算序号。允许病人中途结算交费，本项费用对应到结算记录</td>
</tr>
<tr class="even">
<td>住院收据分类</td>
<td>CLASS_ON_INP_RCPT</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td>会计科目分类</td>
<td>SUBJ_CODE</td>
<td>C</td>
<td>3</td>
<td></td>
</tr>
<tr class="even">
<td>病案首页分类</td>
<td>CLASS_ON_MR</td>
<td>C</td>
<td>4</td>
<td></td>
</tr>
<tr class="odd">
<td>项目标准单价</td>
<td>ITEM_PRICE</td>
<td>N</td>
<td>10,4</td>
<td></td>
</tr>
<tr class="even">
<td>收费系数</td>
<td>PRICE_QUOTIETY</td>
<td>N</td>
<td>7,4</td>
<td></td>
</tr>
<tr class="odd">
<td>出院带药标志</td>
<td>DISCHARGE_TAKING_INDICATOR</td>
<td>N</td>
<td>1</td>
<td></td>
</tr>
<tr class="even">
<td>护理单元</td>
<td>WARD_CODE</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>核算项目分类</td>
<td>CLASS_ON_RECKONING</td>
<td>C</td>
<td>10</td>
<td></td>
</tr>
<tr class="even">
<td>开单医生核算组</td>
<td>ORDER_GROUP</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>开单医生姓名</td>
<td>ORDER_DOCTOR</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>执行医生核算组</td>
<td>PERFORM_GROUP</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="odd">
<td>执行医生</td>
<td>PERFORM_DOCTOR</td>
<td>C</td>
<td>8</td>
<td></td>
</tr>
<tr class="even">
<td>转储时间</td>
<td>CONVEY_DATE</td>
<td>D</td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td>医生代码</td>
<td>DOCTOR_USER</td>
<td>C</td>
<td>16</td>
<td></td>
</tr>
<tr class="even">
<td>医保传送标志</td>
<td>TRANS_FLAG</td>
<td>C</td>
<td>1</td>
<td></td>
</tr>
<tr class="odd">
<td>备注</td>
<td>MEMO</td>
<td>C</td>
<td>128</td>
<td>录入费用时的备注说明</td>
</tr>
<tr class="even">
<td>计费来源操作类型</td>
<td>OPER_TYPE</td>
<td>C</td>
<td>1</td>
<td><p>表明该费是读书笔记的类型。</p>
<p>Z是临床住院记录的。</p></td>
</tr>
<tr class="odd">
<td>操作代码</td>
<td>OPER_CODE</td>
<td>C</td>
<td>12</td>
<td></td>
</tr>
<tr class="even">
<td>单据号</td>
<td>DOCUMENT_NO</td>
<td>C</td>
<td>10</td>
<td>如果是因为药品材料器械等，则应当有相应的入库单据号</td>
</tr>
</tbody>
</table>

注释：本表是为了解决老年病医院的在养老颐养的生活日常消费的费用的录入问题。不用住院费用明细表是因为这些费用都不记入医疗收入，并且如果放到住院费用明细表中，会影响原来的整个流程的。

主键：PATIENT_ID, VISIT_ID, ITEM_NO 名称 PK_LIVE_BILL_DETAIL

## INP_BILL_DETAIL_BACK

|          |                   |      |      |      |
|----------|-------------------|------|------|------|
| 中文名称 | 字段名            | 类型 | 长度 | 说明 |
|          | PATIENT_ID        | C    | 10   |      |
|          | VISIT_ID          | N    | 2    |      |
|          | ITEM_NO           | N    | 6    |      |
|          | ITEM_CLASS        | C    | 1    |      |
|          | ITEM_NAME         | C    | 40   |      |
|          | ITEM_CODE         | C    | 10   |      |
|          | ITEM_SPEC         | C    | 20   |      |
|          | AMOUNT            | N    | 6,2  |      |
|          | UNITS             | C    | 8    |      |
|          | ORDERED_BY        | C    | 8    |      |
|          | PERFORMED_BY      | C    | 8    |      |
|          | COSTS             | N    | 8,2  |      |
|          | CHARGES           | N    | 8,2  |      |
|          | BILLING_DATE_TIME | D    |      |      |
|          | OPERATOR_NO       | C    | 4    |      |
|          | RCPT_NO           | C    | 8    |      |
|          | ORDER_DOCT        | C    | 10   |      |
|          | PERFORM_DOCT      | C    | 10   |      |

结构同INP_BILL_DETAIL

#  收费帐目

## 支票根记录 STUB_CHECK_REC

|              |              |      |      |                              |
|--------------|--------------|------|------|------------------------------|
| 字段中文名称 | 字段名       | 类型 | 长度 | 说明                         |
| 收据号       | RCPT_NO      | C    | 8    | 非空，标识一次结算           |
| 支票号       | CHECK_NO     | C    | 16   | 非空，病人结算时所退的支票号 |
| 支票金额     | CHECK_AMOUNT | N    | 9,2  | 非空                         |
| 支票日期     | CHECK_DATE   | D    |      | 支票开出的日期。非空         |
| 收款员号     | OPERATOR_NO  | C    | 4    | 非空                         |
| 结帐序号     | ACCT_NO      | C    | 6    |                              |

注释：在病人结帐时，需要退还多余的预交金，此表用于记录为此开出的支票信息，以便将来会计记帐。

当记帐序号不为空且支票日期超过6个月，相应的数据将被备份到磁带上并删除。

## 记帐凭单主记录 TALLY_MASTER(新增)

|              |                   |      |      |      |
|--------------|-------------------|------|------|------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明 |
| 凭证号       | TALLY_NO          | N    | 6    |      |
| 记账日期     | TALLY_DATE        | D    |      |      |
| 科目         | TABLER            | C    | 12   |      |
| 科目代码     | TABLER_NO         | N    | 6    |      |
| 结帐科目     | TALLY_ACCT_TABLER | C    | 8    |      |
| 结帐号       | TALLY_ACCT_NO     | N    | 6    |      |
| 输入日期     | ENTER_DATE        | D    | 7    |      |

注释：此表与记帐凭单明细记录一起用于会计记帐。

记帐日期超过3年后，其数据将被删除并保存到磁带上。

## 记帐凭单明细记录 TALLY_DETAIL

|              |                 |      |      |                                      |
|--------------|-----------------|------|------|--------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                 |
| 记帐序号     | TALLY_NO        | N    | 6    | 记帐凭单主记录中对应的序号。非空     |
| 科目代码     | TABLER          | C    | 12   | 由用户定义，见6.15会计科目字典。非空 |
| 收方金额     | TABLER_NO       | N    | 6    | 非空                                 |
| 付方金额     | TALLY_SUB_NO    | N    | 5    | 非空                                 |
| 摘要         | SUBJ_CODE       | C    | 10   | 非空                                 |
| 备注         | SUMMARY         | C    | 48   |                                      |
|              | UNIT_CODE       | C    | 12   |                                      |
|              | DEPT_CODE       | C    | 8    |                                      |
|              | ITEM_CODE       | C    | 8    |                                      |
|              | DEBIT_OR_CREDIT | C    | 1    |                                      |
|              | AMOUNT          | N    | 13,2 |                                      |

注释：在备份删除记帐凭单主记录时，此表中对应的数据将同时删除并备份。

## 记帐凭单中支票记录 TALLY_CHECK_REC

|              |             |      |      |                                                 |
|--------------|-------------|------|------|-------------------------------------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明                                            |
| 记帐序号     | TALLY_NO    | C    | 8    | 记帐凭单主记录中对应的序号。非空                |
| 项目序号     | CHECK_SNO   | N    | 4    | 标识记帐凭单中的多条支票记录，从1开始，顺序排列 |
| 支票标识     | CHECK_LABEL | C    | 4    | 他行、本行、汇票。见6.19支票标识字典。非空      |
| 金额         | AMOUNT      | N    | 12,2 | 非空                                            |

注释：此表用于记录记帐凭单中存在的支票。与银行对帐时使用。

在备份删除记帐凭单主记录时，此表中对应的数据将同时删除并备份。

## 记帐凭单中支票根记录 TALLY_STUB_REC

|              |          |      |      |                                  |
|--------------|----------|------|------|----------------------------------|
| 字段中文名称 | 字段名   | 类型 | 长度 | 说明                             |
| 记帐序号     | TALLY_NO | C    | 8    | 记帐凭单主记录中对应的序号。非空 |
| 支票号       | CHECK_NO | C    | 16   | 非空                             |
| 金额         | AMOUNT   | N    | 12,2 | 非空                             |

注释：此表用于记录记帐凭单中付出的支票。与银行对帐时使用。

在备份删除记帐凭单主记录时，此表中对应的数据将同时删除并备份。

## 汇款收据记录 REMIT_REC

|                  |               |      |      |      |
|------------------|---------------|------|------|------|
| 字段中文名称     | 字段名        | 类型 | 长度 | 说明 |
| 收据号           | RCPT_NO       | C    | 6    | 非空 |
| 汇款单位         | REMIT_UNIT    | C    | 30   |      |
| 汇款单位开户银行 | BANK          | C    | 30   | 非空 |
| 汇款单位帐号     | ACCOUNT_NO    | C    | 16   | 非空 |
| 收款人           | RECEIV_PERSON | C    | 8    | 非空 |
| 金额             | AMOUNT        | N    | 9,2  | 非空 |
| 收到日期         | RECEIV_DATE   | D    |      |      |
| 操作员号         | OPERATOR_NO   | C    | 4    | 非空 |
| 录入日期         | ENTER_DATE    | D    |      | 非空 |
| 核销人号         | VERIFIER_NO   | C    | 4    |      |
| 核销日期         | VERIFY_DATE   | D    |      |      |

注释：此表用于记录病人汇款。由收费帐务子系统生成。

已被核销的记录过6 个月后删除。

## 会计科目摘要字典 TALLY_SUMMARY_DICT

|              |            |      |      |      |
|--------------|------------|------|------|------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO  | N    | 4    |      |
| 摘要         | SUMMARY    | C    | 30   | 非空 |
| 输入码       | INPUT_CODE | C    | 8    |      |

注释：此表定义了记帐科目对应的常用的记帐摘要内容，记帐时使用。

## 收费帐务序号表 ACCT_SNO

|                  |               |      |      |                              |
|------------------|---------------|------|------|------------------------------|
| 字段中文名称     | 字段名        | 类型 | 长度 | 说明                         |
| 记帐凭单当前序号 | TALLY_CURR_NO | N    | 6    | 非空，记帐凭单下一个可用序号 |
| 汇款收据当前序号 | REMIT_CURR_NO | N    | 6    | 非空，汇款收据下一个可用序号 |

注释：每记入一笔帐，序号加1。

## 卫生经济分系统配置表 ECON_DESC

|                |              |      |      |                                                                             |
|----------------|--------------|------|------|-----------------------------------------------------------------------------|
| 字段中文名称   | 字段名       | 类型 | 长度 | 说明                                                                        |
| 科室名称       | DEPT_NAME    | C    | 20   | 卫生经济科名称                                                              |
| 科室代码       | DEPT_CODE    | C    | 8    | 见2.6科室字典                                                               |
| 负责人         | LEADER       | C    | 8    | 卫生经济科负责人                                                            |
| 开户银行       | OPEN_BANK    | C    | 30   |                                                                             |
| 单位名称       | REMIT_UNIT   | C    | 30   | 指汇款单位                                                                  |
| 银行帐号       | ACCOUNT_NO   | C    | 16   |                                                                             |
| 催交预交金限度 | PREPAY_LIMIT | N    | 2    | 当医疗开销达到预交金的多少时，要催补预交金。如：80%，把80记录在此字段。非空 |

## 科室与记帐部门对照字典 DEPT_VS_CLASS_FOR_ACCT

|              |            |      |      |                                              |
|--------------|------------|------|------|----------------------------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                                         |
| 科室代码     | DEPT_CODE  | C    | 8    | 见2.6科室字典                                |
| 部门编码     | CLASS_CODE | C    | 1    | 由用户定义，见卫生经济管理分系统编码字典文档 |

注释：此表由收费帐务管理子系统维护，按会计记帐需要把科室分成不同的部门。

只包括门诊和住院科室，是科室字典的子集。

## （科室）记帐部门字典 DEPT_CLASS_FOR_ACCT_DICT

|              |            |      |      |                              |
|--------------|------------|------|------|------------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                         |
| 编码         | CLASS_CODE | C    | 1    | 部门编码，根据用户需要定义。 |
| 名称         | CLASS_NAME | C    | 10   | 部门名称                     |

注释：按帐务管理需要，将科室分成多个部门，此表说明这些部门的名称和为其设置的编码；此表建在服务器上，长期保存。

## 生成医疗收支月报表模板 ECON_REPORT_PATTERN

|              |          |      |      |                                                                                |
|--------------|----------|------|------|--------------------------------------------------------------------------------|
| 字段中文名称 | 字段名   | 类型 | 长度 | 说明                                                                           |
| 行名         | ROW_NAME | C    | 16   | 报表行的中文名称                                                               |
| 科目集       | SUBJECTS | C    | 100  | 它说明此行所对应的科目（代码），科目（代码）间用“、”分隔。最多可以有16个科目。 |

注释：此表由用户根据报表需要定义，辅助软件生成“医疗收支月报表”。它存放在服务器上，长期保存。

## 转记账业务分类字典TALLY_CLASS_DICT(新增)

|              |            |      |      |                        |
|--------------|------------|------|------|------------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                   |
| 序号         | SERIAL_NO  | N    | 3    |                        |
| 分类代码     | CLASS_CODE | C    | 2    |                        |
| 分类名称     | CLASS_NAME | C    | 20   | 预交金收款、门诊收款等 |

主键：分类代码。

说明：属系统定义。此表记录医疗物资业务名称与编码。所有与财务记帐发生关系的业务被记录在此表中，用于规范业务操作与会计记帐关系接口表中的业务名称与编码字段的内容。

## 医疗收入转记账业务对照表HIS_SUBJ_VS_ACCT_SUBJ (新增)

|                      |                 |      |      |                                                                                                       |
|----------------------|-----------------|------|------|-------------------------------------------------------------------------------------------------------|
| 字段中文名称         | 字段名          | 类型 | 长度 | 说明                                                                                                  |
| 转记帐业务代码       | OPERATION_CODE  | C    | 2    | 见系统定义字典TALLY_CLASS_DICT                                                                        |
| 转记帐业务名称       | OPERATION_NAME  | C    | 20   |                                                                                                       |
| 借贷标识             | DEBIT_OR_CREDIT | C    | 1    | 0是借，1是贷                                                                                          |
| 支付方式或会计科目   | HIS_SUBJ_NAME   | C    | 20   | 规范名称。医疗收款的付款方式或医疗收入的会计科目，由“军字1号“的支付方式字典与会计科目字典的合集定义。 |
| 会计核算系统科目代码 | SUBJ_CODE       | C    | 10   | “会计核算系统“的会计科目字典内容。                                                                    |
| 会计核算系统科目名称 | SUBJ_NAME       | C    | 36   |                                                                                                       |
| 摘要                 | SUMMARY         | C    | 48   | 自由文文。会计分录中对业务的说明。                                                                    |

主键：转记账业务代码，借贷标识，支付方式或会计科目

说明：由于建立引起资产变化的医疗物资业务及业务相关科目与其对应的会计分录业务的会计科目之间的关系。例如对于预交金收现金款这一项业务，对于的会计分录如下：

借：库存现金 5000

贷：医疗预收款 5000

为了＜转记帐系统＞能够准确的生成此会计分录，此字典中需要定义一条记录如下：

|                |                |          |                    |                      |                      |      |
|----------------|----------------|----------|--------------------|----------------------|----------------------|------|
| 转记帐业务代码 | 转记帐业务名称 | 借贷标识 | 支付方式或会计科目 | 会计核算系统科目代码 | 会计核算系统科目名称 | 摘要 |
| 11             | 预交金收款     | 0        | 现金               |                      | 库存现金             |      |
| １１           | 预交金收款     | １       | \*                 |                      | 医疗预收款           |      |

此字典由系统提供模板数据及维护工具进行维护。用户可根据具体情况自行修改。

## 医疗收入记账记录ACCT_VS_TALLY_REC

|                  |                |      |      |                                                                            |
|------------------|----------------|------|------|----------------------------------------------------------------------------|
| 字段中文名称     | 字段名         | 类型 | 长度 | 说明                                                                       |
| 医疗收款业务代码 | OPERATION_CODE | C    | 2    | 系统定义。与“医疗收入对照表“中的转记帐业务代码中的相关业务代码一致（子集） |
| 收款员交款结账号 | ACCT_NO        | C    | 6    | 对应于“军字1号“系统中预交金／门诊／住院结帐记录的结帐号                    |
| 记账人           | TABLER         | C    | 8    | 生成记帐记录的操作者名称                                                   |
| 记账号           | TABLER_NO      | N    | 6    | 记帐凭证的记帐号                                                           |

主键：医疗收入结账号。

说明：此表用于记录记帐记录中转记帐业务所合并的门诊收费、预交金收款、住院收费业务产生的收款员结帐号。主要用于转记帐业务的回朔。

## 应收住院医药费记账缓存表INPBILL_ACCT_REC

|              |            |      |      |                      |
|--------------|------------|------|------|----------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                 |
| 病人ID       | PATIENT_ID | C    | 10   |                      |
| 住院次数     | VISIT_ID   | N    | 2    |                      |
| 项目序号     | ITEM_NO    | N    | 6    |                      |
| 项目类别     | ITEM_CLASS | C    | 1    |                      |
| 项目名称     | ITEM_NAME  | C    | 40   |                      |
| 项目代码     | ITEM_CODE  | C    | 10   |                      |
| 项目规格     | ITEM_SPEC  | C    | 20   |                      |
| 单位         | UNIT       | C    | 8    |                      |
| 计价金额     | COSTS      | N    | 10,2 |                      |
| 应收金额     | CHARGES    | N    | 10,2 |                      |
| 会计科目     | SUBJ_CODE  | C    | 4    | 价表中对应的会计科目 |
| 记账日期     | TALLY_DATE | D    |      | 暂不用               |
| 记账人       | TABLER     | C    | 8    | 暂不用               |
| 记账号       | TABLER_NO  | N    | 6    | 暂不用               |
| 操作日期     | ENTER_DATE | D    |      |                      |

主键：病人ID，住院次数，项目序号

说明：用于缓存应收住院医药费转记账后的住院病人费用明细记录。通过此表可以记录已经被应收转记帐统计过的病人费用明细，同时用于进行转记帐审核功能，通过对那些结算的病人的INP_BILL_DETAIL中的记录与本表记录的比较，调整由于军字1号系统对inp_bill_detail的修改造成的会计记帐数据产生变化的情况。此表由医药收入后台过程产生，由应收住院医药费核查后台过程删除。

## 应收医药费核查记录INPBILL_ACCT_CHECK

|              |             |         |      |                                                                      |
|--------------|-------------|---------|------|----------------------------------------------------------------------|
| 字段中文名称 | 字段名      | 类型    | 长度 | 说明                                                                 |
| 病人ID       | PATIENT_ID  | VARCHAR | 10   |                                                                      |
| 住院次数     | VISIT_ID    | NUMBER  | 2    |                                                                      |
| 项目序号     | ITEM_NO     | NUMBER  | 6    |                                                                      |
| 项目类别     | ITEM_CLASS  | VARCHAR | 1    |                                                                      |
| 项目名称     | ITEM_NAME   | VARCHAR | 40   |                                                                      |
| 项目代码     | ITEM_CODE   | VARCHAR | 10   |                                                                      |
| 项目规格     | ITEM_SPEC   | VARCHAR | 20   |                                                                      |
| 单位         | UNIT        | VARCHAR | 8    |                                                                      |
| 原计价金额   | Org_COSTS   | NUMBER  | 10,2 |                                                                      |
| 原应收金额   | Org_CHARGES | NUMBER  | 10,2 |                                                                      |
| 现计价金额   | Cur_COSTS   | NUMBER  | 10,2 |                                                                      |
| 现应收金额   | Cur_CHARGES | NUMBER  | 10,2 |                                                                      |
| 会计科目     | SUBJ_CODE   | VARCHAR | 4    | 价表中对应的会计科目，改：用原计价对应的，增：用新增的，删：用原来的 |
| 记账日期     | TALLY_DATE  | DATE    |      | 生成记帐记录的日期                                                   |
| 记账人       | TABLER      | VARCHAR | 8    |                                                                      |
| 记账号       | TABLER_NO   | NUMBER  | 6    |                                                                      |
| 核查日期     | ENTER_DATE  | DATE    |      |                                                                      |

主键：病人ID，住院次数，项目序号

说明：长期保存。用于保存出院结算病人费用明细发生改变的记录。

## 军队应收辅助账目统计记录表INP_OUTP_COSTS_REC(不使用)

|          |        |      |      |      |
|----------|--------|------|------|------|
| 中文名称 | 字段名 | 类型 | 长度 | 说明 |
|          |        |      |      |      |

## 记账主记录TALLY_MASTER_ACCT

|                |                   |          |      |                                |
|----------------|-------------------|----------|------|--------------------------------|
| 字段中文名称   | 字段名            | 类型     | 长度 | 说明                           |
| 凭证号         | TALLY_NO          | NUMBER   | 6,0  | NULL                           |
| 记账日期       | TALLY_DATE        | DATE     |      |                                |
| 附单据数       | APPEND_RCPT_NUM   | NUMBER   | 3,0  |                                |
| 填制人         | TABLER            | VARCHAR2 | 12   |                                |
| 填制编号       | TABLER_NO         | NUMBER   | 6,0  |                                |
| 审核人         | CHECKER           | VARCHAR2 | 12   |                                |
| 凭证类型       | TALLY_TYPE        | VARCHAR2 | 1    | 正常、转帐                     |
| 入帐标志       | TALLY_INDICATOR   | VARCHAR2 | 1    | 表明为记帐还是入帐             |
| 财务记账人     | TALLY_ACCT_TABLER | VARCHAR2 | 12   |                                |
| 财务凭证号     | TALLY_ACCT_NO     | NUMBER   | 6,0  |                                |
| 操作日期       | ENTER_DATE        | DATE     |      |                                |
| 转记账业务类型 | TALLY_CLASS       | VARCHAR2 | 2    | 见系统定义字典TALLY_CLASS_DICT |

主键：填制人，填制编号。

说明：本表在转记帐时，生成HIS系统的记帐凭证主记录。

## 记账明细记录TALLY_DETAIL_ACCT

|              |                 |          |      |                                                                              |
|--------------|-----------------|----------|------|------------------------------------------------------------------------------|
| 字段中文名称 | 字段名          | 类型     | 长度 | 说明                                                                         |
| 凭证号       | TALLY_NO        | NUMBER   | 6,0  | 暂不用                                                                       |
| 填制人       | TABLER          | VARCHAR2 | 12   | 产生此记录的操作员姓名                                                       |
| 填制编号     | TABLER_NO       | NUMBER   | 6,0  | 操作员的记帐记录序列号。按每个操作员进行递增。                               |
| 分录顺序号   | TALLY_SUB_NO    | NUMBER   | 5,0  | 本次记帐主记录中对应的各个会计明细的序列号                                   |
| 会计科目代码 | SUBJ_CODE       | VARCHAR2 | 10   | 用户定义字典，内容见tally_subject_dict字典                                   |
| 摘要         | SUMMARY         | VARCHAR2 | 48   |                                                                              |
| 单位代码     | UNIT_CODE       | VARCHAR2 | 12   | 见会计核算系统中的说明，对于只有一个会计核算单元的单位来说，此编码同部门代码 |
| 部门代码     | DEPT_CODE       | VARCHAR2 | 8    |                                                                              |
| 项目代码     | ITEM_CODE       | VARCHAR2 | 8    | 暂不用                                                                       |
| 借贷         | DEBIT_OR_CREDIT | VARCHAR2 | 1    | 0－借，1－贷                                                                 |
| 栏次         | COL_ID          | VARCHAR2 | 1    | 暂不用                                                                       |
| 金额         | AMOUNT          | NUMBER   | 13,2 |                                                                              |

主键：填制人，填制编号，分录顺序号

说明：本表按会计科目分类记录医疗费用发生与收入情况。长期保存。由“预交金／门诊／住院收款“、“地方应收住院病人医药费“、“应收住院医药费记帐结果核查模块“产生。

## 欠费登记表ARREAR_REC

|              |                     |      |      |      |
|--------------|---------------------|------|------|------|
| 字段中文名   | 字段名              | 类型 | 长度 | 说明 |
| 病人ID       | PATIENT_ID          | C    | 10   |      |
| 住院次数     | VISIT_ID            | N    | 2    |      |
| 姓名         | PATIENT_NAME        | C    | 20   |      |
| 累计金额     | CHARGES             | N    | 10,2 |      |
| 预交金       | PREPAY_MONEYS       | N    | 10,2 |      |
| 回收金额     | RECLAIM_MONEYS      | N    | 10,2 |      |
| 欠费原因     | UNSETTLE_RESULT     | C    | 40   |      |
| 输入日期     | ENTER_DATE          | D    |      |      |
| 操作员       | OPERATOR            | C    | 8    |      |
| 入院科室     | DEPT_ADMISSION_TO   | C    | 8    |      |
| 出院科室     | DEPT_DISCHARGE_FROM | C    | 8    |      |
| 入院时间     | ADMISSION_DATE      | D    |      |      |
| 出院时间     | DISCHARGE_DATE      | D    |      |      |
| 预交金收据数 | PREPAY_NUMS         | N    | 2    |      |
| 欠费金额     | ARREARGE            | N    | 10,2 |      |
| 核销标志     | CANCEL_FLOG         | C    | 1    |      |
| 催欠情况     | URGE_CIRCS          | C    | 40   |      |
| 核销时间     | CANCEL_DATE         | D    |      |      |
| 核销操作员   | CANCEL_OPER         | C    | 8    |      |
| 欠费收据号   | RCPT_NO             | C    | 8    |      |

## 回收明细表RECLAIM_REC

|            |               |      |      |      |
|------------|---------------|------|------|------|
| 中文名称   | 字段名        | 类型 | 长度 | 说明 |
| 病人ID     | PATIENT_ID    | C    | 10   |      |
| 住院次数   | VISIT_ID      | N    | 2    |      |
| 回收序号   | RECLAIM_NO    | N    | 2    |      |
| 欠费金额   | ARREARGE      | N    | 10,2 |      |
| 回收金额   | RECLAIM_MONEY | N    | 10,2 |      |
| 回收收据号 | RE_ACCT_NO    | C    | 14   |      |
| 回收时间   | RECLAIM_DATE  | D    |      |      |
| 操作员     | OPERATOR      | C    | 8    |      |

## 欠费记账主记录ARREAR_TALLY_MASTER(不使用)

|          |        |      |      |      |
|----------|--------|------|------|------|
| 中文名称 | 字段名 | 类型 | 长度 | 说明 |
|          |        |      |      |      |

## 欠费记账明细记录ARREAR_TALLY_DETAIL(不使用)

|          |        |      |      |      |
|----------|--------|------|------|------|
| 中文名称 | 字段名 | 类型 | 长度 | 说明 |
|          |        |      |      |      |

## 军队应收辅助项目统计INP_OUTP_FREE_COSTS

|          |                    |      |      |      |
|----------|--------------------|------|------|------|
| 中文名称 | 字段名             | 类型 | 长度 | 说明 |
|          | ST_DATE            | D    |      |      |
|          | ADJUST_INDCT       | C    | 1    |      |
|          | INP_OUTP_INDICATOR | C    | 1    |      |
|          | ARMY_INDICATOR     | C    | 1    |      |
|          | ITEM_CLASS         | C    | 4    |      |
|          | AMOUNT             | N    | 10,2 |      |
|          | ACCT_OPERATOR      | C    | 8    |      |

## 报表名称字典REPORT_CODE_DICT

|          |                 |      |      |      |
|----------|-----------------|------|------|------|
| 中文名称 | 字段名          | 类型 | 长度 | 说明 |
|          | SERICAL_NO      | N    | 4    |      |
|          | REPORT_ID       | C    | 4    |      |
|          | REPORT_NAME     | C    | 60   |      |
|          | REPORT_TYPE     | C    | 1    |      |
|          | USE_CODE        | C    | 6    |      |
|          | USE_DEPT_NAME   | C    | 60   |      |
|          | TALLY_DEPT_NAME | C    | 80   |      |
|          | TALLY_NAME      | C    | 8    |      |
|          | EXCEPTION       | C    | 80   |      |

## 报表对应会计科目字典REPORT_ITEM_DICT

|          |            |      |      |      |
|----------|------------|------|------|------|
| 中文名称 | 字段名     | 类型 | 长度 | 说明 |
|          | SERICAL_NO | N    | 4    |      |
|          | REPORT_ID  | C    | 4    |      |
|          | SUBJ_NAME  | C    | 36   |      |
|          | SUBJ_CODE  | C    | 10   |      |
|          | LEND_FEE   | N    | 12,2 |      |
|          | BORROW_FEE | N    | 12,2 |      |
|          | BLANCE_FEE | N    | 12,2 |      |
|          | TOTAL_BZ   | C    | 1    |      |

## 药品转记账接口表DRUG_MATERIAL_VS_ACCT

|          |                      |      |      |      |
|----------|----------------------|------|------|------|
| 中文名称 | 字段名               | 类型 | 长度 | 说明 |
|          | DRUG_OR_MATERIAL     | C    | 1    |      |
|          | RCPT_TYPE            | C    | 8    |      |
|          | RCPT_CLASS           | C    | 8    |      |
|          | STORAGE_CODE         | C    | 8    |      |
|          | SUB_STORAGE          | C    | 8    |      |
|          | SUPPLIER_OR_RECEIVER | C    | 20   |      |
|          | HIS_SUBJECT          | C    | 40   |      |
|          | DEBIT_OR_CREDIT      | C    | 1    |      |
|          | SUBJ_CODE            | C    | 10   |      |
|          | SUBJ_NAME            | C    | 36   |      |
|          | SUMMARY              | C    | 48   |      |

## DRUG_MATERIAL_TALLY_REC

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
|          | DOCUMENT_NO   | C    | 10   |      |
|          | TALLY_DATE    | D    |      |      |
|          | ACCOUNT_PAYED | N    | 10,2 |      |
|          | TABLER        | C    | 12   |      |
|          | TABLER_NO     | N    | 6    |      |

## 发票分配记录INVOICE_MANAGE_REC

|            |                 |      |      |                                               |
|------------|-----------------|------|------|-----------------------------------------------|
| 中文名称   | 字段名          | 类型 | 长度 | 说明                                          |
| 分配人     | OPERATOR_NO     | C    | 10   |                                               |
| 分配日期   | PROVIDE_DATE    | D    |      |                                               |
| 发票类型   | FLAG            | C    | 6    | 1住院发票、2门诊发票、3挂号发票 4、预交金发票 |
| 前缀       | PREFIX          | C    | 6    |                                               |
| 后缀       | SUFFIX          | C    | 2    |                                               |
| 长度       | SEQUENCE_LENGTH | N    | 2    |                                               |
| 最大号     | MAX_NO          | N    | 12   |                                               |
| 最小号     | MIN_NO          | N    | 12   |                                               |
| 当前号     | CURR_NO         | N    | 12   |                                               |
| 使用状态   | USING_STATUS    | C    | 1    | 1待用 2使用 3停用 4 回收                      |
| 收款员代码 | CASHER_NO       | C    | 16   |                                               |

## 欠费回收支付记录RECLAIM_MONEY

|            |              |      |      |      |
|------------|--------------|------|------|------|
| 中文名称   | 字段名       | 类型 | 长度 | 说明 |
| 回收收据号 | RE_ACCT_NO   | C    | 14   |      |
| 支付方式   | PAY_WAY_CODE | C    | 1    |      |
| 支付金额   | PAY_MONEY    | N    | 10,2 |      |
| 银行名称   | BANK         | C    | 30   |      |
| 支票号码   | CHECK_NO     | C    | 16   |      |

#  医务统计用数据中间库

## 门诊工作量月统计记录 QU_OUTP_CLINIC_NUM

|              |                 |      |      |                                          |
|--------------|-----------------|------|------|------------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                     |
| 统计年月     | YEAR_MONTH      | D    |      | 为表中各项数据统计区间(统计年月)，非空   |
| 科室编码     | DEPT_CODE       | C    | 8    | 见2.6科室字典，非空                      |
| 门诊类别     | CLINIC_TYPE     | C    | 8    | 见3.5门诊类别字典                        |
| 患者身份     | IDENTITY        | C    | 10   | 见1.6身份字典                            |
| 门诊人次     | OUTP_NUM        | N    | 5    | 指对应科室、门诊类别及患者身份的门诊人次 |
| 手术人次     | OPERATED_NUM    | N    | 4    | 指对应科室、门诊类别及患者身份的手术人次 |
| 健康检查人数 | HEALTH_EXAM_NUM | n    | 4    |                                          |
| 门诊下地人数 | DOWN_TEERA_NUM  | n    | 4    |                                          |

注释：此表是门诊工作量的月统计记录，由医务统计子系统每月从就诊记录产生。

数据年增长量为12\*门诊类别数\*门诊科室数\*身份种类数，长期在线保存。

主键：统计年月、科室编码、门诊类别、患者身份

## 急诊工作月统计记录 QU_EMERGENCY_NUM

|              |                       |      |      |                                        |
|--------------|-----------------------|------|------|----------------------------------------|
| 字段中文名称 | 字段名                | 类型 | 长度 | 说明                                   |
| 统计年月     | YEAR_MONTH            | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 科室编码     | DEPT_CODE             | C    | 8    | 见2.6科室字典，非空                    |
| 患者身份     | IDENTITY              | C    | 10   | 见1.6身份字典                          |
| 急诊人次     | EMERGENCY_NUM         | N    | 5    | 指对应科室及患者身份的急诊人次         |
| 抢救人数     | RESCUED_NUM           | N    | 4    | 指对应科室及患者身份的抢救人数         |
| 抢救脱险人数 | RES_SUC_NUM           | N    | 4    | 抢救人数中的脱险人数                   |
| 收容人数     | ADMITTED_NUM          | N    | 4    | 指急诊收容住院人数                     |
| 留观人数     | ADMITTED_OBSERV_NUM   | N    | 4    | 指急诊收容留观人数                     |
| 诊前死亡人数 | DIED_WHEN_ARRIVED_NUM | N    | 2    | 指急诊到来时已死亡人数                 |
| 留观死亡人数 | DIED_IN_OBSERV_NUM    | N    | 2    | 指留观期间死亡人数                     |
| 急诊死亡人数 | DIED_IN_CLINIC_NUM    | N    | 2    | 指急诊过程中死亡人数                   |
| 手术人数     | OPERATED_NUM          | N    | 4    | 指对应急诊人次中的抢救人数             |

注释：此表是急诊工作数质量的月统计记录。

数据年增长量为12\*急诊科室数\*身份种类数，长期在线保存。

主键：统计年月、科室编码、患者身份

## 住院科室工作效率月统计记录 QU_EFFCIENCY_DEPT

|                  |                          |      |      |                                        |
|------------------|--------------------------|------|------|----------------------------------------|
| 字段中文名称     | 字段名                   | 类型 | 长度 | 说明                                   |
| 统计年月         | YEAR_MONTH               | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 科室编码         | DEPT_CODE                | C    | 8    | 见2.6科室字典，非空                    |
| 住院者身份       | IDENTITY                 | C    | 10   | 见1.6身份字典                          |
| 原有人数         | ORIGINAL_NUM             | N    | 4    |                                        |
| 门诊入院人数     | ADMITTED_OUTPS           | N    | 4    |                                        |
| 急诊入院人数     | ADMITTED_EMERGENCY       | N    | 4    |                                        |
| 他院转入人数     | ADMITTED_OTHER_HOSPITALS | N    | 4    |                                        |
| 他科转入人数     | FROM_OTHER_DEPT          | N    | 4    |                                        |
| 出院者住院总日数 | TOTAL_IN_HOSPITAL_DAYS   | N    | 5    |                                        |
| 术前住院总日数   | TOTAL_BEF_OPER_DAYS      | N    | 5    |                                        |
| 术前在科总日数   | IN_DEPT_DAYS_OPER        | N    | 5    |                                        |
| 正常出院者人数   | DISCHARGE_NUM            | N    | 4    |                                        |
| 出科者在科总日数 | TOTAL_IN_DEPT_DAYS       | N    | 5    |                                        |
| 转院者人数       | TRANS_TO_HOSPITAL_NUM    | N    | 3    |                                        |
| 死亡人数         | DIED_NUM                 | N    | 3    |                                        |
| 转他科人数       | TRANS_DEPT_NUM           | N    | 4    |                                        |
| 手术治疗人数     | OPER_TREAT_NUM           | N    | 4    | 统计区间内经手术治疗的出院人数         |
| 占用床位总日数   | TOTAL_BED_USED_DAYS      | N    | 4    |                                        |

注释：此表是住院科室医疗工作效率的月统计记录，由医务统计子系统从病人住院主记录、手术记录、床位记录产生。

数据年增长量为12\*住院科室数\*身份种类数，长期在线保存。

主键：统计年月、科室编码、住院者身份

按住院者科室合计，建立如下视图：

## 住院科室工作效率月统计记录 DEPT_EFFCIENCY

|                      |                     |      |      |                                                      |
|----------------------|---------------------|------|------|------------------------------------------------------|
| 字段中文名称         | 字段名              | 类型 | 长度 | 说明                                                 |
| 统计年月             | YEAR_MONTH          | D    |      | 对应YEAR_MONTH                                       |
| 科室编码             | DEPT_CODE           | C    | 8    | 对应DEPT_CODE                                        |
| 出院者住院总日数     | TOTAL_INP_DAYS      | N    | 5    | 对应TOTAL_IN_HOSPITAL_DAYS                           |
| 术前住院总日数       | BEF_OPER_DAYS       | N    | 5    | 对应TOTAL_BEF_OPER_DAYS                              |
| 出院总人数           | TOTAL_DISCHARGE_NUM | N    | 4    | 对应DISCHARGE_NUM + TRANS_TO_HOSPITAL_NUM + DIED_NUM |
| 手术治疗人数         | OPERATED_NUM        | N    | 4    | 对应OPER_TREAT_NUM                                   |
| 转他科人数           | TO_DEPT             | N    | 4    | 对应TRANS_DEPT_NUM                                   |
| 出科者在科总日数     | IN_DEPT_DAYS        | N    | 5    | 对应TOTAL_IN_DEPT_DAYS                               |
| 出科者术前在科总日数 | BEF_OPER_DEPT_DAYS  | N    | 5    | 对应IN_DEPT_DAYS_OPER                                |
| 占用床位总日数       | USED_BED_DAYS       | N    | 4    | 对应TOTAL_BED_USED_DAYS                              |

## 科室治疗质量月统计记录 QU_THERAPY_QLTY_DEPT

|                  |                          |      |      |                                                    |
|------------------|--------------------------|------|------|----------------------------------------------------|
| 字段中文名称     | 字段名                   | 类型 | 长度 | 说明                                               |
| 统计年月         | YEAR_MONTH               | D    |      | 为表中各项数据统计区间(统计年月)，非空             |
| 科室编码         | DEPT_CODE                | C    | 8    | 见2.6科室字典，非空                                |
| 住院者身份       | IDENTITY                 | C    | 10   | 见1.6身份字典                                      |
| 抢救次数         | RESCUE_NUM               | N    | 4    |                                                    |
| 抢救成功次数     | RES_SUC_NUM              | N    | 3    |                                                    |
| 治愈人数         | RECOVER_NUM              | N    | 3    | 统计区间内出院患者出院第一诊断治疗结果为治愈的人数 |
| 好转人数         | EFFECT_NUM               | N    | 3    | 统计区间内出院患者出院第一诊断治疗结果为好转的人数 |
| 无效人数         | INVALED_NUM              | N    | 3    | 统计区间内出院患者出院第一诊断治疗结果为无效的人数 |
| 未治人数         | UNTREATED_NUM            | N    | 3    | 统计区间内出院患者出院第一诊断治疗结果为未治的人数 |
| 死亡人数         | DIED_NUM                 | N    | 3    | 统计区间内出院患者出院第一诊断治疗结果为死亡的人数 |
| 其他结果人数     | OTHER_NUM                | N    | 3    | 统计区间内出院患者出院第一诊断治疗结果为其他的人数 |
| 治愈者住院总日数 | RECOVER_IN_HOSPITAL_DAYS | N    | 6    |                                                    |

注释：此表是住院科室医疗工作质量的月统计记录，由医务统计子系统从病人住院主记录、诊断记录产生。

数据年增长量为12\*住院科室数\*身份种类数，长期在线保存。

主键：统计年月、科室编码、住院者身份

## 手术科室数质量月统计记录 QU_OPERATION_DEPT

|                  |                  |      |      |                                        |
|------------------|------------------|------|------|----------------------------------------|
| 字段中文名称     | 字段名           | 类型 | 长度 | 说明                                   |
| 统计年月         | YEAR_MONTH       | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 科室编码         | DEPT_CODE        | C    | 8    | 见2.6科室字典，非空                    |
| 特大手术例数     | GREAT_OPER_NUM   | N    | 3    |                                        |
| 大手术例数       | MAJOR_OPER_NUM   | N    | 3    |                                        |
| 中手术例数       | MEDIUM_OPER_NUM  | N    | 3    |                                        |
| 小手术例数       | MINOR_OPER_NUM   | N    | 3    |                                        |
| 手术切口愈合Ⅰ/甲 | FIR_FIR_HEAL_NUM | N    | 3    |                                        |
| 手术切口愈合Ⅰ/乙 | FIR_SEC_HEAL_NUM | N    | 3    |                                        |
| 手术切口愈合Ⅰ/丙 | FIR_THI_HEAL_NUM | N    | 3    |                                        |
| 手术切口愈合Ⅱ/甲 | SEC_FIR_HEAL_NUM | N    | 3    |                                        |
| 手术切口愈合Ⅱ/乙 | SEC_SEC_HEAL_NUM | N    | 3    |                                        |
| 手术切口愈合Ⅱ/丙 | SEC_THI_HEAL_NUM | N    | 3    |                                        |
| 手术切口愈合Ⅲ/甲 | THI_FIR_HEAL_NUM | N    | 3    |                                        |
| 手术切口愈合Ⅲ/乙 | THI_SEC_HEAL_NUM | N    | 3    |                                        |
| 手术切口愈合Ⅲ/丙 | THI_THI_HEAL_NUM | N    | 3    |                                        |

注释：此表是手术科室医疗工作的月统计记录，由医务统计子系统从手术记录产生。

数据年增长量为12\*手术科室数，长期在线保存。

主键：统计年月、科室编码

## 科室医疗管理质量月统计记录 QU_MANAGE_QLTY_DEPT

|                      |                      |      |      |                                             |
|----------------------|----------------------|------|------|---------------------------------------------|
| 字段中文名称         | 字段名               | 类型 | 长度 | 说明                                        |
| 统计年月             | YEAR_MONTH           | D    |      | 为表中各项数据统计区间(统计年月)，非空      |
| 科室编码             | DEPT_CODE            | C    | 8    | 见2.6科室字典，非空                         |
| 手术并发症例数       | OPER_COM_NUM         | N    | 2    |                                             |
| 非手术并发症例数     | NONOPER_COMP_NUM     | N    | 2    |                                             |
| 院内感染发生例数     | HOSPITAL_INFECT_NUM  | N    | 2    |                                             |
| 无菌手术切口感染例数 | ASEP_OPER_INFECT_NUM | N    | 2    | 无菌手术切口（I级切口）感染（丙级愈合）例数 |

注释：此表是科室医疗管理质量的月统计记录。由医务统计子系统从病人在科记录、手术记录、诊断记录产生，部分不能直接从系统中得到的数据，由相应管理部门录入。

数据年增长量为12\*手术科室数，长期在线保存。

主键：统计年月、科室编码

## 独立核算科室医疗收入月统计记录 QU_ACCOUNT_INDEP

|              |              |      |      |                                        |
|--------------|--------------|------|------|----------------------------------------|
| 字段中文名称 | 字段名       | 类型 | 长度 | 说明                                   |
| 统计年月     | YEAR_MONTH   | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 核算科室编码 | ACCOUNT_DEPT | C    | 8    | 见2.6科室字典，非空                    |
| 实际收入     | REAL_INCOME  | N    | 10,2 | 不包括军人及其免减家属被减免的部分费用 |
| 计价收入     | COUNT_INCOME | N    | 10,2 | 军人及其免减家属被减免的部分费用       |

注释：此表是独立核算科室医疗收入的月统计记录。由医务统计子系统从门诊医疗收据记录、门诊病人诊疗费用项目、住院病人费用明细记录产生。

数据年增长量为12\*独立核算科室数，长期在线保存。

主键：统计年月、科室编码

## 核算项目医疗收入月统计记录 QU_ACCOUNT_ITEM

|              |                   |      |      |                                        |
|--------------|-------------------|------|------|----------------------------------------|
| 字段中文名称 | 字段名            | 类型 | 长度 | 说明                                   |
| 统计年月     | YEAR_MONTH        | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 核算项目编码 | ACCOUNT_ITEM      | C    | 3    | 见6.12核算项目分类字典                 |
| 住院实际收入 | INP_REAL_INCOME   | N    | 10,2 | 不包括军人及其免减家属被减免的部分费用 |
| 住院计价收入 | INP_COUNT_INCOME  | N    | 10,2 | 军人及其免减家属被减免的部分费用       |
| 门诊实际收入 | OUTP_REAL_INCOME  | N    | 10,2 | 不包括军人及其免减家属被减免的部分费用 |
| 门诊计价收入 | OUTP_COUNT_INCOME | N    | 10,2 | 军人及其免减家属被减免的部分费用       |

注释：此表是按核算项目医疗收入的月统计记录。由医务统计子系统从门诊医疗收据记录、门诊病人诊疗费用项目、住院病人费用明细记录、价表产生。

数据年增长量为12\*核算项目数，长期在线保存。

主键：统计年月、科室编码

## 特诊检查工作量月统计记录 QU_EXAM_DEPT

|              |               |      |      |                                        |
|--------------|---------------|------|------|----------------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                                   |
| 统计年月     | YEAR_MONTH    | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 科室编码     | DEPT_CODE     | C    | 8    | 见2.6科室字典，非空                    |
| 检查类别     | EXAM_CLASS    | C    | 6    | 见3.3检查类别字典，非空                |
| 完成数量     | EXAM_SUBCLASS | C    | 8    |                                        |
| 其中阳性数量 | COMPLETED_NUM | N    | 4    |                                        |
|              | ABNORMAL_NUM  | N    | 4    |                                        |

注释：此表是特诊检查工作量的月统计记录。由医务统计子系统从检查主记录、检查报告统计产生。

数据年增长量为12\*统计科室数，长期在线保存。

主键：统计年月、科室编码、检查类别

## 检验工作量月统计记录 QU_TEST_DEPT

|              |               |      |      |                                                 |
|--------------|---------------|------|------|-------------------------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                                            |
| 统计年月     | YEAR_MONTH    | D    |      | 为表中各项数据统计区间(统计年月)，非空          |
| 科室编码     | DEPT_CODE     | C    | 8    | 见2.6科室字典，非空                             |
| 项目类别     | ITEM_CLASS    | C    | 8    | 检验项目所属类别，使用中文                      |
| 项目编码     | ITEM_CODE     | C    | 10   | 见4.8检验项目字典。若为“\*”，表示该科室总工作量 |
| 完成数量     | COMPLETED_NUM | N    | 6    |                                                 |
| 其中阳性数量 | ABNOMAL_NUM   | N    | 6    |                                                 |

注释：此表是检验工作量的月统计记录。由医务统计子系统从检验主记录、检验报告统计产生。

数据年增长量为12\*检验科室数\*科室平均项目数，长期在线保存。

主键：统计年月、科室编码、项目编码

## 辅诊辅疗工作量月统计记录 QU_ASST_TREAT_DEPT

|              |              |      |      |                                                      |
|--------------|--------------|------|------|------------------------------------------------------|
| 字段中文名称 | 字段名       | 类型 | 长度 | 说明                                                 |
| 统计年月     | YEAR_MONTH   | D    |      | 为表中各项数据统计区间(统计年月)，非空               |
| 科室编码     | DEPT_CODE    | C    | 8    | 见2.6科室字典，非空                                  |
| 项目编码     | ITEM_CODE    | C    | 8    | 见4.24辅助治疗项目字典。若为“\*”，表示该科室总工作量 |
| 治疗人次     | TREAT_NUM    | N    | 5    |                                                      |
| 有效率       | EFFECT_RATIO | N    | 5,2  |                                                      |

注释：此表是辅疗工作量的月统计记录。由医务统计子系统录入。

数据年增长量为12\*诊疗科室数\*科室平均项目数，长期在线保存。

主键：统计年月、科室编码、项目编码

## 医院等级评审质量指标完成情况统计记录 QU_QUALITY_COMPLETED

|              |                 |      |      |                                        |
|--------------|-----------------|------|------|----------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                   |
| 统计年月     | YEAR_MONTH      | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 指标编码     | INDEX_CODE      | C    | 2    | 见医院等级评审质量指标标准             |
| 完成值       | COMPLETED_VALUE | C    | 9    | 完成值中包括\<=和%符号                 |

注释：此表是医院等级评审质量指标完成情况记录。

## 医院医疗工作计划完成情况统计记录 QU_PLAN_COMPLETED

|              |                 |      |      |                                        |
|--------------|-----------------|------|------|----------------------------------------|
| 字段中文名称 | 字段名          | 类型 | 长度 | 说明                                   |
| 统计年月     | YEAR_MONTH      | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 计划指标编码 | PLAN_CODE       | C    | 10   | 见医院医疗工作计划指标，非空           |
| 完成值       | COMPLETED_VALUE | N    | 8,2  | 完成的数量                             |

注释：此表是医院医疗工作计划指标完成情况记录。

## 门诊综合数据月统计记录 QU_OUTP_SYNTHESIZE

|                              |                        |      |      |                                        |
|------------------------------|------------------------|------|------|----------------------------------------|
| 字段中文名称                 | 字段名                 | 类型 | 长度 | 说明                                   |
| 统计年月                     | YEAR_MONTH             | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 实际工作日数                 | WORK_DAYS              | N    | 2    | 实际门诊日数                           |
| 医师门诊工作总日数           | DOCTOR_WORK_TOTAL_DAYS | N    | 3    | 各级医师门诊工作总日数                 |
| 副主任医师以上门诊工作总日数 | HIGH_LEVEL_WORK_DAYS   | N    | 3    |                                        |
| 体检人数                     | PHYSICAL_NUM           | N    | 5    |                                        |
| 出诊人次                     | HOUSE_CALL_NUM         | N    | 3    |                                        |

注释：此表是门诊综合数据的月统计记录。

主键：统计年月

## 住院科室工作负荷月统计记录 QU_LOAD_DEPT

|                |                         |      |      |                                        |
|----------------|-------------------------|------|------|----------------------------------------|
| 字段中文名称   | 字段名                  | 类型 | 长度 | 说明                                   |
| 统计年月       | YEAR_MONTH              | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 科室编码       | DEPT_CODE               | C    | 8    | 见2.6科室字典，非空                    |
| 特级护理总人日 | SPEC_NURS_TOTAL_DAYS    | N    | 4    |                                        |
| 一级护理总人日 | FIRST_NURS_TOTAL_DAYS   | N    | 4    |                                        |
| 危重总人日数   | CRITICAL_TOTAL_PER_DAYS | N    | 4    |                                        |

注释：此表是科室医疗工作负荷的月统计记录。由统计子系统从病人入出转及状态变化日志、住院科室医疗负荷统计日记录中产生。

数据年增长量为12\*临床科室数，长期在线保存。

主键：统计年月、科室编码

## 住院科室床位使用情况月统计记录 QU_DEPT_BED_REC

|                  |                |      |      |                                        |
|------------------|----------------|------|------|----------------------------------------|
| 字段中文名称     | 字段名         | 类型 | 长度 | 说明                                   |
| 统计年月         | YEAR_MONTH     | D    |      | 为表中各项数据统计区间(统计年月)，非空 |
| 科室编码         | DEPT_CODE      | C    | 8    | 见2.6科室字典，非空                    |
| 床位未使用天数   | BED_NOUSED_NUM | N    | 4    |                                        |
| 实际床位使用天数 | REAL_BED_NUM   | N    | 4    |                                        |

注释：此表是科室床位使用情况月统计记录。

主键：统计年月、科室编码

## 临床医疗工作计划指标 PLAN_INDEX

|              |            |      |      |                      |
|--------------|------------|------|------|----------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                 |
| 计划年月     | YEAR_MONTH | D    |      | 实施计划的年月，非空 |
| 科室编码     | DEPT_CODE  | C    | 8    | 见2.6科室字典，非空  |
| 计划指标编码 | PLAN_CODE  | C    | 10   | 系统定义，非空       |
| 计划值       | PLAN_VALUE | N    | 8    | 计划完成的数量       |

注释：此表是临床医疗工作计划指标记录。

## 医技科室工作数量计划指标 ASST_PLAN_INDEX

|              |            |      |      |                      |
|--------------|------------|------|------|----------------------|
| 字段中文名称 | 字段名     | 类型 | 长度 | 说明                 |
| 计划年月     | YEAR_MONTH | D    |      | 实施计划的年月，非空 |
| 科室编码     | DEPT_CODE  | C    | 8    | 见2.6科室字典，非空  |
| 计划指标编码 | PLAN_CODE  | C    | 10   | 系统定义，非空       |
| 计划值       | PLAN_VALUE | N    | 8    | 计划完成的数量       |

注释：此表是医技工作数量计划指标记录。

## 科室门诊工作量日统计记录 DEPT_OUTP_NUM_DAY

|                      |                       |      |      |                                          |
|----------------------|-----------------------|------|------|------------------------------------------|
| 字段中文名称         | 字段名                | 类型 | 长度 | 说明                                     |
| 统计日期             | ST_DATE               | D    |      | 非空                                     |
| 科室编码             | DEPT_CODE             | C    | 8    | 见2.6科室字典，非空                      |
| 门诊类别             | CLINIC_TYPE           | C    | 8    | 见3.5门诊类别字典                        |
| 患者身份             | IDENTITY              | C    | 10   | 见1.6身份字典                            |
| 门诊人次             | OUTP_NUM              | N    | 5    | 指对应科室、门诊类别及患者身份的门诊人次 |
| 手术人次             | OPERATED_NUM          | N    | 4    | 指对应科室、门诊类别及患者身份的手术人次 |
| 主治医以上出门诊人次 | ATTENDING_UP_OUTP_NUM | N    | 6    |                                          |
| 专家门诊人次         | SPECIALIST_OUTP_NUM   | N    | 6    |                                          |
| 健康检查人数         | HEALTH_EXAM_NUM       | N    | 6    |                                          |
| 门诊下地方人数       | DOWN_TEERA_NUM        | N    | 4    |                                          |
| 总出诊人数           | TOTAL_OUTP_NUM        | N    | 4    |                                          |

注释：此表是科室门诊工作量的日统计记录，由医务统计子系统从就诊记录产生。

数据月增长量为31\*门诊类别数\*门诊科室数\*身份种类数，保存一个月。

主键：统计日期、科室编码、门诊类别、患者身份

## 急诊工作日统计记录 EMERGENCY_DAY

|                |                       |      |      |                                |
|----------------|-----------------------|------|------|--------------------------------|
| 字段中文名称   | 字段名                | 类型 | 长度 | 说明                           |
| 统计日期       | ST_DATE               | D    |      | 非空                           |
| 科室编码       | DEPT_CODE             | C    | 8    | 见2.6科室字典，非空            |
| 患者身份       | IDENTITY              | C    | 10   | 见1.6身份字典                  |
| 急诊人数       | EMERGENCY_NUM         | N    | 2    | 指对应科室及患者身份的急诊人数 |
| 抢救人数       | RESCUED_NUM           | N    | 2    | 指对应科室及患者身份的抢救人数 |
| 抢救脱险人数   | RES_SUC_NUM           | N    | 2    | 抢救人数中的脱险人数           |
| 收容人数       | ADMITTED_NUM          | N    | 2    | 指急诊收容住院人数             |
| 留观人数       | ADMITTED_OBSERV_NUM   | N    | 2    | 指急诊收容留观人数             |
| 诊前死亡人数   | DIED_WHEN_ARRIVED_NUM | N    | 2    | 指急诊到来时已死亡人数         |
| 留观死亡人数   | DIED_IN_OBSERV_NUM    | N    | 2    | 指留观期间死亡人数             |
| 急诊死亡人数   | DIED_IN_CLINIC_NUM    | N    | 2    | 指急诊过程中死亡人数           |
| 手术人数       | OPERATED_NUM          | N    | 2    | 指对应急诊人次中的抢救人数     |
| 出观察室人次数 | OUT_OBSERV_NUM        | N    | 4    |                                |
| 急诊实有病床数 | EMEYGENCY_BED_SUM     | N    | 4    |                                |
| 急诊就诊量     | EMER_CLINIC_NUM       | N    | 5    | 就诊人数                       |

注释：此表是急诊工作数质量的日统计记录。

数据月增长量为31\*急诊科室数\*身份种类数，长期在线保存。

主键：统计日期、科室编码、患者身份

## 科室伤病员流动日统计记录 DEPT_ADT_DAY

|                |                         |      |      |                     |
|----------------|-------------------------|------|------|---------------------|
| 字段中文名称   | 字段名                  | 类型 | 长度 | 说明                |
| 统计日期       | ST_DATE                 | D    |      | 非空                |
| 科室编码       | DEPT_CODE               | C    | 8    | 见2.6科室字典，非空 |
| 住院者身份     | IDENTITY                | C    | 10   | 见1.6身份字典       |
| 门急诊入院人数 | ADM_OUTP_NUM            | N    | 4    |                     |
| 他科转入人数   | FROM_OTHER_DEPT_NUM     | N    | 3    |                     |
| 他院转入人数   | FROM_OTHER_HOSPITAL_NUM | N    | 3    |                     |
| 正常出院人数   | DISCHARGE_NORMAL_NUM    | N    | 3    |                     |
| 转他科人数     | TRANS_DEPT_NUM          | N    | 3    |                     |
| 转他院人数     | TRANS_HOSPITAL_NUM      | N    | 3    |                     |
| 死亡人数       | DIED_NUM                | N    | 3    |                     |
| 占用床位数     | BED_USED_NUM            | N    | 3    |                     |
| 病危人数       | CRITICAL_COND_NUM       | N    | 3    |                     |
| 手术人数       | Operation_num           | N    | 3    |                     |
| 抢救人次       | EMER_TREAT_NUM          | N    | 3    |                     |

注释：此表是科室伤病员流动日记录，由医务统计子系统从病人住院主记录、病人入出转及状态变化日志、床位记录产生。

数据月增长量为31\*住院科室数\*身份种类数，保存时间半年。

主键：统计日期、科室编码、患者身份

按住院者身份分类统计建立如下视图：

## 科室伤病员流动日统计记录 DEPT_ADT

|                |                     |      |      |                             |
|----------------|---------------------|------|------|-----------------------------|
| 字段中文名称   | 字段名              | 类型 | 长度 | 说明                        |
| 统计日期       | ST_DATE             | D    |      | 对应ST_DATE                 |
| 科室编码       | DEPT_CODE           | C    | 8    | 对应DEPT_CODE               |
| 门急诊入院人数 | ADM_OUTP            | N    | 4    | 对应ADM_OUTP_NUM            |
| 他科转入人数   | FROM_DEPT_NUM       | N    | 3    | 对应FROM_OTHER_DEPT_NUM     |
| 他院转入人数   | ADM_OTHER_HOSPITALS | N    | 3    | 对应FROM_OTHER_HOSPITAL_NUM |
| 正常出院人数   | DISCHARGE_NUM       | N    | 3    | 对应DISCHARGE_NORMAL_NUM    |
| 转他科人数     | TO_DEPT_NUM         | N    | 3    | 对应TRANS_DEPT_NUM          |
| 转他院人数     | TO_HOSPITAL_NUM     | N    | 3    | 对应TRANS_HOSPITAL_NUM      |
| 死亡人数       | DIED_NUM            | N    | 3    | 对应DIED_NUM                |
| 占用床位数     | USED_BED_DAYS       | N    | 3    | 对应BED_USED_NUM            |
|                | PRIORITY_NUM        | N    | 3    |                             |

## 空床日统计记录 DEPT_EMPTY_BED

|              |                |      |      |                     |
|--------------|----------------|------|------|---------------------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明                |
| 统计日期     | ST_DATE        | D    |      | 非空                |
| 科室编码     | DEPT_CODE      | C    | 8    | 见2.6科室字典，非空 |
| 空床数       | BED_NOUSED_NUM | N    | 3    | 不包含加床          |
|              | REAL_BED_NUM   | N    | 3    |                     |

注释：此表是科室空床日记录，由医务统计子系统从在院病人记录、病人入出转及状态变化日志、床位记录产生。

## 特诊检查工作量日统计记录 DEPT_EXAM_DAY

|              |               |      |      |                         |
|--------------|---------------|------|------|-------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                    |
| 统计日期     | ST_DATE       | D    |      | 非空                    |
| 科室编码     | DEPT_CODE     | C    | 8    | 见2.6科室字典，非空     |
| 检查类别     | EXAM_CLASS    | C    | 6    | 见3.3检查类别字典，非空 |
| 完成数量     | EXAM_SUBCLASS | C    | 8    |                         |
| 其中阳性数量 | COMPLETED_NUM | N    | 3    |                         |
|              | ABNORMAL_NUM  | N    | 3    |                         |

注释：此表是特诊检查工作量的日统计记录。由医务统计子系统从检查主记录、检查报告统计产生。

数据月增长量为31\*统计科室数，保存一个月。

主键：统计日期、科室编码、检查类别

## 检验工作量日统计记录 DEPT_TEST_DAY

|              |               |      |      |                                                 |
|--------------|---------------|------|------|-------------------------------------------------|
| 字段中文名称 | 字段名        | 类型 | 长度 | 说明                                            |
| 统计日期     | ST_DATE       | D    |      | 非空                                            |
| 科室编码     | DEPT_CODE     | C    | 8    | 见2.6科室字典，非空                             |
| 项目类别     | ITEM_CLASS    | C    | 8    | 检验项目所属类别，使用中文                      |
| 项目编码     | ITEM_CODE     | C    | 10   | 见4.8检验项目字典。若为“\*”，表示该科室总工作量 |
| 完成数量     | COMPLETED_NUM | N    | 4    |                                                 |
| 其中阳性数量 | ABNOMAL_NUM   | N    | 4    |                                                 |

注释：此表是检验工作量的日统计记录。由医务统计子系统从检验主记录、检验报告统计产生。

数据月增长量为31\*检验科室数\*科室平均项目数，保存一个月。

主键：统计日期、科室编码、项目编码

## 辅诊辅疗工作量日统计记录 DEPT_ASST_DAY

|              |           |      |      |                                                      |
|--------------|-----------|------|------|------------------------------------------------------|
| 字段中文名称 | 字段名    | 类型 | 长度 | 说明                                                 |
| 统计日期     | ST_DATE   | D    |      | 非空                                                 |
| 科室编码     | DEPT_CODE | C    | 8    | 见2.6科室字典，非空                                  |
| 项目编码     | ITEM_CODE | C    | 8    | 见4.24辅助治疗项目字典。若为“\*”，表示该科室总工作量 |
| 治疗人次     | TREAT_NUM | N    | 5    |                                                      |

注释：此表是辅疗工作量的日统计记录。由医务统计子系统录入。

数据月增长量为31\*诊疗科室数\*科室平均项目数，保存一个月。

主键：统计日期、科室编码、项目编码

## 住院科室工作负荷日统计记录 DEPT_LOAD_DAY

|              |                |      |      |                     |
|--------------|----------------|------|------|---------------------|
| 字段中文名称 | 字段名         | 类型 | 长度 | 说明                |
| 统计日期     | ST_DATE        | D    |      | 非空                |
| 科室编码     | DEPT_CODE      | C    | 8    | 见2.6科室字典，非空 |
| 危重人数     | CRITICAL_NUM   | N    | 4    |                     |
| 特级护理人数 | SPEC_NURS_NUM  | N    | 4    |                     |
| 一级护理人数 | FIRST_NURS_NUM | N    | 4    |                     |

注释：此表是科室医疗工作负荷的日统计记录。由统计子系统从住院主记录、病人入出转及状态变化日志中产生。

数据月增长量为31\*临床科室数，保存时间半年。

主键：统计日期、科室编码

## 医疗事故差错记录 ACCIDENT_REC

|              |                  |      |      |                                   |
|--------------|------------------|------|------|-----------------------------------|
| 字段中文名称 | 字段名           | 类型 | 长度 | 说明                              |
| 序号         | SERIAL_NO        | N    | 4    | 非空                              |
| 事故差错类型 | ACCIDENT_TYPE    | C    | 4    | 见事故差错类型字典                |
| 事故等级     | ACCIDENT_CLASS   | C    | 1    | 见事故差错等级字典                |
| 发生单位     | OCCUR_DEPT       | C    | 8    | 事故发生科室的代码，见2.6科室字典 |
| 发生日期     | OCCUR_DATE       | D    |      |                                   |
| 病人ID       | PATIENT_ID       | C    | 10   |                                   |
| 病人姓名     | PATIENT_NAME     | C    | 8    |                                   |
| 病人单位     | PATIENT_UNIT     | C    | 40   |                                   |
| 主要责任者   | PERSON_IN_CHARGE | C    | 8    |                                   |
| 定性日期     | IDENTITY_DATE    | D    |      |                                   |
| 主要原因     | CAUSED_BY        | C    | 20   |                                   |
| 后果         | RESULT           | C    | 8    |                                   |
| 定性机构     | IDENTITY_BODY    | C    | 40   |                                   |

注释：此表记录医疗差错事故。

主键：序号

## 医疗工作计划名称字典 PLAN_NAME_DICT

|              |           |      |      |      |
|--------------|-----------|------|------|------|
| 字段中文名称 | 字段名    | 类型 | 长度 | 说明 |
| 计划编码     | PLAN_CODE | C    | 10   | 非空 |
| 计划名称     | PLAN_NAME | C    | 20   | 非空 |

注释：此表是医疗工作数量计划名称字典，用户定义。

主键：计划编码

## 医院等级评审质量指标标准 QUALITY_INDEX_STANDARD

|              |             |      |      |                  |
|--------------|-------------|------|------|------------------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明             |
| 指标编码     | INDEX_CODE  | C    | 2    | 非空             |
| 指标名称     | INDEX_NAME  | C    | 76   | 非空             |
| 指标值       | INDEX_VALUE | C    | 10   | 可包含\<=和%符号 |

注释：此表记录医院等级评审指标，用户定义。

主键：指标编码

## 住院病人疾病分类统计类目字典 DISE_CLASS_STAT_DICT

|               |             |      |      |                                                                          |
|---------------|-------------|------|------|--------------------------------------------------------------------------|
| 字段中文名称  | 字段名      | 类型 | 长度 | 说明                                                                     |
| 疾病统计编码  | STAT_CODE   | C    | 6    | 需分类统计的病种代码                                                     |
| 类目名称      | CLASS_NAME  | C    | 80   | 对应的病种类目名称                                                       |
| ICD-9类目范围 | ICD_9_RANGE | C    | 220  | 以逗号分隔的ICD-9编码或ICD-9编码区间（用-分隔）列表                      |
| 统计等级      | STAT_LEVEL  | C    | 4    | 反映该项统计为哪一级机构所需 1-国家卫生部 2-总医院 3-中心医院 4-驻军医院 |
| 统计序号      | STAT_NO     | C    | 2    |                                                                          |

注释：此表用于记录各级管理机关规定的疾病分类统计项目，用户定义。

主键：疾病统计编码

## 单病种查询条件字典 DISE_QUERY_CONDITION

|              |           |      |      |                                                               |
|--------------|-----------|------|------|---------------------------------------------------------------|
| 字段中文名称 | 字段名    | 类型 | 长度 | 说明                                                          |
| 疾病统计编码 | STAT_CODE | C    | 6    | 需分类统计的病种代码，见住院病人疾病分类统计类目字典          |
| 查询条件     | CONDITION | C    | 1024 | 根据分类统计代码所对应的ICD-9表，生成的WHERE 子句中的条件部分 |

注释：此表用于记录各级管理机关规定的疾病分类统计项目所对应的查询条件，用户定义。

主键：疾病统计编码

## 事故差错类型字典 ACCI_TYPE_DICT

|                  |                |      |      |      |
|------------------|----------------|------|------|------|
| 字段中文名称     | 字段名         | 类型 | 长度 | 说明 |
| 序号             | SERIAL_NO      | N    | 2    |      |
| 事故差错类型代码 | ACCIDENT_CODE  | C    | 2    |      |
| 事故差错类型名称 | ACCI_TYPE_NAME | C    | 8    |      |

注释：本系统定义。

## 事故差错等级字典 ACCI_CLASS_DICT

|                  |                 |      |      |      |
|------------------|-----------------|------|------|------|
| 字段中文名称     | 字段名          | 类型 | 长度 | 说明 |
| 序号             | SERIAL_NO       | N    | 2    |      |
| 事故差错等级代码 | ACCI_CLASS_CODE | C    | 1    |      |
| 事故差错等级名称 | ACCI_CLASS_NAME | C    | 8    |      |

注释：本系统定义。

## 事故差错原因字典 ACCI_REASON_DICT

|              |             |      |      |      |
|--------------|-------------|------|------|------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO   | N    | 4    |      |
| 事故差错原因 | REASON_NAME | C    | 20   |      |

注释：用户定义。

## 事故差错后果字典 ACCI_RESULTED_DICT

|              |             |      |      |      |
|--------------|-------------|------|------|------|
| 字段中文名称 | 字段名      | 类型 | 长度 | 说明 |
| 序号         | SERIAL_NO   | N    | 4    |      |
| 事故差错后果 | RESULT_NAME | C    | 20   |      |

注释：用户定义。

## 特殊统计病种字典 SPECIAL_DISE_DICT

|              |              |      |      |                                                                            |
|--------------|--------------|------|------|----------------------------------------------------------------------------|
| 字段中文名称 | 字段名       | 类型 | 长度 | 说明                                                                       |
| 科室类别     | DEPT         | C    | 1    | 0-内科 1-外科 2-妇产科 3-儿科                                              |
| 序号         | SERIAL_NO    | N    | 2    |                                                                            |
| 病种名称     | DISE_NAME    | C    | 40   | 对参与统计的一类疾病的名称                                                 |
| ICD-9编码    | ICD_9_CODE   | C    | 80   | 指定病种对应的ICD-9编码，允许多个编码，编码之间用逗号分隔，编码区间用-连接 |
| 统计条件     | CONDITION    | C    | 512  | 对应上述ICD-9编码生成的WHERE子句条件                                       |
| 统计类别     | STAT_TYPE    | V    | 2    |                                                                            |
| 病人类别     | PATIENT_TYPE | N    | 22,0 |                                                                            |
| 统计科室代码 | DEPT_CODE    | C    | 8    |                                                                            |

注释：用于定义需统计上报的特殊病种，用户定义。

## 节假日字典HOLIDAY_DICT

|          |              |      |      |      |
|----------|--------------|------|------|------|
| 中文名称 | 字段名       | 类型 | 长度 | 说明 |
| 假日     | HOLIDAY_DATE | D    |      |      |

## STAT_CONFIG

|          |                          |      |      |      |
|----------|--------------------------|------|------|------|
| 中文名称 | 字段名                   | 类型 | 长度 | 说明 |
|          | SERIAL_NO                | N    | 3    |      |
|          | STAT_ITEM                | C    | 16   |      |
|          | STAT_DESCRIPTION         | C    | 40   |      |
|          | UNNEEDED_ADMISSION_CAUSE | C    | 8    |      |

## 统计科室字典STAT_DEPT_DICT

|              |                |      |      |      |
|--------------|----------------|------|------|------|
| 中文名称     | 字段名         | 类型 | 长度 | 说明 |
| 统计科室代码 | STAT_DEPT_CODE | C    | 8    |      |
| 统计科室名称 | STAT_DEPT_NAME | C    | 20   |      |
| 科室代码     | DEPT_CODE      | C    | 8    |      |
| 科室名称     | DEPT_NAME      | C    | 20   |      |
| 显示序号     | REMARK         | C    | 20   |      |

## STAT_DEPT_MODIFYFIX

|          |               |      |      |      |
|----------|---------------|------|------|------|
| 中文名称 | 字段名        | 类型 | 长度 | 说明 |
|          | STAT_DEPTCODE | C    | 8    |      |
|          | STAT_DEPTNAME | C    | 20   |      |
|          | START_DATE    | D    | 7    |      |
|          | ORI_BEDNUM    | N    | 3    |      |
|          | MODIFY_DATE   | D    |      |      |
|          | MODIFY_BEDNUM | N    | 3    |      |
|          | STAT_BC       | C    | 20   |      |

## 统计条件STAT_OPERCLASS_CONDITION

|          |           |      |      |      |
|----------|-----------|------|------|------|
| 中文名称 | 字段名    | 类型 | 长度 | 说明 |
| 统计代码 | STAT_CODE | C    | 2    |      |
| 统计名称 | STAT_NAME | C    | 200  |      |
| 统计条件 | CONDITION | C    | 60   |      |

## 统计报表用付费方式STAT_VS_CHARGE_TYPE

|              |             |      |      |      |
|--------------|-------------|------|------|------|
| 中文名称     | 字段名      | 类型 | 长度 | 说明 |
| 统计代码     | STAT_CODE   | C    | 2    |      |
| 统计名称     | STAT_NAME   | C    | 8    |      |
| 付费代码     | CHARGE_CODE | C    | 1    |      |
| 付费名称     | CHARGE_NAME | C    | 8    |      |
| 序号（备注） | BZ          | C    | 20   |      |

## 统计报表用费用类别STAT_VS_FEE_CLASS

|          |           |      |      |      |
|----------|-----------|------|------|------|
| 中文名称 | 字段名    | 类型 | 长度 | 说明 |
| 统计代码 | STAT_CODE | C    | 2    |      |
| 统计名称 | STAT_NAME | C    | 10   |      |
| 费用代码 | FEE_CODE  | C    | 1    |      |
| 费用名称 | FEE_NAME  | C    | 4    |      |
| 备注     | REMARK    | C    | 20   |      |

## 
