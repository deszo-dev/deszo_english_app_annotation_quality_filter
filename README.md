# Annotation Quality Filter

`annotation_quality_filter` is the v2.0 **quality enricher** for the
[`stanza_annotator`](https://github.com/deszo-dev) v2.0 EPUB pipeline.

> Starting with v2.0 the module is **not a filter**. The historical package
> name is preserved for repository continuity, but the normative contract is:
>
> ```
> StanzaAnnotationResult
>   -> annotation_quality_filter
>   -> AnnotationQualityEnrichmentResult
> ```
>
> The module evaluates the quality of existing Stanza annotations and emits a
> module-owned `quality` sidecar. It **never** removes, rewrites, reorders, or
> mutates Stanza annotations, sentences, tokens, words, or entities.
> Downstream consumers may use the quality sidecar as advisory signal.

The legacy filter contract (`FilteredAnnotatedDocument`, `RetentionPolicy`,
`ACCEPT_ONLY`, `WEAK_ACCEPT`, `filter_document()`, `filter_with_status()`,
`AnnotationQualityFilter`, …) has been removed.

## Public contracts

All public contracts are versioned and shipped as checked-in artifacts in
[`docs/architecture/schema/`](docs/architecture/schema/) and
[`docs/architecture/registry/`](docs/architecture/registry/):

| Artifact | Source of truth |
|---|---|
| Input (consumed Stanza subset) | `stanza_annotator.v2.0.schema.json` |
| Output | `annotation_quality_filter.v2.0.schema.json` |
| User config | `annotation_quality_filter_config.v2.0.schema.json` |
| Effective config | `annotation_quality_filter_effective_config.v2.0.schema.json` |
| Diagnostics | `annotation_quality_filter_diagnostics.v2.0.schema.json` |
| Top-level errors | `annotation_quality_filter_error_registry.v2.0.json` |
| Issue codes | `annotation_quality_filter_issue_registry.v2.0.json` |

Schema resolution is **offline-only** via `schema_catalog.v2.0.json`; the
package never reaches the network during validation. See architecture
[§0.1.1](docs/architecture/annotation_quality_filter_architecture.md) for the
full normative baseline.

## Python API

```py
from annotation_quality_filter import evaluate_stanza_result

result = evaluate_stanza_result(
    stanza_annotation_result,        # dict matching stanza_annotator.v2.0
    user_config=None,                 # optional override per config schema
    include_debug=False,
)

assert result["schema_version"] == "annotation_quality_filter.v2.0"
if result["status"] == "succeeded":
    assert result["document"] == stanza_annotation_result   # unchanged
    quality = result["quality"]                             # sidecar
else:
    error = result["error"]   # code from the v2.0 error registry
```

Expected domain / config / input failures are returned as a structured
`failed` result with `error.code` from the error registry — they do **not**
raise. Only true programmer misuse (non-JSON-serializable Python objects)
raises `TypeError`.

## CLI

```text
annotation-quality-filter evaluate INPUT.json [options]

  --output PATH            full result written to PATH (stdout otherwise)
  --quality-output PATH    quality sidecar (succeeded results only)
  --config PATH            user-config JSON (or "-" for stdin)
  --pretty                 pretty-print JSON output
  --include-debug          attach debug payload (production fields unchanged)
  --debug-dir PATH         CLI-only debug directory (not in fingerprint)
  --version                print "annotation_quality_filter 2.0.0" and exit
```

`INPUT.json = -` reads from stdin. `--output -` is not supported; omit
`--output` to write to stdout. Atomic writes (tmp → `os.replace`) prevent
partial files; symlinks and directories on output paths are rejected.

### Exit codes (architecture §7)

| Code | Meaning |
|---:|---|
| 0 | `status = "succeeded"` |
| 1 | `status = "failed"` except invalid config and output write |
| 2 | CLI usage error; no JSON result |
| 3 | Output write failure; no fallback to stdout |
| 4 | Invalid config (failed JSON result emitted if channel is safe) |
| 99 | Unexpected internal error |

### Quick examples

Evaluate a fixture, write full result and quality sidecar:

```bash
annotation-quality-filter evaluate docs/testing/fixtures/F001/stanza_annotation.json \
  --output out.json --quality-output q.json --pretty
```

Stdin → stdout:

```bash
cat stanza_annotation.json | annotation-quality-filter evaluate -
```

Show version:

```bash
python -m annotation_quality_filter --version
# annotation_quality_filter 2.0.0
```

## Quality model

Sentence scoring uses five families with configurable weights:

```text
score = (
    w_structural   * structural_family_score
  + w_dependency   * dependency_family_score
  + w_morphology   * morphology_family_score
  + w_sentence     * sentence_family_score
  + w_distribution * distribution_family_score
) / sum(enabled weights)
```

Default weights: `structural=0.30`, `dependency=0.35`, `morphology=0.15`,
`sentence=0.10`, `distribution=0.10`. Scores are rounded to 6 decimals using
round-half-even. A single `hard_invalid` issue collapses the sentence score to
`0.0` with `band = "invalid"` and `risk_level = "critical"`.

Default advisory bands:

| Range | Band |
|---|---|
| `score ≥ 0.80` | `high` |
| `0.60 ≤ score < 0.80` | `medium` |
| `score < 0.60` | `low` |
| hard-invalid | `invalid` |

Issue codes, severities, families, and penalties are normative in
[`annotation_quality_filter_issue_registry.v2.0.json`](docs/architecture/registry/annotation_quality_filter_issue_registry.v2.0.json).
The package validates every emitted issue against the registry.

## Determinism

For identical quality-relevant input, effective config (minus debug/logging),
module version, checker versions, and registries, normalized outputs are
byte-identical except `started_at`, `finished_at`, `duration_ms`, debug
previews, and runtime timing traces. The `quality_input_fingerprint`
(architecture §8.2) is a `sha256` over the canonical-JSON projection of the
Stanza quality-relevant view and the effective config.

## Tests

```bash
python -m pytest tests/ -v
```

Covers:

- offline schema/registry loading (`test_schemas_load.py`);
- contract validation of every checked-in golden output and Stanza fixture
  (`test_contracts.py`);
- F002 traversal canonicalization (`test_traversal.py`);
- F003/F004/F006/F007/C001/C002 failed-path golden equality
  (`test_golden_failure.py`);
- F001 happy-path identity-bearing fields (`test_golden_success.py`);
- CLI exit-code matrix and output side effects (`test_cli.py`).

## Documentation map

- Architecture: [`docs/architecture/annotation_quality_filter_architecture.md`](docs/architecture/annotation_quality_filter_architecture.md)
- Stanza input alignment: [`docs/architecture/stanza_input_alignment_note.md`](docs/architecture/stanza_input_alignment_note.md)
- Testing guide: [`docs/testing/annotation_quality_filter_testing.md`](docs/testing/annotation_quality_filter_testing.md)
- Python module guidelines: [`docs/guidelines/python_module_guidelines.md`](docs/guidelines/python_module_guidelines.md)
- CLI guidelines: [`docs/guidelines/cli_transform_guidelines.md`](docs/guidelines/cli_transform_guidelines.md)
- Runtime metadata guideline: [`docs/guidelines/runtime_metadata_guideline.md`](docs/guidelines/runtime_metadata_guideline.md)

## License

Distributed under the repository license. See [`LICENSE`](LICENSE).
