"""Tool to convert Markdown files to PDF or DOCX using fpdf2 / python-docx.

Resolves sandbox virtual paths properly via Runtime context.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from langchain.tools import InjectedToolCallId, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from deerflow.tools.types import Runtime

logger = logging.getLogger(__name__)

_USER_DATA_PREFIX = "/mnt/user-data/"


@tool("convert_md", parse_docstring=True)
def convert_md_tool(
    runtime: Runtime,
    md_path: str,
    output_format: str = "pdf",
    output_path: str | None = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> Command:
    """Convert a Markdown file to PDF or DOCX.

    The file must exist at the given sandbox path. Converts in-place.
    After conversion, use present_files to deliver the result to the user.

    Args:
        md_path: Absolute /mnt/user-data virtual path to the Markdown file.
        output_format: "pdf" or "docx". Defaults to "pdf".
        output_path: Optional output path. Defaults to same name with .pdf or .docx.

    Returns:
        Status message with the output path or error.
    """
    from deerflow.sandbox.tools import (
        get_thread_data,
        resolve_and_validate_user_data_path,
        validate_local_tool_path,
    )

    thread_data = get_thread_data(runtime)

    try:
        validate_local_tool_path(md_path, thread_data, read_only=True)
        real_md = Path(resolve_and_validate_user_data_path(md_path, thread_data))
    except Exception as e:
        return Command(
            update={"messages": [ToolMessage(f"Error: Cannot resolve path: {e}", tool_call_id=tool_call_id)]},
        )

    if not real_md.exists():
        return Command(
            update={"messages": [ToolMessage(f"Error: File not found at {real_md}", tool_call_id=tool_call_id)]},
        )

    if output_path is None:
        stem = Path(md_path).stem
        parent_virtual = Path(md_path).parent
        output_path = str(parent_virtual / f"{stem}.{output_format}")

    try:
        validate_local_tool_path(output_path, thread_data, read_only=False)
        real_output = Path(resolve_and_validate_user_data_path(output_path, thread_data))
    except Exception as e:
        return Command(
            update={"messages": [ToolMessage(f"Error: Cannot resolve output path: {e}", tool_call_id=tool_call_id)]},
        )

    real_output.parent.mkdir(parents=True, exist_ok=True)

    try:
        content = real_md.read_text(encoding="utf-8")
    except Exception as e:
        return Command(
            update={"messages": [ToolMessage(f"Error reading file: {e}", tool_call_id=tool_call_id)]},
        )

    if output_format == "pdf":
        result = _to_pdf(content, str(real_output))
    elif output_format == "docx":
        result = _to_docx(content, str(real_output))
    else:
        result = f"Unsupported format: {output_format}. Use 'pdf' or 'docx'."

    if result.startswith("OK:"):
        result = result.replace("OK:", f"Done. Saved to {output_path}")

    return Command(
        update={"messages": [ToolMessage(result, tool_call_id=tool_call_id)]},
    )


def _to_pdf(content: str, output_path: str) -> str:
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        for line in content.split("\n"):
            s = line.strip()
            if not s:
                pdf.ln(4)
            elif s == "---" or s == "***":
                pdf.add_page()
            elif s and len(s) >= 3 and all(c == "_" for c in s):
                pdf.add_page()
            elif s == "<!-- pagebreak -->" or s == "<-- pagebreak -->":
                pdf.add_page()
            elif s.startswith("# ") and not s.startswith("## "):
                pdf.set_font("Helvetica", "B", 16)
                pdf.cell(0, 10, s[2:], new_x="LMARGIN", new_y="NEXT")
            elif s.startswith("## ") and not s.startswith("### "):
                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 8, s[3:], new_x="LMARGIN", new_y="NEXT")
            elif s.startswith("### "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 7, s[4:], new_x="LMARGIN", new_y="NEXT")
            elif s.startswith("- ") or s.startswith("* "):
                pdf.set_font("Helvetica", size=11)
                pdf.cell(5)
                pdf.multi_cell(0, 6, s)
            else:
                pdf.set_font("Helvetica", size=11)
                pdf.multi_cell(0, 6, s)

        pdf.output(output_path)
        return f"OK:{output_path}"
    except ImportError:
        return "fpdf2 is not installed. Run: cd backend && uv add fpdf2"
    except Exception as e:
        return f"PDF generation failed: {e}"


def _to_docx(content: str, output_path: str) -> str:
    try:
        from docx import Document

        doc = Document()
        for line in content.split("\n"):
            s = line.strip()
            if s == "---" or s == "***":
                doc.add_page_break()
            elif s and len(s) >= 3 and all(c == "_" for c in s):
                doc.add_page_break()
            elif s == "<!-- pagebreak -->" or s == "<-- pagebreak -->":
                doc.add_page_break()
            elif s.startswith("# ") and not s.startswith("## "):
                doc.add_heading(s[2:], level=1)
            elif s.startswith("## ") and not s.startswith("### "):
                doc.add_heading(s[3:], level=2)
            elif s.startswith("### ") and not s.startswith("#### "):
                doc.add_heading(s[4:], level=3)
            elif s.startswith("#### "):
                doc.add_heading(s[5:], level=4)
            elif s.startswith("##### "):
                doc.add_heading(s[6:], level=5)
            elif s.startswith("###### "):
                doc.add_heading(s[7:], level=6)
            elif s.startswith("- ") or s.startswith("* "):
                doc.add_paragraph(s, style="List Bullet")
            elif s:
                doc.add_paragraph(s)
        doc.save(output_path)
        return f"OK:{output_path}"
    except ImportError:
        return "python-docx is not installed. Run: cd backend && uv add python-docx"
    except Exception as e:
        return f"DOCX generation failed: {e}"
