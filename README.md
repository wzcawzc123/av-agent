# AV Agent — 音视频售前工作流 Agent

为音视频行业销售技术工程师打造的对话式工作流 Agent：发需求 → Agent 澄清 → 确认 → 依托公司产品库与模板库，由大模型语义适配，自动生成交付文件（Word 方案 / Excel 偏离表 / PPT）。

## 核心能力

- **对话式需求采集**：识别缺口（面积、场景、预算、品牌、交付物）并逐项追问
- **交付物确认**：一次产出文字方案(Word)、偏离表(Excel)、PPT，确认后执行
- **产品库管理**：导入/更新公司产品 Excel（名称/参数/型号/底价/市场价）
- **模板库管理**：常规配置模板（按面积匹配）、文字方案模板、PPT 母版、偏离表模板
- **大模型适配**：可配置 API Key，内置主流模型提供商，模板按项目语义适配
- **文档生成**：Word 方案按需转 PDF；偏离表 Excel；PPT 套母版
- **手机端 UI**：聊天、需求确认、进度条、文件下载、模型配置、产品上传、模板管理，一页搞定
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
| 打包分发 | PyInstaller（Windows exe） |
| 测试 | pytest + pytest-asyncio + responses |

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
│   └── security/       # 访问鉴权、密钥工具
├── static/             # 手机端单页前端（聊天/产品/模板/设置）
├── data/               # 运行时生成：数据库、密钥、模型配置（git 忽略）
├── output/             # 生成文件输出（git 忽略）
├── uploads/            # 上传文件暂存（git 忽略）
├── tests/              # 单元 / 端到端测试
├── docs/               # 功能说明书、使用说明书、设计文档
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

首次使用：右上角 ⚙️ 配置模型（Provider + API Key）→ 📦 上传产品 Excel → 对话描述需求 → 确认后自动生成并下载。

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
- [设计文档](docs/superpowers/specs/2026-09-04-av-sales-workflow-agent-design.md)

## 状态

- [x] 设计文档 v0.1（2026-09-04）
- [x] M1 骨架：FastAPI + SQLite + 状态机 + 基础对话
- [x] M2 数据：产品 Excel 导入、模板库管理
- [x] M3 生成：LLM 适配 + Word/Excel/PPT + PDF 转换
- [x] M4 体验：SSE 进度、项目管理、文件下载、鉴权
- [x] M5 加固：单测全覆盖（37 用例通过）、错误处理、文档
- [x] M6 分发：手机端 UI 补全（产品/模板管理）+ Windows exe 打包配置
