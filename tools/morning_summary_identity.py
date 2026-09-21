#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""186 晨检汇总（只读）：disable_only 夜跑窗口进度与 enable 状态核对。

两种模式：
  1) 本地证据文件（无网络）：python tools/morning_summary_identity.py -i evidence.json
  2) 平台 API（token 从环境变量读，不硬编码、不落盘、不回显）：
     set ID_TOKEN=xxx && python tools/morning_summary_identity.py --api http://10.10.8.83 --token-env ID_TOKEN

数据来源（与 ro_identity_nightly_observe.py 同一 readonly 视角）：
  - 本地文件：接受归一化 schema（见下）或平台 GET /api/v1/identity-sync/runs 列表 +
    /runs/{run_id} 详情（account_state_attempts）导出的原始 JSON。
  - API 模式：逐 run 只读 GET 上述两个端点；夜间状态端点 best-effort 提取 run_mode。

归一化证据 schema（-i 模式）：
  {
    "baseline": {"approved_total": 230},
    "pending_category": {"total": 60},
    "expected_window_dates": ["2026-09-10", ...],        // 可选：仅用于"无记录"核对
    "config_evidence": {"enable_enabled": false},         // 可选
    "person_categories": {"pending_adjudication": [...]}, // 可选：工号级类目归属
    "windows": [
      {"date": "2026-09-10", "run_id": "RUN-...", "status": "success",
       "attempts": [
         {"person_code": "003740", "target_system": "JHEMR", "action": "disable",
          "status": "executed", "reason_code": null, "category": "baseline"}
       ]}
    ]
  }

口径（严格遵守，代码即口径）：
  - 人员与目标动作分开计数：人员按 person_code 去重；动作按 JHEMR/CDMS 双目标分别统计；
  - 人员"已执行"= 至少 1 个目标 disable executed；partial = 仅单目标成对未齐（单独展示，不并入失败）；
    blocked/failed/skipped 单独展示；
  - 只显示"已执行 X/230"实际数与各窗口明细；禁止按天数/窗口数推算预期进度或完成日期（本工具无此计算）；
  - 60 人类目单独一节，标注"待裁决，未纳入 230 批准基线"；
  - enable 状态固定展示（预期关闭）；证据显示开启或已有 enable 动作执行则醒目警告；
  - 无证据日期显示"无记录"，不插值（仅在 --dates/expected_window_dates 明确列出的日期核对）；
  - 输出无凭据、无身份证/姓名、无工号清单（只输出聚合计数、日期、run_id）。

退出码：0=正常；2=用法/环境错误；3=输入文件或 API 错误。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASELINE_DEFAULT = 230
PENDING_CATEGORY_DEFAULT_TOTAL = 60
TARGETS = ("JHEMR", "CDMS")
EXECUTED_STATUSES = ("executed", "success")
WARNING_MARK = "**[警告]**"
NO_RECORD = "无记录"


# ---------------- 归一化 ----------------

def _as_list(x):
    return x if isinstance(x, list) else []


def _norm_status(value):
    return str(value or "").strip().lower() or "unknown"


def _is_executed(status):
    return status in EXECUTED_STATUSES


def _window_date(win):
    for key in ("date", "window_date"):
        v = win.get(key)
        if v:
            return str(v)[:10]
    return str(win.get("started_at") or "")[:10] or "unknown"


def normalize_evidence(raw):
    if not isinstance(raw, dict):
        raise ValueError("evidence must be a JSON object")
    windows_raw = (_as_list(raw.get("windows")) or _as_list(raw.get("runs"))
                   or _as_list(raw.get("items")))
    if not windows_raw and isinstance(raw.get("data"), dict):
        windows_raw = _as_list(raw["data"].get("items"))
    pending_map = {}
    cats = raw.get("person_categories")
    if isinstance(cats, dict):
        for code in _as_list(cats.get("pending_adjudication")):
            pending_map[str(code)] = "pending_adjudication"
    windows = []
    for w in windows_raw:
        if not isinstance(w, dict):
            continue
        attempts = []
        for a in _as_list(w.get("attempts")) or _as_list(w.get("account_state_attempts")):
            if not isinstance(a, dict):
                continue
            person = str(a.get("person_code") or a.get("personCode") or "")
            raw_category = str(a.get("category") or "").strip().lower()
            attempts.append({
                "person_code": person,
                "target_system": str(a.get("target_system") or a.get("targetSystem") or "").upper(),
                "action": _norm_status(a.get("action")),
                "status": _norm_status(a.get("status")),
                "reason_code": (str(a.get("reason_code") or a.get("reasonCode") or "")[:80] or None),
                "category": raw_category or pending_map.get(person, "baseline"),
            })
        windows.append({
            "date": _window_date(w),
            "run_id": str(w.get("run_id") or w.get("runId") or "")[:40] or None,
            "status": str(w.get("status") or "")[:24] or "unknown",
            "started_at": w.get("started_at"),
            "attempts": attempts,
        })
    windows.sort(key=lambda w: w["date"])
    baseline_raw = raw.get("baseline") if isinstance(raw.get("baseline"), dict) else {}
    pending_raw = raw.get("pending_category") if isinstance(raw.get("pending_category"), dict) else {}
    cfg = raw.get("config_evidence") if isinstance(raw.get("config_evidence"), dict) else {}
    enable_cfg = cfg.get("enable_enabled")
    if not isinstance(enable_cfg, bool):
        enable_cfg = None
    return {
        "windows": windows,
        "baseline_total": int(baseline_raw.get("approved_total") or BASELINE_DEFAULT),
        "pending_total": int(pending_raw.get("total") or PENDING_CATEGORY_DEFAULT_TOTAL),
        "expected_dates": [str(d)[:10] for d in _as_list(raw.get("expected_window_dates"))],
        "enable_config": enable_cfg,
    }


