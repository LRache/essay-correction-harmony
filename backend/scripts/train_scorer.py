from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path


def correlation(left: list[float], right: list[float]) -> float:
    if len(left) < 2:
        return 0.0
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    denominator = math.sqrt(sum((x - left_mean) ** 2 for x in left) * sum((y - right_mean) ** 2 for y in right))
    return numerator / denominator if denominator else 0.0


def chunks(content: str, size: int = 420, overlap: int = 40) -> list[str]:
    if len(content) <= size:
        return [content]
    step = size - overlap
    return [content[start : start + size] for start in range(0, len(content), step) if content[start : start + size]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune a Hugging Face BERT regression head on human essay scores.")
    parser.add_argument("dataset", type=Path, help="Canonical CSV produced by prepare_dataset.py")
    parser.add_argument("--base-model", default="uer/chinese_roberta_L-2_H-128")
    parser.add_argument("--output", type=Path, default=Path("models/aes-scorer"))
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    with args.dataset.open("r", encoding="utf-8-sig", newline="") as fp:
        rows = [row for row in csv.DictReader(fp) if row.get("content") and row.get("human_score")]
    random.Random(args.seed).shuffle(rows)
    validation_count = max(1, int(len(rows) * args.validation_ratio))
    validation_rows, training_rows = rows[:validation_count], rows[validation_count:]
    training_scores = [float(row["human_score"]) for row in training_rows]
    score_mean = sum(training_scores) / len(training_scores)
    score_std = math.sqrt(sum((score - score_mean) ** 2 for score in training_scores) / len(training_scores)) or 1.0
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)

    class EssayDataset(Dataset):
        def __init__(self, items: list[dict[str, str]]):
            self.items: list[tuple[str, str, float]] = []
            for row in items:
                label = (float(row["human_score"]) - score_mean) / score_std
                for chunk in chunks(row["content"]):
                    self.items.append((row.get("prompt", ""), chunk, label))

        def __len__(self) -> int:
            return len(self.items)

        def __getitem__(self, index: int) -> tuple[str, str, float]:
            return self.items[index]

    def collate(batch: list[tuple[str, str, float]]) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
        prompts, texts, labels = zip(*batch)
        encoded = tokenizer(list(prompts), list(texts), padding=True, truncation=True, max_length=512, return_tensors="pt")
        return encoded, torch.tensor(labels, dtype=torch.float32)

    train_loader = DataLoader(EssayDataset(training_rows), batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    model = AutoModelForSequenceClassification.from_pretrained(args.base_model, num_labels=1, ignore_mismatched_sizes=True)
    model.config.score_mean = score_mean
    model.config.score_std = score_std
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    loss_function = torch.nn.MSELoss()
    best_correlation = -1.0
    best_state: dict[str, torch.Tensor] | None = None

    for epoch in range(1, args.epochs + 1):
        model.train()
        losses: list[float] = []
        for encoded, labels in train_loader:
            optimizer.zero_grad()
            predictions = model(**encoded).logits.squeeze(-1)
            loss = loss_function(predictions, labels)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.item()))
        model.eval()
        predicted: list[float] = []
        expected: list[float] = []
        with torch.inference_mode():
            for row in validation_rows:
                parts = chunks(row["content"])
                encoded = tokenizer(
                    [row.get("prompt", "")] * len(parts), parts,
                    padding=True, truncation=True, max_length=512, return_tensors="pt",
                )
                predicted.append(float(model(**encoded).logits.squeeze(-1).mean().item()))
                expected.append((float(row["human_score"]) - score_mean) / score_std)
        value = correlation(predicted, expected)
        print(f"epoch={epoch} train_mse={sum(losses)/max(1,len(losses)):.6f} validation_pearson={value:.4f}")
        if value > best_correlation:
            best_correlation = value
            best_state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    args.output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    metadata = {
        "base_model": args.base_model,
        "training_items": len(training_rows),
        "validation_items": len(validation_rows),
        "validation_pearson": best_correlation,
        "seed": args.seed,
        "epochs": args.epochs,
        "architecture": "prompt-conditioned overlapping chunks with mean aggregation",
        "score_mean": score_mean,
        "score_std": score_std,
    }
    (args.output / "evaluation.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
