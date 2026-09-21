# 185 · docare 每日清单脚本可靠性改进报告

> 类别：执行附件（output_r185，185 号续）
> 日期：2026-09-18（会话内日期 2026-09-19 凌晨完成）
> 状态：本地完成，**改进版未部署**；生产 8.83 cron 00:10 仍运行旧版

## 0. 一句话结论

`output_r177/docare_mismatch_daily.py` 已原位叠加可靠性层（连接类错误有界重试 / 总超时 / 锁防重入 / 原子输出 / 非零退出+stderr 摘要 / 脱敏 / 本地告警接口），**v3 四重判据等业务逻辑逐字保留**；纯逻辑 pytest 20/20 全绿；不连生产、不写任何数据库、未发告警、未部署。

## 1. 故障背景（引自 185 号 §10/§11 与 dryrun 副本头部）

- 09-06 / 09-07 两晚 00:10 cron 正常触发，但 `his_visits` 步骤连 ODS 8.216 报 **ORA-12541（TNS 无监听）**，清单 0 字节；
- 白天补跑（--dry-run）正常 → 00:10 前后 ODS 监听时段性不可用（疑夜间维护窗口）；
- 185 号结论"根治三选待点名：cron 后挪 / 脚本重试 / 告警"——本次即"脚本重试 + 告警接口"路线的仓库副本落地，**部署仍待用户点名**。

## 2. 改动点（可靠性层，全部叠加、不删改业务逻辑）

脚本：`开发起步包/output_r177/docare_mismatch_daily.py`（git diff 确认业务函数 scan/apply_hit/dict_tables/plan_fix/backup_group/apply_fix/audit_platform/fall_in/oper_of/norm/creds/ro_conn/ods_conn/rw_conn 与清单文案逐字不变；仅 main() 包裹可靠性层、argparse 化参数）。

| # | 改进 | 实现要点 |
|---|---|---|
| 1 | 连接类错误有界重试 | `RetryController`：ORA-12541/12543/12170/12514/12545/12560/12154/12537/3113/3114/17002 及等价 TNS 短语识别为瞬时；指数退避 5s→60s 封顶，**总预算默认 600s**（`--retry-budget` / env `DOCARE_RETRY_BUDGET_SECONDS`），全程共享预算；仅包裹探活/scan/his_visits/apply_hit（只读阶段） |
| 2 | 脚本总超时默认 30 分钟 | `--timeout` / env `DOCARE_DAILY_TIMEOUT_SECONDS` 默认 1800s：POSIX `SIGALRM` 硬超时 + 全程 deadline 软检查（重试前、逐组循环前） |
| 3 | 锁文件防重入 | `--lock`（默认 `EV_DIR/.docare_mismatch_daily.lock`）O_CREAT\|O_EXCL；占用且未超 stale 阈值 → 立即退出码 2；stale（默认 1800s，`--stale-lock`）自动接管并 stderr 报告前持有者；释放只删自己 token 的锁，不误删接管者 |
| 4 | 清单原子输出 | `--out`：同目录 `.tmp` 写完 fsync、chmod 0600 后 `os.replace`；失败清理 `.tmp`、原文件原样保留 → **0 字节清单与半写清单均不可能再出现**；无 `--out` 时仍 stdout 整段打印（兼容现行 cron 重定向，失败时 stdout 为空） |
| 5 | 失败语义 | 统一 `fail()` 出口：exit 非零（1=其他 2=锁占用 3=重试耗尽 4=总超时 5=输出失败）+ stderr 脱敏摘要（cron.log 可定位 ORA 码） |
| 6 | 脱敏 | 复用平台 `app.services.data_masking.sanitize_text`（导入失败回退本地等价实现）：password/token/连接串等折叠为 `[REDACTED]`；**患者号按既定口径保留**（清单本就含患者号/病案号，受控目录 0600） |
| 7 | 告警适配器 | `AlertAdapter` 接口 + `NullAlertAdapter`（默认关闭）+ `LocalFileAlertAdapter`（`--alert-file` / env `DOCARE_ALERT_FILE`，追加脱敏行）；**无 webhook/生产配置**，接生产渠道需新增子类并另行批准 |
| 8 | 写入类不重试 | plan_fix/backup_group/apply_fix/audit_platform（UPDATE 修订/备份/审计管线）直连单次执行，`RetryController.call(retryable=False)` 语义并有测试钉死 |

