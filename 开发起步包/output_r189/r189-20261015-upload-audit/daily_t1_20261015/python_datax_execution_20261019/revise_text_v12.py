"""Apply v1.2 planning additions to the existing canonical documents, once."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE/'Python与DataX统一T加1顶层设计及长任务执行计划.md'
PROMPT = HERE/'给执行AI的长任务启动提示词.md'


def change(text, old, new):
    assert text.count(old)==1, old[:70]
    return text.replace(old,new,1)


def main():
    plan=PLAN.read_text(encoding='utf-8')
    assert '## 13. v1.2实测约束与默认失败策略' not in plan,'Already revised; do not apply again.'
    plan=change(plan,'# Python与DataX统一T+1顶层设计及长任务执行计划',
        '# Python与DataX统一T+1顶层设计及长任务执行计划\n\n当前v1.2，维持10批。新增历史业务月漂移重扫、77表按路线画像/LIS重叠路由、在跑写者快照及失败隔离继续；v1.1归_history/v1.1/。详见同目录`实测建议评估与计划修订说明.md`。')
    plan=change(plan,'未核当前在跑任务、插件版本/定制实现、调度配置及真实性能。',
        '本轮没有新采当前在跑任务；E01必须留8.53进程快照，E10逐表切换前重新核实，不能把manual2今晚结束/dqueue/gap_exec等用户时点陈述当成已停证据。插件版本/定制实现、调度配置及逐路线真实性能仍需核。')
    plan=change(plan,'### 3.2 持久化实体（候选设计，非已建表）',
        'TaskSpec还必须关联：failure_policy、逐路线performance_profile、LIS四表route_segments/来源归属、DATETIME依赖指纹、monthly_rescan_policy及历史月覆盖范围、long_lived_credential_ref、旧写者交接状态和deadline_state。UNKNOWN仅阻塞相应生产就绪，不阻止E01合同模型及后续本地软件开发。机器候选全部保持disabled/UNKNOWN。\n\n### 3.2 持久化实体（候选设计，非已建表）')
    plan=change(plan,'## 5. 运行状态机及恢复',
        '### 4.1 迟到漂移的月度补偿（必须实现）\n\n至少EMR_DOC_ORDER_CHECK、EMR_IN_FEE_INFO_CHILD在E06实现历史业务月轮巡；42918和109是既有执行报告/用户陈述，不是本轮重新对账。业务月不同于运行月，只重扫当月无效。E01冻结已纳管历史范围（含2025及已接受基线/2026连续性）、每源成本、轮巡周期/最长未核时长，E02记录每月/来源/分片覆盖，E07日报及RESCAN_OVERDUE显式欠账；范围或容量未知不能报覆盖就绪。\n\n原“删业务月+插业务月”仅为获批发布语义：先完整捕获、质量和stage，再由适用执行器同事务替换完整发布范围并留凭据；失败/隔离未解释/真零未证不先删目标。超事务预算按经核完整子窗发布，整月全片对账通过才闭合，父子可见性及目标无DATETIME另外证明。与日批共用单写和版本保护；旧stage不得覆盖新内容。完整机器规则见`迟到漂移月度重扫策略.json`，本计划没有授予执行删插或cron的批准。\n\n## 5. 运行状态机及恢复')
    plan=change(plan,'附加状态：WAITING_SOURCE、',
        '默认故障行为为`ISOLATE_FAILED_SCOPE_ALERT_AND_CONTINUE_INDEPENDENT_WORK`，详见`失败后继续抽取与补抽规则.md`及机器规则。失败不是SKIP成功；持久待补和告警后，其他独立表/日期/合法记录组继续，总体PARTIAL_SUCCESS_WITH_BACKLOG。COMMIT_UNKNOWN冻结同表所有写任务；父失败只等相关子键；共享源故障只熔断该源；只有共享控制存储/身份/栅栏确实影响全部时才全局暂停。\n\n附加状态：WAITING_SOURCE、')
    plan=change(plan,'### 6.3 可信分母与核对',
        '### 6.2.1 回读类型规整与真实故障复用\n\n只对已核CHAR/NCHAR按填充规则去右侧空格；VARCHAR、正文、路径默认保留原有空白。精确Decimal/int比较不转float，不任意容差/量化金额；日期分数秒不静默丢失。gap_exec.py可参考时间适配、二分、字节/字符和冲突检测，不能直接import原脚本或照搬其same_value的全字符串rstrip/float比较。规则见`回读类型规整契约.json`。\n\n### 6.3 可信分母与核对')
    plan=change(plan,'## 9. 建议代码与接口落点（尚未实现）',
        '### 8.1 每表画像、双源、拆窗与凭据\n\nE01对77表按源身份/视图或投影指纹/引擎/窗口分级测首行和完整取数、行字节及取消能力，记录新鲜度、心跳和查询的独立预算。QUERY_SLOW不等于SOURCE_LATE；出院185秒旧观测、参数化SELECT约2/3秒及未现场验的新视图DDL分开。没有已核画像不能套统一3分钟发晚到告警，未测阈值保持待配。\n\nLIS所有日常、回看和重扫共用四表双源路由；2023-10前ODS_TEST，2023Q4保留文档中的ODS/瑞美并行，之后瑞美，切换时钟/边界逐表复核。旧药敏/明细慢路线局部受阻；不按注册表单源映射重扫整段或删另一源。护理原视图DataX-only线索与B04患者键受控Python路线分开，不自动fallback。三张DATETIME依赖为住院费用明细、门诊费用明细、医嘱检查。\n\n断连按物理源熔断，有界重试/抖动且仅单探针半开；六小时结算潮超5万行或字节预算时持久二分拆窗，完整叶才装载。到最小精度仍超限转已核稳定keyset，无键则待处理；不能无限递归或截断成功。\n\n长期任务必须使用受控密码库secret_ref，禁止沿用/tmp/e2_env等补抽环境。DataX运行时解析后私有短期job可按原安全清理规则物化，受控凭据不因此进入代码/AI/参数/日志。\n\n## 9. 建议代码与接口落点（尚未实现）')
    plan=plan.replace('## 10. 长任务批次E01—E10（v1.1）','## 10. 长任务批次E01—E10（v1.2）')
    plan=change(plan,'本轮将17批合并为10批，保留全部内部工作及验收，新增公共企微告警对接。',
        '沿用v1.1将17批合并为10批的结构，v1.2补充实测故障与漂移机制，保留全部内部工作及验收和公共企微告警契约。')
    rows={
        'E01':('起步盘点、77项配置/CLI；逐表路线性能/双源/DATETIME依赖/长期凭据；8.53写者快照及既有人工项','77项disabled/UNKNOWN；画像/路由/进程证据分已知与待核，E01本地模型不等待live批准'),
        'E02':('Repository/状态机/幂等租约；固定窗/分页/DAG；失败缺口队列、历史月来源覆盖账；告警incident/outbox','后续独立窗继续但连续水位不跨缺片；失败不计成功，commit未知不盲重放'),
        'E03':('Python/DataX适配器；受控类型/流式/取消、监听器断连恢复、递归二分/稳定keyset；参考gap纯逻辑','6小时5万+完整拆分；源级熔断单探针，DataX-only按路线生效，无授权不fallback'),
        'E04':('暂存完整性、V1.3/长度/精度、组守恒/hash、质量隔离；CHAR/VARCHAR/Decimal类型规整','坏组隔离而独立合法组继续；不统一rstrip、不转float、缺片不装正式'),
        'E05':('受控ApplyPort、版本/同事务提交凭据、键内容核对；月重扫stage后原子范围发布及父子/来源保护','未批准拒写；先完整后替换，不先删；commit未知冻结同表、旧stage不覆新'),
        'E06':('调度与局部恢复；历史业务月轮巡/覆盖到期；按画像预算/源级熔断；原企微v2告警/outbox/独立巡检','失败告警入待补后继续独立任务；月不漏/欠账显式，202与送达分开，事件原字节不变'),
        'E07':('人工工单闭环、日报/反馈、deadline未配/失败窗/重扫欠账；建议动作/detail_ref；完整故障矩阵','坏表不拖独立表；等待和真实通过分开；原M-05按LIS双源证据修订不重做已闭合补抽'),
        'E10':('逐源分组灰度；最新8.53快照及单表旧写者/未决提交交接；至少7业务日观测及运维交接','切换/观测/运维分开；不据今晚结束/done推断已停；漂移覆盖和告警恢复各有证据'),
    }
    lines=plan.splitlines(keepends=True)
    for i,line in enumerate(lines):
        if not line.startswith('| E'):continue
        parts=[x.strip() for x in line.strip().strip('|').split('|')]
        if parts[0] in rows:
            objective,accept=rows[parts[0]]
            lines[i]='| '+parts[0]+' | '+parts[1]+' | '+objective+' | '+accept+' |\n'
    plan=''.join(lines)
    plan += '''
## 13. v1.2实测约束与默认失败策略

完整逐项评估见`实测建议评估与计划修订说明.md`；失败行为以`失败后继续抽取与补抽规则.md`及`故障隔离与继续执行规则.json`实现。月扫、画像、LIS路由、进程交接、类型规整及参考指纹都已进入机器契约和xlsx，不只留在本段说明。

日报必须单列失败窗/受影响父子组/COMMIT_UNKNOWN/下次补抽与责任人、月度覆盖欠账、DEADLINE_UNCONFIGURED和A12省端反馈、告警入队与实际送达。未配deadline为SLA_UNKNOWN，不猜截止、不标SLA达标。运维告警包含建议动作及安全detail_ref，依旧不带患者/SQL/secret，relay失败不拖正常抽取。

E01在live快照/画像批准未齐时仍可完成本地契约/采集器设计并推进E02—E07；不得把这些live项标VERIFIED。E09试点只允许范围内画像/路由/凭据及写者清晰的任务，E10切换前必须刷新进程与未决提交证据。所有新增验收场景只是NOT_RUN预期，未实现/未部署，不在本轮生产执行重扫或推消息。
'''
    plan=plan.replace('版本v1.1，2026-10-19','版本v1.2，2026-10-19',1)
    PLAN.write_text(plan,encoding='utf-8')

    prompt=PROMPT.read_text(encoding='utf-8').replace('R189-T1-ENGINEERING-20261019-v1.1','R189-T1-ENGINEERING-20261019-v1.2')
    prompt=prompt.replace('本包已重组为v1.1的10批','本包沿用10批并升至v1.2')
    prompt=change(prompt,'权限与局部依赖：','''v1.2必须新增实现（并保留原告警/门禁契约）：

- 先读实测建议评估与计划修订说明.md、失败后继续抽取与补抽规则.md；程序全量校验故障隔离与继续执行规则.json、迟到漂移月度重扫策略.json、每表性能与通道画像候选.json、LIS双源路由候选.json、在跑任务交接快照模板.json、回读类型规整契约.json、实测参考资产与证据指纹.json、E01已知人工工单种子.json。大JSON用程序校验和任务切片，不倾倒77项全量到上下文。
- 用户指定默认：失败范围持久化/告警/入待补，继续其他独立日/表/合法组；不是首错全停，也不把失败写成SKIP成功。连续水位不越缺片；捕获完整质量隔离的游标按原策略与装载/闭合分离。commit未知冻结该表全部写者，父失败只阻对应子组，源风暴只熔断物理源；共享控制状态确实全局不可用才全局暂停。
- E01盘点全部77表逐路线性能、DATETIME依赖、LIS四表双源及Q4重叠、长期凭据和8.53写者快照。manual2今晚结束、30个月待刷/dqueue/gap_exec均需当前快照，不据聊天/done抢写；E10切换前重采。快照只输出白名单元数据，不读取/打印环境或原始完整命令行。
- E06必须实现至少EMR_DOC_ORDER_CHECK、EMR_IN_FEE_INFO_CHILD的历史业务月轮巡，含已纳管2025等范围及每月/来源/分片欠账，不只运行当月。预算、周期、最长未核时长经E01冻结。源完整+质量+stage之后才获批原子替换完整范围；禁止先删后等源/先删提交。超预算细分、旧stage不覆新、双源不删另一源，原月全片闭合前不是成功。本计划不授权生产删插/cron。
- 护理原整视图DataX-only与B04患者键Python通道分开，均按源身份/权限/路线证据配置；LIS历史慢路线受阻只影响该段，回看/重扫禁止注册表单源硬跑。
- 参考gap_exec纯逻辑但不import/执行/复制连接写入和凭据fallback。其same_value的float和全部字符串rstrip不能照搬；按CHAR元数据、VARCHAR原值及精确Decimal规范测试。
- 加监听器三错误风暴、6小时5万+拆窗与精确类型回读案例。递归拆分有深度/粒度/总预算，到限转已核稳定keyset或局部待处理；所有叶完整之前不算捕获完整。
- 查询耗时/心跳/源可见性分别按表路线画像定阈值，QUERY_SLOW不等于SOURCE_LATE；出院原占位优化稿不能直接用或承诺亚秒，新普通视图性能未验。deadline未配在日报单列并标SLA_UNKNOWN/A12待办。
- 长期系统仅受控密码库secret_ref，禁止沿用/tmp/e2_env补抽环境；授权worker运行时解析/私有短期DataX job按原规则清理。告警必须有建议动作及安全detail_ref，202/逐目标送达/不可变字节/revision/401规则不变，通知失败不阻合法抽取。

权限与局部依赖：''')
    PROMPT.write_text(prompt,encoding='utf-8')
    alert=HERE/'企业微信公共告警接口对接设计.md'
    text=alert.read_text(encoding='utf-8').replace('189抽取工程v1.1告警对接契约','189抽取工程v1.2告警对接契约',1)
    text += '''
## 7. v1.2局部继续、分级阈值与建议动作

失败先持久断点/待补/outbox，再调度其他独立表/窗/合法组；commit未知锁住同表写者，源级连接风暴按物理源聚合并单探针恢复。告警服务失败自身不扩大成全部抽取停止。

SOURCE_LATE仅表示数据未达已约定可见/新鲜度；QUERY_SLOW按具体路线的首行/完整读取阈值判定；心跳另有预算。出院旧185秒不能套3分钟源晚到；画像未配置时保持待配置，不能捏一个统一阈值。新增RESCAN_OVERDUE表示纳管历史业务月覆盖欠账，DEADLINE_UNCONFIGURED在日报单列，deadline未知不伪算SLA_AT_RISK。

运维消息body必须有“建议动作”，metadata允许recommended_action及detail_ref；仍按既有v2字段，不新增顶层协议字段。示例：建议动作=“按工单核出院日期下推，修复后只重试失败窗”；detail_ref=“R189:discharge_opt_review_20261019/复核报告与整改建议.md”。引用由服务端只读受权解析，不携患者/SQL/token，不可成为任意URL。最多32键，事件冻结后不因更新动作而改原字节，需要新revision。

新增规则不改变HMAC、401停盲重试、202仅入队/逐目标送达、不可变字节及通知订阅管理员门禁。本轮没有真实外发或修改qywx。
'''
    alert.write_text(text,encoding='utf-8')
    print('Canonical plan, prompt and alert design revised to v1.2; no runtime implementation.')


if __name__=='__main__':main()
