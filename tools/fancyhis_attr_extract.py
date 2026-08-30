"""fancyhis T2/T3 core: CustomAttribute blob extraction.

- Table(Name="...") attributes on TypeDefs  -> precise entity->table mapping
- Refit HTTP method attributes on MethodDefs -> routes; scoped to JHApi
  namespaces plus a global count for context
Read-only against the DLL copy.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import dnfile

DLL = Path(r"E:\fancyhis\HisApi\HisApi\Fancy.His.Micro.dll")
OUT_DIR = Path(r"F:\python\数据资产\开发起步包\数据资产_新HIS逆向资产包")

ASCII_RUN = re.compile(rb"[\x20-\x7e]{2,120}")
HTTP_ATTR_NAMES = {"Get", "GetAttribute", "Post", "PostAttribute", "Put", "PutAttribute",
                   "Delete", "DeleteAttribute", "Patch", "PatchAttribute", "HttpMethodAttribute"}
TABLE_ATTR_NAMES = {"Table", "TableAttribute", "NameAttribute"}


def ctor_name(ca_row) -> str:
    try:
        member = ca_row.Type.row
        parent = member.Class.row
        return str(getattr(parent, "TypeName", "") or "")
    except Exception:
        return ""


def blob_strings(ca_row) -> list[str]:
    try:
        raw = ca_row.Value.value
    except Exception:
        return []
    if not isinstance(raw, (bytes, bytearray)):
        return []
    return [m.group().decode("ascii", "replace") for m in ASCII_RUN.finditer(raw)]


def normalize_route(value: str | None) -> str | None:
    """Remove CustomAttribute blob marker bytes before a Refit route."""
    if not value:
        return None
    slash = value.find("/")
    if slash < 0:
        return None
    route = value[slash:].strip()
    return route if re.match(r"^/[A-Za-z0-9_{}?&=./:-]+$", route) else None


def main() -> int:
    pe = dnfile.dnPE(DLL)

    typedefs = pe.net.mdtables.TypeDef.rows
    method_owner: dict[int, tuple[int, str, str]] = {}
    for td_idx, row in enumerate(typedefs, start=1):
        ns = str(row.TypeNamespace or "")
        name = str(row.TypeName or "")
        for method in row.MethodList:
            try:
                md_idx = method.row_index
            except Exception:
                continue
            method_owner[md_idx] = (td_idx, ns, name)

    method_names: dict[int, str] = {}
    for md_idx, row in enumerate(pe.net.mdtables.MethodDef.rows, start=1):
        method_names[md_idx] = str(row.Name or "")

    table_attrs = []
    http_attrs = []
    http_attr_other_count = defaultdict(int)

    for ca in pe.net.mdtables.CustomAttribute.rows:
        cname = ctor_name(ca)
        if not cname:
            continue
        parent = ca.Parent
        try:
            table = parent.table.name
            row_index = parent.row_index
        except Exception:
            continue
        strings = blob_strings(ca)

        if cname in TABLE_ATTR_NAMES and table == "TypeDef":
            try:
                td = typedefs[row_index - 1]
            except Exception:
                continue
            # named-arg blobs lead with the property name ("Name"); the value follows
            candidates = [s for s in strings if s not in {"Name", "Name="} and re.match(r"^[A-Za-z_][A-Za-z0-9_$#]*(\.[A-Za-z_][A-Za-z0-9_$#]*)?$", s)]
            table_name = candidates[0] if candidates else None
            if table_name:
                table_attrs.append({
                    "namespace": str(td.TypeNamespace or ""),
                    "entity": str(td.TypeName or ""),
                    "table": table_name,
                })

        elif cname in HTTP_ATTR_NAMES:
            verb = cname.replace("Attribute", "")
            route = next(
                (normalized for s in strings if (normalized := normalize_route(s))),
                None,
            )
            if table == "MethodDef" and row_index in method_owner:
                td_idx, ns, tname = method_owner[row_index]
                entry = {
                    "namespace": ns, "type": tname,
                    "method": method_names.get(row_index, ""),
                    "verb": verb, "route": route,
                }
                if "JHApi" in ns or tname in {"IInPatientManager", "IIPCOrderManager", "IJHPubManager", "ITermManager", "IInPatientEsbManager"}:
                    http_attrs.append(entry)
                else:
                    http_attr_other_count[ns.split(".")[0] if ns else "?"] += 1

    result = {
        "table_attribute_count": len(table_attrs),
        "table_attributes": table_attrs,
        "jh_route_count": len(http_attrs),
        "jh_routes": http_attrs,
        "other_http_attr_by_root": dict(http_attr_other_count),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "fancyhis_attributes.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "table_attribute_count": len(table_attrs),
        "sample_tables": table_attrs[:15],
        "jh_route_count": len(http_attrs),
        "jh_routes_sample": http_attrs[:20],
        "other_http_attr_by_root": dict(http_attr_other_count),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
