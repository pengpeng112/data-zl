# T0 项目画像自探 checkpoint（2026-09-09）

## 1. 技术栈
- 后端：FastAPI + SQLAlchemy 2.0 + pydantic-settings + Alembic；DB=PostgreSQL（psycopg3）；Python venv=backend/.venv
- 前端：pure-admin-thin（Vue3 + Element Plus + Pinia + Tailwind + Vite + TS）；包管理器=pnpm（preinstall only-allow）
- 测试：后端 pytest（164 个 test_*.py）；前端 vitest（48 个 *.test.ts）+ typecheck（tsc && vue-tsc）

## 2. 启动方式
- 后端：uvicorn app.main:app（默认 8000）；依赖 APP_DB_URL
- 前端 dev：pnpm dev（端口 8848，/api 代理 → http://localhost:8000）
- ⚠️ backend/.env 的 APP_DB_URL → 10.20.1.153:5432/data_asset（内网共享开发库，非本地非隔离库）
  → QA 动态测试一律显式覆盖 APP_DB_URL=隔离测试库（127.0.0.1:15432→data_asset_test），绝不使用 .env

## 3. 数据与凭据
- 隔离测试库：127.0.0.1:15432 → 10.10.8.83:5432/data_asset_test（已连通，asset schema 115 表）
- 凭据来源：生产容器 APP_DB_URL 同口令，内存流转不落盘（已验证 TEST_DB_OK）
- 认证：ApiKey Bearer（asset_api_keys.token）；隔离库含既有 verify token（import170 重建）
- 已知副作用：pytest 全量 autouse fixture 会 TRUNCATE 隔离库（166 附录 A.2）→ 基线跑完后需 reseed

## 4. 既有测试基线（运行中）
- backend: APP_TEST_DB_URL 显式指向隔离库，pytest tests/ -q → checkpoints/backend_pytest_baseline.log
- frontend: pnpm typecheck → checkpoints/fe_typecheck.log；pnpm test(vitest) → checkpoints/fe_vitest.log

## 5. 路由与页面清单
- 后端：33 模块 432 端点（@router 装饰器统计）；大模块：systems/identity/dict_medical(27-28)、ops_tools(24)、queries(21)、governance(21)
- 前端：13 个路由模块（asset/catalog/dict/error/governance/home/identity/metadata/ops/quality/query/remaining/standards）

## 6. 运行时降级阶梯
- 计划：整体启动（本地 uvicorn 8000 + vite 8848，均指向隔离测试库）→ 动态测试可行
- 端口预检：8000/8848 空闲；4173 被 PID 27276 占用（未知归属，不杀只记录）；15432 隧道既有（PID 48448）

## 未探明
- 生产 build 产物行为（本次只测 dev 链路，build 预算由 postbuild 脚本在基线外评估）
