"""Test markdown conversion."""
import sys, tempfile
sys.path.insert(0, "backend")
from deerflow.tools.builtins.convert_md_tool import _to_docx, _parse_inline

# Test parsing
items = _parse_inline("**bold** *italic* `code` ~~strike~~ [link](http://ex.com)")
print("Parse test:")
for i, item in enumerate(items):
    t = item.get("text", "")
    f = []
    if item.get("bold"): f.append("B")
    if item.get("italic"): f.append("I")
    if item.get("code"): f.append("C")
    if item.get("strikethrough"): f.append("S")
    tag = ",".join(f) if f else "plain"
    print(f"  [{i}] {t[:25]:25s} {tag}")

# Test DOCX
md = "# **Bold Title**\n## *Italic Section*\n### `code` heading\n\n**Bold** with *italic* and `code` and ~~strike~~.\n\n- **Bold** bullet\n- *Italic* bullet\n\nSee [Google](https://google.com)."
out = tempfile.mktemp(suffix=".docx")
_to_docx(md, out)

from docx import Document
doc = Document(out)
print("\nDOCX output:")
for p in doc.paragraphs:
    style = p.style.name
    parts = []
    for r in p.runs:
        fmt = ""
        if r.bold: fmt += "B"
        if r.italic: fmt += "I"
        if r.font.strike: fmt += "S"
        parts.append(f"[{fmt}]{r.text}")
    if parts:
        print(f"  {style:20s} {''.join(parts)[:80]}")
