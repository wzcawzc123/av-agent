"""知识文档 CRUD + 关键词检索（轻量 RAG，纯 Python 打分，无向量库依赖）。"""
import json
import re

from app.db.models import KnowledgeDocument

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ASCII_WORD_RE = re.compile(r"[a-zA-Z0-9]+")
_STOPWORDS = {
    "的", "了", "和", "与", "或", "在", "是", "有", "为", "请",
    "需要", "一个", "进行", "提供", "用于", "以及", "我们", "可以",
}
_WEIGHTS = {"title": 3.0, "meta": 2.0, "excerpt": 1.0}


def _tokenize(text: str) -> list[str]:
    """轻量分词：ASCII 单词 + 中文单字 + 中文相邻双字。"""
    tokens = [w.lower() for w in _ASCII_WORD_RE.findall(text)]
    cjk_chars = "".join(_CJK_RE.findall(text))
    for ch in cjk_chars:
        if ch not in _STOPWORDS:
            tokens.append(ch)
    for i in range(len(cjk_chars) - 1):
        bigram = cjk_chars[i:i + 2]
        if bigram not in _STOPWORDS:
            tokens.append(bigram)
    return tokens


def _safe_loads(s: str):
    try:
        return json.loads(s or "{}")
    except (TypeError, ValueError):
        return {}


def _to_dict(doc: KnowledgeDocument) -> dict:
    return {
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "file_path": doc.file_path,
        "excerpt": doc.excerpt,
        "meta": _safe_loads(doc.meta_json),
        "org_id": doc.org_id,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


def register_document(session, title: str, doc_type: str, file_path: str, excerpt: str = "", meta=None) -> int:
    """登记一篇知识文档，返回文档 id。"""
    doc = KnowledgeDocument(
        title=title,
        doc_type=doc_type,
        file_path=file_path,
        excerpt=excerpt or "",
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
    )
    session.add(doc)
    session.flush()
    return doc.id


def list_documents(session) -> list[dict]:
    """列出全部知识文档（倒序）。"""
    docs = session.query(KnowledgeDocument).order_by(KnowledgeDocument.id.desc()).all()
    return [_to_dict(d) for d in docs]


def delete_document(session, doc_id: int) -> bool:
    """删除知识文档；不存在返回 False。"""
    doc = session.get(KnowledgeDocument, doc_id)
    if doc is None:
        return False
    session.delete(doc)
    session.flush()
    return True


def retrieve(session, query: str, top_k: int = 5) -> list[dict]:
    """按关键词打分检索：title/excerpt/meta 命中加权求和，返回带 score 的文档列表。"""
    terms = _tokenize(query or "")
    if not terms:
        return []
    docs = session.query(KnowledgeDocument).all()
    scored = []
    for d in docs:
        title_tokens = set(_tokenize(d.title or ""))
        excerpt_tokens = set(_tokenize(d.excerpt or ""))
        meta_text = json.dumps(_safe_loads(d.meta_json), ensure_ascii=False)
        meta_tokens = set(_tokenize(meta_text))
        score = 0.0
        for t in terms:
            if t in title_tokens:
                score += _WEIGHTS["title"]
            if t in meta_tokens:
                score += _WEIGHTS["meta"]
            if t in excerpt_tokens:
                score += _WEIGHTS["excerpt"]
        if score > 0:
            item = _to_dict(d)
            item["score"] = round(score, 3)
            scored.append(item)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
