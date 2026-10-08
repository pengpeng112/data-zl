# -*- coding: utf-8 -*-
"""R211 A1: 生成 requirements.csv —— 原子要求矩阵（211 §2.2字段）。
来源：55当前批次表 + 214 §3十个功能点复核结论 + 193 U01-U10 + 批次A执行报告。
仅登记已核实来源；歧义标 NEEDS_CONFIRMATION，不替用户裁决。"""
import csv
import sys
from collections import Counter
from pathlib import Path

run = Path(sys.argv[1])
cols = ["requirement_id","parent_id","topic","actor","business_object","source_file",
        "source_locator","source_time","latest_requirement","scope","acceptance_oracle",
        "supersedes","decision_reason","effective_status","doc_task_id","code_refs",
        "api_refs","ui_refs","migration_refs","evidence_refs","observed_state","gap_id",
        "test_ids","owner_or_dependency"]
R = []
def row(**kw):
    r = {c: "" for c in cols}; r.update(kw); R.append(r)

# ===== A. 平台级用户要求（最新裁决优先） =====
row(requirement_id="R211-001", topic="页面体验/菜单切换/消息提示", actor="用户", business_object="前端全站",
    source_file="214_系统人工复核与未完成工作核查报告.md", source_locator="§3.1", source_time="2026-10-06",
    latest_requirement="有效复拍16+页、连续菜单切换、退出再登录；DEF-01已裁决选A统一403信封；DEF-02以真实Chrome复现结论关闭",
    scope="全站页面", acceptance_oracle="页签名与正文同页且内容非空；dict_medical断言不改自然转绿；信封契约测试固定",
    supersedes="213旧T01-T18全过声明(以§7复核否定为准)", decision_reason="214 v1.2用户裁决DEF-01选A；批次A已实施",
    effective_status="ACTIVE", doc_task_id="213/214E-A1/E-A2",
    code_refs="backend/app/core/security.py;backend/app/main.py", ui_refs="frontend/src/layout/**",
    evidence_refs="output_r214/(执行报告.md,e_a1_results.json,screenshots/,DEF-01_兼容性清单.md);backend/tests/test_forbidden_envelope_214.py",
    observed_state="已完成(批次A)：18/18页、403信封统一、DEF-02不复现关闭", test_ids="test_forbidden_envelope_214,test_dict_medical")
row(requirement_id="R211-002", topic="211核查与212独立验收", actor="用户", business_object="全系统",
    source_file="55_系统未完成事项统一执行计划.md", source_locator="当前批次表211/212行", source_time="2026-10-02",
    latest_requirement="211核查历史要求/任务时效与系统实现、架构和运行偏离，同范围冲突按最新明确要求裁决，实施可执行改进并冻结候选；212承接独立验收(含O07/O10；O09无干净Linux标BLOCKED)",
    scope="全系统", acceptance_oracle="211 A0-A7产物齐备+候选冻结；212按计划分母验收且受阻如实登记",
    decision_reason="214 §7.3批次B合同", effective_status="ACTIVE", doc_task_id="211/212",
    evidence_refs="211/212计划全文;output_r214/执行报告.md", observed_state="本run执行中")
row(requirement_id="R211-003", topic="真实通知接入(铃铛)", actor="用户", business_object="前端通知中心",
    source_file="214", source_locator="§3.1", source_time="2026-10-06",
    latest_requirement="真实通知是否纳入近期产品排期待定；不新造通知能力，排期确定后接线(后端已有quality-notifications，前端quality.ts已封装，铃铛现为静态空表)",
    scope="通知中心", acceptance_oracle="排期确定后铃铛读取真实接口",
    decision_reason="214 §3.1建议；不擅自排期", effective_status="NEEDS_CONFIRMATION",
    doc_task_id="213遗留BD登记", code_refs="backend/app/api/v1/quality_notifications.py",
    ui_refs="frontend/src/layout/components/lay-notice/data.ts;frontend/src/api/quality.ts",
    evidence_refs="output_r214/执行报告.md", observed_state="后端已有/前端静态空表，待排期",
    gap_id="GAP-211-03", owner_or_dependency="产品排期决策")
row(requirement_id="R211-004", topic="BD-01 platform_admin非隐式全码", actor="用户", business_object="权限模型",
    source_file="55", source_locator="213行", source_time="2026-10-07",
    latest_requirement="platform_admin 是否保持隐式全码(不种入权限码表)需后端工单裁决；当前行为=隐式全码",
    scope="权限", acceptance_oracle="裁决后固定契约并有测试",
    decision_reason="213遗留登记", effective_status="NEEDS_CONFIRMATION",
    code_refs="backend/app/core/security.py", evidence_refs="output_r213/", observed_state="行为一致但契约未裁决",
    gap_id="GAP-211-04", owner_or_dependency="后端工单")

