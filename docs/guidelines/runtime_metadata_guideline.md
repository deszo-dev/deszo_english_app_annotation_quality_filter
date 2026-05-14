# Runtime Metadata Guideline for Pipeline Modules

## Purpose

This guideline defines how pipeline modules should expose deterministic runtime metadata so that an orchestrating service can safely decide whether an existing stage output may be reused or whether the stage must be executed again.

The goal is to prevent unnecessary recomputation while avoiding unsafe reuse of stale artifacts after code, configuration, schema, model, data, or local dependency changes.

This document is intentionally generic and can be applied to any staged processing pipeline.

---

## Core principle

A stage output may be reused only when it is known to be compatible with the current runtime.

A file merely existing on disk is not enough.

The orchestrator MUST verify that the previous output was produced with a compatible:

- stage implementation;
- stage contract;
- input artifact set;
- output schema;
- normalized configuration;
- dependency set;
- model, catalog, rule, or data assets;
- local source fingerprint, when the module is a local dependency.

---

## LLM-agent instructions

When modifying or creating a pipeline module, an LLM agent MUST check whether the module affects stage output.

If the module affects output, the agent MUST add or update runtime metadata.

Use this decision rule:

```text
If changing this code, config, schema, model, catalog, rule, prompt, data file,
or dependency can change the produced artifacts, then it MUST be represented
in runtime metadata or in the stage fingerprint.
```

An LLM agent SHOULD NOT rely on comments, filenames, or informal conventions. Metadata must be explicit, serializable, and testable.

---

## Required outcome

Every reusable stage SHOULD expose a deterministic metadata provider.

The orchestrator uses this metadata to compute a `stage_fingerprint`.

A stage may be skipped only when:

```text
previous stage status is succeeded
AND all expected output artifacts exist
AND artifact hashes match recorded hashes
AND artifact schema versions are compatible
AND previous stage fingerprint is compatible with current stage fingerprint
AND artifacts are not expired
AND the next stage accepts these artifacts as valid input
```

If any check fails, the stage MUST be executed again.

---

## Minimal metadata contract

Each stage module SHOULD expose metadata equivalent to the following structure.

```python
from dataclasses import dataclass, field
from typing import Literal

CompatibilityMode = Literal[
    "exact",
    "semver_compatible",
    "schema_compatible",
    "hash_exact",
]


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


class RuntimeMetadataProvider:
    def runtime_metadata(self) -> StageRuntimeMetadata:
        raise NotImplementedError
```

The exact class names are not mandatory. The required behavior is mandatory.

---

## Required fields

### `stage_name`

Stable machine-readable stage name.

MUST remain stable across releases unless the stage is intentionally replaced.

Example:

```text
content_extraction
entity_annotation
quality_filtering
feature_generation
rule_detection
```

---

### `stage_contract_version`

Version of the stage behavior contract.

Change this when the meaning of the stage changes, even if the output schema stays the same.

Examples of changes that require a new contract version:

- different processing semantics;
- different filtering rules;
- different ordering guarantees;
- changed interpretation of config fields;
- changed expected input artifact types;
- changed output completeness guarantees.

---

### `output_schema_version`

Version of artifacts produced by the stage.

Change this when the output structure changes.

Examples:

- fields added or removed;
- field meaning changed;
- enum values changed;
- page or manifest format changed;
- serialization rules changed.

---

### `config_contract_version`

Version of the normalized config accepted by the stage.

Change this when config semantics change.

The orchestrator SHOULD hash normalized config values as part of the stage fingerprint.

---

### `module_version`

Version of the module or component.

For packaged dependencies, this may come from package metadata.

For local dependencies, `module_version` alone is not enough. Local dependencies MUST also provide `source_fingerprint`.

---

### `source_fingerprint`

A deterministic identifier for the exact source used to produce output.

Required for local dependencies and editable installs.

Allowed formats:

