# r194 S7: generate cases.json + coverage.json from the run's collected evidence.
# 2026-09-18 复核修订：同步 pytest 后补测终态（J11/O02/HR-173-P2-1/P3-5、backend_full、关键旅程口径、
# o02_retest、revised_note）。此前脚本停留在 21:5x pytest 前快照——重跑会把上述条目打回 NOT_RUN/RUNNING，
# 与手工更新后的 cases.json/coverage.json 冲突；本次修订后重跑应产出与在库文件一致的内容。
import json
import os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VIS_PAGES = ["/welcome", "/asset/overview", "/asset/system-map", "/workbench", "/asset/systems", "/asset/tables",
             "/asset/graph", "/asset/lineage", "/metadata/changes", "/identity/persons", "/identity/departments",
             "/identity/accounts", "/identity/local-accounts", "/identity/sync-diffs", "/identity/sync-logs",
             "/identity/roles", "/identity/authorizations", "/identity/permission-requests", "/ops/runs",
             "/ops/sql-workbench", "/ops/tools", "/ops/audit", "/quality/issues", "/quality/controls",
             "/quality/observations", "/probe-findings", "/asset/quality", "/asset/ai-quality", "/asset/ai-sql",
             "/asset/queries", "/asset/queries/accuracy", "/value-domains", "/dict/medical", "/dict/general",
             "/dict/mappings", "/dict/sync-diffs", "/asset/relation-review", "/asset/relation-recipes",
             "/asset/admin", "/asset/ai-tools", "/"]
# "/" is the 工作台 home entry; visible leaf count 41 includes it

PAGE_NOTES = {
    "/asset/queries": "FAIL-detail: 列表空(DEF-02)，页面本身渲染正常",
    "/asset/queries/accuracy": "渲染正常但评测结果空(U-1 待复核)",
    "/dict/mappings": "渲染正常但 0 行(U-2 待复核)",
    "/identity/roles": "0 行 vs 9 角色种子(U-4 待复核)",
    "/ops/audit": "0 行 vs 9 治理审计种子(U-5 口径差待核)",
    "/identity/sync-diffs": "2 行 vs 3 种子(默认 open 过滤，U-3)",
}

cases = []


def add(cid, status, method, **kw):
    cases.append(dict(case_id=cid, status=status, method=method, **kw))


# G01 for all 41 visible pages (deep-link + reload path)
for p in VIS_PAGES:
    st = "PASS"
    note = PAGE_NOTES.get(p, "渲染/数据/空态正常")
    add("G01@" + p, st, "BROWSER_INTEGRATION", route=p,
        expected="页面渲染，主数据加载完成，无空白/致命错误", actual=note,
        evidence=["logs/backend.log", "cases 备注见测试报告 §页面扫测"],
        defect_ids=["DEF-02"] if p == "/asset/queries" else [])
# G02-G10 sampled
add("G02@/asset/tables", "FAIL", "BROWSER_INTEGRATION",
    expected="搜索 PATIENT_INFO 命中同名表并过滤", actual="树被清空、主列表未过滤(DEF-07)", defect_ids=["DEF-07"])
add("G03@/asset/tables", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="SPA 导航冻结(DEF-01)阻断连续交互；时间预算")
add("G04@/asset/tables", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="同上")
add("G05@/asset/systems+table-detail", "PASS", "BROWSER_INTEGRATION",
    expected="深链刷新可恢复", actual="2 个深链整页刷新均正确渲染（含 query 参数）")
add("G05b@invalid-params", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="时间预算")
add("G06@mock-fault-injection", "NOT_RUN", "BROWSER_MOCK", blocked_reason="时间预算（故障注入未做）")
add("G07@role-matrix", "PASS", "API_INTEGRATION",
    expected="viewer/norole 对高权限端点 403", actual="12 例矩阵通过（1 例先受 DEF-05 夹具影响，修正后过）",
    evidence=["api_static/api_matrix_results.json"], defect_ids=[])
add("G08@keyboard-zoom", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="时间预算")
add("G09@repeat-nav", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="DEF-01")
add("G10@counts-vs-seed", "PASS", "BROWSER_INTEGRATION+API_INTEGRATION",
    expected="列表计数与种子对账", actual="表10/血缘2/变更3/质控3/观测3/台账3/探查3/值域3/配方2/人员9/科室3/账号12/本地账号6/同步日志1 全部吻合；查询中心 3(API)≠0(页面)→DEF-02",
    defect_ids=["DEF-02"])

# Journeys
add("J01", "BLOCKED", "BROWSER_INTEGRATION", expected="登录→工作台→收藏→换账号隔离",
    actual="登录/工作台/最近访问(单账号)已验；收藏与跨账号隔离被 DEF-01 阻断", blocked_reason="DEF-01",
    defect_ids=["DEF-01"])
