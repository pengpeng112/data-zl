# backend/AGENTS.md

> 权威规则在根 `AGENTS.md`（先读根 `INDEX.md` 路由）。本文件仅列本目录高频命令与本地约定。

## 命令

- 测试（隔离库须先 `source tools/dev_env.sh` 推导 `APP_TEST_DB_URL`，指向 data_asset_test）：`.venv\Scripts\python.exe -m pytest tests/ -q`
- 纯逻辑子目录（无库门禁）：`tests/db_guard`、`tests/plan*`、`tests/identity_*`、`tests/alembic_env`
- 迁移（仅隔离库）：`.venv\Scripts\python.exe -m alembic upgrade head`（手写 upgrade/downgrade，禁 autogenerate）
- 启动：根 `start_backend.bat`

## 本地约定

- 新表一律 `asset` schema + `asset_<模块>_<实体>` 前缀；旧 MVP 表（api_keys 等）保留不删。
- 凭据/患者数据不写代码、日志、测试 fixture；审计写入前脱敏。
- 一次性探查脚本放 `backend/scripts/`（用途见 manifest docstring），敏感工作包放 gitignored `_oa_work/`。
- 全量 pytest 会 TRUNCATE：跑前清点在跑 pytest、核实隔离库身份与占用。跑后是否恢复基线按该隔离库的约定恢复要求判断：明确要求恢复基线时，使用当前核实有效的恢复工具（不默认依赖历史 import170.py）；恢复受阻单列状态，不混同测试结果，也不覆盖其他会话的测试状态。
