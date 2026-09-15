"""189 降级回归：目标账号缺 users_subsign.default_flag 列级 UPDATE 权限时，
模板补齐照常，仅存量默认方式修复（fix_default）被跳过。纯逻辑，不连库。"""

from __future__ import annotations

from app.services.identity_login_sign_sync import build_login_sign_plan


def _plan(**kwargs):
    args = dict(
        expected={"E1"},
        target_users={"E1"},
        control_users=set(),
        logins={"E1": {"0"}},
        signs={"E1": {"0"}},
        defaults={},
    )
    args.update(kwargs)
    return build_login_sign_plan(**args)


def test_default_repair_runs_when_allowed():
    plan = _plan(allow_default_repair=True)
    assert plan["repairs"][0]["fix_default"] is True


def test_default_repair_skipped_when_privilege_missing():
    plan = _plan(allow_default_repair=False)
    assert all(item["fix_default"] is False for item in plan["repairs"])


def test_template_insert_default_flag_unaffected_by_degradation():
    # 全空账号：模板 INSERT 在 way 0 上带 default_flag=1，与降级开关无关。
    plan = _plan(
        control_users=set(),
        logins={},
        signs={},
        defaults={},
        allow_default_repair=False,
    )
    item = plan["repairs"][0]
    way0 = next(s for s in item["sign_ways"] if s["sign_way"] == "0")
    assert way0["default_flag"] == "1"
    assert item["fix_default"] is False
