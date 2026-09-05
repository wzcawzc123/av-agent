from fastapi import Header, HTTPException, Request

from app.security.auth import _is_local_request, verify_token


async def require_token(request: Request, x_access_token: str = Header(default="")):
    if _is_local_request(request):
        return
    from app.config import settings

    if not verify_token(x_access_token, settings.ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="无效访问口令")
