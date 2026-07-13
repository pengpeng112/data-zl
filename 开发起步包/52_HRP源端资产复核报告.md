> 类别：元数据
# HRP 源端资产复核报告

> 本报告编号 52，续 49 号《HRP 源端资产探查报告》之后。复核基于 49 号已采集 CSV，只读未连库。

## 0. 复核结论（先看这里）

用户提出的复核请求已完成。**核心结论：表级复核已够用，可以进入人工确认；但 49 号探查的口径与分类有 5 处需要修正。**

| 项 | 49 号原结论 | 复核修正 | 影响 |
|---|---|---|---|
| 表总数 | 76057 张 | **真实业务表约 5851 张**（76057 含 38242 个 TEMQ 临时查询 + 23688 个 IUFO 报表对象 + 8215 个 ZDP 打印对象） | 人工确认规模从"76057 张不可能看"降为"5851 张可分级确认" |
| 域分类 | 9 域，"其他"占 73542 | **16 域**，新增"固定资产/设备""采购/请购""库存/出入库""财务/总账""财务/辅助账""财务/成本"6 个被吞进"其他"的关键域 | FA_/PAM_/PO_/IC_/GL_/IA_/COST_/WA_ 不再误判为"其他" |
| 强制保留白名单 | 27 张 | **75 张**（覆盖人员档案全系列、采购、固定资产、薪酬、辅助账） | 第一版核心范围更完整 |
| 关系种子 | 仅标了视图引用次数 | 补标"被视图引用≥3 次且行数>0"提升为 P0 | FA_CARD/FA_CARDHISTORY/FA_CARDSUB 等高引用表正确进入核心 |
| 字段缺失 | 标了 50 张 | 精确到 **423 张业务表字段未覆盖**，其中 8 张是核心表（WA_DATA/WA_ITEM 等） | 核心表标 need_fields，先补采再确认 |

**第二轮：低行数清洗（用户规则 + 我对 HRP/NC 表的理解）**

用户要求"num_rows<10 且非字典的去掉"，我按对表的理解补充了保护规则，避免误删本就该少的维度/配置表：

| 清洗结果 | 数量 | 说明 |
|---|---:|---|
| 剔除（drop） | **3925** | num_rows<10 且非字典、非关系种子、非人员档案子表、非维度根表 |
| 保留（keep） | **1926** | 最终进入治理系统的表清单 |
| 规则未触发（not_applied） | 1511 | num_rows≥10 或缺失，不在阈值范围 |

**保护规则（避免误删）**：
1. 字典/编码域全部保留（用户明确要求）
2. 强制保留白名单 75 张（无论行数）
3. 被视图引用≥1 次（关系种子，删了会断关系图谱）
4. `HI_PSNDOC_*` 人员档案子表（NC 固定结构，0 行也可能是未启用）
5. 表名含 CLASS/TYPE/PERIOD/GRADE/SERIES/LEVEL/CATEGORY 的维度根表

**最终你只需要看 `hrp_decided_keep_list.csv` 的 1926 张**（其中 P0+P0_empty=75 张是核心，其余 1851 张可导入后慢慢优化）。

## 1. 复核范围与方法

### 1.1 输入文件
- `开发起步包/49_HRP源端资产探查报告.md` / `49_HRP源端资产探查结果.json`
- `开发起步包/数据资产_HRP源端资产包/`（hrp_source_tables/columns/indexes/constraints.csv + hrp_view_relationship_seeds.csv + 6 份 cleanup/manual_review CSV）
- `开发起步包/tools/harvest_hrp_source_assets.py` / `build_hrp_cleanup_recommendations.py`

### 1.2 复核方法
- **只读本地 CSV**，不连数据库（复核阶段不产生新的 DB 查询）
- 对 `hrp_source_tables.csv` 76057 行逐行分类，按对象类型（业务表/临时查询/报表/打印/系统）拆分
- 对 `hrp_source_columns.csv` 统计每表字段覆盖数，交叉验证核心表字段是否完整
- 对 `hrp_source_constraints.csv` 提取主键，验证核心表主键字段
- 对 `hrp_view_relationship_seeds.csv` 统计每张表被视图引用次数，作为关系种子强度
- 按用友 NC ERP 标准模块命名规范重判域分类

