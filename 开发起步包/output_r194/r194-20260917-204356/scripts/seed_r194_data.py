# r194 S1: deterministic synthetic seed for isolated platform DB (data_asset_test only).
# Sections are fault-isolated; summary JSON written next to this file.
# Roles/accounts A-F, systems/sources/tables/columns/relations/candidates/recipes,
# value domains, dicts, queries/metrics/products/runs, quality ledger, identity
# 3x3 account-state combos, sync batches/subtasks, AI feedback, audit, metadata
# snapshots/diffs, probe findings, lineage, ops templates/runs.
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models.asset_system as ms
import app.models.asset as ma
import app.models.candidate as mc
import app.models.recipe as mr
import app.models.value_domain as mv
import app.models.dict_medical as mdm
import app.models.dict_general as mdg
import app.models.query_asset as mq
import app.models.query_schedule as mqs
import app.models.metric_asset as mm
import app.models.data_product as mp
import app.models.quality_governance as mg
import app.models.identity as mi
import app.models.identity_sync as mis
import app.models.ai_accuracy as mai
import app.models.governance_base as mgb
import app.models.governance_ops as mo
import app.models.probe as mpr
import app.models.metadata_change as mmc
import app.models.metadata_change as _  # noqa
import app.models.governance as mgov
import app.models.lineage as ml
import app.models.ops_tool as mot
import app.models.auth as mauth
from app.services import auth_service

UTC = timezone.utc
NOW = datetime(2026, 9, 17, 10, 0, 0, tzinfo=UTC)
PW = "R194Seed#A1"

SUMMARY = {}


