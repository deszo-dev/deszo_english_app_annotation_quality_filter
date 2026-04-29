# annotation_quality_filter architecture

`annotation_quality_filter` — модуль оценки качества и фильтрации лингвистических аннотаций, полученных от `stanza_annotator` или другого UD-подобного источника. Первая целевая версия источника — Stanza v1.

Модуль выполняет чистую, детерминированную трансформацию:

```text
AnnotatedDocument -> annotation_quality_filter -> FilteredAnnotatedDocument
                                      + AnnotationQualityDocumentStatus
```

Ключевой контракт:

1. **Основной output** — это `AnnotatedDocument` с уже отфильтрованными аннотациями.
2. Формат основного результата **полностью совпадает** с output contract `stanza_annotator`.
3. `FilteredAnnotatedDocument.sentences` содержит только sentence-аннотации, которые удовлетворили политике фильтрации.
4. Основной `AnnotatedDocument` не содержит quality/debug/log fields.
5. Дополнительный output `status` содержит quality/status-аннотации по исходным предложениям, включая `REJECT`; он передаётся отдельным API-полем или отдельным CLI status-output, а не встраивается в основной `AnnotatedDocument`.

По умолчанию retained policy:

```text
ACCEPT      -> включить в основной AnnotatedDocument
WEAK_ACCEPT -> включить в основной AnnotatedDocument
REJECT      -> исключить из основного AnnotatedDocument
```

Опционально policy может быть ужесточена до `ACCEPT_ONLY`, где `WEAK_ACCEPT` остаётся в `status`, но не попадает в основной `document`.

## 1. Граница ответственности

### Входит в ответственность модуля

- принимать `AnnotatedDocument`, совместимый с output contract `stanza_annotator`;
- валидировать структуру входных аннотаций до передачи в `core`;
- анализировать качество dependency, morphology, sentence-level и distribution сигналов;
- вычислять score в диапазоне `[0.0, 1.0]`;
- присваивать статус фильтрации `ACCEPT`, `WEAK_ACCEPT` или `REJECT`;
- формировать основной output как **отфильтрованный `AnnotatedDocument`**;
- сохранять схему `AnnotatedDocument` без изменений;
- формировать дополнительный `status` output с причинами, diagnostics и флагом включения в основной output;
- обеспечивать CLI/core разделение, логирование и debug-observability-only.

### Не входит в ответственность модуля

- запуск Stanza runtime;
- исправление dependency tree;
- исправление morphology;
- semantic analysis;
- preprocessing текста;
- переписывание `tokens`, `words`, `head`, `deprel`, `feats`;
- добавление quality-полей внутрь `AnnotatedDocument`;
- смешивание результата и логов.

Фильтр может удалять sentence-аннотации из основного output, но не имеет права изменять оставшиеся sentence-аннотации.

## 2. Слои архитектуры

```text
stdin / files / CLI args
        |
        v
+------------------------------+
| CLI                          |
| - parse args                 |
| - resolve config             |
| - read AnnotatedDocument     |
| - validate input             |
| - call pipeline              |
| - write result to stdout     |
| - write logs/errors to stderr|
+------------------------------+
        |
        v
+------------------------------+
| Application pipeline         |
| - deserialize input          |
| - validate schema            |
| - call pure core             |
| - serialize output           |
+------------------------------+
        |
        v
+------------------------------+
| Core                         |
| - no IO                      |
| - no environment access      |
| - no global state            |
| - deterministic scoring      |
| - deterministic filtering    |
| - candidate for Coq spec     |
+------------------------------+
        |
        v
FilteredAnnotatedDocument + AnnotationQualityDocumentStatus
```

### CLI

CLI — тонкий слой. Он:

- парсит аргументы;
- читает JSON из `stdin` или файла;
- разрешает конфигурацию в порядке `CLI args -> ENV -> defaults`;
- валидирует вход до вызова `core`;
- вызывает pipeline;
- пишет основной `FilteredAnnotatedDocument` в `stdout` или `--output` файл;
- пишет только логи и ошибки в `stderr`;
- не меняет семантику `core`.

CLI не имеет права:

- неявно трансформировать входной `AnnotatedDocument` до `core`;
- самостоятельно удалять или сохранять rejected sentences;
- менять порядок sentence-аннотаций;
- добавлять недетерминизм поверх `core`;
- смешивать результат и логи;
- создавать частичный output при ошибке.

### Pipeline

```text
AnnotatedDocument
  -> InputValidation
  -> QualityCore
  -> Filtered AnnotatedDocument + StatusOutput
```

Pipeline допускает IO только на границах чтения/записи. Все формальные гарантии относятся к `core` и к контракту сериализации.

### Core

Core реализует чистую функцию:

```text
output = f(document, config)
```

Свойства `core`:

- нет IO;
- нет `print`;
- нет чтения ENV;
- нет зависимости от времени;
- нет случайности;
- нет скрытого глобального состояния;
- одинаковые `document` и `config` дают одинаковый `output`;
- `output.document` имеет тип и JSON-схему `AnnotatedDocument`;
- `output.document.sentences` является order-preserving subsequence от `input.document.sentences`;
- каждое sentence в `output.document.sentences` удовлетворяет политике включения;
- `len(output.status.annotations) == len(input.document.sentences)`;
- `output.status.annotations[i]` описывает решение по `input.document.sentences[i]`.

## 3. Input contract

Вход модуля — `AnnotatedDocument`, совпадающий со стабильным output contract `stanza_annotator`.

