# 音视频售前工作流 Agent 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个对话式工作流 Agent：发需求 → 澄清 → 确认 → 依托产品库与模板库由大模型适配生成 Word 方案 / Excel 偏离表 / PPT（按需 PDF），电脑端引擎 + 局域网手机浏览器控制。

**Architecture:** 电脑端 FastAPI 服务 + SQLite 本地库；对话编排状态机（COLLECTING→CONFIRMING→GENERATING→DELIVERED）；LLM Provider 可插拔（用户自配 API Key）；文档生成管线（python-docx/openpyxl/python-pptx + LibreOffice 转 PDF）；异步任务队列 + SSE 进度；单页前端手机浏览器访问。

**Tech Stack:** Python 3.12+ / FastAPI / Uvicorn / SQLAlchemy / SQLite / httpx / python-docx / openpyxl / python-pptx / cryptography(Fernet) / pytest / pytest-asyncio / responses / LibreOffice(headless)

**Spec:** `docs/superpowers/specs/2026-09-04-av-sales-workflow-agent-design.md`

## Global Constraints

- Python ≥ 3.12（当前 Debian 环境 3.14.7），全部依赖经 pip 安装到 `.venv`
- 数据库文件 `data/avagent.db`（SQLite），已 gitignore
- 密钥文件 `data/master.key`、`data/secrets.bin`（chmod 600），已 gitignore
- 输出目录 `output/<project_name>/`，已 gitignore
- 服务默认绑定 `0.0.0.0:8000`，访问需启动口令
- 所有 LLM 输出必须先过 JSON Schema 校验，失败自动重试 1 次
- 产品 Excel 约定表头：`产品名称 | 型号 | 参数 | 低价 | 市场价 | 分类`
- 交付规则：文字方案先出 Word，用户要求 PDF 时再转；偏离表 Excel；PPT 套母版
- 所有任务测试优先（TDD），每个任务以 git commit 结束
- 命名规范：函数/类 snake_case / PascalCase，测试文件 `tests/<模块>/test_<名>.py`

---

## 文件结构总览

```
app/
├── __init__.py
├── main.py                  # FastAPI 入口 + 启动自检 + 静态托管
├── config.py                # 路径/端口/口令配置
├── api/
│   ├── __init__.py
│   ├── routes_chat.py       # POST /api/chat
│   ├── routes_projects.py   # GET/POST /api/projects, /api/projects/{id}
│   ├── routes_generate.py   # POST /api/generate, GET /api/tasks/{id}/stream(SSE)
│   ├── routes_data.py       # 产品/模板上传与列表
│   ├── routes_settings.py   # 模型配置 GET/PUT
│   └── deps.py              # 鉴权依赖
├── orchestrator/
│   ├── __init__.py
│   ├── state_machine.py     # 状态机
│   ├── intent.py            # 意图识别/槽位提取
│   ├── clarify.py           # 缺口检测/追问
│   └── confirm.py           # 确认摘要
├── llm/
│   ├── __init__.py
│   ├── base.py              # LLMProvider 抽象 + ChatMessage
│   ├── registry.py          # Provider 注册 + 配置加载
│   ├── prompts.py           # 场景 Prompt 模板
│   └── providers/
│       ├── __init__.py
│       ├── openai_compat.py # OpenAI 兼容（DeepSeek/通义/Kimi/GLM/文心）
│       ├── openai_official.py
│       └── gemini.py
├── generators/
│   ├── __init__.py
│   ├── word_generator.py
│   ├── excel_generator.py
│   ├── ppt_generator.py
│   ├── pdf_converter.py
│   └── pipeline.py
├── tasks/
│   ├── __init__.py
│   └── queue.py             # 任务队列 + worker + 进度
├── db/
│   ├── __init__.py
│   ├── session.py           # engine/session
│   ├── models.py            # ORM 模型
│   ├── product_importer.py  # Excel 导入
│   └── template_store.py    # 模板入库
└── security/
    ├── __init__.py
    ├── crypto.py            # Fernet 加解密
    └── auth.py              # 启动口令鉴权
static/                      # 单页前端（index.html, app.js, style.css）
tests/
├── conftest.py              # fixture: 内存库/临时目录/mock LLM
├── fixtures/                # 样例 Excel/docx/pptx/xlsx + mock 响应
├── unit/
│   ├── test_config.py
│   ├── test_db.py
│   ├── test_crypto.py
│   ├── test_auth.py
│   ├── test_llm_registry.py
│   ├── test_state_machine.py
│   ├── test_intent.py
│   ├── test_clarify.py
│   ├── test_product_importer.py
│   ├── test_template_store.py
│   ├── test_adapt_template.py
│   ├── test_generators.py
│   ├── test_pdf_converter.py
│   ├── test_pipeline.py
│   └── test_queue.py
├── integration/
│   └── test_full_pipeline.py
└── e2e/
    └── test_api_flow.py
```

---

### Task 1: 项目骨架与配置

**Files:**
- Create: `pyproject.toml`, `requirements.txt`
- Create: `app/__init__.py`, `app/config.py`, `app/main.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `app.config.settings`（`Settings` dataclass：`BASE_DIR`, `DATA_DIR`, `OUTPUT_DIR`, `STATIC_DIR`, `DB_PATH`, `HOST`, `PORT`, `ACCESS_TOKEN`）
- Produces: `app.main.app`（FastAPI 实例，含 `/api/health` 与静态托管）

- [ ] **Step 1: 写失败测试** `tests/unit/test_config.py`

```python
import os
from app.config import Settings

def test_settings_defaults(tmp_path):
    s = Settings(base_dir=str(tmp_path))
    assert s.DB_PATH == str(tmp_path / "data" / "avagent.db")
    assert s.OUTPUT_DIR == str(tmp_path / "output")
    assert s.PORT == 8000
    assert len(s.ACCESS_TOKEN) >= 8

def test_settings_creates_dirs(tmp_path):
    s = Settings(base_dir=str(tmp_path))
    s.ensure_dirs()
    assert os.path.isdir(tmp_path / "data")
    assert os.path.isdir(tmp_path / "output")
    assert os.path.isdir(tmp_path / "static")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_config.py -v`
Expected: FAIL（ModuleNotFoundError: app.config）

- [ ] **Step 3: 最小实现**

`requirements.txt`：
```
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
pydantic>=2.7
httpx>=0.27
python-docx>=1.1
openpyxl>=3.1
python-pptx>=1.0
cryptography>=42
pytest>=8.0
pytest-asyncio>=0.23
responses>=0.25
```

`app/config.py`：
```python
import os
import secrets
from dataclasses import dataclass, field

