# L0 域归属与冻结清单（2026-09-25）

> 依据：接手时 `git -c core.quotepath=false status --short`（132 脏 + 25 未跟踪）。
> 规则：本会话不修改、不暂存、不回退他人域文件；允许只读检查。冻结清单是 L3 候选一致性核验和 Git 分域整理的基准。

## 1. plan139 协作者域（禁止触碰、禁止混入 D2 候选）

- `backend/app/services/db_connectors.py`（MysqlConnector ssl_disabled hunk；transport_kwargs 函数块已于 d483861 入库，剩余 hunk 仍为 WIP）
- `backend/app/api/v1/metadata_changes.py`
- `backend/app/api/v1/systems.py`
- `backend/app/services/identity_source_collector.py`
- `backend/app/services/medical_code_push.py`
- `backend/app/services/medical_code_source_collector.py`
- `backend/app/services/quality_sql_runner.py`
- `backend/tests/conftest.py`
- `backend/tests/security_audit/test_fine_grained_write_permissions.py`
- `backend/tests/plan139/test_mysql_runtime_ssl.py`（未跟踪）

> 上述 services/api/tests 修改与 plan139 六调用方特征吻合（55 顶部 r200b 记录）。若 L3 核验发现其中混有 D2 改动，先做 hunk 级分离分析，无法安全分离则暂停该步骤并记录。

## 2. D2 候选域（202 会话产物，L3 冻结与发布核验对象）

- `backend/app/api/v1/ai.py`（195 缺陷1：AI 路由精确豁免 + system-context 确定性排序）
- `backend/app/main.py`（195 豁免清单）
- `backend/tests/plan195/`（未跟踪，HTTP/契约测试）
- `frontend/src/views/dict/medical/components/PushWizard.vue`（page_size=200 + 全动作预览）
- `frontend/tests/pushWizardAllActionPreview.test.ts`（未跟踪 Vitest）
- `开发起步包/output_r195/r195-20260919-084932/`（D2-4 产物 + 执行报告 M + 发布候选包_D2_20260923.md 未跟踪）
- `开发起步包/output_r200/r200-20260922-remediation/browser_t27_t28/`、`cases_recheck_20260923.json`、`待批准清单_剩余项_20260923.md`（未跟踪）
- `开发起步包/output_r200/r200-20260922-remediation/cases.json`、`执行报告.md`（M）

## 3. output_r189 删除现场（保护，不 restore 不提交删除）

- 82 个 ` D` 已跟踪文件（目录磁盘不存在）
- 处置按 203 §4.2：HEAD 恢复到临时路径→敏感扫描→选择性回填（L2）

## 4. 文档状态域（L2 纠偏对象，只改当前状态段）

- `开发起步包/55、README、INDEX、189、191、193、195、200`（M）
- `开发起步包/199、201、202、203`（未跟踪）
- `开发起步包/output_r186/r0_route_inventory.json`、`output_r193/B01/B01_试点契约.md`（M，历史会话产物，非本次范围）

## 5. 本机工具残留（不属于任何任务域，不动）

- `.v2c/`、`.video_agent/`、`.workbuddy/`、`.zcodeignore`、`CacheDB.jar`、`backend/pure_logic_test.db`

## 6. L0 结论

- 目录基线 error 1 / warn 5，与 203 编制时一致，无新增。
- 测试环境 pure_logic_ready：本轮数据库集成测试受阻，只跑纯逻辑门禁；受阻项记录不跳过。
- output_r189 删除归属无法确定 → PARTIAL_EVIDENCE_MISSING；HEAD 内容可恢复；批次1/2 工单需 L2 重建。
- D2 证据链（31/83 分单、查重、发布候选包、浏览器 v2）实际完好，仅 189 部分缺失。