# ---------------- 计数口径 ----------------

def _person_state(attempts):
    """单窗口单人状态：dual/partial/blocked/failed/skipped/none。"""
    executed, blocked, failed, skipped = set(), 0, 0, 0
    for a in attempts:
        if _is_executed(a["status"]):
            executed.add(a["target_system"])
        elif a["status"] == "blocked" or a["status"] == "pending_reconcile":
            blocked += 1
        elif a["status"] == "failed":
            failed += 1
        elif a["status"] in ("skipped", "cancelled_stale"):
            skipped += 1
    if executed:
        return "dual" if len(executed) >= 2 else "partial"
    if blocked:
        return "blocked"
    if failed:
        return "failed"
    if skipped:
        return "skipped"
    return "none"


def _empty_action_totals():
    return {t: {"executed": 0, "attempted": 0, "blocked": 0, "failed": 0, "skipped": 0}
            for t in TARGETS}


_STATE_RANK = {"dual": 5, "partial": 4, "failed": 3, "blocked": 2, "skipped": 1, "none": 0}


def _merge_state(a, b):
    return a if _STATE_RANK.get(a, 0) >= _STATE_RANK.get(b, 0) else b


def summarize(ev, *, expected_dates=None, baseline_total=None, pending_total=None):
    windows_summary = []
    persons_global = {}   # person_code -> {"state": best, "category": ...}
    action_totals = _empty_action_totals()
    enable_actions = {"total": 0, "executed": 0}

    for w in ev["windows"]:
        per_person = {}
        for a in w["attempts"]:
            if a["action"] == "enable":
                enable_actions["total"] += 1
                if _is_executed(a["status"]):
                    enable_actions["executed"] += 1
                continue
            if a["action"] != "disable":
                continue
            per_person.setdefault(a["person_code"], []).append(a)
            bucket = action_totals.get(a["target_system"])
            if bucket is not None:
                bucket["attempted"] += 1
                if _is_executed(a["status"]):
                    bucket["executed"] += 1
                elif a["status"] in ("blocked", "pending_reconcile"):
                    bucket["blocked"] += 1
                elif a["status"] == "failed":
                    bucket["failed"] += 1
                elif a["status"] in ("skipped", "cancelled_stale"):
                    bucket["skipped"] += 1

        counts = {"planned": 0, "executed": 0, "partial": 0,
                  "blocked": 0, "failed": 0, "skipped": 0}
        split = {"baseline": dict(counts), "pending_adjudication": dict(counts)}
        for person, atts in per_person.items():
            state = _person_state(atts)
            category = "pending_adjudication" if any(
                x["category"] == "pending_adjudication" for x in atts) else "baseline"
            for bucket_name, bucket in (("all", counts), (category, split[category])):
                bucket["planned"] += 1
                if state in ("dual", "partial"):
                    bucket["executed"] += 1
                if state == "partial":
                    bucket["partial"] += 1
                elif state == "blocked":
                    bucket["blocked"] += 1
                elif state == "failed":
                    bucket["failed"] += 1
                elif state == "skipped":
                    bucket["skipped"] += 1
            prev = persons_global.get(person)
            if prev is None:
                persons_global[person] = {"state": state, "category": category}
            else:
                prev["state"] = _merge_state(prev["state"], state)

        windows_summary.append({
            "date": w["date"], "run_id": w["run_id"], "status": w["status"],
            "persons": counts, "persons_by_category": split,
        })

    def _global(category):
        states = [v["state"] for v in persons_global.values() if v["category"] == category]
        return {
            "executed": sum(1 for s in states if s in ("dual", "partial")),
            "partial": sum(1 for s in states if s == "partial"),
            "blocked": sum(1 for s in states if s == "blocked"),
            "failed": sum(1 for s in states if s == "failed"),
            "skipped": sum(1 for s in states if s == "skipped"),
        }

    baseline = _global("baseline")
    pending = _global("pending_adjudication")
    baseline_total = int(baseline_total if baseline_total is not None else ev["baseline_total"])
    pending_total = int(pending_total if pending_total is not None else ev["pending_total"])

    enable_config = ev["enable_config"]
    enable_warning = bool(enable_actions["executed"] > 0 or enable_config is True)

    dates = [d for d in (expected_dates or ev["expected_dates"])]
    date_rows = []
    by_date = {w["date"]: w for w in windows_summary}
    for d in sorted(dict.fromkeys(dates)):
        row = {"date": d}
        win = by_date.get(d)
        if win is None:
            row["record"] = False
        else:
            row.update({"record": True, "run_id": win["run_id"], "status": win["status"],
                        "persons": win["persons"]})
        date_rows.append(row)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_total": baseline_total,
        "pending_total": pending_total,
        "baseline_persons": baseline,
        "baseline_progress": f"{baseline['executed']}/{baseline_total}",
        "pending_persons": pending,
        "windows": windows_summary,
        "action_totals": {t: action_totals[t] for t in TARGETS},
        "enable": {
            "config_evidence": enable_config,
            "enable_actions": enable_actions,
            "expected": "closed",
            "warning": enable_warning,
        },
        "date_rows": date_rows,
        "window_count": len(windows_summary),
    }


