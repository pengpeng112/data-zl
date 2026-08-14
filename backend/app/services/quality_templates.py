"""五类质控规则 SQL 模板生成器

规则分类：UNIQUE / COMPLETE / STANDARD / RELATION / ACCURACY
检查层级：TABLE_INNER / TABLE_RELATION / SYSTEM_CROSS / BUSINESS_LOGIC
约束级别：HARD / SOFT / WARN / INFO

127 契约：主统计 SQL 必须返回单行 TOTAL_CNT + ERROR_CNT。
样本 SQL 与统计 SQL 分离，本模块只生成统计 SQL。
"""

from typing import Optional

# 已核实源端唯一键（2026-08-11 HIS 源端数据字典）。自动生成规则必须引用完整组合键。
CORE_UNIQUE_KEYS: dict[str, list[str]] = {
    "PAT_MASTER_INDEX": ["PATIENT_ID"],
    "PAT_VISIT": ["PATIENT_ID", "VISIT_ID"],
    "DIAGNOSIS": ["PATIENT_ID", "VISIT_ID", "DIAGNOSIS_TYPE", "DIAGNOSIS_NO"],
    "LAB_TEST_MASTER": ["TEST_NO"],
    "EXAM_MASTER": ["EXAM_NO"],
    "EXAM_REPORT": ["EXAM_NO"],
    "LAB_RESULT": ["TEST_NO", "ITEM_NO", "PRINT_ORDER"],
    # ORDERS 源端无主键约束，唯一索引 PK_ORDERS 必须含 ORDER_SUB_NO
    "ORDERS": ["PATIENT_ID", "VISIT_ID", "ORDER_NO", "ORDER_SUB_NO"],
    "OPERATION_MASTER": ["PATIENT_ID", "VISIT_ID", "OPER_ID"],
    "INP_BILL_DETAIL": ["PATIENT_ID", "VISIT_ID", "ITEM_NO"],
}

# 禁止无界全表聚合的大表
LARGE_TABLE_DENYLIST = {
    "LAB_RESULT",
    "INP_BILL_DETAIL",
    "ORDERS",
}


def _full_table(table_name: str, namespace: str | None = None) -> str:
    return f"{namespace}.{table_name}" if namespace else table_name


def _stat_wrapper(error_expr_sql: str, total_expr_sql: str) -> str:
    """Wrap error/total expressions into single-row TOTAL_CNT/ERROR_CNT."""
    return (
        "SELECT "
        f"({total_expr_sql}) AS TOTAL_CNT, "
        f"({error_expr_sql}) AS ERROR_CNT "
        "FROM dual"
    )


def template_unique_pk(table_name: str, pk_column: str, namespace: str | None = None) -> str:
    """主键/唯一键唯一性：ERROR_CNT = 重复键组数涉及的多余行近似（重复组数）。"""
    full_table = _full_table(table_name, namespace)
    cols = [c.strip() for c in pk_column.split(",") if c.strip()]
    if not cols:
        cols = [pk_column]
    group_by = ", ".join(cols)
    # 单行统计：重复组数作为 ERROR_CNT，总行数作为 TOTAL_CNT（大表调用方须限窗）
    return (
        f"SELECT COUNT(*) AS TOTAL_CNT, "
        f"NVL((SELECT COUNT(*) FROM ("
        f"SELECT {group_by} FROM {full_table} GROUP BY {group_by} HAVING COUNT(*) > 1"
        f")), 0) AS ERROR_CNT "
        f"FROM {full_table}"
    )


def template_unique_pk_composite(
    table_name: str,
    pk_columns: list[str],
    namespace: str | None = None,
) -> str:
    return template_unique_pk(table_name, ",".join(pk_columns), namespace)


def template_complete_required(table_name: str, column_name: str, namespace: str | None = None) -> str:
    full_table = _full_table(table_name, namespace)
    return (
        f"SELECT COUNT(*) AS TOTAL_CNT, "
        f"SUM(CASE WHEN {column_name} IS NULL THEN 1 ELSE 0 END) AS ERROR_CNT "
        f"FROM {full_table}"
    )


def template_complete_required_any(
    table_name: str, column_names: list[str], namespace: str | None = None
) -> str:
    full_table = _full_table(table_name, namespace)
    cols = [c.strip() for c in column_names if c and c.strip()]
    if not cols:
        return template_complete_required(table_name, "ID", namespace)
    if len(cols) == 1:
        return template_complete_required(table_name, cols[0], namespace)
    missing = " OR ".join(f"{col} IS NULL" for col in cols)
    return (
        f"SELECT COUNT(*) AS TOTAL_CNT, "
        f"SUM(CASE WHEN {missing} THEN 1 ELSE 0 END) AS ERROR_CNT "
        f"FROM {full_table}"
    )


