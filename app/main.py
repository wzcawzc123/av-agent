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
    # E1/A9：重启后把遗留的 running/pending 后台任务标记为 failed
    try:
        from app.tasks.queue import recover_stale_tasks

        n = recover_stale_tasks(engine)
        if n:
            print(f"[tasks] 标记 {n} 条中断任务为 failed")
    except Exception:
        pass
    from app.db.session import get_session
    from app.db.system_seed import seed_system_catalog
    from app.db.tagger import tag_product
    from app.db.models import Product
    with get_session(engine) as s:
        seed_system_catalog(s)
        # 售前专家知识库预置（幂等：已存在的标题跳过）
        try:
            from app.db.presales_seed import seed_presales_knowledge

            n = seed_presales_knowledge(s)
            if n:
                print(f"[knowledge] 预置 {n} 条售前知识文档")
        except Exception:
            pass
        # 旧库产品补齐 system/role_tags（幂等：仅处理未打标行）
        for p in s.query(Product).filter(Product.system == "").limit(2000):
            t = tag_product(p.name, p.category, p.brand)
            if t["system"] or t["role_tags"]:
                p.system = t["system"]
                p.role_tags = __import__("json").dumps(t["role_tags"], ensure_ascii=False)
    yield


from app.version import VERSION as APP_VERSION
app = FastAPI(title="AV Agent", version=APP_VERSION, lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


from app.api.routes_chat import router as chat_router
from app.api.routes_agent import router as agent_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_projects import router as projects_router
from app.api.routes_generate import router as generate_router
from app.api.routes_data import router as data_router
from app.api.routes_settings import router as settings_router
from app.api.routes_tender import router as tender_router
from app.api.routes_workflow import router as workflow_router

app.include_router(chat_router)
app.include_router(agent_router)
app.include_router(ingest_router)
app.include_router(projects_router)
app.include_router(generate_router)
app.include_router(data_router)
app.include_router(settings_router)
app.include_router(tender_router)
app.include_router(workflow_router)

app.mount("/", StaticFiles(directory=settings.STATIC_DIR, html=True), name="static")
