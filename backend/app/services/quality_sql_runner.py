"""只读质控 SQL 执行器——对源库执行 SELECT，返回统计结果和脱敏样例

依赖：P1 源库连接修复后可用。当前为占位实现。
"""

from ..services.data_masking import mask_sensitive


def execute_quality_sql(
    rule_code: str,
    sql: str,
    source_code: str,
    max_rows: int = 1000,
    sample_limit: int = 20,
) -> dict:
    """执行只读质控 SQL，返回 {total_cnt, error_cnt, error_rate, sample_data}

    当前为占位实现。源库连接打通后：
    1. 根据 source_code 查找 AssetDataSource
    2. 解析 credential_ref 得到凭据
    3. 创建 DB_CONNECTOR_MAP 对应连接器
    4. 执行 SQL（max_rows 限制）
    5. 统计 total_cnt / error_cnt
    6. sample_data 脱敏后返回
    """
    return {
        "rule_code": rule_code,
        "total_cnt": 0,
        "error_cnt": 0,
        "error_rate": 0,
        "sample_data": [],
        "status": "placeholder",
        "note": "源库连接待 P1 整改完成后可用",
    }


def execute_and_collect_findings(
    rule,
    source_code: str,
    max_rows: int = 1000,
    sample_limit: int = 20,
) -> list[dict]:
    """便捷方法：执行 SQL 并直接生成 QualityFinding 列表"""
    result = execute_quality_sql(
        rule.rule_code,
        rule.check_sql or "",
        source_code,
        max_rows,
        sample_limit or 20,
    )
    if result["error_cnt"] == 0:
        return []

    findings = []
    for sample in result.get("sample_data", []):
        findings.append({
            "rule_code": rule.rule_code,
            "target_type": rule.target_type or "table",
            "target_ref": f"{rule.namespace_name or ''}.{rule.target_table or ''}.{rule.target_field or ''}",
            "system_code": rule.system_code,
            "source_code": rule.source_code,
            "namespace_name": rule.namespace_name,
            "table_name": rule.target_table,
            "column_name": rule.target_field,
            "severity": rule.error_level or "minor",
            "status": "open",
            "rectification_status": "open",
            "total_cnt": result["total_cnt"],
            "error_cnt": result["error_cnt"],
            "error_rate": result["error_rate"],
            "sample_data": mask_sensitive(sample) if isinstance(sample, dict) else str(sample),
            "detail": {
                "sql": rule.check_sql,
                "execution_result": result,
            },
        })
    return findings
