"""fancyhis T2/T3: dnfile scan of Fancy.His.Micro.dll.

T2 - JHApi Refit surfaces: locate the five JHApi interfaces and every
      TypeDef whose namespace contains ThirdOpenApi.JHApi; dump custom
      attribute constructor names (Refit Get/Post/route hints) plus any
      http(s) strings living in the string heap near those types.
T3 - entity/namespace inventory: TypeDef counts by namespace root, plus
      Repository/Domain types matched (case-insensitive, ignoring
      underscores) against the T1 SQL table tokens.
Read-only; no decryption, no execution.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import dnfile

DLL = Path(r"E:\fancyhis\HisApi\HisApi\Fancy.His.Micro.dll")
SQL_DICT = Path(r"F:\python\数据资产\开发起步包\数据资产_新HIS逆向资产包\fancyhis_sql_dictionary.json")
OUT_DIR = Path(r"F:\python\数据资产\开发起步包\数据资产_新HIS逆向资产包")

JH_INTERFACES = {
    "IInPatientManager", "IIPCOrderManager", "IJHPubManager",
    "ITermManager", "IInPatientEsbManager",
}


def norm_name(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def main() -> int:
    pe = dnfile.dnPE(DLL)

    # ---- TypeDef inventory ----
    types = []
    for row in pe.net.mdtables.TypeDef.rows:
        ns = str(row.TypeNamespace or "")
        name = str(row.TypeName or "")
        types.append((ns, name))

    ns_roots = Counter(ns.split(".")[0] + ("." + ns.split(".")[1] if ns.count(".") >= 1 and ns.split(".")[0] == "Fancy" else "") for ns, _ in types)

    # ---- T2: JHApi types ----
    jh_types = [(ns, name) for ns, name in types if "JHApi" in ns or name in JH_INTERFACES]
    jh_detail = []
    attr_rows = pe.net.mdtables.CustomAttribute
    # map MethodDef/TypeDef row indexes to attribute constructor names
    type_attrs: dict[int, set[str]] = defaultdict(set)
    method_attrs: dict[int, set[str]] = defaultdict(set)
    for ca in attr_rows.rows:
        parent = ca.Parent
        target_idx = None
        table_name = getattr(parent, "table", None)
        if table_name is not None:
            target_idx = parent.row_index
        ctor = ca.Value
        ctor_name = ""
        try:
            ctor_row = ctor.row
            parent_type = ctor_row.Class.row
            ctor_name = str(getattr(parent_type, "TypeName", "") or "")
        except Exception:
            ctor_name = ""
        if not ctor_name:
            continue
        tn = getattr(table_name, "name", "") if table_name is not None else ""
        if tn == "TypeDef" and target_idx:
            type_attrs[target_idx].add(ctor_name)
        elif tn == "MethodDef" and target_idx:
            method_attrs[target_idx].add(ctor_name)

    # method name list per JH type (for route correlation)
    methods_of_type: dict[int, list[str]] = defaultdict(list)
    for idx, row in enumerate(pe.net.mdtables.MethodDef.rows, start=1):
        # MethodDef rows are flat; we cannot easily map owner without resolving
        # the TypeDef method list ranges - approximate via name only below.
        pass

    for idx, row in enumerate(pe.net.mdtables.TypeDef.rows, start=1):
        ns = str(row.TypeNamespace or "")
        name = str(row.TypeName or "")
        if "JHApi" not in ns and name not in JH_INTERFACES:
            continue
        jh_detail.append({
            "namespace": ns,
            "type": name,
            "attributes": sorted(type_attrs.get(idx, set())),
        })

    # http strings from heap for JH context
    data = DLL.read_bytes()
    utf16 = [m.group().decode("utf-16-le") for m in re.finditer(rb"(?:[\x20-\x7e]\x00){6,}", data)]
    http_strings = sorted({s for s in utf16 if re.search(r"https?://", s)})
    route_strings = sorted({s for s in utf16 if re.match(r"^/?[A-Za-z][A-Za-z0-9_/\-{}]{4,60}$", s) and ("/" in s) and "{" not in s[:1]})

    # ---- T3: entity/repo match against SQL table tokens ----
    sql_dict = json.loads(SQL_DICT.read_text(encoding="utf-8"))
    table_tokens = {t["table"]: norm_name(t["table"]) for t in sql_dict["tables"]}
    token_by_norm = {v: k for k, v in table_tokens.items()}

    repo_types = [(ns, name) for ns, name in types if re.search(r"(Repositories|Domain|Entity|Entities)", ns, re.I)]
    entity_matches = []
    matched_tables = set()
    for ns, name in repo_types:
        norm = norm_name(name)
        if norm in token_by_norm:
            entity_matches.append({"namespace": ns, "entity": name, "table": token_by_norm[norm]})
            matched_tables.add(token_by_norm[norm])

    result = {
        "typedef_total": len(types),
        "namespace_roots_top": dict(ns_roots.most_common(20)),
        "jh_types_total": len(jh_types),
        "jh_interfaces_found": sorted({name for _, name in jh_types if name in JH_INTERFACES}),
        "jh_type_details": jh_detail,
        "http_strings": http_strings,
        "route_like_strings_sample": route_strings[:120],
        "repo_domain_type_total": len(repo_types),
        "entity_table_matches": entity_matches,
        "tables_matched": len(matched_tables),
        "tables_total": len(table_tokens),
    }
    out_path = OUT_DIR / "fancyhis_dnfile_scan.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "typedef_total": result["typedef_total"],
        "jh_types_total": result["jh_types_total"],
        "jh_interfaces_found": result["jh_interfaces_found"],
        "http_strings_count": len(http_strings),
        "http_strings": http_strings[:15],
        "repo_domain_type_total": result["repo_domain_type_total"],
        "entity_table_matches": result["entity_table_matches"][:10],
        "tables_matched": result["tables_matched"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
