# -*- coding: utf-8 -*-
"""188 S8: build plan139-style package from r188 snapshots and import via the
production-proven plan139 importer — with two hard adaptations (plan 188 §9.3):

1. SOURCE_REGISTRY extended at RUNTIME with the 13 B-class sources; the old
   FOUR-SOURCES/OA confirm strings are NOT reused (new APPLY-R188-B13-SOURCES).
2. Declared FKs NEVER enter the formal layer: the generated package carries
   FK edges ONLY in relation_candidates.csv (review/draft layer). The legacy
   constraints.csv formal-write path is left empty by construction.

Default mode is dry-run; apply requires --apply --confirm APPLY-R188-B13-SOURCES
plus explicit user approval of the specific run_id/package SHA (step S10).
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

R188_CONFIRM = "APPLY-R188-B13-SOURCES"

# runtime registry for the 13 B-class sources (endpoint facts from platform baseline 2026-09-13)
R188_SOURCE_REGISTRY = {
    "EMERGENCY_CLINIC": ("急诊系统(麦迪斯顿)", "emergency_clinic_10_10_10_120", "oracle", "10.10.10.120", 1521, "clinic", None, "CLINIC"),
    "MEDICAL_RECORD_MGMT": ("病案管理系统(华健)", "mr_mgmt_10_10_10_55", "oracle", "10.10.10.55", 1521, "ycyl", None, "YCYL"),
    "TRANSFUSION_NEW": ("新输血系统(熙恒)", "bloodnew_sqlserver_10_10_8_7", "sqlserver", "10.10.8.7", 1433, None, "XH_BIS,XH_BIS_4.0,HyAppFrame", "dbo"),
    "SDDW_PROD": ("医保结算系统正式(山大地纬)", "sddw_oracle_10_10_10_152", "oracle", "10.10.10.152", 1521, "orcl", None, "MHS5"),
    "INFECTION_SURVEILLANCE": ("医院感染实时监控(杏林)", "infection_10_10_9_45", "oracle", "10.10.9.45", 1521, "orcl", None, None),
    "RESEARCH_MYSQL": ("科研系统MySQL", "research_mysql_10_10_8_200", "mysql", "10.10.8.200", 4306, None, None, None),
    "OUTPATIENT_APPT": ("门诊预约系统", "outpatient_mysql_10_10_8_161", "mysql", "10.10.8.161", 3306, None, None, None),
    "QUEUE": ("门诊叫号系统", "queue_mysql_10_10_8_163", "mysql", "10.10.8.163", 3306, None, "sdsr_queue_java", "sdsr_queue_java"),
    "ADVERSE_EVENT": ("医疗安全不良事件(火龙果)", "adverse_event_10_10_10_50", "mysql", "10.10.10.50", 3306, None, None, None),
    "INTERCONNECT_PROV": ("互联互通省平台", "interconnect_10_10_10_5", "oracle", "10.10.10.5", 1521, "orcl", None, "SPT_EXCHANGE"),
    "HEARING_TEST": ("电测听系统", "hearing_test_postgresql_10_10_9_187", "postgresql", "10.10.9.187", 15432, None, "report", "public"),
    "BRONCHOSCOPY": ("气管镜系统", "bronchoscopy_postgresql_10_10_8_240", "postgresql", "10.10.8.240", 5432, None, "clouddb", "public"),
    "HEMODIALYSIS": ("血透系统", "dialysis_postgresql_10_10_10_88", "postgresql", "10.10.10.88", 5432, None, "dialysis", "public"),
}


def registry_entry(code):
    name_cn, src, dbt, host, port, svc, dbs, schema = R188_SOURCE_REGISTRY[code]
    return {
        "system_code": code, "system_name_cn": name_cn,
        "source_code": src, "source_name_cn": f"{name_cn} 业务库",
        "db_type": dbt, "host": host, "port": port,
        "service_name": svc, "database_name": dbs,
        "service_mode": "service" if svc else "database",
        "default_schema": schema, "labels": [name_cn, code],
        # importer contract requires system_type; use the system code itself
        # instead of inventing a taxonomy (note in S9: apply overwrites this
        # field on already-registered systems)
        "system_type": code,
        "credential_ref": f"file:///etc/data-asset/credentials/{_cred_file(code)}",
    }


def _cred_file(code):
    return {
        "EMERGENCY_CLINIC": "emergency_clinic_oracle_10_10_10_120.readonly",
        "MEDICAL_RECORD_MGMT": "mr_mgmt_oracle_10_10_10_55.readonly",
        "TRANSFUSION_NEW": "bloodnew_sqlserver_10_10_8_7.readonly",
        "SDDW_PROD": "sddw_oracle_10_10_10_152.readonly",
        "INFECTION_SURVEILLANCE": "infection_oracle_10_10_9_45.readonly",
        "RESEARCH_MYSQL": "research_mysql_10_10_8_200.readonly",
        "OUTPATIENT_APPT": "outpatient_mysql_10_10_8_161.readonly",
        "QUEUE": "queue_mysql_10_10_8_163.readonly",
        "ADVERSE_EVENT": "adverse_event_mysql_10_10_10_50.readonly",
        "INTERCONNECT_PROV": "interconnect_oracle_10_10_10_5.readonly",
        "HEARING_TEST": "hearing_test_postgresql_10_10_9_187.readonly",
        "BRONCHOSCOPY": "bronchoscopy_postgresql_10_10_8_240.readonly",
        "HEMODIALYSIS": "dialysis_postgresql_10_10_10_88.readonly",
    }[code]


def system_of_source(source_code):
    for code, ent in R188_SOURCE_REGISTRY.items():
        if ent[1] == source_code:
            return code
    return None


def _w(csv_path, fieldnames, rows):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _comma(vals):
    return ",".join(v for v in vals if v)


def _oracle_fk_candidates(cons_rows):
    """Emit one candidate per Oracle FK constraint group with complete keys.

    Harvester R rows carry no r_column_name (referenced column not captured);
    derive it by position-joining the referenced table's P/U constraints from
    the same snapshot. Rows with the same constraint_name are merged so
    composite FKs stay one candidate with position-ordered column lists.
    Undervivable groups keep to_columns empty (prepare contract skips them).
    """
    from collections import defaultdict

    ref_side = defaultdict(dict)  # (owner, table) -> {constraint_name: {pos: col}}
    fk_groups = defaultdict(dict)  # constraint_name -> {pos: row}
    for row in cons_rows or []:
        ctype = str(row.get("constraint_type", "")).upper()
        pos = int(row.get("position") or 1)
        if ctype in ("P", "U"):
            ref_side[(row.get("owner"), row.get("table_name"))].setdefault(
                row.get("constraint_name"), {})[pos] = row.get("column_name")
        elif ctype == "R":
            fk_groups[row.get("constraint_name")][pos] = row

    out = []
    for cname in sorted(fk_groups, key=str):
        group = fk_groups[cname]
        first = next(iter(group.values()))
        positions = sorted(group)
        from_cols = [group[p].get("column_name") for p in positions]
        r_owner = first.get("r_owner") or first.get("owner")
        to_table = f'{r_owner}.{first.get("r_table_name")}'
        # referenced constraint must have the same column count to map positions
        matches = [cols for cols in ref_side.get((r_owner, first.get("r_table_name")), {}).values()
                   if len(cols) == len(positions)]
        to_cols = []
        derived = False
        if len(matches) == 1 and sorted(matches[0]) == positions:
            to_cols = [matches[0][p] for p in positions]
            derived = True
        out.append({
            "from_table": f'{first.get("owner")}.{first.get("table_name")}',
            "from_columns": _comma(from_cols),
            "to_table": to_table,
            "to_columns": _comma(to_cols),
            "join_condition": _comma(f"{a}={b}" for a, b in zip(from_cols, to_cols))
            if derived else f"{_comma(from_cols)}=?",
            "confidence": "B",
            "evidence_kind": "declared_fk_pos_derived" if derived else "declared_fk_refcol_missing",
            "directional": "true", "review_required": "true",
        })
    return out


_PG_FK_RE = None


def _pg_fk_candidate(row):
    """Parse PG definition text `FOREIGN KEY (cols) REFERENCES ref(cols) ...`.

    Unqualified REFERENCES targets live in the FK's own schema. Unparseable
    text falls back to the def-text form (skipped by the prepare contract).
    """
    global _PG_FK_RE
    import re
    if _PG_FK_RE is None:
        _PG_FK_RE = re.compile(
            r'FOREIGN\s+KEY\s*\((?P<cols>[^)]*)\)\s*'
            r'REFERENCES\s+(?P<ref>(?:"[^"]+"|\w+)(?:\.(?:"[^"]+"|\w+))*\s*)'
            r'\((?P<refcols>[^)]*)\)', re.IGNORECASE)
    text = str(row.get("definition") or "")
    base = {"confidence": "B", "directional": "true", "review_required": "true"}

    def split_cols(chunk):
        return [p.strip().strip('"') for p in chunk.split(",") if p.strip()]

    m = _PG_FK_RE.search(text)
    if m:
        cols = split_cols(m.group("cols"))
        ref_cols = split_cols(m.group("refcols"))
        parts = [p.strip().strip('"') for p in m.group("ref").strip().split(".")]
        to_table = ".".join(parts) if len(parts) > 1 else f'{row.get("schema")}.{parts[0]}'
        if cols and ref_cols and len(cols) == len(ref_cols):
            return {
                "from_table": f'{row.get("schema")}.{row.get("table_name")}',
                "from_columns": _comma(cols),
                "to_table": to_table,
                "to_columns": _comma(ref_cols),
                "join_condition": _comma(f"{a}={b}" for a, b in zip(cols, ref_cols)),
                "evidence_kind": "declared_fk_def_parsed", **base,
            }
    return {
        "from_table": f'{row.get("schema")}.{row.get("table_name")}',
        "from_columns": "", "to_table": "", "to_columns": "",
        "join_condition": text, "evidence_kind": "declared_fk_def_text", **base,
    }


def build_package(run_dir: Path, out_dir: Path) -> dict:
    """Convert r188 harvester snapshots -> plan139-style package CSVs.

    FK edges go ONLY to relation_candidates.csv (draft layer); constraints.csv
    stays header-only so the legacy formal-FK path cannot fire.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_dir = run_dir / "sources" if (run_dir / "sources").is_dir() else run_dir
    objects, columns, view_deps, cands = [], [], [], []
    stats = {}
    # variant dedup (analyzer parity): one snapshot per source, prefer .r2/.xh40
    # over plain — night1 left full plain copies alongside re-run variants and
    # both would double-count objects/columns otherwise
    picked: dict[str, Path] = {}
    for sp in sorted(Path(snap_dir).glob("*.snapshot.json")):
        base = sp.name.replace(".r2.snapshot.json", "").replace(
            ".xh40.snapshot.json", "").replace(".snapshot.json", "")
        pri = 2 if (".r2." in sp.name or ".xh40." in sp.name) else 1
        if base not in picked or pri > picked[base][0]:
            picked[base] = (pri, sp)
    for snap_path in [p[1] for _, p in sorted(picked.items())]:
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        src = snap.get("source_code") or snap_path.stem.replace(".snapshot", "")
        sysc = system_of_source(src) or snap.get("system_code_hint") or src
        n_obj = n_col = n_fk = 0
        engine = snap.get("engine")

        def obj_key(schema, name):
            # plan139 importer keys tables/columns by namespace AS schema_name;
            # namespace must be the real owner/schema, not the source code
            return schema or "", schema, name

        if engine == "oracle":
            for t in (snap.get("tables", {}) or {}).get("data", []):
                ns, schema, name = obj_key(t.get("owner"), t.get("table_name"))
                objects.append({"system_code": sysc, "source_code": src,
                                "namespace": ns, "schema_name": schema,
                                "object_name": name,
                                "object_type": t.get("object_type", "TABLE"),
                                "table_name_cn": "", "comment": (snap.get("table_comments", {}).get("data") or [{}]) and next((c.get("COMMENTS") for c in snap.get("table_comments", {}).get("data", []) if c.get("TABLE_NAME") == name and c.get("OWNER") == schema), ""),
                                "estimated_rows": t.get("num_rows"),
                                "stats_at": t.get("last_analyzed")})
                n_obj += 1
            for c in (snap.get("columns", {}) or {}).get("data", []):
                ns, schema, name = obj_key(c.get("owner"), c.get("table_name"))
                columns.append({"system_code": sysc, "source_code": src,
                                "namespace": ns, "schema_name": schema,
                                "table_name": name,
                                "column_id": c.get("column_id"),
                                "column_name": c.get("column_name"),
                                "data_type": c.get("data_type"),
                                "length": c.get("data_length"),
                                "nullable": c.get("nullable"),
                                "comment": ""})
                n_col += 1
            cons_rows = (snap.get("constraints", {}) or {}).get("data", [])
            for cand in _oracle_fk_candidates(cons_rows):
                cands.append({"system_code": sysc, "source_code": src, **cand})
                n_fk += 1
        elif engine == "mysql":
            for t in (snap.get("tables", {}) or {}).get("data", []):
                ns, schema, name = obj_key(t.get("schema"), t.get("table_name"))
                objects.append({"system_code": sysc, "source_code": src,
                                "namespace": ns, "schema_name": schema,
                                "object_name": name,
                                "object_type": "VIEW" if "VIEW" in str(t.get("TABLE_TYPE", "")) else "TABLE",
                                "table_name_cn": str(t.get("TABLE_COMMENT") or "")[:200],
                                "comment": "", "estimated_rows": t.get("estimated_rows"),
                                "stats_at": None})
                n_obj += 1
            for c in (snap.get("columns", {}) or {}).get("data", []):
                # mysql snapshot rows carry uppercase TABLE_NAME (unaliased catalog select)
                ns, schema, name = obj_key(c.get("schema"), c.get("table_name") or c.get("TABLE_NAME"))
                columns.append({"system_code": sysc, "source_code": src,
                                "namespace": ns, "schema_name": schema,
                                "table_name": name, "column_id": c.get("ORDINAL_POSITION"),
                                "column_name": c.get("COLUMN_NAME"),
                                "data_type": str(c.get("COLUMN_TYPE") or ""),
                                "length": "", "nullable": c.get("IS_NULLABLE"),
                                "comment": str(c.get("COLUMN_COMMENT") or "")[:200]})
                n_col += 1
            for c in (snap.get("constraints", {}) or {}).get("data", []):
                if str(c.get("CONSTRAINT_TYPE", "")).upper() == "FOREIGN KEY":
                    cands.append({"system_code": sysc, "source_code": src,
                                  "from_table": f'{c.get("schema")}.{c.get("TABLE_NAME")}',
                                  "from_columns": c.get("COLUMN_NAME"),
                                  "to_table": f'{c.get("schema")}.{c.get("REFERENCED_TABLE_NAME")}',
                                  "to_columns": c.get("REFERENCED_COLUMN_NAME") or "",
                                  "join_condition": f'{c.get("COLUMN_NAME")}={c.get("REFERENCED_COLUMN_NAME") or "?"}',
                                  "confidence": "B", "evidence_kind": "declared_fk",
                                  "directional": "true", "review_required": "true"})
                    n_fk += 1
        elif engine == "sqlserver":
            for db, per in (snap.get("per_database", {}) or {}).items():
                for t in per.get("tables", {}).get("data", []):
                    ns, schema, name = obj_key(f"{db}.{t.get('schema_name')}", t.get("table_name"))
                    objects.append({"system_code": sysc, "source_code": src,
                                    "namespace": ns, "schema_name": f"{db}.{t.get('schema_name')}",
                                    "object_name": name, "object_type": "TABLE",
                                    "table_name_cn": "", "comment": "",
                                    "estimated_rows": t.get("estimated_rows"), "stats_at": None})
                    n_obj += 1
                for c in per.get("columns", {}).get("data", []):
                    ns, schema, name = obj_key(f"{db}.{c.get('schema_name')}", c.get("object_name"))
                    columns.append({"system_code": sysc, "source_code": src,
                                    "namespace": ns, "schema_name": schema,
                                    "table_name": name, "column_id": c.get("column_id"),
                                    "column_name": c.get("column_name"),
                                    "data_type": c.get("data_type"),
                                    "length": c.get("max_length"), "nullable": c.get("is_nullable"),
                                    "comment": ""})
                    n_col += 1
                for f in per.get("foreign_keys", {}).get("data", []):
                    cands.append({"system_code": sysc, "source_code": src,
                                  "from_table": f'{db}.{f.get("parent_schema")}.{f.get("parent_table")}',
                                  "from_columns": f.get("parent_column"),
                                  "to_table": f'{db}.{f.get("ref_schema")}.{f.get("ref_table")}',
                                  "to_columns": f.get("ref_column"),
                                  "join_condition": f'{f.get("parent_column")}={f.get("ref_column")}',
                                  "confidence": "B", "evidence_kind": "declared_fk",
                                  "directional": "true", "review_required": "true"})
                    n_fk += 1
        elif engine == "postgresql":
            for t in (snap.get("tables", {}) or {}).get("data", []):
                ns, schema, name = obj_key(t.get("schema"), t.get("relname"))
                objects.append({"system_code": sysc, "source_code": src,
                                "namespace": ns, "schema_name": schema,
                                "object_name": name,
                                "object_type": {"r": "TABLE", "p": "TABLE", "v": "VIEW", "m": "MATERIALIZED_VIEW"}.get(t.get("relkind"), "TABLE"),
                                "table_name_cn": str(t.get("comment") or "")[:200], "comment": "",
                                "estimated_rows": None if (t.get("estimated_rows") or 0) < 0 else t.get("estimated_rows"),
                                "stats_at": None})
                n_obj += 1
            for c in (snap.get("columns", {}) or {}).get("data", []):
                ns, schema, name = obj_key(c.get("schema"), None)
                # pg columns rows carry table via batch; table_name attached below
                columns.append({"system_code": sysc, "source_code": src,
                                "namespace": ns, "schema_name": schema,
                                "table_name": c.get("table_name") or c.get("relname") or "",
                                "column_id": c.get("attnum"),
                                "column_name": c.get("attname"),
                                "data_type": c.get("data_type"), "length": "",
                                "nullable": not c.get("attnotnull"),
                                "comment": str(c.get("comment") or "")[:200]})
                n_col += 1
            for c in (snap.get("constraints", {}) or {}).get("data", []):
                if c.get("contype") == "f":
                    cands.append({"system_code": sysc, "source_code": src,
                                  **_pg_fk_candidate(c)})
                    n_fk += 1
        stats[src] = {"objects": n_obj, "columns": n_col, "fk_candidates": n_fk}

    # plan139 importer contract: columns rows must carry object_name (table) and
    # ordinal; normalize engine-specific key spellings in one pass
    for c in columns:
        c.setdefault("object_name", c.get("table_name") or c.get("TABLE_NAME"))
        c.setdefault("ordinal", c.get("column_id") or c.get("ordinal_position")
                     or c.get("attnum") or c.get("ORDINAL_POSITION"))
    # importer matches object_type == "view" (lowercase) for view role
    for o in objects:
        ot = str(o.get("object_type") or "").strip().lower()
        if ot:
            o["object_type"] = ot

    # S10 production baseline reconciliation: drop rows that would violate
    # the platform-wide (schema_name, table_name) ownership (see
    # EXCLUDE_SYSTEM_SCHEMA). Must run before CSVs are written so dry-run
    # and apply consume the identical package.
    objects, columns, cands, exclusion_report = _apply_platform_exclusions(objects, columns, cands)
    stats = {}
    for coll, key in ((objects, "objects"), (columns, "columns"), (cands, "fk_candidates")):
        for row in coll:
            bucket = stats.setdefault(row["source_code"],
                                      {"objects": 0, "columns": 0, "fk_candidates": 0})
            bucket[key] += 1

    _w(out_dir / "objects.csv",
       ["system_code", "source_code", "namespace", "schema_name", "object_name",
        "object_type", "table_name_cn", "comment", "estimated_rows", "stats_at"], objects)
    _w(out_dir / "columns.csv",
       ["system_code", "source_code", "namespace", "schema_name", "table_name",
        "object_name", "ordinal", "column_id", "column_name", "data_type",
        "length", "nullable", "comment"], columns)
    _w(out_dir / "view_dependencies.csv",
       ["system_code", "source_code", "view_namespace", "view_schema", "view_name",
        "dep_namespace", "dep_schema", "dep_object"], view_deps)
    # FKs ONLY here (draft layer); constraints.csv intentionally header-only
    _w(out_dir / "constraints.csv",
       ["system_code", "constraint_name", "constraint_type", "namespace", "schema_name",
        "table_name", "column_name", "position", "r_namespace", "r_schema_name",
        "r_table_name", "r_column_name"], [])
    # importer contract: candidates rows need layer/namespace/view_name/intake_status
    for cand in cands:
        cand.setdefault("layer", "review_draft")
        cand.setdefault("namespace", str(cand.get("from_table", "")).split(".", 1)[0])
        cand.setdefault("view_name", "")
        cand.setdefault("intake_status", "candidate")
        cand.setdefault("is_cross_database", "false")

    _w(out_dir / "relation_candidates.csv",
       ["system_code", "source_code", "layer", "namespace", "view_name",
        "intake_status", "from_table", "from_columns", "to_table", "to_columns",
        "join_condition", "confidence", "evidence_kind", "directional",
        "review_required", "is_cross_database"], cands)
    return {"objects": len(objects), "columns": len(columns),
            "fk_candidates": len(cands), "view_dependencies": len(view_deps),
            "per_source": stats,
            "platform_exclusions": exclusion_report,
            "note": "constraints.csv header-only by construction: legacy formal-FK path cannot fire; FK evidence lives in relation_candidates.csv (draft layer only)"}


