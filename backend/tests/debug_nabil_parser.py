"""Debug script for Nabil parser."""
import pprint
from app.parsers.nabil import NabilStatementParser
from pathlib import Path

pdf_path = Path(__file__).parent.parent.parent / ".opencode" / "skills" / "samples" / "sample_nabil.pdf"

with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

parser = NabilStatementParser()
result = parser.parse(pdf_bytes, "sample_nabil.pdf")

print(f"Transactions parsed: {len(result.transactions)}")
if result.transactions:
    print("\nFirst transaction:")
    pprint.pprint(result.transactions[0].model_dump())
else:
    print("NO TRANSACTIONS PARSED!")

print("\nErrors:")
for e in result.errors:
    print(e)
