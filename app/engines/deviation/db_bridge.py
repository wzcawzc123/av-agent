import re

from app.db.models import Product
from app.engines.deviation.model import ProductCandidate


def _split_params(desc: str) -> list[str]:
    """按编号前缀或换行拆分参数列表；行内的小数（如 HDMI1.4）不会被误拆。"""
    parts = re.split(r"(?m)\n|^\s*(?=\d+[.、])", desc or "")
    return [p.strip() for p in parts if p.strip()]


def build_candidates_from_db(session, models):
    out = []
    for m in models:
        p = session.query(Product).filter_by(model=m).first()
        if p:
            out.append(ProductCandidate(model=m, params=_split_params(p.description)))
    return out
