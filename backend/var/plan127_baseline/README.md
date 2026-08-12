# 127 S0 只读基线快照

> 日期：2026-08-11  
> 来源：计划 127 第 3/8/18 节已核实生产基线（禁止用本机 10.20.1.153 得出数据结论）

## 生产平台（10.10.8.83 / data_asset）

| 对象 | 数量 |
|---|---:|
| 表资产 | 7,766 |
| 字段资产 | 89,730 |
| 非空业务域 | 38 |
| 数据库分区 | 78（59 缺中文名） |
| 未分业务域表 | 820 |
| column_count=0/NULL | 4,246 |
| 关系合计 | 537（candidate 318 / formal 194 / sync_mapping 25） |
| 质量规则 | 185（启用 10 / 停用 175） |
| 质量问题 | 10,439 |
| 检查批次 | 30 |
| 质量任务/指标表 | 0 / 0 |
| relation_reviews | 3 draft |
| 配方 / AI 会话 / 负责人 / 术语 | 0 / 0 / 0 / 0 |
| 元数据快照 | 9 |

## Review 草稿（禁止生产批准，本轮仅测试库验证）

| Review | 建议 | 禁止动作 |
|---|---|---|
| 1 INP_BILL_DETAIL→PAT_VISIT | 确认，链接 formal **468** | 禁止把 candidate **537** 提升 formal |
| 2 CLINIC_MASTER→PAT_MASTER_INDEX | 确认并保留 1 孤儿说明，链接 formal **473** | 禁止提升 **538** |
| 3 MEDREC.PAT_VISIT→ODS HIS.PAT_VISIT | 保持 draft | 禁止自动批准 |

真正业务键重复组：28/45（YDHL）、426/439（gecris 双 formal）。

## 复核脚本

见 `backend/var/verify_127_*.sql/.py`。生产只读查询：

```bash
sudo -u postgres /usr/local/pgsql/bin/psql -d data_asset
# 先 SET TRANSACTION READ ONLY;
```

## 环境

- 测试库：`data_asset_test` @ 8.83，迁移 head `d1e2f3a4b5c6`
- 本机 `.env` → 10.20.1.153 **已弃用**，不得用于数据结论
- 夜间质量任务运行中（最近 2026-08-11 02:00），改动须向后兼容