### 1.3 系统识别
HRP 源端是**用友 NC（UFIDA NC）ERP 系统**，判断依据：
- 表名前缀遵循 NC 标准模块：`BD_`（基础档案）、`HI_`（人事）、`ORG_`（组织）、`OM_`（岗位）、`SM_`（系统管理）、`IC_`（库存）、`PO_`（采购）、`GL_`（总账）、`IA_`（辅助账）、`FA_`（固定资产）、`WA_`（薪酬）、`PAM_`（设备资产）、`COST_`（成本）、`SCM_`（批次）
- 主键命名 `PK_<实体>`、通用字段 `PK_GROUP`/`PK_ORG`/`TS`/`DR`/`CREATIONTIME`/`MODIFIEDTIME`/`DATAORIGINFLAG`
- 多语言字段 `NAME2`~`NAME6`、`DEF1`~`DEF20` 扩展位
- `TEMQ_` 临时查询对象、`IUFO_` 报表对象、`ZDP_` 打印对象均为 NC 平台特征

## 2. 真实表口径修正（最重要发现）

49 号报告"76057 张表"严重高估，因为把 NC 平台的临时查询对象、报表对象、打印对象都计入了表清单。

### 2.1 对象类型拆分

| 对象类型 | 数量 | 说明 | 处理 |
|---|---:|---|---|
| **business（真实业务表）** | **5851** | NC 业务模块表，治理对象 | ✅ 纳入复核 |
| TEMQ_ 临时查询对象 | 38242 | NC 查询引擎缓存的临时结果集，非业务表 | ❌ 排除 |
| IUFO_ 报表对象 | 23688 | NC IUFO 报表平台元数据，非业务表 | ❌ 排除 |
| ZDP_ 打印对象 | 8215 | NC 打印模板衍生对象 | ❌ 排除 |
| BIN$/系统对象 | 61 | Oracle 回收站、系统表 | ❌ 排除 |

### 2.2 真实业务表分布

真实业务表 5851 张，其中：
- **有数据（NUM_ROWS>0）**：约 1661 张（28%）
- **空表或未统计**：约 4190 张（72%）——多为配置表、空表、未分析表

按修正后域分布（有数据的表）：

| 域 | 表数 | 说明 |
|---|---:|---|
| 其他 | 3644 | 含大量 NC 平台配置表、接口表、临时表，需逐域再筛 |
| 财务（总账+辅助+成本+财务） | 546 | GL_/IA_/COST_/BD_BILLTYPE 等 |
| 人员 | 373 | BD_PSNDOC/HI_PSNDOC_*/HI_PSNJOB |
| 字典/编码 | 306 | BD_DEFDOC/MD_ENUMVALUE |
| 科室/组织 | 282 | ORG_DEPT/ORG_ADMINORG/BM_ |
| 固定资产/设备 | 204 | FA_/PAM_/ZC_ |
| 供应商/物资 | 186 | BD_MATERIAL/BD_SUPPLIER |
| 用户账号 | 110 | SM_USER/BD_ACCOUNT |
| 库存/出入库 | 47 | IC_MATERIAL_H/B/IC_ONHANDDIM/NUM |
| 薪酬/绩效 | 68 | WA_DATA/WA_ITEM |
| 岗位/职务 | 59 | OM_JOB |
| 采购/请购 | 13 | PO_INVOICE/PO_PRAYBILL |

## 3. 域分类修正

49 号的 `infer_domain` 把大量 NC 业务表误判为"其他"。复核按 NC 命名规范重判：

### 3.1 新增 6 个域

