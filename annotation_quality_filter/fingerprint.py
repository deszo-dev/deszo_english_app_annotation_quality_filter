"""Quality input fingerprint (architecture §8.2).

The fingerprint summarises the quality-relevant projection of the input
``StanzaAnnotationResult``, the effective config (minus debug/logging), and
the runtime version vectors.
"""

from __future__ import annotations

import hashlib
from typing import Any

from . import canonical_json
from .errors import ERROR_REGISTRY_VERSION
from .issues import ISSUE_REGISTRY_VERSION

PROJECTION_CONTRACT_VERSION = "annotation_quality_filter.v2.0"
SUPPORTED_INPUT_SCHEMA_VERSION = "stanza_annotator.v2.0"


def _project_word(word: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "text_unit_id",
        "sentence_id",
        "word_number",
        "text",
        "lemma",
        "upos",
        "xpos",
        "feats",
        "head",
        "head_word_id",
        "deprel",
        "start_char",
        "end_char",
    )
    return {k: word[k] for k in keys if k in word}


def _project_token(token: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "text_unit_id",
        "sentence_id",
        "token_number",
        "text",
        "start_char",
        "end_char",
        "word_ids",
    )
    return {k: token[k] for k in keys if k in token}


def _project_sentence(sentence: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "text_unit_id", "sentence_number", "text", "start_char", "end_char")
    out = {k: sentence[k] for k in keys if k in sentence}
    out["tokens"] = [_project_token(t) for t in sentence.get("tokens", [])]
    out["words"] = [_project_word(w) for w in sentence.get("words", [])]
    return out


def _project_entity(entity: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "text_unit_id",
        "entity_number",
        "text",
        "type",
        "start_char",
        "end_char",
    )
    return {k: entity[k] for k in keys if k in entity}


def _project_annotation(annotation: dict[str, Any]) -> dict[str, Any]:
    return {
        "text_unit_id": annotation.get("text_unit_id"),
        "ref": annotation.get("ref"),
        "text": annotation.get("text"),
        "sentences": [_project_sentence(s) for s in annotation.get("sentences", [])],
        "entities": [_project_entity(e) for e in annotation.get("entities", [])],
        "summary": annotation.get("summary"),
    }


def _project_text_units(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    document = input_data.get("document")
    if not isinstance(document, dict):
        return []
    book = document.get("book")
    if not isinstance(book, dict):
        return []

    projections: list[dict[str, Any]] = []

    def visit_section(section: dict[str, Any], *, footnote_owner: str | None = None) -> None:
        if section.get("title_annotation_status") == "annotated":
            ann = section.get("title_annotation")
            if isinstance(ann, dict):
                projections.append({"role": "title", "annotation": _project_annotation(ann)})
        elif section.get("title_annotation_status") == "skipped":
            projections.append(
                {
                    "role": "title",
                    "skipped": {
                        "owner_id": section.get("id"),
                        "reason": section.get("title_skipped_reason"),
                    },
                }
            )
        if section.get("text_annotation_status") == "annotated":
            ann = section.get("text_annotation")
            if isinstance(ann, dict):
                projections.append({"role": "text", "annotation": _project_annotation(ann)})
        elif section.get("text_annotation_status") == "skipped":
            projections.append(
                {
                    "role": "text",
                    "skipped": {
                        "owner_id": section.get("id"),
                        "reason": section.get("text_skipped_reason"),
                    },
                }
            )
        for fn in section.get("footnotes", []) or []:
            visit_footnote(fn)

    def visit_footnote(footnote: dict[str, Any]) -> None:
        if footnote.get("annotation_status") == "annotated":
            ann = footnote.get("annotation")
            if isinstance(ann, dict):
                projections.append({"role": "footnote", "annotation": _project_annotation(ann)})
        elif footnote.get("annotation_status") == "skipped":
            projections.append(
                {
                    "role": "footnote",
                    "skipped": {
                        "owner_id": footnote.get("id"),
                        "reason": footnote.get("skipped_reason"),
                    },
                }
            )

    for section in book.get("front_matter") or []:
        visit_section(section)
    for chapter in book.get("chapters") or []:
        visit_section(chapter)
    for section in book.get("back_matter") or []:
        visit_section(section)
    for fn in book.get("footnotes") or []:
        visit_footnote(fn)
    return projections


def _project_annotation_run(input_data: dict[str, Any]) -> dict[str, Any]:
    annotation = input_data.get("annotation") or {}
    keys = (
        "annotator_version",
        "stanza_version",
        "source_book_fingerprint",
        "annotation_input_fingerprint",
        "summary",
    )
    return {k: annotation[k] for k in keys if k in annotation}


def _effective_config_without_debug_and_logging(cfg: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in cfg.items() if k not in ("include_debug", "logging")}


def compute_quality_input_fingerprint(
    input_data: dict[str, Any],
    *,
    effective_config: dict[str, Any],
    module_version: str,
    checker_versions: dict[str, str],
) -> str:
    """Build the deterministic ``quality_input_fingerprint`` (architecture §8.2)."""

    view = {
        "schema_version": input_data.get("schema_version"),
        "status": input_data.get("status"),
        "annotation": _project_annotation_run(input_data),
        "text_units": _project_text_units(input_data),
    }
    payload = {
        "supported_input_schema_version": SUPPORTED_INPUT_SCHEMA_VERSION,
        "stanza_quality_relevant_view": view,
        "effective_config_without_debug_and_logging": _effective_config_without_debug_and_logging(
            effective_config
        ),
        "module_version": module_version,
        "checker_versions": dict(sorted(checker_versions.items())),
        "issue_registry_version": ISSUE_REGISTRY_VERSION,
        "error_registry_version": ERROR_REGISTRY_VERSION,
        "projection_contract_version": PROJECTION_CONTRACT_VERSION,
    }
    digest = hashlib.sha256(canonical_json.encode(payload)).hexdigest()
    return f"sha256:{digest}"
