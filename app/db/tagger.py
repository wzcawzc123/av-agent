"""产品自动打标签：按名称/分类/品牌推断 system 与 role_tags。

规则数据与 system_seed 同源（DeviceRole.match_keywords），此处提供纯函数供导入器与检索共用。
"""

from app.db.system_seed import _ROLES

# 系统级关键词：名称或分类命中即归属该系统
_SYSTEM_KEYWORDS = {
    "prosound": ["音箱", "功放", "调音台", "音频处理器", "专业音响", "同轴", "线阵"],
    "speech": ["会议单元", "发言", "话筒", "麦克风", "咪头", "主席", "代表"],
    "display": ["LED", "显示屏", "拼接", "液晶", "显示器", "投影", "幕布", "智会屏", "会议平板", "触控一体"],
    "paperless": ["无纸化", "升降屏", "升降终端"],
    "control": ["矩阵", "中控", "切换器", "时序器", "继电器", "触屏"],
    "distributed": ["分布式", "编解码", "编码节点", "解码节点"],
    "lighting": ["灯光", "会议灯", "光束", "帕灯", "PAR", "三基色", "调光"],
    "broadcast": ["广播", "寻呼", "号角", "天花喇叭", "吸顶"],
    "videoconf": ["视频会议", "摄像头", "摄像机", "一体机", "终端"],
}

# 角色关键词权重高的品牌排除词（避免把"会议平板"同时打成发言）
_ROLE_BLACKLIST = {
    "chairman_unit": ["主席台", "主席桌"],
    "delegate_unit": ["代表处"],
}


def _kw_hit(text: str, kws) -> bool:
    if not text:
        return False
    return any(k.lower() in text.lower() for k in kws)


def infer_system(name: str, category: str) -> str:
    """名称优先，其次分类；返回 system code 或 ''。"""
    for code, kws in _SYSTEM_KEYWORDS.items():
        if _kw_hit(name, kws) or _kw_hit(category, kws):
            return code
    return ""


def infer_role_tags(name: str, category: str, system: str) -> list[str]:
    """按角色匹配关键词打 role_code 标签；命中多个取全部。"""
    tags = []
    for sys_code, role_code, _rname, _unit, kws in _ROLES:
        if system and sys_code != system:
            continue
        if not _kw_hit(name, kws) and not _kw_hit(category, kws):
            continue
        if role_code in _ROLE_BLACKLIST and any(
                b.lower() in (name or "").lower() for b in _ROLE_BLACKLIST[role_code]):
            continue
        tags.append(role_code)
    return tags


def tag_product(name: str, category: str, brand: str = "") -> dict:
    """返回 {"system": ..., "role_tags": [...]}。"""
    system = infer_system(name, category)
    # 品牌强信号修正：MAXHUB 一体机倾向显示/视频会议
    if brand:
        if _kw_hit(brand, ["maxhub", "视源", "希沃"]) and "会议平板" in (name or ""):
            system = system or "display"
    if not system:
        system = infer_system(name, "")
    return {"system": system, "role_tags": infer_role_tags(name, category, system)}