新增 CLI：`--out/--lock/--timeout/--retry-budget/--stale-lock/--alert-file`（均带 env 覆盖）；原 `--dry-run/--patient/--fix` 语义不变。

## 3. 写路径检查结论

grep 全量文件系统写调用（os.replace/write_text/open-w/mkdir/chmod/unlink/os.open/fsync）后逐一定位：

- **生产绝对路径仅两类，均与旧版一致**：`EV_DIR=/opt/data-asset/evidence/docare_mismatch`（fix 模式备份 JSON + 默认锁文件，旧版既有）；`/etc/data-asset/credentials/*`（只读凭据文件，旧版既有）；
- 新增写路径全部参数化且默认落在同目录：`--out` 及其 `.tmp`、`--lock`、`--alert-file`（默认关闭=不写任何文件）；
- 本地测试只写 `tmp_path`，未触碰 `/opt`、`/etc`、任何业务库与生产平台；
- 186 工具（见同批 output_r186 说明）**零文件写**，仅 stdout 与 API 只读 GET。

## 4. 测试（纯逻辑，fake connection/monkeypatch，不连库）

目录：`backend/tests/plan185_docare_reliability/`（自带 no-op conftest 覆盖根 autouse，模式同 plan144；目录名已追加进 `backend/tests/conftest.py` 的 `_PURE_LOGIC_SUBDIRS`——该文件仅此两行新增）。

**结果：20 passed（0 failed），约 0.6s。** 覆盖：

1. 重试后成功（退避 5s/10s 序列、清单含患者号、stderr 有 retry 日志与 OK 行、锁释放）；
2. 重试耗尽退出码 3、stderr 含 ORA-12541、清单与 .tmp 零残留、锁释放；
3. 非连接类错误（ORA-00942）不重试、退出码 1；
4. 防重入：新锁二次启动退出码 2 且不发起任何连接；stale 锁自动接管并报告前持有者；
5. 原子输出失败（os.replace 抛错）退出码 5、旧文件内容原样、无 .tmp 残留；stdout 模式失败时不打印任何清单；
6. 凭据脱敏：password 不入日志/stderr/告警，患者号保留；
7. 总超时（注入时钟：deadline 触发 ScriptTimeoutError）与预算耗尽、跨调用共享预算；
8. 写入类不重试：retryable=False 单次；`--patient --fix` 管线中 apply_fix 抛 ORA-12543 只调 1 次即退出码 1；
9. 告警适配器：默认 Null 无副作用；本地文件实现写入脱敏行；失败自动触发；
10. 业务回归：dry-run 清单格式与 185 号留档副本一致（FBINCU=4/本地 1/HIS 4 → 编号体系不一致人工裁决）；自动判据样例（登记=1、本地=HIS=3）在 dry-run 下正确显示"1 表/2 行（未写入）"；
11. 锁释放归属（不误删他人锁）。

验收命令（已执行全绿）：
`cd F:\python\数据资产\backend && .\.venv\Scripts\python.exe -m pytest tests/plan185_docare_reliability -q`

## 5. 部署提示（需用户点名批准，本次未做）

1. **发布脚本**：将改进版拷入 8.83 生产位置（受 ops-runbook 镜像/热补链路约束），属生产变更，须用户点名；
2. **建议 cron 行同步改造**：`--out /opt/data-asset/evidence/docare_mismatch/list_%Y%m%d.md`（原子写）替代 `>` 重定向（重定向模式虽已不半写，但仍会由 shell 预创建空文件）；stderr 继续归档 cron.log；
3. **可选告警**：如需本地文件告警，加 `--alert-file /opt/data-asset/evidence/docare_mismatch/alerts.log`；接生产告警渠道（短信/企微等）需另行开发适配器并批准；
4. 参数默认值（重试预算 600s / 总超时 1800s / stale 1800s）可在部署时按夜间维护窗口长度调整，无需改代码。

## 6. 关联

- 故障与晨检背景：`开发起步包/185_执行报告.md` §10/§11、`output_r185/docare_list_20260906_dryrun.md`、`docare_list_20260907_dryrun.md`；
- 测试：`backend/tests/plan185_docare_reliability/test_docare_reliability.py`（20 例）；
- 目录登记：本文件未同步登记进 `开发起步包/README.md`（本次会话文件边界未含 README 编辑），待后续会话补登记。
