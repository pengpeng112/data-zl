# r195-20260919-084932 批准包（S7 生产入库 + S5 夜窗验证）

> 生成：2026-09-19 09:35 本地。生产平台/业务源库写入数为 0；以下动作均未执行，等待批准。
> 本会话授权仅覆盖本地分析与已核实隔离库验收（已完成），不覆盖生产写与白天 live。

## 一、S7 生产平台待审入库（目标：8.83 data_asset / asset.asset_relation_reviews）

- 目标平台：10.10.8.83 data-asset-api（r186-20260910g healthy）→ 库 data_asset，表 `asset.asset_relation_reviews`
- run_id：`r195-20260919-084932`；导入文件 `import_payload_reviews.json`（SHA-256 前16：`e9bb821cc2636255`，178,109 字节，114 行草稿）
- 变更内容（全部 INSERT，零 UPDATE/DELETE）：
  - 114 条 review 草稿（relation_scope=`r195_intake`，review_status=`draft`，confidence=`C`）
    - candidate 29 / recipe_candidate 83 / partial_or_keysubset 2
  - 15 条 existing 候选**不导入**（平台已有正式边，仅本包留证据：平台 ID 已记录在 relation_candidates.json）
  - dry-run（生产基线只读比对）：新增 114 / 重复 0 / 更新 0（import_diff.json）
- 不影响的资产：`asset.asset_relations`（正式关系，零触碰）、值域 confirmed、既有 560 条 reviews（幂等键不含 scope 冲突）
- 隔离预演（data_asset_test）：PASS —— 114 插入/完全重放新增 0/反向边 1（查重层按方向精确匹配，反向需 intake 层归并，符合设计）/清理后零残留/他人行数不变（rehearsal_result.json）
- 备份与撤销方案：
  1. 入库前 `pg_dump` 平台库（按 ops-runbook §2 方言与压缩惯例）；
  2. 单事务 INSERT（同隔离预演语句），失败整体回滚；
  3. 撤销=`DELETE FROM asset.asset_relation_reviews WHERE relation_scope='r195_intake'`（批次级撤销，不动他人行、不删审计）；
  4. 入库后回读：按 scope 计数=114、抽查 cand_id→id 映射、二次 dry-run 新增=0。
- 建议执行通道：平台既有受控服务/审计入口；如走 SQL 通道，操作者与窗口由用户指定。
- 待批准动作：**生产 INSERT 114 条 draft reviews**（对象/范围如上；不含任何正式关系发布、不含 approve/confirm）。

## 二、S5 夜窗受控验证（业务源库只读，12 支聚合探针）

- 探针清单：`validation_plan.json` + `sql/probes/P-*.sql`（12 支：B1×5 / B2×1 / B3×1 / B4×1 / B5×5）
- 目标源（6 个）：`ods_8_216`×8、`his_source_10_10_10_15`×1（ALL_SYNONYMS 元数据）、`dialysis_postgresql_10_10_10_88`×1、`pathology_sqlserver_10_10_9_41`×1、（P-B5-08 含 JHEMR schema 可达性）
- 边界：单条 SELECT/WITH；聚合输出≤50行；超时60s；时间窗+主键子查询有界；`HIS.LAB_RESULT` 仅经 TEST_NO 子查询；不输出患者明细
- 白天（本会话）未执行：`BLOCKED_WINDOW`
- 待批准动作：**夜窗执行 12 支探针**（建议避开 00:10 手麻清单与 02:00 身份夜跑时段；具体时段由用户批准）。
- 执行结果落 `validation_results.jsonl`（含 source、时间、SQL 哈希、分母、指标、审计引用）。

## 三、S8 相关（人工治理，不可由 AI 代批）

- 114 条草稿入库后的 approve/reject/补证由人工在平台完成；
- 57 条配方候选（recipe_candidates.json，SHA 前16 `b4b986d6616cb932`... 实际 `b4b986d661a6e456`）需人工补齐完整键/条件/负例后走配方草稿流程；
- AI 上下文回读验收（S8）需平台 ApiKey 或人工会话导出——本会话 API 401（无 token），如需 AI 直接回读请批准创建一次性只读 ApiKey。

## 四、本 run 未执行项（阻塞标签）

| 项 | 标签 | 恢复条件 |
|---|---|---|
| S5 12 支探针 | BLOCKED_WINDOW | 夜窗批准或用户点名白天豁免 |
| S7 生产 INSERT 114 草稿 | WAIT_APPROVAL | 本批准包第一节获批 |
| S8 人工 approve/confirm | WAIT_APPROVAL（人工） | 治理界面人工操作 |
| AI 回读验收 | BLOCKED_PLATFORM_ACCESS | 一次性只读 ApiKey 批准 |
| 值域 pending 提交 | WAIT_APPROVAL | S5 探针取值后随证据提交（本轮 0 条） |
