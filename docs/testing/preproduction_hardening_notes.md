# annotation_quality_filter pre-production hardening notes

This package applies the Stage 4 re-review fixes and makes the testing layer release-gate friendly.

## Closed blockers

- Removed divergent `TC-*` meanings by reserving `TC-*` for canonical manifest tests and renaming narrative-only testing-guide examples to `TG-*`.
- Fixed the stale upstream-failure fixture path: `F003` now consistently uses `docs/testing/fixtures/F003/stanza_annotation.json`.
- Split config schema-validation and config invariant fixtures:
  - `C001` = schema-valid override that fails effective invariant validation.
  - `C002` = schema-invalid override that fails user config schema validation.
- Replaced the ambiguous `TC-033` dual-error expectation with an explicit precedence test: unsupported schema version wins over upstream `status = failed`.
- Converted P0/P1 manifest entries from placeholder expectations into concrete fixture paths, normalized golden files, or expected assertion artifacts.

## New release-gate artifacts

- `docs/architecture/schema/annotation_quality_filter_expected_assertions.v2.0.schema.json`
- `docs/testing/expected_assertions/*.json`
- `docs/testing/tools/validate_test_contract_consistency.py`
- `docs/testing/fixtures/C002/quality_config.json`
- `docs/testing/fixtures/F006/stanza_failed_unsupported_schema.json`
- `docs/testing/fixtures/F007/schema_invalid_missing_document.json`
- `docs/testing/fixtures/B001/malformed_input.json`
- `docs/testing/fixtures/O001/quality_config.json`
- `docs/testing/fixtures/Q/**/stanza_annotation.json`

## Required pre-production checks

```bash
python docs/testing/tools/validate_embedded_config_blocks.py
python docs/testing/tools/validate_test_contract_consistency.py
```

A full schema/fixture validation pass should also validate:

- all JSON schemas as Draft 2020-12 schemas;
- registries against their schemas;
- the manifest against its schema;
- normalized expected outputs against `annotation_quality_filter.v2.0.schema.json`;
- expected assertion artifacts against `annotation_quality_filter_expected_assertions.v2.0.schema.json`;
- valid Stanza fixtures against `stanza_annotator.v2.0.schema.json`, excluding explicitly unsupported/schema-invalid fixtures;
- valid config fixtures against `annotation_quality_filter_config.v2.0.schema.json`, excluding explicitly schema-invalid config fixtures.
