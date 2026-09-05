"""产品能力标签（capability）规则推断。

品牌无关：只依赖 名称/描述/角色 关键词，不依赖品牌词表。
新品牌产品首次入库后同样适用；可选 LLM 精修（见 llm_pick）。

能力码设计：语义化小写码，按功能命名（tuner/usb_player/preamp/...），
功放通道等数值维度不在此表（走 dimensions.channels）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

# capability -> (关键词列表, 角色码列表)
# 角色码列表命中时代表该产品承担此角色 → 推断对应能力
CAPABILITY_RULES: dict[str, tuple[list[str], list[str]]] = {
    "tuner": (["调谐器", "收音", "tuner"], []),
    "usb_player": (["usb播放", "usb 播放", "usb播放器", "mp3", "usb接口播放"], []),
    "preamp": (["前置放大", "前置放大器", "preamp"], []),
    "power_amp": (["功率放大器", "功放", "放大器"], []),
    "broadcast_amp": (["广播功放", "定压功放", "定压"], ["broadcast_amplifier"]),
    "mixer": (["调音台", "混音器", "mixer"], []),
    "dsp": (["dsp", "数字音频处理", "音频处理器", "效果器"], ["audio_processor"]),
    "paging_mic": (["寻呼话筒", "寻呼"], ["paging_mic"]),
    "mic": (["话筒", "麦克风", "麦克", "mic"], ["wireless_mic", "paging_mic", "array_mic", "chairman_unit", "delegate_unit"]),
    "wireless_mic": (["无线话筒", "无线麦克", "一拖"], ["wireless_mic"]),
    "array_mic": (["阵列麦", "阵列麦克"], ["array_mic"]),
    "ceiling_speaker": (["天花喇叭", "吸顶喇叭", "天花"], ["ceiling_speaker"]),
    "horn_speaker": (["音柱", "号角", "壁挂音箱", "室外音柱"], ["horn_speaker"]),
    "speaker": (["音箱", "扬声器", "喇叭"], ["main_speaker", "subwoofer", "ceiling_speaker", "horn_speaker", "soundbar"]),
    "soundbar": (["一体机", "soundbar", "条形音响", "会议音响"], ["soundbar"]),
    "display": (["显示屏", "显示器", "液晶屏", "大屏"], ["single_display", "led_screen", "lcd_splicing", "projector", "screen"]),
    "led_display": (["led", "小间距"], ["led_screen"]),
    "touch": (["触摸", "触控", "touch"], []),
    "camera": (["摄像头", "摄像机", "camera"], ["camera"]),
    "video_proc": (["图像处理", "视频处理器", "拼接处理器"], ["video_processor"]),
    "matrix": (["矩阵"], ["matrix_hdmi"]),
    "hdmi_matrix": (["hdmi矩阵", "hdmi 矩阵"], ["matrix_hdmi"]),
    "control_host": (["中控主机", "控制主机"], ["control_host"]),
    "control_panel": (["触控屏", "控制面板"], ["control_panel"]),
    "relay": (["继电器", "电源控制", "时序电源"], ["relay_module"]),
    "paperless": (["无纸化"], ["paperless_terminal"]),
    "conference": (["视频会议", "会议终端"], ["codec"]),
}


@dataclass
class CapabilityHit:
    capability: str
    source: str  # keyword|role
    confidence: float


def _normalize_text(*parts: str) -> str:
    return " ".join((p or "") for p in parts).lower()


def tag_capabilities(name: str, description: str = "", role_tags: str | list | None = None) -> list[CapabilityHit]:
    """规则推断产品能力标签。role_tags 可为 JSON 字符串或列表。"""
    hits: dict[str, CapabilityHit] = {}
    text = _normalize_text(name, description)
    if isinstance(role_tags, str):
        try:
            roles = json.loads(role_tags or "[]")
        except (json.JSONDecodeError, TypeError):
            roles = []
    else:
        roles = list(role_tags or [])

    for cap, (keywords, role_codes) in CAPABILITY_RULES.items():
        kw_hit = any(k in text for k in keywords)
        role_hit = any(r in roles for r in role_codes)
        if kw_hit and role_hit:
            hits[cap] = CapabilityHit(cap, "keyword", 1.0)
        elif kw_hit:
            hits[cap] = CapabilityHit(cap, "keyword", 0.9)
        elif role_hit:
            hits[cap] = CapabilityHit(cap, "role", 0.85)
    return list(hits.values())
