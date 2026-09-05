from app.orchestrator.clarify import next_question


def test_all_missing_ask_area_first():
    assert "面积" in next_question({})


def test_missing_budget():
    q = next_question({"area": "100", "scene": "会议室", "brand": "惠威", "deliverables": ["doc"]})
    assert "预算" in q


def test_missing_brand():
    q = next_question({"area": "100", "scene": "会议室", "budget": "5万", "deliverables": ["doc"]})
    assert "品牌" in q


def test_missing_deliverables():
    q = next_question({"area": "100", "scene": "会议室", "budget": "5万", "brand": "惠威"})
    assert "交付" in q


def test_blank_string_is_missing():
    assert next_question({"area": "100", "scene": "会议室", "budget": "5万",
                          "brand": "未提供", "deliverables": ["doc"]}) == "有没有品牌偏好？"


def test_complete_returns_none():
    assert next_question({"area": "100", "scene": "会议室", "budget": "5万",
                          "brand": "惠威", "deliverables": ["doc", "excel"]}) is None
