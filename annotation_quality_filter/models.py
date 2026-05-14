"""Runtime models for annotation_quality_filter v2.0.

JSON shapes match the v2.0 schemas exactly and are produced as plain ``dict``
objects for direct serialization. Only configuration carries a dataclass
representation because it is used as a typed argument across the pipeline.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .schemas import EFFECTIVE_CONFIG_SCHEMA_ID, USER_CONFIG_SCHEMA_ID, first_error

CONFIG_VERSION = "annotation_quality_filter_config.v2.0"

DEFAULT_CONFIG: dict[str, Any] = {
    "thresholds": {"high": 0.8, "medium": 0.6, "low": 0.3},
    "weights": {
        "structural": 0.3,
        "dependency": 0.35,
        "morphology": 0.15,
        "sentence": 0.1,
        "distribution": 0.1,
    },
    "limits": {
        "max_sentence_length": 60,
        "long_sentence_soft": 40,
        "long_sentence_hard": 80,
        "max_conj_ratio": 0.3,
        "severe_conj_ratio": 0.5,
        "max_noun_ratio": 0.6,
        "max_deprel_ratio": 0.5,
        "max_output_json_bytes": 10485760,
        "max_input_json_bytes": 52428800,
        "max_json_depth": 200,
    },
    "checks": {
        "enable_structural": True,
        "enable_dependency": True,
        "enable_morphology": True,
        "enable_sentence": True,
        "enable_distribution": True,
        "enable_entity": True,
        "validate_text_slices": True,
    },
    "include_debug": False,
    "logging": {"enabled": False, "level": "error"},
}


@dataclass(frozen=True)
class ConfigValidationFailure:
    """Outcome of config validation. ``kind`` is either ``"schema"`` or ``"invariant"``."""

    kind: str
    path: str
    message: str


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def resolve_effective_config(
    user_override: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, ConfigValidationFailure | None]:
    """Validate the user override, deep-merge with defaults, and check invariants.

    Returns ``(effective, None)`` on success and ``(None, failure)`` on any
    failure path. The user override is rejected against the user-config schema
    before defaults are applied; the resolved effective config is then validated
    against the effective-config schema and the documented invariants.
    """

    override = user_override or {}
    if not isinstance(override, dict):
        return None, ConfigValidationFailure(
            kind="schema",
            path="",
            message="Config must be a JSON object.",
        )

    schema_err = first_error(USER_CONFIG_SCHEMA_ID, override)
    if schema_err is not None:
        path, message = schema_err
        return None, ConfigValidationFailure(kind="schema", path=path, message=message)

    effective = _deep_merge(DEFAULT_CONFIG, override)

    effective_err = first_error(EFFECTIVE_CONFIG_SCHEMA_ID, effective)
    if effective_err is not None:
        path, message = effective_err
        return None, ConfigValidationFailure(kind="schema", path=path, message=message)

    invariant = _check_invariants(effective)
    if invariant is not None:
        return None, invariant

    return effective, None


def _check_invariants(cfg: dict[str, Any]) -> ConfigValidationFailure | None:
    """Cross-field invariants from architecture §5.3 (CFG-INV-001..007)."""

    thresholds = cfg["thresholds"]
    if not (thresholds["low"] <= thresholds["medium"] <= thresholds["high"]):
        return ConfigValidationFailure(
            kind="invariant",
            path="/thresholds",
            message="Config violates thresholds invariant.",
        )

    weights = cfg["weights"]
    enabled_sum = 0.0
    for family in ("structural", "dependency", "morphology", "sentence", "distribution"):
        if cfg["checks"][f"enable_{family}"]:
            value = float(weights[family])
            if value <= 0.0:
                return ConfigValidationFailure(
                    kind="invariant",
                    path=f"/weights/{family}",
                    message=f"Enabled family weight {family!r} must be > 0.",
                )
            enabled_sum += value
    if enabled_sum <= 0.0:
        return ConfigValidationFailure(
            kind="invariant",
            path="/weights",
            message="Sum of enabled-family weights must be > 0.",
        )

    limits = cfg["limits"]
    if not (
        limits["long_sentence_soft"] <= limits["max_sentence_length"] <= limits["long_sentence_hard"]
    ):
        return ConfigValidationFailure(
            kind="invariant",
            path="/limits",
            message="Config violates long_sentence_soft <= max_sentence_length <= long_sentence_hard.",
        )
    if limits["max_conj_ratio"] > limits["severe_conj_ratio"]:
        return ConfigValidationFailure(
            kind="invariant",
            path="/limits",
            message="Config violates max_conj_ratio <= severe_conj_ratio.",
        )

    return None
