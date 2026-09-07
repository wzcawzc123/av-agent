"""B4 售前知识库预置测试：幂等写入与检索可用性。"""

from app.db.migrate import ensure_schema
from app.db.models import Base
from app.db.presales_seed import PRESALES_DOCUMENTS, seed_presales_knowledge
from app.db.session import get_engine, get_session
from app.knowledge.retriever import list_documents, retrieve


def _fresh(tmp_path, name: str):
    engine = get_engine(f"sqlite:///{tmp_path}/{name}.db")
    Base.metadata.create_all(engine)
    ensure_schema(engine)
    return engine


def test_seed_is_idempotent(tmp_path):
    engine = _fresh(tmp_path, "seed")
    with get_session(engine) as s:
        n1 = seed_presales_knowledge(s)
        n2 = seed_presales_knowledge(s)
        assert n1 == len(PRESALES_DOCUMENTS) >= 8
        assert n2 == 0
        assert len(list_documents(s)) == len(PRESALES_DOCUMENTS)


def test_seed_documents_are_retrievable(tmp_path):
    engine = _fresh(tmp_path, "seed2")
    with get_session(engine) as s:
        seed_presales_knowledge(s)
        hits = retrieve(s, "LED 点距 观看距离", top_k=3)
        assert any("点距" in h["title"] for h in hits)
        hits2 = retrieve(s, "偏离表 投标 应对", top_k=2)
        assert any("偏离" in h["title"] for h in hits2)
