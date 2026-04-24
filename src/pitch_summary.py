import argparse
import json
import sys
from pathlib import Path
import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

SEVERITY_RANK = {"Normal": 0, "Elevated": 1, "Moderate": 2, "High": 3, "Critical": 4}
SEVERITY_COLORS = {
    "Normal":   (50, 205, 50),
    "Elevated": (0, 215, 255),
    "Moderate": (0, 165, 255),
    "High":     (0, 100, 255),
    "Critical": (0, 0, 220),
}

def severity(ratio: float) -> str:
    if   ratio < 1.0:  return "Normal"
    elif ratio < 1.25: return "Elevated"
    elif ratio < 1.5:  return "Moderate"
    elif ratio < 2.0:  return "High"
    else:              return "Critical"


#LOAD
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


#COMPUTATION
def compute_summary(pitches: list[dict]) -> dict:
    n        = len(pitches)
    joint_names = pitches[0]["joint_names"]
    n_joints = len(joint_names)

    correct  = sum(1 for p in pitches if p["verdict"] == "Correct Form")
    accuracy = correct / n * 100

    mse_val   = [p["mse"] for p in pitches]
    threshold = pitches[0]["threshold"]

    risks      = np.array([[p["joint_risks"][j]      for j in range(n_joints)] for p in pitches])
    thresholds = np.array([[p["joint_thresholds"][j] for j in range(n_joints)] for p in pitches])
    ratio      = risks / (thresholds + 1e-10)

    # avg_ratio: mean of (joint_risk / joint_threshold) per joint across all pitches.
    #   < 1.0 = within threshold | > 1.0 = exceeding threshold.
    #   e.g. 2.0 means the joint averaged twice its allowed limit → Critical.
    avg_ratio = ratio.mean(axis=0)

    # flag_rate: fraction of pitches where that joint exceeded its threshold.
    #   e.g. 0.75 means the joint was out of range in 75% of pitches.
    flag_rate = (ratio >= 1.0).mean(axis=0)

    avg_sev  = [severity(float(r)) for r in avg_ratio]
    avg_rank = np.array([SEVERITY_RANK[s] for s in avg_sev], dtype=float)

    # worst joint = highest severity, tie-broken by avg_ratio
    worst_i  = int(np.argmax(avg_rank + avg_ratio * 0.01))

    history = [(p["pitch_number"], p["verdict"], p["main_issue"], p["mse"])
               for p in pitches]

    return {
        "n_pitches":   n,
        "correct":     correct,
        "accuracy":    accuracy,
        "threshold":   threshold,
        "mse_val":     mse_val,
        "mse_mean":    float(np.mean(mse_val)),
        "mse_std":     float(np.std(mse_val)),
        "joint_names": joint_names,
        "avg_ratio":   avg_ratio.tolist(),
        "flag_rate":   flag_rate.tolist(),
        "avg_sev":     avg_sev,
        "avg_rank":    avg_rank.tolist(),
        "worst_i":     worst_i,
        "history":     history,
    }


#SUMMARY (TEXT ONLY)
def print_summary(title: str, stats: dict):
    print(f"\n=== PITCH SESSION SUMMARY: {title} ===")
    print(f"Total pitches: {stats['n_pitches']}")
    print(f"Correct form:  {stats['correct']}")
    print(f"Accuracy:      {stats['accuracy']:.1f}%")
    print(f"Avg MSE:       {stats['mse_mean']:.5f} +/-{stats['mse_std']:.5f}  (threshold: {stats['threshold']:.5f})")

    worst_i = stats["worst_i"]
    wname   = stats["joint_names"][worst_i]
    wratio  = stats["avg_ratio"][worst_i]
    wflag   = stats["flag_rate"][worst_i] * 100
    wsev    = stats["avg_sev"][worst_i]
    if wsev != "Normal":
        print(f"\n  !! WORST JOINT: {wname}")
        print(f"     Severity:   {wsev}")
        print(f"     Avg ratio:  {wratio:.3f}x threshold  "
              f"({(wratio - 1) * 100:.0f}% over limit on average)")
        print(f"     Flagged in: {wflag:.0f}% of pitches  "
              f"({int(round(wflag / 100 * stats['n_pitches']))}/{stats['n_pitches']} pitches exceeded threshold)")

    print("\nPitch history:")
    for num, verdict, issue, mse in stats["history"]:
        label     = "Correct" if verdict == "Correct Form" else "Incorrect"
        issue_str = f"  [{issue}]" if issue else ""
        print(f"  #{num:<3}  {label:<9}  MSE={mse:.5f}{issue_str}")

    print()


