"""产品目录检索与品牌约束。

品牌约束表达（需求里用户怎么说都行，统一解析为结构）：
- 无偏好/不限            -> {"mode": "any"}
- 全部用惠威             -> {"mode": "specified", "all": ["惠威"]}
- 惠威和MAXHUB组合       -> {"mode": "specified", "all": ["惠威", "MAXHUB"]}
- 扩声用惠威显示用MAXHUB -> {"mode": "by_system", "systems": {"prosound": ["惠威"], "display": ["MAXHUB"]}}
"""
import json
import re

from app.db.models import DeviceRole, Product
from app.db.system_seed import _SYSTEMS


_ALL_BRAND_RE = re.compile(r"^(?:全部|所有|整体|整个|一律|都)[用:：]?(.+)$")


def parse_brand_constraints(brand) -> dict:
    """把用户原始品牌表达解析为约束结构；输入 None/空串 -> any。"""
    if not brand:
        return {"mode": "any"}
    if isinstance(brand, dict):
        return brand
    text = str(brand).strip()
    if not text or text in ("无", "不限", "都可以", "任意"):
        return {"mode": "any"}
    m = _ALL_BRAND_RE.match(text)
    if m:
        return {"mode": "specified", "all": _split_brands(m.group(1))}
    by_system = {}
    for m in re.finditer(
            r"([\u4e00-\u9fa5A-Za-z]+(?:系统|用|部分|区)?)[用:：]"
            r"([\u4e00-\u9fa5A-Za-z0-9]+(?:[、,和与/|＋+][\u4e00-\u9fa5A-Za-z0-9]+)*)", text):
        key, val = m.group(1), m.group(2)
        for sys_code in _match_systems(key):
            by_system[sys_code] = _split_brands(val)
    if by_system:
        return {"mode": "by_system", "systems": by_system}
    return {"mode": "specified", "all": _split_brands(text)}

def _match_systems(text: str) -> list[str]:
    """支持“显示和无纸化”等多系统名，返回命中的 system code 列表。"""
    if not text:
        return []
    hits = []
    for part in re.split(r"[和与、/]", text):
        part = part.strip()
        if not part:
            continue
        matched = False
        for code, name, _d in _SYSTEMS:
            if code in part or name in part:
                hits.append(code)
                matched = True
                break
        if matched:
            continue
        for k, v in {"扩声": "prosound", "音响": "prosound", "发言": "speech",
                     "话筒": "speech", "显示": "display", "屏": "display",
                     "无纸化": "paperless", "中控": "control", "矩阵": "control",
                     "分布式": "distributed", "灯光": "lighting", "灯": "lighting",
                     "广播": "broadcast", "视频会议": "videoconf", "会议": "speech"}.items():
            if k in part:
                hits.append(v)
                break
    return hits


_BRAND_SUFFIXES = ("组合", "搭配", "品牌", "的产品", "产品", "一起", "系列")


def _split_brands(text: str) -> list[str]:
    for sep in ("、", "，", ",", "和", "与", "/", "|", "＋", "+", " "):
        text = text.replace(sep, "|")
    out = []
    for b in (x.strip() for x in text.split("|")):
        for suf in _BRAND_SUFFIXES:
            if b.endswith(suf) and len(b) > len(suf):
                b = b[: -len(suf)]
        if b:
            out.append(b)
    return out


def brand_allowed(brand_c: dict, system_code: str) -> list[str] | None:
    """返回该系统允许的品牌列表；None 表示不限品牌。"""
    mode = brand_c.get("mode", "any")
    if mode == "any":
        return None
    if mode == "specified":
        return brand_c.get("all") or None
    if mode == "by_system":
        return brand_c.get("systems", {}).get(system_code) or None
    return None


def role_keywords(session, role_code: str) -> list[str]:
    r = session.query(DeviceRole).filter_by(role_code=role_code).first()
    if r and r.match_keywords:
        try:
            return json.loads(r.match_keywords)
        except Exception:
            return []
    return []
def search_products(session, system: str = "", role: str = "", brand: list[str] | None = None,
                    keyword: str = "", limit: int = 20) -> list[dict]:
    """按 系统x角色x品牌x关键词 检索产品（active=1）。"""
    q = session.query(Product).filter(Product.active == 1)
    if system:
        q = q.filter(Product.system == system)
    if role:
        q = q.filter(Product.role_tags.like(f'%"{role}"%'))
    if brand:
        q = q.filter(Product.brand.in_(brand))
    if keyword:
        like = f"%{keyword}%"
        q = q.filter((Product.name.like(like)) | (Product.model.like(like)) | (Product.description.like(like)))
    rows = q.limit(limit).all()
    return [{
        "name": p.name, "model": p.model, "brand": p.brand,
        "base_price": p.base_price, "market_price": p.market_price,
        "category": p.category, "system": p.system,
        "params_json": p.params_json, "description": p.description,
    } for p in rows]


def backfill_role(session, system: str, role: str, brand_list: list[str] | None) -> dict | None:
    """为单个设备角色回填产品；优先 系统x角色x品牌，逐级回退到 角色x品牌 / 角色。

    LIKE 全部无果时用 rapidfuzz 智能匹配兜底（角色名 → 产品名称/型号模糊匹配）。
    """
    cands = search_products(session, system=system, role=role, brand=brand_list, limit=10)
    if not cands:
        cands = search_products(session, system="", role=role, brand=brand_list, limit=10)
    if not cands and brand_list:
        cands = search_products(session, system="", role=role, brand=None, limit=10)
    if cands:
        return cands[0]
    # rapidfuzz 兜底：角色名（如"主扩音箱"）模糊匹配产品
    try:
        from app.catalog.matcher import match_products

        ms = match_products(session, role or "", limit=5)
        if ms and ms[0]["score"] >= 55:
            m = ms[0]["product"]
            return {k: m.get(k, "") for k in
                    ("name", "model", "brand", "base_price", "market_price",
                     "category", "system", "params_json", "description")}
    except Exception:
        pass
    return None
