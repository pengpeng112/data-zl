# -*- coding: utf-8 -*-
"""R212 O01 隔离短负载：固定合成数据（重种后的隔离库）、本地后端 :8000。

- 逐接口：1并发基线（20 req）→ 5并发短测（50 req），记录 p50/p95/错误率。
- 无冻结 SLO：只报告实测值与零错误断言，不宣称性能达标（212 §10 O01）。
- 令牌经环境变量 R212_TOKEN 传入；不写任何凭据到文件。

用法：backend/.venv/Scripts/python.exe o01_short_load.py
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
HERE = Path(__file__).parent
OUT = HERE / "performance" / "o01_results.json"

ENDPOINTS = [
    ("GET", "/api/v1/systems"),
    ("GET", "/api/v1/tables?page=1&page_size=20"),
    ("GET", "/api/v1/value-domains?page=1&page_size=20"),
    ("GET", "/api/v1/quality-issues?page=1&page_size=20"),
    ("GET", "/api/v1/quality-observations?page=1&page_size=20"),
    ("GET", "/api/v1/ai/system-context?system_code=HIS&max_tables=10"),
    ("POST", "/api/v1/ai/context/resolve"),
]

POST_BODY = {"question": "r212 o01 负载探针：患者住院主表是哪张", "top_k": 5}


def one(client, method, path, token):
    t0 = time.perf_counter()
    if method == "GET":
        r = client.get(BASE + path, headers={"Authorization": f"Bearer {token}"})
    else:
        r = client.post(BASE + path, headers={"Authorization": f"Bearer {token}"}, json=POST_BODY)
    ms = (time.perf_counter() - t0) * 1000
    return ms, r.status_code


def run_round(client, method, path, token, n, workers):
    lat: list[float] = []
    codes: list[int] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, client, method, path, token) for _ in range(n)]
        for f in futs:
            ms, code = f.result()
            lat.append(ms)
            codes.append(code)
    lat.sort()
    return {
        "n": n, "workers": workers,
        "p50_ms": round(statistics.median(lat), 1),
        "p95_ms": round(lat[int(len(lat) * 0.95) - 1], 1),
        "max_ms": round(lat[-1], 1),
        "error_count": sum(1 for c in codes if c >= 500),
        "status_codes": sorted(set(codes)),
    }


def main():
    token = os.environ.get("R212_TOKEN", "")
    if not token:
        raise SystemExit("缺少 R212_TOKEN")
    results = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "endpoints": []}
    with httpx.Client(timeout=30.0) as client:
        for method, path in ENDPOINTS:
            entry = {"method": method, "path": path}
            try:
                entry["baseline_1c"] = run_round(client, method, path, token, 20, 1)
                entry["load_5c"] = run_round(client, method, path, token, 50, 5)
            except Exception as e:  # noqa: BLE001
                entry["error"] = repr(e)[:200]
            results["endpoints"].append(entry)
            print(json.dumps(entry, ensure_ascii=False))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    total_err = sum(e.get("load_5c", {}).get("error_count", 0) + e.get("baseline_1c", {}).get("error_count", 0)
                    for e in results["endpoints"])
    print(f"5xx total = {total_err}; results -> {OUT}")


if __name__ == "__main__":
    main()