#COMBINED SKELETON
def build_combined_skeleton(stats: dict, images_folder: Path, out_path: Path) -> None:
    """
    Merge all 9 joint-severity images into a single skeleton PNG.

    Strategy
    --------
    Every per-joint image is a full-body render with only that joint coloured;
    the rest of the body is neutral grey. We:
      1. Load all 9 images (resize to a common size).
      2. Build a clean base skeleton by taking the per-channel median across
         all 9 images — coloured highlights cancel out, leaving the pure grey body.
      3. For each image, detect highlighted pixels (pixels whose HSV saturation
         or brightness differs from the base) and copy them onto the canvas.
      4. Add a legend panel and footer stats alongside the merged skeleton.
    """
    if not CV2_AVAILABLE:
        print("[warn] opencv-python not installed — skipping combined skeleton.")
        return

    SIZE = 480

    joint_names = stats["joint_names"]
    avg_sev     = stats["avg_sev"]

    # 1. Load every joint image
    frames: list = []
    missing = []
    for idx, (name, sev) in enumerate(zip(joint_names, avg_sev)):
        filename = f"{name.lower().replace(' ', '_')}_{sev.lower()}.png"
        img_path = images_folder / filename
        if img_path.exists():
            raw = cv2.imread(str(img_path))
            if raw is not None:
                frames.append(cv2.resize(raw, (SIZE, SIZE), interpolation=cv2.INTER_AREA))
                continue
        missing.append((idx, name, sev))
        frames.append(None)

    if missing:
        print(f"  [warn] {len(missing)} image(s) missing for combined skeleton:")
        for idx, name, sev in missing:
            print(f"    {name.lower().replace(' ', '_')}_{sev.lower()}.png")

    valid_frames = [f for f in frames if f is not None]
    if not valid_frames:
        print("[error] No joint images could be loaded — aborting combined skeleton.")
        return

    # 2. Median base = clean grey skeleton (highlights cancel out)
    stack = np.stack(valid_frames, axis=0).astype(np.float32)
    base  = np.median(stack, axis=0).astype(np.uint8)

    base_hsv = cv2.cvtColor(base, cv2.COLOR_BGR2HSV).astype(np.float32)

    # 3. Composite highlighted regions from each joint frame
    canvas = base.copy()

    SAT_THRESHOLD      = 40
    SAT_DELTA          = 10
    VAL_DIFF_THRESHOLD = 30

    kernel = np.ones((3, 3), np.uint8)

    for frame in frames:
        if frame is None:
            continue
        frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)

        sat_diff = frame_hsv[:, :, 1] - base_hsv[:, :, 1]
        val_diff = np.abs(frame_hsv[:, :, 2] - base_hsv[:, :, 2])

        highlight_mask = (
            (frame_hsv[:, :, 1] > SAT_THRESHOLD) & (sat_diff > SAT_DELTA)
        ) | (
            (val_diff > VAL_DIFF_THRESHOLD) & (frame_hsv[:, :, 1] > 20)
        )

        highlight_mask = cv2.dilate(
            highlight_mask.astype(np.uint8), kernel, iterations=1
        ).astype(bool)

        canvas[highlight_mask] = frame[highlight_mask]

    # 4. Final canvas: dark bg + skeleton + legend + footer
    LEGEND_W = 190
    PAD      = 20
    HEADER_H = 46
    FOOTER_H = 36

    total_w = PAD + SIZE + PAD + LEGEND_W + PAD
    total_h = HEADER_H + PAD + SIZE + PAD + FOOTER_H

    final = np.full((total_h, total_w, 3), (18, 18, 18), dtype=np.uint8)

    sx, sy = PAD, HEADER_H + PAD
    final[sy:sy + SIZE, sx:sx + SIZE] = canvas

    cv2.putText(final, "COMBINED JOINT SEVERITY",
                (PAD, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, (210, 210, 210), 2, cv2.LINE_AA)

    lx       = PAD + SIZE + PAD
    ly_start = HEADER_H + PAD + 10
    row_h    = max(1, (SIZE - 10) // len(joint_names))

    worst_i = stats["worst_i"]

    for idx, (name, sev) in enumerate(zip(joint_names, avg_sev)):
        color     = SEVERITY_COLORS[sev]
        ly        = ly_start + idx * row_h
        is_worst  = (idx == worst_i and sev != "Normal")

        # Highlight worst joint row with a background band
        if is_worst:
            cv2.rectangle(final,
                          (lx, ly - 2), (lx + LEGEND_W - PAD, ly + row_h - 4),
                          (40, 40, 40), -1)
            cv2.rectangle(final,
                          (lx, ly - 2), (lx + LEGEND_W - PAD, ly + row_h - 4),
                          color, 1)

        dot_r = 8 if is_worst else 6
        cv2.circle(final, (lx + 10, ly + 10), dot_r, color, -1)

        name_color = (255, 255, 255) if is_worst else (195, 195, 195)
        cv2.putText(final, name,
                    (lx + 24, ly + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, name_color, 1, cv2.LINE_AA)
        cv2.putText(final, sev,
                    (lx + 24, ly + 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, color, 1, cv2.LINE_AA)

        # flag_rate = fraction of pitches where joint exceeded threshold
        n_flagged = int(round(stats["flag_rate"][idx] * stats["n_pitches"]))
        flag_str  = f"{stats['flag_rate'][idx] * 100:.0f}% of pitches ({n_flagged}/{stats['n_pitches']})"
        cv2.putText(final, flag_str,
                    (lx + 24, ly + 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.26, (90, 90, 90), 1, cv2.LINE_AA)

        if is_worst:
            badge = "WORST JOINT"
            (bw, _), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.28, 1)
            bx = lx + 24
            by = ly + 47
            cv2.rectangle(final, (bx - 2, by - 10), (bx + bw + 2, by + 2), color, -1)
            cv2.putText(final, badge, (bx, by),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28, (10, 10, 10), 1, cv2.LINE_AA)

    acc_str = (f"Accuracy: {stats['accuracy']:.1f}%"
               f"  ({stats['correct']}/{stats['n_pitches']} correct)"
               f"  |  Avg MSE: {stats['mse_mean']:.5f}")
    cv2.putText(final, acc_str, (PAD, total_h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140, 140, 140), 1, cv2.LINE_AA)

    # Worst joint callout banner overlaid at the bottom of the skeleton panel
    worst_i   = stats["worst_i"]
    worst_sev = avg_sev[worst_i]
    if worst_sev != "Normal":
        wname   = joint_names[worst_i]
        wratio  = stats["avg_ratio"][worst_i]
        wflag   = stats["flag_rate"][worst_i] * 100
        wcolor  = SEVERITY_COLORS[worst_sev]
        banner  = (f"WORST: {wname}  |  {worst_sev}  "
                   f"|  {wratio:.2f}x avg  |  flagged {wflag:.0f}% of pitches")
        bx = PAD
        by = sy + SIZE - 6
        (bw, bh), _ = cv2.getTextSize(banner, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)
        cv2.rectangle(final, (bx - 2, by - bh - 4), (bx + bw + 4, by + 4), (30, 30, 30), -1)
        cv2.rectangle(final, (bx - 2, by - bh - 4), (bx + bw + 4, by + 4), wcolor, 1)
        cv2.putText(final, banner, (bx, by),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, wcolor, 1, cv2.LINE_AA)

    cv2.imwrite(str(out_path), final)
    print(f"Combined skeleton saved → {out_path}")


#MAIN
def main():
    parser = argparse.ArgumentParser(
        description="Summarise pitch session log(s) produced by live_capture.py"
    )
    parser.add_argument(
        "path",
        help="Path to a session JSON file, or a folder to summarise all sessions in it",
    )
    parser.add_argument(
        "--images",
        default=None,
        metavar="FOLDER",
        help=(
            "Path to the folder containing the 45 joint-severity images "
            "(e.g. left_elbow_normal.png, pelvis_critical.png). "
            "When supplied, a combined skeleton PNG is saved alongside each session JSON."
        ),
    )
    args       = parser.parse_args()
    target     = Path(args.path)
    images_dir = Path(args.images) if args.images else None

    if images_dir and not images_dir.is_dir():
        print(f"[warn] --images folder '{images_dir}' does not exist — skipping visuals.")
        images_dir = None

    def save_skeleton_png(stats: dict, label: str, base_path: Path):
        if images_dir is None:
            return
        out_png = base_path.parent / f"{base_path.stem}_combined_skeleton.png"
        print(f"\nBuilding combined skeleton for: {label}")
        build_combined_skeleton(stats, images_dir, out_png)

    # Single session file
    if target.is_file():
        data  = load_session(target)
        stats = compute_summary(data["pitches"])
        print_summary(target.name, stats)
        save_skeleton_png(stats, target.name, target)

    # Folder of session files
    elif target.is_dir():
        sessions = load_all_sessions(target)
        print(f"\nFound {len(sessions)} session(s) in {target}")

        all_pitches = []
        for path, data in sessions:
            all_pitches.extend(data["pitches"])
            stats = compute_summary(data["pitches"])
            print_summary(path.name, stats)
            save_skeleton_png(stats, path.name, path)

        if len(sessions) > 1:
            combined_stats = compute_summary(all_pitches)
            print(f"=== COMBINED SUMMARY ({len(all_pitches)} pitches across {len(sessions)} sessions) ===")
            print_summary("All sessions combined", combined_stats)

            if images_dir:
                out_png = target / "combined_skeleton.png"
                print("\nBuilding combined skeleton for all sessions...")
                build_combined_skeleton(combined_stats, images_dir, out_png)

    else:
        print(f"Error: '{target}' is not a file or directory.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()