# AV-Agent v3.0 企业架构落地设计

> 版本：3.0　|　对应仓库：wzcawzc123/av-agent　|　状态：落地实现中（与 1.x 旧链路并行兼容）

## 1. 总体架构

```
                        ┌───────────────────────────────────────────────┐
  手机浏览器/客户端        │                   AV-Agent v3.0                │
  HTTP + SSE             │                                               │
        │                │   ┌──────────┐    ┌──────────────────────┐    │
        ▼                │   │ Planner  │───▶│  SalesWorkflow        │    │
┌───────────────┐        │   │ create_  │    │  (顺序执行 + depends) │    │
│ app/api       │        │   │ plan()   │    └───────┬──────────────┘    │
│ routes_chat   │        │   └──────────┘            │ get_agent(step)   │
│ routes_generate│       │                           ▼                   │
│ routes_workflow│       │   ┌─────────────────────────────────────┐     │
│ …             │        │   │ Agent Runtime（app/agents/）         │     │
└───────┬───────┘        │   │ BaseAgent: analyze→execute→validate  │     │
        │ 对话槽位/确认    │   │ ├ requirement_analysis               │     │
        ▼                 │   │ ├ product_selection ──────────────┐ │     │
┌───────────────┐        │   │ ├ solution_design                  │ │     │
│ Orchestrator  │        │   │ ├ bom_generation                   │ │     │
│ 澄清/确认/意图  │        │   │ ├ quotation                       │ │     │
└───────┬───────┘        │   │ └ document_generation              │ │     │
        │ 需求确认        │   └──────────────────────┬────────────┼─┘     │
        ▼                 │                          ▼            ▼       │
┌───────────────┐        │   ┌──────────────────────────────────────┐    │
│ Projects/     │        │   │ Knowledge / Database / Memory         │    │
│ requirements  │        │   │ knowledge_documents（关键词检索）      │    │
│               │        │   │ organizations/users/solutions/…       │    │
└───────────────┘        │   │ workflow_runs / agent_execution_logs  │    │
                         │   │ Project.memory_json（remember/recall）│    │
                         │   └──────────────────────────────────────┘    │
                         └───────────────────────────────────────────────┘
```

数据流：`用户 → API → Planner → Agents → Knowledge/Database → Documents`。

## 2. 模块与类职责

### 2.1 Planner（`app/planner/planner.py`）

| 符号 | 职责 |
|---|---|
| `PlanStep`（dataclass） | `name: str`（步骤名=注册名）、`agent: str`、`params: dict`、`depends_on: list[str]`；`params/depends_on` 用 `field(default_factory=…)` |
| `Plan`（dataclass） | `steps: list[PlanStep]`；`to_json() -> str`（`json.dumps`）、`Plan.from_json(s) -> Plan` 反序列化 |
| `Planner` | `@staticmethod create_plan(requirement: dict, deliverables: list[str]) -> Plan`，纯确定性、不调 LLM |

计划规则（见 功能说明书 15.2）：

```
恒有:  requirement_analysis → product_selection
doc/ppt ∈ deliverables →  + solution_design(depends_on=[product_selection])
excel ∈ deliverables 或空(默认 excel) → + bom_generation(depends_on=[product_selection])
                                        + quotation(depends_on=[bom_generation])
ppt/pdf/deviation ∈ deliverables → + document_generation(
    depends_on=[solution_design]  # deliverables 含 doc/ppt 时
    | [bom_generation])           # 否则
```

### 2.2 Agent 运行时（`app/agents/`）

| 符号 | 职责 |
|---|---|
| `BaseAgent` | 类属性 `name="base" / description="" / depends_on=[]`；生命周期 `async analyze(context)`（默认 pass）、`async execute(context)`（默认 `raise NotImplementedError`）、`async validate(context) -> bool`（默认 True） |
| `AGENT_REGISTRY` | `dict[str, type[BaseAgent]]`，具体 Agent 模块导入时自动注册 |
| `register(name, cls)` / `get_agent(name)` / `list_agents()` | 注册 / 取实例（未知抛 KeyError 并附可用列表）/ 列名 |

具体 Agent（文件名即注册名，复用既有引擎/生成器，AI 调用走 `provider.chat` + `prompts.py` 常量）：

| Agent | 复用点 | 产出 |
|---|---|---|
| `requirement_analysis` | `engines/systems/scene.py::infer_systems` | `context.outputs["requirement_analysis"]`（规范化槽位） |
| `product_selection` | `engines/composer.py::compose_devices` + `db/template_store.py::find_config_template` | `context.devices`；`remember` 项目记忆 |
| `solution_design` | `generators/word_generator.py::build_doc_from_llm` + `find_doc_template` | `context.files["doc"]`（仅 deliverables 含 doc 时执行） |
| `bom_generation` | `generators/excel_generator.py::build_design_sheet` | Excel 文件；写 `Project.bom_json` |
| `quotation` | 统计 `context.bom` 总价/待询价 | 写 `Quotation` 行，`total_amount` 汇总 |
| `document_generation` | `build_ppt` / `convert_docx_to_pdf` / `generate_deviation_sheet` | `context.files["pdf"/"ppt"/"deviation"]` |

