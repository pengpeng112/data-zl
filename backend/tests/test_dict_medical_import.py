"""临床诊断映射导入服务纯逻辑测试（101号 §5.1）。

不依赖数据库，验证 Excel 解析、校验、灰码处理、多对一和幂等逻辑。
"""
from __future__ import annotations

import pytest

from app.services.dict_medical_import import (
    _normalize_text,
    _row_hash,
    validate_row,
    parse_diagnosis_mapping_excel,
)


class TestNormalizeText:
    def test_fullwidth_space(self):
        assert _normalize_text("\u3000ABC\u3000") == "ABC"

    def test_invisible_chars(self):
        assert _normalize_text("A\u200bB\ufeffC") == "ABC"

    def test_none(self):
        assert _normalize_text(None) is None

    def test_empty(self):
        assert _normalize_text("") is None
        assert _normalize_text("   ") is None


class TestRowHash:
    def test_deterministic(self):
        v = {"hospital_code": "A01", "hospital_name": "测试"}
        assert _row_hash(v) == _row_hash(dict(v))

    def test_different_values(self):
        v1 = {"hospital_code": "A01"}
        v2 = {"hospital_code": "A02"}
        assert _row_hash(v1) != _row_hash(v2)


class TestValidateRow:
    def test_valid_row(self):
        values = {
            "hospital_code": "Y001",
            "hospital_name": "脑梗死",
            "national_clinical_code": "I63.900",
            "national_clinical_name": "脑梗死",
            "insurance_code": "I63.900",
            "insurance_name": "脑梗死",
        }
        result = validate_row(values, set())
        assert result["validation_status"] == "valid"
        assert result["insurance_mapping_status"] == "valid"
        assert result["diff_type"] == "new"

    def test_grey_code(self):
        values = {
            "hospital_code": "Y002",
            "hospital_name": "测试诊断",
            "national_clinical_code": "I63.800",
            "national_clinical_name": "其他脑梗死",
            "insurance_code": "I63.800",
            "insurance_name": None,
        }
        result = validate_row(values, set())
        assert result["insurance_mapping_status"] == "grey"
        assert result["validation_status"] == "warning"

    def test_missing_hospital_code(self):
        values = {"hospital_code": None, "hospital_name": "测试"}
        result = validate_row(values, set())
        assert result["validation_status"] == "error"
        assert "院内编码为空" in result["validation_errors"]

    def test_existing_code_exact_match(self):
        values = {"hospital_code": "Y001", "hospital_name": "脑梗死"}
        result = validate_row(values, {"Y001"})
        assert result["diff_type"] == "exact_match"

    def test_many_to_one_not_error(self):
        """多对一映射（多个院内编码映射到同一医保编码）不报错。"""
        values1 = {
            "hospital_code": "Y001",
            "hospital_name": "脑梗死1",
            "insurance_code": "I63.200",
            "insurance_name": "大脑动脉闭塞",
        }
        values2 = {
            "hospital_code": "Y002",
            "hospital_name": "脑梗死2",
            "insurance_code": "I63.200",
            "insurance_name": "大脑动脉闭塞",
        }
        r1 = validate_row(values1, set())
        r2 = validate_row(values2, set())
        assert r1["validation_status"] == "valid"
        assert r2["validation_status"] == "valid"

    def test_empty_insurance_code(self):
        values = {
            "hospital_code": "Y003",
            "hospital_name": "测试",
            "insurance_code": None,
            "insurance_name": None,
        }
        result = validate_row(values, set())
        assert result["insurance_mapping_status"] == "empty"


class TestParseExcel:
    def _make_xlsx(self, rows: list[list], sheet_name="诊断字典映射") -> bytes:
        import openpyxl
        from io import BytesIO
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name
        for row in rows:
            ws.append(row)
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_two_row_header_35_rows(self):
        """两行表头 + 35 行数据全部识别。"""
        header1 = ["字典属性", "院内疾病编码", "院内疾病名称", "国家临床版2.0编码", "国家临床版2.0名称", "国家医保版2.0编码", "国家医保版2.0名称"]
        header2 = ["（可选）", "（必填）", "（必填）", "（必填）", "（必填）", "（选填）", "（选填）"]
        data_rows = []
        for i in range(35):
            data_rows.append([f"属性{i}", f"Y{i:03d}", f"诊断{i}", f"I63.{i%10}00", f"国标{i}", f"I63.{i%10}00", f"医保{i}"])
        xlsx = self._make_xlsx([header1, header2] + data_rows)
        result = parse_diagnosis_mapping_excel(xlsx, "test.xlsx")
        assert "error" not in result
        assert result["row_count"] == 35
        assert result["sheet"] == "诊断字典映射"

    def test_empty_file_rejected(self):
        xlsx = self._make_xlsx([["字典属性", "院内疾病编码"]])
        result = parse_diagnosis_mapping_excel(xlsx, "empty.xlsx")
        assert result.get("row_count", 0) == 0 or "error" in result

    def test_missing_hospital_code_column(self):
        header = ["字典属性", "名称"]
        xlsx = self._make_xlsx([header, ["", ""], ["a", "b"]])
        result = parse_diagnosis_mapping_excel(xlsx, "bad.xlsx")
        assert "error" in result

    def test_file_sha_deterministic(self):
        header1 = ["院内疾病编码", "院内疾病名称"]
        header2 = ["", ""]
        data = [["Y001", "测试"]]
        xlsx = self._make_xlsx([header1, header2] + data)
        r1 = parse_diagnosis_mapping_excel(xlsx, "a.xlsx")
        r2 = parse_diagnosis_mapping_excel(xlsx, "a.xlsx")
        assert r1["file_sha256"] == r2["file_sha256"]