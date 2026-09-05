#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""182 方案二：手麻急诊登记住院次错配·每日扫描（只读，零写入）。

用法：
  cron（每日 00:10，报昨日全天新增）：
    docker exec -i data-asset-api python - < /opt/data-asset/scripts/docare_mismatch_daily.py \
      >> /opt/data-asset/evidence/docare_mismatch/cron.log 2>&1
  单人清单（不限窗口，供人工修正核对）：
    docker exec -i data-asset-api python - < /opt/data-asset/scripts/docare_mismatch_daily.py --patient c0632940

行为：
  - 只连 Docare（受控只读凭据）执行 SELECT；
  - 错配判据与 182 号一致：文书 FUPDATE 落 MEDCOMM.MED_PAT_VISIT 入院区间（本次入院
    <= FUPDATE < 下次入院）得真实住院次 real_visit，与登记 FBINCU 不符即错配；
  - 输出 markdown 清单到 stdout（由调用方重定向落盘），含建议修正值；
  - 不写任何数据库；清单文件含患者号，仅存 8.83 受控目录（0600），禁止外传/入 git。
"""
import sys
from pathlib import Path

from app.services.db_connectors import OracleConnector

DOCS_FILTER = "('护理记录单','手术护理单','术后随访','术前访视','麻醉单','安全核查单','介入核查单')"

VISIT_WINDOW = (
    "(SELECT PATIENT_ID, VISIT_ID AS real_visit, ADMISSION_DATE_TIME, "
    "LEAD(ADMISSION_DATE_TIME) OVER (PARTITION BY PATIENT_ID ORDER BY ADMISSION_DATE_TIME) AS next_adm "
    "FROM MEDCOMM.MED_PAT_VISIT)"
)


def connect():
    raw = Path("/etc/data-asset/credentials/docare_oracle_10_10_10_68.readonly").read_text(encoding="utf-8").strip()
    user, pwd = raw.split(":", 1)
    return OracleConnector(
        host="10.10.10.68", port=1521, database="docare",
        user=user, password=pwd, connection_mode="direct",
        oracle_client_lib_dir="/opt/oracle", timeout_ms=120000,
    )


def oper_id_from_pdfname(pdfname: str) -> str:
    # 形如 c0632940_1_麻醉_麻醉单_4_3.pdf → 倒数第 2 段为 OPER_ID
    try:
        stem = str(pdfname).rsplit(".", 1)[0]
        return stem.split("_")[-2]
    except Exception:
        return "?"


def main() -> int:
    patient = None
    args = sys.argv[1:]
    if "--patient" in args:
        patient = args[args.index("--patient") + 1]

    conn = connect()

    if patient:
        where = ("s.PATIENTID = :pid AND s.FREPORTSTYLE = '住院' "
                 "AND v.real_visit IS NOT NULL AND v.real_visit <> s.FBINCU")
        params = {"pid": patient}
        title = f"单人修正清单 · {patient}（全时段）"
        window_desc = "不限窗口"
    else:
        where = ("s.FUPDATE >= TRUNC(SYSDATE-1) AND s.FUPDATE < TRUNC(SYSDATE) "
                 "AND s.FREPORTSTYLE = '住院' "
                 "AND v.real_visit IS NOT NULL AND v.real_visit <> s.FBINCU")
        params = {}
        title = "手麻急诊登记住院次错配 · 昨日新增清单"
        window_desc = "TRUNC(SYSDATE-1) ~ TRUNC(SYSDATE)"

    sql = f"""
        SELECT s.PATIENTID, s.FBIHID, s.FBINCU AS reg_visit, v.real_visit,
               s.reportname, s.pdfname, s.FUPDATE
        FROM MEDSURGERY.T_ITF_SM s
        LEFT JOIN {VISIT_WINDOW} v
          ON v.PATIENT_ID = s.PATIENTID
         AND s.FUPDATE >= v.ADMISSION_DATE_TIME
         AND (v.next_adm IS NULL OR s.FUPDATE < v.next_adm)
        WHERE {where}
    """
    rows = conn.execute_readonly(sql, params, max_rows=10000)

    # 聚合：患者 × (登记住院次 → 应改为)
    groups = {}
    for r in rows:
        key = (r["PATIENTID"], str(r["REG_VISIT"]), str(r["REAL_VISIT"]))
        g = groups.setdefault(key, {"fbihid": r["FBIHID"], "docs": [],
                                    "opers": set(), "first": None, "last": None})
        g["docs"].append((str(r["REPORTNAME"]), str(r["PDFNAME"]), str(r["FUPDATE"])))
        g["opers"].add(oper_id_from_pdfname(r["PDFNAME"]))
        f = str(r["FUPDATE"])
        g["first"] = f if g["first"] is None or f < g["first"] else g["first"]
        g["last"] = f if g["last"] is None or f > g["last"] else g["last"]

    lines = [f"# {title}", "",
             f"- 窗口：{window_desc}",
             f"- 错配文书行数：{len(rows)}；涉及患者×住院次组合：{len(groups)}",
             "- 判据：文书时间落入 MED_PAT_VISIT 入院区间（182 号）",
             "- 处置：手术室在手麻系统「手术登记」中把对应手术的住院次改为【应改为】值，"
             "保存后 T_ITF_SM 视图自动更新，无纸化下次采集即可命中；文书无需重做", ""]
    if not groups:
        lines.append("（本窗口无新增错配）")
    for (pid, reg, real) in sorted(groups):
        g = groups[(pid, reg, real)]
        lines.append(f"## {pid}（病案号 {g['fbihid']}）：登记住院次 {reg} → 应改为 {real}")
        lines.append(f"- 涉及手术 OPER_ID：{', '.join(sorted(g['opers']))}；文书 {len(g['docs'])} 份；"
                     f"文书时间 {g['first']} ~ {g['last']}")
        for name, pdf, ts in g["docs"][:8]:
            lines.append(f"  - {ts} {name} ({pdf})")
        if len(g["docs"]) > 8:
            lines.append(f"  - … 其余 {len(g['docs']) - 8} 份")
        lines.append("")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
