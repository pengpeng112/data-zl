# 离线部署与 R8 验收

目标运行时为 Linux x86_64、CPython 3.11、glibc；API 使用专用 `dataasset`
账号运行。2026-08-11 已在与生产容器一致的 Python 3.11/glibc 运行时和
Docker `--network none` 环境完成从零安装、迁移往返与健康检查。

## 1. Build the offline package

联网准备机负责解析和下载，最终 wheel 仍必须经过目标运行时标签校验。当前
前端固定使用 `pnpm@11.9.0`；CLI 与 store 主版本必须一致：

```bash
# 已有锁文件时按锁文件准备 Linux wheelhouse
python3 -m pip download --require-hashes -r backend/requirements.lock -d package/wheels

# 首次解析后，从扁平 wheelhouse 生成逐包 SHA-256 锁；脚本会拒绝
# Windows/macOS、musllinux、错误 CPython ABI/架构和嵌套 wheel。
python3 deploy/offline/build_hashed_lock.py package/wheels \
  package/backend/requirements.lock \
  --python-version 3.11 --os linux --arch x86_64

cd frontend
# 必须包含 devDependencies（Vite/typecheck）；不要使用 --prod。
pnpm fetch --force --frozen-lockfile --store-dir ../package/pnpm-store
pnpm install --offline --frozen-lockfile --trust-lockfile \
  --store-dir ../package/pnpm-store
pnpm run typecheck
pnpm run build
```

包内保留 `backend/`、`frontend/dist/`、`wheels/`、`deploy/`、
`pnpm-store/v11/` 和 `pnpm-11.9.0.tgz`。不得包含 `.env`、`node_modules` 或
凭据。正式目标机只服务预构建 `frontend/dist/`，无需安装 Node/pnpm；store
用于复现和断网验收构建。

## 2. Prepare the database

The DBA must pre-create and grant the single application schema:

```bash
psql "$POSTGRES_DBA_URL" -f deploy/offline/init_db.sql
```

Inject `APP_DB_URL` and `APP_CREDENTIAL_ENCRYPT_KEY` through the target host's
secret store or a protected environment file.

### Credentials directory (plan 75)

Platform data-source passwords are stored as server files (not in PostgreSQL):

```bash
sudo mkdir -p /etc/data-asset/credentials
sudo chown dataasset:dataasset /etc/data-asset/credentials   # or the API runtime user
sudo chmod 700 /etc/data-asset/credentials
```

- Files: `/etc/data-asset/credentials/<source_code>.readonly` (mode `0600`).
- Content: `username:password` one line; never commit these files.
- Set `APP_CREDENTIAL_DIR=/etc/data-asset/credentials` for the API process.
- Container mount must be **read-write** (`:rw`) so the connection UI can rotate
  credentials; business source databases remain SELECT-only.
- Independent acceptance/test images should use a dedicated empty credentials
  directory, never production secrets.

Then run:

```bash
cd /opt/data-asset/backend
python3 -m venv venv
venv/bin/pip install --require-hashes --no-index \
  --find-links=/opt/data-asset/offline/wheels -r requirements.lock
venv/bin/pip check
venv/bin/alembic upgrade head
venv/bin/python -m scripts.create_admin_token --key-name platform-admin --user-identifier <platform-user-id>
```

The last command prints the raw Token once. Store it in the approved secret
channel; it is already bound to the supplied platform user.

## 3. Install and verify

```bash
# Frontend static files (prebuilt, target host needs no Node/pnpm)
install -d -o dataasset -g dataasset /opt/data-asset/frontend-dist
cp -r /opt/data-asset/frontend/dist/. /opt/data-asset/frontend-dist/

# Backend systemd unit
install -m 0644 deploy/systemd/data-asset.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now data-asset

# Nginx reverse-proxy config — MUST be installed, not just reloaded.
# Without this step Nginx starts but /api/ is NOT proxied to the backend.
install -m 0644 deploy/nginx.conf /etc/nginx/conf.d/data-asset.conf
nginx -t && systemctl reload nginx

# Readiness check: must use --fail so HTTP 503 (DB down) fails the check.
curl --fail http://127.0.0.1:8000/api/v1/health
curl --fail http://127.0.0.1/api/v1/health        # through Nginx
```

2026-08-11 已在临时内部网络中的全新 PostgreSQL 14 完成：从零
`upgrade head`、第二次幂等 `upgrade head`、`downgrade -1`、再次
`upgrade head`，最终 `/health` 返回 200。可在注入隔离测试库 URL 后运行：

```bash
sh deploy/offline/run_backend_drill.sh /opt/data-asset-offline
```

该脚本只应连接全新或明确授权的隔离测试库，不得用于生产库回退演练。

## 4. Verify an offline package before installation

The package root must contain `manifest.json` and `SHA256SUMS`. The manifest
must contain a `files` list (or path-to-hash object), for example:

```json
{
  "target": {"python_version": "3.11", "os": "linux", "arch": "x86_64"},
  "files": [{"path": "wheels/example.whl", "sha256": "<64 hex characters>"}]
}
```

Run the fail-closed verifier on the target package directory before copying or
installing files:

```bash
python3 deploy/offline/verify_offline_package.py \
  /opt/data-asset-offline --profile r8
```

R8 profile 除完整性和运行时检查外，还强制核对 `requirements.lock` 与全部
wheel 哈希完全一致、每个 wheel 与当前 Python/OS/架构/glibc 兼容，以及前端
dist、pnpm 离线 store/CLI 和演练脚本均存在。验证器只使用 Python 标准库，
可在安装 wheel 前运行。任一缺失、未登记文件、符号链接、路径逃逸、哈希或
平台不匹配都会非零退出。

在最终打包前生成确定性清单（时间戳必须显式固定；也可用
`SOURCE_DATE_EPOCH`）：

```bash
python3 deploy/offline/build_offline_manifest.py package \
  --python-version 3.11 --os linux --arch x86_64 \
  --source-revision "$(git rev-parse HEAD)" \
  --source-tree-state clean \
  --created-at 2026-08-11T00:00:00Z
```

正式发布包必须使用 `--source-tree-state clean`；共享工作区候选包必须如实写
`dirty`，不得把未提交内容伪装成由 `source_revision` 可完整复现的 release。