```typescript
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
  lemma: string;
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

### Входные инварианты

- `sentences` и `entities` присутствуют всегда;
- `Sentence.text` не пустой для непустых sentence-аннотаций;
- каждый `Token` содержит хотя бы один `Word`;
- `Word.text`, `Word.upos`, `Word.deprel` не пустые;
- `Word.start_char <= Word.end_char`;
- `Entity.text`, `Entity.type` не пустые;
- `Entity.start_char <= Entity.end_char`;
- для dependency head используется UD-подобная схема: `head = 0` означает root, остальные значения указывают на 1-based индекс слова в sentence.

Нарушение схемы или предусловий является expected data/configuration error и должно завершать CLI с exit code `1`.

## 4. Output contract

Core возвращает пару: основной filtered `AnnotatedDocument` и дополнительный `AnnotationQualityDocumentStatus`. В Python API это может быть представлено wrapper-объектом:

```typescript
interface AnnotationQualityFilterOutput {
  document: AnnotatedDocument;
  status: AnnotationQualityDocumentStatus;
}
```

### 4.1 Основной output: `document`

`document` — это **основной результат фильтрации**.

```typescript
interface AnnotationQualityFilterOutput {
  document: AnnotatedDocument; // filtered annotations, stanza_annotator-compatible
  status: AnnotationQualityDocumentStatus;
}
```

Требования к `document`:

- структура полностью совпадает с `stanza_annotator` `AnnotatedDocument`;
- содержит только sentence-аннотации, прошедшие policy;
- порядок сохранённых sentence-аннотаций совпадает с исходным порядком;
- сохранённые sentence-аннотации не изменяются;
- `document` не содержит `score`, `label`, `reasons`, `diagnostics`, debug или log fields;
- downstream-компонент, ожидающий output `stanza_annotator`, может читать основной output без адаптации схемы. В Python wrapper это поле `output.document`; в CLI default output это весь `stdout` payload.

Entity policy:

- `output.document.entities` содержит только entities, относящиеся к сохранённым sentence spans;
- entity считается относящейся к sentence, если её span полностью попадает в span сохранённой sentence;
- если span sentence нельзя надёжно восстановить из `words.start_char/end_char`, entity filtering считается expected data error или явно отключается конфигурацией с documented warning;
- сохранённые `Entity` не изменяются.

### 4.2 Дополнительный output: `status`

`status` не является частью `AnnotatedDocument`. Он нужен для аудита, логирования качества и объяснения фильтрации.

```typescript
interface AnnotationQualityDocumentStatus {
  annotations: AnnotationQualityAnnotation[];
  summary: AnnotationQualitySummary;
  config_version: string;
  retention_policy: RetentionPolicy;
}

type RetentionPolicy = "ACCEPT_AND_WEAK_ACCEPT" | "ACCEPT_ONLY";

interface AnnotationQualityAnnotation {
  input_sentence_index: number;
  output_sentence_index?: number;
  sentence_text: string;
  included_in_output: boolean;
  status: FilterStatus;
  result: AnnotationQualityResult;
}

type FilterStatus = "ACCEPT" | "WEAK_ACCEPT" | "REJECT";

interface AnnotationQualityResult {
  score: number; // 0.0 – 1.0
  label: FilterStatus;
  reasons: QualityIssue[];
  diagnostics: AnnotationQualityDiagnostics;
}

interface AnnotationQualityDiagnostics {
  structural: StructuralMetrics;
  dependency: DependencyMetrics;
  morphology: MorphologyMetrics;
  sentence: SentenceMetrics;
  distribution: DistributionMetrics;
}

