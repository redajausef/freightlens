# Third-party material and provenance

FreightLens's example companies and shipment packets under `samples/` and packaged
`static/samples/` are fictional workflow fixtures. They are labeled synthetic and do not
represent completed customer work.

## Public freight documents

The following publisher-hosted files were downloaded unchanged for local development
evaluation on 2026-10-15. Original PDF files are not bundled in the source repository.
The download helper verifies their recorded hashes.

| Document | Publisher-hosted source | SHA-256 |
|---|---|---|
| Wayfinder rate confirmation, load 188028 | [GroupRAC](https://www.grouprac.com/Documents/188028Rate%20Confirmation.pdf) | `214319cf1e30de49f6b79dca890e1ece375136afb61124ea376c74935fadeb5b` |
| RXO rate confirmation, load 14521900 | [GroupRAC](https://www.grouprac.com/Documents/14521900Rate%20Confirmation.pdf) | `2125def04753e6a719579b8cbdcaee8ed8c669c52810c5749abebb319667ec85` |
| FedEx Express invoice explanation guide | [FedEx](https://www.fedex.com/content/dam/fedex/international/o2p/pdf/fedex-express-invoice-explanation-master-template-en-gb.pdf) | `186b84adc0c3ae0781518f995595e85c93cf2f1248f86b5238c62bc26cd7d84c` |

Documentation includes a rendered source page, quotations, extracted values and
application screenshots to explain the evaluation. Document content, company names and
marks remain attributable to their respective owners. Public hosting is not treated as
an open-source license or endorsement. The two rate confirmations are unrelated shipments;
the FedEx file is an explanatory guide, not a completed invoice for either shipment.

Other linked XPO/FedEx forms in the walkthrough are layout references. They are not part
of the accepted real-document ground truth. Source/interpretation limitations are recorded
in [the evaluation](docs/external-pdf-evaluation.md).

## Software and services

Runtime and development dependencies are declared in `pyproject.toml` and pinned for the
tested environment in `requirements-dev.lock`. Their licenses remain with their respective
projects; these notices do not replace dependency license terms.

Gemini and the optional NVIDIA-hosted Kimi adapter use the account holder's provider
credentials and service terms. No provider credential is included. Codex and ECC assisted
development; ECC is not bundled as a FreightLens runtime dependency. The interface uses
system fonts and inline SVG icons, with no external icon/font service required at runtime.