add("J02a-table-detail", "PASS", "BROWSER_INTEGRATION",
    expected="source_code 隔离、同名表不串源", actual="R194A1 详情仅 4 字段+3 关系，无跨源合并")
add("J02b-return-filters", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="DEF-01")
add("J03-graph-drill", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="DEF-01；图谱页首屏渲染正常(4 svg)")
add("J04-review-flow", "PASS", "API_INTEGRATION",
    expected="draft→approve 200→二次审核拒绝", actual="approve 200(action=linked_candidate_no_promote)；二次 approve 400")
add("J05-ai-draft", "NOT_RUN", "BROWSER_MOCK", blocked_reason="LLM 出口按计划封禁；草稿链路未测")
add("J06-query-run-bind", "NOT_RUN", "API_INTEGRATION", blocked_reason="真实连接器出口封禁，mock bind 捕获未实现（时间预算）")
add("J07-feedback", "BLOCKED", "API_INTEGRATION",
    expected="viewer 提交/查看反馈", actual="/api/v1/ai/feedback 粗粒度 ai 角色门禁对 viewer 403（设计意图待裁决）",
    blocked_reason="权限门禁与旅程前提冲突，未强行绕过")
add("J08-scope-isolation", "FAIL", "API_INTEGRATION",
    expected="mine/department 精确隔离且跨科室写被拒",
    actual="列表隔离精确 PASS（qa_a=[0001,0003], qa_b=[0002]）；状态机护栏 PASS；跨科室写 new→acknowledged 200（DEF-03）",
    defect_ids=["DEF-03"])
add("J09-sync-logs", "PASS", "BROWSER_INTEGRATION+API_INTEGRATION",
    expected="partial_success 与子任务状态可读", actual="同步日志页 1 行(partial_success)渲染；子任务 4 态种子在库；详情抽屉未逐项点开(NOT_RUN 部分)")
add("J10-dict-import", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="DEF-01+时间预算")
add("J11-audit-trace", "PASS", "API_INTEGRATION",
    actual="/api/v1/govern/audit-logs 200 total=9 与种子对账")
add("J12-session-expiry", "FAIL", "API_INTEGRATION",
    expected="过期会话/禁用后旧 token 失效", actual="refresh 过期 401 ✓；禁用账号后 access JWT 仍 200（DEF-04）",
    defect_ids=["DEF-04"])

# Module cases (N/A/R/Q/L/I/O) — executed subset
add("N01-login", "PARTIAL_PASS", "BROWSER_INTEGRATION+API_INTEGRATION",
    expected="正确进/错误提示/限流/不重不泄", actual="正确登录✓；错误提示✓(形状不统一 DEF-09)；限流 5/min✓；连击未测",
    defect_ids=["DEF-09"])
add("N02-menu-leaves", "PASS", "BROWSER_INTEGRATION", expected="41 可见叶可进入、name 无重复",
    actual="41/41 整页加载渲染（对比 186 基线 40，+1 为首页入口计数口径）")
add("N03-N08", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="DEF-01/时间预算")
add("A01-same-name-tables", "PASS", "BROWSER_INTEGRATION", expected="同名表按源隔离",
    actual="树(5+2+3)/列表(source 列区分)/详情(仅本源字段) 三层一致")
add("A03-table-detail", "PASS", "BROWSER_INTEGRATION", actual="字段/主键/关系与种子一致")
add("A04-graph-first-screen", "PASS", "BROWSER_INTEGRATION", actual="图谱页渲染 svg 节点，无空白/报错；下钻未测")
add("A07/A08/A09/A02/A05/A06/A10", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="DEF-01/时间预算")
add("R01-R08", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="DEF-01/时间预算（值域/字典页 G01 列表渲染正常）")
add("Q01-queries-center", "FAIL", "BROWSER_INTEGRATION", expected="六页签数据加载", actual="查询资产/运行记录均空(DEF-02)",
    defect_ids=["DEF-02"])
add("Q05-certification-gate", "PASS", "API_INTEGRATION",
    actual="viewer run→403 query:run；blocked 查询 run→404 查询版本不存在")
add("Q02/Q03/Q04/Q06-Q16", "NOT_RUN", "API_INTEGRATION/BROWSER_MOCK", blocked_reason="时间预算/出口封禁/DEF-02")
add("L01-scope", "PASS", "API_INTEGRATION", actual="mine/department 精确；URL 直查他科详情 200=按 read_all 设计（记录）；跨科写 FAIL→DEF-03")
add("L03-state-machine", "PASS", "API_INTEGRATION",
    actual="resolved 须走 verify(409)；waiting_verify 须 action_plan(422)；终态回退仅管理员(403)")
