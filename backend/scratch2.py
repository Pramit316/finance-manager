import sys
import os
import pdfplumber

with open(r"D:\Finance Tracker\.opencode\skills\samples\sample_standard_charter.pdf", "rb") as f:
    pdf = pdfplumber.open(f)
    for page in pdf.pages:
        table = page.extract_table()
        if table:
            header = table[0]
            normalized = {str(value or "").strip().lower() for value in header}
            print("Found header:", header)
            print("Normalized:", normalized)
            print("Is subset:", {"date", "description", "withdrawal", "deposit", "balance"}.issubset(normalized))
