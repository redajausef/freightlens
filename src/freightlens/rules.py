"""Deterministic business checks. The language model never decides approval."""

import hashlib
import json
import re
from datetime import date

from freightlens.extraction import normalized, parse_money
from freightlens.models import Document, Issue
from freightlens.scope import scope_problem

SUPPORTED_CURRENCIES = {"USD", "CAD", "EUR", "MAD", "GBP"}

REQUIRED = {
    "rate_confirmation": ["shipment_reference", "carrier", "amount", "currency"],
    "invoice": ["shipment_reference", "carrier", "invoice_number", "amount", "currency"],
    "proof_of_delivery": ["shipment_reference", "delivery_date"],
}


def calendar_date(value: str) -> date:
    """Accept ISO or unambiguous slash dates with an explicit four-digit year.

    Keep original evidence values. Never guess day/month order or the century.
    """
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return date.fromisoformat(value)
    match = re.fullmatch(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})", value)
    if not match:
        raise ValueError("Use a four-digit year and an unambiguous date format.")
    first, second, year = map(int, match.groups())
    if first > 12 and second <= 12:
        return date(year, second, first)
    if second > 12 and first <= 12 or first == second:
        return date(year, first, second)
    raise ValueError("The day/month order is ambiguous.")


def check_documents(documents: list[Document]) -> list[Issue]:
    documents = [
        doc.model_copy(
            update={
                "fields": doc.effective_fields,
                "warnings": [
                    warning
                    for warning in doc.warnings
                    if warning
                    not in {
                        f"Discarded unsupported extraction for {field}."
                        for field in doc.confirmations
                    }
                ],
            }
        )
        for doc in documents
    ]
    issues = []

    def flag(code, message, docs=(), field=None):
        identity = json.dumps([code, message, sorted(doc.id for doc in docs), field])
        issues.append(
            Issue(
                id="issue-" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                code=code,
                message=message,
                document_ids=[doc.id for doc in docs],
                field=field,
            )
        )

    by_kind = {doc.kind: doc for doc in documents}
    for kind, fields in REQUIRED.items():
        if kind not in by_kind:
            flag("missing_document", f"Missing {kind.replace('_', ' ')}.")
            continue
        doc = by_kind[kind]
        scope = scope_problem(doc.kind, doc.pages)
        if scope:
            flag("unsupported_document_scope", scope, [doc])
            continue
        for field in fields:
            if field not in doc.fields:
                flag(
                    "missing_field",
                    f"{doc.filename}: missing {field.replace('_', ' ')}.",
                    [doc],
                    field,
                )
        for warning in doc.warnings:
            flag("extraction_warning", f"{doc.filename}: {warning}", [doc])
        for field in ("pickup_date", "delivery_date"):
            if field in doc.fields:
                try:
                    calendar_date(doc.fields[field].value)
                except ValueError:
                    flag(
                        "invalid_date",
                        f"{doc.filename}: confirm {field.replace('_', ' ')} with a full year "
                        "and explicit day/month order. The printed format needs clarification.",
                        [doc],
                        field,
                    )
        if all(field in doc.fields for field in ("pickup_date", "delivery_date")):
            try:
                if calendar_date(doc.fields["delivery_date"].value) < calendar_date(
                    doc.fields["pickup_date"].value,
                ):
                    flag(
                        "date_order",
                        f"{doc.filename}: delivery precedes its pickup date.",
                        [doc],
                        "delivery_date",
                    )
            except ValueError:
                pass  # Invalid dates have already been flagged above.
        if "currency" in doc.fields:
            currency = doc.fields["currency"].value
            if currency not in SUPPORTED_CURRENCIES:
                flag(
                    "unsupported_currency",
                    f"{doc.filename}: unsupported currency {currency}.",
                    [doc],
                    "currency",
                )
        if "amount" in doc.fields:
            try:
                parse_money(doc.fields["amount"].value)
            except ValueError:
                flag(
                    "invalid_amount",
                    f"{doc.filename}: amount needs manual review.",
                    [doc],
                    "amount",
                )

    documents = [doc for doc in documents if not scope_problem(doc.kind, doc.pages)]
    by_kind = {doc.kind: doc for doc in documents}
    for field in ("shipment_reference", "carrier", "pickup_location", "delivery_location"):
        present = [doc for doc in documents if field in doc.fields]
        if len({normalized(doc.fields[field].value) for doc in present}) > 1:
            flag(
                f"{field}_mismatch",
                f"Documents disagree on {field.replace('_', ' ')}.",
                present,
                field,
            )

    rate, invoice = by_kind.get("rate_confirmation"), by_kind.get("invoice")
    if rate and invoice and all("currency" in doc.fields for doc in [rate, invoice]):
        if rate.fields["currency"].value != invoice.fields["currency"].value:
            flag(
                "currency_mismatch",
                "Rate confirmation and invoice use different currencies.",
                [rate, invoice],
                "currency",
            )
        elif all("amount" in doc.fields for doc in [rate, invoice]):
            try:
                expected, actual = [
                    parse_money(doc.fields["amount"].value) for doc in [rate, invoice]
                ]
                if expected != actual:
                    currency = rate.fields["currency"].value
                    flag(
                        "amount_mismatch",
                        f"Agreed {currency} {expected:,.2f}; invoiced {currency} {actual:,.2f}. "
                        f"Difference: {currency} {actual - expected:+,.2f}.",
                        [rate, invoice],
                        "amount",
                    )
            except ValueError:
                pass  # Already flagged above; never compare invalid monetary values.

    pickup = rate.fields.get("pickup_date") if rate else None
    pod = by_kind.get("proof_of_delivery")
    delivery = pod.fields.get("delivery_date") if pod else None
    if pickup and delivery:
        try:
            if calendar_date(delivery.value) < calendar_date(pickup.value):
                flag(
                    "date_order",
                    "Delivery date precedes pickup date.",
                    [rate, pod],
                    "delivery_date",
                )
        except ValueError:
            pass
    return issues


def draft_email(documents: list[Document], issues: list[Issue]) -> str:
    reference = next(
        (
            doc.fields["shipment_reference"].value
            for doc in documents
            if "shipment_reference" in doc.fields
        ),
        "reference not confirmed",
    )
    if not issues:
        return (
            f"Subject: Shipment {reference} — document review\n\n"
            "The configured document checks found no discrepancies. "
            "Please review the source documents before approving the record.\n\n"
            "Draft only — prepared for employee review."
        )
    return (
        f"Subject: Shipment {reference} — document clarification requested\n\n"
        "Hello,\n\nPlease clarify the following items or provide corrected documents:\n\n"
        + "\n".join(f"- {issue.message}" for issue in issues)
        + "\n\nThank you.\n\nDraft only — review before sending."
    )
