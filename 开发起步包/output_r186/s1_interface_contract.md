# 186 v1.10 S1 修复接口契约（各文件域共享，主AI维护）

基线：git HEAD a14ba12（2026-09-09 18:17 冻结）。

## 运行模式（P0-1/P0-19）
- `settings.identity_run_mode` ∈ {"observe"(默认), "disable_only", "full"}。
- observe：所有身份目标写入=0（新旧入口全封），采集/决策照常落库。
- disable_only：仅 JHEMR_ACCOUNT_DISABLE / CDMS_ACCOUNT_DISABLE 两个动作可过门禁；
  enable/create/align/login/sign/legacy lock 全部 blocked。
- full：全部动作按其余门禁判定（仅测试用）。
- `identity_dual_source_enforce` 保留：false 时 select_account_state_actions 返回
  空动作结构（population 统计保留）；true 且 run_mode=observe 同样零动作。

## 恢复归因（P0-4/P0-9/P0-16/P0-17/§13.3）
- 两适配器 unlock 签名统一为 `unlock_*(emp_no, *, origin_disable: dict | None = None)`。
- origin_disable keys: `attempt_id:int`, `target_raw_time:str|None`,
  `target_account_fingerprint:str`, `rule_version:str`。
- 时间比较 = 原始值精确比对（无 ±300 容差、无时区换算）；任一侧缺失 →
  blocked attribution_unknown；值变化 → blocked attribution_target_changed。
- lock/成功返回增补 `locked_time_raw`(JHEMR) / `changed_at_raw`(CDMS)（datetime→
  isoformat 字符串，否则 str()；None 保持 None）。
- CDMS `_fetch_user_state` 返回规范小写键 {floginname,fuserstate,fchangedate}，
  从真实 cursor.description 大小写不敏感构建；写路径使用 FOR UPDATE 变体。
- automatic_enable_supported=False（两目标无锁原因/版本字段）→ 生产 enable 关闭。

## 门禁（P0-11/P0-14/P0-18/P0-19）
- 新模块 `identity_sync_action_gate.py`：唯一 dispatch；编排器不再直接 import
  bridge 执行函数。bridge 内部二次 fail-closed。
- 执行器注册（asset_action_executors，种子默认 disabled）：
  JHEMR_ACCOUNT_DISABLE / JHEMR_ACCOUNT_ENABLE（target_source_code=jhemr_vastbase_10_10_8_177）
  CDMS_ACCOUNT_DISABLE / CDMS_ACCOUNT_ENABLE（target_source_code=paperless_cdms_oracle_10_10_10_93）
- 用途绑定（新表 asset_source_purpose_bindings，(source_code,purpose) 唯一）：
  purpose=identity_account_sync；身份状态动作凭据只从绑定解析，零 env/字典回退。
- 批准引用 settings.identity_phase_d_approval_version == "186-20260909-disable-only"（生产）。

## 范围与预算（P0-19/P0-20/§13.5）
- 新表 asset_identity_action_scopes(+members)（冻结批准名单）与
  asset_identity_window_budgets(+reservations)（每窗≤20 唯一人员，试点共享预算）。
- select_account_state_actions 输出：本窗 disables/enables、deferred_budget、
  backlog_pending、backlog_unapproved、population/scanned/truncated/remaining、
  blocked_no_decision/blocked_no_person/blocked_conflict/blocked_protected/
  blocked_unknown 计数。
- 阈值判定用本窗计划集；全体积压单列不隐去（P0-20）。

## 采集（P0-6/P0-10）
- employees/sys_users keyset 分页（EMPLCODE/EMPL_CODE 升序子查询+ROWNUM），
  记录 scanned/truncated/source_complete；ORA-01031/ORA-00904 → incomplete，
  不是"表缺失"；source_complete=false 不推进水位、不算普通 success。
- sys_user_row_in_scope：TYPE 必须为 "1"（NULL/未知不在范围）。
- 多账号：任一 disabled→disabled；否则 unknown(sys_user_multi_account_unconfirmed)。

## 时钟健康（§13.2，新模块 identity_clock_health.py）
- 每目标 3 次串行只读采样（JHEMR clock_timestamp/current_setting；CDMS
  SYSDATE/SYSTIMESTAMP/DBTIMEZONE/SESSIONTIMEZONE），t0/t1 UTC+monotonic RTT，
  偏差区间含 RTT/2+量化误差；TTL 300s；样本≤3、单次超时5s、RTT上限2s。
- enable 门禁要求 healthy；disable_only 继续但报 clock_health。
