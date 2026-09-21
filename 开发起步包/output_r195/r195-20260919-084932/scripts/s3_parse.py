# -*- coding: utf-8 -*-
"""S3：静态关系/血缘/值域解析器（heuristic v1）。
能力：
- 查询块拆分（顶层 UNION 分支 + WHERE 中子查询块）
- 别名→对象解析（含 CTE 识别、Owner 前缀、部署 schema 默认）
- 逗号连接 WHERE 等值 + ANSI JOIN ON + Oracle (+) 方向
- 限定条件（日期窗/状态字面量/ROWNUM）与去重聚合标志（ROW_NUMBER/DISTINCT/GROUP BY）
- SELECT 列级血缘（表达式→源别名）
- 值域：V1.3 值域代码 + SQL CASE 映射
所有候选带 SQL 片段定位与 sha256，供人工/AI 复核。
产物：relation_candidates_raw.json、field_lineage.jsonl、value_domain_candidates.json
"""
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r"D:\Users\Administrator\Desktop\三甲复审\6、数管中心三甲数据上报\数据接口规范+值域2.3"

SEG = r'(?:"[^"]+"|[\w$#]+)'
IDENT = rf'(?:{SEG})(?:\s*\.\s*(?:{SEG}))*'
FUNCS = {"regexp_replace", "substr", "to_date", "to_char", "to_number", "nvl", "decode",
         "row_number", "trunc", "add_months", "months_between", "greatest", "least",
         "coalesce", "cast", "trim", "ltrim", "rtrim", "upper", "lower", "length", "instr",
         "replace", "translate", "abs", "round", "count", "sum", "min", "max", "avg",
         "listagg", "extract", "sysdate"}
STOP = {"select", "from", "where", "group", "order", "having", "union", "minus", "intersect",
        "on", "left", "right", "inner", "outer", "full", "cross", "when", "case", "end",
        "and", "or", "not", "as", "by", "distinct", "connect", "start", "set", "values", "dual"}


def read_any(path):
    for enc in ("utf-8-sig", "utf-8", "gbk", "utf-16"):
        try:
            return open(path, encoding=enc).read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return open(path, encoding="latin-1", errors="replace").read()


def strip_comments(txt):
    txt = re.sub(r"--[^\n]*", " ", txt)
    return re.sub(r"/\*.*?\*/", " ", txt, flags=re.S)


def split_top(sql, seps):
    """按顶层分隔符切分（括号深度0）。seps 为正则列表"""
    pat = re.compile("|".join(seps), re.I)
    parts, depth, last, i = [], 0, 0, 0
    tokens = []
    # 扫描字符，跟踪括号与字符串
    in_str = False
    while i < len(sql):
        c = sql[i]
        if in_str:
            if c == "'":
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    i += 2; continue
                in_str = False
            i += 1; continue
        if c == "'":
            in_str = True; i += 1; continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0:
            m = pat.match(sql, i)
            if m:
                parts.append(sql[last:i])
                tokens.append(m.group(0).upper())
                i = m.end()
                last = i
                continue
        i += 1
    parts.append(sql[last:])
    return parts, tokens


def find_from_items(chunk):
    """解析 FROM 后逗号表列表与 ANSI JOIN 链。返回 [(obj, alias, join_kw, on_cond)]"""
    items = []
    # FROM <list> 直到 WHERE/GROUP/ORDER/HAVING/UNION（JOIN 单独处理）
    m = re.search(r"\bfrom\b", chunk, re.I)
    if not m:
        return items
    rest = chunk[m.end():]
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
    seg = rest[:stop] if stop is not None else rest
    # 先按 JOIN 切
    join_parts, join_kw = split_top(seg, [r"\bleft\s+outer\s+join\b", r"\bleft\s+join\b", r"\bright\s+outer\s+join\b",
                                          r"\bright\s+join\b", r"\bfull\s+outer\s+join\b", r"\binner\s+join\b",
                                          r"\bcross\s+join\b", r"\bjoin\b"])
    # 第 0 段：逗号表列表
    first = join_parts[0]
    for part in split_top(first, [r","])[0]:
        pm = re.match(rf"\s*({IDENT})\s*(?:\s(?:as\s+)?([A-Za-z_][\w$#]*))?\s*$", part.strip(), re.I)
        if pm:
            obj, alias = pm.group(1), pm.group(2)
            if obj.split(".")[-1].strip('"').lower() not in STOP:
                items.append({"obj": obj, "alias": alias, "join_kw": "FROM", "on": None})
        else:
            # 表名后跟其他内容的宽松匹配
            pm2 = re.match(rf"\s*({IDENT})", part.strip(), re.I)
            if pm2 and pm2.group(1).split(".")[-1].strip('"').lower() not in STOP:
                tail = part.strip()[len(pm2.group(1)):].strip()
                al = None
                ma = re.match(r"(?:as\s+)?([A-Za-z_][\w$#]*)\b", tail, re.I)
                if ma and ma.group(1).lower() not in STOP:
                    al = ma.group(1)
                items.append({"obj": pm2.group(1), "alias": al, "join_kw": "FROM", "on": None})
    # JOIN 段
    for kw, part in zip(join_kw, join_parts[1:]):
        jm = re.match(rf"\s*({IDENT})(?:\s+(?:as\s+)?([A-Za-z_][\w$#]*))?", part, re.I)
        alias = jm.group(2) if jm and jm.group(2) and jm.group(2).lower() not in STOP else None
        if jm and jm.group(1).split(".")[-1].strip('"').lower() not in STOP:
            obj = jm.group(1)
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


