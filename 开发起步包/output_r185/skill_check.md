# 185 号 Skill/工具链静态校验留档（C3 / C4 / C6）

> 生成：2026-09-06（R4 批次）；ZCode 无 `skill-creator/scripts/quick_validate.py`，
> 按 185 C3④ 降级为人工清单目检（frontmatter / 路径存在性 / 行数 / 代码块变量）。

## C3 project-task-resume 静态校验（人工清单）

| 检查项 | 结果 | 证据 |
|---|---|---|
| frontmatter（name/description） | ✅ | `name: project-task-resume`；description 含触发词（接手/续跑/恢复中断任务/断点续跑） |
| SKILL.md 行数 ≤150 | ✅ | 86 行 |
| references/ 三案例文件存在 | ✅ | case-147（41 行）/ case-177（39 行）/ case-180（41 行） |
| 案例源文件路径正确 | ✅ | 147 在 `_archive/147_146界面完善中断交接与续跑提示词.md`（已归档非现行，回放文件已注明）；177/180 计划与执行报告均在主目录 |
| Skill 内引用的工具存在 | ✅ | tools/check_doc_index.py、tools/check_test_environment.py、tools/dev_env.sh |
| AGENTS.md 路由行 | ✅ | 插入 1 行（ops-runbook 行之后、「后续 AI 不得依赖聊天记忆」行之前），git diff --stat = 1 insertion |
| .gitignore 白名单 | ✅ | 照 ops-runbook 先例两行；`git check-ignore -v` 确认 SKILL.md 被白名单命中（不忽略） |
| 三案例回放语义 | ✅ | 147=中断续跑复用 DONE 项；177=阻塞分型（时点/输入/资源）+SKIP 纪律；180=分段授权+观察点未出数不宣称验证 |

## C4 全局技能引用只读核查（R3 附加项）

| 对象 | 是否引用 tools/multi_ai_evidence.py |
|---|---|
| `~/.zcode/skills/multi-review/SKILL.md` | ❌ 未引用（grep 无命中） |
| `~/.zcode/skills/multi-verify/SKILL.md` | ❌ 未引用（grep 无命中） |
| 仓库内 `.agents/skills/*/SKILL.md` | ❌ 未引用 |

**结论：S4 调用链未接。** 包装脚本已交付（tools/multi_ai_evidence.py，6 单测全绿，
含单缺席收口/全缺席未完成报告两验收用例），但 multi-review/multi-verify 全局技能
尚未改为调用它——改全局技能不在 185 授权范围（S4 仅交付薄包装）。后续接线属
新任务，须用户点名。

## C6 ops-runbook 事后质检（184 产物复核）

| 检查项 | 结果 | 备注 |
|---|---|---|
| frontmatter（name/description） | ✅ | name: ops-runbook；description 触发词齐全 |
| 引用路径：tools/dev_env.sh | ✅ | 存在；`--domain-baseline/--domain-check` 子命令实测可用（R0 已用） |
| 引用文档：179/180 号 | ✅ | 两文件均在 开发起步包/ 主目录 |
| 代码块变量名（§1 src_conn） | ✅ | `u, p = ...split(":", 1)` → `user=u, password=p`；v1.1 修复（password=pwd→p）在位，无需再修 |
| norm() 序列化标准件 | ✅ | bytes/memoryview/LOB 分支齐全 |
| 服务器侧路径（/opt/data-asset/…） | ⚠️ 本机不可核 | 属 8.83 服务器路径，非本机断言对象；R5 夜跑只读核对将实际走 §1/§4 标准件顺带验证 |
| pg_dump 方言注记（§2） | ✅ | `postgresql+psycopg→postgresql` sed 转换与 /usr/local/pgsql/bin 路径记载完整 |

**C6 结论：无需修复。** 未发现语法/变量级错误。
