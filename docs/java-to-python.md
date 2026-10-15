# Read the code as a Java developer

Start with one request: upload a synthetic invoice and rate confirmation, then trace it.

| Familiar Java concept | Where to look in FreightLens |
|---|---|
| Spring controller | FastAPI routes in `api.py` |
| DTO + Bean Validation | Pydantic models in `models.py` |
| Service class | The workflow function in `service.py` |
| Repository + JDBC | Parameterized SQLite queries in `repository.py` |
| Interface | `Extractor` protocol in `extraction.py` |
| Strategy implementations | `DemoExtractor`, `GeminiExtractor` and `KimiExtractor` |
| BigDecimal | Python `Decimal` in `parse_money` |
| JUnit / parameterized tests | pytest tests and `@pytest.mark.parametrize` |
| try-with-resources | Python `with` blocks and context managers |
| Maven/Gradle dependencies | `pyproject.toml` and pip |

## Suggested learning sequence

1. Open `models.py`: explain the difference between `Document`, `Evidence`, and `Review`.
2. Open `rules.py`: follow the USD 2,000 vs USD 2,300 comparison. Explain why `float` is avoided.
3. Run `pytest tests/test_rules.py -q` and change one sample amount. Predict the result first.
4. Follow `service.create_review`: reading, extracting, grounding, checking, saving.
5. Compare the extractors. Explain what the demo parser cannot do and where Gemini sends page text.
6. Trace approval through the API and repository transaction. Try approving a mismatched packet.
7. Add one rule yourself, with a test that fails before the change and passes afterward.
8. Trace a currency/date confirmation from `confirmations.py` through validation, rechecking
   and the repository transaction. Explain why the original AI field remains unchanged.
9. Read `scope.py`: explain why a detected invoice guide is blocked before a model call,
   and why a heuristic cannot identify every unsupported document.

## Practical interview exercises

- Require `invoice_number` and show what happens when it is missing.
- Explain why matching currency matters before comparing amounts.
- Add a configurable amount tolerance using `Decimal`; include tests at the boundary.
- Handle a provider rate limit without claiming extraction succeeded.
- Explain why an exact source quote can still refer to the wrong field.
- Explain what authentication and review identity must change before real deployment.

Describe Codex/ECC assistance honestly. Demonstrate that you can predict behavior, debug a failure,
and implement a small change without blindly accepting generated code.
