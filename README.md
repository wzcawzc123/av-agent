# AV Agent — 音视频售前工作流 Agent

为音视频行业销售技术工程师打造的对话式工作流 Agent：发需求 → Agent 澄清 → 确认 → 依托公司产品库与模板库，由大模型语义适配，自动生成交付文件（Word 方案 / Excel 偏离表 / PPT）。

## 核心能力

- **对话式需求采集**：识别缺口（面积、场景、预算、品牌、交付物）并逐项追问
- **交付物确认**：一次产出文字方案(Word)、偏离表(Excel)、PPT，确认后执行
- **产品库管理**：导入/更新公司产品 Excel（名称/参数/型号/底价/市场价）
- **模板库管理**：常规配置模板（按面积匹配）、文字方案模板、PPT 母版、偏离表模板
- **模型提供商体系**：内置 13 家主流提供商（OpenAI/Anthropic/阿里百炼/DeepSeek/Kimi/MiMo/MiniMax/阶跃星辰/硅基流动/OpenRouter/智谱/文心/Gemini），**支持用户自定义新增任意 OpenAI 兼容 / Anthropic / Gemini 提供商**（填名称 + Base URL + API Key + 模型列表即可），可复制/重置内置、远程拉取模型列表、一键测试连接
- **招标改单**：上传招标清单 Excel/Word/PDF，自动解析设备需求，按品牌/型号/参数匹配产品库，生成改单快照并支持人工确认，一键确认转 BOM
- **报价清单编辑（BOM）**：项目文件页一键打开清单编辑器，增删行、改数量/单价/备注，小计实时计算，一键重出 Excel 报价表（单价为 0 自动标注「待询价」）
- **清单存为配置模板**：编辑后的清单一键存入模板库，按面积/场景自动匹配，同类项目直接复用
- **模板文件上传**：文字方案/PPT 模板 docx/pptx 直接上传注册，无需命令行
- **产品改价**：产品库每项可改底价/市场价，方案生成时自动回填最新价格
- **文档生成**：Word 方案按需转 PDF；偏离表 Excel；PPT 套母版
- **手机端 UI**：聊天、需求确认、进度条、文件下载、产品上传、模板管理、提供商管理，一页搞定
- **局域网联动**：手机浏览器控制电脑端完成方案输出，无需安装 App
- **企业架构（v3.0）**：Planner 拆解需求 → Agent 运行时（6 个可插拔 Agent）→ SalesWorkflow 顺序执行（支持依赖/跳过/错误隔离）→ 企业数据模型（组织/用户/知识库/方案/报价/运行日志），知识库关键词检索 + 项目记忆，PostgreSQL/Redis 可选部署（默认仍为 SQLite，零迁移成本）

## 企业架构（v3.0）

```
用户 → API → Planner → Agents → Knowledge / Database → Documents
```

v3.0 在保留原有「对话澄清 → 确认 → 生成」链路的基础上，将生成阶段重构为**计划驱动的 Agent 工作流**：

1. **Planner**（`app/planner/`）：把确认后的需求确定性拆解为计划步骤，不调 LLM。恒有
   `requirement_analysis → product_selection`，按交付物追加
   `solution_design`（doc/ppt）、`bom_generation + quotation`（excel/默认）、`document_generation`（ppt/pdf/deviation），步骤带 `depends_on`。
2. **Agent 运行时**（`app/agents/`）：`BaseAgent` 定义 `analyze / execute / validate`
   生命周期；6 个具体 Agent（`requirement_analysis / product_selection / solution_design /
   bom_generation / quotation / document_generation`）模块级自动注册进 `AGENT_REGISTRY`，
   复用既有 `engines / generators / llm` 能力，AI 调用统一走 `provider.chat` + `prompts.py` 常量。
3. **SalesWorkflow**（`app/workflow/`）：按计划顺序执行、共享 `WorkflowContext`，
   尊重 `depends_on`（缺失依赖自动跳过并记 `skipped` 日志）、步骤级错误隔离
   （异常写 `errors` 继续后续步骤）、进度回调 0-100；
   每次运行落库 `WorkflowRun` 与逐步骤 `AgentExecutionLog`，返回结构与
   `generate_deliverables` 一致（`{"files", "errors", "bom"}`）。
