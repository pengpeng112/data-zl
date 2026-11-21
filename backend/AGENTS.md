# backend/AGENTS.md

> 权威规则在根 `AGENTS.md`（先读根 `INDEX.md` 路由）。编辑前必先运行 `python tools/ai_handoff.py status` 与 `git status --short`，不得覆盖他人未提交改动或 `tools/dev_env.sh` 列出的 13 个受保护文件。

## 命令

- 测试（隔离库须先 `source tools/dev_env.sh` 推导 `APP_TEST_DB_URL`，指向 `data_asset_test`）：`.venv\Scripts\python.exe -m pytest tests/ -q`
- 纯逻辑子目录（无库门禁）：`tests/db_guard`、`tests/plan*`、`tests/identity_*`、`tests/alembic_env`
- 迁移（仅隔离库）：`.venv\Scripts\python.exe -m alembic upgrade head`（手写 `upgrade()`/`downgrade()`，禁 `--autogenerate`）
- 迁移与文档自检（根目录）：`.\backend\.venv\Scripts\python.exe tools/check_migrations_tracked.py`
- 启动：根 `start_backend.bat`

## 本地约定

- 新表一律 `asset` schema + `asset_<模块>_<实体>` 前缀；旧 MVP 表（`asset_api_keys`/`asset_table_owners`/`asset_business_terms`/`asset_metadata_snapshots` 等）保留不删。
- 凭据与患者敏感信息禁写代码、日志或测试 fixture；审计写入前脱敏。
- 一次性探查脚本放 `backend/scripts/`（用途写进 docstring 供 manifest 采集），敏感工作包放 gitignored `_oa_work/`。
- 隔离库基线与占用：全量 pytest 会 `TRUNCATE`；跑前清点在跑 pytest、核实 `APP_TEST_DB_URL` 非生产/开发库，并按隔离库约定判断是否需要恢复基线（恢复受阻单列状态，不覆盖其他会话结果）。
- 新文档整理：新开发文档归入 `开发起步包/` 并按根 `AGENTS.md` §5 取号登记，临时脚本/文档不散落目录根。
