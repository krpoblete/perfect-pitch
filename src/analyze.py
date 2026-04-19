import argparse
import pickle
import warnings
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import cv2

import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import RunningMode

from pathlib import Path

warnings.filterwarnings("ignore")

MODEL_DIR = Path("models")
OUTPUT_DIR = Path("output")
POSE_MODEL_DIR = Path("pose_landmarker_heavy.task")
FRAMES = 60
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

KEY_JOINTS = [
    (11, 13, 15), (12, 14, 16),  # L/R elbow
    (13, 11, 23), (14, 12, 24),  # L/R shoulder
    (11, 23, 25), (12, 24, 26),  # L/R hip
    (23, 25, 27), (24, 26, 28),  # L/R knee
    (23, 24, 26),                # pelvis
]

NUM_JOINTS = len(KEY_JOINTS)

JOINT_NAMES = [
    "Left Elbow", "Right Elbow",
    "Left Shoulder", "Right Shoulder",
    "Left Hip", "Right Hip",
    "Left Knee", "Right Knee", "Pelvis",
]

FEEDBACK = [
    "Check left elbow position during throw", "Check right elbow position during throw",
    "Check left shoulder alignment", "Check right shoulder alignment",
    "Adjust left hip posture and avoid excessive lean", "Adjust right hip posture and avoid excessive lean",
    "Keep left knee more stable", "Keep right knee more stable",
    "Keep hips more level and balanced",
]

KEYPOINT_LINES = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
    (24, 26), (26, 28), (27, 29), (27, 31), (28, 30),
    (28, 32), (15, 17), (15, 19), (16, 18), (16, 20),
]

CRITICAL_LIMIT  = 1
HIGH_LIMIT      = 2
MODERATE_LIMIT  = 3


LANDMARK_JOINTS = {i: [] for i in range(33)}
for feat_idx, triple in enumerate(KEY_JOINTS):
    for lm_idx in triple:
        LANDMARK_JOINTS[lm_idx].append(feat_idx)


# ─── Model ───────────────────────────────────────────────────────────────────

class LSTMEncoder(nn.Module):
    def __init__(self, input_size, hidden_size, latent_dim, num_layers):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True,
                            dropout=0.2 if num_layers > 1 else 0.0)
        self.fc = nn.Linear(hidden_size, latent_dim)

    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.fc(h[-1])

class LSTMDecoder(nn.Module):
    def __init__(self, latent_dim, hidden_size, output_size, seq_len, num_layers):
        super().__init__()
        self.seq_len = seq_len
        self.fc   = nn.Linear(latent_dim, hidden_size)
        self.lstm = nn.LSTM(hidden_size, hidden_size, num_layers, batch_first=True,
                            dropout=0.2 if num_layers > 1 else 0.0)
        self.out  = nn.Linear(hidden_size, output_size)

    def forward(self, z):
        h = self.fc(z).unsqueeze(1).expand(-1, self.seq_len, -1)
        decoded, _ = self.lstm(h)
        return self.out(decoded)

class LSTMAutoencoder(nn.Module):
    def __init__(self, input_size, hidden_size, latent_dim, seq_len, num_layers):
        super().__init__()
        self.encoder = LSTMEncoder(input_size, hidden_size, latent_dim, num_layers)
        self.decoder = LSTMDecoder(latent_dim, hidden_size, input_size, seq_len, num_layers)

    def forward(self, x):
        return self.decoder(self.encoder(x))


# ─── Pose Extraction ─────────────────────────────────────────────────────────

def joint_angle(a, b, c):
    ba = a - b
    bc = c - b
    cos_val = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cos_val, -1.0, 1.0))))

def resample(arr, target_len=FRAMES):
    if len(arr) == target_len:
        return arr.astype(np.float32)
    old_idx = np.arange(len(arr), dtype=np.float32)
    new_idx = np.linspace(0, len(arr) - 1, target_len, dtype=np.float32)
    flat    = arr.reshape(len(arr), -1)
    result  = np.stack([np.interp(new_idx, old_idx, flat[:, i]) for i in range(flat.shape[1])], axis=1)
    return result.reshape(target_len, *arr.shape[1:]).astype(np.float32)

