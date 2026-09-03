import pytest

from app.db.session import get_engine, get_session
from app.db.models import Base, Template, ConfigTemplate
from app.db.template_store import save_template, save_config_template, find_config_template


@pytest.fixture
def engine(tmp_path):
    e = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(e)
    return e


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
