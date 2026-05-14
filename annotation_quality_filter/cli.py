"""CLI for annotation_quality_filter v2.0 (architecture §7).

Canonical command::

    annotation-quality-filter evaluate INPUT.json [options]

Exit codes follow the architecture and error registry:

* ``0`` success;
* ``1`` failed result other than invalid config / output write;
* ``2`` CLI usage error (no JSON result);
* ``3`` output write failure;
* ``4`` invalid config;
* ``99`` internal error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .errors import exit_code_for
from .pipeline import _failed_result, evaluate_stanza_result
from .runtime_metadata import MODULE_NAME, MODULE_VERSION


class _UsageError(Exception):
    pass


class _WriteError(Exception):
    pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="annotation-quality-filter",
        description="Annotate Stanza v2.0 results with quality metadata.",
    )
    parser.add_argument("--version", action="version", version=f"{MODULE_NAME} {MODULE_VERSION}")

    sub = parser.add_subparsers(dest="command")
    evaluate = sub.add_parser("evaluate", help="Evaluate a StanzaAnnotationResult JSON file.")
    evaluate.add_argument("input", help="Path to input JSON, or '-' for stdin.")
    evaluate.add_argument("--output", help="Write full result to PATH instead of stdout.")
    evaluate.add_argument("--quality-output", help="Write quality sidecar to PATH (success only).")
    evaluate.add_argument("--config", help="Path to user config JSON, or '-' for stdin.")
    evaluate.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    evaluate.add_argument("--include-debug", action="store_true", help="Include debug payload.")
    evaluate.add_argument("--debug-dir", help="Directory for CLI debug artefacts (not in config).")
    return parser


def _read_text(spec: str, *, allow_stdin: bool) -> tuple[str, bool]:
    if spec == "-":
        if not allow_stdin:
            raise _UsageError("Cannot read both input and config from stdin.")
        return sys.stdin.read(), True
    path = Path(spec)
    if not path.is_file():
        raise _UsageError(f"Input not found: {spec}")
    return path.read_text(encoding="utf-8"), False


def _atomic_write(path: Path, body: str) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise _WriteError(f"Parent directory does not exist: {parent}")
    if path.is_dir():
        raise _WriteError(f"Output path is a directory: {path}")
    if path.is_symlink():
        raise _WriteError(f"Output path is a symlink: {path}")
    tmp = parent / f".{path.name}.tmp"
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except (OSError, AttributeError):  # pragma: no cover - platform dependent
                pass
        if path.is_symlink():
            raise _WriteError(f"Output path became a symlink: {path}")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:  # pragma: no cover - best-effort cleanup
                pass


def _serialize(payload: Any, *, pretty: bool) -> str:
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _emit(result: dict[str, Any], *, output: str | None, pretty: bool) -> int:
    body = _serialize(result, pretty=pretty)
    if output:
        try:
            _atomic_write(Path(output), body)
        except _WriteError as err:
            print(f"output_write_failed: {err}", file=sys.stderr)
            return exit_code_for("output_write_failed")
    else:
        sys.stdout.write(body)
        if not body.endswith("\n"):
            sys.stdout.write("\n")
    if result["status"] == "failed":
        return exit_code_for(result["error"]["code"])
    return 0


def _emit_quality_sidecar(result: dict[str, Any], path: str, *, pretty: bool) -> int | None:
    if result["status"] != "succeeded":
        return None
    body = _serialize(result["quality"], pretty=pretty)
    try:
        _atomic_write(Path(path), body)
    except _WriteError as err:
        print(f"output_write_failed: {err}", file=sys.stderr)
        return exit_code_for("output_write_failed")
    return None


def _user_config_limit(user_config: dict[str, Any] | None) -> int:
    from .models import DEFAULT_CONFIG

    if user_config and isinstance(user_config.get("limits"), dict):
        limit = user_config["limits"].get("max_output_json_bytes")
        if isinstance(limit, int) and limit > 0:
            return limit
    return int(DEFAULT_CONFIG["limits"]["max_output_json_bytes"])


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "evaluate":
        parser.print_help(sys.stderr)
        return 2

    try:
        input_text, input_is_stdin = _read_text(args.input, allow_stdin=True)
    except _UsageError as err:
        print(str(err), file=sys.stderr)
        return 2

    user_config: dict[str, Any] | None = None
    if args.config:
        try:
            config_text, _ = _read_text(args.config, allow_stdin=not input_is_stdin)
        except _UsageError as err:
            print(str(err), file=sys.stderr)
            return 2
        try:
            user_config = json.loads(config_text)
        except json.JSONDecodeError as err:
            result = _failed_result(
                error_code="invalid_config",
                message=f"Config JSON parse failed: {err.msg}.",
                helper_code="config_schema_validation_failed",
                helper_path="",
            )
            return _emit(result, output=args.output, pretty=args.pretty)

    try:
        input_data = json.loads(input_text)
    except json.JSONDecodeError:
        result = _failed_result(
            error_code="invalid_input",
            message="Input JSON could not be parsed.",
            helper_code="input_json_parse_failed",
            helper_path="",
        )
        return _emit(result, output=args.output, pretty=args.pretty)

    try:
        result = evaluate_stanza_result(
            input_data,
            user_config=user_config,
            include_debug=args.include_debug,
        )
    except Exception as err:  # pragma: no cover - safety net
        result = _failed_result(
            error_code="internal_error",
            message=f"Unexpected error: {err}",
            helper_code="unexpected_internal_error",
            helper_path="",
        )
        return _emit(result, output=args.output, pretty=args.pretty)

    # Output-size limit (architecture §5.4 / O001) — measured on actual emitted bytes
    if result["status"] == "succeeded":
        body_bytes = _serialize(result, pretty=args.pretty).encode("utf-8")
        limit = _user_config_limit(user_config)
        if len(body_bytes) > limit:
            result = _failed_result(
                error_code="output_too_large",
                message="Serialized output exceeds max_output_json_bytes.",
                helper_code="output_serialization_too_large",
                helper_path="/limits/max_output_json_bytes",
            )

    exit_code = _emit(result, output=args.output, pretty=args.pretty)

    if result["status"] == "succeeded" and args.quality_output:
        write_err = _emit_quality_sidecar(result, args.quality_output, pretty=args.pretty)
        if write_err is not None:
            return write_err

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
