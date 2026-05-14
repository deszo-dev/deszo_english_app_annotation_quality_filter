from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

from .models import AnnotationQualityConfig

CompatibilityMode = Literal[
    "exact",
    "semver_compatible",
    "schema_compatible",
    "hash_exact",
]

PACKAGE_NAME = "annotation-quality-filter"
PIPELINE_NAME = "annotation_quality_filter"
PIPELINE_CONTRACT_VERSION = "1"
STAGE_NAME = "annotation_quality_filter"
STAGE_CONTRACT_VERSION = "1"
OUTPUT_SCHEMA_VERSION = "stanza-annotated-document-filtered.v1"
STATUS_SCHEMA_VERSION = "annotation-quality-status.v1"
CONFIG_CONTRACT_VERSION = "annotation-quality-config.v1"


@dataclass(frozen=True)
class RuntimeDependency:
    name: str
    version: str
    source: str
    compatibility: CompatibilityMode = "exact"
    source_fingerprint: str | None = None


@dataclass(frozen=True)
class RuntimeAsset:
    name: str
    kind: str
    sha256: str
    compatibility: CompatibilityMode = "hash_exact"


@dataclass(frozen=True)
class StageRuntimeMetadata:
    stage_name: str
    stage_contract_version: str
    output_schema_version: str
    config_contract_version: str
    module_version: str
    source_fingerprint: str | None = None
    dependencies: list[RuntimeDependency] = field(default_factory=list)
    assets: list[RuntimeAsset] = field(default_factory=list)
    status_schema_version: str = STATUS_SCHEMA_VERSION


@dataclass(frozen=True)
class PipelineRuntimeMetadata:
    pipeline_name: str
    pipeline_version: str
    pipeline_contract_version: str
    stages: dict[str, StageRuntimeMetadata]


def get_module_version(package_name: str = PACKAGE_NAME) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "unknown"


def annotation_quality_filter_runtime_metadata() -> StageRuntimeMetadata:
    return StageRuntimeMetadata(
        stage_name=STAGE_NAME,
        stage_contract_version=STAGE_CONTRACT_VERSION,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        config_contract_version=CONFIG_CONTRACT_VERSION,
        module_version=get_module_version(),
        source_fingerprint=directory_source_fingerprint(Path(__file__).parent),
        dependencies=[],
        assets=[],
    )


def pipeline_runtime_metadata() -> PipelineRuntimeMetadata:
    stage_metadata = annotation_quality_filter_runtime_metadata()
    return PipelineRuntimeMetadata(
        pipeline_name=PIPELINE_NAME,
        pipeline_version=get_module_version(),
        pipeline_contract_version=PIPELINE_CONTRACT_VERSION,
        stages={stage_metadata.stage_name: stage_metadata},
    )


def normalized_config_hash(config: AnnotationQualityConfig) -> str:
    return sha256_text(canonical_json(config))


def stage_fingerprint(
    metadata: StageRuntimeMetadata,
    config: AnnotationQualityConfig,
    *,
    input_artifact_hashes: dict[str, str] | None = None,
    pipeline_contract_version: str = PIPELINE_CONTRACT_VERSION,
) -> str:
    payload = {
        "stage_name": metadata.stage_name,
        "stage_contract_version": metadata.stage_contract_version,
        "output_schema_version": metadata.output_schema_version,
        "status_schema_version": metadata.status_schema_version,
        "config_contract_version": metadata.config_contract_version,
        "normalized_stage_config_hash": normalized_config_hash(config),
        "input_artifact_hashes": dict(sorted((input_artifact_hashes or {}).items())),
        "module_version": metadata.module_version,
        "source_fingerprint": metadata.source_fingerprint,
        "dependencies": sorted(
            [serializable_value(dependency) for dependency in metadata.dependencies],
            key=lambda dependency: dependency["name"],
        ),
        "assets": sorted(
            [serializable_value(asset) for asset in metadata.assets],
            key=lambda asset: (asset["name"], asset["kind"]),
        ),
        "pipeline_contract_version": pipeline_contract_version,
    }
    return sha256_text(canonical_json(payload))


def canonical_json(value: object) -> str:
    return json.dumps(
        serializable_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def serializable_value(value: object) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return serializable_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): serializable_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable_value(item) for item in value]
    return value


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def directory_source_fingerprint(root: Path) -> str:
    relevant_suffixes = {
        ".py",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".sql",
        ".txt",
    }
    ignored_dirs = {
        "__pycache__",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".venv",
        "node_modules",
    }

    digest = hashlib.sha256()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in relevant_suffixes:
            continue
        if any(part in ignored_dirs for part in path.relative_to(root).parts):
            continue

        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")

    return f"tree-sha256:{digest.hexdigest()}"