# ===== B. 数据质量闭环（214 §3.3 / 55 207行） =====
row(requirement_id="R211-010", topic="质量检测→整改→复测→复发闭环", actor="治理责任人(待定)",
    business_object="quality_governance", source_file="214", source_locator="§3.3", source_time="2026-10-06",
    latest_requirement="本地链+四角色隔离验收已完成；生产旧记录盘点回填、真实规则试跑、worker运行配置、完整调度周期、真实整改复测验收待做",
    scope="生产质量运营", acceptance_oracle="单源规则+跨源规则各一条走完整检测→分派→整改→复测→人工关闭",
    decision_reason="软件完成不等于运营闭环", effective_status="ACTIVE",
    doc_task_id="207/203L4", code_refs="backend/app/services/quality_execution_service.py;backend/scripts/quality_worker_207.py",
    evidence_refs="output_r207/(release_pack,screenshots/T34);output_r214/",
    observed_state="LOCAL_DONE+生产代码已随r210发布；专项生产验收未做",
    gap_id="GAP-211-10", test_ids="test_quality_execution_207等", owner_or_dependency="首批规则五要素+责任人(待输入)")
row(requirement_id="R211-011", topic="165六条问题发现终态", actor="治理责任人", business_object="quality findings",
    source_file="214", source_locator="§3.3", source_time="2026-10-06",
    latest_requirement="责任人、处理时限与终态待定", scope="165遗留", acceptance_oracle="逐条终态",
    effective_status="NEEDS_CONFIRMATION", evidence_refs="203 L8", observed_state="待输入",
    gap_id="GAP-211-11", owner_or_dependency="业务责任人")

# ===== C. 分类分级与用途授权（214 §3.4 / 55 210行） =====
row(requirement_id="R211-020", topic="安全分类分级候选到confirmed人工定级", actor="定级责任人+独立审批人(待定)",
    business_object="dataset_security", source_file="214", source_locator="§3.4", source_time="2026-10-06",
    latest_requirement="270,787候选(含262,841 undecided)需人工定级；confirmed全程0；提案+审批职责分离；P4库内折算不等于已定级",
    scope="生产治理", acceptance_oracle="首批对象定级+审批+回读；候选不作数据读取许可",
    decision_reason="210 S10生产落地后剩余=人工治理", effective_status="ACTIVE",
    doc_task_id="210", code_refs="backend/app/services/dataset_security.py",
    migration_refs="c0d1e2f3a4b5", evidence_refs="output_r210/r210-20261002-s10/",
    observed_state="软件+生产导入完成；人工定级0", gap_id="GAP-211-20",
    test_ids="plan193/210测试族", owner_or_dependency="定级/审批责任人+首批范围(待输入)")
row(requirement_id="R211-021", topic="真实导出目录配置与AI出口桥接", actor="运维+治理", business_object="导出工件",
    source_file="55", source_locator="210行", source_time="2026-10-02",
    latest_requirement="APP_DS_EXPORT_ARTIFACTS_DIR部署配置在真实导出启用前完成；AI出口桥接待真实数据验证",
    scope="生产配置", acceptance_oracle="配置后真实导出端到端",
    effective_status="ACTIVE", code_refs="backend/app/services/dataset_products.py",
    evidence_refs="output_r210/", observed_state="隔离已验/生产配置待做",
    gap_id="GAP-211-21", owner_or_dependency="生产配置批准(待输入)")

# ===== D. 患者纵向数据集（214 §3.5 / 55 193行） =====
row(requirement_id="R211-030", topic="B18真实患者试点", actor="临床/治理/运维三责任人(待定)",
    business_object="patient dataset", source_file="214", source_locator="§3.5", source_time="2026-10-06",
    latest_requirement="已确认原则：总窗2020-01-01起、首试近12个月、心内科I50.x、100-300次住院、独立受限数据面、先时间线与统计；缺具体编码/资源/责任人/范围批准",
    scope="真实试点", acceptance_oracle="小范围时间线+统计试点完成",
    supersedes="旧'业务原则未定'说法(原则已定)", decision_reason="214 §2纠正",
    effective_status="ACTIVE", doc_task_id="193 B18", evidence_refs="output_r193/B01/B01_试点契约.md",
    observed_state="合成闭环DONE；真实试点待输入", gap_id="GAP-211-30",
    owner_or_dependency="科室编码/资源/三责任人/批准(待输入)")

