"""Fix page break handling and underscore line detection."""
import sys
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "backend" / "packages" / "harness" / "deerflow" / "tools" / "builtins" / "convert_md_tool.py"
content = path.read_text(encoding="utf-8")

# Fix docx: remove double page break, fix underscore detection
content = content.replace(
    'if s == "---" or s == "***" or s == "___":\n                doc.add_page_break()\n                doc.add_page_break()',
    'if s == "---" or s == "***":\n                doc.add_page_break()\n            elif s and len(s) >= 3 and all(c == "_" for c in s):\n                doc.add_page_break()'
)

# Fix pdf: add *** and underscore detection
content = content.replace(
    'elif s == "---" and len(s) == 3:\n                pdf.add_page()',
    'elif s == "---" or s == "***":\n                pdf.add_page()\n            elif s and len(s) >= 3 and all(c == "_" for c in s):\n                pdf.add_page()'
)

path.write_text(content, encoding="utf-8")
print("Fixed.")
print(f"  PDF: now handles ---, ***, and ____ lines")
print(f"  DOCX: now handles ---, ***, and ____ lines (no double page break)")
