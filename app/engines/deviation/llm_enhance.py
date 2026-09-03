"""可选 LLM 语义增强：对 medium/low 匹配做二次判断；无 key/异常自动降级为原结果。"""


def _llm_judge(tender, matched_param):
    """默认实现调用 app.llm 的 provider；测试中 monkeypatch 替换。"""
    raise NotImplementedError("未配置 LLM 增强通道")


def enhance_with_llm(results, tender_items, llm_enabled=True, session=None):
    if not llm_enabled:
        return results
    try:
        out = []
        for i, r in enumerate(results):
            if r.confidence in ("medium", "low") and r.matched_param:
                conf, _ = _llm_judge(tender_items[i], r.matched_param)
                if conf in ("high", "medium", "low"):
                    r.confidence = conf
            out.append(r)
        return out
    except Exception:
        return results  # 任何异常降级为原结果
