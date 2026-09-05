"""Debug script to inspect Nabil PDF word positions."""
import pdfplumber
import json
from pathlib import Path

pdf_path = Path(__file__).parent.parent.parent / ".opencode" / "skills" / "samples" / "sample_nabil.pdf"
pdf = pdfplumber.open(str(pdf_path))

for page_num, page in enumerate(pdf.pages):
    print(f"\n=== PAGE {page_num + 1} (w={page.width}, h={page.height}) ===")
    words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=True)
    
    # Show first 80 words with positions
    for w in words[:80]:
        print(f"  x0={w['x0']:7.2f}  x1={w['x1']:7.2f}  top={w['top']:7.2f}  text='{w['text']}'")
    
    if len(words) > 80:
        print(f"  ... ({len(words)} total words on this page)")

pdf.close()
