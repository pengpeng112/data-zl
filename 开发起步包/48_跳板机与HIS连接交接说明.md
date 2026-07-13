> 类别：环境

# 跳板机、HIS 与部署服务器连接交接说明

> 目的：给后续 AI/开发者提供可复用的跳板机、数据中心 ODS、HIS 业务库和平台部署服务器连接方式。本文只记录连接路径和命令模板，不记录明文密码或 Token；账号密码从既有安全渠道或环境变量读取。

## 1. 网络拓扑

```text
本机开发机 Windows
  |
  | SSH key
  v
10.10.8.53:40022  跳板机 / 欧拉工具机
  |
  | Oracle thick mode / SELECT only
  +-- 10.10.8.216:1521/orcl  数据中心 ODS 汇聚库
  |
  +-- 10.10.10.15:1521/his  HIS 业务库（多 owner）
```

硬约束：本机 Windows 不能直连 Oracle；历史 ODS/HIS 探库经 `10.10.8.53` 跳板机执行。当前 HIS 人员/科室同步验证按用户最新说明优先走 `10.10.8.83`。
## 1.1 当前验证入口修订

2026-07-13 更新：`10.10.8.83` 是当前已部署的平台服务器，也是 HIS 人员/科室同步的跳转/中转入口。`10.10.8.84` 是历史候选服务器，未作为当前运行环境使用。

后端 HIS 同步服务已支持连接模式配置：

| 配置 | 当前验证建议 | 说明 |
|---|---|---|
| `APP_HIS_SOURCE_CONNECTION_MODE` | `ssh_jump` | 当前通过 8.83 跳转验证；84 打通后可用 `direct` |
| `APP_HIS_SOURCE_JUMP_HOST` | `10.10.8.83` | 当前可用跳转/中转服务器 |
| `APP_HIS_SOURCE_JUMP_PORT` | `22` | 如现场 SSH 端口不同，以实际为准 |
| `APP_HIS_SOURCE_PASSWORD` | 从安全渠道注入 | 禁止写入代码、日志、文档 |

## 2. 跳板机 SSH

本机到跳板机：

```bash
ssh -p 40022 -i ~/.ssh/id_ed25519_ai root@10.10.8.53
```

Windows PowerShell 示例：

```powershell
ssh -p 40022 -i "C:\Users\Administrator\.ssh\id_ed25519_ai" root@10.10.8.53
```

后端 `ssh_jump` 模式默认读取这些配置：

| 配置 | 默认值 | 说明 |
|---|---|---|
| `APP_SSH_JUMP_HOST` | `10.10.8.53` | 跳板机地址 |
| `APP_SSH_JUMP_PORT` | `40022` | SSH 端口 |
| `APP_SSH_JUMP_USER` | `root` | SSH 用户 |
| `APP_SSH_JUMP_KEY` | `~/.ssh/id_ed25519_ai` | SSH 私钥路径 |
| `APP_ORACLE_CLIENT_LIB_DIR` | `/opt/oracle/instantclient_21` | 跳板机 Oracle Instant Client |

## 3. Oracle Thick 模式

源库是 Oracle 11g，必须在跳板机使用 `oracledb` thick 模式：

```python
import os
import oracledb

oracledb.init_oracle_client(
    lib_dir=os.environ.get("ORACLE_CLIENT", "/opt/oracle/instantclient_21")
)
```

注意：Oracle 11g 不支持 `FETCH FIRST`，抽样统一写 `ROWNUM <= N`。

## 4. 数据中心 ODS 连接

连接目标：

```text
host: 10.10.8.216
port: 1521
service: orcl
credential_ref: env:CRED_ODS_8_216 或安全渠道提供
```

跳板机上最小连通性脚本：

```python
import os
import oracledb

oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_21")
conn = oracledb.connect(
    user=os.environ["ODS_USER"],
    password=os.environ["ODS_PASSWORD"],
    dsn="10.10.8.216:1521/orcl",
)
cur = conn.cursor()
cur.execute("SELECT 1 AS ok FROM dual")
print(cur.fetchone())
cur.close()
conn.close()
```

关键说明：`08_数据中心元数据快照.json` 来自该库；`HIS.LAB_RESULT` 约 1 亿行，严禁全表扫描。

## 5. HIS 业务库连接

连接目标：

```text
host: 10.10.10.15
port: 1521
service: his
credential_ref: env:CRED_HIS_SOURCE
```

后端已按该口径登记 HIS 数据源：

| 字段 | 值 |
|---|---|
| `source_code` | `his_ready_10_10_10_15` |
| `db_type` | `oracle` |
| `connection_mode` | `ssh_jump` |
| `host_masked` | `10.10.10.15` |
| `port` | `1521` |
| `service_name/database_name` | `his` |
| `credential_ref` | `env:CRED_HIS_SOURCE` |

`CRED_HIS_SOURCE` 格式由 `backend/app/services/credentials.py` 定义：

```text
CRED_HIS_SOURCE=<readonly_user>:<readonly_password>
```

不要把真实值写入仓库、日志或报告。若部署到服务器，推荐改用 `file:///etc/data-asset/credentials/his_source`，文件第一行为 `<readonly_user>:<readonly_password>`，并限制权限为 `600`。

跳板机上最小连通性脚本：

