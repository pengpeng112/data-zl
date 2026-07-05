from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.db import Base
from app.models.asset import AssetTable, AssetColumn, AssetRelation  # noqa: F401
from app.models.lineage import AssetViewDependency  # noqa: F401
from app.models.candidate import AssetCandidateRelation  # noqa: F401
from app.models.quality import QualityRule, QualityFinding, QualityCheckRun  # noqa: F401
from app.models.ai_collab import AiSession, AiToolCall, ViewDraft  # noqa: F401
from app.models.governance import ApiKey, TableOwner  # noqa: F401
from app.models.governance_base import (  # noqa: F401
    AssetActionExecutor,
    AssetRole,
    AssetRolePermission,
    AssetUserRole,
    GovernAuditLog,
    GovernChangeRequest,
    GovernEnumValue,
)
from app.models.asset_system import AssetDataSource, AssetSystem  # noqa: F401
from app.models.governance_ops import ChangeRule, GovernEvent, SchedulerJob  # noqa: F401
from app.models.identity import (  # noqa: F401
    IdentityAccount,
    IdentityDepartment,
    IdentityPerson,
    IdentityPersonSource,
    IdentitySyncDiff,
)
from app.models.metadata_change import AssetMetadataChangeEvent, AssetMetadataColumnSnapshot  # noqa: F401
from app.models.ops_tool import OpsToolRun, OpsToolTemplate  # noqa: F401
from app.models.dict_medical import (  # noqa: F401
    DictMedicalCodeItem,
    DictMedicalCodeMapping,
    DictMedicalCodeSet,
    DictMedicalSyncDiff,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.db_url)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
