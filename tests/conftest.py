"""Shared test fixtures: locate the docs/testing directory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs" / "testing"
FIXTURES = DOCS / "fixtures"
EXPECTED = DOCS / "expected"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def expected_dir() -> Path:
    return EXPECTED


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))
