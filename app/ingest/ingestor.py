"""入库逻辑：把 LLM 提取的结构化内容写入对应库，带去重与打标。"""

from __future__ import annotations

from app.db.models import Product
from app.knowledge.retriever import register_document


def ingest_products(session, items: list[dict]) -> tuple[int, int]:
    """写入产品库。返回 (新增条数, 跳过条数)。model 唯一，存在即跳过。"""
    added = 0
    skipped = 0
    existing_models = {m for (m,) in session.query(Product.model).all()}
    for item in items:
        model = str(item.get("model") or "").strip()
        name = str(item.get("name") or "").strip()
        if not model and not name:
            skipped += 1
            continue
        if model and model in existing_models:
            skipped += 1
            continue
        import json

        params = item.get("params") or {}
        p = Product(
            name=name or model,
            model=model or f"auto-{abs(hash(name)) % 10_000_000}",
            brand=str(item.get("brand") or "").strip(),
            description=str(item.get("description") or "").strip(),
            params_json=json.dumps(params, ensure_ascii=False),
            base_price=float(item.get("base_price") or 0),
            market_price=float(item.get("market_price") or 0),
            category=str(item.get("category") or "").strip(),
        )
        session.add(p)
        if model:
            existing_models.add(model)
        added += 1
    session.commit()
    return added, skipped


def ingest_knowledge(session, doc: dict) -> int:
    """写入知识库。返回新增文档 id；标题重复返回 0。"""
    title = str(doc.get("title") or "").strip()
    if not title:
        return 0
    from app.db.models import KnowledgeDocument

    dup = session.query(KnowledgeDocument).filter_by(title=title).first()
    if dup:
        return 0
    doc_id = register_document(
        session,
        title=title,
        doc_type=str(doc.get("doc_type") or "资料"),
        file_path="",
        excerpt=str(doc.get("excerpt") or ""),
        meta={"source": "llm-ingest"},
    )
    session.commit()
    return doc_id


def summarize(type_: str, added: int, skipped: int, doc_id: int = 0) -> str:
    if type_ == "products":
        return f"✅ 产品入库完成：新增 {added} 条，跳过重复 {skipped} 条。"
    if type_ == "knowledge":
        return f"✅ 知识库入库完成：新增 1 条（id={doc_id}），跳过重复 {skipped} 条。"
    return "文件已识别但类型不受支持（仅支持产品清单/知识文档）。"
