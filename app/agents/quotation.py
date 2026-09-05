"""报价 Agent：统计 BOM 总价/待询价项，落一条 Quotation 记录（total_amount 汇总）。"""
import json

from app.agents.base_agent import BaseAgent
from app.agents.registry import register


class QuotationAgent(BaseAgent):
    name = "quotation"
    description = "汇总报价并写入 Quotation 记录"

    async def analyze(self, context) -> None:
        if not context.bom:
            raise ValueError("设备清单为空，无法报价（需先执行 product_selection/bom_generation）")
        if context.session is None:
            raise ValueError("缺少数据库会话（context.session）")

    async def execute(self, context) -> None:
        from app.db.models import Quotation

        items = []
        total = 0.0
        pending = 0
        for d in context.bom:
            price = float(d.get("market_price") or d.get("base_price") or 0)
            qty = int(d.get("qty") or 1)
            amount = round(price * qty, 2)
            total += amount
            if price <= 0:
                pending += 1
            items.append({
                "category": d.get("category", ""),
                "type": d.get("type", ""),
                "spec": d.get("spec", ""),
                "brand": d.get("brand", ""),
                "model": d.get("model", ""),
                "qty": qty,
                "unit": d.get("unit", "台"),
                "price": price,
                "amount": amount,
                "note": d.get("note", ""),
            })
        total = round(total, 2)
        q = Quotation(
            project_id=context.project_id,
            total_amount=total,
            items_json=json.dumps(items, ensure_ascii=False),
            file_path=context.files.get("excel", ""),
            status="draft",
        )
        context.session.add(q)
        context.session.flush()
        context.outputs[self.name] = {
            "quotation_id": q.id,
            "total_amount": total,
            "item_count": len(items),
            "pending_quote": pending,
        }

    async def validate(self, context) -> bool:
        out = context.outputs.get(self.name)
        return bool(out and out.get("quotation_id"))


register(QuotationAgent.name, QuotationAgent)
