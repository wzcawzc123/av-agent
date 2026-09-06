

def test_broadcast_zone_name_with_floor_prefix():
    """回归：分区名含楼层前缀（1F大厅）不得被解析成型号 F。"""
    from app.engines.intent.detect import _broadcast_zones

    zones = _broadcast_zones("广播系统 1F大厅 24只T-601 12只T-105")
    assert zones == [{"zone": "1F大厅", "T-601": 24, "T-105": 12}]
    zones = _broadcast_zones("广播 2F办公区 8只T-601，3F走廊 6只T-105")
    assert [z["zone"] for z in zones] == ["2F办公区", "3F走廊"]
