"""Generate planning assets only. Never connect to a database or run extractors."""

from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import zipfile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
ROOT = RUN.parents[2]
PLAN_NAME = "Python与DataX统一T加1顶层设计及长任务执行计划.md"
PROMPT_NAME = "给执行AI的长任务启动提示词.md"
PACKAGE_ID = "R189-T1-ENGINEERING-20261019-v1.1"

# Independent business/failure expectations for the executor's future tests.
CASES = [
    ("CONFIG", "77项不重不漏，4检验双源与护理ODS对照分开", "77个唯一规范项；81候选对象不冒充81张规范表"),
    ("CONFIG", "未知源/目标/变更依据/投影触发生产计划", "拒绝该动作，仍可离线列示及模拟"),
    ("CONFIG", "护理计划标未使用无法提供", "登记待适用性确认，不能自动通过或免报"),
    ("CONFIG", "只有READ_READY而请求apply", "没有写批准/白名单时拒绝"),
    ("CONFIG", "变更视图或父定义/字典/目标类型", "受影响配置失效，只复核变化及依赖项"),
    ("SOURCE", "业务源SQL含DML/DDL或多语句", "执行前拒绝，不绕只读校验"),
    ("SOURCE", "返回上限小但底层查询缺键/窗或计划依据", "拒绝或待计划证明，不把限量当扫描安全"),
    ("SOURCE", "空页/0行但源延迟或查询异常", "源未到/失败与真零区分"),
    ("SOURCE", "所有分页完整且证实无业务", "记录真实零及证据，0分母不自动显示100%"),
    ("SOURCE", "同秒多ID与边界秒/跨日", "完整且无边界遗漏，重试仍用原区间"),
    ("SOURCE", "早时间戳晚提交或ODS迟到", "用已证机制捕获；无覆盖依据则待核，不报完整"),
    ("SOURCE", "超过行/字节上限、读取中断", "标未完整，分片/恢复，水位不越过缺片"),
    ("SOURCE", "keyset分页末页之外仍有合法记录", "检测未完整，不将末页不足当唯一结束证明"),
    ("SOURCE", "小表快照读取部分失败", "不推断缺行删除"),
    ("SOURCE", "大表无修改时间且无变更清单", "UNRESOLVED，不能用固定回看保证任意历史更正"),
    ("SOURCE", "业务时间旧但今天补录", "可信变更机制捕获，不只按昨日业务时间"),
    ("RELATION", "父时间未变而子图片/项目变更", "重建受影响组并刷新合法输出"),
    ("RELATION", "同患者多次就诊，JOIN只用患者", "完整组合键规则检出错连候选/实值异常"),
    ("RELATION", "父数据未成功且子已读完", "延后相关子，其他独立组继续"),
    ("RELATION", "父一对多扩增或同ID多内容", "冲突隔离，不以最后一条覆盖"),
    ("RELATION", "子项撤销/从完整子集中消失", "按已证协议处理撤销，单次缺行不删除"),
    ("RELATION", "路径排序序号发生变化", "检测同ID换路径/同路径换ID，未核稳定前不覆盖"),
    ("TYPE", "中文字符数合规但目标字节超限", "按目标编码/字节契约检出，不自动截断"),
    ("TYPE", "CLOB跨连接、换行引号或超长正文", "完整流式读取/编码/hash可比，展示截断不参与全内容hash"),
    ("TYPE", "高精度Decimal金额与负数/舍入边界", "不经float损失，按批准精度检查"),
    ("TYPE", "DATE与TIMESTAMP分数秒或时区差异", "明确逻辑类型比较，保留精度，不伪造一致"),
    ("TYPE", "NULL、空串、空白、多分隔符", "遵循字段契约，不能任意混同或替'-'"),
    ("TYPE", "SYSTEM_TIME每次查询变动但业务不变", "业务hash不把全表误判修改"),
    ("QUALITY", "规范必填/条件必填/值域失败", "受影响组隔离并计未完成，证据可定位"),
    ("QUALITY", "源元数据列可空或长度比目标大", "仅作为风险，不能冒充实值为空/超长已证"),
    ("QUALITY", "源读100行分类含冲突/隔离", "互斥分类守恒；装载动作统计用独立分母"),
    ("DATAX", "querySql模式另配where但querySql未限窗", "生成校验拒绝；过滤必须进入实际执行SQL"),
    ("DATAX", "OracleWriter配置writeMode=update", "拒绝该假设，改受控stage和ApplyPort"),
    ("DATAX", "子进程退出0却有dirty/部分分片/缺manifest", "不标捕获或质量通过"),
    ("DATAX", "进程超时、取消和JVM子孙进程残留", "只终止本任务进程组，收回资源、保留可恢复stage"),
    ("DATAX", "重试多个attempt都部分stage成功", "按attempt隔离，仅选已完整版本，不重复正式装载"),
    ("DATAX", "插件缺失/版本不支持LOB或精度", "该表路由待确认/已验证Python，禁止无授权自动改通道"),
    ("SECRET", "DataX展开job/异常/dirty日志含凭据或患者", "仅服务器受控私有记录；AI/普通日志/包只脱敏摘要"),
    ("APPLY", "正式提交前断连", "回滚或待判定，stage保留，按原幂等键恢复"),
    ("APPLY", "提交已成功但回执响应丢失", "COMMIT_UNKNOWN；查同事务凭据/目标，不盲重写"),
    ("APPLY", "Oracle已提交而平台状态尚未更新", "凭receipt+manifest核实补记，不重复DML"),
    ("APPLY", "同批重复触发或操作幂等键已存在", "不重复写，返回可核验证据"),
    ("APPLY", "历史批晚完成且源版本较旧", "不覆盖新目标，旧版计无操作/冲突"),
    ("APPLY", "同版本不同内容或版本无可信顺序", "冲突隔离/受控重读，不比较hash大小定新旧"),
    ("APPLY", "一个记录组超过事务预算", "保持stage，明确原子发布方案，不静默发布半组"),
    ("APPLY", "前置机没有DATETIME辅助字段", "显式载荷排除辅助列，不按不存在列删除"),
    ("CONCURRENCY", "PG租约过期但旧worker仍可能写Oracle", "目标栅栏拒旧token，或禁止自动接管并先解未决事务"),
    ("CONCURRENCY", "每日增量和历史任务竞争同表写入", "同表单写并保护新版本；日常优先，历史错峰"),
    ("CONCURRENCY", "一个源持续超时但其他源正常", "该源熔断/告警，其余已获准源继续"),
    ("CONCURRENCY", "全局/每源并发及截止重试预算耗尽", "不超预算继续开线程，分类预警并保留待办"),
    ("RECONCILE", "源目标条数相等但ID不同", "集合核对检出，计数相等不判完整"),
    ("RECONCILE", "ID相同但业务字段不同", "按规范类型/hash/字段diff检出"),
    ("RECONCILE", "两次源查询不是同一可解释截点", "不把变化造成的差额直接定漏数，先建立一致范围证据"),
    ("RECONCILE", "源系统有数据但未同步到ODS", "源至ODS延迟单列，ODS等于目标不能证明全链完整"),
    ("MANUAL", "一表缺时间/INVALID，其他表就绪", "生成局部工单，继续其他表和本地开发"),
    ("MANUAL", "用户报告视图已修复", "重新取证/验证，不能自动闭单"),
    ("MANUAL", "修复改变字段/ID导致旧stage不兼容", "旧stage隔离，受影响范围重抽，新配置/批次留版本"),
    ("DELIVERY", "目标已落地但无省端回执或被拒绝", "区分待反馈/拒绝，不标全链完成"),
    ("DELIVERY", "重传更改输出状态或SYSTEM_TIME", "按省协议已确认规则处理，不猜EXCHANGE_TYPE映射"),
    ("SLA", "未提供省端deadline/达标环节", "参数待确认，模拟可测但生产及时性不标READY"),
    ("SLA", "累计7次模拟成功但未观测7业务日", "本地用例通过，不冒充E10内部观测验收"),
    ("SECURITY", "隔离库身份不明或pytest会清共享库", "停止集成动作，继续纯逻辑工作"),
    ("SECURITY", "同表有其他会话在跑/文件被占用", "保护原域，不杀进程/不改原执行器，准备交接"),
    ("SECURITY", "无适用白名单执行器但请求正式写入", "保持WAITING_APPROVAL/能力缺口，不临时直连写"),
    ("ALERT", "中文JSON/空白与实际请求字节签名", "先冻结UTF-8原始字节后签名，发送同一字节；内容改一字节验签失败（隔离）"),
    ("ALERT", "GET事件状态请求", "使用POST响应UUID，空body HMAC；不能把source_event_id或{}当GET签名body"),
    ("ALERT", "POST202且任务pending/processing", "仅标ACK_QUEUED，查询目标，不标送达"),
    ("ALERT", "同事件重试跨时间/进程重启", "相同ID和body字节/occurred_at，换新秒header时间戳与签名"),
    ("ALERT", "POST超时但服务端可能已经入队", "原ID原字节重试，duplicate后恢复同一UUID，不能重新造事件"),
    ("ALERT", "同ID不同内容409或无法分型409", "内容冲突待人工；不自动换ID掩盖冲突；已证重放才有界跨秒重签"),
    ("ALERT", "密钥/时钟错误401", "暂停自动重试与记录通道异常，不为测试向生产连续错签名触发锁定"),
    ("ALERT", "429限流/锁定及503背压", "429至少60秒并尊重更长Retry-After；503按Retry-After；原事件不变"),
    ("ALERT", "400/422报文错误或带receivers", "发送端拒绝/待修，不盲重试；收件人只能relay订阅配置"),
    ("ALERT", "5xx/断网/重试预算耗尽", "有界退避及持久待办，不丢事件或把通知报成功"),
    ("ALERT", "77表同源连接失败和持续重复故障", "源级聚合并保留表影响明细，去重/频控不压掉首次及red升级"),
    ("ALERT", "故障升级、持续提醒或已验证恢复", "新revision和新事件ID；原payload不改，恢复不等于简单退出0"),
    ("ALERT", "部分目标失败/取消/needs_attention或outcome_uncertain", "不标全目标送达；记录逐目标与不确定状态，不自动admin重放"),
    ("ALERT", "POST202但零目标/无任务列表", "ROUTE_UNRESOLVED并核订阅，不虚报成功或客户端指定接收人"),
    ("ALERT", "告警outbox与失败任务状态保存中途崩溃", "同事务或可证明补偿恢复；事件唯一键去重，不能重复丢失"),
    ("ALERT", "控制DB不可用或本地spool满", "受限脱敏spool有界补偿，满/积压由独立监测可见，不静默丢"),
    ("ALERT", "worker/控制进程崩溃无法自发告警", "独立巡检按心跳识别并通知；不是第二抽取入口"),
    ("ALERT", "relay本身故障或凭据错，业务读取正常", "通知待办不阻塞合法独立组，不递归向坏relay发它自己的失败"),
    ("ALERT", "异常字符串/metadata含患者、原SQL、密钥", "发送端白名单/脱敏，<=32键；通用AI和消息不泄露原载荷"),
    ("ALERT", "指南示例接收账号或源名尚未登记", "保持接入关闭及管理员待办，不能直接使用示例账号/凭据外发"),
    ("ALERT", "base_url或metadata被用作任意目标URL", "端点白名单和固定路径，事件不能注入URL/接收人"),
    ("ALERT", "同秒重签仍复用签名/GET高频轮询", "等待新秒且限制POST+GET总频率，查询有预算/截止，不绕防重放"),
    ("BATCH", "E08隔离受阻而生产静态包可做", "子任务独立继续，E09仍须隔离与审阅门禁，不能由审阅完成冒充集成通过"),
    ("BATCH", "E10分组上线完成但尚未实测7业务日", "rollout/observation/ops_handover分开，批次合并不降低验收"),
]

