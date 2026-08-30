• 我先读取两份计划与对照文件，然后逐条审查。

• 我并行派出探查代理核对后端/前端既有体系，同时自己读 163、164 对照文件。

• 四路核查已完成（149 §8 与 value_domains.py 实际端点、quality.py 与模型风格、163/164/162 铁律与基线、前端路由/权限/mock/测试现状）。以下为逐条审查意见。

  ---

  # 【165 计划】数据问题 AI 探查与入库

  ## 同意项

  **1. 同意 §1 铁律与 §6 等待域设计。**
  - §1.3「生产建表 apply 与生产首轮探查归等待域（备份→dry-run→apply→二次 dry-run→/health）」与 163 §2 Q3/§7 W2 链逐字一致；X1–X4 全部交用户授权，符合 163 §1 STOP 白名单第 3 类。
  - §1.4「AI 只写 open/last_seen/relapse_count，终态仅人工」与 149 §3「AI 仅可 submit，confirm 仅人工」、AGENTS.md「AI 不执行写操作」一脉相承。
  - §1.2 零患者明细、§5「R-DOM 只写 pending 证据，永不自动 confirm」与 149 既有权限（ai_user 仅 read+submit）闭环。

  **2. 同意 §3 基线数字引用。**
  T1（83.2%，315,952/379,980）、T2（5.97%，3,821/64,028）、T5（99.93%/35.5%）、T10（六档差 0–30、HIS NULL 689）、T12（code1 94.6%）与 164 §2 实测逐项吻合，无编造。承接关系（165←164 R9/R10）与 164 v1.1 头部移交标注一致，属实。

  **3. 同意 §2 与 QualityFinding 并存不合并的切分。**
  QualityFinding 现有状态机（open/assigned/confirmed/fixed/rechecked/resolved/ignored，`schemas/quality.py:103-106`）无 `false_positive`，目标定位是表结构治理六层字段，与跨系统对账域确实不同构，硬合并代价大于并存。

  **4. 同意 §4 执行器复用 db_connectors 只读门禁的方向。**
  `services/db_connectors.py` 的 `validate_readonly_sql`（SELECT/WITH 开头、禁多语句、禁注释、大表禁无 WHERE）、`MAX_READONLY_ROWS=10000`、Oracle `ssh_jump` 模式均可直接服务模板执行；`services/quality_sql_runner.py:59,118` 已有"服务层按 AssetDataSource 建连接器"先例。

  **5. 同意 E3「偏差>5% 记 WARN」口径**，与 163 §1「其余偏差一律 WARN 落 exceptions.json 继续」一致。

  ## 反对项

  **6. 反对 §2 复发语义与唯一键的现有表述——二者存在逻辑矛盾。**
  原文：唯一键 `(probe_type, system_pair, object_desc, metric_name, window_start)`；复发语义「status=resolved 的行在**同键**新 run 再次出现 → relapse_count+1」。
  - 理由：唯一键含 `window_start`，而新 run 的时间窗必然前移（探查的价值就在新月新窗）。若"同键"含 window_start，则复发行永远不会命中旧 resolved 行——relapse 永不触发；若复发判定实际忽略 window_start，则唯一键定义与判定键不一致，且同键同窗幂等更新与跨窗复发是两套键。
  - 风险：执行 AI 按字面实现后，E5 复发验证要么无法复现（构造不出复发），要么绕开唯一键另写一套查询，设计与实现脱节，"改了又改回来"这一核心诉求落空。
  - 建议：显式拆成两键——幂等键（含 window_start，管 upsert）与复发键（不含 window，管 relapse 检索），写进 §2。

  **7. 反对 §3 T8 模板设计，与 §1.2 自相矛盾。**
  原文 T8：「近 90 天住院号在 JHEMR 命中率（**服务端聚合 IN，≤1000**）」；§1.2：「证据 SQL 本身**不得含患者标识字面量**（一律参数化/聚合输出）」。
  - 理由：住院号是患者标识。IN 列表展开 ≤1000 个住院号字面量后，该 SQL 若作为 `evidence_sql` 入库，即单次写入上千条患者标识进平台库——恰恰踩穿本计划自己定的红线，且 166 F4 会把 evidence_sql 原样渲染到界面，泄漏面扩大。
  - 风险：安全红线在"模板设计"环节就被合法化，后续批次（E2 定型、E3 执行）照章办事即违规。
  - 建议：T8/T9 改为源侧子查询（两库各自聚合后经受控通道比对计数），或证明 IN 列表只存在于运行时参数而不落 evidence_sql。

  ## 疑问项

  **8. 疑问 §4 run_probe.py「复用 db_connectors」与夜间窗口的执行落点。**
  - 理由：scripts/ 现有采集脚本（`harvest_oracle_readonly.py:114-131`）均**直连**目标库、不走 db_connectors；db_connectors 凭据解析依赖平台库里的 AssetDataSource 行（`services/credentials.resolve`）。脚本在本机 Windows 跑时需要隧道+平台库可读，而 AGENTS.md 红线是"本机不能直连业务库、探库夜间在跳板机侧执行"。计划未说明 run_probe.py 跑在哪台机器、凭据从哪来。
  - 风险：E3 到夜间才发现通道不通（跳板机上没有 platform DB 配置/隧道方向不对），首轮探查流产。
  - 另：db_connectors **禁 SQL 注释**，模板若按 AGENTS 惯例写【值域待确认】注释会被门禁拒绝——需明确模板 SQL 无注释。

  **9. 疑问 §2 `object_desc` 入唯一键的物理可行性。**
  `object_desc` 是自由文本（如 "EXAM_MASTER.DOCTOR_USER↔SYS_EMPLOYEE"），PG  btree 索引单键约 2704 字节上限，描述稍长即建索引失败。
  - 风险：E1 迁移在隔离库 apply 时才爆错。建议 object_desc 定长（如 varchar(512)）或唯一键改用 digest 列。

  **10. 疑问 E1 测试库前提未写明。**
  conftest 强制 `APP_TEST_DB_URL`（含 "test"，禁 `APP_DB_URL`），163 铁律规定测试库**仅限**隧道 data_asset_test。计划验收命令只写 `pytest -k probe`，未提隧道前置。
  - 风险：执行者无隧道环境下 E1 直接 BLOCKED；虽符合 STOP 口径，但属可预见的卡点，应在 E1 前置条件里点名 162 §1.1 隧道搭建步骤。

  **11. 疑问 E4 权限码 `probe.finding.read` 的登记责任未闭环（与 166 交叉矛盾，详见 166 节第 8 条）。**
  按 149 先例（`b0c1d2e3f4a5_..._149.py:23-36`），新权限码 = RESOURCE_CATALOG + ROLE_DEFAULT_PERMISSIONS + **手写 Alembic 种子**三件套；E4 的 403 测试在隔离库就要用到该码，而 165 全文（含 X1）只说"两表+权限码种子"，未说 RESOURCE_CATALOG/security_audit 硬编码清单（`test_security_audit.py:64-66`）同步归谁。

  ---

  # 【166 计划】值域与探查问题展示导出

  ## 同意项

  **1. 同意 §3「后端增量全部为薄层」的复用判断。**
  - 值域端点核实齐全：列表（含 system_code/schema_name/table_name/column_name/code/domain_kind/status/conflicted 筛选，`value_domains.py:145-199`）、详情含全部证据、版本历史、PATCH confirm/deprecate/resolve-conflict（433-539），前端确实零新增值域后端即可支撑 F1/F2/F3。
  - F1 接入点真实存在：`src/views/asset/table-detail/index.vue` 关联关系卡片后追加 el-card、`loadAll()` 挂请求即可，无结构障碍。
  - 导出可照 `src/api/dict.ts:109-111` blob 模式；openpyxl 已在 requirements.txt:47，xlsx 无新依赖，符合 §1「不新增迁移/依赖」精神。

  **2. 同意 F5 状态流转走独立写端点 + RBAC + 审计。**
  既有 QualityFinding 的 PATCH findings **无状态机校验**（任何字符串直接赋值，`quality.py:1123-1134`）、质量域不写 GovernAuditLog——166 为 probe findings 新建带状态机校验与审计的 transition 端点，是对既有短板的正确规避而非盲目复刻。

  **3. 同意 F7 中 ai_user 仅 read 的授权。**
  与 165 §1.4「AI 不裁决终态」、149 ai_user 不得 confirm 的既有矩阵一致，DoD 中"ai_user 无 manage 权实证"可执行（有 `test_value_domains_api.py` ai_user 403 先例）。

  **4. 同意 §5 空态约定与并行开发策略。**
  "无数据显示等待首轮 run、不显示假 0"与 165 生产首轮在 X2 等待域的现实匹配，避免界面误导。

  ## 反对项

  **5. 反对 §1.3「复用 146 E7 audit 导出模式」的表述——既有模式达不到计划自列的硬约束。**
  核实 `governance.py:383-421` 的 audit 导出实况：有列白名单（无 before/after_data）✓、5000 上限 ✓；但**无导出审计留痕**（导出本身不写 GovernAuditLog）、**文件名固定** `audit-logs.csv` 无时间窗、**无防公式注入转义**、**端点未挂 require_permission**。
  - 理由：§1.3 列的五条硬约束里三条（留痕/时间窗文件名/防注入）在"被复用"的对象上不存在，还有一条隐患（无权限码）计划未提。
  - 风险：执行 AI 若按"复刻"理解，直接拷贝 governance.py 实现，产出物恰好丢掉计划自己要求的三条硬约束和一个权限码，D4 验收才发现返工。
  - 建议：表述改为"参考其流式 CSV 骨架，权限码/留痕/文件名/防注入为本计划新增要求"，并把"导出端点必须挂 require_permission"显式补进 §3。

  **6. 反对 §5 联调开关命名 `APP_PROBE_API_READY`——在前端根本读不到。**
  - 理由：Vite 仅暴露 `VITE_` 前缀变量（本仓未改 envPrefix），先例只有 `VITE_ROUTER_HISTORY`、`VITE_DEV_API_TOKEN`；全仓 grep `APP_PROBE_API_READY` 0 命中。且 mock 基建是 vite-plugin-fake-server，**仅开发环境启用**。
  - 风险：按原名实现则开关恒为 false，联调时 mock 永不切换，D3/D4 的"165 完成后联调一轮"流于形式。
  - 建议：改 `VITE_PROBE_API_READY`，或直接指明用 `frontend/mock/` 新增 fake route（仿 `mock/login.ts`）。

  **7. 反对 D1 验收「路由守卫测试（无权限 403）」的现有写法。**
  - 理由：前端无任何 import 真实 router 的测试先例——真实 router 模块加载即执行副作用（读 localStorage、发请求），jsdom 下不可直接挂。
  - 风险：执行者为过验收要么自建 router 测试基建（超范围），要么弱化断言（163 明令禁止为过测试弱化断言）。
  - 建议：改为既有可行的两种之一：测 `router/utils.ts:428` 已导出的纯函数 `filterNoPermissionTree`，或按 `plan146StageB-E.test.ts` 先例做路由模块源码断言（`toContain("auths:")`）。

  ## 疑问项

  **8. 疑问（与 165 交叉）权限种子的双重所有权矛盾。**
  - 165 §6 X1 写「生产建表 apply（**两表+权限码种子**）」——暗示种子随 165 迁移走；
  - 166 §1.4 写「**权限码种子走幂等 seed，非迁移**」、F7 写「RESOURCE_CATALOG+ROLE_DEFAULT 幂等 seed」；
  - 而 149 先例是**手写 Alembic 迁移**做种子（`b0c1d2e3f4a5_..._149.py`），并非独立幂等脚本。
  - 三方口径互不一致。风险：两计划并行执行时，权限码被各种一遍（幂等则浪费、非幂等则冲突），或都以为对方负责导致 `probe.finding.read` 在 165 E4 的 403 测试时就缺码。另注意 166 F7 默认授 quality_admin read+manage，偏离 144 §8.4「新码默认仅授 platform_admin」惯例——可以偏离，但应在计划里声明是刻意决策。
  - 建议：明确唯一责任方（建议归 165 E1 迁移内种子，166 F7 只做 RESOURCE_CATALOG/ROLE_DEFAULT/security_audit 清单同步与验证），并在两份计划里互相引用同一句话。

  **9. 疑问 165 E4 与 166 mock 之间缺一份钉死的 API 响应契约。**
  165 E4 只列了端点路径和筛选参数，未定义响应包络（分页结构是 `{items,total,page,page_size}` 还是别的）、字段命名（`first_seen_run` vs `firstSeenAt` 风格）、错误格式。166 §5 让前端按 mock 先行开发。
  - 风险：mock 按猜测的契约写，165 E4 按另一套实现，联调轮变成返工轮；§5「联调截图入报告」无法防止契约漂移，只能事后发现。
  - 建议：在 165 E4 补一段响应 JSON Schema（或明确"沿用现有列表端点分页 Schema"），166 mock 以该段为唯一依据。

  **10. 疑问 F2「version 筛选」后端不支持。**
  后端列表端点无 version 维度筛选参数（145-158 行参数清单无 version）；主表也无 version_no 列（由 `vds.version_no_of` 计算）。
  - 风险：界面做出筛选器但请求无效或需全量拉取前端过滤，违背 §1.2「值域 API 全用 149 既有端点」的自我约束。建议删掉该筛选项或标注"前端过滤"。

  **11. 疑问 F5 状态机规格不完整。**
  只定义了 open→任一终态、resolved→false_positive 禁止；未定义 confirmed↔resolved、confirmed→false_positive、false_positive→resolved 是否允许，也未定义与 165 复发机制（resolved→open 自动翻转）叠加后"复发行只读提示走重新裁决"的具体交互。
  - 风险：D3「状态机测试≥4」的自由度过大，实现者与验收者对"状态机"理解可能不同。建议补一张完整迁移表。

  **12. 疑问 F4 展示 evidence_sql 的二次确认缺失。**
  界面直接代码块渲染 evidence_sql（含复制按钮）。该设计的安全性完全押注在 165 §1.2 的执行上，而 165 T8 目前自带矛盾（见 165 节第 7 条）。
  - 风险：一旦 165 侧防线失守，166 侧无任何兜底（如不渲染疑似标识的模式检测）。建议在 F4 加一句"evidence_sql 展示前过 `sanitize_text`/mask_sensitive 同款脱敏管道"（质量域已有 `services/data_masking.py` 先例），成本极低。

  ---

  ## 总体结论

  - **165**：方向、铁律、基线引用均扎实，但有 2 个必须先改的硬伤——**复发语义/唯一键矛盾（§2）**和 **T8 住院号 IN 列表违反自家零患者明细红线（§3）**；另有执行通道落点与权限码登记责任两个待澄清项。
  - **166**：复用判断基本准确，最大问题是**对 146 E7 导出模式的能力高估**（三条硬约束在"被复用"对象上不存在）和**mock 开关命名技术性失效**；权限种子归属需与 165 裁定唯一责任方。
  - **两计划间**：唯一实质性顺序矛盾是权限码种子（165 X1 迁移种子 vs 166 F7 幂等脚本 vs 149 Alembic 先例三方口径）；API 契约靠口头对齐、无钉死的响应 Schema，是联调阶段最大返工源。

  本次审查为纯只读，未修改任何文件，未读取 review/ 目录。

