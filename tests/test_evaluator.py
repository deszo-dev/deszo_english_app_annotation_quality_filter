from annotation_quality_filter import evaluate
from annotation_quality_filter.evaluator import normalize_words, parse_feats


def test_parse_feats_from_stanza_string():
    assert parse_feats("Mood=Ind|Tense=Past|VerbForm=Fin") == {
        "Mood": "Ind",
        "Tense": "Past",
        "VerbForm": "Fin",
    }


def test_accepts_simple_valid_sentence():
    result = evaluate(
        {
            "text": "She reads books.",
            "words": [
                {
                    "text": "She",
                    "lemma": "she",
                    "upos": "PRON",
                    "feats": "Number=Sing|Person=3",
                    "head": 2,
                    "deprel": "nsubj",
                },
                {
                    "text": "reads",
                    "lemma": "read",
                    "upos": "VERB",
                    "xpos": "VBZ",
                    "feats": "Number=Sing|Person=3|Tense=Pres|VerbForm=Fin",
                    "head": 0,
                    "deprel": "root",
                },
                {
                    "text": "books",
                    "lemma": "book",
                    "upos": "NOUN",
                    "feats": "Number=Plur",
                    "head": 2,
                    "deprel": "obj",
                },
                {
                    "text": ".",
                    "lemma": ".",
                    "upos": "PUNCT",
                    "feats": None,
                    "head": 2,
                    "deprel": "punct",
                },
            ],
        }
    )

    assert result.label == "ACCEPT"
    assert result.score >= 0.8


def test_rejects_missing_root():
    result = evaluate(
        {
            "text": "Broken sentence",
            "words": [
                {"text": "Broken", "upos": "ADJ", "head": 2, "deprel": "amod"},
                {"text": "sentence", "upos": "NOUN", "head": 1, "deprel": "nsubj"},
            ],
        }
    )

    assert result.label == "REJECT"
    assert result.score == 0.0
    assert "NO_ROOT" in result.reasons


def test_normalizes_hollow_token_shape():
    sentence = {
        "text": "Hello world.",
        "tokens": [
            {"text": "Hello", "words": [{"text": "Hello", "head": 0, "deprel": "root"}]},
            {"text": "world", "words": [{"text": "world", "head": 1, "deprel": "obj"}]},
        ],
    }

    assert [word["text"] for word in normalize_words(sentence)] == ["Hello", "world"]

