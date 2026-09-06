"""模板存取：常规配置模板（多维匹配）+ 文档/PPT 模板（按 brand×scene 选型）。"""
import json

from app.db.models import Template, ConfigTemplate


def save_template(session, name: str, type_: str, file_path: str,
                  description: str = "", meta: dict | None = None) -> Template:
    t = Template(name=name, type=type_, file_path=file_path,
                 description=description,
                 meta_json=json.dumps(meta or {}, ensure_ascii=False))
    session.add(t)
    session.flush()
    return t


def save_config_template(session, name: str, area: int, scene: str, config_json: dict,
                         systems: list | None = None, config_level: str = "",
                         brand: str = "") -> ConfigTemplate:
    c = ConfigTemplate(
        name=name,
        area=area,
        scene=scene,
        systems=json.dumps(systems or [], ensure_ascii=False),
        config_level=config_level,
        brand=brand,
        config_json=json.dumps(config_json, ensure_ascii=False),
    )
    session.add(c)
    session.flush()
    return c


def _jlist(raw: str) -> list:
    try:
        v = json.loads(raw or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def find_config_template(session, area: int, scene: str = "", systems: list | None = None,
                         config_level: str = "", brand: str = "") -> ConfigTemplate | None:
    """多维匹配：场景/系统/配置档/品牌命中越多越优先，面积差异最小者同分优先。"""
    rows = session.query(ConfigTemplate).all()
    if not rows:
        return None
    want_sys = set(systems or [])
    want_brand = {b.strip().lower() for b in (brand or "").split(",") if b.strip()}
    best, best_score = None, -1
    for r in rows:
        score = 0
        same_scene = (scene and r.scene and (scene in r.scene or r.scene in scene))
        if same_scene:
            score += 3
        if want_sys and _jlist(r.systems):
            score += len(want_sys & set(_jlist(r.systems))) * 2
        if config_level and r.config_level == config_level:
            score += 2
        if want_brand and r.brand:
            r_brands = {b.strip().lower() for b in r.brand.split(",") if b.strip()}
            if r_brands & want_brand:
                score += 2
        if area and r.area:
            score -= min(abs(r.area - area) // 50, 2)
        if best is None or score > best_score:
            best, best_score = r, score
    return best


def find_doc_template(session, scene: str = "", brand: str = "",
                       doc_type: str | None = None) -> Template | None:
    """按 brand×scene 标签选文档模板；doc_type 指定时只在该类型内评选。

    doc_type 支持 "doc" / "ppt" / "deviation"；缺省保持历史行为（doc+ppt 混选）。
    """
    q = session.query(Template)
    if doc_type:
        q = q.filter(Template.type == doc_type)
    else:
        q = q.filter(Template.type.in_(["doc", "ppt"]))
    rows = q.all()
    if not rows:
        return None
    b = (brand or "").strip().lower()
    s = (scene or "").strip()
    best, best_score = None, 0
    for r in rows:
        try:
            meta = json.loads(r.meta_json or "{}") or {}
        except Exception:
            meta = {}
        score = 0
        mb = (meta.get("brand") or "").lower()
        ms = meta.get("scene") or ""
        if b and mb and (b in mb or mb in b):
            score += 4
        if s and ms and (s in ms or ms in s):
            score += 3
        if score > best_score:
            best, best_score = r, score
    return best
