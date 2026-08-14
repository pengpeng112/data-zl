from app.services.relation_metrics import (
    classify_relation_scene,
    hit_rate_tone,
    mixed_relation_hint,
    parse_relation_metrics,
    scene_label,
)


def test_parse_semicolon_orphan_percent():
    parsed = parse_relation_metrics("total=575487; orphan=3; orphan_rate=0.0005%")
    assert parsed["sample_size"] == 575487
    assert parsed["missed"] == 3
    assert parsed["orphan_rate"] == 0.000005
    assert parsed["hit_rate"] == 0.999995


def test_parse_json_match_rate():
    parsed = parse_relation_metrics('{"sampled": 10000, "matched": 9994, "match_rate": 0.9994}')
    assert parsed["sample_size"] == 10000
    assert parsed["matched"] == 9994
    assert parsed["hit_rate"] == 0.9994
    assert parsed["orphan_rate"] == 0.0006


def test_parse_his_source_sample_zero_orphan():
    parsed = parse_relation_metrics("his_source_sample=20000; orphan=0")
    assert parsed["sample_size"] == 20000
    assert parsed["missed"] == 0
    assert parsed["hit_rate"] == 1.0


def test_parse_miss_and_percent_hit():
    parsed = parse_relation_metrics("his_source n=20451 miss=6971 hit=65.9%")
    assert parsed["sample_size"] == 20451
    assert parsed["missed"] == 6971
    assert parsed["hit_rate"] == 0.659


def test_parse_ratio_keys():
    parsed = parse_relation_metrics("detail_rows=768942; matched_visit_keys=1996/2000")
    assert parsed["sample_size"] == 2000
    assert parsed["matched"] == 1996
    assert parsed["hit_rate"] == 0.998


def test_exam_lab_scene_split():
    assert classify_relation_scene(rel_id=553) == "exam_inpatient"
    assert classify_relation_scene(rel_id=554) == "exam_outpatient"
    assert classify_relation_scene(rel_id=555) == "lab_inpatient"
    assert classify_relation_scene(rel_id=556) == "lab_outpatient"
    exam = mixed_relation_hint(14)
    assert exam is not None
    assert "553" in exam["already_split_to"]
    assert mixed_relation_hint(16)["already_split_to"].startswith("555")
    assert mixed_relation_hint(553) is None
    assert scene_label("lab_outpatient") == "检验·门诊"
    assert classify_relation_scene(
        from_table="EXAM.EXAM_MASTER",
        to_table="OUTPBILL.OUTP_RCPT_MASTER",
        from_columns="RCPT_NO",
        join_condition="NVL(VISIT_ID,0)=0",
        note="门诊收据",
    ) == "exam_outpatient"
    assert hit_rate_tone(0.999) == "success"
    assert hit_rate_tone(0.66) == "danger"
