# r194 S0d: enumerate FastAPI routes with methods, permission codes and risk class.
# Import-only (no lifespan/startup), DB URL forced to isolated test DB, no requests sent.
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "backend"))
os.environ.setdefault("APP_HOSPITAL_LLM_ENABLED", "false")
os.environ.setdefault("APP_DIFY_QUALITY_ENABLED", "false")

from fastapi.routing import APIRoute  # noqa: E402
from app.main import app  # noqa: E402


SOURCE_HINTS = ("probe", "execute", "run", "collect", "push", "sync", "test-connection",
                "preview", "plan", "apply", "import", "export", "dispatch", "simulate")
EXTERNAL_HINTS = ("dify", "llm", "ai/", "notify", "webhook")


def _closure_code(fn):
    try:
        for cell in fn.__closure__ or []:
            v = cell.cell_contents
            if isinstance(v, str):
                return v
    except Exception:
        pass
    return None


def perm_codes(route):
    codes = []
    cands = [getattr(dep, "dependency", None) for dep in route.dependencies]
    dep = getattr(route, "dependant", None)
    if dep is not None:
        cands += [getattr(p, "call", None) for p in (getattr(dep, "dependencies", None) or [])]
    for d in cands:
        if d is not None and getattr(d, "__qualname__", "").startswith("require_permission"):
            code = _closure_code(d)
            if code:
                codes.append(code)
    return codes


def classify(path, method):
    m = method.upper()
    p = path.lower()
    if any(h in p for h in EXTERNAL_HINTS):
        return "external_or_llm"
    if m in ("POST", "PUT", "PATCH", "DELETE"):
        if any(h in p for h in SOURCE_HINTS):
            return "platform_write_or_source_touch"
        return "platform_write"
    if any(h in p for h in SOURCE_HINTS):
        return "source_read_or_plan"
    return "pure_read"


def walk_routes(router):
    for r in getattr(router, "routes", []):
        t = type(r).__name__
        if t == "_IncludedRouter":
            yield from walk_routes(getattr(r, "original_router", None))
        elif isinstance(r, APIRoute):
            yield r


out = []
seen = set()
for r in walk_routes(app):
    for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
        key = (m, r.path)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "method": m,
            "path": r.path,
            "endpoint": r.endpoint.__qualname__,
            "summary": (r.summary or "")[:80],
            "permission_codes": sorted(set(perm_codes(r))),
            "risk_class": classify(r.path, m),
        })

with open(os.path.join(os.path.dirname(__file__), "..", "api_static", "api_inventory.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

by_class = {}
for e in out:
    by_class[e.get("risk_class", "?")] = by_class.get(e.get("risk_class", "?"), 0) + 1
print("total method-path entries:", len(out))
print("by class:", json.dumps(by_class, ensure_ascii=False))
print("with explicit permission codes:", sum(1 for e in out if e.get("permission_codes")))
