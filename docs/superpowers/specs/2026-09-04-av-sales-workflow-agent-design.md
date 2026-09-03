# 音视频售前工作流 Agent — 设计文档

- 日期：2026-09-04
- 状态：草案待审
- 作者：薰儿 / Eta
- 版本：v0.1

---

## 1. 项目概述

### 1.1 背景
用户（伍泽成 / 薰儿）是音视频行业销售技术工程师，工作覆盖：需求对接、产品选型、方案配置、系统图/布点图/布线图绘制、商务报价、技术宣讲、声场模拟（EASE Focus）、音响调试（SMAART）、中控矩阵编程、项目跟进与验收培训。

高频痛点是**售前方案产出重复且耗时**：每个项目都要从需求出发生成文字设计方案、设备清单、偏离表、宣讲 PPT。

### 1.2 目标
构建一个**对话式工作流 Agent**：用户发出需求（如"100平会议室方案"），Agent 主动澄清缺失信息，确认交付物清单后，依托公司产品库与模板库，由大模型语义适配，自动生成对应项目的交付文件（Word 方案 / Excel 偏离表 / PPT）。

### 1.3 成功标准
- 从"发需求"到"拿到方案文件"全流程可对话完成，人工干预最小化
- 交付文件可编辑、可套公司模板、排版可用
- 产品库与模板库支持持续更新（新增产品、替换模板）而不改代码
- 手机可通过局域网控制电脑端完成方案输出
- 大模型层可插拔，用户自配 API Key，内置主流提供商

---

## 2. 需求分析

### 2.1 功能需求

| 编号 | 需求 | 说明 |
|---|---|---|
| FR1 | 对话式需求采集 | 用户发需求 → Agent 识别缺口并提问（面积、场景、预算、品牌偏好、交付物） |
| FR2 | 交付物确认 | 支持一次产出多份文件：文字方案(Word)、偏离表(Excel)、PPT；确认后执行 |
| FR3 | 产品库管理 | 导入/更新公司产品 Excel（名称、参数、型号、低价、市场价），支持查询 |
| FR4 | 模板库管理 | 常规配置模板（100/200/300平）、文字方案模板、PPT 母版、偏离表模板，可增删替换 |
| FR5 | 大模型适配 | 依据实际项目需求语义适配模板，生成设备清单与方案内容 |
| FR6 | 文档生成 | Word 方案、Excel 偏离表、PPT 生成；文字方案默认 Word，用户要求 PDF 时再导出 PDF |
| FR7 | 局域网联动 | 手机通过局域网访问电脑端 Web 服务，发起任务、查看进度、下载文件 |
| FR8 | 模型配置 | 用户自配 API Key，内置主流模型提供商，可切换模型 |

### 2.2 非功能需求

| 编号 | 需求 | 说明 |
|---|---|---|
| NFR1 | 安全 | API Key 加密存储（本地密钥）；局域网访问需简单鉴权（启动口令） |
| NFR2 | 可靠性 | 文档生成失败可重试；生成任务有状态记录与日志 |
| NFR3 | 性能 | 单文档生成在模型可用时 ≤ 2 分钟；常规查询响应 < 1s |
| NFR4 | 可维护性 | 分层架构 + 模块化 + 单元测试覆盖核心逻辑 |
| NFR5 | 可扩展性 | 模型 Provider、文档类型、模板类型均为插件式扩展 |
| NFR6 | 数据持久 | SQLite 本地持久化，产品/模板更新即时生效 |

---

## 3. 系统架构

### 3.1 总体架构

