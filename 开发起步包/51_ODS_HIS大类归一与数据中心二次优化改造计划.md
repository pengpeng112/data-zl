# ODS/HIS 大类归一与数据中心二次优化改造计划

> 类别：方案
> ⏳状态：🟡部分完成 | 已完成：T7 归一优化包已生成（2099 表/46725 字段，D 类关系独立） | 下一步：核验后端字段、五层导航与图谱三类图层 | 最后更新：2026-07-13
> 📌多AI协作：动手前先读 `AGENTS.md`、`README.md`、`55_系统未完成事项统一执行计划.md` 和 `40_数据治理复核口径与方法记录.md`；只接续未验收部分，不重复生成已有资产。

## 1. 背景与目标

当前平台已具备资产门户、关系图谱、HIS_READY 治理导入包和前端图谱增强能力，但数据中心二次优化还没有按最新业务口径重新输出最终包。用户确认的新口径是：

1. 前端资产浏览和图谱分组统一按五层展示：`系统大类 -> 系统/库 -> schema/owner -> 表 -> 字段`。
2. `ODS 数据中心系统` 不是单一业务系统，它承载了多个被抽取业务系统的数据，应在 ODS 大类下继续按抽取来源系统分组。
3. `HIS 源端系统` 与 `ODS 数据中心系统` 是两个不同系统大类，不能混在同一层级。
4. D 类跨系统关系可以进入正式图谱展示，但必须明显标识为 D 类/跨系统/待验证关系，不能与 A/B/C 高置信正式关系混色。
5. 允许重跑本地资产包生成脚本，输出最终优化包。

本计划目标是产出一套可供后续 AI 开发和复核的明确改造方案，覆盖资产包、后端接口、前端资产树、前端图谱和验收标准。

## 2. 目标展示层级

### 2.1 总体层级

```text
系统大类
  -> 系统/库
    -> schema/owner
      -> 表
        -> 字段
```

### 2.2 系统大类

第一阶段固定以下大类：

| system_category | 中文名 | 说明 |
|---|---|---|
| `ods_center` | ODS 数据中心系统 | 数据中心汇聚库，内部按抽取来源业务系统继续分组 |
| `his_source` | HIS 源端系统 | HIS 生产源端/ready_his/hisuser 多 owner 资产 |
| `hrp_source` | HRP 源端系统 | HRP 生产源端资产，当前已有首版探查包 |
| `external_business` | 其他业务系统 | EMR/LIS/PACS/护理/手麻/医保等后续独立源库接入扩展 |
| `platform_asset` | 平台元数据系统 | 平台自身 `asset.*` 元数据库，仅用于平台治理和运维，不与业务源库混淆 |

### 2.3 ODS 数据中心系统内部拆分

ODS 内部必须按抽取来源业务系统展示，而不是只显示一个 ODS 平铺层。

建议第一阶段按 schema、视图命名、已有关系证据和资产包字段归一为：

| source_system | 中文名 | 主要来源/识别依据 | 示例 |
|---|---|---|---|
| `ods_his` | HIS 抽取区 | ODS/HIS/CDA 视图依赖、HIS 同名覆盖表、`V_EMR_*`/`CDR_*` 视图 | HIS 住院、门诊、医嘱、费用、检验检查抽取数据 |
| `ods_lis` | LIS 抽取区 | LIS schema、检验条码/TEST_NO 关系、ODS 检验视图 | LAB_TEST_MASTER/LAB_RESULT 相关抽取 |
| `ods_pacs` | PACS 抽取区 | PACS schema、检查号/报告关系、影像检查视图 | EXAM_MASTER/EXAM_REPORT/PACS 报告链路 |
| `ods_emr` | EMR/病历抽取区 | MTL/JHEMR/YBEMR/病历视图 | 电子病历文书、病案首页相关 |
| `ods_ydhl` | 移动护理抽取区 | YDHL schema、护理事实表、PATIENT_UID 关系 | 护理记录、护理评估 |
| `ods_sm` | 手麻抽取区 | SM schema、手术麻醉主从关系、人员映射专题 | 手术排班、麻醉记录 |
| `ods_cda` | CDA/标准字典区 | CDA schema、国标映射、字典表 | `CDA_DICTIONARY`、院内码到国标码 |
| `ods_other` | 其他抽取区 | 暂不能稳定归入上述系统的 ODS/schema/视图 | 待人工复核 |

