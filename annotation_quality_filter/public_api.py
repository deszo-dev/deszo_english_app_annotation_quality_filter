from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping

from .runtime_metadata import get_module_version

AQF_SCHEMA_VERSION = "annotation_quality_filter.v2.0"
AQF_CONFIG_VERSION = "annotation_quality_filter_config.v2.0"
SUPPORTED_INPUT_SCHEMA_VERSION = "stanza_annotator.v2.0"


class AnnotationQualityProgrammerError(TypeError):
    """Raised for unsafe non-JSON-compatible library-mode inputs."""


def evaluate_stanza_result(
    input_data: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
    *,
    user_config: Mapping[str, Any] | None = None,
    include_debug: bool = False,
) -> dict[str, Any]:
    normalized_input = _require_json_mapping(input_data, name="input_data")
    normalized_config = _coalesce_config(config=config, user_config=user_config)

    schema_version = normalized_input.get("schema_version")
    if schema_version != SUPPORTED_INPUT_SCHEMA_VERSION:
        return _failed_result(
            code="unsupported_stanza_schema",
            message=(
                "Unsupported stanza schema_version. "
                f"Expected {SUPPORTED_INPUT_SCHEMA_VERSION!r}, got {schema_version!r}."
            ),
            diagnostic_code="unsupported_input_schema_version",
            normalized_config=normalized_config,
        )

    status = normalized_input.get("status")
    if status != "succeeded":
        code = (
            "upstream_stanza_annotation_failed"
            if status == "failed"
            else "invalid_input"
        )
        diagnostic_code = (
            "upstream_failure_status_seen"
            if status == "failed"
            else "input_schema_validation_failed"
        )
        return _failed_result(
            code=code,
            message=f"Input stanza result must have status='succeeded', got {status!r}.",
            diagnostic_code=diagnostic_code,
            normalized_config=normalized_config,
        )

    document = normalized_input.get("document")
    if not isinstance(document, dict):
        return _failed_result(
            code="invalid_input",
            message="Input stanza result must contain a document object.",
            diagnostic_code="input_schema_validation_failed",
            normalized_config=normalized_config,
        )

    result: dict[str, Any] = {
        "schema_version": AQF_SCHEMA_VERSION,
        "status": "succeeded",
        "document": deepcopy(normalized_input),
        "quality": {
            "source": {
                "stanza_schema_version": SUPPORTED_INPUT_SCHEMA_VERSION,
                "source_book_fingerprint": _source_book_fingerprint(normalized_input),
                "annotation_input_fingerprint": _annotation_input_fingerprint(
                    normalized_input
                ),
                "quality_input_fingerprint": _quality_input_fingerprint(
                    normalized_input,
                    normalized_config,
                ),
            },
            "text_units": [],
            "summary": {},
            "config_version": AQF_CONFIG_VERSION,
        },
        "diagnostics": [],
        "annotation_quality": {
            "module_name": "annotation_quality_filter",
            "module_version": get_module_version(),
            "config_version": AQF_CONFIG_VERSION,
            "status": "succeeded",
            "duration_ms": 0,
        },
    }
    if include_debug:
        result["debug"] = {
            "input_schema_version": SUPPORTED_INPUT_SCHEMA_VERSION,
            "quality_text_unit_count": 0,
        }
    return result


def get_runtime_metadata() -> dict[str, Any]:
    version = get_module_version()
    return {
        "module_name": "annotation_quality_filter",
        "module_version": version,
        "supported_input_schema_versions": [SUPPORTED_INPUT_SCHEMA_VERSION],
        "output_schema_version": AQF_SCHEMA_VERSION,
        "config_schema_version": AQF_CONFIG_VERSION,
        "effective_config_schema_version": "annotation_quality_filter_effective_config.v2.0",
        "issue_registry_version": "annotation_quality_filter_issue_registry.v2.0",
        "error_registry_version": "annotation_quality_filter_error_registry.v2.0",
        "checker_versions": {"core": version},
    }


def _coalesce_config(
    *,
    config: Mapping[str, Any] | None,
    user_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if config is not None and user_config is not None:
        raise AnnotationQualityProgrammerError(
            "Pass either 'config' or 'user_config', not both."
        )
    selected = user_config if user_config is not None else config
    if selected is None:
        return {}
    return _require_json_mapping(selected, name="config")


def _require_json_mapping(value: Mapping[str, Any], *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AnnotationQualityProgrammerError(f"{name} must be a JSON-compatible mapping.")
    normalized = _normalize_json_value(value, name=name)
    assert isinstance(normalized, dict)
    return normalized


def _normalize_json_value(value: Any, *, name: str) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_json_value(item, name=f"{name}.{key}")
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_normalize_json_value(item, name=f"{name}[]") for item in value]
    raise AnnotationQualityProgrammerError(
        f"{name} contains non-JSON-compatible value of type {type(value).__name__}."
    )


def _failed_result(
    *,
    code: str,
    message: str,
    diagnostic_code: str,
    normalized_config: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": AQF_SCHEMA_VERSION,
        "status": "failed",
        "diagnostics": [
            {
                "severity": "error",
                "code": diagnostic_code,
                "message": message,
            }
        ],
        "error": {
            "code": code,
            "message": message,
        },
        "annotation_quality": {
            "module_name": "annotation_quality_filter",
            "module_version": get_module_version(),
            "config_version": AQF_CONFIG_VERSION,
            "status": "failed",
            "duration_ms": 0,
            "config_hash": _config_hash(normalized_config),
        },
    }


def _quality_input_fingerprint(
    input_data: Mapping[str, Any],
    config: Mapping[str, Any],
) -> str:
    payload = {
        "document": input_data.get("document"),
        "annotation": input_data.get("annotation"),
        "config": config,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _config_hash(config: Mapping[str, Any]) -> str:
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _source_book_fingerprint(input_data: Mapping[str, Any]) -> str | None:
    document = input_data.get("document")
    if not isinstance(document, Mapping):
        return None
    source = document.get("source")
    if isinstance(source, Mapping):
        fingerprint = source.get("fingerprint")
        if isinstance(fingerprint, str):
            return fingerprint
    return None


def _annotation_input_fingerprint(input_data: Mapping[str, Any]) -> str | None:
    annotation = input_data.get("annotation")
    if not isinstance(annotation, Mapping):
        return None
    fingerprint = annotation.get("annotation_input_fingerprint")
    return fingerprint if isinstance(fingerprint, str) else None


__all__ = [
    "AQF_CONFIG_VERSION",
    "AQF_SCHEMA_VERSION",
    "AnnotationQualityProgrammerError",
    "SUPPORTED_INPUT_SCHEMA_VERSION",
    "evaluate_stanza_result",
    "get_runtime_metadata",
]
