#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_openapi_drift.py — OpenAPI 快照漂移检查器（215 号 E8，tools 族）。

背景（round-12 R8）：前端 16 个 API 封装模块的类型全部手写，与后端
OpenAPI 无自动同步，漂移窗口只靠 vitest mock 兜底；仓库无 CI，先做
**本地**快照 diff 工具，未来有 CI 再挂钩。

做什么：
1. 从 FastAPI 应用导出 openapi.json（进程内 ``app.openapi()``，不起服务、
   不连数据库——纯路由/模型定义层）；
2. 与基线快照（默认 ``开发起步包/output_r215/openapi_baseline.json``）比对：
   路径新增/删除、路径下方法(操作)新增/删除/变更、components.schemas
   新增/删除/内容变更，分类输出；
3. 前端 ``frontend/src/api/*.ts`` 手写类型漂移：只**报告**前端引用而后端
   OpenAPI 已不存在的路径（模板串 ``${x}`` 归一为 ``{param}``），不自动改。

不做什么：不改任何代码/类型；不写基线以外的文件；不做 CI 挂钩（R11 全仓
无 CI，另案）。

用法（需能 import backend 依赖，用 backend venv）：
  backend/.venv/Scripts/python.exe tools/check_openapi_drift.py               # 文本报告
  backend/.venv/Scripts/python.exe tools/check_openapi_drift.py --json        # 机器可读
  backend/.venv/Scripts/python.exe tools/check_openapi_drift.py --update-baseline  # 重建基线
退出码：0=与基线一致（或仅 --update-baseline 成功），1=发现漂移，2=环境/用法错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
DEFAULT_BASELINE = ROOT / "开发起步包" / "output_r215" / "openapi_baseline.json"
FRONTEND_API_DIR = ROOT / "frontend" / "src" / "api"

# 前端模板字面量归一：`/api/v1/x/${id}/y` -> /api/v1/x/{param}/y
TEMPLATE_ARG_RE = re.compile(r"\$\{[^}]+\}")
# 提取引号串与模板串里的 /api/v1/... 路径
PATH_LITERAL_RE = re.compile(r"""["'`](/api/v1/[A-Za-z0-9_\-/${}.]+)["'`]""")


def export_openapi() -> dict:
    """进程内导出 OpenAPI 文档（不连库；导入失败给出明确指引）。"""
    import os

    # Settings 要求 APP_DB_URL；导出 OpenAPI 只走路由/模型定义层，不建连接，
    # 给哑值即可（ psycopg URL 格式合法但永不连接）。
    os.environ.setdefault("APP_DB_URL", "postgresql+psycopg://openapi-export:nopw@127.0.0.1:1/none")
    sys.path.insert(0, str(BACKEND_DIR))
    try:
        from app.main import app  # noqa: WPS433（工具场景的受控局部导入）
    except Exception as exc:  # pragma: no cover - 环境缺失分支
        raise RuntimeError(
            f"导入 FastAPI 应用失败（{type(exc).__name__}: {exc}）。"
            "请用 backend/.venv/Scripts/python.exe 运行本工具。"
        ) from exc
    try:
        return app.openapi()
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"app.openapi() 导出失败: {type(exc).__name__}: {exc}") from exc


def _digest(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _methods(doc: dict, path: str) -> dict[str, str]:
    out = {}
    for method, op in (doc.get("paths", {}).get(path) or {}).items():
        if method in {"get", "post", "put", "patch", "delete"}:
            out[method] = _digest(op)
    return out


def diff_against_baseline(current: dict, baseline: dict) -> dict:
    """分类输出：paths / operations / schemas 三层的新增、删除、变更。"""
    cur_paths = set(current.get("paths", {}))
    base_paths = set(baseline.get("paths", {}))
    added_paths = sorted(cur_paths - base_paths)
    removed_paths = sorted(base_paths - cur_paths)

    changed_ops: list[dict] = []
    for path in sorted(cur_paths & base_paths):
        cur_m, base_m = _methods(current, path), _methods(baseline, path)
        for m in sorted(set(cur_m) - set(base_m)):
            changed_ops.append({"path": path, "method": m, "change": "added"})
        for m in sorted(set(base_m) - set(cur_m)):
            changed_ops.append({"path": path, "method": m, "change": "removed"})
        for m in sorted(set(cur_m) & set(base_m)):
            if cur_m[m] != base_m[m]:
                changed_ops.append({"path": path, "method": m, "change": "modified"})

    cur_schemas = current.get("components", {}).get("schemas", {})
    base_schemas = baseline.get("components", {}).get("schemas", {})
    added_schemas = sorted(set(cur_schemas) - set(base_schemas))
    removed_schemas = sorted(set(base_schemas) - set(cur_schemas))
    changed_schemas = sorted(
        k for k in set(cur_schemas) & set(base_schemas)
        if _digest(cur_schemas[k]) != _digest(base_schemas[k])
    )

    return {
        "paths": {"added": added_paths, "removed": removed_paths},
        "operations": changed_ops,
        "schemas": {"added": added_schemas, "removed": removed_schemas, "modified": changed_schemas},
        "totals": {
            "paths_current": len(cur_paths),
            "paths_baseline": len(base_paths),
            "schemas_current": len(cur_schemas),
        },
        "has_drift": bool(
            added_paths or removed_paths or changed_ops
            or added_schemas or removed_schemas or changed_schemas
        ),
    }


def frontend_api_drift(openapi_paths: set[str]) -> dict:
    """报告（不改码）：前端 src/api/*.ts 引用而后端已无的路径；以及反向未引用清单。"""
    referenced: dict[str, list[str]] = {}
    for ts in sorted(FRONTEND_API_DIR.glob("*.ts")):
        text = ts.read_text(encoding="utf-8", errors="replace")
        for m in PATH_LITERAL_RE.finditer(text):
            raw = m.group(1)
            normalized = TEMPLATE_ARG_RE.sub("{param}", raw)
            normalized = re.sub(r"\{param\}(/\{param\})+$", "/{param}", normalized)
            referenced.setdefault(normalized, []).append(ts.name)

    frontend_only = sorted(
        p for p in referenced
        if p not in openapi_paths and not any(
            p.startswith(prefix) for prefix in ("/api/v1/health",)  # health 可能不经 openapi 注册
        )
    )
    unreferenced_backend = sorted(openapi_paths - set(referenced))
    return {
        "frontend_only_paths": [
            {"path": p, "referenced_by": sorted(set(referenced[p]))} for p in frontend_only
        ],
        "backend_paths_not_referenced_by_api_modules": unreferenced_backend,
        "scanned_modules": len(list(FRONTEND_API_DIR.glob("*.ts"))),
    }


def build_report(current: dict, baseline: dict | None, baseline_path: Path) -> dict:
    try:
        baseline_label = str(baseline_path.relative_to(ROOT))
    except ValueError:  # 基线在仓库外（如临时路径）时退回原样展示
        baseline_label = str(baseline_path)
    if baseline is None:
        diff = {"has_drift": None, "note": f"基线不存在: {baseline_path}（先 --update-baseline）"}
    else:
        diff = diff_against_baseline(current, baseline)
    fe = frontend_api_drift(set(current.get("paths", {})))
    return {
        "tool": "check_openapi_drift",
        "baseline_path": baseline_label,
        "openapi_version": current.get("openapi"),
        "diff": diff,
        "frontend_type_drift": fe,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenAPI 快照漂移检查（215 E8）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    parser.add_argument("--update-baseline", action="store_true",
                        help="用当前 openapi.json 重建基线（有意变更后使用）")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="基线文件路径")
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline)
    try:
        current = export_openapi()
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    if args.update_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
        )
        msg = (f"基线已重建: {baseline_path}（paths={len(current.get('paths', {}))}, "
               f"schemas={len(current.get('components', {}).get('schemas', {}))}）")
        if args.json:
            print(json.dumps({"updated": True, "baseline": str(baseline_path),
                              "paths": len(current.get("paths", {}))}, ensure_ascii=False))
        else:
            print(f"[baseline] {msg}")
        return 0

    baseline = None
    if baseline_path.exists():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[error] 基线文件不是合法 JSON: {exc}", file=sys.stderr)
            return 2

    report = build_report(current, baseline, baseline_path)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        diff = report["diff"]
        print(f"OpenAPI 快照漂移检查（基线 {report['baseline_path']}）")
        if diff.get("has_drift") is None:
            print(f"  [warn] {diff['note']}")
        elif diff["has_drift"]:
            p, o, s = diff["paths"], diff["operations"], diff["schemas"]
            print(f"  [diff] 路径 +{len(p['added'])}/-{len(p['removed'])}")
            for x in p["added"]:
                print(f"    + {x}")
            for x in p["removed"]:
                print(f"    - {x}")
            print(f"  [diff] 操作变更 {len(o)} 项")
            for x in o[:30]:
                print(f"    {x['change']:>9} {x['method'].upper():>6} {x['path']}")
            if len(o) > 30:
                print(f"    … 其余 {len(o) - 30} 项略（--json 看全量）")
            print(f"  [diff] Schema +{len(s['added'])}/-{len(s['removed'])}/~{len(s['modified'])}")
        else:
            print("  结果：与基线一致（无路径/操作/schema 漂移）")
        fe = report["frontend_type_drift"]
        print(f"  [frontend] 扫描 {fe['scanned_modules']} 个 api 模块；"
              f"前端引用而后端不存在的路径 {len(fe['frontend_only_paths'])} 个（仅报告）")
        for x in fe["frontend_only_paths"][:20]:
            print(f"    ? {x['path']}  <- {', '.join(x['referenced_by'])}")
        print(f"  [frontend] 后端存在而 api 模块未引用的路径 {len(fe['backend_paths_not_referenced_by_api_modules'])} 个（信息项）")

    # 前端漂移只报告不改变退出码（契约：仅报告不自动改）；退出码只看基线 diff
    has_drift = report["diff"].get("has_drift")
    return 1 if has_drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
