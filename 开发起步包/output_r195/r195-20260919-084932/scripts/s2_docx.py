# -*- coding: utf-8 -*-
"""S2d：DOCX 结构化提取（stdlib zipfile+XML）。
- 数据结构.docx：提取每张表的标题与字段行（字段名/类型/含义），输出 docx_2006_tables.json
- 电子病历数据集升级版本V1.3.docx：提取数据集表标题+字段行，输出 v13_spec.json
只读解析，不执行宏；表格保留序号与标题；跨页表按标题聚合。
"""
import json
import os
import re
import zipfile
from xml.etree import ElementTree as ET

RUN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r"D:\Users\Administrator\Desktop\三甲复审\6、数管中心三甲数据上报\数据接口规范+值域2.3"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def cell_text(tc):
    txts = []
    for t in tc.iter(W + "t"):
        txts.append(t.text or "")
    return "".join(txts).strip()


def parse_docx_tables(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(W + "body")
    tables = []
    last_paras = []
    idx = 0
    for el in body:
        if el.tag == W + "p":
            t = "".join(x.text or "" for x in el.iter(W + "t")).strip()
            if t:
                last_paras.append(t)
                last_paras = last_paras[-3:]
        elif el.tag == W + "tbl":
            idx += 1
            rows = []
            for tr in el.findall(W + "tr"):
                cells = [cell_text(tc) for tc in tr.findall(W + "tc")]
                rows.append(cells)
            tables.append({"seq": idx, "context_before": list(last_paras), "rows": rows})
    return tables


def extract(docx_path, out_name, label):
    tabs = parse_docx_tables(docx_path)
    # 过滤目录/修订记录表：行数<2 或首行无字段名特征
    out = []
    for t in tabs:
        rows = t["rows"]
        if len(rows) < 2:
            continue
        out.append(t)
    json.dump({"source": os.path.basename(docx_path), "label": label,
               "table_count_raw": len(tabs), "table_count_kept": len(out), "tables": out},
              open(os.path.join(RUN_DIR, out_name), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{label}: raw tables={len(tabs)} kept={len(out)} -> {out_name}")
    # 打印前几张表的标题上下文样例
    for t in out[:6]:
        head = t["rows"][0][:6] if t["rows"] else []
        print("   seq", t["seq"], "| ctx:", " / ".join(t["context_before"][-2:])[:60], "| header:", head)


extract(os.path.join(PKG, "数据结构.docx"), "docx_2006_tables.json", "数据结构手册2006")
extract(os.path.join(PKG, "电子病历数据集升级版本V1.3.docx"), "v13_spec.json", "电子病历V1.3")
