"""Create explicitly synthetic text/PDF packets; no real business data."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
PACKETS = {
    "clean": ("FL-1001", "2,000.00", True),
    "mismatch": ("FL-1002", "2,300.00", True),
    "missing": ("FL-1003", "2,000.00", False),
}


def main():
    for scenario, (reference, invoiced, has_pod) in PACKETS.items():
        shared = (
            f"Shipment Reference: {reference}\nCarrier: Atlas Demo Transport\n"
            "Pickup Location: Dallas, TX\nDelivery Location: Houston, TX\n"
        )
        documents = {
            "rate_confirmation": (
                "RATE CONFIRMATION\n" + shared + "Pickup Date: 2026-10-12\n"
                "Delivery Date: 2026-10-13\nAmount: 2,000.00\nCurrency: USD\n"
            ),
            "invoice": (
                "CARRIER INVOICE\n" + shared + f"Invoice Number: INV-{reference}\n"
                f"Amount: {invoiced}\nCurrency: USD\n"
            ),
        }
        if has_pod:
            documents["proof_of_delivery"] = (
                "PROOF OF DELIVERY\n" + shared + "Delivery Date: 2026-10-13\n"
                "Receiver: Demo Warehouse Employee\n"
                "Signature: SAMPLE ONLY - NOT A REAL SIGNATURE\n"
            )
        for kind, body in documents.items():
            text = "SYNTHETIC PORTFOLIO EXAMPLE - NO REAL SHIPMENT\n\n" + body
            sample = ROOT / "samples" / scenario
            static = ROOT / "src" / "freightlens" / "static" / "samples" / scenario
            sample.mkdir(parents=True, exist_ok=True)
            static.mkdir(parents=True, exist_ok=True)
            (sample / f"{kind}.txt").write_text(text, encoding="utf-8")
            (static / f"{kind}.txt").write_text(text, encoding="utf-8")
            pdf = canvas.Canvas(str(sample / f"{kind}.pdf"), pagesize=A4)
            pdf.setTitle(f"Synthetic {kind.replace('_', ' ')} - {reference}")
            pdf.setFillColor(colors.HexColor("#152d3a"))
            pdf.rect(0, 765, A4[0], 80, fill=1, stroke=0)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 22)
            pdf.drawString(45, 800, "FreightLens / Sample documents")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(45, 780, "Synthetic portfolio example. No real shipment or company.")
            pdf.setFillColor(colors.HexColor("#192f3b"))
            y = 720
            for line in body.splitlines():
                pdf.setFont("Helvetica-Bold" if ":" not in line else "Helvetica", 12)
                pdf.drawString(45, y, line)
                y -= 28
            pdf.setFont("Helvetica", 9)
            pdf.setFillColor(colors.grey)
            pdf.drawString(45, 45, "SAMPLE ONLY | For extraction and validation tests | Page 1")
            pdf.save()
    print("Created three synthetic packets (text + PDF) and packaged demo fixtures.")


if __name__ == "__main__":
    main()