# ---------------- 渲染（只输出聚合/日期/run_id，无工号无姓名无凭据） ----------------

def _fmt_actions(action_totals):
    return "；".join(
        f"{t} 已执行 {v['executed']}/{v['attempted']}"
        f"（blocked {v['blocked']}｜failed {v['failed']}｜skipped {v['skipped']}）"
        for t, v in action_totals.items())


def _fmt_persons(c, total=None):
    suffix = f"/{total}" if total is not None else ""
    return (f"已执行 {c['executed']}{suffix}（partial {c['partial']}｜blocked {c['blocked']}"
            f"｜failed {c['failed']}｜skipped {c['skipped']}）")


def render_text(s, *, source=""):
    L = ["# 186 晨检汇总 · disable_only 夜跑（只读）",
         "",
         f"- 证据来源：{source}｜生成时间 {s['generated_at']}｜证据窗口数 {s['window_count']}",
         "- 口径：人员与目标动作分开计数；partial/blocked 单独展示；"
         "仅实际证据计数，不按天数/窗口数推算预期进度或完成日期", "",
         "## 总览（230 批准基线）",
         f"- 人员（跨窗口去重）：{_fmt_persons(s['baseline_persons'], s['baseline_total'])}",
         f"- 目标动作：{_fmt_actions(s['action_totals'])}", ""]
    if s["windows"]:
        L.append("## 各窗口明细")
        for w in s["windows"]:
            L.append(f"### {w['date']} · {w['run_id'] or '-'} · {w['status']}")
            L.append(f"- 人员：{_fmt_persons(w['persons'])}")
            p = w["persons_by_category"]["pending_adjudication"]
            if p["planned"]:
                L.append(f"- 其中待裁决类目：{_fmt_persons(p)}")
            L.append("")
    else:
        L += ["## 各窗口明细", NO_RECORD, ""]
    if s["date_rows"]:
        L.append("## 按日期核对（仅列出明确核对日期；未列日期不推断、不插值）")
        for row in s["date_rows"]:
            if row["record"]:
                c = row["persons"]
                L.append(f"- {row['date']}：{row['run_id']}（{row['status']}）——"
                         f"已执行 {c['executed']} 人（partial {c['partial']}｜blocked {c['blocked']}）")
            else:
                L.append(f"- {row['date']}：{NO_RECORD}")
        L.append("")
    L += ["## 员工侧停用 60 人类目（待裁决，未纳入 230 批准基线）",
          f"- 人员：{_fmt_persons(s['pending_persons'], s['pending_total'])}",
          "- 说明：该类目尚未获批准执行，计数仅为证据留痕，不并入上方 230 口径", "",
          "## enable 状态（预期关闭）"]
    cfg = s["enable"]["config_evidence"]
    cfg_text = {True: "证据显示开启", False: "证据显示关闭", None: NO_RECORD}[cfg]
    L.append(f"- 配置证据：{cfg_text}")
    acts = s["enable"]["enable_actions"]
    acts_text = (f"{acts['total']} 个（executed {acts['executed']}）" if acts["total"] else NO_RECORD)
    L.append(f"- enable 动作：{acts_text}")
    if s["enable"]["warning"]:
        L.append(f"- {WARNING_MARK} 证据显示 enable 已开启或已有 enable 动作执行——"
                 "与 186 批准口径（enable 结构性关闭）不符，需立即人工核对")
    else:
        L.append("- 与预期一致：未见 enable 开启证据")
    L.append("")
    L.append("> 本工具只读；无凭据、无身份证/姓名、无工号输出。")
    return "\n".join(L)


