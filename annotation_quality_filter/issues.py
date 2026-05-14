"""Issue registry for annotation_quality_filter v2.0.

Codes, severities, families, and penalty effects are sourced from
``_registry/annotation_quality_filter_issue_registry.v2.0.json``. Every issue
emitted by the core MUST match a registered code; otherwise the registry-aware
:func:`make_issue` helper raises.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .schemas import load_registry

ISSUE_REGISTRY_VERSION = "annotation_quality_filter_issue_registry.v2.0"


@dataclass(frozen=True)
class IssueSpec:
    code: str
    severity: str  # "info" | "warning" | "error"
    entity_type: str  # "text_unit" | "sentence" | "token" | "word" | "entity"
    family: str  # "structural" | "dependency" | "morphology" | "sentence" | "distribution" | "entity"
    scope: str  # "sentence" | "entity"
    mode: str  # "hard_invalid" | "penalty"
    penalty: float
    message_template: str


@lru_cache(maxsize=1)
def _registry_raw() -> dict[str, Any]:
    return load_registry("annotation_quality_filter_issue_registry.v2.0.json")


@lru_cache(maxsize=1)
def specs() -> dict[str, IssueSpec]:
    out: dict[str, IssueSpec] = {}
    for entry in _registry_raw()["codes"]:
        effect = entry["score_effect"]
        out[entry["code"]] = IssueSpec(
            code=entry["code"],
            severity=entry["severity"],
            entity_type=entry["entity_type"],
            family=entry["family"],
            scope=entry["scope"],
            mode=effect["mode"],
            penalty=float(effect.get("penalty", 0.0)),
            message_template=entry["message_template"],
        )
    return out


def make_issue(
    code: str,
    *,
    entity_type: str,
    entity_id: str,
    field: str | None = None,
    path: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Build a ``QualityIssue`` dict validated against the registry.

    Raises ``KeyError`` if ``code`` is not registered.
    """

    spec = specs()[code]
    rendered = message if message is not None else spec.message_template.format(
        entity_type=entity_type, entity_id=entity_id
    )
    issue: dict[str, Any] = {
        "code": code,
        "severity": spec.severity,
        "message": rendered,
        "entity_type": entity_type,
        "entity_id": entity_id,
    }
    if field is not None:
        issue["field"] = field
    if path is not None:
        issue["path"] = path
    return issue
