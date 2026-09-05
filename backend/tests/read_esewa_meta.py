import xlrd
from pathlib import Path

xls_path = Path(__file__).parent.parent.parent / ".opencode" / "skills" / "samples" / "sample_esewa.xls"

workbook = xlrd.open_workbook(xls_path)
sheet = workbook.sheet_by_name("eSewa Report")
for r in range(15):
    row = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
    print(f"Row {r}: {row}")
