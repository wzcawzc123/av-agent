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
    asyncio.get_running_loop().create_task(_run(t))
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
    # v3.0：交付由 Planner → SalesWorkflow 编排（generate_deliverables 已由 workflow 取代，
    # 但保留在 app/generators/pipeline.py 供 tests 直接调用）。
    from app.db.session import get_session
    from app.llm.registry import get_provider, load_model_config
    from app.planner.planner import Planner
    from app.workflow.workflow import SalesWorkflow, WorkflowContext

    t.status = "running"
    try:
        cfg = load_model_config()
        provider = await get_provider(cfg)

        def cb(p, m):
            t.progress, t.message = p, m
            _notify(t.project_id, {"type": "progress", "percent": p, "message": m})

        with get_session() as s:
            plan = Planner.create_plan(t.slots, t.cfg.get("deliverables", ["excel"]))
            ctx = WorkflowContext(project_id=t.project_id, slots=t.slots, cfg=t.cfg,
                                  session=s, provider=provider, plan=plan,
                                  outputs={}, files={}, bom=[], errors={})
            t.result = await SalesWorkflow.run(ctx, cb)
            bom = t.result.get("bom") or []
            if bom:
                from app.db.models import Project
                from json import dumps
                p = s.query(Project).filter_by(id=t.project_id).first()
                if p:
                    p.bom_json = dumps(bom, ensure_ascii=False)
        t.status = "success"
    except Exception as e:
        t.status = "failed"
        t.message = str(e)
        _mark_run_failed(t)
    _notify(t.project_id, {"type": "done", "status": t.status, "result": t.result})


def _mark_run_failed(t: Task):
    """兜底：工作流异常退出时把 WorkflowRun 记录置为 failed（正常收尾由 SalesWorkflow 自己完成）。"""
    run_id = t.cfg.get("run_id")
    if not run_id:
        return
    from json import dumps

    from app.db.models import WorkflowRun
    from app.db.session import get_session

    try:
        with get_session() as s:
            r = s.query(WorkflowRun).filter_by(id=run_id).first()
            if r:
                r.status = "failed"
                r.error = t.message[:2000]
                if t.result:
                    r.result_json = dumps(t.result, ensure_ascii=False)
    except Exception:
        pass
