import json
import subprocess
import sys

import pytest

from annotation_quality_filter import (
    AnnotationQualityConfig,
    AnnotationQualityFilter,
    EntityFilteringConfig,
    InputValidationError,
    Thresholds,
    filter_document,
    filter_with_status,
)
from annotation_quality_filter.evaluator import (
    filter_entities_for_sentences,
    normalize_words,
    parse_feats,
)


def valid_sentence(text="She reads books.", start=0):
    words = [
        {
            "text": "She",
            "lemma": "she",
            "upos": "PRON",
            "feats": "Number=Sing|Person=3",
            "head": 2,
            "deprel": "nsubj",
            "start_char": start,
            "end_char": start + 3,
        },
        {
            "text": "reads",
            "lemma": "read",
            "upos": "VERB",
            "xpos": "VBZ",
            "feats": "Number=Sing|Person=3|Tense=Pres|VerbForm=Fin",
            "head": 0,
            "deprel": "root",
            "start_char": start + 4,
            "end_char": start + 9,
        },
        {
            "text": "books",
            "lemma": "book",
            "upos": "NOUN",
            "feats": "Number=Plur",
            "head": 2,
            "deprel": "obj",
            "start_char": start + 10,
            "end_char": start + 15,
        },
    ]
    return {
        "text": text,
        "tokens": [{"text": word["text"], "words": [word]} for word in words],
        "words": words,
    }


def broken_sentence():
    words = [
        {
            "text": "Broken",
            "lemma": "broken",
            "upos": "ADJ",
            "head": 2,
            "deprel": "amod",
            "start_char": 20,
            "end_char": 26,
        },
        {
            "text": "sentence",
            "lemma": "sentence",
            "upos": "NOUN",
            "head": 1,
            "deprel": "nsubj",
            "start_char": 27,
            "end_char": 35,
        },
    ]
    return {
        "text": "Broken sentence",
        "tokens": [{"text": word["text"], "words": [word]} for word in words],
        "words": words,
    }


def document():
    return {
        "sentences": [valid_sentence(), broken_sentence()],
        "entities": [
            {"text": "She", "type": "PERSON", "start_char": 0, "end_char": 3},
            {"text": "Broken", "type": "MISC", "start_char": 20, "end_char": 26},
        ],
    }


def test_parse_feats_from_stanza_string():
    assert parse_feats("Mood=Ind|Tense=Past|VerbForm=Fin") == {
        "Mood": "Ind",
        "Tense": "Past",
        "VerbForm": "Fin",
    }


def test_evaluate_sentence_accepts_simple_valid_sentence():
    annotation = AnnotationQualityFilter().evaluate_sentence(valid_sentence(), 0)

    assert annotation.status == "ACCEPT"
    assert annotation.result.score >= 0.8
    assert annotation.included_in_output is True
    assert annotation.input_sentence_index == 0


def test_evaluate_sentence_rejects_missing_root():
    annotation = AnnotationQualityFilter().evaluate_sentence(broken_sentence(), 0)

    assert annotation.status == "REJECT"
    assert annotation.result.score == 0.0
    assert "NO_ROOT" in annotation.result.reasons
    assert annotation.included_in_output is False


def test_normalizes_hollow_token_shape():
    sentence = {
        "text": "Hello world.",
        "tokens": [
            {"text": "Hello", "words": [{"text": "Hello", "head": 0, "deprel": "root"}]},
            {"text": "world", "words": [{"text": "world", "head": 1, "deprel": "obj"}]},
        ],
    }

    assert [word["text"] for word in normalize_words(sentence)] == ["Hello", "world"]


def test_filter_with_status_returns_primary_document_and_status():
    output = filter_with_status(document())

    assert [sentence["text"] for sentence in output.document["sentences"]] == [
        "She reads books."
    ]
    assert output.document["entities"] == [
        {"text": "She", "type": "PERSON", "start_char": 0, "end_char": 3}
    ]
    assert len(output.status.annotations) == 2
    assert output.status.annotations[0].output_sentence_index == 0
    assert output.status.annotations[1].output_sentence_index is None
    assert output.status.summary.total_input_sentences == 2
    assert output.status.summary.total_output_sentences == 1
    assert output.status.summary.rejected == 1


def test_filter_document_returns_only_primary_document():
    filtered = filter_document(document())

    assert set(filtered) == {"sentences", "entities"}
    assert "status" not in filtered


def test_accept_only_excludes_weak_accept_from_primary_output():
    weak = valid_sentence("She reads.", 0)
    weak["words"][1]["feats"] = "Number=Sing|Person=3|VerbForm=Fin"
    weak["tokens"][1]["words"][0]["feats"] = "Number=Sing|Person=3|VerbForm=Fin"
    payload = {"sentences": [weak], "entities": []}

    output = filter_with_status(
        payload,
        AnnotationQualityConfig(
            thresholds=Thresholds(accept=0.99, weak_accept=0.60),
            retention_policy="ACCEPT_ONLY",
        ),
    )

    assert output.status.annotations[0].status == "WEAK_ACCEPT"
    assert output.document["sentences"] == []


def test_entity_filtering_requires_resolvable_sentence_spans_by_default():
    sentence = valid_sentence()
    del sentence["words"][0]["start_char"]

    with pytest.raises(InputValidationError):
        filter_entities_for_sentences(
            [sentence],
            [{"text": "She", "type": "PERSON", "start_char": 0, "end_char": 3}],
            AnnotationQualityConfig(),
        )


def test_drop_entities_is_explicit_opt_in_policy_for_unresolvable_spans():
    sentence = valid_sentence()
    del sentence["words"][0]["start_char"]
    config = AnnotationQualityConfig(
        entity_filtering=EntityFilteringConfig(on_unresolvable_sentence_span="drop_entities")
    )

    entities = filter_entities_for_sentences(
        [sentence],
        [{"text": "She", "type": "PERSON", "start_char": 0, "end_char": 3}],
        config,
    )

    assert entities == []


def test_cli_writes_primary_output_and_status_separately(tmp_path):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    status_path = tmp_path / "status.json"
    input_path.write_text(json.dumps(document()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "annotation_quality_filter",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--status-output",
            str(status_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert set(json.loads(output_path.read_text(encoding="utf-8"))) == {
        "sentences",
        "entities",
    }
    assert "annotations" in json.loads(status_path.read_text(encoding="utf-8"))


def test_cli_expected_data_error_returns_1_without_partial_output(tmp_path):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps({"sentences": []}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "annotation_quality_filter",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert not output_path.exists()
