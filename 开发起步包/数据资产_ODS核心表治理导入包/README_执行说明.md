# 93 号 v3 执行说明（交给用户手动跑）

> 本文件由会话 AI 编写，已完成步 0（基线核验）+ 步 1（备份）。
> 步 2-6 的 5 个脚本 + 3 个 CSV 已全部写好，按本文操作即可。

## 已完成（会话 AI 做的）

| 步 | 状态 | 产物 |
|---|---|---|
| 步 0 基线核验 | ✅ 对齐 v3 §1.2 | sources=15 / null 列=26894 / 歧义=0 / DATA_CENTER.target_host=NULL |
| 步 1 备份 | ✅ | `backup_asset_pre93_v3_20260727.json`（5.27MB，回滚依据）|

## 你要做的：把脚本 + CSV 传到容器并执行

### 1. 把 4 个脚本 + 3 个 CSV 传到 8.83 容器

在本机 PowerShell（不是 Git Bash，避免中文路径问题）跑：

```powershell
# 脚本传到容器 backend/scripts/
docker -H ssh://root@10.10.8.83 cp `
  F:\python\数据资产\backend\scripts\fix_datacenter_registration.py `
  F:\python\数据资产\backend\scripts\fix_null_column_sources.py `
  F:\python\数据资产\backend\scripts\import_ods_core_governance.py `
  F:\python\数据资产\backend\scripts\import_ods_core_relations.py `
  F:\python\数据资产\backend\scripts\verify_ods_core_relations_readonly.py `
  data-asset-api:/app/scripts/

# CSV 包传到容器
docker -H ssh://root@10.10.8.83 cp `
  "F:\python\数据资产\开发起步包\数据资产_ODS核心表治理导入包" `
  data-asset-api:/app/开发起步包/
```

> 如果 `docker -H ssh://` 不通，用 SCP + docker cp 两步（先 scp 到 8.83，再 docker cp 进容器）。或者直接 SSH 进 8.83 后在容器里执行。

### 2. 进容器执行（按顺序，每步先 dry-run）

SSH 进 8.83 → 进容器：
```bash
ssh root@10.10.8.83
docker exec -it data-asset-api bash
cd /app
```

**步 2：阶段 1 小修补**
```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -m scripts.fix_datacenter_registration --dry-run
# 核对输出: T1.1_changes 应有 target_host/description_cn 追加; T1.4 全 0
# 确认无误后正式执行:
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -m scripts.fix_datacenter_registration
```
**验收 A1.1**（容器内 psql 或 python）：
```python
python -c "from app.core.db import SessionLocal; from sqlalchemy import text; s=SessionLocal(); print(s.execute(text(\"SELECT count(*) FROM asset.asset_systems WHERE system_code='DATA_CENTER' AND target_host='10.10.8.216'\")).scalar())"
# 期望 1
```

**步 3：T1.3 列 source_code 回填**
```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -m scripts.fix_null_column_sources --dry-run
# 核对: null_count=26894, ambiguous_tables=0, status=DRY_RUN_OK
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -m scripts.fix_null_column_sources
# 期望: updated=26894, remaining_null=0, status=OK
```
**验收 A1.2**：`SELECT count(*) FROM asset.asset_columns WHERE source_code IS NULL` → 期望 0

**步 4：阶段 2 表/列导入**
```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -m scripts.import_ods_core_governance --dry-run
# 核对 warnings 清单(重点关注 COLUMN_NOT_FOUND: MTL 中文列名 段落编号/段落内容 是否匹配)
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -m scripts.import_ods_core_governance
```
**验收 A2.1-A2.5**（见计划 §4.4）：tables_updated≈17 / columns_updated≥120 / approved 计数=0 / is_sensitive≥2 / 中文名未覆盖=17

**步 5：关系登记 3 条 draft**
```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -m scripts.import_ods_core_relations --dry-run
# 核对: skipped_existing 应为空(若非空说明 §5.2 已存在,需核对)
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -m scripts.import_ods_core_relations
```
**验收 A3.1**：`SELECT count(*) FROM asset.asset_relation_reviews WHERE source_evidence LIKE 'SQL与数据架构交接文档_20260727%'` → 期望 3

**步 6：抽样验证 G1/G2**
```bash
# 凭据从容器内文件注入环境变量(不打印)
export ODS_8_216_USER=$(head -c100 /etc/data-asset/credentials/ods_8_216 | cut -d: -f1)
export ODS_8_216_PASSWORD=$(head -c100 /etc/data-asset/credentials/ods_8_216 | cut -d: -f2-)
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -m scripts.verify_ods_core_relations_readonly
# 产物: /app/开发起步包/95_ODS核心关系抽样验证结果.json (skipped_ods_unreachable 也算成功,不阻塞)
```

**步 6 验证后处置**（match_rate≥0.99 才写入 asset_relations）：
验证 JSON 输出后，若 G1/G2 的 pass=true，需手动跑 `import_ods_core_relations` 的转正逻辑——但脚本 5 只登记 draft 到 reviews，**转正到 asset_relations 需要你按计划 §5.3 判断**：
- 若 pass=true：把该关系的 validation_status 改 sample_pass + 写入 asset_relations
- 若 pass=false 或 skipped：保持 draft 不动

> 这一步因为涉及判断，建议把验证 JSON 内容贴给我，我帮你决定哪些转正。

### 3. 步 7-8（可选，我帮你做）

- 步 7 pytest 全量：容器内 `cd /app && python -m pytest tests/ -x -q`
- 步 8 交付报告：把各步输出贴给我，我帮你写 94 号报告

## 遇到问题

| 现象 | 处理 |
|---|---|
| 某 step dry-run 报错 | 把错误输出贴给我，我判断是脚本 bug 还是数据问题 |
| COLUMN_NOT_FOUND 多 | MTL 中文列名大小写问题，把 warnings.json 贴给我调整 CSV |
| ODS TNS 不通 | verify 脚本会自动记 skipped，不阻塞，正常现象 |
| 验收数对不上 | 把实际数贴给我，我核对是脚本问题还是基线变化 |

## 回滚（出问题时）

```bash
# 关系/评审:按批标记精确删
docker exec -i data-asset-api python -c "
from app.core.db import SessionLocal
from sqlalchemy import text
s=SessionLocal()
s.execute(text(\"DELETE FROM asset.asset_relations WHERE note LIKE 'SQL与数据架构交接文档_20260727%'\"))
s.execute(text(\"DELETE FROM asset.asset_relation_reviews WHERE source_evidence LIKE 'SQL与数据架构交接文档_20260727%'\"))
s.execute(text(\"UPDATE asset.asset_tables SET business_desc_cn=NULL WHERE business_desc_cn LIKE '%交接文档%'\"))
s.execute(text(\"UPDATE asset.asset_columns SET column_name_cn=NULL,value_desc_cn=NULL,is_sensitive=false,name_cn_source=NULL WHERE name_cn_source='handover_doc_20260727'\"))
s.commit()
print('rolled back')
"
# T1.3 的 source_code 回填如需回退,从备份 JSON 恢复(极端情况)
```
