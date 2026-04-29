from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TypeAlias

JsonObject: TypeAlias = dict[str, Any]

FilterStatus: TypeAlias = Literal["ACCEPT", "WEAK_ACCEPT", "REJECT"]
RetentionPolicy: TypeAlias = Literal["ACCEPT_AND_WEAK_ACCEPT", "ACCEPT_ONLY"]
UnresolvableSentenceSpanPolicy: TypeAlias = Literal["error", "drop_entities"]

AnnotatedDocument: TypeAlias = JsonObject
Sentence: TypeAlias = JsonObject
Token: TypeAlias = JsonObject
Word: TypeAlias = JsonObject
Entity: TypeAlias = JsonObject


class AnnotationQualityError(Exception):
    """Base error for expected annotation-quality failures."""


class InputValidationError(AnnotationQualityError):
    """Raised when input does not satisfy the AnnotatedDocument contract."""


class ConfigurationError(AnnotationQualityError):
    """Raised when configuration is invalid."""


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
    long_sentence_soft: int = 40
    long_sentence_hard: int = 80
    max_conj_ratio: float = 0.30
    severe_conj_ratio: float = 0.50
    min_token_count: int = 2


@dataclass(frozen=True)
class Checks:
    enable_morphology: bool = True
    enable_dependency: bool = True
    enable_distribution: bool = True


@dataclass(frozen=True)
class EntityFilteringConfig:
    enabled: bool = True
    on_unresolvable_sentence_span: UnresolvableSentenceSpanPolicy = "error"


@dataclass(frozen=True)
class AnnotationQualityConfig:
    thresholds: Thresholds = field(default_factory=Thresholds)
    retention_policy: RetentionPolicy = "ACCEPT_AND_WEAK_ACCEPT"
    weights: Weights = field(default_factory=Weights)
    limits: Limits = field(default_factory=Limits)
    checks: Checks = field(default_factory=Checks)
    entity_filtering: EntityFilteringConfig = field(default_factory=EntityFilteringConfig)
    debug: bool = False
    config_version: str = "1"


@dataclass(frozen=True)
class AnnotationQualityResult:
    score: float
    label: FilterStatus
    reasons: list[str]
    diagnostics: JsonObject

    def to_dict(self) -> JsonObject:
        return asdict(self)


@dataclass(frozen=True)
class AnnotationQualityAnnotation:
    input_sentence_index: int
    sentence_text: str
    included_in_output: bool
    status: FilterStatus
    result: AnnotationQualityResult
    output_sentence_index: int | None = None

    def to_dict(self) -> JsonObject:
        payload = {
            "input_sentence_index": self.input_sentence_index,
            "sentence_text": self.sentence_text,
            "included_in_output": self.included_in_output,
            "status": self.status,
            "result": self.result.to_dict(),
        }
        if self.output_sentence_index is not None:
            payload["output_sentence_index"] = self.output_sentence_index
        return payload


@dataclass(frozen=True)
class AnnotationQualitySummary:
    total_input_sentences: int
    total_output_sentences: int
    accepted: int
    weak_accepted: int
    rejected: int
    mean_score: float

    def to_dict(self) -> JsonObject:
        return asdict(self)


@dataclass(frozen=True)
class AnnotationQualityDocumentStatus:
    annotations: list[AnnotationQualityAnnotation]
    summary: AnnotationQualitySummary
    config_version: str
    retention_policy: RetentionPolicy

    def to_dict(self) -> JsonObject:
        return {
            "annotations": [annotation.to_dict() for annotation in self.annotations],
            "summary": self.summary.to_dict(),
            "config_version": self.config_version,
            "retention_policy": self.retention_policy,
        }


@dataclass(frozen=True)
class AnnotationQualityFilterOutput:
    document: AnnotatedDocument
    status: AnnotationQualityDocumentStatus

    def to_dict(self) -> JsonObject:
        return {
            "document": self.document,
            "status": self.status.to_dict(),
        }


def validate_config(config: AnnotationQualityConfig) -> None:
    thresholds = config.thresholds
    if not 0.0 < thresholds.weak_accept <= thresholds.accept <= 1.0:
        raise ConfigurationError(
            "thresholds must satisfy 0.0 < weak_accept <= accept <= 1.0"
        )

    weights = config.weights
    values = [
        weights.structural,
        weights.dependency,
        weights.morphology,
        weights.sentence,
        weights.distribution,
    ]
    if any(value < 0.0 for value in values):
        raise ConfigurationError("weights must be non-negative")
    if abs(sum(values) - 1.0) > 0.000001:
        raise ConfigurationError("weights must sum to 1.0")

    limits = config.limits
    if any(
        value <= 0
        for value in [
            limits.max_sentence_length,
            limits.long_sentence_soft,
            limits.long_sentence_hard,
            limits.min_token_count,
        ]
    ):
        raise ConfigurationError("integer limits must be positive")
    if not limits.long_sentence_soft <= limits.max_sentence_length <= limits.long_sentence_hard:
        raise ConfigurationError(
            "sentence limits must satisfy soft <= max_sentence_length <= hard"
        )
    if not 0.0 < limits.max_conj_ratio <= limits.severe_conj_ratio <= 1.0:
        raise ConfigurationError(
            "conjunction ratios must satisfy 0.0 < max <= severe <= 1.0"
        )
