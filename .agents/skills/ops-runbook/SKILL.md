---
name: ops-runbook
description: 数据资产平台生产运维四件套标准件——8.83 容器内连库只读探查、业务库受控写修复（备份→单事务→对账→回读→审计）、生产镜像发布（tar→hotpatch 构建→grep 冒烟→切容器→回读）、夜间任务只读核验。用户要求"升级/发布到服务器"、"查夜跑/晨检"、"连库查一下"、"修复这个工号/患者并保证安全"、SSH 到 8.83、docker exec、pg_dump 备份、或任何要在生产服务器/业务源库上执行操作时使用。含已踩坑清单（pg_dump URL 方言、LOB/bytes 序列化、heredoc 中文编码、隧道复用）。
---

# 生产运维 Runbook（ops-runbook）

## 0. 总边界

- 本机 Windows 不直连业务库；一切经 `ssh -o BatchMode=yes -i C:\Users\Administrator\.ssh\id_ed25519_ai root@10.10.8.83`。
- 业务源库（HIS/ODS/Docare/CDMS/JHEMR…）写入必须用户逐例授权；平台库操作按 AGENTS 门禁。
- 生产发布、cron、env 修改须用户点名；口令零落盘（凭据只从 `/etc/data-asset/credentials/` 受控文件注入）。
- 他人域文件零触碰（`bash tools/dev_env.sh --domain-baseline/--domain-check` 管基线）。

## 1. 容器内连库探查（最高频样板，29+ 会话验证）

本地写只读脚本 → stdin 送进容器执行（**禁止 heredoc 内嵌中文长脚本**——031 号会话曾因 GBK 编码损坏 55 号文件；一律本地文件 + `<` 重定向）：

```bash
ssh -o BatchMode=yes -i "C:\Users\Administrator\.ssh\id_ed25519_ai" root@10.10.8.83 \
  "docker exec -i data-asset-api python -" < 本地脚本.py
```

连接标准件（平台 PG 用 SessionLocal；源库用 OracleConnector）：

```python
from pathlib import Path
from app.services.db_connectors import OracleConnector

def src_conn(cred, host, service):  # 凭据文件名见 /etc/data-asset/credentials/
    u, p = Path(f"/etc/data-asset/credentials/{cred}").read_text(encoding="utf-8").strip().split(":", 1)
    return OracleConnector(host=host, port=1521, database=service, user=u, password=pwd,
                           connection_mode="direct", oracle_client_lib_dir="/opt/oracle", timeout_ms=120000)
```

- 平台库：`from app.core.db import SessionLocal`（容器内即生产/开发库）。
- 直连写事务（仅获授权后）：`oracledb.init_oracle_client(lib_dir="/opt/oracle")` + `oracledb.connect(user, password, dsn="host:1521/service")`，`autocommit=False`。
- Oracle 需厚模式；JHEMR 直连须 `-e APP_IDENTITY_SYNC_DIRECT_CONNECTION=true`。

**输出序列化标准件 norm()**（RAW/BLOB/LOB/date 均处理，4+ 会话踩坑后固化）：

```python
def norm(v):
    if v is None: return None
    if isinstance(v, (bytes, memoryview)): return bytes(v).hex()[:2000]
    if type(v).__name__ == "LOB":
        d = v.read()
        return bytes(d).hex()[:2000] if isinstance(d, (bytes, memoryview)) else str(d)[:8000]
    return str(v)[:8000]
```

- 脱敏：结果进报告前剔除 PATIENT_NAME/PHONE/ADDRESS/证件类列；工号可留（用户已给）。
- SQLite 差异坑：db.sqlite 的 JSON 列用 `json_extract(data,'$.role')`，**没有**实体列。
- 测试库隧道与 URL：`source tools/dev_env.sh`（一键建 15432 隧道+推导 `APP_TEST_DB_URL`，复用已有转发不杀别人的）。

## 2. 业务库受控写修复（17 会话成型，181/182 实证）

五步，缺一不可，全部留痕：

