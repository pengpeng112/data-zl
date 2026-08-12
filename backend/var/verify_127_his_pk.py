# 127 计划 6.2 节主键口径只读核实 — 仅查询 ALL_ 数据字典，无业务数据
import oracledb

oracledb.init_oracle_client(lib_dir='/opt/oracle')

TABLES = ['ORDERS', 'PAT_VISIT', 'PAT_MASTER_INDEX', 'DIAGNOSIS', 'LAB_TEST_MASTER',
          'EXAM_MASTER', 'EXAM_REPORT', 'OPERATION_MASTER', 'INP_BILL_DETAIL',
          'CLINIC_MASTER', 'LAB_RESULT']

conn = oracledb.connect(user='ready_his', password='ready_his', dsn='10.10.10.15:1521/his')
cur = conn.cursor()
cur.execute("""
SELECT c.owner, c.table_name, cc.column_name, cc.position
FROM all_constraints c
JOIN all_cons_columns cc ON c.owner=cc.owner AND c.constraint_name=cc.constraint_name
WHERE c.constraint_type='P' AND c.table_name IN ({} )
ORDER BY c.owner, c.table_name, cc.position
""".format(','.join(f"'{t}'" for t in TABLES)))
rows = cur.fetchall()
pk = {}
for owner, tbl, col, pos in rows:
    pk.setdefault((owner, tbl), []).append(col)
for (owner, tbl), cols in sorted(pk.items()):
    print(f'PK|{owner}.{tbl}|{"+".join(cols)}')
found = {t for (_o, t) in pk}
print('无主键约束|', ','.join(sorted(set(TABLES) - found)))
conn.close()
