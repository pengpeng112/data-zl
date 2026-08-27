"""A9：并发摄取时版本号唯一键冲突的单次重试助手。

并发场景下两个摄入同时读到相同 max_ver 并各自 +1，后提交方会撞
(query_id/metric_id, version) 唯一键。用 SAVEPOINT（begin_nested）只回滚
版本行插入、重读 max_ver 再试一次；外层事务中已写入的定义行不受影响。
仅处理唯一键冲突（PostgreSQL SQLSTATE 23505 / UniqueViolation），其它
IntegrityError（外键、CHECK 等）原样抛出，不做盲目重试。
"""
from __future__ import annotations

from typing import Callable

from sqlalchemy.exc import IntegrityError


def _is_unique_violation(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    if getattr(orig, "pgcode", None) == "23505":
        return True
    return "uniqueviolation" in type(orig).__name__.lower()


def flush_new_version_with_retry(
    db,
    *,
    build_version: Callable[[int], object],
    current_max_version: Callable[[], int],
) -> tuple[object, int]:
    """插入带自增版本号的新版本行；唯一键撞号时重读 max 重试一次。

    - build_version(next_ver)：构造全新未入会的模型实例（version=next_ver）。
    - current_max_version()：从数据库重读当前最大版本号。
    返回 (版本行, 实际使用的版本号)。
    """
    for attempt in range(2):
        next_ver = int(current_max_version()) + 1
        version = build_version(next_ver)
        nested = db.begin_nested()
        db.add(version)
        try:
            db.flush()
            nested.commit()
            return version, next_ver
        except IntegrityError as exc:
            nested.rollback()
            if attempt == 1 or not _is_unique_violation(exc):
                raise
    raise RuntimeError("unreachable: version retry loop exhausted")
