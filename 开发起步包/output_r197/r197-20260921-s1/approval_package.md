# 197 S7 批准包（r197-20260921-s1，待批准，未执行平台写入）

> 类别：任务证据　日期：2026-09-21　状态：**待批准**——以下生产写入动作均未执行；批准前仅交付 payload/diff 与预演结果。

## 1. 申请的批准动作（两项，可分别批准）

### A1 关系草稿生产导入（asset_relation_reviews +167 draft）

| 项 | 内容 |
|---|---|
| 目标平台 | 8.83 data_asset（生产）`asset.asset_relation_reviews`，scope=`r197_intake` |
| 准确数量 | **新增 167**（candidate 132 / partial 35；验证态：not_run 148 / passed_in_scope 19）；重复 0（见幂等） |
| 不导入数 | 238（全有理由，见 §3；不丢失——405 族全量保留 `relations.jsonl` 本地证据） |
| payload | `import_payload.json`（211,280 字节，SHA-256 前16 `690a0a7b10e68224`，row_count=167） |
| 字段与状态 | relation_scope/from_system_code/from_table(SCHEMA.TABLE)/from_columns(+连接)/to_*/join_condition/relation_desc_cn/business_logic_cn（粒度+条件+风险）/confidence=**C**（历史 SQL 证据上限，passed_in_scope 不升级）/review_status=**draft**/source_evidence（run_id+relation_id+语句数+文件+验证注记+探针 UID） |
| 幂等依据 | NOT EXISTS(scope+upper(from_table)+from_columns+upper(to_table)+to_columns)；隔离库预演 PASS（首插 167/重放 0/反向 1/单事务回滚干净/清理 168 零残留/他人行不变）——`rehearsal_result.json` |
| 备份 | 批准后执行前：`pg_dump data_asset` → `/opt/data-asset/backup/data_asset_pre_r197_<日期>.dump`（195 同款） |
| 执行方式 | 单事务幂等 INSERT + 行数守卫（新增数=167 或 0 已存在）+ 逐批 ID 回读（674 起连续）+ 审计行 |
| 撤销方案 | `DELETE FROM asset.asset_relation_reviews WHERE relation_scope='r197_intake'`（草稿未被人工处理前可整批撤销；approve 后按 ID 逐条人工处理） |
| 审计与回读 | 导入后回读：总数 674→841、scope 计数 167、ID 连续性、draft 状态、中文条件字段完整性；审计记录写入 |
| 临时身份 | 无需新身份：SSH 公钥通道 + postgres（与 195 相同）；不触碰 approved 行与他人草稿 |

### A2 配方草稿创建（asset_relation_recipes draft ×13）

- 路径：`/api/v1/recipes` 创建 **draft**（RCP-S3-01..08 + RCP-S5-01..05；`recipe_payload.json`，SHA-256 前16 `763f565a17ba3642`）；**禁止 AI approve/activate**，版本状态机留人工。
- 若 API 通道不可用可等价 SQL 插入 draft 行（同批批准、同审计）。

### A3 值域候选提交（pending ×5，随 A1/A2 一并或单独批准）

- `value_domain_candidates.json`（SHA-256 前16 `e9c715ec331f061d`）：OPERATION_SCALE（含 `'一 '` 尾随空格变体）、STOP_FLAG、EXAM_CLASS（17 中文值）、ITEM_CLASS/OPER_CODE 多义分流——**仅提交 pending 证据，确认人工**。

## 2. 查重基线（2026-09-21 当日三刷）

- 正式关系 1329（无漂移）；评审草稿 674（draft 666，195 的 114 在内）；配方 65 全 draft；confirmed 值域 26。
- 本批 167 行已对 ①405 族精确/配对集/变体三层查重 ②1329 正式（existing_supplement 144+5 只补证据不导入）③99 条同构草稿（1 条同边草稿跳过）④payload 内部（8 对列序变体只留首建、2 对连接类型变体只留首建）。

## 3. 不导入 238 的构成（均有本地证据保留）

| 类别 | 数 | 说明 |
|---|---:|---|
| 平台正式已覆盖（补证据） | 144 | existing_supplement——正式关系已有，仅 source_evidence 留档 |
| D 类跨源未定位 | 41 | ZY_ZYYZXXMX/EXP_*/OUTP_PRESC 等，待对象定位 |
| 验证失败不作正向边 | 14 | VISIT_ID/RCPT_NO/VISIT_NO/SERIAL_NO 单列、手术直连、名称 JOIN、药价多价、库存两列、结算两列 |
| 列序变体合并 | 8 | ISS-S5-ORDERVAR 8 对后建族并入首建 |
| 来源受阻 | 13 | 临时表/中文列/PBL-PBD 相邻域 |
| 端点未解析 | 5 | 解析后仍有别名归属不明 |
| 负例 | 4 | S3 2 条 + S5 2 条单位伪边/字典误用 |
| 运维视图 | 4 | V$/DBA_* 非业务资产 |
| 验证零样本 | 2 | 批次表近窗无数据 |
| 平台同构草稿已存在 | 1 | 跳过防重复草稿 |
| 连接类型变体（payload 内） | 2 | inner/outer 只留首建 |

## 4. S6 未执行探针清单（无遗留）

37 支探针全部有执行或受阻记录（42 条 SQL：39 executed、Q14 通道超时后 Q14b 样本重试通过、Q17 失败即结论=ID_NO 列不存在、Q27/Q28 近窗零行后按数据覆盖窗重试通过）。无未批准未执行探针。

## 5. 批准后执行顺序（一次会话内完成）

1. 备份 pg_dump → 2. A1 单事务导入+守卫 → 3. A1 回读（数量/ID/状态/中文完整性）+ 审计 → 4. A2/A3 → 5. 草稿隔离验证（draft 不进 recipes/ai/context 与 system-context 正式段=正常）→ 6.（人工审核发布后另会话）八类 AI 回读用例。