```text
git:<commit_sha>
git:<commit_sha>-dirty
tree-sha256:<hash_of_relevant_files>
build:<ci_build_id>
```

The fingerprint MUST NOT include:

- absolute local paths;
- timestamps;
- usernames;
- machine-specific temporary directories;
- secrets;
- environment-specific credentials.

---

### `dependencies`

List of runtime dependencies that can affect output.

Each dependency SHOULD include:

```text
name
version
source
compatibility mode
source_fingerprint, if local/editable/path-based
```

Typical `source` values:

```text
package
local-path
editable-install
git
container-image
system-binary
remote-service
unknown
```

If a dependency can affect output and its version cannot be determined, the metadata provider SHOULD return a stable explicit value such as `unknown`, and compatibility SHOULD default to `exact` or force rerun.

---

### `assets`

List of non-code assets that can affect output.

Examples:

```text
models
rules
catalogs
dictionaries
lookup tables
prompts
templates
static data files
normalization tables
```

Each asset MUST include a content hash, usually SHA-256.

Asset hashes SHOULD use `hash_exact` compatibility by default.

---

## Local dependency guideline

A local dependency is any module that is imported or installed from a local path, workspace, editable install, monorepo package, sibling directory, or generated source tree.

For local dependencies, package version is not sufficient because code can change without the version changing.

Therefore, local dependencies MUST provide a source fingerprint.

Recommended order:

```text
1. Use git commit SHA if the dependency is in a git repository.
2. If the working tree is dirty, use git:<commit_sha>-dirty or a tree hash.
3. If git metadata is unavailable, compute tree-sha256 over relevant source files.
4. If generated code is used, include the generator version and generated files in the fingerprint.
5. If local data files affect output, include their content hashes as assets.
```

A local dependency MUST NOT report only:

```json
{
  "name": "some_component",
  "version": "0.1.0"
}
```

It SHOULD report something equivalent to:

```json
{
  "name": "some_component",
  "version": "0.1.0",
  "source": "local-path",
  "source_fingerprint": "tree-sha256:7b2f...",
  "compatibility": "hash_exact"
}
```

---

## Example metadata provider

```python
class ExampleStage:
    stage_name = "example_stage"
    stage_contract_version = "1"
    output_schema_version = "example-output.v1"
    config_contract_version = "example-config.v1"

    def runtime_metadata(self) -> StageRuntimeMetadata:
        return StageRuntimeMetadata(
            stage_name=self.stage_name,
            stage_contract_version=self.stage_contract_version,
            output_schema_version=self.output_schema_version,
            config_contract_version=self.config_contract_version,
            module_version=get_module_version("example-stage"),
            source_fingerprint=get_optional_source_fingerprint(__file__),
            dependencies=[
                RuntimeDependency(
                    name="some-runtime-dependency",
                    version=get_dependency_version("some-runtime-dependency"),
                    source="package",
                    compatibility="exact",
                ),
                RuntimeDependency(
                    name="some-local-component",
                    version=get_module_version("some-local-component"),
                    source="local-path",
                    compatibility="hash_exact",
                    source_fingerprint=get_source_fingerprint_for_local_component(),
                ),
            ],
            assets=[
                RuntimeAsset(
                    name="example-static-data",
                    kind="data-file",
                    sha256=sha256_file("path/to/data.json"),
                    compatibility="hash_exact",
                )
            ],
        )
```

---

## Facade-level aggregation

The orchestrator SHOULD depend on a single facade-level metadata method, not on internal module traversal.

Recommended facade contract:

```python
@dataclass(frozen=True)
class PipelineRuntimeMetadata:
    pipeline_name: str
    pipeline_version: str
    pipeline_contract_version: str
    stages: dict[str, StageRuntimeMetadata]


class PipelineFacade:
    def runtime_metadata(self) -> PipelineRuntimeMetadata:
        return PipelineRuntimeMetadata(
            pipeline_name="example_pipeline",
            pipeline_version=get_module_version("example-pipeline"),
            pipeline_contract_version="1",
            stages={
                stage.stage_name: stage.runtime_metadata()
                for stage in self.stages
            },
        )
```

