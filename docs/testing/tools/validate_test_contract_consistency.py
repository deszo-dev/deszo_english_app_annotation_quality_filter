#!/usr/bin/env python3
"""Validate pre-production test manifest consistency for annotation_quality_filter docs."""
from __future__ import annotations
import json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs"
MANIFEST = DOCS / "testing" / "test_manifest.v2.0.json"
CONTRACT_MANIFEST = DOCS / "testing" / "contract_test_manifest.v2.0.json"
ERR_REG = DOCS / "architecture" / "registry" / "annotation_quality_filter_error_registry.v2.0.json"
ISSUE_REG = DOCS / "architecture" / "registry" / "annotation_quality_filter_issue_registry.v2.0.json"
GUIDE = DOCS / "testing" / "annotation_quality_filter_testing.md"
FORBIDDEN = ["delta assertions", "inline complete", "failed result with", "CLI exit 3", "inline malformed", "below compact result size"]
def load(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8"))
def iter_entries(reg):
    for key in ("codes", "errors", "diagnostic_helpers"):
        for e in reg.get(key, []):
            yield e
def codes_from_output(obj):
    codes=set()
    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("code"), str): codes.add(x["code"])
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(obj); return codes
def main() -> int:
    errors=[]
    manifest=load(MANIFEST)
    tests=manifest["tests"]
    contract=load(CONTRACT_MANIFEST)
    contract_tests=contract["tests"]
    ids=[t["id"] for t in tests]
    if len(ids)!=len(set(ids)):
        errors.append(f"duplicate manifest ids: {sorted({x for x in ids if ids.count(x)>1})}")
    by_id={t["id"]:t for t in tests}
    contract_ids=[t["id"] for t in contract_tests]
    if len(contract_ids)!=len(set(contract_ids)):
        errors.append(f"duplicate contract manifest ids: {sorted({x for x in contract_ids if contract_ids.count(x)>1})}")
    guide=GUIDE.read_text(encoding="utf-8")
    md_headings=re.findall(r"^#{1,6}\s+(TC-[A-Za-z0-9_-]+)\b", guide, flags=re.M)
    for h in md_headings:
        if h not in by_id:
            errors.append(f"Markdown heading defines TC id not in manifest: {h}")
    for reg_path in [ERR_REG, ISSUE_REG]:
        for entry in iter_entries(load(reg_path)):
            for tid in entry.get("tests", []):
                if tid not in by_id:
                    errors.append(f"registry {reg_path.name} references missing test id {tid}")
    for t in tests + contract_tests:
        for key in ["input_fixture_or_inline", "config_fixture_or_inline", "expected_result"]:
            val=t.get(key, "")
            if isinstance(val,str) and val.startswith("docs/") and not (ROOT/val).exists():
                errors.append(f"{t['id']} {key} missing path {val}")
        if t.get("priority") in {"P0", "P1"}:
            vals="\n".join(str(t.get(k,"")) for k in ["input_fixture_or_inline", "config_fixture_or_inline", "expected_result"])
            for bad in FORBIDDEN:
                if bad in vals:
                    errors.append(f"{t['id']} contains forbidden placeholder phrase: {bad}")
        exp=t.get("expected_result", "")
        expected=set(t.get("expected_diagnostics_or_issues", []))
        if t.get("area")=="quality_issue" and t.get("priority") in {"P0","P1"} and isinstance(exp,str) and "expected_assertions" in exp and (ROOT/exp).exists():
            assertion=load(ROOT/exp)
            if not assertion.get("expected_quality_assertions"):
                errors.append(f"{t['id']} lacks exact expected_quality_assertions")
        if isinstance(exp,str) and exp.startswith("docs/") and (ROOT/exp).exists():
            if exp.endswith(".normalized.json"):
                got=codes_from_output(load(ROOT/exp))
            elif "expected_assertions" in exp:
                got=set(load(ROOT/exp).get("expected_codes", []))
            else:
                got=set()
            missing=expected-got
            if missing:
                errors.append(f"{t['id']} expected codes {sorted(missing)} absent from {exp}; available={sorted(got)}")
    if errors:
        for e in errors: print("ERROR:", e, file=sys.stderr)
        return 1
    print("test contract consistency: OK")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
