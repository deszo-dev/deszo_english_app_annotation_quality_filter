# annotation_quality_filter architecture v2.0

`annotation_quality_filter` evaluates the quality of linguistic annotations produced by `stanza_annotator.v2.0` and returns an unchanged upstream `StanzaAnnotationResult` plus a module-owned quality sidecar.

The historical package name remains for repository compatibility, but this module is not a retention filter. It does not remove, rewrite, reorder, or repair Stanza annotations.

```text
StanzaAnnotationResult
  -> annotation_quality_filter
  -> AnnotationQualityEnrichmentResult
```

## 0. Normative baseline

### 0.1 Inputs and schemas

The only supported production input is `StanzaAnnotationResult` with:

```json
{ "schema_version": "stanza_annotator.v2.0" }
```

The package vendors a strict consumed subset of the upstream Stanza result schema at:

```text
docs/architecture/schema/stanza_annotator.v2.0.schema.json
```

The files below are retained only as non-normative upstream-reference placeholders for local schema-catalog completeness. They are not used to validate `annotation_quality_filter` production input unless a later module version explicitly says so:

```text
docs/architecture/schema/stanza_annotator_config.v2.0.schema.json
docs/architecture/schema/stanza_annotator_diagnostics.v2.0.schema.json
```

The module-owned public contracts are:

```text
docs/architecture/schema/annotation_quality_filter.v2.0.schema.json
docs/architecture/schema/annotation_quality_filter_config.v2.0.schema.json
docs/architecture/schema/annotation_quality_filter_effective_config.v2.0.schema.json
docs/architecture/schema/annotation_quality_filter_diagnostics.v2.0.schema.json
docs/architecture/schema/schema_catalog.v2.0.json
docs/architecture/schema/annotation_quality_filter_issue_registry.v2.0.schema.json
docs/architecture/schema/annotation_quality_filter_error_registry.v2.0.schema.json
docs/architecture/registry/annotation_quality_filter_issue_registry.v2.0.json
docs/architecture/registry/annotation_quality_filter_error_registry.v2.0.json
```

JSON Schema is the source of truth for machine validation. This Markdown document is normative for behavior that JSON Schema cannot fully express, especially traversal, preservation, fingerprinting, failure order, and privacy rules.

### 0.1.1 Guideline applicability

Files under `docs/guidelines/**` are inherited engineering guidance. They are binding only where this module architecture explicitly references them. If a guideline conflicts with this contract, this module contract wins.

The runtime metadata guideline applies only to the public `get_runtime_metadata()` function defined in section `0.4`; it MUST NOT expand the stable public API beyond that function and `evaluate_stanza_result()`.

### 0.2 Stanza v2.0 alignment

`annotation_quality_filter` consumes the current `stanza_annotator.v2.0` structured EPUB output.

Important upstream assumptions:

- `document.book.chapters[].paragraphs` is not a production field and MUST be rejected by the consumed Stanza schema when present.
- Chapter body text is represented by `document.book.chapters[].text`.
- Chapter body annotation is represented by `document.book.chapters[].text_annotation` when `text_annotation_status = "annotated"`.
- Chapter title annotation is represented by `document.book.chapters[].title_annotation` when `title_annotation_status = "annotated"`.
- Front/back matter sections may carry structural `paragraphs[]`, but those paragraphs are pass-through only and are never annotation targets.
- Section body annotation is represented by `section.text_annotation` when `section.text_annotation_status = "annotated"`.
- Footnotes are represented by `footnote.annotation` when `footnote.annotation_status = "annotated"`.
- Skipped represented units use `*_skipped_reason` or footnote `skipped_reason`, not legacy `skip_reason`.
- There is no top-level flat `sentences[]` or `entities[]` array.

### 0.3 No mutation policy

On success:

```text
output.document == input
```

where equality means deep semantic equality after JSON-compatible normalization.

The module MUST NOT add quality fields to any upstream-owned object, including:

```text
StanzaAnnotationResult
AnnotatedEpubDocument
AnnotatedEpubBook
AnnotatedEpubChapter
AnnotatedEpubSection
AnnotatedEpubFootnote
TextUnitAnnotation
AnnotatedSentence
AnnotatedToken
AnnotatedWord
AnnotatedEntity
```