def template_standard_length(
    table_name: str, column_name: str, max_length: int, namespace: str | None = None
) -> str:
    full_table = _full_table(table_name, namespace)
    return (
        f"SELECT COUNT(*) AS TOTAL_CNT, "
        f"SUM(CASE WHEN LENGTH({column_name}) > {int(max_length)} THEN 1 ELSE 0 END) AS ERROR_CNT "
        f"FROM {full_table}"
    )


def template_standard_domain(
    table_name: str,
    column_name: str,
    valid_values: list[str],
    namespace: str | None = None,
) -> str:
    full_table = _full_table(table_name, namespace)
    values = ", ".join(f"'{v}'" for v in valid_values)
    return (
        f"SELECT COUNT(*) AS TOTAL_CNT, "
        f"SUM(CASE WHEN {column_name} NOT IN ({values}) THEN 1 ELSE 0 END) AS ERROR_CNT "
        f"FROM {full_table}"
    )


def template_relation_orphan(
    child_table: str,
    child_fk: str,
    parent_table: str,
    parent_pk: str,
    namespace: str | None = None,
) -> str:
    child_full = _full_table(child_table, namespace)
    parent_full = _full_table(parent_table, namespace)
    return (
        f"SELECT COUNT(*) AS TOTAL_CNT, "
        f"SUM(CASE WHEN c.{child_fk} IS NOT NULL AND NOT EXISTS ("
        f"SELECT 1 FROM {parent_full} p WHERE p.{parent_pk} = c.{child_fk}"
        f") THEN 1 ELSE 0 END) AS ERROR_CNT "
        f"FROM {child_full} c"
    )


def template_relation_orphan_composite(
    child_table: str,
    child_fks: list[str],
    parent_table: str,
    parent_pks: list[str],
    child_namespace: str | None = None,
    parent_namespace: str | None = None,
) -> str:
    child_cols = [c.strip() for c in child_fks if c and c.strip()]
    parent_cols = [c.strip() for c in parent_pks if c and c.strip()]
    if len(child_cols) == 1 and len(parent_cols) == 1:
        return template_relation_orphan(
            child_table, child_cols[0], parent_table, parent_cols[0], child_namespace
        )
    child_full = _full_table(child_table, child_namespace)
    parent_full = _full_table(parent_table, parent_namespace)
    present = " AND ".join(f"c.{col} IS NOT NULL" for col in child_cols)
    join_pred = " AND ".join(
        f"p.{pcol} = c.{ccol}" for ccol, pcol in zip(child_cols, parent_cols)
    )
    return (
        f"SELECT COUNT(*) AS TOTAL_CNT, "
        f"SUM(CASE WHEN {present} AND NOT EXISTS ("
        f"SELECT 1 FROM {parent_full} p WHERE {join_pred}"
        f") THEN 1 ELSE 0 END) AS ERROR_CNT "
        f"FROM {child_full} c"
    )


def template_accuracy_time(
    first_date: str, second_date: str, table_name: str, namespace: str | None = None
) -> str:
    full_table = _full_table(table_name, namespace)
    return (
        f"SELECT COUNT(*) AS TOTAL_CNT, "
        f"SUM(CASE WHEN {first_date} IS NOT NULL AND {second_date} IS NOT NULL "
        f"AND {first_date} > {second_date} THEN 1 ELSE 0 END) AS ERROR_CNT "
        f"FROM {full_table}"
    )


def template_accuracy_single(
    table_name: str, column_name: str, condition: str, namespace: str | None = None
) -> str:
    full_table = _full_table(table_name, namespace)
    return (
        f"SELECT COUNT(*) AS TOTAL_CNT, "
        f"SUM(CASE WHEN {column_name} = {condition} THEN 1 ELSE 0 END) AS ERROR_CNT "
        f"FROM {full_table}"
    )


def template_cross_system(
    table_a: str,
    key_a: str,
    table_b: str,
    key_b: str,
    compare_field: str,
    namespace_a: str = "",
    namespace_b: str = "",
) -> str:
    """跨系统模板仅作结构参考；执行器应阻止跨物理连接直接 JOIN。"""
    full_a = f"{namespace_a}.{table_a}" if namespace_a else table_a
    full_b = f"{namespace_b}.{table_b}" if namespace_b else table_b
    return (
        f"SELECT COUNT(*) AS TOTAL_CNT, "
        f"SUM(CASE WHEN a.{compare_field} != b.{compare_field} THEN 1 ELSE 0 END) AS ERROR_CNT "
        f"FROM {full_a} a LEFT JOIN {full_b} b ON a.{key_a} = b.{key_b}"
    )


def is_large_table_unbounded_forbidden(table_name: str) -> bool:
    bare = (table_name or "").split(".")[-1].upper()
    return bare in LARGE_TABLE_DENYLIST