def parse_predicates(cond_text):
    """切 AND 顶层条件，返回等值谓词列表 [(lhs, rhs, plus_side, raw)] 与其他条件"""
    eqs, others = [], []
    parts, _ = split_top(cond_text, [r"\band\b", r"\bor\b"])
    for p in parts:
        ps = p.strip()
        if not ps:
            continue
        m = re.match(rf"({IDENT})(\s*\(\+\))?\s*=\s*({IDENT})(\s*\(\+\))?\s*$", ps, re.I)
        if m:
            eqs.append({"lhs": m.group(1), "rhs": m.group(3),
                        "plus_lhs": bool(m.group(2)), "plus_rhs": bool(m.group(4)), "raw": ps[:300]})
            continue
        m2 = re.match(rf"({IDENT})\s*=\s*({IDENT})(\s*\(\+\))?\s*$", ps, re.I)
        if m2:
            eqs.append({"lhs": m2.group(1), "rhs": m2.group(2), "plus_lhs": False,
                        "plus_rhs": bool(m2.group(3)), "raw": ps[:300]})
            continue
        others.append(ps[:200])
    return eqs, others


def qualifier_of(cond):
    c = cond.strip()
    if re.search(r"\(\+\)", c):
        return None
    if re.search(r"\bto_date\b|\bdate\s+'|\bsysdate|between\s+", c, re.I):
        return {"kind": "date_window", "raw": c[:200]}
    m = re.match(rf"({IDENT})\s*=\s*'([^']*)'\s*$", c, re.I)
    if m and not re.match(r"^\d{4}-\d{2}-\d{2}", m.group(2)):
        col = m.group(1).split(".")[-1].upper()
        if any(k in col for k in ("STATUS", "TYPE", "FLAG", "CLASS", "CODE", "INDICATOR", "STATE", "WAY", "LEVEL", "CAT")):
            return {"kind": "status_literal", "col": col, "value": m.group(2), "raw": c[:200]}
    if re.search(r"\brownum\b", c, re.I):
        return {"kind": "rownum_limit", "raw": c[:100]}
    if re.search(r"\bis\s+not\s+null|\bis\s+null", c, re.I):
        return {"kind": "null_filter", "raw": c[:150]}
    if re.search(r"\bin\s*\(", c, re.I):
        return {"kind": "in_subset", "raw": c[:200]}
    return None


def resolve_obj(obj_str, alias_map_ctx, ctes):
    parts = [a or b for a, b in re.findall(r'"([^"]+)"|([\w$#]+)', obj_str)]
    parts = [p.upper() for p in parts]
    if not parts:
        return None
    if len(parts) == 1 and parts[0] in ctes:
        return {"kind": "cte", "name": parts[0]}
    schema = parts[-2] if len(parts) > 1 else None
    table = parts[-1]
    dep = alias_map_ctx.get("deploy")
    default_schema = {"DATA_CENTER": "ODS", "HIS": "HISUSER", "PATHOLOGY": "DBO",
                      "MOBILE_NURSING": "LUNA_MCS_SDSEY", "HRP": "HRPSEY656",
                      "INFECTION_SURVEILLANCE": "C##NIS5"}.get(dep)
    return {"kind": "table", "schema": schema or default_schema or "NONE", "table": table,
            "system": dep or "?"}