def smooth(arr):
    kernel = np.array([1/3, 1/3, 1/3], dtype=np.float32)
    out = arr.copy()
    for j in range(arr.shape[1]):
        for c in range(arr.shape[2]):
            padded = np.pad(arr[:, j, c], (1, 1), mode="edge")
            out[:, j, c] = np.convolve(padded, kernel, mode="valid")
    return out

def extract_features(landmarks):
    angles = np.array([
        [joint_angle(frame[a], frame[b], frame[c]) for a, b, c in KEY_JOINTS]
        for frame in landmarks
    ], dtype=np.float32)
    return angles

def mp_settings():
    options = mp_vision.PoseLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(POSE_MODEL_DIR)),
        running_mode=RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.7,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    return mp_vision.PoseLandmarker.create_from_options(options)

def extract_pose(video_path):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    total_frames = 0
    world_lms    = []
    image_lms    = []

    with mp_settings() as detector:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts_ms  = int(total_frames * 1000 / fps)
            result = detector.detect_for_video(mp_img, ts_ms)
            if result.pose_world_landmarks and result.pose_landmarks:
                world_lms.append(np.array([[p.x, p.y, p.z] for p in result.pose_world_landmarks[0]], dtype=np.float32))
                image_lms.append(np.array([[p.x, p.y]      for p in result.pose_landmarks[0]],       dtype=np.float32))
            total_frames += 1

    cap.release()

    if len(world_lms) < 10:
        raise RuntimeError(f"Too few pose frames ({len(world_lms)}) in {Path(video_path).name}")

    world = smooth(resample(np.stack(world_lms), FRAMES))
    image = resample(np.stack(image_lms), FRAMES)
    return {"world": world, "image": image, "fps": fps,
            "size": (width, height), "n_frames": total_frames, "n_valid": len(world_lms)}


# ─── Scoring ─────────────────────────────────────────────────────────────────

def compute_scores(features, model):
    x = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        recon = model(x)

    error = ((x - recon) ** 2).squeeze(0).cpu().numpy()
    per_joint_frame = error[:, :NUM_JOINTS]
    joint_risks = per_joint_frame.mean(axis=0)
    mse = float(error.mean())
    return per_joint_frame, joint_risks, mse

def get_severity(risk, threshold):
    if   risk < threshold:            return "Normal"
    elif risk < 1.25 * threshold:      return "Elevated"
    elif risk < 1.5 * threshold:      return "Moderate"
    elif risk < 2.0 * threshold:      return "High"
    else:                             return "Critical"

def risk_color(risk, threshold):
    if   risk < threshold:            return (50, 205, 50)    # green        — Normal
    elif risk < 1.25 * threshold:      return (0, 215, 255)    # yellow       — Elevated
    elif risk < 1.5 * threshold:      return (0, 165, 255)    # light orange — Moderate
    elif risk < 2.0 * threshold:      return (0, 100, 255)    # orange       — High
    else:                             return (0, 0, 220)      # red          — Critical

def count_severity(joint_risks, joint_thresholds):
    n_critical = int(np.sum(joint_risks >= 2.0 * joint_thresholds))
    n_high     = int(np.sum((joint_risks >= 1.5 * joint_thresholds) & (joint_risks < 2.0 * joint_thresholds)))
    n_moderate = int(np.sum((joint_risks >= 1.25 * joint_thresholds) & (joint_risks < 1.5 * joint_thresholds)))
    n_elevated = int(np.sum((joint_risks >= joint_thresholds)        & (joint_risks < 1.25 * joint_thresholds)))
    return n_critical, n_high, n_moderate, n_elevated

def risk_rank(joint_risks, joint_thresholds):
    SEVERITY_RANK = {"Critical": 4, "High": 3, "Moderate": 2, "Elevated": 1, "Normal": 0}
    best_idx, best_tier, best_risk = None, -1, -1.0
    for i in range(NUM_JOINTS):
        sev  = get_severity(float(joint_risks[i]), float(joint_thresholds[i]))
        tier = SEVERITY_RANK[sev]
        if tier == 0:
            continue
        if tier > best_tier or (tier == best_tier and float(joint_risks[i]) > best_risk):
            best_idx, best_tier, best_risk = i, tier, float(joint_risks[i])
    return best_idx

