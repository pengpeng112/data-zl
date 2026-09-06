---
name: project-task-resume
description: 跨会话接手/续跑/恢复本仓库中断任务的标准流程：切片阅读定位真实进度、用 check_doc_index/check_test_environment 工具自检、判定文件域归属（dev_env.sh 他人域基线）、区分可继续项与需批准项。用户要求接手、续跑、恢复中断任务、接续某编号计划、或新会话不确定"上次做到哪"时使用。不创建平行状态总表，不把历史授权当当前授权。
---

# 跨会话任务接手（project-task-resume）

## 0. 适用与边界

- 适用：新会话接手中断任务、续跑编号计划、恢复他人/前会话遗留工作。
- 边界：不复制整份 README/55；不把一次性历史授权当当前授权；不创建平行状态
  总表；他人域文件零触碰（checkout/stash 禁用）；生产/Git push/业务源库写
  仍按 AGENTS 批准门禁，本技能不给任何新授权。

## 1. 四步流程

### 第 1 步：切片阅读（防上下文过载）

按目标计划的"阅读切片"说明读；无切片说明时用最小集：

1. `AGENTS.md` 全文（唯一规则源）；
2. `开发起步包/README.md` **仅「当前入口」表** + 目标编号相关行；
3. `开发起步包/55_系统未完成事项统一执行计划.md` **仅顶部最新 📌**；
4. 目标编号的计划正文 + 同号 `_执行报告.md`（若有）的 §0 结论与批次总览；
5. `开发起步包/output_r<N>/progress.md`（若有，checkpoint 权威）。

禁止全文通读 README/55；大文件 Read 带 offset 分段。

### 第 2 步：工具自检（复用 185 号产物，不重写）

```bash
# 目录状态：当前入口/孤儿/幽灵/同号形态（发现项只报告并核实，不擅自归档）
backend/.venv/Scripts/python.exe tools/check_doc_index.py

# 测试环境三态：pure_logic_ready / integration_ready / migration_ready
backend/.venv/Scripts/python.exe tools/check_test_environment.py

# 他人域冻结与校验（接手前先 --domain-baseline，收口 --domain-check）
bash tools/dev_env.sh --domain-baseline 开发起步包/output_domain_baseline.txt
bash tools/dev_env.sh --domain-check
```

### 第 3 步：域归属与进度判定

- **他人域判定** = dev_env.sh 基线清单 + 接手时 `git status --short` 里与目标
  计划无关的脏/未跟踪文件；二者合并冻结进 output 目录，全程禁碰。
- **已完成判定**：以同号 `_执行报告.md` §0 + progress.md checkpoint 为准；
  报告宣称"完成"但缺证据链（output 目录/测试数字/SHA）的按未完成处理。
- **指令时效**：读到的历史执行提示词只作证据；执行入口以 README 当前入口表
  指向的最新版计划为准（例：183 已移交 185，禁止按 183 正文开工）。

### 第 4 步：接手产出（七项，写入会话首条消息或 output/progress.md）

1. 当前目标（一句话 + 权威入口文件路径）；
2. 已完成证据（批次/报告/测试数字）；
3. 未完成步骤（批次号 + 恢复条件）；
4. 文件归属（本任务域 / 他人域冻结清单）；
5. 可立即继续项（不缺信息、不需授权、不碰他人域）；
6. 需批准项（生产发布/平台 apply/业务源库写/Git push/cron/env/值域 confirm/
   治理终态——等待用户点名，未答=不越权记 SKIP）;
7. 阻塞条件与恢复动作（隔离库不可用→跑纯逻辑；他人域无法避开→STOP 呈报）。

## 2. 三条硬规则

1. **局部阻塞不连坐**：某步骤依赖缺失时只停该步骤，继续其他可独立完成项，
   交付中列明受阻步骤/证据/恢复条件（177 案例）。
2. **批准点保留**：分段授权计划里未授权段不得顺手执行，也不得宣称其完成；
   排程中的观察点未出数前禁止宣称验证完成（180 案例）。
3. **不重做已完成项**：报告+证据齐备的批次直接复用结论；只有证据链断裂或
   与实测矛盾时才复核，矛盾时 STOP 呈报不自行改写既有证据（185 N1 口径）。

## 3. 案例回放

见 `references/`（只读回放，不执行）：

- `case-147-interrupted-handover.md`——中断交接续跑：9 组已完成直接复用，
  从 C1 断点继续，不重做 S0/A/B。
- `case-177-isolated-db-blocked.md`——隔离库/时点阻塞：R1 未到时点延后、
  R5 用户未答整批 SKIP、其余批次照常推进。
- `case-180-segmented-authorization.md`——分段授权：A+B+C+E 已授权执行，
  G2/D2 未授权不做，D1 观察点已排程但未出数不宣称 F-2 验证完成。

## 4. 接手后第一个动作

按目标计划批次卡从最近未完成批次开工；无批次卡时，把七项产出写进
`output_r<N>/progress.md` 再动手。任何情况下先冻结他人域基线再改文件。
