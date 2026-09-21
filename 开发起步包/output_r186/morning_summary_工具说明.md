# 186 · 晨检汇总只读工具说明（morning_summary_identity.py）

> 类别：执行附件（output_r186，186 号续：disable_only 夜跑晨检）
> 日期：2026-09-18（会话内日期 2026-09-19 凌晨完成）
> 状态：本地完成，纯只读工具，无生产配置、无部署动作

## 1. 用途与定位

对 186 号 identity 夜跑 **disable_only 窗口**做晨检汇总：只读聚合"人员 / 目标动作（JHEMR、CDMS 双目标）"实际执行情况，固定展示 enable 状态，并把员工侧停用 60 人类目单独列示。数据来源视角与 `backend/scripts/ro_identity_nightly_observe.py` 同为只读（runs/subtasks/account_state_attempts），但本工具面向"窗口进度 + enable 核对"口径，不打印工号。

## 2. 用法

```bash
# 模式①：本地证据文件（无网络）
python tools/morning_summary_identity.py -i evidence.json

# 模式②：平台 API（token 从环境变量读；不硬编码、不回显、不落盘）
export ID_TOKEN=xxx
python tools/morning_summary_identity.py --api http://10.10.8.83 --token-env ID_TOKEN

# 常用参数
--dates 2026-09-10,2026-09-14   # 仅这些日期做"无记录"核对（缺省用证据 expected_window_dates）
--baseline-total 230            # 覆盖批准基线分母（缺省取证据 baseline.approved_total，再缺省 230）
--pending-total 60              # 覆盖待裁决类目分母（缺省 60）
--page-size 100                 # API 模式 runs 列表分页
--format json                   # 结构化输出（text 为默认）
```

退出码：0 正常；2 用法/环境错误（含 token 环境变量未设置）；3 输入文件或 API 错误。

## 3. 证据 JSON 格式

`-i` 模式接受两种形态：

**A. 归一化 schema**（推荐，样例见 `backend/tests/plan186_morning_summary/sample_evidence.json`）：

```json
{
  "baseline": {"approved_total": 230},
  "pending_category": {"total": 60},
  "expected_window_dates": ["2026-09-10", "2026-09-11", "2026-09-12"],
  "config_evidence": {"enable_enabled": false},
  "person_categories": {"pending_adjudication": ["q0001"]},
  "windows": [
    {"date": "2026-09-10", "run_id": "RUN-...", "status": "success",
     "attempts": [
       {"person_code": "p0001", "target_system": "JHEMR", "action": "disable",
        "status": "executed", "reason_code": null, "category": "baseline"}
     ]}
  ]
}
```

- `category`：`baseline`（230 批准范围）/ `pending_adjudication`（60 人类目）；缺省时用 `person_categories` 映射推断，再缺省为 baseline；
- 状态归一：`executed|success`→已执行；`blocked|pending_reconcile`→blocked；`skipped|cancelled_stale`→skipped。

**B. 平台 API 原始导出**：`GET /api/v1/identity-sync/runs` 的 `{"data":{"items":[...]}}`，每个 item 携带 `GET /runs/{run_id}` 详情里的 `account_state_attempts` 数组（API 模式自动按此拼装，本地导出同构即可）。

API 模式另 best-effort 拉取 `GET /api/v1/identity-sync/nightly/status`，从 `run_mode`（如 `disable_only`→关闭）或布尔 `enable_enabled` 提取 enable 配置证据；失败不阻塞（显示"无记录"）。

## 4. 计数口径（严格遵守，与 55 号 186 各 📌 行一致）

1. **人员与目标动作分开计数**：人员按 `person_code` 跨窗口去重；动作按 JHEMR/CDMS 分别统计 executed/attempted/blocked/failed/skipped；
2. **人员"已执行" = 至少 1 个目标 disable executed**（与"20/20 人实际停用（30 动作）"口径一致）；**partial = 仅单目标成对未齐**（如 CDMS 单侧缺失），单独展示、不并入失败也不从已执行中剔除；blocked/failed/skipped 各自单列；
3. **只显示"已执行 X/230"实际数与各窗口明细；禁止按天数/窗口数推算预期进度或完成日期**——工具内无任何此类计算，且页脚明示该口径；
4. **60 人类目单独一节**，标注"待裁决，未纳入 230 批准基线"，计数不并入 X/230；
5. **enable 状态固定展示**（预期关闭）：配置证据 + enable 动作计数；证据显示开启或已有 enable 动作 executed → `**[警告]**` 醒目提示"需立即人工核对"；
6. **无证据日期显示"无记录"，不插值**：仅在 `--dates`/`expected_window_dates` 明确列出的日期核对，未列出日期不生成行、证据日期之间的空档不自动补行；
7. **输出无凭据、无身份证/姓名、无工号**：只输出聚合计数、日期、run_id、状态码；attempt 中混入的 name/id_card/password/token 等字段不会进入输出（测试钉死）。

