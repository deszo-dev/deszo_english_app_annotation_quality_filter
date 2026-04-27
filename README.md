# Annotation Quality Filter

## English

`annotation_quality_filter` is a module for evaluating the quality of linguistic sentence annotations produced by Stanza or another Universal Dependencies-like parser. It checks whether an annotated sentence is structurally valid, linguistically plausible, and suitable for downstream analysis.

The first target parser version is Stanza v1.

### Purpose

The module is designed to filter out low-quality parser output before it is used by grammar extraction, corpus statistics, or other language-learning features.

It does not modify annotations. Instead, it returns a transparent quality decision with a numeric score, a label, and diagnostic reasons.

### Main Capabilities

- Validate dependency tree structure.
- Detect parser errors and annotation anomalies.
- Calculate a quality score from `0.0` to `1.0`.
- Classify sentences as `ACCEPT`, `WEAK_ACCEPT`, or `REJECT`.
- Explain every decision through issue codes and diagnostics.
- Support parser-agnostic UD-like input, not only Stanza.

### Input

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

### Output

```ts
interface AnnotationQualityResult {
  score: number;
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

### Quality Model

The production scoring model uses hard failures and weighted soft penalties:

```text
score = 1.0
  - 0.30 * structural_penalty
  - 0.35 * dependency_penalty
  - 0.15 * morphology_penalty
  - 0.10 * sentence_penalty
  - 0.10 * distribution_penalty
```

Hard failures immediately reject the sentence with `score = 0.0`. Examples include missing root, multiple roots, invalid head indexes, empty sentences, and sentences with fewer than two tokens.

Default production thresholds:

- `score >= 0.80` -> `ACCEPT`
- `0.60 <= score < 0.80` -> `WEAK_ACCEPT`
- `score < 0.60` -> `REJECT`

### Checks

The module is expected to perform these groups of checks:

- Structural validation: root count, valid head indexes, connectedness, orphan nodes.
- Dependency consistency: finite verb subjects, auxiliary chains, conjunction ratio, suspicious dependency relations, relative clause attachment.
- Morphological consistency: missing tense, invalid or empty morphology, basic subject-verb agreement.
- Sentence-level heuristics: length, newlines, absence of verbs, punctuation sanity.
- Distribution checks: POS imbalance, dependency relation imbalance, unusual relation concentration.

### Design Principles

- Fail fast on broken dependency trees.
- Prefer heuristics over strict linguistic truth claims.
- Keep parser integration generic and UD-like.
- Make every decision explainable.
- Never mutate source annotations.
- Allow new checks, custom penalty weights, corpus-level logging, and future trained scoring.

### Usage Example

```ts
const result = annotationQualityFilter.evaluate(sentence);

if (result.label === "REJECT") {
  skip(sentence);
}
```

### Python Usage

```py
from annotation_quality_filter import evaluate

result = evaluate(sentence)

if result.label == "REJECT":
    skip(sentence)
```

### CLI Usage

```bash
python -m annotation_quality_filter hollow.annotations.json --pretty
python -m annotation_quality_filter hollow.annotations.json --limit 20 --jsonl
python -m annotation_quality_filter hollow.annotations.json -o quality-results.json --pretty
```

The CLI accepts a single sentence object, a list of sentence objects, or a Stanza-style JSON object with a top-level `sentences` array.

### License And Use

This project is intended to be published with source code available for non-commercial use. Commercial use is not permitted unless the project owner grants a separate license.

The repository includes a non-commercial source-available `LICENSE`. This is intentionally not a permissive OSI-style open-source license because commercial use is restricted.

See [docs/architecture.en.md](docs/architecture.en.md) for the English architecture specification.

---

## Русский

`annotation_quality_filter` — модуль для оценки качества лингвистических аннотаций предложений, полученных из Stanza или другого UD-подобного парсера. Он проверяет, насколько аннотированное предложение структурно корректно, лингвистически правдоподобно и пригодно для дальнейшего анализа.

Целевая версия парсера для первой версии модуля: Stanza v1.

### Назначение

Модуль нужен, чтобы отсеивать низкокачественный результат парсинга до того, как он попадет в извлечение грамматики, корпусную статистику или другие функции приложения для изучения английского языка.

Модуль не изменяет аннотации. Он возвращает прозрачное решение о качестве: числовой score, итоговую метку и диагностические причины.

### Основные возможности

- Проверка структуры dependency tree.
- Выявление ошибок парсера и аномалий аннотации.
- Расчет quality score от `0.0` до `1.0`.
- Классификация предложений как `ACCEPT`, `WEAK_ACCEPT` или `REJECT`.
- Объяснение каждого решения через issue-коды и диагностику.
- Поддержка UD-подобного входа, не привязанного строго к Stanza.

### Вход

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

### Выход

```ts
interface AnnotationQualityResult {
  score: number;
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

### Модель оценки качества

Production-модель использует hard failures и взвешенные soft penalties:

```text
score = 1.0
  - 0.30 * structural_penalty
  - 0.35 * dependency_penalty
  - 0.15 * morphology_penalty
  - 0.10 * sentence_penalty
  - 0.10 * distribution_penalty
```

Hard failures сразу отклоняют предложение с `score = 0.0`. Примеры: нет root, несколько root, невалидные head-индексы, пустое предложение, меньше двух токенов.

Production-пороги по умолчанию:

- `score >= 0.80` -> `ACCEPT`
- `0.60 <= score < 0.80` -> `WEAK_ACCEPT`
- `score < 0.60` -> `REJECT`

### Проверки

Ожидаемые группы проверок:

- Structural validation: количество root, валидность head-индексов, связность дерева, orphan nodes.
- Dependency consistency: subject у finite verb, цепочки aux, доля conj, подозрительные dependency-связи, attachment для relcl.
- Morphological consistency: отсутствие Tense, некорректная или пустая морфология, базовое subject-verb agreement.
- Sentence-level heuristics: длина, переносы строк, отсутствие глагола, базовая пунктуация.
- Distribution checks: перекос POS, перекос dependency relation, необычная концентрация одного отношения.

### Дизайн-принципы

- Fail-fast для явно сломанных dependency trees.
- Эвристическая оценка вместо претензии на абсолютную лингвистическую истинность.
- Parser-agnostic интеграция через UD-подобные данные.
- Объяснимость каждого решения.
- Отсутствие мутаций исходных аннотаций.
- Расширяемость: новые проверки, настраиваемые веса штрафов, логирование на уровне корпуса и будущий trainable scoring.

### Пример использования

```ts
const result = annotationQualityFilter.evaluate(sentence);

if (result.label === "REJECT") {
  skip(sentence);
}
```

### Использование в Python

```py
from annotation_quality_filter import evaluate

result = evaluate(sentence)

if result.label == "REJECT":
    skip(sentence)
```

### Использование CLI

```bash
python -m annotation_quality_filter hollow.annotations.json --pretty
python -m annotation_quality_filter hollow.annotations.json --limit 20 --jsonl
python -m annotation_quality_filter hollow.annotations.json -o quality-results.json --pretty
```

CLI принимает один объект предложения, список предложений или Stanza-style JSON с массивом `sentences` на верхнем уровне.

### Лицензия и использование

Проект планируется публиковать с доступным исходным кодом для некоммерческого использования. Коммерческое использование запрещено, если владелец проекта не выдал отдельную лицензию.

В репозитории добавлен non-commercial source-available `LICENSE`. Это намеренно не permissive OSI-style open-source лицензия, потому что коммерческое использование ограничено.

Английская версия архитектуры находится в [docs/architecture.en.md](docs/architecture.en.md).
