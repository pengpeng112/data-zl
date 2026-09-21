# -*- coding: utf-8 -*-
"""find_from_items 的段截断改为括号深度感知。"""
src = open("scripts/s3_parse.py", encoding="utf-8").read()
OLD = r'''    rest = chunk[m.end():]
    # 截断到顶层关键字
    stop = None
    for kw in ("where", "group by", "order by", "having", "union", "minus", "intersect", "connect by"):
        mm = re.search(rf"\b{kw}\b", rest, re.I)
        if mm and (stop is None or mm.start() < stop):
            stop = mm.start()
    seg = rest[:stop] if stop is not None else rest'''
NEW = r'''    rest = chunk[m.end():]
    # 截断到顶层关键字（括号深度感知，子查询内不算）
    stop = None
    depth, in_str, j = 0, False, 0
    while j < len(rest):
        c = rest[j]
        if in_str:
            if c == "'":
                if j + 1 < len(rest) and rest[j + 1] == "'":
                    j += 2
                    continue
                in_str = False
            j += 1
            continue
        if c == "'":
            in_str = True
            j += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0:
            mm = re.match(r"\b(where|group\s+by|order\s+by|having|union|minus|intersect|connect\s+by)\b", rest[j:], re.I)
            if mm:
                stop = j
                break
        j += 1
    seg = rest[:stop] if stop is not None else rest'''
assert OLD in src, "OLD not found"
src = src.replace(OLD, NEW)
open("scripts/s3_parse.py", "w", encoding="utf-8").write(src)
print("patched depth-aware stop")
