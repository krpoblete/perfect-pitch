import argparse
import json
import sys
from pathlib import Path
import numpy as np

SEV_RANK = {"Normal": 0, "Elevated": 1, "Moderate": 2, "High": 3, "Critical": 4}

def sev_from_ratio(ratio: float) -> str:
    if   ratio < 1.0:  return "Normal"
    elif ratio < 1.25: return "Elevated"
    elif ratio < 1.5:  return "Moderate"
    elif ratio < 2.0:  return "High"
    else:              return "Critical"

#load json file
def load_session(path: Path) -> dict:
    with open(path) as f:
        data = json.load(f)
    if "pitches" not in data or not data["pitches"]:
        raise ValueError(f"No pitches found in {path}")
    return data

def load_all_sessions(folder: Path) -> list[dict]:
    files = sorted(folder.glob("session_*.json"))
    if not files:
        raise FileNotFoundError(f"No session_*.json files found in {folder}")
    sessions = []
    for p in files:
        try:
            sessions.append((p, load_session(p)))
        except Exception as e:
            print(f"  [skip] {p.name}: {e}")
    return sessions

#compute
def compute_summary(pitches: list[dict]) -> dict:
    n           = len(pitches)
    joint_names = pitches[0]["joint_names"]
    n_joints    = len(joint_names)

    correct  = sum(1 for p in pitches if p["verdict"] == "Correct Form")
    accuracy = correct / n * 100

    mse_vals  = [p["mse"] for p in pitches]
    threshold = pitches[0]["threshold"]

    risks      = np.array([[p["joint_risks"][j]      for j in range(n_joints)] for p in pitches])
    thresholds = np.array([[p["joint_thresholds"][j] for j in range(n_joints)] for p in pitches])
    ratios     = risks / (thresholds + 1e-10)

    avg_ratio = ratios.mean(axis=0)
    flag_rate = (ratios >= 1.0).mean(axis=0)
    avg_sev   = [sev_from_ratio(float(r)) for r in avg_ratio]
    avg_rank  = np.array([SEV_RANK[s] for s in avg_sev], dtype=float)
    worst_i   = int(np.argmax(avg_rank + avg_ratio * 0.01))

    history = [(p["pitch_number"], p["verdict"], p["main_issue"], p["mse"])
               for p in pitches]

    return {
        "n_pitches":   n,
        "correct":     correct,
        "accuracy":    accuracy,
        "threshold":   threshold,
        "mse_vals":    mse_vals,
        "mse_mean":    float(np.mean(mse_vals)),
        "mse_std":     float(np.std(mse_vals)),
        "joint_names": joint_names,
        "avg_ratio":   avg_ratio.tolist(),
        "flag_rate":   flag_rate.tolist(),
        "avg_sev":     avg_sev,
        "avg_rank":    avg_rank.tolist(),
        "worst_i":     worst_i,
        "history":     history,
    }

#print
def print_summary(title: str, stats: dict):
    print(f"\n=== PITCH SESSION SUMMARY: {title} ===")
    print(f"Total pitches : {stats['n_pitches']}")
    print(f"Correct form  : {stats['correct']}")
    print(f"Accuracy      : {stats['accuracy']:.1f}%")
    print(f"Avg MSE       : {stats['mse_mean']:.5f} +/-{stats['mse_std']:.5f}  (threshold: {stats['threshold']:.5f})")

    worst_i = stats["worst_i"]
    if stats["avg_sev"][worst_i] != "Normal":
        print(f"\nMost problematic joint: {stats['joint_names'][worst_i]}"
              f"  |  avg ratio {stats['avg_ratio'][worst_i]:.3f}x"
              f"  |  flagged in {stats['flag_rate'][worst_i]*100:.0f}% of pitches"
              f"  |  severity: {stats['avg_sev'][worst_i]}")

    print("\nPitch history:")
    for num, verdict, issue, mse in stats["history"]:
        label     = "Correct" if verdict == "Correct Form" else "Incorrect"
        issue_str = f"  [{issue}]" if issue else ""
        print(f"  #{num:<3}  {label:<9}  MSE={mse:.5f}{issue_str}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Summarise pitch session log(s) produced by live_capture.py"
    )
    parser.add_argument(
        "path",
        help="Path to a session JSON file, or a folder to summarise all sessions in it",
    )
    args   = parser.parse_args()
    target = Path(args.path)

    if target.is_dir():
        sessions = load_all_sessions(target)
        print(f"\nFound {len(sessions)} session(s) in {target}")

        all_pitches = []
        for path, data in sessions:
            all_pitches.extend(data["pitches"])
            print_summary(path.name, compute_summary(data["pitches"]))

        if len(sessions) > 1:
            print(f"=== COMBINED SUMMARY ({len(all_pitches)} pitches across {len(sessions)} sessions) ===")
            print_summary("All sessions combined", compute_summary(all_pitches))

    elif target.is_file():
        data = load_session(target)
        print_summary(target.name, compute_summary(data["pitches"]))

    else:
        print(f"Error: '{target}' is not a file or directory.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()