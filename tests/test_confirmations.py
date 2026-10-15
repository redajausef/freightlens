import pytest
from fastapi.testclient import TestClient

from freightlens.api import create_app
from freightlens.repository import Repository
from freightlens.versions import PIPELINE_REVISION


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "confirm.db", provider="demo")) as client:
        yield client


def create_packet(client, *, complete=False, invoice_amount="700.00"):
    rate = (
        "Shipment Reference: TEST-1\nCarrier: Test Carrier\n"
        "Pickup Date: 02/23/24\nDelivery Date: 02/24/24\n"
        "Amount: 700.00\nTotal Carrier Pay $700.00\n"
    )
    files = [("files", ("rate.txt", rate.encode(), "text/plain"))]
    kinds = "rate_confirmation"
    if complete:
        invoice = (
            "Shipment Reference: TEST-1\nCarrier: Test Carrier\nInvoice Number: TEST-I1\n"
            f"Amount: {invoice_amount}\nCurrency: USD\n"
        )
        pod = "Shipment Reference: TEST-1\nDelivery Date: 2024-02-24\n"
        files.extend(
            [
                ("files", ("invoice.txt", invoice.encode(), "text/plain")),
                ("files", ("pod.txt", pod.encode(), "text/plain")),
            ]
        )
        kinds += ",invoice,proof_of_delivery"
    response = client.post("/api/v1/reviews", files=files, data={"kinds": kinds})
    assert response.status_code == 201
    return response.json()


def confirmation_body(review, field="currency", value="USD"):
    quote = {
        "currency": "Total Carrier Pay $700.00",
        "pickup_date": "Pickup Date: 02/23/24",
        "delivery_date": "Delivery Date: 02/24/24",
    }[field]
    return {
        "document_id": review["documents"][0]["id"],
        "field": field,
        "value": value,
        "page": 1,
        "quote": quote,
        "reviewer": "Test reviewer",
        "note": "Verified interpretation for this test against the original source.",
        "expected_revision": review["revision"],
    }


def confirm_all(client, review):
    for field, value in [
        ("currency", "USD"),
        ("pickup_date", "2024-02-23"),
        ("delivery_date", "2024-02-24"),
    ]:
        response = client.post(
            f"/api/v1/reviews/{review['id']}/confirmations",
            json=confirmation_body(review, field, value),
        )
        assert response.status_code == 200, response.text
        review = response.json()
    return review


def test_confirmation_preserves_ai_and_source_then_rechecks_only_relevant_fields(client):
    before = create_packet(client)
    after = confirm_all(client, before)
    assert after["documents"][0]["fields"] == before["documents"][0]["fields"]
    assert after["documents"][0]["pages"] == before["documents"][0]["pages"]
    assert after["documents"][0]["confirmations"]["currency"]["value"] == "USD"
    assert after["documents"][0]["confirmations"]["pickup_date"]["value"] == "2024-02-23"
    assert [event["field"] for event in after["confirmations"]] == [
        "currency",
        "pickup_date",
        "delivery_date",
    ]
    assert after["confirmations"][0]["original_value"] is None
    assert after["confirmations"][1]["original_value"] == "02/23/24"
    assert after["revision"] == 3
    assert {issue["code"] for issue in after["issues"]} == {"missing_document"}
    assert {issue["id"] for issue in before["issues"] if issue["code"] == "missing_document"} == {
        issue["id"] for issue in after["issues"]
    }
    assert after["status"] == "needs_review" and after["approval"] is None
    url = f"/api/v1/reviews/{after['id']}"
    assert client.get(url).json()["confirmations"] == after["confirmations"]
    assert (
        client.post(url + "/approval", json={"reviewer": "Test", "note": "Checked."}).status_code
        == 409
    )
    assert client.get(url + "/export").status_code == 409


def test_complete_packet_requires_separate_explicit_approval_and_exports_history(client):
    review = confirm_all(client, create_packet(client, complete=True))
    assert review["issues"] == [] and review["status"] == "ready_for_review"
    url = f"/api/v1/reviews/{review['id']}"
    assert client.get(url + "/export").status_code == 409
    approved = client.post(
        url + "/approval", json={"reviewer": "Test", "note": "Compared sources."}
    )
    assert approved.status_code == 200
    exported = client.get(url + "/export").json()
    assert len(exported["confirmations"]) == 3
    assert exported["documents"][0]["fields"]["pickup_date"]["value"] == "02/23/24"
    assert exported["documents"][0]["confirmations"]["pickup_date"]["value"] == "2024-02-23"
    assert client.post(url + "/confirmations", json=confirmation_body(exported)).status_code == 409


def test_confirmations_cannot_clear_amount_mismatch(client):
    review = confirm_all(client, create_packet(client, complete=True, invoice_amount="775.00"))
    assert {issue["code"] for issue in review["issues"]} == {"amount_mismatch"}
    body = confirmation_body(review)
    body.update(field="amount", value="775.00")
    assert (
        client.post(f"/api/v1/reviews/{review['id']}/confirmations", json=body).status_code == 422
    )


