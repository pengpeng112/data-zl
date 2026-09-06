# 185 号 R6（183-S6 降级版）skill-creator 加载关系只读盘点

> 2026-09-06；纯只读（ls/find/md5sum/cat 配置），未移动/改名/删除/修改任何全局技能。

## 实测事实

| 位置 | 存在性 | 内容 | 状态 |
|---|---|---|---|
| `~/.zcode/skills/`（ZCode 用户级） | 仅 4 个：multi-review / multi-verify / sjzc / wechat-chat-records | **无 skill-creator** | 无同名冲突 |
| `~/.zcode/cli/plugins/cache/zcode-plugins-official/skill-creator/0.1.0/` | ✅（本会话技能清单里 `skill-creator:skill-creator` 即此） | **仅 SKILL.md**（+plugin.json/package.json）；无 scripts/、references/、agents/ | ZCode 唯一激活的 skill-creator（轻量版） |
| `~/.zcode/cli/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/` | ✅（marketplace 源副本） | 全量版：agents/analyzer·comparator·grader、references/schemas.md、scripts/aggregate_benchmark.py、**scripts/quick_validate.py**、eval-viewer | 未被 ZCode 安装激活（installed_plugins.json 的 skill-creator 指向 zcode-plugins-official） |
| `~/.codex/skills/skill-creator/`（Codex 用户级） | ✅ | 全量版（agents/assets/eval-viewer/references/scripts）；SKILL.md md5=68646d7a…，mtime 2026-09-06 06:52（近期刚改） | Codex 域，本计划不动 |
| `~/.codex/skills/.system/skill-creator/`（Codex 系统级） | ✅ | 另一版本，md5=80ee81d4… ≠ 用户级 | Codex 域；系统更新可能覆盖的差异属 183-S6 原始关切，不在 185 收敛范围 |

三份 SKILL.md 两两 md5 不同（68646d7a / 0adc952f / 80ee81d4）——同名三版本分属
两个 CLI 生态，ZCode 内部无遮蔽（shadowing）问题。

## 结论与迁移建议（只建议，不执行）

1. **ZCode 侧无需迁移**：用户级无 skill-creator，插件版（仅 SKILL.md 的轻量版）
   即唯一入口，天然满足 183-S6 验收的"普通 Skill 小修改不强制访谈或评测"。
2. **完整评测流程的迁移路径**：若将来要在 ZCode 使用基准评测，应把
   claude-plugins-official 全量版（或 Codex 用户版）的评测子集沉淀为独立
   `skill-evaluation` 技能（建议放 `~/.zcode/skills/skill-evaluation/`），触发词
   收窄为"基准评测/skill 评测"，与轻量 skill-creator 并存——183-S6 的原始设想。
3. **上游反馈清单**：zcode-plugins-official 的 skill-creator 0.1.0 缺
   `scripts/quick_validate.py`（claude marketplace 版有）——185 C3④ 静态校验因此
   降级为人工清单；可向插件上游提"补齐 scripts"需求，或经用户同意后本地安装
   claude-plugins-official 版。
4. **Codex 侧同名收敛**（用户版 vs .system 版）属 Codex 生态任务，遵循 183-S6
   原则（不直接改系统随附 Skill，先验证发现路径），本计划零触碰。
