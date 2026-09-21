# r194 shared API helper with token cache (login rate limit is 5/min).
import json
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
CACHE_PATH = r"F:\python\数据资产\开发起步包\output_r194\r194-20260917-204356\api_static\token_cache.json"
PW = {"r194_admin": "R194Seed#A1N9x", "r194_viewer": "R194Seed#A1R9x",
      "r194_qa_a": "R194Seed#A1A9x", "r194_qa_b": "R194Seed#A1B9x",
      "r194_norole": "R194Seed#A1E9x", "r194_expiring": "R194Seed#A1G9x"}


def req(method, path, token=None, body=None):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
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


def get_token(user, force=False):
    cache = {}
    try:
        cache = json.load(open(CACHE_PATH, encoding="utf-8"))
    except Exception:
        pass
    if not force and cache.get(user):
        s, d = req("GET", "/api/v1/auth/me", cache[user])
        if s == 200:
            return cache[user]
    for attempt in range(3):
        s, d = req("POST", "/api/v1/auth/login", body={"username": user, "password": PW[user]})
        if s == 200:
            tok = (d.get("data") or {}).get("access_token") or (d.get("data") or {}).get("accessToken")
            cache[user] = tok
            json.dump(cache, open(CACHE_PATH, "w", encoding="utf-8"))
            return tok
        if s == 429:
            time.sleep(65)
        else:
            raise RuntimeError(f"login {user} -> {s}: {json.dumps(d, ensure_ascii=False)[:120]}")
    raise RuntimeError(f"login {user} exhausted retries")


if __name__ == "__main__":
    import sys
    user = sys.argv[1] if len(sys.argv) > 1 else "r194_admin"
    tok = get_token(user)
    print("token ok for", user, len(tok))
