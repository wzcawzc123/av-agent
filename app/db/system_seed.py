"""系统目录与设备角色目录种子（幂等）。角色 role_code 全局唯一，带导入/检索用的匹配关键词。"""
import json

from app.db.models import DeviceRole, System

_SYSTEMS = [
    ("prosound", "专业扩声", "音箱/功放/调音台/音频处理器"),
    ("speech", "会议发言", "手拉手/无线会议话筒"),
    ("display", "显示系统", "LED/LCD/拼接屏/投影"),
    ("paperless", "无纸化会议", "升降屏终端/无纸化服务器"),
    ("control", "中控矩阵", "中控主机/矩阵/时序电源"),
    ("distributed", "分布式", "分布式编解码节点"),
    ("lighting", "灯光系统", "会议照明/舞台灯光"),
    ("broadcast", "公共广播", "广播喇叭/功放/寻呼"),
    ("videoconf", "视频会议", "视频会议终端/摄像头"),
]

_ROLES = [
    ("prosound", "main_speaker", "主音箱", "只", ["音箱", "喇叭", "扬声器", "音柱"]),
    ("prosound", "subwoofer", "超低音音箱", "只", ["低音", "超低"]),
    ("prosound", "amplifier", "功放", "台", ["功放", "放大器"]),
    ("prosound", "mixer", "调音台", "台", ["调音台"]),
    ("prosound", "audio_processor", "音频处理器", "台", ["处理器", "音频矩阵", "DSP"]),
    ("prosound", "power_sequencer", "电源时序器", "台", ["时序器", "电源控制器"]),
    ("speech", "speech_host", "会议发言主机", "台", ["会议主机", "发言主机", "控制主机"]),
    ("speech", "chairman_unit", "主席单元", "台", ["主席"]),
    ("speech", "delegate_unit", "代表单元", "台", ["代表"]),
    ("speech", "wireless_mic", "无线话筒", "套", ["无线手持", "无线麦克风", "一拖"]),
    ("speech", "mic_antenna", "天线系统", "套", ["天线分配", "天线放大器", "吸顶天线"]),
    ("display", "led_screen", "LED显示屏", "㎡", ["LED", "led", "全彩", "显示屏", "屏体"]),
    ("display", "lcd_splicing", "液晶拼接屏", "台", ["拼接", "LCD"]),
    ("display", "single_display", "单屏显示器", "台", ["显示器", "电视机", "一体机", "智会屏"]),
    ("display", "video_processor", "图像处理器", "台", ["图像处理", "视频处理器", "拼接处理器"]),
    ("display", "projector", "投影机", "台", ["投影"]),
    ("display", "screen", "幕布", "幅", ["幕布", "投影幕"]),
    ("paperless", "paperless_terminal", "无纸化终端", "台", ["升降屏", "升降终端", "无纸化", "触控终端"]),
    ("paperless", "paperless_server", "无纸化服务器", "台", ["服务器"]),
    ("paperless", "paperless_software", "无纸化软件", "套", ["软件", "授权"]),
    ("control", "matrix_hdmi", "HDMI矩阵", "台", ["矩阵", "切换器", "HDMI"]),
    ("control", "control_host", "中控主机", "台", ["中控", "控制主机", "可编程"]),
    ("control", "control_panel", "中控触屏", "台", ["触摸屏", "触屏", "控制面板", "面板"]),
    ("control", "relay_module", "电源/继电器模块", "台", ["继电器", "电源模块", "调光模块"]),
    ("distributed", "encode_node", "编码节点", "台", ["编码器", "编码节点", "输入节点"]),
    ("distributed", "decode_node", "解码节点", "台", ["解码器", "解码节点", "输出节点"]),
    ("distributed", "distributed_platform", "分布式管理平台", "套", ["分布式", "管理平台", "控制软件"]),
    ("lighting", "panel_light", "平板会议灯", "台", ["会议灯", "平板灯", "面板灯", "三基色"]),
    ("lighting", "beam_light", "光束灯", "台", ["光束"]),
    ("lighting", "par_light", "PAR灯", "台", ["PAR", "帕灯", "染色"]),
    ("lighting", "light_console", "灯光控制台", "台", ["控台", "灯光控制", "控制台"]),
    ("lighting", "dmx_splitter", "信号放大器", "台", ["放大器", "DMX", "信号分配"]),
    ("broadcast", "ceiling_speaker", "天花喇叭", "只", ["天花", "吸顶"]),
    ("broadcast", "horn_speaker", "音柱/号角", "只", ["音柱", "号角", "壁挂"]),
    ("broadcast", "broadcast_amplifier", "广播功放", "台", ["功放", "广播"]),
    ("broadcast", "paging_mic", "寻呼话筒", "台", ["寻呼", "话筒"]),
    ("videoconf", "vc_terminal", "视频会议终端", "台", ["视频会议", "终端"]),
    ("videoconf", "vc_camera", "会议摄像头", "台", ["摄像头", "摄像机"]),
    ("videoconf", "vc_allinone", "一体化会议屏", "台", ["一体机", "智会屏", "投屏"]),
]


def seed_system_catalog(session):
    for code, name, desc in _SYSTEMS:
        row = session.query(System).filter_by(code=code).first()
        if row is None:
            session.add(System(code=code, name=name, description=desc))
        else:
            row.name, row.description = name, desc
    for sys_code, role_code, role_name, unit, kws in _ROLES:
        row = session.query(DeviceRole).filter_by(role_code=role_code).first()
        if row is None:
            session.add(DeviceRole(system_code=sys_code, role_code=role_code,
                                   role_name=role_name, unit=unit,
                                   match_keywords=json.dumps(kws, ensure_ascii=False)))
        else:
            row.system_code = sys_code
            row.role_name, row.unit, row.match_keywords = role_name, unit, json.dumps(kws, ensure_ascii=False)
    session.flush()
