# Annotation Quality Filter

`annotation_quality_filter` evaluates and filters Stanza-compatible linguistic
annotation documents.

The module accepts an `AnnotatedDocument`, scores every sentence annotation, and
returns:

- a primary filtered `AnnotatedDocument` with the same schema as the input;
- a secondary `AnnotationQualityDocumentStatus` explaining all decisions.

The primary output never contains quality, debug, or log fields.

## Input Contract

```ts
interface AnnotatedDocument {
  sentences: Sentence[];
  entities: Entity[];
}

interface Sentence {
  text: string;
  tokens: Token[];
  words: Word[];
}

interface Token {
  text: string;
  words: Word[];
}

interface Word {
  text: string;
  lemma?: string;
  upos: string;
  xpos?: string;
  feats?: string;
  head: number;
  deprel: string;
  start_char: number;
  end_char: number;
}

interface Entity {
  text: string;
  type: string;
  start_char: number;
  end_char: number;
}
```

## Python Usage

```py
from annotation_quality_filter import AnnotationQualityFilter

filter_ = AnnotationQualityFilter()

primary_document = filter_.filter_document(document)
output = filter_.filter_with_status(document)

assert output.document == primary_document
status = output.status
```

Public API is exported only through `annotation_quality_filter.__init__`.

## Retention Policy

Default policy:

```text
ACCEPT      -> retained in primary document
WEAK_ACCEPT -> retained in primary document
REJECT      -> removed from primary document
```

Strict policy:

```py
from annotation_quality_filter import AnnotationQualityConfig, AnnotationQualityFilter

config = AnnotationQualityConfig(retention_policy="ACCEPT_ONLY")
filter_ = AnnotationQualityFilter(config)
```

With `ACCEPT_ONLY`, `WEAK_ACCEPT` sentences remain in status output but are not
included in the primary document.

## CLI Usage

Read from a file and write the primary filtered document to a file:

```bash
python -m annotation_quality_filter --input hollow.annotations.json --output filtered.annotations.json
```

Also write status to a separate file:

```bash
python -m annotation_quality_filter \
  --input hollow.annotations.json \
  --output filtered.annotations.json \
  --status-output quality-status.json
```

Use stdin/stdout:

```bash
python -m annotation_quality_filter < hollow.annotations.json > filtered.annotations.json
```

Strict retention:

```bash
python -m annotation_quality_filter \
  --input hollow.annotations.json \
  --output filtered.annotations.json \
  --retention-policy ACCEPT_ONLY
```

CLI streams are separated:

- `stdout`: only the primary filtered `AnnotatedDocument`;
- `--output`: only the primary filtered `AnnotatedDocument`;
- `--status-output`: only `AnnotationQualityDocumentStatus`;
- `stderr`: logs and errors only.

Exit codes:

- `0`: success;
- `1`: expected data/configuration error;
- `2+`: system/runtime error.

Errors never create partial output.

## Quality Model

Hard failures immediately produce `score = 0.0` and `REJECT`.

Soft scoring:

```text
score = 1.0
  - 0.30 * structural_penalty
  - 0.35 * dependency_penalty
  - 0.15 * morphology_penalty
  - 0.10 * sentence_penalty
  - 0.10 * distribution_penalty
```

Default thresholds:

- `score >= 0.80`: `ACCEPT`;
- `0.60 <= score < 0.80`: `WEAK_ACCEPT`;
- `score < 0.60`: `REJECT`.

## Entity Filtering

By default, entities are retained only when their span belongs to a retained
sentence span.

If a retained sentence span cannot be resolved, the default policy is an expected
input error. Dropping all entities for unresolved spans is available only through
an explicit opt-in configuration:

```py
from annotation_quality_filter import AnnotationQualityConfig, EntityFilteringConfig

config = AnnotationQualityConfig(
    entity_filtering=EntityFilteringConfig(
        on_unresolvable_sentence_span="drop_entities",
    ),
)
```

## Verification

Run tests:

```bash
python -m pytest -q
```

The architecture specification is in
[`docs/architecture.md`](docs/architecture.md). A checked Coq specification is
kept in [`docs/AnnotationQualityFilterSpec.v`](docs/AnnotationQualityFilterSpec.v).

## License

This project is distributed under the repository license. See [`LICENSE`](LICENSE).