Quality data is emitted only under:

```text
AnnotationQualityEnrichmentResult.quality
```

### 0.4 Public Python API / library mode contract

The stable public API for v2.x is limited to the symbols below. Internal helpers, checker classes, dataclasses, and CLI implementation details are not public contracts unless listed here.

```python
from annotation_quality_filter import (
    AnnotationQualityProgrammerError,
    evaluate_stanza_result,
    get_runtime_metadata,
)

from collections.abc import Mapping
from typing import TypeAlias

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
JSONMapping: TypeAlias = Mapping[str, JSONValue]
AnnotationQualityResult: TypeAlias = dict[str, JSONValue]

# Repeated below as a copyable typing contract; the symbols above are exported from the package root.

class AnnotationQualityProgrammerError(TypeError):
    """Raised only for unsafe programmer misuse that cannot be represented as JSON input."""


def evaluate_stanza_result(
    input_data: JSONMapping,
    config: JSONMapping | None = None,
) -> AnnotationQualityResult:
    """Return an AnnotationQualityEnrichmentResult for a StanzaAnnotationResult."""


def get_runtime_metadata() -> dict[str, JSONValue]:
    """Return deterministic module metadata used by orchestration and stage fingerprints."""
```

Library mode rules:

- `input_data` MUST be a JSON-compatible mapping. The function MUST NOT mutate it.
- `config=None` is equivalent to an empty user config override `{}`.
- Expected config, input, upstream-status and output-size failures return a schema-valid failed `AnnotationQualityEnrichmentResult` and MUST NOT raise.
- The function raises `AnnotationQualityProgrammerError` only when `input_data` or `config` contains unsafe non-JSON runtime objects such as file handles, iterators, generators, unserializable objects, or objects with serialization side effects.
- The function performs no filesystem writes, no network access, and no logging unless logging is explicitly enabled by caller config.
- The function is reentrant and thread-safe when called with independent input/config objects.
- The returned object MUST validate against `annotation_quality_filter.v2.0.schema.json`.
- `get_runtime_metadata()` MUST NOT inspect user input, environment secrets, absolute local paths, current time, or network state. It returns only the deterministic object defined below.

`get_runtime_metadata()` exact object contract:

```json
{
  "module_name": "annotation_quality_filter",
  "module_version": "2.0.0",
  "supported_input_schema_versions": ["stanza_annotator.v2.0"],
  "output_schema_version": "annotation_quality_filter.v2.0",
  "config_schema_version": "annotation_quality_filter_config.v2.0",
  "effective_config_schema_version": "annotation_quality_filter_effective_config.v2.0",
  "issue_registry_version": "annotation_quality_filter_issue_registry.v2.0",
  "error_registry_version": "annotation_quality_filter_error_registry.v2.0",
  "checker_versions": {
    "core": "2.0.0"
  }
}
```

Rules:

- All keys shown above are required.
- `module_version` and `checker_versions.*` MUST be SemVer-compatible strings without a leading `v`.
- `supported_input_schema_versions` MUST contain only schema versions accepted in production input.
- The object MUST be stable across calls for the same installed package version and MUST NOT contain timestamps, local paths, hostnames, usernames, environment values, random values, or debug flags.

Expected failure mapping:

| Condition | Result error code | Helper diagnostic | Raises? |
|---|---|---|---:|
| Config violates user override schema | `invalid_config` | `config_schema_validation_failed` | No |
| Effective config violates cross-field invariants | `invalid_config` | `config_invariant_failed` | No |
| CLI input bytes are malformed JSON | `invalid_input` | `input_json_parse_failed` | No |
| Input is not a supported JSON-compatible Stanza result | `invalid_input` | `input_schema_validation_failed` | No, except programmer misuse |
| `schema_version` is not `stanza_annotator.v2.0` | `unsupported_stanza_schema` | `unsupported_input_schema_version` | No |
| Input `status = "failed"` | `upstream_stanza_annotation_failed` | `upstream_failure_status_seen` | No |
| Output JSON exceeds `max_output_json_bytes` | `output_too_large` | `output_serialization_too_large` | No, when a failed result can be emitted |
| CLI output destination cannot be written safely | `output_write_failed` | `output_channel_write_failed` | No |
| Unexpected implementation failure | `internal_error` | `unexpected_internal_error` | May be converted to failed result when possible |