```
┌──────────────┐  局域网(HTTP/WebSocket)   ┌───────────────────────────────┐
│  手机端       │ ───────────────────────▶ │  电脑端（核心引擎）             │
│ (浏览器 PWA)  │                          │                               │
└──────────────┘                          │  ┌─────────────────────────┐   │
                                          │  │ Web 服务层 (FastAPI)     │   │
                                          │  │  - REST API             │   │
                                          │  │  - SSE 任务进度          │   │
                                          │  └───────────┬─────────────┘   │
                                          │              ▼                 │
                                          │  ┌─────────────────────────┐   │
                                          │  │ 对话编排引擎 (状态机)     │   │
                                          │  │ 采集→澄清→确认→生成→交付  │   │
                                          │  └───────────┬─────────────┘   │
                                          │   ┌──────────┼──────────┐      │
                                          │   ▼          ▼          ▼      │
                                          │ ┌──────┐ ┌──────┐ ┌─────────┐  │
                                          │ │LLM层 │ │文档生成│ │ 任务队列 │  │
                                          │ │(可插拔)│ │管线   │ │         │  │
                                          │ └──────┘ └──────┘ └─────────┘  │
                                          │   ▲          ▲                  │
                                          │   │          │                  │
                                          │ ┌─────────────────────────┐   │
                                          │ │ 数据层: SQLite           │   │
                                          │ │ 产品库/模板库/项目/任务   │   │
                                          │ │ + 文件存储(模板/输出)     │   │
                                          │ └─────────────────────────┘   │
                                          └───────────────────────────────┘
```

### 3.2 部署拓扑
- **电脑端**：Python 服务（FastAPI + uvicorn），监听局域网 IP 的指定端口（默认 8000）
- **手机端**：浏览器访问 `http://<电脑IP>:8000`，无需安装 App（PWA 可离线缓存界面）
- **文件输出**：统一输出目录（`output/<项目名>/`），手机端可预览与下载

### 3.3 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| Web 框架 | FastAPI + Uvicorn | 异步、自动 OpenAPI 文档、SSE 支持 |
| 前端 | 单页 HTML+JS（原生/Vue CDN） | 零构建、手机兼容、开发轻量 |
| 数据库 | SQLite（SQLAlchemy） | 单机持久化、零运维、易备份 |
| 文档生成 | python-docx / openpyxl / python-pptx | 生态成熟、可套模板 |
| PDF 转换 | LibreOffice headless 或 docx2pdf | Word→PDF 保排版 |
| 模型调用 | httpx + Provider 适配器 | 统一接口、多提供商 |
| 测试 | pytest + pytest-asyncio + responses(模拟HTTP) | 单测/集成/E2E 全覆盖 |
| 密钥 | cryptography (Fernet) | API Key 本地加密 |

---

## 4. 核心工作流（对话状态机）

```
                    ┌──────────────┐
                    │    IDLE      │ 等待新需求
                    └──────┬───────┘
                           │ 用户发需求
                           ▼
                    ┌──────────────┐   缺信息(面积/场景/交付物/预算)
                    │  COLLECTING  │◀────────── 追问
                    └──────┬───────┘
                           │ 信息齐全
                           ▼
                    ┌──────────────┐
                    │  CONFIRMING  │ 汇总需求+交付物清单，请求确认
                    └──────┬───────┘
                           │ 用户确认/修改
                           ▼
                    ┌──────────────┐
                    │  GENERATING  │ 任务入队→LLM适配→文档生成→PDF(如需)
                    └──────┬───────┘
                           │ 完成/失败(可重试)
                           ▼
                    ┌──────────────┐
                    │   DELIVERED  │ 文件列表+下载入口
                    └──────────────┘
```

**状态说明**
- `COLLECTING`：通过 LLM 意图识别 + 槽位填充，识别缺失字段（面积、用途、预算、品牌、交付物类型），逐项提问
- `CONFIRMING`：以结构化摘要回显，用户可确认或修改
- `GENERATING`：异步任务，前端 SSE 推送进度（模板匹配中 / 大模型适配中 / 生成 Word / 生成 Excel / 生成 PPT / 完成）

---

## 5. 模块设计

