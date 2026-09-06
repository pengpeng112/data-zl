#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""register_doc.py — 开发起步包「文档四步登记」半自动助手（只打印建议，不改 README）。

用法：
  python tools/register_doc.py                      # 查询当前最大编号与下一个可用编号
  python tools/register_doc.py 开发起步包/184_标题.md # 给定新文档名，生成四步登记模板
  python tools/register_doc.py --check              # 目录自检：转发到唯一检查器 check_doc_index.py

四步（AGENTS 强制）：①编号续用最大+1 ②README 对应分组追加行 ③文档首行类别 ④目录更新记录一行。
本工具只产出模板文本，由 AI/人核对后贴入，避免自动改写 README 出错。
--check 自 185 号 C1 起复用 check_doc_index 的同一套解析函数（唯一规则源，防双检查器漂移）。
"""
import argparse
import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "开发起步包"
README = PKG / "README.md"
NUM = re.compile(r"^(\d+)_")
GROUP_ANCHORS = {  # 新文档常见归属分组 → README 中的表头锚（用于提示贴入位置）
    "执行报告": "## 核心关系证据链",
    "证据": "## 证据链",
    "待办": "## 当前入口",
}


def known_numbers():
    nums = []
    for f in PKG.glob("*.md"):
        m = NUM.match(f.name)
        if m:
            nums.append((int(m.group(1)), f.name))
    return sorted(nums)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docname", nargs="?", help="形如 184_标题.md")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    nums = known_numbers()
    top = nums[-1][0] if nums else 0

    if args.check:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import check_doc_index

        report = check_doc_index.run_checks(PKG)
        check_doc_index.print_report(report)
        return 1 if report["stats"]["findings"]["error"] else 0

    if not args.docname:
        top_name = nums[-1][1] if nums else "无"
        print(f"当前最大编号：{top}（{top_name}）")
        print(f"下一个可用编号：{top + 1}")
        print("登记四步：①编号 ②README 分组行 ③首行 '> 类别：' ④目录更新记录")
        return 0

    m = NUM.match(Path(args.docname).name)
    if not m:
        sys.exit("文档名需形如 NN_中文名.md")
    n = int(m.group(1))
    print(f"""# 登记模板 for {Path(args.docname).name}（编号 {n}，当前最大 {top}）

1) 文档首行：
> 类别：<执行报告/证据/待办/当前——按内容选>

2) README「当前入口」或对应分组追加行：
| P0 | `{Path(args.docname).name}` | <状态> | <一句话用途> |

3) README「目录更新记录」追加行（插在最上方）：
| {Path(args.docname).name.split('_')[0]}-批次日期 | <一句话：为何新增、做了什么、零越权声明> |

4) 若有结果数据：配套同号 `_结果.json`；工件目录 output_r{n}/
提示：编号{'' if n == top + 1 else f'与当前最大 {top} 不连续，请确认不是撞号'}""")


if __name__ == "__main__":
    main()