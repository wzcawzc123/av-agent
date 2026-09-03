from app.orchestrator.clarify import next_question


def test_no_missing_returns_none():
    assert next_question({}) is None


def test_ask_area():
    q = next_question({"missing": ["area"]})
    assert "面积" in q


def test_ask_deliverables():
    q = next_question({"missing": ["deliverables"]})
    assert "交付" in q
