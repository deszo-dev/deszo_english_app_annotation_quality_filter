"""Runtime metadata for annotation_quality_filter v2.0.

Single source of version strings consumed by the package, the output wrapper,
and the runtime_metadata guideline contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MODULE_NAME = "annotation_quality_filter"
MODULE_VERSION = "2.0.0"

STAGE_NAME = "annotation_quality_filter"
STAGE_CONTRACT_VERSION = "annotation_quality_filter.v2.0"

INPUT_SCHEMA_VERSION = "stanza_annotator.v2.0"
OUTPUT_SCHEMA_VERSION = "annotation_quality_filter.v2.0"
CONFIG_CONTRACT_VERSION = "annotation_quality_filter_config.v2.0"
DIAGNOSTICS_SCHEMA_VERSION = "annotation_quality_filter_diagnostics.v2.0"
ISSUE_REGISTRY_VERSION = "annotation_quality_filter_issue_registry.v2.0"
ERROR_REGISTRY_VERSION = "annotation_quality_filter_error_registry.v2.0"

CHECKER_VERSIONS: dict[str, str] = {"core": MODULE_VERSION}


@dataclass(frozen=True)
class StageRuntimeMetadata:
    module_name: str
    module_version: str
    stage_name: str
    stage_contract_version: str
    input_schema_version: str
    output_schema_version: str
    config_contract_version: str
    diagnostics_schema_version: str
    issue_registry_version: str
    error_registry_version: str
    checker_versions: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_name": self.module_name,
            "module_version": self.module_version,
            "stage_name": self.stage_name,
            "stage_contract_version": self.stage_contract_version,
            "input_schema_version": self.input_schema_version,
            "output_schema_version": self.output_schema_version,
            "config_contract_version": self.config_contract_version,
            "diagnostics_schema_version": self.diagnostics_schema_version,
            "issue_registry_version": self.issue_registry_version,
            "error_registry_version": self.error_registry_version,
            "checker_versions": dict(self.checker_versions),
        }


STAGE_METADATA = StageRuntimeMetadata(
    module_name=MODULE_NAME,
    module_version=MODULE_VERSION,
    stage_name=STAGE_NAME,
    stage_contract_version=STAGE_CONTRACT_VERSION,
    input_schema_version=INPUT_SCHEMA_VERSION,
    output_schema_version=OUTPUT_SCHEMA_VERSION,
    config_contract_version=CONFIG_CONTRACT_VERSION,
    diagnostics_schema_version=DIAGNOSTICS_SCHEMA_VERSION,
    issue_registry_version=ISSUE_REGISTRY_VERSION,
    error_registry_version=ERROR_REGISTRY_VERSION,
    checker_versions=CHECKER_VERSIONS,
)
