"""六个系统引擎：会议发言 / 中控矩阵 / 显示(含拼接) / 无纸化 / 分布式 / 灯光。

每个 build_* 输入 slots，输出角色行列表（供 composer 品牌回填）。
"""
from app.engines.systems.scene import (
    resolve_seats, resolve_signal_sources, resolve_displays, seating_capacity,
    recommend_led_pitch, estimate_viewing_distance,
)
import math


def _r(system, role, role_name, qty, unit, spec="", note=""):
    return {"system": system, "role": role, "role_name": role_name,
            "qty": int(qty), "unit": unit, "spec": spec, "note": note}


# ---------- 会议发言 ----------
def build_speech(slots: dict) -> list[dict]:
    seats = resolve_seats(slots)
    cap = seating_capacity(seats)
    rows = [
        _r("speech", "speech_host", "会议发言主机", 1, "台",
           "支持数字手拉手/级联", f"带席位 {cap} 位"),
        _r("speech", "chairman_unit", "主席单元", seats["chairman"], "台",
           "嵌入式安装", "含麦克风"),
        _r("speech", "delegate_unit", "代表单元", seats["delegate"], "台",
           "嵌入式安装", "含麦克风"),
    ]
    # 无线话筒：小型会议室常配一套无线手持备用
    scene = str(slots.get("scene") or "")
    if cap <= 8 or "培训" in scene:
        rows.append(_r("speech", "wireless_mic", "无线手持话筒", 2, "套",
                       "一拖二 UHF", "备用/机动"))
    # 报告厅/礼堂：嘉宾席配无线鹅颈，兼顾发言与主席台
    if "报告厅" in scene or "礼堂" in scene or "剧场" in scene:
        rows.append(_r("speech", "wireless_gooseneck", "无线鹅颈话筒", 4, "只",
                       "UHF 电容", "嘉宾席/讲台拾音"))
    # 单元数量大时需要天线/延长器
    if cap > 16:
        rows.append(_r("speech", "mic_antenna", "天线分配系统", 1, "套",
                       "含吸顶天线×2", "手拉手长距离传输"))
    return rows


# ---------- 中控矩阵 ----------
def build_control(slots: dict) -> list[dict]:
    sources = resolve_signal_sources(slots)
    displays = resolve_displays(slots)
    if sources <= 4:
        matrix = "4进4出 HDMI矩阵"
        mqty = 1
    elif sources <= 8:
        matrix = "8进8出 HDMI矩阵"
        mqty = 1
    else:
        matrix = "16进16出 HDMI矩阵"
        mqty = 1
    rows = [
        _r("control", "matrix_hdmi", "HDMI矩阵", mqty, "台", matrix,
           f"信号源 {sources} 路 / 输出 {max(displays, 4)} 路"),
        _r("control", "control_host", "可编程中控主机", 1, "台",
           "支持RS232/IR/IO/网络控制", "联动灯光/显示/音响"),
        _r("control", "control_panel", "中控无线触屏", 1, "台",
           "10寸以上安卓触屏", "桌面或壁挂"),
        _r("control", "power_sequencer", "电源时序器", 1, "台",
           "8路带滤波", "设备供电管理"),
    ]
    if displays > 1:
        rows.append(_r("control", "relay_module", "继电器/调光模块", 1, "台",
                       "8路继电器", "灯光/电源联动"))
    return rows


# ---------- 显示系统 ----------
def build_display(slots: dict) -> list[dict]:
    scene = str(slots.get("scene") or "")
    area = float(slots.get("area") or 0)
    disp = slots.get("display") or {}
    mode = str(disp.get("mode") or "")
    rows = []
    # LED 需求：交给 LED 引擎逻辑（数量按面积/点距，此处给角色占位由产品回填）
    if "led" in scene.lower() or mode == "led" or "led" in str(disp):
        w = float(disp.get("w") or 0) or (math.sqrt(area) * 0.5 if area else 4)
        h = float(disp.get("h") or 0) or (w * 0.5625)
        sqm = round(w * h, 2)
        # 点距：用户显式指定优先，否则按最近观看距离速查
        pitch = float(disp.get("pitch") or 0) or recommend_led_pitch(estimate_viewing_distance(slots))
        pitch_label = str(pitch).rstrip("0").rstrip(".")
        rows.append(_r("display", "led_screen", "LED显示屏", sqm, "㎡",
                       f"P{pitch_label} 全彩", f"约 {w}m×{h}m，最近观看距离约 {estimate_viewing_distance(slots):.1f}m"))
        rows.append(_r("display", "video_processor", "LED视频处理器", 1, "台",
                       "多路输入拼接处理", "含发送卡"))
        return rows
    # 拼接屏：显式 mode=拼接 或 指挥/监控/展厅
    if mode == "splicing" or "指挥" in scene or "监控" in scene or "展厅" in scene or "展馆" in scene:
        cols = int(disp.get("cols") or 2)
        rows_n = int(disp.get("rows") or 2)
        total = cols * rows_n
        rows.append(_r("display", "lcd_splicing", "液晶拼接屏", total, "台",
                       "55寸 3.5mm拼缝", f"{cols}×{rows_n} 拼接"))
        rows.append(_r("display", "video_processor", "拼接处理器", 1, "台",
                       f"支持 {total} 路输出", "信号分配与开窗"))
        rows.append(_r("display", "single_display", "辅助监视器", 1, "台",
                       "65寸", "预览/备显"))
        return rows
    # 单屏：面积分档
    if area <= 80:
        rows.append(_r("display", "single_display", "会议一体机/显示器", 1, "台", "75寸"))
    elif area <= 150:
        rows.append(_r("display", "single_display", "会议一体机/显示器", 1, "台", "86寸"))
    else:
        rows.append(_r("display", "single_display", "会议一体机/显示器", 1, "台", "98寸"))
    if "报告厅" in scene or area > 200:
        rows.append(_r("display", "single_display", "辅助显示器", 1, "台", "65寸", "演讲提词/备用"))
    return rows


