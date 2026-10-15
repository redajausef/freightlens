"""Cases reproduced by the ECC architecture, provider and security audit."""

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from test_rules import document

from freightlens.api import create_app
from freightlens.extraction import ExtractionError, KimiExtractor, ground_fields
from freightlens.models import Evidence, Page
from freightlens.repository import Repository
from freightlens.rules import check_documents
from freightlens.service import create_review


@pytest.mark.parametrize(
    "quote",
    [
        "Amount: -2,000.00",
        "Amount: (2,000.00)",
        "Amount: ($2,000.00)",
        "Amount: \u22122,000.00",
        "Amount: -$2,000.00",
    ],
)
def test_negative_source_cannot_support_positive_amount(quote):
    accepted, rejected = ground_fields(
        {"amount": Evidence(value="2000.00", page=1, quote=quote)},
        [Page(number=1, text=quote)],
    )
    assert accepted == {}
    assert rejected == ["amount"]


@pytest.mark.parametrize(
    "field,value,quote",
    [
        ("shipment_reference", "FL-1", "Shipment Reference: FL-10"),
        ("shipment_reference", "FL-1", "Shipment Reference: FL-1-A"),
        ("invoice_number", "INV-1", "Invoice Number: INV-1/2026"),
        ("currency", "USD", "Currency: USDT"),
        ("carrier", "Atlas", "Carrier: AtlasDemo"),
    ],
)
def test_identifier_and_currency_prefixes_do_not_count_as_evidence(field, value, quote):
    accepted, rejected = ground_fields(
        {field: Evidence(value=value, page=1, quote=quote)},
        [Page(number=1, text=quote)],
    )
    assert accepted == {}
    assert rejected == [field]


@pytest.mark.parametrize(
    "quote",
    [
        "Account: 1234567890; Amount: 2,000.00",
        "Tax rate: 1.234; Amount: 2,000.00",
    ],
)
def test_unrelated_invalid_number_does_not_discard_valid_amount(quote):
    accepted, rejected = ground_fields(
        {"amount": Evidence(value="2000.00", page=1, quote=quote)},
        [Page(number=1, text=quote)],
    )
    assert "amount" in accepted
    assert rejected == []


@pytest.mark.parametrize(
    "body",
    [
        {"choices": [None]},
        {"choices": "bad"},
        {"choices": [1]},
        {"choices": [{"finish_reason": "stop", "message": None}]},
    ],
)
def test_malformed_provider_envelope_fails_safely(body):
    extractor = KimiExtractor(
        "test-placeholder",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=body),
        ),
    )
    with pytest.raises(ExtractionError, match="invalid"):
        extractor.extract("invoice", [Page(number=1, text="Invoice Number: INV-1")])


def test_rate_confirmation_cannot_plan_delivery_before_its_own_pickup():
    issues = check_documents(
        [
            document("rate_confirmation", delivery_date="2026-10-11"),
            document("invoice"),
            document("proof_of_delivery"),
        ]
    )
    assert "date_order" in {issue.code for issue in issues}


@pytest.mark.parametrize("value", ["20261012", "2026-W42-1"])
def test_date_fields_require_explicit_calendar_format(value):
    issues = check_documents(
        [
            document("rate_confirmation", pickup_date=value),
            document("invoice"),
            document("proof_of_delivery"),
        ]
    )
    assert "invalid_date" in {issue.code for issue in issues}


def test_actual_delivery_may_be_later_than_the_planned_delivery():
    issues = check_documents(
        [
            document("rate_confirmation", delivery_date="2026-10-13"),
            document("invoice"),
            document("proof_of_delivery", delivery_date="2026-10-14"),
        ]
    )
    assert issues == []


def test_body_limit_applies_to_chunked_multipart_before_endpoint(tmp_path):
    app = create_app(db_path=tmp_path / "limit.db", provider="demo", max_body_bytes=1024)
    body = (
        b'--boundary\r\nContent-Disposition: form-data; name="files"; '
        b'filename="test.txt"\r\nContent-Type: text/plain\r\n\r\n'
        + b"x" * 2048
        + b"\r\n--boundary--\r\n"
    )
    with TestClient(app) as client, patch("freightlens.api.create_review") as process:
        response = client.post(
            "/api/v1/reviews",
            content=iter([body[:600], body[600:]]),
            headers={"Content-Type": "multipart/form-data; boundary=boundary"},
        )
        assert "content-length" not in response.request.headers
        assert response.status_code == 413
        process.assert_not_called()


def test_processing_metadata_is_persisted_and_old_pipeline_is_not_reused(tmp_path):
    root = Path(__file__).resolve().parents[1] / "samples" / "clean"
    uploads = [(p.name, p.stem, p.read_bytes()) for p in sorted(root.glob("*.txt"))]
    repository = Repository(tmp_path / "provenance.db")
    with patch("freightlens.service.PIPELINE_REVISION", "prior-test-policy"):
        old, _ = create_review(repository, uploads, "demo")
    fresh, created = create_review(repository, uploads, "demo")
    assert created and fresh.id != old.id
    assert fresh.processing.provider == "demo"
    assert fresh.processing.model == "parser-v1"
    assert fresh.processing.pipeline_revision != old.processing.pipeline_revision
    restored = repository.get(fresh.id)
    assert restored.processing == fresh.processing


def test_negative_invoice_provider_mistake_blocks_review_end_to_end(tmp_path):
    root = Path(__file__).resolve().parents[1] / "samples" / "clean"
    uploads = [
        (
            p.name,
            p.stem,
            p.read_bytes().replace(b"Amount: 2,000.00", b"Amount: -2,000.00")
            if p.stem == "invoice"
            else p.read_bytes(),
        )
        for p in sorted(root.glob("*.txt"))
    ]
    from freightlens.extraction import DemoExtractor

    class MisreadingExtractor:
        def extract(self, kind, pages):
            result = DemoExtractor().extract(kind, pages)
            if kind == "invoice":
                result.fields["amount"].value = "2000.00"
            return result

    app = create_app(db_path=tmp_path / "sign.db", provider="demo")
    with (
        TestClient(app) as client,
        patch(
            "freightlens.service.make_extractor",
            return_value=MisreadingExtractor(),
        ),
    ):
        response = client.post(
            "/api/v1/reviews",
            files=[("files", (name, content, "text/plain")) for name, _, content in uploads],
            data={"kinds": ",".join(kind for _, kind, _ in uploads)},
        )
        review = response.json()
        assert review["status"] == "needs_review"
        assert "extraction_warning" in {issue["code"] for issue in review["issues"]}
        assert (
            client.post(
                f"/api/v1/reviews/{review['id']}/approval",
                json={
                    "reviewer": "Demo reviewer",
                    "note": "Checked the synthetic documents.",
                },
            ).status_code
            == 409
        )
