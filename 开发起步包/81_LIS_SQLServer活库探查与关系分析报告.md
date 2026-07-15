> 类别：证据报告

# LIS SQL Server 活库探查与关系分析报告

## 1. 探查结论

2026-07-14 已使用修正后的数据库名 `rmcloudlis7` 成功连接 `10.10.10.73:1433`，确认数据库为 Microsoft SQL Server 2016 SP1。完成 `dbo` Schema 的活库元数据采集及核心关系只读验证。

- 业务表 1,180 张、视图 74 个、字段 17,025 个。
- 主键/唯一键字段记录 1,960 条，索引字段记录 2,885 条。
- 数据库没有声明外键，检验业务关系需要依靠业务键、视图 SQL 和数据命中率确认。
- 16 条核心关系完成每条最多 10,000 个非空键的限定验证。
- 74 个视图中 65 个解析到本库基础表，共识别 251 条静态依赖。
- 探查使用 `READ UNCOMMITTED`、`NOLOCK`、锁等待 5 秒和显式事务回滚；未执行任何 DML/DDL，源库写入为 0。

## 2. 模块规模

| 表前缀 | 数量 | 主要含义 |
|---|---:|---|
| `lab_*` | 170 | 常规检验、报告、结果、仪器原始数据 |
| `nbd_*` | 143 | 新业务/医嘱或扩展数据模块 |
| `off_*` | 106 | 离线、设备维护及扩展配置 |
| `bact_*` | 100 | 微生物培养、鉴定、药敏、涂片 |
| `req_*` | 97 | 申请、条码、采集、签收、退回和流转 |
| `inv_*` | 66 | 库存和耗材 |
| `bld_*` | 58 | 输血/血库相关模块 |
| `qc_*` | 41 | 质量控制 |
| `dc_*` | 36 | 科室、医生、标本等基础字典 |
| `iso_*` | 32 | ISO质量管理 |
| `sec_*` | 23 | 用户、角色和权限 |

其余还包含 CDC、体检、危急值、统计、接口和历史归档模块。

## 3. 核心检验主线

```text
req_master（申请/条码流程主表，barcode）
  ├─ req_master_pat（患者和申请信息，barcode）
  ├─ req_detail（申请项目，barcode + seq）
  ├─ bact_sample（微生物样本，barcode）
  └─ report_id ← lab_report.reportid（报告映射，存在历史缺口）

lab_report（报告主表，reportid）
  ├─ lab_result（检验结果，reportid + rpt_itemcode）
  ├─ lab_instrdata（仪器原始数据，reportid）
  ├─ lab_reportlog（报告日志，reportid）
  │   └─ lab_reportlogdetail（日志字段变更，rpt_logid）
  └─ bact_report（微生物报告，reportid）

bact_sample（sampleid）
  ├─ bact_culture（cultureid）
  │   └─ bact_culresult（cultureid）
  ├─ bact_eval（evalid）
  │   └─ bact_medresult（evalid，药敏）
  ├─ bact_smear（smearid）
  │   └─ bact_smearresult（smearid）
  └─ bact_report（sampleid）
```

## 4. 关系验证结果

### 4.1 当前较新键样本 100% 命中

| ID | 子表 → 父表 | 键 |
|---|---|---|
| L01 | `req_master_pat → req_master` | `barcode` |
| L04 | `lab_result → lab_report` | `reportid` |
| L07 | `lab_reportlogdetail → lab_reportlog` | `rpt_logid` |
| L08 | `bact_sample → req_master` | `barcode` |
| L09 | `bact_report → bact_sample` | `sampleid` |
| L10 | `bact_report → lab_report` | `reportid` |
| L11 | `bact_culture → bact_sample` | `sampleid` |
| L12 | `bact_culresult → bact_culture` | `cultureid` |
| L13 | `bact_eval → bact_sample` | `sampleid` |
| L15 | `bact_smear → bact_sample` | `sampleid` |
| L16 | `bact_smearresult → bact_smear` | `smearid` |

每条均为 10,000/10,000，适合作为 LIS 关系图谱主干。L07 的未排序历史页样本曾为 70.25%，但按键倒序的较新样本为 100%，说明日志明细父记录存在明显的生命周期/历史清理差异，不能据此建立源库强制外键。

