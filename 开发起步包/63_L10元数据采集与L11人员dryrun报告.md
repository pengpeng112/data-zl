> 类别：证据  
> 日期：2026-07-13  
> 约束：业务源库仅 SELECT；dry_run 不写 identity 主数据

# 63 L10 元数据采集与 L11 人员 dry-run 报告

## 1. 结论

| 项 | 结果 |
|---|---|
| ODS 活库元数据采集 | **成功** snapshot_id=3，**540 表 / 19189 字段**（核心 10 owner） |
| HIS 活库元数据采集 | **成功** snapshot_id=4，**1237 表 / 19912 字段**（主业务 12 owner） |
| HIS 人员/科室 dry-run | **成功**；部门 816、人员 4222、医嘱组 1152；**identity 表 0 写入** |
| 源库写操作 | **零** |
| 平台库写入 | 仅元数据快照 + 数据源 last_check（PostgreSQL） |

前置连通见 `62`。本轮修复了采集器 ROWNUM 漏 schema、批量采列，以及 `COMM.SYS_EMPLOYEE` 缺失时 dry-run 中断问题。

## 2. L10 元数据采集

### 2.1 ODS `ods_8_216`（live_source）

- 标签：`live_ods_core_20260713_1043`
- schema_filter：`HIS,CDA,ODS,LIS,PACS,YDHL,SM,JHEMR,MTL,PORTAL_EMPI`

| owner | 表 | 字段 |
|---|---:|---:|
| HIS | 275 | 8531 |
| CDA | 86 | 4103 |
| MTL | 34 | 1809 |
| YDHL | 31 | 702 |
| JHEMR | 31 | 521 |
| SM | 25 | 969 |
| ODS | 19 | 827 |
| PACS | 18 | 891 |
| LIS | 11 | 538 |
| PORTAL_EMPI | 10 | 298 |
| **合计** | **540** | **19189** |

与历史 `08` 快照量级一致（HIS≈273 等）。

### 2.2 HIS `his_source_10_10_10_15`（live_source）

- 标签：`live_his_core_20260713_1043`
- schema_filter：`MEDREC,ORDADM,LAB,EXAM,COMM,INPBILL,OUTPBILL,OUTPADM,INPADM,DRUG_USER,PHARMACY,MEDADM`

| owner | 表 | 字段 |
|---|---:|---:|
| COMM | 384 | 3460 |
| MEDREC | 163 | 3522 |
| LAB | 137 | 1706 |
| DRUG_USER | 123 | 3281 |
| PHARMACY | 102 | 1931 |
| MEDADM | 73 | 604 |
| INPBILL | 67 | 1878 |
| ORDADM | 55 | 1344 |
| EXAM | 39 | 456 |
| OUTPADM | 36 | 490 |
| OUTPBILL | 32 | 555 |
| INPADM | 26 | 685 |
| **合计** | **1237** | **19912** |

与 `25` HIS 源端资产包量级一致（约 1234 表 / 19831 字段）。

### 2.3 代码修复

1. `metadata_collector.py`：`schema_filter` 直接作为 owner 列表；Oracle **按表批批量** 采 `all_tab_columns`；`list_schemas` 改 `all_users`。
2. 首次空快照（id=1/2）因旧版 `ROWNUM` 漏 owner，可忽略。

## 3. L11 HIS 人员 dry-run

| 扫描对象 | 行数 |
|---|---:|
| COMM.DEPT_DICT | 816 |
| COMM.STAFF_DICT | 4222 |
| COMM.SYS_EMPLOYEE | **0（表不存在）** |
| COMM.DOCTOR_GROUP | 1152 |
| COMM.STAFF_VS_GROUP | 9396 |

| 指标 | 值 |
|---|---|
| prepared.persons | 4222（以 STAFF_DICT.EMP_NO 为主键） |
| prepared.departments | 816 |
| doctor_group matched / unmatched | **1148 / 4** |
| bridge_rate | `null`（无 SYS_EMPLOYEE，无法做 USERID 桥接） |
| dry_run upserted | 全 0 |
| identity 表行数 | persons/departments/sources/links **均为 0** |

`collect_notes`：`COMM.SYS_EMPLOYEE: missing_or_inaccessible`。

### 3.1 代码修复

- `his_identity_sync.py`：可选表缺失不中断；`source_code` 统一为 `his_source_10_10_10_15`；凭据可回退读 `/etc/data-asset/credentials/...`。
- 单测中 `source_code` 同步更新。

## 4. 运行时固化

宿主机脚本：`/etc/data-asset/ensure_oracle_ro_runtime.sh`

- 将 `libclntsh.so` → 19.1
- 将凭据目录 `docker cp` 进容器  

**仍无 bind mount**；容器重建后需重跑该脚本（或改 docker run 挂载）。

## 5. 与计划映射

| 计划 | 本轮状态 |
|---|---|
| 59 L10 | **连通 + 核心 owner 活库快照完成**；与 08 的正式 diff 报表未做 |
| 59 L11 | **dry-run 完成**；桥接率因无 SYS_EMPLOYEE 不可算；未 apply upsert |
| 55 T9 | 阻塞从「无法连库」→「可 dry-run，待业务复核与审批后 upsert」 |

## 6. 用户确认（2026-07-13）

| 议题 | 用户答复 | 落地 |
|---|---|---|
| SYS_EMPLOYEE | **以 SYS_EMPLOYEE 为主** | 源库真表为 **`FXHIS.SYS_EMPLOYEE`**（非 COMM）；代码已改；dry-run 重跑见 §8 |
| 未匹配 DOCTOR_USER | **忽略即可** | 不再单列异常清单 |
| dry_run=false 写平台 | 需白话解释后再定 | 见对话说明；**尚未执行写入** |
| HRP / 凭据挂载 | 需白话解释后再定 | 见对话说明 |
| snapshot 与 08 diff | 未指定 | 暂不做 |

## 7. 后续建议（解释后由用户拍板）

1. 是否把 dry-run 结果**正式写入平台**人员表（只写平台 PostgreSQL，不写 HIS）。
2. 是否做 HRP 人事表只读补采。
3. 容器 credentials 挂载持久化（运维配置）。

## 8. 补验：FXHIS.SYS_EMPLOYEE 为主（同日）

| 指标 | 值 |
|---|---|
| 表 | `FXHIS.SYS_EMPLOYEE`（2468 行） |
| 桥接规则 | `EMPLCODE = COMM.STAFF_DICT.EMP_NO`（USERCODE 全空） |
| bridge_hits / rate | **2430 / 0.9846** |
| prepared.persons | **4260**（员工主档 + STAFF 独有补充约 1792） |
| identity 写入 | **仍为 0**（dry_run） |
| 源库写 | **零** |

## 7. 复现

```powershell
python backend/scripts/_ro_continue_l10_l11_v2.py
python backend/scripts/_ro_verify_counts.py
```
