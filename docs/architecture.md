annotation_quality_filter — модуль, отвечающий за оценку качества лингвистических аннотаций предложений, полученных из Stanza (или аналогичных парсеров), и принятие решения об их пригодности для дальнейшего анализа.

Stanza для первой версии - v1

Модуль:

✔ анализирует структуру аннотаций
✔ выявляет ошибки и аномалии
✔ вычисляет quality score
✔ классифицирует предложения по качеству

nput
interface AnnotatedSentence {
  text: string;
  words: Word[];
}

Где Word:

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

Output
interface AnnotationQualityResult {
  score: number; // 0.0 – 1.0

  label: "ACCEPT" | "WEAK_ACCEPT" | "REJECT";

  reasons: QualityIssue[];

  diagnostics: {
    structural: StructuralMetrics;
    dependency: DependencyMetrics;
    morphology: MorphologyMetrics;
    sentence: SentenceMetrics;
  };
}

Основные задачи
1. Structural validation

Проверка корректности дерева:

✔ ровно один root
✔ валидные head индексы
✔ отсутствие разрывов
✔ связность графа
2. Dependency consistency

Проверка логики зависимостей:

✔ наличие subject у finite verb
✔ корректность aux → verb
✔ адекватность conj / relcl / acl
✔ отсутствие аномальных распределений deprel
3. Morphological consistency

Проверка согласованности признаков:

✔ finite verbs имеют Tense
✔ корректность VerbForm
✔ базовое согласование subject–verb
✔ отсутствие аномально пустых feats
4. Sentence-level heuristics

Проверка свойств предложения:

✔ разумная длина
✔ отсутствие \n
✔ наличие глагола
✔ адекватная пунктуация
5. Distribution checks

Проверка “здоровья” аннотации:

✔ нормальное распределение POS
✔ нормальное распределение deprel
✔ отсутствие перекосов (например, слишком много conj)
📊 Quality scoring
Общая формула
score = 1.0
        - structural_penalty
        - dependency_penalty
        - morphology_penalty
        - sentence_penalty
Классификация
score ≥ 0.8     → ACCEPT
0.5 – 0.8       → WEAK_ACCEPT
< 0.5           → REJECT
🚨 Типы ошибок
type QualityIssue =
  | "MULTIPLE_ROOTS"
  | "NO_ROOT"
  | "INVALID_HEAD_INDEX"
  | "NO_MAIN_VERB"
  | "MISSING_SUBJECT"
  | "BROKEN_AUX_CHAIN"
  | "EXCESSIVE_CONJ"
  | "INVALID_RELCL_ATTACHMENT"
  | "MISSING_TENSE"
  | "EMPTY_MORPHOLOGY"
  | "TOO_LONG_SENTENCE"
  | "CONTAINS_NEWLINE"
  | "DEPREL_DISTRIBUTION_ANOMALY";
