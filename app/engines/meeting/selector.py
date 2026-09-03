from app.db.models import Product, SelectionRule
from app.engines.meeting.codec import MeetingParams


def select_devices(session, params: MeetingParams) -> list[dict]:
    """按场景+配置+面积区间查规则，补产品信息；价格留空。"""
    rules = (session.query(SelectionRule)
             .filter_by(scene=params.scene, config_level=params.config)
             .filter(SelectionRule.area_min <= params.area,
                     SelectionRule.area_max >= params.area)
             .all())
    rows = []
    for i, r in enumerate(rules, start=1):
        prod = session.query(Product).filter_by(model=r.model).first()
        rows.append({
            "seq": i,
            "name": prod.name if prod else r.model,
            "spec": (prod.description.split("\n")[0] if prod and prod.description else ""),
            "brand": prod.brand if prod else "itc",
            "model": r.model,
            "qty": r.qty,
            "unit": r.unit,
            "price": 0,
        })
    return rows
