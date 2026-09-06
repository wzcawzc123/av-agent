"""招标匹配快照持久化与 BOM 转换。"""
from __future__ import annotations

import json
import time

from sqlalchemy.orm import Session

from app.db.models import TenderMatch
from app.engines.tender.model import TenderMatchRow


def new_snapshot() -> str:
    """快照标识：秒级时间戳 + 毫秒，避免同秒多批冲突。"""
    ms = int(time.time() * 1000) % 1000
    return f"{time.strftime('%Y%m%d%H%M%S')}{ms:03d}"


def save_snapshot(session: Session, project_id: int, rows: list[TenderMatchRow]) -> str:
    """保存一批匹配行；返回快照标识。"""
    snap = new_snapshot()
    for r in rows:
        session.add(
            TenderMatch(
                project_id=project_id,
                snapshot=snap,
                source_idx=r.source_idx,
                name=r.name,
                brand=r.brand,
                model=r.model,
                qty=r.qty,
                params_json=json.dumps(r.params, ensure_ascii=False),
                status=r.status,
                matched_product_id=r.matched_product_id,
                matched_model=r.matched_model,
                score=r.score,
                remark=r.remark,
                merged_into=r.merged_into,
                preference=r.preference,
            )
        )
    return snap


def _to_row(m: TenderMatch) -> TenderMatchRow:
    try:
        params = json.loads(m.params_json or "[]")
    except (json.JSONDecodeError, TypeError):
        params = []
    return TenderMatchRow(
        source_idx=m.source_idx,
        name=m.name,
        brand=m.brand,
        model=m.model,
        qty=m.qty,
        params=params,
        status=m.status,
        matched_product_id=m.matched_product_id,
        matched_model=m.matched_model,
        score=m.score,
        remark=m.remark,
        merged_into=m.merged_into,
        preference=m.preference,
    )


def load_rows(session: Session, project_id: int, snapshot: str = "") -> list[TenderMatchRow]:
    """读取项目最新（或指定）快照的匹配行。"""
    q = session.query(TenderMatch).filter(TenderMatch.project_id == project_id)
    if snapshot:
        q = q.filter(TenderMatch.snapshot == snapshot)
    else:
        latest = (
            session.query(TenderMatch.snapshot)
            .filter(TenderMatch.project_id == project_id)
            .order_by(TenderMatch.snapshot.desc())
            .first()
        )
        if not latest:
            return []
        q = q.filter(TenderMatch.snapshot == latest[0])
    return [_to_row(m) for m in q.order_by(TenderMatch.id).all()]


def update_row(session: Session, row_id: int, **fields) -> bool:
    """人工确认：更新单行状态/匹配产品/备注。"""
    m = session.query(TenderMatch).filter_by(id=row_id).first()
    if not m:
        return False
    allowed = {
        "status",
        "matched_product_id",
        "matched_model",
        "remark",
        "merged_into",
        "qty",
        "model",
        "brand",
        "name",
        "preference",
    }
    for k, v in fields.items():
        if k in allowed and v is not None:
            setattr(m, k, v)
    return True


def to_bom_rows(rows: list[TenderMatchRow]) -> list[dict]:
    """转为 rebuild 端点的 BOM 行格式（system/type/spec/brand/model/qty/unit/price/note）。

    merged/extra 行不进 BOM（已标红剔除）；no_match/new 行以 name 占位待人工补充型号。
    """
    out: list[dict] = []
    for r in rows:
        if r.status in ("merged", "extra"):
            continue
        out.append(
            {
                "system": "",
                "type": r.name,
                "spec": " ".join(r.params)[:200],
                "brand": r.brand,
                "model": r.matched_model or r.model or "（待定）",
                "qty": r.qty,
                "unit": "台",
                "price": 0,
                "note": r.remark,
                "category": "主要设备",
                "tender_status": r.status,
                "tender_score": round(r.score, 4),
                "matched_product_id": r.matched_product_id,
            }
        )
    return out


def build_deviation_rows(session, project_id: int, limit: int = 300) -> list[dict]:
    """由项目最近招标快照生成偏离表行（6 列：seq/device/tender_param/bid_param/deviation/note）。

    - matched    → 满足（投标产品参数覆盖招标要求）
    - partial    → 部分满足 / 存在偏离
    - no_match / new → 偏离（库内无匹配，需补充或人工确认）
    - merged / extra → 与 to_bom_rows 一致剔除（已并入或被判冗余）
    无快照数据返回 []，调用方回退占位行。
    """
    rows = load_rows(session, project_id)
    if not rows:
        return []
    out: list[dict] = []
    for r in rows:
        if r.status in ("merged", "extra"):
            continue
        tender = " ".join(r.params) if r.params else r.name
        if r.status == "matched":
            dev, bid = "满足", r.matched_model or r.model or "—"
        elif r.status == "partial":
            dev, bid = "部分满足（存在偏离）", r.matched_model or "（待核）"
        else:  # no_match / new
            dev, bid = "偏离（待补充/确认）", "（无匹配产品）"
        note = r.remark
        if r.status == "partial" and not note:
            note = "参数与招标要求不完全一致，建议复核"
        elif r.status in ("no_match", "new") and not note:
            note = "产品库无匹配型号，需人工补充"
        out.append({
            "seq": len(out) + 1,
            "device": r.name,
            "tender_param": tender,
            "bid_param": bid,
            "deviation": dev,
            "note": note,
        })
        if len(out) >= limit:
            break
    return out