# ---------- 无纸化会议 ----------
def build_paperless(slots: dict) -> list[dict]:
    seats = resolve_seats(slots)
    cap = seating_capacity(seats)
    rows = [
        _r("paperless", "paperless_terminal", "无纸化升降终端", cap, "台",
           "15.6寸升降式触控屏", "主席/代表均配"),
        _r("paperless", "paperless_server", "无纸化服务器", 1, "台",
           "含会议管理软件授权", f"支持 {cap} 席位并发"),
    ]
    # 交换机按席位分档
    if cap <= 24:
        rows.append(_r("paperless", "paperless_software", "千兆交换机", 1, "台",
                       "24口千兆", "无纸化专网"))
    else:
        rows.append(_r("paperless", "paperless_software", "千兆交换机", 2, "台",
                       "48口千兆", "无纸化专网"))
    return rows


# ---------- 分布式 ----------
def build_distributed(slots: dict) -> list[dict]:
    sources = resolve_signal_sources(slots)
    displays = resolve_displays(slots)
    rows = [
        _r("distributed", "encode_node", "分布式编码节点", sources, "台",
           "HDMI输入 1080P/4K", f"接入 {sources} 路信号"),
        _r("distributed", "decode_node", "分布式解码节点", displays, "台",
           "HDMI输出 1080P/4K", f"驱动 {displays} 个显示端"),
        _r("distributed", "distributed_platform", "分布式综合管理平台", 1, "套",
           "含控制软件与授权", "可视化管理/预案"),
    ]
    return rows


# ---------- 灯光系统 ----------
def build_lighting(slots: dict) -> list[dict]:
    scene = str(slots.get("scene") or "")
    area = float(slots.get("area") or 0)
    rows = []
    if "舞台" in scene or "剧场" in scene or "礼堂" in scene or "演出" in scene:
        rows.append(_r("lighting", "beam_light", "光束灯", 8, "台", "230W 7R", "舞台效果"))
        rows.append(_r("lighting", "par_light", "LED PAR灯", 12, "台", "54×3W RGBW", "染色铺光"))
        rows.append(_r("lighting", "light_console", "灯光控制台", 1, "台",
                       "2048通道", "舞台灯具控制"))
        rows.append(_r("lighting", "dmx_splitter", "DMX信号放大器", 2, "台", "8路", "信号隔离分配"))
        return rows
    # 会议室基础照明（三基色会议灯 + 调光）
    if area <= 100:
        n = 6
    elif area <= 200:
        n = 10
    else:
        n = 16
    rows.append(_r("lighting", "panel_light", "三基色会议灯", n, "台",
                   "600W 冷/暖双色", "会议室布光"))
    rows.append(_r("lighting", "relay_module", "调光控制模块", 1, "台",
                   "8路调光", "中控联动"))
    return rows


SYSTEM_BUILDERS = {
    "speech": build_speech,
    "control": build_control,
    "display": build_display,
    "paperless": build_paperless,
    "distributed": build_distributed,
    "lighting": build_lighting,
}


# ---------- 专业扩声（通用角色结构，不依赖硬编码型号） ----------
def build_prosound(slots: dict) -> list[dict]:
    area = float(slots.get("area") or 0)
    scene = str(slots.get("scene") or "")
    room = slots.get("room") or {}
    height = float(room.get("height") or 0)
    # 音箱数量分档（专业扩声经验值：吸顶/壁挂按覆盖面积）
    if area <= 100:
        n = 2
        spec = "8寸 壁挂/吸顶"
    elif area <= 200:
        n = 4
        spec = "10寸 壁挂"
    elif area <= 300:
        n = 6
        spec = "10寸 壁挂"
    else:
        n = 8
        spec = "12寸 壁挂/线阵"
    # 大空间/高层高 → 主扩升级线阵或大功率音箱（层高 >5m 或报告厅）
    tall_room = height > 5 or "报告厅" in scene or "剧场" in scene or "礼堂" in scene
    if tall_room and n >= 4:
        spec = "线阵音箱 双10寸" if n >= 8 else "12寸 主扩+返送"
    # 功放：每 2 只音箱 1 台功放（立体声 2 通道）
    amp = max(1, (n + 1) // 2)
    rows = [
        _r("prosound", "main_speaker", "专业音箱", n, "只", spec,
           f"按 {area:.0f}㎡ 覆盖计算" + (f"，层高 {height:.1f}m" if height else "")),
        _r("prosound", "amplifier", "专业功放", amp, "台",
           f"2×{250 if n <= 4 else 400}W@8Ω", "与音箱功率匹配"),
        _r("prosound", "mixer", "调音台", 1, "台",
           "数字调音台 16路" if (area > 200 or "报告厅" in scene) else "调音台 12路",
           "信号混音"),
    ]
    if tall_room:
        rows.append(_r("prosound", "main_speaker", "舞台返送音箱", 2, "只",
                       "12寸", "舞台/主席位监听"))
    if area > 200 or "报告厅" in scene:
        rows.append(_r("prosound", "audio_processor", "音频处理器", 1, "台",
                       "8进8出 DSP", "压限/均衡/反馈抑制"))
        rows.append(_r("prosound", "power_sequencer", "电源时序器", 1, "台",
                       "8路", "音响系统供电管理"))
    return rows


SYSTEM_BUILDERS["prosound"] = build_prosound