4. **企业数据模型**（`app/db/models.py`）：新增 `Organization / User / KnowledgeDocument /
   Solution / Quotation / WorkflowRun / AgentExecutionLog`，`Project` 扩展
   `org_id / customer_name / memory_json`（Project Memory，`app/db/memory.py`
   提供 `remember / recall` 合并读写）。
5. **知识库**（`app/knowledge/`）：`KnowledgeDocument` + 纯 Python 关键词检索
   （title/excerpt/meta 打分，无需向量库），`register_document / list_documents /
   delete_document / retrieve`。
6. **部署**：仓库根 `docker-compose.yml` 提供 PostgreSQL 16 + Redis 7，
   通过 `AV_DATABASE_URL / AV_REDIS_URL / AV_ENV` 切换（未设置时沿用内置 SQLite，行为不变）。

旧接口 `/api/generate`、SSE 任务事件（`progress` / `done`）与前端完全不变，
测试仍覆盖原有生成管线。设计文档见 [docs/architecture-3.0.md](docs/architecture-3.0.md)。

## 技术栈

| 层 | 选型 |
|---|---|
| Web 框架 | FastAPI + Uvicorn |
| 前端 | 单页 HTML+JS（手机浏览器访问） |
| 数据库 | SQLite 默认（SQLAlchemy）；企业部署可选 PostgreSQL 16（docker-compose + `AV_DATABASE_URL`） |
| 任务队列/缓存 | 内存队列默认；可选 Redis 7（`AV_REDIS_URL`） |
| 文档生成 | python-docx / openpyxl / python-pptx |
| PDF 转换 | LibreOffice headless |
| 模型调用 | httpx + Provider 适配器（可插拔，13 内置 + 自定义） |
| 打包分发 | PyInstaller（Windows exe） |
| 测试 | pytest + pytest-asyncio + responses |

## 目录结构

```
av-agent/
├── app/
│   ├── api/            # REST API 端点（含 routes_workflow：工作流/组织/知识库）
│   ├── orchestrator/   # 对话状态机、意图识别、澄清、确认
│   ├── planner/        # v3.0 计划生成：PlanStep / Plan / Planner（确定性拆解需求）
│   ├── agents/         # v3.0 Agent 运行时：BaseAgent 生命周期 + 注册表 + 6 个具体 Agent
│   ├── workflow/       # v3.0 SalesWorkflow：顺序执行计划、WorkflowContext、进度回调、运行/日志落库
│   ├── knowledge/      # v3.0 知识库：KnowledgeDocument + 关键词检索（RAG）
│   ├── llm/            # 模型 Provider 适配层（可插拔）
│   │   ├── providers/  # openai_compat / anthropic / gemini 客户端
│   │   ├── provider_store.py  # 内置提供商 + 官方模型目录 + 来源注册 + 增删改查
│   │   └── registry.py # 客户端工厂（按 provider 类型分派）
│   ├── generators/     # Word/Excel/PPT 生成 + PDF 转换
│   ├── tasks/          # 异步任务队列 + SSE 进度
│   ├── db/             # SQLite/PG 模型、产品导入、模板存储、memory.py（项目记忆）
│   └── security/       # 访问鉴权、密钥工具
├── static/             # 手机端单页前端（聊天/产品/模板/提供商）
├── data/               # 运行时生成：数据库、密钥、providers.json、model.json（git 忽略）
├── output/             # 生成文件输出（git 忽略）
├── uploads/            # 上传文件暂存（git 忽略）
├── tests/              # 单元 / 端到端测试
├── docs/               # 功能说明书、使用说明书、architecture-3.0.md 设计文档
├── docker-compose.yml  # 企业部署：PostgreSQL 16 + Redis 7（可选）
├── exe_entry.py        # PyInstaller 打包入口
├── av-agent.spec       # PyInstaller 打包配置
├── build_exe.bat       # Windows 一键打包脚本
├── README.md
└── requirements.txt
```

