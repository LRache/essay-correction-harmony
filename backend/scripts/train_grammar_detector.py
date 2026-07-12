from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def overlaps(offset: tuple[int, int], spans: list[list[int]]) -> bool:
    return any(max(offset[0], span[0]) < min(offset[1], span[1]) for span in spans)


def metrics(tp: int, fp: int, fn: int, tn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / max(1, tp + fp + fn + tn)
    return {"accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune a BERT token classifier for Chinese grammar-error spans.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--base-model", default="uer/chinese_roberta_L-2_H-128")
    parser.add_argument("--output", type=Path, default=Path("models/grammar-detector"))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)

    class GrammarDataset(Dataset):
        def __init__(self, rows: list[dict[str, Any]]):
            self.rows = rows

        def __len__(self) -> int:
            return len(self.rows)

        def __getitem__(self, index: int) -> dict[str, Any]:
            return self.rows[index]

    def collate(rows: list[dict[str, Any]]) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
        encoded = tokenizer(
            [row["source"] for row in rows], padding=True, truncation=True,
            max_length=256, return_tensors="pt", return_offsets_mapping=True,
        )
        offsets = encoded.pop("offset_mapping")
        labels = torch.full(encoded["input_ids"].shape, -100, dtype=torch.long)
        for row_index, row in enumerate(rows):
            for token_index, pair in enumerate(offsets[row_index].tolist()):
                start, end = int(pair[0]), int(pair[1])
                if end <= start:
                    continue
                labels[row_index, token_index] = 1 if overlaps((start, end), row["grammar_spans"]) else 0
        return encoded, labels

    train_rows = load_jsonl(args.dataset / "train.jsonl")
    validation_rows = load_jsonl(args.dataset / "validation.jsonl")
    test_rows = load_jsonl(args.dataset / "test.jsonl")
    train_loader = DataLoader(GrammarDataset(train_rows), batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    validation_loader = DataLoader(GrammarDataset(validation_rows), batch_size=args.batch_size, collate_fn=collate)
    test_loader = DataLoader(GrammarDataset(test_rows), batch_size=args.batch_size, collate_fn=collate)
    model = AutoModelForTokenClassification.from_pretrained(
        args.base_model, num_labels=2, id2label={0: "OK", 1: "ERROR"},
        label2id={"OK": 0, "ERROR": 1}, ignore_mismatched_sizes=True,
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    class_weights = torch.tensor([1.0, 5.0], dtype=torch.float32)
    loss_function = torch.nn.CrossEntropyLoss(weight=class_weights, ignore_index=-100)
    best_f1 = -1.0
    best_state: dict[str, torch.Tensor] | None = None

    def evaluate(loader: DataLoader, threshold: float) -> dict[str, float]:
        model.eval()
        tp = fp = fn = tn = 0
        with torch.inference_mode():
            for encoded, labels in loader:
                probabilities = torch.softmax(model(**encoded).logits, dim=-1)[..., 1]
                valid = labels >= 0
                predicted = probabilities >= threshold
                expected = labels == 1
                tp += int((predicted & expected & valid).sum())
                fp += int((predicted & ~expected & valid).sum())
                fn += int((~predicted & expected & valid).sum())
                tn += int((~predicted & ~expected & valid).sum())
        return metrics(tp, fp, fn, tn)

    for epoch in range(1, args.epochs + 1):
        model.train()
        losses: list[float] = []
        for encoded, labels in train_loader:
            optimizer.zero_grad()
            logits = model(**encoded).logits
            loss = loss_function(logits.view(-1, 2), labels.view(-1))
            loss.backward()
            optimizer.step()
            losses.append(float(loss.item()))
        current = evaluate(validation_loader, 0.5)
        print(f"epoch={epoch} loss={sum(losses)/max(1,len(losses)):.5f} validation={json.dumps(current)}")
        if current["f1"] > best_f1:
            best_f1 = current["f1"]
            best_state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    # Tune only on validation; the independent YACSC test remains untouched.
    candidates = [round(value / 20, 2) for value in range(2, 19)]
    threshold = max(candidates, key=lambda value: evaluate(validation_loader, value)["f1"])
    validation_metrics = evaluate(validation_loader, threshold)
    test_metrics = evaluate(test_loader, threshold)
    model.config.error_threshold = threshold
    args.output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    result = {
        "base_model": args.base_model,
        "train_items": len(train_rows),
        "validation_items": len(validation_rows),
        "test_items": len(test_rows),
        "threshold": threshold,
        "validation": validation_metrics,
        "yacsc_independent_test": test_metrics,
        "accuracy_target_0_90_pass": test_metrics["accuracy"] >= 0.90,
    }
    (args.output / "evaluation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
