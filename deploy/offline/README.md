# Offline Deployment

This procedure assumes the target host has no internet access and runs the API as
the dedicated `dataasset` user.

## 1. Build the offline package

On a connected build host (must match the target OS/arch/Python for wheels):

```bash
# Lock and download backend wheels (use a constraints/pinned file if available)
python3 -m pip download -r backend/requirements.txt -d offline/wheels
python3 -m pip check  # verify no dependency conflicts

cd frontend
# Fetch ALL deps (incl. devDependencies like Vite) — do NOT use --prod,
# the build step needs Vite which lives in devDependencies.
pnpm fetch --frozen-lockfile
pnpm install --offline --frozen-lockfile
pnpm run typecheck
pnpm run build
```

Copy `backend/`, `frontend/dist/`, `offline/wheels/`, and `deploy/` to the target
host. Do not copy `.env` files, `node_modules/`, or credentials. The target host
does NOT need Node/pnpm installed — it only serves the prebuilt `frontend/dist/`.

## 2. Prepare the database

The DBA must pre-create and grant the single application schema:

```bash
psql "$POSTGRES_DBA_URL" -f deploy/offline/init_db.sql
```

Inject `APP_DB_URL` and `APP_CREDENTIAL_ENCRYPT_KEY` through the target host's
secret store or a protected environment file, then run:

```bash
cd /opt/data-asset/backend
python3 -m venv venv
venv/bin/pip install --no-index --find-links=/opt/data-asset/offline/wheels -r requirements.txt
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

The repository has not been able to run this procedure on a clean target host;
the first real deployment must record package hashes, migration output, and
health-check output in the release ticket.
