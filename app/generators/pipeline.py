import json
import os

from app.llm.adapt import adapt_template
from app.generators.word_generator import build_doc_from_llm
from app.generators.excel_generator import generate_deviation_sheet
from app.generators.ppt_generator import build_ppt
from app.generators.pdf_converter import convert_docx_to_pdf
from app.db.template_store import find_config_template
from app.db.models import Product


async def generate_deliverables(cfg: dict, provider, slots: dict, session, progress_cb) -> dict:
    files, errors = {}, {}
    total = len(cfg["deliverables"]) + 1
    done = 0
    progress_cb(int(10 / total * 100), "匹配常规配置模板…")
    tpl = find_config_template(session, slots.get("area") or 0)
    products = [
        {"name": p.name, "model": p.model, "low_price": p.low_price,
         "market_price": p.market_price}
        for p in session.query(Product).limit(200)
    ]
    devices = []
    if "doc" in cfg["deliverables"] or "ppt" in cfg["deliverables"]:
        adapted = await adapt_template(provider, slots, tpl, products, session)
        devices = adapted["devices"]
    done += 1
    project_dir = cfg["project_dir"]
    os.makedirs(project_dir, exist_ok=True)
    tpl_paths = cfg.get("template_paths", {})
    for i, dt in enumerate(cfg["deliverables"]):
        progress_cb(int((done + i) / total * 100), f"生成 {dt} …")
        try:
            if dt == "doc":
                out = os.path.join(project_dir, "方案.docx")
                await build_doc_from_llm(provider, slots, devices, tpl_paths.get("doc"), out)
                files["doc"] = out
            elif dt == "pdf":
                src = files.get("doc") or os.path.join(project_dir, "方案.docx")
                out = os.path.join(project_dir, "方案.pdf")
                if convert_docx_to_pdf(src, out):
                    files["pdf"] = out
                else:
                    errors["pdf"] = "PDF 转换失败（需先有 Word，且电脑安装 LibreOffice）"
            elif dt == "deviation":
                out = os.path.join(project_dir, "偏离表.xlsx")
                generate_deviation_sheet(
                    tpl_paths.get("deviation"),
                    [{"requirement": slots.get("scene") or "需求", "status": "满足", "note": ""}],
                    out,
                )
                files["deviation"] = out
            elif dt == "ppt":
                out = os.path.join(project_dir, "方案.pptx")
                await build_ppt(provider, slots, devices, tpl_paths.get("ppt"), out)
                files["ppt"] = out
        except Exception as e:
            errors[dt] = str(e)
    progress_cb(100, "完成")
    return {"files": files, "errors": errors}