```python
import os
import oracledb

user, password = os.environ["CRED_HIS_SOURCE"].split(":", 1)
oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_21")
conn = oracledb.connect(user=user, password=password, dsn="10.10.10.15:1521/his")
cur = conn.cursor()
cur.execute("SELECT 1 AS ok FROM dual")
print(cur.fetchone())
cur.close()
conn.close()
```

本机经后端连接器测试时，使用 `ssh_jump`，由本机 SSH 到跳板机，再在跳板机执行 Oracle 查询。

## 6. 后端连接器调用方式

核心实现：`backend/app/services/db_connectors.py::OracleConnector`。

`ssh_jump` 模式行为：

1. 本机通过 `ssh -p 40022 -i <key> root@10.10.8.53` 登录跳板机。
2. 后端把只读 SQL 和连接参数以 JSON payload 传给跳板机上的 Python。
3. 跳板机使用 `/opt/oracle/instantclient_21` + `oracledb` thick 模式访问 Oracle。
4. 查询结果以 JSON 返回本机。

连接检测端点已不是占位，实际会解析凭据并调用连接器：

```text
POST /api/v1/sources/his_ready_10_10_10_15/check
```

## 7. 平台部署服务器（当前运行环境）

| 项目 | 值 |
|---|---|
| 主机 | `10.10.8.83` |
| SSH 端口 | `22` |
| 运维用户 | `root`（仅限批准的运维会话） |
| SSH 凭据 | 既有安全渠道；不得写入代码、文档、日志或 Git |
| 操作系统 | openEuler 22.03 SP2 x86_64 |
| 平台数据库 | 本机 PostgreSQL 14，数据库名 `data_asset` |
| Web 入口 | Nginx 监听 `80`，静态站点 + `/api/` 反向代理 |
| 后端 | Docker 容器 `data-asset-api`，仅监听 `127.0.0.1:8000` |
| 当前镜像 | `data-asset:20260713` |
| 前端目录 | `/opt/data-asset/frontend-dist` |
| 发布目录 | `/opt/data-asset/releases/20260713` |
| 运行配置 | `/etc/data-asset/backend.env`，权限 `0600`，仅服务器 root 可读 |
| 数据库备份 | `/opt/data-asset/backups/`；迁移前备份文件见 58 号记录 |
| 管理员 Token | 仅服务器 root 权限文件保存；按批准的密钥渠道交付，禁止输出到 AI、日志或文档 |

### 7.1 连接与健康检查

从已获批准的终端连接：

```powershell
ssh root@10.10.8.83
```

连接后仅使用以下不含凭据的检查命令：

```bash
docker ps --filter name=data-asset-api
systemctl is-active nginx
curl -fsS http://127.0.0.1:8000/health
nginx -t
```

预期：容器状态为 `healthy`，Nginx 为 `active`，健康检查返回数据库 `connected`。

### 7.2 已知访问限制

2026-07-13 实测：目标机本机 Nginx 和 API 均正常；开发机到 `10.10.8.83:80` 的 TCP 可达，但 HTTP 响应被服务器外部网络链路中断。后续 AI 不应反复重部署服务；应由网络管理员从实际内网客户端核查并放行 HTTP/HTTPS 路径。发布、备份、回滚和后续同步流程以 `58_发布部署与代码同步整改计划.md` 为准。

## 8. 安全与查询红线

- 源库只读，只允许 `SELECT` / `WITH` 查询。
- 禁止任何 DML/DDL：`INSERT`、`UPDATE`、`DELETE`、`MERGE`、`CREATE`、`ALTER`、`DROP`、`TRUNCATE`、`GRANT` 等。
- 禁止在新文档、新代码、日志里写明文密码。
- 姓名、身份证、电话、地址等 PII 输出前必须脱敏。
- `HIS.LAB_RESULT` 等大表必须通过 `TEST_NO` 子查询、明确条件或 `ROWNUM <= N` 限制，禁止全表扫描。
- 探库任务夜间执行并设置超时。

## 9. 常用验证命令

检查跳板机可用：

```powershell
ssh -p 40022 -i "C:\Users\Administrator\.ssh\id_ed25519_ai" root@10.10.8.53 "hostname; python3 --version; ls -ld /opt/oracle/instantclient_21"
```

检查跳板机到 HIS 端口：

```powershell
ssh -p 40022 -i "C:\Users\Administrator\.ssh\id_ed25519_ai" root@10.10.8.53 "timeout 5 bash -c '</dev/tcp/10.10.10.15/1521 && echo his-port-open || echo his-port-closed'"
```

检查后端 HIS 数据源：

```powershell
cd F:\python\数据资产\backend
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

若只需连通性，优先使用后端数据源检测接口或 `OracleConnector.test_connectivity()`，不要手写临时脚本重复散落凭据。

## 10. 接手时先读

- `02_开发环境与资产总索引.md`：连接总入口和历史注意事项。
- `16_hisuser业务库探查报告.md`：HIS 业务库多 owner 探查结论。
- `21_HIS主业务owner关系补验报告.md`：HIS 主业务关系实测。
- `25_HIS源端资产包生成报告.md`：HIS 源端资产包生成口径。
- `README.md` + `55_系统未完成事项统一执行计划.md`：当前开发接手与未完成事项入口；42 号仅在 `_archive/` 历史追溯。