| 新域 | 触发前缀 | 49 号原域 | 修正理由 |
|---|---|---|---|
| 固定资产/设备 | `FA_`/`PAM_`/`ZC_` | 其他 | FA_CARD 卡片、PAM_EQUIP 设备、ZC_DJKP 设备对账 |
| 采购/请购 | `PO_PRAYBILL`/`PO_PURCHASE`/`PO_INVOICE` | 财务（误判） | PO 是采购不是财务 |
| 库存/出入库 | `IC_PURCHASEIN`/`IC_GENERALIN`/`IC_ONHAND`/`IC_MATERIAL`/`IC_SALEOUT` | 其他 | IC 是库存出入库流水 |
| 财务/总账 | `GL_` | 财务 | GL_ 是总账凭证明细 |
| 财务/辅助账 | `IA_` | 其他 | IA_ 是辅助账/明细账 |
| 财务/成本 | `COST_` | 其他 | COST_ 是成本核算 |

### 3.2 薪酬域修正
49 号把 `WA_` 误判为"其他"（因为 `infer_domain` 没匹配 `WA_` 前缀）。复核把 `WA_` 正确归入"薪酬/绩效"。

## 4. 核心表主键与关系梳理

### 4.1 核心表主键（已从约束文件验证）

| 表 | 主键 | 用途 |
|---|---|---|
| BD_PSNDOC | PK_PSNDOC | 人员档案主表 |
| BD_PSNCL | PK_PSNCL | 人员类别 |
| HI_PSNJOB | PK_PSNJOB | 人员任职（人员↔部门↔岗位的桥接表，核心） |
| ORG_DEPT | PK_DEPT | 部门 |
| ORG_ADMINORG | PK_ADMINORG | 行政组织 |
| OM_JOB | PK_JOB | 岗位 |
| SM_USER | CUSERID | 系统用户（PK_PSNDOC 关联人员档案） |
| BD_MATERIAL | PK_MATERIAL | 物料主数据 |
| BD_SUPPLIER | PK_SUPPLIER | 供应商 |
| IC_MATERIAL_H | CGENERALHID | 出入库单头 |
| IC_MATERIAL_B | CGENERALBID | 出入库单行 |
| IC_ONHANDDIM | PK_ONHANDDIM | 现存量维度 |
| IC_ONHANDNUM | PK_ONHANDNUM | 现存量数量 |
| WA_DATA | PK_WA_DATA | 工资数据 |
| GL_DETAIL | PK_DETAIL | 总账明细 |
| GL_DOCFREE1 | ASSID | 自由项 |
| FA_CARD | — | 固定资产卡片（视图中高频引用） |
| BD_DEFDOC | PK_DEFDOC | 通用档案定义 |
| BD_STORDOC | PK_STORDOC | 仓库 |
| BD_MEASDOC | PK_MEASDOC | 计量单位 |

### 4.2 约束特点
- **无外键约束**：74723 条约束中 P=30439、C=44262、U=22，**R（外键）=0**。NC 不建物理外键，所有关系靠应用层 + 视图 DDL 编码。
- 这意味着**视图依赖（user_dependencies）是关系图谱的唯一权威种子**，149 个视图、947 条依赖边是核心资产。

### 4.3 核心关系主线（基于视图种子与 NC 命名规范推断）

#### 人员主线
```
BD_PSNDOC (PK_PSNDOC) 
  ├─ HI_PSNJOB (PK_PSNJOB → PK_PSNDOC, PK_DEPT, PK_JOB)  ← 人员任职，一人多科室的关键表
  │    ├─ ORG_DEPT (PK_DEPT)
  │    ├─ OM_JOB (PK_JOB)
  │    └─ BD_PSNCL (PK_PSNCL)
  ├─ SM_USER (CUSERID → PK_PSNDOC)  ← 账号映射
  ├─ HI_PSNDOC_EDU / HI_PSNDOC_CERT / HI_PSNDOC_GLBDEF2 / HI_PSNDOC_PSNCHG  ← 档案子表
  └─ WA_DATA (PK_PSNDOC)  ← 工资数据
```