def analyze_file(relpath, category, deploy, view_names, sha, txt_raw):
    txt = strip_comments(txt_raw)
    ctes = set()
    for m in re.finditer(r"(?:\bwith|,)\s*([A-Za-z_][\w$#]*)\s+as\s*\(", txt, re.I):
        ctes.add(m.group(1).upper())
    out = {"file": relpath, "category": category, "deploy_system": deploy,
           "view": view_names[0] if view_names else "", "sha256": sha,
           "edges": [], "blocks": 0, "flags": {}, "lineage": [], "case_maps": []}
    # 顶层 UNION 分支
    body = txt
    mb = re.search(r"\bas\b", txt, re.I)  # CREATE VIEW x AS
    branches, _ = split_top(body, [r"\bunion\s+all\b", r"\bunion\b", r"\bminus\b", r"\bintersect\b"])
    out["flags"]["union_branches"] = max(len(branches), 1)
    out["flags"]["has_row_number"] = bool(re.search(r"row_number\s*\(\s*\)", txt, re.I))
    out["flags"]["has_group_by"] = bool(re.search(r"\bgroup\s+by\b", txt, re.I))
    out["flags"]["has_distinct"] = bool(re.search(r"\bselect\s+distinct\b", txt, re.I))
    out["flags"]["has_oracle_plus"] = "(+)" in txt
    all_others = []
    alias2obj = {}
    for bi, br in enumerate(branches):
        for fm in re.finditer(r"\bfrom\b", br, re.I):
            rest = br[fm.end():]
            # 段截止：下一个顶层 from / where / group / order / having / union（括号外）
            stop = None
            depth = 0
            in_str = False
            j = 0
            while j < len(rest):
                c = rest[j]
                if in_str:
                    if c == "'":
                        if j + 1 < len(rest) and rest[j + 1] == "'":
                            j += 2; continue
                        in_str = False
                    j += 1; continue
                if c == "'":
                    in_str = True; j += 1; continue
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                elif depth == 0:
                    mm = re.match(r"\b(from|where|group\s+by|order\s+by|having|union|minus|intersect)\b", rest[j:], re.I)
                    if mm:
                        stop = j
                        break
                j += 1
            seg = rest[:stop] if stop is not None else rest
            items = find_from_items("from" + seg)
            for it in items:
                ro = resolve_obj(it["obj"], {"deploy": deploy}, ctes)
                if it.get("subquery") and ro and ro.get("kind") == "table":
                    ro = {"kind": "subquery", "rep_table": ro["table"], "schema": ro["schema"],
                          "table": "(SUBQ:" + ro["table"] + ")", "system": ro["system"]}
                it["resolved"] = ro
                if it["alias"]:
                    alias2obj.setdefault(it["alias"].upper(), ro)
            out["blocks"] += 1
            # ANSI ON 条件
            for it in items:
                if it["on"]:
                    eqs, oth = parse_predicates(it["on"])
                    all_others += oth
                    for e in eqs:
                        out["edges"].append({"block": bi, "join_kw": it["join_kw"], "src": "on",
                                             "lhs": e["lhs"], "rhs": e["rhs"], "raw": e["raw"]})
        # WHERE
        wm = re.search(r"\bwhere\b", br, re.I)
        if wm:
            wtail = br[wm.end():]
            stop = None
            for kw in ("group by", "order by", "having", "union"):
                mm = re.search(rf"\b{kw}\b", wtail, re.I)
                if mm and (stop is None or mm.start() < stop):
                    stop = mm.start()
            wtext = wtail[:stop] if stop is not None else wtail
            eqs, others = parse_predicates(wtext)
            all_others += others
            for e in eqs:
                out["edges"].append({"block": bi, "join_kw": "WHERE", "src": "where",
                                     "lhs": e["lhs"], "rhs": e["rhs"],
                                     "plus_lhs": e.get("plus_lhs"), "plus_rhs": e.get("plus_rhs"),
                                     "raw": e["raw"]})
            # 子查询块：粗提取 IN (select...) / exists(select ...) / = (select ...)
            for sm in re.finditer(r"(?:\bin\b|\bexists\b|=)\s*\(\s*select\b", wtext, re.I):
                start = sm.end() - len(sm.group(0))
                depth, j = 0, start
                while j < len(wtext):
                    if wtext[j] == "(":
                        depth += 1
                    elif wtext[j] == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                sub = wtext[start:j + 1]
                for it in find_from_items(sub):
                    ro = resolve_obj(it["obj"], {"deploy": deploy}, ctes)
                    it["resolved"] = ro
                    if it["alias"]:
                        alias2obj.setdefault(it["alias"].upper(), ro)
                    out["edges"].append({"block": bi, "join_kw": "SUBQUERY", "src": "correlated",
                                         "sub_from": it["obj"], "raw": sub[:250]})
    # 限定条件
    quals = [q for q in (qualifier_of(c) for c in all_others) if q]
    out["qualifiers"] = quals
    out["alias_map"] = {k: ({"kind": v["kind"], "name": v.get("name"), "schema": v.get("schema"),
                             "table": v.get("table"), "system": v.get("system")} if v else None)
                        for k, v in alias2obj.items()}
    # SELECT 列血缘（首分支）
    sel = re.search(r"\bselect\b(.*?)\bfrom\b", branches[0], re.I | re.S) if branches else None
    if sel:
        items_sel, _ = split_top(sel.group(1), [r","])
        for it in items_sel:
            s = it.strip()
            expr, alias = None, None
            m = re.match(rf"(?s)(.*?)\s+as\s+([A-Za-z_][\w$#]*)\s*$", s, re.I)
            if m:
                expr, alias = m.group(1), m.group(2)
            else:
                m2 = re.match(rf"({IDENT})\s*$", s)
                if m2:
                    expr, alias = s, m2.group(1).split(".")[-1]
            if alias:
                out["lineage"].append({"target": alias.upper(), "expr": (expr or s)[:400]})
    # CASE 映射（值域线索）
    for cm in re.finditer(r"when\s+'([^']*)'\s+then\s+'([^']*)'", txt, re.I):
        out["case_maps"].append({"when": cm.group(1), "then": cm.group(2)})
    return out


