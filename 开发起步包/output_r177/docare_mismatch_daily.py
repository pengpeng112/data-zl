#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""182 方案二 v3：手麻急诊登记住院次错配·每日扫描 + 受控自动修订。

相对 v2 的关键修正（00344476 解剖发现）：
  手麻本地住院次（MED_PAT_VISIT/MED_OPERATION_MASTER.VISIT_ID）与 HIS 真实住院次
  是两套编号，部分患者一致（c0632940）、部分不一致（00344476 本地 1=HIS 3）。
  视图 FBINCU = NVL(申请反查 his_visit_id, 登记本地值)。因此：
  - FBINCU 来源为申请反查 → 基本正确，不算错配；
  - 错配确认必须以 ODS HIS.PAT_VISIT 落窗算出的真实 HIS 号为基准；
  - 自动修订仅当：FBINCU=登记值 且 ≠HIS真实号 且 该患者本地号==HIS号 且 登记值为默认 1；
    其余形态（本地/HIS 编号不一致、登记非 1 等）只出清单人工裁决。

模式：无参=每日自动（cron 00:10）；--dry-run；--patient P（只读）；--patient P --fix（点名修订）。
护栏：每例先备份（可回滚）、单晚上限 10 组、单事务 rowcount 对账、逐例平台审计。
"""
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

from app.services.db_connectors import OracleConnector

EV_DIR = Path("/opt/data-asset/evidence/docare_mismatch")
DAILY_FIX_LIMIT = 10
VISIT_WINDOW = (
    "(SELECT PATIENT_ID, VISIT_ID AS real_visit, ADMISSION_DATE_TIME, "
    "LEAD(ADMISSION_DATE_TIME) OVER (PARTITION BY PATIENT_ID ORDER BY ADMISSION_DATE_TIME) AS next_adm "
    "FROM MEDCOMM.MED_PAT_VISIT)"
)


def creds():
    raw = Path("/etc/data-asset/credentials/docare_oracle_10_10_10_68.readonly").read_text(encoding="utf-8").strip()
    u, p = raw.split(":", 1)
    return u, p


def ro_conn():
    u, p = creds()
    return OracleConnector(host="10.10.10.68", port=1521, database="docare",
                           user=u, password=p, connection_mode="direct",
                           oracle_client_lib_dir="/opt/oracle", timeout_ms=120000)


def ods_conn():
    raw = Path("/etc/data-asset/credentials/ods_8_216").read_text(encoding="utf-8").strip()
    u, p = raw.split(":", 1)
    return OracleConnector(host="10.10.8.216", port=1521, database="orcl",
                           user=u, password=p, connection_mode="direct",
                           oracle_client_lib_dir="/opt/oracle", timeout_ms=60000)


def rw_conn():
    import oracledb
    try:
        oracledb.init_oracle_client(lib_dir="/opt/oracle")
    except Exception:
        pass
    u, p = creds()
    c = oracledb.connect(user=u, password=p, dsn="10.10.10.68:1521/docare")
    c.autocommit = False
    return c


def norm(v):
    if v is None:
        return None
    if isinstance(v, (bytes, memoryview)):
        return bytes(v).hex()[:2000]
    if type(v).__name__ == "LOB":
        try:
            d = v.read()
            return bytes(d).hex()[:2000] if isinstance(d, (bytes, memoryview)) else str(d)[:8000]
        except Exception:
            return "<LOB>"
    return str(v)[:8000]


def oper_of(pdfname):
    try:
        return str(pdfname).rsplit(".", 1)[0].split("_")[-2]
    except Exception:
        return None


def fall_in(visits, when):
    """visits=[(visit, adm_dt_str)] 升序；返回 when 落入的 visit（区间=本次入院≤when<下次入院）。"""
    v = None
    for visit, adm in visits:
        if when >= str(adm):
            v = str(visit)
    return v


def scan(conn, patient=None):
    if patient:
        where = "s.PATIENTID=:p AND v.real_visit IS NOT NULL AND v.real_visit <> s.FBINCU"
        params = {"p": patient}
        window = "单人全时段"
    else:
        where = ("s.FUPDATE >= TRUNC(SYSDATE-1) AND s.FUPDATE < TRUNC(SYSDATE) "
                 "AND v.real_visit IS NOT NULL AND v.real_visit <> s.FBINCU")
        params = {}
        window = "昨日全天"
    sql = f"""
        SELECT s.PATIENTID, s.FBIHID, s.FBINCU AS reg_v, v.real_visit AS local_real,
               s.reportname, s.pdfname, s.FUPDATE
        FROM MEDSURGERY.T_ITF_SM s
        LEFT JOIN {VISIT_WINDOW} v
          ON v.PATIENT_ID = s.PATIENTID
         AND s.FUPDATE >= v.ADMISSION_DATE_TIME
         AND (v.next_adm IS NULL OR s.FUPDATE < v.next_adm)
        WHERE s.FREPORTSTYLE='住院' AND {where}
    """
    rows = conn.execute_readonly(sql, params, max_rows=10000)
    groups = {}
    bad = 0
    for r in rows:
        op = oper_of(r["PDFNAME"])
        if op is None:
            bad += 1
            continue
        key = (str(r["PATIENTID"]), str(r["REG_V"]), str(r["LOCAL_REAL"]))
        g = groups.setdefault(key, {"fbihid": str(r["FBIHID"]), "opers": {}, "docs": 0,
                                    "when": str(r["FUPDATE"])})
        g["opers"][op] = g["opers"].get(op, 0) + 1
        g["docs"] += 1
    return window, rows, groups, bad


def apply_hit(conn, pid, fbincu, oper):
    n = conn.execute_readonly(
        "SELECT COUNT(*) c FROM MEDCOMM.MED_VS_HIS_OPER_APPLY_V2 "
        "WHERE MED_PATIENT_ID=:p AND MED_VISIT_ID=:v AND MED_SCHEDULE_ID=:o",
        {"p": pid, "v": fbincu, "o": oper}, max_rows=2)[0]["C"]
    return int(n) > 0


DICT_TABLES = None


def dict_tables(conn):
    global DICT_TABLES
    if DICT_TABLES is None:
        rows = conn.execute_readonly(
            "SELECT owner, table_name FROM all_tab_columns "
            "WHERE owner IN ('MEDSURGERY','MEDCOMM','MEDICU') AND column_name IN ('PATIENT_ID','VISIT_ID','OPER_ID') "
            "GROUP BY owner, table_name HAVING COUNT(DISTINCT column_name)=3 AND table_name NOT LIKE 'V\\_%' ESCAPE '\\'",
            None, max_rows=300)
        DICT_TABLES = [(r["OWNER"], r["TABLE_NAME"]) for r in rows]
    return DICT_TABLES


def plan_fix(conn, pid, reg_v, oper):
    hits = {}
    for o, t in dict_tables(conn):
        fq = f"{o}.{t}"
        n = conn.execute_readonly(
            f"SELECT COUNT(*) c FROM {fq} WHERE PATIENT_ID=:p AND VISIT_ID=:v AND OPER_ID=:o",
            {"p": pid, "v": reg_v, "o": oper}, max_rows=2)[0]["C"]
        if int(n) > 0:
            hits[fq] = int(n)
    n = conn.execute_readonly(
        "SELECT COUNT(*) c FROM MEDCOMM.MED_EMR_ARCHIVE_DETIAL "
        "WHERE PATIENT_ID=:p AND VISIT_ID=:v AND MR_CLASS='麻醉' AND ARCHIVE_KEY=:o",
        {"p": pid, "v": reg_v, "o": oper}, max_rows=2)[0]["C"]
    if int(n) > 0:
        hits["MEDCOMM.MED_EMR_ARCHIVE_DETIAL"] = int(n)
    return hits


def backup_group(conn, pid, tag, tables):
    payload = {"pid": pid, "tag": {k: tag[k] for k in ("reg_v", "real_v", "oper")}, "tables": {}}
    for fq in tables:
        w = ("PATIENT_ID=:p AND VISIT_ID=:v AND MR_CLASS='麻醉' AND ARCHIVE_KEY=:o"
             if fq == "MEDCOMM.MED_EMR_ARCHIVE_DETIAL"
             else "PATIENT_ID=:p AND VISIT_ID=:v AND OPER_ID=:o")
        rows = conn.execute_readonly(f"SELECT * FROM {fq} WHERE {w}", tag["bind"], max_rows=5000)
        payload["tables"][fq] = [{k: norm(v) for k, v in r.items()} for r in rows]
    payload["counts"] = {k: len(v) for k, v in payload["tables"].items()}
    payload["total"] = sum(payload["counts"].values())
    fname = EV_DIR / f"fix_backup_{datetime.now():%Y%m%d}_{pid}_{tag['reg_v']}to{tag['real_v']}_oper{tag['oper']}.json"
    fname.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    fname.chmod(0o600)
    return fname.name, payload["total"]


def apply_fix(pid, tag, tables):
    conn = rw_conn()
    res = {"tag": f"{tag['reg_v']}->{tag['real_v']} oper{tag['oper']}", "tables": len(tables)}
    try:
        cur = conn.cursor()
        expect = 0
        for fq, n in tables.items():
            if fq == "MEDCOMM.MED_EMR_ARCHIVE_DETIAL":
                src, dst = ("PATIENT_ID=:p AND VISIT_ID=:v AND MR_CLASS='麻醉' AND ARCHIVE_KEY=:o",
                            "PATIENT_ID=:p AND VISIT_ID=:nv AND MR_CLASS='麻醉' AND ARCHIVE_KEY=:o")
            else:
                src, dst = "PATIENT_ID=:p AND VISIT_ID=:v AND OPER_ID=:o", "PATIENT_ID=:p AND VISIT_ID=:nv AND OPER_ID=:o"
            b2 = dict(tag["bind"], nv=tag["real_v"])
            cur.execute(f"SELECT COUNT(*) FROM {fq} WHERE {dst}", b2)
            if cur.fetchone()[0]:
                raise RuntimeError(f"{fq}: target clash")
            cur.execute(f"SELECT COUNT(*) FROM {fq} WHERE {src}", tag["bind"])
            if cur.fetchone()[0] != n:
                raise RuntimeError(f"{fq}: src drift")
            expect += n
        done = 0
        for fq in tables:
            sql = ("UPDATE MEDCOMM.MED_EMR_ARCHIVE_DETIAL SET VISIT_ID=:nv "
                   "WHERE PATIENT_ID=:p AND VISIT_ID=:v AND MR_CLASS='麻醉' AND ARCHIVE_KEY=:o"
                   if fq == "MEDCOMM.MED_EMR_ARCHIVE_DETIAL" else
                   f"UPDATE {fq} SET VISIT_ID=:nv WHERE PATIENT_ID=:p AND VISIT_ID=:v AND OPER_ID=:o")
            cur.execute(sql, dict(tag["bind"], nv=tag["real_v"]))
            done += cur.rowcount
        if done != expect:
            raise RuntimeError(f"rowcount {done} != {expect}")
        conn.commit()
        res.update({"status": "fixed", "rows": done})
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        res.update({"status": "rolled_back", "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
    finally:
        conn.close()
    return res


def audit_platform(pid, info):
    try:
        from app.core.db import SessionLocal
        from app.models.governance_base import GovernAuditLog
        db = SessionLocal()
        try:
            db.add(GovernAuditLog(
                module="docare", entity_type="MED_OPERATION_MASTER+children", entity_ref=pid,
                action="auto_fix_visit_id_daily", operator="docare-auto-fix-daily",
                reason="182 v3: HIS-verified emergency visit-id auto fix "
                       "(backup-first, single txn, rowcount reconciled, local==HIS numbering required)",
                after_data=info))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def main():
    args = sys.argv[1:]
    patient = args[args.index("--patient") + 1] if "--patient" in args else None
    do_fix = "--fix" in args
    dry = "--dry-run" in args

    dc = ro_conn()
    ods = ods_conn()
    window, rows, groups, bad = scan(dc, patient)
    L = [f"# 手麻住院次错配 · {'单人' if patient else '每日'}"
         f"{'（HIS 核验自动修订' + ('，dry-run' if dry else '') + '）' if (not patient or do_fix) else '（只读清单）'}",
         "", f"- 窗口：{window}",
         f"- 候选错配文书行数：{len(rows)}；患者×住院次组合：{len(groups)}",
         f"- 自动条件：登记=1 且 FBINCU≠HIS 真实号 且 本地号==HIS号；上限 {DAILY_FIX_LIMIT} 组/晚", ""]
    if not groups:
        L.append("（无错配）")
        print("\n".join(L))
        return 0

    his_visits_cache = {}

    def his_visits(pid):
        if pid not in his_visits_cache:
            r = ods.execute_readonly(
                "SELECT VISIT_ID, ADMISSION_DATE_TIME FROM HIS.PAT_VISIT WHERE UPPER(PATIENT_ID)=UPPER(:p) ORDER BY ADMISSION_DATE_TIME",
                {"p": pid}, max_rows=50)
            his_visits_cache[pid] = [(str(x["VISIT_ID"]), str(x["ADMISSION_DATE_TIME"])) for x in r]
        return his_visits_cache[pid]

    auto_all = (not patient and not dry) or (patient and do_fix)
    if auto_all and len(groups) > DAILY_FIX_LIMIT:
        L.append(f"**⚠ 组合数 {len(groups)} > 上限 {DAILY_FIX_LIMIT}：只出清单（NEED_MANUAL）**")
        auto_all = False

    fixed_groups = 0
    for (pid, reg_v, local_real) in sorted(groups):
        g = groups[(pid, reg_v, local_real)]
        his_real = fall_in(his_visits(pid), g["when"])
        apply_src = apply_hit(dc, pid, reg_v, sorted(g["opers"])[0])
        reasons = []
        if apply_src:
            reasons.append("FBINCU 来自申请反查（视为正确）")
        if his_real is None:
            reasons.append("HIS 无落窗住院")
        auto = (auto_all and not apply_src and his_real is not None
                and reg_v != his_real and reg_v == "1" and local_real == his_real)
        if apply_src or his_real is None or reg_v == his_real or local_real != his_real:
            if "FBINCU 来自申请反查（视为正确）" not in reasons and reg_v == his_real:
                reasons.append("FBINCU 已与 HIS 一致")
            if local_real != his_real and his_real is not None:
                reasons.append(f"本地号 {local_real} ≠ HIS 号 {his_real}（编号体系不一致，人工裁决）")
            if reg_v != "1" and not apply_src and his_real is not None and reg_v != his_real:
                reasons.append(f"登记非默认 1（{reg_v}），形态未知")
        L.append(f"## {pid}（病案号 {g['fbihid']}）：FBINCU={reg_v}，本地落窗={local_real}，"
                 f"HIS 真实={his_real}（OPER {','.join(sorted(g['opers']))}；文书 {g['docs']} 份；{g['when']}）")
        if not auto:
            L.append("- 状态：仅清单（" + ("；".join(reasons) or "未满足自动条件") + "）")
            L.append("")
            continue
        target = his_real
        for oper in sorted(g["opers"]):
            tag = {"reg_v": reg_v, "real_v": target, "oper": oper,
                   "bind": {"p": pid, "v": reg_v, "o": oper}}
            tables = plan_fix(dc, pid, reg_v, oper)
            if not tables:
                L.append(f"- OPER {oper}：⚠ 未发现存数表，跳过")
                continue
            if dry:
                L.append(f"- OPER {oper}：dry-run 受影响 {len(tables)} 表/{sum(tables.values())} 行（未写入）")
                continue
            try:
                bname, total = backup_group(dc, pid, tag, tables)
            except Exception as exc:
                L.append(f"- OPER {oper}：⚠ 备份失败 {type(exc).__name__}，跳过")
                continue
            res = apply_fix(pid, tag, tables)
            L.append(f"- OPER {oper}：修订 {res['status']}"
                     + (f"（{res.get('rows')} 行，备份 {bname}）" if res["status"] == "fixed"
                        else f"（{res.get('error')}）"))
            audit_platform(pid, {"tag": res["tag"], "status": res["status"], "rows": res.get("rows"), "backup": bname})
        fixed_groups += 1
        L.append("")
    if bad:
        L.append(f"⚠ {bad} 行文书 PDFNAME 无法解析 OPER_ID，未处理，需人工查看")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
