from __future__ import annotations

import argparse
import csv
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "y", "예", "관련"}
FALSE_VALUES = {"0", "false", "no", "n", "아니오", "무관"}


def parse_label(value: str) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def evaluate(path: Path) -> dict | None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    pairs = [
        (parse_label(row.get("predicted_relevant", "")), parse_label(row.get("human_relevant", "")))
        for row in rows
    ]
    pairs = [(predicted, human) for predicted, human in pairs if predicted is not None and human is not None]
    if not pairs:
        return None
    tp = sum(predicted and human for predicted, human in pairs)
    fp = sum(predicted and not human for predicted, human in pairs)
    fn = sum(not predicted and human for predicted, human in pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "labeled_documents": len(pairs),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="사람 검수 라벨로 관련도 precision/recall/F1 계산")
    parser.add_argument(
        "labels", type=Path, nargs="?",
        default=Path(__file__).resolve().parent / "reports" / "relevance_evaluation_labels.csv",
    )
    args = parser.parse_args()
    result = evaluate(args.labels)
    if result is None:
        print("검수 데이터 필요: human_relevant에 라벨을 입력해 주세요.")
        return 0
    print(
        f"검수 {result['labeled_documents']}건 | precision={result['precision']:.4f} | "
        f"recall={result['recall']:.4f} | F1={result['f1']:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
