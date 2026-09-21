# -*- coding: utf-8 -*-
"""S1 全量文件清点：遍历 195 输入包，计算 SHA-256、检测编码、分类、敏感检查。
只读操作，不执行包内任何程序。产物：source_manifest.json + 汇总(打印)。
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime

ROOT = r"D:\Users\Administrator\Desktop\三甲复审\6、数管中心三甲数据上报\数据接口规范+值域2.3"
OUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEXT_EXTS = {".sql", ".txt", ".md", ".py", ".json", ".csv", ".log", ".xml", ".ini", ".cfg", ".yml", ".yaml", ".js", ".html"}
BIN_EXTS = {".docx", ".xlsx", ".xls", ".rar", ".png", ".jpg", ".zip", ".doc", ".pdf", ".dll", ".exe", ".jar", ".chm"}

SENSITIVE_PAT = re.compile(
    r"(password|passwd|pwd|密码|口令|secret|token)\s*[:=]\s*\S+", re.IGNORECASE)


def detect_encoding(path):
    """返回 (encoding, decode_ok, has_replacement)"""
    raw = open(path, "rb").read(4 * 1024 * 1024)  # 前4MB足够判断
    if raw.startswith(b"\xef\xbb\xbf"):
        enc = "utf-8-sig"
    elif raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        enc = "utf-16"
    else:
        enc = None
    for cand in ([enc] if enc else []) + ["utf-8", "gbk", "utf-16"]:
        if not cand:
            continue
        try:
            txt = raw.decode(cand)
            return cand, True, ("\ufffd" in txt)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "unknown", False, True


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def category_of(rel):
    p = rel.replace("\\", "/")
    low = p.lower()
    if low.startswith("三甲完成视图/备份_20260914活库原样/"):
        return "live_backup_20260914"
    if low.startswith("三甲完成视图/history/"):
        return "history"
    if low.startswith("三甲完成视图/"):
        base = p.split("/", 1)[1]
        if base.lower().endswith("_jhemr.sql"):
            return "root_jhemr_draft"
        return "root_main"
    if low.startswith("governance/"):
        return "governance"
    if low.startswith("普通值域/"):
        return "value_domain_ref"
    if low.startswith("无用文件归档/"):
        return "archived_ignore"
    if low.startswith("scripts/"):
        return "pkg_scripts_do_not_run"
    if low.startswith("skills/"):
        return "pkg_skills_ref"
    return "root_misc"


def main():
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT)
            st = os.stat(full)
            ext = os.path.splitext(fn)[1].lower()
            entry = {
                "relpath": rel,
                "bytes": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "sha256": sha256_file(full),
                "ext": ext,
                "category": category_of(rel),
            }
            if ext in TEXT_EXTS and st.st_size < 50 * 1024 * 1024:
                enc, ok, repl = detect_encoding(full)
                entry["encoding"] = enc
                entry["decode_ok"] = ok
                entry["replacement_char"] = repl
                if ext in {".log", ".txt", ".py", ".md", ".sql"}:
                    try:
                        txt = open(full, "r", encoding=enc if ok else "latin-1", errors="ignore").read()
                        hits = SENSITIVE_PAT.findall(txt)
                        entry["sensitive_scan"] = "hit:" + str(len(hits)) if hits else "clean"
                    except Exception as e:
                        entry["sensitive_scan"] = "error:" + type(e).__name__
            elif ext in BIN_EXTS:
                entry["encoding"] = "binary"
            else:
                entry["encoding"] = "n/a"
            entry["included"] = True  # 默认纳入清单；排除原因在 S1 分析层标注
            files.append(entry)

    files.sort(key=lambda x: x["relpath"].lower())
    out = {
        "root": ROOT,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": len(files),
        "files": files,
    }
    with open(os.path.join(OUT_DIR, "source_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # 汇总
    from collections import Counter
    cat = Counter(x["category"] for x in files)
    ext = Counter(x["ext"] for x in files)
    print("total:", len(files))
    print("by category:", dict(cat))
    print("by ext:", dict(ext.most_common(20)))
    dec_bad = [x["relpath"] for x in files if not x.get("decode_ok", True)]
    print("decode_fail:", len(dec_bad), dec_bad[:10])
    sens = [x["relpath"] for x in files if str(x.get("sensitive_scan", "")).startswith("hit")]
    print("sensitive_hit:", len(sens), sens[:10])


if __name__ == "__main__":
    sys.exit(main())
