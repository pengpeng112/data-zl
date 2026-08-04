"""relation endpoint identity, layer, business key, timestamps and graph sync batch.

S0 前置治理（98号说明 + 97号计划 G2/G3）+ 100号修复：
1. asset_relations 补齐端点五元组（from/to system_code/source_code/namespace_name/schema_name/table_name）；
2. 补齐 created_at/updated_at（updated_at 由应用层在 relations.py 审核编辑时刷新）；
3. 落地关系分层 relation_layer（formal/candidate/dependency/deferred/sync_mapping）；
4. 增加稳定业务幂等键 relation_business_key（不依赖会漂移的 rel_id）；
5. 历史数据按 from_table/to_table 可审计回填，无法唯一映射的保留 NULL 不猜；
6. 新增 asset_graph_sync_batches 表记录图分析层同步批次。

100号修复要点：
- 纯表名 schema 为 NULL（不再错误填充）；
- 三段式正确映射 namespace/schema/table；
- 唯一 pair 匹配使用 CTE + DISTINCT pair 去重，禁止 LIMIT 1 猜测；
- 新增 from_namespace_name/to_namespace_name 列。

不删除 from_table/to_table/rel_id 等兼容字段。
禁止 autogenerate，upgrade/downgrade 全手写。

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "asset"

_ENDPOINT_COLUMNS = [
    "from_system_code",
    "from_source_code",
    "from_namespace_name",
    "from_schema_name",
    "from_table_name",
    "to_system_code",
    "to_source_code",
    "to_namespace_name",
    "to_schema_name",
    "to_table_name",
]


def upgrade() -> None:
    # 1. 时间戳
    op.add_column(
        "asset_relations",
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_relations",
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    # 2. 端点五元组（含 namespace）
    for col in _ENDPOINT_COLUMNS:
        op.add_column(
            "asset_relations",
            sa.Column(col, sa.Text(), nullable=True),
            schema=SCHEMA,
        )

    # 3. 关系分层 + 稳定业务键
    op.add_column(
        "asset_relations",
        sa.Column("relation_layer", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "asset_relations",
        sa.Column("relation_business_key", sa.Text(), nullable=True),
        schema=SCHEMA,
    )

    # 4. 历史回填：namespace/schema/table 从 from_table/to_table 拆分
    #    统一规则（100号 A1）：
    #    - 纯表名（无点）：namespace=NULL, schema=NULL, table=原值
    #    - 二段式（一个点）：namespace=NULL, schema=第一段, table=第二段
    #    - 三段式（两个点）：namespace=第一段, schema=第二段, table=第三段
    op.execute(sa.text("""
        UPDATE asset.asset_relations
        SET from_namespace_name = CASE
                WHEN LENGTH(from_table) - LENGTH(REPLACE(from_table, '.', '')) >= 2
                THEN SPLIT_PART(from_table, '.', 1)
                ELSE NULL
            END,
            from_schema_name = CASE
                WHEN POSITION('.' IN from_table) = 0 THEN NULL
                WHEN LENGTH(from_table) - LENGTH(REPLACE(from_table, '.', '')) >= 2
                THEN SPLIT_PART(from_table, '.', 2)
                ELSE SPLIT_PART(from_table, '.', 1)
            END,
            from_table_name = CASE
                WHEN POSITION('.' IN from_table) = 0 THEN from_table
                WHEN LENGTH(from_table) - LENGTH(REPLACE(from_table, '.', '')) >= 2
                THEN SPLIT_PART(from_table, '.', 3)
                ELSE SPLIT_PART(from_table, '.', 2)
            END
        WHERE from_table IS NOT NULL
          AND from_table_name IS NULL
    """))
    op.execute(sa.text("""
        UPDATE asset.asset_relations
        SET to_namespace_name = CASE
                WHEN LENGTH(to_table) - LENGTH(REPLACE(to_table, '.', '')) >= 2
                THEN SPLIT_PART(to_table, '.', 1)
                ELSE NULL
            END,
            to_schema_name = CASE
                WHEN POSITION('.' IN to_table) = 0 THEN NULL
                WHEN LENGTH(to_table) - LENGTH(REPLACE(to_table, '.', '')) >= 2
                THEN SPLIT_PART(to_table, '.', 2)
                ELSE SPLIT_PART(to_table, '.', 1)
            END,
            to_table_name = CASE
                WHEN POSITION('.' IN to_table) = 0 THEN to_table
                WHEN LENGTH(to_table) - LENGTH(REPLACE(to_table, '.', '')) >= 2
                THEN SPLIT_PART(to_table, '.', 3)
                ELSE SPLIT_PART(to_table, '.', 2)
            END
        WHERE to_table IS NOT NULL
          AND to_table_name IS NULL
    """))

    # 5. 历史回填：system_code/source_code 反查 asset_tables（100号 A2 修复）。
    #    使用 CTE 对 (system_code, source_code) pair 去重，
    #    只有去重后 pair 总数恰好为 1 才回填；0 或多于 1 保持 NULL。
    #    system_code 和 source_code 来自同一个 pair（单次 UPDATE FROM）。
    op.execute(sa.text("""
        WITH candidates AS (
            SELECT
                t.schema_name,
                t.table_name,
                t.system_code,
                t.source_code
            FROM asset.asset_tables t
            WHERE t.schema_name IS NOT NULL
              AND t.table_name IS NOT NULL
        ),
        pair_counts AS (
            SELECT
                schema_name,
                table_name,
                COUNT(DISTINCT (system_code, source_code)) AS pair_count,
                MIN(system_code) AS sys_code,
                MIN(source_code) AS src_code
            FROM candidates
            GROUP BY schema_name, table_name
        )
        UPDATE asset.asset_relations r
        SET from_system_code = pc.sys_code,
            from_source_code = pc.src_code
        FROM pair_counts pc
        WHERE pc.schema_name = r.from_schema_name
          AND pc.table_name = r.from_table_name
          AND pc.pair_count = 1
          AND r.from_schema_name IS NOT NULL
          AND r.from_table_name IS NOT NULL
          AND r.from_system_code IS NULL
    """))
    op.execute(sa.text("""
        WITH candidates AS (
            SELECT
                t.schema_name,
                t.table_name,
                t.system_code,
                t.source_code
            FROM asset.asset_tables t
            WHERE t.schema_name IS NOT NULL
              AND t.table_name IS NOT NULL
        ),
        pair_counts AS (
            SELECT
                schema_name,
                table_name,
                COUNT(DISTINCT (system_code, source_code)) AS pair_count,
                MIN(system_code) AS sys_code,
                MIN(source_code) AS src_code
            FROM candidates
            GROUP BY schema_name, table_name
        )
        UPDATE asset.asset_relations r
        SET to_system_code = pc.sys_code,
            to_source_code = pc.src_code
        FROM pair_counts pc
        WHERE pc.schema_name = r.to_schema_name
          AND pc.table_name = r.to_table_name
          AND pc.pair_count = 1
          AND r.to_schema_name IS NOT NULL
          AND r.to_table_name IS NOT NULL
          AND r.to_system_code IS NULL
    """))

    # 6. 历史回填：relation_layer 按现有状态推导
    op.execute(sa.text("""
        UPDATE asset.asset_relations
        SET relation_layer = CASE
            WHEN UPPER(COALESCE(confidence, '')) = 'D' THEN 'deferred'
            WHEN validation_status LIKE 'user_confirmed_sync%' THEN 'sync_mapping'
            WHEN validation_status = 'candidate' THEN 'candidate'
            WHEN validation_status IN ('verified', 'partial', 'user_confirmed', 'user_confirmed_mapping',
                                       'user_confirmed_parallel_sources', 'manual_reviewed', 'A_rechecked')
                 THEN 'formal'
            WHEN validation_status IS NULL OR validation_status = '' THEN 'candidate'
            ELSE 'candidate'
        END
        WHERE relation_layer IS NULL
    """))

    # 7. 历史回填：relation_business_key 稳定幂等键（含物理身份）
    op.execute(sa.text("""
        UPDATE asset.asset_relations
        SET relation_business_key = MD5(
            LOWER(
                COALESCE(from_system_code, '') || '|' ||
                COALESCE(from_source_code, '') || '|' ||
                COALESCE(from_table, '') || '|' ||
                COALESCE(to_system_code, '') || '|' ||
                COALESCE(to_source_code, '') || '|' ||
                COALESCE(to_table, '') || '|' ||
                COALESCE(from_columns, '') || '|' ||
                COALESCE(to_columns, '') || '|' ||
                COALESCE(join_condition, '')
            )
        )
        WHERE relation_business_key IS NULL
          AND from_table IS NOT NULL
          AND to_table IS NOT NULL
    """))

    # 8. 索引
    op.create_index(
        "ix_asset_relations_updated_at",
        "asset_relations",
        ["updated_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_relations_business_key",
        "asset_relations",
        ["relation_business_key"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_asset_relations_layer",
        "asset_relations",
        ["relation_layer"],
        schema=SCHEMA,
    )

    # 9. 图同步批次表（增加 unresolved_count/skipped_count）
    op.create_table(
        "asset_graph_sync_batches",
        sa.Column("batch_id", sa.Text(), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("node_count", sa.Integer(), server_default="0"),
        sa.Column("edge_count", sa.Integer(), server_default="0"),
        sa.Column("upsert_count", sa.Integer(), server_default="0"),
        sa.Column("delete_count", sa.Integer(), server_default="0"),
        sa.Column("unresolved_count", sa.Integer(), server_default="0"),
        sa.Column("skipped_count", sa.Integer(), server_default="0"),
        sa.Column("checksum", sa.Text()),
        sa.Column("error_masked", sa.Text()),
        sa.PrimaryKeyConstraint("batch_id"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("asset_graph_sync_batches", schema=SCHEMA)
    op.drop_index("ix_asset_relations_layer", table_name="asset_relations", schema=SCHEMA)
    op.drop_index("ix_asset_relations_business_key", table_name="asset_relations", schema=SCHEMA)
    op.drop_index("ix_asset_relations_updated_at", table_name="asset_relations", schema=SCHEMA)
    op.drop_column("asset_relations", "relation_business_key", schema=SCHEMA)
    op.drop_column("asset_relations", "relation_layer", schema=SCHEMA)
    for col in reversed(_ENDPOINT_COLUMNS):
        op.drop_column("asset_relations", col, schema=SCHEMA)
    op.drop_column("asset_relations", "updated_at", schema=SCHEMA)
    op.drop_column("asset_relations", "created_at", schema=SCHEMA)