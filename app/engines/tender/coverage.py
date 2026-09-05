"""能力覆盖分析：识别「某设备功能已被另一匹配产品覆盖」的合并(merged)场景。

规则保守：只对具有明确能力标签的项生效（mixer/dsp/tuner/usb_player/preamp 等），
同类设备（双方需求能力相同）不会互相合并，误判风险低。extra 打标交给 LLM 精修层。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Product, ProductCapability
from app.engines.tender.capability import tag_capabilities
from app.engines.tender.model import TenderMatchRow


# 主设备核心能力：独立采购主体（显示/扩声/拾音/摄像/矩阵/会议终端等），不参与合并。
# 只有附属功能件（mixer/dsp/tuner/preamp/usb_player 等被主机集成的能力）才可被合并。
CORE_DEVICE_CAPS = {
    "display", "led_display", "speaker", "ceiling_speaker", "horn_speaker", "soundbar",
    "power_amp", "broadcast_amp", "mic", "wireless_mic", "paging_mic", "array_mic",
    "camera", "conference", "matrix", "hdmi_matrix", "video_proc", "control_host", "paperless",
}


def item_caps(name: str, params: list[str]) -> set[str]:
    return {h.capability for h in tag_capabilities(name, " ".join(params or []))}


def product_caps(session: Session, product_id: int) -> set[str]:
    """产品能力：优先已落库的 ProductCapability，缺失时用规则打标兜底。"""
    if not product_id:
        return set()
    rows = session.query(ProductCapability).filter_by(product_id=product_id).all()
    if rows:
        return {r.capability for r in rows}
    p = session.get(Product, product_id)
    if not p:
        return set()
    roles = getattr(p, "role_tags", None)
    return {h.capability for h in tag_capabilities(p.name, p.description or "", roles)}


def detect_merge(rows: list[TenderMatchRow], session: Session) -> int:
    """就地标注 merged。返回发生合并的行数。"""
    caps: dict[int, set[str]] = {i: item_caps(r.name, r.params) for i, r in enumerate(rows)}
    pcaps: dict[int, set[str]] = {
        i: product_caps(session, r.matched_product_id)
        for i, r in enumerate(rows)
        if r.status in ("matched", "partial")
    }
    changes = 0
    for i, ri in enumerate(rows):
        if ri.status in ("no_match", "merged", "new"):
            continue
        ic = caps.get(i) or set()
        if not ic:
            continue
        for j, rj in enumerate(rows):
            if i == j or rj.status in ("no_match", "merged"):
                continue
            jc = pcaps.get(j) or set()
            jreq = caps.get(j) or set()
            # 能力被 j 的匹配产品覆盖，且 i、j 需求能力不同（避免同类互并）；
            # 主设备（显示/扩声/拾音等）即使能力被覆盖也不合并，只合并附属功能件
            if ic and ic <= jc and not (ic <= jreq) and not (ic & CORE_DEVICE_CAPS):
                ri.merged_into = rj.matched_model or rj.name
                ri.status = "merged"
                ri.remark = (ri.remark + "；" if ri.remark else "") + f"功能已被「{rj.name}」顺带覆盖，建议合并"
                changes += 1
                break
    return changes