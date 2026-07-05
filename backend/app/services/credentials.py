"""P5.9-T5 凭据解析服务——从 credential_ref 解析只读账号/密码

credential_ref 格式：
- "env:CRED_ODS_8_216" → 从 os.environ["CRED_ODS_8_216"] 读取，格式 "user:password"
- "file:///etc/data-asset/credentials/ods_8_216" → 从文件读取，第一行 "user:password"
- 其他 → 返回 (None, None)
"""

import os
from pathlib import Path


def resolve(credential_ref: str | None) -> tuple[str | None, str | None]:
    """从 credential_ref 解析只读账号密码，返回 (user, password)。"""
    if not credential_ref:
        return None, None

    # env: 前缀
    if credential_ref.startswith("env:"):
        env_key = credential_ref[4:]
        value = os.environ.get(env_key, "")
        if ":" in value:
            user, pwd = value.split(":", 1)
            return user, pwd
        return None, None

    # file:// 前缀
    if credential_ref.startswith("file://"):
        path = credential_ref[7:]
        try:
            content = Path(path).read_text().strip()
            if ":" in content:
                user, pwd = content.split(":", 1)
                return user, pwd
        except (OSError, PermissionError):
            pass
        return None, None

    return None, None
