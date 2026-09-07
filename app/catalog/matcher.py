"""参数智能匹配：输入任意自然语言（如"300W 功放 8Ω"），从产品库匹配最适合的设备。

采纳 GitHub 调研结论（rapidfuzz）：
- 规范化预处理是命中的一半：全半角、单位归一、品牌别名、符号清洗；
- 两层打分：字符串层（名称/型号/品牌 WRatio）+ 规格数值层（功率/尺寸/通道/阻值/点距）；
- 召回+确认：低置信返回候选列表，不静默替换，避免售前配错型号。
"""

from __future__ import annotations

import json
import re
import unicodedata

from rapidfuzz import fuzz

# ---------- 品牌别名：统一到 canonical ----------
BRAND_ALIASES = {
    "惠威": "惠威", "hivi": "惠威", "hi-vi": "惠威",
    "maxhub": "MAXHUB", "领效": "MAXHUB",
    "itc 声光视讯": "ITC", "itc": "ITC",
    "sony": "SONY", "索尼": "SONY",
    "samsung": "SAMSUNG", "三星": "SAMSUNG",
    "huawei": "华为", "华为": "华为",
    "hikvision": "海康威视", "海康威视": "海康威视", "海康": "海康威视",
    "dahua": "大华", "大华": "大华",
    "uniview": "宇视", "宇视": "宇视",
    "leyard": "利亚德", "利亚德": "利亚德",
    "unilumin": "洲明", "洲明": "洲明",
    "absen": "艾比森", "艾比森": "艾比森",
    "crestron": "CRESTRON", "快思聪": "CRESTRON",
    "extron": "EXTRON", "爱思创": "EXTRON",
    "jbl": "JBL", "bose": "BOSE", "bosch": "BOSCH", "lg": "LG", "乐金": "LG",
}

# 单位归一：子串替换（大小写不敏感），统一到标准小写形式
_UNIT_NORM = [
    ("英寸", "寸"), ("英吋", "寸"), ("吋", "寸"), ("inch", "寸"), ('"', "寸"), ("''", "寸"),
    ("瓦特", "w"), ("瓦", "w"),
    ("欧姆", "ω"), ("ohm", "ω"),
    ("毫米", "mm"), ("公厘", "mm"),
    ("通道", "路"), ("声道", "路"), ("ch", "路"),
]

# 数值规格提取：字段名 -> 正则（在规范化后的文本上匹配）
_SPEC_PATTERNS = [
    ("power_w", r"(\d{2,4})\s*w"),                     # 功率 300W
    ("impedance", r"(\d+(?:\.\d+)?)\s*ω"),             # 阻抗 8Ω
    ("size_inch", r"(\d+(?:\.\d+)?)\s*寸"),            # 尺寸 75寸
    ("channels", r"(\d{1,2})\s*路"),                   # 通道数 16路
    ("pitch_mm", r"(?:^|[^a-z])p\s*(\d+(?:\.\d+)?)"),  # LED 点距 P2.5（避免命中型号内字母+数字）
]


def normalize(text: str) -> str:
    """规范化：全半角统一 → 单位归一 → 品牌别名 → 清洗空白/大小写。"""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", str(text))
    t = re.sub(r"\s+", "", t).lower()
    for src, dst in _UNIT_NORM:
        t = re.sub(re.escape(src), dst, t, flags=re.IGNORECASE)
    for alias, canonical in sorted(BRAND_ALIASES.items(), key=lambda x: -len(x[0])):
        t = re.sub(re.escape(alias), canonical, t, flags=re.IGNORECASE)
    return t


def extract_specs(text: str) -> dict[str, float]:
    """从文本提取数值规格：{"power_w": 300, "size_inch": 75, ...}。"""
    specs: dict[str, float] = {}
    normalized = normalize(text)
    for key, pattern in _SPEC_PATTERNS:
        m = re.search(pattern, normalized)
        if m:
            try:
                specs[key] = float(m.group(1))
            except ValueError:
                pass
    return specs


def _product_text(p: dict, include_params: bool = True) -> str:
    parts = [p.get("brand", ""), p.get("name", ""), p.get("model", ""),
             p.get("category", ""), p.get("description", "")]
    if include_params:
        try:
            params = json.loads(p.get("params_json") or "{}")
            parts.append(" ".join(str(v) for v in params.values()))
        except Exception:
            pass
    return " ".join(parts)


