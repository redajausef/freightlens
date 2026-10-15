"""FastAPI transport; run locally with python -m uvicorn freightlens.api:app."""

import hashlib
import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from freightlens.confirmations import validate_confirmation
from freightlens.extraction import ExtractionError
from freightlens.ingestion import MAX_BYTES, DocumentError
from freightlens.middleware import RequestBodyLimitMiddleware
from freightlens.models import (
    Approval,
    AuditEvent,
    ConfirmationEvent,
    FieldConfirmation,
    RecheckRequest,
    Review,
    ReviewNote,
)
from freightlens.repository import Repository
from freightlens.service import create_review, now, revalidate_review
from freightlens.versions import EXTRACTION_REVISION, PIPELINE_REVISION, RULES_REVISION

STATIC = Path(__file__).parent / "static"
KINDS = {"rate_confirmation", "invoice", "proof_of_delivery"}


def create_app(
    *,
    db_path: Path | None = None,
    provider: str | None = None,
    max_body_bytes: int = 3 * MAX_BYTES + 100_000,
) -> FastAPI:
    app = FastAPI(title="FreightLens", version="0.1.0")
    repository = Repository(db_path or Path(os.getenv("FREIGHTLENS_DB", "data/freightlens.db")))
    mode = provider or os.getenv("FREIGHTLENS_PROVIDER", "demo")
    if mode not in {"demo", "gemini", "kimi"}:
        raise ValueError("FREIGHTLENS_PROVIDER must be demo, gemini, or kimi.")
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        # Local single-user prototype. Reject cross-origin browser writes and DNS rebinding.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
                return JSONResponse(
                    {"detail": "Cross-origin writes are not permitted."}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
            )
        return response

    @app.exception_handler(ExtractionError)
    async def extraction_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=502)

    @app.exception_handler(DocumentError)
    async def document_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/v1/health")
    def health():
        return {
            "status": "ok",
            "provider": mode,
            "version": "0.1.0",
            "pipeline_revision": PIPELINE_REVISION,
        }

    def require_current_policy(review: Review):
        if not review.processing or review.processing.pipeline_revision != PIPELINE_REVISION:
            raise HTTPException(
                409,
                "This review used an older validation policy. "
                "Recheck its saved pages or upload the packet again.",
            )

    @app.get("/api/v1/reviews", response_model=list[Review])
    def list_reviews():
        return repository.all()

    @app.get("/api/v1/reviews/{review_id}", response_model=Review)
    def get_review(review_id: str):
        review = repository.get(review_id)
        if review is None:
            raise HTTPException(404, "Review not found.")
        return review

    @app.post("/api/v1/reviews", response_model=Review, status_code=201)
    def upload_review(
        response: Response,
        files: Annotated[list[UploadFile], File()],
        kinds: Annotated[str, Form()],
    ):
        declared = [kind.strip() for kind in kinds.split(",")]
        if (
            not 1 <= len(files) <= 3
            or len(files) != len(declared)
            or any(kind not in KINDS for kind in declared)
            or len(set(declared)) != len(declared)
        ):
            raise HTTPException(422, "Select one unique document type per file, up to three files.")
        uploads, hashes = [], set()
        for upload, kind in zip(files, declared, strict=True):
            content = upload.file.read(MAX_BYTES + 1)
            digest = hashlib.sha256(content).hexdigest()
            if digest in hashes:
                raise HTTPException(409, "The same document appears more than once in this packet.")
            hashes.add(digest)
            uploads.append((upload.filename or "document", kind, content))
        review, created = create_review(repository, uploads, mode)
        response.status_code = 201 if created else 200
        response.headers["Location"] = f"/api/v1/reviews/{review.id}"
        return review

    @app.post("/api/v1/reviews/{review_id}/approval", response_model=Review)
    def approve(review_id: str, approval: Approval):
        def change(review):
            require_current_policy(review)
            if review.status == "approved":
                raise HTTPException(409, "This review is already approved.")
            if review.issues:
                raise HTTPException(
                    409,
                    "Resolve field clarifications and supply missing or corrected documents first.",
                )
            review.approval = approval
            review.status = "approved"
            review.revision += 1
            review.audit.append(
                AuditEvent(at=now(), actor=approval.reviewer, action="approved", note=approval.note)
            )

        review = repository.update(review_id, change)
        if review is None:
            raise HTTPException(404, "Review not found.")
        return review

    @app.post("/api/v1/reviews/{review_id}/confirmations", response_model=Review)
    def confirm_field(review_id: str, confirmation: FieldConfirmation):
        def change(review: Review):
            require_current_policy(review)
            if review.status == "approved":
                raise HTTPException(409, "Approved records are locked. Start a new review.")
            if review.revision != confirmation.expected_revision:
                raise HTTPException(
                    409, "This review changed. Reopen it before confirming a field."
                )
            doc = next(
                (doc for doc in review.documents if doc.id == confirmation.document_id), None
            )
            if doc is None:
                raise HTTPException(422, "Document does not belong to this review.")
            try:
                evidence = validate_confirmation(doc, confirmation)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            field = confirmation.field
            original = doc.fields.get(field)
            previous = doc.effective_fields.get(field)
            at = now()
            review.confirmations.append(
                ConfirmationEvent(
                    at=at,
                    reviewer=confirmation.reviewer.strip(),
                    note=confirmation.note.strip(),
                    document_id=doc.id,
                    field=field,
                    original_value=original.value if original else None,
                    previous_value=previous.value if previous else None,
                    value=evidence.value,
                    page=evidence.page,
                    quote=evidence.quote,
                )
            )
            doc.confirmations[field] = evidence
            revalidate_review(review)
            review.audit.append(
                AuditEvent(
                    at=at,
                    actor=confirmation.reviewer.strip(),
                    action="field_confirmed",
                    note=f"{doc.filename}: {field} confirmed as {evidence.value} "
                    f"(previous: {previous.value if previous else 'not extracted'}). "
                    f"Reason: {confirmation.note.strip()}",
                )
            )

        review = repository.update(review_id, change)
        if review is None:
            raise HTTPException(404, "Review not found.")
        return review

    @app.post("/api/v1/reviews/{review_id}/recheck", response_model=Review)
    def recheck(review_id: str, request: RecheckRequest):
        def change(review: Review):
            if review.revision != request.expected_revision:
                raise HTTPException(409, "This review changed. Reopen it before rechecking.")
            if (
                not review.processing
                or review.processing.extraction_revision != EXTRACTION_REVISION
            ):
                raise HTTPException(
                    409, "This extraction needs a fresh upload under the current policy."
                )
            review.processing.pipeline_revision = PIPELINE_REVISION
            review.processing.rules_revision = RULES_REVISION
            revalidate_review(review)
            review.audit.append(
                AuditEvent(
                    at=now(),
                    actor="system",
                    action="checks_rerun",
                    note="Rechecked saved source pages and fields under the current rules; "
                    "original extraction retained. Employee approval is still required.",
                )
            )

        review = repository.update(review_id, change)
        if review is None:
            raise HTTPException(404, "Review not found.")
        return review

    @app.post("/api/v1/reviews/{review_id}/notes", response_model=Review)
    def add_note(review_id: str, note: ReviewNote):
        def change(review):
            if note.issue_id and note.issue_id not in {issue.id for issue in review.issues}:
                raise HTTPException(422, "Issue does not belong to this review.")
            review.revision += 1
            review.audit.append(
                AuditEvent(
                    at=now(),
                    actor=note.reviewer,
                    action="note_added",
                    note=note.note,
                    issue_id=note.issue_id,
                )
            )

        review = repository.update(review_id, change)
        if review is None:
            raise HTTPException(404, "Review not found.")
        return review

    @app.get("/api/v1/reviews/{review_id}/export", response_model=Review)
    def export(review_id: str, response: Response):
        review = get_review(review_id)
        require_current_policy(review)
        if review.status != "approved":
            raise HTTPException(409, "Employee approval is required before export.")
        response.headers["Content-Disposition"] = f'attachment; filename="review-{review.id}.json"'
        return review

    @app.post("/api/v1/demo/{scenario}", response_model=Review, status_code=201)
    def demo(scenario: Literal["clean", "mismatch", "missing"], response: Response):
        if mode != "demo":
            raise HTTPException(
                409, "Sample shortcuts run only in demo mode. Upload files for AI extraction."
            )
        # Packaged synthetic examples; cannot select a path supplied by a caller.
        base = STATIC / "samples" / scenario
        uploads = [(path.name, path.stem, path.read_bytes()) for path in sorted(base.glob("*.txt"))]
        review, created = create_review(repository, uploads, mode)
        response.status_code = 201 if created else 200
        return review

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=max_body_bytes)
    return app


app = create_app()
