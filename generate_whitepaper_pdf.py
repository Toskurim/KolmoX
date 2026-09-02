import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        
        # Header (pagine successive alla prima)
        if self._pageNumber > 1:
            self.drawString(54, 11 * 72 - 36, "KolmoX Technical Whitepaper — KMX2 Architecture Spec")
            self.drawRightString(8.5 * 72 - 54, 11 * 72 - 36, "August 2026")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 11 * 72 - 42, 8.5 * 72 - 54, 11 * 72 - 42)

        # Footer
        self.drawString(54, 36, "Confidential & Open-Source Research — KolmoX Project")
        self.drawRightString(8.5 * 72 - 54, 36, f"Page {self._pageNumber} of {page_count}")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 46, 8.5 * 72 - 54, 46)
        self.restoreState()

def build_pdf(md_path, pdf_path):
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#2563EB"),
        spaceAfter=12
    )
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=14
    )
    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6
    )
    table_cell = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#1E293B")
    )
    table_cell_hdr = ParagraphStyle(
        'CellHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=9,
        textColor=colors.white
    )
    code_style = ParagraphStyle(
        'CodeBlock',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor("#0F172A"),
        leftIndent=10
    )

    story = []
    in_code = False
    code_lines = []
    in_table = False
    table_data = []

    for line in lines:
        raw = line.rstrip("\r\n")

        # Code block
        if raw.startswith("```"):
            if in_code:
                code_text = "<br/>".join(code_lines).replace(" ", "&nbsp;")
                story.append(Paragraph(code_text, code_style))
                story.append(Spacer(1, 6))
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            sanitized = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            code_lines.append(sanitized)
            continue

        # Markdown Tables
        if raw.startswith("|") and raw.endswith("|"):
            if "---" in raw:
                continue
            cells = [c.strip() for c in raw.split("|")[1:-1]]
            if not in_table:
                in_table = True
                table_data = []
            table_data.append(cells)
            continue
        elif in_table:
            # Finalizza tabella
            t_rows = []
            for r_idx, row in enumerate(table_data):
                fmt_row = []
                for cell in row:
                    clean_cell = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", cell)
                    clean_cell = re.sub(r"\*(.*?)\*", r"<i>\1</i>", clean_cell)
                    st = table_cell_hdr if r_idx == 0 else table_cell
                    fmt_row.append(Paragraph(clean_cell, st))
                t_rows.append(fmt_row)

            # Tabella 6 colonne
            col_widths = [110, 140, 55, 60, 65, 74]
            t = Table(t_rows, colWidths=col_widths, repeatRows=1)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(Spacer(1, 4))
            story.append(t)
            story.append(Spacer(1, 8))
            in_table = False
            table_data = []

        if not raw.strip():
            continue

        # Metadata & Titles
        if raw.startswith("# "):
            story.append(Paragraph(raw[2:].strip(), title_style))
        elif raw.startswith("**") and raw.endswith("**") and len(story) < 3:
            story.append(Paragraph(raw.replace("**", "").strip(), subtitle_style))
        elif raw.startswith("*Author:*") or raw.startswith("*Date:*") or raw.startswith("*Specification:*"):
            clean_m = raw.replace("*", "").strip()
            story.append(Paragraph(clean_m, meta_style))
        elif raw.startswith("## "):
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceAfter=8))
            story.append(Paragraph(raw[3:].strip(), h1_style))
        elif raw.startswith("### "):
            story.append(Paragraph(raw[4:].strip(), h2_style))
        elif raw.startswith("> "):
            clean_b = raw[2:].strip()
            clean_b = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", clean_b)
            clean_b = re.sub(r"\*(.*?)\*", r"<i>\1</i>", clean_b)
            p_note = Paragraph(f"<i>{clean_b}</i>", body_style)
            story.append(p_note)
        else:
            fmt = raw
            fmt = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", fmt)
            fmt = re.sub(r"\*(.*?)\*", r"<i>\1</i>", fmt)
            # LaTeX cleanup for basic PDF rendering
            fmt = fmt.replace("$$", "").replace("$", "")
            story.append(Paragraph(fmt, body_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Whitepaper PDF generato con successo: {pdf_path}")

build_pdf("docs/WHITEPAPER.md", "docs/KolmoX_Technical_Paper_v1.1.0_Complete_EN.pdf")
