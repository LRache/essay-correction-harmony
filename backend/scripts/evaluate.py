from __future__ import annotations

import argparse
import csv
import statistics
import time
from pathlib import Path

from app.analysis.providers import MockRuleProvider
from app.schemas import ExampleOut


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline metric scaffold for essay correction models.")
    parser.add_argument("dataset", type=Path, help="CSV with title,prompt,content and optional human_score columns")
    args = parser.parse_args()

    provider = MockRuleProvider()
    latencies: list[int] = []
    scores: list[float] = []
    human_scores: list[float] = []
    empty_examples: list[ExampleOut] = []

    with args.dataset.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for index, row in enumerate(reader):
            started = time.perf_counter()
            report = provider.analyze(
                essay_id=f"offline-{index}",
                title=row.get("title", ""),
                prompt=row.get("prompt", ""),
                content=row.get("content", ""),
                examples=empty_examples,
            )
            latencies.append(int((time.perf_counter() - started) * 1000))
            scores.append(report.total_score)
            if row.get("human_score"):
                human_scores.append(float(row["human_score"]))

    print(f"items={len(scores)}")
    print(f"latency_ms_p50={statistics.median(latencies) if latencies else 0}")
    print("score_human_correlation=TODO: plug Pearson/Spearman after aligned labeled data is loaded")


if __name__ == "__main__":
    main()

