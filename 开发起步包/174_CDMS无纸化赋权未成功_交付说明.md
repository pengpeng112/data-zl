> 类别：交接执行文档
>
> 状态：**部分完成（2026-09-02 只读核验已闭合 H1/H2/H3/H6；H4/H5 待用户确认「不行」的具体表现后再写库）**
>
> 关联：`172_CDMS无纸化用户权限模型与下乡名单核对.md`（§0 三层模型+三大陷阱、§5 权限补齐、§6 FFREE3 事件）｜`173_全栈模拟测试_问题清单.md`（无关，勿混）｜工装与证据 `开发起步包/output_r171/r172_*.py`

# CDMS 无纸化赋权未成功·交付说明（174）

## 0. 一句话任务

下乡人员（及其他平台同步建户人员）在 CDMS 无纸化系统里「没有赋权成功」——账号在、权限行也在（本会话已补齐并复核），但用户实测仍不可用。**接手 AI 需要先搞清「不可用」的具体表现，再定位真正的生效条件，完成赋权并验证。**

用户 2026-09-02 原话链：
1. 「其中人员需要开启无纸化的权限和角色，请你根据每天同步的任务处理下，之前导入过但是角色和科室都没有成功」
2. 「举例说明，工号 004066 还是不对，你可以和 004019 比较下，她的是对的」
3. 「当前还是不行 拿刚才那个可以举例，我看了还是没有赋权成功 004066」

## 1. 第一步必须是：向用户澄清「不行」的具体表现（三选一，决定根因方向）

| 表现 | 根因方向 | 已有反证/证据 |
|---|---|---|
| A. 登录就失败（密码错/账号无效） | FPWD 密码模板（平台写入的是全院默认密文模板）或账号状态 | 004066 `LOGINERRORCOUNT=NULL`、从未有登录记录——若用户真试过登录失败，此计数为何为空需要解释（也可能系统不启用计数） |
| B. 能登录但功能空白/看不到病案 | 权限行的「值」系统不认（科室码无效/角色 GUID 不被解析） | 权限行结构与 004019 完全同构（见 §3.4），但值的「可解析性」未验证（§5-H1） |
| C. 管理员在界面「用户管理→权限配置」里看 004066 显示未赋权 | 界面读取的表/列与 T_MSS_AUTHMAPPING 不同源（应用层表或字典 join 失败） | 172 已证 `T_MSS_EMP_DEPT`/`T_MSS_USERTOCATEGORY` 为 0 行空壳、AbpUsers 只有 admin——但界面实际读哪张表未确认（§5-H6） |

用户原话「我看了还是没有赋权成功」更接近 C（用户在**看**配置界面），但务必确认。**建议第一步就向用户要：004066 的具体报错文案/截图，或让用户描述操作路径。**

## 2. 环境与通道（全部实测可用）

| 目标 | 通道 | 说明 |
|---|---|---|
| CDMS 只读（能看到 KESHID 字典） | sjzc 技能 live：`paperless_cdms_oracle_10_10_10_93` | 172 §0 用它核实过三层模型；**KESHID（AAA=科室码、BBB=科室名）只有这个身份可见** |
| CDMS 读写（平台同步用的） | 生产容器内 `CdmsIdentityAdapter`（凭据 ref 在容器 env） | 连接身份=**XTWH**；`docker exec` 见 §2.1 |
| 平台生产库（data_asset@8.83 PG） | `ssh root@10.10.8.83` 后本机 psql / 或临时隧道 `-L 15434:127.0.0.1:5432` | 连接串从 `/etc/data-asset/backend.env` 的 APP_DB_URL 推导（凭据零落盘红线） |
| 后端容器 | `data-asset-api`（镜像 data-asset:r169-20260830，healthy） | |
| 每日同步任务 | 宿主机 cron `/etc/cron.d/data-asset-identity-nightly`（02:00，docker exec 带门禁 env 跑 `run_identity_modified_nightly.py`） | 本会话所有写操作都复用了这条通道与 env 集合 |