## 5. 合成样例实跑输出（样例全为虚构数据）

```
# 186 晨检汇总 · disable_only 夜跑（只读）

- 证据来源：文件 sample_evidence.json｜生成时间 ...｜证据窗口数 2
- 口径：人员与目标动作分开计数；partial/blocked 单独展示；仅实际证据计数，不按天数/窗口数推算预期进度或完成日期

## 总览（230 批准基线）
- 人员（跨窗口去重）：已执行 5/230（partial 2｜blocked 1｜failed 0｜skipped 0）
- 目标动作：JHEMR 已执行 7/8（blocked 0｜failed 0｜skipped 1）；CDMS 已执行 5/7（blocked 2｜failed 0｜skipped 0）

## 各窗口明细
### 2026-09-10 · RUN-synth-001 · success
- 人员：已执行 4（partial 1｜blocked 0｜failed 0｜skipped 0）
- 其中待裁决类目：已执行 1（partial 0｜blocked 0｜failed 0｜skipped 0）

### 2026-09-11 · RUN-synth-002 · partial_success
- 人员：已执行 3（partial 1｜blocked 1｜failed 0｜skipped 0）

## 按日期核对（仅列出明确核对日期；未列日期不推断、不插值）
- 2026-09-10：RUN-synth-001（success）——已执行 4 人（partial 1｜blocked 0）
- 2026-09-11：RUN-synth-002（partial_success）——已执行 3 人（partial 1｜blocked 1）
- 2026-09-12：无记录
- 2026-09-13：无记录

## 员工侧停用 60 人类目（待裁决，未纳入 230 批准基线）
- 人员：已执行 1/60（partial 0｜blocked 0｜failed 0｜skipped 0）
- 说明：该类目尚未获批准执行，计数仅为证据留痕，不并入上方 230 口径

## enable 状态（预期关闭）
- 配置证据：证据显示关闭
- enable 动作：无记录
- 与预期一致：未见 enable 开启证据

> 本工具只读；无凭据、无身份证/姓名、无工号输出。
```

enable 反例（证据含 executed enable 动作时）：

```
## enable 状态（预期关闭）
- 配置证据：证据显示关闭
- enable 动作：1 个（executed 1）
- **[警告]** 证据显示 enable 已开启或已有 enable 动作执行——与 186 批准口径（enable 结构性关闭）不符，需立即人工核对
```

## 6. 测试（纯逻辑，合成 JSON，无网络无数据库）

目录：`backend/tests/plan186_morning_summary/`（no-op conftest 同 plan144 模式；目录名已追加进 `backend/tests/conftest.py` 的 `_PURE_LOGIC_SUBDIRS`，该文件仅此两行新增）。

**结果：15 passed（0 failed），约 0.3s。** 覆盖：两模式（文件/API fake fetch，含 token 不回显、Bearer 头、端点族断言）、人员/动作分开计数与跨窗口去重（5/230、JHEMR 7/8、CDMS 5/7）、60 人单列不并入 230、无证据日期"无记录"且不插值、enable 三态（配置开/动作 executed/无证据）与警告、无进度推算字样（"预计/还需/剩余窗口/ETA"零出现，"预期进度/完成日期"仅存在于口径声明行）、输出脱敏（姓名/身份证/密码/token/工号零泄漏）、JSON 格式、用法错误退出码、缺文件退出码 3。

验收命令（已执行全绿）：
`cd F:\python\数据资产\backend && .\.venv\Scripts\python.exe -m pytest tests/plan186_morning_summary -q`

## 7. 写路径与安全

- grep 全文：**零文件写**（无 open-write/write_text/mkdir/unlink/replace）；API 模式仅 `urllib` 只读 GET；token 仅经 `--token-env` 环境变量读取，不硬编码、不落盘、不回显；
- 本地证据文件由用户/运维从平台导出提供（导出动作不在本工具职责内）；
- 不连任何业务源库，不触发任何写操作，无生产配置。

## 8. 关联与登记

- 口径来源：`开发起步包/55_系统未完成事项统一执行计划.md` 顶部 186 相关 📌 行（2026-09-09～09-15）；
- 数据视角参照：`backend/scripts/ro_identity_nightly_observe.py`、`app/api/v1/identity_sync.py`（/runs、/runs/{run_id}、/nightly/status）；
- 样例与测试：`backend/tests/plan186_morning_summary/sample_evidence.json`、`test_morning_summary.py`（15 例）；
- 目录登记：本文件未同步登记进 `开发起步包/README.md`（本次会话文件边界未含 README 编辑），待后续会话补登记。