The orchestrator SHOULD only call:

```python
metadata = pipeline.runtime_metadata()
```

It SHOULD NOT import private stage modules to discover versions.

---

## Stage fingerprint

The orchestrator SHOULD compute a stable fingerprint for every stage.

Recommended input fields:

```text
stage_name
stage_contract_version
output_schema_version
config_contract_version
normalized_stage_config_hash
input_artifact_hashes
module_version
source_fingerprint
dependency names, versions, compatibility modes, and source fingerprints
asset names, kinds, and hashes
pipeline contract version
```

Recommended format:

```text
stage_fingerprint = sha256(canonical_json(fingerprint_payload))
```

The payload MUST be canonicalized before hashing:

```text
sort object keys
sort unordered lists by stable names
normalize paths to relative names
exclude timestamps
exclude absolute paths
exclude secrets
exclude host-specific values
```

---

## Compatibility modes

### `exact`

Current and previous values must be identical.

Use for code dependencies by default.

---

### `hash_exact`

Content hash must be identical.

Use for local source fingerprints, assets, models, catalogs, rules, prompts, templates, and generated files.

---

### `semver_compatible`

Versions may differ only if the compatibility policy explicitly allows it.

Do not assume semantic versioning is safe unless the dependency owner guarantees it.

---

### `schema_compatible`

Schema versions may differ only if the orchestrator has an explicit compatibility matrix or validator.

If no compatibility matrix exists, fallback to `exact`.

---

## Default compatibility policy

Use conservative defaults:

```text
code dependency: exact
local dependency: hash_exact
editable dependency: hash_exact
asset/model/catalog/rule/prompt/template: hash_exact
output schema: exact unless compatibility matrix exists
config contract: exact
stage contract: exact
unknown version: rerun
missing metadata: rerun
```

---

## When to rerun a stage

The stage MUST be rerun if any relevant value changed or cannot be verified.

Examples:

```text
stage contract changed -> rerun stage and downstream stages
output schema changed incompatibly -> rerun stage and downstream stages
normalized config changed -> rerun stage and downstream stages
input artifact hash changed -> rerun stage and downstream stages
local dependency fingerprint changed -> rerun affected stage and downstream stages
asset hash changed -> rerun affected stage and downstream stages
package dependency changed with exact compatibility -> rerun affected stage
metadata missing -> rerun affected stage
artifact hash mismatch -> rerun or fail according to integrity policy
artifact missing -> rerun or fail according to artifact policy
```

The orchestrator SHOULD re-evaluate downstream stages after each rerun because new input artifact hashes may invalidate downstream fingerprints.

---

## When not to rerun a stage

The stage MAY be skipped if a dependency changed but that dependency is not part of the stage metadata and cannot affect the stage output.

Example:

```text
A dependency used only by a downstream stage changed.
Upstream stages whose metadata and input artifacts are unchanged may be reused.
```

This requires accurate per-stage metadata. Do not use one global dependency list for all stages unless full pipeline reruns are acceptable.

---

## Metadata serialization

Runtime metadata SHOULD be serializable to JSON.

The serialized form SHOULD be included in logs, manifests, or database records only if it does not contain secrets or raw sensitive content.

Recommended helper:

```python
import json
from dataclasses import asdict


def canonical_json(value: object) -> str:
    return json.dumps(
        asdict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
```

---

## Source fingerprint helper

A fallback tree hash helper may look like this:

```python
import hashlib
from pathlib import Path


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
        if any(part in ignored_dirs for part in path.parts):
            continue

        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")

    return f"tree-sha256:{digest.hexdigest()}"
```

Use this only as a fallback. Prefer immutable build identifiers or git commit SHAs when available.

---

## Testing requirements

### Test that every stage exposes metadata

