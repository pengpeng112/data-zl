"""回读类型规整：CHAR/VARCHAR/Decimal/时间契约（比较规整不改写入原值）。

对应《回读类型规整契约.json》与计划 §6.2.1：
- 仅已核 CHAR/NCHAR 按填充规则去右侧空格；VARCHAR/正文/路径保留原有空白，
  不统一 rstrip（不照搬 gap_exec 的全字符串 rstrip）。
- 数值用 int/Decimal 精确比较（120 与 120.00 值等价）；禁止经 float、禁止
  任意容差（不照搬 gap_exec 的 float 转换——大整数会误判相等）。
- DATE 秒与 TIMESTAMP 分数秒不静默归一；动态 SYSTEM_TIME/查询时刻从业务
  hash 排除。
- 内容指纹按逻辑类型编码：CLOB 全文、Unicode 按 UTF-8 字节、Decimal 保标度
  语义、二进制 hex；hash 不经 float 或粗糙 TO_CHAR 规范化。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

CHAR_LIKE = ("CHAR", "NCHAR")
TEXT_PRESERVE = ("VARCHAR", "VARCHAR2", "NVARCHAR", "NVARCHAR2", "CLOB", "NCLOB", "TEXT", "PATH")
NUMERIC_EXACT = ("NUMBER", "INT", "INTEGER", "DECIMAL", "NUMERIC")
TIME_LIKE = ("DATE", "TIMESTAMP")


class FloatComparisonRefused(TypeError):
    """声明精确数值却拿到 float：拒绝以 float 比对精确数。"""


@dataclass(frozen=True)
class ColumnMeta:
    name: str
    logical_type: str  # CHAR/NCHAR/VARCHAR/CLOB/NUMBER/INT/DATE/TIMESTAMP/BINARY
    char_length: int | None = None  # 语义长度（字节或字符，按 declared_semantics）
    byte_semantics: bool = True  # True=按字节（Oracle 默认），False=按字符
    precision: int | None = None
    scale: int | None = None
    dynamic_query_time: bool = False  # 查询时刻/回传标记类，业务 hash 排除


def normalize_for_comparison(value, meta: ColumnMeta):
    """比较规整：只对已核 CHAR 族去右填充；其余类型保原值。"""
    if value is None:
        return None
    if meta.logical_type in CHAR_LIKE and isinstance(value, str):
        return value.rstrip(" ")
    if meta.logical_type in NUMERIC_EXACT and isinstance(value, (int, str)) and not isinstance(value, bool):
        if isinstance(value, str):
            try:
                return Decimal(value)
            except InvalidOperation:
                return value  # 交给类型校验报错，不在此伪造
        return value
    return value


def values_equal(a, b, meta: ColumnMeta) -> bool:
    """精确等值：Decimal/Int 不经 float；DATE 与 TIMESTAMP 分数秒不归一。"""
    na, nb = normalize_for_comparison(a, meta), normalize_for_comparison(b, meta)
    if isinstance(na, float) or isinstance(nb, float):
        if meta.logical_type in NUMERIC_EXACT:
            raise FloatComparisonRefused(
                f"列 {meta.name} 声明 {meta.logical_type} 但出现 float 操作数，"
                "拒绝以 float 比对精确数"
            )
    if isinstance(na, (datetime, date)) or isinstance(nb, (datetime, date)):
        # DATE(秒) 与 TIMESTAMP(分数秒) 语义不同：不归一，直接比
        return na == nb
    if isinstance(na, Decimal) or isinstance(nb, Decimal):
        try:
            return Decimal(str(na)) == Decimal(str(nb))  # 120 == 120.00
        except InvalidOperation:
            return False
    if isinstance(na, str) and isinstance(nb, str) and meta.logical_type in CHAR_LIKE:
        return na.rstrip(" ") == nb.rstrip(" ")
    return na == nb


# Oracle 库字符集名 → Python 编码名（BYTE 长度按库字符集计）
ORACLE_CHARSET_CODECS = {
    "ZHS16GBK": "gbk",
    "ZHS16CGB231280": "gbk",
    "ZHS32GB18030": "gb18030",
    "AL32UTF8": "utf-8",
    "UTF8": "utf-8",
    "WE8ISO8859P1": "latin-1",
    "ZHT16BIG5": "big5",
    "JA16EUC": "euc_jp",
}


def byte_length(value, charset: str = "utf-8") -> int:
    """按目标库字符集的字节长度（不是字符数）：超长判断按字节语义。

    Oracle VARCHAR2(n BYTE) 的 n 以库字符集计（如 ZHS16GBK 中文 2 字节）；
    值含目标字符集不可编码字符时回退 UTF-8 长度（该值插入本会失败，
    按超长隔离是安全方向）。
    """
    if value is None:
        return 0
    text = value if isinstance(value, str) else str(value)
    codec = ORACLE_CHARSET_CODECS.get((charset or "").upper(), charset or "utf-8")
    if codec.lower() not in ("utf-8", "utf8"):
        try:
            return len(text.encode(codec))
        except (UnicodeEncodeError, LookupError):
            pass
    return len(text.encode("utf-8"))


def _encode_for_hash(value, meta: ColumnMeta) -> bytes:
    """按逻辑类型编码哈希输入：保证 CLOB/Unicode/Decimal/时间精度不丢。"""
    if value is None:
        return b"\x00N"
    if meta.logical_type in NUMERIC_EXACT:
        if isinstance(value, float):
            raise FloatComparisonRefused(
                f"列 {meta.name} 精确数值不得以 float 进 hash"
            )
        dec = value if isinstance(value, Decimal) else Decimal(str(value))
        return b"\x00D" + str(dec.normalize()).encode("ascii")
    if meta.logical_type in TIME_LIKE and isinstance(value, (datetime, date)):
        # 保精度：datetime isoformat 含微秒；date 无时间成分
        return b"\x00T" + value.isoformat(sep=" ").encode("utf-8")
    if isinstance(value, bytes):
        return b"\x00B" + value.hex().encode("ascii")
    if isinstance(value, str):
        # 文本按 UTF-8 字节：Unicode 不丢、空白保留（VARCHAR/CLOB 族）
        if meta.logical_type in CHAR_LIKE:
            value = value.rstrip(" ")
        return b"\x00S" + value.encode("utf-8")
    return b"\x00O" + repr(value).encode("utf-8")


def content_fingerprint(
    row: Mapping,
    metas: Sequence[ColumnMeta],
    *,
    exclude_dynamic: bool = True,
) -> str:
    """行内容指纹：真实业务列参与，查询时刻/运行ID/重传标记排除。"""
    hasher = hashlib.sha256()
    for meta in metas:
        if exclude_dynamic and meta.dynamic_query_time:
            continue
        hasher.update(meta.name.encode("utf-8"))
        hasher.update(b"=")
        hasher.update(_encode_for_hash(row.get(meta.name), meta))
        hasher.update(b"\x1f")
    return hasher.hexdigest()


def row_diff(
    source_row: Mapping,
    target_row: Mapping,
    metas: Sequence[ColumnMeta],
) -> list[dict]:
    """逐列差异：先规整后比较；返回差异列清单（不含动态列）。"""
    diffs: list[dict] = []
    for meta in metas:
        if meta.dynamic_query_time:
            continue
        a, b = source_row.get(meta.name), target_row.get(meta.name)
        if not values_equal(a, b, meta):
            diffs.append(
                {
                    "column": meta.name,
                    "kind": "VALUE_DIFF",
                    "source_normalized": _safe_repr(normalize_for_comparison(a, meta)),
                    "target_normalized": _safe_repr(normalize_for_comparison(b, meta)),
                }
            )
    return diffs


def _safe_repr(value) -> str:
    if isinstance(value, bytes):
        return f"bytes[{len(value)}]"
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ")
    return repr(value)[:120]
