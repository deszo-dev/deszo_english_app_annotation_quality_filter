from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
from typing import Any, Iterable

from .models import (
    AnnotatedDocument,
    AnnotationQualityAnnotation,
    AnnotationQualityConfig,
    AnnotationQualityDocumentStatus,
    AnnotationQualityFilterOutput,
    AnnotationQualityResult,
    AnnotationQualitySummary,
    Entity,
    FilterStatus,
    InputValidationError,
    Sentence,
    validate_config,
)

VERB_UPOS = {"VERB", "AUX"}
NOUN_LIKE_UPOS = {"NOUN", "PROPN", "PRON"}
SUBJECT_DEPRELS = {"nsubj", "nsubj:pass", "csubj", "csubj:pass", "expl"}
PUNCT_UPOS = {"PUNCT", "SYM"}


class AnnotationQualityFilter:
    def __init__(self, config: AnnotationQualityConfig | None = None) -> None:
        self.config = config or AnnotationQualityConfig()
        validate_config(self.config)

    def filter_document(self, document: AnnotatedDocument) -> AnnotatedDocument:
        """Return the primary filtered document in stanza_annotator format."""
        return self.filter_with_status(document).document

    def filter_with_status(
        self, document: AnnotatedDocument
    ) -> AnnotationQualityFilterOutput:
        """Return filtered document plus filtering status for all input sentences."""
        validate_document(document)
        sentences = document["sentences"]

        annotations: list[AnnotationQualityAnnotation] = []
        kept_sentences: list[Sentence] = []

        for input_index, sentence in enumerate(sentences):
            annotation = self.evaluate_sentence(sentence, input_index)
            output_index = len(kept_sentences) if annotation.included_in_output else None
            if annotation.included_in_output:
                kept_sentences.append(deepcopy(sentence))
            annotations.append(replace(annotation, output_sentence_index=output_index))

        kept_entities = filter_entities_for_sentences(
            kept_sentences,
            document["entities"],
            self.config,
        )
        filtered_document: AnnotatedDocument = {
            "sentences": kept_sentences,
            "entities": kept_entities,
        }
        status = AnnotationQualityDocumentStatus(
            annotations=annotations,
            summary=summarize_status(annotations, len(kept_sentences)),
            config_version=self.config.config_version,
            retention_policy=self.config.retention_policy,
        )
        return AnnotationQualityFilterOutput(document=filtered_document, status=status)

    def evaluate_sentence(
        self, sentence: Sentence, input_sentence_index: int
    ) -> AnnotationQualityAnnotation:
        """Evaluate one sentence annotation and return its filter status."""
        result = self._evaluate(sentence)
        included = label_allowed(self.config, result.label)
        return AnnotationQualityAnnotation(
            input_sentence_index=input_sentence_index,
            sentence_text=str(sentence["text"]),
            included_in_output=included,
            status=result.label,
            result=result,
        )

    def with_config(self, **overrides: Any) -> "AnnotationQualityFilter":
        return AnnotationQualityFilter(replace(self.config, **overrides))

    def _evaluate(self, sentence: Sentence) -> AnnotationQualityResult:
        text = str(sentence.get("text") or "")
        words = normalize_words(sentence)
        reasons: set[str] = set()

        hard_failure = self._collect_hard_failures(words, reasons)
        if hard_failure:
            return AnnotationQualityResult(
                score=0.0,
                label="REJECT",
                reasons=sorted(reasons),
                diagnostics=self._empty_diagnostics(text, words, hard_failure=True),
            )

        structural = self._structural_metrics(words, reasons)
        dependency = (
            self._dependency_metrics(words, reasons)
            if self.config.checks.enable_dependency
            else {"penalty": 0.0, "enabled": False}
        )
        morphology = (
            self._morphology_metrics(words, reasons)
            if self.config.checks.enable_morphology
            else {"penalty": 0.0, "enabled": False}
        )
        sentence_metrics = self._sentence_metrics(text, words, reasons)
        distribution = (
            self._distribution_metrics(words, reasons)
            if self.config.checks.enable_distribution
            else {"penalty": 0.0, "enabled": False}
        )

        score = self._final_score(
            structural["penalty"],
            dependency["penalty"],
            morphology["penalty"],
            sentence_metrics["penalty"],
            distribution["penalty"],
        )

        return AnnotationQualityResult(
            score=score,
            label=self._label(score),
            reasons=sorted(reasons),
            diagnostics={
                "structural": structural,
                "dependency": dependency,
                "morphology": morphology,
                "sentence": sentence_metrics,
                "distribution": distribution,
            },
        )

    def _collect_hard_failures(self, words: list[dict[str, Any]], reasons: set[str]) -> bool:
        if not words:
            reasons.add("EMPTY_SENTENCE")
            return True

        if len(words) < self.config.limits.min_token_count:
            reasons.add("TOKEN_COUNT_LT_2")
            return True

        root_count = sum(1 for word in words if word.get("head") == 0)
        if root_count == 0:
            reasons.add("NO_ROOT")
        elif root_count > 1:
            reasons.add("MULTIPLE_ROOTS")

        if any(not is_valid_head(word.get("head"), len(words)) for word in words):
            reasons.add("INVALID_HEAD_INDEX")

        return bool({"NO_ROOT", "MULTIPLE_ROOTS", "INVALID_HEAD_INDEX"} & reasons)

    def _structural_metrics(self, words: list[dict[str, Any]], reasons: set[str]) -> dict[str, Any]:
        connected = is_connected_tree(words)
        orphan_count = count_orphans(words)
        penalty = 0.0

        if not connected:
            penalty = max(penalty, 0.7)
            reasons.add("DISCONNECTED_TREE")
        if orphan_count:
            penalty = max(penalty, 0.5)
            reasons.add("ORPHAN_NODES")

        return {
            "penalty": clamp01(penalty),
            "root_count": sum(1 for word in words if word.get("head") == 0),
            "connected": connected,
            "orphan_count": orphan_count,
            "token_count": len(words),
        }

    def _dependency_metrics(self, words: list[dict[str, Any]], reasons: set[str]) -> dict[str, Any]:
        by_head = children_by_head(words)
        penalty = 0.0
        finite_verbs = 0
        finite_verbs_without_subject = 0
        broken_aux = 0
        suspicious_pairs = 0
        invalid_relcl = 0

        for index, word in enumerate(words, start=1):
            if is_finite_verb(word):
                finite_verbs += 1
                if not has_subject_child(by_head[index]):
                    finite_verbs_without_subject += 1

            if base_deprel(word) == "aux":
                head = get_head_word(words, word)
                if head is not None and head.get("upos") not in VERB_UPOS:
                    broken_aux += 1

            if is_suspicious_dependency_pair(words, word):
                suspicious_pairs += 1

            if base_deprel(word) == "relcl":
                head = get_head_word(words, word)
                if head is None or head.get("upos") not in NOUN_LIKE_UPOS:
                    invalid_relcl += 1

        if finite_verbs_without_subject:
            penalty += min(0.4 * finite_verbs_without_subject, 0.8)
            reasons.add("MISSING_SUBJECT")
        if broken_aux:
            penalty += min(0.25 * broken_aux, 0.5)
            reasons.add("BROKEN_AUX_CHAIN")

        conj_count = sum(1 for word in words if base_deprel(word) == "conj")
        conj_ratio = conj_count / len(words)
        if conj_ratio > self.config.limits.severe_conj_ratio:
            penalty += 0.5
            reasons.add("EXCESSIVE_CONJ")
        elif conj_ratio > self.config.limits.max_conj_ratio:
            penalty += 0.3
            reasons.add("EXCESSIVE_CONJ")

        if suspicious_pairs:
            penalty += min(0.3 * suspicious_pairs, 0.6)
            reasons.add("SUSPICIOUS_DEPREL_PAIR")
        if invalid_relcl:
            penalty += min(0.25 * invalid_relcl, 0.5)
            reasons.add("INVALID_RELCL_ATTACHMENT")

        return {
            "penalty": clamp01(penalty),
            "finite_verb_count": finite_verbs,
            "finite_verbs_without_subject": finite_verbs_without_subject,
            "broken_aux_count": broken_aux,
            "conj_count": conj_count,
            "conj_ratio": round(conj_ratio, 4),
            "suspicious_pair_count": suspicious_pairs,
            "invalid_relcl_count": invalid_relcl,
        }

    def _morphology_metrics(self, words: list[dict[str, Any]], reasons: set[str]) -> dict[str, Any]:
        penalty = 0.0
        missing_tense = 0
        empty_feats_count = 0

        for word in words:
            feats = parse_feats(word.get("feats"))
            if is_finite_verb(word) and not feats.get("Tense"):
                missing_tense += 1
            if word.get("upos") not in PUNCT_UPOS and not feats:
                empty_feats_count += 1

        if missing_tense:
            penalty += min(0.3 * missing_tense, 0.6)
            reasons.add("MISSING_TENSE")

        empty_ratio = empty_feats_count / len(words)
        if empty_ratio > 0.7:
            penalty += 0.4
            reasons.add("EMPTY_MORPHOLOGY")
        elif empty_ratio > 0.5:
            penalty += 0.2
            reasons.add("EMPTY_MORPHOLOGY")

        agreement_mismatches = count_subject_verb_agreement_mismatches(words)
        if agreement_mismatches:
            penalty += min(0.2 * agreement_mismatches, 0.4)
            reasons.add("AGREEMENT_MISMATCH")

        return {
            "penalty": clamp01(penalty),
            "missing_tense_count": missing_tense,
            "empty_feats_count": empty_feats_count,
            "empty_feats_ratio": round(empty_ratio, 4),
            "agreement_mismatch_count": agreement_mismatches,
        }

    def _sentence_metrics(
        self, text: str, words: list[dict[str, Any]], reasons: set[str]
    ) -> dict[str, Any]:
        penalty = 0.0
        token_count = len(words)
        has_newline = "\n" in text or "\r" in text
        has_verb = any(word.get("upos") in VERB_UPOS for word in words)

        if token_count > self.config.limits.long_sentence_hard:
            penalty += 0.4
            reasons.add("TOO_LONG_SENTENCE")
        elif token_count > self.config.limits.max_sentence_length:
            penalty += 0.2
            reasons.add("TOO_LONG_SENTENCE")
        elif token_count > self.config.limits.long_sentence_soft:
            penalty += 0.1

        if has_newline:
            penalty += 0.2
            reasons.add("CONTAINS_NEWLINE")
        if not has_verb:
            penalty += 0.5
            reasons.add("NO_MAIN_VERB")

        return {
            "penalty": clamp01(penalty),
            "token_count": token_count,
            "has_newline": has_newline,
            "has_verb": has_verb,
        }

    def _distribution_metrics(self, words: list[dict[str, Any]], reasons: set[str]) -> dict[str, Any]:
        penalty = 0.0
        upos_counts = Counter(word.get("upos") for word in words if word.get("upos"))
        deprel_counts = Counter(base_deprel(word) for word in words if word.get("deprel"))
        noun_ratio = upos_counts["NOUN"] / len(words)
        most_common_deprel, most_common_deprel_count = (
            deprel_counts.most_common(1)[0] if deprel_counts else ("", 0)
        )
        one_label_ratio = most_common_deprel_count / len(words)

        if noun_ratio > 0.6:
            penalty += 0.2
            reasons.add("POS_DISTRIBUTION_ANOMALY")
        if one_label_ratio > 0.5:
            penalty += 0.3
            reasons.add("DEPREL_DISTRIBUTION_ANOMALY")

        return {
            "penalty": clamp01(penalty),
            "upos_counts": dict(upos_counts),
            "deprel_counts": dict(deprel_counts),
            "noun_ratio": round(noun_ratio, 4),
            "dominant_deprel": most_common_deprel,
            "dominant_deprel_ratio": round(one_label_ratio, 4),
        }

    def _final_score(
        self,
        structural_penalty: float,
        dependency_penalty: float,
        morphology_penalty: float,
        sentence_penalty: float,
        distribution_penalty: float,
    ) -> float:
        weights = self.config.weights
        score = 1.0 - (
            weights.structural * structural_penalty
            + weights.dependency * dependency_penalty
            + weights.morphology * morphology_penalty
            + weights.sentence * sentence_penalty
            + weights.distribution * distribution_penalty
        )
        return round(max(min(score, 1.0), 0.0), 4)

    def _label(self, score: float) -> FilterStatus:
        thresholds = self.config.thresholds
        if score >= thresholds.accept:
            return "ACCEPT"
        if score >= thresholds.weak_accept:
            return "WEAK_ACCEPT"
        return "REJECT"

    def _empty_diagnostics(
        self, text: str, words: list[dict[str, Any]], hard_failure: bool
    ) -> dict[str, Any]:
        return {
            "structural": {
                "penalty": 1.0,
                "root_count": sum(1 for word in words if word.get("head") == 0),
                "connected": False,
                "orphan_count": count_orphans(words) if words else 0,
                "token_count": len(words),
                "hard_failure": hard_failure,
            },
            "dependency": {"penalty": 0.0},
            "morphology": {"penalty": 0.0},
            "sentence": {
                "penalty": 0.0,
                "token_count": len(words),
                "has_newline": "\n" in text or "\r" in text,
                "has_verb": any(word.get("upos") in VERB_UPOS for word in words),
            },
            "distribution": {"penalty": 0.0},
        }


