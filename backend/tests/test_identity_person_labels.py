from app.services.identity_person_labels import (
    classification_label,
    employment_label,
    person_type_label,
)


def test_employment_status_is_chinese():
    assert employment_label("active") == "在职"
    assert employment_label("inactive") == "停用"
    assert employment_label("unknown") == "未标注"
    assert employment_label(None) == "未标注"


def test_person_type_formal_is_not_doctor():
    assert person_type_label("formal") == "正式"
    assert person_type_label("temporary") == "临时"
    assert classification_label("doctor") == "医生"
    assert classification_label("nurse") == "护士"
    assert classification_label("pharmacist") == "药师"
