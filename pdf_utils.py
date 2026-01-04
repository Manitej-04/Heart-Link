from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from datetime import datetime
import os

def generate_pdf(row, probability, risk, filename):
    os.makedirs("reports", exist_ok=True)
    file_path = os.path.join("reports", filename)

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>Heart Disease Risk Assessment Report</b>", styles["Title"]))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    elements.append(Paragraph("<br/>", styles["Normal"]))

    # -------- Patient Data Table --------
    table_data = [["Parameter", "Value"]]
    for k, v in row.items():
        table_data.append([k, str(v)])

    table = Table(table_data, colWidths=[200, 200])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("FONT", (0,0), (-1,0), "Helvetica-Bold"),
    ]))

    elements.append(Paragraph("<b>Patient Clinical Parameters</b>", styles["Heading2"]))
    elements.append(table)
    elements.append(Paragraph("<br/>", styles["Normal"]))

    # -------- Prediction Result --------
    result_table = Table([
        ["Predicted Risk", risk],
        ["Probability", f"{probability:.3f}"]
    ], colWidths=[200, 200])

    result_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightblue),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("FONT", (0,0), (-1,0), "Helvetica-Bold"),
    ]))

    elements.append(Paragraph("<b>Prediction Result</b>", styles["Heading2"]))
    elements.append(result_table)

    doc.build(elements)
    return file_path