def check_verdict(mse, threshold, joint_risks, joint_thresholds):
    n_critical, n_high, n_moderate, n_elevated = count_severity(joint_risks, joint_thresholds)
    label = f"Crit={n_critical}, High={n_high}, Mod={n_moderate}, Elev={n_elevated}"

    risk_score = n_critical * 1.5 + n_high * 1.25 + n_moderate * 1 + n_elevated * 0.5

    if mse <= threshold:
        return False, f"MSE within threshold. {label}", n_critical, n_high, n_moderate, n_elevated

    # MSE is above threshold — now check joint evidence to confirm
    if (n_critical >= CRITICAL_LIMIT or
        n_high     >= HIGH_LIMIT     or
        n_moderate >= MODERATE_LIMIT or
        risk_score >= 3):
        return True, f"High MSE + joint evidence. {label}", n_critical, n_high, n_moderate, n_elevated

    # MSE is elevated but joints don't confirm — flag only if MSE is significantly high
    if mse > threshold * 1.5:
        return True, f"MSE significantly exceeds threshold. {label}", n_critical, n_high, n_moderate, n_elevated

    return False, f"MSE above threshold but insufficient joint evidence. {label}", n_critical, n_high, n_moderate, n_elevated


# ─── Feedback ────────────────────────────────────────────────────────────────

def build_feedback_table(joint_risks, joint_thresholds):
    rows = []
    for i in range(NUM_JOINTS):
        risk   = float(joint_risks[i])
        thresh = float(joint_thresholds[i])
        rows.append({
            "Joint":     JOINT_NAMES[i],
            "Feedback":  FEEDBACK[i],
            "Risk":      round(risk, 6),
            "Threshold": round(thresh, 6),
            "Flagged":   risk > thresh,
            "Severity":  get_severity(risk, thresh),
        })
    SEVERITY_RANK = {"Critical": 4, "High": 3, "Moderate": 2, "Elevated": 1, "Normal": 0}
    df = pd.DataFrame(rows)
    df["_tier"] = df["Severity"].map(SEVERITY_RANK)
    df = df.sort_values(["_tier", "Risk"], ascending=[False, False]).drop(columns="_tier").reset_index(drop=True)
    return df

def print_summary(verdict, issue, reason, mse, threshold, n_critical, n_high, n_moderate, n_elevated, worst_joint, feedback_df):
    print(f"\n{'=' * 55}")
    print(f"  Verdict   : {verdict.upper()}")
    if issue:
        print(f"  Main Issue: {issue}")
    print(f"  Reason    : {reason}")
    print(f"  MSE       : {mse:.6f}  (threshold: {threshold:.6f})")
    print(f"  Joints    : Critical={n_critical}  High={n_high}  Moderate={n_moderate}  Elevated={n_elevated}")
    if worst_joint is not None:
        print(f"  Feedback  : {FEEDBACK[worst_joint]}")
    print(f"{'=' * 55}\n")
    print(feedback_df.to_string(index=False), "\n")


# ─── Draw ─────────────────────────────────────────────────────────────────────

def landmark_colors(frame_risk, joint_thresholds):
    norm_risk = np.zeros(33, dtype=np.float32)
    for lm_idx, feat_indices in LANDMARK_JOINTS.items():
        if feat_indices:
            scores = [frame_risk[i] / (joint_thresholds[i] + 1e-10) for i in feat_indices]
            norm_risk[lm_idx] = max(scores)
    return norm_risk

def norm_risk_color(norm_risk):
    if   norm_risk < 1.0:   return (50, 205, 50)    # green        — Normal
    elif norm_risk < 1.25:   return (0, 215, 255)    # yellow       — Elevated
    elif norm_risk < 1.5:   return (0, 165, 255)    # light orange — Moderate
    elif norm_risk < 2.0:   return (0, 100, 255)    # orange       — High
    else:                   return (0, 0, 220)       # red          — Critical

