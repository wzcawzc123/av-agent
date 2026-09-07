from app.db.models import Product, SelectionRule
from app.engines.meeting.codec import MeetingParams


def _rule_matches(rule, params: MeetingParams) -> bool:
    """基础规则与话筒/天线段：NULL 表示该段任意值均适用。"""
    mic = params.extra.get("话筒配置", "0")
    ant = params.extra.get("天线", "0")
    if rule.mic_level is not None and mic not in rule.mic_level.split(","):
        return False
    if rule.antenna_level is not None and ant not in rule.antenna_level.split(","):
        return False
    return True


def select_devices(session, params: MeetingParams) -> list[dict]:
    """按场景+配置+面积区间+话筒/天线段查规则，补产品信息；价格留空。"""
    rules = (session.query(SelectionRule)
             .filter_by(scene=params.scene, config_level=params.config)
             .filter(SelectionRule.area_min <= params.area,
                     SelectionRule.area_max >= params.area)
             .all())
    rows = []
    for i, r in enumerate(rules, start=1):
        if not _rule_matches(r, params):
            continue
        prod = session.query(Product).filter_by(model=r.model).first()
        rows.append({
            "seq": i,
            "role": r.device_role,
            "name": prod.name if prod else r.model,
            "spec": (prod.description.split("\n")[0] if prod and prod.description else ""),
            "brand": prod.brand if prod else "itc",
            "model": r.model,
            "qty": r.qty,
            "unit": r.unit,
            "price": 0,
        })
    return rows
