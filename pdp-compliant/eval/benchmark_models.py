"""
Phase 2 model benchmark (§10.2, §12 Phase 2 exit criteria).

Compares candidate local models on: classification accuracy, extraction F1
(via score_pii-style span matching against triage output, not implemented
here — see note below), schema compliance rate, tokens/sec, and latency.
Memory footprint at Q4_K_M must be measured from the serving process
(`ollama ps`, or the container's own metrics) — this script only measures
what it can observe from the client side.

This is a skeleton, not a finished benchmark: it requires a live
Ollama-compatible endpoint with each candidate model pulled. It will run
against MockInferenceClient-shaped output only if you point it at nothing —
which is intentionally not the default, unlike the other eval scripts,
because a mock model benchmark would produce meaningless "winner" output for
what §10.2 calls "a standalone portfolio artifact."

Candidates per §6.3 / Open Question 1: confirm a GGUF build of SEA-LION v4
4B VL exists before assuming it's benchmarkable this way.

Usage:
    python benchmark_models.py ../eval/corpus/complaints.jsonl \\
        --models sea-lion-v4-4b sahabat-ai-8b qwen3:4b phi4-mini \\
        --base-url http://localhost:11434 --sample 30
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.inference.client import LocalInferenceUnavailable, OllamaCompatibleClient  # noqa: E402


def benchmark_model(model: str, base_url: str, records: list[dict]) -> dict:
    client = OllamaCompatibleClient(base_url=base_url, model=model, timeout_s=60.0)
    latencies, schema_ok, category_correct, severity_correct = [], 0, 0, 0
    errors = 0

    for record in records:
        start = time.monotonic()
        try:
            triage = client.classify(record["text"])
        except LocalInferenceUnavailable as exc:
            errors += 1
            print(f"  [{model}] {record['id']}: {exc}", file=sys.stderr)
            continue
        latencies.append(time.monotonic() - start)
        schema_ok += 1  # reaching here means TriageOutput validated (client raises otherwise)
        if triage.category == record.get("category"):
            category_correct += 1
        if triage.severity.value == record.get("severity"):
            severity_correct += 1

    n_attempted = len(records)
    n_ok = len(latencies)
    return {
        "model": model,
        "n_attempted": n_attempted,
        "n_ok": n_ok,
        "schema_compliance_rate": n_ok / n_attempted if n_attempted else 0.0,
        "category_accuracy": category_correct / n_ok if n_ok else float("nan"),
        "severity_accuracy": severity_correct / n_ok if n_ok else float("nan"),
        "latency_p50_s": statistics.median(latencies) if latencies else float("nan"),
        "latency_p95_s": (sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else
                           (latencies[0] if latencies else float("nan"))),
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_path")
    parser.add_argument("--models", nargs="+", required=True,
                         help="Ollama model tags, e.g. sea-lion-v4-4b sahabat-ai-8b qwen3:4b phi4-mini")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--sample", type=int, default=30, help="records to benchmark per model (full corpus is slow)")
    args = parser.parse_args()

    with open(args.corpus_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()][: args.sample]

    print(f"Benchmarking {len(args.models)} model(s) on {len(records)} record(s) from {args.corpus_path}\n")
    results = []
    for model in args.models:
        print(f"Running {model}...")
        results.append(benchmark_model(model, args.base_url, records))

    print(f"\n{'model':20s} {'schema%':>8s} {'cat_acc':>8s} {'sev_acc':>8s} {'p50_s':>7s} {'p95_s':>7s} {'errors':>7s}")
    for r in results:
        print(f"{r['model']:20s} {r['schema_compliance_rate']:8.2%} {r['category_accuracy']:8.2%} "
              f"{r['severity_accuracy']:8.2%} {r['latency_p50_s']:7.2f} {r['latency_p95_s']:7.2f} {r['errors']:7d}")

    print(
        "\nNOT measured here (collect separately per §10.2): tokens/sec on the target instance, "
        "memory footprint at Q4_K_M, Indonesian vs Javanese/Sundanese subset performance breakdown "
        "(filter the corpus by the 'code_switch' field and re-run per subset), extraction F1 "
        "(requires comparing triage-extracted entities against gold spans, not yet wired up)."
    )


if __name__ == "__main__":
    main()
