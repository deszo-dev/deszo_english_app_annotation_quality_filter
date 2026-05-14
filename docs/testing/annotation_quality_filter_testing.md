# annotation_quality_filter testing guide v2.0

This guide defines the contract tests for `annotation_quality_filter.v2.0` after alignment with the current `stanza_annotator.v2.0` output shape.

## 1. Fixture policy

All fixtures MUST validate before behavior assertions run.

Required schema checks:

```text
docs/testing/fixtures/**/stanza_annotation.json
  -> docs/architecture/schema/stanza_annotator.v2.0.schema.json
  except explicitly unsupported-version fixtures such as `fixtures/F004/stanza_annotation.json` and `fixtures/F006/stanza_failed_unsupported_schema.json`, which are JSON-parse-only and MUST short-circuit at the schema-version check before consumed-schema validation. Explicitly schema-invalid fixtures such as `fixtures/F007/schema_invalid_missing_document.json` are JSON-parse-only and are used only by invalid-input tests

docs/testing/expected/*.normalized.json
  -> docs/architecture/schema/annotation_quality_filter.v2.0.schema.json

docs/testing/fixtures/**/quality_config.json
  -> docs/architecture/schema/annotation_quality_filter_config.v2.0.schema.json
  except intentionally schema-invalid config fixtures such as `fixtures/C002/quality_config.json`, which are JSON-parse-only and MUST fail with `config_schema_validation_failed`

Resolved effective configs produced by tests
  -> docs/architecture/schema/annotation_quality_filter_effective_config.v2.0.schema.json
```

The consumed Stanza schema intentionally rejects legacy chapter paragraph annotations. A fixture containing `document.book.chapters[].paragraphs` is invalid for this module.

Malformed CLI byte fixtures such as `fixtures/B001/malformed_input.json` are intentionally not valid JSON. They are used only by JSON-parse failure tests and MUST NOT be included in generic JSON-parse-all fixture checks.

Front/back matter `section.paragraphs[]` may appear as structural pass-through data, but those paragraph objects MUST NOT contain `annotation`, `annotation_status`, `text_annotation`, `title_annotation`, `skip_reason`, or `skipped_reason`.


### 1.0.1 Offline schema resolution

All schema validation MUST be offline. Test harnesses MUST register every checked-in schema by `$id` using `docs/architecture/schema/schema_catalog.v2.0.json` before validation. Network retrieval of schemas is forbidden and counts as a test failure.

Required catalog entries include:

```text
https://deszo.local/schema/annotation_quality_filter.v2.0.schema.json
https://deszo.local/schema/annotation_quality_filter_config.v2.0.schema.json
https://deszo.local/schema/annotation_quality_filter_effective_config.v2.0.schema.json
https://deszo.local/schema/annotation_quality_filter_diagnostics.v2.0.schema.json
https://deszo.local/schema/annotation_quality_filter_error_registry.v2.0.schema.json
https://deszo.local/schema/annotation_quality_filter_issue_registry.v2.0.schema.json
https://deszo.local/schema/stanza_annotator.v2.0.schema.json
```

### 1.0.2 Registry-to-test traceability

Every test ID referenced by `docs/architecture/registry/*.json` MUST be defined in this guide or in `docs/testing/test_manifest.v2.0.json`.

A registry test reference is valid only when the matching definition contains a stable test ID, purpose, requirement reference, exact fixture/config, execution mode, expected result, expected diagnostic or issue codes, and assertions.

CI MUST fail when:

- a registry `tests[]` entry has no matching test definition;
- a P0/P1 test definition has no fixture or inline complete input;
- a P0/P1 test definition has no expected result, expected diagnostics and assertions;
- a test asserts behavior not supported by module documentation.

### 1.0.3 Test ID namespace and uniqueness

Test IDs are stable public testing identifiers.

`TC-*` IDs are reserved for canonical registry-bound tests defined in `docs/testing/test_manifest.v2.0.json`. Narrative examples in this Markdown guide MUST NOT reuse a `TC-*` ID unless they describe exactly the same purpose, fixture/config, execution mode, expected result, expected diagnostics/issues, and assertions as the manifest entry with that ID.

Narrative-only scenarios MUST use the `TG-*` prefix, for example `TG-TRAV-001` or `TG-CLI-001`.

CI MUST fail when the same test ID appears in more than one place with different title, purpose, fixture/config, expected result, or expected diagnostics/issues.

### 1.0.4 Expected assertion artifacts

