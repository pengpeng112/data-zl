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
    expected = {
        "identity.py": {"identity.sync.run"},
        "quality.py": {"asset.quality.rule.create", "asset.quality.rule.execute"},
    }
    for filename, allowed in expected.items():
        routes = _write_route_permissions(BACKEND_DIR / "app" / "api" / "v1" / filename)
        assert routes, f"no write routes discovered in {filename}"
        missing = [f"{method.upper()} {path}" for method, path, permissions in routes if not permissions]
        invalid = [
            f"{method.upper()} {path}: {sorted(permissions)}"
            for method, path, permissions in routes
            if not permissions.issubset(allowed)
        ]
        assert not missing, f"fine-grained permission missing in {filename}: {missing}"
        assert not invalid, f"unexpected permission code in {filename}: {invalid}"


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
