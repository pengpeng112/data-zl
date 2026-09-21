"""193 B17 性能实测（隔离库，合成基准）。

仅记录实测数字（吞吐/耗时），不宣称 SLO——SLO 目标值按 193 §7 需 B18 前业务确认。
产物写入 output_r193/B17/perf_benchmark.json。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.dataset import AssetDsClassification, AssetDsDataset, AssetDsDatasetVersion, AssetDsGrant, AssetDsFact
from app.services import dataset_pipeline as pipe
from app.services import dataset_products as prod
from app.services import dataset_security as sec

OUT = Path(__file__).resolve().parents[3] / "开发起步包" / "output_r193" / "B17"
OUT.mkdir(parents=True, exist_ok=True)

N_PATIENTS = 200
FACTS_PER_PATIENT = 15  # 3000 facts


def test_b17_perf_benchmark():
    db = SessionLocal()
    report: dict = {"started_at": datetime.now(timezone.utc).isoformat(),
                    "scale": {"patients": N_PATIENTS, "facts_per_patient": FACTS_PER_PATIENT},
                    "env": "isolated data_asset_test via SSH tunnel"}
    try:
        # --- 造数据：3000 事实分 10 批 ---
        t0 = time.perf_counter()
        all_records = []
        for p in range(N_PATIENTS):
            pid = f"PF{p:04d}"
            for k in range(FACTS_PER_PATIENT):
                kind = "visit" if k % 5 == 0 else "diagnosis"
                day = 1 + (k % 28)
                ts = f"2026-01-{day:02d}T08:00:00+00:00"
                all_records.append({
                    "fact_key": f"PF:{pid}:{kind}:{k}", "fact_kind": kind,
                    "source_patient_key": pid,
                    "original_value_ref": f"ref/{pid}/{k}",
                    "standard_value": "I50.x00" if kind == "diagnosis" else None,
                    "business_time": ts, "available_time": ts})
        chunk = len(all_records) // 10
        for ci in range(0, len(all_records), chunk):
            pipe.ingest_batch(db, f"RUN-PERF-{ci // chunk}", "SYNTH_PERF", "o",
                              all_records[ci:ci + chunk], "rules_v1")
            db.commit()
        t_ingest = time.perf_counter() - t0
        report["ingest_3000_facts_s"] = round(t_ingest, 2)
        report["ingest_throughput_facts_per_s"] = round(len(all_records) / t_ingest, 1)

        # 幂等重跑（全量 skip 的开销）
        t0 = time.perf_counter()
        r = pipe.ingest_batch(db, "RUN-PERF-0", "SYNTH_PERF", "o",
                              all_records[:chunk], "rules_v1")
        db.commit()
        t_rerun = time.perf_counter() - t0
        assert r["written"] == 0
        report["rerun_skip_300_s"] = round(t_rerun, 2)

        # --- 分类+授权+网关单次判定 ---
        db.add(AssetDsClassification(
            object_type="dataset_version", object_ref="dataset:PERF:1",
            labels={"protection_level": "P3", "personal_info": "personal",
                    "usage_constraints": {"purposes": ["perf"]}},
            protection_level="P3", version=1))
        db.add(AssetDsGrant(principal="perfuser", purpose_code="perf",
                            resource_type="dataset_version", resource_ref="dataset:PERF:1",
                            operations=["read", "export", "train"], legal_basis_ref="t",
                            approved_by="op"))
        db.commit()
        t0 = time.perf_counter()
        n_ok = 0
        for _ in range(50):
            g = sec.enforce_read(db, "perfuser", "perf", "dataset:PERF:1")
            n_ok += 1 if g.allowed else 0
        t_gate = time.perf_counter() - t0
        assert n_ok == 50
        report["gateway_50_checks_s"] = round(t_gate, 3)
        report["gateway_ms_per_check"] = round(t_gate / 50 * 1000, 2)

        # --- 单患者时间线 ---
        sample_pid = pipe.deterministic_patient_id("SYNTH_PERF", "PF0100")
        t0 = time.perf_counter()
        tl = prod.patient_timeline(db, sample_pid)
        t_tl = time.perf_counter() - t0
        assert tl["count"] == FACTS_PER_PATIENT
        report["timeline_1patient_15events_ms"] = round(t_tl * 1000, 1)

        # --- 再入院统计（全量扫描 3000 事实） ---
        t0 = time.perf_counter()
        stats = prod.readmission_rate(db)
        t_stats = time.perf_counter() - t0
        report["stats_readmission_3000facts_s"] = round(t_stats, 2)
        report["stats_result"] = {"denominator": stats["denominator_patients"],
                                  "readmitted": stats["readmitted_patients"]}

        # --- 训练集构建（200 患者分组+泄漏断言） ---
        t0 = time.perf_counter()
        ts = prod.build_training_set(db, 1, cfg=prod.SplitConfig(seed=193))
        t_train = time.perf_counter() - t0
        assert ts["data_card"]["total_patients"] == N_PATIENTS
        report["training_set_200patients_s"] = round(t_train, 2)

        # --- 冻结清单（全量 digest） ---
        db.add(AssetDsDataset(dataset_code="PERF", title="perf", purpose_code="perf",
                              latest_version_id=1))
        db.add(AssetDsDatasetVersion(id=1, dataset_id=1, version=1))
        db.commit()
        t0 = time.perf_counter()
        pipe.freeze_version(db, 1)
        db.commit()
        t_freeze = time.perf_counter() - t0
        report["freeze_manifest_3000facts_s"] = round(t_freeze, 2)

        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["note"] = ("合成基准、经 SSH 隧道（含网络往返）；SLO 阈值待 B18 前业务确认，"
                          "本数字仅作容量参考基线")
        (OUT / "perf_benchmark.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=1))
    finally:
        db.rollback()
        db.close()
