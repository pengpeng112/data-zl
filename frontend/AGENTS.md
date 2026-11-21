# frontend/AGENTS.md

> 权威规则在根 `AGENTS.md`（先读根 `INDEX.md` 路由）。编辑前必先运行 `python tools/ai_handoff.py status` 与 `git status --short`，不得覆盖他人未提交改动（尤其 `tools/dev_env.sh` 守护的 8 个 `frontend/` 他人域文件）。

## 命令

- 包管理**必须 pnpm**（`preinstall: only-allow pnpm`）：`pnpm install`
- 类型检查（`tsc --noEmit` + `vue-tsc` 双过）：`pnpm run typecheck`
- 测试：`pnpm exec vitest run`
- 构建（含 gzip 预算门禁）：`pnpm run build`
- 启动：根 `start_frontend.bat`

## 本地约定

- 基于 `pure-admin-thin`：Vue3 + Element Plus + Pinia + Tailwind + Vite + TS；`typecheck` 双工具都过才算通过。
- API 层按模块拆分在 `src/api/*.ts`（`asset`/`dict`/`identity`/`metadata`/`ops`/`routes`/`user`），新增接口优先扩展现有文件。
- 路由模块在 `src/router/modules/`（`import.meta.glob` 自动导入，工具函数勿放入）；视图在 `src/views/<模块>/`。
- 既有路径（`/relations/{id}/review`、`/dict-medical/*` 等）不改；菜单计数断言在 `tests/plan186Menus.test.ts`（增删菜单须同步）。
- 调试与构建产物不入本目录根，归拢到根 `artifacts/`（见 `INDEX.md`）；新开发文档归入 `开发起步包/` 并按根 `AGENTS.md` §5 取号登记。
