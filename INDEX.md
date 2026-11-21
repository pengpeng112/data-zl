# INDEX.md —— 仓库路由地图（agent 第一跳）

> 路由缓存，不复制版本或进度数字。目录权威：`开发起步包/README.md`；未完成入口：`开发起步包/55_系统未完成事项统一执行计划.md`。按需切片读取，禁整读大文件。

## 物理目录

| 位置 | 角色 | 用途 |
|---|---|---|
| `INDEX.md`、`AGENTS.md`、`CLAUDE.md` | 启动 | 路由、统一规则、转发（`CLAUDE.md` 仅转发 `AGENTS.md`） |
| `开发起步包/README.md` | 唯一目录 | 演进总览、活跃入口与编号文档登记 |
| `开发起步包/55_系统未完成事项统一执行计划.md` | 未完成入口 | 只读顶部当前批次与工作线；历史章节文末留跳转 |
| `开发起步包/NN_*.md` + 同号 JSON/报告 | 专题 | 先查 README 编号，再读正文 |
| `开发起步包/output_rNN/` | 运行证据 | 按 `run_id` 定位；`output_r215/` 含 Day1–Fix3 隔离验收证据 |
| `开发起步包/数据资产_*/` | 机器资产 | 平台不可用时离线回退，须注明快照日期 |
| `开发起步包/_archive/` | 历史归档 | 历史计划、会话导出与 QA/实验纯文本见证，禁执行旧授权 |
| `backend/`、`frontend/`、`deploy/`、`drivers/` | 代码与部署 | 看各自 `AGENTS.md` 与 `deploy/offline/README.md` |
| `.agents/skills/`、`tools/` | 技能与工具 | 只读 SQL/治理/运维/接手技能；`ai_handoff.py` 与 `check_*` 脚本 |
| `取数/` | 本机取数 | 先读 `取数/START_HERE.md`，交付归集 `取数/exports/序号、任务名/`（gitignored） |
| `三仓库互通地图.md`、`review/`、`verify/` | 跨仓与评审 | 跨仓细节查地图；历史评审不作当前授权 |
| `_scratch/`、`artifacts/`、`CacheDB.jar` | 临时与驱动 | 清理后仅留计划 205 快照与 2026-11 脚本；`CacheDB.jar` 保留勿删 |

## 想做 X → 读 Y

| 想做什么 | 去哪里 |
|---|---|
| 开始任何开发、排查或文档任务 | 先读 `AGENTS.md`，再看 `开发起步包/README.md` 相关分组与 `开发起步包/55_系统未完成事项统一执行计划.md` |
| 连库查表结构 / 日常只读查询 | 全局 `~/.zcode/skills/sjzc/SKILL.md` + `开发起步包/216_数据库连接说明_AI工具与项目通用.md` |
| 日常取数、保存 SQL 与口径治理 | `取数/START_HERE.md` + `.agents/skills/query-governance-intake/SKILL.md` |
| 历史 SQL 关系解析与图谱摄取 | `.agents/skills/sql-relation-intake/SKILL.md` |
| 生产发布、夜跑核验与受控修复 | `.agents/skills/ops-runbook/SKILL.md` |
| 跨会话断点续跑与任务接手 | `.agents/skills/project-task-resume/SKILL.md` |
| Day1–Fix3 收官与工程治理基线 | `开发起步包/55_系统未完成事项统一执行计划.md`、`开发起步包/output_r215/fix3_zero_failure_and_scale_closure/总收官验收报告_DAY1至FIX3.md` |
| 后端或前端修改与测试 | `backend/AGENTS.md`、`frontend/AGENTS.md` |
| 多 AI 协作占用与文档规范 | `开发起步包/204_启动入口与文档分层整理及持续维护执行计划.md`（§8 + `tools/ai_handoff.py`） |
| 全源只读再探索与差量分析 | `开发起步包/205_全系统数据库只读再探索与差量分析长任务计划.md` |
| 三甲复审（88/189/191/195/218） | 已迁 E 盘独立工作区（见 `AGENTS.md`「三甲独立工作区」节，本仓仅提供受控连接器） |
| 新 HIS 源码/安全分级/整改/UI 验收 | `开发起步包/219_新HIS源码hisuser库表结构关系值域分析报告.md`、`开发起步包/210_数据资产安全分类分级功能核查与完善改进执行计划.md`、`开发起步包/211_系统需求任务偏离核查与架构完善改进执行计划.md`、`开发起步包/212_整改后前后端全栈与判断准确性详细测试执行计划.md`、`开发起步包/213_前端界面布局核查与美化整改执行计划.md` |
| 跨仓库联动与医院运维知识 | `三仓库互通地图.md`、HIS 日常故障排查见 `AGENTS.md` 技能路由表 |

## 目录守护表 & 新文件规则

- **13 个他人域保护文件**：`frontend/src/layout/` 等 8 件 + `tools/capture_*` 5 脚本，禁未授权修改（`tools/dev_env.sh --domain-check`）。
- **主开发域（`backend/`、`frontend/` 其余）**：含 Day1–Fix3 未提交成果；编辑前必先 `python tools/ai_handoff.py status` 与 `git status --short`，`claim` 后改动、交付 `release`。
- **新文件落点**：临时脚本放 `_scratch/`；构建日志/离线包放 `artifacts/`（根目录禁 `_tmp_*`）；取数交付放 `取数/exports/` 下新建序号中文子目录（见 `AGENTS.md`）；新编号文档先用 `tools/register_doc.py` 取号并在 `开发起步包/README.md` 登记。
- **用户新建文书自动规范**：用户新放入的文书/需求/表格由接手 AI 顺带按 `AGENTS.md` §5 归位、取号补头并登记 `开发起步包/README.md`（原件保留不删，被替代旧版只迁 `开发起步包/_archive/`）。
