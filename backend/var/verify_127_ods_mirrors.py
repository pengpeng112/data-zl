# ODS 镜像连接只读连通性测试 — 仅查数据字典，验证各镜像 schema 可达
import oracledb

oracledb.init_oracle_client(lib_dir='/opt/oracle')

with open('/etc/data-asset/credentials/ods_8_216') as f:
    user, password = f.read().strip().split(':', 1)

conn = oracledb.connect(user=user, password=password, dsn='10.10.8.216:1521/orcl')
cur = conn.cursor()
cur.execute('SELECT USER, SYS_CONTEXT(\'USERENV\',\'DB_NAME\') FROM DUAL')
print('连接成功|', cur.fetchone())

# 各镜像连接对应的业务 schema 是否存在且可读（只读数据字典）
for label, schema in [('ods_emr', 'EMR'), ('ods_lis', 'LIS'), ('ods_pacs', 'PACS'),
                      ('ods_sm', 'SM'), ('ods_ydhl', 'YDHL'), ('ods_his', 'HIS')]:
    cur.execute("SELECT COUNT(*) FROM all_users WHERE username = :s", s=schema)
    exists = cur.fetchone()[0]
    if exists:
        cur.execute("SELECT COUNT(*) FROM all_tables WHERE owner = :s", s=schema)
        n = cur.fetchone()[0]
        print(f'{label}|schema={schema}|存在|可见表={n}')
    else:
        print(f'{label}|schema={schema}|不存在')
conn.close()
