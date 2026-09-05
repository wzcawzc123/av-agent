import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.config import settings


def verify_token(token: str, expected: str) -> bool:
    return hmac.compare_digest(token or "", expected or "")


def _is_local_request(request: Request) -> bool:
    """本机访问（127.0.0.1 / ::1 / localhost）免口令，防止用户自己反被口令锁死。"""
    host = (request.client.host if request.client else "") or ""
    return host in ("127.0.0.1", "::1", "localhost")


def require_token(request: Request, x_access_token: str = Header(default="")):
    if _is_local_request(request):
        return
    if not verify_token(x_access_token, settings.ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="无效访问口令")


def require_token_router():
    """测试辅助路由：验证 require_token 依赖生效。"""
    router = APIRouter()

    @router.get("/api/health", dependencies=[Depends(require_token)])
    def health():
        return {"status": "ok"}

    return router