### 2.1 容器内执行模板（与夜间任务同 env）

```bash
docker exec -e APP_IDENTITY_SCHEDULER_PROVIDER=host_cron -e APP_IDENTITY_NIGHTLY_ENABLED=false \
  -e PYTHONPATH=/app -e APP_IDENTITY_SYNC_ENABLED=true -e APP_IDENTITY_JHEMR_PASSWORD_WRITE_ENABLED=true \
  -e APP_IDENTITY_CDMS_FID_SEMANTICS_CONFIRMED=true \
  -e APP_IDENTITY_PHASE_D_APPROVAL_VERSION=identity-nightly-modified-20260805-v1 \
  -e APP_IDENTITY_SYNC_DIRECT_CONNECTION=true \
  data-asset-api python /tmp/<脚本>.py
```

只读探查可省略门禁 env，只留 `APP_IDENTITY_SYNC_DIRECT_CONNECTION=true`。

## 3. 已核实事实链（时间线，全部有证据脚本）

1. **172 号核对（2026-09-01）**：33 人下乡名单，6 人有权限、24 人在户无权限行、3 人未建户、赵慧工号存疑（名单 001172 无 CDMS 户；库内同名 000110）。三层模型与三大陷阱见 172 §0（FID=被授权人、FUSER=操作人恒 admin、FUSERSTATE 无停用语义）。
2. **根因一（已修）**：26 人平台分类 `legacy_unmanaged`（LEGACY_CUTOFF 存量线先于职称规则）→ 夜间 MODIFIEDTIME 增量管线永不认领。2026-09-02 经夜间任务同代码路径（`_process_single_candidate(reconcile_existing=True)` → `align_existing_user`/`apply_single_user`）补齐 27 人：24 人补角色（FTYPE=0 医疗质控 a1c9192fbe31423fab2dce6f81791b88）+科室（FTYPE=2）+基础（3/100005、5/A00001、10/1），3 人新建户（001324/003176/002124）。**独立只读复核 ALL_27_OK**（每人权限行零缺失、FDEPT=主科室）。run=RUN-f2513dc373c1，审计 actions 27×2、managed_relations 54 行 active。
3. **用户第一次报障 004066** → 全列 diff（vs 004019）：权限行同构、FUSERSTATE 同 0；差异=004019 FSYSID=1/FFREE3='1'/有登录记录，004066 FSYSID=2/FFREE3=NULL/从未登录。全库统计：1735 登录账号 99.7% FFREE3='1'；**未登录 46 户全部 FFREE3=NULL 零例外**（FSYSID/FUSERTYPE 非开关，各值都有登录用户）。
4. **根因二（已修）**：平台建户模板 `_SQL_INSERT_EMP` 漏 FFREE3 列。修复：46 户数据 `FFREE3 NULL→'1'`（46/46 复核，审计 operator=r172_ffree3_fix）+ adapter 四处根修（模板/INSERT/binds/align 幂等补 FFREE3），identity 测试 146P 全绿，容器已热修（明晚夜间任务建新户自动带）。
5. **用户第二次反馈：004066 仍「没有赋权成功」**。复查：FFREE3=1 仍在、权限行 5 行仍在。→ FFREE3 不是（或不是唯一的）生效条件。

### 3.4 004066 vs 004019 当前状态快照（修复后，仍不对 vs 对）

| 项 | 004066 吕尊辉（不对） | 004019 赵仁清（对） |
|---|---|---|
| EMP_DICT | FDEPT=040465, FSYSID=2, FUSERTYPE=0, FUSERSTATE=0, **FFREE3=1(已修)**, FPWD=B946…(16位密文), LOGINERRORCOUNT=NULL, LASTLOGINDATE=**从未** | FDEPT=040507, FSYSID=**1**, FUSERTYPE=0, FUSERSTATE=0, FFREE3=1, FPWD=AE56…(16位密文), LOGINERRORCOUNT=0, LASTLOGINDATE=2026-08-19 |
| AUTHMAPPING | 5 行：FTYPE=0 角色 a1c9192f…、2=040465、3=100005、5=A00001、10=1；FDATE=2026-08-20；FUSER=admin | 5 行：FTYPE=0 同角色 GUID、2=040507、3=100005、5=A00001、10=1；FDATE=2026-06-15；FUSER=admin |

