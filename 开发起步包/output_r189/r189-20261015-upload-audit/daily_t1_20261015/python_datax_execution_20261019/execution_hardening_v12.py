"""Planning assets for observed drift and scoped failure handling. Never run an extractor."""

from pathlib import Path
import ast
import hashlib
import json

EXTRA_CASES = [
    ('DRIFT', '2026运行时补录2025业务日，昨日窗已完成', '两漂移表进入已纳管历史业务月轮巡，不只扫运行当月；待补及覆盖截止显式记账'),
    ('DRIFT', '月度任务只重扫当前月或遗漏已纳管2025月份', '范围验证拒绝覆盖通过；逐业务月账本定位漏月并预警'),
    ('DRIFT', '重扫源读失败/缺分片/质量未通过', '不删正式业务月，保留原数据；失败月待补，其他独立任务继续'),
    ('DRIFT', '旧重扫完成时同表每日批已写新内容', '同表单写/目标栅栏及版本保护；无版本则获锁后重读/废弃旧stage，不覆新'),
    ('DRIFT', '一次月重扫超过事务预算', '获批后按可证明完整且不破坏父子组的日/键范围原子发布；月仅全片核对后闭合'),
    ('ROUTE', 'LIS 2023-Q4业务月重扫', '四表保留ODS_TEST及瑞美双来源，按来源分片/对账；不整月清掉另一源或按ID自动业务去重'),
    ('ROUTE', 'LIS旧药敏/明细慢路线不可用', '只阻塞该历史路线/窗口，保持当前瑞美合法任务；不回退单源注册表冒充完整'),
    ('PERF', '出院185秒已知历史查询超过统一3分钟', '用该路线性能画像判QUERY_SLOW，不仅凭执行时长发SOURCE_LATE；参数化2秒与新视图版分开'),
    ('HANDOFF', 'E01只有manual2今晚结束的文字，无新进程证据', '登记USER_REPORTED，不能据此启动同表新写者；E10切换前重新核快照和未决提交'),
    ('SOURCE', '同物理库连续ORA-12541/ORA-12547/DPY-4011', '单源熔断/有界退避/单探针半开及聚合告警，不77表同时重连；其他源继续'),
    ('SLICE', '六小时结算窗超过50000条并出现上限探针', '超限窗不标完整；持久化递归二分树，左右起含止不含，完整叶才可装载'),
    ('SLICE', '最小时间精度内仍超上限或分裂深度耗尽', '改经验证稳定keyset；无稳定键则局部待处理，有限退出，不重复同一窗口'),
    ('TYPE', 'CHAR列0和0加尾随空格；VARCHAR正文含有意义尾空格', '只按已核CHAR元数据/契约去右侧填充空格；VARCHAR/LOB不能统一rstrip'),
    ('TYPE', 'Decimal(9007199254740992)与Decimal(9007199254740993)', '必须检出不同，不经float；120和120.00按批准数值语义相等，金额不任意量化'),
    ('SECRET', '长期任务指向/tmp/e2_env或其他补抽环境文件', '生产就绪验证拒绝；受控密码库/secret_ref由授权worker运行时解析，普通日志不见密钥'),
    ('SLA', '部分表deadline未配置且其余表成功', '日报单列DEADLINE_UNCONFIGURED及责任人/A12；SLA为UNKNOWN，不标达标或强行计算SLA_AT_RISK'),
    ('ALERT', '异常有告警但缺建议动作/安全detail_ref', '本地契约拒不完整运维事件；动作和只读工单入口可定位，不携患者、SQL或任意URL'),
    ('CONTINUE', '一张表一个业务日读取失败，其他日/表有独立合法任务', '持久失败窗和待补，继续独立任务；总状态PARTIAL，连续水位不跨缺口'),
    ('CONTINUE', '部分行质量失败但其他独立组已完整捕获', '隔离坏组并告警，合法组继续；捕获/装载/质量闭合分开，缺原始载荷不推水位'),
    ('CONTINUE', '一表COMMIT_UNKNOWN但另一表可写', '冻结未知表写者并核提交证据，其他表继续；未判提交前不切同表到另一天写'),
    ('CONTINUE', '父键集合局部失败，子表其他组父键已验', '只等相关子键/组；经证其他独立子组继续，不丢子记录或全表永久跳过'),
    ('CONTINUE', '告警relay失败但业务任务与控制存储正常', '持久化outbox并独立监测，合法业务继续，不因通知失败整体停止'),
    ('CONTINUE', '调度控制存储不可用或目标身份不符影响全部任务', '停止无法持久化/证明安全的领取或写入；只扩大到实际共享范围，保留恢复证据'),
    ('DRIFT', '历史月到期未扫、空源快照未证明真零、迟到分布仍在扩大', '覆盖债务/最近全核日/超期及零行证据单列；不删目标，不宣称月扫保证无限历史'),
]

