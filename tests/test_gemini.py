import json

import httpx
import pytest
from fastapi.testclient import TestClient

from freightlens.api import create_app
from freightlens.extraction import ExtractionError, GeminiExtractor
from freightlens.models import Page


def envelope(content='{"fields":{}}', finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": content}]}}]}


def test_gemini_request_uses_header_auth_fixed_endpoint_and_no_tools():
    def handler(request):
        assert str(request.url).startswith("https://generativelanguage.googleapis.com/")
        assert request.url.query == b""
        assert request.headers["x-goog-api-key"] == "test-only-key"
        payload = json.loads(request.content)
        assert "tools" not in payload
        assert "untrusted" in payload["systemInstruction"]["parts"][0]["text"]
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert "USD" in payload["systemInstruction"]["parts"][0]["text"]
        return httpx.Response(
            200,
            json=envelope(
                json.dumps(
                    {
                        "fields": {
                            "amount": {
                                "value": "700.00",
                                "page": 3,
                                "quote": "Total Cost USD 700.00",
                            },
                        }
                    }
                )
            ),
        )

    result = GeminiExtractor("test-only-key", transport=httpx.MockTransport(handler)).extract(
        "rate_confirmation",
        [Page(number=3, text="Total Cost USD 700.00")],
    )
    assert result.fields["amount"].page == 3


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 503])
def test_gemini_failures_do_not_leak_upstream_details(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="PRIVATE-UPSTREAM-SECRET")

    extractor = GeminiExtractor(
        "test-only-key",
        transport=httpx.MockTransport(handler),
        retry_delay=0,
    )
    with pytest.raises(ExtractionError) as error:
        extractor.extract("invoice", [Page(number=1, text="Example invoice")])
    assert "PRIVATE" not in str(error.value)
    if status == 429:
        assert len(calls) == 1  # No quota loop or paid fallback.


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"candidates": [None]},
        {"candidates": "bad"},
        envelope(finish="MAX_TOKENS"),
        envelope('{"fields":{}, "approve":true}'),
        envelope("not json"),
        envelope('{"fields":{"unknown":{}}}'),
        {"candidates": [{"finishReason": "STOP", "content": None}]},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [None]}}]},
        {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"functionCall": {"name": "approve"}},
                        ]
                    },
                }
            ]
        },
    ],
)
def test_gemini_rejects_blocked_malformed_or_incomplete_responses(body):
    extractor = GeminiExtractor(
        "test-only-key",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)),
    )
    with pytest.raises(ExtractionError):
        extractor.extract("invoice", [Page(number=1, text="Example invoice")])


def test_gemini_retries_temporary_unavailability_and_ignores_thought_parts():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        body = envelope()
        body["candidates"][0]["content"]["parts"].insert(0, {"thought": True, "text": "private"})
        return httpx.Response(200, json=body)

    result = GeminiExtractor(
        "test-only-key",
        transport=httpx.MockTransport(handler),
        retry_delay=0,
    ).extract("invoice", [Page(number=1, text="Example invoice")])
    assert result.fields == {} and len(calls) == 2


def test_gemini_transport_failure_is_safe():
    def handler(request):
        raise httpx.ConnectError("private network detail")

    with pytest.raises(ExtractionError, match="could not be reached"):
        GeminiExtractor("test-only-key", transport=httpx.MockTransport(handler)).extract(
            "invoice",
            [Page(number=1, text="Example invoice")],
        )


def test_gemini_missing_configuration_never_falls_back(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with TestClient(create_app(db_path=tmp_path / "gemini.db", provider="gemini")) as client:
        assert client.get("/api/v1/health").json()["provider"] == "gemini"
        assert client.post("/api/v1/demo/clean").status_code == 409
        response = client.post(
            "/api/v1/reviews",
            files={"files": ("test.txt", b"Invoice Number: A")},
            data={"kinds": "invoice"},
        )
        assert response.status_code == 502
        assert "GEMINI_API_KEY" in response.json()["detail"]
        assert client.get("/api/v1/reviews").json() == []


@pytest.mark.parametrize("model", ["https://example.com", "../other", "", "x?key=secret"])
def test_gemini_model_cannot_change_the_endpoint(model):
    with pytest.raises(ExtractionError, match="model ID"):
        GeminiExtractor("test-only-key", model=model)
