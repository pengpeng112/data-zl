> 类别：执行记录
>
> 状态：已完成（2026-08-27，新子任务已上线生产 + 一次性补齐收敛；用户授权"复核后开发执行"）
>
> 上位入口：`55_系统未完成事项统一执行计划.md`
>
> 关联文档：`124_HIS职称同步JHEMR执行与复用说明.md`（子任务模式母版）、107（多科室白名单口径）、122/125（每夜任务链）

# JHEMR 多科室同步子任务开发与一次性补齐执行报告（156）

## 1. 背景与复核结论

用户问"每夜电子病历同步能否覆盖一人多科室（按 HIS 科室）"。评估（含代码证据复核）确认三缺口：

| # | 缺口 | 复核后准确边界 |
|---|---|---|
| 1 | 触发缺口 | 每夜 APPLY 恒传 `reconcile_existing=True`，**MODIFIEDTIME 有变化的人会对齐科室**；但 `COMM.STAFF_VS_GROUP` 纯组变化不产生员工表时间戳 → 永不进候选 → 科室不同步 |
| 2 | 主科室不生效 | `align_existing_user` 只加 `user_dept` 行，不更新 `users.user_dept` 登录默认科室、不迁移 `default_dept_flag` |
| 3 | 覆盖边界 | 每夜托管人口=分类完备活跃医护药（实测 103 人）；3,756 legacy_unmanaged 按设计不托管 |

方案（新每日子任务 + 主科室对齐 + 一次性补齐）经用户批准执行。

## 2. 交付内容（镜像 `data-asset:deptsync3-20260827211250`，生产已上线）

**外科手术发布**：基线 `p144-149-20260826094113` + 仅 6 文件（`identity_dept_sync.py` 新服务、`jhemr_identity_adapter.py` 新增 `apply_user_dept_changes`、`identity_sync_status/audit.py` 聚合扩展、夜跑 runner 接入第四必需子任务、`run_dept_backfill_once.py` 一次性工具）。**刻意剔除**了工作区中并行进行的 153 号 WIP（adapter 的 A6 隧道修复等），避免部署未完成改动。

**业务契约**（107 口径不变）：主科室=`FXHIS.SYS_EMPLOYEE`（权威）；附加科室=`COMM.STAFF_VS_GROUP` 组类别白名单（医生=病区医生、护士=病区护士、药师=无；GROUP_CODE 即病区编码）；期望计算**复用** orchestrator `_get_person_depts`（单一语义源）。目标写法三态：缺 `user_dept` 行→INSERT（additive 永不删）；主科室变化→UPDATE `users.user_dept`+`default_dept_flag` 唯一迁移（变化才写）；已一致幂等跳过。全程 planned action 审计先行→JHEMR 单事务（锁行+旧值核对+逐行影响数=1+回读）→完成态审计；完成态失败留 `target_committed_pending_audit` 并可凭 HMAC 值指纹只读核对补记；HMAC-only 输出（无工号/科室明细）。

**失败关闭**：目标重复行/行数截断/权限缺失/备份摘要不符/回读不一致/审计写失败 → 整批回滚或拒绝写入。子任务为每夜**必需**（失败→overall partial_success）。

## 3. 一次性补齐执行证据（2026-08-27）

| 步 | 结果 |
|---|---|
| S0 复核 | 三缺口全部代码实证；方案评审通过（用户批准） |
| S1 测试 | 专项 `tests/identity_dept_sync/` 9 用例 + title 9 用例 = **29 passed**；镜像内模块导入/方法存在/AST 验证 |
| S2 数据刷新 | 平台采集全量刷新（2527 员工/9479 组关系/17456 人员-科室） |
| S3 计划 | managed 103 人：**dept_adds 47 + primary_changes 13 = 60**，已一致 86，无号 1 |
| S4 备份 | `jhemr_user_dept_backup_20260827.json`（600，SHA 20942029…，13 个主科室变更人的旧值+全部行标记；INSERT 项无旧值） |
| S5 执行 | run `deptbackfill-20260827131336`：47+13=60 全执行，failed=0，单事务回读一致 |
| S6 终验 | **二次计划 dept_adds=0 / primary_changes=0（完全收敛）**；审计守恒：run success 60、subtask 60/60/0、actions 60 executed（47 add + 13 primary） |
| S7 清理 | /tmp 精确清理；平台库变更前备份 `data_asset_pre_deptsync2_20260827210637.dump` |

## 4. 过程发现（登记备查）

1. **并行会话冲突**：153 号执行 AI 正在同一工作区工作（test_153_g1_g3.py 20:56 仍在更新、共享隔离库）——本任务全量 pytest 门禁两次被并发互踩（E 级联/进程中断），已用对照实验证明**非本任务代码回归**；全量门禁待 153 完成后随其收口补跑。这也是采用"手术镜像"而非整树发布的原因。
2. **177 Vastbase 间歇连接黑洞**：同参数连接 0.01s 成功与 20s 挂死随机交替（服务端 accept 偶发挂起，4 连发矩阵实测）。已为补齐工具加重试包装（6 次×2s）；夜跑子任务遇此会失败关闭（次夜自动重试），如频发可后续在 adapter connect 加统一重试（与 153 A6 邻域，建议合并处理）。
3. 测试库种子/TRUNCATE 链在并发下脆弱（预存在问题，归属 130/153 P7 测试基建）。

## 5. 遗留与建议

- 今晚夜跑起 `jhemr_user_dept_sync` 为必需子任务自动执行（组变化次日内同步到 JHEMR）。
- legacy_unmanaged 3,756 人不在托管范围（设计内）；如需扩面另行立项。
- 153 完成后：全量 pytest 补跑 + 下一次常规发布时将本 6 文件并入正式链（当前为手术层，随下次整树发布自然吸收）。
- JHEMR 侧回滚：如需撤销 13 个主科室变更，凭备份文件+SHA 按参数化恢复（同 124 §10 规则，需单独授权）。
