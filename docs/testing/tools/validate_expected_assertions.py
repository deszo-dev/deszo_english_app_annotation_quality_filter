#!/usr/bin/env python3
"""Validate and optionally apply annotation_quality_filter expected assertion artifacts.

Without arguments, this is a release-gate documentation check:
- validates every expected assertion artifact against its JSON Schema;
- validates the non-registry contract-test manifest;
- requires every P0/P1 quality_issue manifest entry to have exact expected_quality_assertions.

With --expected and --actual, it can be used by generated tests to verify exact
issue location, score, band, risk, warning/error counts, and summary fields.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover
    raise SystemExit("jsonschema is required to run this validation script") from exc

ROOT = pathlib.Path(__file__).resolve().parents[3]
SCHEMA_DIR = ROOT / "docs" / "architecture" / "schema"
ASSERTION_SCHEMA = SCHEMA_DIR / "annotation_quality_filter_expected_assertions.v2.0.schema.json"
CONTRACT_MANIFEST_SCHEMA = SCHEMA_DIR / "annotation_quality_filter_contract_test_manifest.v2.0.schema.json"
EXPECTED_DIR = ROOT / "docs" / "testing" / "expected_assertions"
TEST_MANIFEST = ROOT / "docs" / "testing" / "test_manifest.v2.0.json"
CONTRACT_MANIFEST = ROOT / "docs" / "testing" / "contract_test_manifest.v2.0.json"


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def format_path(error: Any) -> str:
    return "/" + "/".join(str(part) for part in error.path)


def validate_json(schema_path: pathlib.Path, instance_path: pathlib.Path) -> list[str]:
    schema = load(schema_path)
    instance = load(instance_path)
    validator = Draft202012Validator(schema)
    return [f"{instance_path.relative_to(ROOT)} {format_path(err)}: {err.message}" for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.path))]


def issue_codes_from_actual(actual: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            code = value.get("code")
            if isinstance(code, str):
                codes.add(code)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(actual)
    return codes


def find_text_unit(actual: dict[str, Any], text_unit_id: str | None) -> dict[str, Any] | None:
    if text_unit_id is None:
        return None
    for text_unit in actual.get("quality", {}).get("text_units", []):
        if text_unit.get("text_unit_id") == text_unit_id:
            return text_unit
    return None


def find_scoped_quality(actual: dict[str, Any], assertion: dict[str, Any]) -> dict[str, Any] | None:
    scope = assertion["scope"]
    text_unit = find_text_unit(actual, assertion.get("text_unit_id"))
    if scope == "document":
        return actual.get("quality", {})
    if text_unit is None:
        return None
    if scope == "text_unit":
        return text_unit
    if scope == "sentence":
        sid = assertion.get("sentence_id")
        for sentence in text_unit.get("sentence_quality", []):
            if sentence.get("sentence_id") == sid:
                return sentence
    if scope == "entity":
        eid = assertion.get("entity_id")
        for entity in text_unit.get("entity_quality", []):
            if entity.get("entity_id") == eid:
                return entity
    return None


def severity_counts(issues: list[dict[str, Any]]) -> tuple[int, int]:
    warnings = sum(1 for issue in issues if issue.get("severity") == "warning")
    errors = sum(1 for issue in issues if issue.get("severity") == "error")
    return warnings, errors


def get_summary_value(actual: dict[str, Any], assertion: dict[str, Any], dotted_path: str) -> Any:
    if dotted_path.startswith("quality.summary."):
        value: Any = actual.get("quality", {}).get("summary", {})
        rest = dotted_path.removeprefix("quality.summary.").split(".")
    elif dotted_path.startswith("text_unit.summary."):
        text_unit = find_text_unit(actual, assertion.get("text_unit_id")) or {}
        value = text_unit.get("summary", {})
        rest = dotted_path.removeprefix("text_unit.summary.").split(".")
    else:
        raise KeyError(f"Unsupported summary assertion path: {dotted_path}")
    for part in rest:
        value = value[part]
    return value


def apply_expected_assertions(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if expected.get("expected_error_code") is not None:
        got_error = actual.get("error", {}).get("code")
        if got_error != expected["expected_error_code"]:
            failures.append(f"error.code expected {expected['expected_error_code']!r}, got {got_error!r}")
    actual_codes = issue_codes_from_actual(actual)
    for code in expected.get("expected_codes", []):
        if code not in actual_codes:
            failures.append(f"expected code {code!r} not found in actual output")
    for code in expected.get("expected_absent_codes", []):
        if code in actual_codes:
            failures.append(f"absent code {code!r} was found in actual output")
    for qa in expected.get("expected_quality_assertions", []):
        scoped = find_scoped_quality(actual, qa)
        if scoped is None:
            failures.append(f"missing scoped quality object for {qa.get('scope')} {qa.get('sentence_id') or qa.get('entity_id') or qa.get('text_unit_id')}")
            continue
        issues = scoped.get("issues", [])
        got_issue_codes = [issue.get("code") for issue in issues]
        if got_issue_codes != qa.get("expected_issue_codes", []):
            failures.append(f"{qa.get('scope')} issues expected {qa.get('expected_issue_codes')}, got {got_issue_codes}")
        for field in ["score", "band", "risk_level"]:
            exp_key = f"expected_{field}"
            if exp_key in qa and qa[exp_key] is not None:
                got = scoped.get(field)
                if got != qa[exp_key]:
                    failures.append(f"{qa.get('scope')} {field} expected {qa[exp_key]!r}, got {got!r}")
        warnings, errors = severity_counts(issues)
        if warnings != qa.get("expected_warning_count"):
            failures.append(f"warning_count expected {qa.get('expected_warning_count')}, got {warnings}")
        if errors != qa.get("expected_error_count"):
            failures.append(f"error_count expected {qa.get('expected_error_count')}, got {errors}")
        for issue_exp in qa.get("expected_issue_entities", []):
            matches = [issue for issue in issues if issue.get("code") == issue_exp["code"]]
            if not matches:
                failures.append(f"missing issue entity assertion code {issue_exp['code']}")
                continue
            issue = matches[0]
            for key in ["entity_type", "entity_id", "field", "path"]:
                if key in issue_exp and issue_exp[key] is not None and issue.get(key) != issue_exp[key]:
                    failures.append(f"issue {issue_exp['code']} {key} expected {issue_exp[key]!r}, got {issue.get(key)!r}")
        for path, exp_value in qa.get("expected_summary_assertions", {}).items():
            got = get_summary_value(actual, qa, path)
            if got != exp_value:
                failures.append(f"summary {path} expected {exp_value!r}, got {got!r}")
    return failures


def documentation_gate() -> int:
    failures: list[str] = []
    for assertion_path in sorted(EXPECTED_DIR.glob("*.json")):
        failures.extend(validate_json(ASSERTION_SCHEMA, assertion_path))
    failures.extend(validate_json(CONTRACT_MANIFEST_SCHEMA, CONTRACT_MANIFEST))

    manifest = load(TEST_MANIFEST)
    for test in manifest["tests"]:
        if test.get("area") == "quality_issue" and test.get("priority") in {"P0", "P1"}:
            assertion_path = ROOT / test["expected_result"]
            assertion = load(assertion_path)
            qa = assertion.get("expected_quality_assertions", [])
            if not qa:
                failures.append(f"{test['id']} P0/P1 quality_issue lacks expected_quality_assertions")
            for item in qa:
                required_exact = ["scope", "text_unit_id", "expected_issue_codes", "expected_score", "expected_band", "expected_warning_count", "expected_error_count", "expected_summary_assertions"]
                missing = [key for key in required_exact if key not in item]
                if missing:
                    failures.append(f"{test['id']} quality assertion missing exact fields: {missing}")
    contract = load(CONTRACT_MANIFEST)
    ids = [test["id"] for test in contract["tests"]]
    if len(ids) != len(set(ids)):
        failures.append("duplicate CT-* ids in contract_test_manifest.v2.0.json")
    for test in contract["tests"]:
        exp = test["expected_result"]
        if exp.startswith("docs/") and not (ROOT / exp).exists():
            failures.append(f"{test['id']} expected_result missing path {exp}")
        for key in ["input_fixture_or_inline", "config_fixture_or_inline"]:
            value = test.get(key, "")
            if isinstance(value, str) and value.startswith("docs/") and not (ROOT / value).exists():
                failures.append(f"{test['id']} {key} missing path {value}")
    if failures:
        for failure in failures:
            print("ERROR:", failure, file=sys.stderr)
        return 1
    print("expected assertion validation: OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=pathlib.Path)
    parser.add_argument("--actual", type=pathlib.Path)
    args = parser.parse_args()
    if args.expected or args.actual:
        if not (args.expected and args.actual):
            parser.error("--expected and --actual must be supplied together")
        failures = validate_json(ASSERTION_SCHEMA, args.expected)
        if failures:
            for failure in failures:
                print("ERROR:", failure, file=sys.stderr)
            return 1
        failures = apply_expected_assertions(load(args.expected), load(args.actual))
        if failures:
            for failure in failures:
                print("ERROR:", failure, file=sys.stderr)
            return 1
        print("actual output matches expected assertion artifact")
        return 0
    return documentation_gate()


if __name__ == "__main__":
    raise SystemExit(main())
