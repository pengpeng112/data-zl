# 数据资产平台后端

FastAPI + SQLAlchemy + Alembic + PostgreSQL（单一 `asset` schema）。当前功能、未完成事项和发布门禁以根 `AGENTS.md`、`开发起步包/README.md`、`开发起步包/55_系统未完成事项统一执行计划.md` 为准；不要以旧模块数量或旧测试数量判断完成度。

## 本地启动

```powershell
cd F:\python\数据资产\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

环境变量由本地 `.env` 或部署密钥管理注入。`APP_DB_URL`、`APP_CREDENTIAL_ENCRYPT_KEY` 等不得写入代码或文档；生产首次管理员 Token 仅能通过受控部署脚本生成。

## 验收

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m alembic upgrade head
```

测试必须使用独立测试数据库。当前测试隔离整改属于 P0，执行前阅读 55 号计划。

## API 与安全

- 运行时 OpenAPI：`http://127.0.0.1:8000/docs`
- 静态接口说明：`docs/api.md`，与 OpenAPI 不一致时以运行时 OpenAPI 和代码为准。
- 业务源库只读；AI 不执行写操作；平台库写通道默认关闭。
- 部署统一以 `deploy/offline/README.md` 为准。
