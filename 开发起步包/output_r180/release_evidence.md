# 180 批发布证据（release_evidence.md，2026-09-05）

> 全程凭据零回显零落盘；SSH 公钥通道；业务源库零连接。

## B0 只读侦察（发布前）

- 容器：`data-asset-api` / `data-asset:r175-20260903` / Up 39 hours (healthy)
- 基底与回滚点镜像 `data-asset:r175-20260903` 存在（另有 r166-20260830）
- run 脚本：`/etc/data-asset/scripts/run_data_asset_api.sh`（另有 /opt/data-asset/deploy/scripts/ 同名）
- 磁盘：/ 41G 可用
- cron：`/etc/cron.d/data-asset-identity-nightly` = `0 2 * * * root flock -n ... docker exec -e ... data-asset-api python /app/scripts/run_identity_modified_nightly.py`（**容器路径**；env 开关含 DIRECT_CONNECTION 等，未改动）
- 前端：current → releases/r175-20260903；releases 含 r169-storage-fix/r169-theme-fix/r171/r175；pg_dump=/usr/local/pgsql/bin；nginx=/usr/sbin/nginx

## B1 上载

- 本地 tar（backend/app backend/alembic backend/alembic.ini backend/scripts deploy/docker/Dockerfile.hotpatch）= 2.9M → scp → 服务器解包 `/opt/data-asset/hotpatch/r178-20260905/`（backend + deploy）
- runner md5 双侧一致：`63daf260da40765059d8ccbb75b8f565`
- **打包时间线（W-05 相关）**：tar 生成于 10:22:24；并行会话 10:23:53–10:25:09 修改 4 个 identity 文件 → **r178 镜像内容=10:22 打包态（A 段提交基线），不含并行改动**

## 并行会话检出（10:35 终检）

- 4 个 identity 文件工作区 M（+118/-23，003531 事故防护），零提交、未触本批任何产出；生产不受影响（runner 不执行 login_sign 子任务）。详见 exceptions.json W-05。

## B2 DB 备份

- `/opt/data-asset/data_asset_pre_r178_20260905.dump` = **139M**（用户/库名经容器 env 解析，口令仅入变量不回显）

## B3 镜像构建与冒烟

- `docker build -f deploy/docker/Dockerfile.hotpatch --build-arg BASE_IMAGE=data-asset:r175-20260903 -t data-asset:r178-20260905` → `Successfully built e42bfaf55360`
- 镜像内 grep 冒烟：FFREE3=**11**；resync_unchanged=**5**；CREATE SCHEMA IF NOT EXISTS=**2**（online+offline）；apply_login_sign_gaps=**1**

## B4 切换与回读（第一次重建，容器 575a9b284506）

- `DATA_ASSET_IMAGE=data-asset:r178-20260905 bash /etc/data-asset/scripts/run_data_asset_api.sh` → healthy
- `/health` 200：`{"status":"ok","database":"connected",...}`（build_id 字段=r175-20260903 系 env 旧值，见 exceptions W-01）
- 三端点 401：/api/v1/quality-issues、/api/v1/systems、/api/v1/quality-observations 全 401
- `alembic current` = `d5e6f7a8b9c0 (head)`（无迁移 no-op）
- settings：`identity_cb_max_update=150 identity_cb_max_new=130`（切换时刻未变）

## B5 夜跑脚本核验（决策：不 docker cp）

- hotpatch 层只 COPY app/ alembic/ alembic.ini，**不含 scripts/** → 容器 `/app/scripts/run_identity_modified_nightly.py` 保持 r175 基底版（md5 `87ff0c8ff2ae059ba704e542fc7224a9`）
- 容器内 runner grep：**login_sign=0**（G2 未接线——保持未授权边界，**刻意不 cp 新 runner**，否则今晚 02:00 将未授权激活 login_sign 子任务）；jhemr_signature_sync=1（既有三子任务在）
- F-2 语义在 `app/services/identity_sync_orchestrator.py`（新层）✓；FFREE3 在 adapter（新层）✓ → 今晚夜跑预期：主任务 success + 既有三子任务恢复，login_sign 不出现（属预期）

## B6 G3 · MAX_NEW 130→50（第二次重建，容器 25970c9185b6）

- env 备份 `/etc/data-asset/backend.env.bak-maxnew-20260905` → sed → grep 确认 1 行 `APP_IDENTITY_CB_MAX_NEW=50`
- 重建 → healthy → `/health` 200 → settings 终值 **`150 50`**

## C 段 前端

- 本地 `pnpm run build`：三预算 PASS（657.2/700、404.5/430、103.5/110 KB gzip）；入口 `index-vXKROi89.js`
- 上载解包 hash 逐字一致 → `release_frontend.sh r178-20260905`：ASSETS 校验 `all referenced assets present`，current → releases/r178-20260905
- `nginx -t` successful + reload；生产首页 200、HTML 引用 `index-vXKROi89.js` 与本地一致；`/api/v1/quality-issues` 经 nginx 401（鉴权墙完好）
- previous 链接沿承 `r169-20260831-storage-fix`（脚本继承行为，见 exceptions W-03）；真回滚点 r175-20260903 仍在 releases/

## 回滚链（备查）

- 后端：`DATA_ASSET_IMAGE=data-asset:r175-20260903 bash /etc/data-asset/scripts/run_data_asset_api.sh`
- env：`cp backend.env.bak-maxnew-20260905 backend.env` + 重建（回 130）
- 前端：`ln -sfn releases/r175-20260903 /opt/data-asset/frontend-dist/current` + reload
- DB：无迁移；极端用 B2 dump
