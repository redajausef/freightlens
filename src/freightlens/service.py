"""Application workflow: ingest -> extract -> ground -> validate -> record."""

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import PureWindowsPath
from uuid import uuid4

from freightlens.extraction import configured_model, ground_fields, make_extractor
from freightlens.ingestion import read_pages
from freightlens.models import AuditEvent, Document, Extraction, ProcessingMetadata, Review
from freightlens.repository import Repository
from freightlens.rules import check_documents, draft_email
from freightlens.scope import scope_problem
from freightlens.versions import EXTRACTION_REVISION, PIPELINE_REVISION, RULES_REVISION


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_review(
    repository: Repository, uploads: list[tuple], provider: str
) -> tuple[Review, bool]:
    start = time.perf_counter()
    identifiers = [(kind, hashlib.sha256(content).hexdigest()) for _, kind, content in uploads]
    model = configured_model(provider)
    fingerprint = hashlib.sha256(
        json.dumps([provider, model, PIPELINE_REVISION, sorted(identifiers)]).encode()
    ).hexdigest()
    existing = repository.find(fingerprint)
    if existing:
        return existing, False
    # Validate all documents before the first outbound API call.
    prepared = [(name, kind, content, read_pages(name, content)) for name, kind, content in uploads]
    extractor = None
    documents = []
    for filename, kind, content, pages in prepared:
        scope = scope_problem(kind, pages)
        if scope:
            extracted = Extraction()
        else:
            if extractor is None:
                extractor = make_extractor(provider)
            extracted = extractor.extract(kind, pages)
        fields, rejected = ground_fields(extracted.fields, pages)
        warnings = [f"Discarded unsupported extraction for {field}." for field in rejected]
        if any(not page.text.strip() for page in pages):
            warnings.append("At least one page has no readable text; check for scanned content.")
        documents.append(
            Document(
                id=str(uuid4()),
                kind=kind,
                filename=PureWindowsPath(filename).name[:150],
                sha256=hashlib.sha256(content).hexdigest(),
                pages=pages,
                fields=fields,
                warnings=warnings,
                extraction_status="skipped_scope" if scope else "extracted",
            )
        )
    issues = check_documents(documents)
    review = Review(
        id=str(uuid4()),
        created_at=now(),
        provider=provider,
        processing=ProcessingMetadata(
            provider=provider,
            model=model,
            pipeline_revision=PIPELINE_REVISION,
            extraction_revision=EXTRACTION_REVISION,
            rules_revision=RULES_REVISION,
        ),
        status="needs_review" if issues else "ready_for_review",
        documents=documents,
        issues=issues,
        draft_email=draft_email(documents, issues),
        elapsed_ms=int((time.perf_counter() - start) * 1000),
        audit=[
            AuditEvent(
                at=now(),
                actor="system",
                action="review_created",
                note=f"Processed with {provider}; employee approval required.",
            )
        ],
    )
    return repository.insert(fingerprint, review)


def revalidate_review(review: Review) -> None:
    review.issues = check_documents(review.documents)
    review.status = "needs_review" if review.issues else "ready_for_review"
    review.draft_email = draft_email(review.documents, review.issues)
    review.approval = None
    review.revision += 1
