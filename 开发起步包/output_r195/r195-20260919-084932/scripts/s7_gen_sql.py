# -*- coding: utf-8 -*-
"""S7：生成生产单事务入库 SQL（r195_insert.sql）。
内容：114 条幂等 INSERT（与隔离预演同款 NOT EXISTS 守卫）+ 1 行审计 + 行数守卫 DO 块。
dollar-quoting（$r195$）避免转义问题。
"""
import json
import os

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
payload = json.load(open(os.path.join(RUN_DIR, "import_payload_reviews.json"), encoding="utf-8"))["rows"]
assert len(payload) == 114, f"payload 行数异常: {len(payload)}"

TAG = "$r195$"


def q(v):
    return TAG + str(v) + TAG


stmts = []
for r in payload:
    stmts.append(
        "INSERT INTO asset.asset_relation_reviews\n"
        "(relation_scope, from_system_code, from_table, from_columns, to_system_code, to_table, to_columns,\n"
        " join_condition, relation_desc_cn, business_logic_cn, confidence, review_status, source_evidence, created_at)\n"
        "SELECT {scope}, {fsys}, {ftab}, {fcol}, {tsys}, {ttab}, {tcol}, {jc}, {rdesc}, {blogic}, {conf}, 'draft', {ev}, now()\n"
        "WHERE NOT EXISTS (\n"
        "  SELECT 1 FROM asset.asset_relation_reviews r\n"
        "  WHERE r.relation_scope = {scope}\n"
        "    AND upper(r.from_table)=upper({ftab}) AND coalesce(r.from_columns,'')=coalesce({fcol},'')\n"
        "    AND upper(r.to_table)=upper({ttab}) AND coalesce(r.to_columns,'')=coalesce({tcol},'')\n"
        ");".format(
            scope=q(r["relation_scope"]), fsys=q(r["from_system_code"]), ftab=q(r["from_table"]),
            fcol=q(r["from_columns"]), tsys=q(r["to_system_code"]), ttab=q(r["to_table"]),
            tcol=q(r["to_columns"]), jc=q(r["join_condition"]), rdesc=q(r["relation_desc_cn"]),
            blogic=q(r["business_logic_cn"]), conf=q(r["confidence"]), ev=q(r["source_evidence"]),
        ))

audit = (
    "INSERT INTO asset.asset_govern_audit_logs\n"
    "(module, entity_type, entity_ref, action, before_data, after_data, operator, reason, created_at)\n"
    "VALUES (\n"
    f"  {q('relation_intake')},\n"
    f"  {q('asset_relation_reviews')},\n"
    f"  {q('r195-20260919-084932')},\n"
    f"  {q('batch_insert_draft')},\n"
    "  '{\"before\": {\"r195_intake_rows\": 0, \"total_reviews\": 560}}'::jsonb,\n"
    "  '{\"after\": {\"insert_expected\": 114, \"payload_sha256_prefix\": \"e9bb821cc2636255\", \"source\": \"195号三甲视图关系再核验\", \"backup\": \"/opt/data-asset/backup/data_asset_pre_r195_20260919.dump\", \"backup_sha256_prefix\": \"0974f2bd87440f4f\"}}'::jsonb,\n"
    f"  {q('ai:r195-intake')},\n"
    f"  {q('用户2026-09-20批准S7生产入库：114条r195_intake草稿，单事务，批次级撤销=DELETE WHERE relation_scope=r195_intake')},\n"
    "  now());"
)

guard = (
    "DO $$\n"
    "DECLARE n int;\n"
    "BEGIN\n"
    "  SELECT count(*) INTO n FROM asset.asset_relation_reviews WHERE relation_scope = 'r195_intake';\n"
    "  IF n <> 114 THEN\n"
    "    RAISE EXCEPTION 'r195_intake 行数守卫失败: % (期望114)，事务回滚', n;\n"
    "  END IF;\n"
    "END $$;"
)

sql = "-- r195 S7 生产入库 | 单事务执行: psql -1 -v ON_ERROR_STOP=1\n"
sql += "-- run_id=r195-20260919-084932 | payload SHA-256 前16: e9bb821cc2636255 | 2026-09-20 用户批准\n\n"
sql += "\n\n".join(stmts) + "\n\n" + audit + "\n\n" + guard + "\n"

out = os.path.join(RUN_DIR, "sql", "r195_insert.sql")
open(out, "w", encoding="utf-8", newline="\n").write(sql)
print("written", out, len(sql), "bytes,", len(stmts), "inserts")
