from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis import build_provider
from app.config import load_settings
from app.schemas import ExampleOut


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean, right_mean = statistics.mean(left), statistics.mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    denominator = math.sqrt(sum((x - left_mean) ** 2 for x in left) * sum((y - right_mean) ** 2 for y in right))
    return numerator / denominator if denominator else None


def ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        rank = (index + 1 + end) / 2
        for position in range(index, end):
            result[ordered[position][0]] = rank
        index = end
    return result


def parse_spans(raw: str) -> set[tuple[int, int]]:
    if not raw:
        return set()
    value = json.loads(raw)
    spans: set[tuple[int, int]] = set()
    for item in value:
        if isinstance(item, dict):
            spans.add((int(item["start"]), int(item["end"])))
        elif isinstance(item, list) and len(item) >= 2:
            spans.add((int(item[0]), int(item[1])))
    return spans


def overlaps(predicted: tuple[int, int], expected: tuple[int, int]) -> bool:
    return max(predicted[0], expected[0]) < min(predicted[1], expected[1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate grammar accuracy, human-score correlation and latency.")
    parser.add_argument("dataset", type=Path, help="Canonical CSV: title,prompt,content,human_score,grammar_spans")
    parser.add_argument("--provider", choices=["local-nlp", "openai-compatible"], default="local-nlp")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--fail-below-target", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    provider = build_provider(settings, args.provider)
    predicted_scores: list[float] = []
    paired_predictions: list[float] = []
    paired_humans: list[float] = []
    latencies: list[int] = []
    true_positive = false_positive = false_negative = 0
    labelled_grammar_rows = 0
    empty_examples: list[ExampleOut] = []

    with args.dataset.open("r", encoding="utf-8-sig", newline="") as fp:
        rows = list(csv.DictReader(fp))
    if args.limit > 0:
        rows = rows[: args.limit]
    for index, row in enumerate(rows):
        started = time.perf_counter()
        report = provider.analyze(
            essay_id=f"evaluation-{index}",
            title=row.get("title", ""),
            prompt=row.get("prompt", ""),
            content=row.get("content", ""),
            examples=empty_examples,
        )
        latencies.append(int((time.perf_counter() - started) * 1000))
        predicted_scores.append(report.total_score)
        if row.get("human_score", "").strip():
            paired_predictions.append(report.total_score)
            paired_humans.append(float(row["human_score"]))
        if "grammar_spans" in row and row.get("grammar_spans", "").strip():
            labelled_grammar_rows += 1
            expected = parse_spans(row["grammar_spans"])
            predicted = {(issue.start, issue.end) for issue in report.grammar_issues}
            matched_expected: set[tuple[int, int]] = set()
            for candidate in predicted:
                match = next((span for span in expected if span not in matched_expected and overlaps(candidate, span)), None)
                if match is None:
                    false_positive += 1
                else:
                    true_positive += 1
                    matched_expected.add(match)
            false_negative += len(expected - matched_expected)

    paired_count = len(paired_humans)
    pearson_value = pearson(paired_predictions, paired_humans)
    spearman_value = pearson(ranks(paired_predictions), ranks(paired_humans)) if paired_count >= 2 else None
    grammar_denominator = true_positive + false_positive + false_negative
    grammar_accuracy = true_positive / grammar_denominator if grammar_denominator else None
    latency_p50 = statistics.median(latencies) if latencies else 0
    latency_p95 = sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)] if latencies else 0

    grammar_model_accuracy = None
    grammar_evaluation_path = Path(settings.local_grammar_model) / "evaluation.json"
    if grammar_evaluation_path.is_file():
        grammar_metadata = json.loads(grammar_evaluation_path.read_text(encoding="utf-8"))
        grammar_model_accuracy = grammar_metadata.get("yacsc_independent_test", {}).get("accuracy")
    held_out_score_correlation = None
    scorer_evaluation_path = Path(settings.local_scoring_model) / "evaluation.json"
    if scorer_evaluation_path.is_file():
        scorer_metadata = json.loads(scorer_evaluation_path.read_text(encoding="utf-8"))
        held_out_score_correlation = scorer_metadata.get("validation_pearson")
    grammar_acceptance_value = grammar_accuracy if grammar_accuracy is not None else grammar_model_accuracy
    score_acceptance_value = held_out_score_correlation if held_out_score_correlation is not None else pearson_value

    result = {
        "items": len(rows),
        "provider": args.provider,
        "grammar_labelled_items": labelled_grammar_rows,
        "grammar_detection_accuracy": grammar_accuracy,
        "grammar_independent_yacsc_accuracy": grammar_model_accuracy,
        "grammar_target_90_pass": grammar_acceptance_value is not None and grammar_acceptance_value >= 0.90,
        "score_pairs": paired_count,
        "score_pearson": pearson_value,
        "score_spearman": spearman_value,
        "score_held_out_pearson": held_out_score_correlation,
        "score_correlation_target_0_7_pass": score_acceptance_value is not None and score_acceptance_value >= 0.70,
        "latency_ms_p50": latency_p50,
        "latency_ms_p95": latency_p95,
        "latency_target_2000ms_pass": bool(latencies) and latency_p95 < 2000,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.fail_below_target and not all(
        (result["grammar_target_90_pass"], result["score_correlation_target_0_7_pass"], result["latency_target_2000ms_pass"])
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
