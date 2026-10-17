"""Server-side PDF receipt (reportlab, standard Helvetica, uncompressed text)."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

MAX_LINE = 90


def format_pkr(minor: int) -> str:
    """450000 -> 'PKR 4500.00' (major units, two decimals, no thousands separator)."""
    sign = "-" if minor < 0 else ""
    minor = abs(int(minor))
    return f"{sign}PKR {minor // 100}.{minor % 100:02d}"


def _safe(text: str) -> str:
    # Standard Type 1 fonts only cover WinAnsi; never let user data break rendering.
    cleaned = "".join(ch if ch >= " " else "?" for ch in str(text))
    return cleaned.encode("cp1252", errors="replace").decode("cp1252")


def _chunks(text: str) -> list[str]:
    return [text[i : i + MAX_LINE] for i in range(0, len(text), MAX_LINE)] or [""]


def build_receipt_pdf(payload: dict[str, Any]) -> bytes:
    lines: list[str] = [
        "Receipt",
        f"Order: {payload['order_id']}",
        f"Customer: {payload['customer_id']}",
        f"Paid at: {payload.get('paid_at', '')}",
        "",
        "Items:",
    ]
    for item in payload["items"]:
        unit = int(item["unit_price_minor"])
        qty = int(item["quantity"])
        lines.append(
            f"{item['variant_id']} x {qty} @ {format_pkr(unit)} = {format_pkr(unit * qty)}"
        )
    lines += [
        "",
        f"Subtotal: {format_pkr(payload['subtotal_minor'])}",
        f"Discount: {format_pkr(payload['discount_minor'])}",
        f"Total: {format_pkr(payload['total_minor'])}",
    ]

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=0)
    pdf.setTitle(f"Receipt {_safe(payload['order_id'])}")
    width, height = A4
    y = height - 60
    first = True
    for line in lines:
        for chunk in _chunks(_safe(line)):
            if y < 50:
                pdf.showPage()
                y = height - 60
            pdf.setFont("Helvetica-Bold" if first else "Helvetica", 16 if first else 11)
            pdf.drawString(50, y, chunk)
            y -= 26 if first else 16
            first = False
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