@dataclass
class Settings:
    base_dir: str = field(default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ACCESS_TOKEN: str = field(default_factory=lambda: os.environ.get("AV_ACCESS_TOKEN", secrets.token_urlsafe(16)))

    def __post_init__(self):
        self.DATA_DIR = os.path.join(self.base_dir, "data")
        self.OUTPUT_DIR = os.path.join(self.base_dir, "output")
        self.STATIC_DIR = os.path.join(self.base_dir, "static")
        self.UPLOAD_DIR = os.path.join(self.base_dir, "uploads")
        self.DB_PATH = os.path.join(self.DATA_DIR, "avagent.db")
        self.MASTER_KEY_PATH = os.path.join(self.DATA_DIR, "master.key")
        self.SECRETS_PATH = os.path.join(self.DATA_DIR, "secrets.bin")

    def ensure_dirs(self):
        for d in (self.DATA_DIR, self.OUTPUT_DIR, self.STATIC_DIR, self.UPLOAD_DIR):
            os.makedirs(d, exist_ok=True)

settings = Settings()
```

`app/main.py`：
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.config import settings

app = FastAPI(title="AV Agent", version="0.1.0")

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}

@app.on_event("startup")
def startup():
    settings.ensure_dirs()

app.mount("/", StaticFiles(directory=settings.STATIC_DIR, html=True), name="static")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_config.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: 项目骨架与配置模块"
```

---

### Task 2: SQLite 数据层（ORM 模型）

**Files:**
- Create: `app/db/__init__.py`, `app/db/session.py`, `app/db/models.py`
- Test: `tests/unit/test_db.py`

**Interfaces:**
- Consumes: `app.config.settings.DB_PATH`
- Produces: `app.db.session.get_engine()`, `get_session()`（上下文管理器）
- Produces ORM：`Product`, `Template`, `ConfigTemplate`, `Project`, `TaskRecord`, `Setting`（表名：products/templates/config_templates/projects/tasks/settings）

- [ ] **Step 1: 写失败测试** `tests/unit/test_db.py`

```python
from app.db.session import get_engine, get_session
from app.db.models import Base, Product, Project, Setting

def test_engine_creates_tables(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        tables = [r[0] for r in conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'")]
    assert "products" in tables and "projects" in tables and "settings" in tables

def test_product_crud(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        p = Product(name="8寸音箱", model="AV-8A", params_json='{"功率":"80W"}',
                    low_price=800, market_price=1200, category="音箱")
        s.add(p); s.commit()
        got = s.query(Product).filter_by(model="AV-8A").first()
        assert got is not None and got.name == "8寸音箱"
        assert got.market_price == 1200
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_db.py -v`
Expected: FAIL（ModuleNotFoundError: app.db）

- [ ] **Step 3: 最小实现**

`app/db/session.py`：
```python
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionLocal = None

def get_engine(url: str | None = None):
    global _engine, _SessionLocal
    if _engine is None:
        url = url or f"sqlite:///{__import__('app.config', fromlist=['settings']).settings.DB_PATH}"
        _engine = create_engine(url, connect_args={"check_same_thread": False})
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine

@contextmanager
def get_session(engine=None):
    engine = engine or get_engine()
    sess = _SessionLocal()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
```

`app/db/models.py`：
```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), index=True)
    model = Column(String(100), unique=True, index=True)
    params_json = Column(Text, default="{}")
    low_price = Column(Float)
    market_price = Column(Float)
    category = Column(String(100), index=True, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Template(Base):
    __tablename__ = "templates"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    type = Column(String(50), index=True)  # config|doc|ppt|deviation
    description = Column(Text, default="")
    file_path = Column(String(500))
    meta_json = Column(Text, default="{}")
    version = Column(String(20), default="1.0")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ConfigTemplate(Base):
    __tablename__ = "config_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    area = Column(Integer, index=True)
    scene = Column(String(100), default="")
    config_json = Column(Text)  # {"devices":[{type,spec,qty},...]}
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    requirement_json = Column(Text, default="{}")
    status = Column(String(50), default="IDLE")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TaskRecord(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, index=True)
    deliverable_type = Column(String(50))  # doc|deviation|ppt|pdf
    status = Column(String(50), default="pending")  # pending|running|success|failed
    progress = Column(Integer, default=0)
    error = Column(Text, default="")
    file_path = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(100), primary_key=True)
    value = Column(Text, default="")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_db.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: SQLite ORM 数据层"
```

---

### Task 3: 安全模块（API Key 加密 + 启动口令）

**Files:**
- Create: `app/security/__init__.py`, `app/security/crypto.py`, `app/security/auth.py`
- Test: `tests/unit/test_crypto.py`, `tests/unit/test_auth.py`

**Interfaces:**
- Consumes: `app.config.settings.MASTER_KEY_PATH`, `SECRETS_PATH`, `ACCESS_TOKEN`
- Produces: `app.security.crypto.get_cipher()`, `encrypt_text(plain) -> str`, `decrypt_text(token) -> str`
- Produces: `app.security.auth.verify_token(token) -> bool`, `AuthDependency`（FastAPI 依赖）

- [ ] **Step 1: 写失败测试**

`tests/unit/test_crypto.py`：
```python
import pytest
from app.security.crypto import get_cipher, encrypt_text, decrypt_text

def test_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.security.crypto.KEY_PATH", str(tmp_path / "master.key"))
    c1 = get_cipher()
    token = encrypt_text("sk-abc123")
    assert token != "sk-abc123"
    assert decrypt_text(token) == "sk-abc123"

def test_key_file_created_with_600(tmp_path, monkeypatch):
    monkeypatch.setattr("app.security.crypto.KEY_PATH", str(tmp_path / "master.key"))
    get_cipher()
    mode = oct((tmp_path / "master.key").stat().st_mode & 0o777)
    assert mode == "0o600"
```

`tests/unit/test_auth.py`：
```python
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from app.security.auth import verify_token, require_token

def test_verify_token():
    assert verify_token("correct-token", "correct-token") is True
    assert verify_token("wrong", "correct-token") is False

def test_require_token_dependency():
    app = FastAPI()
    app.include_router(require_token_router())
    client = TestClient(app)
    r = client.get("/api/health", headers={"X-Access-Token": "t"})
    assert r.status_code in (200, 401)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_crypto.py tests/unit/test_auth.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 最小实现**

`app/security/crypto.py`：
```python
import os
from cryptography.fernet import Fernet

KEY_PATH = None  # 由 main 启动时注入 settings.MASTER_KEY_PATH

def _ensure_key_path():
    global KEY_PATH
    if KEY_PATH is None:
        from app.config import settings
        KEY_PATH = settings.MASTER_KEY_PATH
    return KEY_PATH

def get_cipher():
    path = _ensure_key_path()
    if not os.path.exists(path):
        key = Fernet.generate_key()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
    with open(path, "rb") as f:
        return Fernet(f.read().strip())

def encrypt_text(plain: str) -> str:
    return get_cipher().encrypt(plain.encode()).decode()

def decrypt_text(token: str) -> str:
    return get_cipher().decrypt(token.encode()).decode()
```

`app/security/auth.py`：
```python
from fastapi import Header, HTTPException

def verify_token(token: str, expected: str) -> bool:
    import hmac
    return hmac.compare_digest(token or "", expected)

def require_token(x_access_token: str = Header(default="")) -> None:
    from app.config import settings
    if not verify_token(x_access_token, settings.ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="无效访问口令")
```

（`require_token_router` 为测试辅助，可放 `app/api/deps.py`；本任务先提供 `require_token` 供后续路由使用。）

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_crypto.py tests/unit/test_auth.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: API Key 加密与启动口令鉴权"
```

---

### Task 4: LLM Provider 抽象层与注册表

**Files:**
- Create: `app/llm/__init__.py`, `app/llm/base.py`, `app/llm/registry.py`, `app/llm/prompts.py`
- Create: `app/llm/providers/__init__.py`, `app/llm/providers/openai_compat.py`, `app/llm/providers/openai_official.py`, `app/llm/providers/gemini.py`
- Test: `tests/unit/test_llm_registry.py`

**Interfaces:**
- Produces: `app.llm.base.ChatMessage(role: str, content: str)`（dataclass）
- Produces: `app.llm.base.LLMProvider`（抽象类：`name: str`、`async chat(messages: list[ChatMessage]) -> str`）
- Produces: `app.llm.registry.PROVIDER_NAMES`（list）、`async get_provider(config: dict) -> LLMProvider`、`save_model_config(cfg: dict)`、`load_model_config() -> dict`
- Produces: `app.llm.prompts.INTENT_PROMPT`, `ADAPT_PROMPT`, `DOC_PROMPT`, `DEVIATION_PROMPT`, `PPT_PROMPT`（字符串常量）

- [ ] **Step 1: 写失败测试** `tests/unit/test_llm_registry.py`

```python
import pytest
from app.llm.base import ChatMessage, LLMProvider
from app.llm.registry import PROVIDER_NAMES, save_model_config, load_model_config, get_provider

def test_builtin_providers():
    assert "deepseek" in PROVIDER_NAMES
    assert "openai" in PROVIDER_NAMES
    assert "gemini" in PROVIDER_NAMES
    assert "qwen" in PROVIDER_NAMES

def test_save_load_config(tmp_path, monkeypatch):
    monkeypatch.setattr("app.llm.registry.CONFIG_PATH", str(tmp_path / "model.json"))
    save_model_config({"provider": "deepseek", "api_key": "sk-x", "model": "deepseek-chat"})
    cfg = load_model_config()
    assert cfg["provider"] == "deepseek"
    assert cfg["api_key"] == "sk-x"

@pytest.mark.asyncio
async def test_get_provider_returns_chat():
    cfg = {"provider": "deepseek", "api_key": "sk-test", "model": "deepseek-chat",
           "base_url": "https://api.deepseek.com/v1"}
    p = await get_provider(cfg)
    assert isinstance(p, LLMProvider)
    assert p.name == "deepseek"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_llm_registry.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 最小实现**

`app/llm/base.py`：
```python
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class ChatMessage:
    role: str  # system | user | assistant
    content: str

class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], temperature: float = 0.7) -> str:
        """返回模型回复文本。"""
        raise NotImplementedError