A manifest `expected_result` may point either to a normalized golden result under `docs/testing/expected/*.normalized.json` or to a field-level assertion artifact under `docs/testing/expected_assertions/*.json`.

Expected assertion artifacts MUST validate against `docs/architecture/schema/annotation_quality_filter_expected_assertions.v2.0.schema.json` and are used when the exact full output depends on implementation timestamps or generated fingerprints but the public contract can still be tested with exact fixture/config/code/score assertions.

For every P0/P1 `quality_issue` manifest entry, the assertion artifact MUST include `expected_quality_assertions[]` with exact `scope`, `text_unit_id`, `sentence_id` or `entity_id`, `expected_issue_codes`, `expected_issue_entities`, `expected_score`, `expected_band`, `expected_risk_level` when applicable, warning/error counts, and summary assertions. Generic prose such as “apply registry scoring rules” is not sufficient for release.

Non-registry production contract tests are defined in `docs/testing/contract_test_manifest.v2.0.json`. This manifest covers scoring boundaries, rounding, API behavior, CLI filesystem behavior, determinism, and limit boundary behavior that are not owned by a single registry code.

## 1.1 Complete default effective config fixture

```json
{
  "thresholds": {
    "high": 0.8,
    "medium": 0.6,
    "low": 0.3
  },
  "weights": {
    "structural": 0.3,
    "dependency": 0.35,
    "morphology": 0.15,
    "sentence": 0.1,
    "distribution": 0.1
  },
  "limits": {
    "max_sentence_length": 60,
    "long_sentence_soft": 40,
    "long_sentence_hard": 80,
    "max_conj_ratio": 0.3,
    "severe_conj_ratio": 0.5,
    "max_noun_ratio": 0.6,
    "max_deprel_ratio": 0.5,
    "max_output_json_bytes": 10485760,
    "max_input_json_bytes": 52428800,
    "max_json_depth": 200
  },
  "checks": {
    "enable_structural": true,
    "enable_dependency": true,
    "enable_morphology": true,
    "enable_sentence": true,
    "enable_distribution": true,
    "enable_entity": true,
    "validate_text_slices": true
  },
  "include_debug": false,
  "logging": {
    "enabled": false,
    "level": "error"
  }
}
```

## 1.2 User override config fixtures

The user config schema is partial. These overrides MUST validate against `annotation_quality_filter_config.v2.0.schema.json`:

```json
{}
```

```json
{"include_debug": true}
```

```json
{"limits": {"max_output_json_bytes": 1048576}}
```

The following override MUST fail because unknown nested fields are invalid:

```json
{"limits": {"unknown_limit": 123}}
```

The following override MUST pass user schema validation but fail effective invariant validation with `invalid_config` and helper diagnostic `config_invariant_failed`:

```json
{"thresholds": {"low": 0.9, "medium": 0.6, "high": 0.8}}
```

## 2. Minimal valid Stanza input shape

```json
{
  "schema_version": "stanza_annotator.v2.0",
  "status": "succeeded",
  "document": {
    "source": {
      "source_id": "src-001",
      "filename": "tiny.epub",
      "fingerprint": "bookfp001"
    },
    "book": {
      "id": "book-001",
      "title": "Tiny Book",
      "language": "en",
      "front_matter": [],
      "chapters": [
        {
          "id": "ch1",
          "chapter_number": 1,
          "type": "chapter",
          "title": "Chapter 1",
          "text": "Alice sees Bob.",
          "text_annotation_status": "annotated",
          "text_annotation": {
            "text_unit_id": "ch1:text",
            "ref": {
              "kind": "chapter_text",
              "text_unit_id": "ch1:text",
              "owner_type": "chapter",
              "owner_id": "ch1",
              "source_field": "text"
            },
            "text": "Alice sees Bob.",
            "sentences": [],
            "entities": [],
            "summary": {
              "sentence_count": 0,
              "token_count": 0,
              "word_count": 0,
              "entity_count": 0
            }
          },
          "footnotes": []
        }
      ],
      "back_matter": [],
      "footnotes": []
    }
  },
  "diagnostics": [],
  "annotation": {
    "annotator_version": "2.0.0",
    "stanza_schema_version": "stanza_annotator.v2.0",
    "annotation_input_fingerprint": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "summary": {
      "text_unit_count": 1,
      "annotated_text_unit_count": 1,
      "skipped_text_unit_count": 0,
      "chapter_count": 1,
      "sentence_count": 0,
      "token_count": 0,
      "word_count": 0,
      "entity_count": 0,
      "warning_count": 0,
      "error_count": 0
    }
  }
}
```