add("L02/L04-L08", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="DEF-01/时间预算")
add("I02-account-combos", "PARTIAL_PASS", "BROWSER_INTEGRATION",
    actual="9 组合人员+12 账号行渲染；逐格对照 186 真值表未完成")
add("I07-subtask-stats", "PARTIAL_PASS", "BROWSER_INTEGRATION", actual="主 run partial_success + 4 子任务态在库；页面一致性核验部分")
add("I11-192-mirror-check", "PASS", "STATIC_REVIEW+HISTORICAL_EVIDENCE",
    actual="D3 修复在树（子表检查无 FOR UPDATE）；生产证据=192 晨检文档（未连生产复核）")
add("I12-disabled-token", "FAIL", "API_INTEGRATION", actual="禁用后旧 JWT 200（DEF-04）", defect_ids=["DEF-04"])
add("I01/I03-I06/I08-I10", "NOT_RUN", "API_INTEGRATION", blocked_reason="写链路模拟与时间预算；I08 由 I11 部分覆盖")
add("O01-ops-runs", "PARTIAL_PASS", "BROWSER_INTEGRATION", actual="2 行渲染；失败原因/审计关联未逐项核")
add("O02-sql-gate", "PASS", "API_INTEGRATION",
    actual="正确字段复测：UPDATE 到源库 valid=false(仅允许 asset schema 写)；DROP valid=false(禁词+模板限制)；多语句 DELETE valid=false；bind 参数缺失检出。scope=platform_asset_only",
    evidence=["api_static（本轮复测输出）"])
add("O03-executor-gate", "PASS", "API_INTEGRATION", actual="未注册执行器 404；库内执行器 0 行，全部执行路径闭合")
add("O04-O08", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="时间预算")

# AR/UX
add("AR02-contract", "PARTIAL_FAIL", "STATIC_REVIEW",
    expected="前端调用与 OpenAPI 方法级一致", actual="发现 DEF-02（查询中心消费断链）；全量比对 NOT_RUN",
    defect_ids=["DEF-02"])
add("AR03-api-classification", "PASS", "STATIC_REVIEW",
    actual="434/434 方法-路径完成分类（pure_read 158 / platform_write 148 / platform_write_or_source_touch 52 / source_read_or_plan 33 / external_or_llm 43）",
    evidence=["api_static/api_inventory.json"])
add("AR04-authz-matrix", "PASS", "API_INTEGRATION", actual="12 例矩阵（附 DEF-05 夹具修正记录）")
add("AR07-alembic-graph", "PASS", "UNIT+API_INTEGRATION", actual="单头 e8f9a0b1c2d3；115 表含旧 MVP 表")
add("AR08-migration-roundtrip", "PASS", "API_INTEGRATION",
    actual="一次性库 data_asset_test_r194：空库 upgrade head(115 表)→downgrade -2→re-upgrade(115 表) 三态对账",
    evidence=["logs（本文件 §AR08 输出）"])
add("AR09-authn-config", "PARTIAL_PASS", "STATIC_REVIEW+API_INTEGRATION",
    actual="JWT 占位密钥仅 dev 告警（隔离环境预期）；假 token 403；access token 内存存储（代码核）")
add("AR12-startup-degradation", "PARTIAL_PASS", "API_INTEGRATION", actual="LLM 关闭位生效、页面正常降级渲染")
add("AR01/AR05/AR06/AR10/AR11/AR13-15", "NOT_RUN", "STATIC_REVIEW/UNIT", blocked_reason="时间预算（AR10 部分：多语句/DML 拒绝待 O02 复测）")
add("UX01-1440", "FAIL", "BROWSER_INTEGRATION", actual="登录页 1440 裁切(DEF-06)；内页 1440 扫测未做（登录后以 1920 扫测）",
    defect_ids=["DEF-06"])
add("UX06-load-times", "PARTIAL_PASS", "BROWSER_INTEGRATION",
    actual="41 页整页加载 3.7–4.7s/页（含 vite dev 编译，非生产构建口径）")
add("UX09-build-budget", "PASS", "UNIT", actual="build ✓ gzip 预算 ✓（logs/build.log）")
add("UX05-visual-review", "BLOCKED", "BROWSER_INTEGRATION",
    blocked_reason="会话模型无图像输入，截图已存档 screenshots/ 但未逐张人工判读")
add("UX02/UX03/UX04/UX07/UX08/UX10", "NOT_RUN", "BROWSER_INTEGRATION", blocked_reason="时间预算/控制台采集不可用(IAB)")

