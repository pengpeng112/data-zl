"""五类质控规则 SQL 模板生成器

规则分类：UNIQUE / COMPLETE / STANDARD / RELATION / ACCURACY
检查层级：TABLE_INNER / TABLE_RELATION / SYSTEM_CROSS / BUSINESS_LOGIC
约束级别：HARD / SOFT / WARN / INFO
"""

from typing import Optional


def template_unique_pk(table_name: str, pk_column: str, namespace: str | None = None) -> str:
    """主键唯一性校验 SQL 模板"""
    full_table = f"{namespace}.{table_name}" if namespace else table_name
    return (
        f"SELECT {pk_column}, COUNT(*) as dup_cnt "
        f"FROM {full_table} "
        f"GROUP BY {pk_column} "
        f"HAVING COUNT(*) > 1"
    )


def template_complete_required(table_name: str, column_name: str, namespace: str | None = None) -> str:
    """必填字段空值校验 SQL 模板"""
    full_table = f"{namespace}.{table_name}" if namespace else table_name
    return f"SELECT COUNT(*) as null_cnt FROM {full_table} WHERE {column_name} IS NULL"


def template_standard_length(table_name: str, column_name: str, max_length: int, namespace: str | None = None) -> str:
    """字段长度超长校验 SQL 模板"""
    full_table = f"{namespace}.{table_name}" if namespace else table_name
    return f"SELECT COUNT(*) as overflow_cnt FROM {full_table} WHERE LENGTH({column_name}) > {max_length}"


def template_standard_domain(table_name: str, column_name: str, valid_values: list[str], namespace: str | None = None) -> str:
    """值域代码合法性校验 SQL 模板"""
    full_table = f"{namespace}.{table_name}" if namespace else table_name
    values = ", ".join(f"'{v}'" for v in valid_values)
    return f"SELECT COUNT(*) as invalid_cnt FROM {full_table} WHERE {column_name} NOT IN ({values})"


def template_relation_orphan(
    child_table: str, child_fk: str,
    parent_table: str, parent_pk: str,
    namespace: str | None = None,
) -> str:
    """主从关系孤儿校验 SQL 模板"""
    child_full = f"{namespace}.{child_table}" if namespace else child_table
    parent_full = f"{namespace}.{parent_table}" if namespace else parent_table
    return (
        f"SELECT COUNT(*) as orphan_cnt FROM {child_full} c "
        f"WHERE c.{child_fk} IS NOT NULL "
        f"AND NOT EXISTS (SELECT 1 FROM {parent_full} p WHERE p.{parent_pk} = c.{child_fk})"
    )


def template_accuracy_time(first_date: str, second_date: str, table_name: str, namespace: str | None = None) -> str:
    """时间逻辑校验 SQL 模板（如入院时间 > 出院时间）"""
    full_table = f"{namespace}.{table_name}" if namespace else table_name
    return f"SELECT COUNT(*) as error_cnt FROM {full_table} WHERE {first_date} > {second_date}"


def template_accuracy_single(table_name: str, column_name: str, condition: str, namespace: str | None = None) -> str:
    """单字段条件逻辑校验 SQL 模板（如主要诊断只能有一条）"""
    full_table = f"{namespace}.{table_name}" if namespace else table_name
    return f"SELECT COUNT(*) as error_cnt FROM {full_table} WHERE {column_name} = {condition}"


def template_cross_system(table_a: str, key_a: str, table_b: str, key_b: str,
                          compare_field: str, namespace_a: str = "",
                          namespace_b: str = "") -> str:
    """跨系统质控 SQL 模板"""
    full_a = f"{namespace_a}.{table_a}" if namespace_a else table_a
    full_b = f"{namespace_b}.{table_b}" if namespace_b else table_b
    return (
        f"SELECT COUNT(*) as mismatch_cnt "
        f"FROM {full_a} a LEFT JOIN {full_b} b ON a.{key_a} = b.{key_b} "
        f"WHERE a.{compare_field} != b.{compare_field}"
    )