剩余可见差异仅：**FSYSID(2 vs 1)、FPWD 密文不同、FDATE、登录史**。FSYSID 全院 1671 户=2（含大量正常用户）看似非开关，但注意 004019 属少数 FSYSID=1 组——若厂商语义是「1=病案/无纸化子系统、2=其他子系统」，则**登录入口/客户端版本不同的用户需要的 FSYSID 不同**，值得向厂商确认（§5-H2）。

## 4. 生产库已变更清单（接手 AI 必读，避免误判基线）

**CDMS（10.10.10.93，经平台受控执行器/容器脚本）：**
- 27 人 AUTHMAPPING 新增行（24 人补齐+3 新户全套）+ 对应 FDEPT 修正（幂等 align，只增不删）
- 3 个新 EMP_DICT 户：001324 李进叶/003176 安鹏（0503 影像科）、002124 李威（050202 病理科）
- 46 户 FFREE3 NULL→'1'（含 004066；含崔忠丽 003888——她另有 133 行历史手工权限，本会话未动）
- 上述全部有平台审计（asset_govern_audit_logs：r172_ffree3_fix 一行 + identity actions/batches/managed_relations）

**平台生产库（data_asset）：** managed_relations +54 active、sync_batches/actions/scheduler_runs 各一批（run=RUN-f2513dc373c1）、审计若干行。

**容器热修：** `/app/app/services/cdms_identity_adapter.py` 已被替换为带 FFREE3 修复版（容器原版=git HEAD 零差异，替换是纯增量）。**镜像重建会回退——工作区 `backend/app/services/cdms_identity_adapter.py` 的修改需随下批正式提交发布。**

## 5. 未验证假设（按优先级；每条带验证方法）

- **H1（最高）科室码有效性**：权限行 FTYPE=2 与 FDEPT 写的是 HIS 侧科室码（6 位或带 H 的 7 位病区码，如 030422H）。若无纸化系统解析科室用的是自己的字典（172 记录为 CDMS.KESHID：AAA=6位码、BBB=科室名），**码不在字典=行在而系统不认=「没有赋权成功」**。验证：用 sjzc 只读身份查 KESHID 中 040465（004066 的码）与 040507（004019 的码）是否存在；再抽 46 户的 FDEPT 全量命中率（本会话想查但写身份 XTWH 下 KESHID 不可见，ORA-00942，见 H3）。
- **H2 FSYSID 语义**：004019=1 而平台模板=2。全院 1671 户=2 大多正常，但不能排除「不同登录入口/客户端需要不同 FSYSID」——需厂商确认 FSYSID/FFREE3/FUSERTYPE 的官方语义（当前全部结论来自数据统计推断，**厂商一句话能顶十天排查**）。
- **H3 两连接身份可见库不一致**：平台写身份 **XTWH** 下 `ALL_TABLES` 查不到任何 KESHID 表；172 用 sjzc 只读身份能看到。→ ①172 的「科室码=KESHID.AAA」映射仅 sjzc 视角成立；②界面对话框里的科室列表来源表待确认（可能 KESHID 在另一 owner 下，XTWH 无授权）。验证：sjzc 身份 `SELECT OWNER FROM ALL_TABLES WHERE TABLE_NAME='KESHID'`。
- **H4「看」的到底是什么**：用户「我看了还是没有赋权成功」——若是管理员配置界面里看 004066 权限页显示空，则界面读取源≠AUTHMAPPING（或 join 字典失败同 H1）。验证：让用户截图，或厂商确认「用户管理→权限配置」页面的数据来源表；也可在测试环境用 admin 界面打开 004019 与 004066 对比截图。
- **H5 密码**：平台建户/对齐从不改 FPWD（新户写全院默认密文模板 `fetch_mode_fpwd_ciphertext()`）。004066 的 FPWD 即该模板。用户若用错初始密码→登录失败（表现 A）。验证：问用户登录时用的密码规则，或厂商确认默认密码。
- **H6 应用层角色表**：172 已排除 AbpUsers（仅 admin）/USERTOCATEGORY（0 行），但未穷尽 ABP 框架角色表（AbpRoles/AbpUserRoles 等）。若界面/功能读应用层角色，则 T_MSS_AUTHMAPPING 写得再对也不生效。验证：sjzc 身份列 CDMS owner 全部表名，找出含 ROLE/PERMISSION 的候选并查数据量。

