# 数据资产平台 后端

FastAPI + SQLAlchemy + PostgreSQL，医院数据资产管理与多系统探库平台。

> 更新：2026-07-05 — v0.2.0，P5.5~P14 全部模块完成，180 条测试全通过。

## 技术栈

- Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic
- PostgreSQL 14（仅 `asset` schema，不拆物理 schema）
- APScheduler（定时调度）/ slowapi（频率限制）
- 多数据库连接器：Oracle / PostgreSQL / MySQL / SQL Server

## 快速启动

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_systems
.\.venv\Scripts\python.exe -m scripts.seed_enum_values
.\.venv\Scripts\python.exe -m scripts.seed_quality_rules
.\.venv\Scripts\python.exe -m scripts.seed_ops_tools
.\.venv\Scripts\python.exe -m scripts.seed_roles
uvicorn app.main:app --reload
```

## 目录结构

```
backend/
├── app/
│   ├── main.py              # 应用入口（鉴权/RBAC/APScheduler/lifespan）
│   ├── api/v1/              # 16 个路由模块
│   │   ├── admin.py         # API Token/表Owner/业务术语/快照
│   │   ├── ai.py            # AI 工具协作
│   │   ├── candidates.py    # 候选关系
│   │   ├── dict_general_api.py   # 通用字典
│   │   ├── dict_medical_api.py   # 诊断/手术字典
│   │   ├── governance.py    # RBAC/审批/审计/执行器
│   │   ├── governance_ops.py     # 调度/事件/变更规则
│   │   ├── graph.py         # 关系图谱
│   │   ├── health.py        # 健康检查
│   │   ├── identity.py      # 人员与科室
│   │   ├── lineage.py       # 血缘与影响
│   │   ├── metadata_changes.py   # 元数据变更检测
│   │   ├── ops_tools.py     # 运维工具
│   │   ├── quality.py       # 数据质量
│   │   ├── relations.py     # 关系路径与复核
│   │   ├── systems.py       # 系统与数据源
│   │   └── tables.py        # 表资产
│   ├── core/                # 基础设施（配置/数据库/认证/异常/日志）
│   ├── models/              # 14 个模型文件，40 张表
│   │   ├── asset.py         # 表/字段/关系/关系复核
│   │   ├── asset_system.py  # 系统/数据源
│   │   ├── dict_general.py  # 通用字典（分类/标准项/系统项/映射/版本）
│   │   ├── dict_medical.py  # 诊断/手术编码体系
│   │   ├── governance.py    # 旧 MVP 表（ApiKey/TableOwner等）
│   │   ├── governance_base.py  # 底座表（RBAC/审批/审计/执行器/枚举）
│   │   ├── governance_ops.py   # 调度/事件/变更规则
│   │   ├── identity.py      # 人员/科室/账号/差异
│   │   ├── metadata_change.py  # 元数据快照/变更事件
│   │   ├── ops_tool.py      # 运维工具模板/运行记录
│   │   ├── quality.py       # 质检规则/问题/检查/任务/指标
│   │   └── ...
│   ├── schemas/             # Pydantic 响应模型
│   └── services/            # 业务服务层
│       ├── db_connectors.py      # Oracle/PG/MySQL/SQLS 连接器
│       ├── metadata_collector.py # 多数据库元数据采集适配器
│       ├── metadata_diff.py      # 快照 diff 引擎
│       └── sync_executor.py      # 跨系统同步框架
├── alembic/                 # 15 次迁移
├── scripts/                 # 5 个种子数据脚本
├── tests/                   # 16 个测试文件，180 条
└── requirements.txt
```

## 测试

```bash
.\.venv\Scripts\python.exe -m pytest tests/ -v -q
# 180 passed
```

## 环境变量

参考 `.env.example`：
- `APP_DB_URL` — PostgreSQL 连接串
- `APP_CORS_ORIGINS` — CORS 白名单
- `APP_CREDENTIAL_ENCRYPT_KEY` — 凭据加密密钥
- `APP_SNAPSHOT_RETENTION_DAYS` — 快照保留天数（默认 90）
- `APP_EVENT_RETENTION_DAYS` — 事件保留天数（默认 365）
- `APP_SCHEDULER_TIMEZONE` — 调度时区（默认 Asia/Shanghai）

## 安全约束

- 源库一律只读 `SELECT`，禁止 DML/DDL
- 运维写操作必须通过 `asset_action_executors` 白名单 + 审批 + 审计
- AI 工具只能调用只读端点和审计日志，不接入写操作执行器
- 审计日志写入前脱敏（姓名/身份证/电话/地址）
- Token 支持过期时间（`expires_at` 字段）
- RBAC 按路径前缀和角色控制访问权限
- slowapi 频率限制（`/ops/*` 敏感端点 5/分钟）
