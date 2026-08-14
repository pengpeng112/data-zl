from app.services.identity_dept_labels import dept_status_label, dept_type_label, infer_parent_dept_code


def test_his_dept_type_uses_official_names():
    assert dept_type_label("0") == "门诊"
    assert dept_type_label("1") == "住院"
    assert dept_type_label("2") == "门诊住院"
    assert dept_type_label("9") == "其他"
    assert dept_type_label("3") == "医技"


def test_dept_status_is_chinese():
    assert dept_status_label("active") == "启用"
    assert dept_status_label("inactive") == "停用"


def test_parent_code_follows_his_hierarchy():
    assert infer_parent_dept_code("01") is None
    assert infer_parent_dept_code("0101") == "01"
    assert infer_parent_dept_code("010101") == "0101"
