"""对话 → 引擎意图检测：规则匹配，不依赖 LLM。"""

from app.engines.intent.detect import detect_engine_intent


def test_meeting_intent_with_code():
    r = detect_engine_intent("会议清单 12-10-5-0-0-1-2-")
    assert r["engine"] == "meeting"
    assert r["params"]["code"] == "12-10-5-0-0-1-2"  # 尾连字符规范化移除


def test_meeting_intent_with_area_and_scene():
    r = detect_engine_intent("100平会议室音响清单")
    assert r["engine"] == "meeting"
    code = r["params"]["code"]
    assert code.split("-")[0] == "10"  # 长=sqrt(100)=10
    assert code.split("-")[5] == "1"   # 圆桌


def test_broadcast_intent():
    r = detect_engine_intent("广播系统 1F大厅 24只T-601 12只T-105")
    assert r["engine"] == "broadcast"
    z = r["params"]["zones"][0]
    assert z["T-601"] == 24 and z["T-105"] == 12


def test_led_intent():
    r = detect_engine_intent("LED屏 6米宽 3.5米高 TV-PH250-YZ")
    assert r["engine"] == "led"
    assert r["params"]["want_w_m"] == 6
    assert r["params"]["want_h_m"] == 3.5
    assert r["params"]["model"] == "TV-PH250-YZ"


def test_deviation_intent():
    r = detect_engine_intent("帮我做偏离表：1、8寸音箱；2、900W功放")
    assert r["engine"] == "deviation"
    assert len(r["params"]["tender_items"]) == 2


def test_no_engine_keyword():
    assert detect_engine_intent("你好") is None
    assert detect_engine_intent("帮我写个设计方案") is None


def test_meeting_requires_strong_intent_word():
    # 「100平会议室方案」是 LLM 对话流，不应被引擎拦截
    assert detect_engine_intent("100平会议室方案") is None
    # 带「清单」才触发
    r = detect_engine_intent("100平会议室音响清单")
    assert r and r["engine"] == "meeting"
