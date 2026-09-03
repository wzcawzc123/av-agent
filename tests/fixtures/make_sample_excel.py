from openpyxl import Workbook


def build(path: str):
    wb = Workbook()
    ws = wb.active
    ws.append(["产品名称", "型号", "参数", "底价", "市场价", "分类"])
    ws.append(["8寸音箱", "AV-8A", '{"功率":"80W"}', 800, 1200, "音箱"])
    ws.append(["功放", "PA-400", '{"功率":"400W"}', 1500, 2200, "功放"])
    wb.save(path)


if __name__ == "__main__":
    build("/workspace/av-agent/tests/fixtures/sample_products.xlsx")
