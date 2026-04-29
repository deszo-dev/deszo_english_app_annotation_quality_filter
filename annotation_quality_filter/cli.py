from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from .evaluator import AnnotationQualityFilter
from .models import (
    AnnotationQualityConfig,
    AnnotationQualityError,
    RetentionPolicy,
)

LOGGER = logging.getLogger("annotation_quality_filter")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="annotation-quality-filter",
        description="Filter Stanza-compatible AnnotatedDocument payloads by annotation quality.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Read AnnotatedDocument JSON from this file. Defaults to stdin.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write primary filtered AnnotatedDocument JSON to this file. Defaults to stdout.",
    )
    parser.add_argument(
        "--status-output",
        type=Path,
        help="Write AnnotationQualityDocumentStatus JSON to this file.",
    )
    parser.add_argument(
        "--retention-policy",
        choices=["ACCEPT_AND_WEAK_ACCEPT", "ACCEPT_ONLY"],
        default="ACCEPT_AND_WEAK_ACCEPT",
        help="Policy for retaining sentences in the primary filtered document.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug logging without changing the result payload.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON outputs.",
    )
    args = parser.parse_args(argv)

    configure_logging(debug=args.debug)

    try:
        LOGGER.info("pipeline.start")
        document = load_json(args.input)
        config = AnnotationQualityConfig(
            retention_policy=args.retention_policy,
            debug=args.debug,
        )
        output = AnnotationQualityFilter(config).filter_with_status(document)
        LOGGER.info(
            "pipeline.end input_sentences=%s output_sentences=%s",
            output.status.summary.total_input_sentences,
            output.status.summary.total_output_sentences,
        )
    except (json.JSONDecodeError, AnnotationQualityError) as exc:
        LOGGER.error("expected_error: %s", exc)
        return 1
    except Exception:
        LOGGER.error("system_error")
        if args.debug:
            LOGGER.exception("system_error_details")
        return 2

    indent = 2 if args.pretty else None
    document_body = json.dumps(output.document, ensure_ascii=False, indent=indent)
    status_body = json.dumps(output.status.to_dict(), ensure_ascii=False, indent=indent)

    try:
        write_success_outputs(
            output_path=args.output,
            document_body=document_body,
            status_path=args.status_output,
            status_body=status_body,
        )
    except OSError:
        LOGGER.error("system_error")
        if args.debug:
            LOGGER.exception("failed_to_write_output")
        return 2

    return 0


def configure_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
        stream=sys.stderr,
    )


def load_json(path: Path | None) -> Any:
    if path is None:
        return json.loads(sys.stdin.read())
    return json.loads(path.read_text(encoding="utf-8"))


def write_success_outputs(
    output_path: Path | None,
    document_body: str,
    status_path: Path | None,
    status_body: str,
) -> None:
    prepared_files: list[tuple[Path, Path]] = []
    for path, body in [(output_path, document_body), (status_path, status_body)]:
        if path is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_text(body + "\n", encoding="utf-8")
        prepared_files.append((tmp_path, path))

    for tmp_path, final_path in prepared_files:
        tmp_path.replace(final_path)

    if output_path is None:
        sys.stdout.write(document_body + "\n")
