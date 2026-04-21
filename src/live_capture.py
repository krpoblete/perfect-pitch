import argparse
import json
import pickle
import queue
import threading
import time
import warnings
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import torch

from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import RunningMode

from src.analyze import (
    LSTMAutoencoder,
    FRAMES,
    POSE_MODEL_DIR, MODEL_DIR, DEVICE,
    NUM_JOINTS, JOINT_NAMES, FEEDBACK,
    extract_features,
    compute_scores,
    check_verdict,
    risk_rank,
    resample,
    smooth,
    build_feedback_table,
    risk_color,
)

warnings.filterwarnings("ignore")

KEYPOINTS = [13, 14, 11, 12, 23, 24, 25, 26]
NOSE = 0
PELVIS = 32

JOINT_LANDMARKS = [
    (11, 13,  0),   # L.Shoulder -> L.Elbow
    (12, 14,  1),   # R.Shoulder -> R.Elbow
    (13, 15,  0),   # L.Elbow -> L.Wrist
    (14, 16,  1),   # R.Elbow -> R.Wrist
    (11, 12,  2),   # L.Shoulder <-> R.Shoulder
    (11, 23,  4),   # L.Shoulder -> L.Hip
    (12, 24,  5),   # R.Shoulder -> R.Hip
    (23, 24, -1),   # L.Hip <-> R.Hip
    (23, 25,  6),   # L.Hip -> L.Knee  
    (24, 26,  7),   # R.Hip -> R.Knee
]

def landmark_colors(joint_risks: np.ndarray, thresholds: np.ndarray) -> np.ndarray:

    out = np.zeros(33, dtype=np.float32)
    for j, dot in enumerate(KEYPOINTS):        
        out[dot] = float(joint_risks[j]) / (float(thresholds[j]) + 1e-10)
    out[PELVIS] = float(joint_risks[8]) / (float(thresholds[8]) + 1e-10)
    return out

def severity_color(ratio: float) -> tuple:
    if ratio < 1.0:
        return (50, 205, 50)#green(normal)
    if ratio < 1.25:
        return (0, 215, 255)#yellow(elevated)
    if ratio < 1.5:
        return (0, 165, 255)#light orange(moderate)
    if ratio < 2.0:
        return (0, 100, 255)#orange(high)
    return (0, 0, 220)#red(critical)

def draw_keypoints(frame: np.ndarray, screen_pts: np.ndarray,
                  dot_risk: np.ndarray) -> np.ndarray:
    if screen_pts is None:
        return frame.copy()

    out = frame.copy()
    frame_height, frame_width = out.shape[:2]

    def pixel(idx: int) -> tuple:
        if idx == PELVIS:                         
            lh, rh = screen_pts[23], screen_pts[24]
            return int((lh[0] + rh[0]) / 2 * frame_width), int((lh[1] + rh[1]) / 2 * frame_height)
        x, y = screen_pts[idx]
        return int(x * frame_width), int(y * frame_height)

    #segment
    for mp_a, mp_b, j_idx in JOINT_LANDMARKS:
        ratio = (dot_risk[PELVIS] if j_idx == -1
                 else dot_risk[KEYPOINTS[j_idx]])
        cv2.line(out, pixel(mp_a), pixel(mp_b),
                 severity_color(ratio), 2, cv2.LINE_AA)

    #landmarks
    for dot in [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 32]:
        color = severity_color(dot_risk[dot])
        size = 3 if dot == NOSE else 5
        cv2.circle(out, pixel(dot), size, color, -1, cv2.LINE_AA)
        cv2.circle(out, pixel(dot), size, (0, 0, 0),  1, cv2.LINE_AA)

    return out

#camera settings
DETECT_WIDTH  = 134
DETECT_HEIGHT = 75 

EMA_ALPHA     = 0.5
VELOCITY_GAIN = 0.4

#pitchflow
COUNTDOWN_SECS = 3
MAX_PITCH_FRAMES = 90

#live alert
INFER_EVERY      = 10
ALERT_RISK_RATIO = 1.5

COOLDOWN = 10

from src.config import ROOT_DIR
LOG_DIR = ROOT_DIR / "output" 

SHORT_NAMES = [
    "L.Elbow",    "R.Elbow",
    "L.Shoulder", "R.Shoulder",
    "L.Hip",      "R.Hip",
    "L.Knee",     "R.Knee",
    "Pelvis",
]

