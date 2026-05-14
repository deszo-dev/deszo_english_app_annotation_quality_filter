"""Offline JSON Schema loader and validators for annotation_quality_filter v2.0.

Schemas and registries are shipped as package data under ``_schemas/`` and
``_registry/``. The :data:`SCHEMA_CATALOG` registry maps every public ``$id``
to its local file, so the package never reaches the network during validation.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any, Iterable

import jsonschema
from jsonschema import Draft202012Validator, RefResolver

_SCHEMA_PKG = "annotation_quality_filter._schemas"
_REGISTRY_PKG = "annotation_quality_filter._registry"

_CATALOG_FILE = "schema_catalog.v2.0.json"

OUTPUT_SCHEMA_ID = "https://deszo.local/schema/annotation_quality_filter.v2.0.schema.json"
USER_CONFIG_SCHEMA_ID = "https://deszo.local/schema/annotation_quality_filter_config.v2.0.schema.json"
EFFECTIVE_CONFIG_SCHEMA_ID = (
    "https://deszo.local/schema/annotation_quality_filter_effective_config.v2.0.schema.json"
)
INPUT_SCHEMA_ID = "https://deszo.local/schema/stanza_annotator.v2.0.schema.json"
DIAGNOSTICS_SCHEMA_ID = (
    "https://deszo.local/schema/annotation_quality_filter_diagnostics.v2.0.schema.json"
)


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, dict[str, Any]]:
    raw = json.loads(resources.files(_SCHEMA_PKG).joinpath(_CATALOG_FILE).read_text("utf-8"))
    return {entry["id"]: entry for entry in raw["schemas"]}


@lru_cache(maxsize=None)
def load_schema(schema_id: str) -> dict[str, Any]:
    """Return the JSON Schema body for the given ``$id``."""

    entry = _load_catalog().get(schema_id)
    if entry is None:
        raise KeyError(f"Unknown schema id: {schema_id}")
    # entry["file"] is "docs/architecture/schema/<name>.json"; only the basename is shipped.
    filename = entry["file"].rsplit("/", 1)[-1]
    return json.loads(resources.files(_SCHEMA_PKG).joinpath(filename).read_text("utf-8"))


@lru_cache(maxsize=1)
def _store() -> dict[str, dict[str, Any]]:
    return {schema_id: load_schema(schema_id) for schema_id in _load_catalog()}


@lru_cache(maxsize=None)
def _validator(schema_id: str) -> Draft202012Validator:
    schema = load_schema(schema_id)
    resolver = RefResolver(base_uri=schema_id, referrer=schema, store=_store())
    return Draft202012Validator(schema, resolver=resolver)


def _format_error(err: jsonschema.ValidationError) -> tuple[str, str]:
    path = "/" + "/".join(str(p) for p in err.absolute_path) if err.absolute_path else ""
    return path, err.message


def iter_errors(schema_id: str, payload: Any) -> Iterable[jsonschema.ValidationError]:
    return _validator(schema_id).iter_errors(payload)


def first_error(schema_id: str, payload: Any) -> tuple[str, str] | None:
    """Return ``(json_pointer_path, message)`` for the first validation error, or ``None``."""

    for err in iter_errors(schema_id, payload):
        return _format_error(err)
    return None


def is_valid(schema_id: str, payload: Any) -> bool:
    return first_error(schema_id, payload) is None


# Public convenience wrappers --------------------------------------------------


def validate_user_config(payload: Any) -> tuple[str, str] | None:
    return first_error(USER_CONFIG_SCHEMA_ID, payload)


def validate_effective_config(payload: Any) -> tuple[str, str] | None:
    return first_error(EFFECTIVE_CONFIG_SCHEMA_ID, payload)


def validate_input(payload: Any) -> tuple[str, str] | None:
    return first_error(INPUT_SCHEMA_ID, payload)


def validate_output(payload: Any) -> tuple[str, str] | None:
    return first_error(OUTPUT_SCHEMA_ID, payload)


def load_registry(name: str) -> dict[str, Any]:
    """Load a JSON registry from package data (``_registry/<name>``)."""

    return json.loads(resources.files(_REGISTRY_PKG).joinpath(name).read_text("utf-8"))
