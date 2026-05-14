"""Sentence/entity scoring from collected issues (architecture §8.1).

Family scores start at 1.0 and accept registered penalties; a single
``hard_invalid`` issue collapses the sentence score to 0.0 and band ``invalid``.
The overall sentence score is the weighted mean over *enabled* families,
normalized by the sum of enabled-family weights. Scores and means are exact
after 6-decimal round-half-even rounding.
"""

from __future__ import annotations

import decimal
from typing import Any

from ..issues import specs as issue_specs

_FAMILIES = ("structural", "dependency", "morphology", "sentence", "distribution")

_ENABLE_KEYS = {f: f"enable_{f}" for f in _FAMILIES}


def round6(value: float) -> float:
    return float(decimal.Decimal(value).quantize(decimal.Decimal("0.000001"), rounding=decimal.ROUND_HALF_EVEN))


def _band(score: float, thresholds: dict[str, float], *, invalid: bool) -> str:
    if invalid:
        return "invalid"
    if score >= float(thresholds["high"]):
        return "high"
    if score >= float(thresholds["medium"]):
        return "medium"
    if score >= float(thresholds["low"]):
        return "low"
    return "low"


def _risk_level(band: str, score: float) -> str:
    if band == "invalid":
        return "critical"
    if band == "high":
        return "low"
    if band == "medium":
        return "medium"
    return "high"


def score_sentence(
    issues: list[dict[str, Any]],
    *,
    cfg: dict[str, Any],
) -> tuple[float, str, str]:
    """Return ``(score, band, risk_level)`` for a sentence."""

    family_score = {f: 1.0 for f in _FAMILIES}
    invalid = False

    # Apply penalties / detect hard_invalid; emit each issue code at most once per family for "single penalty" issues.
    emitted_once: set[tuple[str, str]] = set()
    single_penalty_codes = {"EXCESSIVE_CONJ", "EMPTY_MORPHOLOGY", "TOO_LONG_SENTENCE"}

    for issue in issues:
        code = issue["code"]
        spec = issue_specs().get(code)
        if spec is None:
            continue
        if spec.mode == "hard_invalid":
            if spec.scope == "sentence":
                invalid = True
                continue
        if spec.mode == "penalty":
            key = (spec.family, code)
            if code in single_penalty_codes and key in emitted_once:
                continue
            emitted_once.add(key)
            family_score[spec.family] = max(0.0, family_score[spec.family] - spec.penalty)

    if invalid:
        return 0.0, "invalid", "critical"

    weights = cfg["weights"]
    enabled_sum = 0.0
    weighted_sum = 0.0
    for family in _FAMILIES:
        if cfg["checks"][_ENABLE_KEYS[family]]:
            w = float(weights[family])
            enabled_sum += w
            weighted_sum += w * family_score[family]

    score = weighted_sum / enabled_sum if enabled_sum > 0 else 0.0
    score = round6(min(1.0, max(0.0, score)))
    band = _band(score, cfg["thresholds"], invalid=False)
    return score, band, _risk_level(band, score)


def score_entity(issues: list[dict[str, Any]], *, cfg: dict[str, Any]) -> tuple[float, str]:
    base = 1.0
    invalid = False
    for issue in issues:
        spec = issue_specs().get(issue["code"])
        if spec is None:
            continue
        if spec.mode == "hard_invalid":
            invalid = True
            continue
        if spec.mode == "penalty":
            base = max(0.0, base - spec.penalty)
    if invalid:
        return 0.0, "invalid"
    score = round6(min(1.0, max(0.0, base)))
    return score, _band(score, cfg["thresholds"], invalid=False)
