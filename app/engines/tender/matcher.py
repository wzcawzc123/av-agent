"""品牌就近匹配器。

品牌池由产品库动态发现；不硬编码任何品牌知识。
匹配流程：解析项 -> 品牌过滤候选 -> 有向维度距离排序 -> 就近取高/取低。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import Product
from app.engines.tender.dimensions import DimMap, extract_dims, prefer_distance
from app.engines.tender.model import (
    STATUS_MATCHED,
    STATUS_NO_MATCH,
    STATUS_PARTIAL,
    TenderItem,
    TenderMatchRow,
)

# 距离阈值：小于该值视为可靠命中；大于则标记 partial 待人工确认
DISTANCE_MATCHED = 0.35
DISTANCE_PARTIAL = 0.8


@dataclass
class Candidate:
    product: Product
    score: float
    common: set = field(default_factory=set)
    gaps: set = field(default_factory=set)


def brand_pool(session: Session) -> dict[str, int]:
    """品牌池：distinct brand -> 在库产品数（active=1，空品牌跳过）。"""
    pool: dict[str, int] = {}
    for (b,) in session.query(Product.brand).filter(Product.active == 1).all():
        b = (b or "").strip()
        if b:
            pool[b] = pool.get(b, 0) + 1
    return pool


def brand_seen(session: Session, brand: str) -> bool:
    """品牌是否已在产品库出现（首次出现检测：False -> 前端提示入库）。"""
    b = (brand or "").strip()
    if not b:
        return True  # 无品牌信息不触发提示
    return session.query(Product.id).filter(Product.brand == b, Product.active == 1).first() is not None


def product_dims(p: Product) -> DimMap:
    """产品维度：description + params_json 值 + name 合并提取。"""
    parts = [p.description or "", p.name or ""]
    try:
        params = json.loads(p.params_json or "{}")
        if isinstance(params, dict):
            parts.extend(str(v) for v in params.values())
        elif isinstance(params, list):
            parts.extend(str(v) for v in params)
    except (json.JSONDecodeError, TypeError):
        pass
    return extract_dims(" ".join(parts))


def item_dims(item: TenderItem) -> DimMap:
    return extract_dims(" ".join([item.name, *item.params]))


def find_candidates(
    session: Session, item: TenderItem, brand: str | None = None, preference: str = "higher"
) -> list[Candidate]:
    """候选按有向距离升序。brand 为 None 时全库检索。"""
    q = session.query(Product).filter(Product.active == 1)
    if brand:
        q = q.filter(Product.brand == brand)
    t_dims = item_dims(item)
    out: list[Candidate] = []
    for p in q.all():
        dist, common, gaps = prefer_distance(t_dims, product_dims(p), preference)
        if dist is None:
            continue
        out.append(Candidate(p, dist, common, gaps))
    out.sort(key=lambda c: c.score)
    return out


def _status_for(dist: float) -> str:
    if dist <= DISTANCE_MATCHED:
        return STATUS_MATCHED
    if dist <= DISTANCE_PARTIAL:
        return STATUS_PARTIAL
    return STATUS_NO_MATCH


def match_item(session: Session, item: TenderItem, preference: str = "higher") -> TenderMatchRow:
    """匹配单个招标项。品牌在库 -> 品牌内就近；品牌首次 -> 全库就近 + 提示入库。"""
    row = TenderMatchRow(
        source_idx=item.idx,
        name=item.name,
        brand=item.brand,
        model=item.model,
        qty=item.qty,
        params=list(item.params),
        preference=preference,
    )
    seen = brand_seen(session, item.brand)
    brand_filter = item.brand.strip() if (item.brand and seen) else None
    candidates = find_candidates(session, item, brand=brand_filter, preference=preference)
    if not candidates:
        row.status = STATUS_NO_MATCH
        row.remark = "新增：库内无匹配产品，需补充设备" if seen else f"新增：品牌「{item.brand}」首次出现，建议先入库产品"
        return row
    best = candidates[0]
    row.status = _status_for(best.score)
    row.score = 1.0 - min(best.score, 1.0)
    row.matched_product_id = best.product.id
    row.matched_model = best.product.model
    notes = []
    if not seen:
        notes.append(f"品牌「{item.brand}」首次出现，已按全库就近匹配，建议入库该品牌产品")
    if best.gaps:
        notes.append("参数缺口：" + "/".join(sorted(best.gaps)))
    if row.status == STATUS_PARTIAL:
        notes.append("参数差异较大，请确认")
    elif row.status == STATUS_NO_MATCH:
        notes.append("差异过大，建议新增设备")
    row.remark = "；".join(notes)
    return row


def match_items(
    session: Session, items: list[TenderItem], preference: str = "higher"
) -> list[TenderMatchRow]:
    return [match_item(session, it, preference) for it in items]
