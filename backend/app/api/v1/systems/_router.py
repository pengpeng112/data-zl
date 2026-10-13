"""215 E11：systems 域共享 router（路径前缀与原 systems.py 一致）。"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["systems"])