#### 物资/库存主线
```
BD_MATERIAL (PK_MATERIAL)
  ├─ BD_MATERIALSTOCK (PK_MATERIALSTOCK → PK_MATERIAL, PK_STORDOC)  ← 物料仓库关系
  ├─ BD_MARBASCLASS (PK_MARBASCLASS)  ← 物料分类
  ├─ BD_MEASDOC (PK_MEASDOC)  ← 计量单位
  ├─ IC_MATERIAL_H (CGENERALHID) ─ IC_MATERIAL_B (CGENERALBID)  ← 出入库单头行
  ├─ IC_ONHANDDIM (PK_ONHANDDIM) ─ IC_ONHANDNUM (PK_ONHANDNUM)  ← 现存量
  └─ SCM_BATCHCODE (PK_BATCHCODE)  ← 批次
```

#### 采购/供应商主线
```
BD_SUPPLIER (PK_SUPPLIER)
  ├─ BD_SUPPLIERCLASS  ← 供应商分类
  ├─ PO_INVOICE (PK_INVOICE) ─ PO_INVOICE_B (PK_INVOICE_B)  ← 采购发票
  └─ PO_PRAYBILL_B  ← 请购单
```

#### 固定资产/设备主线（视图高频引用，原"其他"误判）
```
FA_CARD (卡片) ─ FA_CARDHISTORY (卡片历史) ─ FA_CARDSUB (卡片附表)
  ├─ FA_CATEGORY (资产分类，被 44 个视图引用)
  ├─ FA_CAPITALSOURCE (资金来源)
  ├─ FA_DEPTSCALE (部门折旧)
  └─ PAM_EQUIP (设备主表) ─ PAM_CATEGORY / PAM_STATUS / PAM_ADDREDUCESTYLE
```

#### 财务主线
```
GL_DETAIL (PK_DETAIL)  ← 总账明细，被 PL_CWPZMX 视图引用
  ├─ GL_DOCFREE1 (ASSID)  ← 自由项
  ├─ BD_BILLTYPE / BD_VOUCHERTYPE  ← 单据/凭证类型
  ├─ IA_DETAILLEDGER / IA_ASSISTANTLEDGER  ← 辅助账（311万/223万行）
  └─ COST_* 系列  ← 成本核算
```

### 4.4 HIS 桥接关系（关键跨系统种子）

| HRP 表/视图 | 用途 | 关联 HIS |
|---|---|---|
| `CDA_SECTION_MAP` | 院内科室↔CS_SECTION 标准科室代码对照（205 行） | HIS 科室编码映射 |
| `V_SEY_MATERIALINFOTOHIS` | 物料信息同步到 HIS | BD_MATERIAL/BD_MARBASCLASS/BD_MEASDOC |
| `V_SEY_SCSTOHIS` / `V_LYYY_SCSTOHIS` | 供应商同步到 HIS | BD_SUPPLIER |
| `V_LYYY_MATERIALPRICETOHIS` | 物料价格同步到 HIS | BD_MATERIAL |
| `EMR_HOS_INFORMATION` / `EMR_HOS_PRACTITIONER` | 人员信息供 EMR 使用 | BD_PSNDOC/HI_PSNJOB/ORG_DEPT |
| `HRP_HIS_HCCKXX` / `SEY_HCCK` / `SEY_WZCK` | 耗材出库同步 HIS | IC_MATERIAL_H/B/BD_MATERIAL |

## 5. 字段覆盖缺口

### 5.1 字段采集现状
- 采集上限：500 万行（`HRP_COLUMNS_MAX_ROWS=5000000`）
- 已采集字段：500 万行（命中上限）
- **未覆盖业务表**：423 张

### 5.2 核心表字段缺口（8 张，标 need_fields）