### 5.1 Web 服务层 (`app/api/`)
| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/chat` | POST | 对话消息（含状态机流转） |
| `/api/projects` | GET/POST | 项目列表 / 新建 |
| `/api/projects/{id}` | GET | 项目详情与生成记录 |
| `/api/generate` | POST | 手动触发生成（确认后调用） |
| `/api/tasks/{id}/stream` | GET(SSE) | 任务进度流 |
| `/api/products` | GET/POST | 产品查询 / 上传 Excel 导入 |
| `/api/templates` | GET/POST/DELETE | 模板库管理（上传/列表/删除） |
| `/api/files/{project}/{name}` | GET | 下载/预览生成文件 |
| `/api/settings/model` | GET/PUT | 模型 Provider 与 API Key 配置 |
| `/api/health` | GET | 健康检查 |

### 5.2 对话编排引擎 (`app/orchestrator/`)
- `state_machine.py`：状态机流转（禁止非法迁移）
- `intent.py`：LLM 意图识别 + 槽位提取，输出结构化 JSON（面积、场景、预算、品牌、交付物[]）
- `clarify.py`：缺口检测与单轮一问
- `confirm.py`：确认摘要渲染

### 5.3 大模型适配层 (`app/llm/`)
- `base.py`：`LLMProvider` 抽象接口（`chat()`、`stream()`、`name`、`models`）
- `providers/openai_compat.py`：通用 OpenAI 兼容协议（DeepSeek/通义/Kimi/GLM/智谱等）
- `providers/openai.py`：官方 OpenAI
- `providers/gemini.py`：Google Gemini
- `registry.py`：Provider 注册表 + 用户配置（key/base_url/model）
- `prompts/`：场景化 Prompt 模板（需求澄清、配置适配、方案撰写、偏离分析、PPT 大纲）
- 适配核心：`adapt_template(requirement, template, products) -> config_json`，要求模型输出**严格 JSON**（设备清单/数量/单价/总价/偏离项）

### 5.4 数据层 (`app/db/`)
- SQLite 表设计见 §6
- `product_importer.py`：解析产品 Excel（表头映射：名称/参数/型号/低价/市场价），全量替换或增量合并
- `template_store.py`：模板文件入库 + 元数据（类型、适用场景、版本）

### 5.5 文档生成管线 (`app/generators/`)
- `word_generator.py`：打开文字方案模板（docx），定位占位符（`{{项目名称}}`、`{{设备清单}}`…）填充，输出新 docx
- `pdf_converter.py`：按需调用 LibreOffice headless 将 docx 转 PDF
- `excel_generator.py`：打开偏离表模板（xlsx），填入产品/参数/偏离项/价格
- `ppt_generator.py`：打开 PPT 母版，按 LLM 生成的大纲填充页（封面/项目概况/方案/配置清单/报价/价值）
- `pipeline.py`：任务编排（并行/串行生成多份文件，收集结果与错误）

### 5.6 任务系统 (`app/tasks/`)
- 内存队列 + 后台 worker（asyncio）
- 任务状态：pending → running → success / failed（可重试）
- 进度事件经 SSE 推送

### 5.7 安全 (`app/security/`)
- 启动时生成访问口令（可配置），手机端首次访问输入后存 localStorage
- API Key 用 Fernet 加密存储于 `data/secrets.bin`，密钥文件 `data/master.key`（chmod 600）

---

## 6. 数据设计（SQLite）

```
products(id, name, model, params_json, low_price, market_price, category, updated_at)
templates(id, name, type, description, file_path, meta_json, version, updated_at)
  -- type: config(常规配置) | doc(文字方案) | ppt(母版) | deviation(偏离表)
config_templates(id, name, area, scene, config_json, updated_at)
  -- 如 {area:100, scene:'会议室', devices:[{type:'音箱',spec:'8寸',qty:2},...]}
