"""Stanza v2.0 EPUB traversal (architecture §2.2, stanza_input_alignment_note).

Order: ``book.front_matter[]`` -> ``book.chapters[]`` -> ``book.back_matter[]``
-> ``book.footnotes[]``. Within each section: ``title_annotation`` ->
``text_annotation`` -> ``footnotes[].annotation``.

Quality refs are canonicalized to Stanza ``TextUnitRef`` kinds
(``chapter_text``, ``section_text``, ``chapter_title``, ``section_title``,
``footnote``). Paragraphs are forbidden in input and are not traversed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class QualityTarget:
    """A text unit to evaluate (or record as not evaluated)."""

    text_unit_id: str
    ref: dict[str, Any]
    evaluation_status: str  # "evaluated" | "not_evaluated"
    annotation: dict[str, Any] | None
    not_evaluated_reason: str | None


_SKIP_TO_REASON = {
    "excluded_by_config": "excluded_by_config",
    "empty_text": "empty_text",
    "too_large": "too_large",
}


def _section_ref(section: dict[str, Any], *, owner_type: str, source_field: str, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "text_unit_id": f"{section.get('id', '')}:{source_field}" if False else None,
    }


def _footnote_ref(footnote: dict[str, Any], owner: dict[str, Any], owner_type: str) -> dict[str, Any]:
    fn_id = footnote.get("id") or ""
    return {
        "kind": "footnote",
        "text_unit_id": fn_id,
        "owner_type": owner_type,
        "owner_id": owner.get("id") or "",
        "source_field": "text",
        "footnote_id": fn_id,
    }


def _annotation_ref(annotation: dict[str, Any]) -> dict[str, Any]:
    return dict(annotation.get("ref") or {})


def _yield_section(
    section: dict[str, Any],
    *,
    owner_type: str,
    title_kind: str,
    text_kind: str,
) -> Iterator[QualityTarget]:
    title_status = section.get("title_annotation_status")
    if title_status == "annotated":
        ann = section.get("title_annotation") or {}
        yield QualityTarget(
            text_unit_id=ann.get("text_unit_id") or "",
            ref=_annotation_ref(ann),
            evaluation_status="evaluated",
            annotation=ann,
            not_evaluated_reason=None,
        )
    elif title_status == "skipped":
        yield QualityTarget(
            text_unit_id=f"{section.get('id', '')}:title",
            ref={
                "kind": title_kind,
                "text_unit_id": f"{section.get('id', '')}:title",
                "owner_type": owner_type,
                "owner_id": section.get("id") or "",
                "source_field": "title",
            },
            evaluation_status="not_evaluated",
            annotation=None,
            not_evaluated_reason=_SKIP_TO_REASON.get(
                section.get("title_skipped_reason") or "", "excluded_by_config"
            ),
        )

    text_status = section.get("text_annotation_status")
    if text_status == "annotated":
        ann = section.get("text_annotation") or {}
        yield QualityTarget(
            text_unit_id=ann.get("text_unit_id") or "",
            ref=_annotation_ref(ann),
            evaluation_status="evaluated",
            annotation=ann,
            not_evaluated_reason=None,
        )
    elif text_status == "skipped":
        yield QualityTarget(
            text_unit_id=f"{section.get('id', '')}:text",
            ref={
                "kind": text_kind,
                "text_unit_id": f"{section.get('id', '')}:text",
                "owner_type": owner_type,
                "owner_id": section.get("id") or "",
                "source_field": "text",
            },
            evaluation_status="not_evaluated",
            annotation=None,
            not_evaluated_reason=_SKIP_TO_REASON.get(
                section.get("text_skipped_reason") or "", "excluded_by_config"
            ),
        )

    for footnote in section.get("footnotes") or []:
        yield from _yield_footnote(footnote, owner=section, owner_type=owner_type)


def _yield_footnote(footnote: dict[str, Any], *, owner: dict[str, Any], owner_type: str) -> Iterator[QualityTarget]:
    status = footnote.get("annotation_status")
    if status == "annotated":
        ann = footnote.get("annotation") or {}
        yield QualityTarget(
            text_unit_id=ann.get("text_unit_id") or footnote.get("id") or "",
            ref=_annotation_ref(ann),
            evaluation_status="evaluated",
            annotation=ann,
            not_evaluated_reason=None,
        )
    elif status == "skipped":
        yield QualityTarget(
            text_unit_id=footnote.get("id") or "",
            ref=_footnote_ref(footnote, owner, owner_type),
            evaluation_status="not_evaluated",
            annotation=None,
            not_evaluated_reason=_SKIP_TO_REASON.get(
                footnote.get("skipped_reason") or "", "excluded_by_config"
            ),
        )


def traverse(input_data: dict[str, Any]) -> list[QualityTarget]:
    """Walk a ``StanzaAnnotationResult`` and produce ordered text-unit targets."""

    document = input_data.get("document") or {}
    book = document.get("book") or {}
    targets: list[QualityTarget] = []

    for section in book.get("front_matter") or []:
        targets.extend(_yield_section(section, owner_type="front_matter", title_kind="section_title", text_kind="section_text"))
    for chapter in book.get("chapters") or []:
        targets.extend(_yield_section(chapter, owner_type="chapter", title_kind="chapter_title", text_kind="chapter_text"))
    for section in book.get("back_matter") or []:
        targets.extend(_yield_section(section, owner_type="back_matter", title_kind="section_title", text_kind="section_text"))
    for fn in book.get("footnotes") or []:
        targets.extend(_yield_footnote(fn, owner=book, owner_type="book"))

    return targets