## 3. Traversal tests

### TG-SCENARIO-001: Valid chapter text annotation

Input fixture: `docs/testing/fixtures/F001/stanza_annotation.json`.

Expected output: `docs/testing/expected/F001_success.normalized.json`.

Assertions:

- result status is `succeeded`;
- `output.document` is deep-equal to input Stanza result;
- exactly one `quality.text_units[]` record is emitted;
- `quality.text_units[0].text_unit_id == "ch1:text"`;
- `quality.text_units[0].ref.kind == "chapter_text"`;
- `quality.text_units[0].ref.owner_type == "chapter"`;
- `quality.text_units[0].evaluation_status == "evaluated"`;
- sentence and entity quality counts match the upstream `text_annotation` arrays.

### TG-SCENARIO-002: Full structured traversal order

Input fixture: `docs/testing/fixtures/F002/stanza_annotation.json`.

Expected refs: `docs/testing/expected/F002_expected_text_unit_refs.json`.

The implementation must discover represented units in this order:

1. front matter section title;
2. front matter section text;
3. front matter footnotes;
4. chapter title;
5. chapter text;
6. chapter footnotes;
7. back matter section title;
8. back matter section text;
9. back matter footnotes;
10. book-level footnotes.

Expected quality refs use only these `kind` values:

```text
chapter_text
section_text
chapter_title
section_title
footnote
```

Legacy ref kinds such as `chapter_paragraph`, `front_matter_paragraph`, and `back_matter_paragraph` MUST NOT appear.

### TG-SCENARIO-003: Skipped represented unit coverage

Create a Stanza fixture with:

```json
{
  "text": "",
  "text_annotation_status": "skipped",
  "text_skipped_reason": "empty_text"
}
```

Assertions:

- one `TextUnitQuality` coverage record is emitted;
- `evaluation_status == "not_evaluated"`;
- `not_evaluated_reason == "empty_text"`;
- `sentence_quality == []`;
- `entity_quality == []`.

### TG-SCENARIO-004: Section paragraphs are structural only

Create a front matter section with `paragraphs[]` containing plain `id`, `paragraph_number`, and `text` fields, plus a section-level `text_annotation`.

Assertions:

- the section text annotation is evaluated as `ref.kind == "section_text"`;
- structural paragraph text is preserved in `output.document`;
- no quality record is keyed to a paragraph id;
- any paragraph object carrying an `annotation` field fails Stanza consumed-schema validation.

## 4. Failure tests

### TG-SCENARIO-005: Upstream Stanza failure

Input fixture: `docs/testing/fixtures/F003/stanza_annotation.json`.

This fixture MUST validate against the consumed Stanza schema before behavior assertions run. Failed upstream Stanza results must still include the minimal public envelope: `schema_version`, `status`, `diagnostics`, `annotation.summary`, and `error`.

Expected output: `docs/testing/expected/F003_upstream_failed.normalized.json`.

Expected:

- result `status == "failed"`;
- `error.code == "upstream_stanza_annotation_failed"`;
- diagnostic helper `upstream_failure_status_seen` at `/status`;
- no `document`;
- no `quality`;
- CLI exit code `1`.

### TG-SCENARIO-006: Unsupported Stanza schema

Input fixture: `docs/testing/fixtures/F004/stanza_annotation.json`, with `schema_version = "stanza_annotator.v1.0"`.

Expected:

- `status == "failed"`;
- `error.code == "unsupported_stanza_schema"`;
- diagnostic helper `unsupported_input_schema_version`;
- diagnostic path is `/schema_version`;
- CLI exit code `1`.

### TG-SCENARIO-007: Legacy chapter paragraphs are invalid

Input contains:

```json
{
  "document": {
    "book": {
      "chapters": [
        {
          "id": "ch1",
          "chapter_number": 1,
          "type": "chapter",
          "text": "Alice sees Bob.",
          "text_annotation_status": "skipped",
          "text_skipped_reason": "excluded_by_config",
          "paragraphs": [
            {
              "id": "ch1:p1",
              "text": "Alice sees Bob.",
              "annotation_status": "annotated",
              "annotation": {}
            }
          ],
          "footnotes": []
        }
      ]
    }
  }
}
```

Expected:

- consumed Stanza schema validation fails;
- document API returns `error.code == "invalid_input"`;
- no traversal is attempted.

### TG-SCENARIO-008: Invalid config

Input fixture: `docs/testing/fixtures/F001/stanza_annotation.json`.

