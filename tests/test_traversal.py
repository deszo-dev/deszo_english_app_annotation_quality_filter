"""F002 — traversal canonicalizes TextUnitRef.kind per §2.2 / alignment note."""

from __future__ import annotations

from annotation_quality_filter.core.traversal import traverse

from .conftest import EXPECTED, FIXTURES, load_json


def test_f002_text_unit_refs_match_expected() -> None:
    data = load_json(FIXTURES / "F002" / "stanza_annotation.json")
    expected = load_json(EXPECTED / "F002_expected_text_unit_refs.json")
    actual = [t.ref for t in traverse(data)]  # type: ignore[arg-type]
    assert actual == expected