def evaluate_sentence(
    sentence: Sentence,
    input_sentence_index: int = 0,
    config: AnnotationQualityConfig | None = None,
) -> AnnotationQualityAnnotation:
    return AnnotationQualityFilter(config).evaluate_sentence(sentence, input_sentence_index)


def filter_document(
    document: AnnotatedDocument, config: AnnotationQualityConfig | None = None
) -> AnnotatedDocument:
    return AnnotationQualityFilter(config).filter_document(document)


def filter_with_status(
    document: AnnotatedDocument, config: AnnotationQualityConfig | None = None
) -> AnnotationQualityFilterOutput:
    return AnnotationQualityFilter(config).filter_with_status(document)


def validate_document(document: AnnotatedDocument) -> None:
    if not isinstance(document, dict):
        raise InputValidationError("input must be an AnnotatedDocument object")
    if not isinstance(document.get("sentences"), list):
        raise InputValidationError("AnnotatedDocument.sentences must be present and be a list")
    if not isinstance(document.get("entities"), list):
        raise InputValidationError("AnnotatedDocument.entities must be present and be a list")

    for index, sentence in enumerate(document["sentences"]):
        validate_sentence(sentence, index)
    for index, entity in enumerate(document["entities"]):
        validate_entity(entity, index)


def validate_sentence(sentence: Any, index: int) -> None:
    if not isinstance(sentence, dict):
        raise InputValidationError(f"sentences[{index}] must be an object")
    if not isinstance(sentence.get("text"), str) or not sentence["text"]:
        raise InputValidationError(f"sentences[{index}].text must be a non-empty string")
    if not isinstance(sentence.get("tokens"), list):
        raise InputValidationError(f"sentences[{index}].tokens must be present and be a list")
    if not isinstance(sentence.get("words"), list):
        raise InputValidationError(f"sentences[{index}].words must be present and be a list")

    for token_index, token in enumerate(sentence["tokens"]):
        if not isinstance(token, dict):
            raise InputValidationError(f"sentences[{index}].tokens[{token_index}] must be an object")
        if not isinstance(token.get("text"), str) or not token["text"]:
            raise InputValidationError(
                f"sentences[{index}].tokens[{token_index}].text must be a non-empty string"
            )
        if not isinstance(token.get("words"), list) or not token["words"]:
            raise InputValidationError(
                f"sentences[{index}].tokens[{token_index}].words must be a non-empty list"
            )
        for token_word_index, word in enumerate(token["words"]):
            validate_word(
                word,
                f"sentences[{index}].tokens[{token_index}].words[{token_word_index}]",
            )

    for word_index, word in enumerate(sentence["words"]):
        validate_word(word, f"sentences[{index}].words[{word_index}]")


