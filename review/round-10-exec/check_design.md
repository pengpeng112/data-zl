# check_doc_index 扩展设计稿（P1 → P5 实现）

## 目标
在既有唯一目录检查器 `tools/check_doc_index.py` 上扩展三项能力 + 一项提示，不新建第二检查器。

## 扩展点
1. **_archive 子目录扫描**：现 `scan_package()` 对 `_archive/` 只 glob 顶层文件（`is_file()` 跳过子目录）。扩展：`output_r*/` 子目录视为"已归档证据目录"，登记形态=目录行（不做文件级登记，检查其被 README 归档记录提及即可）。
2. **exports 任务编号联检（仅本机有效，输出声明）**：扫描 `取数/exports/` 下目录：任务目录须匹配 `^\d+、` 或在白名单（`_templates`）；登记"无编号目录"为 error、"编号缺位"为 info（缺位合法、只提示）；**因 取数/ 为 gitignored，本项仅本机工作区有效，工具输出首行声明**。
3. **INDEX.md 一致性（warn 级）**：根 INDEX.md 存在时，校验「想做X读Y」**表格第二列**反引号路径 + 全文 `→ \`路径\`` 存在性（断链=warn）。不扫守护表（含 glob/`captureMode.ts` 片段）。`~/...` 环境路径与 `tools/.cache/` 本地缓存缺失记 info。命令反引号（`python ...`）跳过。
4. **编号-标题一致性（warn 级）**：`NN_标题.md` 的正文一级标题含编号 NN 或标题词（如 187 号正文标题"150"→ warn 提示错配）。

## 基线口径（重采法）
扩围检查器就绪后对**当前状态**重采基线 `review/round-10-exec/check_baseline_post.json`；与 P0 前旧基线（error1=181 未登记 / warn1=output_r181）按三分类比较：既有（181 家族，他人域不处理）/ 已修复（本轮登记动作消除的）/ 新引入（本轮改动造成的，须归零或解释）。

## 验收
`tools/tests/` 新增 `test_check_doc_index_ext.py`：exports 编号判定（合法/无编号/白名单/缺位 info）、INDEX 箭头断链 warn、**表格第二列断链 + 命令跳过 + 缓存 info**、编号-标题错配 warn、archive 子目录形态；主路径用 tmp fixture。另有一条对仓库真实 `INDEX.md` 的路由表无 warn 断言（INDEX 不存在则 skip）。
