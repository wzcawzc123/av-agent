from fastapi import Header, HTTPException, Request

from app.security.auth import _is_local_request, verify_token


async def require_token(request: Request, x_access_token: str = Header(default="")):
    """统一鉴权依赖：兼容 X-Access-Token 与 Authorization: Bearer 两种写法。

    本机访问（127.0.0.1 / ::1 / localhost）免口令（见 _is_local_request）。
    """
    if _is_local_request(request):
        return
    token = (x_access_token or "").strip()
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        token = request.headers.get("X-Access-Token", "").strip()
    from app.config import settings

    if not verify_token(token, settings.ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="无效访问口令")
