"""Read bounded text-bearing PDFs; never execute document content."""

from io import BytesIO
from pathlib import PureWindowsPath

from pypdf import PdfReader

from freightlens.models import Page

MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 12
MAX_TEXT = 60_000


class DocumentError(ValueError):
    pass


def read_pages(filename: str, content: bytes) -> list[Page]:
    suffix = PureWindowsPath(filename).suffix.lower()
    if len(content) > MAX_BYTES:
        raise DocumentError("Each document must be 5 MB or smaller.")
    if not content:
        raise DocumentError("Empty documents cannot be processed.")
    if suffix == ".txt":
        try:
            texts = [content.decode("utf-8-sig")]
        except UnicodeDecodeError as exc:
            raise DocumentError("Text documents must use UTF-8 encoding.") from exc
    elif suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise DocumentError("This file is not a valid PDF.")
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise DocumentError("Encrypted PDFs are not supported in this version.")
            if len(reader.pages) > MAX_PAGES:
                raise DocumentError(f"PDFs must contain at most {MAX_PAGES} pages.")
            texts = [page.extract_text() or "" for page in reader.pages]
        except DocumentError:
            raise
        except Exception as exc:
            raise DocumentError("The PDF could not be read. Please upload a valid PDF.") from exc
    else:
        raise DocumentError("Use a PDF or UTF-8 .txt document.")
    if not texts or sum(len(text) for text in texts) > MAX_TEXT:
        raise DocumentError("Document text exceeds the 60,000-character limit.")
    if not any(text.strip() for text in texts):
        raise DocumentError("No readable text found. Scanned PDFs need OCR before upload.")
    return [Page(number=i, text=text) for i, text in enumerate(texts, start=1)]
