"""Quality checkers for sentences/tokens/words/entities (issue registry v2.0).

Each helper yields ``QualityIssue`` dicts via :func:`annotation_quality_filter.issues.make_issue`.
The collected issues are then converted into family penalties by ``scoring.py``.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..issues import IssueSpec, make_issue, specs as issue_specs

_FINITE_VERB_UPOS = {"VERB", "AUX"}
_SUBJECT_DEPRELS = {"nsubj", "nsubj:pass", "csubj", "csubj:pass", "expl"}
_AUX_DEPRELS = {"aux", "aux:pass", "cop"}
_AUX_HEAD_UPOS = {"VERB", "AUX", "ADJ", "NOUN", "PROPN", "PRON"}
_RELCL_HEAD_UPOS = {"NOUN", "PROPN", "PRON"}
_NOUNISH_UPOS = {"NOUN", "PROPN", "PRON"}
_SUSPICIOUS_PAIRS = {
    ("nsubj", "PUNCT", None),
    ("obj", "PUNCT", None),
    ("det", None, "VERB"),
}


def _feats_contains(feats: str, key: str) -> bool:
    if not feats or feats == "_":
        return False
    for part in feats.split("|"):
        if part.startswith(key):
            return True
    return False


def _feats_get(feats: str, key: str) -> str | None:
    if not feats or feats == "_":
        return None
    for part in feats.split("|"):
        if part.startswith(key + "="):
            return part.split("=", 1)[1]
    return None


def _non_punct_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [w for w in words if w.get("upos") != "PUNCT"]


def check_sentence(
    sentence: dict[str, Any],
    *,
    text_unit_text: str,
    text_unit_offset: int,
    cfg: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return ``(issues, diagnostics_by_family)`` for a sentence."""

    words: list[dict[str, Any]] = sentence.get("words", [])
    tokens: list[dict[str, Any]] = sentence.get("tokens", [])
    issues: list[dict[str, Any]] = []
    structural: dict[str, Any] = {}
    dependency: dict[str, Any] = {}
    morphology: dict[str, Any] = {}
    sentence_metrics: dict[str, Any] = {}
    distribution: dict[str, Any] = {}

    sent_id = sentence.get("id") or ""
    text = sentence.get("text") or ""
    start_char = int(sentence.get("start_char", 0))
    end_char = int(sentence.get("end_char", 0))
    span_valid = (
        start_char >= 0
        and end_char >= start_char
        and end_char - start_char == len(text)
    )

    contains_newline = "\n" in text

    if not span_valid:
        issues.append(make_issue("SENTENCE_SPAN_INVALID", entity_type="sentence", entity_id=sent_id))

    # Build word-id -> word index, and word_id set
    word_ids = [w.get("id") for w in words]
    word_id_to_index = {wid: i for i, wid in enumerate(word_ids)}
    word_id_set = set(word_ids)

    # ---- structural: token_word_references ---------------------------------
    unresolved = 0
    for token in tokens:
        for wid in token.get("word_ids") or []:
            if wid not in word_id_set:
                unresolved += 1
                issues.append(
                    make_issue(
                        "TOKEN_WORD_REFERENCE_INVALID",
                        entity_type="token",
                        entity_id=token.get("id") or "",
                    )
                )

    # token spans
    for token in tokens:
        s, e = token.get("start_char"), token.get("end_char")
        if not isinstance(s, int) or not isinstance(e, int) or s < 0 or e < s:
            issues.append(
                make_issue("TOKEN_SPAN_INVALID", entity_type="token", entity_id=token.get("id") or "")
            )
    # word spans
    for word in words:
        s, e = word.get("start_char"), word.get("end_char")
        if not isinstance(s, int) or not isinstance(e, int) or s < 0 or e < s:
            issues.append(
                make_issue("WORD_SPAN_INVALID", entity_type="word", entity_id=word.get("id") or "")
            )

    # empty sentence
    if not words:
        issues.append(make_issue("EMPTY_SENTENCE_WORDS", entity_type="sentence", entity_id=sent_id))

    # text-slice check
    if cfg["checks"]["validate_text_slices"] and span_valid and text_unit_text:
        rel_start = start_char - text_unit_offset
        rel_end = end_char - text_unit_offset
        if 0 <= rel_start <= rel_end <= len(text_unit_text):
            slice_ = text_unit_text[rel_start:rel_end]
            if slice_ != text:
                issues.append(
                    make_issue("SENTENCE_TEXT_MISMATCH", entity_type="sentence", entity_id=sent_id)
                )

    structural.update(
        {
            "sentence_text_length_chars": len(text),
            "token_count": len(tokens),
            "word_count": len(words),
            "span_start_char": start_char,
            "span_end_char": end_char,
            "span_valid": span_valid,
            "text_matches_source_slice": span_valid,
            "contains_newline": contains_newline,
            "unresolved_token_word_reference_count": unresolved,
        }
    )

    # ---- dependency family --------------------------------------------------
    root_indices = [i for i, w in enumerate(words) if w.get("head") == 0]
    root_count = len(root_indices)
    invalid_head_count = 0
    head_id_mismatch_count = 0
    orphan_count = 0
    for i, w in enumerate(words):
        head = w.get("head")
        if not isinstance(head, int) or head < 0 or head > len(words):
            invalid_head_count += 1
            issues.append(make_issue("INVALID_HEAD_INDEX", entity_type="word", entity_id=w.get("id") or ""))
            continue
        if head != 0:
            expected_id = words[head - 1].get("id")
            if w.get("head_word_id") and w.get("head_word_id") != expected_id:
                head_id_mismatch_count += 1
                issues.append(
                    make_issue("HEAD_WORD_ID_MISMATCH", entity_type="word", entity_id=w.get("id") or "")
                )

    if root_count == 0 and words:
        issues.append(make_issue("NO_ROOT", entity_type="sentence", entity_id=sent_id))
    if root_count > 1:
        issues.append(make_issue("MULTIPLE_ROOTS", entity_type="sentence", entity_id=sent_id))

    # connectivity (only when heads are otherwise valid)
    disconnected = False
    max_depth: int | None = None
    if words and invalid_head_count == 0 and root_count >= 1:
        # depth-from-root via head pointers
        depths: list[int | None] = [None] * len(words)

        def depth_of(idx: int, stack: tuple[int, ...] = ()) -> int | None:
            if idx in stack:
                return None  # cycle
            cached = depths[idx]
            if cached is not None:
                return cached
            head = words[idx].get("head")
            if head == 0:
                depths[idx] = 1
                return 1
            parent = head - 1  # type: ignore[operator]
            d = depth_of(parent, stack + (idx,))
            if d is None:
                return None
            depths[idx] = d + 1
            return d + 1

        for i in range(len(words)):
            d = depth_of(i)
            if d is None:
                orphan_count += 1
                issues.append(
                    make_issue("ORPHAN_DEPENDENCY_NODE", entity_type="word", entity_id=words[i].get("id") or "")
                )
        connected_depths = [d for d in depths if d is not None]
        if connected_depths:
            max_depth = max(connected_depths)
        if orphan_count > 0:
            disconnected = True
            issues.append(
                make_issue("DISCONNECTED_DEPENDENCY_TREE", entity_type="sentence", entity_id=sent_id)
            )

    # dominant deprel — counts over all words; tie-break: prefer "root", then lexicographic
    deprels = [w.get("deprel") or "" for w in words if w.get("deprel")]
    dominant_deprel = None
    if deprels:
        cnt = Counter(deprels)
        dominant_deprel = sorted(
            cnt.items(), key=lambda kv: (-kv[1], 0 if kv[0] == "root" else 1, kv[0])
        )[0][0]

    dependency.update(
        {
            "root_count": root_count,
            "invalid_head_count": invalid_head_count,
            "head_word_id_mismatch_count": head_id_mismatch_count,
            "disconnected_tree": disconnected,
            "orphan_node_count": orphan_count,
            "max_tree_depth": max_depth,
            "dominant_deprel": dominant_deprel,
        }
    )

    # ---- sentence family ----------------------------------------------------
    non_punct = _non_punct_words(words)
    has_main_verb = any(w.get("upos") in _FINITE_VERB_UPOS for w in non_punct)
    has_subject = any((w.get("deprel") or "").split(":", 1)[0] in {"nsubj", "csubj", "expl"} or (w.get("deprel") or "") in _SUBJECT_DEPRELS for w in non_punct)
    total_word_count = len(words)
    soft = int(cfg["limits"]["long_sentence_soft"])
    hard = int(cfg["limits"]["long_sentence_hard"])
    if total_word_count > hard:
        length_band = "hard_long"
    elif total_word_count > soft:
        length_band = "soft_long"
    else:
        length_band = "normal"
    # TOO_LONG_SENTENCE: any soft/max/hard exceeded (total word count)
    if total_word_count > soft or total_word_count > int(cfg["limits"]["max_sentence_length"]) or total_word_count > hard:
        issues.append(make_issue("TOO_LONG_SENTENCE", entity_type="sentence", entity_id=sent_id))
    if contains_newline:
        issues.append(make_issue("CONTAINS_NEWLINE", entity_type="sentence", entity_id=sent_id))
    if cfg["checks"]["enable_sentence"] and not has_main_verb and words:
        issues.append(make_issue("NO_MAIN_VERB", entity_type="sentence", entity_id=sent_id))

    conjunction_count = sum(1 for w in words if (w.get("deprel") or "") == "conj")
    sentence_metrics.update(
        {
            "word_count": total_word_count,
            "has_main_verb": has_main_verb,
            "has_subject": has_subject,
            "length_band": length_band,
            "conjunction_count": conjunction_count,
        }
    )

    # MISSING_SUBJECT
    has_finite_verb = any(
        w.get("upos") in _FINITE_VERB_UPOS and _feats_contains(w.get("feats") or "", "VerbForm=Fin")
        for w in non_punct
    )
    has_any_subject = any((w.get("deprel") or "") in _SUBJECT_DEPRELS for w in non_punct)
    if has_finite_verb and not has_any_subject:
        issues.append(make_issue("MISSING_SUBJECT", entity_type="sentence", entity_id=sent_id))

    # BROKEN_AUX_CHAIN, INVALID_RELCL_ATTACHMENT
    for w in non_punct:
        deprel = (w.get("deprel") or "")
        head = w.get("head")
        if isinstance(head, int) and head > 0 and head <= len(words):
            head_word = words[head - 1]
            if deprel in _AUX_DEPRELS and head_word.get("upos") not in _AUX_HEAD_UPOS:
                issues.append(
                    make_issue("BROKEN_AUX_CHAIN", entity_type="word", entity_id=w.get("id") or "")
                )
            if deprel == "acl:relcl" and head_word.get("upos") not in _RELCL_HEAD_UPOS:
                issues.append(
                    make_issue("INVALID_RELCL_ATTACHMENT", entity_type="word", entity_id=w.get("id") or "")
                )

    # SUSPICIOUS_DEPREL_PAIR
    for w in non_punct:
        deprel = w.get("deprel") or ""
        head = w.get("head")
        head_upos = None
        if isinstance(head, int) and 0 < head <= len(words):
            head_upos = words[head - 1].get("upos")
        if deprel == "nsubj" and w.get("upos") == "PUNCT":
            issues.append(make_issue("SUSPICIOUS_DEPREL_PAIR", entity_type="word", entity_id=w.get("id") or ""))
        elif deprel == "obj" and w.get("upos") == "PUNCT":
            issues.append(make_issue("SUSPICIOUS_DEPREL_PAIR", entity_type="word", entity_id=w.get("id") or ""))
        elif deprel == "det" and head_upos == "VERB":
            issues.append(make_issue("SUSPICIOUS_DEPREL_PAIR", entity_type="word", entity_id=w.get("id") or ""))

    # EXCESSIVE_CONJ — ratio over total words (matches golden fixtures)
    conj_ratio = conjunction_count / len(words) if words else 0.0
    if conj_ratio > float(cfg["limits"]["max_conj_ratio"]):
        issues.append(make_issue("EXCESSIVE_CONJ", entity_type="sentence", entity_id=sent_id))

    # ---- morphology family --------------------------------------------------
    empty_morphology_count = sum(
        1 for w in words if not w.get("feats") or w.get("feats") == "_"
    )
    missing_tense_count = 0
    agreement_mismatch_count = 0

    for w in non_punct:
        if (
            w.get("upos") in _FINITE_VERB_UPOS
            and _feats_contains(w.get("feats") or "", "VerbForm=Fin")
            and not _feats_contains(w.get("feats") or "", "Tense=")
        ):
            missing_tense_count += 1
            issues.append(
                make_issue("MISSING_TENSE", entity_type="word", entity_id=w.get("id") or "")
            )

    if non_punct and empty_morphology_count / len(non_punct) > 0.5:
        issues.append(make_issue("EMPTY_MORPHOLOGY", entity_type="sentence", entity_id=sent_id))

    # AGREEMENT_MISMATCH minimal explicit-number case
    for w in non_punct:
        if w.get("upos") not in _FINITE_VERB_UPOS:
            continue
        feats = w.get("feats") or ""
        if not _feats_contains(feats, "VerbForm=Fin"):
            continue
        if _feats_get(feats, "Tense") != "Pres":
            continue
        # Find nsubj dependent
        verb_idx = words.index(w) + 1
        for dep in non_punct:
            if dep.get("head") == verb_idx and (dep.get("deprel") or "").startswith("nsubj"):
                v_num = _feats_get(feats, "Number")
                v_per = _feats_get(feats, "Person")
                d_num = _feats_get(dep.get("feats") or "", "Number")
                if (
                    v_per == "3"
                    and v_num == "Sing"
                    and d_num == "Plur"
                ) or (v_num == "Plur" and d_num == "Sing"):
                    agreement_mismatch_count += 1
                    issues.append(
                        make_issue("AGREEMENT_MISMATCH", entity_type="sentence", entity_id=sent_id)
                    )
                    break

    morphology.update(
        {
            "empty_morphology_count": empty_morphology_count,
            "missing_tense_count": missing_tense_count,
            "agreement_mismatch_count": agreement_mismatch_count,
        }
    )

    # ---- distribution family (denominator = total words, matches golden fixtures) ----
    if words:
        noun_ratio = sum(1 for w in words if w.get("upos") in _NOUNISH_UPOS) / len(words)
        deprel_counts = Counter(
            (w.get("deprel") or "") for w in words if w.get("deprel")
        )
        max_deprel_ratio = (
            max(deprel_counts.values()) / len(words) if deprel_counts else 0.0
        )
        pos_counts = Counter(w.get("upos") for w in non_punct if w.get("upos"))
        dominant_pos = (
            sorted(pos_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            if pos_counts
            else None
        )
    else:
        noun_ratio = 0.0
        max_deprel_ratio = 0.0
        dominant_pos = None

    if noun_ratio > float(cfg["limits"]["max_noun_ratio"]):
        issues.append(make_issue("POS_DISTRIBUTION_ANOMALY", entity_type="sentence", entity_id=sent_id))
    if max_deprel_ratio > float(cfg["limits"]["max_deprel_ratio"]):
        issues.append(
            make_issue("DEPREL_DISTRIBUTION_ANOMALY", entity_type="sentence", entity_id=sent_id)
        )

    distribution.update(
        {
            "noun_ratio": _round6(noun_ratio),
            "conj_ratio": _round6(conj_ratio),
            "max_deprel_ratio": _round6(max_deprel_ratio),
            "dominant_pos": dominant_pos,
            "dominant_deprel": dominant_deprel,
        }
    )

    return issues, {
        "structural": structural,
        "dependency": dependency,
        "morphology": morphology,
        "sentence": sentence_metrics,
        "distribution": distribution,
    }


def check_entity(entity: dict[str, Any], *, text_unit_text: str, text_unit_offset: int, validate_slices: bool) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    s = entity.get("start_char")
    e = entity.get("end_char")
    span_valid = isinstance(s, int) and isinstance(e, int) and s >= 0 and e >= s
    if not span_valid:
        issues.append(make_issue("ENTITY_SPAN_INVALID", entity_type="entity", entity_id=entity.get("id") or ""))
        return issues
    if validate_slices and text_unit_text:
        rel_s = s - text_unit_offset  # type: ignore[operator]
        rel_e = e - text_unit_offset  # type: ignore[operator]
        if 0 <= rel_s <= rel_e <= len(text_unit_text):
            slice_ = text_unit_text[rel_s:rel_e]
            if slice_ != (entity.get("text") or ""):
                issues.append(
                    make_issue("ENTITY_TEXT_MISMATCH", entity_type="entity", entity_id=entity.get("id") or "")
                )
    return issues


def _round6(value: float) -> float:
    """6-decimal round-half-even (architecture §8.1)."""

    import decimal

    q = decimal.Decimal("0.000001")
    return float(decimal.Decimal(value).quantize(q, rounding=decimal.ROUND_HALF_EVEN))
