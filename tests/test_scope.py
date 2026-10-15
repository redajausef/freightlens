from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from freightlens.api import create_app
from freightlens.models import Page
from freightlens.scope import scope_problem


@pytest.mark.parametrize(
    "cover",
    [
        "Understanding Your\nFedEx Invoice",
        "Invoice explanation",
        "A guide to invoices",
        "How to understand your invoice",
    ],
)
def test_guide_covers_are_rejected_as_single_invoices(cover):
    assert scope_problem("invoice", [Page(number=1, text=cover)])


@pytest.mark.parametrize("label", ["Invoice Number:", "Invoice No.:", "Invoice #"])
def test_distinct_labeled_invoice_ids_are_a_bundle(label):
    assert scope_problem("invoice", [Page(number=1, text=f"{label} INV-1\n{label} INV-2")])


def test_repeated_single_invoice_and_help_link_are_not_a_bundle():
    pages = [
        Page(number=1, text="Invoice Number: INV-1\nRead our invoice guide for help."),
        Page(number=2, text="Invoice Number: INV-1\nContinued charges"),
    ]
    assert scope_problem("invoice", pages) is None
    assert scope_problem("rate_confirmation", [Page(number=1, text="Invoice guide")]) is None
    assert scope_problem("invoice", []) is None


def test_unsupported_scope_skips_provider_and_cannot_be_confirmed(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with TestClient(create_app(db_path=tmp_path / "scope.db", provider="gemini")) as client:
        with patch("freightlens.service.make_extractor") as extractor:
            response = client.post(
                "/api/v1/reviews",
                files={"files": ("guide.txt", b"Understanding Your Freight Invoice")},
                data={"kinds": "invoice"},
            )
            assert response.status_code == 201
            extractor.assert_not_called()
        review = response.json()
        assert review["documents"][0]["fields"] == {}
        assert review["documents"][0]["extraction_status"] == "skipped_scope"
        assert "unsupported_document_scope" in {issue["code"] for issue in review["issues"]}
        url = f"/api/v1/reviews/{review['id']}"
        assert (
            client.post(
                url + "/confirmations",
                json={
                    "document_id": review["documents"][0]["id"],
                    "field": "currency",
                    "value": "USD",
                    "page": 1,
                    "quote": "Understanding Your Freight Invoice",
                    "reviewer": "Test",
                    "note": "Trying to confirm a guide.",
                    "expected_revision": 0,
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                url + "/approval", json={"reviewer": "Test", "note": "Checked."}
            ).status_code
            == 409
        )