## 3. 功能描述

### 3.1 资产浏览功能

前端资产浏览页需要支持：

1. 左侧或顶部按 `系统大类` 筛选。
2. ODS 大类下继续展示抽取来源系统，例如 `HIS 抽取区`、`LIS 抽取区`、`PACS 抽取区`。
3. HIS 源端系统下展示真实源端库/owner，例如 `hisuser/ready_his -> MEDREC/COMM/ORDADM/LAB/EXAM`。
4. 表列表展示系统大类、系统/库、schema/owner、表名、中文名、业务域、表角色、纳入状态、数据量/活跃度。
5. 字段列表展示字段名、中文名、类型、敏感级别、主题域、是否主键候选、是否关系字段。
6. 支持搜索 `MEDREC.PAT_VISIT`、`PAT_VISIT`、中文表名、字段名并定位到对应层级。
7. 支持按纳入状态筛选：核心表、候选表、排除表、待确认表。
8. 支持按系统来源筛选：ODS-HIS、HIS 源端、HRP 源端、LIS、PACS 等。

### 3.2 关系图谱功能

图谱页需要支持：

1. 视图模式：系统级、系统/库级、schema/owner 级、业务域级、表级、字段证据详情。
2. 节点聚合：按 `system_category`、`source_system`、`schema_name`、`business_domain`、`table_name` 聚合。
3. 搜索定位：输入 `MEDREC.PAT_VISIT` 可定位 HIS 源端核心节点；输入 ODS 视图或表可定位 ODS 抽取区节点。
4. 链路聚焦：只显示当前表直接上下游、一跳/两跳链路、按上游/下游方向过滤。
5. 点击节点：高亮相关边，其他节点和边降透明。
6. 点击边：展示字段映射、覆盖率、孤儿率、验证状态、关系来源、来源文档、待验证说明。
7. D 类关系进入正式图谱，但必须样式区分：虚线、灰紫色或独立色系、图例标注 `D类跨系统待验证`。
8. A/B/C/D 关系可筛选，默认展示策略由产品配置决定，但 D 类不能伪装成 A_rechecked。

### 3.3 D 类关系新口径

旧口径中 D 类跨系统关系只进入待分析层，不进入正式图谱。用户现已调整口径：D 类关系可以进入正式图谱。

实施规则：

| 项目 | 规则 |
|---|---|
| 是否进入正式图谱 | 可以进入正式图谱展示 |
| 是否作为高置信关系 | 不可以，必须保留 D 类标记 |
| 默认样式 | 虚线、灰紫色、低饱和度、可高亮 |
| 图例 | 必须单独显示 `D类跨系统待验证` |
| 详情抽屉 | 必须显示验证状态、来源文档、字段映射、覆盖率、孤儿率、待补验证说明 |
| 资产包字段 | `relationship_class = D`，`validation_status = pending_cross_system_validation` |
| 是否参与自动推导 | 第一阶段不参与自动推导主线，只参与展示和人工复核 |

## 4. 数据归一化字段设计

最终优化包建议至少输出以下字段。

### 4.1 表资产字段

| 字段 | 说明 |
|---|---|
| `system_category` | 系统大类：ODS 数据中心/HIS 源端/HRP 源端/其他业务系统/平台元数据 |
| `source_system` | 系统/库或 ODS 抽取来源系统，如 `ods_his`、`his_source` |
| `source_database` | 实际库名或逻辑库名，如 `data_center_ods`、`ready_his`、`hisuser` |
| `schema_name` | ODS/PostgreSQL schema 或 Oracle owner |
| `table_name` | 表名 |
| `table_name_cn` | 中文名 |
| `business_domain` | 业务域：患者、就诊、医嘱、检验、检查、费用、药品、人员、科室等 |
| `table_role` | 核心事实表、字典维表、关系表、接口表、日志表、临时表等 |
| `include_status` | 核心/候选/排除/待确认 |
| `exclude_reason` | 排除原因 |
| `source_evidence` | 来源文档或脚本证据 |