def validate_word(word: Any, path: str) -> None:
    if not isinstance(word, dict):
        raise InputValidationError(f"{path} must be an object")
    for field in ["text", "upos", "deprel"]:
        if not isinstance(word.get(field), str) or not word[field]:
            raise InputValidationError(f"{path}.{field} must be a non-empty string")
    if "lemma" in word and word["lemma"] is not None and not isinstance(word["lemma"], str):
        raise InputValidationError(f"{path}.lemma must be a string when present")
    if not isinstance(word.get("head"), int):
        raise InputValidationError(f"{path}.head must be an integer")
    if not isinstance(word.get("start_char"), int) or not isinstance(word.get("end_char"), int):
        raise InputValidationError(f"{path}.start_char/end_char must be integers")
    if word["start_char"] > word["end_char"]:
        raise InputValidationError(f"{path}.start_char must be <= end_char")


def validate_entity(entity: Any, index: int) -> None:
    if not isinstance(entity, dict):
        raise InputValidationError(f"entities[{index}] must be an object")
    for field in ["text", "type"]:
        if not isinstance(entity.get(field), str) or not entity[field]:
            raise InputValidationError(f"entities[{index}].{field} must be a non-empty string")
    if not isinstance(entity.get("start_char"), int) or not isinstance(entity.get("end_char"), int):
        raise InputValidationError(f"entities[{index}].start_char/end_char must be integers")
    if entity["start_char"] > entity["end_char"]:
        raise InputValidationError(f"entities[{index}].start_char must be <= end_char")


