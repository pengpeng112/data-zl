"""r194 收尾会话：清空隔离库全部表后重跑 194 合成种子（复刻 194 首轮条件）。

用法（仓库根）：
  source tools/dev_env.sh >/dev/null 2>&1
  cd backend && PYTHONPATH=. ./.venv/Scripts/python.exe "../开发起步包/output_r194/r194-20260918-wrapup/reseed_clean.py"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

SEED = Path(__file__).resolve().parents[1] / "r194-20260917-204356" / "scripts" / "seed_r194_data.py"


def main() -> int:
    url = os.environ["APP_TEST_DB_URL"]
    if "test" not in url.lower():
        print("[reseed] 拒绝：APP_TEST_DB_URL 未标识测试库")
        return 2
    eng = create_engine(url)
    with eng.begin() as c:
        rows = c.execute(text(
            "select tablename from pg_tables where schemaname='asset'"
        )).fetchall()
        tables = [r[0] for r in rows]
        if tables:
            joined = ",".join(f'"asset"."{t}"' for t in tables)
            c.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))
    print(f"[reseed] 已清空 asset schema {len(tables)} 表")
    # 运行既有种子脚本（同进程，显式调用 main，复用其全部段落）
    sys.path.insert(0, str(SEED.parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location("seed_r194_data", SEED)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    rc = mod.main()
    print(f"[reseed] 种子脚本返回 {rc}（以上为其输出）")
    return int(rc or 0)


if __name__ == "__main__":
    raise SystemExit(main())