| 表 | 行数 | 域 | 字段数 | 处理 |
|---|---:|---|---:|---|
| WA_DATA | 124520 | 薪酬/绩效 | 0 | **need_fields**（工资主表，必须补采） |
| WA_PSNTAX | 109984 | 薪酬/绩效 | 0 | need_fields（个税） |
| WA_CLASSITEM | 9955 | 薪酬/绩效 | 0 | need_fields（工资项目） |
| WA_ITEMPOWER | 2230 | 薪酬/绩效 | 0 | need_fields |
| WA_WACLASS | 8 | 薪酬/绩效 | 0 | need_fields（工资类别） |
| WA_PSNHI_B | 199 | 薪酬/绩效 | 0 | need_fields（社保） |
| WA_ITEM | 86 | 薪酬/绩效 | 0 | need_fields（工资项目定义） |
| WA_PSNHI | 6 | 薪酬/绩效 | 0 | need_fields（社保类别） |

**原因**：WA_ 系列表在 ALL_TAB_COLUMNS 中排序靠后，500 万行上限截断时未采到。补采方法：`harvest_hrp_source_assets.py` 增加 `WHERE c.table_name LIKE 'WA_%'` 分段查询。

## 6. 人工确认主清单说明

### 6.1 新生成文件
复核产出 `hrp_review_confirmation_pack.csv`（5851 张真实业务表）+ `hrp_review_confirmation_summary.json`。

### 6.2 优先级分布

| 优先级 | 数量 | 含义 | 你要看 |
|---|---:|---|---|
| P0 | 75 | 强制保留白名单 + 高引用种子表 | ✅ 全看 |
| P0_empty | 4 | 强制保留但空表（HI_PSNDOC_CTRT 等） | ✅ 确认是否保留 |
| P1 | 668 | 被视图引用或非"其他"域有数据表 | 抽看 |
| P2 | 900 | "其他"域有数据表 | 按需 |
| P3 | 4208 | 空表/未统计 | 可批量排除 |

### 6.3 建议动作分布

| 动作 | 数量 | 含义 |
|---|---:|---|
| KEEP_CORE | 63 | 建议直接纳入（字段+行数齐全） |
| NEED_FIELDS | 8 | 核心但字段未覆盖，先补采 |
| KEEP_CORE_EMPTY | 4 | 核心但空，确认保留 |
| REVIEW_INCLUDE | 1568 | 业务表，建议确认 |
| REVIEW_EMPTY | 1472 | 空表，确认是否配置表 |
| EXCLUDE_EMPTY | 2736 | 空表+非核心域，建议排除 |

### 6.4 你优先看的 P0（75 张）

**第一组：人员档案（7 张，字段全）**
- BD_PSNDOC（3279 行，人员主表，115 字段）
- HI_PSNJOB（5460 行，人员任职，73 字段，**一人多科室的关键表**）
- BD_PSNCL（19 行，人员类别）
- HI_PSNDOC_EDU（3824 行，学历）
- HI_PSNDOC_GLBDEF2（3567 行，自定义扩展）
- HI_PSNDOC_PSNCHG（3287 行，人员变动）
- HI_PSNDOC_CERT（3216 行，证件）

**第二组：组织/部门（10 张）**
- ORG_DEPT（325 行，部门主表，80 字段，被 77 个视图引用）
- ORG_ADMINORG（行政组织）
- ORG_DEPT_V（部门版本视图）
- ORG_STOCKORG（库存组织）
- CDA_SECTION_MAP（**HIS 科室对照表，205 行**）
- BM_CENTERDEPTMAKE / BM_CENTERDEPTMAKE_B / BM_BUDGETCENTERDEPT（预算中心）
- ORG_ORGS / ORG_ORGTYPE

**第三组：用户/岗位（3 张）**
- SM_USER（987 行，系统用户，PK_PSNDOC 关联人员）
- BD_ACCOUNT（2757 行，账号）
- OM_JOB（326 行，岗位）

**第四组：薪酬（8 张，字段全缺，标 need_fields）**
- WA_DATA / WA_ITEM / WA_WACLASS / WA_CLASSITEM / WA_PSNTAX / WA_PSNHI / WA_PSNHI_B / WA_ITEMPOWER

