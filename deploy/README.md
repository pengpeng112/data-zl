# 数据资产管理平台 — 部署指南

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

# 前端依赖已随项目提交 node_modules，无需额外下载
# 离线 node 二进制可从内网 dev 机复制
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

## 3. 数据库初始化 (8.83)

```sql
-- 以 postgres 用户执行
CREATE USER asset_app WITH PASSWORD '<安全密码>';
CREATE DATABASE data_asset OWNER asset_app;
GRANT ALL PRIVILEGES ON DATABASE data_asset TO asset_app;

-- 授权 public schema
\c data_asset
GRANT ALL ON SCHEMA public TO asset_app;
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
User=root
WorkingDirectory=/opt/data-asset/backend
EnvironmentFile=/opt/data-asset/backend/.env
ExecStart=/opt/data-asset/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable data-asset-api
systemctl start data-asset-api
```

## 5. 前端部署 (8.83)

```bash
cd /opt/data-asset/frontend

# 安装依赖 & 构建 (开发机做或 8.83 上有 node)
pnpm install
pnpm build

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
