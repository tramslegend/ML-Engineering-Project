"""
M4: triage classification accuracy (§10.2).

IMPORTANT SCOPE NOTE: this scores whichever InferenceClient you pass it
against the corpus's category/severity labels. Those labels come from the
synthetic corpus generator (generate_corpus.py), NOT from a human analyst
baseline — M4 explicitly wants accuracy "within 5pp of human baseline,"
which requires a real hand-labelled eval set and a human-triaged comparison
set that don't exist yet. Run against MockInferenceClient (the default),
this script only proves the scoring pipeline works end to end; it says
nothing about real model quality. Point it at OllamaCompatibleClient with a
live SEA-LION/Sahabat-AI/Qwen3/Phi-4-mini endpoint (Phase 2, §10.2) to get a
number that means anything, and get real human labels before trusting M4
against that number.

Usage: python score_triage.py ../corpus/complaints.jsonl [--mock]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.inference.client import MockInferenceClient, get_local_inference_client
from app.core.pii import detect_all
from app.core.vault.pseudonymize import pseudonymize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_path")
    parser.add_argument("--mock", action="store_true", default=True,
                         help="use MockInferenceClient (default; see module docstring)")
    parser.add_argument("--live", action="store_true",
                         help="use a live OllamaCompatibleClient instead of the mock")
    args = parser.parse_args()

    client = get_local_inference_client(use_mock=not args.live)

    with open(args.corpus_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    category_correct = 0
    severity_correct = 0
    confusion: dict[tuple[str, str], int] = defaultdict(int)
    errors = []

    for record in records:
        try:
            detection = detect_all(record["text"])
            pseudo = pseudonymize(record["text"], detection, job_id=f"eval_{record['id']}")
            triage = client.classify(pseudo.tokenized_text)
        except Exception as exc:  # noqa: BLE001 - count as a miss, keep scoring the rest
            errors.append({"id": record["id"], "error": str(exc)})
            continue

        if triage.category == record["category"]:
            category_correct += 1
        if triage.severity.value == record["severity"]:
            severity_correct += 1
        confusion[(record["severity"], triage.severity.value)] += 1

    n = len(records) - len(errors)
    print(f"Corpus: {args.corpus_path} ({len(records)} records, {len(errors)} error(s))")
    print(f"Model: {'mock (heuristic baseline)' if not args.live else 'live local endpoint'}")
    print(f"\nCategory accuracy: {category_correct/n:.4f}" if n else "no scoreable records")
    print(f"Severity accuracy: {severity_correct/n:.4f}" if n else "")
    print("\nSeverity confusion (gold -> predicted):")
    for (gold, pred), count in sorted(confusion.items()):
        marker = "" if gold == pred else "  <-- mismatch"
        print(f"   {gold:10s} -> {pred:10s}: {count}{marker}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:20]:
            print(f"   [{e['id']}] {e['error']}")

    print(
        "\nM4 target is 'within 5pp of human baseline' — this run has no human baseline to "
        "compare against (see module docstring). Treat the numbers above as a pipeline smoke "
        "test, not a Phase 2 result."
    )


if __name__ == "__main__":
    main()
