# P1 M1 验收样本清单

> 验收目标：确认只读资产门户所有功能可用，前后端联调正常。

## 后端 API 验收

| # | 接口 | 请求 | 预期 |
|---|---|---|---|
| 1 | GET /health | — | 200, database=connected, 无 db_error |
| 2 | GET /api/v1/summary | — | 200, tables/columns/relations/domains 均为正数 |
| 3 | GET /api/v1/tables?keyword=PAT_VISIT&page=1&page_size=5&sort=table_name | — | 200, total>=1, 首行含 PAT_VISIT |
| 4 | GET /api/v1/tables/HIS/PAT_VISIT | — | 200, schema_name=HIS, table_name=PAT_VISIT, relation_count>0 |
| 5 | GET /api/v1/tables/HIS/PAT_VISIT/columns | — | 200, 数组长度 > 0 |
| 6 | GET /api/v1/columns/search?keyword=PATIENT_ID&page=1&page_size=10&sort=column_name | — | 200, total>0 |
| 7 | GET /api/v1/tables/HIS/PAT_VISIT/relations | — | 200, 包含至少 1 条 validated 关系 |
| 8 | GET /api/v1/relations/path?from=HIS.PAT_VISIT&to=HIS.PAT_MASTER_INDEX | — | 200, path 不为 null, hops 含 validation_level |
| 9 | POST /api/v1/ai/export-context | {"tables":["HIS.PAT_VISIT"],"include_relations":true,"include_columns":true} | 200, safety 含"脱敏" |
| 10 | POST /api/v1/ai/export-context | {} | 400, 提示缺少 tables |
| 11 | GET /api/v1/tables?sort=drop_table | — | 400, 提示不支持的排序字段 |
| 12 | GET /api/v1/tables?page=0 | — | 422 |

## 前端页面验收

| # | 页面 | 操作 | 预期 |
|---|---|---|---|
| 1 | 资产总览 | 登录后 数据资产 > 资产总览 | 4 个统计卡片显示正数；业务域柱状图有数据 |
| 2 | 表资产 | 搜索 PAT_VISIT 回车 | 表格显示匹配行；分页可用 |
| 3 | 表详情 | 点击表名行 | 跳转详情页，显示基本信息、字段列表、关联关系表 |
| 4 | 关系路径 | 输入 HIS.PAT_VISIT → HIS.PAT_MASTER_INDEX，查询 | 显示路径卡片，含 join 条件、验证等级 |
| 5 | AI 上下文 | 搜索 PAT_VISIT 勾选，导出 | 显示导出成功，可复制/下载 JSON |
| 6 | 菜单导航 | 逐一访问各子菜单 | 均跳转正常，无空白页、无控制台报错 |

## 验收条件

- 后端 12 项 API 验收全部通过。
- 前端 6 项页面验收全部通过。
- 验收人在下方签字/确认。

---

| 角色 | 姓名/标识 | 确认结果 | 日期 |
|---|---|---|---|
| 项目负责人 | | | |
| 信息科验收人 | | | |
