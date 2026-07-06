# AGENTS.md

> 本仓库包含**文档资产参考包 + 可运行代码**。
> - 文档：`开发起步包/` 下编号资产 + `数据资产_*/` 资产包 + `tools/`
> - 代码：`backend/`（FastAPI）、`frontend/`（Vue3）、`deploy/`（部署方案）
> - 会话开始前先读本文件，再读 `开发起步包/02_开发环境与资产总索引.md`。

## 仓库性质（最重要）

- **本仓库包含可运行代码**：`backend/`（FastAPI + SQLAlchemy + Alembic）、`frontend/`（Vue3 + Element Plus + Vite）、`deploy/`（部署方案）。代码仓库路径即本目录根。
- 文档资产：`开发起步包/` 下编号资产 + `tools/` + `数据资产_*/` 资产包。
- **已移除**：科研系统(labsop)、三甲 DataX 抽取流程、三甲 V1.3 合规核查。

## 当前阶段目标（第一步，已与用户确认）

**只做 Track A：AI 探库（数据中心 8.216 + HIS）→ 表结构与表间关系 → 关系图谱。**
- 视图生成、内网服务部署**延后**，探库跑通再启动（见 `01` 蓝图）。

**进度**：
- ✅ **连接已打通**：跳板机 8.53（SSH 免密）→ 源库 8.216（thick 模式），DB 版本 11.2.0.4.0。
- ✅ **元数据已采集**：`08_数据中心元数据快照.json`（32 schema / 865 表 / 26894 字段 / 404 视图 DDL）。实测发现数据中心业务库远超初始描述，含 `HIS`(273表)、`CDA`(86表+149视图)、`ODS`(119视图)、`MTL`(老EMR)、`JHEMR`(新EMR)、`YDHL`(移动护理)、`SM`(手麻)、`LIS`、`PACS`、`PORTAL_EMPI`(患者主索引) 等。
- ✅ **表结构与关联已梳理**：`09_数据资产_表结构与关联关系.md`（合并两份已确认文档 + 经 08 校验：33 张核心表 32 张在 8.216 验证通过）+ 机器可读资产包 `数据资产_资产包/`（tables/columns/relationships.csv + catalog.json，由 `tools/build_asset_package.py` 生成）。
- ✅ **核心关系已数据库验证并回写资产包**：`10_关系验证报告.md` / `10_关系验证结果.json`（25 项核心关系；确认 EXAM_MASTER 需拆住院/门诊子集，LAB_TEST_MASTER 需拆住院检验与 VISIT_ID=0/NULL 检验）。`relationships.csv` / `catalog.json` 已带 `validation_level/status/metrics/note`。
- ✅ **视图 DDL 静态关系已解析 + HIS 已分类**：`11_视图关系解析与HIS分类报告.md` / `数据资产_关系图谱/`（ODS 119 视图 → 772 条依赖、732 条候选 join；HIS 273 表分类，66 张被 ODS 引用）。
- ✅ **高频候选关系已排序并完成首批验证**：`12_候选关系验证报告.md` / `12_候选关系验证结果.json`（13 项候选验证，7 条提升入正式资产；`relationships.csv` 现 35 条正式关系）。
- ✅ **手麻人员映射专题已验证**：`13_手麻人员映射验证报告.md` / `13_手麻人员映射验证结果.json`（确认外科医生/助手多为姓名、麻醉医生/护士多为工号、`HIS.STAFF_DICT.NAME` 存在重名；排班表仅 `STATE IN (2,3)` 可强关联手术主表）。
- ✅ **PACS/LIS/YDHL 三库关系已专题验证**：`14_PACS_LIS_YDHL关系验证报告.md` / `14_PACS_LIS_YDHL关系验证结果.json`（PACS 内部关系成立但未发现直接挂 HIS.EXAM_MASTER 的同键；LIS 通过 `BARCODE=TEST_NO` 挂 HIS 检验；YDHL 通过 `MRN=INP_NO` + `SERIES=VISIT_ID` 挂 HIS 住院，护理事实表通过 `PATIENT_UID` 挂 `INPATIENTS`）。
- ✅ **关系补验并回写资产包**：`15_关系补验与资产回写报告.md` / `15_关系补验与资产回写结果.json`（确认 JHEMR 按 `PATIENT_ID+VISIT_ID` 精确挂 HIS 住院；PACS 内部关系、LIS 内部关系、YDHL 深层关系已补验；正式关系 `relationships.csv` 现 47 条）。
- ✅ **HISUSER 业务库已探查**：`16_hisuser业务库探查报告.md` / `16_hisuser业务库探查结果.json` / `16_hisuser业务库元数据快照.json`（确认 `hisuser` 自身 schema 不是业务主 schema；HIS 业务表分散在 `MEDREC/ORDADM/LAB/EXAM/COMM/DRUG_USER/PHARMACY/...` 等 owner；两份 HIS 文档 435 张候选表中 415 张在业务库可见，药房药库 67 张全部可见）。
- ✅ **药房药库与发药主线已验证**：`19_药房药库关系验证报告.md` / `19_药房药库关系验证结果.json`（确认 `DRUG_USER` 新药库/发药申请主线、`PHARMACY` 旧处方/住院发药主线；两套表不是简单一对一同步）。
- ✅ **HIS 主业务 owner 关系已补验**：`21_HIS主业务owner关系补验报告.md` / `21_HIS主业务owner关系补验结果.json`（验证 `MEDREC/ORDADM/LAB/EXAM/INPBILL/OUTPBILL/OUTPADM/INPADM` 21 条源端关系；确认源端口径与 ODS 主线一致，但暂不直接回写 ODS 资产包）。
- ✅ **HIS 源端字段主题与 ODS 覆盖差异已梳理**：`22_HIS源端字段主题与ODS覆盖差异报告.md` / `22_HIS源端字段主题与ODS覆盖差异结果.json`（12 个 owner、1234 张表、19831 字段；105 张源端表与 ODS.HIS 同名覆盖，1129 张未按同名表覆盖）。
- ✅ **HIS 源端资产范围已复核**：`23_HIS源端资产范围复核与下一步计划报告.md` / `23_HIS源端资产范围复核与下一步计划结果.json`（用户确认 `COMM/MEDADM` 纳入；`ST_*`、日志、接口中间表排除；医嘱执行、预交金纳入；`VISIT_ID=0/NULL` 检验/检查按门诊口径）。
- ✅ **独立 HIS 源端资产包草案已生成**：`25_HIS源端资产包生成报告.md` / `25_HIS源端资产包生成结果.json` / `数据资产_HIS源端资产包/`（1234 表、19831 字段、33 条关系；含 `source_owner/table_role/include_status/exclude_reason/ods_same_name_covered`）。
- ✅ **应用整改入口已更新**：原 `27/28` 已归档到 `开发起步包/_archive/`，当前应用整改以 `29_系统功能对照复核与整改计划.md` 为主；后续交接以 `42_下一步工作与整改交接说明.md` 为准。
- ✅ **用户治理口径已沉淀**：`40_数据治理复核口径与方法记录.md` 记录表清洗、待确认表收敛、强制保留表、B/C 关系采纳、D 关系跨系统延后等用户确认规则；后续 HIS/数据中心/周边系统治理分析必须优先沿用。
- ⏭ **下一步**：HIS_READY 最终治理导入包、质量执行器和前端层级图谱基础整改已完成；后续按 `42_下一步工作与整改交接说明.md` 继续执行真实 HIS 源库连通复核、核心表质量分析、数据中心二次优化与 D 类跨系统关系。