def main():
    VV = json.load(open(os.path.join(RUN_DIR, "view_versions.json"), encoding="utf-8"))
    D = json.load(open(os.path.join(RUN_DIR, "s1_excel_and_74rows.json"), encoding="utf-8"))
    rows_74 = {r["view"].upper(): r for r in D["rows_74"]}
    ORIGIN2SYS = {"ods_8_216": "DATA_CENTER", "his_source_10_10_10_15": "HIS",
                  "mobile_nursing_oracle_10_10_10_125": "MOBILE_NURSING",
                  "pathology_sqlserver_10_10_9_41": "PATHOLOGY", "hrp_10_10_10_23": "HRP"}
    OWNER2SYS = {"ODS": "DATA_CENTER", "LUNA_MCS_SDSEY": "MOBILE_NURSING", "HISUSER": "HIS",
                 "DBO": "PATHOLOGY", "HRPSEY656": "HRP", "C##NIS5": "INFECTION_SURVEILLANCE",
                 "C##FXPT": "INFECTION_SURVEILLANCE"}
    results = []
    for f in VV["sql_files"]:
        if f["category"] not in ("root_main", "root_jhemr_draft"):
            continue
        vowner = None
        for vn in f["view_names"]:
            if "." in vn:
                vowner = vn.split(".")[0].strip('"').upper(); break
        dep = OWNER2SYS.get(vowner) if vowner else None
        vname0 = f["view_names"][0].split(".")[-1].strip('"').upper() if f["view_names"] else ""
        if not dep:
            r74 = rows_74.get(vname0)
            if r74 and r74["origin"]:
                src = r74["origin"].split(":", 1)[1].split("__", 1)[0]
                dep = ORIGIN2SYS.get(src)
                if not dep and r74["origin"].startswith("history:"):
                    dep = "HISTORY_UNRESOLVED"
        txt = read_any(os.path.join(PKG, f["relpath"]))
        results.append(analyze_file(f["relpath"], f["category"], dep or "?", f["view_names"], f["sha256"], txt))
    json.dump({"generated_at": datetime.now().isoformat(), "parser": "heuristic_v1", "files": results},
              open(os.path.join(RUN_DIR, "relation_candidates_raw.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 汇总
    nfiles = len(results)
    nedge = sum(len(r["edges"]) for r in results)
    nline = sum(len(r["lineage"]) for r in results)
    ncase = sum(len(r["case_maps"]) for r in results)
    print(f"files={nfiles} edges(raw)={nedge} lineage_items={nline} case_maps={ncase}")
    from collections import Counter
    print("join_kw dist:", dict(Counter(e["join_kw"] for r in results for e in r["edges"])))
    print("union>1 files:", sum(1 for r in results if r["flags"]["union_branches"] > 1))
    print("has(+) files:", sum(1 for r in results if r["flags"]["has_oracle_plus"]))
    print("row_number files:", sum(1 for r in results if r["flags"]["has_row_number"]))


if __name__ == "__main__":
    main()
