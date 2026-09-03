import hmac

from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings


def verify_token(token: str, expected: str) -> bool:
    return hmac.compare_digest(token or "", expected or "")


def require_token(x_access_token: str = Header(default="")) -> None:
    if not verify_token(x_access_token, settings.ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="无效访问口令")


def require_token_router():
    """测试辅助路由：验证 require_token 依赖生效。"""
    router = APIRouter()

    @router.get("/api/health", dependencies=[Depends(require_token)])
    def health():
        return {"status": "ok"}

    return router
