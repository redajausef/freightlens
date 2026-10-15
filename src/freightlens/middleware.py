"""Enforce the total byte budget while receiving, before multipart spooling."""

from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyLimitExceeded(MultiPartException):
    """Multipart parsers close partially opened temp files for this exception."""


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        detail = "Request body exceeds the configured size limit."
        length = dict(scope.get("headers", [])).get(b"content-length")
        if length is not None and (
            not length.isdigit() or len(length) > 20 or int(length) > self.max_bytes
        ):
            await JSONResponse({"detail": detail}, status_code=413)(scope, receive, send)
            return
        received = 0
        exceeded = False

        async def bounded_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    raise BodyLimitExceeded(detail)
            return message

        async def checked_send(message: Message):
            if exceeded and message["type"] == "http.response.start":
                # Request.form translates MultiPartException to400 after cleaning temp files.
                message = {**message, "status": 413}
            await send(message)

        try:
            await self.app(scope, bounded_receive, checked_send)
        except BodyLimitExceeded:
            await JSONResponse({"detail": detail}, status_code=413)(scope, receive, send)
