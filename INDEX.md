# INDEX.md —— 仓库路由地图（agent 第一跳）

> **定性**：本文件是路由缓存，不是目录权威——登记与状态以 `开发起步包/README.md`（目录唯一权威）与 `开发起步包/55_系统未完成事项统一执行计划.md`（唯一未完成入口）为准；两者更新后本文件须同步一行。**新会话第一步：先读本文件，再按需分段读 README/55，禁止整读大文件。**

## 想做 X → 读 Y

| 想做什么 | 去哪里 |
|---|---|
| 董哥历史SQL成果复核与一次性整改 | `开发起步包/198_董哥SQL资产复核问题与一次性整改执行计划.md`（**B0—B9 已执行（本地）**：解析/查重/来源/验证/配方/值域全链修复；待批准 live 探针 24 条+生产修订+B5 发布+129 源口径；人工队列 73 项；证据 output_r198/r198-20260922-remediation/） |
| 用三甲历史结构/视图再核验关系并纳入平台 | `开发起步包/195_三甲历史表结构与视图关系再核验及平台入库执行计划.md`（AI 侧执行完成 r195-20260919-084932：S7 已入库 114 条草稿待人工审核；S5 11/12 探针；S8 回读 8/8；遗留人工项见 `开发起步包/output_r195/r195-20260919-084932/执行报告.md`） |
| 了解安全红线/技能路由/验证命令 | `AGENTS.md`（根，单一权威） |
| 知道当前做什么/待办 | `开发起步包/55_系统未完成事项统一执行计划.md` 顶部 📌 |
| 诊断维护传染病名称同步到HIS | `开发起步包/196_HIS传染病诊断名称专项同步实现与验收.md`（本地实现；仅DIAGNOSIS_NAME_CRB，生产启用与实际写入待批准） |
| 一次免费AI全功能测试/模拟真人操作 | `开发起步包/194_系统全功能架构与人工操作模拟一次性测试计划.md`（待执行；第12节复制提示词，默认隔离环境只测不修） |
| 患者纵向高质量数据集分阶段开发 | `开发起步包/193_患者纵向高质量数据集分阶段开发执行计划.md`（2026-09-16 B00/B01 DONE；B02—B19 未执行，每日按§11提示词接续，状态见55及193） |
| 找某编号文档/资产包 | `开发起步包/README.md` 对应分组（分段读） |
| 日常取数/保存 SQL/查询资产 | `取数/START_HERE.md`（126 治理入口）+ `.agents/skills/query-governance-intake/` |
| 连库/查表结构 | 全局技能 `~/.zcode/skills/sjzc/`（经 AGENTS 路由） |
| 未探索源库、容量、基础分类与值域计划 | `开发起步包/188_未探索业务数据库只读探索执行计划.md` v2.1（第一步 B13 只读探索已完成 2026-09-17：终版 dry-run 6102/74693、S9 批准包已呈报，S10 生产 apply 待用户批准；当前状态见55） |
| 三甲复审上报 2025 扩窗 / MTL→JHEMR | 交接 `开发起步包/191_三甲复审2025扩窗与JHEMR视图交接.md`；计划口径 `189_*` v1.1。本机已改时间/`_jhemr`，活库未改 |
| 生产运维/发布/夜跑核验 | `.agents/skills/ops-runbook/` |
| 接手中断任务 | `.agents/skills/project-task-resume/` |
| 后端构建/测试 | `backend/AGENTS.md`（薄层：命令+约定） |
| 前端构建/测试 | `frontend/AGENTS.md`（薄层） |
| 找某个脚本干什么 | `tools/.cache/repo_manifest.json`（本地缓存，`python tools/build_repo_manifest.py` 重生成） |
| 看历史评审/对辩证据 | `review/` 目录（round-1…round-10 各轮子目录）、`verify/` |
| 找离线构建/验收产物 | `artifacts/`（gitignored 归拢区） |

## 目录守护表（CODEOWNERS 本地化；基线=tools/dev_env.sh `--domain-check`）

| 目录 | 归属/约束 |
|---|---|
| `frontend/src/layout/`+`captureMode.ts` 等 8 文件、`tools/capture_*` 5 脚本 | 他人域（dev_env 13 文件基线，改动前跑 `--domain-check`） |
| `开发起步包/181*`、`output_r181/`、`.agents/skills/*`（WIP）、`output_r186/` | 并行会话域（round-10 保护清单 `review/round-10-exec/protection_extra.json`） |
| `backend/`、`frontend/` 其余 | 主开发域（改前看 git status，留他人改动） |
| `取数/` | 本机工作区（gitignored；任务目录规则见 START_HERE；`_legacy/` 有危险门禁） |
| `_scratch/`、`artifacts/` | 归拢区（gitignored；见下方产生规则） |
| `review/`、`verify/` | 评审证据（模型间只经此通信） |

## 新文件产生规则（防回潮）

- 根目录禁止新增 `_tmp_*`：调试脚本 → `_scratch/`
- 日志/构建 tar/离线包 → `artifacts/`；frontend 日志不入工程根
- 外部 AI 审查产物 → `review/` 目录（round-1…round-10 各轮子目录） 或 `review/adhoc/`（raw/err 默认忽略；round-N 为通配示例）
- 编号文档：单一整合者经 `tools/register_doc.py` 取号→创建→登记一次完成
- 共享文件（README/55/AGENTS/本文件）：并行会话产出交一方合并；全量 pytest 前清点在跑 pytest

*建立：round-10 文件规范化（2026-09-11）；维护义务：改动被路由目标时同步本表。*