SCOPES = {'E01': ['本轮证据及配置目录', 'backend/app/services/reporting_pipeline/contracts.py', 'backend/scripts/reporting_ctl.py'],
 'E02': ['backend/app/services/reporting_pipeline/repositories.py',
         'backend/app/services/reporting_pipeline/planner.py',
         'backend/app/models/asset_reporting.py',
         '候选手写迁移及alert incident/outbox模型'],
 'E03': ['backend/app/services/reporting_pipeline/adapters/python_reader.py',
         'backend/app/services/reporting_pipeline/adapters/datax_runner.py',
         '候选DataX模板'],
 'E04': ['backend/app/services/reporting_pipeline/staging.py', 'backend/app/services/reporting_pipeline/quality.py'],
 'E05': ['backend/app/services/reporting_pipeline/apply_port.py',
         'backend/app/services/reporting_pipeline/reconcile.py',
         '适用白名单桥接候选'],
 'E06': ['backend/app/services/reporting_pipeline/recovery.py',
         'backend/app/services/reporting_pipeline/scheduler_bridge.py',
         'backend/app/services/reporting_pipeline/alerts_client.py',
         'backend/app/services/reporting_pipeline/alerts_outbox.py',
         '既有独立巡检桥接'],
 'E07': ['backend/app/services/reporting_pipeline/manual_tickets.py',
         'backend/app/services/reporting_pipeline/reports.py',
         'backend/tests/reporting_pipeline_unit/',
         '本轮证据目录'],
 'E08': ['backend/tests/reporting_pipeline_integration/', '明确可清理隔离环境（条件依赖）', 'deploy/reporting_pipeline/', '本轮生产审阅材料'],
 'E09': ['逐对象获批真实试点范围', '管理员指定且明确获准的relay测试订阅', '本轮试点证据'],
 'E10': ['逐组获批切换及范围内观测', '本轮运维交接/观测证据']}

