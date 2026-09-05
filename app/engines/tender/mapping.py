"""架构映射：招标设备名 -> 系统/角色归类（基于 DeviceRole 匹配关键词）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import DeviceRole
from app.engines.tender.model import TenderItem

ROLE_MATCH_CACHE: dict[str, list[tuple[str, str, list[str]]]] = {}


def _roles(session: Session) -> list[tuple[str, str, list[str]]]:
    """(system_code, role_code, keywords) 列表；关键词按长度降序。"""
    import json

    out: list[tuple[str, str, list[str]]] = []
    for code, role_code, kw_json in (
        session.query(DeviceRole.system_code, DeviceRole.role_code, DeviceRole.match_keywords).all()
    ):
        try:
            kws = json.loads(kw_json or "[]")
        except (json.JSONDecodeError, TypeError):
            kws = []
        kws = [k for k in kws if k]
        if kws:
            out.append((code, role_code, sorted(kws, key=len, reverse=True)))
    # 长 role 优先，关键词内长词优先
    out.sort(key=lambda x: -len(x[2][0]) if x[2] else 0)
    return out


def map_item(session: Session, item_name: str) -> tuple[str, str] | None:
    """设备名 -> (system_code, role_code)；未命中返回 None。"""
    name = (item_name or "").lower()
    for code, role_code, kws in _roles(session):
        for kw in kws:
            if kw.lower() in name:
                return code, role_code
    return None


def systems_covered(session: Session, items: list[TenderItem]) -> dict[str, int]:
    """各系统覆盖的招标项计数。用于系统完整性提示。"""
    covered: dict[str, int] = {}
    for it in items:
        mapped = map_item(session, it.name)
        if mapped:
            covered[mapped[0]] = covered.get(mapped[0], 0) + 1
    return covered