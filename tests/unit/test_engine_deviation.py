"""偏离表引擎：字符评分匹配 + LLM 增强（monkeypatch）+ DB 桥接"""
from app.db.models import Base, Product
from app.db.session import get_engine, get_session
from app.engines.deviation.db_bridge import build_candidates_from_db
from app.engines.deviation.llm_enhance import enhance_with_llm
from app.engines.deviation.matcher import match_tender_to_product
from app.engines.deviation.model import MatchResult, ProductCandidate


def test_match_simple_keyword():
    cand = ProductCandidate("DS-8004", ["支持输入输出支持HDMI1.4", "双向串口控制"])
    results = match_tender_to_product(
        ["1、支持≥4个HDMI输入接口", "2、支持双向串口控制"], [cand])
    assert len(results) == 2
    assert results[1].matched_param == "双向串口控制"
    assert results[1].confidence == "high"


def test_match_no_hit_returns_low():
    cand = ProductCandidate("X-1", ["纯装饰性产品说明"])
    r = match_tender_to_product(["激光投影技术参数"], [cand])[0]
    assert r.matched_param == "" and r.confidence == "low"


def test_numeric_chars_score_lower():
    cand = ProductCandidate("Y-2", ["支持4路输入"])
    r = match_tender_to_product(["支持4路输入"], [cand])[0]
    assert r.confidence == "high"


def test_build_candidates_from_db(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(Product(name="矩阵", model="DS-8004",
                      description="1.支持HDMI1.4\n2.双向串口控制"))
        s.commit()
        cands = build_candidates_from_db(s, ["DS-8004"])
        assert len(cands) == 1 and cands[0].model == "DS-8004"
        assert len(cands[0].params) == 2


def test_build_candidates_from_db_missing_model(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        assert build_candidates_from_db(s, ["不存在-型号"]) == []


def test_llm_enhance_disabled_returns_original(monkeypatch):
    r = MatchResult("M", "p", 3.0, "medium")
    out = enhance_with_llm([r], ["招标参数"], llm_enabled=False)
    assert out == [r]


def test_llm_enhance_upgrades_confidence(monkeypatch):
    monkeypatch.setattr("app.engines.deviation.llm_enhance._llm_judge",
                        lambda *a, **k: ("high", "理由"))
    r = MatchResult("M", "p", 3.0, "medium")
    out = enhance_with_llm([r], ["招标参数"], llm_enabled=True)
    assert out[0].confidence == "high"


def test_llm_enhance_fallback_on_error(monkeypatch):
    monkeypatch.setattr("app.engines.deviation.llm_enhance._llm_judge",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no key")))
    r = MatchResult("M", "p", 3.0, "medium")
    out = enhance_with_llm([r], ["招标参数"], llm_enabled=True)
    assert out == [r]
