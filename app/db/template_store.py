import json

from app.db.models import Template, ConfigTemplate


def save_template(session, name: str, type_: str, file_path: str, description: str = "") -> Template:
    t = Template(name=name, type=type_, file_path=file_path, description=description)
    session.add(t)
    session.flush()
    return t


def save_config_template(session, name: str, area: int, scene: str, config_json: dict) -> ConfigTemplate:
    c = ConfigTemplate(
        name=name,
        area=area,
        scene=scene,
        config_json=json.dumps(config_json, ensure_ascii=False),
    )
    session.add(c)
    session.flush()
    return c


def find_config_template(session, area: int):
    exact = (
        session.query(ConfigTemplate)
        .filter_by(area=area)
        .order_by(ConfigTemplate.id.desc())
        .first()
    )
    if exact:
        return exact
    rows = session.query(ConfigTemplate).all()
    if not rows:
        return None
    return min(rows, key=lambda r: abs(r.area - area))