## 1. Responsibility

### 1.1 In scope

The module is responsible for:

- validating config before input traversal;
- validating input against the consumed Stanza v2.0 subset;
- traversing existing text-unit annotations emitted by Stanza;
- evaluating sentence, token, word, entity, offset, dependency, morphology, and distribution quality;
- computing deterministic scores in `[0.0, 1.0]`;
- assigning advisory quality bands;
- emitting sidecar quality records keyed by upstream stable IDs;
- emitting deterministic summaries, diagnostics, and fingerprints;
- preserving the upstream result unchanged.

### 1.2 Out of scope

The module MUST NOT:

- run Stanza;
- parse EPUBs;
- normalize or repair source text;
- create missing annotations;
- repair dependencies, heads, morphology, offsets, or entities;
- drop sentences, tokens, words, entities, annotations, chapters, sections, or footnotes;
- mutate upstream summary counts or fingerprints;
- decide whether downstream grammar extraction should skip a sentence.

## 2. Consumed traversal model

### 2.1 Traversable annotation locations

The module traverses only official `TextUnitAnnotation` objects and represented skipped units in these locations:

| Traversal path | Evaluated when | Quality `ref.kind` | Quality `ref.owner_type` |
|---|---|---|---|
| `document.book.chapters[].title_annotation` | `title_annotation_status = "annotated"` | `chapter_title` | `chapter` |
| `document.book.chapters[].text_annotation` | `text_annotation_status = "annotated"` | `chapter_text` | `chapter` |
| `document.book.chapters[].footnotes[].annotation` | `annotation_status = "annotated"` | `footnote` | `chapter` |
| `document.book.front_matter[].title_annotation` | `title_annotation_status = "annotated"` | `section_title` | `front_matter` |
| `document.book.front_matter[].text_annotation` | `text_annotation_status = "annotated"` | `section_text` | `front_matter` |
| `document.book.front_matter[].footnotes[].annotation` | `annotation_status = "annotated"` | `footnote` | `front_matter` |
| `document.book.back_matter[].title_annotation` | `title_annotation_status = "annotated"` | `section_title` | `back_matter` |
| `document.book.back_matter[].text_annotation` | `text_annotation_status = "annotated"` | `section_text` | `back_matter` |
| `document.book.back_matter[].footnotes[].annotation` | `annotation_status = "annotated"` | `footnote` | `back_matter` |
| `document.book.footnotes[].annotation` | `annotation_status = "annotated"` | `footnote` | `book` |

The quality sidecar ref mirrors the upstream Stanza text-unit ref shape:

```typescript
interface TextUnitRef {
  kind: "chapter_text" | "section_text" | "chapter_title" | "section_title" | "footnote";
  text_unit_id: string;
  owner_type: "chapter" | "front_matter" | "back_matter" | "book";
  owner_id: string;
  footnote_id?: string;
  source_field: "title" | "text";
}
```

Legacy quality ref kinds such as `chapter_paragraph`, `front_matter_paragraph`, `back_matter_paragraph`, `chapter_footnote`, `front_matter_footnote`, `back_matter_footnote`, and `book_footnote` are invalid in v2.0.

### 2.2 Traversal order

Quality records are emitted in deterministic reading order:

1. front matter sections in array order:
   1. section title when represented;
   2. section text when represented;
   3. section footnotes in array order;
2. chapters in array order:
   1. chapter title when represented;
   2. chapter text when represented;
   3. chapter footnotes in array order;
3. back matter sections in array order using the same section ordering;
4. book-level footnotes in array order.

A represented skipped unit receives one `TextUnitQuality` record with `evaluation_status = "not_evaluated"`. It does not produce sentence-level or entity-level quality records.

### 2.3 Not-evaluated mapping

