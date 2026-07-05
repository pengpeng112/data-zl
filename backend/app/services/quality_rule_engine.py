"""质控规则执行引擎——分发 metadata_only/sql_template 规则"""

import re
from sqlalchemy.orm import Session

from ..models.quality import QualityFinding, QualityRule

FORBIDDEN_SQL = {
    "INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "CALL", "EXEC", "EXECUTE",
}
BIG_TABLES = {"HIS.LAB_RESULT", "INP_BILL_DETAIL", "ORDERS", "HIS.MEDREC"}


def validate_sql_safety(sql: str, db_type: str = "oracle") -> dict:
    """校验 SQL 是否只读安全，返回 {valid: bool, errors: [str], warnings: [str]}"""
    errors = []
    warnings = []
    upper = sql.upper().strip()

    # 检查多语句
    if ";" in sql.rstrip(";"):
        errors.append("禁止多语句")

    # 检查禁止关键字
    for kw in FORBIDDEN_SQL:
        pattern = rf"\b{kw}\b"
        if re.search(pattern, upper):
            errors.append(f"禁止关键字: {kw}")

    # 必须是 SELECT 开头
    first_word = upper.split()[0] if upper.split() else ""
    if first_word not in ("SELECT", "WITH"):
        errors.append(f"只允许 SELECT 或 WITH SELECT，当前: {first_word}")

    # Oracle 11g 不允许 FETCH FIRST
    if db_type == "oracle" and "FETCH FIRST" in upper:
        errors.append("Oracle 11g 不支持 FETCH FIRST，请使用 ROWNUM <= N")

    # 大表全扫警告
    for bt in BIG_TABLES:
        if bt.upper() in upper:
            if "ROWNUM" not in upper and "LIMIT" not in upper and "WHERE" not in upper:
                warnings.append(f"大表 {bt} 缺少限定条件，有全扫风险")

    # 无条件 SELECT 警告
    if first_word == "SELECT" and "WHERE" not in upper and "LIMIT" not in upper and "ROWNUM" not in upper:
        if "JOIN" not in upper and "(" not in upper:
            warnings.append("SELECT 缺少 WHERE/LIMIT/ROWNUM 条件")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def run_metadata_rule(rule: QualityRule, db: Session) -> list[QualityFinding]:
    """执行 metadata_only 规则——从本地资产元数据生成 findings。
    由 quality.py 的 RULE_RUNNERS 分发，保留兼容。
    """
    from ..api.v1.quality import RULE_RUNNERS
    runner = RULE_RUNNERS.get(rule.rule_code)
    if runner:
        return runner(db)
    return []


def run_sql_rule(rule: QualityRule, db: Session) -> list[QualityFinding]:
    """执行 sql_template 规则——调用 quality_sql_runner 对源库执行 SQL。
    当前为占位实现，返回空列表。源库连接打通后由 Q2-2 替换。
    """
    return []
