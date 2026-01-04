# report_utils.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def generate_report(filepath, email, probability, risk, data):
    c = canvas.Canvas(filepath, pagesize=A4)
    c.setFont("Helvetica", 12)

    c.drawString(50, 800, "Heart-Link Medical Prediction Report")
    c.drawString(50, 770, f"Patient Email: {email}")
    c.drawString(50, 740, f"Heart Disease Probability: {probability:.3f}")
    c.drawString(50, 710, f"Risk Category: {risk}")

    y = 670
    for k, v in data.items():
        c.drawString(50, y, f"{k}: {v}")
        y -= 20

    c.save()
