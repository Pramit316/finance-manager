import pdfplumber
from pathlib import Path

pdf_path = Path(__file__).parent.parent.parent / ".opencode" / "skills" / "samples" / "sample_nabil.pdf"

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        print(page.extract_text())
