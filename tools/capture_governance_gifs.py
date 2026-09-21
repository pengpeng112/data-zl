"""Capture two long-form, PPT-ready governance GIFs using production read-only GETs."""
from __future__ import annotations
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import Route, sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'/'scripts'))
from e2e_graph_acceptance import LOCAL_PORT, TunnelForward, fetch_session_material  # noqa:E402

FRONTEND='http://127.0.0.1:4173'; PRODUCTION=f'http://127.0.0.1:{LOCAL_PORT}'
OUT=Path(r'D:\中心\20、评级\3、大赛\2026\14山东省数智健康大赛\多源医疗数据资产图谱与高质量数据治理实践\参赛截图_系统核查_20260830\治理动态配图')

def gif_from_webm(webm:Path,out:Path,start:float,duration:float)->None:
    palette=webm.parent/(out.stem+'_palette.png')
    vf='fps=8,scale=1280:-1:flags=lanczos'
    subprocess.run(['ffmpeg','-y','-ss',str(start),'-i',str(webm),'-t',str(duration),'-vf',vf+',palettegen=max_colors=192',str(palette)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['ffmpeg','-y','-ss',str(start),'-i',str(webm),'-t',str(duration),'-i',str(palette),'-lavfi',vf+'[x];[x][1:v]paletteuse=dither=sierra2_4a','-loop','0',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def main()->None:
    OUT.mkdir(parents=True,exist_ok=True); temp=Path(tempfile.mkdtemp(prefix='governance_gifs_'))
    session=fetch_session_material(); tunnel=TunnelForward(); tunnel.start(); tunnel.serve()
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        def new_context(name:str):
          ctx=browser.new_context(viewport={'width':1920,'height':1080},device_scale_factor=1,color_scheme='light',record_video_dir=str(temp/name),record_video_size={'width':1920,'height':1080})
          ctx.add_init_script("localStorage.setItem('user-info', JSON.stringify(%s));document.cookie='multiple-tabs=true; path=/';"%json.dumps({**session,'nickname':'演示账号','username':'demo'},ensure_ascii=False))
          def proxy(route:Route)->None:
            req=route.request;p=urlsplit(req.url)
            if not(p.path.startswith('/api/') or p.path=='/get-async-routes'):route.continue_();return
            if req.method not in {'GET','HEAD','OPTIONS'}:route.abort('blockedbyclient');return
            headers={k:v for k,v in req.headers.items() if k.lower() not in {'host','origin','referer','content-length'}};headers['Authorization']=f"Bearer {session['accessToken']}"
            target=f'{PRODUCTION}{p.path}'+(f'?{p.query}' if p.query else '')
            route.fulfill(response=ctx.request.fetch(target,method=req.method,headers=headers,timeout=45000))
          ctx.route('**/*',proxy);return ctx

        # GIF 1: command center -> asset overview -> catalogue/field drill-down.
        if False:
          ctx=new_context('overview');page=ctx.new_page()
          page.goto(f'{FRONTEND}/#/welcome',wait_until='networkidle',timeout=90000);page.wait_for_timeout(2500)
          for delta in (430,480,520): page.mouse.wheel(0,delta);page.wait_for_timeout(1800)
          page.mouse.wheel(0,-1500);page.wait_for_timeout(1200)
          page.goto(f'{FRONTEND}/#/asset/overview',wait_until='networkidle',timeout=90000);page.wait_for_timeout(2500)
          for delta in (420,460): page.mouse.wheel(0,delta);page.wait_for_timeout(1800)
          page.goto(f'{FRONTEND}/#/asset/tables',wait_until='networkidle',timeout=90000);page.wait_for_timeout(2500)
          page.mouse.wheel(0,430);page.wait_for_timeout(1800);page.close();ctx.close()
          webm=next((temp/'overview').glob('*.webm'));gif_from_webm(webm,OUT/'01_指挥中心大屏与资产总览.gif',3,25)

        # GIF 2: real graph drill-down: overview -> PAT_VISIT 1-hop -> 2-hop -> inspector.
        ctx=new_context('graph');page=ctx.new_page()
        ctx.add_init_script("HTMLCanvasElement.prototype.getContext=function(){return null}")
        page.goto(f'{FRONTEND}/#/asset/graph',wait_until='networkidle',timeout=90000);page.wait_for_timeout(6000)
        # SVG fallback gives deterministic, clickable labels for genuine layers.
        system_node=page.locator('svg .node-title').filter(has_text='数据中心').first
        if system_node.count(): system_node.locator('..').click(force=True);page.wait_for_timeout(6000)
        schema_node=page.locator('svg .node-title').filter(has_text='HIS').first
        if schema_node.count(): schema_node.locator('..').click(force=True);page.wait_for_timeout(6000)
        page.wait_for_timeout(4500)
        # Start a clean relation-explore state so overview filters do not suppress
        # PAT_VISIT neighbors.
        page.goto(f'{FRONTEND}/#/welcome',wait_until='networkidle',timeout=90000);page.wait_for_timeout(1200)
        page.goto(f'{FRONTEND}/#/asset/graph',wait_until='networkidle',timeout=90000);page.wait_for_timeout(5000)
        page.locator('.el-segmented__item',has_text='关系探索').first.click();page.wait_for_timeout(2500)
        search=page.locator("input[placeholder*='搜索表名']").first
        search.fill('DATA_CENTER|ods_8_216|HIS|HIS|PAT_VISIT');page.get_by_role('button',name='搜索并聚焦').click();page.wait_for_timeout(9000)
        depth=page.locator('.global-search-row .el-segmented').first
        depth.get_by_text('2 跳',exact=True).click();page.wait_for_timeout(9000)
        node=page.locator('svg .node-title').filter(has_text='PAT_VISIT').first
        if node.count(): node.locator('..').click(force=True);page.wait_for_timeout(3500)
        page.close();ctx.close()
        webm=next((temp/'graph').glob('*.webm'));gif_from_webm(webm,OUT/'02_关系图谱逐层下钻.gif',3,32)
        browser.close()
    finally:
      tunnel.stop();shutil.rmtree(temp,ignore_errors=True)
    print(json.dumps({'output':str(OUT),'files':['01_指挥中心大屏与资产总览.gif','02_关系图谱逐层下钻.gif']},ensure_ascii=False))

if __name__=='__main__':main()
