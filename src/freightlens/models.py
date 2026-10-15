"""Contracts shared by the API, extractors, rules, and database."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentKind = Literal["rate_confirmation", "invoice", "proof_of_delivery"]
FieldName = Literal[
    "shipment_reference",
    "carrier",
    "pickup_location",
    "delivery_location",
    "pickup_date",
    "delivery_date",
    "invoice_number",
    "amount",
    "currency",
]
ConfirmableField = Literal["currency", "pickup_date", "delivery_date"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Page(Contract):
    number: int = Field(ge=1)
    text: str


class Evidence(Contract):
    value: str = Field(min_length=1, max_length=300)
    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=600)


class Extraction(Contract):
    fields: dict[FieldName, Evidence] = Field(default_factory=dict)


class Document(Contract):
    id: str
    kind: DocumentKind
    filename: str
    sha256: str
    pages: list[Page]
    fields: dict[FieldName, Evidence]
    warnings: list[str] = Field(default_factory=list)
    confirmations: dict[ConfirmableField, Evidence] = Field(default_factory=dict)
    extraction_status: Literal["extracted", "skipped_scope"] = "extracted"

    @property
    def effective_fields(self) -> dict[FieldName, Evidence]:
        return {**self.fields, **self.confirmations}


class Issue(Contract):
    id: str
    code: str
    message: str
    document_ids: list[str] = Field(default_factory=list)
    field: str | None = None


class AuditEvent(Contract):
    at: str
    actor: str
    action: str
    note: str
    issue_id: str | None = None


class Approval(Contract):
    reviewer: str = Field(min_length=2, max_length=80, pattern=r"\S")
    note: str = Field(min_length=5, max_length=1000, pattern=r"\S")


class ReviewNote(Approval):
    issue_id: str | None = None


class FieldConfirmation(Approval):
    document_id: str = Field(min_length=1, max_length=100)
    field: ConfirmableField
    value: str = Field(min_length=1, max_length=300, pattern=r"\S")
    page: int = Field(ge=1, strict=True)
    quote: str = Field(min_length=1, max_length=600, pattern=r"\S")
    expected_revision: int = Field(ge=0, strict=True)


class ConfirmationEvent(Contract):
    at: str
    reviewer: str
    note: str
    document_id: str
    field: ConfirmableField
    original_value: str | None
    previous_value: str | None
    value: str
    page: int
    quote: str


class RecheckRequest(Contract):
    expected_revision: int = Field(ge=0, strict=True)


class ProcessingMetadata(Contract):
    provider: str
    model: str
    pipeline_revision: str
    extraction_revision: str
    rules_revision: str


class Review(Contract):
    id: str
    created_at: str
    provider: str
    status: Literal["needs_review", "ready_for_review", "approved"]
    documents: list[Document]
    issues: list[Issue]
    draft_email: str
    elapsed_ms: int
    audit: list[AuditEvent]
    approval: Approval | None = None
    processing: ProcessingMetadata | None = None
    revision: int = Field(default=0, ge=0)
    confirmations: list[ConfirmationEvent] = Field(default_factory=list)
