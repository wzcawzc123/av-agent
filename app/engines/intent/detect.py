"""对话 → 引擎意图检测（本地规则，不调 LLM）。

命中规则返回 {"engine": "meeting|broadcast|led|deviation", "params": {...}}，
未命中返回 None。规则保持轻量：关键词 + 正则，供 /api/chat 前置分流。
"""
import math
import re

_MEETING_KEY = ("会议", "音响", "音箱", "设备", "会议室", "报告厅", "阶梯")
_MEETING_STRONG = ("清单", "选型", "列表", "配置单", "报价单", "配单")  # 强意图词，避免误拦截「…方案」
_BROADCAST_KEY = ("广播", "分区")
_LED_KEY = ("led", "led屏", "大屏", "显示屏", "屏体")
_DEVIATION_KEY = ("偏离表", "偏差表")

_CODE_RE = re.compile(r"(?<![\d-])(\d{1,2}(?:-\d{1,2}){4,9}-?)(?![\d-])")
_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")


def _meeting_code(text: str) -> str | None:
    m = _CODE_RE.search(text)
    if m:
        return m.group(1).rstrip("-")
    # 无编码：面积 → 长宽；场景关键词 → 类型
    area = None
    for seg in text.replace("平", " ").replace("㎡", " ").replace("m²", " ").split():
        mm = _NUM_RE.match(seg)
        if mm and "平" in text[: text.find(seg) + len(seg)] or "㎡" in text or "m²" in text:
            v = float(mm.group(1))
            if area is None and v > 0:
                area = v
    if area is None:
        mm = re.search(r"(\d+(?:\.\d+)?)\s*(?:平米|平方|平|㎡|m²)", text)
        if mm:
            area = float(mm.group(1))
    if area is None:
        return None
    side = int(round(math.sqrt(area)))
    side = max(1, min(side, 30))
    scene = "1"
    if "报告厅" in text or "礼堂" in text:
        scene = "3"
    elif "阶梯" in text:
        scene = "2"
    return f"{side}-{side}-{max(3, side // 2)}-0-0-{scene}-2-"


def _broadcast_zones(text: str) -> list[dict]:
    zones = []
    # 优先：分区名 数量只型号 … 例如 "1F大厅 24只T-601 12只T-105"
    seg = re.split(r"[，。;；]", text)
    for chunk in seg:
        m = re.match(r"\s*([^\d\s,，;；]+(?:[层厅区号]|F|楼)?)\s+(.+)", chunk)
        if not m:
            continue
        zone = {"zone": m.group(1)}
        rest = m.group(2)
        items = re.findall(r"(\d+)\s*只?\s*([A-Za-z][A-Za-z0-9\-]*)", rest)
        for qty, model in items:
            zone[model] = int(qty)
        if len(zone) > 1:
            zones.append(zone)
    return zones


def _led_params(text: str) -> dict | None:
    model = None
    for m in re.findall(r"(TV-PH\d+-YZ|TV-PH\d+)", text):
        model = m
        break
    nums = [float(x) for x in _NUM_RE.findall(text)]
    if len(nums) < 2:
        return None
    w, h = nums[0], nums[1]
    mode = "就近"
    if "向上" in text:
        mode = "向上"
    elif "向下" in text:
        mode = "向下"
    return {"want_w_m": w, "want_h_m": h, "model": model or "TV-PH250-YZ", "round_mode": mode}


def _deviation_items(text: str) -> list[str]:
    # 去掉触发词后按分隔符拆分；无分隔符则整段为一条
    body = re.sub(r"(帮我|请|做|生成|出)?(偏离表|偏差表)[：:、\s]*", "", text).strip(" ，。;；")
    if not body:
        return []
    parts = re.split(r"[，,;；\n]", body)
    return [p.strip(" 、1234567890.。") for p in parts if p.strip()]


_GENERIC_SYSTEMS = ("扩声", "发言", "显示", "无纸化", "中控", "矩阵", "分布式",
                    "灯光", "广播", "视频会议", "会议发言")
_GENERIC_BRANDS = ("惠威", "MAXHUB", "JBL", "BOSE", "博士", "雷亚", "ITC", "台电",
                   "华为", "海康", "大华", "利亚德", "洲明", "艾比森", "哈曼",
                   "铁三角", "舒尔", "索尼", "松下", "JVC", "克莱默", "快思聪")
_GENERIC_BRAND_RE = re.compile("(?:用|选|配)(" + "|".join(_GENERIC_BRANDS) + ")")


def should_use_generic_flow(text: str) -> bool:
    """通用化架构特征：多系统 / 品牌约束 / 方案类交付 → 走新流程而非老引擎直通。"""
    hits = sum(1 for kw in _GENERIC_SYSTEMS if kw in text)
    if hits >= 2:
        return True
    if _GENERIC_BRAND_RE.search(text):
        return True
    if "方案" in text and ("清单" in text or "列表" in text or "设备" in text):
        return True
    return False


def detect_engine_intent(text: str) -> dict | None:
    low = text.lower()
    if any(k in low for k in _MEETING_KEY) and any(k in low for k in _MEETING_STRONG):
        code = _meeting_code(text)
        if code:
            return {"engine": "meeting", "params": {"code": code, "header": {}}}
    if any(k in low for k in _BROADCAST_KEY):
        zones = _broadcast_zones(text)
        if zones:
            return {"engine": "broadcast", "params": {"zones": zones, "header": {}}}
    if any(k in low for k in _LED_KEY):
        p = _led_params(text)
        if p:
            return {"engine": "led", "params": {**p, "header": {}}}
    if any(k in low for k in _DEVIATION_KEY):
        items = _deviation_items(text)
        if items:
            return {"engine": "deviation", "params": {"tender_items": items, "models": [], "llm_enabled": False}}
    return None
