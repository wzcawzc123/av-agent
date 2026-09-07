"""LLM 智能入库：文件分类与结构化提取。

classify_document: 判断上传内容属于哪类数据（产品清单/知识文档/其他）
extract_products:   从产品清单文本提取结构化产品 JSON
extract_knowledge:  从文档文本生成知识库条目
"""

from __future__ import annotations

import json

from app.llm.base import ChatMessage
from app.llm.prompts import (
    INGEST_CLASSIFY_PROMPT,
    INGEST_KNOWLEDGE_PROMPT,
    INGEST_PRODUCTS_PROMPT,
)


def _clean_json(text: str) -> dict | None:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
            return data if isinstance(data, dict) else None
        except Exception:
            return None


async def classify_document(provider, text: str, filename: str) -> dict:
    """返回 {"type": "products|knowledge|tender|other", "title", "summary", "confidence"}。"""
    resp = await provider.chat(
        [
            ChatMessage("system", INGEST_CLASSIFY_PROMPT),
            ChatMessage("user", f"文件名：{filename}\n\n文件内容（前 3000 字符）：\n{text[:3000]}"),
        ],
        temperature=0.1,
    )
    data = _clean_json(resp) or {}
    ftype = str(data.get("type") or "other")
    if ftype not in ("products", "knowledge", "tender", "other"):
        ftype = "other"
    return {
        "type": ftype,
        "title": str(data.get("title") or filename),
        "summary": str(data.get("summary") or ""),
        "confidence": float(data.get("confidence") or 0),
    }


async def extract_products(provider, text: str) -> list[dict]:
    """从产品清单文本提取产品 JSON 列表；严格按原文，不编造。"""
    resp = await provider.chat(
        [
            ChatMessage("system", INGEST_PRODUCTS_PROMPT),
            ChatMessage("user", text[:24000]),
        ],
        temperature=0.1,
    )
    data = _clean_json(resp) or {}
    products = data.get("products")
    if not isinstance(products, list):
        return []
    cleaned = []
    for p in products:
        if not isinstance(p, dict):
            continue
        item = {
            "name": str(p.get("name") or "").strip(),
            "model": str(p.get("model") or "").strip(),
            "brand": str(p.get("brand") or "").strip(),
            "category": str(p.get("category") or "").strip(),
            "description": str(p.get("description") or "").strip(),
            "base_price": _to_price(p.get("base_price")),
            "market_price": _to_price(p.get("market_price")),
        }
        params = p.get("params")
        if isinstance(params, dict):
            item["params"] = {str(k): str(v) for k, v in params.items()}
        if item["name"] or item["model"]:
            cleaned.append(item)
    return cleaned


async def extract_knowledge(provider, text: str, filename: str) -> dict | None:
    """从文档文本生成知识库条目 {"title","doc_type","excerpt"}。"""
    resp = await provider.chat(
        [
            ChatMessage("system", INGEST_KNOWLEDGE_PROMPT),
            ChatMessage("user", f"文件名：{filename}\n\n内容：\n{text[:12000]}"),
        ],
        temperature=0.2,
    )
    data = _clean_json(resp) or {}
    title = str(data.get("title") or filename).strip()
    excerpt = str(data.get("excerpt") or "").strip()
    if not title or not excerpt:
        return None
    return {
        "title": title,
        "doc_type": str(data.get("doc_type") or "资料").strip() or "资料",
        "excerpt": excerpt,
    }


def _to_price(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "").replace("¥", "").replace("元", "")
    try:
        return float(s)
    except Exception:
        return 0.0
