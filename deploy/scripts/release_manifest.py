"""108 号 P0-03：生成发布 manifest（Git SHA / backend image / frontend build ID / Alembic head / 构建时间）。

用法（后端目录）：
    python deploy/scripts/release_manifest.py --backend-dir backend --frontend-dist frontend/dist \
        --backend-image data-asset:<tag> --out release-manifest.json

输出 JSON（不含任何秘密）：
{
  "git_sha": "...",
  "backend_image": "data-asset:...",
  "frontend_build_id": "<dist 指纹>",
  "alembic_head": "...",
  "built_at": "2026-08-02T09:00:00+08:00",
  "backend_sha256": { "app/api/v1/graph.py": "..." },
  "frontend_index_sha256": "..."
}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_sha(repo: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo), capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _alembic_head(backend_dir: Path, python: str) -> str:
    try:
        out = subprocess.run(
            [python, "-m", "alembic", "heads"],
            cwd=str(backend_dir), capture_output=True, text=True, timeout=60,
        )
        for line in out.stdout.splitlines():
            if "(head)" in line:
                return line.split("(")[0].strip()
        return out.stdout.strip()
    except Exception:
        return ""


def _frontend_build_id(dist: Path) -> str:
    """前端构建指纹：对 dist/index.html 与 main js/css 做稳定哈希（不含内容敏感信息）。"""
    index = dist / "index.html"
    if not index.exists():
        return ""
    files = sorted(
        p for p in dist.rglob("*")
        if p.is_file() and p.suffix in {".js", ".css", ".html"}
    )
    h = hashlib.sha256()
    for p in files:
        rel = p.relative_to(dist)
        h.update(str(rel).encode("utf-8"))
        h.update(_sha256(p).encode("utf-8"))
    return h.hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 108 号发布 manifest")
    parser.add_argument("--backend-dir", required=True, help="backend 目录")
    parser.add_argument("--frontend-dist", required=True, help="frontend/dist 目录")
    parser.add_argument("--backend-image", default="", help="后端镜像标签，如 data-asset:20260802-108")
    parser.add_argument("--python", default=sys.executable, help="python 可执行路径")
    parser.add_argument("--out", required=True, help="manifest 输出路径")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    backend_dir = Path(args.backend_dir)
    dist = Path(args.frontend_dist)

    graph_py = backend_dir / "app" / "api" / "v1" / "graph.py"
    schema_graph_py = backend_dir / "app" / "schemas" / "graph.py"

    manifest = {
        "git_sha": _git_sha(repo),
        "backend_image": args.backend_image,
        "frontend_build_id": _frontend_build_id(dist),
        "alembic_head": _alembic_head(backend_dir, args.python),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "backend_sha256": {
            "app/api/v1/graph.py": _sha256(graph_py),
            "app/schemas/graph.py": _sha256(schema_graph_py),
        },
        "frontend_index_sha256": _sha256(dist / "index.html") if (dist / "index.html").exists() else "",
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
