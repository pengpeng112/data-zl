"""188 low-load read-only metadata harvester (Oracle/MySQL/SQLServer/PostgreSQL).

Adapted per plan 188 v2.0 §3/§4/S3/S5:
- read-only session protections per engine (no universal switch claim for SQLServer)
- batched metadata queries (<=50 objects per batch, row cap with subdivide-once)
- throttle 2s between statements, 60s pause every 50 statements
- per-source budget: max statements / DB seconds / wall seconds (checkpointed)
- circuit breaker: timeout, lock wait, memory error, unknown cancel -> stop source
- definitions fetched per object, truncated at 256 KiB, sanitized
- estimated rows + space from existing catalog statistics only (no COUNT/ANALYZE)
- per-source checkpoint saved atomically after each stage shard

Credentials: only from a credential file path (user:password or JSON) or env.
Never passed on the command line, never written to outputs/logs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULTS = {
    "batch_objects": 50,          # objects per metadata batch (plan: <=100)
    "row_cap": 2000,              # rows per metadata query (plan: <=2000)
    "statement_timeout_ms": 15000,  # hard statement cap; target 5s, circuit at this
    "throttle_seconds": 2.0,
    "pause_every": 50,
    "pause_seconds": 60.0,
    "max_statements_per_source": 500,   # plan: <=500 SQL per source per night
    "max_db_seconds_per_source": 600.0,  # plan: <=10 min DB execution
    "max_wall_seconds_per_source": 2700.0,  # plan: <=45 min wall
    "definition_max_bytes": 262144,      # 256 KiB per object definition
    "max_space_objects": 400,            # per-table space probes per source per night
    "max_definitions": 200,              # view/routine definitions per source per night
}

PW_PATTERNS = [
    (re.compile(r"(IDENTIFIED\s+BY\s+)(?:VALUES\s+)?[^\s,;)]+", re.I), r"\1***"),
    (re.compile(r"(PASSWORD\s*=\s*)'[^']*'", re.I), r"\1'***'"),
    (re.compile(r"(jdbc:[a-z0-9]+://[^\s\"']*?[:/])[^\s\"'@]*@", re.I), r"\1***@"),
]


def sanitize_definition(text: str | None, max_bytes: int) -> dict:
    if text is None:
        return {"text": None, "truncated": False}
    out = str(text)
    for pat, rep in PW_PATTERNS:
        out = pat.sub(rep, out)
    raw = out.encode("utf-8", errors="replace")
    truncated = len(raw) > max_bytes
    if truncated:
        keep = max_bytes - 3
        out = raw[:keep].decode("utf-8", errors="ignore") + "..."
    return {"text": out, "truncated": truncated}


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def sql_fingerprint(sql: str) -> str:
    norm = re.sub(r"\s+", " ", sql or "").strip().lower()
    return hashlib.sha256(norm.encode("utf-8", errors="replace")).hexdigest()[:16]


class BudgetExceeded(Exception):
    pass


class CircuitBreak(Exception):
    pass


class Budget:
    def __init__(self, cfg, log):
        self.cfg = {**DEFAULTS, **(cfg.get("budget", {}) or {})}
        self.statements = 0
        self.db_seconds = 0.0
        self.started = time.monotonic()
        self.since_pause = 0
        self.log = log
        self.stopped_reason = None

    def pre(self, label):
        if self.stopped_reason:
            raise BudgetExceeded(self.stopped_reason)
        if self.statements >= self.cfg["max_statements_per_source"]:
            self.stopped_reason = "max_statements"
            raise BudgetExceeded(self.stopped_reason)
        if self.db_seconds >= self.cfg["max_db_seconds_per_source"]:
            self.stopped_reason = "max_db_seconds"
            raise BudgetExceeded(self.stopped_reason)
        if time.monotonic() - self.started >= self.cfg["max_wall_seconds_per_source"]:
            self.stopped_reason = "max_wall_seconds"
            raise BudgetExceeded(self.stopped_reason)
        time.sleep(self.cfg["throttle_seconds"])
        if self.since_pause and self.since_pause % self.cfg["pause_every"] == 0:
            self.log({"event": "pause", "after": self.since_pause,
                      "seconds": self.cfg["pause_seconds"]})
            time.sleep(self.cfg["pause_seconds"])

    def post(self, label, sql, seconds, rows=None, error=None):
        self.statements += 1
        self.since_pause += 1
        self.db_seconds += seconds
        self.log({
            "event": "sql", "label": label, "fingerprint": sql_fingerprint(sql),
            "seconds": round(seconds, 3), "rows": rows, "error": error,
            "seq": self.statements, "db_seconds_total": round(self.db_seconds, 1),
        })


class BaseEngine:
    name = "base"

    def __init__(self, cfg, budget: Budget, log):
        self.cfg = cfg
        self.b = budget
        self.log = log

    def connect(self):
        raise NotImplementedError

    def execute(self, label, sql, params=None):
        """Run one guarded statement; returns (rows, seconds). Raises CircuitBreak on timeout/mem errors."""
        self.b.pre(label)
        t0 = time.monotonic()
        rows = None
        err = None
        try:
            rows = self._exec(sql, params)
            return rows, time.monotonic() - t0
        except CircuitBreak:
            err = "circuit"
            raise
        except BudgetExceeded:
            err = "budget"
            raise
        finally:
            if err != "budget":
                self.b.post(label, sql, time.monotonic() - t0,
                            rows=len(rows) if rows is not None else None, error=err)


class OracleEngine(BaseEngine):
    name = "oracle"

    def connect(self):
        import oracledb
        lib = os.environ.get("APP_ORACLE_CLIENT_LIB_DIR", "/opt/oracle")
        if os.path.isdir(lib):
            try:
                oracledb.init_oracle_client(lib_dir=lib)
            except Exception as exc:
                if "already" not in str(exc).lower():
                    raise
        cred = self.cfg["credentials"]
        self.conn = oracledb.connect(user=cred["user"], password=cred["password"],
                                     dsn=self.cfg["dsn"], tcp_connect_timeout=10)
        self.conn.call_timeout = int(self.cfg["budget"].get(
            "statement_timeout_ms", DEFAULTS["statement_timeout_ms"]))
        self.cur = self.conn.cursor()
        # read-only session-level transaction (verified path per 159 precedent)
        self.cur.execute("SET TRANSACTION READ ONLY")

    CIRCUIT_MARKERS = ("ORA-04030", "ORA-00060", "ORA-30005", "DPI-1080", "DPI-1019")

    def _exec(self, sql, params):
        try:
            self.cur.execute(sql, params or {})
            names = [d[0].lower() for d in self.cur.description] if self.cur.description else []
            data = self.cur.fetchall()
            return [dict(zip(names, r)) for r in data]
        except Exception as exc:
            msg = str(exc)
            if any(m in msg for m in self.CIRCUIT_MARKERS) or "timed out" in msg.lower():
                raise CircuitBreak(f"oracle:{msg[:200]}")
            raise

    def close(self):
        try:
            self.conn.rollback()
            self.conn.close()
        except Exception:
            pass


class MySQLEngine(BaseEngine):
    name = "mysql"

    def connect(self):
        import pymysql
        cred = self.cfg["credentials"]
        self.conn = pymysql.connect(host=self.cfg["host"], port=int(self.cfg["port"]),
                                    user=cred["user"], password=cred["password"],
                                    charset="utf8mb4", use_unicode=False,
                                    connect_timeout=5,
                                    ssl_disabled=bool(self.cfg.get("mysql_ssl_disabled")),
                                    read_timeout=int(self.cfg["budget"].get(
                                        "statement_timeout_ms", DEFAULTS["statement_timeout_ms"]) / 1000) + 5,
                                    write_timeout=5, cursorclass=pymysql.cursors.DictCursor)
        self.cur = self.conn.cursor()
        self.cur.execute("SET SESSION TRANSACTION READ ONLY")

    @staticmethod
    def _decode_cell(v):
        """pymysql with use_unicode=False returns raw bytes for text columns;
        catalog data on mixed-charset servers may be gbk/latin1-mislabeled,
        so decode utf-8 first, then gbk, else replace (counted as fallback)."""
        if not isinstance(v, (bytes, bytearray)):
            return v, False
        raw = bytes(v)
        for enc in ("utf-8", "gbk"):
            try:
                return raw.decode(enc), False
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace"), True

    def _exec(self, sql, params=None):
        try:
            # params=None must stay None: an empty tuple would make psycopg run
            # placeholder validation and reject literal '%' (e.g. NOT LIKE 'pg_toast%')
            if params:
                self.cur.execute(sql, params)
            else:
                self.cur.execute(sql)
            if self.cur.description is None:
                return []
            fb = 0
            out = []
            for row in self.cur.fetchall():
                dec = {}
                for k, v in row.items():
                    dk, _ = self._decode_cell(k)
                    dv, fell = self._decode_cell(v)
                    fb += int(fell)
                    dec[dk if isinstance(dk, str) else str(dk)] = dv
                out.append(dec)
            if fb:
                self.log({"event": "decode_fallback", "count": fb})
            return out
        except Exception as exc:
            msg = str(exc)
            if "lost connection" in msg.lower() or "timeout" in msg.lower():
                raise CircuitBreak(f"mysql:{msg[:200]}")
            raise

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


class SQLServerEngine(BaseEngine):
    name = "sqlserver"

    def connect(self):
        cred = self.cfg["credentials"]
        self._mod = None
        try:
            import pymssql  # container has pymssql fallback
            self._mod = "pymssql"
            self.conn = pymssql.connect(server=self.cfg["host"], port=str(self.cfg["port"]),
                                        user=cred["user"], password=cred["password"],
                                        database=self.cfg.get("database") or "master",
                                        login_timeout=5, timeout=int(self.cfg["budget"].get(
                                            "statement_timeout_ms", DEFAULTS["statement_timeout_ms"]) / 1000))
            self.cur = self.conn.cursor(as_dict=True)
        except ImportError:
            import pyodbc
            self._mod = "pyodbc"
            cs = (f"DRIVER={{SQL Server}};SERVER={self.cfg['host']},{self.cfg['port']};"
                  f"DATABASE={self.cfg.get('database') or 'master'};UID={cred['user']};"
                  f"PWD={cred['password']}")
            self.conn = pyodbc.connect(cs, timeout=5)
            self.cur = self.conn.cursor()
        # No universal read-only switch on SQLServer: lock timeout + metadata-only scope.
        self.cur.execute("SET LOCK_TIMEOUT %d" % int(self.cfg["budget"].get(
            "lock_timeout_ms", 1000)))

    def _exec(self, sql, params=None):
        try:
            self.cur.execute(sql, params or ())
            if self.cur.description is None:
                return []
            if self._mod == "pymssql":
                return list(self.cur.fetchall())
            cols = [d[0] for d in self.cur.description]
            return [dict(zip(cols, tuple(r))) for r in self.cur.fetchall()]
        except Exception as exc:
            msg = str(exc)
            if "timeout" in msg.lower() or "canceled" in msg.lower():
                raise CircuitBreak(f"sqlserver:{msg[:200]}")
            raise

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


class PGEngine(BaseEngine):
    name = "postgresql"

    def connect(self):
        import psycopg
        import psycopg.rows
        cred = self.cfg["credentials"]
        self.conn = psycopg.connect(host=self.cfg["host"], port=int(self.cfg["port"]),
                                    dbname=self.cfg.get("database") or "postgres",
                                    user=cred["user"], password=cred["password"],
                                    connect_timeout=5)
        self.conn.autocommit = True
        self.cur = self.conn.cursor(row_factory=psycopg.rows.dict_row)
        # SET does not accept bind parameters on PG-compatible engines
        # (HuaChainSQL rejects "$1"); literal int from our own config is safe.
        to_ms = int(self.cfg["budget"].get(
            "statement_timeout_ms", DEFAULTS["statement_timeout_ms"]))
        self._try_set(f"SET statement_timeout = {to_ms}", "statement_timeout")
        self._try_set("SET default_transaction_read_only = on",
                      "default_transaction_read_only")
        self._try_set("SET idle_in_transaction_session_timeout = '30s'",
                      "idle_in_transaction_session_timeout")

    def _try_set(self, sql, setting):
        try:
            self.cur.execute(sql)
        except Exception as exc:
            # dialect gap: record and continue (budget/wall guards still apply)
            self.log({"event": "dialect_error", "where": "session_init",
                      "setting": setting,
                      "error": f"{type(exc).__name__}:{str(exc)[:200]}"})
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _exec(self, sql, params=None):
        try:
            # params=None must stay None: an empty tuple would make psycopg run
            # placeholder validation and reject literal '%' (e.g. NOT LIKE 'pg_toast%')
            if params:
                self.cur.execute(sql, params)
            else:
                self.cur.execute(sql)
            if self.cur.description is None:
                return []
            # PG-compatible engines (Vastbase) fold unquoted column labels to
            # UPPER case while native PG folds to lower; normalize so stage
            # code can index lowercase keys on both (no-op on native PG).
            return [{k.lower(): v for k, v in r.items()}
                    for r in self.cur.fetchall()]
        except Exception as exc:
            msg = str(exc)
            if "canceling statement" in msg or "timeout" in msg.lower():
                raise CircuitBreak(f"pg:{msg[:200]}")
            raise

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


ENGINES = {"oracle": OracleEngine, "mysql": MySQLEngine,
           "sqlserver": SQLServerEngine, "postgresql": PGEngine}


def read_credential_file(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8").strip()
    if text.startswith("{"):
        d = json.loads(text)
        return {"user": str(d.get("user") or d.get("username")),
                "password": str(d.get("password"))}
    if ":" in text and "\n" not in text:
        u, p = text.split(":", 1)
        return {"user": u.strip(), "password": p.strip()}
    raise ValueError("unsupported credential file format")


# ---------------- stage implementations (shared, engine-specific SQL) --------------

ORACLE_SYSTEM_OWNERS_SKIP = {
    "SYS", "SYSTEM", "XDB", "OUTLN", "DBSNMP", "APPQOSSYS", "WMSYS", "EXFSYS",
    "ORDPLUGINS", "SI_INFORMTN_SCHEMA", "ANONYMOUS", "XS$NULL", "GSMADMIN_INTERNAL",
    "LBACSYS", "DVSYS", "DVF", "AUDSYS", "OJVMSYS", "DBSFWUSER", "MGMT_VIEW",
    "SYSMAN", "OWBSYS", "OWBSYS_AUDIT", "FLOWS_FILES", "APEX_PUBLIC_USER",
    "MDSYS", "OLAPSYS", "ORDDATA", "ORDSYS", "CTXSYS", "MDDATA",
    "ORACLE_OCM",  # R4 finding: auxiliary owner recorded as observation item
}
ORACLE_SYSTEM_OWNER_PREFIXES_SKIP = ("SPATIAL_", "APEX_", "FLOWS_")


def _flush_partial(out, **named_lists):
    """Progressive flush: mirror accumulated stage lists into the snapshot dict
    at each per-owner/schema checkpoint so a budget/circuit stop mid-stage keeps
    every completed unit (r205 fix for lost partial structure on big sources).

    208B (205 R07) patch: REPLACE-by-key. The stage lists passed in are already
    cumulative within a round, and resume rounds rehydrate them from the prior
    snapshot (v8), so replacing keeps prior data without re-appending it. The
    previous ACCUMULATIVE merge appended the full cumulative list on every
    per-owner flush, duplicating each row ~N-owners times (his_source evidence:
    295,568 table rows / 4,775 unique = 112x). Products-level _dedupe preserved
    correctness; this patch removes the snapshot bloat at the source.
    Offline case matrix (first-collect / repeated flush / crash-resume):
    _scratch/r205_flush_repro_208B.py."""
    for key, val in named_lists.items():
        out[key] = {"provenance": "progressive flush per completed unit (replace-by-key, cumulative list)",
                    "data": list(val), "collected_at": now()}


def stage_oracle(eng, cfg, out, ckpt):
    q = eng.execute
    # identity (CON_NAME is 12c+ only -> separate optional probe for 11g compat)
    ident, _ = q("identity", """
        SELECT SYS_CONTEXT('USERENV','DB_NAME') db_name,
               SYS_CONTEXT('USERENV','SERVER_HOST') server_host,
               SYS_CONTEXT('USERENV','INSTANCE_NAME') instance_name,
               SYS_CONTEXT('USERENV','SERVICE_NAME') service_name,
               SYS_CONTEXT('USERENV','CURRENT_SCHEMA') current_schema,
               (SELECT version FROM product_component_version
                 WHERE product LIKE 'Oracle Database%') db_version
          FROM DUAL""")
    con_probe_err = None
    try:
        con_rows, _ = q("identity_con_name",
                        "SELECT SYS_CONTEXT('USERENV','CON_NAME') con_name FROM DUAL")
        ident[0]["con_name"] = con_rows[0]["con_name"] if con_rows else None
    except Exception as exc:  # 11g: ORA-02003 invalid USERENV parameter
        con_probe_err = str(exc)[:120]
        ident[0]["con_name"] = None
    out["identity"] = {"provenance": "oracle sys_context", "data": ident,
                       "collected_at": now(), "partial": False,
                       "con_name_probe_error": con_probe_err}
    ckpt["stages_done"].append("identity")

    # owners: visible non-system owners (oracle_maintained is 12c+; fall back on 11g)
    try:
        owner_rows, _ = q("owners", """
            SELECT username FROM all_users
             WHERE oracle_maintained = 'N' ORDER BY username""")
        owners_source = "all_users(oracle_maintained=N)"
    except Exception:
        owner_rows, _ = q("owners_fallback", "SELECT username FROM all_users ORDER BY username")
        owners_source = "all_users(no oracle_maintained, 11g)"
    owners = [r["username"] for r in owner_rows]
    out["owners"] = {"provenance": owners_source,
                     "data": owners, "collected_at": now()}
    ckpt["stages_done"].append("owners")

    # 12c container note: if con_name != db_name we are inside a PDB already
    con_name = (ident[0] or {}).get("con_name")
    out["container_note"] = {
        "con_name": con_name,
        "note": "no ALTER SESSION set_container executed; login service defines container",
    }

    owners_wanted = cfg.get("owners") or [
        o for o in owners
        if o.upper() not in ORACLE_SYSTEM_OWNERS_SKIP
        and not o.upper().startswith(ORACLE_SYSTEM_OWNER_PREFIXES_SKIP)]
    out["owners_harvested"] = owners_wanted

    tables, columns, constraints, indexes = [], [], [], []
    owner_errors = []
    for owner in owners_wanted:
      if f"struct:{owner}" in ckpt.get("stages_done", []):
          continue  # r205 resume: owner fully collected in a previous round
      try:
        obj_rows, _ = q("objects", """
            SELECT t.OWNER, t.TABLE_NAME, t.NUM_ROWS, t.LAST_ANALYZED, t.PARTITIONED,
                   (SELECT COUNT(*) FROM ALL_TAB_PARTITIONS p
                     WHERE p.TABLE_OWNER=t.OWNER AND p.TABLE_NAME=t.TABLE_NAME) partition_count
              FROM ALL_TABLES t WHERE t.OWNER = :o ORDER BY t.TABLE_NAME""", {"o": owner})
        view_rows, _ = q("objects_views", """
            SELECT v.OWNER, v.VIEW_NAME TABLE_NAME FROM ALL_VIEWS v
             WHERE v.OWNER = :o ORDER BY v.VIEW_NAME""", {"o": owner})
        names = [r["table_name"] for r in obj_rows]
        tables.extend([{"owner": owner, "object_type": "TABLE", **r} for r in obj_rows])
        tables.extend([{"owner": owner, "object_type": "VIEW", "table_name": r["table_name"],
                        "num_rows": None, "last_analyzed": None} for r in view_rows])
        for batch in chunks(names, eng.b.cfg["batch_objects"]):
            binds = {f"t{i}": n for i, n in enumerate(batch)}
            inlist = ",".join(f":{k}" for k in binds)
            cols, _ = q("columns", f"""
                SELECT c.OWNER, c.TABLE_NAME, c.COLUMN_ID, c.COLUMN_NAME, c.DATA_TYPE,
                       c.DATA_LENGTH, c.DATA_PRECISION, c.DATA_SCALE, c.NULLABLE
                  FROM ALL_TAB_COLUMNS c
                 WHERE c.OWNER = :o AND c.TABLE_NAME IN ({inlist})
                 ORDER BY c.TABLE_NAME, c.COLUMN_ID""", {"o": owner, **binds})
            columns.extend(cols)
            cons, _ = q("constraints", f"""
                SELECT ac.OWNER, ac.CONSTRAINT_NAME, ac.CONSTRAINT_TYPE, ac.TABLE_NAME,
                       acc.COLUMN_NAME, acc.POSITION, ac.R_OWNER, ac.STATUS,
                       rc.TABLE_NAME R_TABLE_NAME, rcc.COLUMN_NAME R_COLUMN_NAME
                  FROM ALL_CONSTRAINTS ac
                  JOIN ALL_CONS_COLUMNS acc
                    ON acc.OWNER=ac.OWNER AND acc.CONSTRAINT_NAME=ac.CONSTRAINT_NAME
                  LEFT JOIN ALL_CONSTRAINTS rc
                    ON rc.OWNER=ac.R_OWNER AND rc.CONSTRAINT_NAME=ac.R_CONSTRAINT_NAME
                  LEFT JOIN ALL_CONS_COLUMNS rcc
                    ON rcc.OWNER=rc.OWNER AND rcc.CONSTRAINT_NAME=rc.R_CONSTRAINT_NAME
                   AND rcc.POSITION=acc.POSITION
                 WHERE ac.OWNER = :o AND ac.TABLE_NAME IN ({inlist})
                   AND ac.CONSTRAINT_TYPE IN ('P','U','R')
                 ORDER BY ac.TABLE_NAME, ac.CONSTRAINT_NAME, acc.POSITION""", {"o": owner, **binds})
            constraints.extend(cons)
            idx, _ = q("indexes", f"""
                SELECT i.TABLE_OWNER owner, i.TABLE_NAME, i.INDEX_NAME, i.UNIQUENESS,
                       c.COLUMN_NAME, c.COLUMN_POSITION
                  FROM ALL_INDEXES i JOIN ALL_IND_COLUMNS c
                    ON c.INDEX_OWNER=i.OWNER AND c.INDEX_NAME=i.INDEX_NAME
                   AND c.TABLE_OWNER=i.TABLE_OWNER AND c.TABLE_NAME=i.TABLE_NAME
                 WHERE i.TABLE_OWNER = :o AND i.TABLE_NAME IN ({inlist})
                 ORDER BY i.TABLE_NAME, i.INDEX_NAME, c.COLUMN_POSITION""", {"o": owner, **binds})
            indexes.extend(idx)
        ckpt["stages_done"].append(f"struct:{owner}")
        save_ckpt(ckpt)
        _flush_partial(out, tables=tables, columns=columns,
                       constraints=constraints, indexes=indexes)
      except CircuitBreak:
          raise
      except BudgetExceeded:
          ckpt["stages_done"].append(f"struct_partial:{owner}")
          raise
      except Exception as exc:
          owner_errors.append({"owner": owner, "error": str(exc)[:120]})
          ckpt["stages_done"].append(f"struct_error:{owner}")
    out["owner_struct_errors"] = owner_errors

    def _final(key, prov, data):
        prev = out.get(key)
        prev_rows = prev.get("data") if isinstance(prev, dict) else []
        out[key] = {"provenance": prov, "data": list(prev_rows or []) + data,
                    "collected_at": now()}
    _final("tables", "ALL_TABLES/ALL_VIEWS+partition_count", tables)
    _final("columns", "ALL_TAB_COLUMNS batched", columns)
    _final("constraints", "ALL_CONSTRAINTS P/U/R composite order", constraints)
    _final("indexes", "ALL_INDEXES/ALL_IND_COLUMNS composite order", indexes)

    # comments (batched by owner; separate small query)
    comments = []
    comments_error = None
    for owner in owners_wanted:
        try:
            tc, _ = q("table_comments", """
                SELECT OWNER, TABLE_NAME, COMMENTS FROM ALL_TAB_COMMENTS
                 WHERE OWNER = :o AND COMMENTS IS NOT NULL""", {"o": owner})
            comments.extend(tc)
        except (CircuitBreak, BudgetExceeded):
            raise
        except Exception as exc:
            comments_error = str(exc)[:120]
            break
    out["table_comments"] = {"provenance": "ALL_TAB_COMMENTS", "data": comments,
                             "error": comments_error, "collected_at": now()}

    # view definitions one by one (per plan: definition per object)
    defs = []
    view_objs = [t for t in tables if t["object_type"] == "VIEW"]
    cap = eng.b.cfg["max_definitions"]
    for v in view_objs[:cap]:
        d, _ = q("view_def", """
            SELECT TEXT FROM ALL_VIEWS WHERE OWNER=:o AND VIEW_NAME=:v""",
                 {"o": v["owner"], "v": v["table_name"]})
        raw = d[0]["text"] if d else None
        s = sanitize_definition(raw, eng.b.cfg["definition_max_bytes"])
        defs.append({"owner": v["owner"], "object_name": v["table_name"], "kind": "VIEW",
                     "definition": s["text"], "truncated": s["truncated"]})
    out["view_definitions"] = {
        "provenance": "ALL_VIEWS.TEXT per-object", "collected_at": now(),
        "count_total_views": len(view_objs), "count_fetched": len(defs),
        "capped_reason": "max_definitions" if len(view_objs) > cap else None,
        "data": defs,
    }

    # capacity: existing statistics only
    cap_rows = []
    cap_provenance = "ALL_SEGMENTS aggregated per segment (partition children summed; table+index+lob separate)"
    cap_error = None
    for owner in owners_wanted:
        try:
            seg, _ = q("capacity_segments", """
                SELECT OWNER, SEGMENT_TYPE, SEGMENT_NAME,
                       SUM(BYTES) bytes_sum, COUNT(*) segment_count
                  FROM ALL_SEGMENTS WHERE OWNER = :o
                 GROUP BY OWNER, SEGMENT_TYPE, SEGMENT_NAME""",
                       {"o": owner})
            cap_rows.extend(seg)
        except CircuitBreak:
            raise
        except BudgetExceeded:
            raise
        except Exception as exc:  # e.g. ORA-00942: app account cannot see ALL_SEGMENTS
            if owner == owners_wanted[0]:
                cap_error = f"ALL_SEGMENTS:{str(exc)[:100]}"
                break
            cap_rows.append({"owner": owner, "error": str(exc)[:100]})
    if cap_error:
        # fallback: own-schema segment stats only (USER_SEGMENTS always visible)
        try:
            seg, _ = q("capacity_user_segments", """
                SELECT USER owner, SEGMENT_TYPE, SEGMENT_NAME,
                       SUM(BYTES) bytes_sum, COUNT(*) segment_count
                  FROM USER_SEGMENTS
                 GROUP BY SEGMENT_TYPE, SEGMENT_NAME""")
            cap_rows.extend(seg)
            cap_provenance = ("USER_SEGMENTS fallback (login schema only; "
                              "ALL_SEGMENTS not visible to app account)")
        except Exception as exc2:
            cap_error += f" | USER_SEGMENTS fallback also failed:{str(exc2)[:80]}"
    out["capacity"] = {
        "provenance": cap_provenance,
        "method": "allocated bytes from segment stats; RAC counted once per segment",
        "error": cap_error,
        "collected_at": now(),
        "data": cap_rows,
    }


def stage_mysql(eng, cfg, out, ckpt):
    q = eng.execute
    ver, _ = q("identity", "SELECT VERSION() version, @@hostname hostname")
    dbs, _ = q("schemas", "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME")
    schemas = [r["SCHEMA_NAME"] for r in dbs]
    skip = {"information_schema", "mysql", "performance_schema", "sys", "test"}
    wanted = cfg.get("schemas") or [s for s in schemas if s not in skip]
    out["identity"] = {"provenance": "VERSION()/@@hostname", "data": ver, "collected_at": now()}
    out["schemas_all"] = schemas
    out["schemas_harvested"] = wanted

    tables, columns, constraints, indexes, defs = [], [], [], [], []
    for schema in wanted:
        if f"struct:{schema}" in ckpt.get("stages_done", []):
            continue  # r205 resume: schema fully collected in a previous round
        t_rows, _ = q("tables", """
            SELECT TABLE_NAME table_name, TABLE_TYPE, ENGINE, TABLE_ROWS estimated_rows,
                   DATA_LENGTH, INDEX_LENGTH, DATA_FREE, TABLE_COMMENT,
                   CREATE_TIME, UPDATE_TIME
              FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s
             ORDER BY TABLE_NAME""", (schema,))
        tables.extend([{"schema": schema, **r} for r in t_rows])
        names = [r["table_name"] for r in t_rows if r["TABLE_TYPE"] == "BASE TABLE"]
        for batch in chunks(names, DEFAULTS["batch_objects"]):
            ph = ",".join(["%s"] * len(batch))
            cols, _ = q("columns", f"""
                SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
                       COLUMN_KEY, EXTRA, COLUMN_COMMENT, COLUMN_DEFAULT
                  FROM information_schema.COLUMNS
                 WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({ph})
                 ORDER BY TABLE_NAME, ORDINAL_POSITION""", (schema, *batch))
            columns.extend([{"schema": schema, **r} for r in cols])
            cons, _ = q("constraints", f"""
                SELECT tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE, ku.TABLE_NAME,
                       ku.COLUMN_NAME, ku.ORDINAL_POSITION,
                       ku.REFERENCED_TABLE_NAME, ku.REFERENCED_COLUMN_NAME
                  FROM information_schema.TABLE_CONSTRAINTS tc
                  JOIN information_schema.KEY_COLUMN_USAGE ku
                    ON ku.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA
                   AND ku.CONSTRAINT_NAME=tc.CONSTRAINT_NAME
                 WHERE tc.CONSTRAINT_SCHEMA = %s AND ku.TABLE_NAME IN ({ph})
                 ORDER BY ku.TABLE_NAME, tc.CONSTRAINT_NAME, ku.ORDINAL_POSITION""",
                          (schema, *batch))
            constraints.extend([{"schema": schema, **r} for r in cons])
            idx, _ = q("indexes", f"""
                SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME
                  FROM information_schema.STATISTICS
                 WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({ph})
                 ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX""", (schema, *batch))
            indexes.extend([{"schema": schema, **r} for r in idx])
        # capacity comes with information_schema.TABLES (DATA_LENGTH/INDEX_LENGTH)
        ckpt["stages_done"].append(f"struct:{schema}")
        save_ckpt(ckpt)
        _flush_partial(out, tables=tables, columns=columns,
                       constraints=constraints, indexes=indexes)

    out["tables"] = {"provenance": "information_schema.TABLES (TABLE_ROWS estimated)",
                     "data": tables, "collected_at": now()}
    out["columns"] = {"provenance": "information_schema.COLUMNS batched", "data": columns,
                      "collected_at": now()}
    out["constraints"] = {"provenance": "TABLE_CONSTRAINTS+KEY_COLUMN_USAGE composite",
                          "data": constraints, "collected_at": now()}
    out["indexes"] = {"provenance": "information_schema.STATISTICS composite", "data": indexes,
                      "collected_at": now()}
    out["capacity"] = {
        "provenance": "information_schema.TABLES DATA_LENGTH/INDEX_LENGTH (allocated, per engine)",
        "caveats": "DATA_FREE may be shared space, not summed per table",
        "collected_at": now(),
        "data": [{"schema": t["schema"], "table_name": t["table_name"],
                  "data_length": t.get("DATA_LENGTH"), "index_length": t.get("INDEX_LENGTH"),
                  "data_free": t.get("DATA_FREE")} for t in tables],
    }
    # view definitions (information_schema.VIEWS)
    for schema in wanted:
        v, _ = q("views", """
            SELECT TABLE_NAME, VIEW_DEFINITION FROM information_schema.VIEWS
             WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME""", (schema,))
        for r in v[:eng.b.cfg["max_definitions"]]:
            s = sanitize_definition(r["VIEW_DEFINITION"], eng.b.cfg["definition_max_bytes"])
            defs.append({"schema": schema, "object_name": r["TABLE_NAME"], "kind": "VIEW",
                         "definition": s["text"], "truncated": s["truncated"]})
    out["view_definitions"] = {"provenance": "information_schema.VIEWS", "data": defs,
                               "collected_at": now()}


def stage_sqlserver(eng, cfg, out, ckpt):
    q = eng.execute
    ident, _ = q("identity", "SELECT @@SERVERNAME server_name, @@VERSION version")
    dbs, _ = q("databases", """
        SELECT name FROM sys.databases
         WHERE state_desc = 'ONLINE' AND database_id > 4 ORDER BY name""")
    all_dbs = [r["name"] for r in dbs]
    wanted = cfg.get("databases") or all_dbs
    out["identity"] = {"provenance": "@@SERVERNAME/@@VERSION", "data": ident, "collected_at": now()}
    out["databases_online"] = all_dbs
    out["databases_harvested"] = wanted

    for db in wanted:
        if f"db:{db}" in ckpt.get("stages_done", []):
            continue  # r205 resume: database fully collected in a previous round
        eng.cur.execute(f"USE [{db.replace(']', ']]')}]")
        tables, _ = q("tables", """
            SELECT s.name schema_name, t.name table_name,
                   CAST(SUM(CASE WHEN p.index_id IN (0,1) THEN p.rows ELSE 0 END) AS bigint) estimated_rows
              FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
              LEFT JOIN sys.partitions p ON p.object_id=t.object_id
             WHERE t.is_ms_shipped=0 GROUP BY s.name, t.name ORDER BY s.name, t.name""")
        columns, _ = q("columns", """
            SELECT s.name schema_name, o.name object_name, o.type_desc object_type,
                   c.column_id, c.name column_name, ty.name data_type, c.max_length,
                   c.precision, c.scale, c.is_nullable, c.is_identity, c.is_computed
              FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id
              JOIN sys.columns c ON c.object_id=o.object_id
              JOIN sys.types ty ON ty.user_type_id=c.user_type_id
             WHERE o.type IN ('U','V') ORDER BY o.name, c.column_id""")
        cons, _ = q("constraints", """
            SELECT s.name schema_name, t.name table_name, k.name constraint_name,
                   k.type_desc constraint_type, ic.key_ordinal, c.name column_name
              FROM sys.key_constraints k JOIN sys.tables t ON t.object_id=k.parent_object_id
              JOIN sys.schemas s ON s.schema_id=t.schema_id
              JOIN sys.index_columns ic ON ic.object_id=t.object_id AND ic.index_id=k.unique_index_id
              JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=ic.column_id
             ORDER BY t.name, k.name, ic.key_ordinal""")
        fks, _ = q("foreign_keys", """
            SELECT cs.name parent_schema, ct.name parent_table, cc.name parent_column,
                   ps.name ref_schema, pt.name ref_table, pc.name ref_column,
                   fkc.constraint_column_id ordinal, fk.name constraint_name,
                   fk.is_disabled, fk.is_not_trusted
              FROM sys.foreign_keys fk
              JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id
              JOIN sys.tables ct ON ct.object_id=fk.parent_object_id
              JOIN sys.schemas cs ON cs.schema_id=ct.schema_id
              JOIN sys.columns cc ON cc.object_id=ct.object_id AND cc.column_id=fkc.parent_column_id
              JOIN sys.tables pt ON pt.object_id=fk.referenced_object_id
              JOIN sys.schemas ps ON ps.schema_id=pt.schema_id
              JOIN sys.columns pc ON pc.object_id=pt.object_id AND pc.column_id=fkc.referenced_column_id
             ORDER BY fk.name, fkc.constraint_column_id""")
        idx, _ = q("indexes", """
            SELECT s.name schema_name, t.name table_name, i.name index_name,
                   i.is_unique, i.is_primary_key, i.type_desc,
                   ic.key_ordinal, c.name column_name
              FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id
              JOIN sys.schemas s ON s.schema_id=t.schema_id
              JOIN sys.index_columns ic ON ic.object_id=t.object_id AND ic.index_id=i.index_id
              JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=ic.column_id
             WHERE i.name IS NOT NULL
             ORDER BY t.name, i.name, ic.key_ordinal""")
        views, _ = q("views", """
            SELECT s.name schema_name, v.name view_name, m.definition
              FROM sys.views v JOIN sys.schemas s ON s.schema_id=v.schema_id
              LEFT JOIN sys.sql_modules m ON m.object_id=v.object_id
             WHERE v.is_ms_shipped=0 ORDER BY s.name, v.name""")
        defs = []
        for r in views[:eng.b.cfg["max_definitions"]]:
            s = sanitize_definition(r["definition"], eng.b.cfg["definition_max_bytes"])
            defs.append({"database": db, "schema": r["schema_name"],
                         "object_name": r["view_name"], "kind": "VIEW",
                         "definition": s["text"], "truncated": s["truncated"]})
        space, _ = q("capacity", """
            SELECT s.name schema_name, t.name table_name,
                   CAST(SUM(CASE WHEN p.index_id IN (0,1) THEN p.rows ELSE 0 END) AS bigint) estimated_rows,
                   CAST(SUM(au.total_pages) * 8 AS bigint) allocated_kb,
                   CAST(SUM(au.used_pages) * 8 AS bigint) used_kb,
                   CAST(SUM(CASE WHEN i.index_id IN (0,1) THEN au.total_pages ELSE 0 END) * 8 AS bigint) base_index_kb
              FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
              JOIN sys.indexes i ON i.object_id=t.object_id
              JOIN sys.partitions p ON p.object_id=i.object_id AND p.index_id=i.index_id
              JOIN sys.allocation_units au ON au.container_id = CASE
                    WHEN i.type IN (0,1) THEN p.hobt_id WHEN i.type=2 THEN p.partition_id END
             WHERE t.is_ms_shipped=0
             GROUP BY s.name, t.name ORDER BY s.name, t.name""")
        out.setdefault("per_database", {})[db] = {
            "tables": {"provenance": "sys.tables+sys.partitions(index_id 0/1 only)", "data": tables},
            "columns": {"provenance": "sys.columns (U+V)", "data": columns},
            "key_constraints": {"provenance": "sys.key_constraints composite", "data": cons},
            "foreign_keys": {"provenance": "sys.foreign_keys + is_disabled/is_not_trusted", "data": fks},
            "indexes": {"provenance": "sys.indexes composite", "data": idx},
            "view_definitions": {"provenance": "sys.sql_modules", "data": defs},
            "capacity": {"provenance": "allocation_units total_pages*8KB (rows only index 0/1)", "data": space},
        }
        ckpt["stages_done"].append(f"db:{db}")
        save_ckpt(ckpt)


def stage_postgres(eng, cfg, out, ckpt):
    q = eng.execute
    ident, _ = q("identity", "SELECT version() AS version, current_database() AS db, "
                             "current_user AS current_user")
    schemas, _ = q("schemas", """
        SELECT n.nspname schema_name FROM pg_catalog.pg_namespace n
         WHERE n.nspname NOT IN ('pg_catalog','information_schema')
           AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp%'
         ORDER BY 1""")
    wanted = cfg.get("schemas") or [r["schema_name"] for r in schemas]
    out["identity"] = {"provenance": "version()/current_database()", "data": ident,
                       "collected_at": now()}
    out["schemas_harvested"] = wanted

    tables, columns, constraints, indexes, defs = [], [], [], [], []
    dialect_errors = {}
    for schema in wanted:
        if f"schema:{schema}" in ckpt.get("stages_done", []):
            continue  # r205 resume: schema fully collected in a previous round
        try:
            rels, _ = q("relations", """
                SELECT c.oid, c.relname, c.relkind, c.reltuples::bigint estimated_rows,
                       c.relispartition, pg_get_expr(c.relpartbound, c.oid) partbound,
                       (SELECT count(*) FROM pg_catalog.pg_inherits i
                         WHERE i.inhrelid = c.oid) is_partition_child,
                       obj_description(c.oid, 'pg_class') comment
                  FROM pg_catalog.pg_class c
                  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = %s AND c.relkind IN ('r','p','v','m')
                 ORDER BY c.relname""", (schema,))
        except (CircuitBreak, BudgetExceeded):
            raise
        except Exception as exc:
            # helper functions unavailable on PG-compatible engines: plain-catalog retry
            dialect_errors.setdefault("relations", []).append(f"{schema}:{str(exc)[:90]}")
            rels, _ = q("relations_lite", """
                SELECT c.oid, c.relname, c.relkind, c.reltuples::bigint estimated_rows
                  FROM pg_catalog.pg_class c
                  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = %s AND c.relkind IN ('r','p','v','m')
                 ORDER BY c.relname""", (schema,))
        tables.extend([{"schema": schema, **{k: r[k] for k in r if k != "oid"}} for r in rels])
        names = [r["relname"] for r in rels if r["relkind"] in ("r", "p")]
        for batch in chunks(names, DEFAULTS["batch_objects"]):
            ph = ",".join(["%s"] * len(batch))
            try:
                cols, _ = q("columns", f"""
                    SELECT c.relname table_name, a.attname, a.attnum,
                           format_type(a.atttypid, a.atttypmod) data_type,
                           a.attnotnull, a.attidentity, a.attgenerated,
                           col_description(a.attrelid, a.attnum) comment
                      FROM pg_catalog.pg_attribute a
                      JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                      JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                     WHERE n.nspname = %s AND c.relname IN ({ph}) AND a.attnum > 0
                       AND NOT a.attisdropped
                     ORDER BY c.relname, a.attnum""", (schema, *batch))
            except (CircuitBreak, BudgetExceeded):
                raise
            except Exception as exc:
                dialect_errors.setdefault("columns", []).append(f"{schema}:{str(exc)[:90]}")
                cols, _ = q("columns_lite", f"""
                    SELECT c.relname table_name, a.attname, a.attnum,
                           t.typname data_type, a.attnotnull
                      FROM pg_catalog.pg_attribute a
                      JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
                      JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                      JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
                     WHERE n.nspname = %s AND c.relname IN ({ph}) AND a.attnum > 0
                       AND NOT a.attisdropped
                     ORDER BY c.relname, a.attnum""", (schema, *batch))
            columns.extend([{"schema": schema, **r} for r in cols])
            # dialect guards: PG-compatible engines (HuaChainSQL etc.) may lack
            # helper functions; capture per-schema instead of blocking the source
            try:
                cons, _ = q("constraints", f"""
                    SELECT con.conname, con.contype, c.relname table_name,
                           pg_get_constraintdef(con.oid) definition, con.convalidated
                      FROM pg_catalog.pg_constraint con
                      JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
                      JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                     WHERE n.nspname = %s AND c.relname IN ({ph})
                     ORDER BY c.relname, con.conname""", (schema, *batch))
                constraints.extend([{"schema": schema, **r} for r in cons])
            except (CircuitBreak, BudgetExceeded):
                raise
            except Exception as exc:
                dialect_errors.setdefault("constraints", []).append(f"{schema}:{str(exc)[:90]}")
            try:
                idx, _ = q("indexes", f"""
                    SELECT c.relname table_name, i.relname index_name,
                           ix.indisunique, ix.indisprimary,
                           pg_get_indexdef(i.oid) index_def
                      FROM pg_catalog.pg_index ix
                      JOIN pg_catalog.pg_class c ON c.oid = ix.indrelid
                      JOIN pg_catalog.pg_class i ON i.oid = ix.indexrelid
                      JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                     WHERE n.nspname = %s AND c.relname IN ({ph})
                     ORDER BY c.relname, i.relname""", (schema, *batch))
                indexes.extend([{"schema": schema, **r} for r in idx])
            except (CircuitBreak, BudgetExceeded):
                raise
            except Exception as exc:
                dialect_errors.setdefault("indexes", []).append(f"{schema}:{str(exc)[:90]}")
        # view definitions
        for r in rels:
            if r["relkind"] in ("v", "m") and len(defs) < eng.b.cfg["max_definitions"]:
                try:
                    d, _ = q("view_def", """
                        SELECT pg_get_viewdef(%s::regclass, true) def""", (f'{schema}.{r["relname"]}',))
                    raw_def = d[0]["def"] if d else None
                except (CircuitBreak, BudgetExceeded):
                    raise
                except Exception as exc:
                    dialect_errors.setdefault("view_def", []).append(
                        f'{schema}.{r["relname"]}:{str(exc)[:70]}')
                    raw_def = None
                s = sanitize_definition(raw_def, eng.b.cfg["definition_max_bytes"])
                defs.append({"schema": schema, "object_name": r["relname"],
                             "kind": "VIEW" if r["relkind"] == "v" else "MATERIALIZED_VIEW",
                             "definition": s["text"], "truncated": s["truncated"]})
        ckpt["stages_done"].append(f"schema:{schema}")
        save_ckpt(ckpt)
        _flush_partial(out, tables=tables, columns=columns,
                       constraints=constraints, indexes=indexes,
                       view_definitions=defs)

    out["tables"] = {"provenance": "pg_class r/p/v/m + reltuples (estimates; -1/None=unknown)",
                     "data": tables, "collected_at": now()}
    out["dialect_errors"] = dialect_errors
    out["columns"] = {"provenance": "pg_attribute batched", "data": columns, "collected_at": now()}
    out["constraints"] = {"provenance": "pg_constraint + definition + validated", "data": constraints,
                          "collected_at": now()}
    out["indexes"] = {"provenance": "pg_index + get_indexdef", "data": indexes,
                      "collected_at": now()}
    out["view_definitions"] = {"provenance": "pg_get_viewdef", "data": defs, "collected_at": now()}

    # capacity: guarded per-object size calls (throttled by budget), parent/child flagged
    cap_data = []
    for t in tables[:eng.b.cfg["max_space_objects"]]:
        if t.get("relkind") in ("r", "p"):
            try:
                sz, _ = q("capacity", """
                    SELECT pg_total_relation_size(%s::regclass) total_bytes,
                           pg_relation_size(%s::regclass) heap_bytes""",
                          (f'{t["schema"]}.{t["relname"]}',) * 2)
                if sz:
                    cap_data.append({"schema": t["schema"], "table_name": t["relname"],
                                     "is_partition_child": t.get("is_partition_child"),
                                     "total_bytes": sz[0]["total_bytes"],
                                     "heap_bytes": sz[0]["heap_bytes"]})
            except CircuitBreak:
                raise
            except Exception as exc:
                cap_data.append({"schema": t["schema"], "table_name": t["relname"],
                                 "error": str(exc)[:120]})
    out["capacity"] = {
        "provenance": "pg_total_relation_size per object (guarded, throttled)",
        "dedup_rule": "partition parent pg_total_relation_size contains only parent itself; children listed separately with is_partition_child; never summed blindly",
        "collected_at": now(),
        "count_total": len([t for t in tables if t.get("relkind") in ("r", "p")]),
        "count_fetched": len(cap_data),
        "data": cap_data,
    }


def now():
    return datetime.now(timezone.utc).isoformat()


def save_ckpt(ckpt):
    path = Path(ckpt["_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ckpt, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, type=Path, help="JSON config path")
    ap.add_argument("--checkpoint", required=True, type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--logs", type=Path)
    ap.add_argument("--credential-file", default="")
    ap.add_argument("--limit-schemas", default="", help="comma list override for pilot")
    args = ap.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    if args.limit_schemas:
        cfg["owners"] = [s.strip() for s in args.limit_schemas.split(",") if s.strip()]
        cfg["schemas"] = cfg["owners"]
        cfg["databases"] = cfg["owners"]

    cred = {}
    if args.credential_file:
        cred = read_credential_file(args.credential_file)
    else:
        cred = {"user": os.environ.get("R188_HARVEST_USER", ""),
                "password": os.environ.get("R188_HARVEST_PASSWORD", "")}
    if not cred.get("user") or not cred.get("password"):
        raise SystemExit("credentials unavailable")
    cfg["credentials"] = cred

    log_lines = []
    if args.logs:
        # durable per-event log: SIGKILL must not erase run evidence
        args.logs.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(args.logs, "a", encoding="utf-8") if args.logs else None

    def log(record):
        line = json.dumps({"ts": now(), **record}, ensure_ascii=False, default=str)
        log_lines.append(line)
        if log_fh:
            log_fh.write(line + "\n")
            log_fh.flush()

    ckpt = {
        "_path": str(args.checkpoint),
        "schema_version": "r188-checkpoint/1.0",
        "config": {k: v for k, v in cfg.items() if k != "credentials"},
        "started_at": now(), "stages_done": [], "config_sha256": hashlib.sha256(
            args.config.read_bytes()).hexdigest()[:16],
        "status": "running", "stopped_reason": None,
    }
    if args.checkpoint.exists():
        prev = json.loads(args.checkpoint.read_text(encoding="utf-8"))
        if prev.get("config_sha256") == ckpt["config_sha256"]:
            ckpt = prev  # resume: keep stage progress and counters via logs
            log({"event": "resume", "stages_done": prev.get("stages_done")})
        else:
            log({"event": "config_changed_restart"})

    budget = Budget(cfg, log)
    eng_cls = ENGINES.get(cfg["engine"])
    if not eng_cls:
        raise SystemExit(f"unknown engine {cfg['engine']}")
    eng = eng_cls(cfg, budget, log)
    out = {"run_id": cfg.get("run_id"), "source_code": cfg.get("source_code"),
           "engine": cfg["engine"], "collected_at": now(), "budget_cfg": budget.cfg}

    # r205 v7: resume-rehydrate — when resuming (ckpt kept) and a previous snapshot
    # exists, load its data lists into out so per-owner skip + accumulative flush
    # keep prior rounds' rows instead of being cleared by stage-end assignment.
    if ckpt.get("stages_done") and args.output and args.output.exists():
        try:
            prev_snap = json.loads(args.output.read_text(encoding="utf-8"))
            rehydrated = 0
            for key in ("tables", "columns", "constraints", "indexes",
                        "view_definitions", "table_comments", "capacity",
                        "capacity_segments", "databases", "objects"):
                pd = prev_snap.get(key)
                if isinstance(pd, dict) and isinstance(pd.get("data"), list) and pd["data"]:
                    out[key] = pd
                    rehydrated += len(pd["data"])
            if rehydrated:
                log({"event": "resume_rehydrate", "rows": rehydrated})
        except Exception as exc:
            log({"event": "resume_rehydrate_error", "error": str(exc)[:120]})

    try:
        eng.connect()
        if cfg["engine"] == "oracle":
            stage_oracle(eng, cfg, out, ckpt)
        elif cfg["engine"] == "mysql":
            stage_mysql(eng, cfg, out, ckpt)
        elif cfg["engine"] == "sqlserver":
            stage_sqlserver(eng, cfg, out, ckpt)
        else:
            stage_postgres(eng, cfg, out, ckpt)
        ckpt["status"] = "done"
        ckpt["stopped_reason"] = None  # resumed runs must not keep stale block reason
        out["source_writes"] = 0
        out["write_evidence"] = {
            "session_protection": {
                "oracle": "SET TRANSACTION READ ONLY",
                "mysql": "SET SESSION TRANSACTION READ ONLY",
                "postgresql": "default_transaction_read_only=on",
                "sqlserver": "no universal switch; metadata-only scope + LOCK_TIMEOUT",
            }.get(cfg["engine"]),
            "sql_log": "see logs file; all statements are catalog SELECTs",
        }
        out["budget_used"] = {"statements": budget.statements,
                              "db_seconds": round(budget.db_seconds, 1),
                              "wall_seconds": round(time.monotonic() - budget.started, 1)}
    except BudgetExceeded as exc:
        ckpt["status"] = "stopped_budget"
        ckpt["stopped_reason"] = str(exc)
        out["stopped_reason"] = f"budget:{exc}"
        out["partial"] = True
        log({"event": "budget_stopped", "reason": str(exc)})
    except CircuitBreak as exc:
        ckpt["status"] = "stopped_circuit"
        ckpt["stopped_reason"] = str(exc)
        out["stopped_reason"] = f"circuit:{exc}"
        out["partial"] = True
        log({"event": "circuit_break", "reason": str(exc)})
    except Exception as exc:  # auth/network/dialect -> record, do not retry
        ckpt["status"] = "blocked"
        ckpt["stopped_reason"] = f"{type(exc).__name__}:{str(exc)[:300]}"
        out["blocked_reason"] = ckpt["stopped_reason"]
        out["partial"] = True
        log({"event": "blocked", "reason": ckpt["stopped_reason"]})
    finally:
        eng.close()
        ckpt["finished_at"] = now()
        ckpt["budget_used"] = {"statements": budget.statements,
                               "db_seconds": round(budget.db_seconds, 1)}
        save_ckpt(ckpt)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(out, ensure_ascii=False, default=str, indent=1),
                                   encoding="utf-8")
        if log_fh:
            log_fh.close()  # events already flushed incrementally; resume history kept
        summary = {
            "source_code": cfg.get("source_code"), "status": ckpt["status"],
            "stopped_reason": ckpt.get("stopped_reason"),
            "statements": budget.statements,
            "db_seconds": round(budget.db_seconds, 1),
        }
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
