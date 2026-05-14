"""Foundation tests: schemas and registries load and resolve offline."""

from __future__ import annotations

from annotation_quality_filter import schemas
from annotation_quality_filter.errors import diagnostic_helpers, errors
from annotation_quality_filter.issues import specs as issue_specs


def test_catalog_lists_expected_schemas() -> None:
    catalog = schemas._load_catalog()
    for schema_id in (
        schemas.OUTPUT_SCHEMA_ID,
        schemas.USER_CONFIG_SCHEMA_ID,
        schemas.EFFECTIVE_CONFIG_SCHEMA_ID,
        schemas.INPUT_SCHEMA_ID,
        schemas.DIAGNOSTICS_SCHEMA_ID,
    ):
        assert schema_id in catalog


def test_all_schemas_parse() -> None:
    for schema_id in schemas._load_catalog():
        body = schemas.load_schema(schema_id)
        assert body["$id"] == schema_id or schema_id.endswith(body.get("$id", ""))


def test_error_registry_codes() -> None:
    codes = set(errors())
    assert codes == {
        "invalid_config",
        "invalid_input",
        "unsupported_stanza_schema",
        "upstream_stanza_annotation_failed",
        "output_too_large",
        "output_write_failed",
        "internal_error",
    }
    helpers = set(diagnostic_helpers())
    assert helpers == {
        "config_schema_validation_failed",
        "config_invariant_failed",
        "input_json_parse_failed",
        "input_schema_validation_failed",
        "unsupported_input_schema_version",
        "upstream_failure_status_seen",
        "output_serialization_too_large",
        "output_channel_write_failed",
        "unexpected_internal_error",
    }


def test_issue_registry_has_27_codes() -> None:
    assert len(issue_specs()) == 27
