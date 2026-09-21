# -*- coding: utf-8 -*-
"""修复 JOIN 别名正则的回溯问题。"""
src = open("scripts/s3_parse.py", encoding="utf-8").read()
OLD1 = r'''        jm = re.match(rf"\s*({IDENT})\s*(?:\s(?:as\s+)?([A-Za-z_][\w$#]*))?", part, re.I)
        if jm and jm.group(1).split(".")[-1].strip('"').lower() not in STOP:
            obj, alias = jm.group(1), jm.group(2)'''
NEW1 = r'''        jm = re.match(rf"\s*({IDENT})(?:\s+(?:as\s+)?([A-Za-z_][\w$#]*))?", part, re.I)
        alias = jm.group(2) if jm and jm.group(2) and jm.group(2).lower() not in STOP else None
        if jm and jm.group(1).split(".")[-1].strip('"').lower() not in STOP:
            obj = jm.group(1)'''
assert OLD1 in src, "OLD1 not found"
src = src.replace(OLD1, NEW1)
open("scripts/s3_parse.py", "w", encoding="utf-8").write(src)
print("patched alias regex")
