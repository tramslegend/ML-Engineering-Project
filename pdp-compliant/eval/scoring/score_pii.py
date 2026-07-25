"""
M1/M2: PII detection recall and precision (§10.2/§10.3).

Matches predicted entities to gold spans by entity_type + span overlap
(IoU >= 0.5), not exact offset equality — a detector that finds "Budi
Santoso" when gold is "Budi Santoso " (trailing space) should not be
penalized for a boundary difference that doesn't change what's exposed.

M1 says "misses individually documented" — this script does that, printing
every unmatched gold span (a miss) and every unmatched prediction (a false
positive) rather than only the aggregate numbers.

Usage:
    python score_pii.py ../corpus/complaints.jsonl
    python score_pii.py ../red_team/pii_red_team.jsonl --red-team
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.pii import detect_all


def overlap_ratio(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    inter = max(0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union if union > 0 else 0.0


def score_record(text: str, gold_spans: list[dict]) -> dict:
    try:
        detection = detect_all(text)
    except Exception as exc:  # noqa: BLE001 - fail-closed IS the correct outcome to report
        return {"detector_error": str(exc), "gold_spans": gold_spans, "predicted": []}

    predicted = [
        {"entity_type": e.entity_type.value, "start": e.start, "end": e.end, "text": e.raw_text, "confidence": e.confidence}
        for e in detection.entities
    ]

    matched_gold = set()
    matched_pred = set()
    for gi, g in enumerate(gold_spans):
        best = None
        for pi, p in enumerate(predicted):
            if pi in matched_pred or p["entity_type"] != g["entity_type"]:
                continue
            # Gold spans from the corpus generator carry exact offsets; red-team
            # cases only carry text, so fall back to substring position.
            g_start = g.get("start")
            g_end = g.get("end")
            if g_start is None:
                g_start = text.find(g["text"])
                g_end = g_start + len(g["text"]) if g_start >= 0 else -1
            if g_start < 0:
                continue
            ratio = overlap_ratio(g_start, g_end, p["start"], p["end"])
            if ratio >= 0.5 and (best is None or ratio > best[1]):
                best = (pi, ratio)
        if best:
            matched_pred.add(best[0])
            matched_gold.add(gi)

    misses = [g for gi, g in enumerate(gold_spans) if gi not in matched_gold]
    false_positives = [p for pi, p in enumerate(predicted) if pi not in matched_pred]

    return {
        "gold_count": len(gold_spans),
        "true_positives": len(matched_gold),
        "misses": misses,
        "false_positives": false_positives,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_path")
    parser.add_argument("--red-team", action="store_true", help="corpus uses text-only gold spans (no offsets)")
    args = parser.parse_args()

    per_type_tp: dict[str, int] = defaultdict(int)
    per_type_gold: dict[str, int] = defaultdict(int)
    per_type_pred_fp: dict[str, int] = defaultdict(int)
    all_misses = []
    detector_errors = []

    with open(args.corpus_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    for record in records:
        result = score_record(record["text"], record["pii_spans"])
        if "detector_error" in result:
            detector_errors.append({"id": record.get("id"), "error": result["detector_error"]})
            for g in result["gold_spans"]:
                per_type_gold[g["entity_type"]] += 1
            continue

        for g in record["pii_spans"]:
            per_type_gold[g["entity_type"]] += 1
        for m in result["misses"]:
            all_misses.append({"id": record.get("id"), **m})
        for fp in result["false_positives"]:
            per_type_pred_fp[fp["entity_type"]] += 1

        miss_keys = {(m.get("entity_type"), m.get("text")) for m in result["misses"]}
        for g in record["pii_spans"]:
            if (g["entity_type"], g["text"]) not in miss_keys:
                per_type_tp[g["entity_type"]] += 1

    print(f"Corpus: {args.corpus_path} ({len(records)} records)")
    if detector_errors:
        print(f"\n!! Detector raised (fail-closed) on {len(detector_errors)} record(s):")
        for e in detector_errors:
            print(f"   {e['id']}: {e['error']}")

    total_gold = sum(per_type_gold.values())
    total_tp = sum(per_type_tp.values())
    total_fp = sum(per_type_pred_fp.values())
    recall = total_tp / total_gold if total_gold else float("nan")
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else float("nan")

    print(f"\nOverall: recall={recall:.4f} (target >=0.995, M1)  precision={precision:.4f} (target >=0.90, M2)")
    print(f"{'entity_type':16s} {'gold':>6s} {'tp':>6s} {'fp':>6s} {'recall':>8s} {'precision':>10s}")
    for et in sorted(per_type_gold):
        g, tp, fp = per_type_gold[et], per_type_tp[et], per_type_pred_fp[et]
        r = tp / g if g else float("nan")
        p = tp / (tp + fp) if (tp + fp) else float("nan")
        print(f"{et:16s} {g:6d} {tp:6d} {fp:6d} {r:8.3f} {p:10.3f}")

    if all_misses:
        print(f"\nDocumented misses ({len(all_misses)}) — M1 requires these be listed individually:")
        for m in all_misses:
            print(f"   [{m['id']}] {m['entity_type']}: {m.get('text', '')!r}")

    sys.exit(0)


if __name__ == "__main__":
    main()
