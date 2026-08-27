"""Quick post-check: snapshots + identity counts (platform PG only)."""
from __future__ import annotations

import os
import paramiko

HOST = "10.10.8.83"
PASSWORD = os.environ.get("APP_SSH_PASSWORD", "P@ssw0rd@123")


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=15, allow_agent=False, look_for_keys=False)
    sql = r"""
sudo -u postgres /usr/local/pgsql/bin/psql -d data_asset -c "
SELECT id, source_code, label, table_count, column_count FROM asset.asset_metadata_snapshots ORDER BY id;
SELECT source_code, last_check_status, last_check_at FROM asset.asset_data_sources;
SELECT 'persons' AS t, COUNT(*) FROM asset.asset_identity_persons
UNION ALL SELECT 'departments', COUNT(*) FROM asset.asset_identity_departments
UNION ALL SELECT 'person_sources', COUNT(*) FROM asset.asset_identity_person_sources
UNION ALL SELECT 'person_departments', COUNT(*) FROM asset.asset_identity_person_departments;
"
"""
    _i, o, e = c.exec_command(sql, timeout=30)
    print(o.read().decode())
    err = e.read().decode()
    if err and "could not change directory" not in err:
        print(err)
    c.close()


if __name__ == "__main__":
    main()