interface AnnotationQualitySummary {
  total_input_sentences: number;
  total_output_sentences: number;
  accepted: number;
  weak_accepted: number;
  rejected: number;
  mean_score: number;
}
```

### 4.3 Output invariants

- `output.document` is a valid `AnnotatedDocument`;
- `output.document.sentences` is an order-preserving subsequence of `input.document.sentences`;
- every retained sentence has `included_in_output = true` in `status.annotations`;
- no rejected sentence appears in `output.document.sentences`;
- if `retention_policy = ACCEPT_AND_WEAK_ACCEPT`, retained labels are `ACCEPT` or `WEAK_ACCEPT`;
- if `retention_policy = ACCEPT_ONLY`, retained label is only `ACCEPT`;
- `status.annotations.length == input.document.sentences.length`;
- `status.annotations[i].input_sentence_index == i`;
- `status.annotations[i].sentence_text == input.document.sentences[i].text`;
- `status.annotations[i].status == status.annotations[i].result.label`;
- `status.annotations[i].included_in_output == true` iff the sentence is present in `output.document.sentences`;
- `output_sentence_index` exists only for retained sentences;
- `0.0 <= score <= 1.0`;
- `summary.total_input_sentences == input.document.sentences.length`;
- `summary.total_output_sentences == output.document.sentences.length`;
- `summary.accepted + summary.weak_accepted + summary.rejected == summary.total_input_sentences`;
- logs and debug trace do not enter `document` or `status`.

## 5. Quality checks

### 5.1 Structural validation

Проверяет корректность dependency tree:

- ровно один root;
- валидные head индексы;
- отсутствие orphan nodes;
- связность графа;
- отсутствие пустой sentence-аннотации.

Hard failures:

| Issue | Условие | Эффект |
| --- | --- | --- |
| `NO_ROOT` | нет root | `score = 0`, `REJECT` |
| `MULTIPLE_ROOTS` | больше одного root | `score = 0`, `REJECT` |
| `INVALID_HEAD_INDEX` | `head` вне `[0, len(words)]` | `score = 0`, `REJECT` |
| `EMPTY_SENTENCE` | `words.length == 0` | `score = 0`, `REJECT` |
| `TOKEN_COUNT_LT_2` | `words.length < 2` | `score = 0`, `REJECT` |

Soft structural penalties:

| Условие | Penalty |
| --- | ---: |
| несвязное дерево | `+0.7` |
| orphan nodes | `+0.5` |

### 5.2 Dependency consistency

Проверяет dependency-эвристики:

- наличие subject у finite verb;
- корректность `aux -> VERB/AUX` chain;
- адекватность `conj`, `relcl`, `acl`;
- отсутствие подозрительных deprel/POS пар;
- отсутствие аномальных распределений `deprel`.

| Условие | Issue | Penalty |
| --- | --- | ---: |
| finite verb без subject | `MISSING_SUBJECT` | `+0.4` |
| `aux` attached не к `VERB/AUX` | `BROKEN_AUX_CHAIN` | `+0.25` |
| `conj_ratio > 0.3` | `EXCESSIVE_CONJ` | `+0.3` |
| `conj_ratio > 0.5` | `EXCESSIVE_CONJ` | `+0.5` |
| `nsubj -> ADJ`, `obj -> ADV` | `SUSPICIOUS_DEPREL_PAIR` | `+0.3` |
| `relcl` без noun-like head | `INVALID_RELCL_ATTACHMENT` | `+0.25` |

### 5.3 Morphological consistency

| Условие | Issue | Penalty |
| --- | --- | ---: |
| `VerbForm=Fin` без `Tense` | `MISSING_TENSE` | `+0.3` |
| `empty_feats_ratio > 0.5` | `EMPTY_MORPHOLOGY` | `+0.2` |
| `empty_feats_ratio > 0.7` | `EMPTY_MORPHOLOGY` | `+0.4` |
| базовый subject–verb mismatch | `AGREEMENT_MISMATCH` | `+0.2` |

### 5.4 Sentence-level heuristics

| Условие | Issue | Penalty |
| --- | --- | ---: |
| `len(words) > 40` | `TOO_LONG_SENTENCE` | `+0.1` |
| `len(words) > 60` | `TOO_LONG_SENTENCE` | `+0.2` |
| `len(words) > 80` | `TOO_LONG_SENTENCE` | `+0.4` |
| содержит newline | `CONTAINS_NEWLINE` | `+0.2` |
| нет глагола | `NO_MAIN_VERB` | `+0.5` |

### 5.5 Distribution checks

| Условие | Issue | Penalty |
| --- | --- | ---: |
| `NOUN_ratio > 0.6` | `POS_DISTRIBUTION_ANOMALY` | `+0.2` |
| `max_deprel_ratio > 0.5` | `DEPREL_DISTRIBUTION_ANOMALY` | `+0.3` |

## 6. Quality scoring

Production scoring использует hard failures и soft penalties.

### 6.1 Hard failure

Если найден хотя бы один hard failure:

```text
score = 0.0
label = REJECT
included_in_output = false
```

### 6.2 Soft scoring

```text
score = 1.0
  - 0.30 * structural_penalty
  - 0.35 * dependency_penalty
  - 0.15 * morphology_penalty
  - 0.10 * sentence_penalty
  - 0.10 * distribution_penalty
```

Каждый penalty нормализуется в диапазон `[0.0, 1.0]`. Финальный score clamp-ится в `[0.0, 1.0]`.

### 6.3 Classification thresholds

| Score | Label |
| ---: | --- |
| `score >= 0.80` | `ACCEPT` |
| `0.60 <= score < 0.80` | `WEAK_ACCEPT` |
| `score < 0.60` | `REJECT` |

`dependency_penalty` имеет максимальный вес, потому что качество dependency tree — главный сигнал для downstream grammar extraction.

## 7. Configuration contract

```typescript
interface AnnotationQualityConfig {
  thresholds: {
    accept: number;      // default 0.80
    weak_accept: number; // default 0.60
  };

  retention_policy: "ACCEPT_AND_WEAK_ACCEPT" | "ACCEPT_ONLY";

  weights: {
    structural: number;   // default 0.30
    dependency: number;   // default 0.35
    morphology: number;   // default 0.15
    sentence: number;     // default 0.10
    distribution: number; // default 0.10
  };

  limits: {
    max_sentence_length: number; // default 60
    long_sentence_soft: number;  // default 40
    long_sentence_hard: number;  // default 80
    max_conj_ratio: number;      // default 0.30
    severe_conj_ratio: number;   // default 0.50
  };

  checks: {
    enable_morphology: boolean;   // default true
    enable_dependency: boolean;   // default true
    enable_distribution: boolean; // default true
  };

  entity_filtering: {
    enabled: boolean; // default true
    on_unresolvable_sentence_span: "error" | "drop_entities";
  };

  debug: boolean; // default false
}
```

Defaults:

- `accept = 0.80`;
- `weak_accept = 0.60`;
- `retention_policy = "ACCEPT_AND_WEAK_ACCEPT"`;
- weights sum to `1.0`;
- `entity_filtering.enabled = true`;
- `on_unresolvable_sentence_span = "error"`.

Configuration resolution:

```text
CLI args -> ENV -> defaults
```

Config validation:

- `0.0 < weak_accept <= accept <= 1.0`;
- all weights `>= 0.0`;
- sum of weights is `1.0`;
- limits are positive;
- disabled check does not add penalty or issue for the group;
- invalid configuration is expected configuration error, CLI exit code `1`.

## 8. Public Python API

Публичный API экспортируется только через `__init__.py`.

```python
from annotation_quality_filter import (
    AnnotatedDocument,
    AnnotationQualityConfig,
    AnnotationQualityDocumentStatus,
    AnnotationQualityError,
    AnnotationQualityFilter,
    AnnotationQualityFilterOutput,
    AnnotationQualityResult,
    ConfigurationError,
    FilterStatus,
    InputValidationError,
    RetentionPolicy,
)
```

Основной API:

```python
class AnnotationQualityFilter:
    def filter_document(
        self,
        document: AnnotatedDocument,
    ) -> AnnotatedDocument:
        """Return the primary filtered document in stanza_annotator format."""

    def filter_with_status(
        self,
        document: AnnotatedDocument,
    ) -> AnnotationQualityFilterOutput:
        """Return filtered document plus filtering status."""

    def evaluate_sentence(
        self,
        sentence: Sentence,
        input_sentence_index: int,
    ) -> AnnotationQualityAnnotation:
        """Evaluate one sentence annotation and return its filter status."""
