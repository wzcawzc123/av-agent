# AV Agent — 音视频售前工作流 Agent

为音视频行业销售技术工程师打造的对话式工作流 Agent：发需求 → Agent 澄清 → 确认 → 依托公司产品库与模板库，由大模型语义适配，自动生成交付文件（Word 方案 / Excel 偏离表 / PPT）。

## 核心能力

- **对话式需求采集**：识别缺口（面积、场景、预算、品牌、交付物）并逐项追问
- **交付物确认**：一次产出文字方案(Word)、偏离表(Excel)、PPT，确认后执行
- **产品库管理**：导入/更新公司产品 Excel（名称/参数/型号/底价/市场价）
- **模板库管理**：常规配置模板（100/200/300平）、文字方案模板、PPT 母版、偏离表模板
- **大模型适配**：可配置 API Key，内置主流模型提供商，模板按项目语义适配
- **文档生成**：Word 方案按需转 PDF；偏离表 Excel；PPT 套母版
- **局域网联动**：手机浏览器控制电脑端完成方案输出，无需安装 App

## 技术栈

| 层 | 选型 |
|---|---|
| Web 框架 | FastAPI + Uvicorn |
| 前端 | 单页 HTML+JS（手机浏览器访问） |
| 数据库 | SQLite（SQLAlchemy） |
| 文档生成 | python-docx / openpyxl / python-pptx |
| PDF 转换 | LibreOffice headless |
| 模型调用 | httpx + Provider 适配器（可插拔） |
| 测试 | pytest + pytest-asyncio + responses |
| 密钥 | cryptography (Fernet) |

## 目录结构

```
av-agent/
├── app/
│   ├── api/            # REST API 端点
│   ├── orchestrator/   # 对话状态机、意图识别、澄清、确认
│   ├── llm/            # 模型 Provider 适配层（可插拔）
│   │   └── providers/  # openai / openai_compat / gemini ...
│   ├── generators/     # Word/Excel/PPT 生成 + PDF 转换
│   ├── tasks/          # 异步任务队列 + SSE 进度
│   ├── db/             # SQLite 模型、产品导入、模板存储
│   └── security/       # API Key 加密、访问鉴权
├── data/               # SQLite 数据库、密钥、输出文件（git 忽略）
├── tests/
│   ├── unit/           # 单元测试
│   ├── integration/    # 集成测试
│   ├── e2e/            # 端到端测试
│   └── fixtures/       # 样例产品/模板/ mock LLM 响应
├── docs/
│   └── superpowers/specs/  # 设计文档
├── README.md
└── requirements.txt
```

## 快速开始（规划中）

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务（默认 0.0.0.0:8000）
python -m app.main

# 手机浏览器访问
# http://<电脑局域网IP>:8000
```

## 设计文档

- [音视频售前工作流 Agent 设计文档](docs/superpowers/specs/2026-09-04-av-sales-workflow-agent-design.md)

## 状态

- [x] 设计文档 v0.1（2026-09-04）
- [ ] M1 骨架：FastAPI + SQLite + 状态机 + 基础对话
- [ ] M2 数据：产品 Excel 导入、模板库管理
- [ ] M3 生成：LLM 适配 + Word/Excel/PPT + PDF 转换
- [ ] M4 体验：SSE 进度、项目管理、文件下载、鉴权
- [ ] M5 加固：单测全覆盖、错误处理、文档
