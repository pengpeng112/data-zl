# 178 批等待域呈报包（R6，2026-09-04 晚）

> 呈用户/主 AI 裁决。本批执行 AI 未做任何下方勾选动作；所有"待拍板"项保持原状。
> 按 178 §1.5 要求：本文件誊写 **G1–G17 全量 17 项**（源=177 §4 与 `output_r177/wait_domain.md`），不是 §1.5 速查表子集。
> 165 生产 6 条 open finding 明细仍见 `output_r177/wait_domain.md` 第二节，本轮未重新 COUNT、未代点终态。

## 一、G1–G17 全量清单（本轮后状态）

| # | 事项 | 谁拍板 | 本轮后状态 |
|---|---|---|---|
| G1 | 提交并重建镜像，持久化 CDMS FFREE3 模板/建户 dict/align 逻辑 | 用户点名授权 Git+镜像 | **未动**（代码仍在工作区；容器一重建即丢 172 热修的风险不变） |
| G2 | 生产接入 `jhemr_login_sign_sync` 夜窗子任务 | 用户授权接 cron | **未动**（代码+测试已复核；R1 证实生产子任务列表仍只有 signature/user_dept/education_title 三项，登录/签名方式子任务尚未接线） |
| G3 | 发布 F-2 熔断语义 + 授权 `MAX_NEW` 130 回落 50（F-1 的 150 随之可回默认 100） | 用户授权发布窗口 | **未动，且紧迫度上升**：N1 实证 09-04 02:00 仍熔断（维度=max_change_ratio，见 nightly_n1.md）。F-2 是根治项，已在工作区+9 测试 |
| G4 | 165 X3：生产 6 条 open 探查发现人工终态裁决 | 用户在 `/probe-findings` 界面 | **未动**（6 条 open 维持；本轮新增的互链 ③ 反查按钮可辅助从发现页跳台账，但终态仍人工） |
| G5 | 165 X4：探查调度周期（关/每周/每月） | 用户 | **未动**（本轮零改 cron） |
| G6 | T7 PACSREPORT side-b | 业务提供申请键或授权改模板 | **未动**（BLOCKED 维持） |
| G7 | CDMS 004066：用户选表现 A 登录失败 / B 能登功能空白 / C 管理界面未赋权，再授权写 `KESHID`/核密码 | 用户 | **未选**（178 R0 提问一次未获答复 → R5 整批 SKIP）；未选前禁止写 KESHID/改 FPWD/补权限 |
| G8 | 160 职称包（125 自动 + 44 人工，含身份证禁入 git） | 信息科/DBA | **未动**（SQL 包仍在 `backend/_oa_work/title2026/`） |
| G9 | 150 医保课题三选一（还做/放弃/从备份恢复） | 用户书面裁决 | **未答**（178 R0 提问一次未获答复 → 记"仍开"；截止日 2026-09-04 已到，正文与 150_fill_form.py 仍为 git D；AI 不虚构申报内容） |
| G10 | 144 黄金用例生产种子 + FF_G5_EVAL_GATE 评测开关 | 用户授权发布窗口 | **未动** |
| G11 | 127 Review 批准/配方 active/历史问题重建 | 用户逐项 | **未动**（不自批） |
| G12 | 凭据轮换（门诊 SSH/DRG hisserver/OA admin/ECG sa） | 运维窗口 | **未动** |
| G13 | Git 分域提交（177 改动 + 本轮 C6/C7/L1）+ push | 用户点名文件组 | **未动**（本批零 Git 写；178 §3 R7 已给出四组分域提交预案：fix(173) GraphToolbar / fix(alembic) schema / feat(quality) cross links / docs(178)） |
| G14 | 值域 pending→confirmed（151/175/W3 历史项） | 人工 | **未动**（永不自动 confirm） |
| G15 | 关系草稿升正式（复核池约 98 条） | 独立复核人（非原执行 AI） | **未动** |
| G16 | 112/96 业务库写 | 用户 | **保持关闭** |
| G17 | 176 F-3：主熔断时子任务降级（不因主失败一刀切 skip） | 可选另批 | **未动**；R1 证实 09-04 三子任务仍被 `main_account_sync_not_successful` 一刀切 skip——发布 F-2（G3）后主任务预期 success，该问题自然缓解；F-3 仍可作独立韧性增强 |

## 二、N1 夜跑结论（写入等待域佐证 G3）

- **FAIL（仍熔断）**：`RUN-b3324c242e78`（2026-09-04 02:00，host_cron_modified_sync），circuit_breaker_triggered=True，**维度 max_change_ratio**（09-03 为 max_update）。
- 归因：F-1（max_update=150）已放行 update 维度（110<150）；但生产仍为 F-2 前语义，110 例行 resync 计入 update → ratio 110/110=1.0 > 0.3 熔断。签名/职称/科室三子任务被一刀切 skip，空签名未回补。
- 处置：未调阈值、未热进 F-2、未改 env/cron；等用户走 G3。详见 `nightly_n1.md`。

## 三、本轮新增等待项

| # | 事项 | 说明 |
|---|---|---|
| 新-1 | C6 GraphToolbar 单向数据流 | **代码完成、测试绿（plan178R2 + 图谱既有 47/47；vue/no-mutating-props 归零）**，待随 G13 提交并随下次前端发布上生产 |
| 新-2 | C7 alembic 空库自建 schema | **代码完成（env.py 幂等 DDL；tests/alembic_env 4/4；隔离库 upgrade head no-op、current=d5e6f7a8b9c0 不变）**，待随 G13 提交；生产库已有 schema，发布时为 no-op |
| 新-3 | L1 台账↔探查互链 | **代码完成（① scoped-slot 正向链接两页、② finding_id 消费、③ listQualityObservations 反查按钮；plan178R4 + plan174/166 回归 22/22 绿）**，待随 G13 提交并随下次前端发布；生产观测约 6 条 probe_finding，一页反查即命中 |

## 四、用户两问状态（178 R0 开工问过一次，未获答复）

1. 004066 表现 A/B/C：**未答** → R5 CDMS 整批 SKIP，G7 仍开。
2. 150 课题三选一：**未答** → G9 记"仍开"，AI 不写申报内容。
