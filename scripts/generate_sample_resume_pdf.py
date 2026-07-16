"""Generate a test PDF resume from a UTF-8 text file. Uses reportlab on demand via `uv run --with reportlab`."""
from pathlib import Path
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# Register a CJK-capable font shipped with reportlab (no external font files needed).
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def main(txt_path: str, pdf_path: str) -> None:
    src = Path(txt_path).read_text(encoding="utf-8")
    out = Path(pdf_path)

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="张伟明 - 简历",
    )

    base = getSampleStyleSheet()["BodyText"]
    body = ParagraphStyle(
        "body",
        parent=base,
        fontName="STSong-Light",
        fontSize=10,
        leading=15,
        spaceAfter=2,
    )
    title = ParagraphStyle(
        "title",
        parent=body,
        fontSize=18,
        leading=22,
        alignment=1,  # center
        spaceAfter=6,
    )
    subtitle = ParagraphStyle(
        "subtitle",
        parent=body,
        fontSize=12,
        leading=16,
        alignment=1,
        spaceAfter=10,
    )
    h2 = ParagraphStyle(
        "h2",
        parent=body,
        fontSize=12,
        leading=16,
        spaceBefore=8,
        spaceAfter=4,
        textColor="#1f4e79",
    )

    flow = []
    for i, line in enumerate(src.splitlines()):
        line = line.rstrip()
        if not line.strip():
            flow.append(Spacer(1, 4))
            continue
        if i == 0:
            flow.append(Paragraph(line, title))
        elif i == 1:
            flow.append(Paragraph(line, subtitle))
        elif line.startswith("=====") and line.endswith("====="):
            clean = line.replace("=", "").strip()
            flow.append(Paragraph(clean, h2))
        else:
            flow.append(Paragraph(line.replace(" ", "&nbsp;"), body))

    doc.build(flow)
    print(f"wrote {out} ({out.stat().st_size} bytes, {out.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    txt = sys.argv[1] if len(sys.argv) > 1 else "scripts/sample_resume.txt"
    pdf = sys.argv[2] if len(sys.argv) > 2 else ".uploads/zhangweiming_resume.pdf"
    main(txt, pdf)