**关键捷径**：`03_view_registry.json` + `08` 里的 `V_EMR_*`/`CDR_*` 视图 SQL **本身就是关系样本**——它们编码了 HIS 表如何用 `PATIENT_ID+VISIT_ID`、`TEST_NO`、`EXAM_NO` 等关联。关系图谱以这些视图为种子扩展，不要从零推断。

## 导航

| 想做什么 | 先读哪里 |
|---|---|
| 总入口 / 连接 / 已知坑 | `02`（§2 连接、§4 核心主线、§5 数据坑、§7 资产包） |
| 平台总目标与架构 | `01_平台执行方案.md` |
| **表结构与关联关系（权威）** | `09_数据资产_表结构与关联关系.md`（含置信度 A/B/C、Mermaid 图） |
| 数据库实测关系验证 | `10_关系验证报告.md` / `10_关系验证结果.json` |
| 静态关系扩展 + HIS 分类 | `11_视图关系解析与HIS分类报告.md` / `开发起步包/数据资产_关系图谱/` |
| 高频候选关系验证 | `12_候选关系验证报告.md` / `12_候选关系验证结果.json` |
| 手麻人员映射专题 | `13_手麻人员映射验证报告.md` / `13_手麻人员映射验证结果.json` |
| PACS/LIS/YDHL 三库关系 | `14_PACS_LIS_YDHL关系验证报告.md` / `14_PACS_LIS_YDHL关系验证结果.json` |
| 关系补验与资产回写 | `15_关系补验与资产回写报告.md` / `15_关系补验与资产回写结果.json` |
| HISUSER 业务库探查 | `16_hisuser业务库探查报告.md` / `16_hisuser业务库探查结果.json` / `16_hisuser业务库元数据快照.json` |
| 药房药库关系验证 | `19_药房药库关系验证报告.md` / `19_药房药库关系验证结果.json` |
| HIS 主业务 owner 关系补验 | `21_HIS主业务owner关系补验报告.md` / `21_HIS主业务owner关系补验结果.json` |
| HIS 源端字段主题与 ODS 覆盖差异 | `22_HIS源端字段主题与ODS覆盖差异报告.md` / `22_HIS源端字段主题与ODS覆盖差异结果.json` |
| HIS 源端资产范围复核与下一步计划 | `23_HIS源端资产范围复核与下一步计划报告.md` / `23_HIS源端资产范围复核与下一步计划结果.json` |
| HIS 源端资产包 | `25_HIS源端资产包生成报告.md` / `25_HIS源端资产包生成结果.json` / `开发起步包/数据资产_HIS源端资产包/` |
| **应用整改主入口** | `29_系统功能对照复核与整改计划.md`（原 `27/28` 已归档，仅作历史参考） |
| **用户确认的数据治理复核口径** | `40_数据治理复核口径与方法记录.md`（表清洗、强制保留、待确认清零、B/C 关系采纳、D 跨系统延后） |
| **未完成工作与接手说明** | `41_未完成工作与目录整理计划.md` / `42_下一步工作与整改交接说明.md` |
| 机器可读资产包（导入资产系统） | `开发起步包/数据资产_资产包/`（tables/columns/relationships.csv + catalog.json，关系含数据库实测验证等级） |
| **实测全量元数据（关系图谱底座）** | `开发起步包/08_数据中心元数据快照.json` |
| 现有视图→HIS 表关系（图谱种子） | `03_view_registry.json` |
| 标准化目标表清单 + 数据中心源库 | `06_前置机与数据中心分析报告.md` |
| 待探业务系统 + 探库开放问题 | `07_业务系统与探查开放问题.md` |