Config fixture: `docs/testing/fixtures/C001/quality_config.json`.

Use `docs/testing/expected/C001_invalid_config.normalized.json` as the normalized expected failed result.

Expected:

- `error.code == "invalid_config"`;
- diagnostic helper `config_invariant_failed`;
- diagnostic path is `/thresholds`;
- exit code `4` in CLI mode when JSON output channel is available.

## 5. Quality checks

For every evaluated text unit, tests must cover:

- valid sentence span and source-slice match;
- invalid sentence span;
- token span outside sentence/source text;
- word span outside sentence/source text;
- missing token-to-word reference;
- invalid dependency head;
- `head_word_id` mismatch;
- zero dependency roots;
- multiple dependency roots;
- disconnected dependency tree;
- missing/empty morphology where morphology is expected;
- entity span outside text-unit bounds;
- entity text mismatch.

Malformed deltas should patch paths under current Stanza locations, for example:

```text
/document/book/chapters/0/text_annotation/sentences/0/words/0/head_word_id
/document/book/front_matter/0/text_annotation/sentences/0/end_char
/document/book/footnotes/0/annotation/entities/0/end_char
```

Paths under chapter `paragraphs` are invalid for v2.0 tests.


### 5.1 Deterministic scoring issue fixtures

Every P0/P1 quality issue fixture MUST assert the exact issue code, scope, score, band, risk level where applicable, warning/error counts, and summary aggregation.

Minimum issue fixtures:

| Test ID | Fixture intent | Required issue | Required score assertion |
|---|---|---|---|
| `TG-SCORE-010` | sentence text differs from source slice | `SENTENCE_TEXT_MISMATCH` | subtract registry penalty from `structural` family and recompute weighted score |
| `TG-SCORE-011` | no dependency root | `NO_ROOT` | sentence score `0.0`, band `invalid`, risk `critical` |
| `TG-SCORE-012` | disabled family removes denominator | family-specific penalty in disabled family | score ignores disabled family and denominator |
| `TG-SCORE-013` | score exactly equals threshold boundary | none or controlled penalty | lower-bound inclusive band mapping |
| `TG-SCORE-110` | mean rounding half-even | multiple sentence scores | exact 6-decimal arithmetic mean |

Scoring tests MUST derive expected scores from `annotation_quality_filter_issue_registry.v2.0.json` and then record the exact expected value in `expected_assertions/*.json`. Hard-coded unexplained scores are invalid tests, but release-gate tests MUST still contain exact machine-readable score/band/risk/count expectations so test generators do not have to infer them from prose.

The canonical manifest-backed production scoring boundary tests are:

| Contract Test ID | Fixture/config | Exact expectation artifact |
|---|---|---|
| `CT-SCORE-012` | `Q/TC-P1-005` with `checks.enable_dependency=false` | `docs/testing/expected_assertions/CT-SCORE-012.json` |
| `CT-SCORE-013` | `Q/TC-P1-005` with `thresholds.high=0.9475` | `docs/testing/expected_assertions/CT-SCORE-013.json` |
| `CT-SCORE-110` | summary aggregator unit case with `[0.123456, 0.123457]` | `docs/testing/expected_assertions/CT-SCORE-110.json` |

## 6. Golden output tests

Golden files:

```text
docs/testing/expected/F001_success.normalized.json
docs/testing/expected/F001_quality_input_fingerprint.txt
docs/testing/expected/F003_upstream_failed.normalized.json
docs/testing/expected/F004_unsupported_schema.normalized.json
docs/testing/expected/C001_invalid_config.normalized.json
```

Assertions:

- normalized actual output equals golden output except `started_at`, `finished_at`, `duration_ms`, debug previews, temporary filesystem paths and runtime timing traces when those are not frozen;
- no normalization is allowed for IDs, refs, issue codes, scores, bands, counts, diagnostics, fingerprints, or traversal order;
- public scores and means compare exactly after 6-decimal round-half-even rounding;
- `quality.source.quality_input_fingerprint` equals `F001_quality_input_fingerprint.txt` for F001;
- changing only debug/logging options does not change the fingerprint;
- changing an evaluated Stanza annotation changes the fingerprint.

## 7. CLI tests

Required CLI cases:

| Case | Expected |
|---|---|
| `evaluate INPUT.json` | JSON result on stdout |
| `evaluate INPUT.json --output out.json` | stdout empty, output file contains result |
| `evaluate INPUT.json --quality-output quality.json` | stdout contains full result and `quality.json` contains standalone `quality` sidecar on success |
| `evaluate INPUT.json --output out.json --quality-output quality.json` with unsafe second path | preflight prevents both writes; exit `3`; stdout empty |
| `--config invalid.json` | failed result with `invalid_config`, exit `4` |
| unsupported Stanza schema | failed result, exit `1` |
| upstream Stanza failure | failed result, exit `1` |
| output path is directory | exit `3`, no fallback stdout |
| output symlink | exit `3`, no write-through |
| `--pretty` | whitespace only changes |
| `--include-debug` | may add `debug`, does not alter production fields |

Production CLI/API release-gate cases that are not registry-owned are listed in `docs/testing/contract_test_manifest.v2.0.json`, including `CT-CLI-142`, `CT-CLI-135`, `CT-API-021`, `CT-API-022`, `CT-DET-050`, `CT-LIMIT-120`, and `CT-LIMIT-121`. Each entry points to a checked-in expected assertion artifact with exact command/preconditions or API call semantics.

## 8. API, config, limit, and determinism tests

### 8.1 API tests

| Test ID | Expected |
|---|---|
| `TG-API-020` | invalid config returns schema-valid failed result; no exception |
| `TG-API-021` | unsafe non-JSON runtime object raises `AnnotationQualityProgrammerError` |
| `TG-API-022` | API does not mutate input or config objects |
| `TG-API-023` | API return validates against `annotation_quality_filter.v2.0.schema.json` |

### 8.2 Config tests

| Test ID | Config | Expected |
|---|---|---|
| `TG-CONFIG-001` | `{}` | success with defaults |
| `TG-CONFIG-002` | `{"limits":{"max_output_json_bytes":1048576}}` | success; effective config merges defaults |
| `TG-CONFIG-003` | `{"limits":{"unknown_limit":123}}` | `invalid_config`, helper `config_schema_validation_failed`, exit `4` |
| `TG-CONFIG-004` | `{"thresholds":{"low":0.9,"medium":0.6,"high":0.8}}` | `invalid_config`, helper `config_invariant_failed`, exit `4` |

### 8.3 Limit and filesystem tests

| Test ID | Expected |
|---|---|
| `TG-LIMIT-120` | `max_input_json_bytes` exact boundary allowed |
| `TG-LIMIT-121` | `max_input_json_bytes + 1` rejected with `invalid_input` |
| `TG-LIMIT-122` | `max_json_depth` exact boundary allowed |
| `TG-LIMIT-123` | `max_json_depth + 1` rejected with `invalid_input` |
| `TG-LIMIT-124` | oversized serialized output emits `output_too_large` |
| `TG-CLI-140` | missing output parent exits `3`; no fallback stdout |
| `TG-CLI-141` | permission-denied output path exits `3` |
| `TG-CLI-142` | multi-output preflight prevents partial writes |

### 8.4 Determinism and compatibility tests

| Test ID | Expected |
|---|---|
| `TG-DET-050` | repeated runs produce identical normalized output |
| `TG-DET-051` | debug/logging changes do not change fingerprint or production fields |
| `TG-DET-052` | quality-relevant Stanza annotation change changes fingerprint |
| `TG-SEC-170` | schema validation uses local catalog only; zero network requests |
| `TG-COMPAT-180` | unknown future Stanza schema returns `unsupported_stanza_schema` |
| `TG-COMPAT-181` | registry code removal is detected as a breaking-change test failure |

## 9. Privacy tests

Logs, diagnostics, and debug previews MUST NOT contain:

- full book text;
- full text-unit text;
- raw Stanza documents;
- raw HTML;
- absolute local paths;
- usernames;
- environment variables;
- credentials or secrets;
- stack traces for expected errors.

Error messages may include schema path, diagnostic code, stable text-unit id, sentence id, token id, word id, and entity id.


## 10. Production release-gate consistency checks

Before release, CI MUST run:

```bash
python docs/testing/tools/validate_embedded_config_blocks.py
python docs/testing/tools/validate_test_contract_consistency.py
python docs/testing/tools/validate_expected_assertions.py
```

`validate_test_contract_consistency.py` MUST fail on:

- duplicate or divergent `TC-*` IDs across Markdown and manifest;
- registry `tests[]` IDs missing from the manifest;
- concrete `docs/...` paths in manifest entries that do not exist;
- P0/P1 manifest entries using placeholder fixtures or placeholder expected results;
- manifest expected codes that are not present in referenced normalized golden outputs or expected assertion artifacts.
