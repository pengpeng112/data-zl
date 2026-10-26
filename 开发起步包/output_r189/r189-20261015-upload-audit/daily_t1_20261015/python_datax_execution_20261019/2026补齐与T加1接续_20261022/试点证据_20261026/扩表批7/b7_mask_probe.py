"""批7 前置探查+错配列源值样例定 mask（只读限量，ODS 白天例外）：
- 11 表业务日 2026-10-25 窗 COUNT（60s 超时纪律）
- 错配列源值 DISTINCT 样例（2026-01-01 起窗内 ROWNUM<=2000 限量子查询再 DISTINCT，定 TO_DATE/TO_NUMBER mask）
- 目标 8.74：HOS_PREOP_DISCUSS.PERFORM_OPERATION_DATE 既有值样例（验证 14 字符紧凑格式）+ 11 表现量
运行：ssh 8.83 "docker exec -i data-asset-api python -" < b7_mask_probe.py
"""
import oracledb

BIZ_DAY = "2026-10-25"
NEXT_DAY = "2026-10-26"
TABLES = ["EMR_REFERRAL_HOS_RECORD", "EMR_ADMISSION_DEAD_RECORD_TF", "EMR_HOS_DIFFIC_CASE_DISCUSS",
          "EMR_HOS_DND_RECORD", "EMR_HOS_SUCCESSION_RECORD", "EMR_OPERATION_NURSING",
          "EMR_HOS_PREOP_DISCUSS", "EMR_AFTER_OPERA_RECORD", "EMR_INFOR_ANESTHESIA",
          "EMR_OUTPATIENT_RECIPE", "EMR_OUTPATIENT_RECIPE_ITEM"]

# 错配列（批678预核结论§四）：S→D/S→N 需看源值格式定 mask；N→S 只确认源 NUMBER 形态
MASK_COLS = [
    ("EMR_OPERATION_NURSING", ["OPERATION_END_DATE", "OPERATION_START_DATE", "IN_ROOM_DATE",
                               "OUT_ROOM_DATE", "HANDOVER_DATE", "RECORD_DATE"]),
    ("EMR_REFERRAL_HOS_RECORD", ["SURGERY_START_DATE"]),
    ("EMR_ADMISSION_DEAD_RECORD_TF", ["JOB_CODE"]),
    ("EMR_AFTER_OPERA_RECORD", ["ANES_METHOD_CODE"]),
    ("EMR_INFOR_ANESTHESIA", ["AGE_MONTH"]),
    ("EMR_HOS_PREOP_DISCUSS", ["PROF_TECH_CATE_CODE", "PERFORM_ANES_CODE"]),
]

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
cur = conn.cursor()

print("== 批7 前置探查（业务日", BIZ_DAY, "源=ODS 10.10.8.216）==")
for t in TABLES:
    view = "V_" + t
    conn.call_timeout = 60000
    try:
        cur.execute(
            f"SELECT COUNT(*) FROM ODS.{view} "
            "WHERE DATETIME >= TO_DATE(:s,'YYYY-MM-DD') AND DATETIME < TO_DATE(:e,'YYYY-MM-DD')",
            {"s": BIZ_DAY, "e": NEXT_DAY})
        print(f"{t}: 窗COUNT({BIZ_DAY})={cur.fetchone()[0]}")
    except Exception as exc:
        print(f"{t}: 窗COUNT=TIMEOUT_OR_ERR({type(exc).__name__}: {str(exc)[:90]})")
        conn.rollback()

print("== 错配列源值 DISTINCT 样例（窗 2026-01-01 起，ROWNUM<=2000 限量，60s 超时）==")
for t, cols in MASK_COLS:
    view = "V_" + t
    for c in cols:
        conn.call_timeout = 60000
        try:
            cur.execute(
                f"SELECT DISTINCT vals FROM (SELECT {c} AS vals FROM ODS.{view} "
                "WHERE DATETIME >= TO_DATE('2026-01-01','YYYY-MM-DD') "
                f"AND {c} IS NOT NULL AND ROWNUM <= 2000) WHERE ROWNUM <= 12")
            rows = [str(r[0]) for r in cur.fetchall()]
            print(f"{t}.{c}: 样例={rows if rows else 'EMPTY(2026窗无值)'}")
        except Exception as exc:
            print(f"{t}.{c}: ERR({type(exc).__name__}: {str(exc)[:90]})")
            conn.rollback()
conn.call_timeout = 0
conn.close()

# 目标侧：PERFORM_OPERATION_DATE 既有值样例（14 字符紧凑格式确认）+ 11 表现量
line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
tconn = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
tcur = tconn.cursor()
print("== 目标 8.74：HOS_PREOP_DISCUSS.PERFORM_OPERATION_DATE 既有值样例（LEN 分布+样例12）==")
tcur.execute(
    "SELECT LENGTH(PERFORM_OPERATION_DATE), COUNT(*) FROM DBOPER.EMR_HOS_PREOP_DISCUSS "
    "WHERE PERFORM_OPERATION_DATE IS NOT NULL GROUP BY LENGTH(PERFORM_OPERATION_DATE) "
    "ORDER BY 1")
print("LEN 分布:", tcur.fetchall())
tcur.execute(
    "SELECT PERFORM_OPERATION_DATE FROM DBOPER.EMR_HOS_PREOP_DISCUSS "
    "WHERE PERFORM_OPERATION_DATE IS NOT NULL AND ROWNUM <= 12")
print("样例:", [r[0] for r in tcur.fetchall()])
print("== 目标现量（DBOPER@8.74）==")
for t in TABLES:
    tcur.execute(f"SELECT COUNT(*) FROM DBOPER.{t}")
    print(f"{t}: target_total={tcur.fetchone()[0]}")
tconn.close()
print("== 探查结束 ==")