```

Требования к `filter_document`:

- возвращает `AnnotatedDocument`;
- это основной результат модуля;
- схема результата полностью совместима с `stanza_annotator`;
- метод не выполняет IO;
- метод не мутирует input document;
- status не встраивается в возвращаемый `AnnotatedDocument`.

Требования к `filter_with_status`:

- возвращает `AnnotationQualityFilterOutput`;
- `output.document` совпадает с результатом `filter_document`;
- `output.status` содержит решения по всем input sentences.

Требования к Python-коду:

- полная типизация публичного API;
- `mypy --strict`;
- `ruff` с правилами `E`, `F`, `I`, `B`;
- `black`, max line length `88`;
- `Any` запрещён в публичном API;
- wildcard imports запрещены;
- все ошибки представлены кастомными исключениями;
- IO отделён от доменной логики;
- Dependency Injection обязателен для расширяемых checker/diagnostics компонентов;
- `print` запрещён, используется только `logging`;
- формальные инварианты отражаются в типах, runtime validation и тестах.

Suggested exceptions:

```python
class AnnotationQualityError(Exception):
    """Base exception for annotation_quality_filter."""

class InputValidationError(AnnotationQualityError):
    """Input AnnotatedDocument contract was violated."""

class ConfigurationError(AnnotationQualityError):
    """Configuration is invalid or unsupported."""
```

## 9. CLI contract

CLI должен поддерживать:

- вход из `stdin`;
- вход из файла через `--input`;
- запись основного filtered `AnnotatedDocument` в файл через `--output`;
- запись дополнительного status output через `--status-output`;
- `--debug` / `-d`;
- `--retention-policy ACCEPT_AND_WEAK_ACCEPT|ACCEPT_ONLY`;
- стабильные аргументы;
- JSON output без неявного изменения структуры.

Потоки вывода:

- `stdout` — только основной filtered `AnnotatedDocument`, совместимый со `stanza_annotator`;
- `--status-output` файл — только `AnnotationQualityDocumentStatus`, если задан;
- `stderr` — только логи и ошибки.

Если указан `--output`, основной filtered `AnnotatedDocument` пишется в файл, а `stdout` остаётся пустым. Если указан `--status-output`, статус пишется в отдельный файл и не смешивается с основным результатом.

Exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | success |
| `1` | expected data/configuration error |
| `2+` | system/runtime error |

Ошибки никогда не создают частичный output ни в `stdout`, ни в `--output`, ни в `--status-output`.

## 10. Logging and debug

Логирование обязательно и выполняется через `logging`.

Логируются:

- разрешённые входные параметры без чувствительных данных;
- start/end каждого шага pipeline;
- количество input/output предложений;
- summary качества;
- expected data/configuration errors;
- system errors без раскрытия внутренних деталей.

Уровни:

- `DEBUG`;
- `INFO`;
- `WARNING`;
- `ERROR`.

Debug mode:

- включается через `--debug` / `-d` или config flag;
- увеличивает наблюдаемость;
- может логировать diagnostics и промежуточные penalties;
- не меняет вычисления;
- не изменяет `output.document`;
- не смешивает debug output с `stdout`.

Пример debug-фрагмента в `stderr`:

```json
{
  "input_sentence_index": 3,
  "output_sentence_index": 2,
  "included_in_output": true,
  "score": 0.73,
  "label": "WEAK_ACCEPT",
  "issues": ["MISSING_SUBJECT", "EXCESSIVE_CONJ"],
  "penalties": {
    "structural": 0.0,
    "dependency": 0.4,
    "morphology": 0.2,
    "sentence": 0.2,
    "distribution": 0.0
  }
}
```

## 11. Formal Coq specification

Эта секция формализует проверяемую часть архитектуры:

- структуру `AnnotatedDocument`, совместимую с `stanza_annotator`;
- основной output как filtered `AnnotatedDocument`;
- дополнительный `status` output как список решений по всем input sentences;
- score bounds;
- hard failure => `score = 0` и `REJECT`;
- threshold classification;
- retention policy;
- filtered output as order-preserving sentence filter;
- determinism;
- debug-observability-only;
- CLI exit-code/stdout mapping.

Coq-спецификация не доказывает лингвистическую истинность эвристик. Она фиксирует контракт scoring/status/filtering layer и свойства, которые обязан сохранять Python-код. Конкретная реализация `SentenceAnalysis` строится Python-checker'ами и проверяется unit/property tests.

```coq
From Coq Require Import Arith.Arith.
From Coq Require Import Bool.Bool.
From Coq Require Import Lists.List.
From Coq Require Import Lia.
From Coq Require Import Strings.String.

Import ListNotations.
Open Scope string_scope.
Open Scope list_scope.
Open Scope nat_scope.

Module AnnotationQualityFilterSpec.

Inductive FilterLabel : Type :=
| Accept
| WeakAccept
| Reject.

Inductive QualityIssue : Type :=
| MultipleRoots
| NoRoot
| InvalidHeadIndex
| DisconnectedTree
| OrphanNodes
| EmptySentence
| TokenCountLt2
| NoMainVerb
| MissingSubject
| BrokenAuxChain
| ExcessiveConj
| SuspiciousDeprelPair
| InvalidRelclAttachment
| MissingTense
| EmptyMorphology
| AgreementMismatch
| TooLongSentence
| ContainsNewline
| PosDistributionAnomaly
| DeprelDistributionAnomaly.

Inductive ExitCode : Type :=
| Success
| ExpectedError
| SystemError.

Definition exit_code_value (c : ExitCode) : nat :=
  match c with
  | Success => 0
  | ExpectedError => 1
  | SystemError => 2
  end.