def _spec_score(product: dict, query_specs: dict[str, float]) -> tuple[float, list[str]]:
    """规格数值层：产品参数命中 query 规格则加分，返回 (加分, 命中理由)。"""
    if not query_specs:
        return 0.0, []
    text = normalize(_product_text(product))
    hits: list[str] = []
    bonus = 0.0
    patterns = {
        "power_w": r"(\d{2,4})\s*w",
        "impedance": r"(\d+(?:\.\d+)?)\s*ω",
        "size_inch": r"(\d+(?:\.\d+)?)\s*寸",
        "channels": r"(\d{1,2})\s*路",
        "pitch_mm": r"(?:^|[^a-z])p\s*(\d+(?:\.\d+)?)",
    }
    for key, qv in query_specs.items():
        m = re.search(patterns[key], text)
        if not m:
            continue
        try:
            pv = float(m.group(1))
        except ValueError:
            continue
        if key == "pitch_mm":
            # 点距：产品点距 <= 需求点距（更清晰）视为可用
            if pv <= qv * 1.2:
                bonus += 20
                hits.append(f"点距 P{pv:g}")
        elif pv * 0.85 <= qv <= pv * 1.15:
            bonus += 20
            hits.append(f"{key.replace('_', ' ')} {pv:g}")
    return bonus, hits


def _core_term(query: str) -> str:
    """提取查询的核心名词（中文段，4 字以上取末尾 2 字，如「无线话筒」→「话筒」）。"""
    n = normalize(query)
    # 去掉规格数值（数字+单位）
    n = re.sub(r"\d+(?:\.\d+)?\s*(?:w|ω|寸|路|mm)?", "", n)
    for alias, canonical in sorted(BRAND_ALIASES.items(), key=lambda x: -len(x[0])):
        n = n.replace(canonical, "")
    segs = re.findall(r"[\u4e00-\u9fff]{2,}", n)
    if not segs:
        return ""
    seg = segs[-1]
    return seg[-2:] if len(seg) >= 4 else seg


def match_products(session, query: str, limit: int = 8) -> list[dict]:
    """主入口：任意自然语言 → top-k 匹配（score 0-100，含 reason）。

    score >= 75 视为高置信；否则为候选列表（调用方应让用户确认）。
    """
    from app.db.models import Product

    if not query or not query.strip():
        return []
    normalized_q = normalize(query)
    query_specs = extract_specs(query)
    core_term = _core_term(query)
    products = session.query(Product).filter(Product.active == 1).all()
    if not products:
        return []

    scored: list[tuple[float, dict, list[str]]] = []
    for p in products:
        pd = {"id": p.id, "name": p.name, "model": p.model, "brand": p.brand,
              "category": p.category, "description": p.description,
              "params_json": p.params_json,
              "base_price": p.base_price, "market_price": p.market_price,
              "system": p.system}
        normalized_p = normalize(_product_text(pd))
        # 字符串层：品牌+名称+型号 加权 WRatio
        str_score = fuzz.WRatio(normalized_q, normalized_p)
        name_score = fuzz.WRatio(normalized_q, normalize(f"{p.brand} {p.name} {p.model}"))
        base = max(str_score, name_score * 1.1)
        # 纯型号精确命中直接高分
        if normalized_q and normalized_q in normalized_p:
            base = max(base, 92.0)
        # 核心名词包含加分（如「话筒」命中名称含话筒的产品）
        core_bonus = 0.0
        if core_term and core_term in normalize(p.name or ""):
            core_bonus = 25.0
        # 规格数值层
        spec_bonus, hits = _spec_score(pd, query_specs)
        total = min(100.0, base * 0.8 + core_bonus + spec_bonus + (8 if hits else 0))
        scored.append((total, pd, hits))

    scored.sort(key=lambda x: -x[0])
    results = []
    for total, pd, hits in scored[:limit]:
        reason = f"匹配 {total:.0f}"
        if hits:
            reason += " · " + "、".join(hits)
        results.append({"product": pd, "score": round(total, 1), "reason": reason})
    return results
