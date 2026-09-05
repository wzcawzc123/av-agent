"""招标文件解析器测试。"""
from app.engines.tender.parser import (
    detect_columns,
    parse_model_field,
    rows_to_items,
    split_params,
)


class TestColumns:
    def test_alias_detect(self):
        cols = detect_columns(["序号", "设备名称", "品牌", "型号", "数量"])
        assert cols["name"] == 1
        assert cols["brand"] == 2
        assert cols["model"] == 3
        assert cols["qty"] == 4

    def test_brand_model_long_alias_priority(self):
        # 「品牌型号」应映射到 brand，且不吞掉独立 model 列
        cols = detect_columns(["设备名称", "品牌型号", "规格型号", "数量"])
        assert cols["brand"] == 1
        assert cols["model"] == 2


class TestSplitParams:
    def test_newline_split(self):
        assert split_params("额定功率150W\n阻抗8Ω\n频率响应60Hz") == [
            "额定功率150W",
            "阻抗8Ω",
            "频率响应60Hz",
        ]

    def test_semicolon_split(self):
        assert split_params("功率150W；阻抗8Ω;信噪比90dB") == [
            "功率150W",
            "阻抗8Ω",
            "信噪比90dB",
        ]

    def test_indexed_list(self):
        assert split_params("1、功率150W 2、阻抗8Ω 3、频率响应60Hz") == [
            "功率150W",
            "阻抗8Ω",
            "频率响应60Hz",
        ]

    def test_dedup(self):
        assert split_params("功率150W\n功率150W") == ["功率150W"]

    def test_empty(self):
        assert split_params("") == []
        assert split_params(None) == []


class TestModelField:
    def test_separate_fields(self):
        assert parse_model_field("ITC", "T-62200") == ("ITC", "T-62200")

    def test_model_column_contains_brand(self):
        assert parse_model_field("", "ITC T-62200") == ("ITC", "T-62200")

    def test_brand_column_contains_model(self):
        assert parse_model_field("ITC T-62200", "") == ("ITC", "T-62200")

    def test_slash_separated(self):
        assert parse_model_field("", "ITC/T-62200") == ("ITC", "T-62200")

    def test_single_token_model_no_brand(self):
        assert parse_model_field("", "T-62200") == ("", "T-62200")


class TestRowsToItems:
    def test_full_table(self):
        raw = [
            ["序号", "设备名称", "品牌型号", "数量", "技术参数"],
            ["1", "专业功放", "ITC T-62200", "2", "额定功率150W\n阻抗8Ω"],
            ["2", "调音台", "YAMAHA MG16", "1", "16路；内置USB播放"],
            ["合计", "", "", "", ""],
        ]
        items = rows_to_items(raw)
        assert len(items) == 2
        assert items[0].name == "专业功放"
        assert items[0].brand == "ITC"
        assert items[0].model == "T-62200"
        assert items[0].qty == 2
        assert items[0].params == ["额定功率150W", "阻抗8Ω"]
        assert items[1].params == ["16路", "内置USB播放"]

    def test_empty_table(self):
        assert rows_to_items([]) == []

    def test_header_not_first_row(self):
        raw = [
            ["某单位招标清单"],
            ["序号", "设备名称", "品牌", "数量"],
            ["1", "主音箱", "惠威", "4"],
        ]
        items = rows_to_items(raw)
        assert len(items) == 1
        assert items[0].name == "主音箱"