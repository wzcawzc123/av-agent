"""知识库（RAG 关键词检索）单测：register / list / delete / retrieve 关键词命中。"""
import pytest

from app.db.models import Base, KnowledgeDocument
from app.db.session import get_engine, get_session
from app.knowledge.retriever import delete_document, list_documents, register_document, retrieve


@pytest.fixture()
def db(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'k.db'}")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        register_document(s, "MAXHUB会议平板手册", "manual", "/tmp/maxhub.pdf",
                          excerpt="W85PN3 85寸会议平板 内置麦克风", meta={"brand": "MAXHUB"})
        register_document(s, "惠威专业音箱说明书", "manual", "/tmp/hv.pdf",
                          excerpt="8寸专业音箱 额定功率80W", meta={"brand": "惠威"})
        register_document(s, "投标偏离表填写指引", "guide", "/tmp/deviation.pdf",
                          excerpt="偏离表按行填写 满足或偏离")
    yield engine
    engine.dispose()


def test_list_documents(db):
    with get_session(db) as s:
        docs = list_documents(s)
    assert len(docs) == 3
    titles = {d["title"] for d in docs}
    assert titles == {"MAXHUB会议平板手册", "惠威专业音箱说明书", "投标偏离表填写指引"}
    assert all(isinstance(d["id"], int) and "file_path" in d for d in docs)


def test_register_document_returns_id(db):
    with get_session(db) as s:
        did = register_document(s, "灯光控制手册", "manual", "/tmp/light.pdf")
    assert isinstance(did, int) and did > 0
    with get_session(db) as s:
        row = s.query(KnowledgeDocument).filter_by(id=did).first()
        assert row is not None and row.title == "灯光控制手册"
        assert any(d["id"] == did and d["doc_type"] == "manual" for d in list_documents(s))


def test_delete_document(db):
    with get_session(db) as s:
        docs = list_documents(s)
        target = next(d for d in docs if d["title"] == "惠威专业音箱说明书")
        assert delete_document(s, target["id"]) is True
        assert delete_document(s, target["id"]) is False  # 已删除
        assert delete_document(s, 99999) is False  # 不存在
        assert len(list_documents(s)) == 2


def test_retrieve_title_and_excerpt_hit(db):
    with get_session(db) as s:
        hits = retrieve(s, "会议平板", top_k=5)
    assert hits and hits[0]["title"] == "MAXHUB会议平板手册"
    with get_session(db) as s:
        hits = retrieve(s, "音箱", top_k=5)
    assert hits and hits[0]["title"] == "惠威专业音箱说明书"


def test_retrieve_meta_hit(db):
    with get_session(db) as s:
        register_document(s, "产品目录", "catalog", "/tmp/cat.pdf",
                          excerpt="公司全系列产品", meta={"category": "音视频设备"})
    with get_session(db) as s:
        hits = retrieve(s, "音视频设备", top_k=5)
    assert hits and hits[0]["title"] == "产品目录"


def test_retrieve_top_k_and_empty(db):
    with get_session(db) as s:
        for i in range(8):
            register_document(s, f"通用手册{i}", "manual", f"/tmp/g{i}.pdf", excerpt="通用资料内容")
    with get_session(db) as s:
        hits = retrieve(s, "通用", top_k=3)
    assert 0 < len(hits) <= 3
    assert all("通用手册" in h["title"] for h in hits)
    with get_session(db) as s:
        hits = retrieve(s, "不存在的关键词xyz", top_k=5)
    assert hits == []