### 4.2 高命中关系

| ID | 关系 | 命中 | 判断 |
|---|---|---:|---|
| L02 | `req_detail → req_master` | 9,998/10,000（99.98%） | 强业务关系，保留少量孤儿提示 |
| L05 | `lab_instrdata → lab_report` | 9,982/10,000（99.82%） | 仪器原始数据强关系；可能有未成报告或历史清理记录 |
| L06 | `lab_reportlog → lab_report` | 9,889/10,000（98.89%） | 日志生命周期长于报告主表，按历史关系展示 |
| L14 | `bact_medresult → bact_eval` | 9,981/10,000（99.81%） | 药敏到鉴定强关系，保留孤儿质量指标 |

### 4.3 报告到申请的历史缺口

`lab_report.reportid → req_master.report_id` 当前较新键样本为 9,003/10,000（90.03%）。直接以 `lab_report.barcode → req_master.barcode` 验证历史物理页样本为 0%，不能将 barcode 当作该链路的唯一稳定连接。

建议图谱采用：

1. 优先 `reportid → report_id`，关系等级为条件关系并显示约 90% 当前样本命中率。
2. 对未命中的报告，再结合 `barcode`、历史申请表、拆分/合并标本和归档表分析。
3. 不得因为字段同名就将全部报告无条件挂到当前 `req_master`。

## 5. 大表安全边界

以下行数取自 SQL Server 分区元数据，不是本轮全表 `COUNT(*)`：

| 表 | 行数 | 后续查询要求 |
|---|---:|---|
| `lab_instrdata` | 70,782,712 | 必须按 `reportid/instrdataid` 限定 |
| `lab_result` | 40,365,961 | 必须按 `reportid` 限定 |
| `turnover_temp` | 19,409,636 | 按批次/时间限定 |
| `req_log` | 15,535,703 | 按条码或时间限定 |
| `lab_reportlogdetail` | 6,366,963 | 按 `rpt_logid` 限定 |
| `lab_reportlog` | 6,157,089 | 按 `reportid` 或时间限定 |
| `req_detail` | 3,114,455 | 按 `barcode` 限定 |
| `lab_report` | 2,943,314 | 按 `reportid/barcode` 限定 |
| `req_master` / `req_master_pat` | 约 2,809,767 | 按 `barcode` 限定 |

## 6. 视图关系种子

视图静态解析得到 251 条基础表依赖，重点包括：

- `lab_reportshow`：报告、自动审核、申请主表、患者申请信息、科室/医生/病区/标本和用户。
- `req_master_all*`：申请主表、患者申请信息、退回记录及基础字典。
- `TJ_LIS_REPORT`：报告、结果、项目、报告单元和申请主表。
- `v_EMR_INSPECTION`：报告、结果、申请明细、申请主表及人员/科室。
- `CDR_INSPECTION_REPORT`：报告、申请主从、患者申请信息和科室。
- `bact_sample_all`：微生物当前/历史样本、患者申请信息及标本字典。

这些视图是后续对接 HIS、EMR、CDR 时最可靠的静态关系样本，应优先解析其 JOIN 条件。

## 7. 执行环境和安全

生产 API 镜像缺少可用 SQL Server Unix 驱动。本轮将本机下载的 `pymssql` wheel 上传至服务器临时目录，并在一次性 `--rm` 容器中使用；没有修改生产 API 镜像或数据库服务器。

- 密码未写入代码、快照、报告、Git或平台表。
- 所有关系查询使用 `TOP 10000`、`NOLOCK` 和 `READ UNCOMMITTED`。
- 所有连接最终 rollback，源库写入为 0。
- 本轮未把 LIS 资产写入平台库；正式接入应建立独立 SQL Server 物理连接和 source/domain，并先备份平台数据库。

## 8. 产物

- `81_LIS_SQLServer元数据快照.json`
- `81_LIS_SQLServer关系验证结果.json`
- `backend/scripts/harvest_lis_sqlserver_readonly.py`
- `backend/scripts/verify_lis_sqlserver_relationships_readonly.py`
