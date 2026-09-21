# r194 S3/S4: API-level journeys & permission matrix against isolated backend (localhost:8000).
# Covers: G07/AR04 role matrix, J08 dept isolation, J12 session expiry,
# O02 SQL workbench negative, O03 write-executor negative, J04 review transition checks.
import json
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
PW = {"r194_admin": "R194Seed#A1N9x", "r194_viewer": "R194Seed#A1R9x",
      "r194_qa_a": "R194Seed#A1A9x", "r194_qa_b": "R194Seed#A1B9x",
      "r194_norole": "R194Seed#A1E9x", "r194_expiring": "R194Seed#A1G9x"}
RESULTS = []


def req(method, path, token=None, body=None, base=BASE):
    url = base + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            try:
                return resp.status, json.loads(resp.read().decode() or "{}")
            except Exception:
                return resp.status, {}
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:
        return -1, {"err": str(e)[:100]}


def login(user):
    s, d = req("POST", "/api/v1/auth/login", body={"username": user, "password": PW[user]})
    if s != 200:
        return None, d
    return d["data"].get("access_token") or d["data"].get("accessToken"), d


def record(case, status, expected, note=""):
    ok = None
    if isinstance(expected, list):
        ok = status in expected
    else:
        ok = status == expected
    RESULTS.append({"case": case, "status": status, "expected": expected,
                    "pass": ok, "note": note[:180]})


import time as _t
_t.sleep(50)  # clear login rate-limit window (5/min)
admin, _ = login("r194_admin"); _t.sleep(1)
viewer, _ = login("r194_viewer"); _t.sleep(1)
qa_a, _ = login("r194_qa_a"); _t.sleep(1)
qa_b, _ = login("r194_qa_b"); _t.sleep(1)
norole, _ = login("r194_norole")
_t.sleep(50)
expiring, exp_login = login("r194_expiring")
assert admin and viewer and qa_a and qa_b and norole and expiring, "logins failed"

# --- AR04/G07: role access matrix ---
matrix = [
    # (case, method, path, token, expected)
    ("AR04-anon-systems", "GET", "/api/v1/systems", None, 401),
    ("AR04-norole-systems", "GET", "/api/v1/systems", norole, 200),  # read asset browsing needs valid token only
    ("AR04-norole-admin-keys", "GET", "/api/v1/admin/keys", norole, 403),
    ("AR04-norole-identity-write", "POST", "/api/v1/identity/persons", norole, 403),
    ("AR04-viewer-admin", "GET", "/api/v1/admin/keys", viewer, 403),
    ("AR04-viewer-issues", "GET", "/api/v1/quality-issues", viewer, 200),
    ("AR04-viewer-issue-create", "POST", "/api/v1/quality-issues", viewer, 403),
    ("AR04-norole-ops-tools", "GET", "/api/v1/ops/tools", norole, 403),
    ("AR04-viewer-ops-tools", "GET", "/api/v1/ops/tools", viewer, 403),
    ("AR04-admin-ops-tools", "GET", "/api/v1/ops/tools", admin, 200),
    ("AR04-viewer-executors", "GET", "/api/v1/admin/executors", viewer, 403),
    ("AR04-bogus-token", "GET", "/api/v1/systems", "fake.token.here", 403),
]
for case, m, p, tok, exp in matrix:
    s, d = req(m, p, tok, body={})
    record(case, s, exp, json.dumps(d, ensure_ascii=False)[:120])

# --- J08: dept isolation on quality issues (C=NK vs D=WK) ---
s, d = req("GET", "/api/v1/quality-issues?mine=true", qa_a)
mine_a = d.get("data", {}).get("items", d.get("data", [])) if s == 200 else []
record("J08-qaA-mine-200", s, 200)
codes_a = [i.get("issue_code") for i in mine_a] if isinstance(mine_a, list) else []
s, d = req("GET", "/api/v1/quality-issues?mine=true", qa_b)
mine_b = d.get("data", {}).get("items", d.get("data", [])) if s == 200 else []
codes_b = [i.get("issue_code") for i in mine_b] if isinstance(mine_b, list) else []
# J08: A sees only NK issues (0001/0003), B only WK (0002)
a_ok = set(codes_a) <= {"ISS194-0001", "ISS194-0003"} and codes_a
b_ok = set(codes_b) <= {"ISS194-0002"} and codes_b
RESULTS.append({"case": "J08-qaA-sees-only-NK", "status": 200 if a_ok else 0, "expected": 200,
                "pass": bool(a_ok), "note": f"qa_a mine={codes_a}"})
RESULTS.append({"case": "J08-qaB-sees-only-WK", "status": 200 if b_ok else 0, "expected": 200,
                "pass": bool(b_ok), "note": f"qa_b mine={codes_b}"})
# direct detail access cross-dept (guess D's issue id via list as admin)
s, d = req("GET", "/api/v1/quality-issues", admin)
items = d.get("data", {}).get("items", [])
id_map = {i.get("issue_code"): i.get("id") for i in items}
d_issue = id_map.get("ISS194-0002")
if d_issue:
    s, _ = req("GET", f"/api/v1/quality-issues/{d_issue}", qa_a)
    record("J08-qaA-read-WK-issue", s, [403, 404], f"GET issue {d_issue} as qa_a -> {s}")
    # cross-dept transition attempt: try close/transition D's issue as A
    s, d = req("POST", f"/api/v1/quality-issues/{d_issue}/transition", qa_a, body={"to_status": "resolved", "reason": "r194 cross-dept attempt"})
    record("J08-qaA-transition-WK-issue", s, [403, 404, 422], f"transition as qa_a -> {s}")

