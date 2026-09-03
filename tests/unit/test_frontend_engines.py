"""前端引擎工具箱验收：index.html 含四引擎抽屉骨架与按钮，app.js 含调用逻辑。"""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
JS = (STATIC / "app.js").read_text(encoding="utf-8")


def test_index_has_toolbox_button():
    assert 'id="btnTools"' in HTML
    assert "工具箱" in HTML


def test_index_has_engine_drawer():
    assert 'id="engines-drawer"' in HTML
    # 四个引擎子面板
    for panel in ("engine-meeting", "engine-broadcast", "engine-led", "engine-deviation"):
        assert f'id="{panel}"' in HTML


def test_index_meeting_form_fields():
    # 会议编码输入 + 编码说明
    assert 'id="m-code"' in HTML


def test_index_broadcast_form_fields():
    assert 'id="bc-zones"' in HTML


def test_index_led_form_fields():
    assert 'id="led-w"' in HTML and 'id="led-h"' in HTML and 'id="led-model"' in HTML


def test_index_deviation_form_fields():
    assert 'id="dv-items"' in HTML and 'id="dv-llm"' in HTML


def test_js_has_engine_handlers():
    assert "btnTools" in JS and "engines-drawer" in JS
    for ep in ("/api/engines/meeting", "/api/engines/broadcast",
               "/api/engines/led", "/api/engines/deviation"):
        assert ep in JS


def test_js_engine_results_render():
    # 结果区展示 + 下载链接渲染函数
    for fn in ("engTable", "engDownload", "runEngine", "eng-dl"):
        assert fn in JS