| Source condition | `not_evaluated_reason` |
|---|---|
| Upstream represented unit has skipped reason `empty_text`, or source text is empty | `empty_text` |
| Upstream represented unit has skipped reason `too_large` | `too_large` |
| Unit is intentionally excluded by annotation-quality config | `excluded_by_config` |
| Unit is marked annotated but the annotation object is missing, or skipped reason is absent/unknown | `missing_annotation` |

The module MUST NOT invent additional `not_evaluated_reason` values in v2.0.

## 3. Output model

### 3.1 Result envelope

```typescript
interface AnnotationQualityEnrichmentResult {
  schema_version: "annotation_quality_filter.v2.0";
  status: "succeeded" | "failed";
  document?: StanzaAnnotationResult;
  quality?: AnnotationQualityDocument;
  diagnostics: AnnotationQualityDiagnostic[];
  annotation_quality: AnnotationQualityRunInfo;
  error?: AnnotationQualityError;
  debug?: AnnotationQualityDebugInfo;
}
```

On success, `document` and `quality` are required and `error` is absent.

On failure, `error` is required and `document` and `quality` are absent.

### 3.2 Quality document

```typescript
interface AnnotationQualityDocument {
  source: AnnotationQualitySource;
  text_units: TextUnitQuality[];
  summary: AnnotationQualitySummary;
  config_version: "annotation_quality_filter_config.v2.0";
}
```

`AnnotationQualitySource.annotation_input_fingerprint` is copied exactly from `input.annotation.annotation_input_fingerprint` when present. It is not recomputed by this module.

`quality_input_fingerprint` is computed from the normalized quality-relevant Stanza input view, effective quality config, quality module version, and checker implementation versions.

Debug fields, logging options, CLI paths, timestamps, and durations MUST NOT affect `quality_input_fingerprint`.

### 3.3 Text-unit quality

```typescript
type TextUnitQualityEvaluationStatus = "evaluated" | "not_evaluated";

interface TextUnitQuality {
  text_unit_id: string;
  ref: TextUnitRef;
  evaluation_status: TextUnitQualityEvaluationStatus;
  not_evaluated_reason?: "excluded_by_config" | "empty_text" | "too_large" | "missing_annotation";
  sentence_quality: SentenceQuality[];
  entity_quality: EntityQuality[];
  summary: TextUnitQualitySummary;
}
```

Rules:

- `evaluation_status = "evaluated"` requires an input `TextUnitAnnotation`.
- `evaluation_status = "evaluated"` forbids `not_evaluated_reason`.
- `evaluation_status = "not_evaluated"` requires `not_evaluated_reason`.
- `evaluation_status = "not_evaluated"` requires empty `sentence_quality` and `entity_quality` arrays.
- For evaluated units, `sentence_quality.length == annotation.sentences.length` and `entity_quality.length == annotation.entities.length`.

## 4. Quality checks

Quality checks are advisory. Hard issues may mark a quality record as `invalid`, but they do not delete or change the upstream annotation.

Required check families:

- structural shape and required fields;
- sentence span and source-slice consistency;
- token and word offsets;
- token-to-word references;
- dependency root count;
- dependency head bounds;
- `head_word_id` consistency when present;
- disconnected dependency tree detection;
- morphology presence and coarse consistency;
- presence of a main verb and subject-like dependency for finite clauses when applicable;
- distribution anomalies such as extreme dominant POS/dependency ratios;
- entity span validity and entity source-slice consistency.

The issue registry is normative for issue codes, severity, and scoring effect.


### 4.0.1 Single-issue and multi-threshold rule

For v2.0, an issue code is emitted at most once per scoped item unless that registry entry explicitly says otherwise. When an issue trigger mentions multiple thresholds but the registry defines a single `score_effect`, exceeding any or all of those thresholds emits the same issue once and applies the single registry score effect once.

Implementations MUST NOT invent severity escalation, additional penalties, additional issue occurrences, or alternate banding from threshold names such as `soft`, `max`, or `hard`. If a later version needs severe-threshold behavior, it MUST introduce explicit registry fields such as `threshold_penalties` or separate issue codes and update this contract version.



### 4.1 Deterministic scoring and bands

