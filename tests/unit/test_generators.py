import pytest
from docx import Document

from app.generators.word_generator import fill_docx_template


def _make_template(path):
    doc = Document()
    doc.add_paragraph("项目名称：{{项目名称}}")
    doc.add_paragraph("{{方案正文}}")
    doc.save(path)


def test_fill_docx_template(tmp_path):
    tpl = tmp_path / "tpl.docx"
    _make_template(tpl)
    out = tmp_path / "out.docx"
    fill_docx_template(str(tpl), {"项目名称": "100平会议室", "方案正文": "正文内容"}, str(out))
    doc = Document(str(out))
    texts = [p.text for p in doc.paragraphs]
    assert any("100平会议室" in t for t in texts)
    assert any("正文内容" in t for t in texts)
    assert not any("{{" in t for t in texts)
