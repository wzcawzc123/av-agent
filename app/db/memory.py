"""Project Memory：以 Project.memory_json 持久化的键值记忆（JSON 文本存储）。"""
import json

from app.db.models import Project


def _load(memory_json: str) -> dict:
    try:
        mem = json.loads(memory_json or "{}")
        return mem if isinstance(mem, dict) else {}
    except (TypeError, ValueError):
        return {}


def remember(session, project_id: int, key: str, value) -> None:
    """合并写入一条项目记忆；项目不存在时静默忽略（幂等）。"""
    p = session.get(Project, project_id)
    if p is None:
        return
    mem = _load(p.memory_json)
    mem[key] = value
    p.memory_json = json.dumps(mem, ensure_ascii=False)


def recall(session, project_id: int, key=None) -> dict:
    """读取项目记忆；key 缺省返回全部 dict，指定 key 返回对应值（无则 None）。"""
    p = session.get(Project, project_id)
    if p is None:
        return {} if key is None else None
    mem = _load(p.memory_json)
    if key is None:
        return mem
    return mem.get(key)
