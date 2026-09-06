"""后台任务队列：内存 Task + TaskRecord 持久化（A9）+ Redis 事件桥（A8）。

- 未配置 REDIS_URL 时行为与旧版完全一致（内存 _tasks + 每项目 watcher 队列）；
- 配置 REDIS_URL（多进程/多副本部署）时，_notify 额外把进度事件 publish 到
  av:tasks:<project_id> 频道，subscribe 侧轮询接收，实现跨进程 SSE；
- submit_task 落 TaskRecord 行，运行中回写进度/结果；进程重启后
  recover_stale_tasks(engine) 把遗留 running/pending 记录置为 failed。
"""
import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime


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
    error: str = ""


_tasks: dict[str, Task] = {}
_watchers: dict[int, list[asyncio.Queue]] = {}


def _redis_url() -> str:
    try:
        from app.config import settings
    except Exception:
        return ""
    return (os.environ.get("AV_REDIS_URL") or settings.REDIS_URL or "").strip()


def _submit_record(t: Task) -> None:
    try:
        from app.db.models import TaskRecord
        from app.db.session import get_session

        dels = ",".join(t.cfg.get("deliverables") or []) or "excel"
        with get_session() as s:
            s.add(TaskRecord(task_key=t.id, project_id=t.project_id,
                             deliverable_type=dels[:50], status=t.status,
                             progress=t.progress, message=t.message, error="",
                             result_json="{}", file_path=""))
    except Exception:
        pass


def _persist_record(t: Task, *, finished: bool = False) -> None:
    try:
        from app.db.models import TaskRecord
        from app.db.session import get_session

        with get_session() as s:
            rec = s.query(TaskRecord).filter_by(task_key=t.id).first()
            if rec is None:
                return
            rec.status = t.status
            rec.progress = t.progress
            rec.message = (t.message or "")[:2000]
            rec.error = (t.error or "")[:2000]
            rec.result_json = json.dumps(t.result or {}, ensure_ascii=False)
            files = (t.result or {}).get("files") or {}
            if files:
                rec.file_path = next(iter(files.values()), "")
            if finished:
                rec.finished_at = datetime.utcnow()
    except Exception:
        pass


def recover_stale_tasks(engine) -> int:
    """启动时把遗留 running/pending 的 TaskRecord 置为 failed（服务重启中断）。"""
    from app.db.models import TaskRecord
    from app.db.session import get_session

    n = 0
    try:
        with get_session(engine) as s:
            stale = (s.query(TaskRecord)
                     .filter(TaskRecord.status.in_(["pending", "running"])).all())
            for rec in stale:
                rec.status = "failed"
                rec.error = "服务重启，任务中断（未完成交付物）"
                rec.finished_at = datetime.utcnow()
                n += 1
    except Exception:
        return 0
    return n


def submit_task(project_id: int, cfg: dict, slots: dict) -> str:
    t = Task(id=uuid.uuid4().hex, project_id=project_id, cfg=cfg, slots=slots)
    _tasks[t.id] = t
    _submit_record(t)
    asyncio.get_running_loop().create_task(_run(t))
    return t.id


def get_task(task_id: str):
    """内存命中优先；重启后内存 miss 时从 TaskRecord 恢复只读视图。"""
    t = _tasks.get(task_id)
    if t is not None:
        return t
    try:
        from app.db.models import TaskRecord
        from app.db.session import get_session

        with get_session() as s:
            rec = s.query(TaskRecord).filter_by(task_key=task_id).first()
        if rec is None:
            return None
        try:
            result = json.loads(rec.result_json or "{}")
        except Exception:
            result = {}
        t = Task(id=rec.task_key, project_id=rec.project_id,
                 cfg={"deliverables": rec.deliverable_type.split(",")
                      if rec.deliverable_type else [], "project_id": rec.project_id},
                 slots={}, status=rec.status, progress=rec.progress,
                 message=rec.message, result=result, error=rec.error)
        _tasks[t.id] = t
        return t
    except Exception:
        return None


async def _publish_redis(project_id: int, event: dict) -> None:
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(_redis_url(), socket_connect_timeout=2)
        try:
            await r.publish(f"av:tasks:{project_id}",
                            json.dumps(event, ensure_ascii=False))
        finally:
            await r.aclose()
    except Exception:
        pass


_main_loop = None  # 任务协程所在事件循环（跨线程发布 Redis 用）


def _notify(project_id: int, event: dict, task_id: str | None = None):
    if task_id:
        event = {**event, "task_id": task_id}
    for q in _watchers.get(project_id, []):
        q.put_nowait(event)
    if _redis_url():
        try:
            asyncio.get_running_loop().create_task(_publish_redis(project_id, event))
        except RuntimeError:
            # 非事件循环线程（如 def 路由线程池）：转发到主循环，避免事件静默丢失
            if _main_loop is not None and _main_loop.is_running():
                asyncio.run_coroutine_threadsafe(_publish_redis(project_id, event), _main_loop)


async def subscribe(project_id: int):
    """订阅项目进度事件：未配 Redis 走内存队列；已配置时走 Redis pub/sub。"""
    if not _redis_url():
        q = asyncio.Queue()
        _watchers.setdefault(project_id, []).append(q)
        try:
            while True:
                yield await q.get()
        finally:
            if q in _watchers.get(project_id, []):
                _watchers[project_id].remove(q)
        return

    import redis.asyncio as aioredis

    r = aioredis.from_url(_redis_url(), socket_connect_timeout=2)
    ps = r.pubsub()
    await ps.subscribe(f"av:tasks:{project_id}")
    try:
        while True:
            msg = await ps.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg.get("type") == "message":
                try:
                    yield json.loads(msg["data"])
                except (TypeError, ValueError):
                    continue
    finally:
        try:
            await ps.unsubscribe()
            await ps.aclose()
            await r.aclose()
        except Exception:
            pass


async def _run(t: Task):
    # v3.0：交付由 Planner → SalesWorkflow 编排（generate_deliverables 已由 workflow 取代，
    # 但保留在 app/generators/pipeline.py 供 tests 直接调用）。
    from app.db.session import get_session
    from app.llm.registry import get_provider, load_model_config
    from app.planner.planner import Planner
    from app.workflow.workflow import SalesWorkflow, WorkflowContext

    t.status = "running"
    _persist_record(t)
    try:
        cfg = load_model_config()
        provider = await get_provider(cfg)

        global _main_loop
        _main_loop = asyncio.get_running_loop()

        def cb(p, m):
            t.progress, t.message = p, m
            _notify(t.project_id, {"type": "progress", "percent": p, "message": m}, task_id=t.id)

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
        t.error = str(e)
        t.message = str(e)
        _mark_run_failed(t)
    _persist_record(t, finished=True)
    _notify(t.project_id, {"type": "done", "status": t.status,
                           "error": t.error, "result": t.result}, task_id=t.id)


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
                r.error = (t.error or t.message or "")[:2000]
                if t.result:
                    r.result_json = dumps(t.result, ensure_ascii=False)
    except Exception:
        pass
