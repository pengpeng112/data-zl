# 数据资产平台前端

Vue 3 + TypeScript + Element Plus + Vite，基于 `pure-admin-thin` 模板二次开发。平台功能状态和开发优先级以根 `AGENTS.md`、`开发起步包/README.md`、`开发起步包/55_系统未完成事项统一执行计划.md` 为准。

## 启动与验收

```powershell
cd F:\python\数据资产\frontend
pnpm install
pnpm run dev
pnpm run typecheck
pnpm run build
```

开发代理指向本机后端 `/api`。本地开发 Token 只能通过未跟踪 `.env.local` 或进程环境变量配置，禁止硬编码、写入 localStorage 自动回填或提交到 git。

## 约定

- API 定义在 `src/api/`，路由在 `src/router/modules/`，页面在 `src/views/`。
- 后端权限是唯一授权边界；前端路由和按钮权限只改善体验。
- 新增页面或接口契约必须补类型、验收和 README 目录更新。

## 上游来源

模板源自 [vue-pure-admin](https://github.com/pure-admin/vue-pure-admin)，许可证见 `LICENSE`；上游英文说明保留于 `README.en-US.md`。