```python
def test_all_stages_expose_runtime_metadata(pipeline):
    metadata = pipeline.runtime_metadata()

    assert metadata.stages

    for stage_name, stage_metadata in metadata.stages.items():
        assert stage_metadata.stage_name == stage_name
        assert stage_metadata.stage_contract_version
        assert stage_metadata.output_schema_version
        assert stage_metadata.config_contract_version
        assert stage_metadata.module_version
```

---

### Test local dependencies have source fingerprints

```python
def test_local_dependencies_have_source_fingerprints(pipeline):
    metadata = pipeline.runtime_metadata()

    for stage in metadata.stages.values():
        if stage.source_fingerprint is not None:
            assert stage.source_fingerprint.startswith((
                "git:",
                "tree-sha256:",
                "build:",
            ))

        for dependency in stage.dependencies:
            if dependency.source in {"local-path", "editable-install"}:
                assert dependency.source_fingerprint is not None
                assert dependency.compatibility == "hash_exact"
```

---

### Test metadata is deterministic

```python
def test_runtime_metadata_is_deterministic(pipeline):
    first = canonical_json(pipeline.runtime_metadata())
    second = canonical_json(pipeline.runtime_metadata())

    assert first == second
```

---

### Test fingerprint changes when relevant source changes

For local modules, add at least one test or CI check proving that a source change changes the source fingerprint.

```text
Modify relevant source file in a temporary copy.
Compute fingerprint before and after.
Assert fingerprints differ.
```

---

## LLM-agent implementation checklist

When an LLM agent adds or edits a stage module, it SHOULD complete this checklist:

```text
[ ] Identify whether the module can affect stage output.
[ ] Add or update runtime_metadata().
[ ] Set stable stage_name.
[ ] Set stage_contract_version.
[ ] Set output_schema_version.
[ ] Set config_contract_version.
[ ] Set module_version.
[ ] Add source_fingerprint for local/editable modules.
[ ] List all output-affecting dependencies.
[ ] Add source_fingerprint for local/editable dependencies.
[ ] List all output-affecting assets with SHA-256 hashes.
[ ] Avoid timestamps, absolute paths, secrets, and host-specific values.
[ ] Add or update tests for metadata presence.
[ ] Add or update tests for deterministic serialization.
[ ] Add or update tests for local dependency fingerprints.
[ ] Ensure the orchestrator includes this metadata in stage_fingerprint.
```

---

## Common mistakes

### Mistake: using only package version

Bad:

```json
{
  "name": "example_stage",
  "version": "0.1.0"
}
```

Good:

```json
{
  "stage_name": "example_stage",
  "stage_contract_version": "1",
  "output_schema_version": "example-output.v1",
  "config_contract_version": "example-config.v1",
  "module_version": "0.1.0",
  "source_fingerprint": "tree-sha256:abc...",
  "dependencies": [],
  "assets": []
}
```

---

### Mistake: including absolute paths in fingerprint

Bad:

```text
/home/user/project/module/file.py
```

Good:

```text
module/file.py
```

---

### Mistake: using timestamp as version

Bad:

```text
built_at: 2026-05-05T10:00:00Z
```

Good:

```text
source_fingerprint: git:abc123...
```

---

### Mistake: global dependency invalidates all stages

Bad:

```text
Any dependency changes -> rerun the whole pipeline.
```

Good:

```text
Only stages whose own metadata/fingerprint changed must rerun.
Downstream stages are then re-evaluated based on new input artifacts.
```

---

## Final rule

Every output-affecting pipeline stage MUST expose deterministic runtime metadata.

The metadata MUST include enough information to decide whether previous outputs are compatible with the current runtime.

For local dependencies, metadata MUST include source fingerprints, not just package versions.

The orchestrator MUST use this metadata, together with input artifact hashes and normalized config, to compute a stage fingerprint.

Existing outputs MAY be reused only when the stored fingerprint is compatible with the current fingerprint and all artifact integrity checks pass.

When in doubt, rerun the stage.
