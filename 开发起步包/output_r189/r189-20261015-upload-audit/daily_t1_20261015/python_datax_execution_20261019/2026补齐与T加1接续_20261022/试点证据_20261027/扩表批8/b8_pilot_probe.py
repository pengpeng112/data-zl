"""批8 试点前置探查（只读限量，ODS 白天例外）：10 表业务日 2026-10-26 窗 COUNT（60s 超时纪律；
INFOR_OPERATION/OTHERS 预期超时=预案证据）+ 目标表现量 + 参考窗 2026-10-25 对照（跨页基线）。
运行（容器）：ssh -F .ssh/config_ai data-asset-83 "docker exec -i data-asset-api python -" < b8_pilot_probe.py
"""
import oracledb

BIZ_DAY = "2026-10-26"
NEXT_DAY = "2026-10-27"
TABLES = ["EMR_ANES_RECORD_MED", "EMR_ADMISSION_RECORD_EXAM", "EMR_CONSUMABLES",
          "EMR_OUTPATIENT_DIAG", "EMR_DOC_ORDER_DRUG", "EMR_OUT_FEE_INFO_MAIN",
          "EMR_OUT_FEE_INFO_CHILD", "EMR_IN_FEE_INFO_CHILD", "EMR_INFOR_OPERATION",
          "EMR_INFOR_OTHERS"]

oracledb.init_oracle_client(lib_dir="/opt/oracle")
line = open("/etc/data-asset/credentials/ods_8_216").readline().strip()
u, _, p = line.partition(":")
conn = oracledb.connect(user=u, password=p, dsn="10.10.8.216:1521/orcl", tcp_connect_timeout=20)
cur = conn.cursor()
print("== 批8 前置探查（业务日", BIZ_DAY, "源=ODS 10.10.8.216；另附 2026-10-25 参考窗对照）==")
for t in TABLES:
    view = "V_" + t
    for label, s, e in (("试点窗", BIZ_DAY, NEXT_DAY), ("参考窗", "2026-10-25", "2026-10-26")):
        conn.call_timeout = 60000
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM ODS.{view} "
                "WHERE DATETIME >= TO_DATE(:s,'YYYY-MM-DD') AND DATETIME < TO_DATE(:e,'YYYY-MM-DD')",
                {"s": s, "e": e})
            wincnt = cur.fetchone()[0]
            print(f"{t}: {label}({s})={wincnt}")
        except Exception as exc:
            print(f"{t}: {label}({s})=TIMEOUT_OR_ERR({type(exc).__name__}: {str(exc)[:90]})")
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
