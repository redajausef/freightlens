"""Validate explicit employee interpretations without rewriting AI/source evidence."""

import re

from freightlens.extraction import normalized
from freightlens.models import Document, Evidence, FieldConfirmation
from freightlens.rules import SUPPORTED_CURRENCIES, calendar_date
from freightlens.scope import scope_problem


def validate_confirmation(document: Document, request: FieldConfirmation) -> Evidence:
    if scope_problem(document.kind, document.pages):
        raise ValueError("Upload a standalone invoice before confirming fields in this document.")
    source = next((page.text for page in document.pages if page.number == request.page), None)
    quote = request.quote.strip()
    value = request.value.strip()
    if source is None or normalized(quote) not in normalized(source):
        raise ValueError("The supporting quote must exist on the selected source page.")
    if request.field == "currency":
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("Select a supported explicit currency code.")
        codes = {code for code in SUPPORTED_CURRENCIES if re.search(rf"\b{code}\b", quote)}
        symbols = {"USD": "$", "CAD": "$", "EUR": "€", "GBP": "£"}
        if codes:
            supported = value in codes
        else:
            symbol = symbols.get(value)
            supported = bool(symbol and symbol in quote and re.search(r"[0-9]", quote))
        if not supported:
            raise ValueError("The source quote does not support that currency or its symbol.")
    else:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("Confirm dates as YYYY-MM-DD, including the full year.")
        expected = calendar_date(value)
        supported = bool(re.search(rf"(?<![\d-]){re.escape(value)}(?![\d-])", quote))
        for match in re.finditer(
            r"(?<![\d/])([0-9]{1,2})/([0-9]{1,2})/([0-9]{4}|[0-9]{2})(?![\d/])",
            quote,
        ):
            first, second = int(match[1]), int(match[2])
            year_matches = (
                expected.year == int(match[3])
                if len(match[3]) == 4
                else expected.year % 100 == int(match[3])
            )
            supported |= year_matches and (expected.month, expected.day) in {
                (first, second),
                (second, first),
            }
        if not supported:
            raise ValueError("The confirmed date must match a printed date in the source quote.")
    return Evidence(value=value, page=request.page, quote=quote)
