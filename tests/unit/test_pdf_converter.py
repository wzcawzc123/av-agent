from app.generators.pdf_converter import convert_docx_to_pdf


def test_missing_input_returns_false(tmp_path):
    assert convert_docx_to_pdf(str(tmp_path / "nope.docx"), str(tmp_path / "out.pdf")) is False
