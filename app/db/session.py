from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionLocal = None


def get_engine(url: str | None = None):
    """返回单例 engine；首次调用时可用显式 url 覆盖默认（测试用内存/临时库）。"""
    global _engine, _SessionLocal
    if _engine is None:
        if url is None:
            from app.config import settings

            url = f"sqlite:///{settings.DB_PATH}"
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


@contextmanager
def get_session(engine=None):
    engine = engine or get_engine()
    sess = _SessionLocal()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