@pytest.mark.parametrize(
    "change",
    [
        {"page": 9},
        {"quote": "Invented quote $700.00"},
        {"value": "XYZ"},
        {"value": "EUR"},
        {"reviewer": " "},
        {"note": " "},
        {"document_id": "another-document"},
        {"quote": "Amount: 700.00"},
        {"value": "USD", "approve": True},
    ],
)
def test_invalid_confirmations_leave_record_unchanged(client, change):
    review = create_packet(client)
    body = confirmation_body(review)
    body.update(change)
    url = f"/api/v1/reviews/{review['id']}"
    assert client.post(url + "/confirmations", json=body).status_code == 422
    assert client.get(url).json() == review


@pytest.mark.parametrize("value", ["02/23/2024", "2024-03-23", "2025-02-23", "2024-02-30"])
def test_date_confirmation_requires_full_valid_date_supported_by_printed_parts(client, value):
    review = create_packet(client)
    response = client.post(
        f"/api/v1/reviews/{review['id']}/confirmations",
        json=confirmation_body(review, "pickup_date", value),
    )
    assert response.status_code == 422


def test_stale_revision_cannot_overwrite_newer_confirmation(client):
    review = create_packet(client)
    body = confirmation_body(review)
    url = f"/api/v1/reviews/{review['id']}"
    first = client.post(url + "/confirmations", json=body).json()
    body["value"] = "CAD"
    assert client.post(url + "/confirmations", json=body).status_code == 409
    body["expected_revision"] = first["revision"]
    changed = client.post(url + "/confirmations", json=body).json()
    assert changed["confirmations"][-1]["previous_value"] == "USD"
    assert changed["confirmations"][-1]["original_value"] is None
    assert len(changed["confirmations"]) == 2


def test_recheck_keeps_extraction_and_history_but_invalidates_approval(tmp_path):
    path = tmp_path / "recheck.db"
    with TestClient(create_app(db_path=path, provider="demo")) as client:
        review = client.post("/api/v1/demo/clean").json()
        url = f"/api/v1/reviews/{review['id']}"
        approved = client.post(
            url + "/approval", json={"reviewer": "Test", "note": "Compared sources."}
        ).json()
        repository = Repository(path)

        def older(saved):
            saved.processing.pipeline_revision = "earlier-policy"

        repository.update(review["id"], older)
        before = client.get(url).json()
        response = client.post(url + "/recheck", json={"expected_revision": approved["revision"]})
        assert response.status_code == 200
        after = response.json()
        assert after["processing"]["pipeline_revision"] == PIPELINE_REVISION
        assert after["processing"]["model"] == before["processing"]["model"]
        assert after["documents"] == before["documents"]
        assert after["status"] == "ready_for_review" and after["approval"] is None
        assert after["audit"][:-1] == before["audit"]
        assert client.get(url + "/export").status_code == 409
        assert client.post(url + "/recheck", json={"expected_revision": 0}).status_code == 409


def test_missing_review_and_legacy_metadata_are_safe(client, tmp_path):
    review = create_packet(client)
    assert (
        client.post(
            "/api/v1/reviews/missing/confirmations", json=confirmation_body(review)
        ).status_code
        == 404
    )
    assert (
        client.post("/api/v1/reviews/missing/recheck", json={"expected_revision": 0}).status_code
        == 404
    )


def test_source_currency_cannot_be_changed_to_a_conflicting_code(client):
    response = client.post(
        "/api/v1/reviews",
        files={"files": ("rate.txt", b"Currency: CAD $700.00")},
        data={"kinds": "rate_confirmation"},
    )
    review = response.json()
    body = confirmation_body(review)
    body["quote"] = "Currency: CAD $700.00"
    assert (
        client.post(f"/api/v1/reviews/{review['id']}/confirmations", json=body).status_code == 422
    )


def test_legacy_field_confirmation_requires_compatible_recheck(tmp_path):
    path = tmp_path / "older.db"
    with TestClient(create_app(db_path=path, provider="demo")) as client:
        review = create_packet(client)
        repository = Repository(path)

        def earlier(saved):
            saved.processing.pipeline_revision = "older-policy"

        repository.update(review["id"], earlier)
        url = f"/api/v1/reviews/{review['id']}"
        assert (
            client.post(url + "/confirmations", json=confirmation_body(review)).status_code == 409
        )
        fresh = client.post(url + "/recheck", json={"expected_revision": 0}).json()
        assert client.post(url + "/confirmations", json=confirmation_body(fresh)).status_code == 200

        def incompatible(saved):
            saved.processing = None

        repository.update(review["id"], incompatible)
        revision = client.get(url).json()["revision"]
        assert (
            client.post(url + "/recheck", json={"expected_revision": revision}).status_code == 409
        )


def test_confirmation_cannot_remove_an_unrelated_extraction_warning(tmp_path):
    path = tmp_path / "warning.db"
    with TestClient(create_app(db_path=path, provider="demo")) as client:
        review = create_packet(client, complete=True)

        def warning(saved):
            saved.documents[0].warnings = [
                "Discarded unsupported extraction for currency.",
                "Discarded unsupported extraction for amount.",
            ]

        Repository(path).update(review["id"], warning)
        after = confirm_all(client, review)
        warnings = [
            item["message"] for item in after["issues"] if item["code"] == "extraction_warning"
        ]
        assert len(warnings) == 1 and "amount" in warnings[0]
        assert len(after["documents"][0]["warnings"]) == 2
