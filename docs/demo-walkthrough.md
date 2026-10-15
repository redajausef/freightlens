# Reproduce the document-review demo

The repository contains actual, downloadable PDFs for three controlled shipment scenarios.
Their contents are **synthetic**: no real shipment, customer or signature is represented.
These packets demonstrate the upload/review/approval workflow. They do not establish accuracy
on unfamiliar business documents.

## 1. Start with a complete matching packet

Run FreightLens locally, open `http://127.0.0.1:8765`, and choose **New review**.
Save these three PDFs from the repository, then choose each file under its named document type:

| Document type | PDF |
|---|---|
| Rate confirmation | [Download](../samples/clean/rate_confirmation.pdf) |
| Carrier invoice | [Download](../samples/clean/invoice.pdf) |
| Proof of delivery | [Download](../samples/clean/proof_of_delivery.pdf) |

Choose **Review documents**. Expected result:

- Shipment `FL-1001`, carrier `Atlas Demo Transport`, Dallas to Houston.
- Agreed amount USD 2,000.00; invoice amount USD 2,000.00.
- Three supplied documents; no configured findings; status **Ready to review**.
- Selecting a field shows its supporting quote and source page text.
- Export is blocked until an employee supplies a name and review note and chooses **Approve record**.
- After approval, **Download approved record** returns the actual review JSON.

The built-in sample shortcut uses packaged text fixtures. Upload the linked PDF files to
demonstrate the PDF ingestion path. Identical uploads reuse their existing review, so a packet
previously approved under the current policy will reopen as approved rather than create a duplicate.

## 2. Show a billing discrepancy

| Document type | PDF |
|---|---|
| Rate confirmation | [Download](../samples/mismatch/rate_confirmation.pdf) |
| Carrier invoice | [Download](../samples/mismatch/invoice.pdf) |
| Proof of delivery | [Download](../samples/mismatch/proof_of_delivery.pdf) |

Upload all three in a new review. For `FL-1002`, the rate confirmation agrees USD 2,000.00,
but the invoice requests USD 2,300.00. Expect **Needs attention**, an `amount_mismatch`
finding for USD 300.00, and blocked approval/export. Compare each amount with its source quote.
Saving a note must not clear the discrepancy. A corrected packet starts a new review.

## 3. Show missing paperwork

| Document type | PDF |
|---|---|
| Rate confirmation | [Download](../samples/missing/rate_confirmation.pdf) |
| Carrier invoice | [Download](../samples/missing/invoice.pdf) |
| Proof of delivery | Deliberately absent |

Upload the two available PDFs. For `FL-1003`, expect **Needs attention**, a `missing_document`
finding for proof of delivery, readable evidence from the supplied documents and blocked approval.

The machine-readable scenario expectations are in
[samples/expected-results.json](../samples/expected-results.json).
The [recorded local verification](demo-validation.json) checks those expectations through
actual PDF uploads, including approval/export responses. It uses demo mode and makes zero
external model calls.

## Public documents with real industry layouts

The following are publisher-hosted references, checked on 2026-10-15. Original PDFs are linked
rather than bundled. Documentation includes attributed excerpts and rendered evaluation images.
Public availability does not establish a license to
republish, alter or brand a publisher's documents as our own.

| Source | What it provides | Appropriate use |
|---|---|---|
| [XPO billing help](https://www.xpo.com/help-center/billing-and-invoicing/where-to-send-payment/) | Links to sample electronic and paper freight-invoice PDFs | Layout reference; the linked sample was excluded from accepted ground truth for the reason below |
| [XPO sample electronic invoice PDF](https://www.xpo.com/cdn/files/s1/Blank_Invoice_PDF_USyMX.pdf) | One-page invoice template/sample | Caution: local rendering looked blank in populated regions while pypdf exposed populated text. Excluded from clean extraction ground truth pending visual/text reconciliation |
| [FedEx Freight shipping forms](https://www.fedexfreight.com/en-us/rate-ship/shipping/forms) | Official Bill of Lading forms and field guidance | Layout reference. A blank BOL is not completed proof of delivery |
| [FedEx Freight blank BOL PDF](https://www.fedexfreight.com/content/dam/web/us/documents/uniform-straight-bol.pdf) | Blank two-page shipping form | Missing-data/blank-form exercise, not a successful complete shipment packet |

An invoice, rate confirmation and delivery record downloaded independently should not be
presented as the same shipment. Different identifiers, companies, routes or dates can correctly
produce mismatches. No publicly verified matching three-document real shipment packet was found
in this research.

## Getting an authentic matched shipment packet

The strongest next dataset is a packet provided by a carrier, broker or logistics operator
with permission: rate confirmation, invoice and completed delivery record for the **same load**.
Use a consistent pseudonym/reference across the three files and remove private customer,
contact, signature, payment and account details before public sharing. Verify both rendered
pages and extracted text after anonymization. Keep the original authorized documents outside Git.

If no operator can supply one, create original realistic layouts using fictional details and
label them synthetic. Do not claim real-business usage. Include tables, multiple monetary
candidates, multiline addresses and missing/conflicting fields, then reserve unseen layouts
for evaluation rather than only testing the examples used during development.

## Provider and evaluation status

Current demo mode is a deterministic labeled-field parser. It is useful for the controlled
PDFs above and is not expected to understand arbitrary carrier layouts.

Gemini extraction is implemented. Set `FREIGHTLENS_PROVIDER=gemini`, configure the key and
model, and restart the server. The [external PDF evaluation](external-pdf-evaluation.md)
records actual uploads, corrections and the historical guide ambiguity failure. The current
[scope guard](field-confirmations.md) catches that guide before extraction. The optional
Kimi adapter has mocked tests only; see [configuration](configuration.md) for provider status.

Before an external-document accuracy claim:

1. Connect a working provider and run the controlled PDFs end to end.
2. Manually label expected fields and page evidence on unseen, permitted documents.
3. Compare extracted values, missing/incorrect fields, evidence support and discrepancy findings.
4. Record model/policy revisions, failures, latency and actual request count, not only a screenshot.
5. Test dates explicitly: checks accept ISO dates and unambiguous slash dates with four-digit
   years. Ambiguous order and two-digit years require review. Original evidence stays unchanged.
   Scanned/image-only PDFs need OCR in the current app.

Use fictional data with a free hosted API unless its data terms and the document owner's
permission support the intended use. Keep blank/scanned/unreadable cases as visible failures;
do not count them as successful extraction.

## Suggested short portfolio demonstration

Show the matching PDFs and evidence, then the USD 300 discrepancy and the missing POD. Finish
with an approved JSON download and explain which decisions belong to Python, the model and the
employee. State whether the run used the demo parser or a live provider and link to the recorded
results. This makes the demonstration reproducible without inventing accuracy or savings claims.
