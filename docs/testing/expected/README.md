# Expected normalized outputs

This directory is reserved for golden files used by the testing guide.

Required files before the implementation can pass the 9+/10 gate:

- `F001_success.normalized.json`
- `F003_upstream_failed.normalized.json`
- `F004_unsupported_schema.normalized.json`
- `C001_invalid_config.normalized.json`
- `F001_quality_input_fingerprint.txt`

Golden snapshots must follow the normalization rules in `docs/testing/annotation_quality_filter_testing.md`.

## Checked-in minimal golden files

The second contract-hardening pass adds these concrete normalized golden files:

- `F001_success.normalized.json`
- `F003_upstream_failed.normalized.json`
- `F004_unsupported_schema.normalized.json`
- `C001_invalid_config.normalized.json`
- `F001_quality_input_fingerprint.txt`

These files are intentionally minimal and schema-valid. They are not full linguistic quality examples; they exist to make snapshot/golden-output tests executable before the implementation generates richer fixtures. Test normalization MUST set unstable runtime fields such as `annotation_quality.duration_ms` to `0.0` before comparing against these files.



## Fixture-derived golden policy

`F001_success.normalized.json` is fixture-derived. Its `document` field is the complete F001 `StanzaAnnotationResult` fixture aligned with chapter-level `text_annotation`, including top-level `diagnostics`, top-level `annotation`, sentence tokens, words, and both entity records. The expected fingerprint is `sha256:9affe824d23513289902324d9a65d9c04662d54a24421c720904257bc012a20b` and is duplicated in `F001_quality_input_fingerprint.txt`.


`docs/testing/expected_assertions/*.json` contains field-level assertion artifacts for registry-bound tests where exact full-output goldens would duplicate implementation-generated fingerprints/timestamps but exact public contract behavior is still testable.
