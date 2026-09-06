import os

from app.engines.composer import compose_devices
from app.generators.word_generator import build_doc_from_llm
from app.generators.excel_generator import generate_deviation_sheet, build_design_sheet
from app.generators.ppt_generator import build_ppt
from app.generators.pdf_converter import convert_docx_to_pdf
from app.db.template_store import find_config_template, find_doc_template


async def generate_deliverables(cfg: dict, provider, slots: dict, session, progress_cb) -> dict:
    files, errors = {}, {}
    total = len(cfg["deliverables"]) + 1
    done = 0
    progress_cb(int(10 / total * 100), "匹配常规配置模板…")
    tpl = find_config_template(session, slots.get("area") or 0)
    devices = []
    if any(d in cfg["deliverables"] for d in ("doc", "ppt", "excel")):
        progress_cb(int(20 / total * 100), "编排系统设备清单…")
        devices = await compose_devices(provider, slots, session, tpl)
    done += 1
    project_dir = cfg["project_dir"]
    os.makedirs(project_dir, exist_ok=True)
    tpl_paths = dict(cfg.get("template_paths", {}))
    brand_txt = slots.get("brand") or ""
    if not tpl_paths.get("doc"):
        doc_tpl = find_doc_template(session, slots.get("scene") or "", brand_txt, doc_type="doc")
        if doc_tpl:
            tpl_paths["doc"] = doc_tpl.file_path
    if not tpl_paths.get("ppt"):
        ppt_tpl = find_doc_template(session, slots.get("scene") or "", brand_txt, doc_type="ppt")
        if ppt_tpl:
            tpl_paths["ppt"] = ppt_tpl.file_path
    if not tpl_paths.get("deviation"):
        dev_tpl = find_doc_template(session, slots.get("scene") or "", brand_txt, doc_type="deviation")
        if dev_tpl:
            tpl_paths["deviation"] = dev_tpl.file_path
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
                from app.engines.tender.store import build_deviation_rows
                dev_rows = build_deviation_rows(session, cfg.get("project_id") or 0)
                if dev_rows:
                    build_deviation_sheet(out, {}, dev_rows, tpl_paths.get("deviation"))
                else:
                    generate_deviation_sheet(
                        tpl_paths.get("deviation"),
                        [{"requirement": slots.get("scene") or "需求", "status": "满足", "note": ""}],
                        out,
                    )
                files["deviation"] = out
            elif dt == "excel":
                out = os.path.join(project_dir, "设计方案清单.xlsx")
                build_design_sheet(out, {"项目名称": slots.get("scene") or "音视频方案"}, devices,
                                   tpl_paths.get("excel"))
                files["excel"] = out
            elif dt == "ppt":
                out = os.path.join(project_dir, "方案.pptx")
                await build_ppt(provider, slots, devices, tpl_paths.get("ppt"), out)
                files["ppt"] = out
        except Exception as e:
            errors[dt] = str(e)
    progress_cb(100, "完成")
    return {"files": files, "errors": errors, "bom": devices}
