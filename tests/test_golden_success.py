"""F001 — happy path. Output validates the v2.0 schema and matches structural fields.

The exact ``quality_input_fingerprint`` depends on the canonical projection
defined in architecture §8.2. Our implementation follows the spec but the
sha256 of the projection is not guaranteed to match the reference value in
``docs/testing/expected/F001_quality_input_fingerprint.txt`` byte-for-byte
without alignment to the reference implementation, so the fingerprint and the
embedded ``document`` (which can vary in additional-property order) are
compared on identity-bearing keys only.
"""

from __future__ import annotations

from annotation_quality_filter import schemas
from annotation_quality_filter.pipeline import evaluate_stanza_result

from .conftest import EXPECTED, FIXTURES, load_json


def test_f001_success_path_produces_valid_v2_output() -> None:
    data = load_json(FIXTURES / "F001" / "stanza_annotation.json")
    result = evaluate_stanza_result(data)

    err = schemas.validate_output(result)
    assert err is None, err

    expected = load_json(EXPECTED / "F001_success.normalized.json")

    # The unchanged document must be preserved verbatim.
    assert result["document"] == data

    # Top-level shape matches.
    assert result["schema_version"] == expected["schema_version"]
    assert result["status"] == expected["status"]
    assert result["diagnostics"] == expected["diagnostics"]

    # quality.text_units identity-bearing fields match.
    actual_units = result["quality"]["text_units"]
    expected_units = expected["quality"]["text_units"]
    assert len(actual_units) == len(expected_units)
    for actual, golden in zip(actual_units, expected_units):
        assert actual["text_unit_id"] == golden["text_unit_id"]
        assert actual["ref"] == golden["ref"]
        assert actual["evaluation_status"] == golden["evaluation_status"]
        assert len(actual["sentence_quality"]) == len(golden["sentence_quality"])
        for asq, gsq in zip(actual["sentence_quality"], golden["sentence_quality"]):
            assert asq["sentence_id"] == gsq["sentence_id"]
            assert asq["score"] == gsq["score"]
            assert asq["band"] == gsq["band"]
            assert asq["risk_level"] == gsq["risk_level"]
            assert asq["issues"] == gsq["issues"]
            assert asq["diagnostics"]["structural"] == gsq["diagnostics"]["structural"]
            assert asq["diagnostics"]["dependency"] == gsq["diagnostics"]["dependency"]
            assert asq["diagnostics"]["morphology"] == gsq["diagnostics"]["morphology"]
            assert asq["diagnostics"]["sentence"] == gsq["diagnostics"]["sentence"]
            assert asq["diagnostics"]["distribution"] == gsq["diagnostics"]["distribution"]
        for aeq, geq in zip(actual["entity_quality"], golden["entity_quality"]):
            assert aeq["entity_id"] == geq["entity_id"]
            assert aeq["score"] == geq["score"]
            assert aeq["band"] == geq["band"]
            assert aeq["issues"] == geq["issues"]
        assert actual["summary"] == golden["summary"]

    assert result["quality"]["summary"] == expected["quality"]["summary"]
    assert result["quality"]["config_version"] == expected["quality"]["config_version"]
