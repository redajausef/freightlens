"""Download unchanged public evaluation PDFs, checking recorded SHA-256 hashes."""

import argparse
import hashlib
from pathlib import Path

import httpx

PROJECT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024
SOURCES = (
    (
        "wayfinder-rate-confirmation-188028.pdf",
        "https://www.grouprac.com/Documents/188028Rate%20Confirmation.pdf",
        "214319cf1e30de49f6b79dca890e1ece375136afb61124ea376c74935fadeb5b",
    ),
    (
        "rxo-rate-confirmation-14521900.pdf",
        "https://www.grouprac.com/Documents/14521900Rate%20Confirmation.pdf",
        "2125def04753e6a719579b8cbdcaee8ed8c669c52810c5749abebb319667ec85",
    ),
    (
        "fedex-express-invoice-guide.pdf",
        "https://www.fedex.com/content/dam/fedex/international/o2p/pdf/"
        "fedex-express-invoice-explanation-master-template-en-gb.pdf",
        "186b84adc0c3ae0781518f995595e85c93cf2f1248f86b5238c62bc26cd7d84c",
    ),
)


def download(client: httpx.Client, folder: Path, name: str, url: str, digest: str) -> str:
    target = folder / name
    if target.exists():
        if (
            target.stat().st_size > MAX_BYTES
            or hashlib.sha256(target.read_bytes()).hexdigest() != digest
        ):
            raise ValueError(
                f"{name}: existing file differs from the recorded original; not replaced."
            )
        return "verified existing file"
    content = bytearray()
    with client.stream("GET", url) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            if len(content) + len(chunk) > MAX_BYTES:
                raise ValueError(f"{name}: response exceeds 5 MB; nothing saved.")
            content.extend(chunk)
    if not content.startswith(b"%PDF-"):
        raise ValueError(f"{name}: publisher returned a non-PDF response; nothing saved.")
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError(f"{name}: publisher content changed; hash mismatch, nothing saved.")
    folder.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(content)
    return "downloaded and verified"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=PROJECT / "data" / "public-pdfs")
    args = parser.parse_args()
    try:
        with httpx.Client(
            timeout=60,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FreightLens-public-sample-check/0.1)"},
        ) as client:
            for name, url, digest in SOURCES:
                print(f"{name}: {download(client, args.directory, name, url, digest)}", flush=True)
    except (httpx.HTTPError, ValueError, OSError) as error:
        parser.exit(1, f"Download stopped: {error}\n")
    print(f"Saved under {args.directory.resolve()}. No model requests were made.")


if __name__ == "__main__":
    main()