# ===== E. 关系/配方/值域治理（214 §3.6） =====
row(requirement_id="R211-040", topic="195/198治理队列人工审核", actor="治理负责人(待定)",
    business_object="relations/recipes/value_domains", source_file="214", source_locator="§3.6", source_time="2026-10-06",
    latest_requirement="195的114条草稿(31关系+83配方)分别审核；198剩余列变更12/拟撤6/证据降级27/13配方语义/37值域确认；approve不等于formal",
    scope="治理队列", acceptance_oracle="逐项决议+formal回读",
    effective_status="ACTIVE", doc_task_id="195/198/203L4",
    evidence_refs="output_r203/l4_治理第一批_20260925.md;output_r195/;output_r198/",
    observed_state="首批20项approve完成；5条探针非pass禁转formal(214E-A5登记)",
    gap_id="GAP-211-40", owner_or_dependency="治理负责人+逐项决议(待输入)")
row(requirement_id="R211-041", topic="治理队列自然键查重", actor="AI(可执行)",
    business_object="195/198队列", source_file="55", source_locator="205行", source_time="2026-10-07",
    latest_requirement="195/198队列自然键去重未开始；按当前live状态去重后交人工",
    scope="队列预处理", acceptance_oracle="重复族识别清单",
    effective_status="ACTIVE", doc_task_id="205 B剩余",
    evidence_refs="output_r205/r205-20260926/", observed_state="未开始(属205线，211登记不改判)", gap_id="GAP-211-41")

# ===== F. 数据库资产再探索（214 §3.7） =====
row(requirement_id="R211-050", topic="205元数据差异包(离线准备)", actor="AI(受限)",
    business_object="metadata差异", source_file="214", source_locator="§7.3", source_time="2026-10-06",
    latest_requirement="差异包仅离线准备(复用205快照产物)；活库补探与生产差异入库不在本轮(205 R8无批准)",
    scope="离线", acceptance_oracle="差异包产物落盘或按205线登记",
    decision_reason="214批次B边界", effective_status="ACTIVE", doc_task_id="205",
    evidence_refs="output_r205/r205-20260926/", observed_state="按离线准备在205线执行；211不越权连源库")

# ===== G. 角色/196（214 §3.8） =====
row(requirement_id="R211-060", topic="四正式身份最小权限试用+196受控执行", actor="管理员(待定)",
    business_object="identity/dict_medical", source_file="214", source_locator="§3.8", source_time="2026-10-06",
    latest_requirement="四身份账号(计划创建员/独立审核员/执行运维员/AI只读)；诊断下发1-3编码+当前/目标值+依据+执行器+时段",
    scope="生产受控动作", acceptance_oracle="不写源库计划流程跑通；首条幂等执行",
    effective_status="ACTIVE", doc_task_id="200/196",
    code_refs="backend/app/api/v1/dict_medical*;identity*",
    evidence_refs="output_r200/", observed_state="软件DONE；正式试用待输入",
    gap_id="GAP-211-60", owner_or_dependency="四身份名单+编码清单(待输入)")

# ===== H. 三甲扩窗（214 §3.9） =====
row(requirement_id="R211-070", topic="189/191扩窗live实施", actor="DBA+审批(待定)",
    business_object="上报视图", source_file="214", source_locator="§3.9", source_time="2026-10-06",
    latest_requirement="离线44对象50谓词49改/1HOLD完成不等于live完成；活库定义核对、分批实施、MTL/JHEMR选型、DataX补抽待做；EXAM_IMAGE_PATH无日期谓词专项复核",
    scope="源库受控修改", acceptance_oracle="真实计数+对象级恢复材料+分批实施",
    effective_status="ACTIVE", doc_task_id="189/191", evidence_refs="output_r189/",
    observed_state="离线DONE；live待批准", gap_id="GAP-211-70", owner_or_dependency="取证窗口+通道批准(待输入)")

# ===== I. 指标/黄金用例（214 §3.10） =====
row(requirement_id="R211-080", topic="20核心指标业务口径+144黄金种子+G5门禁", actor="业务方(待定)",
    business_object="metrics/golden", source_file="214", source_locator="§3.10", source_time="2026-10-06",
    latest_requirement="逐项分子/分母/排除/物理来源/值域/负责人/刷新频率/验收样例；未确认口径保持草稿",
    scope="指标治理", acceptance_oracle="高频指标+典型黄金样例由业务方提供标准答案",
    effective_status="ACTIVE", doc_task_id="203L8/144", evidence_refs="203 §12",
    observed_state="能力已有；口径未定", gap_id="GAP-211-80", owner_or_dependency="业务口径(待输入)")

