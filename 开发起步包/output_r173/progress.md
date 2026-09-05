# r173 执行进度（逐批追加）

## T0 环境基线（2026-09-01，完成）
- HEAD=96ed0270ad854d32008ba6c5b792d1de87112714（=171 收口提交，与 171 报告一致）；git status 落档 baseline_hashes_t0.txt（他人域 16 文件 hash-object 存档）。
- 15432 隧道已在监听（171 遗留，未新建 SSH）；APP_TEST_DB_URL 按 162 §1.2 从服务器 env 推导（凭据仅进环境变量，工装 get_test_db_url.sh 运行时取，零落盘零回显）。
- 测试库连通：data_asset_test，asset schema 103 张表（171 T2.5 重灌态：12702 业务表数据/1329 关系在 asset_* 业务表内）。
- openapi.json 实测拉取（TestClient 离线 app.openapi()）：**345 路径 / 393 操作**（GET 191 / 写 202），34 个 tag。routes_list.json 落档。
- 外部 pytest 进程清查：0 个在跑。
- 三清单：routes_list.json（393）、api 模块（src/api/ 14 文件，其中 types.ts 非请求）、views 58 页（weak_pages.json 含全量）。
- S0 三产物：s0_expectations.json（期望码表）、s0_blacklist.json（54 黑名单端点+3 流式鉴权-only）、weak_pages.json（6 薄弱页：error/404、error/500、identity/authorizations、identity/departments、identity/roles、query-center/accuracy）。
- 黑名单定性抽查：/ai/ai-sql/generate 实调 HospitalLlmClient（LLM 铁证，ai.py:925+）；/quality/checks/run 默认 include_sql=False 仅元数据但属重活。
- 未跑全量 pytest（基线引用 171 报告 1341/1s）→ 无重灌义务。
- .gitignore 追加 `backend/_r173_work/`（唯一允许仓库改动，已在 .gitignore 登记说明）。

## T1 C 线（进行中）

## T1 C 线（完成）
- 解析覆盖率 99.0%（286/289 occurrence，3 条为注释提及）；路径/方法级真实漂移 **0**（15 未匹配全为变量前缀/动态 action，人工逐条裁决后端实路由均存在）。
- 字段级静态可比对仅 9 对（后端 ApiResponse[dict] 泛型广泛）；1 条 flag 定性为平行类型双声明（P3），非漂移；运行时字段交叉核验转 S 线搭车。
- 关键工具事实：FastAPI 新版 _IncludedRouter 需展平 original_router；/api/v1/health 为 include_in_schema=False 别名（非漂移）。详见 contract_diff_report.md。

## T2 A 线（完成）
- 10 规则全跑+定性：P2=6（同页按钮级 v-perms 不一致：probe-findings:238、value-domains:269、dict/general:191/218/247/288）；P3=24 死 API 封装+4 页零按钮级策略+console 2 条+as any 70 聚合；v-html/硬编码/空catch/敏感串/内联事件/菜单死码全部 0 真命中。
- 详见 frontend_scan_report.md。

## T3 S 线（完成）
- 主探针：1328 次/395 路由；**5xx=0、真实鉴权旁路=0（6 个 2xx 全为 PUBLIC_EXACT 设计）、真实契约矛盾=0**；CSRF 外源 Origin=403 实证；黑名单 63 端点（T3 中补录 12 个，W4）从未真实执行。
- 写成功路径：38 用例 37/38 PASS（审计写入 16）。**P1 根因链**：首轮 11 端点 500 → engine handle_error 捕获 asset_govern_audit_logs_pkey duplicate → max(id)=194 vs seq=17（import170 重灌未重置序列）→ 修复 102 条序列后复跑全绿（根因唯一性证明）。
- **P2-1**：GET /systems 仅返回 CANONICAL_SYSTEMS（asset_catalog.py:205-216），新建系统 200 但列表永不显示（systems 页 152/243 消费）。
- P3-5：recipes create 静默接受非法 primary_tables。

## T4 补充线（完成）
- RBAC 34×2=68 检查 0 违规；全局健康 12/12 无 5xx；typecheck exit 0；build 49.10s（gzip 183.1/65.8 kB）；空库 alembic 需预建 schema（P3-6，补建后 103 表 c1d2e3f4a5b6）；只读 lint 4236 errors（4216 prettier + GraphToolbar 20 处 no-mutating-props=P3-3）；临时库 data_asset_test_r173empty 已 DROP。

## T5 V 线（完成）
- 6 薄弱页 18 条源码断言全过（output_r173/vtests + vitest.r173.config.mjs，不进门禁）——薄弱页结构质量达标，0 新问题。

## T6 交卷（完成）
- 产出：173_全栈模拟测试_问题清单.md（P0=0 说明/P1×1/P2×2/P3×8/不确定项×3/修复建议）+ _结果.json + README 目录行+更新记录 + 55 📌 行（措辞按任务书）。
- 终检：他人域 16 文件哈希与 T0 基线一致；r173 探针数据/密钥清理完毕（leftovers=0，keys 残留 0）；审计表 +76 行 append-only 留痕；171 完成态零改写。
- DoD：四线+三补充证据文件齐；四桶计数齐（5xx=0/旁路=0/漂移=0/写断言失败=1→升级 P2-1）；不确定项非空；P0/P1≥3 条或说明（P1×1+P2×2，P0=0 已书面说明）。
