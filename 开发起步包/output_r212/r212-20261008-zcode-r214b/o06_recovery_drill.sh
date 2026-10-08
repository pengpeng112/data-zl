#!/usr/bin/env bash
# R212 O06 隔离备份恢复演练（仅 data_asset_test；pytest/浏览器全部结束后串行执行）。
#
# 流程：录制前置状态(关键表行数+alembic版本+实体校验和) → pg_dump →
#       DROP/CREATE data_asset_test → 恢复 → 逐项对账 → 清理服务器临时文件。
# 安全：库名硬校验=data_asset_test；不动 data_asset(生产)；凭据只在服务器端解析，不回传。
set -euo pipefail
KEY="C:/Users/Administrator/.ssh/id_ed25519_ai"
SSHOPTS=(-o BatchMode=yes -o ConnectTimeout=10 -i "$KEY")
HOST=root@10.10.8.83
RUN="F:\python\数据资产\开发起步包\output_r212\r212-20261008-zcode-r214b"

remote() { ssh "${SSHOPTS[@]}" "$HOST" "$1" 2>&1 | grep -vE "WARNING|store now|upgraded|^\*\*|Authorized users"; }

echo "== O06 step1: 前置状态 =="
PRE=$(remote 'set -e
URL=$(grep ^APP_DB_URL /etc/data-asset/backend.env | cut -d= -f2-)
DB=$(echo "$URL" | awk -F/ "{print \$NF}" | cut -d'?' -f1)
# backend.env 指向生产 data_asset（dev_env.sh 在本地改写为 _test）；
# 本演练所有命令硬编码 data_asset_test，仅当 URL 库名属于本平台两库之一才放行。
case "$DB" in data_asset|data_asset_test) TARGET=data_asset_test;; *) echo "GUARD_FAIL db=$DB"; exit 1;; esac
U=$(echo "$URL" | sed -E "s#.*//([^:]+):.*#\1#")
P=$(echo "$URL" | sed -E "s#.*:([^@]+)@.*#\1#")
export PGPASSWORD="$P"; PG=/usr/local/pgsql/bin
PSQL="$PG/psql -U $U -h 127.0.0.1 -d data_asset_test -At"
echo "alembic=$($PSQL -c "select version_num from asset.alembic_version" 2>/dev/null || $PSQL -c "select version_num from public.alembic_version")"
for t in asset_auth_users asset_roles asset_role_permissions asset_systems asset_data_sources asset_tables asset_columns asset_column_value_domains asset_quality_issues; do
  echo "count_$t=$($PSQL -c "select count(*) from asset.$t" 2>/dev/null || echo NA)"
done
echo "chk_users=$($PSQL -c "select md5(string_agg(username, chr(44) order by username)) from asset.asset_auth_users" 2>/dev/null || echo NA)"
echo "chk_systems=$($PSQL -c "select md5(string_agg(system_code, chr(44) order by system_code)) from asset.asset_systems" 2>/dev/null || echo NA)"
')
echo "$PRE"

echo "== O06 step2: pg_dump =="
remote 'set -e
URL=$(grep ^APP_DB_URL /etc/data-asset/backend.env | cut -d= -f2-)
U=$(echo "$URL" | sed -E "s#.*//([^:]+):.*#\1#"); P=$(echo "$URL" | sed -E "s#.*:([^@]+)@.*#\1#")
export PGPASSWORD="$P"
/usr/local/pgsql/bin/pg_dump -U "$U" -h 127.0.0.1 -Fc -f /tmp/r212_o6_backup.dump data_asset_test
ls -la /tmp/r212_o6_backup.dump | awk "{print \"dump_size=\"\$5}"
md5sum /tmp/r212_o6_backup.dump | cut -d" " -f1
'

echo "== O06 step3: DROP/CREATE + 恢复 =="
remote 'set -e
URL=$(grep ^APP_DB_URL /etc/data-asset/backend.env | cut -d= -f2-)
U=$(echo "$URL" | sed -E "s#.*//([^:]+):.*#\1#"); P=$(echo "$URL" | sed -E "s#.*:([^@]+)@.*#\1#")
export PGPASSWORD="$P"; PG=/usr/local/pgsql/bin
$PG/psql -U "$U" -h 127.0.0.1 -d postgres -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='"'"'data_asset_test'"'"' and pid<>pg_backend_pid()" >/dev/null
$PG/dropdb -U "$U" -h 127.0.0.1 data_asset_test
$PG/createdb -U "$U" -h 127.0.0.1 data_asset_test
$PG/pg_restore -U "$U" -h 127.0.0.1 -d data_asset_test --no-owner /tmp/r212_o6_backup.dump
echo "restore_exit=$?"
'

echo "== O06 step4: 恢复后对账 =="
POST=$(remote 'set -e
URL=$(grep ^APP_DB_URL /etc/data-asset/backend.env | cut -d= -f2-)
U=$(echo "$URL" | sed -E "s#.*//([^:]+):.*#\1#"); P=$(echo "$URL" | sed -E "s#.*:([^@]+)@.*#\1#")
export PGPASSWORD="$P"; PG=/usr/local/pgsql/bin
PSQL="$PG/psql -U $U -h 127.0.0.1 -d data_asset_test -At"
echo "alembic=$($PSQL -c "select version_num from asset.alembic_version" 2>/dev/null || $PSQL -c "select version_num from public.alembic_version")"
for t in asset_auth_users asset_roles asset_role_permissions asset_systems asset_data_sources asset_tables asset_columns asset_column_value_domains asset_quality_issues; do
  echo "count_$t=$($PSQL -c "select count(*) from asset.$t" 2>/dev/null || echo NA)"
done
echo "chk_users=$($PSQL -c "select md5(string_agg(username, chr(44) order by username)) from asset.asset_auth_users" 2>/dev/null || echo NA)"
echo "chk_systems=$($PSQL -c "select md5(string_agg(system_code, chr(44) order by system_code)) from asset.asset_systems" 2>/dev/null || echo NA)"
')
echo "$POST"

echo "== O06 step5: 清理服务器临时文件 =="
remote 'rm -f /tmp/r212_o6_backup.dump && echo cleanup_ok'

{
  echo "pre:"; echo "$PRE"; echo "post:"; echo "$POST"
} > "$RUN/recovery/o06_drill_log.txt"
echo "== O06 完成，对账日志 -> recovery/o06_drill_log.txt =="