# ===== J. 193 U01-U10（历史编号保留） =====
u_map = [
    ("U01","扩展不破坏原有功能","新模块增量接入、API/路由/统计口径兼容","合成阶段DONE(B00/B16/B17回归)","output_r193/","ACTIVE"),
    ("U02","清洗后患者高质量数据集贴合原业务","来源保真/原值治理值并存/业务粒度","合成DONE；真实=B18(R211-030)","output_r193/B01/","ACTIVE"),
    ("U03","20年至今数据抽独立库","总窗2020起/首试12个月/按年回填独立数据面","原则已确认(BC-01)；实施待B18","output_r193/B01/B01_试点契约.md","ACTIVE"),
    ("U04","患者全生命周期就诊信息","本院纵向就诊链，院外/随访扩展储备","合成DONE","output_r193/","ACTIVE"),
    ("U05","统计/AI训练/数据交易场景","统一底座、按用途独立发布","软件能力DONE(210)；真实出口待配置(R211-021)","output_r210/","ACTIVE"),
    ("U06","历史数据乱不可改，防新旧不一致","源端零写/规则版本化/双轨核对/可复现","DONE(设计约束持续有效)","output_r193/","ACTIVE"),
    ("U07","参考成熟方案给建议规划","组件选型依据193§13","DONE","output_r193/","ACTIVE"),
    ("U08","分阶段每日AI按计划开发","B00-B19依赖与验收","DONE(合成阶段)","output_r193/","ACTIVE"),
    ("U09","用户要求写入计划便于核查","U01-U10落文","DONE","193 §1","ACTIVE"),
    ("U10","数据安全分类分级支撑扩展","分类标签/保护等级/用途授权/撤销删除","软件+生产导入DONE(210)；人工定级=R211-020","output_r210/r210-20261002-s10/","ACTIVE"),
]
for uid, topic, latest, status, ev, st in u_map:
    row(requirement_id=uid,
        parent_id="R211-030" if uid in ("U02","U03","U04") else ("R211-020" if uid == "U10" else ""),
        topic=topic, actor="用户", business_object="dataset",
        source_file="193_患者纵向高质量数据集分阶段开发执行计划.md", source_locator="§1.1 U表",
        source_time="2026-09-15", latest_requirement=latest, scope="数据集",
        acceptance_oracle="193 B17逐项", decision_reason="193 U01-U10原编号保留(211 §2.2)",
        effective_status=st, doc_task_id="193", evidence_refs=ev, observed_state=status)

# ===== K. 技术收尾（214 §4） =====
row(requirement_id="R211-090", topic="性能与恢复测试", actor="AI(212)",
    business_object="性能/恢复", source_file="214", source_locator="§4", source_time="2026-10-06",
    latest_requirement="当前候选隔离负载+完整备份恢复纳入212(O01/O06对应209 O07/O10)",
    scope="隔离环境", acceptance_oracle="212 O01/O06执行+阈值来源",
    effective_status="ACTIVE", doc_task_id="212", evidence_refs="output_r209/(O07/O10 NOT_RUN登记)",
    observed_state="212本轮执行")
row(requirement_id="R211-091", topic="离线部署演练", actor="环境提供方(待定)",
    business_object="部署", source_file="214", source_locator="§4", source_time="2026-10-06",
    latest_requirement="可弃干净断网Linux环境；无环境标BLOCKED_ENV",
    scope="部署演练", acceptance_oracle="真实断网部署证据",
    effective_status="ACTIVE", doc_task_id="212 O07", evidence_refs="209 O09 BLOCKED登记",
    observed_state="本机无干净Linux故BLOCKED_ENV", gap_id="GAP-211-91", owner_or_dependency="Linux环境(待提供)")
row(requirement_id="R211-092", topic="发布脚本服务器副本同步", actor="运维",
    business_object="deploy", source_file="55", source_locator="运维与技术债行", source_time="2026-10-07",
    latest_requirement="release_frontend.sh修复版(E-A3)在下次发布前同步服务器副本",
    scope="生产运维", acceptance_oracle="服务器脚本与仓库一致",
    effective_status="ACTIVE", evidence_refs="output_r214/EA3_发布脚本演练记录.md",
    observed_state="本地修复完成；服务器同步待发布窗口", gap_id="GAP-211-92", owner_or_dependency="发布窗口")
row(requirement_id="R211-093", topic="graph_sync契约覆盖+AI注释占位", actor="AI",
    business_object="graph/ai注释", source_file="214", source_locator="§4", source_time="2026-10-06",
    latest_requirement="graph_sync抽象契约覆盖核实；表目录AI注释建议端点占位——先核已有测试和实现证据再定范围",
    scope="图谱/注释", acceptance_oracle="契约覆盖证据或缺口登记",
    effective_status="ACTIVE", observed_state="211 A2/A3核查对象", gap_id="GAP-211-93")
row(requirement_id="R211-094", topic="Git分域收口(本地commit纪律)", actor="AI",
    business_object="仓库", source_file="214", source_locator="§4", source_time="2026-10-06",
    latest_requirement="本地分域commit、不push不tag、三条未跟踪迁移保留、不夹带他人WIP",
    scope="Git", acceptance_oracle="提交清单自证",
    effective_status="ACTIVE", observed_state="持续执行")

with open(run / "requirements.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(R)
print(f"requirements.csv: {len(R)} rows")
print(Counter(r["effective_status"] for r in R))