**第五组：物资/供应商（6 张）**
- BD_MATERIAL（37976 行，物料主表）
- BD_SUPPLIER（3035 行，供应商）
- SCM_BATCHCODE（75445 行，批次）
- BD_MATERIALSTOCK / BD_SUPPLIERCLASS / BD_MARBASCLASS

**第六组：库存出入库（9 张）**
- IC_MATERIAL_H / IC_MATERIAL_B（出入库单头行，128万/17万行）
- IC_ONHANDDIM / IC_ONHANDNUM（现存量）
- IC_PURCHASEIN_H / IC_PURCHASEIN_B（采购入库）
- IC_GENERALIN_H / IC_GENERALIN_B（其他入库）
- IC_ONHANDSN（序列号现存量，142万行）

**第七组：采购（3 张）**
- PO_INVOICE / PO_INVOICE_B（采购发票）
- PO_PRAYBILL_B（请购单）

**第八组：固定资产/设备（11 张，原"其他"误判，被大量视图引用）**
- FA_CARD（115442 行，卡片，被 61 个视图引用）
- FA_CARDHISTORY（1454132 行，卡片历史，60 视图）
- FA_CARDSUB（卡片附表，59 视图）
- FA_CATEGORY（资产分类，44 视图）
- FA_CAPITALSOURCE / FA_DEPTSCALE
- PAM_EQUIP（55337 行，设备主表，223 字段）
- PAM_CATEGORY / PAM_STATUS / PAM_ADDREDUCESTYLE

**第九组：财务（7 张）**
- GL_DETAIL（1086132 行，总账明细）
- GL_DOCFREE1（自由项）
- IA_DETAILLEDGER（311万行，辅助明细账）
- IA_ASSISTANTLEDGER（223万行，辅助账）
- BD_BILLTYPE / BD_VOUCHERTYPE / BD_FUNDSOURCE / BD_ACCPERIODMONTH

**第十组：字典（3 张）**
- BD_DEFDOC（22087 行，通用档案）
- BD_MARBASCLASS（物料分类）
- MD_ENUMVALUE（10133 行，枚举）

**第十一组：其他基础档案（5 张）**
- BD_STORDOC（仓库）/ BD_MEASDOC（计量单位）/ BD_PROJECT（项目）/ BD_ADDRESS / BD_COUNTRYZONE

## 7. 排除审计（需你复核的"误排"风险表）

### 7.1 TEMP_FA_ASSETSD / TEMP_FA_CAPTIALSOURCE（59 个视图引用）
- 49 号排除理由：表名疑似临时，NUM_ROWS 缺失
- **复核发现**：被 59 个 TEMQ_ 视图引用，是固定资产报表的中间表
- **建议**：排除（TEMP_ 前缀确认是临时表，视图引用来自 TEMQ 临时查询本身，不是业务视图）

### 7.2 HSTF_INSTOCKDATA / HSTF_OUTSTOCKDATA 系列（4 张，0 行）
- 49 号排除理由：NUM_ROWS=0
- **复核发现**：被 HSTF_*_VIEW 视图引用，但行数为 0
- **建议**：排除（0 行确认是废弃/未使用表，IC_MATERIAL_H/B 已覆盖出入库主线）

### 7.3 HI_PSNDOC_CTRT / HI_PSNDOC_TITLE / HI_PSNDOC_LANGABILITY / HI_PSNTRANSTER（4 张，0 行）
- 49 号排除理由：NUM_ROWS=0
- **复核发现**：被 HR_RYDA / HR_LZXX 视图引用（合同/职称/语言能力/人员调动）
- **建议**：**保留为 P0_empty**（人员档案子表，虽然当前 0 行，但结构上属于人员主线，可能未启用或已迁移）

## 8. 与 49 号探查的口径对照

