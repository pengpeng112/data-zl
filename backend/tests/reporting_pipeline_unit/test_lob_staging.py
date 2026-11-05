"""LOB 暂存编码回归（计划C P3，069 会话 2026-11-05）。

对应缺陷：EMR_MEDICAL_RECORD_INFO capture 暂存 JSON 遇到 oracledb 厚模式
LOB 定位器（MED_NOTE 为 CLOB）抛 ContractViolation，多批挂 CAPTURING。
修复：_encode_json_value 增补 LOB 分支——目标列为 CLOB（DBOPER 实证），
默认无损全量读取（clob/blob 标记）；仅病态巨型 LOB 超过安全阀
（_LOB_SAFETY_CAP）才截断标记（clob_trunc/blob_trunc）；解码侧
clob*→str、blob*→bytes。离线单测以伪造 oracledb 模块类型的 LOB 桩验证，
不连 Oracle；安全阀行为用 monkeypatch 小 cap 验证。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline import durable_staging
from app.services.reporting_pipeline.durable_staging import (
    _VALUE_TAG,
    _decode_json_value,
    _encode_json_value,
    encode_json_rows,
)


class _FakeLob:
    """伪造 oracledb.LOB：模块名前缀匹配 + read(amount) 语义。"""

    def __init__(self, payload, *, module="oracledb.dbapi"):
        self._payload = payload
        self.__class__.__module__ = module

    def read(self, amount):
        if isinstance(self._payload, (str, bytes, bytearray)):
            return self._payload[:amount]
        return self._payload


class EncodeLobTests(unittest.TestCase):
    def test_clob_short_roundtrip(self):
        lob = _FakeLob("住院病历摘要文本")
        enc = _encode_json_value(lob)
        self.assertEqual(enc[_VALUE_TAG], "clob")
        self.assertEqual(_decode_json_value(enc), "住院病历摘要文本")

    def test_clob_16k_content_lossless(self):
        # 实测源端最大 16,168 字符：全量读取必须无损
        text = "病" * 16168
        enc = _encode_json_value(_FakeLob(text))
        self.assertEqual(enc[_VALUE_TAG], "clob")
        self.assertEqual(_decode_json_value(enc), text)

    def test_clob_in_row_roundtrip(self):
        enc = _encode_json_value({"MED_NOTE": _FakeLob("abc"), "ID": "1"})
        dec = _decode_json_value(enc)
        self.assertEqual(dec, {"MED_NOTE": "abc", "ID": "1"})

    def test_clob_boundary_exact_4000_not_truncated(self):
        # v2 计划曾按 4000 截断；目标列为 CLOB 后 4000 字符必须完整保留
        enc = _encode_json_value(_FakeLob("B" * 4000))
        self.assertEqual(enc[_VALUE_TAG], "clob")
        self.assertEqual(len(enc["value"]), 4000)

    def test_clob_none_untouched(self):
        enc = _encode_json_value({"MED_NOTE": None, "ID": "1"})
        self.assertEqual(_decode_json_value(enc), {"MED_NOTE": None, "ID": "1"})

    def test_blob_roundtrip(self):
        blob = bytes(range(256)) * 64  # 16384 bytes
        enc = _encode_json_value(_FakeLob(blob))
        self.assertEqual(enc[_VALUE_TAG], "blob")
        dec = _decode_json_value(enc)
        self.assertEqual(dec, blob)
        self.assertIsInstance(dec, bytes)

    def test_blob_short_roundtrip(self):
        blob = b"\x00\x01\x02sanjia"
        enc = _encode_json_value(_FakeLob(blob))
        self.assertEqual(enc[_VALUE_TAG], "blob")
        self.assertEqual(_decode_json_value(enc), blob)

    def test_cx_oracle_module_also_supported(self):
        enc = _encode_json_value(_FakeLob("legacy", module="cx_Oracle"))
        self.assertEqual(enc[_VALUE_TAG], "clob")

    def test_non_lob_readable_object_still_refused(self):
        class FileLike:
            def read(self, amount):
                return "x" * amount

        with self.assertRaises(ContractViolation):
            _encode_json_value(FileLike())

    def test_lob_unsupported_payload_type_refused(self):
        with self.assertRaises(ContractViolation):
            _encode_json_value(_FakeLob(3.14))

    def test_safety_cap_truncates_and_flags(self):
        saved = durable_staging._LOB_SAFETY_CAP
        durable_staging._LOB_SAFETY_CAP = 100
        try:
            enc = _encode_json_value(_FakeLob("C" * 150))
            self.assertEqual(enc[_VALUE_TAG], "clob_trunc")
            self.assertEqual(len(enc["value"]), 100)
            self.assertEqual(_decode_json_value(enc), "C" * 100)
            blob_enc = _encode_json_value(_FakeLob(b"D" * 150))
            self.assertEqual(blob_enc[_VALUE_TAG], "blob_trunc")
            self.assertEqual(_decode_json_value(blob_enc), b"D" * 100)
        finally:
            durable_staging._LOB_SAFETY_CAP = saved

    def test_encode_json_rows_with_clob(self):
        rows = [{"ID": "1", "MED_NOTE": _FakeLob("abc")}]
        payload = encode_json_rows(rows)
        self.assertIn(b'"MED_NOTE"', payload)
        self.assertIn(b"clob", payload)


if __name__ == "__main__":
    unittest.main()
