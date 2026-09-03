from openpyxl import Workbook, load_workbook


def generate_deviation_sheet(template_path, items: list[dict], out_path: str) -> str:
    if template_path:
        wb = load_workbook(template_path)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.append(["需求", "状态", "说明"])
    for it in items:
        ws.append([it.get("requirement", ""), it.get("status", "满足"), it.get("note", "")])
    wb.save(out_path)
    return out_path
