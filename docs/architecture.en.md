# Annotation Quality Filter Architecture

`annotation_quality_filter` is a module responsible for evaluating the quality of linguistic sentence annotations produced by Stanza or a similar Universal Dependencies-like parser. Its goal is to decide whether an annotated sentence is reliable enough for downstream analysis.

The first target parser version is Stanza v1.

## Responsibilities

The module:

- Analyzes annotation structure.
- Detects parser errors and annotation anomalies.
- Calculates a quality score.
- Classifies sentences by quality.
- Provides transparent diagnostics for every decision.

## Input

```ts
interface AnnotatedSentence {
  text: string;
  words: Word[];
}

interface Word {
  text: string;
  lemma: string;
  upos: string;
  feats?: string;
  head: number;
  deprel: string;
  start_char: number;
  end_char: number;
}
```

## Output

```ts
interface AnnotationQualityResult {
  score: number; // 0.0 - 1.0

  label: "ACCEPT" | "WEAK_ACCEPT" | "REJECT";

  reasons: QualityIssue[];

  diagnostics: {
    structural: StructuralMetrics;
    dependency: DependencyMetrics;
    morphology: MorphologyMetrics;
    sentence: SentenceMetrics;
    distribution: DistributionMetrics;
  };
}
```

## Main Tasks

### 1. Structural Validation

Validate dependency tree correctness:

- Exactly one root.
- Valid head indexes.
- No broken references.
- Connected graph.
- No orphan nodes.

### 2. Dependency Consistency

Validate dependency logic:

- Finite verbs should have a subject when expected.
- `aux` should attach to a verbal head.
- `conj`, `relcl`, and `acl` attachments should be plausible.
- Dependency relation distribution should not contain obvious anomalies.

### 3. Morphological Consistency

Validate morphological feature consistency:

- Finite verbs should have `Tense`.
- `VerbForm` should be plausible for the token.
- Basic subject-verb agreement should be checked when the required features are available.
- Morphology should not be anomalously empty.

### 4. Sentence-Level Heuristics

Validate sentence-level properties:

- Reasonable token length.
- No newline characters inside the sentence.
- Presence of a verb when expected.
- Basic punctuation sanity.

### 5. Distribution Checks

Validate annotation health:

- POS distribution should be plausible.
- Dependency relation distribution should be plausible.
- Strong skews, such as too many `conj` relations, should be penalized.

## Quality Scoring

### General Formula

The basic scoring principle is:

```text
score = 1.0 - structural_penalty - dependency_penalty - morphology_penalty - sentence_penalty
```

For production use, the module should use weighted penalties:

```text
score = 1.0 - sum(weight_i * penalty_i)
```

Not all errors are equal. Some errors are hard failures, while others are soft penalties.

### Hard Failures

If at least one hard failure is detected:

```text
score = 0.0
label = REJECT
```

Hard failure examples:

| Issue | Reason |
| --- | --- |
| `NO_ROOT` | The dependency tree is invalid. |
| `MULTIPLE_ROOTS` | The parse is broken. |
| `INVALID_HEAD_INDEX` | One or more dependency references are invalid. |
| `EMPTY_SENTENCE` | The sentence has no words. |
| `TOKEN_COUNT < 2` | The sentence is not informative enough. |

### Soft Penalty Formula

```text
score = 1.0
  - 0.30 * structural_penalty
  - 0.35 * dependency_penalty
  - 0.15 * morphology_penalty
  - 0.10 * sentence_penalty
  - 0.10 * distribution_penalty
```

Dependency quality is the strongest signal.

### Structural Penalty

`structural_penalty` is in the `[0, 1]` range.

| Check | Penalty |
| --- | --- |
| No root | `1.0`, hard failure |
| More than one root | `1.0`, hard failure |
| Disconnected tree | `0.7` |
| Orphan nodes | `0.5` |

### Dependency Penalty

`dependency_penalty` is in the `[0, 1]` range.

Important heuristics:

- Finite verb without a subject: `+0.4`.
- Broken auxiliary chain where `aux` does not point to a verb: `+0.25`.
- Conjunction explosion:

| `conj_count / total_words` | Penalty |
| --- | --- |
| `> 0.3` | `+0.3` |
| `> 0.5` | `+0.5` |

- Suspicious dependency pairs, such as `nsubj -> ADJ` or `obj -> ADV`: `+0.3`.
- `relcl` without a noun-like head: `+0.25`.

### Morphology Penalty

`morphology_penalty` is in the `[0, 1]` range.

- `VerbForm=Fin` without `Tense`: `+0.3`.
- Empty features ratio:

| `words_without_feats / total_words` | Penalty |
| --- | --- |
| `> 0.5` | `+0.2` |
| `> 0.7` | `+0.4` |

- Subject-verb agreement mismatch: `+0.2`.

### Sentence Penalty

`sentence_penalty` is in the `[0, 1]` range.

- Length:

| Token count | Penalty |
| --- | --- |
| `> 40` | `+0.1` |
| `> 60` | `+0.2` |
| `> 80` | `+0.4` |

