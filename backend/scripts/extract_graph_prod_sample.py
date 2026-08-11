"""119 号 S2：提取生产图谱响应（只读，直接调用接口函数，绕过 HTTP 认证层）。

仅输出计数到 stdout；完整响应写入 /tmp/graph_prod_sample.json（仅表级关系字段，
不含 Token/人员信息/凭据）。
"""
import json
import sys

sys.path.insert(0, "/app")

from app.api.v1.graph import diagnostics, graph, options  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        g = graph(
            system_code=None, source_code=None, schema=None, domain=None,
            validation_status=None, confidence="A", keyword=None,
            include_candidates=False, include_dependencies=False, limit=120, db=db,
        )
        o = options(db=db)
        d = diagnostics(db=db)
        out = {
            "graph": g.model_dump(mode="json"),
            "options": o.model_dump(mode="json"),
            "diagnostics": d.model_dump(mode="json"),
        }
        with open("/tmp/graph_prod_sample.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        nodes = out["graph"]["data"]["nodes"]
        edges = out["graph"]["data"]["edges"]
        diag = out["diagnostics"]["data"]
        print(json.dumps({
            "nodes": len(nodes),
            "edges": len(edges),
            "relation_count": diag.get("relation_count"),
            "unresolved_endpoints": diag.get("unresolved_endpoints"),
            "duplicate_business_keys": diag.get("duplicate_business_keys"),
            "orphan_references": diag.get("orphan_references"),
            "healthy": diag.get("healthy"),
            "warnings": diag.get("warnings"),
        }, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