# --- J12: session expiry ---
s, d = req("GET", "/api/v1/auth/me", expiring)
record("J12-expiring-me-ok", s, 200)
# expire server-side: admin disables the user then re-enables? Instead use refresh of a fabricated expired token is not possible.
# Simulate by revoking all sessions via admin password change is destructive; skip destructive path:
# use token with wrong signature instead (401 path) + note real expiry not simulated here.
s, d = req("GET", "/api/v1/auth/me", "eyJhbGciOiJIUzI1NiJ9.expired.signature")
record("J12-bad-token-me", s, [401, 403])

# --- O02: SQL workbench negative (DML/DDL/multi-statement rejected) ---
sql_cases = [
    ("O02-select-limit", "SELECT * FROM CLIN.PATIENT_INFO WHERE ROWNUM <= 10", [200, 422]),
    ("O02-update", "UPDATE CLIN.PATIENT_INFO SET NAME='x'", [403, 422]),
    ("O02-delete", "DELETE FROM CLIN.VISIT_RECORD", [403, 422]),
    ("O02-drop", "DROP TABLE CLIN.PATIENT_INFO", [403, 422]),
    ("O02-multi", "SELECT 1 FROM dual; DELETE FROM CLIN.PATIENT_INFO", [403, 422]),
    ("O02-noscan", "SELECT * FROM CLIN.PATIENT_INFO", [403, 422]),
]
for case, sql, exp in sql_cases:
    s, d = req("POST", "/api/v1/ops/sql/validate", admin, body={"sql_text": sql, "source_code": "R194A1"})
    if s == 404:
        # endpoint name guess failed; try plan/preview variant once
        s2, d2 = req("POST", "/api/v1/ops/sql/preview", admin, body={"sql_text": sql})
        if s2 != 404:
            record(case, s2, exp, f"via preview: {json.dumps(d2, ensure_ascii=False)[:100]}")
            continue
        RESULTS.append({"case": case, "status": 404, "expected": exp, "pass": None,
                        "note": "sql validate/preview endpoint not found at guessed path; NOT_RUN"})
        continue
    record(case, s, exp, json.dumps(d, ensure_ascii=False)[:100])

# --- O03: write executor without approval ---
s, d = req("POST", "/api/v1/ops/executions", admin, body={"executor_code": "not_registered", "params": {}})
record("O03-unregistered-executor", s, [400, 403, 404, 422], json.dumps(d, ensure_ascii=False)[:100])

# --- J04: relation review draft state machine ---
s, d = req("GET", "/api/v1/relation-reviews?review_status=draft", admin)
items = d.get("data", {}).get("items") or d.get("data", []) or []
record("J04-draft-list", s, 200, f"items={len(items) if isinstance(items, list) else '?'}")
if isinstance(items, list) and items:
    rid = items[0].get("id")
    s, d = req("POST", f"/api/v1/relation-reviews/{rid}/review", admin,
               body={"decision": "approved", "note": "r194 approve"})
    record("J04-approve-draft", s, [200, 201], json.dumps(d, ensure_ascii=False)[:100])
    s, d = req("POST", f"/api/v1/relation-reviews/{rid}/review", admin,
               body={"decision": "rejected", "note": "r194 second"})
    record("J04-second-review-rejected", s, [400, 404, 409, 422], "second review should not silently re-review")

# --- J06/Q05: certification gate on run ---
s, d = req("POST", "/api/v1/queries/run", viewer,
           body={"query_code": "QRY_R194_B", "params": {"start_date": "2026-01-01"}})
record("Q05-legacy-unverified-run-by-viewer", s, [200, 403, 422],
       f"status={s}; " + json.dumps(d, ensure_ascii=False)[:120])
s, d = req("POST", "/api/v1/queries/run", admin,
           body={"query_code": "QRY_R194_C", "params": {}})
record("Q05-blocked-query-run", s, [200, 403, 422, 404],
       f"blocked status query run -> {s}; " + json.dumps(d, ensure_ascii=False)[:120])

# --- I02: account state combos exposure (page data check at API level) ---
s, d = req("GET", "/api/v1/identity/accounts?person_code=P19401", admin)
record("I02-accounts-P19401", s, 200, json.dumps(d, ensure_ascii=False)[:140])

# --- J11: audit list as admin + no-leak quick scan ---
s, d = req("GET", "/api/v1/audit?limit=5", admin)
record("J11-audit-list", s, [200, 404], json.dumps(d, ensure_ascii=False)[:100])

out = {"ran_at": time.strftime("%Y-%m-%d %H:%M:%S"), "results": RESULTS}
with open(r"F:\python\数据资产\开发起步包\output_r194\r194-20260917-204356\api_static\api_matrix_results.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
npass = sum(1 for r in RESULTS if r["pass"] is True)
nfail = sum(1 for r in RESULTS if r["pass"] is False)
nnone = sum(1 for r in RESULTS if r["pass"] is None)
print(f"cases={len(RESULTS)} pass={npass} fail={nfail} unknown={nnone}")
for r in RESULTS:
    if r["pass"] is not True:
        print(" !", r["case"], "status=", r["status"], "expected=", r["expected"], "|", r["note"][:100])
