from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now():
    return datetime.utcnow()


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    model: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    brand: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    base_price: Mapped[float] = mapped_column(Float, default=0)
    market_price: Mapped[float] = mapped_column(Float, default=0)
    category: Mapped[str] = mapped_column(String(100), default="")
    system: Mapped[str] = mapped_column(String(50), default="")  # 所属系统 code
    role_tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of role codes
    active: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(50))  # config|doc|ppt|deviation
    description: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(Text)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class ConfigTemplate(Base):
    __tablename__ = "config_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    area: Mapped[int] = mapped_column(Integer, index=True)
    scene: Mapped[str] = mapped_column(String(100), default="")
    systems: Mapped[str] = mapped_column(Text, default="[]")      # JSON list of system codes
    config_level: Mapped[str] = mapped_column(String(50), default="")
    brand: Mapped[str] = mapped_column(String(200), default="")   # 逗号分隔
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="未命名项目")
    requirement_json: Mapped[str] = mapped_column(Text, default="{}")
    bom_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(50), default="IDLE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, default=None, index=True)
    customer_name: Mapped[str] = mapped_column(String(200), default="")
    memory_json: Mapped[str] = mapped_column(Text, default="{}")


class TaskRecord(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    deliverable_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class SelectionRule(Base):
    """会议选型规则（场景×配置→设备角色→型号数量），数据驱动可后台维护。"""
    __tablename__ = "selection_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scene: Mapped[str] = mapped_column(String(50), index=True)
    area_min: Mapped[float] = mapped_column(Float, default=0)
    area_max: Mapped[float] = mapped_column(Float, default=9999)
    config_level: Mapped[str] = mapped_column(String(20), default="中配")
    device_role: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    unit: Mapped[str] = mapped_column(String(20), default="台")
    mic_level: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    antenna_level: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class SpeakerSpec(Base):
    """广播喇叭功率规格表。"""
    __tablename__ = "speaker_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    power_w: Mapped[float] = mapped_column(Float, default=0)
    category: Mapped[str] = mapped_column(String(50), default="")


class LedPanelSpec(Base):
    """LED 屏体/模组规格表。"""
    __tablename__ = "led_panel_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    module_w_mm: Mapped[int] = mapped_column(Integer, default=0)
    module_h_mm: Mapped[int] = mapped_column(Integer, default=0)
    res_w: Mapped[int] = mapped_column(Integer, default=0)
    res_h: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(50), default="")


class AmplifierTier(Base):
    """广播功放功率档位表。"""
    __tablename__ = "amplifier_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    min_w: Mapped[float] = mapped_column(Float, default=0)
    max_w: Mapped[float] = mapped_column(Float, default=0)
    model: Mapped[str] = mapped_column(String(100))


class System(Base):
    """系统目录：扩声/发言/显示/无纸化/中控矩阵/分布式/灯光/广播/视频会议…"""
    __tablename__ = "systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[int] = mapped_column(Integer, default=1)


class DeviceRole(Base):
    """设备角色目录：系统内的设备角色（主音箱/功放/主席单元…），带匹配关键词用于导入打标与检索。"""
    __tablename__ = "device_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    system_code: Mapped[str] = mapped_column(String(50), index=True)
    role_code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    role_name: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(20), default="台")
    match_keywords: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    sort: Mapped[int] = mapped_column(Integer, default=0)
class ProductCapability(Base):
    """产品能力标签：供招标改单能力覆盖判定。capability 为能力码（如 tuner/usb_player/amp_2ch）。"""

    __tablename__ = "product_capabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, index=True)
    capability: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(20), default="rule")  # rule|llm
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class TenderMatch(Base):
    """招标改单匹配快照：每次上传解析+匹配的结果按行持久化，前端确认后转 BOM。"""

    __tablename__ = "tender_match"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    snapshot: Mapped[str] = mapped_column(String(40), default="")  # 时间戳快照标识
    source_idx: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(200), default="")
    brand: Mapped[str] = mapped_column(String(100), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    qty: Mapped[int] = mapped_column(Integer, default=1)
    params_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="no_match")  # matched|partial|no_match|merged|extra|new
    matched_product_id: Mapped[int] = mapped_column(Integer, default=0)
    matched_model: Mapped[str] = mapped_column(String(100), default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    remark: Mapped[str] = mapped_column(Text, default="")
    merged_into: Mapped[str] = mapped_column(String(100), default="")
    preference: Mapped[str] = mapped_column(String(20), default="higher")  # higher|value
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Organization(Base):
    """企业组织（企业架构多租户维度）。"""
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    contact: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class User(Base):
    """组织内用户。"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, default=None, index=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50), default="")
    username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class KnowledgeDocument(Base):
    """知识库文档：RAG 关键词检索的知识条目。"""
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    doc_type: Mapped[str] = mapped_column(String(50), default="")
    file_path: Mapped[str] = mapped_column(Text, default="")
    excerpt: Mapped[str] = mapped_column(Text, default="")
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, default=None, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class WorkflowRun(Base):
    """一次完整的工作流运行记录（计划+进度+结果）。"""
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    plan_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    progress: Mapped[float] = mapped_column(Float, default=0)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)


class AgentExecutionLog(Base):
    """工作流中单个 Agent 步骤的执行日志。"""
    __tablename__ = "agent_execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    step: Mapped[str] = mapped_column(String(100), default="")
    agent_name: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # success|failed|skipped
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)


class Solution(Base):
    """方案文档：内容与产出文件路径。"""
    __tablename__ = "solutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    content_json: Mapped[str] = mapped_column(Text, default="{}")
    file_paths_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(50), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Quotation(Base):
    """报价单：分项明细+总价。"""
    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    items_json: Mapped[str] = mapped_column(Text, default="[]")
    file_path: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
