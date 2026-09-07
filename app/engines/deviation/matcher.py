from app.engines.deviation.model import MatchResult
from app.engines.deviation.rules import DEFAULT_DEVIATION_RULES


def _is_num(ch: str) -> bool:
    return ch.isdigit() or ch in ".%≥≤"


def _score_pair(tender: str, param: str, rules: dict) -> float:
    score = 0.0
    for i in range(len(tender)):
        c = tender[i]
        if c in param:
            score += rules["numeric_char_weight"] if _is_num(c) else rules["single_char_weight"]
            if i + 1 < len(tender) and tender[i:i + 2] in param:
                score += rules["numeric_double_weight"] if _is_num(c) else rules["double_char_weight"]
    return score


def match_tender_to_product(tender_items, candidates, rules=None):
    """招标参数 → 候选产品参数 字符评分匹配；返回 MatchResult 列表（保持输入顺序）。"""
    rules = rules or dict(DEFAULT_DEVIATION_RULES)
    high_t = rules.get("high_threshold", 6.0)
    med_t = rules.get("medium_threshold", 2.0)
    out = []
    for item in tender_items:
        best_score, best_param, best_model = 0.0, "", ""
        for cand in candidates:
            for p in cand.params:
                s = _score_pair(item, p, rules)
                if s > best_score:
                    best_score, best_param, best_model = s, p, cand.model
        if best_score == 0:
            out.append(MatchResult("", "", 0.0, "low"))
        elif best_score >= high_t:
            out.append(MatchResult(best_model, best_param, best_score, "high"))
        elif best_score >= med_t:
            out.append(MatchResult(best_model, best_param, best_score, "medium"))
        else:
            out.append(MatchResult(best_model, best_param, best_score, "low"))
    return out
