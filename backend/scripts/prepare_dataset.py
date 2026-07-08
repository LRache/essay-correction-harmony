from __future__ import annotations

import argparse
import csv
import difflib
import json
import urllib.request
from pathlib import Path
from typing import Any, Iterable


ALIASES = {
    "title": ("title", "essay_title", "题目", "标题"),
    "prompt": ("prompt", "requirement", "topic", "作文要求", "要求"),
    "content": ("content", "essay", "text", "source", "sentence", "作文", "正文"),
    "corrected_content": ("corrected_content", "target", "correction", "corrected", "修改后"),
    "human_score": ("human_score", "score", "grade", "人工评分", "得分"),
    "grammar_spans": ("grammar_spans", "error_spans", "errors", "语病位置"),
}


def first(row: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return ""


def load_rows(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix.lower() in {".jsonl", ".json"}:
        text = path.read_text(encoding="utf-8-sig")
        data = [json.loads(line) for line in text.splitlines() if line.strip()] if path.suffix.lower() == ".jsonl" else json.loads(text)
        if isinstance(data, dict):
            data = data.get("data", data.get("items", []))
        yield from data
        return
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        yield from csv.DictReader(fp)


def read_text_auto(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_aes_rows(root: Path) -> Iterable[dict[str, Any]]:
    scores: dict[str, float] = {}
    for line in read_text_auto(root / "scores.txt").splitlines():
        fields = line.split("\t")
        if len(fields) >= 3:
            scores[fields[0].strip()] = float(fields[-1].strip())
    for essay_path in sorted((root / "essays").glob("*.txt")):
        essay_id = essay_path.stem
        text = read_text_auto(essay_path).strip()
        lines = text.splitlines()
        if not lines:
            continue
        yield {
            "title": lines[0].strip(),
            "prompt": f"请以《{lines[0].strip()}》为题写一篇中文作文。",
            "content": "\n".join(lines[1:]).strip(),
            "corrected_content": "",
            "human_score": scores.get(essay_id, ""),
            "grammar_spans": "",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a public Chinese student essay corpus to the evaluation schema.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Local CSV/JSON/JSONL corpus")
    source.add_argument("--url", help="Direct URL to a public CSV/JSON/JSONL corpus")
    source.add_argument("--aes-root", type=Path, help="Checked-out declan-haojin/AES-Dataset directory")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    input_path = args.input
    if args.url:
        suffix = Path(args.url.split("?", 1)[0]).suffix or ".jsonl"
        input_path = args.output.with_name(f"downloaded-source{suffix}")
        input_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(args.url, input_path)
    if args.aes_root is None:
        assert input_path is not None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with args.output.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(ALIASES))
        writer.writeheader()
        source_rows = load_aes_rows(args.aes_root) if args.aes_root else load_rows(input_path)
        for row in source_rows:
            canonical = {name: first(row, aliases) for name, aliases in ALIASES.items()}
            if not canonical["content"]:
                continue
            if isinstance(canonical["grammar_spans"], (list, dict)):
                canonical["grammar_spans"] = json.dumps(canonical["grammar_spans"], ensure_ascii=False)
            if not canonical["grammar_spans"] and canonical["corrected_content"]:
                matcher = difflib.SequenceMatcher(a=str(canonical["content"]), b=str(canonical["corrected_content"]))
                spans = []
                for tag, start, end, _target_start, _target_end in matcher.get_opcodes():
                    if tag != "equal":
                        spans.append([start, max(end, start + 1)])
                canonical["grammar_spans"] = json.dumps(spans, ensure_ascii=False)
            writer.writerow(canonical)
            count += 1
    print(f"converted_items={count} output={args.output}")


if __name__ == "__main__":
    main()
