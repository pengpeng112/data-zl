# 取数工作区（126 查询资产闭环）

> 所有 AI 开始日常取数、保存 SQL、复用指标或修订口径前，必须先读本文件与根目录 `AGENTS.md`、`开发起步包/126_AI查询SQL与统计指标闭环治理建设计划.md`。

## 硬规则

1. 平台是唯一事实源；本目录是缓存与交接，不是权威库。
2. SQL 必须保存；结果默认不保存（`result_storage: none`），仅按需保存小型汇总。
3. 只允许单条 `SELECT` / 只读 CTE；禁止 DML/DDL/存储过程/锁表/无界大表扫描。
4. 自动门禁通过后直接成为现行版本，不设管理员确认；门禁失败进入 `blocked/candidate`。
5. 参数（月份、科室等）只产生 run，不产生新 version；SQL/口径变化必须新 version。
6. 不把凭据、姓名、身份证、电话、地址、患者明细写入外网 AI、SQL 注释、日志或 Git。
7. JOIN 证据优先正式关系 / active 配方；历史 SQL JOIN 走 `sql-relation-intake`，不得直接写正式关系。

## 推荐目录

| 目录 | 用途 |
|---|---|
| `_query_working/` | 正在编写 |
| `_query_inbox/` | AI/人工新提交 |
| `_query_outbox/` | 已校验待同步 |
| `_query_synced/` | 已同步到平台 |
| `_query_quarantine/` | 风险/错误包 |
| `_query_context/` | 脱敏上下文缓存 |
| `_query_templates/` | 模板 |
| `48项目核心制度/` | 现有试点 SQL（保留，不自动移动） |

## 命令

```powershell
# 初始化包
python tools/queryctl.py init --query-code QRY_DEMO --title "示例"

# 校验
python tools/queryctl.py validate 取数/_query_working/QRY_DEMO

# 进入 outbox（可选 --to-platform 写测试/平台库，需 APP_DB_URL）
python tools/queryctl.py submit 取数/_query_working/QRY_DEMO
```

## 平台 API（P1/P2/P3）

- `POST /api/v1/queries/ingest` 摄取（自动门禁）
- `GET /api/v1/queries` 列表
- `GET /api/v1/queries/{code}` 详情与版本
- `POST /api/v1/queries/run` 只读执行（结果默认 none）
- `GET /api/v1/queries/ai/context` AI 现行查询上下文
- `POST /api/v1/metrics/ingest` 指标摄取
- `GET /api/v1/metrics` / `ai/context`
- `POST /api/v1/queries/import/core-48` 48 项试点导入（默认 dry-run）
- `GET /api/v1/queries/impact/table?table_name=PAT_VISIT` 表影响分析
- `GET /api/v1/queries/{code}/relation-candidates` JOIN 候选（不写正式关系）
- 调度：`POST /api/v1/queries/schedules`（enabled 默认 false；全局 `APP_QUERY_SCHEDULE_ENABLED` 默认 false）

```powershell
# 48 项 dry-run / 写入测试库
python tools/import_core_48_metrics.py
python tools/import_core_48_metrics.py --apply --only 3 4 5
```