#pitching state
WAITING    = "waiting"
COUNTDOWN  = "countdown"
COLLECTING = "collecting"
ANALYZING  = "analyzing"
POST_PITCH = "post_pitch"


#camera thread
class CameraThread(threading.Thread):

    def __init__(self, cap: cv2.VideoCapture):
        super().__init__(daemon=True)
        self._cap  = cap
        self._q    = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self.ok    = True

    def run(self):
        while not self._stop.is_set():
            ret, frame = self._cap.read()
            if not ret:
                self.ok = False
                break
            if self._q.full():
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    pass
            self._q.put(frame)

    def read(self):
        try:
            return True, self._q.get(timeout=0.05)
        except queue.Empty:
            return self.ok, None

    def stop(self):
        self._stop.set()


# ── Panel helpers ──────────────────────────────────────────────────────────────

def side_panel(fh: int, pw: int) -> np.ndarray:
    return np.full((fh, pw, 3), (25, 25, 25), dtype=np.uint8)


def blend_panel(frame: np.ndarray, panel: np.ndarray) -> np.ndarray:
    fw  = frame.shape[1]
    pw  = panel.shape[1]
    out = frame.copy()
    roi = out[:, fw - pw:]
    cv2.addWeighted(panel, 0.70, roi, 0.30, 0, roi)
    return out


# ── Overlays ───────────────────────────────────────────────────────────────────

