import oracledb, os
try:
    oracledb.init_oracle_client(lib_dir="/opt/oracle")
except Exception:
    pass
conn = oracledb.connect(user=os.environ["ODS_8_216_USER"], password=os.environ["ODS_8_216_PASSWORD"], dsn="10.10.8.216:1521/orcl")
conn.call_timeout = 90000
cur = conn.cursor()
cur.execute("SET TRANSACTION READ ONLY")
q = lambda sql: list(cur.execute(sql).fetchall())

print("=== 1. OUTP_ORDERS_COSTS 存在性 ===")
print("HIS.OUTP_ORDERS_COSTS:", q("SELECT count(*) FROM ALL_TABLES WHERE OWNER='HIS' AND TABLE_NAME='OUTP_ORDERS_COSTS'"))

print("\n=== 2. 住院各前缀分布(近3月,0502) ===")
for r in q("""SELECT CASE WHEN i.ITEM_NAME LIKE 'DT%' THEN 'DT'
  WHEN i.ITEM_NAME LIKE 'DP%' THEN 'DP' WHEN i.ITEM_NAME LIKE 'WK%' THEN 'WK'
  WHEN i.ITEM_NAME LIKE 'BR%' THEN 'BR' WHEN i.ITEM_CODE LIKE 'WS%' THEN 'WS(code)'
  ELSE '其他' END AS p, count(*) cnt, count(distinct i.ITEM_CODE) codes
FROM LAB_TEST_MASTER m JOIN LAB_TEST_ITEMS i ON m.TEST_NO=i.TEST_NO
WHERE m.REQUESTED_DATE_TIME >= ADD_MONTHS(SYSDATE,-3) AND m.VISIT_ID > 0
  AND m.PERFORMED_BY='0502' AND m.BILLING_INDICATOR=1
GROUP BY CASE WHEN i.ITEM_NAME LIKE 'DT%' THEN 'DT'
  WHEN i.ITEM_NAME LIKE 'DP%' THEN 'DP' WHEN i.ITEM_NAME LIKE 'WK%' THEN 'WK'
  WHEN i.ITEM_NAME LIKE 'BR%' THEN 'BR' WHEN i.ITEM_CODE LIKE 'WS%' THEN 'WS(code)'
  ELSE '其他' END ORDER BY cnt DESC"""):
    print("  ", r)

print("\n=== 3. '其他'类样本(可能漏的外送) ===")
for r in q("""SELECT * FROM (SELECT i.ITEM_CODE, i.ITEM_NAME, count(*) cnt
FROM LAB_TEST_MASTER m JOIN LAB_TEST_ITEMS i ON m.TEST_NO=i.TEST_NO
WHERE m.REQUESTED_DATE_TIME >= ADD_MONTHS(SYSDATE,-3) AND m.VISIT_ID > 0
  AND m.PERFORMED_BY='0502' AND m.BILLING_INDICATOR=1
  AND i.ITEM_NAME NOT LIKE 'DT%' AND i.ITEM_NAME NOT LIKE 'DP%'
  AND i.ITEM_NAME NOT LIKE 'WK%' AND i.ITEM_NAME NOT LIKE 'BR%' AND i.ITEM_CODE NOT LIKE 'WS%'
GROUP BY i.ITEM_CODE, i.ITEM_NAME ORDER BY cnt DESC) WHERE ROWNUM<=15"""):
    print("  ", r)

print("\n=== 4. DT/DP/WK/BR 样本 ===")
for r in q("""SELECT * FROM (SELECT DISTINCT i.ITEM_CODE, i.ITEM_NAME FROM LAB_TEST_ITEMS i
WHERE i.ITEM_NAME LIKE 'DT%' OR i.ITEM_NAME LIKE 'DP%' OR i.ITEM_NAME LIKE 'WK%' OR i.ITEM_NAME LIKE 'BR%'
ORDER BY i.ITEM_NAME) WHERE ROWNUM<=15"""):
    print("  ", r)

print("\n=== 5. performed_by=0502 是外送科室吗(对照) ===")
for r in q("""SELECT PERFORMED_BY, count(*) cnt FROM LAB_TEST_MASTER
WHERE REQUESTED_DATE_TIME >= ADD_MONTHS(SYSDATE,-3) AND VISIT_ID > 0
GROUP BY PERFORMED_BY ORDER BY cnt DESC"""):
    print("  ", r)
cur.close(); conn.close()
