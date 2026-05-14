"""CLI exit-code and side-effect tests (architecture §7)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from annotation_quality_filter.cli import main
from annotation_quality_filter.errors import exit_code_for

from .conftest import FIXTURES


def _run(argv: list[str], stdin_text: str | None = None, capsys: Any = None) -> int:
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        return main(argv)
    finally:
        sys.stdin = sys.__stdin__


def test_cli_version_exit_0(capsys: Any) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "annotation_quality_filter" in out
    assert "2.0.0" in out


def test_cli_usage_error_exit_2(capsys: Any) -> None:
    # No subcommand.
    rc = main([])
    assert rc == 2


def test_cli_evaluate_success_stdout(tmp_path: Path, capsys: Any) -> None:
    fixture = FIXTURES / "F001" / "stanza_annotation.json"
    rc = main(["evaluate", str(fixture)])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["status"] == "succeeded"


def test_cli_evaluate_upstream_failed_exit_1(capsys: Any) -> None:
    fixture = FIXTURES / "F003" / "stanza_annotation.json"
    rc = main(["evaluate", str(fixture)])
    assert rc == exit_code_for("upstream_stanza_annotation_failed")  # 1
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["error"]["code"] == "upstream_stanza_annotation_failed"


def test_cli_evaluate_unsupported_schema_exit_1(capsys: Any) -> None:
    fixture = FIXTURES / "F004" / "stanza_annotation.json"
    rc = main(["evaluate", str(fixture)])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "unsupported_stanza_schema"


def test_cli_evaluate_invalid_json_exit_1(tmp_path: Path, capsys: Any) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    rc = main(["evaluate", str(bad)])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "invalid_input"
    assert payload["diagnostics"][0]["code"] == "input_json_parse_failed"


def test_cli_evaluate_missing_file_exit_2(capsys: Any) -> None:
    rc = main(["evaluate", "no_such_file_zzz.json"])
    assert rc == 2


def test_cli_evaluate_invalid_config_exit_4(tmp_path: Path, capsys: Any) -> None:
    fixture = FIXTURES / "F001" / "stanza_annotation.json"
    cfg = FIXTURES / "C001" / "quality_config.json"
    rc = main(["evaluate", str(fixture), "--config", str(cfg)])
    assert rc == 4
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "invalid_config"


def test_cli_evaluate_writes_output_file(tmp_path: Path, capsys: Any) -> None:
    fixture = FIXTURES / "F001" / "stanza_annotation.json"
    out = tmp_path / "out.json"
    rc = main(["evaluate", str(fixture), "--output", str(out)])
    assert rc == 0
    assert capsys.readouterr().out == ""
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "succeeded"


def test_cli_evaluate_quality_output_success_only(tmp_path: Path, capsys: Any) -> None:
    fixture = FIXTURES / "F001" / "stanza_annotation.json"
    main_out = tmp_path / "out.json"
    qout = tmp_path / "q.json"
    rc = main([
        "evaluate",
        str(fixture),
        "--output",
        str(main_out),
        "--quality-output",
        str(qout),
    ])
    assert rc == 0
    quality = json.loads(qout.read_text(encoding="utf-8"))
    assert "text_units" in quality
    assert quality["config_version"] == "annotation_quality_filter_config.v2.0"


def test_cli_quality_output_not_written_on_failure(tmp_path: Path, capsys: Any) -> None:
    fixture = FIXTURES / "F003" / "stanza_annotation.json"
    qout = tmp_path / "should_not_exist.json"
    rc = main(["evaluate", str(fixture), "--quality-output", str(qout)])
    assert rc == 1
    assert not qout.exists()
