from fastapi import HTTPException, Request


def get_current_user(request: Request) -> str:
    """Return the authenticated user set by the HTTP authentication middleware."""
    user_identifier = getattr(request.state, "user_identifier", None)
    if not user_identifier:
        raise HTTPException(status_code=403, detail="Token 未绑定可信操作人")
    return user_identifier
