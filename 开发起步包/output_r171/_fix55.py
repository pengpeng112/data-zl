# -*- coding: utf-8 -*-
"""修复 55 号顶部编码损坏的 171 pin：切除损坏块，按正确 UTF-8 重插。"""
import io
import sys

P = r"F:\python\数据资产\开发起步包\55_系统未完成事项统一执行计划.md"
s = io.open(P, encoding="utf-8", newline="").read()

# 损坏块特征：从文件头到第一个 "\n\n> 📌" 之前（即插入的 pin+空行）
first_real = s.find("\n\n> 📌", 1)
if first_real == -1:
    sys.exit("未找到原始内容边界，中止")

removed = s[:first_real + 1]
# 校验切除的确实是损坏 pin（不含正确中文）而非原内容
if "171" not in removed or "T0→R4" in removed:
    # 若已是正确编码（含 T0→R4），说明无需修复
    if "T0→R4" in removed:
        sys.exit("pin 已是正确编码，无需修复")
    sys.exit(f"切除块特征异常：{removed[:80]!r}")

body = s[first_real + 1:]

pin = (
    "> 📌 2026-09-01 **171 号（系统前后端全面修复与测试）T0→R4 一次性执行完成**："
    "按用户任务书闭环——T0 基线（隧道重建+export170 工装 import 修复+生产只读重导重灌 12702/1329+他人域 19 文件哈希基线）；"
    "T1 前端 typecheck+253 tests 0 failed+gzip 预算三绿（typecheck 揪出 system-map tone 类型错并修）；"
    "T2 后端全量 **1341 passed/1 skipped/0 failed**（显式隔离库；归因案件 0）；T2.5 强制重灌；"
    "T3 浏览器六查全过（15 截图落 output_r171/），**抓获并修复 169 域 2 活体缺陷**"
    "（搜索聚焦后误报「图谱接口请求失败」面板——focusNode 画布竞态被归类 api_error+errorInfo 成功后从不清；"
    "graph 页 RePageHeader 未导入页头丢失），plan169G2 断言随修复加严（非弱化）；"
    "R3 plan171R3.test.ts 8 用例（Inspector 兜底链红转绿实录/菜单可见性功能测/误报面板回归锁）+depth 控件记录；"
    "**R1 四域本地提交**（da7255e 169 域 18 文件/bec3ad4 167 域 7 文件/8c49b32 170 system-map 3 文件/"
    "d12aaee 171 卫生+R3 2 文件；api/asset.ts 双 hunk 按域补丁拆分；git show 零越界；.gitignore 五项生效；"
    "**git push 未做，留用户/主 AI 复核**）；"
    "**R2 前端原子切换 r171-20260901**（previous=r169-storage-fix 保留可回滚，ASSETS_OK+nginx reload）、"
    "167 后端经 md5×2+容器启动晚于热补 10h 三证**已在产运行改在产核验**（未重启容器）；"
    "T5 容器 healthy+首页/入口 JS 200 且 hash 与本地构建一致+system-map KPI 与生产导出数双证"
    "（浏览器级生产截图待授权用户=P2）；"
    "R4 核对：**165 X2 生产首轮探查仍待授权（生产 findings=0/审计 0 行实证）、165 T7 维持 BLOCKED"
    "（PACSREPORT side-b 待补）、168 P1 与 166 P2 维持开放**；"
    "他人域（登录签名/layout）19 文件哈希终检与 T0 基线完全一致零触碰。"
    "报告 `171_系统前后端全面修复与测试_执行报告.md`+`_结果.json`+`output_r171/exceptions.json`（W1–W9）。\n"
)

io.open(P, "w", encoding="utf-8", newline="").write(pin + "\n" + body)
print("fixed: removed", len(removed), "chars of corrupted pin; re-inserted correct UTF-8 pin")