- Contains newline: `+0.2`.
- No verb: `+0.5`.

### Distribution Penalty

- POS imbalance where `NOUN_ratio > 0.6`: `+0.2`.
- Dependency relation imbalance where one label ratio is greater than `0.5`: `+0.3`.

## Final Score

```py
def final_score(p):
    score = 1.0 - (
        0.30 * p.structural +
        0.35 * p.dependency +
        0.15 * p.morphology +
        0.10 * p.sentence +
        0.10 * p.distribution
    )
    return max(score, 0.0)
```

## Classification Thresholds

Production thresholds:

- `score >= 0.80` -> `ACCEPT`
- `0.60 <= score < 0.80` -> `WEAK_ACCEPT`
- `score < 0.60` -> `REJECT`

## Issue Types

```ts
type QualityIssue =
  | "MULTIPLE_ROOTS"
  | "NO_ROOT"
  | "INVALID_HEAD_INDEX"
  | "EMPTY_SENTENCE"
  | "TOKEN_COUNT_TOO_LOW"
  | "NO_MAIN_VERB"
  | "MISSING_SUBJECT"
  | "BROKEN_AUX_CHAIN"
  | "EXCESSIVE_CONJ"
  | "SUSPICIOUS_DEPREL_PAIR"
  | "INVALID_RELCL_ATTACHMENT"
  | "MISSING_TENSE"
  | "EMPTY_MORPHOLOGY"
  | "AGREEMENT_MISMATCH"
  | "TOO_LONG_SENTENCE"
  | "CONTAINS_NEWLINE"
  | "POS_DISTRIBUTION_ANOMALY"
  | "DEPREL_DISTRIBUTION_ANOMALY";
```

## Configuration

```ts
interface AnnotationQualityConfig {
  thresholds: {
    accept: number;      // default 0.8
    weak_accept: number; // default 0.6
  };

  weights: {
    structural: number;  // default 0.30
    dependency: number;  // default 0.35
    morphology: number;  // default 0.15
    sentence: number;    // default 0.10
    distribution: number;// default 0.10
  };

  limits: {
    max_sentence_length: number; // default 60
    max_conj_ratio: number;      // default 0.3
  };

  checks: {
    enable_morphology: boolean;
    enable_dependency: boolean;
    enable_distribution: boolean;
  };
}
```

## Design Principles

### 1. Fail Fast

Obvious structural errors immediately produce `REJECT`.

### 2. Heuristic, Not Strict

The module does not guarantee linguistic truth. It estimates the probability that an annotation is good enough for downstream processing.

### 3. Parser-Agnostic

The module should work not only with Stanza, but with any UD-like annotation source.

### 4. Transparent Diagnostics

Every decision should be explainable through `reasons` and diagnostics.

### 5. Non-Destructive

The module must not modify source annotations.

## Non-Goals

The module does not:

- Fix dependency annotations.
- Fix morphology.
- Extract grammar.
- Perform semantic analysis.

## Usage

```ts
const result = annotationQualityFilter.evaluate(sentence);

if (result.label === "REJECT") {
  skip(sentence);
}
```

Python API:

```py
from annotation_quality_filter import evaluate

result = evaluate(sentence)

if result.label == "REJECT":
    skip(sentence)
```

CLI:

```bash
python -m annotation_quality_filter hollow.annotations.json --pretty
python -m annotation_quality_filter hollow.annotations.json --limit 20 --jsonl
python -m annotation_quality_filter hollow.annotations.json -o quality-results.json --pretty
```

## Example

Good sentence:

```text
She has been reading a book.
```

Penalties:

```text
structural = 0
dependency = 0
morphology = 0
sentence = 0
distribution = 0

score = 1.0
```

Broken or suspicious sentence:

```text
What passed at this interview...
```

Example penalties:

```text
dependency: conj misuse -> 0.4
sentence: newline -> 0.2
morphology: weak -> 0.2

score = 1 - (0.35 * 0.4 + 0.10 * 0.2 + 0.15 * 0.2)
      ~= 0.81
```

The original draft estimated this case at approximately `0.73 -> WEAK_ACCEPT`; exact classification depends on the final penalty values and enabled checks.

## Practical Improvements

### Confidence Buckets

- `HIGH`: use for grammar extraction.
- `MEDIUM`: use for statistics or manual inspection.
- `LOW`: discard.

### Logging

Quality decisions should be loggable:

```json
{
  "score": 0.62,
  "issues": ["MISSING_SUBJECT", "EXCESSIVE_CONJ"]
}
```

### Corpus-Level Monitoring

The module should support aggregate monitoring, such as average score per book or per corpus batch.

## Extensibility

The module should allow:

- Adding new checks.
- Changing penalty weights.
- Training scoring in the future.
- Logging corpus quality statistics.

## Core Insight

The goal is not to judge every sentence perfectly. The goal is to consistently filter out the worst 20-30% of annotations before they damage downstream analysis.