Scoring is a public v2.x contract. Implementations MUST compute scores from the effective config and the issue registry only. Implementation-defined hidden heuristics are forbidden for fields that appear in public output.

Every issue registry entry MUST include:

- `family`: `structural`, `dependency`, `morphology`, `sentence`, `distribution`, or `entity`;
- `scope`: `sentence` or `entity`;
- `score_effect.mode`: `penalty` or `hard_invalid`;
- `score_effect.penalty`: number in `[0.0, 1.0]` when mode is `penalty`.

Sentence score calculation:

1. Build the enabled sentence-family set from `checks.enable_structural`, `checks.enable_dependency`, `checks.enable_morphology`, `checks.enable_sentence`, and `checks.enable_distribution`.
2. Each enabled sentence family starts at family score `1.0`.
3. For every emitted sentence-scoped issue with `score_effect.mode = "penalty"`, subtract the issue penalty from the matching family score.
4. Clamp every family score to `[0.0, 1.0]`.
5. If any emitted sentence-scoped issue has `score_effect.mode = "hard_invalid"`, final sentence `score = 0.0`, `band = "invalid"`, and `risk_level = "critical"`.
6. Otherwise compute the weighted average: `score = sum(family_score * weight) / sum(enabled_family_weights)`.
7. Round final score to 6 decimal places using round-half-even decimal rounding.

Entity score calculation:

1. Entity scoring runs only when `checks.enable_entity = true`.
2. Entity-scoped penalty issues subtract from an entity family score that starts at `1.0`.
3. Entity-scoped hard-invalid issues set entity `score = 0.0` and `band = "invalid"`.
4. Entity score is rounded to 6 decimal places using round-half-even decimal rounding.

Band mapping:

| Condition | Band |
|---|---|
| hard-invalid issue emitted, or score is below `thresholds.low` | `invalid` |
| `thresholds.low <= score < thresholds.medium` | `low` |
| `thresholds.medium <= score < thresholds.high` | `medium` |
| `score >= thresholds.high` | `high` |

Sentence `risk_level` mapping:

| Condition | `risk_level` |
|---|---|
| `band = "invalid"` or any hard-invalid issue | `critical` |
| at least one error issue and no hard-invalid issue | `high` |
| at least one warning issue and no error issue | `medium` |
| no issues | `low` |

Summary mean fields are `null` when there are no evaluated items in that category. Otherwise they are arithmetic means of already-rounded item scores, rounded to 6 decimal places using round-half-even. Count fields are exact integers and MUST be derived from emitted quality records, not from upstream summary hints.

## 5. Configuration

### 5.1 User config override and effective config

`annotation_quality_filter_config.v2.0.schema.json` validates the user-supplied config override. The override is intentionally partial: every section and nested field is optional, but every present field MUST conform to the schema and unknown properties are invalid at every depth.

`annotation_quality_filter_effective_config.v2.0.schema.json` validates the fully resolved effective config after defaults and invariants. The effective schema is complete: all runtime fields required by the evaluator are required.

`config=None` in library mode and omitted `--config` in CLI mode are equivalent to an empty override `{}`.

Processing order:

1. Treat missing config as `{}`.
2. Validate the user config override against `annotation_quality_filter_config.v2.0.schema.json`.
3. Deep-merge the override into the built-in default config. Object fields are merged recursively. Scalar fields replace the default value. Arrays, if added in a later version, replace defaults unless that version explicitly says otherwise.
4. Validate the resolved effective config against `annotation_quality_filter_effective_config.v2.0.schema.json`.
5. Validate the cross-field invariants in section `5.3`.
6. Check input byte/depth limits where applicable.
7. Validate `schema_version` and upstream status according to section `0.4`.
8. Validate successful input against the consumed Stanza schema.
9. Traverse represented text units, run quality checks, build output, and enforce output-size limit.

Only the effective config participates in `quality_input_fingerprint`. Raw user override order, omitted default fields, debug/logging settings, CLI paths, timestamps and durations MUST NOT affect the fingerprint.

### 5.2 Default effective config

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

### 5.3 Config cross-field invariants

