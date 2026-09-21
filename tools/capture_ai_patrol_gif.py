"""Create a ~10-second AI patrol GIF for PPT explanation.

GET requests use the live read-only platform tunnel. Patrol submission/job reads
are intercepted with an anonymized fixture so the animation never creates a
production task or audit row.
"""
from __future__ import annotations
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import Route, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
from e2e_graph_acceptance import LOCAL_PORT, TunnelForward, fetch_session_material  # noqa: E402

FRONTEND = "http://127.0.0.1:4173"
PRODUCTION = f"http://127.0.0.1:{LOCAL_PORT}"
OUT = Path(r"D:\中心\20、评级\3、大赛\2026\14山东省数智健康大赛\多源医疗数据资产图谱与高质量数据治理实践\参赛截图_系统核查_20260830\AI巡查_问题分析_思考过程联合演示.gif")
JOBS = {
  9301: {"id":9301,"job_id":9301,"task_type":"finding_batch","status":"succeeded","result":{"id":9301,"job_id":9301,"risk_level":"medium","summary":"发现字段登记与关系证据不完整，建议补充字段级 JOIN 证据后复核。","review_status":"pending","structured_result":{"root_causes":[],"recommendations":[]}}},
  9302: {"id":9302,"job_id":9302,"task_type":"finding_batch","status":"succeeded","result":{"id":9302,"job_id":9302,"risk_level":"low","summary":"关系覆盖率存在提升空间，当前结论基于脱敏元数据。","review_status":"pending","structured_result":{"root_causes":[],"recommendations":[]}}},
  9303: {"id":9303,"job_id":9303,"task_type":"finding_batch","status":"succeeded","result":{"id":9303,"job_id":9303,"task_type":"finding_batch","risk_level":"medium","summary":"移动护理镜像表存在治理提醒，建议纳入下一轮人工复核。","review_status":"pending","structured_result":{"root_causes":[],"recommendations":[]}}},
}
FINDINGS = {"total": 3, "page": 1, "page_size": 50, "items": [
 {"id":12077,"rule_code":"TABLE_ZERO_COLUMNS","rule_name":"字段登记完整性","rule_description":"登记字段数与实际字段数不一致","problem":"病人住院主记录字段登记异常","target_display":"DATA_CENTER / HIS.PAT_VISIT","target_ref":"HIS.PAT_VISIT","target_type":"table","system_code":"DATA_CENTER","system_name_cn":"数据中心","source_code":"HIS","source_name_cn":"HIS","namespace_name":"HIS","schema_name":"HIS","table_name":"PAT_VISIT","table_name_cn":"病人住院主记录","column_name":"-","related_schema":"","related_table":"","related_field":"","severity":"major","status":"open","metric_value":"declared=268, actual=0","found_at":"2026-08-31T02:00:06Z"},
 {"id":12218,"rule_code":"RELATION_COVERAGE","rule_name":"关系覆盖率","rule_description":"核心表关联关系需要补充证据","problem":"病人手术主记录关系证据待补齐","target_display":"DATA_CENTER / SM.MED_OPERATION_MASTER","target_ref":"SM.MED_OPERATION_MASTER","target_type":"table","system_code":"DATA_CENTER","system_name_cn":"数据中心","source_code":"SM","source_name_cn":"手麻系统","namespace_name":"SM","schema_name":"SM","table_name":"MED_OPERATION_MASTER","table_name_cn":"病人手术主记录","column_name":"-","related_schema":"","related_table":"","related_field":"","severity":"minor","status":"open","metric_value":"coverage=0.19%","found_at":"2026-08-31T02:00:06Z"},
 {"id":12580,"rule_code":"MOBILE_MIRROR_FRESHNESS","rule_name":"镜像数据及时性","rule_description":"移动护理镜像表需关注同步时效","problem":"移动护理镜像数据存在时效提醒","target_display":"DATA_CENTER / YDHL.INPATIENTS","target_ref":"YDHL.INPATIENTS","target_type":"table","system_code":"DATA_CENTER","system_name_cn":"数据中心","source_code":"YDHL","source_name_cn":"移动护理","namespace_name":"YDHL","schema_name":"YDHL","table_name":"INPATIENTS","table_name_cn":"移动护理镜像数据表","column_name":"-","related_schema":"","related_table":"","related_field":"","severity":"major","status":"open","metric_value":"lag=0.7%","found_at":"2026-08-31T02:00:06Z"},
]}

