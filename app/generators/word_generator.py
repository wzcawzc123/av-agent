import re

from docx import Document


def fill_docx_template(template_path: str | None, replacements: dict, out_path: str) -> str:
    if template_path:
        doc = Document(template_path)
    else:
        doc = Document()
        doc.add_paragraph("{{项目名称}}")
        doc.add_paragraph("{{项目概述}}")
        doc.add_paragraph("{{方案正文}}")
    pattern = re.compile(r"\{\{\s*(\w+)\s*\}\}")

    for para in doc.paragraphs:
        def _sub(m):
            key = m.group(1)
            return str(replacements.get(key, m.group(0)))

        para.text = pattern.sub(_sub, para.text)
    doc.save(out_path)
    return out_path


async def build_doc_from_llm(provider, slots: dict, devices: list[dict],
                             template_path: str | None, out_path: str) -> str:
    from app.llm.base import ChatMessage
    from app.llm.prompts import DOC_PROMPT

    devices_txt = "\n".join(
        f"- {d['type']} {d.get('spec', '')} × {d['qty']}" for d in devices)
    user_msg = f"项目：{slots}\n设备清单：\n{devices_txt}"
    body = await provider.chat([
        ChatMessage("system", DOC_PROMPT),
        ChatMessage("user", user_msg),
    ], temperature=0.5)
    return fill_docx_template(template_path,
                              {"项目名称": slots.get("scene") or "音视频方案",
                               "方案正文": body}, out_path)
