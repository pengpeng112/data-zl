> 类别：证据  
> 日期：2026-07-13  
> 用户授权：正式写入平台人员表（不写源库）+ HRP 只读补采

# 64 HIS 人员入库与 HRP 补采报告

## 1. 总览

| 任务 | 结果 |
|---|---|
| 1. HIS 人员正式写入平台 identity | **成功** |
| 2. HRP 只读字段补采 | **部分完成**（缺 HRP 直连凭据；已完成 ODS.HRP 镜像 21 表/928 字段） |
| 业务源库写操作 | **零** |

## 2. 任务 1：HIS 人员正式入库（平台 PostgreSQL）

### 2.1 口径

- 主数据：`FXHIS.SYS_EMPLOYEE`
- 补充：`COMM.STAFF_DICT` 独有工号
- 科室：`COMM.DEPT_DICT`
- 桥接：`EMPLCODE = STAFF_DICT.EMP_NO`（rate **0.9846**）
- 源表只读 SELECT；写入仅 `asset.asset_identity_*`

### 2.2 修复

首次 apply 因 `DOCTOR_GROUP` 重复 `(person,dept,source)` 触发唯一约束失败。  
已在 `his_identity_sync._upsert_person_department` 增加同事务 `seen` 去重后重跑成功。

### 2.3 入库结果

| 表 | 写入后行数 | upserted 计数 |
|---|---:|---:|
| `asset_identity_departments` | **816** | 816 |
| `asset_identity_persons` | **4260** | 4260 |
| `asset_identity_person_sources` | **6690** | 6690 |
| `asset_identity_person_departments` | **7831** | 7831 |

| 扫描 | 行数 |
|---|---:|
| DEPT_DICT | 816 |
| STAFF_DICT | 4222 |
| SYS_EMPLOYEE | 2468 |
| DOCTOR_GROUP | 1152 |
| STAFF_VS_GROUP | 9396 |

- `mode=apply`，`dry_run=false`
- 审计：`module=sync` / `entity_ref=his_source_10_10_10_15`
- **HIS/ODS 源库未写入**

## 3. 任务 2：HRP 字段补采

### 3.1 直连 HRP 源库

| 项 | 状态 |
|---|---|
| 地址 | `10.10.10.23:1521/hrpdb` |
| 8.83 → 1521 | **OPEN** |
| 凭据 | **缺失**（无 `HRP_USER`/`HRP_PASSWORD`，无 credentials 文件） |
| 跳板 8.53 | 8.83 SSH **Permission denied**（无私钥） |
| WA_* 8 张核心表字段 | **未能从源库补采** |

### 3.2 回退：ODS.HRP 镜像只读补采（已完成）

从 `10.10.8.216` 的 `HRP` owner 采集元数据：

| 指标 | 值 |
|---|---:|
| 表 | **21** |
| 字段 | **928** |
| WA_* | **0**（镜像中无薪酬 WA 表） |

核心人员相关表均可读：`BD_PSNDOC`、`HI_PSNJOB`、`ORG_DEPT`、`SM_USER`、`BD_PSNCL`、`HI_PSNDOC_EDU` 等。

产出文件（不进 git 凭据）：

- `开发起步包/数据资产_HRP源端资产包/hrp_ods_mirror_tables.csv`
- `开发起步包/数据资产_HRP源端资产包/hrp_ods_mirror_columns.csv`
- `开发起步包/数据资产_HRP源端资产包/hrp_ods_mirror_summary.json`

### 3.3 平台登记

| source_code | enabled | last_check_status |
|---|---|---|
| `hrp_10_10_10_23` | false | `credential_missing` |

系统：`HRP` / HRP/用友NC。

### 3.4 解阻条件（需你提供一次）

在 8.83 创建（权限 600，**不要发到聊天**）：

```bash
# 格式 user:password 一行
install -m 600 /dev/null /etc/data-asset/credentials/hrp_10_10_10_23
# 再写入只读账号
```

或设置环境变量 `HRP_USER` / `HRP_PASSWORD` 后通知继续，即可补采 `WA_DATA` 等 8 张 need_fields 表。

## 4. 与计划映射

| 计划项 | 状态 |
|---|---|
| 59 L11 apply | **完成**（平台 identity 有数据） |
| 59 L12 / 55 T10 HRP | **部分**：镜像字段 OK；源库 WA_ 待凭据 |
| 源库只读红线 | 全程遵守 |

## 5. 复现

```powershell
python backend/scripts/_apply_identity_retry_and_hrp_cred.py
python backend/scripts/_hrp_ods_fallback_harvest.py
```