EXTRA_FILES = [
    '实测建议评估与计划修订说明.md', '失败后继续抽取与补抽规则.md',
    '故障隔离与继续执行规则.json', '迟到漂移月度重扫策略.json',
    '每表性能与通道画像候选.json', 'LIS双源路由候选.json',
    '在跑任务交接快照模板.json', '实测参考资产与证据指纹.json',
    'E01已知人工工单种子.json', '回读类型规整契约.json',
]
DRIFT_TABLES = ['EMR_DOC_ORDER_CHECK', 'EMR_IN_FEE_INFO_CHILD']
DEPENDENT_TIME_TABLES = ['EMR_IN_FEE_INFO_CHILD','EMR_OUT_FEE_INFO_CHILD','EMR_DOC_ORDER_CHECK']


def dump(here, name, value):
    (here/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def operational_assets(here, run, seeds, package_id):
    root = run.parents[2]
    special = {
        'EMR_DISCHARGE_RECORD': ('SLOW_ANALYTIC_REPORTED', ['185秒是旧视图查询观测；原优化建议不能直接执行；后续参数化SELECT两样本2.068/3.085秒，新视图变体尚未现场验收'], 'OPEN_DISCHARGE_PERF_AND_QUALITY'),
        'EMR_IN_OUT_AMOUNT': ('LEGACY_VIEW_DATAX_ONLY_REPORTED', ['仅原整视图路线标DataX-only待复核；125/ewell B04患者键Python受控通道已有独立试点/执行报告，不能混同ODS同名对象或自动切换'], 'VERIFY_ROUTE_SPECIFIC_CAPABILITY'),
        'EMR_INSPECTION_ALLERGY': ('LEGACY_TEST_PATHOLOGIC_REPORTED', ['历史ODS_TEST单年COUNT>9分钟；当前瑞美与历史分路，不能用当前路线预算覆盖历史'], 'LEGACY_LIS_ACCESS_OPTIMIZATION'),
        'EMR_INSPECTION_ITEM': ('LEGACY_TEST_UNVERIFIED_SLOW', ['历史约3242万目标量仅是旧报告线索，禁止全扫；与瑞美分路'], 'LEGACY_LIS_ACCESS_OPTIMIZATION'),
    }
    profiles=[]
    for seed in seeds:
        name=seed['canonical_table']
        tier, notes, ticket = special.get(name, ('UNMEASURED', [], None))
        if name in DEPENDENT_TIME_TABLES:
            tier='DATETIME_PUSHDOWN_DEPENDENT_REPORTED'
            notes=['三张费用/医嘱视图依赖DBA加DATETIME下推的既有执行报告；不是三张费用表，按对象核当前类型/表达式/计划']
            ticket='REVERIFY_DATETIME_DEPENDENCY'
        profile={'canonical_table':name,'profile_id':name+'__PENDING_ROUTE_PROFILES',
            'tier_hint':tier,'evidence_notes':notes,'ticket_ref':ticket,
            'measurement_state':'PENDING_CURRENT_ROUTE_MEASUREMENT','verified_for_production':False,
            'measure_per':['physical_source_identity','view_or_projection_sha256','engine_driver_version','business_window','query_shape','source_visibility_cutoff'],
            'measurements_required':['first_row_seconds','full_fetch_seconds','rows','bytes','source_plan_or_index_evidence','timeout_cancel_verified','retry_resource_cost','p50_p95_when_sufficient_samples'],
            'query_warning_seconds':None,'query_cancel_seconds':None,'max_rows':None,'max_bytes':None,
            'freshness_lag_budget_seconds':None,'heartbeat_budget_seconds':None,'approved_query_budget_ref':None,
            'profile_missing_action':'REFUSE_PRODUCTION_READY_ALLOW_OFFLINE_DEVELOPMENT'}
        profiles.append(profile)
        seed.update({'failure_policy_ref':'故障隔离与继续执行规则.json',
            'performance_profile_ref':profile['profile_id'], 'deadline_state':'UNCONFIGURED',
            'monthly_rescan_policy_ref':'迟到漂移月度重扫策略.json' if name in DRIFT_TABLES else None,
            'long_lived_credential_ref':None,'running_writer_handoff_state':'NOT_LIVE_VERIFIED',
            'route_policy_ref':'LIS双源路由候选.json' if name.startswith('EMR_INSPECTION') else None})
        if name=='EMR_IN_OUT_AMOUNT':
            seed['legacy_view_transport_hint']='DATAX_ONLY_REPORTED_DO_NOT_AUTOFALLBACK'
            seed['alternative_route_evidence']='priority_extract_20261018/护理出入量通道复核_20261018/护理出入量_处理结论与续抽交接.md'
    failure={'package_id':package_id,'planning_only':True,'user_policy':'失败范围隔离并告警，继续其他可独立任务，失败项排队补抽',
        'default':'CONTINUE_INDEPENDENT_SCOPES','failure_terminal_success_allowed':False,'silent_skip_allowed':False,
        'persist':['task','source_identity','fixed_window_or_keyset_digest','attempt','error_class_and_safe_code','manifest_state','next_retry_or_manual_condition','owner','alert_incident','receipt_state','gap_ledger'],
        'rules':[
            {'error':'ROW_OR_GROUP_QUALITY','scope':'affected_record_group','state':'QUARANTINED','next':'其他完整合法组继续；原载荷持久后可推进捕获游标，但质量/装载仍未闭合'},
            {'error':'READ_SQL_OR_VIEW_ERROR','scope':'failed_window_or_route','state':'WAITING_VIEW_FIX','next':'保留失败窗和工单；继续独立日/表；不能伪造取到0行'},
            {'error':'TRANSIENT_READ_DISCONNECT','scope':'window_then_physical_source_if_repeated','state':'RETRYABLE_OR_WAITING_SOURCE','next':'有界退避抖动；源级熔断及单探针半开，不逐表重连风暴'},
            {'error':'ROW_OR_BYTE_CAP','scope':'incomplete_slice','state':'SPLIT_PENDING','next':'仅完整叶可复用；拆分树持久化，到最小粒度转稳定keyset或待处理'},
            {'error':'KNOWN_ROLLBACK','scope':'affected_apply_batch','state':'RETRYABLE','next':'确认回滚后同幂等键恢复；其他表继续'},
            {'error':'COMMIT_UNKNOWN','scope':'same_target_table_writer','state':'COMMIT_UNKNOWN','next':'冻结该表全部写任务，先核同事务凭据；其他表继续，不盲重放或切到下一天写'},
            {'error':'PARENT_PENDING','scope':'affected_child_keys_or_groups','state':'BLOCKED_DEPENDENCY','next':'暂存待父，其他已证父键的独立子组继续'},
            {'error':'SOURCE_IDENTITY_MISMATCH','scope':'affected_physical_source_routes','state':'BLOCKED_IDENTITY','next':'拒绝该源，其他已验证源继续'},
            {'error':'ALERT_RELAY_FAILURE','scope':'notification_channel','state':'ALERT_PENDING','next':'outbox持久重试/独立监测，合法抽取继续，不递归告警'},
            {'error':'CONTROL_STORE_OR_GLOBAL_FENCE_FAILURE','scope':'actual_shared_unprovable_scope','state':'SAFETY_HOLD','next':'无法持久断点或保证单写时暂停相关领取/写入；只有全局依赖确失效才全局暂停'},
        ],
        'source_circuit_key':'physical_source_identity_not_table_name',
        'retry_budgets':{'max_attempts':None,'max_elapsed_seconds':None,'backoff_jitter_required':True,'half_open_probes':1,'must_freeze_per_profile_before_enable':True},
        'watermark':'允许后续独立窗口完成并入区间账本；连续水位只到首个缺片前。质量已完整捕获可按原持久化规则推进捕获游标，装载/质量/回执仍单列未闭合。',
        'run_summary':['SUCCESS','PARTIAL_SUCCESS_WITH_BACKLOG','WAITING_SHARED_DEPENDENCY','SAFETY_HOLD'],
        'stop_all_on_first_error':False}
    dump(here,'故障隔离与继续执行规则.json',failure)
    rescan={'package_id':package_id,'planning_only':True,'enabled':False,'required_before_drift_tables_production_ready':True,
        'tables':DRIFT_TABLES,'cadence_candidate':'MONTHLY_COVERAGE_CYCLE','business_month_is_not_run_month':True,
        'managed_history_scope':'已接受历史基线业务月 + 2026至H0基线 + 此后纳管业务月，至少明确2025；E01填写，不猜起止月',
        'managed_history_start_month':None,'managed_history_end_month':None,'cycle_max_age_days':None,
        'coverage_ledger':['table','business_month','route_or_origin','last_complete_snapshot_cutoff','last_reconciled_at','next_due','pending_slices','failed_slices','unresolved_quality','overdue_reason'],
        'scope_missing_action':'BLOCK_THIS_RESCAN_READY_REPORT_COVERAGE_UNKNOWN',
        'budget':'E01按历史月/每源画像测算整轮成本与完成期限；优先每日，夜间错峰轮巡；到期未扫告警，不承诺未证明可完成的每月全扫',
        'logical_mode':'REPLACE_COMPLETE_BUSINESS_MONTH_OR_APPROVED_COMPLETE_SUBSLICES',
        'publish_order':['freeze_routes_and_scope','complete_bounded_source_capture','manifest_and_quality','stage_verify','obtain_same_table_writer_and_version_guard','approved_atomic_replace','readback_and_receipt','close_all_slices_then_business_month'],
        'delete_before_source_complete_allowed':False,'delete_commit_before_insert_allowed':False,
        'target_datetime_assumed':False,'window_target_proof':'实际目标业务列或经核完整键清单/来源归属；不能按目标不存在的DATETIME删',
        'atomicity':'源完整质量通过后，获批执行器在同事务删该发布范围+插完整stage并留提交证据；超预算按完整受控子窗发布，每月全片成功才闭合，父子可见性另外核实',
        'partial_quality_action':'整月替换不得含未解释隔离；合法组仅通过获批独立按键发布，月仍待补，原目标不盲删',
        'old_snapshot_guard':'获同表写锁后验证源截点/版本；不能把旧stage替换最新日批。无版本则受控重读或废弃旧stage。',
        'source_partition_guard':'LIS等多源不可单源整月删除；完整来源账本及父子覆盖先验',
        'limitations':'仅保证已纳管且完成轮巡的可见截点；任意更早/超范围历史修改仍须覆盖扩展或可靠变更日志，不声称无限历史无漏'}
    dump(here,'迟到漂移月度重扫策略.json',rescan)
    dump(here,'每表性能与通道画像候选.json',{'package_id':package_id,'planning_only':True,'count':77,'profiles':profiles,
        'alert_axes':'QUERY_SLOW/EXTRACT_FAILED看读取预算；SOURCE_LATE看数据可见性/新鲜度。不能用3分钟无结果一刀切。'})
    lis=[]
    for seed in seeds:
        if seed['canonical_table'] not in ['EMR_INSPECTION','EMR_INSPECTION_IMAGE','EMR_INSPECTION_ALLERGY','EMR_INSPECTION_ITEM']:continue
        current=next(x for x in seed['source_candidates'] if x['role']=='primary')
        old=next(x for x in seed['source_candidates'] if x['role']=='history')
        lis.append({'canonical_table':seed['canonical_table'],'current':current,'historical':old,
            'business_time_expression':None,'route_clock_and_timezone_verified':False,
            'segments':[
                {'start':None,'end_exclusive':'2023-10-01','sources':[old['object_id']]},
                {'start_inclusive':'2023-10-01','end_exclusive':'2024-01-01','sources':[old['object_id'],current['object_id']],'mode':'PRESERVE_DOCUMENTED_OVERLAP_REVERIFY_BOUNDARIES'},
                {'start_inclusive':'2024-01-01','end':None,'sources':[current['object_id']]},
            ],'current_evidence_state':'RECORDED_USER_AND_EXECUTOR_REPORT_NOT_NEW_LIVE_VERIFIED',
            'delete_other_origin_allowed':False,'automatic_business_dedupe_allowed':False,'history_slow_path_may_block_independently':True})
    dump(here,'LIS双源路由候选.json',{'package_id':package_id,'planning_only':True,'tables':lis,
        'authority':'执行产物/LIS双源架构记录_20261019.md，文中简述两段与Q4并行需结合读取；上线前逐表按真实业务时钟核边界',
        'overlap_state':'2023Q4业务级重复ID不同按既有保留口径；不静默去重或物理删另一源',
        'supersedes':'M-05瑞美放开2021/2022历史的旧归因已被双源证据替代；历史药敏/明细性能待核仍开放',
        'all_modes_use_routes':['T1','LATE_BACKLOG','LOOKBACK','MONTHLY_RESCAN','HISTORICAL_REPAIR']})
    handoff={'package_id':package_id,'planning_only':True,'snapshot_captured':False,'state':'LIVE_SNAPSHOT_REQUIRED_AT_E01_AND_REFRESH_AT_CUTOVER',
        'source':'8.53按ops-runbook受控只读进程/状态文件核验；本轮未SSH',
        'user_reported_tasks':['discharge_manual2（用户称今晚收尾，未新核）','出院30个月旧数据重刷（待排期，不据此启动）','dqueue','gap_exec'],
        'collect_allowlist':['host','capture_time','pid','ppid','process_start_time','elapsed_seconds','comm','allowlisted_script_name','script_sha256','canonical_tables','business_windows','write_mode','writer_owner','checkpoint_or_receipt_safe_ref','commit_unknown_state'],
        'never_collect':['environment_values','full_command_line','credentials','patient_identifiers_or_file_payload'],
        'handoff_template':{'table':None,'old_writer_identity':None,'latest_progress_evidence':None,'remaining_windows':None,'pending_commit_resolved':None,'old_writer_stopped_or_fenced_evidence':None,'new_writer_lease_and_target_fence':None,'cutover_snapshot_ref':None,'handoff_owner':None},
        'gates':['没有快照不视为旧写者已停','切换前新快照核PID+启动时间防PID复用','不因文件done判所有窗成功','不杀原进程、不覆盖在跑脚本、不启动第二正式writer'],
        'local_development_not_blocked_by_snapshot_missing':True}
    dump(here,'在跑任务交接快照模板.json',handoff)
    assets=[
        ('current_source_mapping',run/'all_views_review_20261019/字典核查对象与源配置_不含凭据.json','CURRENT_LOCAL_MAPPING_NOT_PRODUCTION_VERIFIED'),
        ('gap_exec_reference',run/'priority_extract_20261018/大缺口补抽_20261018/gap_exec.py','REFERENCE_ONLY_NO_IMPORT_NO_EXECUTE'),
        ('lis_dual_source',run/'priority_extract_20261018/大缺口补抽_20261018/执行产物/LIS双源架构记录_20261019.md','RECORDED_EVIDENCE_NOT_RETESTED'),
        ('manual_M01_M08',run/'priority_extract_20261018/大缺口补抽_20261018/执行产物/待人工与受阻清单_20261018.md','M05_SUPERSEDED_BY_LIS_DUAL_SOURCE'),
        ('conservation_report',run/'priority_extract_20261018/大缺口补抽_20261018/执行产物/执行结果汇总_20261018.md','REGRESSION_REFERENCE_NOT_CURRENT_TRUTH'),
        ('quantity_followup',run/'priority_extract_20261018/大缺口补抽_20261018/执行产物/数量核查后续补抽_20261019.md','HAS_OLDER_LIS_SINGLE_SOURCE_CLAIMS_DO_NOT_REUSE'),
        ('nursing_patient_route',run/'priority_extract_20261018/护理出入量通道复核_20261018/护理出入量_处理结论与续抽交接.md','SCOPED_ALTERNATIVE_CONTROLLED_ROUTE'),
        ('discharge_old_proposal',run/'priority_extract_20261018/大缺口补抽_20261018/执行产物/V_EMR_DISCHARGE_RECORD_优化建议_20261019.sql','REJECTED_AS_DIRECTLY_EXECUTABLE'),
        ('discharge_review',run/'discharge_opt_review_20261019/复核报告与整改建议.md','CURRENT_REVIEW_WITH_OPEN_QUALITY_ISSUES'),
        ('discharge_full_ddl',run/'discharge_opt_review_20261019/V_EMR_DISCHARGE_RECORD_完整替换_含DATETIME.sql','LOCAL_STATIC_ONLY_DEPLOYMENT_AND_PERFORMANCE_UNVERIFIED'),
    ]
    refs=[]
    for code,path,state in assets:
        refs.append({'code':code,'path':str(path),'exists':path.exists(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,'evidence_state':state})
    gap_path=next(p for key,p,state in assets if key=='gap_exec_reference')
    code=gap_path.read_text(encoding='utf-8-sig');tree=ast.parse(code)
    fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='same_value')
    segment=ast.get_source_segment(code,fn)
    previous=json.loads((here/'_history/v1.1/77项任务候选种子.json').read_text(encoding='utf-8'))['items']
    mapping_changes=[]
    for before,after in zip(previous,seeds):
        for a,b in zip(before['source_candidates'],after['source_candidates']):
            assert {k:v for k,v in a.items() if k!='object_name_candidates'}=={k:v for k,v in b.items() if k!='object_name_candidates'},'SOURCE_IDENTITY_CHANGED_REQUIRES_REVIEW'
            if a['object_name_candidates']!=b['object_name_candidates']:
                mapping_changes.append({'table':after['canonical_table'],'object_id':b['object_id'],
                    'before_aliases':a['object_name_candidates'],'after_aliases':b['object_name_candidates'],
                    'state':'CURRENT_SHARED_INPUT_ALIAS_DRIFT_RECORDED_NOT_LIVE_VERIFIED'})
    dump(here,'实测参考资产与证据指纹.json',{'package_id':package_id,'read_only_references':True,'server_files_not_freshly_verified':True,'assets':refs,
        'source_alias_changes_since_v11':mapping_changes,
        'gap_exec_findings':{'same_value_calls_float':'float(' in segment,'same_value_strips_all_strings':'.rstrip()' in segment,
            'policy':'只拆取经审阅纯逻辑重写，不import/执行原文件，不复制其连接/写入/凭据fallback；类型比较修正后独立测试'},
        'claimed_numbers':{'doc_order_late_inserted':42918,'in_fee_late_inserted':109,'status':'LOCAL_EXECUTOR_REPORT_AND_USER_REPORTED_NOT_NEW_DATABASE_RECONCILIATION'},
        'redaction':'只登记文件指纹及聚合事实，不复制人工单中的原始ID/载荷/敏感内容'})
    tickets=[
        {'ticket':'E01-DISCHARGE-PERF','table':'EMR_DISCHARGE_RECORD','state':'VERIFY_CURRENT_DEFINITION_AND_PERFORMANCE','detail_ref':'R189:discharge_opt_review_20261019/复核报告与整改建议.md','action':'按正确候选人工修复并验外层窗口下推，不能执行原占位稿或承诺亚秒'},
        {'ticket':'E01-DISCHARGE-QUALITY','table':'EMR_DISCHARGE_RECORD','state':'OPEN','detail_ref':'R189:discharge_opt_review_20261019/问题与后续核查.json','action':'医师/证号各113、正文1条旧样本缺失需定位修复；不视为当前全量计数'},
        {'ticket':'E01-DATETIME-DEPENDENCY','tables':DEPENDENT_TIME_TABLES,'state':'REVERIFY_REPORTED_CHANGE','action':'核当前DATETIME类型/表达式/依赖指纹与下推，不把辅助列写目标'},
        {'ticket':'E01-LIS-LEGACY-ACCESS','tables':['EMR_INSPECTION_ALLERGY','EMR_INSPECTION_ITEM'],'state':'OPEN_HISTORICAL_ROUTE_ONLY','action':'历史TEST路线先有界访问优化，M-05改为双源，不要求瑞美凭空补上线前历史'},
        {'ticket':'E01-WRITER-HANDOFF','state':'LIVE_SNAPSHOT_REQUIRED','action':'核8.53在跑进程与未决提交，逐表交接，开发可继续但新正式写者不能抢跑'},
        {'ticket':'E01-CREDENTIAL-LIFETIME','state':'LONG_LIVED_SECRET_REF_REQUIRED','action':'长期服务接受控密码库，禁止沿用/tmp/e2_env；临时job仅运行时解析后私有短期物化'},
    ]
    dump(here,'E01已知人工工单种子.json',{'package_id':package_id,'planning_only':True,'tickets':tickets,'legacy_manual_ref':'实测参考资产与证据指纹.json#manual_M01_M08','never_auto_close':True})
    dump(here,'回读类型规整契约.json',{'package_id':package_id,'planning_only':True,
        'CHAR':'仅已核固定宽CHAR/NCHAR及字段契约去右侧填充空格，不统一strip全部Unicode空白',
        'VARCHAR_LOB_PATH':'默认完整比较，保留有意义空白/换行，不套CHAR rstrip；另有明确业务规范才变换',
        'NUMERIC':'int/Decimal精确十进制比较；120和120.00值等价；禁经float、禁任意容差、禁未经批准量化金额',
        'FLOAT_FROM_DRIVER':'按真实逻辑类型单独处理；声明Decimal/金额却仅获float需兼容验收，不以float比对精确数',
        'DATE_TIMESTAMP':'核逻辑时区及精度，DATE秒与TIMESTAMP分数秒不静默归一；动态SYSTEM_TIME从业务hash排除',
        'NULL_EMPTY':'保留原已批准字段语义，不把NULL/空串/占位随意互换',
        'comparison_audit':'保存规则版本、元数据及内容摘要；类型规整不能修改写入原值来掩盖差异'})
    return {'failure':failure,'rescan':rescan,'profiles':profiles,'lis':lis,'handoff':handoff,'tickets':tickets}


def enrich_contract(contract):
    contract.update({'failure_policy':'故障隔离与继续执行规则.json','late_drift_rescan':'迟到漂移月度重扫策略.json',
        'performance_profiles':'每表性能与通道画像候选.json','lis_routes':'LIS双源路由候选.json',
        'writer_handoff':'在跑任务交接快照模板.json','type_normalization':'回读类型规整契约.json',
        'review':'实测建议评估与计划修订说明.md','user_default_error_action':'ISOLATE_FAILED_SCOPE_ALERT_AND_CONTINUE_INDEPENDENT_WORK',
        'long_lived_credentials':'APPROVED_SECRET_STORE_REF_NOT_TMP_ENV',
        'daily_report_required':['failed_windows_and_next_retry','commit_unknown_tables','affected_child_groups','monthly_coverage_overdue','deadline_unconfigured','relay_delivery_state'],
        'deadline_unknown_sla':'UNKNOWN_NOT_MET_NOT_ASSUMED_AT_RISK'})
    for t in contract['tasks']:
        t['operational_refs']=['故障隔离与继续执行规则.json']
        if t['id']=='E01':t['operational_refs']+=['每表性能与通道画像候选.json','LIS双源路由候选.json','在跑任务交接快照模板.json','实测参考资产与证据指纹.json','E01已知人工工单种子.json']
        if t['id']=='E06':t['operational_refs']+=['迟到漂移月度重扫策略.json']
        if t['id'] in ['E04','E05']:t['operational_refs']+=['回读类型规整契约.json']
        t['recovery']='依故障隔离规则持久化失败范围/断点并告警，继续独立任务，失败不是成功或永久跳过；commit未知只冻结同表写者；共享源故障只熔断同源。'


def add_workbook_sheets(book, assets, style):
    sheet=book.create_sheet('故障后继续与告警')
    sheet.append(['错误','隔离范围','状态','继续及补抽动作'])
    for r in assets['failure']['rules']:sheet.append([r['error'],r['scope'],r['state'],r['next']])
    style(sheet,[35,40,30,100])
    sheet=book.create_sheet('77表性能通道画像')
    sheet.append(['规范表','画像提示','证据边界','慢查询阈值','取消预算','新鲜度预算','生产已验','工单'])
    for r in assets['profiles']:sheet.append([r['canonical_table'],r['tier_hint'],'\n'.join(r['evidence_notes']),None,None,None,False,r['ticket_ref']])
    style(sheet,[44,45,110,20,20,20,18,50])
    sheet=book.create_sheet('历史月轮巡与双源')
    sheet.append(['对象','策略','范围及门禁','当前状态'])
    for table in DRIFT_TABLES:sheet.append([table,'MONTHLY_COVERAGE_CYCLE','纳管历史业务月账本；先完整stage后受控原子范围替换；不只扫当前月','DISABLED_SCOPE_BUDGET_PENDING'])
    for r in assets['lis']:sheet.append([r['canonical_table'],'LIS_DUAL_SOURCE','2023Q4保留双源并行；边界/业务时钟待逐表验；重扫不可单源整月删','RECORDED_NOT_NEW_LIVE_VERIFIED'])
    style(sheet,[48,35,120,45])
    report=book['每日运行日报模板']
    for name in ['失败业务窗/待补','下次重试/责任人','deadline是否配置','SLA未知原因','月度重扫最近全核/到期/欠账','告警投递及detail_ref']:
        report.cell(1,report.max_column+1,name)
    style(report,[16,40,55,18,12,12,14,12,16,22,16,16,25,25,30,45,45,40,25,45,60,60])


def validate_assets(here, assets, seeds, contract):
    checks=[]
    assert len(assets['profiles'])==77 and all(not p['verified_for_production'] for p in assets['profiles']);checks.append('77表逐路画像待实测，未用统一3分钟判源晚到')
    assert assets['rescan']['tables']==DRIFT_TABLES and assets['rescan']['business_month_is_not_run_month'] is True;checks.append('两已证漂移表明确历史业务月轮巡及覆盖欠账，不只运行当月')
    assert not assets['rescan']['delete_before_source_complete_allowed'] and not assets['rescan']['delete_commit_before_insert_allowed'];checks.append('月重扫先完整质量stage，后受控原子发布，禁止先删后等源')
    assert len(assets['lis'])==4 and all(len(r['segments'][1]['sources'])==2 and not r['delete_other_origin_allowed'] for r in assets['lis']);checks.append('LIS四表Q4双源并行保留，旧路线受阻不误用单源')
    assert assets['handoff']['snapshot_captured'] is False and all(s['running_writer_handoff_state']=='NOT_LIVE_VERIFIED' for s in seeds);checks.append('在跑快照未采不冒充旧写者已停，E10切换前重核')
    assert not assets['failure']['stop_all_on_first_error'] and not assets['failure']['silent_skip_allowed'];checks.append('故障局部隔离继续并持久待补，不首错全停、不静默跳过')
    unknown=next(x for x in assets['failure']['rules'] if x['error']=='COMMIT_UNKNOWN');assert unknown['scope']=='same_target_table_writer';checks.append('未知提交冻结同表写者、父子只限相关组，其他表继续')
    assert all(s['deadline'] is None and s['deadline_state']=='UNCONFIGURED' for s in seeds);checks.append('deadline缺失在日报显式且不虚报SLA达标')
    assert all(s['long_lived_credential_ref'] is None for s in seeds) and contract['long_lived_credentials']=='APPROVED_SECRET_STORE_REF_NOT_TMP_ENV';checks.append('长期任务凭据只引用受控密码库，禁沿用/tmp补抽环境')
    normal=json.loads((here/'回读类型规整契约.json').read_text(encoding='utf-8'));assert '禁经float' in normal['NUMERIC'] and '默认完整比较' in normal['VARCHAR_LOB_PATH'];checks.append('回读规整区分CHAR/VARCHAR及精确Decimal，不照搬旧float/rstrip')
    assert all((here/name).exists() for name in EXTRA_FILES);checks.append('实测评估、策略、交接及参考指纹齐备，未把软件预期当已实现')
    return checks
