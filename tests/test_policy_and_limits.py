"""Policy transitions and streaming-body limits use real request boundaries."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from freightlens.api import create_app
from freightlens.repository import Repository


@pytest.mark.parametrize("approved", [False, True])
def test_legacy_reviews_are_readable_but_require_rechecking_before_actions(tmp_path, approved):
    path = tmp_path / "legacy.db"
    with TestClient(create_app(db_path=path, provider="demo")) as client:
        review = client.post("/api/v1/demo/clean").json()
        action = f"/api/v1/reviews/{review['id']}"
        body = {"reviewer": "Demo reviewer", "note": "Checked the sources."}
        if approved:
            assert client.post(action + "/approval", json=body).status_code == 200
        repository = Repository(path)
        repository.update(review["id"], lambda saved: setattr(saved, "processing", None))
        assert client.get(action).status_code == 200
        assert client.get(action).json()["processing"] is None
        assert client.post(action + "/approval", json=body).status_code == 409
        assert client.get(action + "/export").status_code == 409
        fresh = client.post("/api/v1/demo/mismatch").json()
        assert fresh["processing"]["pipeline_revision"]


def test_streamed_limit_closes_multipart_tempfiles(tmp_path, monkeypatch):
    import starlette.formparsers

    original = starlette.formparsers.SpooledTemporaryFile
    opened = []

    def track_file(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", track_file)
    app = create_app(db_path=tmp_path / "stream.db", provider="demo", max_body_bytes=1024)
    chunks = iter(
        [
            b'--boundary\r\nContent-Disposition: form-data; name="files"; '
            b'filename="test.txt"\r\nContent-Type: text/plain\r\n\r\n' + b"a" * 100,
            b"b" * 200,
            b"c" * 2048,
        ]
    )
    sent = []

    async def receive():
        try:
            return {"type": "http.request", "body": next(chunks), "more_body": True}
        except StopIteration:
            return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/reviews",
        "raw_path": b"/api/v1/reviews",
        "query_string": b"",
        "root_path": "",
        "server": ("testserver", 80),
        "client": ("local", 1),
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"multipart/form-data; boundary=boundary"),
        ],
    }
    asyncio.run(app(scope, receive, send))
    assert next(item["status"] for item in sent if item["type"] == "http.response.start") == 413
    assert opened and all(file.closed for file in opened)