def main() -> None:
    session = fetch_session_material(); tunnel = TunnelForward(); tunnel.start(); tunnel.serve()
    temp = Path(tempfile.mkdtemp(prefix="ai_patrol_gif_"))
    try:
      with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe", headless=True)
        context = browser.new_context(viewport={"width":1920,"height":1080}, device_scale_factor=1, color_scheme="light", record_video_dir=str(temp), record_video_size={"width":1920,"height":1080})
        context.add_init_script("localStorage.setItem('user-info', JSON.stringify(%s));document.cookie='multiple-tabs=true; path=/';" % json.dumps({**session,"nickname":"演示账号","username":"demo"}, ensure_ascii=False))
        def proxy(route: Route) -> None:
          req=route.request; p=urlsplit(req.url)
          if not (p.path.startswith('/api/') or p.path=='/get-async-routes'): route.continue_(); return
          if req.method=='POST' and p.path.endswith('/quality/ai/patrol/run'):
            data={"patrol_run_id":"demo-patrol-20260831","jobs":[{"table":"HIS.PAT_VISIT","job_id":9301},{"table":"SM.MED_OPERATION_MASTER","job_id":9302},{"table":"YDHL.INPATIENTS","job_id":9303}],"errors":[]}
            route.fulfill(status=202,content_type='application/json',body=json.dumps({"code":0,"message":"accepted","data":data},ensure_ascii=False)); return
          if req.method=='GET' and '/quality/ai/jobs/' in p.path:
            try: job=JOBS[int(p.path.rsplit('/',1)[-1])]
            except (KeyError,ValueError): job=None
            if job: route.fulfill(status=200,content_type='application/json',body=json.dumps({"code":0,"message":"success","data":job},ensure_ascii=False)); return
          if req.method=='GET' and p.path.endswith('/quality/findings'):
            route.fulfill(status=200, content_type='application/json', body=json.dumps({"code":0,"message":"success","data":FINDINGS},ensure_ascii=False)); return
          if req.method not in {'GET','HEAD','OPTIONS'}: route.abort('blockedbyclient'); return
          headers={k:v for k,v in req.headers.items() if k.lower() not in {'host','origin','referer','content-length'}}; headers['Authorization']=f"Bearer {session['accessToken']}"
          target=f"{PRODUCTION}{p.path}"+(f"?{p.query}" if p.query else '')
          route.fulfill(response=context.request.fetch(target,method=req.method,headers=headers,timeout=45000))
        context.route('**/*',proxy)
        page=context.new_page(); page.goto(f"{FRONTEND}/#/asset/ai-quality",wait_until='networkidle',timeout=90000); page.wait_for_timeout(1800)
        # Part 1: problem analysis first, with a readable, auditable progress panel.
        page.locator('.view-switch .el-segmented__item-label', has_text='问题分析').click(); page.wait_for_timeout(1800)
        checkbox = page.locator('.el-table__body-wrapper .el-checkbox__inner').first
        if checkbox.count(): checkbox.click(force=True)
        page.wait_for_timeout(1000)
        page.evaluate("""() => { const s=document.createElement('style'); s.id='progress-style'; s.textContent='.ai-progress-demo{padding:4px 2px;color:#303133;font-size:14px}.ai-progress-demo h3{margin:0 0 12px;color:#303133;font-size:17px}.ai-progress-demo .step{padding:9px 10px;margin-bottom:7px;border:1px solid #ebeef5;border-radius:6px;background:#fafcff}.ai-progress-demo .done{color:#1f9d55;background:#f0f9eb}.ai-progress-demo .current{color:#d88900;border-color:#f3d19e;background:#fdf6ec;font-weight:600}.ai-progress-demo small{display:block;color:#909399;margin-top:4px;font-size:12px}';document.head.appendChild(s); const host=document.querySelector('.report-panel .el-card__body'); if(host) host.innerHTML='<div class="ai-progress-demo"><h3>AI 分析进度 · 病人住院主记录</h3><div class="step current">● 读取治理问题<small>规则：TABLE_ZERO_COLUMNS · 严重度：重要</small></div><div class="step">○ 加载元数据证据</div><div class="step">○ 核对关系与值域</div><div class="step">○ 评估影响范围</div><div class="step">○ 生成治理建议</div></div>'; }""")
        page.wait_for_timeout(1700)
        for step in [
            ("加载元数据证据", "登记字段 268 · 实际字段 0 · 来源 DATA_CENTER"),
            ("核对关系与值域", "住院主键 + 离院方式值域 + 关系证据"),
            ("评估影响范围", "住院统计 · 离院方式分析 · AI 写 SQL"),
            ("生成治理建议", "重新采集 · 补充证据 · 人工复核"),
        ]:
            title, detail = step
            page.evaluate("""([title,detail]) => { const box=document.querySelector('.ai-progress-demo'); if(!box)return; const rows=[...box.querySelectorAll('.step')]; const i=rows.findIndex(x=>x.textContent.includes(title)); rows.forEach((r,j)=>{if(j<i)r.className='step done'; else if(j===i)r.className='step current';}); if(i>=0) rows[i].innerHTML='● '+title+'<small>'+detail+'</small>'; }""", [title, detail])
            page.wait_for_timeout(1600)
        page.evaluate("""() => { const box=document.querySelector('.ai-progress-demo'); if(box) box.innerHTML='<h3>AI 分析结果 <span style="float:right;color:#e6a23c;font-size:12px;font-weight:400">重要 · 待人工复核</span></h3><div class="step done"><b>问题定位：</b>病人住院主记录字段登记异常</div><div class="step done"><b>证据：</b>登记字段 268 个，实际字段 0 个；来源 DATA_CENTER</div><div class="step done"><b>根因：</b>元数据采集结果未同步到资产目录</div><div class="step done"><b>影响：</b>住院统计、离院方式分析、AI 写 SQL 上下文</div><div class="step current"><b>处理建议：</b>重新采集字段 → 补充 JOIN 证据 → 数据管理员确认</div>'; }""")
        page.wait_for_timeout(4800)
        page.evaluate("""() => { document.querySelector('#progress-style')?.remove(); }""")
        # Part 2: switch to AI patrol and show all three hospital core tables.
        page.locator('.view-switch .el-segmented__item-label', has_text='AI 巡查演示').click(); page.wait_for_timeout(2600)
        page.get_by_text('一键巡查',exact=True).click(); page.wait_for_timeout(3800)
        page.evaluate("""() => { const s=document.createElement('style');s.textContent='.patrol-summary-demo{margin-top:12px;padding:14px 16px;border:1px solid #dcdfe6;border-radius:8px;background:#f8fbff;color:#303133;font-size:14px}.patrol-summary-demo h3{margin:0 0 9px;color:#303133;font-size:17px}.patrol-summary-demo .item{padding:7px 9px;margin-bottom:6px;border-left:3px solid #e6a23c;background:#fff}.patrol-summary-demo b{color:#606266}.patrol-summary-demo .total{margin-top:10px;color:#1f9d55;font-weight:600}';document.head.appendChild(s);const host=document.querySelector('.patrol-results .el-card__body');if(host){const n=document.createElement('div');n.className='patrol-summary-demo';n.innerHTML='<h3>本轮 AI 巡查问题汇总</h3><div class="item"><b>住院主记录：</b>字段登记异常（重要）</div><div class="item"><b>手术主记录：</b>关系证据不完整（一般）</div><div class="item"><b>移动护理镜像表：</b>同步时效提醒（重要）</div><div class="total">3 张核心表 · 发现 3 项问题 · 已生成 3 份分析 · 待人工复核</div>';host.appendChild(n);} }""")
        page.mouse.wheel(0, 580); page.wait_for_timeout(3400); page.mouse.wheel(0, -580); page.wait_for_timeout(3200)
        page.close(); context.close(); browser.close()
      webm=next(temp.glob('*.webm'))
      palette=temp/'palette.png'
      # Drop the initial route-loading/empty-state seconds; the GIF opens on the
      # populated 3/3 result so the first frame is immediately useful in PPT.
      subprocess.run(['ffmpeg','-y','-ss','3.0','-i',str(webm),'-t','28','-vf','fps=8,scale=1280:-1:flags=lanczos,palettegen=max_colors=192',str(palette)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
      subprocess.run(['ffmpeg','-y','-ss','3.0','-i',str(webm),'-t','28','-i',str(palette),'-lavfi','fps=8,scale=1280:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=sierra2_4a', '-loop','0',str(OUT)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
      print(json.dumps({"output":str(OUT),"size":OUT.stat().st_size},ensure_ascii=False))
    finally:
      tunnel.stop(); shutil.rmtree(temp,ignore_errors=True)

if __name__=='__main__': main()
