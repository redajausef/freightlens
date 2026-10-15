from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from freightlens.api import create_app

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "test.db", provider="demo")) as client:
        yield client


def packet(client, scenario="mismatch"):
    paths = sorted((SAMPLES / scenario).glob("*.txt"))
    kinds = [path.stem for path in paths]
    return client.post(
        "/api/v1/reviews",
        files=[("files", (path.name, path.read_bytes(), "text/plain")) for path in paths],
        data={"kinds": ",".join(kinds)},
    )


def test_mismatch_is_blocked_from_approval(client):
    response = packet(client)
    assert response.status_code == 201, response.text
    review = response.json()
    assert review["status"] == "needs_review"
    assert "amount_mismatch" in {issue["code"] for issue in review["issues"]}
    approval = client.post(
        f"/api/v1/reviews/{review['id']}/approval",
        json={"reviewer": "Demo reviewer", "note": "Checked"},
    )
    assert approval.status_code == 409
    assert client.get(f"/api/v1/reviews/{review['id']}/export").status_code == 409


def test_clean_packet_requires_explicit_review_then_exports(client):
    review = packet(client, "clean").json()
    assert review["status"] == "ready_for_review"
    assert review["issues"] == []
    assert client.get(f"/api/v1/reviews/{review['id']}/export").status_code == 409
    approval = client.post(
        f"/api/v1/reviews/{review['id']}/approval",
        json={"reviewer": "Amina", "note": "Compared all three source documents."},
    )
    assert approval.status_code == 200
    approved = approval.json()
    assert approved["status"] == "approved"
    assert approved["audit"][-1]["actor"] == "Amina"
    exported = client.get(f"/api/v1/reviews/{review['id']}/export")
    assert exported.status_code == 200
    assert exported.json()["approval"]["reviewer"] == "Amina"


def test_same_packet_returns_existing_review_without_duplicate_processing(client):
    first = packet(client)
    second = packet(client)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get("/api/v1/reviews").json()) == 1


def test_missing_document_flagged_and_unknown_review_is_404(client):
    path = SAMPLES / "clean" / "invoice.txt"
    response = client.post(
        "/api/v1/reviews",
        files={"files": (path.name, path.read_bytes(), "text/plain")},
        data={"kinds": "invoice"},
    )
    assert response.status_code == 201
    assert sum(i["code"] == "missing_document" for i in response.json()["issues"]) == 2
    assert client.get("/api/v1/reviews/does-not-exist").status_code == 404


def test_rejects_invalid_types_duplicate_bytes_and_kind_count(client):
    assert (
        client.post(
            "/api/v1/reviews",
            files={"files": ("script.exe", b"MZ", "application/octet-stream")},
            data={"kinds": "invoice"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/reviews",
            files=[("files", ("a.txt", b"same")), ("files", ("b.txt", b"same"))],
            data={"kinds": "invoice,rate_confirmation"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/reviews",
            files={"files": ("a.txt", b"hello")},
            data={"kinds": "invoice,proof_of_delivery"},
        ).status_code
        == 422
    )


def test_ui_and_health_are_available(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/health").json()["provider"] == "demo"


def test_comment_does_not_resolve_a_discrepancy(client):
    review = packet(client).json()
    issue = next(i for i in review["issues"] if i["code"] == "amount_mismatch")
    response = client.post(
        f"/api/v1/reviews/{review['id']}/notes",
        json={
            "reviewer": "Amina",
            "note": "Requested corrected invoice.",
            "issue_id": issue["id"],
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "needs_review"
    assert response.json()["audit"][-1]["action"] == "note_added"


def test_demo_shortcuts_and_pdf_upload(client):
    assert client.post("/api/v1/demo/mismatch").status_code == 201
    assert client.post("/api/v1/demo/missing").json()["status"] == "needs_review"
    paths = sorted((SAMPLES / "clean").glob("*.pdf"))
    response = client.post(
        "/api/v1/reviews",
        files=[("files", (p.name, p.read_bytes(), "application/pdf")) for p in paths],
        data={"kinds": ",".join(p.stem for p in paths)},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "ready_for_review"


def test_browser_origin_boundary_and_request_limit(client):
    assert (
        client.post(
            "/api/v1/demo/clean",
            headers={
                "Origin": "https://unrelated.example",
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/demo/clean",
            headers={
                "Content-Length": str(20 * 1024 * 1024),
            },
        ).status_code
        == 413
    )
    assert client.get("/", headers={"host": "unrelated.example"}).status_code == 400


def test_failed_kimi_configuration_never_falls_back_to_demo(tmp_path, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with TestClient(create_app(db_path=tmp_path / "kimi.db", provider="kimi")) as client:
        assert client.post("/api/v1/demo/clean").status_code == 409
        response = packet(client, "clean")
        assert response.status_code == 502
        assert "NVIDIA_API_KEY" in response.json()["detail"]
        assert client.get("/api/v1/reviews").json() == []


def test_invalid_state_changes_leave_history_intact(client):
    review = packet(client, "clean").json()
    review_id = review["id"]
    body = {"reviewer": "Amina", "note": "Checked the source documents."}
    assert client.post(f"/api/v1/reviews/{review_id}/approval", json=body).status_code == 200
    assert client.post(f"/api/v1/reviews/{review_id}/approval", json=body).status_code == 409
    assert len(client.get(f"/api/v1/reviews/{review_id}").json()["audit"]) == 2
    assert client.post("/api/v1/reviews/missing/approval", json=body).status_code == 404
    assert client.post("/api/v1/reviews/missing/notes", json=body).status_code == 404
    body["issue_id"] = "not-a-real-issue"
    assert client.post(f"/api/v1/reviews/{review_id}/notes", json=body).status_code == 422
    assert len(client.get(f"/api/v1/reviews/{review_id}").json()["audit"]) == 2
