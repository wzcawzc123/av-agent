import json
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.api.deps import require_token
from app.api.routes_chat import get_session_slots
from app.tasks.queue import submit_task, get_task, subscribe

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


class GenerateIn(BaseModel):
    project_id: int


@router.post("/generate")
def generate(body: GenerateIn):
    from app.config import settings

    slots = get_session_slots(body.project_id)
    project_dir = f"{settings.OUTPUT_DIR}/proj_{body.project_id}"
    cfg = {
        "deliverables": slots.get("deliverables", ["doc"]),
        "project_dir": project_dir,
        "template_paths": {},
    }
    task_id = submit_task(body.project_id, cfg, slots)
    return {"task_id": task_id}


@router.get("/tasks/{task_id}")
def task_status(task_id: str):
    t = get_task(task_id)
    if not t:
        return {"error": "任务不存在"}
    return {"id": t.id, "status": t.status, "progress": t.progress,
            "message": t.message, "result": t.result}


@router.get("/tasks/{task_id}/stream")
async def task_stream(task_id: str):
    t = get_task(task_id)
    if not t:
        return {"error": "任务不存在"}

    async def gen():
        async for event in subscribe(t.project_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/download")
def download(path: str):
    from app.config import settings

    real = os.path.realpath(path)
    out_dir = os.path.realpath(settings.OUTPUT_DIR)
    if not real.startswith(out_dir + os.sep) or not os.path.isfile(real):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(real, filename=os.path.basename(real))
