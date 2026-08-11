# 数据资产管理平台 — 部署指南

> 状态：本文件保留环境与Nginx参考。**可复现的离线部署流程以 `deploy/offline/README.md` 为唯一执行入口。**
> 当前发布门禁见 `开发起步包/55_系统未完成事项统一执行计划.md`、`123_系统剩余开发与验收收口执行计划.md`及`65_发布门禁与凭据轮换清单.md`。
> 用户已确认取消T13人工凭据轮换阻塞并接受内网继续使用HTTP，因此凭据轮换签字和TLS不再作为封板门禁；当前真实部署阻断仅为最新Linux离线依赖包及干净断网演练尚未完成。

## 0. Docker 运行时硬要求（8.83 当前形态）

容器 `data-asset-api` 必须：

1. **挂载凭据目录（只读）**，避免重建丢账号：

```bash
-v /etc/data-asset/credentials:/etc/data-asset/credentials:ro
```

2. **Oracle Instant Client thick**：目录内 `libclntsh.so` 必须指向 **19.1+**（不要 11.2）。  
   可在镜像构建或 entrypoint 中执行：

```bash
ln -sfn libclntsh.so.19.1 /opt/oracle/libclntsh.so
```

3. 环境文件：`/etc/data-asset/backend.env`（0640），**不进 Git**。生产建议：

```bash
APP_ENV=production
APP_RBAC_REQUIRE_BOUND_TOKEN=true
APP_OPS_WRITE_ENABLED=false
APP_AUTH_COOKIE_SECURE=false   # 仅当全站 HTTPS 时改为 true
```

4. 重建容器后执行一次（若未写入镜像）：

```bash
bash /etc/data-asset/scripts/ensure_oracle_ro_runtime.sh
```

5. **推荐重建命令**（挂载凭据 + Oracle 目录，脚本在仓库 `deploy/scripts/`）：

```bash
# 将 deploy/scripts 同步到服务器后：
bash /etc/data-asset/scripts/run_data_asset_api.sh
# 或手动 docker run 时务必带：
#   -v /etc/data-asset/credentials:/etc/data-asset/credentials:ro
#   -v /opt/oracle:/opt/oracle:ro
#   并在启动命令中先执行 ensure_oracle_ro_runtime.sh
```

## 目标环境

| 项目 | 配置 |
|---|---|
| OS | openEuler 22.03 |
| 服务器 | 10.10.8.83 |
| 网络 | 内网 (无公网访问) |
| 数据库 | PostgreSQL 14 (已安装) |
| Web 服务 | Nginx |

## 1. 服务器前置条件 (8.83)

```bash
# 确认已有
postgresql-14 --version
python3 --version          # 需要 3.11+
nginx -v
```

若缺少，由运维在 openEuler 上用离线 rpm 包安装。

## 2. 离线部署包准备 (开发机 → 8.83)

### 2.1 开发机上准备

```bash
# 后端依赖
cd backend
pip download -r requirements.txt -d ../offline-pkgs/backend-pip

# 前端依赖使用 pnpm store 离线缓存，构建机执行 pnpm fetch
pnpm fetch
```

### 2.2 文件传输 (经跳板机 10.10.8.53)

```bash
# 在开发机上打包
tar -czf data-asset-deploy.tar.gz \
  backend/ \
  frontend/ \
  deploy/backend.env.example \
  offline-pkgs/

# scp 到跳板机
scp data-asset-deploy.tar.gz root@10.10.8.53:/tmp/

# 从跳板机 scp 到目标服务器
ssh root@10.10.8.53
scp /tmp/data-asset-deploy.tar.gz root@10.10.8.83:/tmp/

# 在 8.83 上解压
ssh root@10.10.8.83
mkdir -p /opt/data-asset
cd /opt/data-asset
tar -xzf /tmp/data-asset-deploy.tar.gz
```

## 3. 数据库初始化 (8.83，历史示例，执行前按 offline README 修订)

```sql
-- 以 postgres 用户执行
CREATE USER asset_app WITH PASSWORD '<安全密码>';
CREATE DATABASE data_asset OWNER asset_app;
GRANT ALL PRIVILEGES ON DATABASE data_asset TO asset_app;

-- 所有应用表都在 asset schema，不能只授权 public
\c data_asset
CREATE SCHEMA IF NOT EXISTS asset AUTHORIZATION asset_app;
GRANT USAGE, CREATE ON SCHEMA asset TO asset_app;
```

## 4. 后端部署 (8.83)

```bash
cd /opt/data-asset/backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖 (离线)
pip install --no-index --find-links=../offline-pkgs/backend-pip -r requirements.txt

# 配置环境变量
cp ../deploy/backend.env.example .env
vim .env   # 修改 APP_DB_URL 密码和 APP_CREDENTIAL_ENCRYPT_KEY

# 数据库迁移
alembic upgrade head

# 启动服务 (测试)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 生产环境 systemd 服务

```ini
# /etc/systemd/system/data-asset-api.service
[Unit]
Description=Data Asset Platform API
After=network.target postgresql-14.service

[Service]
Type=simple
User=dataasset
Group=dataasset
WorkingDirectory=/opt/data-asset/backend
EnvironmentFile=/opt/data-asset/backend/.env
ExecStart=/opt/data-asset/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

首次生成管理员 Token：

```bash
cd /opt/data-asset/backend
venv/bin/python -m scripts.create_admin_token --key-name platform-admin
```

Token 不通过 HTTP 初始化接口暴露；生产跳板连接必须预置专用 SSH 用户和
`known_hosts`，应用不会自动接受未知主机指纹。

```bash
systemctl daemon-reload
systemctl enable data-asset-api
systemctl start data-asset-api
```

## 5. 前端部署 (8.83)