> 元数据权威性：手头的表结构文档已陈旧（字段扩展未维护、含废弃表），**以 `08` 快照的活元数据为准**，手文档仅作命名/含义参考。快照可由跳板机重跑 `harvest_stage2.py` 重新生成。

## 探库/写 SQL 时的硬约束（高代价易错点）

不读会静默出错的事实（综合自多份文档）：

1. **本机 Windows 不能直连数据库**，所有 DB 操作必须经跳板机 `10.10.8.53:40022`（见 `02` §2）。账号密码不要写入新代码仓库；内部凭据按既有安全渠道获取。
2. **源库 Oracle 旧版**：`oracledb` 必须 thick 模式 + `/opt/oracle/instantclient_21`，否则 `DPY-3010`；旧版不支持 `FETCH FIRST`，用 `ROWNUM <= N`。
3. **`HIS.LAB_RESULT` 约 1 亿行**，查询必须用 `TEST_NO` 子查询限定，禁止全表扫描；大表（>1000 万行）只采元数据。
4. **`HIS.OPERATION.OPER_ID` 全为 NULL**，手术主从关联改用 `SM.MED_OPERATION_NAME`。
5. **`HIS.EXAM_MASTER.EXAM_CLASS` 存中文**（`'CT'`/`'磁共振'`），不是字典内码——过滤按中文，不要 join 字典。
6. `EXAM_REPORT` 无 `PATIENT_ID`，必须经 `EXAM_NO` 关联 `EXAM_MASTER`。
7. HIS 万能主键：`PATIENT_ID + VISIT_ID`（住院）/ `OUTPATIENT_NUM`（门诊）；检验 `TEST_NO`、检查 `EXAM_NO`。
8. 跨库捷径：前置机已建 DBLINK `sjzx` 指向源 ODS，可 `SELECT ... FROM V_EMR_xxx@sjzx`。

## 值域映射模式（写视图时统一写法）

```sql
nvl((SELECT zd.国标编码 FROM cda.cda_dictionary zd
     WHERE zd.字典名称='性别代码' AND zd.院内编码=pmi.sex), '9')
```
- 所有 `V_EMR_*` 视图依赖 `CDA.CDA_DICTIONARY`（院内码→国标码）。
- 固定机构字段：`'49557032X' AS ORG_CODE`、`'山东省第二人民医院' AS ORG_NAME`、`'370104' AS DISTRICT_CODE`；ID = `'49557032X'||'|'||patient_id||'|'||visit_id`。（历史文档里的 `YLV21051` 已过期，勿用。）

## 已知严重数据问题（详见 `02` §5）

- `EMR_ANES_AFTER_RECORD` ID 重复约 30%；`EMR_OUTPATIENT_RECIPE_ITEM.OR_ID` 100% 孤儿；`EMR_OUTPATIENT_DIAG` 0 行；4 张表 `ADMISSION_ID` 缺失。

## 安全红线

