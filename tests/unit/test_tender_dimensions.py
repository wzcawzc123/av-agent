"""参数维度提取与距离度量测试。"""
from app.engines.tender.dimensions import (
    DIM_WEIGHTS,
    extract_dims,
    match_distance,
)


class TestExtractDims:
    def test_power_impedance(self):
        dm = extract_dims("额定功率 150W，阻抗 8Ω")
        assert dm.get("power").value == 150
        assert dm.get("impedance").value == 8

    def test_power_less_sign(self):
        dm = extract_dims("功率 ≥80W")
        assert dm.get("power").value == 80

    def test_freq_range_hz(self):
        dm = extract_dims("频率响应 60Hz-20kHz")
        assert dm.get("freq").value == 60
        assert dm.get("freq_hi").value == 20000

    def test_freq_range_khz(self):
        dm = extract_dims("频响 0.05kHz~20kHz")
        assert dm.get("freq").value == 50
        assert dm.get("freq_hi").value == 20000

    def test_sens_needs_context(self):
        # 无「灵敏度」上下文时 dB 不应被提取为 sens
        dm = extract_dims("最大声压级 110dB")
        assert dm.get("sens") is None

    def test_sens_with_context(self):
        dm = extract_dims("灵敏度 90dB")
        assert dm.get("sens").value == 90

    def test_ratio_with_context(self):
        dm = extract_dims("信噪比 ≥80dB")
        assert dm.get("ratio").value == 80

    def test_size_inch(self):
        dm = extract_dims("65英寸超高清液晶屏")
        assert dm.get("size").value == 65

    def test_channels(self):
        dm = extract_dims("四通道功放")  # 中文数字不提取
        assert dm.get("channels") is None
        dm2 = extract_dims("4通道功放")
        assert dm2.get("channels").value == 4
        dm3 = extract_dims("双通道 2CH")
        assert dm3.get("channels").value == 2

    def test_resolution(self):
        dm = extract_dims("分辨率 3840*2160")
        assert dm.get("resolution").value == 3840
        assert dm.get("resolution_hi").value == 2160

    def test_empty(self):
        assert not extract_dims("")
        assert not extract_dims(None)

    def test_impedance_in_sentence(self):
        # 中文标点后仍是合法边界
        dm = extract_dims("阻抗8Ω，额定功率150W，频率响应60Hz-20kHz")
        assert dm.get("impedance").value == 8
        assert dm.get("power").value == 150
        assert dm.get("freq_hi").value == 20000

    def test_hz_khz_mixed_range(self):
        dm = extract_dims("频率响应 40Hz-18kHz")
        assert dm.get("freq").value == 40
        assert dm.get("freq_hi").value == 18000


class TestMatchDistance:
    def test_no_common_dims(self):
        t = extract_dims("150W 8Ω")
        p = extract_dims("65英寸 触摸")
        dist, common, gaps = match_distance(t, p)
        assert dist is None
        assert gaps == {"power", "impedance"}

    def test_closer_winner(self):
        t = extract_dims("150W 8Ω")
        p80 = extract_dims("80W 8Ω")
        p180 = extract_dims("180W 8Ω")
        d80, _, _ = match_distance(t, p80)
        d180, _, _ = match_distance(t, p180)
        assert d180 < d80  # 就近取高：180W 更近

    def test_gap_reported(self):
        t = extract_dims("4通道 150W")
        p = extract_dims("150W 8Ω")
        _, _, gaps = match_distance(t, p)
        assert "channels" in gaps

    def test_same_dims_zero(self):
        t = extract_dims("150W 8Ω")
        p = extract_dims("150W 8Ω")
        dist, _, _ = match_distance(t, p)
        assert dist == 0

    def test_weight_positive(self):
        assert DIM_WEIGHTS["channels"] > DIM_WEIGHTS["ratio"]
