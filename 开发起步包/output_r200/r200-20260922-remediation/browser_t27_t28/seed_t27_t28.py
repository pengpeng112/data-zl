# -*- coding: utf-8 -*-
"""T27/T28 浏览器闭环种子（隔离库 data_asset_test，经 dev_env.sh 隧道）。

用法（仓库根）：
  source tools/dev_env.sh >/dev/null 2>&1
  cd backend && PYTHONPATH=. ./.venv/Scripts/python.exe \
    "../开发起步包/output_r200/r200-20260922-remediation/browser_t27_t28/seed_t27_t28.py"

幂等：已存在的用户/角色/码表项/假源跳过。只写 asset schema，不触业务源库。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, select  # noqa: E402


def main() -> int:
    url = os.environ.get("APP_TEST_DB_URL", "")
    if "test" not in url.lower():
        print("[seed] 拒绝：APP_TEST_DB_URL 未标识测试库")
        return 2
    eng = create_engine(url)

    from app.models import auth as mauth
    from app.models import governance_base as mgb
    from app.models import dict_medical as mdm
    from app.models.asset_system import AssetDataSource, AssetSystem
    from app.api.v1.permissions import ROLE_DEFAULT_PERMISSIONS
    from app.services import auth_service

    PW = {"qa_t27_maint": "T27Seed#M1", "qa_t27_approver": "T27Seed#A2",
          "qa_t27_viewer": "T27Seed#V3", "qa_t27_admin": "T27Seed#P0"}

    with eng.begin() as conn:
        pass  # 连通性预热

    from sqlalchemy.orm import Session
    with Session(eng) as db:
        # 1) RBAC：角色 + 权限（action=access，DEF-05 口径）
        for r in [
            {"role_code": c, "role_name_cn": c, "role_type": "builtin"}
            for c in ROLE_DEFAULT_PERMISSIONS
        ]:
            if not db.query(mgb.AssetRole).filter_by(role_code=r["role_code"]).first():
                db.add(mgb.AssetRole(**r))
        db.flush()
        for role_code, perms in ROLE_DEFAULT_PERMISSIONS.items():
            existing = {p.resource for p in db.query(mgb.AssetRolePermission).filter_by(role_code=role_code).all()}
            for code in perms:
                if code not in existing:
                    db.add(mgb.AssetRolePermission(role_code=role_code, resource=code, action="access"))
        db.commit()
        print("[seed] RBAC ok")

        # 2) 用户
        for username, roles in [
            ("qa_t27_maint", ["dict_admin"]),
            ("qa_t27_approver", ["dict_admin"]),
            ("qa_t27_viewer", ["asset_viewer"]),
            ("qa_t27_admin", ["platform_admin"]),
        ]:
            if not db.query(mauth.AuthUser).filter_by(username=username).first():
                u = auth_service.create_local_user(
                    db, username=username, password=PW[username],
                    user_identifier=username, must_change_password=False)
                print(f"[seed] user {username} created id={u.id}")
            for r in roles:
                if not db.query(mgb.AssetUserRole).filter_by(user_identifier=username, role_code=r).first():
                    db.add(mgb.AssetUserRole(user_identifier=username, role_code=r))
        db.commit()
        print("[seed] users ok")

        # 2b) 202 D201-01 职责分离自定义角色（仅隔离库；D2-2 四身份核对用）
        SPLIT_ROLES = {
            "dict_plan_creator": ("字典计划创建员", ["dict", "dict.medical.view", "dict.medical.plan.create"]),
            "dict_approver_only": ("字典审核员（仅审批）", ["dict", "dict.medical.view", "dict.medical.approve"]),
            "dict_executor": ("字典执行运维员", ["dict", "dict.medical.view", "dict.medical.execute",
                                                  "dict.medical.retry", "dict.medical.reconcile"]),
            "ai_context_pilot": ("AI 上下文试点", ["ai.context.read"]),
        }
        for code, (name_cn, perms) in SPLIT_ROLES.items():
            if not db.query(mgb.AssetRole).filter_by(role_code=code).first():
                db.add(mgb.AssetRole(role_code=code, role_name_cn=name_cn, role_type="custom"))
        db.flush()
        for code, (_name_cn, perms) in SPLIT_ROLES.items():
            existing = {p.resource for p in db.query(mgb.AssetRolePermission).filter_by(role_code=code).all()}
            for p in perms:
                if p not in existing:
                    db.add(mgb.AssetRolePermission(role_code=code, resource=p, action="access"))
        SPLIT_USERS = {
            "qa_t27_creator": (["dict_plan_creator"], "T27Seed#C4"),
            "qa_t27_approver2": (["dict_approver_only"], "T27Seed#B5"),
            "qa_t27_executor": (["dict_executor"], "T27Seed#E6"),
            "qa_t27_aipilot": (["ai_context_pilot"], "T27Seed#I7"),
        }
        for username, (roles, pw) in SPLIT_USERS.items():
            if not db.query(mauth.AuthUser).filter_by(username=username).first():
                auth_service.create_local_user(
                    db, username=username, password=pw,
                    user_identifier=username, must_change_password=False)
            for r in roles:
                if not db.query(mgb.AssetUserRole).filter_by(user_identifier=username, role_code=r).first():
                    db.add(mgb.AssetUserRole(user_identifier=username, role_code=r))
        db.commit()
        print("[seed] split roles ok")

        # 3) 诊断码表项（canonical 码表，供 v3 快照解析）
        local_set = "diagnosis_local_clinical"
        for code, name in [
            ("QA_T27D01", "T27测试诊断甲"),
            ("QA_T27D02", "T27测试诊断乙"),
        ]:
            if not db.scalar(select(mdm.DictMedicalCodeItem).where(
                    mdm.DictMedicalCodeItem.code_set_code == local_set,
                    mdm.DictMedicalCodeItem.item_code == code)):
                db.add(mdm.DictMedicalCodeItem(
                    category_code="diagnosis", code_set_code=local_set,
                    item_code=code, item_name_cn=name, status="active", extra={}))
            for to_set, to_code, to_name in [
                ("diagnosis_national_clinical_v2", "N27.01", "国标测试一"),
                ("diagnosis_insurance_v2", "Y27.01", "医保测试一"),
            ]:
                if not db.scalar(select(mdm.DictMedicalCodeMapping).where(
                        mdm.DictMedicalCodeMapping.category_code == "diagnosis",
                        mdm.DictMedicalCodeMapping.from_code_set == local_set,
                        mdm.DictMedicalCodeMapping.from_item_code == code,
                        mdm.DictMedicalCodeMapping.to_code_set == to_set)):
                    db.add(mdm.DictMedicalCodeMapping(
                        category_code="diagnosis", from_code_set=local_set,
                        from_item_code=code, to_code_set=to_set, to_item_code=to_code))
        db.commit()
        print("[seed] dict items ok")

        # 4) 假目标源（写策略指向测试用，连接由 run_t27_api.py 的假源连接器接管）
        if not db.query(AssetSystem).filter_by(system_code="QA_T27_SYS").first():
            db.add(AssetSystem(system_code="QA_T27_SYS", system_name_cn="T27浏览器验证假系统"))
        # PushWizard systemOptions 按 system_code∈{HIS_SOURCE,JHEMR_VASTBASE} 过滤动态选项：
        # 隔离库缺 HIS_SOURCE 系统行会导致向导目标里没有 HIS——补种（仅隔离库）。
        if not db.query(AssetSystem).filter_by(system_code="HIS_SOURCE").first():
            db.add(AssetSystem(system_code="HIS_SOURCE", system_name_cn="HIS"))
        db.flush()
        for code in ("qa_t27_his", "qa_t27_jhemr"):
            if not db.query(AssetDataSource).filter_by(source_code=code).first():
                # qa_t27_his 挂 HIS_SOURCE：list_first_level_systems 要求系统有
                # 非别名连接才会出现在向导目标选项中（仅隔离库，假源连接器接管写入）。
                db.add(AssetDataSource(
                    system_code="HIS_SOURCE" if code == "qa_t27_his" else "QA_T27_SYS",
                    source_code=code,
                    source_name_cn=f"T27假源 {code}", db_type="postgresql",
                    host_masked="127.0.0.1", target_host="127.0.0.1", port=15432,
                    database_name="data_asset_test",
                    write_policy="medical_dict_push",
                    write_credential_ref="env:QA_T27_FAKE_CRED"))
        his_src = db.query(AssetDataSource).filter_by(source_code="qa_t27_his").first()
        if his_src and his_src.system_code != "HIS_SOURCE":
            his_src.system_code = "HIS_SOURCE"
        his_sys = db.query(AssetSystem).filter_by(system_code="HIS_SOURCE").first()
        if his_sys and (his_sys.status or "").lower() != "active":
            his_sys.status = "active"  # merged 会被一级系统列表过滤，向导看不到 HIS 目标
        db.commit()
        print("[seed] fake sources ok")
    print("[seed] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
