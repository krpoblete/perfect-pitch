import argparse
from pathlib import Path
import pandas as pd
from analyze import analyze

EXPECTED_COLUMNS = [
    "video",
    "ground_truth",
    "predicted",
    "verdict_reason",
    "mse",
    "correct",
]


def _safe_pct(num: int, den: int) -> float:
    return (num / den * 100.0) if den else 0.0


def evaluate_batch(correct: str, incorrect: str, out_csv: str = "eval_results.csv"):
    """
    correct_dir   — folder containing correct form videos
    incorrect_dir — folder containing incorrect form videos
    """
    results = []

    correct_paths = sorted(Path(correct).glob("*.mp4"))
    incorrect_paths = sorted(Path(incorrect).glob("*.mp4"))

    if not correct_paths:
        print(f"Warning: no .mp4 files found in correct folder: {correct}")
    if not incorrect_paths:
        print(f"Warning: no .mp4 files found in incorrect folder: {incorrect}")

    # ── Correct form videos ───────────────────────────────────────────────
    for video in correct_paths:
        print(f"\nProcessing CORRECT: {video.name}")
        try:
            result = analyze(str(video))
            predicted = result.get("verdict", "Unknown")
            is_correct_prediction = predicted == "Correct Form"

            results.append({
                "video": video.name,
                "ground_truth": "Correct Form",
                "predicted": predicted,
                "verdict_reason": result.get("reason", ""),
                "mse": round(float(result.get("mse", 0.0)), 6),
                "correct": bool(is_correct_prediction),
            })
        except Exception as e:
            print(f"  ERROR processing {video.name}: {e}")
            results.append({
                "video": video.name,
                "ground_truth": "Correct Form",
                "predicted": "ERROR",
                "verdict_reason": str(e),
                "mse": None,
                "correct": False,
            })

    # ── Incorrect form videos ─────────────────────────────────────────────
    for video in incorrect_paths:
        print(f"\nProcessing INCORRECT: {video.name}")
        try:
            result = analyze(str(video))
            predicted = result.get("verdict", "Unknown")
            is_correct_prediction = predicted != "Correct Form"

            results.append({
                "video": video.name,
                "ground_truth": "Incorrect Form",
                "predicted": predicted,
                "verdict_reason": result.get("reason", ""),
                "mse": round(float(result.get("mse", 0.0)), 6),
                "correct": bool(is_correct_prediction),
            })
        except Exception as e:
            print(f"  ERROR processing {video.name}: {e}")
            results.append({
                "video": video.name,
                "ground_truth": "Incorrect Form",
                "predicted": "ERROR",
                "verdict_reason": str(e),
                "mse": None,
                "correct": False,
            })

    # ── Build DataFrame safely ────────────────────────────────────────────
    df = pd.DataFrame(results)
    if df.empty:
        df = pd.DataFrame(columns=EXPECTED_COLUMNS)

    # Ensure expected columns exist even if some results failed / list is empty
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")

    # Make sure 'correct' is boolean so sum()/~ work consistently
    if len(df):
        df["correct"] = df["correct"].fillna(False).astype(bool)
    else:
        df["correct"] = pd.Series(dtype=bool)

    total = len(df)
    n_correct = int(df["correct"].sum()) if total else 0
    accuracy = _safe_pct(n_correct, total)

    # Per-class subsets
    correct_vids = df[df["ground_truth"] == "Correct Form"]
    incorrect_vids = df[df["ground_truth"] == "Incorrect Form"]

    n_correct_vids = len(correct_vids)
    n_incorrect_vids = len(incorrect_vids)

    tn = int(correct_vids["correct"].sum()) if n_correct_vids else 0
    tp = int(incorrect_vids["correct"].sum()) if n_incorrect_vids else 0
    fp = int((~correct_vids["correct"]).sum()) if n_correct_vids else 0
    fn = int((~incorrect_vids["correct"]).sum()) if n_incorrect_vids else 0

    acc_correct = _safe_pct(tn, n_correct_vids)
    acc_incorrect = _safe_pct(tp, n_incorrect_vids)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    # ── Print report ──────────────────────────────────────────────────────
    print(f"\n{'='*54}")
    print(f"  EVALUATION RESULTS  ({total} videos)")
    print(f"{'='*54}")
    print(f"  Overall Accuracy    : {accuracy:.1f}%  ({n_correct}/{total})")
    print(f"  Correct Form Acc    : {acc_correct:.1f}%  ({tn}/{n_correct_vids})")
    print(f"  Incorrect Form Acc  : {acc_incorrect:.1f}%  ({tp}/{n_incorrect_vids})")
    print(f"{'─'*54}")
    print(f"  TP: {tp}  TN: {tn}  FP: {fp}  FN: {fn}")
    print(f"  Precision : {precision:.3f}")
    print(f"  Recall    : {recall:.3f}")
    print(f"  F1 Score  : {f1:.3f}")
    print(f"{'='*54}")
    print("\nPer-Video Results:")
    if total:
        print(df.to_string(index=False))
    else:
        print("No videos were evaluated. Check your folder paths and file extensions.")

    # ── Save ──────────────────────────────────────────────────────────────
    df.to_csv(out_csv, index=False)
    print(f"\nResults saved → {out_csv}")

    return df, {
        "accuracy": accuracy,
        "acc_correct": acc_correct,
        "acc_incorrect": acc_incorrect,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--correct", required=True, help="Folder of correct form videos")
    parser.add_argument("--incorrect", required=True, help="Folder of incorrect form videos")
    parser.add_argument("--out", default="eval_results.csv")
    args = parser.parse_args()

    evaluate_batch(args.correct, args.incorrect, args.out)