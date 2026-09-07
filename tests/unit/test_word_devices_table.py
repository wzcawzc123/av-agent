"""Word 方案参数表测试：方案末尾必须包含数据驱动的设备参数表格。"""

import asyncio

from docx import Document


class _FakeProvider:
    async def chat(self, messages, temperature=0.7):
        return "# 系统设计\n会议室扩声采用专业音箱。\n\n## 扩声系统\n壁挂音箱覆盖全场。"


def _build(tmp_path):
    from app.generators.word_generator import build_doc_from_llm

    devices = [
        {"category": "主设备", "type": "专业音箱", "spec": "8寸 壁挂/吸顶",
         "brand": "MAXHUB", "model": "AV-8A", "qty": 2, "unit": "只", "note": "按覆盖计算"},
        {"category": "主设备", "type": "专业功放", "spec": "2×250W@8Ω",
         "brand": "", "model": "PA-400", "qty": 1, "unit": "台", "note": ""},
        {"category": "配件辅材", "type": "音箱线", "spec": "2×1.5mm²",
         "brand": "", "model": "", "qty": 200, "unit": "米", "note": "按实结算"},
    ]
    out = str(tmp_path / "方案.docx")
    asyncio.run(build_doc_from_llm(
        _FakeProvider(),
        {"area": 100, "scene": "会议室", "budget": "5万", "brand": "惠威"},
        devices, None, out,
    ))
    return out


def test_word_contains_devices_table(tmp_path):
    out = _build(tmp_path)
    doc = Document(out)
    # 存在设备参数表标题
    headings = [p.text for p in doc.paragraphs]
    assert any("设备清单及技术参数" in h for h in headings)
    # 表格存在且含规格/型号
    assert len(doc.tables) >= 1
    table = doc.tables[0]
    header = [c.text for c in table.rows[0].cells]
    assert "规格/参数" in header and "型号" in header and "品牌" in header
    # 行内容包含设备规格与型号（数据驱动，非 LLM 文本）
    cells_text = "\n".join(c.text for row in table.rows for c in row.cells)
    assert "8寸 壁挂/吸顶" in cells_text
    assert "AV-8A" in cells_text
    assert "2×250W@8Ω" in cells_text
    # 配件也入表
    assert "2×1.5mm²" in cells_text


def test_word_placeholder_inserts_table_at_position(tmp_path):
    """模板含 {{设备参数表}} 占位符时，表格插入占位位置而非文档末尾。"""
    from docx import Document as _D

    tpl = tmp_path / "tpl.docx"
    t = _D()
    t.add_paragraph("{{项目名称}}")
    t.add_paragraph("这是正文占位")
    t.add_paragraph("{{设备参数表}}")
    t.add_paragraph("结尾段落")
    t.save(tpl)

    devices = [
        {"type": "专业音箱", "spec": "8寸", "brand": "MAXHUB", "model": "AV-8A",
         "qty": 2, "unit": "只", "note": ""},
    ]
    from app.generators.word_generator import fill_docx_template

    out = str(tmp_path / "out.docx")
    fill_docx_template(str(tpl), {"项目名称": "测试方案", "方案正文": "正文"}, out, devices=devices)
    doc = Document(out)
    texts = [p.text for p in doc.paragraphs]
    # 占位符被表格替换，正文与结尾段落仍在
    assert "测试方案" in texts
    assert "结尾段落" in texts
    assert "{{设备参数表}}" not in texts
    # 表格存在且含设备
    assert len(doc.tables) >= 1
    cells = "\n".join(c.text for row in doc.tables[0].rows for c in row.cells)
    assert "AV-8A" in cells and "8寸" in cells
