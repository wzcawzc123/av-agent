"""产品能力标签规则推断测试。"""
from app.engines.tender.capability import tag_capabilities


class TestCapabilityTagger:
    def test_broadcast_integrated_unit(self):
        # 惠威集成调谐器+USB 播放的型号
        hits = tag_capabilities(
            "数字广播主机（带调谐器与USB播放）",
            "集成收音调谐与U盘播放功能",
        )
        caps = {h.capability for h in hits}
        assert "tuner" in caps
        assert "usb_player" in caps

    def test_preamp(self):
        caps = {h.capability for h in tag_capabilities("前置放大器")}
        assert "preamp" in caps

    def test_amp_channels_not_in_caps(self):
        # 通道数是数值维度，不走能力标签
        caps = {h.capability for h in tag_capabilities("四通道专业功放")}
        assert "power_amp" in caps
        assert "channels" not in caps

    def test_role_based(self):
        hits = tag_capabilities("天花喇叭", role_tags='["ceiling_speaker"]')
        caps = {h.capability for h in hits}
        assert "ceiling_speaker" in caps
        assert "speaker" in caps

    def test_role_json_and_list(self):
        a = {h.capability for h in tag_capabilities("中控主机", role_tags='["control_host"]')}
        b = {h.capability for h in tag_capabilities("中控主机", role_tags=["control_host"])}
        assert "control_host" in a
        assert a == b

    def test_no_false_positive(self):
        caps = {h.capability for h in tag_capabilities("投影幕布")}
        assert "display" not in caps  # 幕布无关键词