def draw_skeleton(frame, image_lms, lm_norm_risk):
    out = frame.copy()
    h, w = out.shape[:2]

    def pt(i):
        return int(image_lms[i, 0] * w), int(image_lms[i, 1] * h)

    for a, b in KEYPOINT_LINES:
        cv2.line(out, pt(a), pt(b), norm_risk_color(max(lm_norm_risk[a], lm_norm_risk[b])), 2, cv2.LINE_AA)

    for i in range(33):
        cv2.circle(out, pt(i), 4, norm_risk_color(lm_norm_risk[i]), -1, cv2.LINE_AA)
        cv2.circle(out, pt(i), 4, (255, 255, 255), 1, cv2.LINE_AA)

    return out

def draw_panel(frame, verdict, issue, frame_risk, joint_thresholds, feedback_df,
               frame_idx, total_frames, pitch_count=0, correct_count=0):
    out = frame.copy()
    fh, fw = out.shape[:2]
    pw    = 300
    panel = np.full((fh, pw, 3), (25, 25, 25), dtype=np.uint8)

    # Header
    header_color = (50, 205, 50) if verdict == "Correct Form" else (0, 0, 200)
    cv2.rectangle(panel, (0, 0), (pw, 46), header_color, -1)
    cv2.putText(panel, verdict[:22], (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)

    y = 62
    if issue:
        cv2.putText(panel, f"Issue: {issue[:20]}", (8, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 220), 1, cv2.LINE_AA)
        y = 78

    # Session accuracy bar
    cv2.putText(panel, "Session Accuracy", (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1, cv2.LINE_AA)
    if pitch_count > 0:
        acc = correct_count / pitch_count * 100
        acc_color = (50, 205, 50) if acc >= 70 else (0, 215, 255) if acc >= 50 else (0, 0, 220)
        y += 20
        bar_w = int((acc / 100.0) * (pw - 16))
        cv2.rectangle(panel, (8, y + 5), (pw - 8, y + 17), (70, 70, 70), -1)
        cv2.rectangle(panel, (8, y + 5), (8 + bar_w, y + 17), acc_color, -1)
        cv2.putText(panel, f"{correct_count}/{pitch_count} correct ({acc:.0f}%)",
                    (8, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.35, acc_color, 1, cv2.LINE_AA)
    else:
        cv2.putText(panel, "No pitches yet", (8, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 100), 1, cv2.LINE_AA)

    # Per-joint risk bars
    y = 108
    cv2.putText(panel, "Joint Risk (this frame)", (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1, cv2.LINE_AA)
    for i, name in enumerate(JOINT_NAMES):
        risk   = float(frame_risk[i])
        thresh = float(joint_thresholds[i])
        color  = risk_color(risk, thresh)
        norm  = min(risk / (2.0 * thresh + 1e-10), 1.0)
        bar_w = int(norm * 110)
        y += 18
        cv2.putText(panel, name, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (160, 160, 160), 1, cv2.LINE_AA)
        cv2.rectangle(panel, (76, y - 10), (186, y), (55, 55, 55), -1)
        cv2.rectangle(panel, (76, y - 10), (76 + bar_w, y), color, -1)
        cv2.putText(panel, f"{risk:.2f}", (190, y), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (140, 140, 140), 1, cv2.LINE_AA)

    # Top feedback
    y += 22
    cv2.putText(panel, "Top Movement Feedback", (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1, cv2.LINE_AA)
    for _, row in feedback_df.head(3).iterrows():
        y += 17
        color = risk_color(row["Risk"], row["Threshold"])
        cv2.putText(panel, row["Feedback"][:20], (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1, cv2.LINE_AA)
        cv2.putText(panel, row["Severity"],       (220, y), cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1, cv2.LINE_AA)

    cv2.putText(panel, f"Frame {frame_idx + 1}/{total_frames}", (8, fh - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 100, 100), 1, cv2.LINE_AA)

    out[:, fw - pw:fw] = cv2.addWeighted(panel, 0.70, out[:, fw - pw:fw], 0.30, 0)
    return out


# ─── Main Pipeline ───────────────────────────────────────────────────────────

def load_model():
    print("Loading model...")
    checkpoint = torch.load(MODEL_DIR / "lstm_autoencoder.pt", map_location=DEVICE, weights_only=False)
    cfg       = checkpoint["config"]
    threshold = checkpoint["threshold"]

    # Load per-joint thresholds saved during training.
    # Falls back to a flat multiplier of 1.0 for checkpoints that pre-date this change.
    if "joint_thresholds" in checkpoint:
        joint_thresholds = np.array(checkpoint["joint_thresholds"], dtype=np.float32)
    else:
        print("  [WARN] checkpoint has no joint_thresholds — falling back to global threshold for all joints.")
        joint_thresholds = np.full(NUM_JOINTS, threshold, dtype=np.float32)

    model = LSTMAutoencoder(
        cfg["input_size"], cfg["hidden_size"], cfg["latent_dim"],
        cfg["seq_len"], cfg["num_layers"]
    ).to(DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    with open(MODEL_DIR / "scaler.pkl", "rb") as f:
        scaler = pickle.load(f)

    return model, scaler, threshold, joint_thresholds


def write_output_video(video_path, out_path, fps, size, image_lms_full,
                       frame_risks_full, joint_thresholds, verdict, issue, feedback_df):
    print(f"Writing annotated video -> {out_path}")
    w, h   = size
    cap    = cv2.VideoCapture(str(video_path))
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    for i in range(len(frame_risks_full)):
        ok, frame = cap.read()
        if not ok:
            break
        lm_norm_risk = landmark_colors(frame_risks_full[i], joint_thresholds)
        frame = draw_skeleton(frame, image_lms_full[i], lm_norm_risk)
        frame = draw_panel(frame, verdict, issue, frame_risks_full[i], joint_thresholds,
                           feedback_df, i, len(frame_risks_full))
        writer.write(frame)

    cap.release()
    writer.release()
    print(f"Done. Open: {out_path}")


def analyze(video_path, out_path=None):
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = Path(out_path) if out_path else OUTPUT_DIR / f"annotated_{Path(video_path).stem}.mp4"

    model, scaler, threshold, joint_thresholds = load_model()

    print(f"Global threshold : {threshold:.6f}")
    print("Per-joint thresholds (from training data):")
    for name, jt in zip(JOINT_NAMES, joint_thresholds):
        print(f"  {name:<16} {jt:.6f}")

    print(f"Extracting pose from: {video_path}")
    pose = extract_pose(video_path)
    fps = pose["fps"]
    width, height = pose["size"]
    print(f"  {pose['n_valid']}/{pose['n_frames']} valid frames at {fps:.1f}fps ({width}x{height})")

    features        = extract_features(pose["world"])
    features_scaled = scaler.transform(features)

    frame_risks, joint_risks, mse = compute_scores(features_scaled, model)

    # Stretch frame-level data back to original video length for annotation
    frame_risks_full = resample(frame_risks, pose["n_frames"])
    image_lms_full   = resample(pose["image"], pose["n_frames"])

    is_incorrect, reason, n_critical, n_high, n_moderate, n_elevated = check_verdict(mse, threshold, joint_risks, joint_thresholds)
    verdict = "Incorrect Form" if is_incorrect else "Correct Form"

    worst_joint = risk_rank(joint_risks, joint_thresholds) if is_incorrect else None
    main_issue  = JOINT_NAMES[worst_joint] if worst_joint is not None else None

    feedback_df = build_feedback_table(joint_risks, joint_thresholds)

    print_summary(verdict, main_issue, reason, mse, threshold,
                  n_critical, n_high, n_moderate, n_elevated, worst_joint, feedback_df)

    write_output_video(video_path, out_path, fps, (width, height),
                       image_lms_full, frame_risks_full, joint_thresholds,
                       verdict, main_issue, feedback_df)

    return {
        "verdict":          verdict,
        "main_issue":       main_issue,
        "reason":           reason,
        "mse":              mse,
        "threshold":        threshold,
        "joint_risks":      joint_risks,
        "joint_thresholds": joint_thresholds,
        "feedback":         feedback_df,
        "output_path":      str(out_path),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze pitch form in a video.")
    parser.add_argument("video", help="Path to input video file")
    parser.add_argument("--out", default=None, help="Path for annotated output video")
    args = parser.parse_args()
    analyze(args.video, args.out)