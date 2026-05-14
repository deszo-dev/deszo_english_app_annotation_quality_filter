"""Golden failure-path tests.

For each fixture, ``evaluate_stanza_result`` must produce a failed result whose
top-level ``error.code`` and helper-diagnostic ``code`` match the checked-in
``docs/testing/expected/*.normalized.json`` golden file.
"""

from __future__ import annotations

import json

import pytest

from annotation_quality_filter import schemas
from annotation_quality_filter.pipeline import _failed_result, evaluate_stanza_result

from .conftest import EXPECTED, FIXTURES, load_json


def _expected(name: str) -> dict[str, object]:
    return load_json(EXPECTED / name)  # type: ignore[return-value]


def _normalize(result: dict[str, object]) -> dict[str, object]:
    aq = dict(result.get("annotation_quality") or {})
    for key in ("started_at", "finished_at"):
        aq.pop(key, None)
    aq["duration_ms"] = 0.0
    new = dict(result)
    new["annotation_quality"] = aq
    return new


def test_F003_upstream_failed() -> None:
    payload = load_json(FIXTURES / "F003" / "stanza_annotation.json")
    actual = _normalize(evaluate_stanza_result(payload))
    expected = _expected("F003_upstream_failed.normalized.json")
    assert actual == expected


def test_F004_unsupported_schema() -> None:
    payload = load_json(FIXTURES / "F004" / "stanza_annotation.json")
    actual = _normalize(evaluate_stanza_result(payload))
    expected = _expected("F004_unsupported_schema.normalized.json")
    assert actual == expected


def test_F006_unsupported_schema_precedence() -> None:
    payload = load_json(FIXTURES / "F006" / "stanza_failed_unsupported_schema.json")
    actual = _normalize(evaluate_stanza_result(payload))
    expected = _expected("F006_unsupported_schema_precedence.normalized.json")
    assert actual == expected


def test_F007_invalid_input_schema() -> None:
    payload = load_json(FIXTURES / "F007" / "schema_invalid_missing_document.json")
    result = _normalize(evaluate_stanza_result(payload))
    expected = _expected("F007_invalid_input_schema.normalized.json")
    assert result["status"] == "failed"
    assert result["error"] == expected["error"]
    assert result["diagnostics"][0]["code"] == expected["diagnostics"][0]["code"]


def test_C001_invalid_config_invariant() -> None:
    cfg = load_json(FIXTURES / "C001" / "quality_config.json")
    # The C001 invariant failure path is reached purely from config invariants —
    # input is irrelevant when config validation fails first. We give any small
    # valid Stanza payload.
    actual = _normalize(evaluate_stanza_result({}, user_config=cfg))
    expected = _expected("C001_invalid_config.normalized.json")
    assert actual["status"] == "failed"
    assert actual["error"] == expected["error"]
    assert actual["diagnostics"][0]["code"] == expected["diagnostics"][0]["code"]


def test_C002_invalid_config_schema() -> None:
    cfg = load_json(FIXTURES / "C002" / "quality_config.json")
    actual = _normalize(evaluate_stanza_result({}, user_config=cfg))
    expected = _expected("C002_invalid_config_schema.normalized.json")
    assert actual["status"] == "failed"
    assert actual["error"] == expected["error"]
    assert actual["diagnostics"][0]["code"] == expected["diagnostics"][0]["code"]


def test_all_failed_results_validate_against_output_schema() -> None:
    samples = [
        _failed_result(error_code="invalid_config", message="x", helper_code="config_invariant_failed", helper_path="/thresholds"),
        _failed_result(error_code="invalid_input", message="x", helper_code="input_schema_validation_failed", helper_path="/document"),
        _failed_result(error_code="upstream_stanza_annotation_failed", message="x", helper_code="upstream_failure_status_seen", helper_path="/status"),
        _failed_result(error_code="unsupported_stanza_schema", message="x", helper_code="unsupported_input_schema_version", helper_path="/schema_version"),
        _failed_result(error_code="output_too_large", message="x", helper_code="output_serialization_too_large", helper_path="/limits/max_output_json_bytes"),
        _failed_result(error_code="output_write_failed", message="x", helper_code="output_channel_write_failed", helper_path=""),
        _failed_result(error_code="internal_error", message="x", helper_code="unexpected_internal_error", helper_path=""),
    ]
    for result in samples:
        err = schemas.validate_output(result)
        assert err is None, err