```bash
cd /opt/data-asset/frontend

# 目标机无外网。使用 deploy/offline/README.md 的 pnpm 离线 store，或直接上传开发机构建的 dist。

# 部署产物
mkdir -p /opt/data-asset/frontend-dist
cp -r dist/* /opt/data-asset/frontend-dist/
```

> 若 8.83 上无 node，可在开发机构建后只传 dist/ 目录。

## 6. Nginx 配置 (8.83)

```bash
cp /opt/data-asset/deploy/nginx.conf /etc/nginx/conf.d/data-asset.conf

# 测试并重载
nginx -t
systemctl reload nginx

# 开放防火墙 (如启用)
firewall-cmd --add-service=http --permanent
firewall-cmd --reload
```

## 7. 环境变量说明

| 变量 | 用途 | 示例 |
|---|---|---|
| `APP_DB_URL` | PostgreSQL 连接串 | `postgresql+psycopg://asset_app:xxx@127.0.0.1:5432/data_asset` |
| `APP_CORS_ORIGINS` | 允许的跨域来源 | `["http://10.10.8.83","http://localhost:8848"]` |
| `APP_CREDENTIAL_ENCRYPT_KEY` | 凭据加密密钥 | 32字符随机串 (Feret 密钥) |
| `APP_SNAPSHOT_RETENTION_DAYS` | 快照保留天数 | `90` |
| `APP_EVENT_RETENTION_DAYS` | 事件日志保留天数 | `365` |
| `APP_SCHEDULER_TIMEZONE` | 定时任务时区 | `Asia/Shanghai` |

## 8. 验证

```bash
# 后端健康检查
curl http://10.10.8.83/api/v1/health

# 预期返回: {"status":"ok"}

# 前端访问
curl http://10.10.8.83/
# 浏览器打开: http://10.10.8.83
```

## 9. 端口清单

| 服务 | 端口 | 说明 |
|---|---|---|
| Backend (uvicorn) | 8000 | 仅 localhost 监听 |
| Frontend (nginx) | 80 | 对外提供 |
| PostgreSQL | 5432 | 仅 localhost 监听 |

## 10. 常见问题

- **pip 安装报错**: 确认 `offline-pkgs/` 包含所有 .whl，检查 Python 版本与 wheel 平台标签匹配。
- **alembic 报连接失败**: 检查 `.env` 中 `APP_DB_URL` 密码是否正确，`pg_hba.conf` 是否允许本地 md5 认证。
- **前端白屏**: 检查 nginx root 指向是否正确，浏览器 DevTools 查看静态资源路径。
- **跨域报错**: 确认 `APP_CORS_ORIGINS` 包含前端访问的完整 URL (含端口)。

## 11. 108 号关系图谱专项：原子发布与回滚（P0-03）

> 本节约束生产发布方式，禁止逐文件热更新后宣称完成。

### 11.1 后端不可变镜像

- 后端必须按**同一 Git SHA** 构建不可变镜像，禁止容器内逐文件热更作为正式发布。
- 启动时日志输出脱敏版本号（`build_id / git_sha / frontend_build_id`）。
- 健康接口 `/health`、`/health/live`、`/api/v1/health` 返回 `build_id / git_sha / frontend_build_id`。

```bash
# 在 8.83 构建（离线 wheelhouse 已具备）：
cd /opt/data-asset/backend
docker build -f ../deploy/docker/Dockerfile -t data-asset:<tag> .
# 或用既有构建机 + deploy/offline 的 wheelhouse。
```

### 11.2 前端版本目录原子切换

```bash
# 1. 生成 dist（开发机构建后上传，或服务器离线构建）
# 2. 完整上传版本目录并原子切换：
BUILD_ID="<build_id>"   # 例如 frontend-20260802-108
bash /etc/data-asset/scripts/release_frontend.sh "${BUILD_ID}" <dist目录>
#    → 把 dist 复制到 releases/<build_id>，校验 HTML 引用资源均存在，
#      原子切换 current 软链接，保留 previous 供回滚。

# 3. Nginx root 指向 current 软链接（deploy/nginx.conf 已更新）
nginx -t && nginx -s reload
```

### 11.3 生成发布 manifest

```bash
cd /opt/data-asset/backend
python /opt/data-asset/deploy/scripts/release_manifest.py \
  --backend-dir /opt/data-asset/backend \
  --frontend-dist /opt/data-asset/frontend-dist/current \
  --backend-image "data-asset:<tag>" \
  --out /opt/data-asset/releases/release-manifest.json
```

manifest 包含：Git SHA、backend image、frontend build ID、Alembic head、构建时间、
关键文件 SHA256。发布前校验 manifest 中 `git_sha` 与后端容器、`frontend_build_id`
与 Nginx 活动目录一致。

### 11.4 回滚

```bash
# 前端完整版本回滚（软链接切回 previous）：
bash /etc/data-asset/scripts/rollback_frontend.sh
nginx -s reload

# 后端回滚：替换为上一不可变镜像标签并重建容器：
docker tag data-asset:<上一tag> data-asset:current
bash /etc/data-asset/scripts/run_data_asset_api.sh
```

**回滚必须同时恢复完整后端镜像与完整前端版本目录**，禁止只回滚单个文件。
回滚触发条件见 `开发起步包/108_关系图谱无法打开专项排查整改与测试计划.md` §8.3。

### 11.5 发布后烟雾验证

- 匿名路由 `/`、`/asset/graph` 返回 200；
- 认证后 `graph / options / diagnostics` 200，且默认图有节点和边；
- `curl -H 'Cache-Control: no-cache' http://<host>/index.html` 返回新 build ID；
- hash JS/CSS 响应头含 `immutable`，index.html 含 `no-cache`；
- 强刷、无痕、新会话三种方式加载同一版本。
