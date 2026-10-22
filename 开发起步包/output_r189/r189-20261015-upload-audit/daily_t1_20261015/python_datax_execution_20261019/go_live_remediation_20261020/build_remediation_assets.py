"""Build offline R189 T+1 remediation definitions and review workbook; no network."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


HERE = Path(__file__).resolve().parent
PKG = HERE.parent
ROOT = next(p for p in HERE.parents if (p / "AGENTS.md").is_file())


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(name: str, value):
    (HERE / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


TASK_ROWS = [
    ("R01", "E08补强/E01增量", [], "证据与77配置冻结", "当前seed/路由/画像/定义/工单及112原场景映射；纠正血透database_hint等错位", "77唯一项、冻结指纹、旧结论逐项关联、真实待办清单", "本地可做；实际源画像另需受控范围与窗口"),
    ("R02", "E08补强", ["R01"], "耐久状态及暂存", "Repository接口+PG实现，manifest/隔离/版本/outbox耐久化，租约原子领取与续期", "重启可恢复、两工作者并发与旧token拒绝、增量迁移隔离往返", "实现/纯逻辑可做；PG集成需已核可清理隔离库"),
    ("R03", "E08补强", ["R01", "R02"], "真实采集适配", "受控RowSource、真实DataX进程/插件、流式stage及密钥引用，驱动取消", "拆窗守恒、LOB完整、dirty不发布、半截捕获拒绝、源风暴有界", "离线可准备并开发；真实源及stage操作按各自门禁"),
    ("R04", "E08补强", ["R01", "R02"], "受控装载与恢复", "平台批准/白名单、目标侧围栏、同事务提交凭据、精确类型版本比较", "伪批准/无token被拒；COMMIT_UNKNOWN核证恢复；旧覆盖和不完整月替换被拒", "接口/模拟可做；目标辅助DDL及实际DML逐例批准"),
    ("R05", "E08补强", ["R02", "R03", "R04"], "运行用例与调度", "真实管道/CLI、DAG就绪队列、失败继续且如实总体状态、连续性和历史漂移轮巡", "实际入口串通、token贯穿、跳过不误报成功、2026接续无隐性缺窗", "用例可先模拟开发；生产排程发布另核批准"),
    ("R06", "E08补强", ["R01", "R02"], "告警与真实日报", "HTTP transport、耐久投递轮询、认证挂起/限流、结构化错误、真实日报", "202不算送达、实际数据不走内存、告警故障不阻断抽取、缺deadline显性", "本地模拟可独立做；真实订阅与测试接收范围由管理员提供"),
    ("R07", "E09", ["R01", "R02", "R03", "R04", "R05", "R06"], "真实小组试点", "3—5已就绪项、两相邻日窗、幂等恢复、按键/内容回读、告警逐目标sent", "配置/批准/真实执行/回读/投递证据闭合；特殊路线另组补齐", "实际读/stage/apply/告警分动作取得批准；不扩大范围"),
    ("R08", "E10", ["R07"], "交接扩围与7日观测", "逐表旧写者交接、约5—10项分组、7业务日值守、回退演练和签收", "逐表就绪及欠账透明；院内与省端分签；历史月周期保留独立观测", "生产发布/排程/停旧入口等具备具体批准；省端未知如实单列"),
]

CASE_ROWS = [
    ("R01", "OFFLINE", "77项与输入变更", "修改一个源身份或依赖哈希，其他通过项不变", "只使受影响项/依赖失效；不重核无关项、不批量READY"),
    ("R01", "OFFLINE", "血透DSN及故障旧配置", "87地址搭配dialysis hint，旧17432网络待办仍存在", "拒绝未冻结连接身份；确认hdis后更新相关冻结件，作废旧待办而非执行"),
    ("R02", "ISOLATED_PG", "捕获后重启", "A持久化完整stage后退出，B恢复", "复用同一完整manifest，attempt/游标/缺口不丢，半截stage不被视为完整"),
    ("R02", "ISOLATED_PG", "多工作者租约", "两个进程同时领取同一目标/表", "仅一个成功，重领取后旧token不可续期/提交，无双写"),
    ("R02", "ISOLATED_PG", "耐久原子性", "在批次/缺口/游标/outbox事务各边界注入失败并重启", "无水位越OPEN缺口、无丢事件、无重复已完成批次；恢复动作一致"),
    ("R03", "OFFLINE_AND_ISOLATED", "超窗细分", "6小时5万+行、同秒多键、最小粒度仍超限", "递归拆分守恒，keyset完整；无可靠键则PARKED，不能截断成功"),
    ("R03", "ISOLATED_DRIVER", "阻塞fetch取消", "真实驱动fetch阻塞并触发时限/取消", "在已配置预算内取消实际调用/子进程并释放资源，manifest不完整"),
    ("R03", "ISOLATED_DRIVER", "CLOB及字节", "超页LOB、中文、多字节、末尾空白，关闭连接后读取", "连接关闭前完整转存；字节/类型按契约核对，CLOB尾空白不误裁"),
    ("R03", "ISOLATED_DATAX", "退出0假成功", "真实进程exit0但dirty>0/缺指标/读写不同", "全部拒绝COMPLETE及apply，保存安全指标和失败窗"),
    ("R03", "OFFLINE_AND_ISOLATED", "源级风暴", "同源多表同时ORA-12541/12547/DPY-4011", "同源有界退避、聚合incident和单半开探针，其他源继续"),
    ("R03", "OFFLINE", "通道与投影", "DataX-only失败、source有DATETIME而target无该列", "不擅自fallback；源列可用于窗，正式投影不含不存在列"),
    ("R04", "OFFLINE_AND_ISOLATED", "批准不可伪造", "调用方填自定义approved_ref/执行器ID或扩大范围", "可信平台校验拒绝；不出现实际DML，离线preview可继续"),
    ("R04", "ISOLATED_TARGET", "围栏竞态", "执行器门禁后旧租约失效、新工作者接管", "旧工作者在目标提交处被拒，不能只在PG预查一次token"),
    ("R04", "OFFLINE_AND_ISOLATED", "版本精度与隔离", "9007199254740992与9007199254740993；跨表同ID；无版本同键异值", "精确比较；表/租户/目标互不污染；未知顺序CONFLICT，不按采集时间覆盖"),
    ("R04", "ISOLATED_TARGET", "提交后断线", "目标commit后响应丢失、进程重启", "COMMIT_UNKNOWN冻结同表；查同事务operation/manifest再恢复APPLIED，不重复写"),
    ("R04", "ISOLATED_TARGET", "未提交或未能判定", "明确回滚、事务状态仍未知分别恢复", "仅明确回滚可安全重试；仍未知保持冻结，不能因查不到凭据盲重放"),
    ("R04", "ISOLATED_TARGET", "不完整月替换", "一个子窗失败/隔离或一个历史来源缺段", "禁止整月删除发布；其他独立完整组/表可按已批准范围继续"),
    ("R04", "ISOLATED_TARGET", "跨月移动与撤销", "源键业务时间改月/撤销，目标缺时间列", "凭耐久键归属和已批准范围处理；不能查询不存在列或默默残留双份"),
    ("R05", "OFFLINE", "父子优先级", "历史父任务+T1子任务，另有独立T1任务", "父先子后；独立T1可优先；父失败子待父而非写孤儿"),
    ("R05", "OFFLINE", "同表多任务", "同表T1/历史/重扫与多个窗同时排队", "按批次和窗保留所有任务，不被canonical_table字典覆盖，正式写串行"),
    ("R05", "OFFLINE_AND_ISOLATED", "按动作就绪", "READ/STAGE已核、APPLY已有具体批准、REPORT未知；历史路由一段未知", "只准已就绪活动路线的相应动作；全链启用/省端报送仍拒绝，未知不改READY"),
    ("R05", "OFFLINE_AND_ISOLATED", "跳过不是成功", "所有任务熔断/租约忙；另测run返回失败但不抛异常", "应完成窗未闭合时PARTIAL/WAITING_WITH_BACKLOG；NO_WORK只用于确实无应运行任务"),
    ("R05", "OFFLINE_AND_ISOLATED", "局部失败继续", "一行超长、一父组不齐、一个窗失败", "隔离相关组并告警/留缺口；独立项继续；连续游标不越缺口"),
    ("R05", "OFFLINE", "午夜固定窗", "23:59启动，00:01重试，源在不同时区", "使用冻结的业务时区和H，半开窗不漂移，不用SYSTEM_TIME当变更依据"),
    ("R05", "OFFLINE_AND_ISOLATED", "2026接续缺窗", "旧基线只到2025末，当日已经捕获且中间有缺口", "分开已捕获与连续完成，保留H0后捕获并受控补缺，日报不冒充连续完成"),
    ("R05", "OFFLINE_AND_ISOLATED", "历史漂移", "对日窗外旧月新增/更正，轮巡管理60个月", "按覆盖年龄发现并留账；只扫当前月或每月单月轮转不得声称30天覆盖全历史"),
    ("R05", "OFFLINE_AND_ISOLATED", "LIS重叠历史路由", "2023Q4双源同键异值、2024+新源以及一源暂缺", "同一路由器覆盖日常/回看/重扫；冲突按核定策略，不单源删完整双源月"),
    ("R06", "LOCAL_HTTP_FAKE", "202与多目标", "POST202，GET部分sent/空目标/延迟sent", "ACK_QUEUED与送达分开；按必需目标状态完成，零目标ROUTE_UNRESOLVED"),
    ("R06", "LOCAL_HTTP_FAKE", "认证与限流", "401、429 Retry-After、跨秒重签和幂等冲突", "401停盲重试；429至少60秒并尊重更长Retry-After；原body不变，新revision新事件"),
    ("R06", "ISOLATED_PG_AND_LOCAL_HTTP", "投递重启", "ACK前/ACK后/sent前分别退出再恢复，多个sender并发", "耐久claim及事件幂等，逐目标继续查询，原字节与revision证据不丢"),
    ("R06", "OFFLINE_AND_ISOLATED", "日报与隐私", "真实仓储含失败/隔离/deadline空；异常串含模拟患者字段/SQL/secret", "正式日报来自耐久状态；SLA_UNKNOWN单列；外发只安全码/汇总/detail_ref"),
    ("R07", "APPROVED_PILOT", "真实读取装载告警", "已批准3—5项、两相邻日窗及同窗重复；覆盖特殊路线", "真实数/键/内容守恒、隔离如实、无重复/旧覆盖；告警逐目标sent有回执"),
    ("R08", "APPROVED_ROLLOUT", "旧写者及回退", "新鲜快照有同表在途/未知提交；再模拟安全交还", "不启第二写者；核事务后交接；回退无并发、已提交数据不靠代码回滚抹掉"),
    ("R08", "BUSINESS_DAY_OBSERVATION", "7日观测及省端分签", "7业务日存在隔离/告警失败，省端无回执，月周期未跑完", "逐项列欠账并延长受影响验收；院内与省端结论分开；月周期另待观测"),
]

FINDING_ROWS = [
    ("F01", "backend/app/services/reporting_pipeline/repositories.py", 129, "仅InMemoryControlRepository，无生产PG Repository", "R02"),
    ("F02", "backend/app/services/reporting_pipeline/staging.py", 51, "StageStore内存存储，缺耐久分块清单及恢复", "R02"),
    ("F03", "backend/app/services/reporting_pipeline/adapters/python_reader.py", 75, "RowSource为Protocol，真实受控连接器未绑定", "R03"),
    ("F04", "backend/app/services/reporting_pipeline/adapters/datax_runner.py", 149, "ProcessRunner为Protocol，真实运行/密钥/stage绑定待补", "R03"),
    ("F05", "backend/app/services/reporting_pipeline/apply_port.py", 228, "现有执行器为InMemoryApplyExecutor，缺平台实际执行器及目标事务凭据", "R04"),
    ("F06", "backend/app/services/reporting_pipeline/apply_port.py", 121, "批准/白名单由内存集合传入，lease_validator和token可缺省，不能直接作生产权限边界", "R04"),
    ("F07", "backend/app/services/reporting_pipeline/apply_port.py", 113, "版本先转float，存在大整数精度问题；未声明类型回退字典序", "R04"),
    ("F08", "backend/app/services/reporting_pipeline/scheduler_bridge.py", 72, "拓扑排序后全局按模式sort可能使T1子先于历史父；by_table会覆盖同表多任务", "R05"),
    ("F09", "backend/app/services/reporting_pipeline/scheduler_bridge.py", 112, "领取lease后未把token送入task.run，目标资源硬编码DBOPER", "R04/R05"),
    ("F10", "backend/app/services/reporting_pipeline/scheduler_bridge.py", 129, "总体状态只看exceptions；全部skipped或run返回失败仍可SUCCESS", "R05"),
    ("F11", "backend/scripts/reporting_ctl.py", 208, "9个主要命令NOT_IMPLEMENTED；daily-report每次创建内存仓储", "R05/R06"),
    ("F12", "backend/app/services/reporting_pipeline/alerts_client.py", 61, "HTTP Transport仍协议；outbox依赖内存仓储，无实际运行绑定", "R06"),
    ("F13", "backend/tests/reporting_pipeline_integration/test_control_state_isolated.py", 39, "3集成测试验证表/不可变字节唯一约束/月覆盖唯一；非Repository恢复并发测试", "R02/R07"),
    ("F14", "backend/app/services/reporting_pipeline/scheduler_bridge.py", 123, "异常直接异常文本进入failure摘要，生产需安全码/脱敏detail_ref", "R05/R06"),
    ("F15", "backend/app/services/reporting_pipeline/contracts.py", 406, "validate_enable要求五层全READY；需保留全链门禁并补动作/活动路由级验证，防省端未知阻塞独立院内动作", "R05"),
]


def add_sheet(wb, title, headers, rows, widths):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for row in rows:
        ws.append(row)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor="244062")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row[0].row].height = 62 if title != "77项候选快照" else 90
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    return ws


def main():
    seed = read_json(PKG / "77项任务候选种子.json")
    validation = read_json(HERE / "当前种子离线校验.json")
    actual = json.loads(validation["stdout"])
    tasks = [
        dict(id=i, original_batch=b, integration_dependencies=d, title=t,
             implementation=w, exit_criteria=x, external_dependency=g,
             offline_preparation_can_start_before_integration_dependencies=True)
        for i, b, d, t, w, x, g in TASK_ROWS
    ]
    cases = [
        dict(id=f"RT1-{i:03d}", work_package=r, environment=e, title=t,
             trigger=g, expected=x, execution_state="NOT_RUN", actual_evidence=None)
        for i, (r, e, t, g, x) in enumerate(CASE_ROWS, 1)
    ]
    definitions = {
        "kind": "SUPPLEMENTAL_PLAN_DEFINITIONS_NOT_RUNTIME_CHECKPOINT",
        "date": "2026-10-20", "parent_package": seed["package_id"],
        "state_authority": "../../../checkpoint.json#daily_t1.engineering_execution_20261019",
        "task_definitions": tasks, "supplemental_acceptance_cases": cases,
        "original_112_cases": {"file": "../验收场景矩阵.json", "preserve_historical_states": True,
                               "next_action": "逐条映射实际测试/环境/结果/证据；本补充不替代原112条"},
        "scope": "77规范项，R01—R06=E08运行补强，R07=E09，R08=E10",
        "no_production_authorization_granted": True,
    }
    write_json("整改任务与验收清单.json", definitions)
    findings = []
    for i, path, line, conclusion, r in FINDING_ROWS:
        data = (ROOT / path).read_bytes()
        findings.append(dict(id=i, file=path, line=line, sha256=hashlib.sha256(data).hexdigest(),
                             conclusion=conclusion, work_package=r, remediation_state="NOT_IMPLEMENTED_THIS_REVIEW"))
    evidence = {
        "review_date": "2026-10-20", "review_method": "本地源码/既有交付证据审阅，独立只读审阅结果经主执行者复核",
        "findings": findings,
        "actual_verification": [
            {"command": ".venv/Scripts/python.exe -m pytest tests/reporting_pipeline_unit -q",
             "cwd": "backend", "exit_code": 0, "actual": "173 passed, 1 warning in 1.21s",
             "warning": "Starlette TestClient/httpx既有弃用提示；不影响本轮通过",
             "environment": "PURE_LOGIC_NO_DB", "not_a_pass_for": "新补充场景/Oracle/DataX/relay/生产运行"},
            {"command": "backend/.venv/Scripts/python.exe backend/scripts/reporting_ctl.py validate --offline",
             "exit_code": validation["exit_code"], "actual": actual,
             "note": "结构通过不等于接入通过；SOURCE_READY_EXTRACT_PENDING注释不等于生产READ_READY"},
            {"command": "python tools/check_test_environment.py", "actual": "pure_logic_ready；APP_TEST_DB_URL未配置"},
            {"command": "python tools/check_doc_index.py", "actual": "error0/warn1；216缺类别为既有无关提示"},
        ],
        "historical_only": "10-19的3项PG集成及迁移往返保留；本轮未运行数据库集成测试",
        "original_acceptance_cases": {"count": 112, "not_run": 112},
        "supplemental_case_count": len(cases), "supplemental_cases_executed": 0,
        "business_source_queries": 0, "business_writes": 0, "production_deploys": 0,
        "scheduler_changes": 0, "real_alert_messages": 0, "original_checkpoint_modified": False,
        "configuration_observation": {
            "seed_sha256": hashlib.sha256((PKG / "77项任务候选种子.json").read_bytes()).hexdigest(),
            "dialysis": "当前候选源87且database_hint=dialysis，交接实际DB=hdis，待冻结一致；仍不自动写READY",
            "input_freshness": "仅代表此时点；执行前比较基线指纹并读取后续证据",
        },
    }
    write_json("源码复核与本轮验证.json", evidence)
    wb = Workbook()
    wb.remove(wb.active)
    add_sheet(wb, "阅读说明", ["项目", "说明"], [
        ["性质", "2026-10-20接续计划和输入快照，不是第二份运行进度；状态沿原checkpoint"],
        ["本轮实测", "173纯逻辑通过；77配置结构通过；READ/STAGE/APPLY/REPORT四层各77项UNKNOWN"],
        ["原验证", "10-19隔离PG三例是历史证据，本轮未重跑；112原场景仍需映射"],
        ["新增验收", f"{len(cases)}个补充回归期望均NOT_RUN，不用173测试数字冒充已通过"],
        ["推进方法", "R01—R06补运行工程，R07试点，R08逐表交接和7业务日观测；局部受阻继续独立项"],
        ["报错策略", "失败窗留缺口/告警/待补，继续独立表；COMMIT_UNKNOWN冻结同表，不盲重放"],
        ["配置提醒", "血透87为当前源；database_hint须核成实际hdis；17432仅备用。旧工单/zip不覆盖新证据"],
        ["原状态权威", "原run/checkpoint.json → daily_t1.engineering_execution_20261019；本轮未修改"],
    ], [24, 110])
    add_sheet(wb, "八包整改", ["包号", "原批次", "依赖(集成)", "工作", "开发内容", "验收出口", "外部依赖"],
              [[i, b, ",".join(d), t, w, x, g] for i, b, d, t, w, x, g in TASK_ROWS],
              [10, 22, 20, 25, 60, 65, 65])
    add_sheet(wb, "新增验收期望", ["编号", "包号", "环境", "场景", "触发", "通过条件", "执行状态"],
              [[c["id"], c["work_package"], c["environment"], c["title"], c["trigger"], c["expected"], c["execution_state"]] for c in cases],
              [15, 10, 30, 30, 65, 85, 15])
    source_rows = []
    for x in seed["items"]:
        sources = "; ".join(
            f"{s.get('role')} {s.get('host')}:{s.get('port')}/{s.get('database_hint')} "
            f"{s.get('owner_hint')} {','.join(s.get('object_name_candidates', []))}"
            for s in x["source_candidates"]
        )
        source_rows.append([
            x["index"], x["canonical_table"], x["business_name"], x["enabled"],
            x["engine"], x["runtime_readiness"], sources, x.get("historical_business_time_hint"),
            "已提供" if x.get("business_time") else "待落实", "已核" if x["stable_key"]["verified"] else "待核",
            "已提供" if x.get("projection") else "待落实", x.get("deadline_state"),
            x.get("running_writer_handoff_state"), x.get("source_ready_note", ""),
        ])
    add_sheet(wb, "77项候选快照", ["序号", "规范表", "名称", "enabled", "引擎", "seed注记状态(非分层验收)", "候选来源(须核实例)", "历史业务时间线索", "business_time", "稳定键", "投影", "deadline", "写者交接", "来源补充说明(不等于READY)"], source_rows,
              [8, 42, 30, 10, 18, 35, 85, 28, 18, 12, 15, 20, 28, 90])
    add_sheet(wb, "源码问题", ["编号", "文件", "行", "问题", "整改包"],
              [[i, p, n, c, r] for i, p, n, c, r in FINDING_ROWS], [10, 65, 10, 100, 18])
    wb.save(HERE / "整改批次与验收清单.xlsx")
    print(json.dumps({"tasks": len(tasks), "supplemental_cases_not_run": len(cases),
                      "source_snapshot_rows": len(source_rows), "findings": len(findings),
                      "sheets": len(wb.sheetnames)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
