from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

QualityLabel = Literal["ACCEPT", "WEAK_ACCEPT", "REJECT"]


@dataclass(frozen=True)
class Thresholds:
    accept: float = 0.80
    weak_accept: float = 0.60


@dataclass(frozen=True)
class Weights:
    structural: float = 0.30
    dependency: float = 0.35
    morphology: float = 0.15
    sentence: float = 0.10
    distribution: float = 0.10


@dataclass(frozen=True)
class Limits:
    max_sentence_length: int = 60
    max_conj_ratio: float = 0.30
    min_token_count: int = 2


@dataclass(frozen=True)
class Checks:
    enable_morphology: bool = True
    enable_dependency: bool = True
    enable_distribution: bool = True


@dataclass(frozen=True)
class AnnotationQualityConfig:
    thresholds: Thresholds = field(default_factory=Thresholds)
    weights: Weights = field(default_factory=Weights)
    limits: Limits = field(default_factory=Limits)
    checks: Checks = field(default_factory=Checks)


@dataclass(frozen=True)
class AnnotationQualityResult:
    score: float
    label: QualityLabel
    reasons: list[str]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

