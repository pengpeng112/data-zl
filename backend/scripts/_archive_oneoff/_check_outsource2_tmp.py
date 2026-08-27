import oracledb, os
try: oracledb.init_oracle_client(lib_dir="/opt/oracle")
except Exception: pass
conn = oracledb.connect(user=os.environ["ODS_8_216_USER"], password=os.environ["ODS_8_216_PASSWORD"], dsn="10.10.8.216:1521/orcl")
conn.call_timeout = 60000
cur = conn.cursor()
cur.execute("SET TRANSACTION READ ONLY")
q = lambda sql: list(cur.execute(sql).fetchall())

print("=== A. 0502 在 LAB_TEST_MASTER 有多少行(近3月) ===")
print(q("SELECT count(*), count(distinct PERFORMED_BY) FROM LAB_TEST_MASTER WHERE REQUESTED_DATE_TIME >= ADD_MONTHS(SYSDATE,-3) AND VISIT_ID > 0 AND PERFORMED_BY='0502'"))

print("\n=== B. 不限 0502,近3月住院检验 performed_by 分布 ===")
for r in q("SELECT PERFORMED_BY, count(*) FROM LAB_TEST_MASTER WHERE REQUESTED_DATE_TIME >= ADD_MONTHS(SYSDATE,-3) AND VISIT_ID > 0 GROUP BY PERFORMED_BY ORDER BY 2 DESC"):
    print("  ", r)

print("\n=== C. outpatient 0502:OUTP_TREAT_REC.PERFORMED_BY ===")
for r in q("SELECT PERFORMED_BY, count(*) FROM OUTP_TREAT_REC WHERE VISIT_DATE >= ADD_MONTHS(SYSDATE,-3) AND ITEM_CLASS='C' GROUP BY PERFORMED_BY ORDER BY 2 DESC"):
    print("  ", r)

print("\n=== D. 0502 在住院里 ITEM_NAME 前缀(不限BILLING) ===")
for r in q("""SELECT CASE WHEN i.ITEM_NAME LIKE 'DT%' THEN 'DT' WHEN i.ITEM_NAME LIKE 'DP%' THEN 'DP'
  WHEN i.ITEM_NAME LIKE 'WK%' THEN 'WK' WHEN i.ITEM_NAME LIKE 'BR%' THEN 'BR'
  WHEN i.ITEM_CODE LIKE 'WS%' THEN 'WS' ELSE 'O' END p, count(*) cnt
FROM LAB_TEST_MASTER m JOIN LAB_TEST_ITEMS i ON m.TEST_NO=i.TEST_NO
WHERE m.REQUESTED_DATE_TIME >= ADD_MONTHS(SYSDATE,-3) AND m.VISIT_ID > 0 AND m.PERFORMED_BY='0502'
GROUP BY CASE WHEN i.ITEM_NAME LIKE 'DT%' THEN 'DT' WHEN i.ITEM_NAME LIKE 'DP%' THEN 'DP'
  WHEN i.ITEM_NAME LIKE 'WK%' THEN 'WK' WHEN i.ITEM_NAME LIKE 'BR%' THEN 'BR'
  WHEN i.ITEM_CODE LIKE 'WS%' THEN 'WS' ELSE 'O' END ORDER BY cnt DESC"""):
    print("  ", r)

print("\n=== E. 外送样本名称(DT/DP/WK/BR 去重前10) ===")
for r in q("SELECT DISTINCT ITEM_NAME FROM LAB_TEST_ITEMS WHERE ITEM_NAME LIKE 'DT%' OR ITEM_NAME LIKE 'DP%' OR ITEM_NAME LIKE 'WK%' OR ITEM_NAME LIKE 'BR%' AND ROWNUM<=10"):
    print("  ", r[0])

cur.close(); conn.close()
