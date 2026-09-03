from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    import app.security.crypto as crypto

    crypto.KEY_PATH = settings.MASTER_KEY_PATH
    from app.db.session import get_engine
    from app.db.migrate import ensure_schema
    from app.db.models import Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    ensure_schema(engine)
    yield


from app.version import VERSION as APP_VERSION
app = FastAPI(title="AV Agent", version=APP_VERSION, lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


from app.api.routes_chat import router as chat_router
from app.api.routes_projects import router as projects_router
from app.api.routes_generate import router as generate_router
from app.api.routes_data import router as data_router
from app.api.routes_settings import router as settings_router

app.include_router(chat_router)
app.include_router(projects_router)
app.include_router(generate_router)
app.include_router(data_router)
app.include_router(settings_router)

app.mount("/", StaticFiles(directory=settings.STATIC_DIR, html=True), name="static")
