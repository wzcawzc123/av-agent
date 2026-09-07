"""场景映射扩展测试：体育馆/宴会厅/大堂/演播厅 系统推断。"""

from app.engines.systems.scene import infer_systems


def test_gym():
    assert set(infer_systems({"scene": "600平体育馆"})) == {
        "prosound", "display", "lighting", "broadcast"}
    assert set(infer_systems({"scene": "学校操场"})) >= {"prosound", "broadcast"}


def test_banquet():
    assert set(infer_systems({"scene": "宴会厅"})) == {
        "prosound", "speech", "display", "lighting", "broadcast"}
    assert set(infer_systems({"scene": "婚礼堂"})) >= {"lighting"}


def test_lobby():
    assert set(infer_systems({"scene": "酒店大堂"})) == {"prosound", "display", "broadcast"}


def test_studio():
    assert set(infer_systems({"scene": "录播教室"})) >= {"videoconf", "distributed", "display"}


def test_explicit_systems_override():
    assert infer_systems({"scene": "会议室", "systems": ["prosound"]}) == ["prosound"]
