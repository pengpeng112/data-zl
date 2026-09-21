# r194 S0d: parse frontend/src/router/modules/*.ts into a route inventory
# (path, name, title, showLink, auths, activePath, component, redirect).
import glob
import json
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "frontend", "src", "router")
out = []
for f in sorted(glob.glob(os.path.join(ROOT, "modules", "*.ts"))):
    mod = os.path.basename(f)[:-3]
    text = open(f, encoding="utf-8").read()

    def rx(pat, s, default=None):
        m = re.search(pat, s, re.S)
        return m.group(1).strip().strip('"\'') if m else default

    # split children blocks by top-level route objects: crude but structure is uniform
    # find each { path: ... name: ... meta: { ... } } chunk
    for m in re.finditer(r"\{\s*(//.*)?\s*path:\s*[\"']([^\"']+)[\"']", text):
        path = m.group(2)
        start = m.start()
        # take window until next path occurrence or EOF
        nxt = text.find("path:", m.end())
        chunk = text[start: nxt if nxt != -1 else len(text)]
        name = rx(r"name:\s*[\"']([^\"']+)[\"']", chunk)
        title = rx(r"title:\s*[\"']([^\"']+)[\"']", chunk)
        show = rx(r"showLink:\s*(true|false)", chunk)
        auths = re.findall(r"auths:\s*\[([^\]]*)\]", chunk)
        auths_list = []
        for a in auths:
            auths_list += re.findall(r"['\"]([^'\"]+)['\"]", a)
        comp = rx(r"component:\s*\(\)\s*=>\s*import\([\"']([^\"']+)[\"']\)", chunk)
        redir = rx(r"redirect:\s*([\"'][^\"']*[\"']|\w+)", chunk)
        active = rx(r"activePath:\s*[\"']([^\"']+)[\"']", chunk)
        rank = rx(r"rank:\s*(\d+)", chunk)
        out.append({
            "module": mod,
            "path": path,
            "name": name,
            "title": title,
            "showLink": show,
            "auths": auths_list,
            "activePath": active,
            "component": comp,
            "redirect": redir,
            "rank": rank,
        })

with open(os.path.join(os.path.dirname(__file__), "..", "api_static", "routes.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

vis = [r for r in out if r["showLink"] == "true"]
hidden = [r for r in out if r["showLink"] == "false"]
print("total route entries:", len(out), "| visible:", len(vis), "| hidden/compat:", len(hidden))
print("visible leaf titles:", json.dumps([r["title"] for r in vis], ensure_ascii=False))
