"""Contract tests: every checked-in golden output validates against v2.0 schemas."""

from __future__ import annotations

from pathlib import Path

import pytest

from annotation_quality_filter import schemas

from .conftest import EXPECTED, FIXTURES, load_json


_OUTPUT_GOLDENS = [
    "B001_invalid_json_parse.normalized.json",
    "C001_invalid_config.normalized.json",
    "C002_invalid_config_schema.normalized.json",
    "F001_success.normalized.json",
    "F003_upstream_failed.normalized.json",
    "F004_unsupported_schema.normalized.json",
    "F006_unsupported_schema_precedence.normalized.json",
    "F007_invalid_input_schema.normalized.json",
    "O001_output_too_large.normalized.json",
]


@pytest.mark.parametrize("name", _OUTPUT_GOLDENS)
def test_expected_output_validates_against_v2_schema(name: str) -> None:
    payload = load_json(EXPECTED / name)
    err = schemas.validate_output(payload)
    assert err is None, err


def test_f001_stanza_fixture_validates_against_input_schema() -> None:
    payload = load_json(FIXTURES / "F001" / "stanza_annotation.json")
    err = schemas.validate_input(payload)
    assert err is None, err


def test_f002_stanza_fixture_validates_against_input_schema() -> None:
    payload = load_json(FIXTURES / "F002" / "stanza_annotation.json")
    err = schemas.validate_input(payload)
    assert err is None, err
