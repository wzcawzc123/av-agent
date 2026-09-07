"""B2 售前专家规则测试：LED 点距速查、扩声层高分档、报告厅拾音。"""

from app.engines.systems.engines import build_display, build_prosound, build_speech
from app.engines.systems.scene import estimate_viewing_distance, recommend_led_pitch


def test_recommend_led_pitch_tiers():
    assert recommend_led_pitch(2) == 1.53
    assert recommend_led_pitch(3) == 1.53
    assert recommend_led_pitch(4) == 2.5
    assert recommend_led_pitch(8) == 3.0
    assert recommend_led_pitch(15) == 4.0


def test_estimate_viewing_distance_uses_room_length_first():
    assert estimate_viewing_distance({"room": {"length": 12, "width": 8}, "area": 200}) == 12
    # 无 length 时按面积 sqrt 近似，且不小于 2.5m
    assert estimate_viewing_distance({"area": 100}) >= 2.5
    assert estimate_viewing_distance({}) >= 2.5


def test_display_led_pitch_falls_back_to_viewing_distance():
    # 未指定 pitch：长房间（纵深 15m）→ P4
    rows = build_display({"area": 300, "scene": "led会议室",
                          "room": {"length": 15, "width": 20},
                          "display": {"mode": "led", "w": 6, "h": 3}})
    led = next(r for r in rows if r["role"] == "led_screen")
    assert "P4" in led["spec"]
    # 短房间（纵深 2.5m）→ P1.53 及以下
    rows2 = build_display({"area": 40, "scene": "led会议室",
                           "room": {"length": 2.5, "width": 5},
                           "display": {"mode": "led", "w": 2, "h": 1}})
    led2 = next(r for r in rows2 if r["role"] == "led_screen")
    assert "P1.53" in led2["spec"]
    # 显式 pitch 优先于速查
    rows3 = build_display({"area": 300, "scene": "led会议室",
                           "room": {"length": 15, "width": 20},
                           "display": {"mode": "led", "pitch": 2.0, "w": 6, "h": 3}})
    led3 = next(r for r in rows3 if r["role"] == "led_screen")
    assert "P2" in led3["spec"]


def test_prosound_tall_room_upgrades_and_monitor():
    # 300㎡ + 层高6m → 6 只 12寸 主扩+返送
    rows = build_prosound({"area": 300, "scene": "报告厅",
                           "room": {"length": 20, "width": 15, "height": 6}})
    speakers = [r for r in rows if r["role"] == "main_speaker" and "返送" in r["role_name"]]
    assert any("12寸 主扩+返送" in r["spec"] for r in rows if r["role"] == "main_speaker")
    assert speakers, "应配置舞台返送音箱"
    # 400㎡ 大报告厅 → 8 只线阵主扩
    rows_big = build_prosound({"area": 400, "scene": "报告厅",
                               "room": {"length": 25, "width": 16, "height": 7}})
    assert any("线阵音箱" in r["spec"] for r in rows_big if r["role"] == "main_speaker")
    # 常规会议室（层高低）不配返送
    rows2 = build_prosound({"area": 150, "scene": "会议室",
                            "room": {"length": 10, "width": 15, "height": 3}})
    assert not any("返送" in r["role_name"] for r in rows2)


def test_speech_report_hall_adds_gooseneck():
    rows = build_speech({"seats": {"chairman": 1, "delegate": 100}, "scene": "报告厅"})
    assert any(r["role"] == "wireless_gooseneck" and r["qty"] == 4 for r in rows)
    rows2 = build_speech({"seats": {"chairman": 1, "delegate": 10}, "scene": "会议室"})
    assert not any(r["role"] == "wireless_gooseneck" for r in rows2)
