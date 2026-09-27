import sys
import pdfplumber

with open(r"D:\Finance Tracker\.opencode\skills\samples\sample_standard_charter.pdf", "rb") as f:
    pdf = pdfplumber.open(f)
    for page in pdf.pages:
        table_text = page.extract_table({"vertical_strategy": "text", "horizontal_strategy": "text"})
        if table_text:
            for row in table_text[:5]:
                print(row)