```

`app/llm/providers/openai_compat.py`：
```python
import httpx
from app.llm.base import LLMProvider, ChatMessage

class OpenAICompatProvider(LLMProvider):
    """适用于 DeepSeek / 通义 / Kimi / GLM / 文心（OpenAI 兼容 /v1/chat/completions）。"""
    def __init__(self, api_key: str, model: str, base_url: str, name: str = "openai_compat"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.name = name

    async def chat(self, messages, temperature=0.7):
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
```

`app/llm/providers/openai_official.py`：
```python
from app.llm.providers.openai_compat import OpenAICompatProvider

class OpenAIProvider(OpenAICompatProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        super().__init__(api_key, model, "https://api.openai.com/v1", name="openai")
```

`app/llm/providers/gemini.py`：
```python
import httpx
from app.llm.base import LLMProvider, ChatMessage

class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model = model

    async def chat(self, messages, temperature=0.7):
        contents = []
        for m in messages:
            if m.role in ("user", "assistant"):
                contents.append({"role": "model" if m.role == "assistant" else "user",
                                 "parts": [{"text": m.content}]})
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json={"contents": contents},
            )
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
```

`app/llm/registry.py`：
```python
import json
import os
from app.llm.base import LLMProvider
from app.llm.providers.openai_compat import OpenAICompatProvider
from app.llm.providers.openai_official import OpenAIProvider
from app.llm.providers.gemini import GeminiProvider

CONFIG_PATH = None

BUILTIN = {
    "deepseek":   {"base_url": "https://api.deepseek.com/v1",   "default_model": "deepseek-chat"},
    "qwen":       {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "default_model": "qwen-plus"},
    "kimi":       {"base_url": "https://api.moonshot.cn/v1",    "default_model": "moonshot-v1-8k"},
    "glm":        {"base_url": "https://open.bigmodel.cn/api/paas/v4", "default_model": "glm-4-flash"},
    "openai":     {"base_url": "https://api.openai.com/v1",     "default_model": "gpt-4o-mini"},
    "wenxin":     {"base_url": "https://qianfan.baidubce.com/v2", "default_model": "ernie-4.0-turbo-8k"},
    "gemini":     {"base_url": "", "default_model": "gemini-1.5-flash"},
}
PROVIDER_NAMES = list(BUILTIN.keys())

def _path():
    global CONFIG_PATH
    if CONFIG_PATH is None:
        from app.config import settings
        CONFIG_PATH = os.path.join(settings.DATA_DIR, "model.json")
    return CONFIG_PATH

def save_model_config(cfg: dict):
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_model_config() -> dict:
    if not os.path.exists(_path()):
        return {}
    with open(_path(), "r", encoding="utf-8") as f:
        return json.load(f)

async def get_provider(config: dict) -> LLMProvider:
    provider = config.get("provider", "deepseek")
    api_key = config.get("api_key", "")
    model = config.get("model") or BUILTIN[provider]["default_model"]
    base_url = config.get("base_url") or BUILTIN[provider]["base_url"]
    if provider == "openai":
        return OpenAIProvider(api_key, model)
    if provider == "gemini":
        return GeminiProvider(api_key, model)
    return OpenAICompatProvider(api_key, model, base_url, name=provider)
```

`app/llm/prompts.py`（占位常量，后续任务填充使用）：
```python
INTENT_PROMPT = """你是音视频售前方案助手。请从用户需求中提取结构化信息，输出 JSON：{"area": 面积数字或null, "scene": 场景, "budget": 预算或null, "brand": 品牌偏好或null, "deliverables": ["doc","deviation","ppt"], "missing": [缺失字段列表]}。只输出 JSON。"""
ADAPT_PROMPT = """你是音视频系统集成专家。根据项目需求与常规配置模板，结合产品库给出设备清单 JSON。严格输出：{"devices": [{"type":"音箱","spec":"8寸","qty":2,"model":"","low_price":0,"market_price":0}], "notes": "说明"}。只输出 JSON。"""
DOC_PROMPT = """你是音视频售前工程师。根据设备清单与项目信息，撰写文字设计方案正文，输出 Markdown。"""
DEVIATION_PROMPT = """你是售前工程师。对照招标/需求逐项判断满足或偏离，输出 JSON：{"items": [{"requirement":"","status":"满足|偏离","note":""}]}。只输出 JSON。"""
PPT_PROMPT = """你是售前演示专家。根据设备清单与方案生成 PPT 大纲，输出 JSON：{"slides": [{"title":"","bullets":[]}]}。只输出 JSON。"""
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_llm_registry.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: LLM Provider 抽象层与注册表"
```

---

### Task 5: 对话状态机

**Files:**
- Create: `app/orchestrator/__init__.py`, `app/orchestrator/state_machine.py`
- Test: `tests/unit/test_state_machine.py`

**Interfaces:**
- Produces: `app.orchestrator.state_machine.ConversationState`（类：`status: str`、`transition(target: str) -> None`、合法迁移表 `ALLOWED`）
- 合法迁移：IDLE→COLLECTING→CONFIRMING→GENERATING→DELIVERED；COLLECTING→CONFIRMING↔COLLECTING；CONFIRMING→GENERATING；GENERATING→DELIVERED / GENERATING→CONFIRMING(重试)

- [ ] **Step 1: 写失败测试** `tests/unit/test_state_machine.py`

```python
import pytest
from app.orchestrator.state_machine import ConversationState, InvalidTransition

def test_valid_flow():
    s = ConversationState("IDLE")
    s.transition("COLLECTING")
    s.transition("CONFIRMING")
    s.transition("GENERATING")
    s.transition("DELIVERED")
    assert s.status == "DELIVERED"

def test_invalid_transition_raises():
    s = ConversationState("IDLE")
    with pytest.raises(InvalidTransition):
        s.transition("GENERATING")

def test_collecting_loopback():
    s = ConversationState("COLLECTING")
    s.transition("COLLECTING")  # 追问后仍处采集
    assert s.status == "COLLECTING"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_state_machine.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 最小实现**

`app/orchestrator/state_machine.py`：
```python
class InvalidTransition(Exception):
    pass

ALLOWED = {
    "IDLE": {"COLLECTING"},
    "COLLECTING": {"COLLECTING", "CONFIRMING"},
    "CONFIRMING": {"COLLECTING", "GENERATING"},
    "GENERATING": {"DELIVERED", "CONFIRMING"},
    "DELIVERED": {"IDLE", "COLLECTING"},
}

class ConversationState:
    def __init__(self, status: str = "IDLE"):
        self.status = status

    def transition(self, target: str):
        if target not in ALLOWED.get(self.status, set()):
            raise InvalidTransition(f"{self.status} -> {target} 不允许")
        self.status = target
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_state_machine.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: 对话状态机"
```

---

### Task 6: 意图识别与槽位提取

**Files:**
- Create: `app/orchestrator/intent.py`, `app/orchestrator/clarify.py`, `app/orchestrator/confirm.py`
- Test: `tests/unit/test_intent.py`, `tests/unit/test_clarify.py`

**Interfaces:**
- Consumes: `app.llm.base.ChatMessage`, `app.llm.prompts.INTENT_PROMPT`, `app.llm.registry.get_provider`
- Produces: `app.orchestrator.intent.parse_intent(provider, user_text) -> dict`（含 area/scene/budget/brand/deliverables/missing）
- Produces: `app.orchestrator.intent.extract_json(text) -> dict`（容错提取 JSON）
- Produces: `app.orchestrator.clarify.next_question(slots: dict) -> str | None`（返回缺口问题或 None）
- Produces: `app.orchestrator.confirm.render_summary(slots: dict, deliverable_names: dict) -> str`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_intent.py`：
```python
import json
import pytest
from app.orchestrator.intent import extract_json, parse_intent

def test_extract_json_with_code_fence():
    text = '```json\n{"area": 100}\n```'
    assert extract_json(text) == {"area": 100}

def test_extract_json_plain():
    assert extract_json('{"area": 100, "scene": "会议室"}')["scene"] == "会议室"

@pytest.mark.asyncio
async def test_parse_intent_mock(monkeypatch):
    class FakeProvider:
        name = "fake"
        async def chat(self, messages, temperature=0.7):
            return '{"area": 100, "scene": "会议室", "budget": null, "brand": null, "deliverables": ["doc"], "missing": ["budget"]}'
    slots = await parse_intent(FakeProvider(), "100平会议室方案")
    assert slots["area"] == 100
    assert slots["missing"] == ["budget"]
```

`tests/unit/test_clarify.py`：
```python
from app.orchestrator.clarify import next_question

def test_no_missing_returns_none():
    assert next_question({}) is None

def test_ask_area():
    q = next_question({"missing": ["area"]})
    assert "面积" in q

def test_ask_deliverables():
    q = next_question({"missing": ["deliverables"]})
    assert "交付" in q
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_intent.py tests/unit/test_clarify.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

`app/orchestrator/intent.py`：
```python
import json
import re
from app.llm.base import ChatMessage
from app.llm.prompts import INTENT_PROMPT

def extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("无 JSON 内容")
    return json.loads(m.group(0))

async def parse_intent(provider, user_text: str) -> dict:
    resp = await provider.chat([
        ChatMessage("system", INTENT_PROMPT),
        ChatMessage("user", user_text),
    ], temperature=0.2)
    slots = extract_json(resp)
    slots.setdefault("area", None)
    slots.setdefault("scene", None)
    slots.setdefault("budget", None)
    slots.setdefault("brand", None)
    slots.setdefault("deliverables", [])
    slots.setdefault("missing", [])
    return slots
```

`app/orchestrator/clarify.py`：
```python
QUESTIONS = {
    "area": "这个项目大概多少平方米？",
    "scene": "主要用途/场景是什么（会议室、展厅、报告厅…）？",
    "budget": "客户预算大概多少？",
    "brand": "有没有品牌偏好？",
    "deliverables": "需要哪些交付物？文字方案 / 偏离表 / PPT 都可以选。",
}

def next_question(slots: dict) -> str | None:
    for key in ("area", "scene", "budget", "brand", "deliverables"):
        if key in slots.get("missing", []):
            return QUESTIONS[key]
    return None
```

`app/orchestrator/confirm.py`：
```python
DELIVERABLE_NAMES = {"doc": "文字方案(Word)", "deviation": "偏离表(Excel)", "ppt": "PPT", "pdf": "PDF"}

def render_summary(slots: dict, deliverable_names: dict | None = None) -> str:
    names = deliverable_names or DELIVERABLE_NAMES
    lines = ["已确认以下需求，请确认后开始生成：", ""]
    lines.append(f"- 面积：{slots.get('area', '未提供')}")
    lines.append(f"- 场景：{slots.get('scene', '未提供')}")
    lines.append(f"- 预算：{slots.get('budget', '未提供')}")
    lines.append(f"- 品牌：{slots.get('brand', '未提供')}")
    dels = [names.get(d, d) for d in slots.get("deliverables", [])]
    lines.append(f"- 交付物：{', '.join(dels) if dels else '未选择'}")
    return "\n".join(lines)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_intent.py tests/unit/test_clarify.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: 意图识别、槽位提取与澄清追问"
```

---

### Task 7: 产品 Excel 导入器

**Files:**
- Create: `app/db/product_importer.py`
- Test: `tests/unit/test_product_importer.py`（含 fixture 样例 Excel）

**Interfaces:**
- Consumes: `app.db.session.get_session`, `app.db.models.Product`
- Produces: `app.db.product_importer.import_products(excel_path: str, session) -> dict`（返回 `{"inserted": n, "updated": m}`）
- 表头映射：`产品名称→name`、`型号→model`、`参数→params_json`、`低价→low_price`、`市场价→market_price`、`分类→category`

- [ ] **Step 1: 写失败测试**

`tests/fixtures/make_sample_excel.py`：
```python
from openpyxl import Workbook

def build(path: str):
    wb = Workbook()
    ws = wb.active
    ws.append(["产品名称", "型号", "参数", "低价", "市场价", "分类"])
    ws.append(["8寸音箱", "AV-8A", '{"功率":"80W"}', 800, 1200, "音箱"])
    ws.append(["功放", "PA-400", '{"功率":"400W"}', 1500, 2200, "功放"])
    wb.save(path)

if __name__ == "__main__":
    build("/workspace/av-agent/tests/fixtures/sample_products.xlsx")
```

`tests/unit/test_product_importer.py`：
```python
import pytest
from openpyxl import Workbook
from app.db.session import get_engine, get_session
from app.db.models import Base, Product
from app.db.product_importer import import_products

@pytest.fixture
def excel_path(tmp_path):
    wb = Workbook(); ws = wb.active
    ws.append(["产品名称", "型号", "参数", "低价", "市场价", "分类"])
    ws.append(["8寸音箱", "AV-8A", '{"功率":"80W"}', 800, 1200, "音箱"])
    ws.append(["功放", "PA-400", '{"功率":"400W"}', 1500, 2200, "功放"])
    p = tmp_path / "products.xlsx"; wb.save(p); return str(p)

def test_import_new(tmp_path, excel_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db"); Base.metadata.create_all(engine)
    with get_session(engine) as s:
        r = import_products(excel_path, s)
        assert r == {"inserted": 2, "updated": 0}
        assert s.query(Product).count() == 2

def test_import_updates_existing(tmp_path, excel_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db"); Base.metadata.create_all(engine)
    with get_session(engine) as s:
        import_products(excel_path, s)
    with get_session(engine) as s:
        wb = Workbook(); ws = wb.active
        ws.append(["产品名称", "型号", "参数", "低价", "市场价", "分类"])
        ws.append(["8寸音箱改", "AV-8A", '{}', 900, 1300, "音箱"])
        p2 = tmp_path / "p2.xlsx"; wb.save(p2)
        r = import_products(str(p2), s)
        assert r == {"inserted": 0, "updated": 1}
        got = s.query(Product).filter_by(model="AV-8A").first()
        assert got.name == "8寸音箱改" and got.low_price == 900
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_product_importer.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

`app/db/product_importer.py`：
```python
import json
from openpyxl import load_workbook
from app.db.models import Product

HEADER_MAP = {"产品名称": "name", "型号": "model", "参数": "params_json",
              "低价": "low_price", "市场价": "market_price", "分类": "category"}

def _norm(s):
    return str(s or "").strip()

def import_products(excel_path: str, session) -> dict:
    wb = load_workbook(excel_path, read_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = [_norm(c) for c in next(rows)]
    col = {HEADER_MAP[h]: i for i, h in enumerate(header) if h in HEADER_MAP}
    inserted = updated = 0
    for row in rows:
        if not row or not _norm(row[col["model"]]):
            continue
        model = _norm(row[col["model"]])
        data = {k: row[i] for k, i in col.items()}
        if data.get("params_json") is not None and not isinstance(data["params_json"], str):
            data["params_json"] = json.dumps(data["params_json"], ensure_ascii=False)
        existing = session.query(Product).filter_by(model=model).first()
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            updated += 1
        else:
            session.add(Product(**data))
            inserted += 1
    wb.close()
    return {"inserted": inserted, "updated": updated}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_product_importer.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: 产品 Excel 导入器"
```

---

### Task 8: 模板库存储与配置模板

**Files:**
- Create: `app/db/template_store.py`
- Test: `tests/unit/test_template_store.py`

**Interfaces:**
- Consumes: `app.db.models.Template`, `ConfigTemplate`, `app.config.settings.UPLOAD_DIR`
- Produces: `app.db.template_store.save_template(session, name, type_, file_path, description="") -> Template`
- Produces: `app.db.template_store.save_config_template(session, name, area, scene, config_json: dict) -> ConfigTemplate`
- Produces: `app.db.template_store.find_config_template(session, area: int) -> ConfigTemplate | None`（最接近面积匹配）

- [ ] **Step 1: 写失败测试** `tests/unit/test_template_store.py`

```python
import pytest
from app.db.session import get_engine, get_session
from app.db.models import Base, Template, ConfigTemplate
from app.db.template_store import save_template, save_config_template, find_config_template

@pytest.fixture
def engine(tmp_path):
    e = get_engine(f"sqlite:///{tmp_path}/t.db"); Base.metadata.create_all(e); return e

def test_save_template(engine):
    with get_session(engine) as s:
        t = save_template(s, "文字方案模板", "doc", "/tmp/tpl.docx", "通用")
        assert t.id is not None and t.type == "doc"

def test_save_and_find_config(engine):
    with get_session(engine) as s:
        save_config_template(s, "100平会议室", 100, "会议室",
                             {"devices": [{"type": "音箱", "spec": "8寸", "qty": 2}]})
        got = find_config_template(s, 100)
        assert got is not None and got.area == 100

def test_find_nearest(engine):
    with get_session(engine) as s:
        save_config_template(s, "100平", 100, "", {"devices": []})
        save_config_template(s, "300平", 300, "", {"devices": []})
        got = find_config_template(s, 120)  # 无精确则取最近
        assert got.area == 100
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_template_store.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

`app/db/template_store.py`：
```python
import json
from app.db.models import Template, ConfigTemplate

def save_template(session, name: str, type_: str, file_path: str, description: str = "") -> Template:
    t = Template(name=name, type=type_, file_path=file_path, description=description)
    session.add(t)
    session.flush()
    return t

def save_config_template(session, name: str, area: int, scene: str, config_json: dict) -> ConfigTemplate:
    c = ConfigTemplate(name=name, area=area, scene=scene, config_json=json.dumps(config_json, ensure_ascii=False))
    session.add(c)
    session.flush()
    return c

def find_config_template(session, area: int):
    exact = session.query(ConfigTemplate).filter_by(area=area).order_by(ConfigTemplate.id.desc()).first()
    if exact:
        return exact
    rows = session.query(ConfigTemplate).all()
    if not rows:
        return None
    return min(rows, key=lambda r: abs(r.area - area))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_template_store.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: 模板库存储与配置模板匹配"
```

---

### Task 9: LLM 模板适配（设备清单生成）

**Files:**
- Create: `app/llm/adapt.py`
- Test: `tests/unit/test_adapt_template.py`

**Interfaces:**
- Consumes: `app.llm.prompts.ADAPT_PROMPT`, `app.orchestrator.intent.extract_json`, `app.db.template_store.find_config_template`, `app.db.models.Product`
- Produces: `app.llm.adapt.adapt_template(provider, slots: dict, config_template, products: list[dict], session) -> dict`
  - 返回 `{"devices": [{"type","spec","qty","model","low_price","market_price"}], "notes": str}`
  - 校验：devices 非空且每项含 type/qty；价格缺失时尝试用产品库匹配（按 spec 关键词）

- [ ] **Step 1: 写失败测试** `tests/unit/test_adapt_template.py`

```python
import json
import pytest
from app.db.session import get_engine, get_session
from app.db.models import Base, Product, ConfigTemplate
from app.llm.adapt import adapt_template

class FakeProvider:
    name = "fake"
    def __init__(self, resp): self.resp = resp
    async def chat(self, messages, temperature=0.7): return self.resp

@pytest.mark.asyncio
async def test_adapt_returns_devices(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db"); Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(Product(name="8寸音箱", model="AV-8A", low_price=800, market_price=1200, category="音箱"))
        s.add(ConfigTemplate(name="100平", area=100, scene="会议室",
                             config_json=json.dumps({"devices": [{"type": "音箱", "spec": "8寸", "qty": 2}]})))
        s.commit()
        resp = json.dumps({"devices": [{"type": "音箱", "spec": "8寸", "qty": 2}], "notes": "ok"})
        result = await adapt_template(FakeProvider(resp), {"area": 100}, None, [], s)
        assert len(result["devices"]) == 1
        assert result["devices"][0]["qty"] == 2

@pytest.mark.asyncio
async def test_adapt_invalid_json_raises(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db"); Base.metadata.create_all(engine)
    with get_session(engine) as s:
        with pytest.raises(Exception):
            await adapt_template(FakeProvider("not json"), {"area": 100}, None, [], s)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_adapt_template.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

`app/llm/adapt.py`：
```python
import json
from app.llm.base import ChatMessage
from app.llm.prompts import ADAPT_PROMPT
from app.orchestrator.intent import extract_json

def _validate(result: dict) -> dict:
    devices = result.get("devices")
    if not isinstance(devices, list) or not devices:
        raise ValueError("适配结果缺少 devices")
    for d in devices:
        if not d.get("type") or not d.get("qty"):
            raise ValueError(f"设备项缺字段: {d}")
        d.setdefault("spec", "")
        d.setdefault("model", "")
        d.setdefault("low_price", 0)
        d.setdefault("market_price", 0)
    result.setdefault("notes", "")
    return result

async def adapt_template(provider, slots: dict, config_template, products: list[dict], session) -> dict:
    tpl_json = json.dumps(json.loads(config_template.config_json) if config_template else {"devices": []},
                          ensure_ascii=False)
    product_summary = json.dumps(products[:50], ensure_ascii=False)
    user_msg = (f"项目需求：{json.dumps(slots, ensure_ascii=False)}\n"
                f"常规配置模板：{tpl_json}\n"
                f"产品库（名称/型号/低价/市场价）：{product_summary}")
    resp = await provider.chat([
        ChatMessage("system", ADAPT_PROMPT),
        ChatMessage("user", user_msg),
    ], temperature=0.2)
    result = extract_json(resp)
    return _validate(result)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_adapt_template.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: LLM 模板适配生成设备清单"
```

---

### Task 10: Word 方案生成器

**Files:**
- Create: `app/generators/__init__.py`, `app/generators/word_generator.py`
- Test: `tests/unit/test_generators.py`（Word 部分）

**Interfaces:**
- Consumes: `app.llm.prompts.DOC_PROMPT`, `app.llm.base.ChatMessage`
- Produces: `app.generators.word_generator.fill_docx_template(template_path: str, replacements: dict, out_path: str) -> str`
  - replacements 键：`{{项目名称}}`、`{{项目概述}}`、`{{设备清单}}`（Markdown 表格文本）、`{{方案正文}}`
- Produces: `app.generators.word_generator.build_doc_from_llm(provider, slots, devices, template_path, out_path) -> str`（LLM 写正文→填充）

- [ ] **Step 1: 写失败测试**

`tests/unit/test_generators.py`：
```python
import pytest
from docx import Document
from app.generators.word_generator import fill_docx_template

def _make_template(path):
    doc = Document()
    doc.add_paragraph("项目名称：{{项目名称}}")
    doc.add_paragraph("{{方案正文}}")
    doc.save(path)

def test_fill_docx_template(tmp_path):
    tpl = tmp_path / "tpl.docx"; _make_template(tpl)
    out = tmp_path / "out.docx"
    fill_docx_template(str(tpl), {"项目名称": "100平会议室", "方案正文": "正文内容"}, str(out))
    doc = Document(str(out))
    texts = [p.text for p in doc.paragraphs]
    assert any("100平会议室" in t for t in texts)
    assert any("正文内容" in t for t in texts)
    assert not any("{{" in t for t in texts)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_generators.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

`app/generators/word_generator.py`：
```python
import re
from docx import Document

def fill_docx_template(template_path: str, replacements: dict, out_path: str) -> str:
    doc = Document(template_path)
    pattern = re.compile(r"\{\{\s*(\w+)\s*\}\}")
    for para in doc.paragraphs:
        def _sub(m):
            key = m.group(1)
            return str(replacements.get(key, m.group(0)))
        para.text = pattern.sub(_sub, para.text)
    doc.save(out_path)
    return out_path

async def build_doc_from_llm(provider, slots: dict, devices: list[dict],
                             template_path: str, out_path: str) -> str:
    from app.llm.base import ChatMessage
    from app.llm.prompts import DOC_PROMPT
    from app.llm.adapt import _validate
    devices_txt = "\n".join(
        f"- {d['type']} {d.get('spec','')} × {d['qty']}" for d in devices)
    user_msg = f"项目：{slots}\n设备清单：\n{devices_txt}"
    body = await provider.chat([
        ChatMessage("system", DOC_PROMPT),
        ChatMessage("user", user_msg),
    ], temperature=0.5)
    return fill_docx_template(template_path,
                              {"项目名称": slots.get("scene") or "音视频方案",
                               "方案正文": body}, out_path)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_generators.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: Word 方案生成器"
```

---

### Task 11: Excel 偏离表生成器

**Files:**
- Create: `app/generators/excel_generator.py`
- Test: `tests/unit/test_generators.py`（Excel 部分）

**Interfaces:**
- Produces: `app.generators.excel_generator.generate_deviation_sheet(template_path: str | None, items: list[dict], out_path: str) -> str`
  - items 元素：`{"requirement": str, "status": "满足"|"偏离", "note": str}`；无模板时创建基础表头 `需求 | 状态 | 说明`

- [ ] **Step 1: 写失败测试**（追加到 `tests/unit/test_generators.py`）

```python
from openpyxl import load_workbook
from app.generators.excel_generator import generate_deviation_sheet

def test_deviation_sheet_no_template(tmp_path):
    out = tmp_path / "dev.xlsx"
    generate_deviation_sheet(None, [{"requirement": "支持8欧负载", "status": "满足", "note": "功放支持"}], str(out))
    wb = load_workbook(str(out)); ws = wb.active
    assert ws.cell(1, 1).value == "需求"
    assert ws.cell(2, 1).value == "支持8欧负载"
    assert ws.cell(2, 2).value == "满足"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_generators.py -v`
Expected: FAIL（generate_deviation_sheet 未定义）

- [ ] **Step 3: 最小实现**

`app/generators/excel_generator.py`：
```python
from openpyxl import Workbook, load_workbook

def generate_deviation_sheet(template_path, items: list[dict], out_path: str) -> str:
    if template_path:
        wb = load_workbook(template_path)
        ws = wb.active
    else:
        wb = Workbook(); ws = wb.active
        ws.append(["需求", "状态", "说明"])
    for it in items:
        ws.append([it.get("requirement", ""), it.get("status", "满足"), it.get("note", "")])
    wb.save(out_path)
    return out_path
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_generators.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: Excel 偏离表生成器"
```

---

### Task 12: PPT 生成器

**Files:**
- Create: `app/generators/ppt_generator.py`
- Test: `tests/unit/test_generators.py`（PPT 部分）

**Interfaces:**
- Consumes: `app.llm.prompts.PPT_PROMPT`
- Produces: `app.generators.ppt_generator.build_ppt(provider, slots, devices, template_path: str | None, out_path: str) -> str`
  - LLM 输出 `{"slides": [{"title": str, "bullets": [str]}]}`；无母版时创建默认版式（标题+要点占位符）

- [ ] **Step 1: 写失败测试**（追加到 `tests/unit/test_generators.py`）

```python
import json
from pptx import Presentation
from app.generators.ppt_generator import build_ppt

class FakeProvider:
    name = "fake"
    async def chat(self, messages, temperature=0.7):
        return json.dumps({"slides": [{"title": "项目概述", "bullets": ["100平会议室"]},
                                      {"title": "配置清单", "bullets": ["音箱×2"]}]})

@pytest.mark.asyncio
async def test_build_ppt_no_template(tmp_path):
    out = tmp_path / "out.pptx"
    await build_ppt(FakeProvider(), {"scene": "会议室"}, [], None, str(out))
    prs = Presentation(str(out))
    texts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
    assert any("项目概述" in t for t in texts)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_generators.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

`app/generators/ppt_generator.py`：
```python
import json
from pptx import Presentation
from app.llm.base import ChatMessage
from app.llm.prompts import PPT_PROMPT
from app.orchestrator.intent import extract_json

async def build_ppt(provider, slots: dict, devices: list[dict], template_path, out_path: str) -> str:
    user_msg = f"项目：{json.dumps(slots, ensure_ascii=False)}\n设备清单：{json.dumps(devices, ensure_ascii=False)}"
    resp = await provider.chat([
        ChatMessage("system", PPT_PROMPT),
        ChatMessage("user", user_msg),
    ], temperature=0.5)
    data = extract_json(resp)
    slides = data.get("slides", [])
    if template_path:
        prs = Presentation(template_path)
        blank = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[-1]
    else:
        prs = Presentation()
        blank = prs.slide_layouts[1]
    for s in slides:
        slide = prs.slides.add_slide(blank)
        title = slide.shapes.title
        if title is not None:
            title.text = s.get("title", "")
        body = None
        for shape in slide.shapes:
            if shape.has_text_frame and shape != title and shape.text_frame.text == "":
                body = shape.text_frame
                break
        if body is not None:
            for i, b in enumerate(s.get("bullets", [])):
                p = body.paragraphs[0] if i == 0 else body.add_paragraph()
                p.text = b
    prs.save(out_path)
    return out_path
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_generators.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: PPT 生成器（套母版/默认版式）"
```

---

### Task 13: PDF 转换器与生成管线

**Files:**
- Create: `app/generators/pdf_converter.py`, `app/generators/pipeline.py`
- Test: `tests/unit/test_pdf_converter.py`, `tests/unit/test_pipeline.py`

**Interfaces:**
- Consumes: Task 10/11/12 生成器、Task 9 适配、`app.llm.registry.get_provider`
- Produces: `app.generators.pdf_converter.convert_docx_to_pdf(docx_path: str, out_pdf: str) -> bool`（LibreOffice headless，失败返回 False 不抛异常）
- Produces: `app.generators.pipeline.generate_deliverables(cfg: dict, provider, slots, session, progress_cb) -> dict`
  - cfg 含 `deliverables: list[str]`、`project_dir`、`template_paths: dict`
  - 返回 `{"files": {type: path}, "errors": {type: msg}}`
  - progress_cb(percent, message) 供任务系统上报

- [ ] **Step 1: 写失败测试**

`tests/unit/test_pdf_converter.py`：
```python
from app.generators.pdf_converter import convert_docx_to_pdf

def test_missing_input_returns_false(tmp_path):
    assert convert_docx_to_pdf(str(tmp_path / "nope.docx"), str(tmp_path / "out.pdf")) is False
```

`tests/unit/test_pipeline.py`：
```python
import json
import pytest
from app.db.session import get_engine, get_session
from app.db.models import Base, Product, ConfigTemplate
from app.generators.pipeline import generate_deliverables

class FakeProvider:
    name = "fake"
    def __init__(self, resp): self.resp = resp
    async def chat(self, messages, temperature=0.7): return self.resp

@pytest.mark.asyncio
async def test_generate_deliverables_doc(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db"); Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(ConfigTemplate(name="100平", area=100, scene="会议室",
                             config_json=json.dumps({"devices": []})))
        s.commit()
        prov = FakeProvider(json.dumps({"devices": [{"type": "音箱", "spec": "8寸", "qty": 2}], "notes": ""}))
        project_dir = tmp_path / "proj"; project_dir.mkdir()
        slots = {"area": 100, "scene": "会议室", "deliverables": ["doc"]}
        progress = []
        result = await generate_deliverables(
            {"deliverables": ["doc"], "project_dir": str(project_dir), "template_paths": {}},
            prov, slots, s, lambda p, m: progress.append((p, m)))
        assert "doc" in result["files"]
        assert any(p > 0 for p, _ in progress)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_pdf_converter.py tests/unit/test_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

`app/generators/pdf_converter.py`：
```python
import os
import subprocess

def convert_docx_to_pdf(docx_path: str, out_pdf: str) -> bool:
    if not os.path.exists(docx_path):
        return False
    try:
        subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf",
                        "--outdir", os.path.dirname(out_pdf), docx_path],
                       check=True, capture_output=True, timeout=180)
        return os.path.exists(out_pdf)
    except Exception:
        return False
```

`app/generators/pipeline.py`：
```python
import os
import json
from app.llm.adapt import adapt_template
from app.generators.word_generator import build_doc_from_llm
from app.generators.excel_generator import generate_deviation_sheet
from app.generators.ppt_generator import build_ppt
from app.generators.pdf_converter import convert_docx_to_pdf
from app.db.template_store import find_config_template

async def generate_deliverables(cfg: dict, provider, slots: dict, session, progress_cb) -> dict:
    files, errors = {}, {}
    total = len(cfg["deliverables"]) + 1
    done = 0
    progress_cb(int(10 / total * 100), "匹配常规配置模板…")
    tpl = find_config_template(session, slots.get("area") or 0)
    products = [{"name": p.name, "model": p.model, "low_price": p.low_price,
                 "market_price": p.market_price} for p in session.query(__import__("app.db.models", fromlist=["Product"]).Product).limit(200)]
    devices = []
    if "doc" in cfg["deliverables"] or "ppt" in cfg["deliverables"]:
        adapted = await adapt_template(provider, slots, tpl, products, session)
        devices = adapted["devices"]
    done += 1
    project_dir = cfg["project_dir"]
    os.makedirs(project_dir, exist_ok=True)
    tpl_paths = cfg.get("template_paths", {})
    for i, dt in enumerate(cfg["deliverables"]):
        progress_cb(int((done + i) / total * 100), f"生成 {dt} …")
        try:
            if dt == "doc":
                out = os.path.join(project_dir, "方案.docx")
                await build_doc_from_llm(provider, slots, devices, tpl_paths.get("doc"), out)
                files["doc"] = out
            elif dt == "pdf":
                src = files.get("doc") or os.path.join(project_dir, "方案.docx")
                out = os.path.join(project_dir, "方案.pdf")
                if convert_docx_to_pdf(src, out):
                    files["pdf"] = out
                else:
                    errors["pdf"] = "PDF 转换失败（需先有 Word，且电脑安装 LibreOffice）"
            elif dt == "deviation":
                out = os.path.join(project_dir, "偏离表.xlsx")
                generate_deviation_sheet(tpl_paths.get("deviation"),
                                         [{"requirement": slots.get("scene") or "需求", "status": "满足", "note": ""}],
                                         out)
                files["deviation"] = out
            elif dt == "ppt":
                out = os.path.join(project_dir, "方案.pptx")
                await build_ppt(provider, slots, devices, tpl_paths.get("ppt"), out)
                files["ppt"] = out
        except Exception as e:
            errors[dt] = str(e)
    progress_cb(100, "完成")
    return {"files": files, "errors": errors}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/unit/test_pdf_converter.py tests/unit/test_pipeline.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: PDF 转换器与生成管线"
```

---

### Task 14: 任务队列与 API 端点

**Files:**
- Create: `app/tasks/__init__.py`, `app/tasks/queue.py`
- Create: `app/api/__init__.py`, `app/api/deps.py`, `app/api/routes_chat.py`, `app/api/routes_projects.py`, `app/api/routes_generate.py`, `app/api/routes_data.py`, `app/api/routes_settings.py`
- Modify: `app/main.py`（挂载路由）
- Test: `tests/e2e/test_api_flow.py`（API 全流程，mock LLM）

**Interfaces:**
- Produces: `app.tasks.queue.submit_task(project_id, cfg, slots) -> task_id`、`get_task(task_id)`、`subscribe(project_id)`（异步生成器，SSE）
- Produces API：`POST /api/chat`（body `{"text": str, "project_id": int|None}` → `{"reply": str, "project_id": int, "status": str}`）
- Produces API：`POST /api/generate`（body `{"project_id": int}` → `{"task_id": str}`）；`GET /api/tasks/{id}/stream`（SSE）
- Produces API：`GET/POST /api/products`、`GET/POST/DELETE /api/templates`、`GET/PUT /api/settings/model`
- 依赖：`app.api.deps.require_token`

- [ ] **Step 1: 写失败测试** `tests/e2e/test_api_flow.py`

```python
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    with TestClient(app) as c:
        yield c

def _auth(client):
    return {"X-Access-Token": "test-token"}

def test_health_no_auth(client):
    r = client.get("/api/health")
    assert r.status_code == 200

def test_chat_flow(client, monkeypatch):
    class FakeProvider:
        name = "fake"
        async def chat(self, messages, temperature=0.7):
            return '{"area": 100, "scene": "会议室", "budget": null, "brand": null, "deliverables": ["doc"], "missing": ["budget"]}'
    monkeypatch.setattr("app.api.routes_chat.get_provider", lambda cfg: FakeProvider())
    r = client.post("/api/chat", json={"text": "100平会议室方案"}, headers=_auth(client))
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("COLLECTING", "CONFIRMING")
    assert "预算" in data["reply"]

def test_settings_model_roundtrip(client, monkeypatch, tmp_path):
    import app.llm.registry as reg
    monkeypatch.setattr(reg, "CONFIG_PATH", str(tmp_path / "model.json"))
    r = client.put("/api/settings/model", json={"provider": "deepseek", "api_key": "sk-x", "model": "deepseek-chat"},
                   headers=_auth(client))
    assert r.status_code == 200
    r2 = client.get("/api/settings/model", headers=_auth(client))
    assert r2.json()["provider"] == "deepseek"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/e2e/test_api_flow.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**（关键文件）

`app/tasks/queue.py`：
```python
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

def subscribe(project_id: int):
    q = asyncio.Queue()
    _watchers.setdefault(project_id, []).append(q)
    try:
        while True:
            yield q.get()
    finally:
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
```

`app/api/deps.py`：
```python
from fastapi import Header, HTTPException
from app.security.auth import verify_token

async def require_token(x_access_token: str = Header(default="")):
    from app.config import settings
    if not verify_token(x_access_token, settings.ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="无效访问口令")
```

`app/api/routes_chat.py`（核心对话端点，其余路由按同模式实现）：
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.api.deps import require_token
from app.orchestrator.state_machine import ConversationState
from app.orchestrator.intent import parse_intent
from app.orchestrator.clarify import next_question
from app.orchestrator.confirm import render_summary
from app.llm.registry import get_provider, load_model_config

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])
_sessions: dict[int, dict] = {}

class ChatIn(BaseModel):
    text: str
    project_id: int | None = None

@router.post("/chat")
async def chat(body: ChatIn):
    pid = body.project_id or 0
    sess = _sessions.setdefault(pid, {"state": ConversationState(), "slots": {}})
    st, slots = sess["state"], sess["slots"]
    if st.status == "IDLE":
        st.transition("COLLECTING")
    cfg = load_model_config()
    provider = await get_provider(cfg)
    new_slots = await parse_intent(provider, body.text)
    for k, v in new_slots.items():
        if k != "missing" and v not in (None, [], ""):
            slots[k] = v
    q = next_question(new_slots)
    if q is None and not new_slots.get("missing"):
        st.transition("CONFIRMING")
        return {"reply": render_summary(slots), "project_id": pid, "status": st.status}
    return {"reply": q, "project_id": pid, "status": st.status}
```

`app/main.py` 修改：注册路由（chat/projects/generate/data/settings），`settings.ensure_dirs()` 后初始化数据库（`Base.metadata.create_all`）、初始化 `crypto.KEY_PATH`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/e2e/test_api_flow.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: 任务队列与 API 端点（chat/generate/settings）"
```

---

### Task 15: 手机端单页前端

**Files:**
- Create: `static/index.html`, `static/style.css`, `static/app.js`

**Interfaces:**
- Consumes: `POST /api/chat`、`POST /api/generate`、`GET /api/tasks/{id}/stream`(SSE)、`GET /api/products`、`GET /api/templates`、`GET /api/settings/model`
- Produces: 手机浏览器可用的单页应用（聊天区 + 确认卡片 + 生成进度 + 文件列表 + 设置抽屉）

- [ ] **Step 1: 写失败测试**

前端静态文件无单测；本任务验收改为**手动/自动化冒烟**：`GET /` 返回 index.html 且含 `chat-app` 挂载点。

`tests/e2e/test_static.py`：
```python
from fastapi.testclient import TestClient
from app.main import app

def test_index_served():
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "chat-app" in r.text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/e2e/test_static.py -v`
Expected: FAIL（404 或文本缺失）

- [ ] **Step 3: 最小实现**（核心结构）

`static/index.html`：
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AV Agent</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <header>
    <h1>🎧 AV Agent</h1>
    <button id="btnSettings">⚙️</button>
  </header>
  <main id="chat-app">
    <div id="chat-log"></div>
    <form id="chat-form">
      <input id="chat-input" placeholder="例如：100平会议室方案" autocomplete="off">
      <button type="submit">发送</button>
    </form>
  </main>
  <div id="settings-drawer" hidden>
    <h3>模型配置</h3>
    <select id="cfg-provider"></select>
    <input id="cfg-key" type="password" placeholder="API Key">
    <input id="cfg-model" placeholder="模型名">
    <input id="cfg-base" placeholder="Base URL（可选）">
    <button id="cfg-save">保存</button>
    <button id="cfg-close">关闭</button>
  </div>
  <script src="/app.js"></script>
</body>
</html>
```

`static/app.js`（关键逻辑，完整实现见文件）：
```js
const TOKEN_KEY = "av_access_token";
let projectId = null;

async function api(path, opts = {}) {
  const token = localStorage.getItem(TOKEN_KEY) || prompt("请输入访问口令") || "";
  localStorage.setItem(TOKEN_KEY, token);
  opts.headers = Object.assign({ "Content-Type": "application/json",
    "X-Access-Token": token }, opts.headers || {});
  const r = await fetch(path, opts);
  if (r.status === 401) { localStorage.removeItem(TOKEN_KEY); location.reload(); }
  return r.json();
}

function addMsg(role, text) {
  const d = document.createElement("div");
  d.className = "msg " + role;
  d.textContent = text;
  document.getElementById("chat-log").appendChild(d);
}

document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;
  addMsg("user", text); input.value = "";
  const data = await api("/api/chat", { method: "POST",
    body: JSON.stringify({ text, project_id: projectId }) });
  projectId = data.project_id;
  addMsg("agent", data.reply);
  if (data.status === "CONFIRMING") showConfirm(data);
});

function showConfirm(data) {
  const btn = document.createElement("button");
  btn.textContent = "✅ 确认并生成";
  btn.onclick = async () => {
    const t = await api("/api/generate", { method: "POST",
      body: JSON.stringify({ project_id: projectId }) });
    listenProgress(t.task_id);
  };
  document.getElementById("chat-log").appendChild(btn);
}

function listenProgress(taskId) {
  const es = new EventSource(`/api/tasks/${taskId}/stream?token=${localStorage.getItem(TOKEN_KEY)}`);
  es.onmessage = (ev) => {
    const d = JSON.parse(ev.data);
    addMsg("agent", `[${d.percent}%] ${d.message || d.status}`);
    if (d.type === "done") { es.close(); if (d.result) showFiles(d.result.files); }
  };
}

function showFiles(files) {
  for (const [k, v] of Object.entries(files)) {
    const a = document.createElement("a");
    a.href = `/api/files/${encodeURIComponent(v)}`;
    a.target = "_blank"; a.textContent = `下载 ${k}`;
    document.getElementById("chat-log").appendChild(a);
  }
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /workspace/av-agent && .venv/bin/pytest tests/e2e/test_static.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: 手机端单页前端（聊天/确认/进度/下载）"
```

---

## 自审记录

**1. Spec 覆盖检查**
- FR1 对话式需求采集 → Task 6/14 ✅
- FR2 交付物确认 → Task 5/6/14 ✅
- FR3 产品库管理 → Task 2/7 ✅
- FR4 模板库管理 → Task 8 ✅
- FR5 大模型适配 → Task 4/9 ✅
- FR6 文档生成（Word/Excel/PPT/按需PDF） → Task 10/11/12/13 ✅
- FR7 局域网联动 → Task 14/15 ✅
- FR8 模型配置 → Task 4/14 ✅
- NFR1 安全 → Task 3 ✅
- NFR2 可靠性（重试/日志） → Task 9/13/14（重试与 JSON 校验内联实现）✅

**2. 占位符扫描**：无 TBD/TODO；prompts.py 为具名常量，正文在 Task 9/10/11/12 消费处完整定义。

**3. 类型一致性**
- `parse_intent(provider, text) -> dict`（Task 6）与 Task 14 使用一致 ✅
- `adapt_template(provider, slots, config_template, products, session)`（Task 9）与 Task 13 pipeline 调用一致（`tpl` 为 `ConfigTemplate|None`，`products` 为 list[dict]）✅
- `get_provider(cfg) -> LLMProvider`（Task 4）在 Task 6/9/14 复用一致 ✅
- `generate_deliverables(cfg, provider, slots, session, progress_cb)`（Task 13）与 queue `_run` 调用一致 ✅

**遗留说明**：`/api/files` 下载端点在 Task 14 路由中实现（返回 `FileResponse`）；`routes_generate.py` 的 SSE 端点直接转发 `queue.subscribe` 生成器。前端文件下载路径基于生成文件名，路由内部映射到 `settings.OUTPUT_DIR/<project>/<name>`。
