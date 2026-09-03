"""偏离匹配评分权重（可从 DB/设置覆盖，默认值移植自 itc VBA 逆向）。"""

DEFAULT_DEVIATION_RULES = {
    "numeric_char_weight": 0.2,   # 单字命中（数字类字符）
    "single_char_weight": 0.75,   # 单字命中（普通字符）
    "numeric_double_weight": 0.75,  # 双字命中（数字开头）
    "double_char_weight": 1.0,    # 双字命中（普通）
    "high_threshold": 6.0,
    "medium_threshold": 2.0,
}
