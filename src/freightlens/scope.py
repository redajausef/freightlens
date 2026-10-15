"""Conservative text checks for unsupported invoice guides and invoice bundles."""

import re

from freightlens.models import DocumentKind, Page


def scope_problem(kind: DocumentKind, pages: list[Page]) -> str | None:
    if kind != "invoice" or not pages:
        return None
    cover = " ".join(pages[0].text.split())
    if (
        len(cover) < 400
        and re.search(r"\binvoices?\b", cover, re.IGNORECASE)
        and re.search(
            r"^(?:a\s+|the\s+)?(?:handy\s+)?(?:"
            r"guide\b.{0,100}\binvoices?\b|understanding\b.{0,100}\binvoices?\b|"
            r"invoices?\s+(?:guide|explanation|explained)\b|"
            r"how\s+to\b.{0,100}\binvoices?\b)",
            cover,
            re.I,
        )
    ):
        return (
            "This upload appears to be an invoice guide, not a single transaction. "
            "Upload the actual standalone invoice. AI extraction was skipped for new uploads."
        )
    invoice_ids = set()
    for page in pages:
        for match in re.finditer(
            r"\binvoice\s*(?:number\b|no\b\.?|#)\s*[:#-]?\s*"
            r"([a-z0-9][a-z0-9/_-]{1,60})(?![a-z0-9/_-])",
            page.text,
            re.IGNORECASE,
        ):
            value = match.group(1).casefold()
            if any(char.isdigit() for char in value):
                invoice_ids.add(value)
    if len(invoice_ids) > 1:
        return (
            "Multiple distinct labeled invoice numbers were detected. "
            "Upload each transaction separately; this review cannot confirm a bundled invoice."
        )
    return None
