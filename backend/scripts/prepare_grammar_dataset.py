from __future__ import annotations

import argparse
import difflib
import json
import random
from pathlib import Path
from typing import Any


def changed_spans(source: str, target: str) -> list[list[int]]:
    spans: list[list[int]] = []
    matcher = difflib.SequenceMatcher(a=source, b=target, autojunk=False)
    for tag, start, end, _target_start, _target_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        if start == end:
            start = max(0, start - 1)
            end = min(len(source), start + 1)
        spans.append([start, max(start + 1, end)])
    return spans


def choose_yaclc_target(row: dict[str, Any]) -> str:
    source = str(row["sentence_text"])
    annotations = [item for item in row.get("sentence_annos", []) if item.get("correction")]
    if not annotations:
        return source
    # Prefer corrections supported by more annotators, then the smallest edit
    # that resolves the sentence. This limits alignment noise.
    best = max(
        annotations,
        key=lambda item: (int(item.get("annotator_count", 0)), -int(item.get("edits_count", 9999))),
    )
    return str(best["correction"])


def record(identifier: str, source: str, target: str) -> dict[str, Any]:
    spans = changed_spans(source, target)
    return {"id": identifier, "source": source, "target": target, "grammar_spans": spans, "has_error": bool(spans)}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build leakage-safe grammar detector train/validation/test files.")
    parser.add_argument("--yaclc", type=Path, required=True, help="YACLC repository root")
    parser.add_argument("--yacsc", type=Path, required=True, help="YACSC repository root")
    parser.add_argument("--flacgec", type=Path, help="FlaCGEC repository root")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    args = parser.parse_args()

    yaclc_rows: list[dict[str, Any]] = []
    for line in (args.yaclc / "valid.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        source = str(row["sentence_text"])
        yaclc_rows.append(record(f"yaclc-{row['sentence_id']}", source, choose_yaclc_target(row)))
    random.Random(args.seed).shuffle(yaclc_rows)
    validation_count = max(1, int(len(yaclc_rows) * args.validation_ratio))

    yacsc_rows: list[dict[str, Any]] = []
    for line in (args.yacsc / "YACSC" / "YACSC.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        yacsc_rows.append(record(f"yacsc-{row['id']}", str(row["src"]), str(row["gec_trg"])))

    training_rows = yaclc_rows[validation_count:]
    validation_rows = yaclc_rows[:validation_count]
    if args.flacgec:
        fla_train = json.loads((args.flacgec / "data" / "train.json").read_text(encoding="utf-8"))
        fla_dev = json.loads((args.flacgec / "data" / "dev.json").read_text(encoding="utf-8"))
        training_rows.extend(
            record(f"flacgec-train-{key}", str(row["source"]), str(row["target"]))
            for key, row in fla_train.items()
        )
        validation_rows.extend(
            record(f"flacgec-dev-{key}", str(row["source"]), str(row["target"]))
            for key, row in fla_dev.items()
        )

    write_jsonl(args.output / "train.jsonl", training_rows)
    write_jsonl(args.output / "validation.jsonl", validation_rows)
    write_jsonl(args.output / "test.jsonl", yacsc_rows)
    summary = {
        "train": len(training_rows),
        "validation": len(validation_rows),
        "test": len(yacsc_rows),
        "test_source": "YACSC held out from training",
    }
    (args.output / "dataset.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