### 4.2 字段资产字段

| 字段 | 说明 |
|---|---|
| `system_category` | 继承表资产 |
| `source_system` | 继承表资产 |
| `schema_name` | schema/owner |
| `table_name` | 表名 |
| `column_name` | 字段名 |
| `column_name_cn` | 字段中文名 |
| `data_type` | 字段类型 |
| `sensitivity_level` | 敏感等级 |
| `is_key_candidate` | 是否候选主键/关联键 |
| `business_term` | 业务术语 |

### 4.3 关系资产字段

| 字段 | 说明 |
|---|---|
| `source_system_category` | 源节点系统大类 |
| `source_system` | 源系统/库 |
| `source_schema` | 源 schema/owner |
| `source_table` | 源表 |
| `source_columns` | 源字段列表 |
| `target_system_category` | 目标节点系统大类 |
| `target_system` | 目标系统/库 |
| `target_schema` | 目标 schema/owner |
| `target_table` | 目标表 |
| `target_columns` | 目标字段列表 |
| `relationship_class` | A/B/C/D |
| `validation_status` | `sample_pass`、`validated`、`pending_cross_system_validation` 等 |
| `graph_layer` | `formal`、`cross_system_pending`、`candidate` 等 |
| `coverage_rate` | 覆盖率 |
| `orphan_rate` | 孤儿率 |
| `evidence_docs` | 来源文档列表 |
| `evidence_summary` | 证据摘要 |

## 5. 资产包输出规划

允许重跑本地资产包生成脚本，建议输出新的最终优化包目录：

```text
开发起步包/数据资产_ODS_HIS归一优化包/
  normalized_system_categories.csv
  normalized_sources.csv
  normalized_tables.csv
  normalized_columns.csv
  normalized_relationships.csv
  normalized_graph_nodes.csv
  normalized_graph_edges.csv
  normalized_catalog.json
  generation_summary.json
```

同时更新或派生：

```text
开发起步包/数据资产_HIS_READY治理导入包/
开发起步包/数据资产_HIS_READY二次优化包/
开发起步包/数据资产_关系图谱/
```

不建议覆盖旧包原始文件。优先新增归一优化包，旧包作为证据留存。

## 6. 后端改造计划

### 6.1 API 字段补齐

需要检查并扩展以下接口返回字段：

1. 资产表列表接口：返回 `system_category/source_system/source_database/schema_name/table_name/table_name_cn/business_domain/table_role/include_status`。
2. 字段列表接口：返回 `system_category/source_system/schema_name/table_name/column_name/sensitivity_level/business_term`。
3. 图谱接口：返回 `relationship_class/validation_status/graph_layer/metrics/evidence_docs/evidence_summary`。
4. 搜索接口：支持 `系统大类 + 系统/库 + schema/owner + 表 + 字段` 多级搜索。

### 6.2 后端原则

1. 不在前端硬编码 ODS/HIS 分类规则，分类结果应来自资产包或后端接口。
2. D 类关系不降级为普通正式关系，必须保留 `relationship_class = D`。
3. 旧字段保持兼容，避免破坏已有图谱和资产页。
4. 生成脚本必须可重复执行，输出 `generation_summary.json` 记录输入文件、输出数量、规则版本和时间。

## 7. 前端改造计划

### 7.1 资产浏览页

目标展示：

```text
ODS 数据中心系统
  HIS 抽取区
    ODS / HIS / CDA
      表
        字段
  LIS 抽取区
    LIS
      表
        字段

HIS 源端系统
  hisuser / ready_his
    MEDREC / COMM / ORDADM / LAB / EXAM
      表
        字段
```

需要实现：

1. 系统大类筛选器。
2. 系统/库二级筛选器。
3. schema/owner 筛选器。
4. 表/字段搜索定位。
5. 表角色和纳入状态标签。
6. ODS 抽取区与 HIS 源端系统视觉区分。

