# Configuration and troubleshooting

Run commands from the repository root. Installation and offline startup are in the
[README](../README.md). Configuration is read from environment variables; `run.py` also
loads the root `.env` without overriding variables already set in your shell.

Copy the template on Windows:

```powershell
Copy-Item .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

Edit the local `.env`, then restart the server. Never paste a real key into a source file,
screenshot, issue or commit. `.env` and runtime `data/` are ignored by Git.

| Variable | Default | Purpose |
|---|---|---|
| `FREIGHTLENS_PROVIDER` | `demo` | `demo`, `gemini` or `kimi` |
| `GEMINI_API_KEY` | Empty | Your Google API key; required in Gemini mode |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Model ID sent to the Gemini API |
| `NVIDIA_API_KEY` | Empty | Your NVIDIA API key; required in Kimi mode |
| `KIMI_MODEL` | `moonshotai/kimi-k3` | Model ID sent to the optional NVIDIA adapter |
| `FREIGHTLENS_DB` | `data/freightlens.db` | SQLite path, relative to the working directory unless absolute |

## Providers

**Demo:** offline parser for exact labeled fields such as `Amount: 2000.00`. It makes no
network requests. Built-in fictional packets demonstrate checks, review and approval.
It cannot extract arbitrary carrier layouts.

**Gemini:** set `FREIGHTLENS_PROVIDER=gemini`, configure your own key and model, restart,
and check that the interface displays **Gemini API**. Uploading documents sends numbered
page text to Google's API, not the original PDF bytes. The application checks the returned
fields and evidence before running business rules. See the recorded
[live evaluation](external-pdf-evaluation.md); availability, quota and billing depend on
your Google project. The application does not change project billing settings.

**Kimi:** optional adapter through NVIDIA's hosted API. Set `FREIGHTLENS_PROVIDER=kimi`
and configure `NVIDIA_API_KEY` and `KIMI_MODEL`. This adapter has mocked tests, not a
successful live account-key evaluation. Check availability in your provider account before
using it; the recorded development notes reported endpoint deprecation. Gemini is the
provider used in this repository's live PDF evidence.

Provider errors remain visible. The application does not silently switch providers or
pretend the offline parser is AI extraction.

## Reproduce the public PDF evaluation

```powershell
.\.venv\Scripts\python.exe scripts/download_public_samples.py
.\.venv\Scripts\python.exe scripts/evaluate_public_pdfs.py --pdf-dir data/public-pdfs
```

The second command is an offline baseline. Add `--live` explicitly to use Gemini and your
API quota. Use `.venv/bin/python` on macOS/Linux. Downloads are unmodified publisher files
checked against recorded SHA-256 hashes. A changed or unavailable publisher file fails
visibly rather than becoming a new reference result.

New evaluations write to ignored `data/evaluations/`; they do not overwrite the committed
historical results in `docs/`. `--output path/to/results.json` chooses another result file.
Identical packets reuse an existing review for the same provider/model/policy, so a
rerun may read cached extraction. The result records whether a review was newly created.

## Common issues

| Symptom | Action |
|---|---|
| API key missing or rejected | Check the provider/key in your local environment and restart. Do not share the key in a bug report. |
| Provider quota/rate-limit error | Check your project's quota and retry when available. The app does not enable paid billing or bypass limits. |
| Port 8765 already in use | Stop the earlier FreightLens process. `run.py` binds to `127.0.0.1:8765`. |
| PDF has no readable text | Use a text-bearing PDF. OCR for scans is not implemented. |
| pypdf prints a fontTools warning | Some embedded PDF fonts need optional `fonttools` support. Compare the visible page with extracted text; do not accept unreadable fields. The recorded FedEx guide still triggered the scope block in the clean environment. |
| Upload rejected | Maximum 3 files, one per document type; 5 MB and 12 pages per file, 60,000 extracted characters. Use PDF or UTF-8 text. |
| Missing invoice/POD | Upload a new packet with the matching separate document. A note cannot clear missing paperwork. |
| Ambiguous currency or date | Use **Clarify this field** with the verified value, source page, exact quote, name and reason. Other discrepancies remain blocked. |
| Wrong amount/reference/carrier | Supply a corrected source packet in a new review; those fields do not support manual confirmation. |
| Older review cannot be approved | Use the displayed recheck action when compatible. A changed extraction policy requires a fresh upload. |
| Clean packet cannot be exported | Supply a name and review note and explicitly approve it first. |
| Confirmation rejected as stale | Reload the review and inspect its latest revision before trying again. |

Original PDF bytes are not retained after ingestion. The SQLite record stores extracted
page text, accepted fields, findings, confirmations and history. Treat the database as
potentially sensitive when using your own documents. Keep the server on loopback; hosted
authentication and verified employee identities are outside this prototype's scope.
