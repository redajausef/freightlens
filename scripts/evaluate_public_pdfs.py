"""Run real multipart uploads against the app; --live explicitly enables Gemini calls."""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

CASES = [
    {
        "file": "wayfinder-rate-confirmation-188028.pdf",
        "kind": "rate_confirmation",
        "expected": {
            "shipment_reference": "188028",
            "carrier": "R A C TRANSPORT LLC",
            "pickup_location": "CARTERSVILLE",
            "delivery_location": "LOXLEY",
            "pickup_date": "9/24/2023",
            "delivery_date": "9/25/2023",
            "amount": "700.00",
            "currency": "USD",
        },
    },
    {
        "file": "rxo-rate-confirmation-14521900.pdf",
        "kind": "rate_confirmation",
        "expected": {
            "shipment_reference": "14521900",
            "carrier": "R A C TRANSPORT LLC",
            "pickup_location": "POLAND SPRING",
            "delivery_location": "North Bergen",
            "pickup_date": "02/23/24",
            "delivery_date": "02/24/24",
            "amount": "775.00",
        },
    },
    {"file": "fedex-express-invoice-guide.pdf", "kind": "invoice", "expected": {}},
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", type=Path, default=PROJECT / "data" / "public-pdfs")
    parser.add_argument("--live", action="store_true", help="Send extracted PDF text to Gemini")
    parser.add_argument("--output", type=Path, help="Result JSON; defaults to data/evaluations/")
    args = parser.parse_args()
    provider = "gemini" if args.live else "demo"
    if args.live:
        load_dotenv(PROJECT / ".env", override=False)
    result_dir = PROJECT / "data" / "evaluations"
    result_dir.mkdir(parents=True, exist_ok=True)
    db_path = result_dir / f"evaluation-{provider}.db"
    os.environ["FREIGHTLENS_DB"] = str(db_path)
    # Import after selecting the evaluation database, including the module-level app.
    from fastapi.testclient import TestClient

    from freightlens.api import create_app
    from freightlens.extraction import configured_model, normalized

    target = args.output or result_dir / f"public-pdf-{provider}-results.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    results = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "live_api": args.live,
        "model": configured_model(provider),
        "scope": "Two unrelated rate confirmations and one multi-invoice guide; no matched packet.",
        "cases": [],
    }
    with TestClient(create_app(db_path=db_path, provider=provider)) as client:
        for case in CASES:
            filename, kind = case["file"], case["kind"]
            content = (args.pdf_dir / filename).read_bytes()

            def upload():
                return client.post(
                    "/api/v1/reviews",
                    files={"files": (filename, content, "application/pdf")},
                    data={"kinds": kind},
                )

            print(json.dumps({"processing": filename, "provider": provider}), flush=True)
            response = upload()
            data = response.json()
            record = {
                "file": filename,
                "sha256": hashlib.sha256(content).hexdigest(),
                "document_kind": kind,
                "http_status": response.status_code,
                "created_in_this_run": response.status_code == 201,
            }
            if response.status_code in (200, 201):
                doc = data["documents"][0]
                record.update(
                    {
                        "review_id": data["id"],
                        "page_count": len(doc["pages"]),
                        "status": data["status"],
                        "fields": doc["fields"],
                        "warnings": doc["warnings"],
                        "issues": [
                            {
                                "code": issue["code"],
                                "field": issue["field"],
                                "message": issue["message"],
                            }
                            for issue in data["issues"]
                        ],
                        "elapsed_ms": data["elapsed_ms"],
                        "processing": data["processing"],
                    }
                )
                checks = {}
                for field, expected in case["expected"].items():
                    actual = doc["fields"].get(field, {}).get("value", "")
                    checks[field] = (
                        normalized(expected) in normalized(actual)
                        if field.endswith("_location")
                        else normalized(expected) == normalized(actual)
                    )
                if filename.startswith("rxo"):
                    checks["currency_not_inferred_from_dollar_symbol"] = (
                        "currency" not in doc["fields"]
                    )
                if kind == "invoice":
                    checks["multiple_examples_not_merged"] = doc["fields"] == {}
                record["manual_reference_checks"] = checks
                review_url = f"/api/v1/reviews/{data['id']}"
                record["approval_status"] = client.post(
                    review_url + "/approval",
                    json={"reviewer": "Evaluation", "note": "Test of blocked approval gate."},
                ).status_code
                record["export_status"] = client.get(review_url + "/export").status_code
                duplicate = upload()
                record["duplicate_status"] = duplicate.status_code
                record["same_review_reused"] = duplicate.json()["id"] == data["id"]
            else:
                record["error"] = data.get("detail", "Request failed")
            results["cases"].append(record)
            target.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            print(
                json.dumps(
                    {
                        "file": filename,
                        "status": response.status_code,
                        "values": {
                            key: evidence["value"]
                            for key, evidence in record.get("fields", {}).items()
                        },
                        "reference_checks": record.get("manual_reference_checks"),
                        "warnings": record.get("warnings"),
                        "error": record.get("error"),
                    }
                ),
                flush=True,
            )
            if response.status_code not in (200, 201):
                break
    print(str(target), flush=True)


if __name__ == "__main__":
    main()