### 7.2 图谱页

需要实现或复核：

1. 系统大类分组布局。
2. ODS 内部按抽取来源系统聚合。
3. HIS 源端 owner 级聚合。
4. D 类关系正式展示层。
5. A/B/C/D 图例和筛选。
6. 边详情抽屉显示证据。
7. 搜索 `MEDREC.PAT_VISIT` 定位并高亮上下游。
8. 支持直接上下游、两跳链路、上游/下游方向过滤。

## 8. 执行顺序

1. 复核输入文件：`38`、`39`、`40`、`35`、`数据资产_HIS_READY二次优化包`、`数据资产_HIS_READY治理导入包`、`数据资产_资产包`、`数据资产_HIS源端资产包`。
2. 新增或改造本地生成脚本，输出 `数据资产_ODS_HIS归一优化包`。
3. 校验输出 CSV/JSON 数量、字段完整性和 D 类关系标记。
4. 补后端 API 字段，不把分类规则硬编码在前端。
5. 改造前端资产浏览层级。
6. 改造前端图谱 D 类正式展示层和证据详情。
7. 更新文档状态和验收记录。

## 9. 验收标准

### 9.1 资产包验收

1. 存在 `数据资产_ODS_HIS归一优化包/normalized_catalog.json`。
2. 表资产均具备 `system_category/source_system/schema_name/table_name`。
3. ODS 资产能拆分到 HIS/LIS/PACS/EMR/YDHL/SM/CDA/other 等抽取区。
4. HIS 源端资产能按 owner 展示，如 MEDREC/COMM/ORDADM/LAB/EXAM。
5. D 类关系保留 `relationship_class = D` 和 `validation_status = pending_cross_system_validation`。

### 9.2 前端功能验收

1. 资产页能按以下层级浏览：`系统大类 -> 系统/库 -> schema/owner -> 表 -> 字段`。
2. ODS 数据中心系统下能看到各抽取业务系统分组。
3. HIS 源端系统不与 ODS-HIS 抽取区混在同一层级。
4. 搜索 `MEDREC.PAT_VISIT` 能定位 HIS 源端表。
5. 图谱中 D 类关系可见、可筛选、可高亮，且样式明显区别于 A/B/C。
6. 点击 D 类边能看到字段映射、覆盖率、孤儿率、来源文档和待验证提示。

### 9.3 命令验收

后端：

```powershell
cd F:\python\数据资产\backend
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m alembic upgrade head
```

前端：

```powershell
cd F:\python\数据资产\frontend
pnpm.cmd run typecheck
pnpm.cmd run build
```

## 10. 给后续执行 AI 的提示词

```text
请按 `开发起步包/51_ODS_HIS大类归一与数据中心二次优化改造计划.md` 接续数据中心二次优化。先读取 `AGENTS.md`、`开发起步包/README.md`、`55_系统未完成事项统一执行计划.md`、`40_数据治理复核口径与方法记录.md`、`38_secondary_manual_confirm_tables复核修订报告.md`、`39_secondary_relationships分级修订报告.md`；35/46 号仅在 `_archive/` 作历史证据，不作为执行入口。

目标：重跑本地资产包生成脚本，输出 ODS/HIS 大类归一最终优化包；前端和后端统一支持 `系统大类 -> 系统/库 -> schema/owner -> 表 -> 字段`。ODS 数据中心系统内部必须按抽取来源业务系统拆分，如 HIS/LIS/PACS/EMR/YDHL/SM/CDA。HIS 源端系统与 ODS-HIS 抽取区必须分开展示。

D 类跨系统关系允许进入正式图谱，但必须保留 relationship_class=D、validation_status=pending_cross_system_validation，并在图谱中使用独立样式、图例和证据详情，不能与 A/B/C 高置信关系混色。

不要在前端硬编码分类规则；如果 API 缺字段，先补后端和资产包。完成后运行 pytest、alembic upgrade head、pnpm.cmd run typecheck、pnpm.cmd run build，并同步更新 46 号状态总表和 README。
```
