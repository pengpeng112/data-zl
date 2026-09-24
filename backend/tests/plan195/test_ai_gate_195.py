"""195 缺陷1：/api/v1/ai 粗角色门禁不拦 ai.context.read 持有者。

纯逻辑：直接调用 app.main._enforce_rbac，不触数据库、不发 HTTP。
豁免清单只覆盖自带 require_permission("ai.context.read") 路由级依赖的路径，
其余 /api/v1/ai* 路由（含 ai-accuracy、未挂码路由）仍受粗门禁保护。
"""
from __future__ import annotations

import ast
from pathlib import Path

AI_FILE = Path(__file__).resolve().parents[2] / "app" / "api" / "v1" / "ai.py"

EXEMPT_EXACT = {
    "/api/v1/ai/propose-sql",
    "/api/v1/ai/export-context",
    "/api/v1/ai/system-context",
    "/api/v1/ai/ai-sql/generate",
    "/api/v1/ai/ai-sql/history",
    "/api/v1/ai/tool-execute",
}
EXEMPT_PREFIXES = ("/api/v1/ai/context/",)


def _enforce(path, method="GET", roles=("ai_user",)):
    from app.main import _enforce_rbac

    return _enforce_rbac(path, method, list(roles))


def test_exempted_context_endpoints_reachable_for_ai_user():
    """195 缺陷1 回归：仅持 ai_user（默认含 ai.context.read）的角色可到达
    AI 上下文端点——此前被 ai 粗前缀门禁整体拦截（交集唯一=platform_admin）。"""
    for path in EXEMPT_EXACT:
        assert _enforce(path) is None, path
        assert _enforce(path, "POST") is None, path
    # /context/{context_id} 带路径参数，走前缀豁免
    assert _enforce("/api/v1/ai/context/abc-123") is None
    assert _enforce("/api/v1/ai/context/resolve", "POST") is None


def test_unarmed_ai_routes_still_coarse_gated():
    """未挂端点权限码的 ai 路由不豁免：ai_user 仍被粗门禁拦截（保持现状，
    防止豁免清单扩大成无保护裸奔）。"""
    for path, method in [
        ("/api/v1/ai/sessions", "POST"),
        ("/api/v1/ai/sessions", "GET"),
        ("/api/v1/ai/tool-call", "POST"),
        ("/api/v1/ai/tool-calls", "GET"),
        ("/api/v1/ai/drafts", "GET"),
        ("/api/v1/ai/mcp/catalog", "GET"),
        ("/api/v1/ai/sql-risk-scan", "POST"),
    ]:
        assert _enforce(path, method) is not None, (path, method)


def test_ai_accuracy_prefix_unaffected():
    """ai-accuracy 前缀不因 '/api/v1/ai' startswith 被连带豁免。"""
    assert _enforce("/api/v1/ai-accuracy/feedback") is not None
    assert _enforce("/api/v1/ai-accuracy/dashboard") is not None


def test_platform_admin_still_passes_coarse_gate():
    assert _enforce("/api/v1/ai/sessions", "POST", roles=("platform_admin",)) is None
    assert _enforce("/api/v1/ai/drafts", "GET", roles=("platform_admin",)) is None
    assert _enforce("/api/v1/ai-accuracy/feedback", "GET", roles=("platform_admin",)) is None


def test_quality_admin_unchanged_on_unarmed_routes():
    """quality_admin 在粗门禁路由上的现状可达性不变（豁免只作用于自带码端点）。"""
    assert _enforce("/api/v1/ai/sessions", "GET", roles=("quality_admin",)) is None


def test_exempted_paths_all_carry_route_permission_code():
    """守卫：豁免清单里每条 ai.py 路径都必须真的挂了
    require_permission("ai.context.read")——新增未挂码路径进清单会被抓出。"""
    tree = ast.parse(AI_FILE.read_text(encoding="utf-8-sig"))
    coded: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            call = dec if isinstance(dec, ast.Call) else None
            if call is None or not (getattr(call.func, "attr", "") or getattr(call.func, "id", "")):
                continue
            attrs = []
            for kw in call.keywords:
                if kw.arg == "dependencies":
                    deps = kw.value
                    deps = deps.elts if isinstance(deps, ast.List) else [deps]
                    for d in deps:
                        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "Depends":
                            inner = d.args[0] if d.args else None
                            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "require_permission":
                                code = inner.args[0] if inner.args else None
                                if isinstance(code, ast.Constant):
                                    attrs.append(code.value)
            if not attrs:
                # 装饰器行内 dependencies（单行写法）
                for sub in ast.walk(dec):
                    if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                            and sub.func.id == "require_permission" and sub.args):
                        arg = sub.args[0]
                        if isinstance(arg, ast.Constant):
                            attrs.append(arg.value)
            path = None
            if call.args:
                first = call.args[0]
                if isinstance(first, ast.Constant):
                    path = first.value
            if path and "ai.context.read" in attrs:
                coded.add(f"/api/v1/ai{path}")
    for path in EXEMPT_EXACT:
        assert path in coded, f"豁免路径未挂 ai.context.read：{path}"


def test_context_prefix_only_contains_coded_routes():
    """守卫：/api/v1/ai/context/ 前缀下所有 ai.py 路由都挂 ai.context.read。"""
    tree = ast.parse(AI_FILE.read_text(encoding="utf-8-sig"))
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            call = dec if isinstance(dec, ast.Call) else None
            if call is None or not call.args:
                continue
            first = call.args[0]
            if not (isinstance(first, ast.Constant) and first.value.startswith("/context")):
                continue
            has_code = any(
                (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                 and sub.func.id == "require_permission" and sub.args
                 and isinstance(sub.args[0], ast.Constant)
                 and sub.args[0].value == "ai.context.read")
                for sub in ast.walk(dec)
            )
            found[f"/api/v1/ai{first.value}"] = has_code
    assert found, "未在 ai.py 解析到 /context* 路由"
    for path, has_code in found.items():
        assert has_code, f"{path} 未挂 ai.context.read，不能落在前缀豁免内"