After defaults are applied, the effective config MUST satisfy all invariants below. Violations return `error.code = "invalid_config"` and emit helper diagnostic `config_invariant_failed`.

| Invariant ID | Rule | Diagnostic path |
|---|---|---|
| `CFG-INV-001` | `0 <= thresholds.low <= thresholds.medium <= thresholds.high <= 1` | `/thresholds` |
| `CFG-INV-002` | At least one sentence check family is enabled among structural, dependency, morphology, sentence, and distribution. Entity-only evaluation does not make sentence scoring valid for text units with sentences. | `/checks` |
| `CFG-INV-003` | Every enabled sentence family has weight `> 0`. | `/weights/<family>` |
| `CFG-INV-004` | Sum of enabled-family weights is `> 0`. Weights do not have to sum to `1.0`; scoring normalizes by the enabled-weight denominator. | `/weights` |
| `CFG-INV-005` | `limits.long_sentence_soft <= limits.max_sentence_length <= limits.long_sentence_hard`. | `/limits` |
| `CFG-INV-006` | `limits.max_conj_ratio <= limits.severe_conj_ratio`. | `/limits` |
| `CFG-INV-007` | `max_input_json_bytes`, `max_output_json_bytes`, and `max_json_depth` are inclusive minimum `1`. | `/limits` |

### 5.4 Limit semantics

| Limit | Unit | Boundary | Check timing | Exceeded behavior |
|---|---|---|---|---|
| `max_input_json_bytes` | CLI raw input bytes before JSON parse; API compact UTF-8 JSON serialization of `input_data` | allowed when `size <= limit` | before schema validation | `invalid_input` + `input_schema_validation_failed` when object can be inspected; `invalid_input` + `input_json_parse_failed` for malformed bytes |
| `max_json_depth` | maximum object/array nesting depth; root object depth is `1` | allowed when `depth <= limit` | after parse, before schema validation | `invalid_input` + `input_schema_validation_failed` |
| `max_output_json_bytes` | exact UTF-8 bytes of the actual selected output serialization; pretty whitespace counts when `--pretty` is used | allowed when `size <= limit` | after result construction, before stdout/file write | `output_too_large` + `output_serialization_too_large` |
| `long_sentence_soft` | word count | warning when `word_count > soft` and `<= max_sentence_length` | sentence checks | `TOO_LONG_SENTENCE` penalty |
| `max_sentence_length` | word count | warning when `word_count > max_sentence_length`; hard limit only when checker registry declares hard invalid in a later version | sentence checks | `TOO_LONG_SENTENCE` penalty |
| `long_sentence_hard` | word count | warning severity may be escalated when `word_count > hard`; document still preserved | sentence checks | `TOO_LONG_SENTENCE` penalty unless registry says otherwise |

Debug and logging config MUST NOT change production quality scores, summaries, traversal order, diagnostics, or fingerprints.

## 6. Diagnostics and privacy

Diagnostics are production-safe. They MUST NOT contain:

- full book text;
- full text-unit text;
- raw Stanza documents;
- raw HTML;
- absolute local paths;
- usernames;
- credentials, secrets, environment dumps, or stack traces for expected errors.

Diagnostic paths should point to the relevant JSON Pointer when possible, for example:

```text
/document/document/book/chapters/0/text_annotation/sentences/0/words/0/head_word_id
```

Messages should mention stable IDs and codes instead of full text.

## 7. CLI contract

Canonical command:

```bash
annotation-quality-filter evaluate INPUT.json [options]
```

Supported options:

```text
--output PATH
--quality-output PATH
--config PATH
--pretty
--include-debug
--debug-dir PATH
--version
--help
```

Rules:

