# Review FreightLens in five minutes

Start with the [README](../README.md) for installation. No API key is required for the
complete synthetic workflow. The demo parser is deterministic; Gemini is the real AI path.

## 1. See the business behavior

1. Run `python run.py` from the repository root using the installed virtual environment.
2. Open `http://127.0.0.1:8765` and choose **New review**.
3. Load the matching fictional sample. Inspect an amount and its supporting page text.
4. Supply a reviewer name and note, approve, and download the approved JSON.
5. Try the charge-mismatch sample. The USD 300.00 difference blocks approval.
6. Try the missing-delivery-record sample. A missing POD also blocks approval.

For the actual PDF ingestion path, upload the files linked in the
[sample walkthrough](demo-walkthrough.md). Sample shortcuts use packaged text fixtures.

## 2. Inspect the real-document evidence

The [public PDF walkthrough](public-pdf-demo.md) shows the unchanged source PDF, saved Gemini
extraction, page evidence and blocked approval. Two unrelated public rate confirmations
produced 15 matching checked values in the recorded development run. This is a small,
manually checked set, not an accuracy benchmark.

The invoice/POD blocks mean that those separate documents were not uploaded. They do not
mean an invoice or POD should appear inside a rate confirmation. RXO's dollar symbol and
two-digit years also require an employee's interpretation under the current policy.

The [confirmation workflow](field-confirmations.md) explains how source-supported currency
or dates can be clarified without replacing the original AI extraction. A separate
simulation reduced the RXO copy from five findings to two; the missing documents still
prevented approval. The actual public review was not changed by those assumptions.

## 3. Trace the code

Paths below are relative to `src/freightlens/`.

| Question | Implementation | Useful test |
|---|---|---|
| How does a PDF become numbered text? | `ingestion.py` | `tests/test_ingestion.py` |
| How are model fields grounded in source text? | `extraction.py` | `tests/test_extraction.py` |
| Who decides whether amounts and dates agree? | `rules.py` | `tests/test_rules.py` |
| How are employee corrections recorded? | `confirmations.py`, `service.py` | `tests/test_confirmations.py` |
| How is an invoice guide blocked? | `scope.py` | `tests/test_scope.py` |
| What prevents premature approval/export? | `api.py`, `repository.py` | `tests/test_workflow.py` |

See the [architecture](architecture.md) for routes and storage, and the
[Java-to-Python tour](java-to-python.md) for familiar controller/service/repository concepts.

## 4. Assess reliability and scope

[Local verification](verification.md) records the automated and browser checks. GitHub CI
is configured but has not run yet. Reviewer names are self-reported; this is a single-user
local prototype. Scans need OCR, source quotes do not prove semantic correctness, and no
external business actions are executed. The [roadmap](roadmap.md) separates implemented
features from future work.

Codex and ECC assisted development. The project is intended to support a code walkthrough
and live modification, not imply unaided authorship or existing customer deployment.