⚙️ Конфигурация
interface AnnotationQualityConfig {
  thresholds: {
    accept: number;      // default 0.8
    weak_accept: number; // default 0.5
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
🧠 Дизайн-принципы
1. Fail-fast
явные ошибки → сразу REJECT
2. Heuristic, not strict
модуль НЕ гарантирует истинность,
он оценивает вероятность корректности
3. Parser-agnostic
работает не только со Stanza,
но с любым UD-подобным источником
4. Transparent diagnostics
каждое решение объяснимо через reasons
5. Non-destructive
модуль НЕ изменяет аннотации
🚫 Non-goals
❌ исправление dependency
❌ исправление morphology
❌ извлечение грамматики
❌ semantic анализ
🧪 Использование
const result = annotationQualityFilter.evaluate(sentence);

if (result.label === "REJECT") {
  skip(sentence);
}
📈 Расширяемость

Модуль должен позволять:

✔ добавлять новые проверки
✔ изменять веса штрафов
✔ обучать scoring (в будущем)
✔ логировать статистику качества корпуса

production-ready scoring

Общий принцип
score = 1.0 - Σ(weight_i * penalty_i)

Но важно:

👉 не все ошибки равны
👉 есть hard failures и soft penalties

🚨 1. Hard failures (сразу REJECT)

Если выполняется хоть одно:

score = 0.0
label = REJECT
Список
Ошибка	Причина
NO_ROOT	дерево невалидно
MULTIPLE_ROOTS	сломан parse
INVALID_HEAD_INDEX	битые ссылки
EMPTY_SENTENCE	нет слов
TOKEN_COUNT < 2	неинформативно
⚖️ 2. Soft penalties (веса)
📊 Итоговая формула
score = 1.0
  - 0.30 * structural_penalty
  - 0.35 * dependency_penalty
  - 0.15 * morphology_penalty
  - 0.10 * sentence_penalty
  - 0.10 * distribution_penalty

👉 dependency — самый важный сигнал

🔍 3. Детализация penalties
3.1 Structural penalty (вес: 0.30)
structural_penalty ∈ [0,1]
Проверка	Penalty
нет root	1.0 (hard)
>1 root	1.0 (hard)
несвязное дерево	0.7
orphan nodes	0.5
3.2 Dependency penalty (вес: 0.35 🔥)
dependency_penalty ∈ [0,1]
Ключевые эвристики
1. Нет subject у finite verb
if finite_verb and not subject:
    penalty += 0.4
2. Broken aux chain
aux → не у VERB
+0.25
3. Conj explosion
conj_ratio = conj_count / total_words
Значение	Penalty
> 0.3	+0.3
> 0.5	+0.5
4. Suspicious deprel pairs
nsubj → ADJ
obj   → ADV
+0.3
5. relcl без head noun
+0.25
3.3 Morphology penalty (вес: 0.15)
morphology_penalty ∈ [0,1]
1. Missing tense
if VerbForm=Fin and no Tense:
    +0.3
2. Empty feats ratio
empty_ratio = words_without_feats / total_words
Значение	Penalty
> 0.5	+0.2
> 0.7	+0.4
3. Agreement mismatch
+0.2
3.4 Sentence penalty (вес: 0.10)
sentence_penalty ∈ [0,1]
1. Length
Длина	Penalty
> 40	+0.1
> 60	+0.2
> 80	+0.4
2. Newlines
+0.2
3. No verb
+0.5
3.5 Distribution penalty (вес: 0.10)
1. POS imbalance
if NOUN_ratio > 0.6:
    +0.2
2. deprel imbalance
if one_label_ratio > 0.5:
    +0.3
🧮 4. Финальный расчет
def final_score(p):
    score = 1.0 - (
        0.30 * p.structural +
        0.35 * p.dependency +
        0.15 * p.morphology +
        0.10 * p.sentence +
        0.10 * p.distribution
    )
    return max(score, 0.0)
🏷️ 5. Thresholds (production)
score ≥ 0.80 → ACCEPT
0.60–0.80   → WEAK_ACCEPT
< 0.60      → REJECT
📊 6. Пример
Хорошее предложение
She has been reading a book.
structural = 0
dependency = 0
morphology = 0
sentence = 0
distribution = 0

score = 1.0
Плохое (типично broken)
What passed at this interview...
dependency: conj misuse → 0.4
sentence: newline → 0.2
morphology: weak → 0.2

score = 1 - (0.35*0.4 + 0.10*0.2 + 0.15*0.2)
      ≈ 0.73 → WEAK_ACCEPT
🔥 7. Практические улучшения (важно)
1. Confidence buckets
HIGH → grammar extraction
MEDIUM → статистика
LOW → discard
2. Logging (обязательно)
{
  "score": 0.62,
  "issues": ["MISSING_SUBJECT", "EXCESSIVE_CONJ"]
}
3. Corpus-level monitoring
средний score по книге

🧠 Главный инсайт
не нужно идеально оценивать каждое предложение
нужно стабильно отсеивать худшие 20–30%