| 指标 | 49 号 | 复核 | 差异原因 |
|---|---:|---:|---|
| 表总数 | 76057 | 5851（业务表） | 49 号未剔除 TEMQ/IUFO/ZDP |
| 字段 | 5000000 | 5000000（同，命中上限） | 一致 |
| 视图 | 149 | 149 | 一致 |
| 视图依赖 | 947 | 947 | 一致（复核统计种子引用 788 边） |
| 约束 | 74723 | 74723（P=30439/C=44262/U=22/R=0） | 一致，补标无外键 |
| 核心候选 | 1207 | 75（P0）+ 668（P1） | 49 号"核心候选"含大量空配置表 |
| 字段缺失表 | 50 | 423（业务表）/ 8（核心表） | 49 号只统计了 core_candidates 的缺失 |

## 9. 下一步建议

### 9.1 立即可做（不依赖 DB）
1. **直接导入 `hrp_decided_keep_list.csv` 的 1926 张**：这是按"num_rows<10 且非字典剔除 + 保护规则"清洗后的最终保留集，可导入系统后慢慢优化
2. **P0 的 75 张是核心**：71 张 KEEP_CORE + 4 张 P0_empty + 8 张 NEED_FIELDS，优先确认这些
3. **WA_ 系列先标 need_fields**：8 张薪酬表字段未覆盖，确认结构后再纳入

### 9.2 需补采字段（夜间执行）
```sql
-- 在 harvest_hrp_source_assets.py 增加 WA_ 分段查询
SELECT c.table_name, c.column_name, c.data_type, ...
FROM user_tab_columns c
WHERE c.table_name LIKE 'WA_%'
```

### 9.3 需 DB 连接验证（后续）
- 人员唯一键：确认 BD_PSNDOC.PK_PSNDOC 与 HIS COMM.STAFF_DICT 工号的映射口径
- CDA_SECTION_MAP：确认 HOSPITAL_CODE 是否对应 HIS 科室编码
- HI_PSNJOB 一人多科室：确认 ISMAINJOB 字段区分主兼职

### 9.4 低行数剔除表后期回看
- `hrp_decided_drop_list.csv`（3925 张）保留备查；导入系统后如果发现某张表被业务引用但不在 keep_list，可从这里捞回
- 剔除规则有审计标记：每张表带 `low_row_reason`，说明为什么被剔除

## 10. 文件清单

| 文件 | 用途 |
|---|---|
| `hrp_decided_keep_list.csv` | **最终保留清单（1926 张，导入系统用）** |
| `hrp_decided_drop_list.csv` | **剔除清单（3925 张，备查回捞）** |
| `hrp_review_confirmation_pack.csv` | 复核全量清单（5851 张，含 low_row_decision 审计列） |
| `hrp_review_confirmation_summary.json` | 复核统计摘要 |
| `hrp_source_tables.csv` | 原始表清单（76057，保留） |
| `hrp_source_columns.csv` | 原始字段（500万行上限） |
| `hrp_source_constraints.csv` | 约束（无外键） |
| `hrp_source_indexes.csv` | 索引 |
| `hrp_view_relationship_seeds.csv` | 视图关系种子（149 视图，核心） |
| `hrp_tables_core_candidates.csv` | 49 号核心候选（1207，保留参考） |
| `hrp_manual_confirmation_pack.csv` | 49 号人工确认包（200，已被复核版替代） |
| `tools/build_hrp_review_pack.py` | **复核脚本**（可复跑，补采字段后重跑更新） |

## 11. 警告与限制

- 复核基于 49 号已采集的 CSV，**未重新连库**；行数来自 ALL_TABLES.NUM_ROWS 统计值，可能不是实时。
- 字段覆盖缺口（423 表）是 500 万行上限导致，核心 8 张 WA_ 表需补采后才能确认结构。
- 视图依赖来自 `user_dependencies`，未解析视图 DDL 中的具体 JOIN 条件；关系主线是基于命名规范 + 视图引用频次的推断，**需 DB 实测验证**后才能回写正式关系。
- 域分类修正基于 NC 命名规范启发式，个别表可能因自定义命名而不符（如 `CDA_SECTION_MAP` 是自定义桥接表，归"科室/组织"正确但前缀非 ORG_）。
