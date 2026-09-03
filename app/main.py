from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    yield


app = FastAPI(title="AV Agent", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


app.mount("/", StaticFiles(directory=settings.STATIC_DIR, html=True), name="static")
