# ODS 视图关系解析与 HIS 表分类报告

> 生成时间：2026-07-02  
> 输入：`08_数据中心元数据快照.json` 中 ODS 119 个视图 DDL + HIS 273 张表元数据。  
> 输出目录：`数据资产_关系图谱/`。  
> 方法：静态解析视图 DDL 中 `FROM/JOIN` 依赖与 `alias.col = alias.col` 条件；HIS 表按已确认清单、ODS 视图上下文、表名规则分层分类。

---

## 1. 输出文件

| 文件 | 内容 | 用途 |
|---|---|---|
| `数据资产_关系图谱/ods_view_dependencies.csv` | ODS 视图引用的表与别名（772 条去重依赖） | 视图血缘、表使用频次 |
| `数据资产_关系图谱/ods_view_join_edges.csv` | 从视图 DDL 条件抽取的疑似 join 边（732 条） | 关系图谱候选边，需后续验证 |
| `数据资产_关系图谱/his_table_classification.csv` | HIS 273 张表主题分类 + 是否被 ODS 视图引用 | 后期维护、分域治理 |
| `数据资产_关系图谱/graph_seed.json` | 上述三类结果的程序读取版 | 图谱服务/API 导入 |

生成脚本：

```bash
python 开发起步包/tools/extract_view_relationships.py
```

---

## 2. ODS 视图解析结果

| 指标 | 数量 |
|---|---:|
| ODS 视图 | 119 |
| 表依赖（去重后） | 772 |
| 疑似 join 边 | 732 |
| 被 ODS 视图引用的 HIS 表 | 66 |

示例（来自 `EMR_DISCHARGE_RECORD_DIAGNOSIS`）：

```text
HIS.DIAGNOSIS.PATIENT_ID = HIS.PAT_VISIT.PATIENT_ID
HIS.DIAGNOSIS.VISIT_ID   = HIS.PAT_VISIT.VISIT_ID
HIS.DIAGNOSIS.PATIENT_ID = HIS.PAT_MASTER_INDEX.PATIENT_ID
```

注意：本步骤是静态 SQL 解析，结果应作为“候选关系/图谱种子”，不是数据库实测结论。正式入图前应按 `10_关系验证报告.md` 的方式抽样或全量验证。

---

## 3. HIS 表分类结果

HIS 共 273 张表，分类统计如下：

| 主题域 | 表数 | 说明 |
|---|---:|---|
| 未分类 | 126 | 多为未被 ODS 引用的历史、规则、临时、中文命名质控/收费类表；后续按需要人工归类 |
| 医嘱 | 19 | `ORDER/ORDERS` 相关 |
| 费用 | 17 | `BILL/FEE/CHARGE/PRICE/COST/PAY/SETTLE/RCPT` 相关 |
| 字典 | 15 | `DICT/CODE/MAP` 等 |
| 患者/就诊 | 13 | `PAT/VISIT/CLINIC` 相关 |
| 人员 | 12 | `STAFF/EMP/DOCTOR/NURSE/USER` 相关 |
| 病案首页 | 10 | 来自 ODS 视图上下文 `V_EMR_ICH` 等 |
| 检验 | 10 | `LAB/TEST/INSPECTION` 相关 |
| 门诊 | 8 | 门诊处方、门诊就诊等 |
| 诊断 | 7 | `DIAG` 相关 |
| 科室/组织 | 7 | `DEPT/WARD/BED/ROOM` 相关 |
| 检查/影像 | 5 | `EXAM/PACS/IMAGE/REPORT` 相关 |
| 手术 | 4 | `OPER/SURG` 相关 |
| 电子病历 | 3 | 由 ODS 视图上下文识别 |
| 其他小类 | 15 | 药品、物资/耗材、门诊费用、患者主数据、诊断字典等 |

维护建议：

- **优先维护被 ODS 视图引用的 66 张 HIS 表**，它们已经参与现有视图/血缘，是关系图谱的一线资产。
- `未分类` 的 126 张表先不要删除；其中不少是 0 行、质控规则、收费规则或中文命名临时表，后续按使用频次和业务需求人工归类。
- `his_table_classification.csv` 中有 `referenced_by_ods_view_count` 和 `referenced_by_ods_views`，可作为维护优先级依据。

---

## 4. 与已验证关系的关系

`10_关系验证报告.md` 已验证的是 25 项核心关系；本报告解析得到的是更大范围的候选关系。

建议分层使用：

| 层级 | 来源 | 入图策略 |
|---|---|---|
| 已验证核心关系 | `relationships.csv` + `10` | 直接入正式图，带 `validation_level/status` |
| 静态解析候选关系 | `ods_view_join_edges.csv` | 入候选图；按表重要性分批验证 |
| 仅依赖无 join 条件 | `ods_view_dependencies.csv` | 用于视图血缘，不直接当表间关系 |
| HIS 分类 | `his_table_classification.csv` | 用于资产域维护、权限/责任域划分 |

---

## 5. 下一步验证优先级

1. 对 `ods_view_join_edges.csv` 中出现频次最高的表对做去重汇总，优先验证高频关系。
2. 优先验证涉及 `PORTAL_EMPI`、`JHEMR`、`YDHL`、`PACS/LIS` 跨系统关系。
3. 对 `EXAM_MASTER`、`LAB_TEST_MASTER` 的候选关系继续按“住院/门诊/其他”拆子集。
4. 将验证通过的候选边追加到 `数据资产_资产包/relationships.csv`，并带上 `validation_level/status/metrics`。

---

## 6. 注意事项

- 静态解析不能理解所有 SQL 语义，尤其是子查询、函数包裹、隐式连接、动态拼接字段。
- `UNKNOWN.*` 依赖通常表示未显式写 schema 的表或当前解析器未识别的对象，需要人工复核。
- 本报告不读取业务数据，仅基于本地 `08` 快照解析。
