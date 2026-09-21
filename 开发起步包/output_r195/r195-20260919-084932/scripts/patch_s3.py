# -*- coding: utf-8 -*-
"""重写 s3_parse.py 的 JOIN 段（修复 heredoc 转义损坏）。"""
src = open("scripts/s3_parse.py", encoding="utf-8").read()
lines = src.splitlines(keepends=True)
start = next(i for i, l in enumerate(lines) if l.strip() == "# JOIN 段")
end = next(i for i in range(start, len(lines)) if lines[i].strip() == "return items")

NEW = r'''    # JOIN 段
    for kw, part in zip(join_kw, join_parts[1:]):
        jm = re.match(rf"\s*({IDENT})\s*(?:\s(?:as\s+)?([A-Za-z_][\w$#]*))?", part, re.I)
        if jm and jm.group(1).split(".")[-1].strip('"').lower() not in STOP:
            obj, alias = jm.group(1), jm.group(2)
            on_m = re.search(r"\bon\b(.*?)(?=\bleft\b|\bright\b|\binner\b|\bjoin\b|\bwhere\b|\bgroup\b|\border\b|\bhaving\b|\bunion\b|$)", part[jm.end():], re.I | re.S)
            items.append({"obj": obj, "alias": alias, "join_kw": kw, "on": on_m.group(1).strip() if on_m else None})
            continue
        sm = re.match(r"\s*\(", part)
        if sm:
            depth, j, in_str, endp = 0, 0, False, None
            while j < len(part):
                c = part[j]
                if in_str:
                    if c == "'":
                        if j + 1 < len(part) and part[j + 1] == "'":
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
                    if depth == 0:
                        endp = j
                        break
                j += 1
            if endp is not None:
                inner = part[1:endp]
                am = re.match(r"\s*(?:as\s+)?([A-Za-z_][\w$#]*)\b", part[endp + 1:], re.I)
                on_m = re.search(r"\bon\b(.*?)$", part[endp + 1:], re.I | re.S)
                fm2 = re.search(rf"\bfrom\b\s+({IDENT})", inner, re.I)
                rep = fm2.group(1) if fm2 else "(SUBQUERY)"
                items.append({"obj": rep, "alias": am.group(1) if am else None, "join_kw": kw,
                              "on": on_m.group(1).strip() if on_m else None, "subquery": True})
    return items
'''
lines[start:end + 1] = [NEW]
open("scripts/s3_parse.py", "w", encoding="utf-8").write("".join(lines))
print("rewritten lines", start, "-", end + 1)