Theorem exit_code_contract :
  exit_code_value Success = 0 /\
  exit_code_value ExpectedError = 1 /\
  exit_code_value SystemError >= 2.
Proof.
  repeat split; simpl; lia.
Qed.

Definition non_empty_string (s : string) : Prop := s <> "".
Definition valid_span (start finish : nat) : Prop := start <= finish.

Record Word : Type := {
  word_surface : string;
  word_lemma : string;
  word_upos : string;
  word_xpos : option string;
  word_feats : option string;
  word_head : nat;
  word_deprel : string;
  word_start_char : nat;
  word_end_char : nat
}.

Definition valid_word (w : Word) : Prop :=
  valid_span (word_start_char w) (word_end_char w) /\
  non_empty_string (word_surface w) /\
  non_empty_string (word_upos w) /\
  non_empty_string (word_deprel w).

Record Token : Type := {
  token_surface : string;
  token_words : list Word
}.

Definition valid_token (t : Token) : Prop :=
  non_empty_string (token_surface t) /\
  token_words t <> [] /\
  Forall valid_word (token_words t).

Record Sentence : Type := {
  sentence_surface : string;
  sentence_tokens : list Token;
  sentence_words : list Word
}.

Definition valid_sentence (s : Sentence) : Prop :=
  non_empty_string (sentence_surface s) /\
  Forall valid_token (sentence_tokens s) /\
  Forall valid_word (sentence_words s).

Record Entity : Type := {
  entity_surface : string;
  entity_type : string;
  entity_start_char : nat;
  entity_end_char : nat
}.

Definition valid_entity (e : Entity) : Prop :=
  non_empty_string (entity_surface e) /\
  non_empty_string (entity_type e) /\
  valid_span (entity_start_char e) (entity_end_char e).

Record AnnotatedDocument : Type := {
  doc_sentences : list Sentence;
  doc_entities : list Entity
}.

Definition valid_document (d : AnnotatedDocument) : Prop :=
  Forall valid_sentence (doc_sentences d) /\
  Forall valid_entity (doc_entities d).

Record AnnotationQualityConfig : Type := {
  cfg_accept_threshold : nat;
  cfg_weak_accept_threshold : nat;
  cfg_keep_weak_accept : bool;
  cfg_max_sentence_length : nat;
  cfg_max_conj_ratio_bp : nat;
  cfg_enable_morphology : bool;
  cfg_enable_dependency : bool;
  cfg_enable_distribution : bool;
  cfg_debug : bool
}.

(* Thresholds and ratios are represented as integer percents in [0, 100]. *)
Definition valid_config (cfg : AnnotationQualityConfig) : Prop :=
  0 < cfg_weak_accept_threshold cfg /\
  cfg_weak_accept_threshold cfg <= cfg_accept_threshold cfg /\
  cfg_accept_threshold cfg <= 100.

Definition default_config : AnnotationQualityConfig :=
  {|
    cfg_accept_threshold := 80;
    cfg_weak_accept_threshold := 60;
    cfg_keep_weak_accept := true;
    cfg_max_sentence_length := 60;
    cfg_max_conj_ratio_bp := 30;
    cfg_enable_morphology := true;
    cfg_enable_dependency := true;
    cfg_enable_distribution := true;
    cfg_debug := false
  |}.

Theorem default_config_valid : valid_config default_config.
Proof.
  unfold valid_config, default_config; simpl; lia.
Qed.

Record Penalties : Type := {
  structural_penalty : nat;
  dependency_penalty : nat;
  morphology_penalty : nat;
  sentence_penalty : nat;
  distribution_penalty : nat
}.

Definition penalty_bounded (p : Penalties) : Prop :=
  structural_penalty p <= 100 /\
  dependency_penalty p <= 100 /\
  morphology_penalty p <= 100 /\
  sentence_penalty p <= 100 /\
  distribution_penalty p <= 100.

(* Production weights:
   structural=0.30, dependency=0.35, morphology=0.15,
   sentence=0.10, distribution=0.10. *)
Definition weighted_penalty (p : Penalties) : nat :=
  30 * structural_penalty p +
  35 * dependency_penalty p +
  15 * morphology_penalty p +
  10 * sentence_penalty p +
  10 * distribution_penalty p.

Definition score_from_penalties (hard_failure : bool) (p : Penalties) : nat :=
  if hard_failure then 0 else 100 - (weighted_penalty p / 100).

Theorem hard_failure_score_zero :
  forall p, score_from_penalties true p = 0.
Proof.
  reflexivity.
Qed.

Theorem score_from_penalties_upper_bound :
  forall hard p, score_from_penalties hard p <= 100.
Proof.
  intros hard p.
  unfold score_from_penalties.
  destruct hard; simpl; try lia.
  set (loss := weighted_penalty p / 100).
  lia.
Qed.

Definition classify_score (cfg : AnnotationQualityConfig) (score : nat)
  : FilterLabel :=
  if Nat.leb (cfg_accept_threshold cfg) score then Accept
  else if Nat.leb (cfg_weak_accept_threshold cfg) score then WeakAccept
  else Reject.

Definition label_allowed (cfg : AnnotationQualityConfig) (label : FilterLabel)
  : bool :=
  match label with
  | Accept => true
  | WeakAccept => cfg_keep_weak_accept cfg
  | Reject => false
  end.

Theorem reject_is_never_allowed :
  forall cfg, label_allowed cfg Reject = false.
Proof.
  reflexivity.
Qed.

Theorem accept_is_always_allowed :
  forall cfg, label_allowed cfg Accept = true.
Proof.
  reflexivity.
Qed.

Theorem classify_accept_at_threshold :
  forall cfg score,
    cfg_accept_threshold cfg <= score ->
    classify_score cfg score = Accept.
