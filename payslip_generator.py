"""
payslip_generator.py
Generates a professional PDF payslip for one employee row.
Used by both the dashboard (bulk) and guard portal (individual).
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

NAVY  = colors.HexColor("#001f3f")
BLUE  = colors.HexColor("#0074D9")
LIGHT = colors.HexColor("#E8F0FE")
WHITE = colors.white
GRAY  = colors.HexColor("#f5f5f5")

def fmt(val):
    """Format a number as Philippine peso string."""
    try:
        return f"₱ {float(val):,.2f}"
    except:
        return "₱ 0.00"

def generate_payslip_pdf(row: dict, logo_path: str = None) -> bytes:
    """
    Generate a single payslip PDF for one employee.
    row: dict with keys matching the Excel columns
    Returns: PDF as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=12*mm,
        bottomMargin=12*mm
    )

    styles = {
        "agency": ParagraphStyle("agency", fontSize=14, fontName="Helvetica-Bold",
                                  textColor=WHITE, alignment=TA_CENTER, leading=18),
        "sub":    ParagraphStyle("sub",    fontSize=8,  fontName="Helvetica",
                                  textColor=LIGHT, alignment=TA_CENTER, leading=11),
        "title":  ParagraphStyle("title",  fontSize=11, fontName="Helvetica-Bold",
                                  textColor=NAVY, alignment=TA_CENTER, leading=14),
        "label":  ParagraphStyle("label",  fontSize=9,  fontName="Helvetica-Bold",
                                  textColor=NAVY),
        "value":  ParagraphStyle("value",  fontSize=9,  fontName="Helvetica",
                                  textColor=colors.black),
        "footer": ParagraphStyle("footer", fontSize=7,  fontName="Helvetica",
                                  textColor=colors.gray, alignment=TA_CENTER),
        "section":ParagraphStyle("section",fontSize=9,  fontName="Helvetica-Bold",
                                  textColor=WHITE),
        "net":    ParagraphStyle("net",    fontSize=14, fontName="Helvetica-Bold",
                                  textColor=WHITE, alignment=TA_CENTER),
        "netlbl": ParagraphStyle("netlbl", fontSize=8,  fontName="Helvetica",
                                  textColor=LIGHT, alignment=TA_CENTER),
    }

    story = []

    # ── HEADER BANNER ──────────────────────────────────────────────────────────
    header_data = [[
        Paragraph("JA.PREMIER SECURITY AGENCY", styles["agency"]),
    ]]
    header_table = Table(header_data, colWidths=[180*mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(header_table)

    sub_data = [[Paragraph("EMPLOYEE PAYSLIP", styles["sub"])]]
    sub_table = Table(sub_data, colWidths=[180*mm])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLUE),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(sub_table)
    story.append(Spacer(1, 6*mm))

    # ── EMPLOYEE INFO ──────────────────────────────────────────────────────────
    info_data = [
        [Paragraph("Employee ID:",    styles["label"]), Paragraph(str(row.get("Employee ID",   "")), styles["value"]),
         Paragraph("Date Covered:",   styles["label"]), Paragraph(str(row.get("Date Covered",  "")), styles["value"])],
        [Paragraph("Employee Name:",  styles["label"]), Paragraph(str(row.get("Employee Name", "")), styles["value"]),
         Paragraph("Designation:",    styles["label"]), Paragraph(str(row.get("Designation",   "")), styles["value"])],
        [Paragraph("Post Assignment:",styles["label"]), Paragraph(str(row.get("Post Assignment","")),styles["value"]),
         Paragraph("No. of Days:",    styles["label"]), Paragraph(str(row.get("No. of Days",   "")), styles["value"])],
    ]
    info_table = Table(info_data, colWidths=[38*mm, 52*mm, 38*mm, 52*mm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), GRAY),
        ("GRID",       (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5*mm))

    # ── EARNINGS & DEDUCTIONS SIDE BY SIDE ────────────────────────────────────
    def section_header(text):
        t = Table([[Paragraph(text, styles["section"])]], colWidths=[86*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), NAVY),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]))
        return t

    def detail_row(label, val, shade=False):
        bg = colors.HexColor("#f0f4ff") if shade else WHITE
        return [label, fmt(val), bg]

    earnings = [
        detail_row("Daily Rate",          row.get("Daily Rate", 0),          False),
        detail_row("Basic Salary",         row.get("Basic Salary", 0),        True),
        detail_row("Holiday Pay",          row.get("Holiday", 0),             False),
        detail_row("Overtime Pay",         row.get("Overtime pay", 0),        True),
        detail_row("Night Differential",   row.get("Night Differential", 0),  False),
        detail_row("5-Day Incentives",     row.get("5 days Incentives", 0),   True),
        detail_row("Uniform Allowance",    row.get("Uniform Allowance", 0),   False),
    ]

    deductions = [
        detail_row("SSS",                  row.get("SSS", 0),                 False),
        detail_row("Pag-Ibig",             row.get("Pag-Ibig", 0),            True),
        detail_row("PhilHealth",           row.get("PhilHealth", 0),          False),
        detail_row("Loans",                row.get("Loans", 0),               True),
        detail_row("FA Bonds",             row.get("FA Bonds", 0),            False),
        detail_row("Cash Advance",         row.get("Cash Advance", 0),        True),
        detail_row("",                     0,                                  False),  # spacer row
    ]

    def build_detail_table(rows):
        data  = [[r[0], r[1]] for r in rows]
        bgs   = [r[2] for r in rows]
        t = Table(data, colWidths=[52*mm, 34*mm])
        style_cmds = [
            ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
            ("FONTSIZE",  (0,0), (-1,-1), 9),
            ("FONTNAME",  (0,0), (0,-1),  "Helvetica"),
            ("TEXTCOLOR", (0,0), (0,-1),  colors.HexColor("#444444")),
            ("ALIGN",     (1,0), (1,-1),  "RIGHT"),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (0,-1),  8),
            ("RIGHTPADDING",  (1,0), (1,-1),  8),
            ("LINEBELOW", (0,-1), (-1,-1), 0.5, colors.lightgrey),
        ]
        for i, bg in enumerate(bgs):
            style_cmds.append(("BACKGROUND", (0,i), (-1,i), bg))
        t.setStyle(TableStyle(style_cmds))
        return t

    earn_header = section_header("EARNINGS")
    dedu_header = section_header("DEDUCTIONS")
    earn_detail = build_detail_table(earnings)
    dedu_detail = build_detail_table(deductions)

    # Gross total row
    gross_data = [["GROSS PAY", fmt(row.get("Gross Pay", 0))]]
    gross_table = Table(gross_data, colWidths=[52*mm, 34*mm])
    gross_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), LIGHT),
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (-1,-1), NAVY),
        ("ALIGN",     (1,0), (1,0),   "RIGHT"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (0,0),   8),
        ("RIGHTPADDING",  (1,0), (1,0),   8),
    ]))

    # Total deduction row
    totded_data = [["TOTAL DEDUCTION", fmt(row.get("Total Deduction", 0))]]
    totded_table = Table(totded_data, colWidths=[52*mm, 34*mm])
    totded_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#fff0f0")),
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.HexColor("#cc0000")),
        ("ALIGN",     (1,0), (1,0),   "RIGHT"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (0,0),   8),
        ("RIGHTPADDING",  (1,0), (1,0),   8),
    ]))

    side_by_side = Table([
        [earn_header,  dedu_header],
        [earn_detail,  dedu_detail],
        [gross_table,  totded_table],
    ], colWidths=[86*mm, 86*mm], spaceBefore=0, spaceAfter=0)
    side_by_side.setStyle(TableStyle([
        ("VALIGN",  (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 2),
        ("RIGHTPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(side_by_side)
    story.append(Spacer(1, 5*mm))

    # ── NET PAY BANNER ─────────────────────────────────────────────────────────
    net_data = [
        [Paragraph("NET PAY", styles["netlbl"])],
        [Paragraph(fmt(row.get("NET PAY", 0)), styles["net"])],
    ]
    net_table = Table(net_data, colWidths=[180*mm])
    net_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(net_table)
    story.append(Spacer(1, 10*mm))

    # ── SIGNATURE LINES ────────────────────────────────────────────────────────
    sig_data = [[
        "_______________________\nEmployee Signature",
        "_______________________\nPrepared by",
        "_______________________\nApproved by",
    ]]
    sig_table = Table(sig_data, colWidths=[60*mm, 60*mm, 60*mm])
    sig_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 8),
        ("ALIGN",     (0,0), (-1,-1), "CENTER"),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.gray),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 6*mm))

    # ── FOOTER ─────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "This is a system-generated payslip. For questions contact JA.PREMIER SECURITY AGENCY administration.",
        styles["footer"]
    ))

    doc.build(story)
    return buffer.getvalue()


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = {
        "Employee ID": "2024-001",
        "Employee Name": "Juan Dela Cruz",
        "Designation": "Security Guard",
        "Post Assignment": "SM City Naga",
        "Date Covered": "June 1-15, 2026",
        "No. of Days": 13,
        "Daily Rate": 650.00,
        "Basic Salary": 8450.00,
        "Holiday": 650.00,
        "Overtime pay": 320.00,
        "Night Differential": 150.00,
        "5 days Incentives": 500.00,
        "Uniform Allowance": 200.00,
        "Gross Pay": 10270.00,
        "SSS": 450.00,
        "Pag-Ibig": 100.00,
        "PhilHealth": 275.00,
        "Loans": 500.00,
        "FA Bonds": 100.00,
        "Cash Advance": 1000.00,
        "Total Deduction": 2425.00,
        "NET PAY": 7845.00,
    }
    pdf_bytes = generate_payslip_pdf(sample)
    with open("/mnt/user-data/outputs/sample_payslip.pdf", "wb") as f:
        f.write(pdf_bytes)
    print(f"PDF generated: {len(pdf_bytes)} bytes")
