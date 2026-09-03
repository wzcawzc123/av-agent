import asyncio
import uuid
from dataclasses import dataclass, field


@dataclass
class Task:
    id: str
    project_id: int
    cfg: dict
    slots: dict
    status: str = "pending"
    progress: int = 0
    message: str = ""
    result: dict = field(default_factory=dict)


_tasks: dict[str, Task] = {}
_watchers: dict[int, list[asyncio.Queue]] = {}


def submit_task(project_id: int, cfg: dict, slots: dict) -> str:
    t = Task(id=uuid.uuid4().hex, project_id=project_id, cfg=cfg, slots=slots)
    _tasks[t.id] = t
    asyncio.get_event_loop().create_task(_run(t))
    return t.id


def get_task(task_id: str):
    return _tasks.get(task_id)


def _notify(project_id: int, event: dict):
    for q in _watchers.get(project_id, []):
        q.put_nowait(event)


async def subscribe(project_id: int):
    q = asyncio.Queue()
    _watchers.setdefault(project_id, []).append(q)
    try:
        while True:
            yield await q.get()
    finally:
        if q in _watchers.get(project_id, []):
            _watchers[project_id].remove(q)


async def _run(t: Task):
    from app.db.session import get_session
    from app.llm.registry import get_provider, load_model_config
    from app.generators.pipeline import generate_deliverables

    t.status = "running"
    try:
        cfg = load_model_config()
        provider = await get_provider(cfg)

        def cb(p, m):
            t.progress, t.message = p, m
            _notify(t.project_id, {"type": "progress", "percent": p, "message": m})

        with get_session() as s:
            t.result = await generate_deliverables(t.cfg, provider, t.slots, s, cb)
        t.status = "success"
    except Exception as e:
        t.status = "failed"
        t.message = str(e)
    _notify(t.project_id, {"type": "done", "status": t.status, "result": t.result})