- 源库一律只读，仅 `SELECT`，禁止任何 DML/DDL；高风险操作需人工确认。
- 连接密码**不要写进任何新代码仓库或 git**；用 `.env` + 密钥管理，`.gitignore` 排除。本快照文档里的明文凭证仅为查阅方便。
- 姓名/身份证/电话/地址**脱敏后**才能进 AI、日志、报告。
- 探库任务夜间执行并加超时。

## 文档管理与目录维护（强制，每次会话执行）

> 文档量大且持续增长，必须维护**单一权威目录**（`开发起步包/README.md` 文件清单表）。
> **任何 AI（含本助手）每次会话开始时，先做"目录自检"再动文档；每次新增/废弃文档必须同步清单。不遵守 = 后续 AI 无法定位资产。**

### 1. 启动自检（会话第一步，必做）
- 读 `开发起步包/README.md` 文件清单表（权威目录）。
- 用 Glob 列 `开发起步包/*` 实际文件，与清单比对：
  - **孤儿文件**（实际存在、清单未登记）：补登记；若判断为废弃则迁入 `_archive/`。
  - **幽灵条目**（清单有、文件不存在）：修正或删除该行。
- 发现不一致**先修正目录**，再开始正文工作。

### 2. 新增文档（强制 3 步，缺一不可）
1. **编号**：续用当前最大编号 +1（查清单尾部），前缀 `NN_中文名.md`；配套结果文件用同号 `_结果.json`。
2. **登记**：立即在 README 文件清单表追加一行（序号 / 类别 / 文件 / 用途）。
3. **归类**：文档首行加 `> 类别：xxx`（类别定义见 README），并确认归入清单正确分组。

### 3. 归类汇总
- 文件清单表带"类别"列；类别定义维护在 README。
- 现有类别：`索引` / `方案` / `环境` / `元数据` / `表结构` / `关系验证` / `部署` / `待办`。
- 新增类别须同步更新 README 类别定义与本节。

### 4. 无用文档迁移（只迁不删）
- 过时 / 被取代 / 废弃 / 临时文档 → 移入 `开发起步包/_archive/`。
- 在 README "归档区" 记录：原序号 + 文件名 + 归档原因 + 日期。
- 主清单不再列归档文件；迁移前确认无其他文档引用。

### 5. 文档体例
- UTF-8 Markdown，中文文件名 + 编号前缀（可跳号）。
- 以"索引 + 源文件路径"组织，不堆全量内容。
- 凭据脱敏；明文密码不进新代码仓库。
- 后续建代码仓库：脚本 ASCII 描述性命名（`verify_*/check_*/test_*`），4 空格缩进。

---

## 代码开发约束

> 以下约束适用于 `backend/`、`frontend/`、`deploy/` 目录的开发。

1. **源库只读**：所有数据库连接默认只读 `SELECT`，禁止 DML/DDL。写操作必须通过 `asset_action_executors` 白名单 + 审批。
2. **凭据脱敏**：密码、Token、身份证、姓名、电话、地址**不写代码、不写日志、不进 git**。审计写入前脱敏。
3. **单一 schema**：所有新表继续在 `asset` schema 内用 `asset_<模块>_<实体>` 前缀，不得拆物理 schema。
4. **Alembic 手写**：迁移必须手写 `upgrade()` 和 `downgrade()`，禁用 `--autogenerate`。
5. **AI 不执行写操作**：AI 工具仅调用只读探查端点 + 强制审计，不接入 `asset_action_executors` 写操作执行器。
6. **大表禁全扫**：`HIS.LAB_RESULT` 等大表必须用 `ROWNUM <= N` 或子查询限定。
7. **保留旧表**：`asset_api_keys`/`asset_table_owners`/`asset_business_terms`/`asset_metadata_snapshots` 是旧 MVP 表，保留不删。
8. **前端不改现有路径**：`/relations/{id}/review`、`/dict-medical/*` 等现有路径保留不变。
9. **前端技术栈与约定**：基于 `pure-admin-thin` 模板，Vue3 + Element Plus + Pinia + Tailwind + Vite + TypeScript。typecheck 同时跑 `tsc --noEmit` 和 `vue-tsc`，必须两者都过。API 层在 `src/api/*.ts`，按模块分文件（asset/dict/identity/metadata/ops/routes/user）；新增接口优先扩展现有文件而非新建。路由模块在 `src/router/modules/`，视图在 `src/views/<模块>/`。

### 验收命令

后端：
```powershell
cd F:\python\数据资产\backend
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m alembic upgrade head
```

前端（**必须用 pnpm**，仓库 `package.json` 有 `preinstall: only-allow pnpm`，锁文件为 `pnpm-lock.yaml`，用 npm/yarn 会失败或引入幻影依赖）：
```powershell
cd F:\python\数据资产\frontend
pnpm install
pnpm run typecheck
pnpm run build
```