BATCH_MAP = {'E01': ['E00', 'E01'],
 'E02': ['E02', 'E03'],
 'E03': ['E04', 'E05'],
 'E04': ['E06'],
 'E05': ['E07', 'E08'],
 'E06': ['E09'],
 'E07': ['E10', 'E11'],
 'E08': ['E12', 'E13'],
 'E09': ['E14'],
 'E10': ['E15', 'E16']}

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def dump(name, data):
    (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def style(sheet, widths):
    sheet.freeze_panes='C2';sheet.auto_filter.ref=sheet.dimensions
    for cell in sheet[1]:
        cell.fill=PatternFill('solid',fgColor='305496');cell.font=Font(bold=True,color='FFFFFF')
    for row in sheet:
        for cell in row:cell.alignment=Alignment(wrap_text=True,vertical='top')
    for i,width in enumerate(widths,1):sheet.column_dimensions[get_column_letter(i)].width=width


def alert_rules():
    return [
        {'code':'EXTRACT_FAILED','trigger':'连接/SQL/驱动/读取不完整/DataX失败或dirty','severity':'yellow','upgrade':'接近截止或关键来源受影响升级red'},
        {'code':'SOURCE_LATE','trigger':'源或ODS未到约定可见点/异常零行','severity':'yellow','upgrade':'超延迟预算或影响截止升级red'},
        {'code':'VIEW_BLOCKED','trigger':'INVALID/缺字段或时间/历史范围/定义漂移','severity':'yellow','upgrade':'生成局部人工工单；影响截止升级red'},
        {'code':'QUALITY_BLOCKED','trigger':'必填/值域/字节精度/冲突ID/父键异常','severity':'yellow','upgrade':'已证严重错连或广泛冲突red'},
        {'code':'RECONCILE_DIFF','trigger':'同取证范围ID/内容/关系未解释差额','severity':'red','upgrade':'立即，不能用条数相等掩盖'},
        {'code':'COMMIT_UNKNOWN','trigger':'正式提交/回执结果不明','severity':'red','upgrade':'立即，先对账不盲写'},
        {'code':'WORKER_STALE','trigger':'worker/控制层长期无心跳','severity':'red','upgrade':'独立巡检发出，阈值按实际预算'},
        {'code':'SLA_AT_RISK','trigger':'剩余时间不足/逾期','severity':'yellow','upgrade':'逾期red，deadline未知保持待配置'},
        {'code':'DELIVERY_REJECTED','trigger':'省端拒绝或反馈超时','severity':'yellow','upgrade':'按截止和影响范围red，区别于relay失败'},
        {'code':'ALERT_DELIVERY_FAILED','trigger':'relay/投递失败/积压','severity':'red','upgrade':'relay不健康时本地/独立监测，不递归推给坏relay'},
        {'code':'RECOVERED','trigger':'原故障已复核恢复/闭环','severity':'blue','upgrade':'notice，新revision关联原incident'},
    ]


def write_alert_assets():
    config={
        'package_id':PACKAGE_ID,'planning_only':True,'enabled':False,'integration_state':'DESIGN_ONLY_NOT_CONNECTED',
        'base_url_candidate':'http://10.20.1.153:3000','allowed_paths':['/api/v2/events','/api/v2/events/{relay_event_id}'],
        'source_id_candidate':'sanjia-etl','source_id':None,'secret_ref':None,'category_candidate':'sanjia_etl',
        'auth':'HMAC-SHA256_HEX_LOWER','signing_input':'UTF8(source_id + "." + unix_seconds + ".") + raw_body_bytes',
        'get_body':'EMPTY_BYTES','event_id_for_get':'SERVER_RESPONSE_UUID_NOT_SOURCE_EVENT_ID',
        'payload_fields':['source_event_id','event_type','category','severity','title','body','occurred_at','metadata'],
        'metadata_max_keys':32,'source_event_id_max_characters':200,'outbox_body_immutable':True,
        'retry_same_event':'SAME_ID_SAME_BODY_NEW_SECOND_TIMESTAMP_AND_SIGNATURE',
        'lifecycle_change':'NEW_REVISION_NEW_SOURCE_EVENT_ID',
        'post_202':'ACK_QUEUED_NOT_DELIVERED','post_200_duplicate':'RESUME_EXISTING_EVENT_STATUS',
        'delivered':'ALL_EXPECTED_TARGETS_SENT_NO_UNCERTAIN_NONEMPTY',
        'candidate_timeouts_seconds':{'connect':3,'read':10},
        'retry':{'401':'PAUSE_AUTH_RETRIES','409':'CLASSIFY_REPLAY_OR_CONTENT_CONFLICT_NO_NEW_ID_BYPASS',
                 '429_min_delay_seconds':60,'respect_longer_retry_after':True,'503':'RESPECT_RETRY_AFTER',
                 '400_422':'PERMANENT_PAYLOAD_ERROR','5xx_timeout':'BOUNDED_BACKOFF_JITTER_SAME_IMMUTABLE_EVENT'},
        'candidate_poll_seconds':[30,120],'candidate_dedupe_minutes':10,'candidate_reminder_minutes':30,
        'rate_limit':'POST_PLUS_GET_WITHIN_ADMIN_SOURCE_LIMIT','daily_report_push_enabled':False,
        'independent_heartbeat_monitor_required':True,'relay_failure_recursion_allowed':False,
        'metadata_allowlist':['system','environment','canonical_table','source_group','stage','business_date','batch_id',
                              'incident_id','error_class','error_code','affected_count','task_status','ticket_ref','deadline','detail_ref'],
        'admin_todo':['独立源及限流/IP白名单确认','受控secret_ref配置','管理员指定测试/正式订阅和收件人',
                      '确认可达路径及实际服务协议','明确真实联调和投递范围批准'],
        'never_send':['患者标识/姓名/证件/电话/地址/正文/路径载荷','原SQL和未脱敏异常','密码/token/secret','receivers字段'],
        'real_requests_sent':0,
    }
    dump('告警接入配置候选.json',config)
    dump('告警触发与升级规则.json',{'package_id':PACKAGE_ID,'planning_only':True,'rules':alert_rules(),
         'thresholds_status':'CANDIDATE_REQUIRES_OPERATOR_CONFIRMATION','runtime_state':'NOT_IMPLEMENTED'})
    dump('批次合并映射.json',{'from_version':'1.0','from_batches':17,'to_version':'1.1','to_batches':10,
         'mapping':BATCH_MAP,'original_files':'_history/v1.0/','state_authority':'原checkpoint同节点，旧状态存历史，不按同E编号混用',
         'subgates':{'E08':['isolated_integration','production_review_pack'],'E09':['E08两项门禁及具体批准'],
                     'E10':['rollout','observation','ops_handover']},'source_implementation_started':False})
    docs=[Path('F:/python/前后端代码/qywx/docs/08_通用告警推送公共接口对接指南.md'),
          Path('F:/python/前后端代码/qywx/docs/06_v2接口与连接器接入指南.md')]
    dump('接口资料指纹.json',{'read_only_references':True,'provider_repo_modified':False,'relay_contacted':False,
        'sources':[{'path':str(d),'sha256':hashlib.sha256(d.read_bytes()).hexdigest(),'bytes':d.stat().st_size} for d in docs]})


def main():
    inv=read(RUN/'all_views_review_20261019/本轮77项冻结清单.json')
    source_plan=read(RUN/'all_views_review_20261019/字典核查对象与源配置_不含凭据.json')
    spec=read(RUN/'规范MD逐表要求.json')
    assert hashlib.sha256(Path(inv['workbook']).read_bytes()).hexdigest()==inv['workbook_sha256']
    assert hashlib.sha256(Path(inv['spec']).read_bytes()).hexdigest()==inv['spec_sha256']
    seeds=[]
    for item in inv['items']:
        candidates=[]
        for obj in source_plan['objects']:
            if obj['index']!=item['index']:continue
            src=source_plan['sources'][obj['source_group']]
            candidates.append({'object_id':obj['id'],'role':obj['role'],'source_group':obj['source_group'],
                'host':src['host'],'port':src['port'],'database_hint':src['database'],'owner_hint':src['owner'],
                'object_name_candidates':obj['names'],'current_identity_verified':False})
        relations=[r for r in spec['declared_relations'] if r['child'].upper()==item['table']]
        seeds.append({'index':item['index'],'canonical_table':item['table'],'business_name':item['name'],
            'enabled':False,'runtime_readiness':'UNKNOWN','applicability':'WAITING_BUSINESS_CONFIRMATION' if item['index']==61 else 'TO_VERIFY',
            'engine':'UNDECIDED','incremental_strategy':'UNRESOLVED','source_candidates':candidates,
            'target_candidate':{'host':'10.10.8.74','port':1521,'service':'orcl','owner':'DBOPER','table':item['table'],'current_identity_verified':False},
            'historical_business_time_hint':item['historical_registry_time_column'],
            'business_time':None,'change_evidence':None,'delete_or_retract_evidence':None,'source_version_order':None,
            'stable_key':{'candidate':['ID'],'verified':False},'projection':[],'deadline':None,
            'declared_parent_candidates':[{'parent':r['parent'],'child_key':r['child_key'],'parent_key':r['parent_key'],'relation_id':r['relation_id'],'verified':False} for r in relations],
            'approval_refs':[],'apply_executor_ref':None,'definition_fingerprint':None,'dependency_fingerprints':{},
            'human_view_ticket_state':'TO_REVIEW','alert_policy_ref':'告警触发与升级规则.json',
            'note':'规划种子；历史时间/来源/目标是线索，未证明生产可执行，不含SQL或凭据'})
    dump('77项任务候选种子.json',{'package_id':PACKAGE_ID,'planning_only':True,'scope':77,'items':seeds})
    plan=(HERE/PLAN_NAME).read_text(encoding='utf-8')
    tasks=[]
    for line in plan.splitlines():
        if not re.match(r'^\| E\d\d \|',line):continue
        parts=[v.strip() for v in line.strip('|').split('|')]
        key=parts[0]
        dependency=[] if key=='E01' else [f'E{int(key[1:])-1:02d}']
        environment='LOCAL_OFFLINE'
        if key=='E08':environment='ISOLATED_INTEGRATION_PLUS_INDEPENDENT_STATIC_REVIEW'
        if int(key[1:])>=9:environment='EXPLICITLY_APPROVED_PRODUCTION_AND_RELAY_SCOPE_ONLY'
        tasks.append({'id':key,'maps_to':parts[1],'objective':parts[2],'acceptance':parts[3],
            'depends_on':dependency,'proposed_edit_scope':SCOPES[key],'environment':environment,
            'evidence':[f'执行证据/v1.1/{key}/命令与结果.json',f'执行证据/v1.1/{key}/验收说明.md'],
            'status_authority':'原run/checkpoint.json -> daily_t1.engineering_execution_20261019.batches',
            'execution_state':'NOT_STARTED','legacy_tasks_v1_0':BATCH_MAP[key],
            'subtasks': ['isolated_integration','production_review_pack'] if key=='E08' else (['rollout','observation','ops_handover'] if key=='E10' else []),
            'entry_gates': ['E08.isolated_integration=VERIFIED','E08.production_review_pack=READY','explicit_current_production_and_relay_approval'] if key=='E09' else [],
            'recovery':'保留成功/失败证据和原批次边界；只暂停必要条件未满足的步骤，继续其他独立任务；不覆盖其他会话或绕门禁'})
    assert len(tasks)==10 and {t['id'] for t in tasks}=={f'E{i:02d}' for i in range(1,11)}
    cases=[{'id':f'AT-{i:03d}','category':category,'trigger':trigger,'expected':expected,
            'execution_state':'NOT_RUN','actual_evidence':None,
            'environment_note':'先映射实际实现的离线/隔离/批准真实验证；不能把模拟冒充真实通过'}
           for i,(category,trigger,expected) in enumerate(CASES,1)]
    dump('验收场景矩阵.json',{'package_id':PACKAGE_ID,'planning_only':True,'count':len(cases),'cases':cases})
    package={'package_id':PACKAGE_ID,'version':'1.1','parent_task':'R189-UPLOAD-AUDIT-2021-2024','planning_only':True,
        'repo_root':str(ROOT),'plan':PLAN_NAME,'prompt':PROMPT_NAME,
        'checkpoint':'开发起步包/output_r189/r189-20261015-upload-audit/checkpoint.json',
        'checkpoint_node':'daily_t1.engineering_execution_20261019',
        'result_path':'执行结果总报告.md','state':'PLAN_READY_EXECUTION_NOT_STARTED',
        'scope':{'canonical_items':77,'source_groups':11,'review_objects':81,'not_provided_pending_applicability':1},
        'user_boundary':'用户人工修改源视图；执行AI负责抽取工程、证据及局部阻塞恢复',
        'architecture':'Python control + DataX/Python read adapters + staged validation + approved apply + reconcile/delivery',
        'invariants':['源只读且通道逐源获准','生产写入只走适用白名单/批准','默认77项disabled/UNKNOWN','固定窗口/完整清单/水位分离',
            '正式提交未知先回读','旧批不能覆盖新版本','父子及仅子变化覆盖','视图问题局部工单不拖全部',
            'AI接口只读、不自动审批','平台asset新表及隔离验收','不强制特定模型/CLI/工具替换','告警202只入队、逐目标查送达','不可变事件及HMAC原字节','同源聚合/去重/升级恢复、独立失联监测'],
        'approvals':{'local_development':'任务范围内可持续开发；核claim与仓库规则','source_daytime_batch':'PENDING_CURRENT_SCOPE',
            'business_data_reads':'PER_SQL_KEY_WINDOW_AND_BUDGET_REQUIRED','isolated_db':'VERIFY_DISPOSABLE_IDENTITY_BEFORE_MUTATION',
            'production_schema_write_publish_cron_cdc':'NOT_AUTHORIZED_BY_THIS_PLAN','git_push_tag':'NOT_AUTHORIZED','relay_registration_subscription_secret_or_real_send':'ADMIN_SETUP_AND_SPECIFIC_TEST_OR_PRODUCTION_SCOPE_REQUIRED'},
        'alerts':{'design':'企业微信公共告警接口对接设计.md','config':'告警接入配置候选.json','rules':'告警触发与升级规则.json','state':'DESIGN_ONLY_NOT_CONNECTED'},
        'batch_mapping':'批次合并映射.json','previous_version':'1.0','tasks':tasks,'milestones':['LOCAL_ENGINE_VERIFIED','ISOLATED_INTEGRATION_VERIFIED','PILOT_VERIFIED','ROLLOUT_PARTIAL_OR_FULL','OBSERVATION_ACCEPTED','OPS_HANDOVER_ACCEPTED'],
        'done_criteria':['E01—E07实现和真实离线证据，不虚构命令或测试','E08隔离验收不能以PG冒充Oracle，静态包可独立推进',
            'E09—E10只按真实批准和证据判定，E10上线/观测/运维子门禁分开','告警真实入队与目标送达分开，未注册/配置/获准不得外发','77项均有上线或具体待核/人工/适用性结论','源目标无未解释差额且时效按省端契约','报告/目录/checkpoint与等待同步']}
    dump('长任务执行契约.json',package)
    book=Workbook();s=book.active;s.title='E01至E10执行批次'
    s.append(['批次','主方案','目标','依赖','环境及门禁','验收','建议编辑范围','执行证据','状态权威'])
    for t in tasks:s.append([t['id'],t['maps_to'],t['objective'],','.join(t['depends_on']),t['environment'],t['acceptance'],'\n'.join(t['proposed_edit_scope']),'\n'.join(t['evidence']),t['status_authority']])
    style(s,[10,18,65,18,35,75,60,45,55])
    s=book.create_sheet('77项接入候选')
    s.append(['序号','规范表','业务名','来源候选','历史时间线索','引擎','增量策略','适用性','当前就绪','启用','人工处理与下一步'])
    for item in seeds:
        src='\n'.join(f"{r['source_group']} {r['host']}:{r['port']}/{r['database_hint']} {r['owner_hint'] or 'Owner待核'} {','.join(r['object_name_candidates'])} ({r['role']})" for r in item['source_candidates'])
        s.append([item['index'],item['canonical_table'],item['business_name'],src,item['historical_business_time_hint'],item['engine'],item['incremental_strategy'],item['applicability'],item['runtime_readiness'],False,'确认当前定义/变更依据/目标/稳定键/审批；视图错误形成局部工单'])
    style(s,[8,43,33,80,25,18,22,35,20,10,65])
    s=book.create_sheet('验收场景')
    s.append(['用例','类别','触发','应有结果','实际状态','证据要求'])
    for case in cases:s.append([case['id'],case['category'],case['trigger'],case['expected'],'NOT_RUN',case['environment_note']])
    style(s,[13,20,65,80,16,65])
    s=book.create_sheet('人工视图整改模板')
    s.append(['工单','规范表/源身份','视图/定义及依赖哈希','问题类别/SQL位置','影响批次和组','建议修改与期望','验收及恢复条件','责任角色','状态','旧暂存处理'])
    s.append(['模板（非已发现问题）','待填','待填','待填','仅阻塞受影响范围','待填','人工报修后复核，不自动闭单','人工视图维护/业务确认','OPEN','明确可重放或须重抽'])
    style(s,[25,45,55,55,45,60,65,30,20,50])
    s=book.create_sheet('每日运行日报模板')
    s.append(['业务日','规范表','源可见上界/分母依据','应处理键数','新增','更新','无变化','撤销','质量隔离','未解释缺失ID','内容差异','父键异常','目标提交状态','省反馈','截止及时性','人工工单/责任人'])
    style(s,[16,40,55,18,12,12,14,12,16,22,16,16,25,25,30,45])
    s=book.create_sheet('告警触发与推送')
    s.append(['事件','触发','初始级别','升级/恢复要求','发送与状态契约'])
    for rule in alert_rules():s.append([rule['code'],rule['trigger'],rule['severity'],rule['upgrade'],'v2持久入队后核逐目标投递；去重/HMAC/重试；未注册未获准保持关闭'])
    style(s,[30,65,16,75,85])
    s=book.create_sheet('批次合并映射')
    s.append(['当前批次v1.1','历史批次v1.0','保持的内部门禁','当前状态'])
    for key,old in BATCH_MAP.items():s.append([key,','.join(old),'E08隔离/审阅独立；E09两门禁及批准；E10上线/观测/运维分别验收','NOT_STARTED'])
    style(s,[25,30,90,20])
    book.save(HERE/'执行批次与验收矩阵.xlsx')

    # Offline consistency checks only; no implementation execution is claimed.
    assertions=[]
    assert len(seeds)==len({s['canonical_table'] for s in seeds})==77;assertions.append('77项唯一且与冻结范围一致')
    assert sum(len(s['source_candidates']) for s in seeds)==81;assertions.append('81候选对象含双源/对照，未误当规范表数')
    assert all(s['enabled'] is False and s['runtime_readiness']=='UNKNOWN' for s in seeds);assertions.append('全部disabled/UNKNOWN，不伪装生产READY')
    assert sum(s['applicability']=='WAITING_BUSINESS_CONFIRMATION' for s in seeds)==1;assertions.append('1未提供项适用性待确认，不自动免报')
    assert len(tasks)==10 and all(set(t['depends_on'])<={x['id'] for x in tasks} for t in tasks);assertions.append('10任务卡依赖完整，E08内部隔离与静态包独立')
    seen=set()
    while len(seen)<len(tasks):
        ready={t['id'] for t in tasks if t['id'] not in seen and set(t['depends_on'])<=seen};assert ready,'任务依赖成环';seen|=ready
    assertions.append('任务依赖无环')
    assert len(cases)==len({c['id'] for c in cases}) and all(c['execution_state']=='NOT_RUN' for c in cases);assertions.append('验收预期编号唯一且全部未执行')
    prompt=(HERE/PROMPT_NAME).read_text(encoding='utf-8');assert all(x in prompt for x in ['E01','E10','人工','checkpoint','批准','告警']);assertions.append('启动提示词含范围、长任务及边界')
    wb=load_workbook(HERE/'执行批次与验收矩阵.xlsx',read_only=True,data_only=True)
    assert wb['77项接入候选'].max_row==78 and wb['E01至E10执行批次'].max_row==11 and wb['验收场景'].max_row==len(cases)+1;wb.close();assertions.append('xlsx重开核行数/工作表')
    assert hashlib.sha256(Path(inv['spec']).read_bytes()).hexdigest()==spec['summary']['md_sha256'];assertions.append('规范MD与解析件/冻结指纹一致')
    assert all(not s['projection'] and s['apply_executor_ref'] is None for s in seeds);assertions.append('未猜投影或白名单执行器')
    assert all(s['change_evidence'] is None and s['source_version_order'] is None for s in seeds);assertions.append('未用历史业务时间冒充变更/版本依据')
    write_alert_assets()
    config=read(HERE/'告警接入配置候选.json')
    assert config['enabled'] is False and config['source_id'] is None and config['secret_ref'] is None;assertions.append('告警接入默认关闭，未编造源/密钥或真实推送')
    assert 'receivers' not in config['payload_fields'] and config['metadata_max_keys']==32;assertions.append('消息禁止客户端指定收件人且metadata有界')
    assert config['post_202']=='ACK_QUEUED_NOT_DELIVERED' and config['outbox_body_immutable'];assertions.append('告警入队/送达分开且事件重试内容不可变')
    assert {x for vals in BATCH_MAP.values() for x in vals}=={f'E{i:02d}' for i in range(17)};assertions.append('旧17批完整映射到10批，未删除内部工作')
    assert next(t for t in tasks if t['id']=='E08')['subtasks']==['isolated_integration','production_review_pack'];assertions.append('隔离与静态准备独立且真实试点门禁显式')
    dump('计划包离线验收.json',{'state':'PLANNING_ASSETS_VALIDATED_NO_ENGINE_IMPLEMENTATION','checks_passed':len(assertions),'checks':assertions,
        'tasks':len(tasks),'acceptance_cases':len(cases),'seed_items':len(seeds),'business_queries':0,'production_changes':0,'implementation_tests_run':0})
    names=[PLAN_NAME,PROMPT_NAME,'长任务执行契约.json','77项任务候选种子.json','验收场景矩阵.json','执行批次与验收矩阵.xlsx','计划包离线验收.json','企业微信公共告警接口对接设计.md','告警接入配置候选.json','告警触发与升级规则.json','批次合并映射.json','接口资料指纹.json']
    hashes={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in names}
    dump('交付文件指纹.json',hashes)
    with zipfile.ZipFile(HERE/'Python_DataX统一T加1长任务执行包_20261019.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in names+['交付文件指纹.json']:archive.write(HERE/name,name)
    print(json.dumps({'state':'PLAN_PACKAGE_READY_NOT_IMPLEMENTED','tasks':len(tasks),'cases':len(cases),'checks':len(assertions),'items':len(seeds),'objects':81},ensure_ascii=False))


if __name__=='__main__':main()
