import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from app.parsers.standard_chartered import StandardCharteredStatementParser

parser = StandardCharteredStatementParser()
with open(r"D:\Finance Tracker\.opencode\skills\samples\sample_standard_charter.pdf", "rb") as f:
    pdf_bytes = f.read()

result = parser.parse(pdf_bytes, "sample_standard_charter.pdf")
print("Transactions:", len(result.transactions))
if result.errors:
    print("Errors:", result.errors)
