# frontend/AGENTS.md

> 权威规则在根 `AGENTS.md`（先读根 `INDEX.md` 路由）。本文件仅列本目录高频命令与本地约定。

## 命令

- 包管理**必须 pnpm**（`preinstall: only-allow pnpm`）：`pnpm install`
- 类型检查（tsc+vue-tsc 双过）：`pnpm run typecheck`
- 测试：`pnpm exec vitest run`
- 构建（含 gzip 预算门禁）：`pnpm run build`
- 开发：根 `start_frontend.bat`

## 本地约定

- 基于 pure-admin-thin：Vue3+Element Plus+Pinia+Tailwind+Vite+TS；typecheck 两工具都过才算过。
- API 层按模块分 `src/api/*.ts`（asset/dict/identity/metadata/ops/routes/user），新增接口优先扩展现有文件。
- 路由模块在 `src/router/modules/`（`import.meta.glob` 自动导入——工具函数勿放入）；视图在 `src/views/<模块>/`。
- 既有路径（`/relations/{id}/review`、`/dict-medical/*` 等）不改；菜单计数断言在 `tests/plan186Menus.test.ts`（增删菜单须同步）。
- 日志不入本目录根：构建/调试输出写 `artifacts/`（见根 INDEX 产生规则）。