`context.files` 的 key 命名与 `generators/pipeline.py` 保持一致：`doc / pdf / excel / ppt / deviation`。

### 2.3 Workflow（`app/workflow/workflow.py`）

| 符号 | 职责 |
|---|---|
| `WorkflowContext`（dataclass） | `project_id: int, slots: dict, cfg: dict, session, provider=None, plan=None, outputs: dict, files: dict, bom: list, errors: dict, status="running"`；共享上下文 |
| `SalesWorkflow.run(context, progress_cb=None) -> dict` | 执行计划：run_id 取 `cfg.get("run_id")`，缺失则建 `WorkflowRun(status=pending, plan_json=plan.to_json())` 并回写 `cfg["run_id"]`；每步 `get_agent → analyze → execute → validate`；写 `AgentExecutionLog`；错误隔离；进度回调；结束更新 `WorkflowRun`；返回 `{"files", "errors", "bom"}` |

执行语义：

- **depends_on**：仅当依赖步骤全部执行成功才执行；依赖缺失/失败 → 跳过并记 `skipped` 日志；
- **错误隔离**：步骤级 `try/except`，异常写 `context.errors[step] = str(e)`，继续后续步骤；日志记 `failed` + error 字符串；
- **进度**：`progress_cb(percent: int, message: str)` 按步骤数均分 0-100，结束时 100；
- **落库**：`WorkflowRun`（status/progress/result_json=`json.dumps(result, ensure_ascii=False)`）与每步 `AgentExecutionLog`（step/agent_name/status/detail_json/error/started_at/finished_at）；
- **返回结构**与既有 `generate_deliverables` 一致：`{"files": context.files, "errors": context.errors, "bom": context.bom}`。

### 2.4 企业数据模型（`app/db/models.py`）

沿用现有风格（`Base`、`Mapped/mapped_column`、`datetime.utcnow` 默认、JSON 字段用 Text 存 JSON 字符串、`ForeignKey`）：

| 表 | 关键字段 |
|---|---|
| `organizations` | id, name, code(unique), contact, created_at |
| `users` | id, org_id(FK organizations.id, 可空), name, role, username(unique, 可空), created_at |
| `knowledge_documents` | id, title, doc_type, file_path, excerpt(Text), meta_json(Text), org_id(FK 可空), created_at |
| `solutions` | id, project_id(FK projects.id), title, content_json(Text), file_paths_json(Text), status, created_at |
| `quotations` | id, project_id(FK), total_amount(Float), items_json(Text), file_path, status, created_at |
| `workflow_runs` | id, project_id(FK), plan_json(Text), status, progress(Float), result_json(Text), error(Text), created_at, finished_at |
| `agent_execution_logs` | id, run_id(FK workflow_runs.id), project_id(FK), step, agent_name, status, detail_json(Text), error(Text), started_at, finished_at |
| `projects`（扩展） | + org_id(FK organizations.id, 可空), customer_name, memory_json(Text) |

### 2.5 记忆与知识库

- `app/db/memory.py`：`remember(session, project_id, key, value) -> None` 以 key 合并写 `Project.memory_json`（同 key 覆盖、不丢其它 key）；`recall(session, project_id, key=None) -> dict`（key 缺省返回整份记忆 dict）。
- `app/knowledge/retriever.py`：`register_document(session, title, doc_type, file_path, excerpt="", meta=None) -> int`；`list_documents(session) -> list[dict]`；`delete_document(session, doc_id) -> bool`；`retrieve(session, query, top_k=5) -> list[dict]`，对 title/excerpt/meta 关键词打分，纯 Python、无向量库。

### 2.6 API 与任务队列

- `app/api/routes_workflow.py`：`APIRouter(prefix="/api", tags=["workflow"], dependencies=[Depends(require_token)])`；
  `POST /api/workflow/runs`（读 `Project.requirement_json` 恢复 slots，deliverables 缺省 `["excel"]`，建 `WorkflowRun(status=pending)`，组 cfg，`submit_task` → `{run_id, task_id}`）；
  `GET /api/workflow/runs`（倒序）、`GET /api/workflow/runs/{run_id}`（含 plan 与 result）、`GET /api/workflow/runs/{run_id}/logs`；
  `GET/POST /api/organizations`、`GET/POST/DELETE /api/knowledge`。
- `app/tasks/queue.py`：`_run` 重构为 `load_model_config → get_provider → Planner.create_plan → WorkflowContext → SalesWorkflow.run(ctx, cb) → 写 Project.bom_json`；
  `submit_task / get_task / subscribe / SSE` 事件格式（`progress`/`done`）、`/api/generate` 的 422 门控、`task_id` 返回完全不变；`generate_deliverables` 保留原样。

### 2.7 部署（D 负责）

