import re

from app.db.models import Product
from app.engines.deviation.model import ProductCandidate


def _split_params(desc: str) -> list[str]:
    """按编号前缀或换行拆分参数列表；行内的小数（如 HDMI1.4）不会被误拆。"""
    parts = re.split(r"(?m)\n|^\s*(?=\d+[.、])", desc or "")
    return [p.strip() for p in parts if p.strip()]


def build_candidates_from_db(session, models):
    """按型号过滤构造候选；models 为空时使用全库产品。"""
    out = []
    q = session.query(Product)
    if models:
        q = q.filter(Product.model.in_(models))
    for p in q.all():
        out.append(ProductCandidate(model=p.model, params=_split_params(p.description)))
    return out