Proof.
  intros cfg score Hge.
  unfold classify_score.
  destruct (Nat.leb (cfg_accept_threshold cfg) score) eqn:Hleb.
  - reflexivity.
  - apply Nat.leb_gt in Hleb. lia.
Qed.

Theorem classify_weak_between_thresholds :
  forall cfg score,
    score < cfg_accept_threshold cfg ->
    cfg_weak_accept_threshold cfg <= score ->
    classify_score cfg score = WeakAccept.
Proof.
  intros cfg score Hlt_accept Hge_weak.
  unfold classify_score.
  destruct (Nat.leb (cfg_accept_threshold cfg) score) eqn:Hacc.
  - apply Nat.leb_le in Hacc. lia.
  - destruct (Nat.leb (cfg_weak_accept_threshold cfg) score) eqn:Hweak.
    + reflexivity.
    + apply Nat.leb_gt in Hweak. lia.
Qed.

Theorem classify_reject_below_weak :
  forall cfg score,
    valid_config cfg ->
    score < cfg_weak_accept_threshold cfg ->
    classify_score cfg score = Reject.
Proof.
  intros cfg score Hcfg Hlt_weak.
  destruct Hcfg as [_ [Hweak_le_accept _]].
  unfold classify_score.
  destruct (Nat.leb (cfg_accept_threshold cfg) score) eqn:Hacc.
  - apply Nat.leb_le in Hacc. lia.
  - destruct (Nat.leb (cfg_weak_accept_threshold cfg) score) eqn:Hweak.
    + apply Nat.leb_le in Hweak. lia.
    + reflexivity.
Qed.

Theorem hard_failure_reject :
  forall cfg p,
    valid_config cfg ->
    classify_score cfg (score_from_penalties true p) = Reject.
Proof.
  intros cfg p Hcfg.
  rewrite hard_failure_score_zero.
  apply classify_reject_below_weak.
  - exact Hcfg.
  - destruct Hcfg as [Hweak_pos [_ _]]. lia.
Qed.

Record SentenceAnalysis : Type := {
  analysis_hard_failure : bool;
  analysis_penalties : Penalties;
  analysis_reasons : list QualityIssue
}.

Record AnnotationQualityResult : Type := {
  result_score : nat;
  result_label : FilterLabel;
  result_reasons : list QualityIssue;
  result_penalties : Penalties;
  result_hard_failure : bool
}.

Definition evaluate_analysis
  (cfg : AnnotationQualityConfig)
  (analysis : SentenceAnalysis) : AnnotationQualityResult :=
  let score := score_from_penalties
    (analysis_hard_failure analysis)
    (analysis_penalties analysis) in
  {|
    result_score := score;
    result_label := classify_score cfg score;
    result_reasons := analysis_reasons analysis;
    result_penalties := analysis_penalties analysis;
    result_hard_failure := analysis_hard_failure analysis
  |}.

Definition valid_quality_result (r : AnnotationQualityResult) : Prop :=
  result_score r <= 100.

Theorem evaluate_analysis_valid :
  forall cfg analysis,
    valid_quality_result (evaluate_analysis cfg analysis).
Proof.
  intros cfg analysis.
  unfold valid_quality_result, evaluate_analysis.
  simpl.
  apply score_from_penalties_upper_bound.
Qed.

Record SentenceQualityAnnotation : Type := {
  annotation_input_sentence_index : nat;
  annotation_status : FilterLabel;
  annotation_included_in_output : bool;
  annotation_result : AnnotationQualityResult
}.

Definition valid_quality_annotation (a : SentenceQualityAnnotation) : Prop :=
  valid_quality_result (annotation_result a).

(* The boolean included_in_output is generated from cfg + label in
   build_quality_annotation. *)
Definition build_quality_annotation
  (cfg : AnnotationQualityConfig)
  (sentence_index : nat)
  (analysis : SentenceAnalysis) : SentenceQualityAnnotation :=
  let result := evaluate_analysis cfg analysis in
  {|
    annotation_input_sentence_index := sentence_index;
    annotation_status := result_label result;
    annotation_included_in_output := label_allowed cfg (result_label result);
    annotation_result := result
  |}.

Fixpoint build_quality_annotations
  (cfg : AnnotationQualityConfig)
  (start_index : nat)
  (analyses : list SentenceAnalysis) : list SentenceQualityAnnotation :=
  match analyses with
  | [] => []
  | analysis :: rest =>
      build_quality_annotation cfg start_index analysis
      :: build_quality_annotations cfg (S start_index) rest
  end.

Theorem build_quality_annotations_length :
  forall cfg start analyses,
    length (build_quality_annotations cfg start analyses) = length analyses.
Proof.
  intros cfg start analyses.
  revert start.
  induction analyses as [| analysis rest IH]; intros start; simpl.
  - reflexivity.
  - rewrite IH. reflexivity.
Qed.

(* The primary output is a filtered AnnotatedDocument.  Its sentence list is the
   input sentence list filtered by the per-sentence quality policy. *)
Fixpoint filter_sentences
  (sentences : list Sentence)
  (annotations : list SentenceQualityAnnotation) : list Sentence :=
  match sentences, annotations with
  | sentence :: rest_sentences, annotation :: rest_annotations =>
      if annotation_included_in_output annotation then
        sentence :: filter_sentences rest_sentences rest_annotations
      else
        filter_sentences rest_sentences rest_annotations
  | _, _ => []
  end.

Theorem filter_sentences_length_le :
  forall sentences annotations,
    length (filter_sentences sentences annotations) <= length sentences.
Proof.
  intros sentences annotations.
  revert annotations.
  induction sentences as [| sentence rest IH]; intros annotations; simpl.
  - destruct annotations; simpl; lia.
  - destruct annotations as [| annotation rest_annotations]; simpl; try lia.
    destruct (annotation_included_in_output annotation); simpl; specialize (IH rest_annotations); lia.
