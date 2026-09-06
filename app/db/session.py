from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engines: dict[str, object] = {}
_sessionmakers: dict[int, object] = {}


def get_engine(url: str | None = None):
    """按 URL 缓存 engine；url 缺省时优先 settings.DATABASE_URL（PG/Redis 部署），否则使用应用默认 SQLite。"""
    if url is None:
        from app.config import settings

        url = settings.DATABASE_URL or f"sqlite:///{settings.DB_PATH}"
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    if url not in _engines:
        _engines[url] = create_engine(url, **kwargs)
    return _engines[url]


@contextmanager
def get_session(engine=None):
    engine = engine or get_engine()
    key = id(engine)
    SessionLocal = _sessionmakers.get(key)
    if SessionLocal is None:
        SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        _sessionmakers[key] = SessionLocal
    sess = SessionLocal()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
