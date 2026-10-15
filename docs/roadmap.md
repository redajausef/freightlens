# Roadmap

## Milestone 1 — local foundation

- [x] Python modules, typed contracts, API and local interface.
- [x] Synthetic rate/invoice/delivery packets in text and PDF.
- [x] Offline workflow and Kimi HTTP adapter with simulated-provider tests.
- [x] Evidence grounding and deterministic checks.
- [x] SQLite persistence, employee notes, blocked approval, approved JSON export.
- [x] Architecture PNG/SVG, README, Java-to-Python guide and CI configuration.
- [x] ECC architecture/security audit, regression fixes, versioned provenance and legacy recheck gate.
- [x] Streamed request-body limit, multipart cleanup regression and application type checks.

## Milestone 2 — establish live extraction quality

- [x] Connect Gemini and record live API uploads of public PDFs, including failure cases.
- [x] Add conservative guide-cover and distinct labeled invoice-ID checks before extraction.
- [ ] Evaluate document-scope checks across broader guides, bundles and unfamiliar layouts.
- [ ] Build a separately labeled dataset of approximately 30 shipment packets with varied layouts.
- [ ] Include missing fields, ambiguous totals, poor scans, conflicting references and adversarial text.
- [ ] Measure field accuracy, discrepancy precision/recall, failures, latency and token usage.
- [x] Record this small development set separately from deterministic demo checks.
- [ ] Add OCR with page provenance for scanned PDFs.
- [x] Add audited currency/date confirmations with source checks and automatic revalidation.
- [ ] Expand correction workflows to other fields and document replacement when needed.

## Milestone 3 — business integration and portfolio finish

- [ ] Add a clearly labeled mock operations API and approval-gated webhook delivery.
- [ ] Implement retry and idempotency at the integration boundary.
- [ ] Detect duplicate invoice identities across different packets.
- [ ] Add authenticated users and roles before hosted multi-user access.
- [ ] Add bounded worker jobs, parser process limits, operational metrics and retention controls.
- [ ] Record a three-minute English walkthrough and practice a supervised live code change.
- [ ] Create a GitHub repository and publish the reviewed code when requested.

Keep the company knowledge assistant as a later project. Complete and measure this workflow first.