## 6. 建议执行顺序

1. 向用户拿「具体表现+截图/报错文案」（§1 三选一）——**不打这一步，后面全是盲查**。
2. sjzc 只读验证 H1（KESHID 命中率）+ H3（KESHID owner）+ H6（角色表清单）——纯只读，半小时内。
3. 拿 H1/H3 结论对照：若科室码不匹配→修正映射（平台 person_departments→CDMS 码表的转换层）并重跑 align（工装现成，见 §7）；若 H4 指向界面读别的表→按厂商语义补写对应表（需用户授权）。
4. 同步向用户/厂商确认 H2（FSYSID/FFREE3 官方语义）——若厂商给语义，回头修正 CDMS_BASE_TEMPLATE。
5. 每次变更后用 `r172_verify.py` 模式独立只读复核（勿信写入方自述）。

## 7. 工装与证据索引（`开发起步包/output_r171/`）

| 文件 | 用途 |
|---|---|
| r172_reconcile_xiaxiang.py | 权限补齐主脚本（dry/apply 两态；改 EMPS 名单可复用于任意批次） |
| r172_verify.py | 独立只读复核（注意 AUTHMAPPING 键名大写 FTYPE/FAUTHORITYID、EMP_DICT 键 FDEPT——本会话踩过小写坑） |
| r172_cmp.py / r172_full.py | 两人对比 / EMP_DICT 全列 diff（含 FPWD 长度脱敏展示） |
| r172_probe2.py | 全库登录事实统计（FFREE3 证据） |
| r172_probe3.py | 46 未登录户清单+模板参考账号 904/1036（已不在库） |
| r172_fix_ffree3.py / r172_audit2.py | FFREE3 修复+审计留痕（审计表真实列：module/entity_type/entity_ref/action/before_data/after_data/operator/reason） |
| cdms_xiaxiang_check.json / cdms_grant_missing.sql | 172 号原始核对与手工 SQL（SQL 方案已被管线方案取代，留作字典参考） |

## 8. 红线与已知坑

- 源库写仅两条路：平台受控执行器（夜间任务代码路径）或用户明确授权的最小幂等 UPDATE+审计留痕；一切 DELETE 禁止。HIS/CDMS 直连探索一律只读。
- 凭据零落盘零回显；姓名/身份证不进日志（工单只允许工号+姓名）。
- 容器内 adapter 热修会随镜像重建回退（见 §4）；`backend/app/services/cdms_identity_adapter.py` 工作区改动待提交。
- 测试库隧道 15432 会话间会断（`ssh -i C:/Users/Administrator/.ssh/id_ed25519_ai -fN -L 15432:127.0.0.1:5432 root@10.10.8.83` 重建）；APP_TEST_DB_URL 从服务器 env 推导（162 §1.2）；**隔离库序列已修但若再跑 import170 重灌会复发**（173 P1-1，修复 SQL 见 173 结果.json env_repair）。
- Oracle：源库旧版用 ROWNUM 不用 FETCH FIRST；XTWH 身份 KESHID 不可见（ORA-00942）不代表表不存在，是授权差异。
- 他人域未提交改动（identity_sync_*、jhemr_identity_adapter、conftest、layout 等）零触碰；本会话新增改动仅 `cdms_identity_adapter.py` 一个文件+文档。

## 9. 2026-09-02 只读核验结论（sjzc live，零写入）

