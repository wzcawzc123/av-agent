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
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="未命名项目")
    requirement_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(50), default="IDLE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


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
