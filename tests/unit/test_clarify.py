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
    q = next_question({"area": "100", "scene": "会议室", "budget": "5万",
                       "brand": "未提供", "deliverables": ["doc"]})
    assert "品牌" in q


def test_explicit_negation_counts_as_provided():
    # brand=无 不应死循环追问（B1 修复）
    assert next_question({"area": "100", "scene": "园区", "budget": "不限",
                          "brand": "无", "deliverables": ["doc"]}) is None


def test_complete_non_scene_returns_none():
    # 非专家追问场景：基础字段完整即确认
    assert next_question({"area": "100", "scene": "园区", "budget": "5万",
                          "brand": "惠威", "deliverables": ["doc", "excel"]}) is None


def test_meeting_room_asks_expert_questions_in_order():
    base = {"area": "100", "scene": "会议室", "budget": "5万",
            "brand": "惠威", "deliverables": ["doc"]}
    q1 = next_question(base)
    assert "容纳多少人" in q1
    base["seats"] = {"chairman": 1, "delegate": 12}
    q2 = next_question(base)
    assert "显示" in q2
    base["display"] = {"mode": "led", "w": 4, "h": 2}
    q3 = next_question(base)
    assert "视频会议" in q3
    base["videoconf"] = "是"
    q4 = next_question(base)
    assert "无纸化" in q4
    base["paperless"] = "不需要"
    assert next_question(base) is None


def test_report_hall_asks_height_and_lighting():
    base = {"area": "400", "scene": "报告厅", "budget": "30万",
            "brand": "无", "deliverables": ["doc"]}
    q1 = next_question(base)
    assert "座位" in q1
    base["seats"] = {"chairman": 1, "delegate": 200}
    q2 = next_question(base)
    assert "层高" in q2
    base["room"] = {"length": 20, "width": 15, "height": 6}
    q3 = next_question(base)
    assert "灯光" in q3
    base["lighting"] = "不需要"
    assert next_question(base) is None


def test_exhibition_asks_display_and_signals():
    base = {"area": "300", "scene": "企业展厅", "budget": "20万",
            "brand": "无", "deliverables": ["doc"]}
    q1 = next_question(base)
    assert "LED" in q1 or "拼接" in q1
    base["display"] = {"mode": "led", "pitch": 2.5, "w": 6, "h": 3}
    q2 = next_question(base)
    assert "信号源" in q2
    base["signal_sources"] = 4
    q3 = next_question(base)
    assert "互动" in q3
    base["interact"] = "不需要"
    assert next_question(base) is None
