from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from freightlens.ingestion import MAX_BYTES, DocumentError, read_pages


def pdf_bytes(*, encrypted=False, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    if encrypted:
        writer.encrypt("sample")
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_pdf_preserves_page_numbers_and_text():
    path = Path(__file__).resolve().parents[1] / "samples" / "mismatch" / "invoice.pdf"
    pages = read_pages(path.name, path.read_bytes())
    assert pages[0].number == 1
    assert "Amount: 2,300.00" in pages[0].text


@pytest.mark.parametrize(
    "filename,content",
    [
        ("empty.txt", b""),
        ("bad.txt", b"\xff"),
        ("big.txt", b"a" * (MAX_BYTES + 1)),
        ("fake.pdf", b"not a pdf"),
        ("broken.pdf", b"%PDF-invalid"),
        ("scan.pdf", pdf_bytes()),
        ("encrypted.pdf", pdf_bytes(encrypted=True)),
        ("long.pdf", pdf_bytes(pages=13)),
        ("too-long.txt", b"x" * 60_001),
    ],
    ids=[
        "empty",
        "encoding",
        "size",
        "fake-pdf",
        "broken-pdf",
        "scan",
        "encrypted",
        "pages",
        "text-limit",
    ],
)
def test_unreadable_or_oversized_documents_are_rejected(filename, content):
    with pytest.raises(DocumentError):
        read_pages(filename, content)
