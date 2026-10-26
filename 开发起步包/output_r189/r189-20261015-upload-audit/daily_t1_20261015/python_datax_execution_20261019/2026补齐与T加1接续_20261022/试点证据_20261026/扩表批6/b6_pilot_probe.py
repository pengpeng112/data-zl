"""批6 试点前置探查（只读限量，ODS 白天例外）：11 表业务日 2026-10-25 窗 COUNT（60s 超时纪律）+ 目标表现量。
运行（容器）：ssh 8.83 "docker exec -i data-asset-api python -" < b6_pilot_probe.py
"""
import oracledb

BIZ_DAY = "2026-10-25"
NEXT_DAY = "2026-10-26"
TABLES = ["EMR_INFOR_TRANS_BLOOD", "EMR_HOS_CHANGE_MAJOR_RECORD", "EMR_ANES_RECORD_BLOOD",
          "EMR_INFOR_CRITICALLY_ILL", "EMR_HOS_POSTOPER_RECORD", "EMR_BOFORE_OPERA_RECORD",
          "EMR_ANESTHESIA_RECORD", "EMR_OPERA_RECORD", "EMR_IN_FEE_INFO_MAIN",
          "EMR_HOS_CONSUL_RECORD", "EMR_DOC_ORDER_CHECK"]

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
cur = conn.cursor()
print("== 批6 前置探查（业务日", BIZ_DAY, "源=ODS 10.10.8.216）==")
for t in TABLES:
    view = "V_" + t
    conn.call_timeout = 60000
    try:
        cur.execute(
            f"SELECT COUNT(*) FROM ODS.{view} "
            "WHERE DATETIME >= TO_DATE(:s,'YYYY-MM-DD') AND DATETIME < TO_DATE(:e,'YYYY-MM-DD')",
            {"s": BIZ_DAY, "e": NEXT_DAY})
        wincnt = cur.fetchone()[0]
        print(f"{t}: 窗COUNT({BIZ_DAY})={wincnt}")
    except Exception as exc:
        print(f"{t}: 窗COUNT=TIMEOUT_OR_ERR({type(exc).__name__}: {str(exc)[:90]})")
        conn.rollback()
conn.call_timeout = 0
conn.close()

# 目标现状量（8.74 只读）
line = open("/etc/data-asset/credentials/sanjia_front_oracle_10_10_8_74.readonly").readline().strip()
u, _, p = line.partition(":")
tconn = oracledb.connect(user=u, password=p, dsn="10.10.8.74:1521/orcl", tcp_connect_timeout=20)
tcur = tconn.cursor()
print("== 目标现量（DBOPER@8.74）==")
for t in TABLES:
    tcur.execute(f"SELECT COUNT(*) FROM DBOPER.{t}")
    print(f"{t}: target_total={tcur.fetchone()[0]}")
tconn.close()
print("== 探查结束 ==")