def draw_waiting_overlay(frame: np.ndarray) -> np.ndarray:
    fh, fw = frame.shape[:2]
    pw     = 300
    panel  = side_panel(fh, pw)
    cv2.rectangle(panel, (0, 0), (pw, 46), (60, 60, 60), -1)
    cv2.putText(panel, "Waiting for pitcher", (8, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
    for i, line in enumerate(["Step into frame.", "", "R = reset", "Q = quit"]):
        cv2.putText(panel, line, (8, 70 + i * 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (140, 140, 140), 1, cv2.LINE_AA)
    return blend_panel(frame, panel)


def draw_countdown_overlay(frame: np.ndarray, screen_pts: np.ndarray,
                            secs_left: float) -> np.ndarray:
    out     = draw_keypoints(frame, screen_pts, np.zeros(33))
    fh, fw  = out.shape[:2]
    overlay = out.copy()
    cx, cy  = fw // 2, fh // 2
    cv2.circle(overlay, (cx, cy), 70, (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, out, 0.45, 0, out)
    number      = str(max(1, int(np.ceil(secs_left))))
    (tw, th), _ = cv2.getTextSize(number, cv2.FONT_HERSHEY_SIMPLEX, 3.5, 6)
    cv2.putText(out, number, (cx - tw // 2, cy + th // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 3.5, (50, 220, 50), 6, cv2.LINE_AA)
    cv2.putText(out, "Get ready to pitch...", (cx - 95, cy + 95),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
    pw    = 300
    panel = side_panel(fh, pw)
    cv2.rectangle(panel, (0, 0), (pw, 46), (60, 100, 60), -1)
    cv2.putText(panel, "Pitcher detected!", (8, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(panel, f"Recording in {secs_left:.1f}s", (8, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 200, 160), 1, cv2.LINE_AA)
    cv2.putText(panel, "R = cancel  |  Q = quit", (8, fh - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.33, (80, 80, 80), 1, cv2.LINE_AA)
    return blend_panel(out, panel)


def draw_collecting_overlay(frame: np.ndarray, n_collected: int, fps_live: float,
                              screen_pts: np.ndarray, thresholds: np.ndarray,
                              early_risk, alert_joint) -> np.ndarray:
    if alert_joint is not None:
        cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, frame.shape[0] - 1),
                      (0, 0, 220), 6)

    dot_risk = (landmark_colors(early_risk, thresholds)
               if early_risk is not None else np.zeros(33, dtype=np.float32))
    out    = draw_keypoints(frame, screen_pts, dot_risk)
    fh, fw = out.shape[:2]
    pw     = 300
    panel  = side_panel(fh, pw)

    hdr    = (0, 0, 200) if alert_joint else (110, 50, 20)
    cv2.rectangle(panel, (0, 0), (pw, 46), hdr, -1)
    header = f"ALERT: {alert_joint[:14]}" if alert_joint else "Recording pitch..."
    cv2.putText(panel, header, (8, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

    progress = n_collected / MAX_PITCH_FRAMES
    bar_w    = int(progress * (pw - 16))
    cv2.putText(panel, f"{n_collected}/{MAX_PITCH_FRAMES} frames  ({fps_live:.0f} fps)", (8, 56),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 120, 120), 1, cv2.LINE_AA)
    cv2.rectangle(panel, (8, 62), (pw - 8, 72), (55, 55, 55), -1)
    cv2.rectangle(panel, (8, 62), (8 + bar_w, 72), (80, 160, 80), -1)

    if early_risk is not None:
        y = 86
        cv2.putText(panel, "Live Joint Risk", (8, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 180, 180), 1, cv2.LINE_AA)
        for k in range(NUM_JOINTS):
            risk   = float(early_risk[k])
            thresh = float(thresholds[k])
            color  = risk_color(risk, thresh)
            bw     = int(min(risk / (2.0 * thresh + 1e-10), 1.0) * 110)
            y     += 16
            cv2.putText(panel, SHORT_NAMES[k], (8, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28, (160, 160, 160), 1, cv2.LINE_AA)
            cv2.rectangle(panel, (76, y - 10), (186, y), (55, 55, 55), -1)
            cv2.rectangle(panel, (76, y - 10), (76 + bw, y), color, -1)
            cv2.putText(panel, f"{risk:.3f}", (190, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.26, (140, 140, 140), 1, cv2.LINE_AA)
    else:
        cv2.putText(panel, "Warming up...", (8, 94),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, (100, 100, 100), 1, cv2.LINE_AA)

    cv2.putText(panel, "R = reset", (8, fh - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.33, (80, 80, 80), 1, cv2.LINE_AA)
    return blend_panel(out, panel)


def draw_post_pitch_overlay(frame: np.ndarray, result: dict, secs_left: float,
                             n_pitches: int, n_correct: int,
                             screen_pts: np.ndarray = None) -> np.ndarray:
    thresholds = result["thresholds"]
    if screen_pts is not None:
        dot_risk = landmark_colors(result["joint_risks"], thresholds)
        out = draw_keypoints(frame, screen_pts, dot_risk)
    else:
        out = frame.copy()

    fh, fw = out.shape[:2]
    pw     = 300
    panel  = side_panel(fh, pw)

    is_correct = result["verdict"] == "Correct Form"
    cv2.rectangle(panel, (0, 0), (pw, 46),
                  (50, 205, 50) if is_correct else (0, 0, 200), -1)
    cv2.putText(panel, result["verdict"][:22], (8, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)

    if result["main_issue"]:
        cv2.putText(panel, f"Issue: {result['main_issue'][:20]}", (8, 48),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, (220, 220, 220), 1, cv2.LINE_AA)

    y = 60
    if n_pitches > 0:
        acc     = n_correct / n_pitches * 100
        acc_col = (50, 205, 50) if acc >= 70 else (0, 215, 255) if acc >= 50 else (0, 0, 220)
        bw      = int((acc / 100.0) * (pw - 16))
        cv2.putText(panel, f"{n_correct}/{n_pitches} correct ({acc:.0f}%)", (8, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, acc_col, 1, cv2.LINE_AA)
        cv2.rectangle(panel, (8, y + 4), (pw - 8, y + 14), (70, 70, 70), -1)
        cv2.rectangle(panel, (8, y + 4), (8 + bw, y + 14), acc_col, -1)

    y = 82
    cv2.putText(panel, "Joint Risk (this pitch)", (8, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 180, 180), 1, cv2.LINE_AA)
    for k in range(NUM_JOINTS):
        risk   = float(result["joint_risks"][k])
        thresh = float(thresholds[k])
        color  = risk_color(risk, thresh)
        bw     = int(min(risk / (2.0 * thresh + 1e-10), 1.0) * 110)
        y     += 17
        cv2.putText(panel, SHORT_NAMES[k], (8, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, (160, 160, 160), 1, cv2.LINE_AA)
        cv2.rectangle(panel, (76, y - 10), (186, y), (55, 55, 55), -1)
        cv2.rectangle(panel, (76, y - 10), (76 + bw, y), color, -1)
        cv2.putText(panel, f"{risk:.3f}", (190, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.28, (140, 140, 140), 1, cv2.LINE_AA)

    y += 18
    cv2.putText(panel, "Top Feedback", (8, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 180, 180), 1, cv2.LINE_AA)
    for _, row in result["feedback_df"].head(3).iterrows():
        y += 17
        color = risk_color(row["Risk"], row["Threshold"])
        cv2.putText(panel, row["Feedback"][:20], (8, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, color, 1, cv2.LINE_AA)
        cv2.putText(panel, row["Severity"], (220, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, color, 1, cv2.LINE_AA)

    y += 20
    cv2.putText(panel, f"Next pitch in {secs_left:.1f}s", (8, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1, cv2.LINE_AA)
    prog  = max(0.0, 1.0 - secs_left / COOLDOWN)
    bar_w = int(prog * (pw - 16))
    cv2.rectangle(panel, (8, y + 6), (pw - 8, y + 16), (60, 60, 60), -1)
    cv2.rectangle(panel, (8, y + 6), (8 + bar_w, y + 16), (80, 160, 80), -1)
    cv2.putText(panel, "R = reset now", (8, fh - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.33, (80, 80, 80), 1, cv2.LINE_AA)

    return blend_panel(out, panel)

#landmark smoother
class LandmarkSmoother:
    def __init__(self, alpha: float = EMA_ALPHA, vel_gain: float = VELOCITY_GAIN):
        self.alpha    = alpha
        self.vel_gain = vel_gain
        self._pts     = None
        self._vel     = None

    def update(self, new_pts: np.ndarray) -> np.ndarray:
        if self._pts is None:
            self._pts = new_pts.copy()
            self._vel = np.zeros_like(new_pts)
        else:
            delta     = new_pts - self._pts
            self._vel = 0.6 * self._vel + 0.4 * delta
            self._pts = self.alpha * new_pts + (1.0 - self.alpha) * self._pts
        return self._pts.copy()

    def predict(self) -> np.ndarray | None:
        if self._pts is None:
            return None
        self._pts = self._pts + self.vel_gain * self._vel
        return self._pts.copy()

    def reset(self):
        self._pts = None
        self._vel = None

    @property
    def ready(self) -> bool:
        return self._pts is not None


#main
def run_live(camera_id: int = 0, width: int = 1280, height: int = 720):

    #model
    print("Loading model...")
    ckpt      = torch.load(MODEL_DIR / "lstm_autoencoder.pt",
                           map_location=DEVICE, weights_only=False)
    cfg       = ckpt["config"]
    threshold = ckpt["threshold"]

    ae = LSTMAutoencoder(
        input_size=cfg["input_size"], hidden_size=cfg["hidden_size"],
        latent_dim=cfg["latent_dim"], seq_len=cfg["seq_len"],
        num_layers=cfg["num_layers"],
    ).to(DEVICE)
    ae.load_state_dict(ckpt["model_state_dict"])
    ae.eval()

    with open(MODEL_DIR / "scaler.pkl", "rb") as f:
        scaler = pickle.load(f)

    thresholds = (
        np.array(ckpt["joint_thresholds"], dtype=np.float32)
        if "joint_thresholds" in ckpt
        else np.full(NUM_JOINTS, threshold, dtype=np.float32)
    )
    if "joint_thresholds" not in ckpt:
        print("No joint_thresholds in checkpoint. Using global threshold.")
    print(f"Threshold : {threshold:.6f}")
    print(f"Per-joint : {dict(zip(SHORT_NAMES, thresholds.round(5)))}")
    print(f"Device    : {DEVICE}")

    #camera
    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {camera_id}")

    print(f"Camera    : {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
          f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ "
          f"{cap.get(cv2.CAP_PROP_FPS):.0f}fps  |  R = reset  |  Q = quit")

    cam_thread = CameraThread(cap)
    cam_thread.start()

    # ── MediaPipe — LIVE_STREAM ────────────────────────────────────────────────
    result_list    = [None]
    result_lock = threading.Lock()
    result_ts_list = [0]

    def onresult_list(result, output_image, timestamp_ms):
        with result_lock:
            if timestamp_ms >= result_ts_list[0]:
                result_list[0]    = result
                result_ts_list[0] = timestamp_ms

    options = mp_vision.PoseLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(POSE_MODEL_DIR)),
        running_mode=RunningMode.LIVE_STREAM,
        result_callback=onresult_list,
        num_poses=1,
        min_pose_detection_confidence=0.7,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = mp_vision.PoseLandmarker.create_from_options(options)

    cv2.namedWindow("Live Pitch Analysis", cv2.WINDOW_NORMAL)
    t0 = time.perf_counter()

    # ── Session counters ───────────────────────────────────────────────────────
    n_pitches   = 0
    n_correct   = 0
    frame_count = 0

    # ── Session log ────────────────────────────────────────────────────────────
    LOG_DIR.mkdir(exist_ok=True)
    session_start = datetime.now()
    log_path      = LOG_DIR / f"session_{session_start.strftime('%Y%m%d_%H%M%S')}.json"
    session_log   = []

    # ── Per-pitch state ────────────────────────────────────────────────────────
    state          = WAITING
    cd_start       = None   # countdown start time
    post_start     = None   # post-pitch cooldown start time
    lastresult_list    = None
    world_pts      = None
    image_pts      = None
    smoother       = LandmarkSmoother()


    world_frames        = []
    screen_frames        = []
    since_infer = 0
    early_risk  = None
    alert_joint = None

    seen_ts = [-1]

    def reset():
        nonlocal state, cd_start, post_start, lastresult_list
        nonlocal world_pts, image_pts
        nonlocal world_frames, screen_frames, since_infer, early_risk, alert_joint
        state       = WAITING
        cd_start    = None
        post_start  = None
        lastresult_list = None
        world_pts   = None
        image_pts   = None
        world_frames        = []
        screen_frames        = []
        since_infer = 0
        early_risk  = None
        alert_joint = None
        smoother.reset()

    print("Live capture — step into frame to begin.  R = reset  Q = quit\n")

    while True:
        cam_ok, frame = cam_thread.read()
        if not cam_ok:
            print("Camera thread stopped — exiting.")
            break
        if frame is None:
            continue

        frame        = cv2.flip(frame, 1)
        frame_count += 1
        ts_ms        = int((time.perf_counter() - t0) * 1000)

        small  = cv2.resize(frame, (DETECT_WIDTH, DETECT_HEIGHT))
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB,
                          data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        landmarker.detect_async(mp_img, ts_ms)

        with result_lock:
            detection = result_list[0]
            result_ts = result_ts_list[0]

        new_detection = (result_ts > seen_ts[0])
        if new_detection:
            seen_ts[0] = result_ts

        person_seen = bool(detection and detection.pose_world_landmarks
                           and detection.pose_landmarks)

        if person_seen:
            world_pts = np.array([[lm.x, lm.y, lm.z]
                                   for lm in detection.pose_world_landmarks[0]],
                                  dtype=np.float32)
            image_pts = np.array([[lm.x, lm.y]
                                   for lm in detection.pose_landmarks[0]],
                                  dtype=np.float32)

        if person_seen and new_detection:
            display_lm = smoother.update(image_pts)
        elif smoother.ready:
            display_lm = smoother.predict()
        else:
            display_lm = None

        fps_live = frame_count / max(time.perf_counter() - t0, 1e-6)

        # ── State machine ──────────────────────────────────────────────────────

        if state == WAITING:
            if person_seen:
                state    = COUNTDOWN
                cd_start = time.perf_counter()

        elif state == COUNTDOWN:
            if not person_seen:
                state = WAITING
            else:
                if time.perf_counter() - cd_start >= COUNTDOWN_SECS:
                    state       = COLLECTING
                    world_frames  = []
                    screen_frames = []
                    since_infer = 0
                    early_risk  = None
                    alert_joint = None
                    print("Recording...")

        elif state == COLLECTING:
            if person_seen:
                world_frames.append(world_pts)
                screen_frames.append(image_pts)

            n = len(world_frames)

            since_infer += 1
            if n >= FRAMES // 2 and since_infer >= INFER_EVERY:
                since_infer = 0
                world_arr   = smooth(resample(np.stack(world_frames), FRAMES))
                feat        = extract_features(world_arr)
                feat_scaled = scaler.transform(feat)
                _, early_risk, _ = compute_scores(feat_scaled, ae)
                worst       = int(np.argmax(early_risk / (thresholds + 1e-10)))
                alert_joint = (SHORT_NAMES[worst]
                               if early_risk[worst] >= ALERT_RISK_RATIO * thresholds[worst]
                               else None)

            if n >= MAX_PITCH_FRAMES:
                state = ANALYZING

        elif state == ANALYZING:
            world_arr   = smooth(resample(np.stack(world_frames), FRAMES))
            feat        = extract_features(world_arr)
            feat_scaled = scaler.transform(feat)
            _, joint_risks, mse = compute_scores(feat_scaled, ae)

            print(f"  MSE={mse:.5f}  threshold={threshold:.5f}")

            is_incorrect, reason, *_ = check_verdict(mse, threshold, joint_risks, thresholds)
            verdict = "Incorrect Form" if is_incorrect else "Correct Form"
            worst_joint = risk_rank(joint_risks, thresholds) if is_incorrect else None
            main_issue = JOINT_NAMES[worst_joint] if worst_joint is not None else None
            print(f"  {reason}")

            feedback_df = build_feedback_table(joint_risks, thresholds)

            lastresult_list = {
                "verdict": verdict,
                "main_issue": main_issue,
                "joint_risks": joint_risks,
                "thresholds": thresholds,
                "feedback_df": feedback_df,
                "n_frames": len(world_frames),
            }

            n_pitches += 1
            if verdict == "Correct Form":
                n_correct += 1
            print(f"Pitch {n_pitches}: {verdict}"
                  f"({n_correct}/{n_pitches} correct)"
                  f"[{len(world_frames)} frames | MSE={mse:.5f}]")
            if main_issue:
                print(f"Issue: {main_issue}")

            #pitch logging
            pitch_record = {
                "pitch_number": n_pitches,
                "timestamp": datetime.now().isoformat(),
                "verdict": verdict,
                "main_issue": main_issue,
                "reason": reason,
                "mse": round(float(mse), 6),
                "threshold": round(float(threshold), 6),
                "n_frames": len(world_frames),
                "joint_names": JOINT_NAMES,
                "joint_risks": [round(float(r), 6) for r in joint_risks],
                "joint_thresholds": [round(float(t), 6) for t in thresholds],
                "joint_severities": [str(row["Severity"]) for _, row in
                                     feedback_df.sort_values("Joint").iterrows()],
            }
            session_log.append(pitch_record)
            with open(log_path, "w") as f:
                json.dump({
                    "session_start": session_start.isoformat(),
                    "pitches": session_log,
                }, f, indent=2)
            print(f"Logged to {log_path}")

            state      = POST_PITCH
            post_start = time.perf_counter()
            early_risk = None
            alert_joint = None

        elif state == POST_PITCH:
            if time.perf_counter() - post_start >= COOLDOWN:
                reset()
                print("Ready for next pitch.\n")

        #display
        lm = display_lm if display_lm is not None else (screen_frames[-1] if screen_frames else None)

        if state == WAITING:
            display = draw_waiting_overlay(frame)

        elif state == COUNTDOWN:
            secs    = max(0.0, COUNTDOWN_SECS - (time.perf_counter() - cd_start))
            display = (draw_countdown_overlay(frame, lm, secs)
                       if lm is not None else frame.copy())

        elif state == COLLECTING:
            display = (draw_collecting_overlay(
                frame, len(world_frames), fps_live, lm,
                thresholds, early_risk, alert_joint,
            ) if lm is not None else frame.copy())

        elif state == ANALYZING:
            display = (draw_keypoints(frame, lm, np.zeros(33))
                       if lm is not None else frame.copy())
            cv2.putText(display, "Analyzing...", (20, display.shape[0] // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 215, 255), 2, cv2.LINE_AA)

        else:
            secs    = max(0.0, COOLDOWN - (time.perf_counter() - post_start))
            display = draw_post_pitch_overlay(frame, lastresult_list, secs,
                                              n_pitches, n_correct, lm)

        cv2.putText(display, f"FPS {fps_live:.1f}", (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.imshow("Live Pitch Analysis", display)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("r"):
            reset()
            print("Reset, waiting for pitcher.")

    cam_thread.stop()
    landmarker.close()
    cap.release()
    cv2.destroyAllWindows()
    print(f"Session ended — {n_pitches} pitches, {n_correct} correct.")
    if session_log:
        print(f"Session log saved → {log_path}")
        print(f"Run: python pitch_summary.py {log_path}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real-time pitch form analysis.")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width",  type=int, default=1340)
    parser.add_argument("--height", type=int, default=754)
    args = parser.parse_args()
    run_live(camera_id=args.camera, width=args.width, height=args.height)