#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_zcode_conversations.py — 从本机 ZCode 会话库导出指定项目的历次对话为 Markdown。

用途：把「用户 ↔ AI」的历次会话（含工具调用摘要）导出为可直接交给其他 AI/工具
分析的纯文本档案。

数据源（本机只读）：
  C:/Users/<user>/.zcode/cli/db/db.sqlite
    session  表：directory/path 定位项目；title 为会话标题
    message  表：role(user/assistant)、sequence、时间(ms epoch)
    part     表：消息分片；type=text 为正文，type=tool 为工具调用（state 含输入/输出）
  （补充源：C:/Users/<user>/.zcode/cli/rollout/model-io-sess_*.jsonl 为模型级请求流，
   体积大且含完整 system prompt，一般分析用本脚本导出的会话档案即可。）

用法：
  python tools/export_zcode_conversations.py                       # 默认导出"数据资产"项目
  python tools/export_zcode_conversations.py --project datart      # 其它项目按目录关键词
  python tools/export_zcode_conversations.py --include-subagents   # 连子代理会话一起导
  python tools/export_zcode_conversations.py --full-tools          # 工具输出不截断（文件很大）
  python tools/export_zcode_conversations.py --out D:/conv         # 自定义输出目录

注意：导出内容含内网 IP、工号、路径等内部信息——仅限本机/内网受控环境分析使用，
禁止上传公网服务或随 git 提交。
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = Path(r"C:\Users\Administrator\.zcode\cli\db\db.sqlite")
DEFAULT_OUT = Path(r"F:\python") / "对话导出_数据资产"
TOOL_SNIPPET = 400


def ms(t):
    try:
        return datetime.fromtimestamp(int(t) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(t or "")


def state_brief(state_raw, full):
    try:
        st = json.loads(state_raw) if isinstance(state_raw, str) else (state_raw or {})
    except Exception:
        return "(state 不可解析)"
    inp = st.get("input") or {}
    keys = ("command", "sql", "file_path", "prompt", "url", "code", "path", "description")
    picked = {k: v for k, v in inp.items() if k in keys and v}
    brief = json.dumps(picked, ensure_ascii=False)
    if not full and len(brief) > TOOL_SNIPPET:
        brief = brief[:TOOL_SNIPPET] + "…"
    lines = [f"    输入: {brief}"]
    out = st.get("output")
    if out is not None:
        text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        if not full and len(text) > TOOL_SNIPPET:
            text = text[:TOOL_SNIPPET] + "…"
        lines.append(f"    输出: {text}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="数据资产", help="session directory/path 关键词")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--include-subagents", action="store_true")
    ap.add_argument("--full-tools", action="store_true")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    if not Path(args.db).is_file():
        sys.exit(f"会话库不存在: {args.db}")
    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    like = f"%{args.project}%"
    sessions = con.execute(
        "SELECT id, title, directory FROM session "
        "WHERE (directory LIKE ? OR path LIKE ?) ORDER BY id", (like, like)).fetchall()
    if not args.include_subagents:
        sessions = [s for s in sessions if not s["id"].startswith("sess_subagent_")]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    index = ["# 会话导出索引", "",
             f"- 项目关键词：{args.project}",
             f"- 导出时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
             f"- 会话数：{len(sessions)}（子代理{'含' if args.include_subagents else '不含'}）",
             f"- 工具输出：{'完整' if args.full_tools else f'截断 {TOOL_SNIPPET} 字符'}", "",
             "| # | 文件 | 标题 | 消息数 | 时间范围 |", "|---|---|---|---|---|"]
    total_msgs = 0
    for i, s in enumerate(sessions, 1):
        msgs = con.execute(
            "SELECT id, json_extract(data,'$.role') AS role, time_created, sequence "
            "FROM message WHERE session_id=? ORDER BY sequence, id",
            (s["id"],)).fetchall()
        total_msgs += len(msgs)
        fname = f"{i:03d}_{s['id'].replace('sess_', '')[:12]}.md"
        t0 = ms(msgs[0]["time_created"]) if msgs else ""
        t1 = ms(msgs[-1]["time_created"]) if msgs else ""
        index.append(f"| {i} | {fname} | {(s['title'] or '')[:40].replace('|', '/')} | {len(msgs)} | {t0[:16]}~{t1[:11]} |")
        with (out_dir / fname).open("w", encoding="utf-8") as f:
            f.write(f"# 会话 {i}：{s['title'] or '(无标题)'}\n\n"
                    f"- session_id: `{s['id']}`\n- 目录: {s['directory']}\n"
                    f"- 消息数: {len(msgs)}\n- 时间: {t0} ~ {t1}\n\n---\n\n")
            for m in msgs:
                role = m["role"] or "?"
                parts = con.execute(
                    "SELECT data FROM part WHERE message_id=? ORDER BY sequence, id",
                    (m["id"],)).fetchall()
                body = []
                for p in parts:
                    d = json.loads(p["data"])
                    if d.get("type") == "text":
                        body.append(str(d.get("text") or ""))
                    elif d.get("type") == "tool" and not args.full_tools is None:
                        st = d.get("state")
                        body.append(f"🔧 [{d.get('tool')}] 已调用\n"
                                    + state_brief(json.dumps(st, ensure_ascii=False) if not isinstance(st, str) else st,
                                                  args.full_tools))
                text = "\n\n".join(x for x in body if x.strip())
                if not text.strip():
                    continue
                who = "👤 用户" if role == "user" else ("🤖 AI" if role == "assistant" else f"({role})")
                f.write(f"## {who} · {ms(m['time_created'])}\n\n{text}\n\n")
    (out_dir / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"导出完成：{len(sessions)} 个会话 / {total_msgs} 条消息 -> {out_dir}")
    print(f"索引：{out_dir / 'INDEX.md'}")


if __name__ == "__main__":
    main()
