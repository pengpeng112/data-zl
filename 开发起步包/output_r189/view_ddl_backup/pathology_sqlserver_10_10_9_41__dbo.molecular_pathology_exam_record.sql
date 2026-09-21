CREATE VIEW [dbo].[molecular_pathology_exam_record] AS 
select 
a.PatientID as	patient_id	,----	患者ID
cast(a.PathologyID as VARCHAR(20))+'|'+CAST(a.PatientID as VARCHAR(20))  as	visit_sn	,----	单次就诊唯一标识号
case when A.InPatientID ='' then '门诊' when A.InPatientID <>'' then '住院' else '其他'end  as 	visit_type	,----	就诊类型
'' as	visit_card_no	,----	就诊卡号
a.outPatientID as	outpatient_no	,----	门诊号
'' as	visit_times	,----	就诊次数
''as	medical_record_no	,----	病案号
InPatientID as	inpatient_no	,----	住院号
a.HospitalizationTime as	hospitalization_times	,----	住院次数
a.PatientName as	name	,----	患者姓名
a.PatientSex as	gender	,----	性别
a.PatientAge as	age	,----	年龄（岁）
CONVERT(VARCHAR, a.Birthday, 120) as	date_of_birth	,----	出生日期
a.ReqNoteID as	apply_no	,----	申请单号
a.hisid as	order_sn	,----	申请医嘱流水号
CONVERT(VARCHAR, a.SubmitCheckTime, 120) as	apply_datetime	,----	申请时间
a.PathologyID as	mol_patho_no	,------	分子病理号
a.PathologyID as	lab_sn	,------	检测流水号
CONVERT(VARCHAR, a.SubmitCheckTime, 120) as	exam_datetime	,------	检测时间
''as	sample_no	,------	标本编号
a.bblx as	sample_type	,------	标本类型
''as	test_platform	,------	检测平台
case when a.MedicalRecordDB in ('22','10004')then 'HPV检测' 
when a.MedicalRecordDB ='9998'then '药物基因检测' 
when a.MedicalRecordDB ='9999'then 'RNA检测' 
when a.MedicalRecordDB in ('24','25')then 'FISH' 
when a.MedicalRecordDB in ('10000')then 'BRAF'  
end   as test_item	,------	检测项目
case when a.MedicalRecordDB in ('22','10004')then 'PCR' 
when a.MedicalRecordDB ='9998'then '多重荧光探针杂交锚定连接测序' 
when a.MedicalRecordDB ='9999'then 'PCR' 
when a.MedicalRecordDB in ('24','25')then 'FISH' 
when a.MedicalRecordDB in ('10000')then 'BRAF' else '无' end as	test_method	,------	检测方法
''as	test_content	,------	检测内容
a.zdyj as	test_result	,------	检测结果
a.PathologyID as	report_no	,------	报告单号
CONVERT(VARCHAR, a.ReportTime, 120) as	report_datetime	,------	报告时间
''as	test_exon	,------	外显子
''as	test_locus	,------	位点
''as	test_gene	,------	检测基因
''as	transcript	,------	转录本
''as	nucle_alt	,------	核苷酸改变
''as	amino_acid_alt	,------	氨基酸改变
''as	mut_abundance	,------	丰度
''as	variation_type	,------	变异类型
''as	mut_interpretation	,------	变异解读
''as	geno_type	,------	基因型
a.bbmc as	sampling_site	,------	取材部位
''as	gene_sequencing_depth	,------	测序深度
''as	tmb	,------	肿瘤突变负荷
''as	extend_data1	,------	扩展字段1
''as	extend_data2	,------	扩展字段2
case when a.status='0' then '已登记' when a.status >=128 then '已诊断' else '诊断中' end   as	record_status	------	记录状态
from dbo.Pitaya a
where a.MedicalRecordDB in ('22','24','25','9998','9999','10000','10004') 
