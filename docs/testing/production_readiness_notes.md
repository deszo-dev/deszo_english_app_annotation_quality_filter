# annotation_quality_filter Production Readiness Notes

This package closes the Stage 5 pre-production gaps by converting the remaining broad testing expectations into machine-readable production release gates.

Production-level additions:

- `annotation_quality_filter_expected_assertions.v2.0.schema.json` now models exact quality assertions: scope, text-unit/sentence/entity ids, issue entities, score, band, risk level, warning/error counts, and summary paths.
- All P0/P1 registry-bound quality issue tests under `docs/testing/expected_assertions/` include `expected_quality_assertions`.
- P2 quality issue tests were also upgraded to the same exact assertion format to avoid a future second hardening pass.
- `contract_test_manifest.v2.0.json` defines non-registry release-gate tests for scoring boundaries, half-even rounding, CLI output preflight, CLI usage errors, API programmer errors, API no-mutation behavior, determinism, and input-size boundaries.
- `validate_expected_assertions.py` validates assertion artifact strength and can also apply one assertion artifact to an actual implementation output using `--expected` and `--actual`.

Required production release-gate commands:

```bash
python docs/testing/tools/validate_embedded_config_blocks.py
python docs/testing/tools/validate_test_contract_consistency.py
python docs/testing/tools/validate_expected_assertions.py
```

The package is considered production-doc ready only when all three commands pass and all checked JSON/JSON Schema artifacts validate offline through `schema_catalog.v2.0.json`.