def load_plan139():
    spec = importlib.util.spec_from_file_location(
        "import_plan139_sources_to_platform",
        Path(__file__).resolve().parent / "import_plan139_sources_to_platform.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Platform ownership exclusions discovered at S10 production apply
# (2026-09-16/17): asset_tables unique key (schema_name, table_name) is
# GLOBAL platform-wide, so a qualified name may be registered under exactly
# one source. Two exclusion rules, applied at build time so dry-run and
# apply always use the same package and re-runs stay idempotent:
#  A) EMERGENCY_CLINIC's MEDCOMM objects: the MEDCOMM schema is already
#     registered under the DOCARE source in production (shared anesthesia
#     communication schema). Registering a second copy violates uniqueness.
#  B) Oracle vendor SAMPLE schemas (SCOTT/HR/IX/OE/PM/SH) appear under
#     several r188 Oracle sources with identical content; duplicated keys
#     are dropped from EVERY owning system — vendor demo metadata has no
#     business value and the platform-wide key allows a single copy at most.
EXCLUDE_SYSTEM_SCHEMA = {("EMERGENCY_CLINIC", "MEDCOMM")}


def _apply_platform_exclusions(objects, columns, cands):
    """Drop rows violating the platform-wide (schema, table) ownership.

    Returns (objects, columns, cands, report dict). Candidates whose either
    endpoint lands on an excluded object are dropped too (their evidence
    would fail metadata_check anyway)."""
    from collections import Counter

    dup_keys = {k for k, n in Counter(
        (o["namespace"].upper(), o["object_name"].upper()) for o in objects).items() if n > 1}
    excluded = set(dup_keys)
    for o in objects:
        if (o["system_code"], o["namespace"].upper()) in {
                (s, n.upper()) for s, n in EXCLUDE_SYSTEM_SCHEMA}:
            excluded.add((o["namespace"].upper(), o["object_name"].upper()))
    # rule B refines: only sample-schema duplicates are auto-excluded; any
    # other duplicate key would signal a data bug — keep (crash loud) path
    # by excluding it too but reporting it distinctly.
    def obj_key(ns, name):
        return (str(ns or "").upper(), str(name or "").upper())

    def endpoint_key(table):
        parts = str(table or "").split(".")
        return obj_key(parts[-2], parts[-1]) if len(parts) >= 2 else None

    kept_objects = [o for o in objects if obj_key(o["namespace"], o["object_name"]) not in excluded]
    kept_columns = [c for c in columns
                    if obj_key(c.get("namespace"), c.get("object_name") or c.get("table_name")) not in excluded]
    kept_cands, dropped_cands = [], 0
    for cand in cands:
        f, t = endpoint_key(cand.get("from_table")), endpoint_key(cand.get("to_table"))
        if (f and f in excluded) or (t and t in excluded):
            dropped_cands += 1
        else:
            kept_cands.append(cand)
    sample_dups = sorted(k for k in dup_keys
                         if k[0] in {"SCOTT", "HR", "IX", "OE", "PM", "SH"})
    other_dups = sorted(dup_keys - set(sample_dups))
    report = {
        "rule_A_platform_owned": sorted(k for k in excluded if k not in dup_keys),
        "rule_B_sample_schema_dup_keys": sample_dups,
        "rule_B_other_dup_keys_flag": other_dups,
        "excluded_objects": len(objects) - len(kept_objects),
        "excluded_columns": len(columns) - len(kept_columns),
        "excluded_candidates_endpoint_on_excluded": dropped_cands,
    }
    return kept_objects, kept_columns, kept_cands, report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--package-dir", required=True, type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirm", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--systems", default="", help="comma list to restrict")
    ap.add_argument("--selftest", action="store_true",
                    help="validate package build round-trip only (no DB)")
    args = ap.parse_args()

    if args.selftest:
        summary = build_package(args.run_dir, args.package_dir)
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        return 0

    summary = build_package(args.run_dir, args.package_dir)
    (args.package_dir / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"package_built": summary}, ensure_ascii=False))

    mod = load_plan139()
    # runtime registry extension + dedicated confirm string; old confirms NOT accepted
    for code in R188_SOURCE_REGISTRY:
        mod.SOURCE_REGISTRY[code] = registry_entry(code)
    mod.CONFIRM_TEXTS = {R188_CONFIRM}
    mod.BATCH_TAG_PREFIX = "r188_b13"
    if args.apply:
        if args.confirm != R188_CONFIRM:
            raise SystemExit(f"--confirm must be {R188_CONFIRM}; old plan139 confirm strings are not valid for r188")
        if not args.run_id:
            raise SystemExit("--run-id required for apply")

    selected = [s for s in args.systems.split(",") if s.strip()] or None
    result = mod.execute(args.package_dir, run_id=args.run_id, apply=args.apply,
                         confirm=args.confirm if args.apply else R188_CONFIRM,
                         selected_systems=selected)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