## 快速开始（源码运行）

```bash
# 安装依赖（需 Python ≥ 3.12）
pip install -r requirements.txt

# 启动服务（0.0.0.0:8000，务必设置访问口令）
AV_ACCESS_TOKEN=你的口令 uvicorn app.main:app --host 0.0.0.0 --port 8000

# 手机浏览器访问（手机与电脑同一局域网）
# http://<电脑局域网IP>:8000
```

首次使用：右上角 ⚙️ 选择/新增模型提供商并填 API Key → 📦 上传产品 Excel → 对话描述需求 → 确认后自动生成并下载。

## 打包为 Windows exe（用户免装 Python）

在 Windows 电脑上执行：

```bat
build_exe.bat
```

脚本自动安装依赖与 PyInstaller 并打包，产出 `dist\AVAgent.exe`。把该 exe 发给用户：

1. 双击 `AVAgent.exe` 即启动服务，浏览器自动打开界面；
2. 首次运行在 exe 同级目录生成 `data\`（数据库 + 访问口令，重启不变）；
3. 终端窗口会显示本机/手机访问地址与访问口令。

> 打包需在 Windows 上执行（PyInstaller 不支持跨平台编译）；生成 PDF 依赖电脑安装 LibreOffice。

## 文档

- [功能说明书](docs/功能说明书.md) — 功能清单、系统架构、数据模型、API 参考
- [使用说明书](docs/使用说明书.md) — 部署、配置、日常操作、常见问题
- [v3.0 架构设计](docs/architecture-3.0.md) — Planner / Agent 运行时 / Workflow / 企业数据模型 / 部署设计
- [设计文档](docs/superpowers/specs/2026-09-04-av-sales-workflow-agent-design.md)

## 状态

- [x] 设计文档 v0.1（2026-09-04）
- [x] M1 骨架：FastAPI + SQLite + 状态机 + 基础对话
- [x] M2 数据：产品 Excel 导入、模板库管理
- [x] M3 生成：LLM 适配 + Word/Excel/PPT + PDF 转换
- [x] M4 体验：SSE 进度、项目管理、文件下载、鉴权
- [x] M5 加固：单测全覆盖、错误处理、文档
- [x] M6 分发：手机端 UI 补全（产品/模板管理）+ Windows exe 打包配置
- [x] M7 模型：13 家内置提供商（含 MiMo）+ 自定义提供商体系（参考 ETA-2 逻辑）
- [x] v3.0 企业架构：Planner / Agent 运行时（6 Agent）/ SalesWorkflow / 企业数据模型 / 知识库检索 / 项目记忆（SQLite 兼容，PG+Redis 可选部署）

## 手机端使用（PWA）

前端已内置 PWA 支持（`manifest.json` + 图标 + Service Worker）。手机浏览器打开页面后：
Chrome → 菜单 →「添加到主屏幕」，桌面即生成 **AV Agent** 图标，点开全屏运行，接近原生 App 体验。
Service Worker 仅 HTTPS/localhost 下启用离线缓存；局域网 HTTP 访问不影响功能，只是无离线缓存。

## 更新与发布

> 完整发布流程见 [docs/发布更新操作手册.md](docs/发布更新操作手册.md)（含 gh 命令、私有仓库 Token 配置、常见问题）。

**客户端更新机制**：客户端「设置 → 软件更新」检查 GitHub Releases（默认 `https://api.github.com/repos/wzcawzc123/av-agent/releases/latest`），
比较本地版本号，有新版时给出更新说明与下载链接（exe 资产）。私有仓库需在更新配置中填入 GitHub Token（只读 Release 权限即可）。

**发布新版流程**：
1. 修改 `app/version.py` 的 `VERSION`，提交推送；
2. 在 Windows 上运行 `build_exe.bat` 生成 `dist\AVAgent.exe`；
3. 创建 Release：`gh release create v1.0.1 dist\AVAgent.exe --title "v1.0.1" --notes "更新说明"`（或 GitHub 网页上传）；
4. 客户端点击「检查更新」即可发现并下载新版。
