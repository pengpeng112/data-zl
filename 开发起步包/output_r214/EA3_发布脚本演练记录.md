# E-A3 前端发布脚本 previous 锚点维护——修复与演练记录（214 批次A）

> 对象：`deploy/scripts/release_frontend.sh`（未实际发布，仅本地干跑；生产动作不在本轮）
> 日期：2026-10-07

## 1. 缺陷定位（比 214 §4 表述更进一步：根因是两处叠加缺陷，均已复现）

生产表现（r210 执行报告 §6）：三次发布（r169→r203→r210）后 previous 恒指 r169，r210 人工修正。

repo 脚本（696cc47 起）第 62—66 行"看似"维护 previous，实际两处缺陷：

1. **`cp -d "${CURRENT_LINK}" …`**：current 是"指向目录的软链"时，部分 cp 实现按目录复制处理，`-r` 未指定直接拒绝（本机 Git Bash 复现：`cp: -r not specified; omitting directory 'current'`）。
2. **`mv -f "${PREVIOUS_LINK}.tmp" "${PREVIOUS_LINK}"`（决定性根因）**：previous 已是"指向目录的软链"时，`mv -f` 把 .tmp **移进该目录内部**而非替换链接（缺 `-T`）。干跑实锤：`releases/sim-r169/previous.tmp` 残留。→ **第二次发布起 previous 永不更新**，与"恒指 r169"完全吻合（首次发布时 previous 不存在，mv 是重命名语义，恰能建成 r169）。

## 2. 修复内容

- 显式 `readlink` 取旧 current 目标 → `ln -sfn` 造 `.tmp` → **`mv -Tf`** 原子替换 previous。
- 新增切换后校验：current 原始目标必须等于本次 target；previous 不得与 current 同目标（不等则 `exit 1`，宁可发布失败也不留错锚点）。
- 同版本复跑改为 **no-op 成功**（previous 不动）——避免重传同版本时覆盖回滚锚点。
- 校验用 `readlink` 原始值比对而非 `readlink -f`（MSYS 下 `-f` 不解析末级软链；Linux 亦无必要）。

## 3. 演练（临时目录 /tmp/r214_drill，MSYS=winsymlinks:nativestrict 真软链；未触碰任何正式 releases 目录、未发布）

| 场景 | 结果 | current → / previous → |
|---|---|---|
| 发布1 sim-r169（首发布，无 current） | rc=0 | sim-r169 / none |
| 发布2 sim-r203 | rc=0 | sim-r203 / **sim-r169** |
| 发布3 sim-r210 | rc=0 | sim-r210 / **sim-r203**（r210 当时应有的正确状态） |
| 发布4 sim-r211 | rc=0 | sim-r211 / sim-r210 |
| 同版本复跑 sim-r211 | rc=0（no-op） | sim-r211 / sim-r210（锚点不动） |
| 负例：index.html 引用缺失资源 | rc≠0，切换前失败 | 锚点不变 |
| 残留检查 `find releases -name previous.tmp` | 0 | — |

`bash -n` 语法检查：通过。

## 4. 边界与遗留

- 仅改 repo 内脚本；**生产服务器上的脚本副本同步属发布链动作，不在本轮**（下次发布前需确认服务器副本为本修复版）。
- 未执行任何真实发布/回滚（214 §7.5 禁止）。