def section(name):
    def deco(fn):
        def run(db):
            try:
                n = fn(db)
                SUMMARY[name] = {"ok": True, "count": n}
                print(f"[seed] {name}: ok ({n})")
            except Exception as e:
                db.rollback()
                SUMMARY[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
                print(f"[seed] {name}: FAIL {type(e).__name__}: {e}")
        return run
    return deco


@section("users")
def s_users(db):
    n = 0
    specs = [
        ("r194_admin", ["platform_admin"], False),
        ("r194_viewer", ["asset_viewer"], False),
        ("r194_qa_a", ["quality_admin"], False),
        ("r194_qa_b", ["quality_admin"], False),
        ("r194_norole", [], False),
        ("r194_expiring", ["asset_viewer"], False),
    ]
    for username, roles, must in specs:
        if db.query(mauth.AuthUser).filter_by(username=username).first():
            continue
        u = auth_service.create_local_user(
            db, username=username, password=PW + username[-1].upper() + "9x",
            user_identifier=username, must_change_password=must)
        for r in roles:
            db.add(mgb.AssetUserRole(user_identifier=username, role_code=r))
        n += 1
    db.commit()
    return n


@section("systems_sources")
def s_systems(db):
    n = 0
    sys_specs = [
        ("SYS_R194A", "194测试系统甲", "HIS"),
        ("SYS_R194B", "194测试系统乙", "LIS"),
        ("SYS_R194C", "194空测试系统", "OTHER"),
    ]
    for code, name, typ in sys_specs:
        if not db.query(ms.AssetSystem).filter_by(system_code=code).first():
            db.add(ms.AssetSystem(system_code=code, system_name_cn=name, system_type=typ,
                                  target_host="127.0.0.1", owner_department="信息科",
                                  description_cn="r194 合成系统（只测不修）", status="active"))
            n += 1
    src_specs = [
        ("SYS_R194A", "R194A1", "194甲源一(Oracle)", "oracle", 11521, "orcl"),
        ("SYS_R194A", "R194A2", "194甲源二(Postgres)", "postgresql", 15432, "pdb1"),
        ("SYS_R194B", "R194B1", "194乙源一(MySQL)", "mysql", 13306, "clinicdb"),
    ]
    for sysc, srcc, name, dbt, port, dbname in src_specs:
        if not db.query(ms.AssetDataSource).filter_by(source_code=srcc).first():
            db.add(ms.AssetDataSource(
                system_code=sysc, source_code=srcc, source_name_cn=name, db_type=dbt,
                host_masked="127.0.0.*", target_host="127.0.0.1", port=port,
                database_name=dbname, default_schema="CLIN" if dbt != "mysql" else "clinic",
                write_policy="readonly", credential_status="unconfigured",
                environment="test", enabled=True, collect_mode="metadata_only"))
            n += 1
    sch = [("R194A1", "CLIN"), ("R194A2", "CLIN"), ("R194B1", "clinic")]
    for srcc, schema in sch:
        if not db.query(ms.AssetSourceSchema).filter_by(source_code=srcc, schema_name=schema).first():
            db.add(ms.AssetSourceSchema(source_code=srcc, schema_name=schema, table_count=0))
            n += 1
    db.commit()
    return n


@section("tables_columns")
def s_tables(db):
    n = 0
    long_name = "测试超长中文表名用于验证界面换行悬停与图谱标签遮挡场景_" * 2
    specs = [
        # (source, schema, table, cn, comment, pk, columns)
        ("R194A1", "CLIN", "PATIENT_INFO", "患者主索引", "患者基本信息表", "PATIENT_ID",
         [("PATIENT_ID", "患者ID", "VARCHAR2(20)", "N"), ("NAME", "姓名(敏感)", "VARCHAR2(60)", "Y"),
          ("SEX", "性别代码", "VARCHAR2(2)", "Y"), ("BIRTH_DATE", "出生日期", "DATE", "Y")]),
        ("R194A1", "CLIN", "VISIT_RECORD", "就诊记录", null := None, "VISIT_ID",
         [("VISIT_ID", "就诊ID", "VARCHAR2(24)", "N"), ("PATIENT_ID", "患者ID", "VARCHAR2(20)", "N"),
          ("VISIT_TYPE", "就诊类型", "VARCHAR2(2)", "Y"), ("IN_TIME", "入院时间", "TIMESTAMP", "Y"),
          ("PARENT_VISIT_ID", "父就诊ID", "VARCHAR2(24)", "Y")]),
        ("R194A1", "CLIN", "EXAM_ORDER", "检查申请", "检查申请单", "EXAM_NO",
         [("EXAM_NO", "检查号", "VARCHAR2(20)", "N"), ("VISIT_ID", "就诊ID", "VARCHAR2(24)", "N"),
          ("STATUS", "状态", "VARCHAR2(2)", "Y"), ("IS_URGENT", "急查标志", "VARCHAR2(1)", "Y")]),
        ("R194A1", "CLIN", "NO_COMMENT_TBL", None, None, "ID",
         [("ID", None, "NUMBER(10)", "N"), ("VAL", None, "VARCHAR2(50)", "Y")]),
        ("R194A1", "CLIN", long_name, "长名称表", "验证长标签", "ID",
         [("ID", "主键", "NUMBER(10)", "N"), ("CONTENT", "内容", "CLOB", "Y")]),
        ("R194A2", "CLIN", "PATIENT_INFO", "患者主索引(乙源)", "同名表-甲源二", "PATIENT_ID",
         [("PATIENT_ID", "患者ID", "varchar(20)", "NO"), ("NAME", "姓名", "varchar(60)", "YES"),
          ("SEX_CODE", "性别", "varchar(2)", "YES")]),
        ("R194A2", "CLIN", "VISIT_RECORD", "就诊记录(乙源)", "同名表-甲源二", "VISIT_ID",
         [("VISIT_ID", "visit id", "varchar(24)", "NO"), ("PATIENT_ID", "患者ID", "varchar(20)", "NO")]),
        ("R194B1", "clinic", "LAB_RESULT_TEST", "检验结果", "合成检验结果表", "TEST_NO",
         [("TEST_NO", "检验单号", "varchar(20)", "NO"), ("PATIENT_ID", "患者ID", "varchar(20)", "NO"),
          ("ITEM_CODE", "项目编码", "varchar(20)", "YES"), ("RESULT_FLAG", "结果标志", "varchar(2)", "YES")]),
        ("R194B1", "clinic", "PATIENT_INFO", "患者主索引(乙系统)", "同名表-乙系统", "PATIENT_ID",
         [("PATIENT_ID", "患者ID", "varchar(20)", "NO"), ("NAME", "姓名", "varchar(60)", "YES")]),
        ("R194B1", "clinic", "ORPHAN_TBL", "孤立表", None, None,
         [("STRAY_FIELD", "无关系字段", "varchar(30)", "YES")]),
    ]
    sysmap = {"R194A1": "SYS_R194A", "R194A2": "SYS_R194A", "R194B1": "SYS_R194B"}
    for srcc, schema, tbl, cn, cmt, pk, cols in specs:
        if db.query(ma.AssetTable).filter_by(source_code=srcc, schema_name=schema, table_name=tbl).first():
            continue
        db.add(ma.AssetTable(
            system_code=sysmap[srcc], source_code=srcc, schema_name=schema, table_name=tbl,
            table_name_cn=cn, comment=cmt, pk=pk, column_count=len(cols), domain="临床",
            include_status="included", review_status="reviewed", row_count_stats="123",
            row_presence_status="has_rows"))
        for i, (col, colcn, dt, nullable) in enumerate(cols, 1):
            db.add(ma.AssetColumn(
                system_code=sysmap[srcc], source_code=srcc, schema_name=schema, table_name=tbl,
                column_id=i, column_name=col, column_name_cn=colcn, data_type=dt,
                nullable=nullable, is_sensitive=(col == "NAME"), review_status="reviewed",
                semantic_type="key" if col == pk else None))
        n += 1
    db.commit()
    return n


@section("relations")
def s_relations(db):
    n = 0
    rel_specs = [
        dict(rel_id=19401, domain="临床", from_table="CLIN.PATIENT_INFO", from_columns="PATIENT_ID",
             to_table="CLIN.VISIT_RECORD", to_columns="PATIENT_ID",
             join_condition="a.PATIENT_ID = b.PATIENT_ID", cardinality="1:N",
             confidence="A", validation_level="live_join", validation_status="passed",
             relation_layer="formal",
             fs="SYS_R194A", fsrc="R194A1", ts="SYS_R194A", tsrc="R194A1",
             ftn="PATIENT_INFO", ttn="VISIT_RECORD"),
        dict(rel_id=19402, domain="临床", from_table="CLIN.VISIT_RECORD", from_columns="VISIT_ID",
             to_table="CLIN.EXAM_ORDER", to_columns="VISIT_ID",
             join_condition="v.VISIT_ID = e.VISIT_ID", cardinality="1:N",
             confidence="B", validation_level="live_join", validation_status="passed",
             relation_layer="formal",
             fs="SYS_R194A", fsrc="R194A1", ts="SYS_R194A", tsrc="R194A1",
             ftn="VISIT_RECORD", ttn="EXAM_ORDER"),
        # self loop
        dict(rel_id=19403, domain="临床", from_table="CLIN.VISIT_RECORD", from_columns="PARENT_VISIT_ID",
             to_table="CLIN.VISIT_RECORD", to_columns="VISIT_ID",
             join_condition="v1.PARENT_VISIT_ID = v2.VISIT_ID", cardinality="N:1",
             confidence="B", validation_level="sampled", validation_status="passed",
             relation_layer="formal",
             fs="SYS_R194A", fsrc="R194A1", ts="SYS_R194A", tsrc="R194A1",
             ftn="VISIT_RECORD", ttn="VISIT_RECORD"),
        # reverse edge of 19401 (bidirectional pair)
        dict(rel_id=19404, domain="临床", from_table="CLIN.VISIT_RECORD", from_columns="PATIENT_ID",
             to_table="CLIN.PATIENT_INFO", to_columns="PATIENT_ID",
             join_condition="b.PATIENT_ID = a.PATIENT_ID", cardinality="N:1",
             confidence="B", validation_level="sampled", validation_status="passed",
             relation_layer="formal",
             fs="SYS_R194A", fsrc="R194A1", ts="SYS_R194A", tsrc="R194A1",
             ftn="VISIT_RECORD", ttn="PATIENT_INFO"),
        # candidate layer
        dict(rel_id=19405, domain="跨源", from_table="clinic.LAB_RESULT_TEST", from_columns="PATIENT_ID",
             to_table="clinic.PATIENT_INFO", to_columns="PATIENT_ID",
             join_condition="l.PATIENT_ID = p.PATIENT_ID", cardinality="N:1",
             confidence="C", validation_level="unverified", validation_status="pending",
             relation_layer="candidate",
             fs="SYS_R194B", fsrc="R194B1", ts="SYS_R194B", tsrc="R194B1",
             ftn="LAB_RESULT_TEST", ttn="PATIENT_INFO"),
    ]
    for s in rel_specs:
        key = f"{s['fs']}|{s['fsrc']}|{s['ftn']}->{s['ts']}|{s['tsrc']}|{s['ttn']}|{s['from_columns']}"
        if db.query(ma.AssetRelation).filter_by(relation_business_key=key).first():
            continue
        db.add(ma.AssetRelation(
            rel_id=s["rel_id"], domain=s["domain"], from_table=s["from_table"],
            from_columns=s["from_columns"], to_table=s["to_table"], to_columns=s["to_columns"],
            join_condition=s["join_condition"], cardinality=s["cardinality"],
            confidence=s["confidence"], validation_level=s["validation_level"],
            validation_status=s["validation_status"], relation_layer=s["relation_layer"],
            from_system_code=s["fs"], from_source_code=s["fsrc"], from_schema_name="CLIN" if s["fs"] == "SYS_R194A" else "clinic",
            from_table_name=s["ftn"], to_system_code=s["ts"], to_source_code=s["tsrc"],
            to_schema_name="CLIN" if s["ts"] == "SYS_R194A" else "clinic", to_table_name=s["ttn"],
            relation_business_key=key))
        n += 1
    # candidates (legacy candidate table)
    for i, (ft, fc, tt, tc, status) in enumerate([
        ("CLIN.PATIENT_INFO", "PATIENT_ID", "clinic.PATIENT_INFO", "PATIENT_ID", "candidate"),
        ("CLIN.VISIT_RECORD", "VISIT_ID", "clinic.LAB_RESULT_TEST", "TEST_NO", "candidate"),
        ("CLIN.EXAM_ORDER", "EXAM_NO", "clinic.LAB_RESULT_TEST", "TEST_NO", "candidate"),
        ("CLIN.PATIENT_INFO", "NAME", "clinic.PATIENT_INFO", "NAME", "rejected"),
    ], 19410):
        if not db.query(mc.AssetCandidateRelation).filter_by(from_table=ft, to_table=tt, from_columns=fc).first():
            db.add(mc.AssetCandidateRelation(
                domain="跨源", from_table=ft, from_columns=fc, to_table=tt, to_columns=tc,
                join_condition=f"a.{fc.split(',')[0]} = b.{tc.split(',')[0]}",
                confidence="C", status=status, source_view="V_R194_SEED",
                note="r194 synthetic candidate"))
            n += 1
    # reviews: draft candidate-scope + approved formal + rejected
    rev_specs = [
        ("candidate", "CLIN.PATIENT_INFO", "clinic.PATIENT_INFO", "draft", None),
        ("formal", "CLIN.PATIENT_INFO", "CLIN.VISIT_RECORD", "approved", "r194_admin"),
        ("formal", "CLIN.VISIT_RECORD", "CLIN.EXAM_ORDER", "approved", "r194_admin"),
        ("candidate", "CLIN.PATIENT_INFO", "clinic.PATIENT_INFO", "rejected", "r194_admin"),
    ]
    for scope, ft, tt, st, reviewer in rev_specs:
        if not db.query(ma.AssetRelationReview).filter_by(from_table=ft, to_table=tt, review_status=st).first():
            db.add(ma.AssetRelationReview(
                relation_scope=scope, from_table=ft, from_columns="PATIENT_ID",
                to_table=tt, to_columns="PATIENT_ID",
                join_condition="a.PATIENT_ID = b.PATIENT_ID",
                confidence="B" if scope == "formal" else "C",
                review_status=st, reviewer=reviewer,
                reviewed_at=NOW if st != "draft" else None,
                review_note="r194 synthetic review",
                source_evidence="seed", relation_desc_cn="r194 合成复核",
                business_logic_cn="按患者主索引关联"))
            n += 1
    db.commit()
    return n


@section("recipes")
def s_recipes(db):
    n = 0
    if not db.query(mr.AssetRelationRecipe).filter_by(recipe_id="R194-RECIPE-1").first():
        db.add(mr.AssetRelationRecipe(
            recipe_id="R194-RECIPE-1", version=1, recipe_name="患者-就诊关联配方",
            status="active", is_active=True,
            description="r194 active 合成配方",
            domain="临床", primary_tables=["CLIN.PATIENT_INFO", "CLIN.VISIT_RECORD"],
            generated_sql="SELECT /*+ USE_NL(v) */ v.VISIT_ID FROM CLIN.PATIENT_INFO p JOIN CLIN.VISIT_RECORD v ON p.PATIENT_ID = v.PATIENT_ID WHERE v.IN_TIME >= :start_date",
            sql_dialect="oracle", content_hash=hashlib.sha256("R194-RECIPE-1".encode()).hexdigest()[:16], created_by="r194_admin"))
        n += 1
    if not db.query(mr.AssetRelationRecipe).filter_by(recipe_id="R194-RECIPE-2").first():
        db.add(mr.AssetRelationRecipe(
            recipe_id="R194-RECIPE-2", version=1, recipe_name="停用配方示例",
            status="inactive", is_active=False,
            description="r194 inactive 合成配方（不得当可执行）",
            domain="临床", primary_tables=["clinic.LAB_RESULT_TEST"],
            generated_sql="SELECT 1 FROM clinic.LAB_RESULT_TEST WHERE TEST_NO = :no",
            sql_dialect="mysql", content_hash=hashlib.sha256("R194-RECIPE-2".encode()).hexdigest()[:16], created_by="r194_admin"))
        n += 1
    db.commit()
    return n


@section("value_domains")
def s_vd(db):
    n = 0
    base = dict(system_code="SYS_R194A", source_code="R194A1", schema_name="CLIN", domain_kind="enum")
    specs = [
        (dict(**base, table_name="VISIT_RECORD", column_name="VISIT_TYPE",
              status="confirmed", code="1", meaning="普通就诊", confirmed_by="r194_admin"),
         [("1", "普通就诊"), ("2", "急诊就诊"), ("3", "日间就诊")]),
        (dict(**base, table_name="EXAM_ORDER", column_name="STATUS",
              status="pending", code="1", meaning="申请"),
         [("1", "申请"), ("2", "执行"), ("3", "报告")]),
        (dict(**base, table_name="EXAM_ORDER", column_name="IS_URGENT",
              status="pending", code="0", meaning="否", conflict_status="conflict"),
         [("0", "否"), ("1", "是")]),
    ]
    for kw, items in specs:
        if db.query(mv.AssetColumnValueDomain).filter_by(
                source_code=kw["source_code"], table_name=kw["table_name"],
                column_name=kw["column_name"], code=kw["code"]).first():
            continue
        dom = mv.AssetColumnValueDomain(**kw)
        if kw.get("status") == "confirmed" and "confirmed_at" in [c.name for c in mv.AssetColumnValueDomain.__table__.columns]:
            dom.confirmed_at = NOW
        db.add(dom)
        db.flush()
        db.add(mv.AssetColumnValueDomainVersion(
            domain_id=dom.id, version_no=1,
            snapshot={"items": [{"code": c, "meaning": m} for c, m in items]}))
        db.add(mv.AssetColumnValueDomainEvidence(
            domain_id=dom.id, source_type="seed_synthetic",
            observed_meaning="r194 合成证据" + ("（与字典一致）" if kw.get("status") == "confirmed" else "（待核）"),
            actor="r194_admin"))
        n += 1
    db.commit()
    return n


@section("dicts")
def s_dict(db):
    n = 0
    if not db.query(mdm.DictMedicalCodeSet).filter_by(code_set_code="R194_ICD10").first():
        db.add(mdm.DictMedicalCodeSet(category_code="diagnosis", code_set_code="R194_ICD10",
                                      code_set_type="icd", code_set_name_cn="r194诊断字典"))
        db.add(mdm.DictMedicalCodeSet(category_code="operation", code_set_code="R194_ICD9",
                                      code_set_type="icd9", code_set_name_cn="r194手术字典"))
        n += 2
    for i, (code, nm) in enumerate([("I50.900", "心力衰竭"), ("J06.900", "急性上呼吸道感染"),
                                    ("E11.900", "2型糖尿病"), ("I50.900x002", "慢性心力衰竭")]):
        if not db.query(mdm.DictMedicalCodeItem).filter_by(code_set_code="R194_ICD10", item_code=code).first():
            db.add(mdm.DictMedicalCodeItem(code_set_code="R194_ICD10", item_code=code,
                                           item_name_cn=nm, category_code="diagnosis"))
            n += 1
    if not db.query(mdm.DictMedicalCodeMapping).filter_by(category_code="diagnosis", from_code_set="R194_ICD10").first():
        db.add(mdm.DictMedicalCodeMapping(category_code="diagnosis", from_code_set="R194_ICD10",
                                          from_item_code="I50.900", to_code_set="R194_STD",
                                          to_item_code="HF-001", mapping_type="cross",
                                          review_status="approved", reviewer="r194_admin"))
        n += 1
    # general dicts
    if not db.query(mdg.DictCategory).filter_by(category_code="R194_GENDER").first():
        db.add(mdg.DictCategory(category_code="R194_GENDER", category_name_cn="r194性别代码"))
        n += 1
    for code, nm in [("1", "男"), ("2", "女"), ("9", "未知")]:
        if not db.query(mdg.DictStandardItem).filter_by(category_code="R194_GENDER", standard_code=code).first():
            db.add(mdg.DictStandardItem(category_code="R194_GENDER", standard_code=code,
                                        standard_name_cn=nm, status="active"))
            n += 1
    for code, nm in [("M", "男"), ("F", "女"), ("0", "未说明")]:
        if not db.query(mdg.DictSystemItem).filter_by(category_code="R194_GENDER", system_code="SYS_R194A", system_item_code=code).first():
            db.add(mdg.DictSystemItem(category_code="R194_GENDER", system_code="SYS_R194A",
                                      system_item_code=code, system_item_name_cn=nm))
            n += 1
    for sysc, sysitem, std in [("M", "M", "1"), ("F", "F", "2"), ("0", "0", "9")]:
        if not db.query(mdg.DictItemMapping).filter_by(category_code="R194_GENDER", system_code="SYS_R194A", system_item_code=sysitem).first():
            kw = dict(category_code="R194_GENDER", system_code="SYS_R194A",
                      system_item_code=sysitem, standard_code=std)
            mcols = [c.name for c in mdg.DictItemMapping.__table__.columns]
            if "status" in mcols:
                kw["status"] = "active"
            if "mapping_status" in mcols:
                kw["mapping_status"] = "active"
            db.add(mdg.DictItemMapping(**kw))
            n += 1
    if not db.query(mdg.DictVersion).filter_by(category_code="R194_GENDER").first():
        db.add(mdg.DictVersion(category_code="R194_GENDER", version_no=1, version_name_cn="r194 v1", publish_status="published"))
        n += 1
    db.commit()
    return n


@section("queries_metrics_products")
def s_queries(db):
    n = 0
    def sha(t):
        return hashlib.sha256(t.encode()).hexdigest()
    qdefs = [
        ("QRY_R194_A", "合成查询A-就诊量按类型", "active"),
        ("QRY_R194_B", "合成查询B-legacy", "active"),
        ("QRY_R194_C", "合成查询C-已停用", "blocked"),
    ]
    qids = {}
    for code, title, status in qdefs:
        q = db.query(mq.AssetQueryDefinition).filter_by(query_code=code).first()
        if not q:
            q = mq.AssetQueryDefinition(query_code=code, title=title, system_code="SYS_R194A",
                                        source_code="R194A1", status=status,
                                        business_domain="临床", owner_name="r194_admin",
                                        sensitivity="aggregate", created_by="r194_admin")
            db.add(q); db.flush()
            n += 1
        qids[code] = q.id
    sql = ("SELECT v.VISIT_TYPE, COUNT(*) AS CNT FROM CLIN.VISIT_RECORD v "
           "WHERE v.IN_TIME >= TO_DATE(:start_date,'YYYY-MM-DD') GROUP BY v.VISIT_TYPE")
    vers = [
        ("QRY_R194_A", 1, "active", True, "certified"),
        ("QRY_R194_A", 2, "draft", False, "uncertified"),
        ("QRY_R194_B", 1, "active", True, "legacy_unverified"),
        ("QRY_R194_C", 1, "blocked", False, "uncertified"),
        ("QRY_R194_C", 2, "superseded", False, "uncertified"),
    ]
    vids = {}
    for code, ver, status, is_act, cert in vers:
        v = db.query(mq.AssetQueryVersion).filter_by(query_code=code, version=ver).first()
        if not v:
            v = mq.AssetQueryVersion(
                query_id=qids[code], query_code=code, version=ver, status=status,
                is_active=is_act, dialect="oracle", sql_text=sql, sql_sha256=sha(sql + code + str(ver)),
                parameter_schema=[{"name": "start_date", "type": "date", "required": True,
                                   "description": "起始日期"}],
                certification_status=cert, created_by="r194_admin")
            db.add(v); db.flush()
            db.add(mq.AssetQueryDependency(
                query_version_id=v.id, dep_type="table", system_code="SYS_R194A",
                source_code="R194A1", schema_name="CLIN", object_name="VISIT_RECORD",
                is_formal=True, evidence="r194 seed", resolution_status="resolved"))
            n += 1
        vids[(code, ver)] = v.id
    qa = db.query(mq.AssetQueryDefinition).filter_by(query_code="QRY_R194_A").first()
    qa.current_version_id = vids[("QRY_R194_A", 1)]
    runs = [
        ("QRY_R194_A", 1, "success", 12, 340, {"start_date": "2026-01-01"}),
        ("QRY_R194_A", 1, "failed", None, 20, {"start_date": "BAD"}),
        ("QRY_R194_B", 1, "timeout", None, 300000, {"start_date": "2025-01-01"}),
    ]
    for code, ver, status, rows_, dur, params in runs:
        r = mq.AssetQueryRun(
            query_version_id=vids[(code, ver)], query_code=code, version=ver,
            source_code="R194A1", dialect="oracle", parameters=params,
            parameters_hash=sha(json.dumps(params, sort_keys=True)), status=status,
            started_at=NOW - timedelta(hours=3), finished_at=NOW - timedelta(hours=3, seconds=-dur / 1000 if dur else 1),
            duration_ms=dur, row_count=rows_, result_storage="summary",
            result_hash=sha(code + status) if status == "success" else None,
            triggered_by="r194_admin" if "triggered_by" in
            [c.name for c in mq.AssetQueryRun.__table__.columns] else None)
        if status == "failed" and "error_message" in [c.name for c in mq.AssetQueryRun.__table__.columns]:
            r.error_message = "ORA-00942: 表或视图不存在（r194 合成失败）"
        db.add(r)
        n += 1
    # metric: 3/4 = 75% oracle for Q08
    m = db.query(mm.AssetMetricDefinition).filter_by(metric_code="MET_R194_1").first()
    if not m:
        m = mm.AssetMetricDefinition(metric_code="MET_R194_1", title="合成指标-急诊占比",
                                     meaning="急诊就诊占总就诊比例", category="临床",
                                     unit="ratio", frequency="monthly", owner_dept="NK",
                                     created_by="r194_admin", status="active")
        db.add(m); db.flush(); n += 1
    mv_cols = [c.name for c in mm.AssetMetricVersion.__table__.columns]
    mv_kw = dict(metric_id=m.id, metric_code="MET_R194_1", version=1,
                 status="active", is_active=True)
    for k, v in (("formula", "numerator / denominator"),
                 ("numerator_desc", "急诊就诊数(VISIT_TYPE=2)"),
                 ("denominator_desc", "总就诊数"),
                 ("query_code", "QRY_R194_A"), ("query_version", 1)):
        if k in mv_cols:
            mv_kw[k] = v
    mv_row = db.query(mm.AssetMetricVersion).filter_by(metric_id=m.id, version=1).first()
    if not mv_row:
        mv_row = mm.AssetMetricVersion(**mv_kw)
        db.add(mv_row); db.flush(); n += 1
    mr_cols = [c.name for c in mm.AssetMetricResult.__table__.columns]
    res_kw = dict(metric_version_id=mv_row.id, metric_code="MET_R194_1",
                  version=1, period_key="2026-09", metric_value=0.75, status="final")
    for k, v in (("numerator_value", 3), ("denominator_value", 4),
                 ("numerator_num", 3), ("denominator_num", 4)):
        if k in mr_cols:
            res_kw[k] = v
    res = mm.AssetMetricResult(**res_kw)
    db.add(res); db.flush(); n += 1
    db.add(mm.AssetMetricRun(metric_code="MET_R194_1", metric_version_id=mv_row.id,
                             version=1, period_key="2026-09", status="success",
                             started_at=NOW - timedelta(hours=2), finished_at=NOW - timedelta(hours=2, minutes=-1)))
    n += 1
    p_cols = [c.name for c in mp.AssetDataProduct.__table__.columns]
    if not db.query(mp.AssetDataProduct).filter_by(product_code="PRD_R194_1").first():
        kw = dict(product_code="PRD_R194_1", title="合成产品-急诊监测看板",
                  product_type="dashboard", status="published",
                  metric_codes=["MET_R194_1"] if "metric_codes" in p_cols else None,
                  owner="r194_admin")
        db.add(mp.AssetDataProduct(**{k: v for k, v in kw.items() if k in p_cols}))
        n += 1
    if not db.query(mqs.AssetQuerySchedule).filter_by(query_code="QRY_R194_A").first():
        db.add(mqs.AssetQuerySchedule(query_code="QRY_R194_A", source_code="R194A1",
                                      enabled=False, schedule_cron="0 3 * * *",
                                      created_by="r194_admin"))
        n += 1
    db.commit()
    return n


@section("quality")
def s_quality(db):
    n = 0
    ctrl_specs = [
        ("QC_R194_1", "内科-就诊类型完整性", "active", "NK", "r194_qa_a"),
        ("QC_R194_2", "外科-检验结果标志规范", "active", "WK", "r194_qa_b"),
        ("QC_R194_3", "草稿-检查状态规范", "draft", "NK", None),
    ]
    cids = {}
    for code, title, life, dept, assignee in ctrl_specs:
        c = db.query(mg.QualityControl).filter_by(control_code=code).first()
        if not c:
            c = mg.QualityControl(control_code=code, version=1, title=title,
                                  lifecycle_status=life, dimension="completeness",
                                  category="data", primary_system_code="SYS_R194A",
                                  metric_name="null_ratio", comparator="lte", metric_unit="ratio",
                                  threshold_value=0.05, no_data_policy="blocked",
                                  default_severity="medium", default_priority="P2",
                                  default_dept_code=dept, verification_policy="manual",
                                  created_by="r194_admin", updated_by="r194_admin")
            db.add(c); db.flush(); n += 1
        cids[code] = c.id
        if not db.query(mg.QualityControlDetector).filter_by(control_id=c.id).first():
            db.add(mg.QualityControlDetector(control_id=c.id, detector_kind="manual",
                                             detector_ref="r194-seed", detector_version="1",
                                             status="active" if life == "active" else "draft",
                                             last_bound_at=NOW, created_by="r194_admin"))
            n += 1
    obs_specs = [
        ("QC_R194_1", "pass", 0.01, 4, 400, None),
        ("QC_R194_2", "fail", 0.30, 30, 100, "threshold_exceeded"),
        ("QC_R194_1", "no_data", None, None, None, "no_rows"),
    ]
    obs_ids = []
    for code, st, val, num, den, err in obs_specs:
        if db.query(mg.QualityObservation).filter_by(control_id=cids[code], run_key=f"run-{code}-{st}").first():
            continue
        o = mg.QualityObservation(control_id=cids[code], control_version=1,
                                  run_key=f"run-{code}-{st}", scope_key="seed-scope",
                                  window_start=None, window_end=None,
                                  observed_at=NOW - timedelta(hours=5),
                                  result_status=st, metric_value=val, metric_unit="ratio",
                                  numerator=num, denominator=den, source_kind="manual",
                                  source_record_ref="r194-seed", historical_precision="exact",
                                  error_code=err, created_by="r194_admin")
        db.add(o); db.flush(); obs_ids.append(o.id); n += 1
    iss_specs = [
        ("ISS194-0001", "QC_R194_1", "内科就诊类型存在空值", "NK", "r194_qa_a", "in_progress", 0),
        ("ISS194-0002", "QC_R194_2", "外科检验标志越界", "WK", "r194_qa_b", "new", 1),
        ("ISS194-0003", "QC_R194_1", "已解决示例问题", "NK", "r194_qa_a", "resolved", None),
    ]
    for code, ctrl, title, dept, assignee, status, obs_i in iss_specs:
        if db.query(mg.QualityIssue).filter_by(issue_code=code).first():
            continue
        i = mg.QualityIssue(issue_code=code, control_id=cids[ctrl], issue_type="data_defect",
                            title=title, description="r194 合成问题（只测不修）",
                            primary_system_code="SYS_R194A", scope_key="seed-scope",
                            severity="medium", priority="P2", status=status,
                            responsible_dept_code=dept,
                            assignee_user_identifier=assignee,
                            responsible_dept_name_snapshot="内科" if dept == "NK" else "外科",
                            assignee_name_snapshot=assignee,
                            latest_observation_id=obs_ids[obs_i] if obs_i is not None else None,
                            first_seen_at=NOW - timedelta(days=2),
                            last_seen_at=NOW - timedelta(hours=5),
                            created_by="r194_admin", updated_by="r194_admin")
        db.add(i); db.flush(); n += 1
        db.add(mg.QualityIssueEvent(issue_id=i.id, event_type="created",
                                    from_status=None, to_status="new",
                                    actor_user_identifier="r194_admin",
                                    occurred_at=NOW - timedelta(days=2),
                                    reason="r194 seed"))
        if status != "new":
            db.add(mg.QualityIssueEvent(issue_id=i.id, event_type="status_changed",
                                        from_status="new", to_status=status,
                                        actor_user_identifier=assignee,
                                        occurred_at=NOW - timedelta(days=1),
                                        reason="r194 seed transition"))
    db.commit()
    return n


@section("identity")
def s_identity(db):
    n = 0
    depts = [("NK", "内科"), ("WK", "外科"), ("XK", "信息科")]
    for code, name in depts:
        if not db.query(mi.IdentityDepartment).filter_by(dept_code=code).first():
            db.add(mi.IdentityDepartment(dept_code=code, dept_name_cn=name, dept_type="clinical" if code != "XK" else "admin"))
            n += 1
    # 3x3 combos: employment(active/disabled/unknown) x account(enabled/disabled/missing)
    combos = []
    for pi, emp in enumerate(["active", "disabled", None]):
        for ai, accst in enumerate(["enabled", "disabled", "missing"]):
            combos.append((f"P1940{pi * 3 + ai + 1}", emp, accst))
    for code, emp, accst in combos:
        person = db.query(mi.IdentityPerson).filter_by(person_code=code).first()
        if not person:
            db.add(mi.IdentityPerson(
                person_code=code, person_name_cn=f"合成人员{code[-2:]}",
                dept_code="NK" if int(code[-1]) % 2 == 0 else "WK",
                dept_name_cn="内科" if int(code[-1]) % 2 == 0 else "外科",
                job_title="医师", employment_status=emp,
                primary_source_system="R194HR", is_managed=True,
                review_status="reviewed"))
            db.add(mi.IdentityPersonSource(
                source_system="R194HR", source_table="EMP", source_person_id=code,
                source_person_name=f"合成人员{code[-2:]}", source_status=emp or "unknown",
                match_status="matched"))
            n += 1
        if accst != "missing":
            for sysc in ("R194J", "R194C2"):
                if not db.query(mi.IdentityAccount).filter_by(system_code=sysc, account_id=code).first():
                    db.add(mi.IdentityAccount(
                        person_code=code, system_code=sysc, source_code=sysc,
                        account_id=code, account_name=f"账号{code}",
                        account_status=accst, last_sync_at=NOW - timedelta(hours=8)))
                    n += 1
    # protected account
    if not db.query(mis.IdentityProtectedAccount).filter_by(target_system="R194J", account_id="P19401").first():
        db.add(mis.IdentityProtectedAccount(target_system="R194J", account_id="P19401",
                                            reason="r194 受保护账号",
                                            **{"protected_by" if "protected_by" in
                                               [c.name for c in mis.IdentityProtectedAccount.__table__.columns] else "note": "r194_admin"}))
        n += 1
    # sync diffs
    for i, (dt, ent, status) in enumerate([
        ("account_missing", "P19409", "open"),
        ("account_disabled", "P19402", "open"),
        ("dept_mismatch", "P19405", "handled"),
    ]):
        if not db.query(mi.IdentitySyncDiff).filter_by(diff_type=dt, entity_code=ent).first():
            db.add(mi.IdentitySyncDiff(diff_type=dt, source_system="R194HR", target_system="R194J",
                                       entity_type="person", entity_code=ent,
                                       severity="medium", status=status,
                                       before_data={"status": "a"}, after_data={"status": "b"}))
            n += 1
    # scheduler run + subtasks (192 regression states)
    run = db.query(mis.IdentitySchedulerRun).filter_by(run_id="RUN-R194-001").first()
    if not run:
        run = mis.IdentitySchedulerRun(run_id="RUN-R194-001", triggered_by="r194-cron-sim",
                                       status="partial_success",
                                       started_at=NOW - timedelta(hours=10),
                                       finished_at=NOW - timedelta(hours=10, minutes=-42))
        run.report_summary = {"subtasks": {"login_sign": "success", "signature": "partial_success",
                                         "dept": "failed", "title": "skipped"}}
        db.add(run); db.flush(); n += 1
        sub_specs = [
            ("login_sign", "success", 36, 0, None),
            ("signature", "partial_success", 20, 3, "3 人缺签名图片"),
            ("dept", "failed", 0, 12, "ORA-00942 合成"),
            ("title", "skipped", 0, 0, "白名单未放行"),
        ]
        for code, st, okc, failc, err in sub_specs:
            db.add(mis.IdentitySyncSubtask(
                run_id="RUN-R194-001", subtask_code=code, target_system="R194J",
                status=st, planned_count=okc + failc, succeeded_count=okc,
                failed_count=failc, skipped_count=failc if st == "skipped" else 0,
                report_summary={"note": err} if err else None,
                started_at=NOW - timedelta(hours=10),
                finished_at=NOW - timedelta(hours=10, minutes=-40)))
            n += 1
    db.commit()
    return n


@section("ai_feedback")
def s_ai(db):
    n = 0
    ev_specs = [
        ("r194_viewer", "q-digest-001", "accurate"),
        ("r194_qa_a", "q-digest-002", "inaccurate"),
    ]
    for user, digest, rating in ev_specs:
        e = db.query(mai.AssetAiAnswerEvent).filter_by(question_digest=digest).first()
        if not e:
            e = mai.AssetAiAnswerEvent(question_digest=digest,
                                       **{k: v for k, v in dict(
                                           user_identifier=user, question="合成问题（脱敏）",
                                           answer="合成回答", query_code="QRY_R194_A",
                                           created_at=NOW - timedelta(hours=6)).items()
                                          if k in [c.name for c in mai.AssetAiAnswerEvent.__table__.columns]})
            db.add(e); db.flush(); n += 1
        if not db.query(mai.AssetAiFeedback).filter_by(answer_event_id=e.id, rating=rating).first():
            db.add(mai.AssetAiFeedback(answer_event_id=e.id, rating=rating,
                                       **{"comment" if "comment" in
                                          [c.name for c in mai.AssetAiFeedback.__table__.columns] else "note":
                                          "r194 合成反馈"}))
            n += 1
    if not db.query(mai.AssetQueryEvaluationCase).filter_by(case_code="CASE_R194_1").first():
        db.add(mai.AssetQueryEvaluationCase(case_code="CASE_R194_1", title="合成评测-急诊占比",
                                            query_code="QRY_R194_A",
                                            assertions={"expected_value": 0.75},
                                            enabled=True if "enabled" in
                                            [c.name for c in mai.AssetQueryEvaluationCase.__table__.columns] else None,
                                            created_by="r194_admin"))
        n += 1
        case = db.query(mai.AssetQueryEvaluationCase).filter_by(case_code="CASE_R194_1").first()
        db.add(mai.AssetQueryEvaluationRun(
            case_id=case.id, case_code="CASE_R194_1", evaluation_set_version="r194-1",
            query_code="QRY_R194_A", query_version=1, status="completed", passed=True,
            **{k: v for k, v in dict(ran_at=NOW - timedelta(hours=4), executed_by="r194_admin").items()
               if k in [c.name for c in mai.AssetQueryEvaluationRun.__table__.columns]}))
        n += 1
    db.commit()
    return n


@section("wrapup_u_items")
def s_wrapup_u(db):
    """r194 收尾会话补充：U-2 宽表码表数据 + U-5 运维事件流。

    - U-2：mapping-rows 页面契约码表为 diagnosis_local_clinical 等，原种子只写
      R194_ICD10 导致页面 0 条（口径差非缺陷），此处补齐页面口径数据。
    - U-5：运维审计页读 asset_ops_event_logs（原种子只写 govern_audit_logs），
      补 3 条脱敏运维事件。
    """
    n = 0
    # U-2：本地临床版码表 + 国家临床版 v2 目标项 + 两类映射
    local_set, national_set = "diagnosis_local_clinical", "diagnosis_national_clinical_v2"
    if not db.query(mdm.DictMedicalCodeSet).filter_by(code_set_code=local_set).first():
        db.add(mdm.DictMedicalCodeSet(category_code="diagnosis", code_set_code=local_set,
                                      code_set_type="local", code_set_name_cn="r194院内诊断码"))
        n += 1
    if not db.query(mdm.DictMedicalCodeSet).filter_by(code_set_code=national_set).first():
        db.add(mdm.DictMedicalCodeSet(category_code="diagnosis", code_set_code=national_set,
                                      code_set_type="national", code_set_name_cn="r194国家临床版v2"))
        n += 1
    for code, nm in [("I50.900", "心力衰竭"), ("E11.900", "2型糖尿病")]:
        if not db.query(mdm.DictMedicalCodeItem).filter_by(code_set_code=local_set, item_code=code).first():
            db.add(mdm.DictMedicalCodeItem(code_set_code=local_set, item_code=code,
                                           item_name_cn=nm, category_code="diagnosis"))
            n += 1
    for code, nm in [("I50.x00", "心力衰竭"), ("E11.x00", "2型糖尿病")]:
        if not db.query(mdm.DictMedicalCodeItem).filter_by(code_set_code=national_set, item_code=code).first():
            db.add(mdm.DictMedicalCodeItem(code_set_code=national_set, item_code=code,
                                           item_name_cn=nm, category_code="diagnosis"))
            n += 1
    for f, t in [("I50.900", "I50.x00"), ("E11.900", "E11.x00")]:
        if not db.query(mdm.DictMedicalCodeMapping).filter_by(
                category_code="diagnosis", from_code_set=local_set, from_item_code=f,
                to_code_set=national_set).first():
            db.add(mdm.DictMedicalCodeMapping(category_code="diagnosis", from_code_set=local_set,
                                              from_item_code=f, to_code_set=national_set,
                                              to_item_code=t, mapping_type="cross",
                                              review_status="approved", reviewer="r194_admin"))
            n += 1
    # U-5：运维事件流（脱敏摘要）
    for i, (etype, ref, action, status) in enumerate([
            ("connection", "R194A1", "probe", "success"),
            ("dict_sync", "R194_GENDER", "dry_run", "success"),
            ("quality_rule", "QR194-1", "execute", "partial")]):
        ev = f"r194w-{i + 1}"
        if not db.query(mot.OpsEventLog).filter_by(event_id=ev).first():
            db.add(mot.OpsEventLog(
                event_id=ev, module="ops", entity_type=etype, entity_ref=ref,
                action=action, status=status, operator="r194_admin",
                affected_count=2 + i, duration_ms=100 + i * 50,
                summary_masked=f"r194 合成运维事件 {ev}",
                started_at=NOW - timedelta(hours=i + 1),
                finished_at=NOW - timedelta(hours=i + 1) + timedelta(seconds=2)))
            n += 1
    db.commit()
    return n


@section("audit_metadata_probe_ops")
def s_misc(db):
    n = 0
    days = [2, 1, 0]
    modules = [("quality", "issue", "ISS194-0001", "update"), ("relations", "relation", "19401", "review"),
               ("dict", "mapping", "R194_ICD10", "import")]
    for d in days:
        for mod, etype, ref, action in modules:
            if not db.query(mgb.GovernAuditLog).filter_by(
                    module=mod, entity_type=etype, entity_ref=ref, action=action,
                    created_at=NOW - timedelta(days=d)).first():
                db.add(mgb.GovernAuditLog(
                    module=mod, entity_type=etype, entity_ref=ref, action=action,
                    operator="r194_admin",
                    created_at=NOW - timedelta(days=d),
                    reason="r194 合成审计"))
                n += 1
    # metadata snapshots: two snapshots -> diff events
    base_cols = [("VISIT_ID", "VARCHAR2(24)"), ("PATIENT_ID", "VARCHAR2(20)"),
                 ("VISIT_TYPE", "VARCHAR2(2)"), ("IN_TIME", "TIMESTAMP")]
    snap2 = [("VISIT_ID", "VARCHAR2(24)"), ("PATIENT_ID", "VARCHAR2(20)"),
             ("VISIT_TYPE", "VARCHAR2(2)"), ("IN_TIME", "TIMESTAMP"),
             ("OUT_TIME", "TIMESTAMP"), ("CHARGE_FLAG", "CHAR(1)")]
    for sid in (1941, 1942):
        if not db.query(mgov.MetadataSnapshot).filter_by(id=sid).first():
            db.add(mgov.MetadataSnapshot(id=sid, source_code="R194A1",
                                         label=f"r194-snapshot-{sid}",
                                         scope="CLIN.VISIT_RECORD",
                                         snapshot_time=NOW - timedelta(days=(1 if sid == 1941 else 0)),
                                         table_count=1, column_count=len(base_cols if sid == 1941 else snap2)))
            n += 1
    for sid, cols in ((1941, base_cols), (1942, snap2)):
        for i, (c, t) in enumerate(cols, 1):
            if not db.query(mmc.AssetMetadataColumnSnapshot).filter_by(
                    snapshot_id=sid, column_name=c).first():
                db.add(mmc.AssetMetadataColumnSnapshot(
                    snapshot_id=sid, system_code="SYS_R194A", source_code="R194A1",
                    table_name="VISIT_RECORD", column_name=c, data_type=t,
                    **{k: v for k, v in dict(nullable="Y").items()
                       if k in [c2.name for c2 in mmc.AssetMetadataColumnSnapshot.__table__.columns]}))
                n += 1
    for ctype, col in (("column_added", "OUT_TIME"), ("column_removed", "PARENT_VISIT_ID"), ("type_changed", "IN_TIME")):
        if not db.query(mmc.AssetMetadataChangeEvent).filter_by(snapshot_id_to=1942, change_type=ctype).first():
            db.add(mmc.AssetMetadataChangeEvent(
                snapshot_id_to=1942, system_code="SYS_R194A", source_code="R194A1",
                table_name="VISIT_RECORD", change_type=ctype, column_name=col,
                **{k: v for k, v in dict(old_value="X", new_value="Y", snapshot_id_from=1941).items()
                   if k in [c2.name for c2 in mmc.AssetMetadataChangeEvent.__table__.columns]}))
            n += 1
    # probe
    if not db.query(mpr.AssetProbeRun).filter_by(run_id="RUN-PROBE-R194-1").first():
        pr_cols = [c.name for c in mpr.AssetProbeRun.__table__.columns]
        db.add(mpr.AssetProbeRun(run_id="RUN-PROBE-R194-1",
                                 **{k: v for k, v in dict(status="completed", system_code="SYS_R194A",
                                                          source_code="R194A1", started_at=NOW - timedelta(days=1),
                                                          finished_at=NOW - timedelta(days=1, minutes=-5),
                                                          triggered_by="r194_admin").items()
                                    if k in pr_cols}))
        n += 1
    f_cols = [c.name for c in mpr.AssetProbeFinding.__table__.columns]
    for i, (pt, od, mn, val) in enumerate([
        ("orphan_fk", "=SUM(A1)+CMD(\"calc\")特殊字符-探查发现对象描述", "orphan_ratio", 0.12),
        ("dup_key", "重复键示例-探查发现对象描述二", "dup_ratio", 0.05),
        ("null_pk", "主键空值-探查发现对象描述三", "null_pk_ratio", 0.0),
    ]):
        kw = dict(probe_type=pt, system_pair="SYS_R194A|SYS_R194B", object_desc=od,
                  object_key_digest=hashlib.sha256(od.encode()).hexdigest()[:16],
                  metric_name=mn, metric_value=val,
                  **{k: v for k, v in dict(run_id="RUN-PROBE-R194-1", status="open",
                                           severity="high", detected_at=NOW - timedelta(days=1)).items()
                     if k in f_cols})
        if "metric_value" not in f_cols:
            kw.pop("metric_value")
        db.add(mpr.AssetProbeFinding(**kw))
        n += 1
    # lineage
    if not db.query(ml.AssetViewDependency).filter_by(view_name="V_R194_PAT").first():
        for t in ("PATIENT_INFO", "VISIT_RECORD"):
            db.add(ml.AssetViewDependency(view_name="V_R194_PAT", referenced_table=f"CLIN.{t}",
                                          **{k: v for k, v in dict(source_code="R194A1").items()
                                             if k in [c2.name for c2 in ml.AssetViewDependency.__table__.columns]}))
            db.add(ml.AssetLineageEdge(edge_key=f"LE-R194-{t}",
                                       from_object_key="view|R194A1|CLIN|V_R194_PAT",
                                       to_object_key=f"table|R194A1|CLIN|{t}",
                                       from_object_type="view", to_object_type="table",
                                       edge_type="view_dependency"))
            n += 1
    # ops
    t_cols = [c.name for c in mot.OpsToolTemplate.__table__.columns]
    if not db.query(mot.OpsToolTemplate).filter_by(tool_code="TOOL_R194_1").first():
        db.add(mot.OpsToolTemplate(
            tool_code="TOOL_R194_1", tool_name_cn="合成只读巡检模板", system_code="SYS_R194A",
            tool_type="readonly_check", input_schema={"host": "string", "port": "int"},
            execution_mode="readonly",
            **{k: v for k, v in dict(status="active", created_by="r194_admin", description="r194 合成").items()
               if k in t_cols}))
        n += 1
    r_cols = [c.name for c in mot.OpsToolRun.__table__.columns]
    for st, err in (("success", None), ("failed", "连接超时（合成）")):
        db.add(mot.OpsToolRun(tool_code="TOOL_R194_1",
                              **{k: v for k, v in dict(status=st, started_at=NOW - timedelta(hours=7),
                                                       finished_at=NOW - timedelta(hours=7, minutes=-1),
                                                       triggered_by="r194_admin", error_message=err,
                                                       output_summary="r194 合成输出").items()
                                 if k in r_cols}))
        n += 1
    # gov events + graph batch + manual scheduler job row (trigger_mode manual — safe, no cron)
    if not db.query(mo.GovernEvent).filter_by(event_type="r194_seed_event").first():
        db.add(mo.GovernEvent(event_type="r194_seed_event", module="quality",
                              **{k: v for k, v in dict(occurred_at=NOW, payload={"seed": True}).items()
                                 if k in [c2.name for c2 in mo.GovernEvent.__table__.columns]}))
        n += 1
    if not db.query(mo.SchedulerJob).filter_by(job_type="metadata_scan", source_code="R194A1", trigger_mode="manual").first():
        db.add(mo.SchedulerJob(job_type="metadata_scan", source_code="R194A1", trigger_mode="manual",
                               status="success", started_at=NOW - timedelta(days=1),
                               finished_at=NOW - timedelta(days=1, minutes=-2),
                               total_processed=10, total_changes=0))
        n += 1
    db.commit()
    return n


def main():
    url = os.environ["APP_TEST_DB_URL"]
    assert "data_asset_test" in url, "refusing to seed non-test database"
    eng = create_engine(url)
    with Session(eng) as db:
        # RBAC first (roles + permissions)
        from app.api.v1.permissions import BUILTIN_ROLES, ROLE_DEFAULT_PERMISSIONS, RESOURCE_CATALOG
        for r in BUILTIN_ROLES:
            if not db.query(mgb.AssetRole).filter_by(role_code=r["role_code"]).first():
                db.add(mgb.AssetRole(role_code=r["role_code"], role_name_cn=r["role_name_cn"],
                                     role_type=r.get("role_type") or "builtin",
                                     description=r.get("description")))
        db.flush()
        for role_code, perms in ROLE_DEFAULT_PERMISSIONS.items():
            existing = {p.resource for p in db.query(mgb.AssetRolePermission).filter_by(role_code=role_code).all()}
            for code in perms:
                if code in existing:
                    continue
                db.add(mgb.AssetRolePermission(role_code=role_code, resource=code, action="access"))  # DEF-05（194）：对齐 c307a04 seeder 修复
        for r in RESOURCE_CATALOG:
            code = r.get("code") or r.get("resource_code")
            if not code:
                continue
            if not db.query(mgb.AssetPermissionResource).filter_by(resource_code=code).first():
                db.add(mgb.AssetPermissionResource(
                    resource_code=code, resource_name_cn=r.get("name_cn") or r.get("name") or code,
                    module_code=r.get("module") or "asset",
                    action_code=r.get("action") or "read",
                    **{k: v for k, v in dict(description=r.get("description")).items()
                       if k in [c.name for c in mgb.AssetPermissionResource.__table__.columns]}))
        db.commit()
        print("[seed] rbac ok")
        for fn in (s_users, s_systems, s_tables, s_relations, s_recipes, s_vd, s_dict,
                   s_queries, s_quality, s_identity, s_ai, s_wrapup_u, s_misc):
            fn(db)
    out = os.path.join(os.path.dirname(__file__), "seed_summary.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"seeded_at": datetime.now(UTC).isoformat(), "sections": SUMMARY}, f, ensure_ascii=False, indent=1)
    bad = [k for k, v in SUMMARY.items() if not v.get("ok")]
    print("[seed] done; failed sections:", bad or "none")


if __name__ == "__main__":
    main()
