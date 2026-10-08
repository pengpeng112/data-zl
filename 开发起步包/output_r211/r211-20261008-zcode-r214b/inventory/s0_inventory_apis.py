# -*- coding: utf-8 -*-
"""209 S0.7: 盘点 FastAPI 当前全部路由（方法/path/operationId），作为 API 覆盖率分母。
app.include_router 为 lazy 包装（_IncludedRouter 无 path），app.routes 不可直接枚举；
权威来源改为 app.openapi() 的 paths（FastAPI 生成 OpenAPI 时解析全部注册路由）。
只 import app 不发请求、不连库（假 URL 仅过 Settings/db_guard 门禁，端口1不可达）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "backend"))

from app.main import app  # noqa: E402

spec = app.openapi()
paths = spec.get("paths", {})
rows = []
collisions = []
for p in sorted(paths):
    for m, op in sorted(paths[p].items()):
        if m not in ("get", "post", "put", "patch", "delete", "head", "options"):
            continue  # path-level parameters 等非方法键
        rows.append({
            "method": m.upper(),
            "path": p,
            "operation_id": op.get("operationId", ""),
            "summary": op.get("summary", ""),
        })

# path 级静态段冲突粗查：同一前缀下 /export 与 /{id} 顺序问题在 S5 B01 用真实请求详测
path_count = len(paths)
op_count = len(rows)
out = {
    "source": "app.openapi() paths (authoritative; include_router is lazy-wrapped)",
    "api_path_count": path_count,
    "api_operation_count": op_count,
    "routes": rows,
}
print(json.dumps(out, ensure_ascii=False, indent=1))