- 仓库根 `docker-compose.yml`：`postgres:16-alpine` + `redis:7-alpine`，带 volume、healthcheck、示例环境变量注释；
- `app/config.py`：`DATABASE_URL`（env `AV_DATABASE_URL`）、`REDIS_URL`（env `AV_REDIS_URL`）、`ENV`（env `AV_ENV`，默认 `dev`）；
- `app/db/session.py`：`get_engine(url=None)` 缺省优先 `settings.DATABASE_URL`；sqlite 保留 `check_same_thread=False`，非 sqlite 不加；
- `app/db/migrate.py`：`ensure_schema` 对非 sqlite 直接 return（PG 新表由 `create_all` 建，补列迁移仅 SQLite）；
- `requirements.txt`：追加 `psycopg[binary]>=3.1`、`redis>=5.0`（已确认与既有依赖不重复）。

## 3. 执行流程时序

```
POST /api/workflow/runs {project_id}
 1. 读 Project.requirement_json → slots；deliverables = body 或 ["excel"]
 2. WorkflowRun(status="pending", plan_json="[]") 落库 → run_id
 3. cfg = {deliverables, project_dir, run_id, …}
 4. task_id = submit_task(project_id, cfg, slots) → {run_id, task_id}

后台 _run(task):
 5. model_cfg = load_model_config(); provider = await get_provider(model_cfg)
 6. plan = Planner.create_plan(task.slots, task.cfg.get("deliverables", ["excel"]))
 7. ctx = WorkflowContext(project_id, slots, cfg, session, provider, plan)
 8. result = await SalesWorkflow.run(ctx, progress_cb=cb)
      for step in plan.steps:                      # 尊重 depends_on
          agent = get_agent(step.agent)
          await agent.analyze(ctx)                 # 默认 pass
          await agent.execute(ctx)                 # 复用引擎/生成器
          ok = await agent.validate(ctx)           # 默认 True
          # 写 AgentExecutionLog；异常隔离进 ctx.errors[step]
      # run_id 取自 ctx.cfg；更新 WorkflowRun(status/progress/result_json)
 9. 成功：Project.bom_json = dumps(result["bom"], ensure_ascii=False)
10. t.result = result；_notify(done)
```

## 4. 进度回调与事件

- `cb(p, m)` 沿用既有签名 `(percent: int, message: str)`，转发 `t.progress / t.message` 并 `_notify`；
- 事件格式与旧链路一致：`{"type": "progress", "percent": p, "message": m}`、`{"type": "done", "status": "success|failed", "result": {...}}`；
- 前端与旧 `/api/generate` 使用同一套 SSE 订阅，无需改动。

## 5. 向后兼容说明

1. **旧生成链路保留**：`/api/generate`、`generate_deliverables`（`app/generators/pipeline.py`）原样保留，既有测试继续覆盖；
2. **接口与事件不变**：`/api/tasks/{task_id}`、SSE `progress`/`done`、422 门控、`task_id` 返回结构不变；
3. **数据兼容**：既有 SQLite 库通过 `create_all` 自动建新表 + `ensure_schema` 补列（仅 SQLite），无需手动迁移；
4. **模型层复用**：v3.0 Agent 与旧管线共用 `compose_devices / build_doc_from_llm / build_design_sheet / build_ppt / convert_docx_to_pdf / find_config_template / find_doc_template` 与 `LLMProvider.chat` 体系；
5. **默认部署不变**：未设置 `AV_DATABASE_URL` 时仍为内置 SQLite + 内存队列，单机体验与 1.x 一致；
6. **新表命名**：`organizations / users / knowledge_documents / solutions / quotations / workflow_runs / agent_execution_logs`，与现有表无命名冲突。

## 6. 测试覆盖（tests/unit/）

| 文件 | 覆盖点 |
|---|---|
| `test_planner.py` | 步骤结构与顺序、depends_on、`Plan.to_json/from_json` 往返、空 deliverables 默认 excel |
| `test_agents.py` | 注册表含 6 个名字、register/get_agent/list_agents、未知名 KeyError 带可用列表、BaseAgent 默认生命周期 |
| `test_workflow.py` | 假 Agent（继承 BaseAgent）跑通 run；WorkflowRun/AgentExecutionLog 落库；cfg.run_id 复用；缺失依赖跳过记 skipped；步骤异常隔离；返回结构与进度回调 |
| `test_enterprise_models.py` | Organization/User/KnowledgeDocument/Solution/Quotation/WorkflowRun/AgentExecutionLog CRUD；Project 扩展列；memory remember 合并 / recall |
| `test_knowledge.py` | register/list/delete/retrieve；title/excerpt/meta 关键词命中；top_k 与空结果 |

测试风格与既有单测一致：`get_engine("sqlite:///tmp/…") + get_session` 隔离、`Base.metadata.create_all`；
mock LLM 用返回固定字符串的 FakeProvider（参照 `tests/e2e/test_api_flow.py`）。