- `INPUT.json` is a local JSON file; `INPUT.json = -` reads from stdin.
- If `--config PATH` is omitted, user config is `{}`.
- `--config -` is supported only when `INPUT.json` is not `-`; the CLI MUST NOT read both input and config from stdin.
- stdout is reserved for machine-readable JSON except `--version` and `--help`.
- Human-readable logs and warnings go to stderr only and are disabled by default on success.
- If `--output` is supplied, the full `AnnotationQualityEnrichmentResult` is written there and stdout is empty on success.
- If `--quality-output PATH` is supplied and the evaluation result has `status = "succeeded"`, the CLI MUST write `result.quality` to `PATH` as a standalone JSON document.
- If the evaluation result has `status = "failed"`, `--quality-output` MUST NOT be created or overwritten.
- `--include-debug` sets effective `include_debug = true` and may add top-level `debug`, but MUST NOT alter production fields, scores, summaries, diagnostics, traversal order, or fingerprints.
- `--debug-dir` is CLI-only and MUST NOT appear in user config, effective config, or `quality_input_fingerprint`.
- `--pretty` changes JSON whitespace only; output-size limits are measured against the actual pretty/non-pretty emitted bytes.
- `--version` prints a single line: `annotation_quality_filter <module_version>` and exits `0`.
- `--help` prints usage text and exits `0`.

### 7.1 Output path and atomic write contract

Parent directories MUST already exist. The CLI MUST NOT create parent directories implicitly.

Output paths that are directories fail with exit `3`. Output symlinks MUST be rejected by default with exit `3` to avoid writing through unexpected targets.

When both `--output` and `--quality-output` are supplied, the CLI MUST preflight both target paths before writing either file. If either path is unsafe or unwritable, exit `3`, keep stdout empty, and do not create or modify either output file.

Atomic overwrite policy:

1. Write to a temporary file in the same parent directory.
2. Flush and fsync when the platform supports it.
3. Re-check that the target is not a symlink immediately before replace.
4. Replace the target regular file atomically.
5. Clean up temporary files after success or failure when cleanup is possible.

If atomic replace is unavailable, the CLI MUST fail with exit `3` rather than risk a partial production JSON file. When an output path was requested and writing fails, the CLI MUST NOT fall back to stdout.

Exit codes:

| Code | Meaning |
|---:|---|
| 0 | Result status `succeeded` |
| 1 | Result status `failed` except invalid config and output-write failure |
| 2 | CLI usage error; no JSON result |
| 3 | Output write failure; no fallback stdout when file output was selected |
| 4 | Invalid config; JSON failed result emitted if selected output channel is available |
| 99 | Unexpected internal error |

## 8. Determinism, fingerprints, and versioning

For identical quality-relevant input, effective semantic quality config, module version, checker versions, registries, and Stanza annotations, normalized outputs MUST be identical except timestamps and durations.

### 8.1 Canonical JSON

Canonical JSON for fingerprints uses UTF-8 JSON, sorted object keys, compact separators, and arrays preserved in semantic order. No insignificant whitespace is included.

Normalized golden-output comparison removes only fields explicitly marked unstable in this guide: `started_at`, `finished_at`, `duration_ms`, debug previews, temporary filesystem paths, and runtime timing traces. It MUST NOT normalize IDs, refs, issue codes, scores, bands, counts, diagnostics, fingerprints, or traversal order.

Floating-point public scores and means are exact after 6-decimal round-half-even rounding. Tests compare those numbers exactly, not approximately.

### 8.2 Quality input fingerprint view

`quality_input_fingerprint = "sha256:" + sha256(canonical_json({...}))` over this object:

```json
{
  "supported_input_schema_version": "stanza_annotator.v2.0",
  "stanza_quality_relevant_view": "see field list below",
  "effective_config_without_debug_and_logging": {},
  "module_version": "string",
  "checker_versions": {},
  "issue_registry_version": "annotation_quality_filter_issue_registry.v2.0",
  "projection_contract_version": "annotation_quality_filter.v2.0"
}
```

The Stanza quality-relevant view includes only:

- top-level `schema_version` and `status`;
- `annotation.annotator_version`, `annotation.stanza_version`, `annotation.source_book_fingerprint`, and `annotation.annotation_input_fingerprint` when present;
- traversed text-unit IDs, refs, source text, sentence/token/word/entity IDs, offsets, text, lemma, POS/XPOS, feats, dependency fields, entity types, and upstream annotation summaries;
- represented skipped unit IDs, refs and skipped reasons.

It excludes debug data, diagnostics message text, logging options, CLI paths, timestamps, durations, source filenames, and untraversed structural paragraph text.

