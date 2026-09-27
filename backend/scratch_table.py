import sys
import pdfplumber

with open(r"D:\Finance Tracker\.opencode\skills\samples\sample_standard_charter.pdf", "rb") as f:
    pdf = pdfplumber.open(f)
    for page in pdf.pages:
        # Default extract_table
        table = page.extract_table()
        print("Default rows:", len(table) if table else 0)
        
        # Text-based strategy
        table_text = page.extract_table({"vertical_strategy": "text", "horizontal_strategy": "text"})
        print("Text-based rows:", len(table_text) if table_text else 0)
