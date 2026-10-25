"""批4 护理 8 表预核（只读限量）：对象/锚点类型/目标列对齐/新鲜度。"""
import json

line = open("/etc/data-asset/credentials/mobile_nursing_oracle_10_10_10_125.readonly").readline().strip()
u, _, p = line.partition(":")
import oracledb
oracledb.init_oracle_client(lib_dir="/opt/oracle")
conn = oracledb.connect(user=u, password=p, dsn="10.10.10.125:1521/ewell", tcp_connect_timeout=20)
conn.call_timeout = 180000
cur = conn.cursor()

TABLES = ["EMR_ADMISSION_ASSESSMENT","EMR_DISCHARGE_ASSESSMENT","EMR_CHILDBIRTH",
          "EMR_GENERAL_NURSING","EMR_CRITICALLY_ILL_NURS","EMR_IN_OUT_AMOUNT",
          "EMR_VITAL_SIGN","EMR_NURSING_ASSESSMENT"]
tgt_all = json.load(open("/tmp/b4_targets.json", encoding="utf-8"))

for t in TABLES:
    view = "V_" + t
    cur.execute(
        "SELECT OBJECT_TYPE FROM ALL_OBJECTS WHERE OWNER='LUNA_MCS_SDSEY' AND OBJECT_NAME=:v",
        {"v": view})
    row = cur.fetchone()
    otype = row[0] if row else "NOT_FOUND"
    cur.execute(
        "SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS WHERE OWNER='LUNA_MCS_SDSEY' AND TABLE_NAME=:v AND COLUMN_NAME IN ('ID','DATETIME')",
        {"v": view})
    key_anchor = cur.fetchall()
    cur.execute(
        "SELECT COUNT(*) FROM ALL_TAB_COLUMNS WHERE OWNER='LUNA_MCS_SDSEY' AND TABLE_NAME=:v",
        {"v": view})
    ncols = cur.fetchone()[0]
    info = f"{t}: {otype} src_cols={ncols} {key_anchor}"
    if otype == "VIEW":
        src = set()
        cur.execute(
            "SELECT COLUMN_NAME FROM ALL_TAB_COLUMNS WHERE OWNER='LUNA_MCS_SDSEY' AND TABLE_NAME=:v",
            {"v": view})
        src = {r[0].upper() for r in cur.fetchall()}
        tset = set(tgt_all.get(t, []))
        gap = sorted(tset - src) if tset else "?"
        cur.execute(f"SELECT COUNT(*), MAX(DATETIME) FROM LUNA_MCS_SDSEY.{view}")
        cnt, mx = cur.fetchone()
        info += f" total={cnt} max={mx!r} 目标{len(tset)}列 目标有源无={gap}"
    print(info)
conn.close()
