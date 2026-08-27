"""Fine-grained authorization must cover identity and quality mutations."""

from __future__ import annotations

import ast
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
WRITE_METHODS = {"post", "put", "patch", "delete"}


def _write_route_permissions(path: Path) -> list[tuple[str, str, set[str]]]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    routes: list[tuple[str, str, set[str]]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            method = decorator.func.attr.lower()
            if method not in WRITE_METHODS or not decorator.args:
                continue
            route_path = ast.literal_eval(decorator.args[0])
            permissions = {
                child.args[0].value
                for child in ast.walk(decorator)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "require_permission"
                and child.args
                and isinstance(child.args[0], ast.Constant)
                and isinstance(child.args[0].value, str)
            }
            routes.append((method, route_path, permissions))
    return routes


def test_identity_and_quality_write_routes_have_fine_grained_permissions():
    # 153 B5：dict_medical 全部写端点必须挂 dict.medical.* 端点级权限码。
    # POST /push/export-preview 是携带请求体的只读预览（153 列定的 8 写端点之外），豁免。
    read_only_post_exemptions = {("post", "/push/export-preview")}
    expected = {
        "identity.py": {"identity.sync.run", "identity.local_account.manage"},
        "quality.py": {"asset.quality.rule.create", "asset.quality.rule.execute"},
        "dict_medical_api.py": {
            "dict.medical.edit",
            "dict.medical.plan.create",
            "dict.medical.approve",
            "dict.medical.execute",
            "dict.medical.retry",
            "dict.medical.reconcile",
        },
    }
    for filename, allowed in expected.items():
        routes = _write_route_permissions(BACKEND_DIR / "app" / "api" / "v1" / filename)
        assert routes, f"no write routes discovered in {filename}"
        routes = [(m, p, perms) for m, p, perms in routes if (m, p) not in read_only_post_exemptions]
        missing = [f"{method.upper()} {path}" for method, path, permissions in routes if not permissions]
        invalid = [
            f"{method.upper()} {path}: {sorted(permissions)}"
            for method, path, permissions in routes
            if not permissions.issubset(allowed)
        ]
        assert not missing, f"fine-grained permission missing in {filename}: {missing}"
        assert not invalid, f"unexpected permission code in {filename}: {invalid}"


def test_ai_execution_and_context_routes_permissions():
    """153 B5：AI 真实执行端点挂 ai.sql.execute；只读上下文端点只挂 ai.context.read。"""
    import ast as _ast

    source = (BACKEND_DIR / "app" / "api" / "v1" / "ai.py").read_text(encoding="utf-8-sig")
    tree = _ast.parse(source)

    route_permissions: dict[tuple[str, str], set[str]] = {}
    for node in tree.body:
        if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, _ast.Call) or not isinstance(decorator.func, _ast.Attribute):
                continue
            method = decorator.func.attr.lower()
            if method not in WRITE_METHODS and method != "get":
                continue
            if not decorator.args:
                continue
            try:
                route_path = _ast.literal_eval(decorator.args[0])
            except (ValueError, SyntaxError):
                continue
            permissions = {
                child.args[0].value
                for child in _ast.walk(decorator)
                if isinstance(child, _ast.Call)
                and isinstance(child.func, _ast.Name)
                and child.func.id == "require_permission"
                and child.args
                and isinstance(child.args[0], _ast.Constant)
                and isinstance(child.args[0].value, str)
            }
            route_permissions[(method, route_path)] = permissions

    # 执行类端点（新码）。
    assert route_permissions.get(("post", "/drafts/{draft_id}/execute")) == {"ai.sql.execute"}
    assert route_permissions.get(("post", "/tool-execute")) == {"ai.sql.execute"}
    # 只读上下文端点（既有读码，禁止执行码套读接口）。
    assert route_permissions.get(("get", "/system-context")) == {"ai.context.read"}
    assert route_permissions.get(("post", "/export-context")) == {"ai.context.read"}
    assert route_permissions.get(("post", "/propose-sql")) == {"ai.context.read"}


def test_ai_sql_execute_code_registered_and_granted():
    """153 B5：ai.sql.execute 必须在 RESOURCE_CATALOG 且授予 platform_admin/quality_admin，不授予 ai_user。"""
    from app.api.v1.permissions import RESOURCE_CATALOG, ROLE_DEFAULT_PERMISSIONS

    codes = {item["code"] for item in RESOURCE_CATALOG}
    assert "ai.sql.execute" in codes
    # platform_admin 默认拿全目录；quality_admin 显式授予。
    assert "ai.sql.execute" in ROLE_DEFAULT_PERMISSIONS["platform_admin"] or codes.issubset(
        set(ROLE_DEFAULT_PERMISSIONS["platform_admin"])
    )
    assert "ai.sql.execute" in ROLE_DEFAULT_PERMISSIONS["quality_admin"]
    # 执行码不得授予 ai_user（裁决 #8：锁死 AI 协作角色的直连执行）。
    assert "ai.sql.execute" not in ROLE_DEFAULT_PERMISSIONS["ai_user"]


def test_asset_editor_can_pass_recipe_module_gate():
    source = (BACKEND_DIR / "app" / "main.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    role_required = None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "ROLE_REQUIRED":
            role_required = ast.literal_eval(node.value)
            break
    assert role_required is not None
    assert "asset_editor" in role_required["recipes"]