def normalize_words(sentence: Sentence) -> list[dict[str, Any]]:
    direct_words = sentence.get("words")
    if isinstance(direct_words, list) and direct_words:
        return [dict(word) for word in direct_words if isinstance(word, dict)]

    words: list[dict[str, Any]] = []
    for token in sentence.get("tokens") or []:
        if not isinstance(token, dict):
            continue
        for word in token.get("words") or []:
            if isinstance(word, dict):
                words.append(dict(word))
    return words


def filter_entities_for_sentences(
    kept_sentences: list[Sentence],
    entities: list[Entity],
    config: AnnotationQualityConfig,
) -> list[Entity]:
    if not config.entity_filtering.enabled:
        return deepcopy(entities)

    spans: list[tuple[int, int]] = []
    for sentence in kept_sentences:
        span = sentence_span(sentence)
        if span is None:
            if config.entity_filtering.on_unresolvable_sentence_span == "drop_entities":
                return []
            raise InputValidationError("cannot resolve sentence span for entity filtering")
        spans.append(span)

    return [
        deepcopy(entity)
        for entity in entities
        if any(span_start <= entity["start_char"] and entity["end_char"] <= span_end for span_start, span_end in spans)
    ]


def sentence_span(sentence: Sentence) -> tuple[int, int] | None:
    words = normalize_words(sentence)
    starts = [word.get("start_char") for word in words]
    ends = [word.get("end_char") for word in words]
    if not starts or not ends:
        return None
    if not all(isinstance(value, int) for value in [*starts, *ends]):
        return None
    return min(starts), max(ends)