Qed.

Theorem filter_sentences_valid :
  forall sentences annotations,
    Forall valid_sentence sentences ->
    Forall valid_sentence (filter_sentences sentences annotations).
Proof.
  intros sentences annotations Hvalid.
  revert annotations.
  induction Hvalid as [| sentence rest Hsentence Hrest IH]; intros annotations; simpl.
  - destruct annotations; constructor.
  - destruct annotations as [| annotation rest_annotations]; simpl.
    + constructor.
    + destruct (annotation_included_in_output annotation).
      * constructor; [exact Hsentence | apply IH].
      * apply IH.
Qed.

(* Entity filtering depends on span semantics shared with the Stanza-compatible
   document model.  This is an explicit implementation obligation for Python:
   keep only entities whose spans belong to retained sentence spans, and prove by
   tests that schema validity is preserved. *)
Parameter filter_entities_for_sentences : list Sentence -> list Entity -> list Entity.
Parameter filter_entities_preserves_validity :
  forall kept_sentences input_entities,
    Forall valid_entity input_entities ->
    Forall valid_entity
      (filter_entities_for_sentences kept_sentences input_entities).

Record AnnotationQualitySummary : Type := {
  summary_total_sentences : nat;
  summary_output_sentences : nat;
  summary_accepted : nat;
  summary_weak_accepted : nat;
  summary_rejected : nat
}.

Record AnnotationQualityDocumentStatus : Type := {
  status_annotations : list SentenceQualityAnnotation;
  status_summary : AnnotationQualitySummary
}.

Record AnnotationQualityFilterOutput : Type := {
  output_document : AnnotatedDocument;
  output_status : AnnotationQualityDocumentStatus
}.

Definition empty_summary
  (input_len output_len : nat) : AnnotationQualitySummary :=
  {|
    summary_total_sentences := input_len;
    summary_output_sentences := output_len;
    summary_accepted := 0;
    summary_weak_accepted := 0;
    summary_rejected := 0
  |}.

Definition filter_core
  (cfg : AnnotationQualityConfig)
  (document : AnnotatedDocument)
  (analyses : list SentenceAnalysis) : AnnotationQualityFilterOutput :=
  let annotations := build_quality_annotations cfg 0 analyses in
  let kept_sentences := filter_sentences (doc_sentences document) annotations in
  let kept_entities := filter_entities_for_sentences kept_sentences (doc_entities document) in
  {|
    output_document := {|
      doc_sentences := kept_sentences;
      doc_entities := kept_entities
    |};
    output_status := {|
      status_annotations := annotations;
      status_summary := empty_summary
        (length (doc_sentences document))
        (length kept_sentences)
    |}
  |}.

Definition valid_filter_output
  (input : AnnotatedDocument)
  (o : AnnotationQualityFilterOutput) : Prop :=
  valid_document (output_document o) /\
  length (status_annotations (output_status o)) = length (doc_sentences input) /\
  length (doc_sentences (output_document o)) <= length (doc_sentences input).

Theorem filter_core_status_length :
  forall cfg document analyses,
    length (status_annotations (output_status (filter_core cfg document analyses))) =
    length analyses.
Proof.
  intros cfg document analyses.
  unfold filter_core; simpl.
  apply build_quality_annotations_length.
Qed.

Theorem filter_core_output_sentence_length_le :
  forall cfg document analyses,
    length (doc_sentences (output_document (filter_core cfg document analyses))) <=
    length (doc_sentences document).
Proof.
  intros cfg document analyses.
  unfold filter_core; simpl.
  apply filter_sentences_length_le.
Qed.

Theorem filter_core_primary_output_schema :
  forall cfg document analyses,
    valid_document document ->
    valid_document (output_document (filter_core cfg document analyses)).
Proof.
  intros cfg document analyses Hdoc.
  destruct Hdoc as [Hsentences Hentities].
  unfold filter_core; simpl.
  split.
  - apply filter_sentences_valid. exact Hsentences.
  - apply filter_entities_preserves_validity. exact Hentities.
Qed.

Theorem filter_core_valid :
  forall cfg document analyses,
    valid_document document ->
    length analyses = length (doc_sentences document) ->
    valid_filter_output document (filter_core cfg document analyses).
Proof.
  intros cfg document analyses Hdoc Hlen.
  unfold valid_filter_output.
  repeat split.
  - apply filter_core_primary_output_schema. exact Hdoc.
  - rewrite filter_core_status_length. exact Hlen.
  - apply filter_core_output_sentence_length_le.
Qed.

Theorem filter_core_deterministic :
  forall cfg document analyses,
    filter_core cfg document analyses = filter_core cfg document analyses.
Proof.
  reflexivity.
Qed.

Definition DebugTrace : Type := list string.

Definition observe_debug
  (output : AnnotationQualityFilterOutput)
  (_trace : DebugTrace) : AnnotationQualityFilterOutput :=
  output.

Theorem debug_does_not_change_filter_output :
  forall output trace,
    observe_debug output trace = output.
Proof.
  reflexivity.
Qed.

Inductive CliStatus : Type :=
| CliOk (output : AnnotationQualityFilterOutput)
| CliExpectedDataError
| CliSystemFailure.

Definition cli_exit_code (status : CliStatus) : ExitCode :=
  match status with
  | CliOk _ => Success
  | CliExpectedDataError => ExpectedError
  | CliSystemFailure => SystemError
  end.

Definition cli_stdout (status : CliStatus)
  : option AnnotatedDocument :=
  match status with
  | CliOk output => Some (output_document output)
  | CliExpectedDataError => None
  | CliSystemFailure => None
  end.

Theorem cli_stdout_is_primary_document :
  forall output,
    cli_stdout (CliOk output) = Some (output_document output).
Proof.
  reflexivity.
Qed.