1. **侦察**：数据字典定位受影响表集（如 `all_tab_columns` 三键拥有表逐表 count>0），**主键成分列（如 VISIT_ID）的修订必须全链同改，否则断链**；
2. **预检**：目标键冲突必须全 0、源行数与预期一致；
3. **备份**：受影响行全列 SELECT → JSON 落 `8.83:/opt/data-asset/evidence/<主题>/`（目录 700、文件 600、记 SHA-256 前 16 位）；
4. **执行**：单事务，逐表 UPDATE 后 `rowcount` 与备份数对账，**不符立即 rollback 整例**；每例独立事务，单例失败不连坐；
5. **回读+审计**：复核查询验证目标形态；平台 `GovernAuditLog` 写一行（module/entity_ref/action/operator=标识串/before/after）。

- 回滚 = 按备份 JSON 逆向 UPDATE。
- **pg_dump 备份坑（两次会话踩）**：`APP_DB_URL` 是 `postgresql+psycopg://` 方言，pg_dump 不认——先 `sed s/postgresql+psycopg/postgresql/`；宿主机 pg_dump 在 `/usr/local/pgsql/bin/`。备份文件命名 `data_asset_pre_<tag>_<ts>.dump`。

## 3. 生产镜像发布（153/166/169/171/174/180/181 验证；详细版见 179/180 号文档）

```text
1. git 分组提交（整文件归组、每组 show 零越界、他人域禁入）
2. DB 备份：pg_dump（见 §2 坑）→ /opt/data-asset/backup/ + SHA
3. 打包：tar czf r<N>_dist.tar.gz backend/app backend/alembic backend/alembic.ini backend/scripts deploy/docker/Dockerfile.hotpatch
4. scp → /opt/data-asset/hotpatch/r<N>-<date>/ 解包
5. 构建：cd 解包目录 && docker build -f deploy/docker/Dockerfile.hotpatch \
     --build-arg BASE_IMAGE=<基底镜像> -t data-asset:r<N>-<date> backend/   # context=backend/！
6. grep 冒烟（镜像内）：docker run --rm --entrypoint grep <img> -c <标记串> <路径>，逐个标记 ≥1
7. 切换：DATA_ASSET_IMAGE=data-asset:r<N>-<date> bash /etc/data-asset/scripts/run_data_asset_api.sh
8. 回读六项：docker ps healthy / health 200 / settings 关键值未变 / alembic head 不变 / 三端点 401 / 镜像内标记 grep 复核
9. 回滚：DATA_ASSET_IMAGE=<旧镜像> 同脚本；env/cron 不动
```

- 镜像不含 runner（Dockerfile 只 COPY app/alembic）——新子任务接线须另行 docker cp 或全量构建（180 W-02 决策）。
- 前端：`deploy` 目录 `release_frontend.sh` 原子切换，hash 逐字一致校验。

## 4. 夜间任务只读核验（晨检模板，7+ 会话）

```sql
-- 最新夜跑 + 子任务 + 计数守恒（平台库）
SELECT run_id,status,circuit_breaker_triggered,circuit_breaker_dimension,candidates_total,
       success_count,failed_count,skipped_count,started_at
FROM asset.asset_identity_scheduler_runs ORDER BY started_at DESC LIMIT 3;
SELECT subtask_code,status,planned_count,succeeded_count,failed_count
FROM asset.asset_identity_sync_subtasks WHERE run_id=:latest;
```

- 判读：success+例行 resync 执行=预期；熔断看 dimension 定位阈值；`protected` 过滤跳过=预期非异常。
- docare 每日错配任务：`docker exec -i data-asset-api python - < /opt/data-asset/scripts/docare_mismatch_daily.py --patient <pid>`（只读核对模式）。

## 5. 已踩坑速查（中断预防）

| 坑 | 预防 |
|---|---|
| pg_dump `role "root" does not exist` / 方言 URL | scheme 转换 §2；显式传 URL |
| bytes/LOB JSON 序列化失败 | 统一 norm() §1 |
| heredoc 中文经 stdin 编码损坏 | 本地文件 + `<` 重定向，禁 heredoc 长脚本 |
| 并行会话互踩测试库/僵尸 pytest | 全量前 `tasklist` 清点非本会话 pytest；跑完重灌 import170.py |
| 镜像/发布窗口竞态（他方先发布） | 发布前 git log+docker ps 双快照；改动尽早提交占位 |
| README/大文件超 25k tokens | Read 带 offset 分段；工具大输出转 stdout 日志文件再读 |
| 用户选项卡未答 | 按"未答=不越权"处理记 SKIP，不空转等待 |
