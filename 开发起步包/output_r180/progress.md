# 180 批执行进度（progress.md，2026-09-05）

授权：用户点名按 `180_G13分域提交与G1G3生产发布一次性执行计划.md` 执行 → A+B+C+D1(排程)+E；push/D2/G2 未授权未做。

## R0 开工自检 ✅

- HEAD=96ed027 ✓；stash=0 ✓；快照落 `workspace_snapshot.txt`（含 A 段收口追加）。

## A 段 · G13 分域提交 ✅（9 组，零 push）

| # | sha | 内容 | 文件数 |
|---|---|---|---|
| A1 | 5487ebf | chore(hygiene): ignore one-shot work dirs（_r172/_r175 生效实证） | 1 |
| A2 | 9a1616b | feat(174): quality governance ledger backend | 14 |
| A3 | a9925dd | feat(175): import scripts | 2 |
| A4 | 5664365 | fix(177): catalog readback/recipe 422/edge label/v-perms | 9 |
| A5 | f691abb | feat(identity): FFREE3+login/sign 子任务模块+F-2 | 14 |
| A6 | ce8e9a8 | fix(alembic): CREATE SCHEMA IF NOT EXISTS | 3 |
| A7 | ab18625 | fix(178): GraphToolbar 单向数据流 | 3 |
| A8 | 013b6a4 | feat(quality): 174 前端 + 178 互链（含 177 C3 一行） | 11 |
| A9 | 809f0b2 | docs(173-180) 全部报告/计划/output 证据目录（150 删除按现状） | 162 |

- A0 确定式核对：白名单 51 项全脏 ✓；残留恰=他人域 13 文件+工作目录 ✓；每组 `git show --stat` 零越界 ✓。
- 收口冒烟：backend `pytest tests/alembic_env` **4 passed**；frontend 三测试文件 **16 passed**。

## B 段 · G1+G3 后端发布 ✅

- B0 侦察：r175 镜像在；run 脚本 `/etc/data-asset/scripts/`；cron=`/etc/cron.d/data-asset-identity-nightly`（容器路径）；磁盘 41G。
- B1 上载 2.9M（runner md5 双侧 63daf260 一致）。
- B2 备份 `data_asset_pre_r178_20260905.dump` **139M**。
- B3 镜像 `data-asset:r178-20260905`（e42bfaf55360）：FFREE3=11 / resync_unchanged=5 / SCHEMA_DDL=2 / login_sign_adapter=1。
- B4 切换（575a9b28）：healthy+DB connected；三端点 401；alembic=d5e6f7a8b9c0 不变；settings 150/130。
- B5 runner 核验：保持 r175 旧版（**刻意不 cp**，避免未授权激活 G2 login_sign 子任务；login_sign=0/signature=1 实证）。
- B6 MAX_NEW 130→50（env 备份 bak-maxnew-20260905；重建 25970c9185b6；settings 终值 **150/50**；health 200）。

## C 段 · 前端 r178 原子切换 ✅

- 构建三预算 PASS；入口 `index-vXKROi89.js` 本地=服务器解包=生产 HTML 三处逐字一致。
- `release_frontend.sh r178-20260905`：ASSETS 校验过；current→r178；nginx reload；首页 200；API 经 nginx 401。

## D1 · 夜跑验证 ⏳ 已排程

- automation-2f3ff9ec（2026-09-06 02:25 触发，一次性，只读）：验证 F-2 首个夜窗，产出 `nightly_d.md`；不做 D2。

## E 段 · 收口 ✅

- 本文件 + `release_evidence.md` + `exceptions.json`（W-01~W-04）+ `180_G13提交与G1G3发布_执行报告.md` + `_结果.json`；README/55 各登记一次。

## 红线自检

零 push / 零 checkout / 零 stash / 零 reset；他人域 13 文件未入任何提交；cron 只读未改；Dockerfile 未改；业务源库零连接；凭据零落盘（口令仅存命令变量）。
