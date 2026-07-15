"""Validate ultrasound/endoscopy cross-database relationships, read-only."""
from __future__ import annotations

import argparse, json, os
from datetime import datetime, timezone
from pathlib import Path


# id, child db/table/columns/order, parent db/table/columns
RELATIONS = [
    ("U01", "MedcareUS", "dbo", "预约登记", ["AccessNo"], "编号", "AnyImage", "grid", "BHosCheckUS", ["AccessNo"]),
    # AccessionNo is currently empty in MedcareES. Keep only the cheap,
    # reproducible check as negative evidence; do not brute-force candidate
    # columns against a production report table during routine validation.
    ("E01", "MedcareES", "dbo", "预约登记", ["AccessionNo"], "编号", "AnyImageSLES", "grid", "BHosCheckES", ["AccessNo"]),
    ("E02", "MedcareES", "dbo", "预约登记", ["AccessionNo"], "编号", "AnyImage", "grid", "BHosCheckES", ["AccessNo"]),
    ("A01", "AnyImage", "grid", "BHosCheckUS", ["MID"], "ID", "AnyImage", "grid", "BHosPatient", ["ID"]),
    ("A02", "AnyImage", "grid", "BHosCheckES", ["MID"], "ID", "AnyImage", "grid", "BHosPatient", ["ID"]),
    ("S01", "AnyImageSLES", "grid", "BHosCheckES", ["MID"], "ID", "AnyImageSLES", "grid", "BHosPatient", ["ID"]),
    ("P01", "PacsServer", "grid", "BHosSeries", ["StudyID"], "ID", "PacsServer", "grid", "BHosStudy", ["ID"]),
    ("P02", "PacsServer", "grid", "BHosImages", ["StudyID"], "ID", "PacsServer", "grid", "BHosStudy", ["ID"]),
    ("P03", "PacsServer", "grid", "BHosImages", ["SeriesID"], "ID", "PacsServer", "grid", "BHosSeries", ["ID"]),
    ("M01", "MdcArchiveBrowse", "dbo", "BExamIndex", ["MID"], "ID", "MdcArchiveBrowse", "dbo", "BPatientIndex", ["ID"]),
    ("M02", "MdcArchiveBrowse", "dbo", "BExamDetail", ["ExamID"], "ID", "MdcArchiveBrowse", "dbo", "BExamIndex", ["ID"]),
    ("M03", "MdcArchiveBrowse", "dbo", "BExamDetail", ["MID"], "ID", "MdcArchiveBrowse", "dbo", "BPatientIndex", ["ID"]),
]


def ref(db: str, schema: str, table: str) -> str:
    return f"[{db}].[{schema}].[{table}]"


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True);parser.add_argument("--sample-size",type=int,default=10_000);args=parser.parse_args()
    if not 1 <= args.sample_size <= 20_000: raise SystemExit("sample-size must be between 1 and 20000")
    import pymssql
    conn=pymssql.connect(server=os.environ.get("UE_SQLSERVER_HOST","10.10.10.161"),port=1433,user=os.environ["UE_SQLSERVER_USER"],password=os.environ["UE_SQLSERVER_PASSWORD"],database="master",login_timeout=10,timeout=60,autocommit=False,tds_version="7.0",appname="DataAssetReadOnlyRelationCheck")
    cur=conn.cursor();out=[]
    try:
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED");cur.execute("SET LOCK_TIMEOUT 5000")
        for rid,cdb,cschema,ctable,ccols,order_col,pdb,pschema,ptable,pcols in RELATIONS:
            selected=",".join(f"c0.[{x}]" for x in ccols);nonnull=" AND ".join(f"c0.[{x}] IS NOT NULL" for x in ccols);joins=" AND ".join(f"CONVERT(NVARCHAR(4000),p.[{r}])=CONVERT(NVARCHAR(4000),c.[{l}])" for l,r in zip(ccols,pcols))
            sample=f"SELECT TOP ({int(args.sample_size)}) {selected} FROM {ref(cdb,cschema,ctable)} c0 WITH (NOLOCK) WHERE {nonnull} ORDER BY c0.[{order_col}] DESC"
            cur.execute(f"SELECT COUNT_BIG(*) FROM ({sample}) c");sampled=int(cur.fetchone()[0] or 0)
            cur.execute(f"SELECT COUNT_BIG(*) FROM ({sample}) c WHERE EXISTS(SELECT 1 FROM {ref(pdb,pschema,ptable)} p WITH (NOLOCK) WHERE {joins})");matched=int(cur.fetchone()[0] or 0)
            out.append({"relationship_id":rid,"child":f"{cdb}.{cschema}.{ctable}","parent":f"{pdb}.{pschema}.{ptable}","child_columns":ccols,"parent_columns":pcols,"sampled_nonnull_keys":sampled,"matched":matched,"orphan":sampled-matched,"match_rate":round(matched/sampled,6) if sampled else None})
        payload={"generated_at":datetime.now(timezone.utc).isoformat(),"source":"10.10.10.161:1433","safety":{"isolation":"READ UNCOMMITTED","nolock":True,"sample_limit_per_relation":args.sample_size,"source_writes":0},"results":out};args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps({"checked":len(out),"source_writes":0},ensure_ascii=False))
    finally:
        cur.close();conn.rollback();conn.close()


if __name__=="__main__":main()
