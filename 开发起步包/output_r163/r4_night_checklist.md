# R4 夜间执行清单（2026-08-29 日间登记，夜窗执行）

> 依据：163 §5 R4；159 报告 §修订。会话进行到 R4 时不在夜间窗口 → 按 R4-3 登记 WARN 后继续 R5–R7；夜间部分由夜窗补跑。

## 1. 重采山大地纬（sddw）索引

前置：上传修订后采集器（默认隔离 SYSTEM owner）。

```bash
# 1) 备份服务器旧脚本与旧快照（SSH root@10.10.8.83）
cp /opt/data-asset/evidence/newsrc7-20260827/scripts/harvest_oracle_readonly.py \
   /opt/data-asset/evidence/newsrc7-20260827/scripts/harvest_oracle_readonly.py.bak-r4
# 2) 上传修订版（本机）
scp -i C:/Users/Administrator/.ssh/id_ed25519_ai backend/scripts/harvest_oracle_readonly.py \
   root@10.10.8.83:/opt/data-asset/evidence/newsrc7-20260827/scripts/
# 3) 夜窗在服务器执行（显式超时 300s 每查询由采集器内控；凭据经
#    /etc/data-asset/credentials/sddw_oracle_10_10_10_151.readonly 注入 env，不落命令行）
cd /opt/data-asset/evidence/newsrc7-20260827
timeout 3000 python3 scripts/harvest_oracle_readonly.py \
  --output snapshots/sddw_snapshot_r4.json
# （修订版默认自动发现 owner 并隔离 SYSTEM；不用 --owners SYSTEM）
# 4) 新旧对照：旧 snapshots 内 sddw index_columns=273,631（SYSTEM 混入，作废）
#    vs 新 sddw_snapshot_r4.json summary.index_columns 与 owners 清单（须无 SYSTEM）
# 5) SHA256SUMS 重算并更新（见下）
```

## 2. 新输血候选与校验和同步 8.83

```bash
# 1) 备份服务器旧副本
ssh root@10.10.8.83 'cp /opt/data-asset/evidence/newsrc7-20260827/relation_candidates.json \
   /opt/data-asset/evidence/newsrc7-20260827/relation_candidates.json.bak-r4'
# 2) 上传（本机 → 服务器）
scp -i C:/Users/Administrator/.ssh/id_ed25519_ai \
   开发起步包/数据资产_七系统源端资产包/relation_candidates.json \
   root@10.10.8.83:/opt/data-asset/evidence/newsrc7-20260827/relation_candidates.json
# 3) 校验：两侧 sha256sum 一致（37 候选+23 unresolved 计数以本地为基准）
```

## 3. 159 报告补执行记录

夜间完成后在 `159_七系统只读探查与表结构资产采集报告.md` 补「R4 重采执行记录」节（新旧计数对照表+校验和）。

## 验收（163 R4）

新旧计数对照 + 服务器校验和一致 + 159 补记录；全部只读源库（采集器 SELECT-only），零业务写入。
