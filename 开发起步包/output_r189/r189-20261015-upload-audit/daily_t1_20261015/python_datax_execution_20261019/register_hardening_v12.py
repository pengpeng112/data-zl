"""Register v1.2 planning delivery in original task without changing running jobs."""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

HERE=Path(__file__).resolve().parent
RUN=HERE.parents[1]
ROOT=RUN.parents[2]
REL=HERE.relative_to(ROOT/'开发起步包').as_posix()
DESKTOP=Path('D:/Users/Administrator/Desktop/三甲复审/6、数管中心三甲数据上报/数据接口规范+值域2.3')


def main():
    contract=json.loads((HERE/'长任务执行契约.json').read_text(encoding='utf-8'))
    validation=json.loads((HERE/'计划包离线验收.json').read_text(encoding='utf-8'))
    independent=json.loads((HERE/'交付独立核对.json').read_text(encoding='utf-8'))
    assert validation['checks_passed']==28 and independent['all_pass'] and independent['checks_passed']==22
    cp=RUN/'checkpoint.json'
    base=hashlib.sha256(cp.read_bytes()).hexdigest()
    data=json.loads(cp.read_text(encoding='utf-8'))
    node=data['daily_t1']['engineering_execution_20261019']
    assert all(b['state']=='NOT_STARTED' for b in node['batches'].values()),'PRESERVE_EXECUTOR_PROGRESS_REVIEW_REQUIRED'
    node.setdefault('version_history',[])
    if not any(x.get('version')=='1.1' for x in node['version_history']):
        node['version_history'].append({'version':'1.1','package_id':node['package_id'],'archive':'daily_t1_20261015/python_datax_execution_20261019/_history/v1.1/','planning_validation':node['planning_validation']})
    node.update({'package_id':contract['package_id'],'version':'1.2','updated_utc':datetime.now(timezone.utc).isoformat(),
        'state':'PLAN_READY_HANDOFF_DELIVERED_ENGINE_NOT_IMPLEMENTED',
        'planning_validation':'28规划检查+22独立交付核对通过；10批、77disabled/UNKNOWN候选、112未执行验收预期、10页xlsx；引擎未实现，未上线/未真实告警',
        'failure_policy':'daily_t1_20261015/python_datax_execution_20261019/故障隔离与继续执行规则.json',
        'user_error_policy':'隔离失败范围+持久待补+告警，继续独立任务；失败不算成功；未知提交冻结同表写者，父失败只等相关子组',
        'operational_additions':['历史业务月轮巡及覆盖欠账','77表逐路线性能/通道画像','LIS四表Q4双源重叠保护','E01/E10在跑写者快照','监听器风暴/细分/类型真实用例','长期secret_ref禁临时env','deadline未配单列','建议动作/detail_ref'],
        'new_input_limits':['月轮巡起止范围/周期/预算待E01冻结','所有逐路线画像/阈值待当前实测','在跑快照本轮未采，不能推断旧writer已停','LIS边界/业务时钟仍需核','新视图实际部署/下推性能待核，原错误稿不可用'],
        'implementation_tests_run':0,'business_queries':0,'production_changes':0,'real_alerts_sent':0})
    data['updated_on']='2026-10-19'
    data.setdefault('previous_action_before_t1_v12_20261019',data.get('current_action'))
    data['current_action']='T+1执行包就地升v1.2，保留10批和既有企微/安全门禁；补历史月漂移轮巡、每表画像/双源Q4路由、在跑快照，以及失败隔离告警后继续独立任务。112未运行预期/28计划检查/22独立核对通过，10页xlsx和zip已重建。原v1.1归档；工程未实现、未SSH/连库/启停/cron/外发，待执行AI按新版继续。'
    for waiting in data.get('waiting',[]):
        if waiting.get('kind')=='WAITING_INPUT_AND_INCREMENTAL_DESIGN':
            waiting['item']='每日T+1省端截止/达标环节/回执A12及真实源变更撤销依据仍待核。v1.2已明确迟到历史月轮巡与失败继续机制；E01仍须冻结历史月范围/轮巡预算、逐路线性能/时钟/长期凭据和当前写者快照，不能把设计当当前生产已配置。'
            waiting['allows']='依v1.2继续本地工程开发、纯逻辑与候选配置，局部待核不阻独立任务'
    assert hashlib.sha256(cp.read_bytes()).hexdigest()==base,'CONCURRENT_CHECKPOINT_CHANGE'
    cp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    extra=' **v1.2实测补强**：[评估说明]('+REL+'/实测建议评估与计划修订说明.md)/[失败继续规则]('+REL+'/失败后继续抽取与补抽规则.md)；新增历史业务月轮巡/77表画像/LIS重叠路由/写者快照及局部失败继续，原告警和内部门禁保留。112验收预期、28规划检查+22独立核对、10页xlsx；仍未实现部署或实际告警。'
    for name,prefix in [('README.md','| P0 | `189_'),('55_系统未完成事项统一执行计划.md','| 189/191 |')]:
        path=ROOT/'开发起步包'/name
        text=path.read_text(encoding='utf-8')
        lines=text.splitlines(keepends=True)
        matching=[i for i,l in enumerate(lines) if l.startswith(prefix)]
        assert len(matching)==1
        i=matching[0]
        if 'v1.2实测补强' not in lines[i]:
            lines[i]=lines[i].replace('当前T+1工程执行入口（v1.1，10批及企微告警）','当前T+1工程执行入口（v1.2，10批/故障继续/历史月轮巡）')
            lines[i]=lines[i].replace('88验收预期','112验收预期').replace('17计划检查通过','28规划检查+22独立核对通过')
            anchor='**当前T+1工程执行入口（v1.2，10批/故障继续/历史月轮巡）**'
            assert anchor in lines[i]
            lines[i]=lines[i].replace(anchor,anchor+extra,1)
        text=''.join(lines)
        if name=='README.md':
            entry='- 2026-10-19 | **189 T+1执行包v1.2实测补强与失败继续** | 同目录就地升级、v1.1归_history/v1.1。10批不增，补纳管历史业务月轮巡/原子发布、77表路线画像、LIS Q4双源与写者快照；失败隔离持久待补+告警后继续独立任务，未知提交限同表。增24预期到112，28规划+22独立核对通过，xlsx十页/zip重建；长期凭据/缺deadline/动作入口及类型规整已明确。未实现引擎、未连接/改在跑链/外发，原checkpoint完成与待核同步。\n\n'
            if entry not in text:text=text.replace('## 目录更新记录\n\n','## 目录更新记录\n\n'+entry,1)
        path.write_text(text,encoding='utf-8')
    index=ROOT/'INDEX.md';text=index.read_text(encoding='utf-8')
    lines=text.splitlines(keepends=True)
    for i,line in enumerate(lines):
        if line.startswith('| Python与DataX统一每日T+1抽取工程长任务 |'):
            lines[i]=line.replace('v1.1：77项/88验收预期','v1.2：77项/112验收预期')
            if '历史月轮巡' not in lines[i]:lines[i]=lines[i].rstrip('\n').rstrip('|').rstrip()+'；新增历史月轮巡、路线画像/双源/写者快照、失败隔离继续并告警；工程未实现 |\n'
    index.write_text(''.join(lines),encoding='utf-8')

    sessions=DESKTOP/'governance/06、会话记录'
    folder=sessions/'025_20261019_T加1计划实测补强与失败继续';folder.mkdir(exist_ok=True)
    report=(HERE/'实测建议评估与计划修订说明.md').as_posix()
    prompt=(HERE/'给执行AI的长任务启动提示词.md').as_posix()
    (folder/'记录.md').write_text('> 类别：会话证据\n\n# T+1计划v1.2实测补强及报错继续\n\n用户要求评估其他AI三硬四软建议，并明确失败后跳过继续补抽、告警。计划就地升级v1.2，仍10批，保留原告警/幂等/单写/COMMIT_UNKNOWN及隔离试点上线观测门禁。补纳管历史业务月轮巡（不仅当月，先完整stage后受控发布）、77表路线画像/LIS Q4重叠、在跑写者快照和故障局部继续。出院错误原稿不直接复用，护理DataX-only只限旧路线，gap比较不照搬float/全rstrip。长期凭据、deadline未配及建议动作/detail_ref已明确。\n\n112未执行验收预期、28计划检查及22独立核对通过，xlsx10页及zip更新，旧v1.1完整归档。工程尚未实现，未SSH/查询业务库/改视图/启停任务/cron/真实发消息。当前运行快照未采，不能据用户时点报告认定旧写者已停。\n\n[评估与修订]('+report+')、[新版启动提示词]('+prompt+')；状态沿原run/checkpoint.daily_t1.engineering_execution_20261019，失败保留待补，不计成功。\n',encoding='utf-8')
    readme=sessions/'README.md';text=readme.read_text(encoding='utf-8')
    row='| 025 | 2026-10-19 | T+1计划v1.2：历史月漂移轮巡/路线画像/写者快照及失败继续预警 | [本条记录](025_20261019_T加1计划实测补强与失败继续/记录.md) | 10批/112未跑预期，28计划+22独立核对；仅修订计划，未改在跑链，失败入待补不计成功 |\n\n'
    if row not in text:
        assert '下一号从 **025** 起。' in text
        readme.write_text(text.replace('下一号从 **025** 起。',row+'下一号从 **026** 起。'),encoding='utf-8')
    print(json.dumps({'registered':True,'version':'1.2','tasks':10,'expected_cases':112,'planning_checks':28,'independent_checks':22,'engine_implemented':False},ensure_ascii=False))


if __name__=='__main__':main()
