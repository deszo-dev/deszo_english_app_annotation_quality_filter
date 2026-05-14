"""End-to-end pipeline for annotation_quality_filter v2.0.

Implements the architecture §0.3 / §11 contract:

1. Validate user config (schema + invariants).
2. Validate input shape (JSON-compat then Stanza v2.0 schema).
3. Check ``schema_version`` and upstream ``status``.
4. Traverse text units, run checkers, score sentences/entities.
5. Assemble ``AnnotationQualityEnrichmentResult`` and validate output.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from . import canonical_json, schemas
from .errors import (
    AnnotationQualityError,
    InternalError,
    InvalidConfigError,
    InvalidConfigInvariantError,
    InvalidInputError,
    InvalidInputParseError,
    UnsupportedStanzaSchemaError,
    UpstreamStanzaAnnotationFailed,
    helper_code_for,
)
from .core.checkers import check_entity, check_sentence
from .core.scoring import round6, score_entity, score_sentence
from .core.traversal import QualityTarget, traverse
from .fingerprint import compute_quality_input_fingerprint
from .issues import specs as issue_specs
from .models import CONFIG_VERSION, ConfigValidationFailure, resolve_effective_config
from .runtime_metadata import (
    CHECKER_VERSIONS,
    INPUT_SCHEMA_VERSION,
    MODULE_NAME,
    MODULE_VERSION,
    OUTPUT_SCHEMA_VERSION,
)


def _failed_result(
    *,
    error_code: str,
    message: str,
    helper_code: str | None = None,
    helper_path: str = "",
    helper_message: str | None = None,
) -> dict[str, Any]:
    helper = helper_code or helper_code_for(error_code)
    diagnostic: dict[str, Any] = {
        "code": helper,
        "severity": "error",
        "message": helper_message or message,
        "source": "annotation_quality_filter",
        "path": helper_path,
    }
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "status": "failed",
        "diagnostics": [diagnostic],
        "annotation_quality": {
            "module_name": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "config_version": CONFIG_VERSION,
            "status": "failed",
            "duration_ms": 0.0,
        },
        "error": {
            "code": error_code,
            "message": message,
            "recoverable": False,
        },
    }


def _is_json_compatible(value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, list):
        return all(_is_json_compatible(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_json_compatible(v) for k, v in value.items())
    return False


def _band_to_summary_key(band: str, kind: str) -> str:
    return f"{band}_quality_{kind}"


def _build_text_unit_quality(
    target: QualityTarget,
    *,
    cfg: dict[str, Any],
) -> tuple[dict[str, Any], list[float], list[float], int, int]:
    """Return ``(text_unit_quality, sentence_scores, entity_scores, warnings, errors)``."""

    if target.evaluation_status == "not_evaluated":
        unit = {
            "text_unit_id": target.text_unit_id,
            "ref": target.ref,
            "evaluation_status": "not_evaluated",
            "not_evaluated_reason": target.not_evaluated_reason or "missing_annotation",
            "sentence_quality": [],
            "entity_quality": [],
            "summary": _empty_text_unit_summary(),
        }
        return unit, [], [], 0, 0

    ann = target.annotation or {}
    sentences = ann.get("sentences") or []
    entities = ann.get("entities") or []
    text_unit_text = ann.get("text") or ""
    text_unit_offset = sentences[0].get("start_char", 0) if sentences else 0

    sentence_quality: list[dict[str, Any]] = []
    sentence_scores: list[float] = []
    sentence_warnings = 0
    sentence_errors = 0
    band_counts_s: Counter[str] = Counter()

    for sentence in sentences:
        issues, family_diags = check_sentence(
            sentence,
            text_unit_text=text_unit_text,
            text_unit_offset=text_unit_offset,
            cfg=cfg,
        )
        score, band, risk = score_sentence(issues, cfg=cfg)
        sentence_quality.append(
            {
                "sentence_id": sentence.get("id") or "",
                "text_unit_id": sentence.get("text_unit_id") or target.text_unit_id,
                "sentence_number": int(sentence.get("sentence_number") or 1),
                "score": score,
                "band": band,
                "risk_level": risk,
                "issues": issues,
                "diagnostics": family_diags,
            }
        )
        sentence_scores.append(score)
        band_counts_s[band] += 1
        for issue in issues:
            if issue["severity"] == "warning":
                sentence_warnings += 1
            elif issue["severity"] == "error":
                sentence_errors += 1

    entity_quality: list[dict[str, Any]] = []
    entity_scores: list[float] = []
    entity_warnings = 0
    entity_errors = 0
    band_counts_e: Counter[str] = Counter()

    if cfg["checks"]["enable_entity"]:
        for entity in entities:
            issues = check_entity(
                entity,
                text_unit_text=text_unit_text,
                text_unit_offset=text_unit_offset,
                validate_slices=cfg["checks"]["validate_text_slices"],
            )
            score, band = score_entity(issues, cfg=cfg)
            entity_quality.append(
                {
                    "entity_id": entity.get("id") or "",
                    "text_unit_id": entity.get("text_unit_id") or target.text_unit_id,
                    "entity_number": int(entity.get("entity_number") or 1),
                    "score": score,
                    "band": band,
                    "issues": issues,
                }
            )
            entity_scores.append(score)
            band_counts_e[band] += 1
            for issue in issues:
                if issue["severity"] == "warning":
                    entity_warnings += 1
                elif issue["severity"] == "error":
                    entity_errors += 1

    unit_summary = {
        "sentence_count": len(sentences),
        "evaluated_sentence_count": len(sentence_quality),
        "entity_count": len(entities),
        "evaluated_entity_count": len(entity_quality),
        "high_quality_sentences": band_counts_s["high"],
        "medium_quality_sentences": band_counts_s["medium"],
        "low_quality_sentences": band_counts_s["low"],
        "invalid_sentences": band_counts_s["invalid"],
        "high_quality_entities": band_counts_e["high"],
        "medium_quality_entities": band_counts_e["medium"],
        "low_quality_entities": band_counts_e["low"],
        "invalid_entities": band_counts_e["invalid"],
        "mean_sentence_score": (
            round6(sum(sentence_scores) / len(sentence_scores)) if sentence_scores else None
        ),
        "mean_entity_score": (
            round6(sum(entity_scores) / len(entity_scores)) if entity_scores else None
        ),
        "warning_count": sentence_warnings + entity_warnings,
        "error_count": sentence_errors + entity_errors,
    }

    return (
        {
            "text_unit_id": target.text_unit_id,
            "ref": target.ref,
            "evaluation_status": "evaluated",
            "sentence_quality": sentence_quality,
            "entity_quality": entity_quality,
            "summary": unit_summary,
        },
        sentence_scores,
        entity_scores,
        sentence_warnings + entity_warnings,
        sentence_errors + entity_errors,
    )


def _empty_text_unit_summary() -> dict[str, Any]:
    return {
        "sentence_count": 0,
        "evaluated_sentence_count": 0,
        "entity_count": 0,
        "evaluated_entity_count": 0,
        "high_quality_sentences": 0,
        "medium_quality_sentences": 0,
        "low_quality_sentences": 0,
        "invalid_sentences": 0,
        "high_quality_entities": 0,
        "medium_quality_entities": 0,
        "low_quality_entities": 0,
        "invalid_entities": 0,
        "mean_sentence_score": None,
        "mean_entity_score": None,
        "warning_count": 0,
        "error_count": 0,
    }


def evaluate_stanza_result(
    input_data: Any,
    *,
    user_config: dict[str, Any] | None = None,
    include_debug: bool = False,
) -> dict[str, Any]:
    """Top-level API. Returns an ``AnnotationQualityEnrichmentResult`` dict.

    Expected domain/config/input failures are reported as a failed result with
    ``error.code`` from ``annotation_quality_filter_error_registry.v2.0.json``.
    Only true programmer misuse (non-JSON Python objects passed in) raises.
    """

    try:
        # ---- config -------------------------------------------------------
        effective, cfg_fail = resolve_effective_config(user_config)
        if cfg_fail is not None:
            return _config_failed_result(cfg_fail)
        assert effective is not None

        # ---- input shape -------------------------------------------------
        if not _is_json_compatible(input_data):
            raise TypeError(
                "input_data is not JSON-compatible; programmer misuse"
            )
        if not isinstance(input_data, dict):
            return _failed_result(
                error_code="invalid_input",
                message="Input must be a JSON object.",
                helper_code="input_schema_validation_failed",
            )

        schema_version = input_data.get("schema_version")
        if schema_version is not None and schema_version != INPUT_SCHEMA_VERSION:
            return _failed_result(
                error_code="unsupported_stanza_schema",
                message="Unsupported Stanza schema version.",
                helper_code="unsupported_input_schema_version",
                helper_path="/schema_version",
            )

        input_err = schemas.validate_input(input_data)
        if input_err is not None:
            path, _message = input_err
            return _failed_result(
                error_code="invalid_input",
                message="Input does not satisfy the consumed Stanza schema.",
                helper_code="input_schema_validation_failed",
                helper_path=path or "/document",
            )

        if input_data.get("status") == "failed":
            return _failed_result(
                error_code="upstream_stanza_annotation_failed",
                message="Upstream stanza annotation failed.",
                helper_code="upstream_failure_status_seen",
                helper_path="/status",
            )

        if input_data.get("status") != "succeeded" or "document" not in input_data:
            return _failed_result(
                error_code="invalid_input",
                message="Successful Stanza result must include document.",
                helper_code="input_schema_validation_failed",
                helper_path="/document",
            )

        # ---- evaluate ----------------------------------------------------
        targets = traverse(input_data)
        text_units_payload: list[dict[str, Any]] = []
        all_sentence_scores: list[float] = []
        all_entity_scores: list[float] = []
        total_warnings = 0
        total_errors = 0
        band_s_total: Counter[str] = Counter()
        band_e_total: Counter[str] = Counter()
        evaluated_units = 0
        not_evaluated_units = 0

        for target in targets:
            unit, s_scores, e_scores, warns, errs = _build_text_unit_quality(target, cfg=effective)
            text_units_payload.append(unit)
            all_sentence_scores.extend(s_scores)
            all_entity_scores.extend(e_scores)
            total_warnings += warns
            total_errors += errs
            if target.evaluation_status == "evaluated":
                evaluated_units += 1
                for sq in unit["sentence_quality"]:
                    band_s_total[sq["band"]] += 1
                for eq in unit["entity_quality"]:
                    band_e_total[eq["band"]] += 1
            else:
                not_evaluated_units += 1

        summary = {
            "total_text_units_seen": len(targets),
            "evaluated_text_units": evaluated_units,
            "not_evaluated_text_units": not_evaluated_units,
            "total_sentences_evaluated": len(all_sentence_scores),
            "high_quality_sentences": band_s_total["high"],
            "medium_quality_sentences": band_s_total["medium"],
            "low_quality_sentences": band_s_total["low"],
            "invalid_sentences": band_s_total["invalid"],
            "total_entities_evaluated": len(all_entity_scores),
            "high_quality_entities": band_e_total["high"],
            "medium_quality_entities": band_e_total["medium"],
            "low_quality_entities": band_e_total["low"],
            "invalid_entities": band_e_total["invalid"],
            "mean_sentence_score": (
                round6(sum(all_sentence_scores) / len(all_sentence_scores))
                if all_sentence_scores
                else None
            ),
            "mean_entity_score": (
                round6(sum(all_entity_scores) / len(all_entity_scores))
                if all_entity_scores
                else None
            ),
            "warning_count": total_warnings,
            "error_count": total_errors,
        }

        fingerprint = compute_quality_input_fingerprint(
            input_data,
            effective_config=effective,
            module_version=MODULE_VERSION,
            checker_versions=CHECKER_VERSIONS,
        )

        annotation = input_data.get("annotation") or {}
        source_payload = {
            "stanza_schema_version": INPUT_SCHEMA_VERSION,
            "quality_input_fingerprint": fingerprint,
        }
        for key, src in (
            ("stanza_annotator_version", "annotator_version"),
            ("stanza_version", "stanza_version"),
            ("source_book_fingerprint", "source_book_fingerprint"),
            ("annotation_input_fingerprint", "annotation_input_fingerprint"),
        ):
            if src in annotation:
                source_payload[key] = annotation[src]

        # Field naming alignment with F001 expected: F001 uses
        # ``source_book_fingerprint`` and ``annotation_input_fingerprint`` directly.
        source_payload.pop("stanza_annotator_version", None)
        source_payload.pop("stanza_version", None)

        quality = {
            "source": source_payload,
            "text_units": text_units_payload,
            "summary": summary,
            "config_version": CONFIG_VERSION,
        }

        result: dict[str, Any] = {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "status": "succeeded",
            "document": input_data,
            "quality": quality,
            "diagnostics": [],
            "annotation_quality": {
                "module_name": MODULE_NAME,
                "module_version": MODULE_VERSION,
                "config_version": CONFIG_VERSION,
                "status": "succeeded",
                "duration_ms": 0.0,
                "quality_input_fingerprint": fingerprint,
                "checker_versions": dict(CHECKER_VERSIONS),
            },
        }

        if include_debug:
            result["debug"] = {
                "effective_config": effective,
            }

        return result

    except TypeError:
        raise
    except AnnotationQualityError as err:
        return _failed_result(
            error_code=err.code,
            message=err.message,
            helper_code=err.helper_code,
            helper_path=err.helper_path,
        )
    except Exception as err:  # pragma: no cover - defensive
        return _failed_result(
            error_code="internal_error",
            message=f"Unexpected error: {err}",
            helper_code="unexpected_internal_error",
        )


def _config_failed_result(failure: ConfigValidationFailure) -> dict[str, Any]:
    if failure.kind == "invariant":
        helper = "config_invariant_failed"
        # Use the invariant-specific message from the validator (e.g. "Config
        # violates thresholds invariant.") — matches C001 golden output.
        message = failure.message
    else:
        helper = "config_schema_validation_failed"
        # Schema-derived messages contain implementation-specific text (e.g. the
        # jsonschema "Additional properties are not allowed (...)") which would
        # leak validator internals into the public output. Replace with a
        # canonical message; the diagnostic ``path`` retains the JSON pointer.
        message = "Config violates user config schema."
    return _failed_result(
        error_code="invalid_config",
        message=message,
        helper_code=helper,
        helper_path=failure.path,
    )
