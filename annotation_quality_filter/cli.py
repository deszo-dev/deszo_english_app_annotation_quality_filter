from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .evaluator import AnnotationQualityFilter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="annotation-quality-filter",
        description="Evaluate quality of Stanza/UD-like sentence annotations.",
    )
    parser.add_argument("input", type=Path, help="Path to a JSON annotations file.")
    parser.add_argument("-o", "--output", type=Path, help="Write results to this JSON file.")
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Write one result object per line instead of a single JSON document.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Evaluate only the first N sentences.",
    )
    args = parser.parse_args(argv)

    try:
        payload = load_json(args.input)
        sentences = extract_sentences(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"annotation-quality-filter: {exc}", file=sys.stderr)
        return 2

    if args.limit is not None:
        sentences = sentences[: max(args.limit, 0)]

    evaluator = AnnotationQualityFilter()
    results = [
        {
            "index": index,
            "text": sentence.get("text", ""),
            **evaluator.evaluate(sentence).to_dict(),
        }
        for index, sentence in enumerate(sentences)
    ]

    if args.jsonl:
        body = "\n".join(json.dumps(result, ensure_ascii=False) for result in results)
    else:
        body = json.dumps(
            {
                "summary": summarize(results),
                "results": results,
            },
            ensure_ascii=False,
            indent=2 if args.pretty else None,
        )

    if args.output:
        args.output.write_text(body + "\n", encoding="utf-8")
    else:
        print(body)

    return 0


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_sentences(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("sentences"), list):
        return [sentence for sentence in payload["sentences"] if isinstance(sentence, dict)]
    if isinstance(payload, dict) and ("words" in payload or "tokens" in payload):
        return [payload]
    if isinstance(payload, list):
        return [sentence for sentence in payload if isinstance(sentence, dict)]
    raise ValueError("input must be a sentence object, a list of sentences, or an object with 'sentences'")


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(result["label"] for result in results)
    issue_counts = Counter(issue for result in results for issue in result["reasons"])
    average_score = (
        round(sum(float(result["score"]) for result in results) / len(results), 4)
        if results
        else 0.0
    )
    return {
        "total": len(results),
        "average_score": average_score,
        "labels": dict(labels),
        "issue_counts": dict(issue_counts),
    }

