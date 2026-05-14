"""annotation_quality_filter — Stanza v2.0 annotation quality enricher.

Migrated from the legacy filter contract to the v2.0 enrichment contract. The
module produces ``AnnotationQualityEnrichmentResult`` JSON that preserves the
input ``StanzaAnnotationResult`` unchanged and attaches a module-owned
``quality`` sidecar. See ``docs/architecture/annotation_quality_filter_architecture.md``.
"""

from .errors import (
    AnnotationQualityError,
    InternalError,
    InvalidConfigError,
    InvalidConfigInvariantError,
    InvalidInputError,
    InvalidInputParseError,
    OutputTooLargeError,
    OutputWriteError,
    UnsupportedStanzaSchemaError,
    UpstreamStanzaAnnotationFailed,
)
from .pipeline import evaluate_stanza_result
from .runtime_metadata import (
    CONFIG_CONTRACT_VERSION,
    INPUT_SCHEMA_VERSION,
    MODULE_NAME,
    MODULE_VERSION,
    OUTPUT_SCHEMA_VERSION,
    STAGE_CONTRACT_VERSION,
    STAGE_METADATA,
)

__all__ = [
    "AnnotationQualityError",
    "CONFIG_CONTRACT_VERSION",
    "INPUT_SCHEMA_VERSION",
    "InternalError",
    "InvalidConfigError",
    "InvalidConfigInvariantError",
    "InvalidInputError",
    "InvalidInputParseError",
    "MODULE_NAME",
    "MODULE_VERSION",
    "OUTPUT_SCHEMA_VERSION",
    "OutputTooLargeError",
    "OutputWriteError",
    "STAGE_CONTRACT_VERSION",
    "STAGE_METADATA",
    "UnsupportedStanzaSchemaError",
    "UpstreamStanzaAnnotationFailed",
    "evaluate_stanza_result",
]
