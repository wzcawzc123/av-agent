"""SalesWorkflow：按 Plan 顺序执行 Agent，共享 WorkflowContext。

- 每步：get_agent → analyze → execute → validate，写 AgentExecutionLog 行；
- 步骤级异常写入 context.errors[step] 后继续后续步骤；
- 遵守 depends_on，依赖步骤在计划中缺失则跳过并记日志；
- WorkflowRun 行：cfg 缺 run_id 时自动创建（pending），结束时回写状态/进度/结果。
"""
import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WorkflowContext:
    project_id: int
    slots: dict
    cfg: dict
    session: object = None
    provider: object = None
    plan: object = None
    outputs: dict = field(default_factory=dict)
    files: dict = field(default_factory=dict)
    bom: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)
    status: str = "running"


def _bounded(data, max_str=500, max_items=50):
    """递归截断产出摘要，保证 detail_json 始终是合法 JSON。"""
    if isinstance(data, dict):
        return {k: _bounded(v, max_str, max_items) for k, v in list(data.items())[:max_items]}
    if isinstance(data, list):
        return [_bounded(x, max_str, max_items) for x in data[:max_items]]
    if isinstance(data, str) and len(data) > max_str:
        return data[:max_str] + "…"
    return data


def _summarize(context: WorkflowContext, step_name: str) -> dict:
    """步骤产出摘要：该步骤 outputs + 已生成文件 key + bom 数量。"""
    summary = {}
    out = context.outputs.get(step_name)
    if out is not None:
        summary["output"] = out
    if context.files:
        summary["files"] = list(context.files.keys())
    if context.bom:
        summary["bom"] = len(context.bom)
    return _bounded(summary)


class SalesWorkflow:
    @staticmethod
    async def run(context: WorkflowContext, progress_cb=None) -> dict:
        from app.db.session import get_session

        plan = context.plan
        steps = list(plan.steps) if plan is not None else []
        total = len(steps)
        step_names = {s.name for s in steps}
        cb = progress_cb or (lambda p, m: None)

        if context.session is not None:
            await SalesWorkflow._execute(context, steps, step_names, total, cb)
        else:
            with get_session() as s:
                context.session = s
                await SalesWorkflow._execute(context, steps, step_names, total, cb)
        return {"files": context.files, "errors": context.errors, "bom": context.bom}

    @staticmethod
    async def _execute(context: WorkflowContext, steps, step_names, total, cb):
        from app.agents.registry import get_agent
        from app.db.models import AgentExecutionLog, WorkflowRun

        s = context.session
        run = None
        run_id = context.cfg.get("run_id")
        if run_id:
            run = s.get(WorkflowRun, run_id)
        if run is None:
            run = WorkflowRun(
                project_id=context.project_id,
                plan_json=context.plan.to_json() if context.plan is not None else "[]",
                status="pending",
            )
            s.add(run)
            s.flush()
            context.cfg["run_id"] = run.id
        elif context.plan is not None:
            # 端点预建的行只带 status，回填计划内容
            run.plan_json = context.plan.to_json()
        run.status = "running"
        run.progress = 0

        for i, step in enumerate(steps):
            pct = int(i / total * 100) if total else 100
            started_at = datetime.utcnow()
            missing = [d for d in step.depends_on if d not in step_names]
            if missing:
                s.add(AgentExecutionLog(
                    run_id=run.id, project_id=context.project_id, step=step.name,
                    agent_name=step.agent, status="skipped",
                    detail_json=json.dumps({"reason": f"缺失依赖: {missing}"}, ensure_ascii=False),
                    started_at=started_at, finished_at=datetime.utcnow(),
                ))
                cb(pct, f"跳过 {step.name}（缺失依赖）")
                continue

            cb(pct, f"执行 {step.name} …")
            agent = None
            status = "success"
            error = ""
            detail = {}
            try:
                agent = get_agent(step.agent)
                await agent.analyze(context)
                await agent.execute(context)
                if not await agent.validate(context):
                    raise RuntimeError(f"{step.name} validate 未通过")
                detail = _summarize(context, step.name)
            except Exception as e:
                status = "failed"
                error = str(e)
                context.errors[step.name] = str(e)
            s.add(AgentExecutionLog(
                run_id=run.id, project_id=context.project_id, step=step.name,
                agent_name=agent.name if agent is not None else step.agent,
                status=status,
                detail_json=json.dumps(detail, ensure_ascii=False),
                error=error,
                started_at=started_at, finished_at=datetime.utcnow(),
            ))

        result = {"files": context.files, "errors": context.errors, "bom": context.bom}
        run.status = "success" if not context.errors else "failed"
        run.progress = 100
        run.result_json = json.dumps(result, ensure_ascii=False)
        run.error = json.dumps(context.errors, ensure_ascii=False) if context.errors else ""
        run.finished_at = datetime.utcnow()
        cb(100, "完成")
