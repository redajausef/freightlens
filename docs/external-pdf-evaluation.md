# Live evaluation with external freight PDFs

**Historical inference run:** the results below describe policy `2026-10-15.3`. Policy
`2026-10-15.4` adds source-checked employee currency/date confirmations and a preflight
guard that catches this FedEx guide before a new model call. See the
[subsequent implementation and verification](field-confirmations.md). The original live
results remain unchanged for comparison.

On 15 October 2026, the original downloaded PDFs were uploaded through FreightLens's
multipart review API using Gemini `gemini-3.1-flash-lite`. No PDF contents were edited.

The result is promising for the two rate confirmations, with a remaining failure on a
multi-invoice guide. This is a three-document development check, not a production benchmark.
The prompts and date checks were changed after the first run; these are not held-out examples.

| Document | Checked result | Remaining review items |
|---|---|---|
| Wayfinder, load 188028 | All 8 checked fields matched: load, carrier, both locations, both dates, USD 700.00 and currency. Rate evidence is on page 3. | Invoice and signed delivery record were not supplied. |
| RXO, load 14521900 | All 7 checked fields matched: load, carrier, both locations, both raw dates and 775.00 carrier pay. | Currency is only a dollar symbol; USD is not inferred. Dates use two-digit years. Invoice and delivery record were not supplied. |
| FedEx invoice guide | Upload succeeded and review/approval/export stayed blocked. | Ambiguity check failed in the rerun: partial fields from an example invoice were returned. No single invoice should be chosen from this guide. |

Across the two rate confirmations, 15 manually checked field values matched in the final
run. This limited result does not measure general accuracy or complete address accuracy:
the automated location comparison checks the expected city text; supporting quotes were
also inspected against the source. The FedEx guide is a negative case, not a successful
standalone invoice extraction. There is no matching invoice/rate/POD packet in this download.

## What the tests uncovered and what changed

1. **The demo parser was insufficient.** It found only the carrier in Wayfinder and no
   fields in RXO. The new Gemini connector performs real model extraction with JSON Schema,
   bounded responses, fixed endpoint/header authentication, safe errors and no paid fallback.
2. **Dates were too restrictive.** Wayfinder's `9/24/2023` and `9/25/2023` were grounded
   correctly but rejected by ISO-only validation. Unambiguous slash dates with four-digit
   years now validate without changing the original evidence. `02/23/24` remains for human
   review; the application does not invent a century. `03/04/2024` remains ambiguous.
3. **Address reconstruction failed grounding.** The first RXO extraction returned unsupported
   address evidence. Instructions now require contiguous verbatim address blocks. Both
   locations passed their source checks on the rerun. Grounding was not weakened.
4. **Guide ambiguity remains unresolved.** The first model run returned no fields, but a
   second run selected partial fields from an invoice example. Unsupported invoice and
   shipment identifiers were discarded. Required-field checks blocked the result, but this
   is not reliable document-scope classification. A robust classifier/bundle workflow is
   still needed before this kind of input is supported.

All three final reviews are `needs_review`. Approval and export requests returned HTTP 409.
Identical repeat uploads returned the original review with HTTP 200. This validates sequential
reuse; concurrent requests are not guaranteed to make only one model call.

## Reproduce

Download the same original PDFs into a folder and use the exact filenames in the source list
below. From the project folder:

```powershell
# Offline baseline: no AI calls.
python scripts/evaluate_public_pdfs.py --pdf-dir ../external-freight-pdfs

# Explicit live Gemini test; requires a locally configured key.
python scripts/evaluate_public_pdfs.py --pdf-dir ../external-freight-pdfs --live
```

The script uses separate SQLite files under `data/evaluation-demo.db` and
`data/evaluation-gemini.db`. Set `FREIGHTLENS_DB=data/evaluation-gemini.db` to inspect the
live results in the interface. Identical files with the same provider/model/pipeline revision
reuse their stored result; changing that revision triggers fresh model calls.

- [Final live results and source quotes](external-pdf-live-results.json)
- [Initial live results before the fixes](external-pdf-initial-results.json)
- [Offline parser baseline](external-pdf-baseline.json)

Six document extraction jobs were submitted across two development passes. Transport retries
and token usage were not instrumented, and project billing was not inspected. No billing
settings were changed. Google lists a free tier for the selected model in its
[pricing documentation](https://ai.google.dev/gemini-api/docs/pricing).

## Original public sources

- [Wayfinder rate confirmation hosted by GroupRAC](https://www.grouprac.com/Documents/188028Rate%20Confirmation.pdf)
- [RXO rate confirmation hosted by GroupRAC](https://www.grouprac.com/Documents/14521900Rate%20Confirmation.pdf)
- [FedEx official invoice guide](https://www.fedex.com/content/dam/fedex/international/o2p/pdf/fedex-express-invoice-explanation-master-template-en-gb.pdf)

The PDFs remain outside the project source archive. Their hashes are recorded in the final
results, and the download pack contains its original-source manifest.

## Engineering verification

The regression suite covers Gemini authentication/endpoint boundaries, missing credentials,
rate limits, transient errors, blocked/truncated/invalid responses, prompt-injection text,
schema violations, safe failures, and date ambiguity/chronology. The full suite passed
117 tests with 97.48% coverage during this change. These automated tests are separate from
the three live document checks and do not measure model accuracy.
