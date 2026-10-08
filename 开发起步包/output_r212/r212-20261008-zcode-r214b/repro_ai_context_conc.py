# -*- coding: utf-8 -*-
"""R212 缺陷定位：ai/context/resolve 5并发6×500 的根因复现。
直接以5线程各持独立Session调用 build_context_snapshot（同参数），打印真实异常链。
"""
from __future__ import annotations

import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))

from app.core.db import SessionLocal  # noqa: E402
from app.services.ai_context_builder import build_context_snapshot  # noqa: E402


def build_once(i: int) -> tuple[int, str]:
    db = SessionLocal()
    try:
        doc = build_context_snapshot(
            db,
            question_summary="r212 o01 负载探针：患者住院主表是哪张",
            max_objects=5,
            include_sql=False,
            created_by="r212-repro",
        )
        db.commit()
        return i, f"OK sha={doc.get('content_sha256', doc.get('sha256', '?'))[:12]}"
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        chain = []
        e = exc
        while e is not None:
            chain.append(f"{type(e).__name__}: {str(e)[:160]}")
            e = e.__cause__ or e.__context__
        return i, "FAIL <- " + " | caused by: ".join(chain[:3])
    finally:
        db.close()


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=5) as ex:
        for i, msg in ex.map(build_once, range(5)):
            print(f"[{i}] {msg}")
