"""Error registry and exit-code mapping for annotation_quality_filter v2.0.

Top-level error codes, severities, CLI exit codes, and helper diagnostic codes
are sourced from ``_registry/annotation_quality_filter_error_registry.v2.0.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .schemas import load_registry

ERROR_REGISTRY_VERSION = "annotation_quality_filter_error_registry.v2.0"


@dataclass(frozen=True)
class ErrorSpec:
    code: str
    severity: str
    cli_exit_code: int
    message_template: str


@dataclass(frozen=True)
class DiagnosticHelperSpec:
    code: str
    severity: str
    maps_to_error_code: str
    cli_exit_code: int


@lru_cache(maxsize=1)
def _registry() -> dict[str, Any]:
    return load_registry("annotation_quality_filter_error_registry.v2.0.json")


@lru_cache(maxsize=1)
def errors() -> dict[str, ErrorSpec]:
    return {
        e["code"]: ErrorSpec(
            code=e["code"],
            severity=e["severity"],
            cli_exit_code=int(e["cli_exit_code"]),
            message_template=e["message_template"],
        )
        for e in _registry()["errors"]
    }


@lru_cache(maxsize=1)
def diagnostic_helpers() -> dict[str, DiagnosticHelperSpec]:
    return {
        d["code"]: DiagnosticHelperSpec(
            code=d["code"],
            severity=d["severity"],
            maps_to_error_code=d["maps_to_error_code"],
            cli_exit_code=int(d["cli_exit_code"]),
        )
        for d in _registry()["diagnostic_helpers"]
    }


def exit_code_for(error_code: str) -> int:
    """Return the CLI exit code defined for an error code."""

    return errors()[error_code].cli_exit_code


def helper_code_for(error_code: str) -> str:
    """Return the canonical helper-diagnostic code mapping to ``error_code``."""

    for helper in diagnostic_helpers().values():
        if helper.maps_to_error_code == error_code:
            return helper.code
    raise KeyError(f"No diagnostic helper maps to error code {error_code!r}")


# Exception hierarchy --------------------------------------------------------


class AnnotationQualityError(Exception):
    """Base class for annotation_quality_filter expected failures."""

    code: str = "internal_error"
    helper_code: str = "unexpected_internal_error"
    helper_path: str = ""

    def __init__(self, message: str, *, path: str = "") -> None:
        super().__init__(message)
        self.message = message
        if path:
            self.helper_path = path

    @property
    def exit_code(self) -> int:
        return exit_code_for(self.code)


class InvalidConfigError(AnnotationQualityError):
    code = "invalid_config"
    helper_code = "config_schema_validation_failed"


class InvalidConfigInvariantError(AnnotationQualityError):
    code = "invalid_config"
    helper_code = "config_invariant_failed"


class InvalidInputError(AnnotationQualityError):
    code = "invalid_input"
    helper_code = "input_schema_validation_failed"


class InvalidInputParseError(AnnotationQualityError):
    code = "invalid_input"
    helper_code = "input_json_parse_failed"


class UnsupportedStanzaSchemaError(AnnotationQualityError):
    code = "unsupported_stanza_schema"
    helper_code = "unsupported_input_schema_version"
    helper_path = "/schema_version"


class UpstreamStanzaAnnotationFailed(AnnotationQualityError):
    code = "upstream_stanza_annotation_failed"
    helper_code = "upstream_failure_status_seen"
    helper_path = "/status"


class OutputTooLargeError(AnnotationQualityError):
    code = "output_too_large"
    helper_code = "output_serialization_too_large"
    helper_path = "/limits/max_output_json_bytes"


class OutputWriteError(AnnotationQualityError):
    code = "output_write_failed"
    helper_code = "output_channel_write_failed"


class InternalError(AnnotationQualityError):
    code = "internal_error"
    helper_code = "unexpected_internal_error"
