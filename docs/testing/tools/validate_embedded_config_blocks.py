#!/usr/bin/env python3
"""Validate embedded annotation_quality_filter config JSON blocks.

The user config schema is partial, so every JSON object that looks like an
AnnotationQuality config override is validated against
annotation_quality_filter_config.v2.0.schema.json. Complete default/effective
config blocks are additionally validated against
annotation_quality_filter_effective_config.v2.0.schema.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover - CI dependency guard
    raise SystemExit("jsonschema is required to run this validation script") from exc

REPO_ROOT = Path(__file__).resolve().parents[3]
TESTING_GUIDE = REPO_ROOT / "docs" / "testing" / "annotation_quality_filter_testing.md"
SCHEMA_DIR = REPO_ROOT / "docs" / "architecture" / "schema"
USER_CONFIG_SCHEMA = SCHEMA_DIR / "annotation_quality_filter_config.v2.0.schema.json"
EFFECTIVE_CONFIG_SCHEMA = SCHEMA_DIR / "annotation_quality_filter_effective_config.v2.0.schema.json"

CONFIG_TOP_LEVEL_KEYS = {
    "thresholds",
    "weights",
    "limits",
    "checks",
    "include_debug",
    "logging",
}

INTENTIONALLY_INVALID_CONFIG_OWNERS = {"UNKNOWN_NEGATIVE_CONFIG_EXAMPLE"}


def iter_json_fences(markdown: str) -> list[tuple[int, str, str]]:
    blocks: list[tuple[int, str, str]] = []
    for match in re.finditer(r"```json\n(.*?)\n```", markdown, flags=re.DOTALL):
        line_number = markdown[: match.start()].count("\n") + 1
        prior = markdown[: match.start()]
        heading_matches = list(
            re.finditer(
                r"^###\s+([A-Za-z0-9_. -]+)|^##\s+([A-Za-z0-9_. -]+)",
                prior,
                flags=re.MULTILINE,
            )
        )
        owner = "UNKNOWN"
        if heading_matches:
            owner = next(group for group in heading_matches[-1].groups() if group)
        blocks.append((line_number, owner, match.group(1)))
    return blocks


def looks_like_config(value: Any) -> bool:
    return isinstance(value, dict) and bool(CONFIG_TOP_LEVEL_KEYS.intersection(value.keys()))


def is_complete_config(value: Any) -> bool:
    return isinstance(value, dict) and CONFIG_TOP_LEVEL_KEYS.issubset(value.keys())


def format_path(err: Any) -> str:
    return "/" + "/".join(str(part) for part in err.path)


def main() -> int:
    markdown = TESTING_GUIDE.read_text(encoding="utf-8")
    user_schema = json.loads(USER_CONFIG_SCHEMA.read_text(encoding="utf-8"))
    effective_schema = json.loads(EFFECTIVE_CONFIG_SCHEMA.read_text(encoding="utf-8"))
    user_validator = Draft202012Validator(user_schema)
    effective_validator = Draft202012Validator(effective_schema)

    failures: list[str] = []
    checked_user = 0
    checked_effective = 0
    skipped_invalid = 0

    for line_number, owner, raw_json in iter_json_fences(markdown):
        try:
            value = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        if not looks_like_config(value):
            continue
        if "unknown_limit" in raw_json:
            skipped_invalid += 1
            continue
        if owner in INTENTIONALLY_INVALID_CONFIG_OWNERS:
            skipped_invalid += 1
            continue
        checked_user += 1
        for err in sorted(user_validator.iter_errors(value), key=lambda err: list(err.path)):
            failures.append(f"line {line_number}: user {format_path(err)}: {err.message}")
        if is_complete_config(value):
            checked_effective += 1
            for err in sorted(effective_validator.iter_errors(value), key=lambda err: list(err.path)):
                failures.append(f"line {line_number}: effective {format_path(err)}: {err.message}")

    if checked_user == 0:
        failures.append("No embedded AnnotationQuality config override blocks were found")
    if checked_effective == 0:
        failures.append("No complete embedded effective AnnotationQualityConfig block was found")

    if failures:
        print("Embedded config validation FAILED", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Embedded config validation OK: "
        f"{checked_user} user override block(s), "
        f"{checked_effective} effective config block(s), "
        f"{skipped_invalid} intentionally invalid block(s) skipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