def summarize_status(
    annotations: list[AnnotationQualityAnnotation], output_sentence_count: int
) -> AnnotationQualitySummary:
    accepted = sum(1 for annotation in annotations if annotation.status == "ACCEPT")
    weak_accepted = sum(1 for annotation in annotations if annotation.status == "WEAK_ACCEPT")
    rejected = sum(1 for annotation in annotations if annotation.status == "REJECT")
    mean_score = (
        round(sum(annotation.result.score for annotation in annotations) / len(annotations), 4)
        if annotations
        else 0.0
    )
    return AnnotationQualitySummary(
        total_input_sentences=len(annotations),
        total_output_sentences=output_sentence_count,
        accepted=accepted,
        weak_accepted=weak_accepted,
        rejected=rejected,
        mean_score=mean_score,
    )


def label_allowed(config: AnnotationQualityConfig, label: FilterStatus) -> bool:
    if label == "ACCEPT":
        return True
    if label == "WEAK_ACCEPT":
        return config.retention_policy == "ACCEPT_AND_WEAK_ACCEPT"
    return False


def parse_feats(feats: Any) -> dict[str, str]:
    if isinstance(feats, dict):
        return {str(key): str(value) for key, value in feats.items() if value is not None}
    if not isinstance(feats, str) or not feats or feats == "_":
        return {}

    parsed: dict[str, str] = {}
    for part in feats.split("|"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key and value:
            parsed[key] = value
    return parsed


def is_valid_head(head: Any, word_count: int) -> bool:
    return isinstance(head, int) and 0 <= head <= word_count


def is_connected_tree(words: list[dict[str, Any]]) -> bool:
    if not words:
        return False

    graph: dict[int, set[int]] = defaultdict(set)
    for index, word in enumerate(words, start=1):
        head = word.get("head")
        if not is_valid_head(head, len(words)) or head == 0:
            continue
        graph[index].add(head)
        graph[head].add(index)

    seen = set()
    stack = [1]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph[node] - seen)

    return len(seen) == len(words)


