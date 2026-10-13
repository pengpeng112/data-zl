#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""perf_patrol.py — 平台只读接口 p50/p95 性能巡检（215 号 E9，tools 族）。

背景（round-12 R7 / 209·212 O01 口径）：性能只有一次性抽样记录（列表端点
5 并发 p50≈100-270ms、ai/context/resolve 1 并发≈2.7s），无固化巡检；本脚本
把「固定七端点、逐接口 p50/p95/错误率留档」固化为可重复执行的本地巡检。

口径（沿用 212 O01：无 SLO，只报告实测，不宣称达标）：
- 七端点 = 1 个就绪 + 5 个跨域列表（tables/relations/queries/metrics/
  data-products）+ 1 个慢路径样本（ai/context/resolve，POST）；
- 每端点默认 20 次串行采样（--samples 可调），统计 p50/p95/min/max/错误率；
- 只读：GET 列表 + resolve 构建快照（写留档行为与线上等价，不在本巡检
  语义内新增写操作）；
- 目标环境默认本机开发实例；**禁止指向生产**——非 localhost/127.0.0.1
  的 --base-url 需要 --allow-remote 显式确认；
- 产物留档到 开起步包/output_r215/perf_patrol/<时间戳>.json（--json 只打
  报告不落盘）。

用法：
  backend/.venv/Scripts/python.exe tools/perf_patrol.py --token <API token>
  backend/.venv/Scripts/python.exe tools/perf_patrol.py --token ... --json   # 不落盘
  backend/.venv/Scripts/python.exe tools/perf_patrol.py --list-endpoints
退出码：0=巡检完成（即使有错误率），1=全部端点不可达，2=用法/环境错误。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "开发起步包" / "output_r215" / "perf_patrol"

# 212 O01 抽样口径的七端点（列表端点 + 慢路径样本；209/212 实测沿用）
PATROL_ENDPOINTS = [
    {"name": "health_readiness", "method": "GET", "path": "/api/v1/health", "auth": False},
    {"name": "tables_list", "method": "GET", "path": "/api/v1/tables?page=1&page_size=20", "auth": True},
    {"name": "relations_list", "method": "GET", "path": "/api/v1/relations/list?page=1&page_size=20", "auth": True},
    {"name": "queries_list", "method": "GET", "path": "/api/v1/queries?page=1&page_size=20", "auth": True},
    {"name": "metrics_list", "method": "GET", "path": "/api/v1/metrics?page=1&page_size=20", "auth": True},
    {"name": "data_products_list", "method": "GET", "path": "/api/v1/data-products?page=1&page_size=20", "auth": True},
    {"name": "ai_context_resolve", "method": "POST", "path": "/api/v1/ai/context/resolve", "auth": True,
     "body": {"question_summary": "perf-patrol-215 巡检样本", "system_code": None, "max_objects": 20}},
]


def _request_once(base_url: str, endpoint: dict, token: str | None, timeout: float) -> tuple[bool, float, int | None]:
    url = base_url.rstrip("/") + endpoint["path"]
    data = json.dumps(endpoint.get("body") or {}).encode("utf-8") if endpoint["method"] == "POST" else None
    req = urllib.request.Request(url, data=data, method=endpoint["method"])
    req.add_header("Accept", "application/json")
    if endpoint.get("auth"):
        if not token:
            return False, 0.0, None  # 无 token：跳过（不计失败，不伪造成功）
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
        return True, (time.perf_counter() - start) * 1000, resp.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return False, (time.perf_counter() - start) * 1000, exc.code
    except Exception:
        return False, (time.perf_counter() - start) * 1000, None


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, max(0, round(pct / 100 * (len(sorted_values) - 1))))
    return round(sorted_values[idx], 2)


def patrol(base_url: str, token: str | None, samples: int, timeout: float) -> dict:
    results = []
    for ep in PATROL_ENDPOINTS:
        if ep.get("auth") and not token:
            results.append({"name": ep["name"], "status": "skipped_no_token"})
            continue
        durations: list[float] = []
        errors = 0
        last_status: int | None = None
        for _ in range(samples):
            ok, ms, status = _request_once(base_url, ep, token, timeout)
            last_status = status
            if ok:
                durations.append(ms)
            else:
                errors += 1
        durations.sort()
        results.append({
            "name": ep["name"],
            "method": ep["method"],
            "path": ep["path"].split("?")[0],
            "samples": samples,
            "ok": len(durations),
            "errors": errors,
            "error_rate": round(errors / samples, 4) if samples else None,
            "last_status": last_status,
            "p50_ms": _percentile(durations, 50),
            "p95_ms": _percentile(durations, 95),
            "min_ms": round(durations[0], 2) if durations else None,
            "max_ms": round(durations[-1], 2) if durations else None,
        })
    # 可达 = 拿到过任何 HTTP 响应（ok>0 或有状态码的失败）；连接层失败
    # （last_status=None 且 ok=0）不算可达；无 token 跳过不算不可达。
    reachable = sum(
        1 for r in results
        if r.get("ok", 0) > 0 or (r.get("last_status") is not None and r.get("status") != "skipped_no_token")
    )
    return {
        "tool": "perf_patrol",
        "base_url": base_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "samples_per_endpoint": samples,
        "slo": "无SLO：只报告实测（212 O01 口径），不宣称达标",
        "endpoints": results,
        "reachable_endpoints": reachable,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="平台只读接口 p50/p95 巡检（215 E9）")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", default=None, help="API Bearer token（认证端点必需，缺失则跳过）")
    parser.add_argument("--samples", type=int, default=20, help="每端点采样次数（默认 20）")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--allow-remote", action="store_true",
                        help="允许非 localhost 目标（防误指生产）")
    parser.add_argument("--list-endpoints", action="store_true", help="只打印巡检端点清单")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告（不落盘）")
    args = parser.parse_args(argv)

    if args.list_endpoints:
        for ep in PATROL_ENDPOINTS:
            print(f"  {ep['method']:<5} {ep['path']:<50} auth={ep.get('auth', False)}")
        return 0

    host = args.base_url.split("//")[-1].split("/")[0].split(":")[0]
    if host not in {"localhost", "127.0.0.1"} and not args.allow_remote:
        print(f"[error] 目标 {host} 非 localhost：巡检只面向隔离/本机实例；"
              f"确需远端请加 --allow-remote（禁止指向生产）。", file=sys.stderr)
        return 2
    if args.samples < 1:
        print("[error] --samples 必须 >= 1", file=sys.stderr)
        return 2

    report = patrol(args.base_url, args.token, args.samples, args.timeout)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f"性能巡检（{report['base_url']}，每端点 {args.samples} 次，{report['generated_at']}）")
        for r in report["endpoints"]:
            if r.get("status") == "skipped_no_token":
                print(f"  {r['name']:<22} SKIP（无 token）")
                continue
            print(f"  {r['name']:<22} p50={r['p50_ms']:>8.2f}ms p95={r['p95_ms']:>8.2f}ms "
                  f"err={r['errors']}/{r['samples']} last={r['last_status']}")
        print(f"  口径：{report['slo']}")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUTPUT_DIR / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  留档：{out.relative_to(ROOT)}")

    if report["reachable_endpoints"] == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
