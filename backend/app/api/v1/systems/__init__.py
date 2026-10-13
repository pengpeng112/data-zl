"""215 E11：systems 域门面（原 api/v1/systems.py）。

原文件按子域拆为本包模块；本 __init__ 保持两个兼容面：
1. ``from app.api.v1 import systems; systems.router``（main.py include_router）；
2. ``from app.api.v1.systems import _classify_asset_source`` 等既有符号引用。
路由注册顺序 = 子模块导入顺序 = 原 systems.py 定义顺序（路径与匹配语义不变）。
"""
from __future__ import annotations

from . import (  # noqa: F401  # 注册顺序=原文件定义顺序
    assets_tree,
    connections,
    purpose_bindings,
    sources,
    systems_mgmt,
)
from ._router import router  # noqa: F401
from ._shared import _apply_connection_meta, _audit, _source_public  # noqa: F401
from .assets_tree import _classify_asset_source, _presence_visible_clause, _table_brief  # noqa: F401
from .connections import ConnectionDraftTest, _CONNECTION_TEST_SLOTS, _run_connectivity_test  # noqa: F401
from .sources import (
    ALLOWED_WRITE_POLICIES,
    CredentialUpdate,
    DataSourceUpsert,
    SourcePatch,
)
from .systems_mgmt import ConnectionInput, SystemUpsert, SystemWithConnectionsCreate
from .purpose_bindings import PurposeBindingUpsert  # noqa: F401

__all__ = [
    "router",
    "assets_tree",
    "connections",
    "purpose_bindings",
    "sources",
    "systems_mgmt",
    "SystemUpsert",
    "ConnectionInput",
    "SystemWithConnectionsCreate",
    "DataSourceUpsert",
    "CredentialUpdate",
    "SourcePatch",
    "ALLOWED_WRITE_POLICIES",
    "ConnectionDraftTest",
    "PurposeBindingUpsert",
    "_source_public",
    "_apply_connection_meta",
    "_audit",
    "_run_connectivity_test",
    "_CONNECTION_TEST_SLOTS",
    "_classify_asset_source",
    "_presence_visible_clause",
    "_table_brief",
]
