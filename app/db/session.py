from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engines: dict[str, object] = {}


def get_engine(url: str | None = None):
    """按 URL 缓存 engine；url 缺省时使用应用默认数据库。"""
    if url is None:
        from app.config import settings

        url = f"sqlite:///{settings.DB_PATH}"
    if url not in _engines:
        _engines[url] = create_engine(url, connect_args={"check_same_thread": False})
    return _engines[url]


@contextmanager
def get_session(engine=None):
    engine = engine or get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