# ---------------- API 模式（只读 GET；token 仅经环境变量，不回显不落盘） ----------------

def _http_get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_enable_flag(payload):
    """best-effort：从夜间状态响应识别 run_mode / enable 开关。True/False/None=无证据。"""
    def _scan(obj):
        if isinstance(obj, dict):
            run_mode = obj.get("run_mode") or obj.get("runMode")
            if isinstance(run_mode, str):
                rm = run_mode.lower()
                if "disable_only" in rm or rm == "disable":
                    return False
                if "enable" in rm:
                    return True
            if isinstance(obj.get("enable_enabled"), bool):
                return obj["enable_enabled"]
            for v in obj.values():
                found = _scan(v)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for v in obj:
                found = _scan(v)
                if found is not None:
                    return found
        return None
    return _scan(payload)


def fetch_api_evidence(base_url, token, *, page_size=100, max_runs=50, fetch=None):
    fetch = fetch or _http_get_json
    base = str(base_url).rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    runs_payload = fetch(f"{base}/api/v1/identity-sync/runs?page=1&page_size={int(page_size)}",
                         headers=headers)
    items = None
    if isinstance(runs_payload, dict):
        data = runs_payload.get("data")
        items = data.get("items") if isinstance(data, dict) else runs_payload.get("items")
    windows = []
    for item in _as_list(items)[:max_runs]:
        if not isinstance(item, dict):
            continue
        attempts = []
        run_id = item.get("run_id")
        if run_id:
            detail = fetch(f"{base}/api/v1/identity-sync/runs/{run_id}", headers=headers)
            dd = detail.get("data") if isinstance(detail.get("data"), dict) else {}
            attempts = _as_list(dd.get("account_state_attempts"))
        windows.append({**item, "attempts": attempts})
    raw = {"windows": windows, "fetched_at": datetime.now().isoformat(timespec="seconds")}
    try:
        status_payload = fetch(f"{base}/api/v1/identity-sync/nightly/status", headers=headers)
        flag = _extract_enable_flag(status_payload)
        if flag is not None:
            raw["config_evidence"] = {"enable_enabled": flag}
    except Exception:
        pass  # 状态端点不可用不阻塞：enable 证据显示"无记录"
    return raw


# ---------------- CLI ----------------

def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="186 morning summary: readonly disable_only nightly windows (no credentials output)")
    parser.add_argument("-i", "--input", default=None, help="本地证据 JSON 文件（无网络）")
    parser.add_argument("--api", default=None, help="平台 base_url（如 http://10.10.8.83）")
    parser.add_argument("--token-env", default=None, help="承载 API token 的环境变量名")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--baseline-total", type=int, default=None)
    parser.add_argument("--pending-total", type=int, default=None)
    parser.add_argument("--dates", default=None,
                        help="逗号分隔核对日期（YYYY-MM-DD）；缺省用证据 expected_window_dates")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv=None):
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    args = parse_args(argv)
    if bool(args.input) == bool(args.api):
        print("[morning_summary] FAIL code=2: 需要 -i <json> 或 --api <base_url> --token-env <VAR>（二选一）",
              file=sys.stderr)
        return 2
    if args.api and not args.token_env:
        print("[morning_summary] FAIL code=2: --api 需要 --token-env <VAR>（token 从环境变量读）",
              file=sys.stderr)
        return 2
    try:
        if args.input:
            raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
            source = f"文件 {Path(args.input).name}"
        else:
            token = os.environ.get(args.token_env, "")
            if not token:
                print(f"[morning_summary] FAIL code=2: 环境变量 {args.token_env} 未设置"
                      "（token 不硬编码、不回显、不落盘）", file=sys.stderr)
                return 2
            raw = fetch_api_evidence(args.api, token, page_size=args.page_size)
            source = f"API（{len(raw['windows'])} runs 只读拉取）"
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"[morning_summary] FAIL code=3: {type(exc).__name__}: "
              f"{str(exc)[:120]}（输出不含 URL 查询串与 token）", file=sys.stderr)
        return 3
    ev = normalize_evidence(raw)
    expected = ([d.strip() for d in args.dates.split(",") if d.strip()]
                if args.dates else None)
    s = summarize(ev, expected_dates=expected,
                  baseline_total=args.baseline_total, pending_total=args.pending_total)
    if args.format == "json":
        print(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        print(render_text(s, source=source))
    return 0


if __name__ == "__main__":
    sys.exit(main())
