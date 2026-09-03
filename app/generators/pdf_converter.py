import os
import subprocess


def convert_docx_to_pdf(docx_path: str, out_pdf: str) -> bool:
    if not os.path.exists(docx_path):
        return False
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf",
             "--outdir", os.path.dirname(out_pdf), docx_path],
            check=True, capture_output=True, timeout=180,
        )
        return os.path.exists(out_pdf)
    except Exception:
        return False
