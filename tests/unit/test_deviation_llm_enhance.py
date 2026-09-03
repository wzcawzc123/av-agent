"""偏离表 LLM 增强通道测试：真实调用路径 + 降级路径。"""
import pytest

from app.engines.deviation import llm_enhance
from app.engines.deviation.model import MatchResult


def _result(model="MH-VS08", param="8寸两分频音箱", conf="medium"):
    return MatchResult(model=model, matched_param=param, score=2.0, confidence=conf)


async def _fake_judge(tender, param):
    assert "招标参数" in str(param) or param  # 参数已传入
    return ("high", "等效替代")


def test_llm_upgrades_medium_to_high(monkeypatch):
    monkeypatch.setattr(llm_enhance, "_judge_with_provider", _fake_judge)
    results = [_result()]
    out = llm_enhance.enhance_with_llm(results, ["8寸音箱"], llm_enabled=True)
    assert out[0].confidence == "high"


def test_llm_disabled_keeps_original(monkeypatch):
    results = [_result()]
    out = llm_enhance.enhance_with_llm(results, ["8寸音箱"], llm_enabled=False)
    assert out[0].confidence == "medium"


def test_llm_exception_degrades(monkeypatch):
    async def boom(tender, param):
        raise RuntimeError("no key")

    monkeypatch.setattr(llm_enhance, "_judge_with_provider", boom)
    results = [_result(conf="low")]
    out = llm_enhance.enhance_with_llm(results, ["未知设备"], llm_enabled=True)
    assert out[0].confidence == "low"  # 原样返回


def test_prompt_contains_tender_and_param():
    assert "{tender}" in llm_enhance.DEV_ENHANCE_PROMPT
    assert "{param}" in llm_enhance.DEV_ENHANCE_PROMPT