Theorem cli_exit_code_mapping :
  forall output,
    cli_exit_code (CliOk output) = Success /\
    cli_exit_code CliExpectedDataError = ExpectedError /\
    cli_exit_code CliSystemFailure = SystemError.
Proof.
  intro output.
  repeat split; reflexivity.
Qed.

Theorem non_success_has_no_stdout_payload :
  forall status,
    cli_exit_code status <> Success ->
    cli_stdout status = None.
Proof.
  intros status Hnot_success.
  destruct status as [output | |]; simpl in *.
  - contradiction.
  - reflexivity.
  - reflexivity.
Qed.

End AnnotationQualityFilterSpec.
```

### Coq ↔ Python mapping

| Coq symbol | Python responsibility |
| --- | --- |
| `AnnotatedDocument` | input model and primary filtered output model, aligned with `stanza_annotator` schema |
| `valid_document` | runtime validation + property tests for schema invariants |
| `AnnotationQualityConfig` | immutable resolved config object |
| `cfg_keep_weak_accept` | `retention_policy`: `ACCEPT_AND_WEAK_ACCEPT` vs `ACCEPT_ONLY` |
| `valid_config` | config validation before `core` |
| `Penalties` | normalized penalty values from Python checkers |
| `SentenceAnalysis` | pure result of structural/dependency/morphology/sentence/distribution checks |
| `score_from_penalties` | production scoring formula in integer basis points |
| `classify_score` | `ACCEPT` / `WEAK_ACCEPT` / `REJECT` threshold mapping |
| `label_allowed` | inclusion policy for primary filtered output |
| `evaluate_analysis` | pure per-sentence scoring function |
| `build_quality_annotations` | ordered status generation for all input sentences |
| `filter_sentences` | primary output sentence filtering |
| `filter_entities_for_sentences` | entity span filtering implementation obligation |
| `filter_core` | pure document-level function returning filtered `AnnotatedDocument` plus status |
| `filter_core_primary_output_schema` | primary output remains valid `AnnotatedDocument` |
| `filter_core_status_length` | one status annotation per input sentence |
| `filter_core_output_sentence_length_le` | filtered output cannot contain more sentences than input |
| `debug_does_not_change_filter_output` | debug only increases observability |
| `cli_stdout_is_primary_document` | CLI stdout/default output is the primary filtered `AnnotatedDocument`, not the status wrapper |
| `cli_exit_code_mapping` | CLI exit-code contract |
| `non_success_has_no_stdout_payload` | no partial stdout on expected/system errors |

## 12. Testing obligations

Unit tests:

- validate input `AnnotatedDocument` schema;
- validate config resolution and config errors;
- verify hard failures always produce `REJECT`, `score = 0.0`, `included_in_output = false`;
- verify score bounds `[0.0, 1.0]`;
- verify threshold mapping;
- verify `output.document` schema equals `stanza_annotator` `AnnotatedDocument` schema;
- verify `output.document.sentences` is an order-preserving subsequence of input sentences;
- verify no `REJECT` sentence is present in `output.document.sentences`;
- verify `ACCEPT_ONLY` excludes `WEAK_ACCEPT` from `output.document.sentences`;
- verify default policy includes `ACCEPT` and `WEAK_ACCEPT`;
- verify `status.annotations.length == input.document.sentences.length`;
- verify `input_sentence_index` ordering;
- verify `output_sentence_index` exists only for retained sentences;
- verify entity filtering keeps only entities attached to retained sentence spans;
- verify disabled checks do not contribute issues or penalties;
- verify stdout/stderr separation;
- verify exit code mapping;
- verify debug mode does not change payload.

Property-based tests are recommended for:

- span invariants;
- head-index validation;
- root-count validation;
- score bounds under arbitrary normalized penalties;
- deterministic output for repeated calls;
- order-preserving subsequence property;
- stability of JSON serialization;
- equivalence between debug and non-debug output payloads.

Coq-related checks:

- maintain `AnnotationQualityFilterSpec.v` as the checked Coq specification;
- run `coqc AnnotationQualityFilterSpec.v` in CI;
- fail CI if the specification no longer compiles;
- fail CI if a theorem is removed, weakened, or replaced by an unmarked assumption;
- every public Python function covered by the Coq mapping must have unit/property tests.

## 13. Security

- sensitive input data must not be logged in full;
- debug logs must be gated by `--debug` / local config;
- errors must not expose internal paths, secrets or stack traces unless explicitly enabled for local debugging;
- input must be validated before `core`;
- logs must never alter the result.

## 14. Evolution rules

A breaking change is any change that:

- changes public Python API;
- changes CLI contract;
- changes primary `output.document` schema or serialization semantics;
- changes default thresholds or weights;
- changes default retention policy;
- changes hard failure semantics;
- weakens or invalidates a proved Coq property;
- changes `AnnotatedDocument` compatibility with `stanza_annotator`.

Every such change requires:

- architecture update;
- tests update;
- Coq specification update or explicit declaration that the previous proof no longer applies;
- changelog entry.

## 15. Definition of Done

The module is ready when:

- input contract matches `stanza_annotator` `AnnotatedDocument`;
- primary output is filtered `AnnotatedDocument` with the same schema as `stanza_annotator` output;
- secondary status output explains filtering decisions for all input sentences;
- public API is minimal and exported only via `__init__.py`;
- public API is fully typed;
- `mypy --strict` passes;
- `ruff` and `black` pass;
- unit tests are deterministic and isolated from external IO;
- core contains no IO and no global state;
- CLI keeps stdout/stderr separated;
- CLI supports `--debug` / `-d`;
- debug mode does not change result payload;
- input validation happens before core;
- all expected errors map to exit code `1`;
- system errors map to exit code `2+`;
- no partial results are emitted;
- Coq specification compiles in CI;
- Coq theorem ↔ Python function mapping is maintained;
- implementation tests check the documented invariants.
