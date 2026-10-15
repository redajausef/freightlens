import pytest

from freightlens.extraction import DemoExtractor, parse_money
from freightlens.models import Document, Evidence, Page
from freightlens.rules import check_documents


def document(kind, **overrides):
    fields = {
        "shipment_reference": "FL-1",
        "carrier": "Atlas Demo",
        "amount": "2000.00",
        "currency": "USD",
        "invoice_number": "INV-1",
        "pickup_date": "2026-10-12",
        "delivery_date": "2026-10-13",
        "delivery_location": "Houston, TX",
    }
    fields.update(overrides)
    return Document(
        id=kind,
        kind=kind,
        filename=f"{kind}.txt",
        sha256="a" * 64,
        pages=[],
        fields={
            key: Evidence(value=value, page=1, quote=f"{key}: {value}")
            for key, value in fields.items()
            if value is not None
        },
    )


def test_clean_packet_and_decimal_equivalence():
    packet = [
        document("rate_confirmation"),
        document("invoice", amount="2,000.00"),
        document("proof_of_delivery"),
    ]
    assert check_documents(packet) == []
    assert parse_money("0.10") + parse_money("0.20") == parse_money("0.30")


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("amount", "2300", "amount_mismatch"),
        ("currency", "CAD", "currency_mismatch"),
        ("currency", "XYZ", "unsupported_currency"),
        ("shipment_reference", "FL-2", "shipment_reference_mismatch"),
        ("carrier", "Different Carrier", "carrier_mismatch"),
        ("delivery_location", "Austin, TX", "delivery_location_mismatch"),
        ("invoice_number", None, "missing_field"),
        ("amount", "-2", "invalid_amount"),
        ("delivery_date", "not a date", "invalid_date"),
    ],
)
def test_document_errors_block_approval(field, value, code):
    issues = check_documents(
        [
            document("rate_confirmation"),
            document("invoice", **{field: value}),
            document("proof_of_delivery"),
        ]
    )
    assert code in {issue.code for issue in issues}


def test_delivery_before_pickup_and_extraction_warnings_are_blocking():
    rate = document("rate_confirmation")
    rate.warnings = ["Discarded unsupported amount."]
    issues = check_documents(
        [rate, document("invoice"), document("proof_of_delivery", delivery_date="2026-10-11")]
    )
    assert {"date_order", "extraction_warning"} <= {issue.code for issue in issues}


@pytest.mark.parametrize("bad", ["-100", "NaN", "1e3", "1.234", "1,00", "$2,000", "1000000000"])
def test_money_does_not_guess_or_accept_nonfinite_values(bad):
    with pytest.raises(ValueError):
        parse_money(bad)


def test_conflicting_repeated_fields_are_omitted_by_demo_parser():
    result = DemoExtractor().extract(
        "invoice",
        [Page(number=1, text=("Amount: 2000.00\nAmount: 2300.00\nInvoice Number: INV-1\n"))],
    )
    assert "amount" not in result.fields
    assert result.fields["invoice_number"].value == "INV-1"


def test_oversized_labeled_values_are_missing_instead_of_crashing():
    result = DemoExtractor().extract("invoice", [Page(number=1, text="Carrier: " + "x" * 301)])
    assert result.fields == {}
