"""Regression gate for the Tamil / English / Tanglish classifier.

The eval set (tests/data/language_eval.jsonl) is the contract: accuracy must
stay >= 90% overall and >= 85% per class. Extend the set when adding lexicon
entries so improvements are locked in.
"""

import json
from collections import defaultdict
from pathlib import Path

from app.services.language import (
    detect_language,
    dominant_language,
    language_breakdown,
)

EVAL_PATH = Path(__file__).parent / "data" / "language_eval.jsonl"

OVERALL_THRESHOLD = 0.90
PER_CLASS_THRESHOLD = 0.85


def load_eval():
    with EVAL_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_eval_set_is_substantial():
    rows = load_eval()
    assert len(rows) >= 100
    labels = {r["label"] for r in rows}
    assert labels == {"tamil", "english", "tanglish"}


def test_accuracy_thresholds():
    rows = load_eval()
    total_correct = 0
    per_class = defaultdict(lambda: [0, 0])  # label -> [correct, total]
    failures = []

    for row in rows:
        got = detect_language(row["text"])
        per_class[row["label"]][1] += 1
        if got == row["label"]:
            total_correct += 1
            per_class[row["label"]][0] += 1
        else:
            failures.append(f"  [{got} != {row['label']}] {row['text']}")

    accuracy = total_correct / len(rows)
    report = "\n".join(failures)
    assert accuracy >= OVERALL_THRESHOLD, (
        f"Overall accuracy {accuracy:.1%} < {OVERALL_THRESHOLD:.0%}\nMisclassified:\n{report}"
    )
    for label, (correct, total) in per_class.items():
        class_acc = correct / total
        assert class_acc >= PER_CLASS_THRESHOLD, (
            f"{label} accuracy {class_acc:.1%} < {PER_CLASS_THRESHOLD:.0%}\nMisclassified:\n{report}"
        )


def test_rollups():
    assert dominant_language(["tanglish", "english", "tamil"]) == "tanglish"
    assert dominant_language(["tamil", "english"]) == "mixed"
    assert dominant_language(["english", "english"]) == "english"
    assert dominant_language([]) == "english"

    breakdown = language_breakdown(["english", "tanglish", "tanglish", "tamil"])
    assert breakdown["tanglish"] == 50.0
    assert sum(breakdown.values()) == 100.0


def test_empty_and_punctuation():
    assert detect_language("") == "english"
    assert detect_language("   ") == "english"
    assert detect_language("...!!!") == "english"