def count_orphans(words: list[dict[str, Any]]) -> int:
    return sum(
        1
        for index, word in enumerate(words, start=1)
        if word.get("head") == index or not is_valid_head(word.get("head"), len(words))
    )


def children_by_head(words: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    children: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for word in words:
        head = word.get("head")
        if isinstance(head, int):
            children[head].append(word)
    return children


def get_head_word(words: list[dict[str, Any]], word: dict[str, Any]) -> dict[str, Any] | None:
    head = word.get("head")
    if not isinstance(head, int) or head <= 0 or head > len(words):
        return None
    return words[head - 1]


def base_deprel(word: dict[str, Any]) -> str:
    return str(word.get("deprel") or "").split(":", 1)[0]


def is_finite_verb(word: dict[str, Any]) -> bool:
    if word.get("upos") not in VERB_UPOS:
        return False
    feats = parse_feats(word.get("feats"))
    return feats.get("VerbForm") == "Fin" or str(word.get("xpos") or "") in {
        "VBD",
        "VBP",
        "VBZ",
        "MD",
    }


def has_subject_child(children: Iterable[dict[str, Any]]) -> bool:
    return any(word.get("deprel") in SUBJECT_DEPRELS for word in children)


def is_suspicious_dependency_pair(words: list[dict[str, Any]], word: dict[str, Any]) -> bool:
    relation = base_deprel(word)
    head = get_head_word(words, word)
    if head is None:
        return False
    if relation == "nsubj" and head.get("upos") == "ADJ":
        return True
    if relation == "obj" and word.get("upos") == "ADV":
        return True
    return False


def count_subject_verb_agreement_mismatches(words: list[dict[str, Any]]) -> int:
    mismatches = 0
    for word in words:
        if word.get("deprel") not in SUBJECT_DEPRELS:
            continue
        head = get_head_word(words, word)
        if head is None or head.get("upos") not in VERB_UPOS:
            continue
        subject_feats = parse_feats(word.get("feats"))
        verb_feats = parse_feats(head.get("feats"))
        if (
            subject_feats.get("Number")
            and verb_feats.get("Number")
            and subject_feats["Number"] != verb_feats["Number"]
        ):
            mismatches += 1
    return mismatches


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))