`quality.source.quality_input_fingerprint` and `annotation_quality.quality_input_fingerprint` MUST both be present on success and MUST be identical.

### 8.3 Issue and diagnostic ordering

Issue order is deterministic: hard-invalid issues before penalty issues, then severity (`error` before `warning` before `info`), then text-unit order, sentence/entity order, stable entity id, issue code lexicographically, and JSON pointer lexicographically.

Diagnostic order is deterministic: config/input/output failure diagnostics first in validation order, then traversal diagnostics in reading order, then issue-derived diagnostics by the issue ordering rule.

Every failed result MUST include at least one helper diagnostic whose `code` maps to the top-level `error.code` in `annotation_quality_filter_error_registry.v2.0.json`.

### 8.4 Versioning and compatibility

Public contracts are versioned by schema, registry and catalog version strings. Within v2.x, the following are backward-compatible changes:

- adding optional output fields that do not alter existing fields;
- adding optional config fields with defaults;
- adding new tests and fixtures;
- adding new warning-level issue codes only when consumers opt into the newer issue registry.

The following are breaking changes and require a new major contract version or a new explicitly named schema/registry version:

- removing, renaming, or changing type/nullability/requiredness of public fields;
- changing diagnostic or issue code meaning;
- changing top-level error codes or CLI exit codes;
- changing scoring formula, default score effects, thresholds, or default weights;
- changing fingerprint canonicalization;
- changing traversal order;
- accepting a previously rejected stale input shape as production input without versioning.

Unknown Stanza `schema_version` values MUST produce `unsupported_stanza_schema` after config validation and before full successful-input traversal.

## 9. Validation checklist

CI MUST validate:

1. every valid Stanza fixture against `docs/architecture/schema/stanza_annotator.v2.0.schema.json`;
2. every success/failure output against `docs/architecture/schema/annotation_quality_filter.v2.0.schema.json`;
3. every config fixture and every embedded config block against `annotation_quality_filter_config.v2.0.schema.json`;
4. error and issue registry files against their schemas;
4a. every `$id` through `docs/architecture/schema/schema_catalog.v2.0.json` with network access disabled;
4b. every referenced registry `tests[]` ID against `docs/testing/test_manifest.v2.0.json` or testing-guide headings;
5. that `document.book.chapters[].paragraphs` is rejected in Stanza input;
6. that structural front/back matter `section.paragraphs[]` are preserved but never traversed as annotation targets;
7. that the output `document` remains deep-equal to the input Stanza result on success;
8. that old paragraph-based quality refs are rejected.

## 10. Glossary

| Term | Definition |
|---|---|
| User config override | Partial caller-supplied config validated before defaults. |
| Effective config | Fully materialized runtime config after defaults/deep merge and invariant checks. |
| Text unit | A whole Stanza annotation target such as chapter text, title, section text, or footnote. |
| Represented unit | A text unit represented by upstream status fields, whether annotated or skipped. |
| Quality sidecar | Module-owned `quality` object emitted next to the unchanged upstream `document`. |
| Coverage record | A `TextUnitQuality` emitted for an evaluated or not-evaluated represented text unit. |
| Normalized output | Output after removing only documented unstable fields for golden comparison. |
| Helper diagnostic | A diagnostic code that maps to a top-level error and explains the specific failure cause/path. |

## 11. Implementation checklist

A conforming implementation MUST:

1. Validate config before validating input.
2. Reject unsupported Stanza schema versions.
3. Map upstream `status = "failed"` to `upstream_stanza_annotation_failed`.
4. Reject successful input without `document`.
5. Reject legacy chapter paragraph annotations.
6. Traverse `title_annotation`, `text_annotation`, and footnote `annotation` fields only.
7. Preserve source-side `TextUnitAnnotation.ref` in `output.document` unchanged.
8. Emit quality-sidecar refs in the current Stanza text-unit ref shape.
9. Represent skipped units as `not_evaluated` coverage records.
10. Never emit sentence/entity quality for skipped units.
11. Never mutate upstream annotation objects.
12. Enforce output-size limits before writing.
13. Keep debug data redacted and production-inert.