**总判断：数据层赋权已经做成；004066 现在「看起来没赋权」更像是 CDMS 科室字典落后 HIS，而不是权限行没写上。能解决，但下一步必须先确认用户看到的是界面空白还是登录失败，再决定写 KESHID 还是核默认密码。**

### 9.1 假设闭合

| 假设 | 结论 | 证据 |
|---|---|---|
| H1 科室码不在 KESHID | **成立，但是运行时非阻断** | 004066 `FDEPT/FTYPE=2=040465` 在 `CDMS.KESHID` 0 行；参照 004019 `040507` 命中（神经外一科二）。全院 EMP 1781 户中 289 户 FDEPT 不在 KESHID，其中 **272 户有登录记录**。同批 002751 `040466` 也不在 KESHID，却于 2026-08-18 登录成功。001708 `030227` 不在 KESHID，2026-09-02 仍登录成功。 |
| H2 FSYSID 1 vs 2 | **排除为开关** | FSYSID=1：110/110 登录过；FSYSID=2：1625/1671 登录过。平台模板写 2 是主流可登录组。禁止把 004066 改成 1。 |
| H3 KESHID owner / 写身份 | **闭合** | sjzc 只读身份可见 `CDMS.KESHID`（646 行，owner=CDMS）。XTWH 写身份不可见是授权差，不是表不存在。 |
| H6 ABP 角色表 | **排除** | `AbpUsers`/`AbpUserRoles` 统计行约 1（仅 admin）；`T_MSS_PAGEROLE` 0 行。业务权限落点仍是 `T_MSS_AUTHMAPPING` + `T_MSS_ROLE`。角色 GUID `a1c9192f…` 在 `T_MSS_ROLE` 存在，名=医疗质控角色。 |
| H4 界面读源 / H5 密码 | **仍开放** | 004066 `LASTLOGINDATE` 仍 NEVER、`LOGINERRORCOUNT` 仍 NULL——没有登录尝试痕迹。用户原话「我看了」更接近管理员界面。 |

### 9.2 004066 当前与参照的真实差异

HIS `COMM.DEPT_DICT`：`040465=创伤骨科(手足一组)`，`040466=创伤骨科(手足二组)`。这两码是 HIS 新组，**CDMS.KESHID 从未收录**（邻近有 040413 创伤骨科、040423 创伤骨科一、040432 手足外科一、040451 手足显微外科，不能擅自替映射）。

EMP_DICT 全列对比后，除科室码、FSYSID、登录史、日期外，`FROLEID`/`FPAGEROLE`/`FISAUDIT`/`FFREE1/2/4` 双方都是空；AUTHMAPPING 五行星结构与 004019 同构（含 FST=0、FPRIVIEGETYPE=FTYPE、32 位主键）。

### 9.3 可执行修复（均需用户授权，本会话未写）

1. **若管理员界面科室显示空（表现 C，优先）**：把 HIS 新科室写入 `CDMS.KESHID`（至少 `AAA=040465, BBB=创伤骨科(手足一组)`，建议同批补 `040466`）。禁止把 004066 改绑到 040423/040432 等邻近码——会串病案范围。写 KESHID 走受控执行器+审计，禁止 DELETE。
2. **若本人登录失败（表现 A）**：平台建户复用全院默认 FPWD 密文（算法未知，见 adapter `fetch_mode_fpwd_ciphertext`）。向信息科确认该密文对应的明文初始密码，让 004066 用该密码登录；**不得在日志/文档回显密文或明文**。
3. **长期**：`cdms_identity_adapter` 在写 FTYPE=2 前对 `KESHID.AAA` 做存在性检查，未命中则拒绝或登记「HIS 新科室待同步 CDMS 字典」，避免再出现「行在、界面空」。
4. **禁止**：改 FSYSID、改 FPWD、映射错科室、DELETE 权限行。

### 9.4 仍需用户一句话

请确认 004066 是：A 登录失败（报错原文）/ B 能登录但看不到病案 / C 管理员「用户管理→权限配置」里科室或角色显示空。有截图更好。确认后按 §9.3 对应项执行。