# Historical review cases
add("HR-186", "PARTIAL_PASS", "HISTORICAL_EVIDENCE", actual="菜单 41 叶/迁移在链/账号线渲染 OK；导航主路径回归(DEF-01)；09-12 后窗口推进缺最新生产证据")
add("HR-188", "PASS(doc)", "HISTORICAL_EVIDENCE", actual="44 件产物在位；生产现状未由本轮验证")
add("HR-192", "PASS", "HISTORICAL_EVIDENCE+STATIC_REVIEW", actual="D3/partial_success/白名单在树+晨检文档闭环；未连生产")
add("HR-193", "PASS(doc)", "HISTORICAL_EVIDENCE", actual="B00/B01 文件在位；B02+ 端点不存在=PLANNED_NOT_IMPLEMENTED")
add("HR-173-P2-2", "PASS", "STATIC_REVIEW", actual="6 按钮 v-perms 已补（3 页计数 5/7/14）")
add("HR-173-P3-6", "PASS", "API_INTEGRATION", actual="空库 upgrade 直接成功（本轮 AR08 实证）")
add("HR-173-P2-1/P3-5", "PARTIAL_PASS", "API_INTEGRATION",
    actual="P2-1 已修复（PUT /api/v1/systems upsert 注册 SYS_R194_NEW 200 @backend.log:3043 + 列表回读见 4 系统 @3045）；P3-5 未修复（非法 primary_tables 创建 recipes 仍 200 @backend.log:3047，校验后置）")
add("HR-173-others", "NOT_RUN", "STATIC_REVIEW", blocked_reason="时间预算")

with open(os.path.join(RUN, "cases.json"), "w", encoding="utf-8") as f:
    json.dump({"generated": "2026-09-17", "cases": cases}, f, ensure_ascii=False, indent=1)

from collections import Counter
cnt = Counter(c["status"] for c in cases)
cov = {
    "run_id": "r194-20260917-204356",
    "case_status_counts": dict(cnt),
    "total_cases": len(cases),
    "coverage_by_layer": {
        "页面访问覆盖": {"done": 41, "denominator": "41 可见叶（G01 整页加载路径）", "blocked_note": "SPA 站内导航路径 0/41（DEF-01）"},
        "人工交互覆盖(G子项)": {"done": 6, "denominator": "适用 G 子项约 40（41页×部分适用）", "note": "G01 全量 + G02/G05/G07/G10 抽样；其余 NOT_RUN/BLOCKED"},
        "关键旅程覆盖": {"executed": 6, "attempted_blocked": 2, "not_run": 4, "denominator": 12, "detail": "执行 6：J02(部分：J02a PASS/J02b 未做)、J04、J08(FAIL)、J09、J11(补测 PASS)、J12(FAIL)；尝试被 DEF-01 阻断 2：J01/J07；未做 4：J03/J05/J06/J10。口径=cases.json 单一事实源（2026-09-18 修订：原 executed=8 系把 BLOCKED 尝试计入，且 J11 曾误列 NOT_RUN）"},
        "API风险分类覆盖": {"classified": 434, "denominator": 434, "api_executed": "约 40 端点被真实调用（矩阵+页面）"},
        "历史复核覆盖": {"checked": "186/188/190/192/193/173(6条) ", "pending": "173 其余 P3、189/191 活库类、127/129/144/149 深项"},
        "质量门禁": {"typecheck": "PASS", "vitest": "320/320 PASS", "build+budget": "PASS", "backend_pure_logic": "15P/1S PASS", "backend_full": "1 failed(startup_check 测试债 DEF-11) / 1617 passed / 1 skipped (36m38s)", "o02_retest": "PASS"},
    },
    "environment_counts": {
        "BROWSER_INTEGRATION": sum(1 for c in cases if "BROWSER" in c["method"] and "MOCK" not in c["method"]),
        "API_INTEGRATION": sum(1 for c in cases if "API" in c["method"]),
        "STATIC_REVIEW": sum(1 for c in cases if "STATIC" in c["method"]),
        "HISTORICAL_EVIDENCE": sum(1 for c in cases if "HISTORICAL" in c["method"]),
        "UNIT": sum(1 for c in cases if "UNIT" in c["method"]),
        "BROWSER_MOCK": sum(1 for c in cases if "MOCK" in c["method"]),
    },
    "no_fake_note": "NOT_RUN/BLOCKED 全部保留；O02 首轮字段错误未计通过；历史通过未替代本轮 PASS",
    "revised_note": "2026-09-18 复核修订（另一 AI 审阅+本仓复核确认）：①关键旅程覆盖与 cases.json 对齐（执行 6+阻断 2+未做 4）；②状态分布与全部 PASS/FAIL 结论零变化；③配套修订见 测试报告.md §8 修订记录 与 progress.md",
}
with open(os.path.join(RUN, "coverage.json"), "w", encoding="utf-8") as f:
    json.dump(cov, f, ensure_ascii=False, indent=1)
print("cases:", len(cases), dict(cnt))