projects(id, name, requirement_json, status, created_at, updated_at)
tasks(id, project_id, deliverable_type, status, progress, error, file_path, created_at)
settings(key, value)  -- 模型配置、口令哈希等
```

**产品 Excel 导入规范**（约定表头，可在导入时映射）：
`产品名称 | 型号 | 参数 | 低价 | 市场价 | 分类`

**常规配置模板**（100/200/300平）由用户提供初始版，后续可由大模型基于历史项目持续优化建议。

---

## 7. 大模型层设计要点

1. **Provider 注册表**：内置 DeepSeek、通义千问、Kimi、智谱 GLM、OpenAI、Gemini、文心一言；统一由用户填 `API Key + Base URL + 模型名`
2. **对话分类**：先判断意图（新需求/追问补充/修改/查询），再决定状态迁移
3. **槽位提取**：结构化输出（JSON Schema 校验，失败自动重试 1 次）
4. **配置适配**：输入=需求 + 相近常规模板 + 产品库子集；输出=设备清单 JSON；温度 0.2 保准
5. **方案撰写**：输入=适配后的配置 + 项目背景；输出=Word 填充内容分节（项目概述/需求分析/设计依据/系统配置/报价/售后）
6. **偏离表**：对照招标要求/需求清单逐项给出"满足/偏离"及说明
7. **PPT 大纲**：按演示逻辑生成页级大纲，再逐页填充母版占位符

---

## 8. 错误处理与降级

| 场景 | 处理 |
|---|---|
| LLM 超时/限流 | 指数退避重试 3 次，仍失败则任务置 failed 并给出可读错误 |
| LLM 输出非 JSON | 解析失败重试 1 次；再失败降级为纯文本提示 |
| 模板文件缺失 | 报错并提示上传模板；不允许无模板硬生成 |
| 产品库无匹配产品 | 生成"建议选型"并标注"产品库未收录，需人工确认" |
| PDF 转换失败 | 保留 Word 交付，标注 PDF 生成失败原因 |
| 断网/未配 Key | 启动自检提示，功能入口禁用并引导配置 |
| 磁盘/权限错误 | 任务失败 + 日志；输出目录可配置 |

---

## 9. 测试策略

### 9.1 测试层级
1. **单元测试**（`tests/unit/`，pytest）
   - `test_intent.py`：意图识别/槽位提取（mock LLM 返回固定 JSON）
   - `test_state_machine.py`：状态迁移合法/非法路径
   - `test_clarify.py`：缺口检测与提问生成
   - `test_product_importer.py`：Excel 解析（表头映射、空值、重复、价格类型）
   - `test_adapt_template.py`：LLM 适配输出 JSON 校验（mock）
   - `test_generators/`：docx/xlsx/pptx 生成后校验文件结构（打开 zip 检查内容/占位符替换正确）
   - `test_pdf_converter.py`：PDF 转换调用与失败分支
   - `test_security.py`：Fernet 加解密、口令鉴权
   - `test_db.py`：CRUD、导入幂等性
2. **集成测试**（`tests/integration/`）
   - 产品导入 → 模板匹配 → LLM 适配（mock）→ 文档生成的完整管线
   - 任务队列并发与失败重试
3. **端到端测试**（`tests/e2e/`，可选真实 Key）
   - `/api/chat` 全流程：发需求→澄清→确认→生成→文件可下载
4. **覆盖率目标**：核心模块（orchestrator/llm/generators/importer）≥ 85%

### 9.2 测试数据
- `tests/fixtures/`：样例产品 Excel、100平配置模板、文字方案模板 docx、PPT 母版、偏离表 xlsx、mock LLM 响应 JSON

### 9.3 CI（本地）
- `make test` / `pytest -v`；`make lint`（ruff）；提交前 `make check` 全量执行

---

## 10. 里程碑

| 阶段 | 内容 | 验收 |
|---|---|---|
| M1 骨架 | FastAPI + SQLite + 状态机 + 基础对话 | 手机浏览器可访问、可对话 |
| M2 数据 | 产品 Excel 导入、模板库管理、配置模板 | 上传即用，可查询 |
| M3 生成 | LLM 适配 + Word/Excel/PPT 生成 + PDF 转换 | 三件套可产出 |
| M4 体验 | SSE 进度、项目管理、文件预览下载、鉴权 | 手机端全流程可用 |
| M5 加固 | 单测全覆盖、错误处理、文档 | 覆盖率达标，可交付 |

---

## 11. 风险与开放问题

| 风险 | 缓解 |
|---|---|
| 大模型适配结果不稳定 | JSON Schema 校验 + 重试 + 人工确认环节 |
| 公司模板格式复杂 | 首期支持占位符式模板，复杂版式逐步适配 |
| LibreOffice 转换环境 | 电脑端需安装 LibreOffice，提供启动自检 |
| 局域网环境多变 | 支持端口/绑定 IP 配置，提供二维码扫码连接 |
| 产品库数据量大 | 导入时建索引，查询走分类过滤 + 关键词 |

**待用户确认**
1. 输出目录默认放哪（桌面/指定文件夹）
2. 是否需要多用户/团队共享（当前按单用户设计）
3. 报价是否要含税费/折扣策略
