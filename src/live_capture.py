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
    (25, 27,  6),   # L.Knee -> L.Ankle  (inherits L.Knee severity)
    (26, 28,  7),   # R.Knee -> R.Ankle  (inherits R.Knee severity)
]

def landmark_colors(joint_risks: np.ndarray, thresholds: np.ndarray) -> np.ndarray:

    out = np.zeros(33, dtype=np.float32)
    for j, dot in enumerate(KEYPOINTS):
        out[dot] = float(joint_risks[j]) / (float(thresholds[j]) + 1e-10)
    out[PELVIS] = float(joint_risks[8]) / (float(thresholds[8]) + 1e-10)
    # Ankles inherit knee severity — visual extension only
    out[27] = float(joint_risks[6]) / (float(thresholds[6]) + 1e-10)  # L.Ankle = L.Knee
    out[28] = float(joint_risks[7]) / (float(thresholds[7]) + 1e-10)  # R.Ankle = R.Knee
    return out

def severity_color(ratio: float) -> tuple:
    if ratio < 1.0:
        return (50, 205, 50)    # green   (normal)
    if ratio < 1.25:
        return (0, 215, 255)    # yellow  (elevated)
    if ratio < 1.5:
        return (0, 165, 255)    # orange  (moderate)
    if ratio < 2.0:
        return (0, 100, 255)    # orange+ (high)
    return (0, 0, 220)          # red     (critical)

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

    # segments
    for mp_a, mp_b, j_idx in JOINT_LANDMARKS:
        ratio = (dot_risk[PELVIS] if j_idx == -1
                 else dot_risk[KEYPOINTS[j_idx]])
        cv2.line(out, pixel(mp_a), pixel(mp_b),
                 severity_color(ratio), 2, cv2.LINE_AA)

    # landmarks — includes ankles (27, 28) for visual continuity
    for dot in [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 32]:
        color = severity_color(dot_risk[dot])
        size = 3 if dot == NOSE else 5
        cv2.circle(out, pixel(dot), size, color, -1, cv2.LINE_AA)
        cv2.circle(out, pixel(dot), size, (0, 0, 0),  1, cv2.LINE_AA)

    return out


# ── Camera settings ────────────────────────────────────────────────────────────

DETECT_WIDTH  = 192
DETECT_HEIGHT = 108

# pitchflow
COUNTDOWN_SECS   = 3
MAX_PITCH_FRAMES = 90

# live alert
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

# pitching state
WAITING    = "waiting"
COUNTDOWN  = "countdown"
COLLECTING = "collecting"
ANALYZING  = "analyzing"
POST_PITCH = "post_pitch"


# ── Camera thread ──────────────────────────────────────────────────────────────

class CameraThread(threading.Thread):

    def __init__(self, cap: cv2.VideoCapture):
        super().__init__(daemon=True)
        self._cap  = cap
        self._q    = queue.Queue(maxsize=2)
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
            return True, self._q.get(timeout=0.033)
        except queue.Empty:
            return self.ok, None

    def stop(self):
        self._stop.set()





def get_text_size(text: str, size: int) -> tuple:
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, size / 28.0, max(1, round(size / 18)))
    return w, h


def put_text(img: np.ndarray, text: str, pos: tuple,
             size: int, color_bgr: tuple) -> None:
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                size / 28.0, color_bgr, max(1, round(size / 18)), cv2.LINE_AA)



# ── Font size constants ────────────────────────────────────────────────────────

FS_TINY   = 14   # muted hints, key legend, joint value column
FS_SMALL  = 18   # joint names, progress labels, body values
FS_BODY   = 22   # general status text, feedback lines
FS_MEDIUM = 28   # panel sub-headers / verdict text
FS_LARGE  = 42   # "Analyzing..." overlay
FS_HUGE   = 84   # countdown number


# ── UI constants ───────────────────────────────────────────────────────────────

# PANEL_W is now computed per-frame — use panel_layout() to get all values.
# The fallback constant is kept so importers of PANEL_W still work.
PANEL_W       = 420   # fallback — overridden per-draw by panel_layout()
PANEL_BG      = (18, 18, 18)
HDR_H         = 72
CLR_PRIMARY   = (230, 230, 230)
CLR_SECONDARY = (155, 155, 155)
CLR_MUTED     = (82, 82, 82)
CLR_DIVIDER   = (40, 40, 40)
CLR_BAR_BG    = (48, 48, 48)


def panel_layout(fw: int) -> tuple:
    """Return (pw, bar_x, bar_w, val_x) where fw is the CAMERA frame width.

    Panel = 40% of camera width, clamped [240, 380] px.
    This gives roughly a 60/40 camera/panel split at any resolution.
    Bar columns scale proportionally inside the panel.
    """
    pw    = max(240, min(380, int(fw * 0.40)))
    bar_x = max(72,  int(pw * 0.28))
    bar_w = max(100, int(pw * 0.42))
    val_x = bar_x + bar_w + 5
    return pw, bar_x, bar_w, val_x


def _divider(panel: np.ndarray, y: int, pw: int) -> None:
    cv2.line(panel, (10, y), (pw - 10, y), CLR_DIVIDER, 1, cv2.LINE_AA)


def _section_label(panel: np.ndarray, text: str, y: int) -> None:
    put_text(panel, text.upper(), (10, y), FS_TINY, CLR_MUTED)


# ── Panel helpers ──────────────────────────────────────────────────────────────

def side_panel(fh: int, pw: int) -> np.ndarray:
    p = np.full((fh, pw, 3), PANEL_BG, dtype=np.uint8)
    cv2.line(p, (1, 0), (1, fh), (45, 45, 45), 1)
    return p


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
    pw, _, _, _ = panel_layout(fw)   # total width = camera + panel
    panel  = side_panel(fh, pw)

    # Header
    cv2.rectangle(panel, (0, 0), (pw, HDR_H), (52, 52, 52), -1)
    put_text(panel, "STANDBY",          (10, 28), FS_TINY,   CLR_MUTED)
    put_text(panel, "Awaiting Pitcher", (10, 64), FS_MEDIUM, CLR_PRIMARY)

    _divider(panel, HDR_H + 2, pw)

    # Instructions
    y = HDR_H + 32
    _section_label(panel, "Instructions", y)
    y += 28
    put_text(panel, "Step into frame to begin.", (10, y), FS_BODY, CLR_SECONDARY)

    # Bottom status
    put_text(panel, "System ready", (10, fh - 16), FS_TINY, CLR_MUTED)

    return blend_panel(frame, panel)


def draw_countdown_overlay(frame: np.ndarray, screen_pts: np.ndarray,
                            secs_left: float) -> np.ndarray:
    out     = draw_keypoints(frame, screen_pts, np.zeros(33))
    fh, fw  = out.shape[:2]
    overlay = out.copy()
    cx, cy  = fw // 2, fh // 2
    cv2.circle(overlay, (cx, cy), 96, (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.60, out, 0.40, 0, out)

    number = str(max(1, int(np.ceil(secs_left))))
    tw, th = get_text_size(number, FS_HUGE)
    put_text(out, number, (cx - tw // 2, cy + th // 2), FS_HUGE, (50, 220, 50))

    hint = "Get ready to pitch..."
    hw, _ = get_text_size(hint, FS_BODY)
    put_text(out, hint, (cx - hw // 2, cy + 138), FS_BODY, (200, 200, 200))

    pw, _, _, _ = panel_layout(out.shape[1])
    panel = side_panel(fh, pw)
    cv2.rectangle(panel, (0, 0), (pw, HDR_H), (32, 88, 42), -1)
    put_text(panel, "DETECTED",      (10, 28), FS_TINY,   (130, 195, 130))
    put_text(panel, "Pitcher Ready", (10, 64), FS_MEDIUM, CLR_PRIMARY)

    _divider(panel, HDR_H + 2, pw)

    y = HDR_H + 30
    put_text(panel, f"Recording in  {secs_left:.1f}s", (10, y), FS_BODY, (140, 200, 140))

    prog  = max(0.0, 1.0 - secs_left / COUNTDOWN_SECS)
    bar_w = int(prog * (pw - 20))
    y += 18
    cv2.rectangle(panel, (10, y), (pw - 10, y + 9), CLR_BAR_BG, -1)
    cv2.rectangle(panel, (10, y), (10 + bar_w, y + 9), (70, 180, 70), -1)

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
    pw, bar_x, bar_w_max, val_x = panel_layout(fw)
    panel  = side_panel(fh, pw)

    # Header
    if alert_joint:
        hdr_col = (140, 20, 20)
        hdr_tag = "ALERT"
        hdr_sub = alert_joint
    else:
        hdr_col = (38, 72, 108)
        hdr_tag = "RECORDING"
        hdr_sub = "Pitch in progress"

    cv2.rectangle(panel, (0, 0), (pw, HDR_H), hdr_col, -1)
    put_text(panel, hdr_tag, (10, 28), FS_TINY,   (170, 170, 200))
    put_text(panel, hdr_sub, (10, 64), FS_MEDIUM, CLR_PRIMARY)

    _divider(panel, HDR_H + 2, pw)

    # Progress bar
    y         = HDR_H + 28
    progress  = n_collected / MAX_PITCH_FRAMES
    prog_bw   = int(progress * (pw - 20))
    frame_lbl = f"{n_collected} / {MAX_PITCH_FRAMES} frames"
    fps_lbl   = f"{fps_live:.0f} fps"
    put_text(panel, frame_lbl, (10, y), FS_SMALL, CLR_SECONDARY)
    fw2, _ = get_text_size(fps_lbl, FS_SMALL)
    put_text(panel, fps_lbl, (pw - fw2 - 10, y), FS_SMALL, CLR_MUTED)
    y += 16
    cv2.rectangle(panel, (10, y), (pw - 10, y + 9), CLR_BAR_BG, -1)
    cv2.rectangle(panel, (10, y), (10 + prog_bw, y + 9), (80, 160, 80), -1)

    y += 24
    _divider(panel, y, pw)
    y += 20

    # Joint risk table — row height scales with available vertical space
    _section_label(panel, "Live Joint Risk", y)
    y += 26

    if early_risk is not None:
        row_h = max(18, (fh - y - 24) // NUM_JOINTS)
        for k in range(NUM_JOINTS):
            risk   = float(early_risk[k])
            thresh = float(thresholds[k])
            color  = risk_color(risk, thresh)
            bw     = int(min(risk / (2.0 * thresh + 1e-10), 1.0) * bar_w_max)
            put_text(panel, SHORT_NAMES[k], (10, y), FS_SMALL, CLR_SECONDARY)
            cv2.rectangle(panel, (bar_x, y - 14), (bar_x + bar_w_max, y + 4), CLR_BAR_BG, -1)
            cv2.rectangle(panel, (bar_x, y - 14), (bar_x + bw,        y + 4), color,       -1)
            put_text(panel, f"{risk:.3f}", (val_x, y), FS_TINY, CLR_MUTED)
            y += row_h
    else:
        put_text(panel, "Warming up...", (10, y), FS_BODY, CLR_MUTED)

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
    pw, bar_x, bar_w_max, val_x = panel_layout(fw)
    panel  = side_panel(fh, pw)

    # Header
    is_correct = result["verdict"] == "Correct Form"
    hdr_col    = (20, 150, 35) if is_correct else (18, 18, 185)
    cv2.rectangle(panel, (0, 0), (pw, HDR_H), hdr_col, -1)
    put_text(panel, "RESULT",          (10, 28), FS_TINY,
             (130, 220, 140) if is_correct else (130, 130, 230))
    put_text(panel, result["verdict"], (10, 64), FS_MEDIUM, CLR_PRIMARY)

    _divider(panel, HDR_H + 2, pw)
    y = HDR_H + 26

    if result["main_issue"]:
        put_text(panel, f"Issue:  {result['main_issue'][:30]}", (10, y),
                 FS_BODY, (210, 155, 95))
        y += 30

    # Session accuracy bar
    if n_pitches > 0:
        acc     = n_correct / n_pitches * 100
        acc_col = (50, 205, 50) if acc >= 70 else (0, 215, 255) if acc >= 50 else (0, 80, 220)
        acc_bw  = int((acc / 100.0) * (pw - 20))
        lbl     = f"{n_correct} / {n_pitches} correct  -  {acc:.0f}%"
        put_text(panel, lbl, (10, y), FS_SMALL, acc_col)
        y += 16
        cv2.rectangle(panel, (10, y), (pw - 10, y + 9), CLR_BAR_BG, -1)
        cv2.rectangle(panel, (10, y), (10 + acc_bw, y + 9), acc_col, -1)
        y += 22

    _divider(panel, y, pw)
    y += 20
    _section_label(panel, "Joint Risk", y)
    y += 26

    # Dynamic row height so joints + feedback + cooldown always fit
    joint_budget  = int((fh - y - 120) * 0.50)
    joint_row_h   = max(16, joint_budget // NUM_JOINTS)
    for k in range(NUM_JOINTS):
        risk   = float(result["joint_risks"][k])
        thresh = float(thresholds[k])
        color  = risk_color(risk, thresh)
        bw     = int(min(risk / (2.0 * thresh + 1e-10), 1.0) * bar_w_max)
        put_text(panel, SHORT_NAMES[k], (10, y), FS_SMALL, CLR_SECONDARY)
        cv2.rectangle(panel, (bar_x, y - 14), (bar_x + bar_w_max, y + 4), CLR_BAR_BG, -1)
        cv2.rectangle(panel, (bar_x, y - 14), (bar_x + bw,        y + 4), color,       -1)
        put_text(panel, f"{risk:.3f}", (val_x, y), FS_TINY, CLR_MUTED)
        y += joint_row_h

    _divider(panel, y, pw)
    y += 14
    _section_label(panel, "Top Feedback", y)
    y += 20

    for _, row in result["feedback_df"].head(3).iterrows():
        color = risk_color(row["Risk"], row["Threshold"])
        fb = row["Feedback"]
        while fb and get_text_size(fb, FS_SMALL)[0] > pw - 20:
            fb = fb[:-1]
        put_text(panel, fb, (10, y), FS_SMALL, color)
        y += 20
        put_text(panel, row["Severity"], (10, y), FS_TINY, color)
        y += 18

    _divider(panel, y, pw)
    y += 14

    # Cooldown countdown
    put_text(panel, f"Next pitch in  {secs_left:.1f}s", (10, y), FS_BODY, CLR_SECONDARY)
    prog   = max(0.0, 1.0 - secs_left / COOLDOWN)
    cd_bw  = int(prog * (pw - 20))
    y += 16
    cv2.rectangle(panel, (10, y), (pw - 10, y + 9), CLR_BAR_BG, -1)
    cv2.rectangle(panel, (10, y), (10 + cd_bw, y + 9), (80, 160, 80), -1)

    return blend_panel(out, panel)


# ── Landmark smoother ──────────────────────────────────────────────────────────

class LandmarkSmoother:
    def __init__(self):
        self.alpha    = 0.7   # pure passthrough, no EMA lag
        self.vel_gain = 0.2   # no velocity-based prediction
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


# ── Main ───────────────────────────────────────────────────────────────────────

def run_live(camera_id: int = 0, width: int = 1280, height: int = 720, throwing_hand: str = "RHP"):

    # model
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

    # camera — CAP_DSHOW works with OBS Virtual Camera on Windows
    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {camera_id}")
    flip = (throwing_hand == "LHP")

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

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # Window width = feed + panel; height = feed height
    win_w = actual_w + PANEL_W
    win_h = actual_h
    cv2.namedWindow("Live Pitch Analysis", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Live Pitch Analysis", win_w, win_h)
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
    cd_start       = None
    post_start     = None
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

        if flip:
            frame = cv2.flip(frame, 1)
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
            if flip:
                # LHP: swap L↔R keypoints so model sees RHP geometry
                _SWAP = [(11,12),(13,14),(15,16),(23,24),(25,26),(27,28)]
                for a, b in _SWAP:
                    world_pts[[a, b]] = world_pts[[b, a]]
                    image_pts[[a, b]] = image_pts[[b, a]]
                world_pts[:, 0] *= -1
                image_pts[:, 0]  = 1.0 - image_pts[:, 0]

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

            # pitch logging
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

        # display
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
            analyzing_txt = "Analyzing..."
            atw, ath = get_text_size(analyzing_txt, FS_LARGE)
            ax = (display.shape[1] - atw) // 2
            ay = display.shape[0] // 2
            cv2.rectangle(display, (ax - 18, ay - ath - 12), (ax + atw + 18, ay + 12),
                          (0, 0, 0), -1)
            cv2.rectangle(display, (ax - 18, ay - ath - 12), (ax + atw + 18, ay + 12),
                          (40, 40, 40), 1)
            put_text(display, analyzing_txt, (ax, ay), FS_LARGE, (0, 215, 255))

        else:
            secs    = max(0.0, COOLDOWN - (time.perf_counter() - post_start))
            display = draw_post_pitch_overlay(frame, lastresult_list, secs,
                                              n_pitches, n_correct, lm)

        # FPS counter
        fps_txt = f"FPS  {fps_live:.1f}"
        ftw, fth = get_text_size(fps_txt, FS_BODY)
        cv2.rectangle(display, (6, 6), (ftw + 18, fth + 16), (0, 0, 0), -1)
        cv2.rectangle(display, (6, 6), (ftw + 18, fth + 16), (42, 42, 42), 1)
        put_text(display, fps_txt, (12, fth + 11), FS_BODY, (200, 200, 200))

        cv2.imshow("Live Pitch Analysis", display)

        cv2.waitKey(1)

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
    parser.add_argument("--camera", type=int,  default=0)
    parser.add_argument("--width",  type=int,  default=1280)
    parser.add_argument("--height", type=int,  default=720)
    parser.add_argument("--hand",   type=str,  default="RHP",
                        choices=["RHP", "LHP"], help="Pitcher throwing hand")
    args = parser.parse_args()
    run_live(camera_id=args.camera, width=args.width,
             height=args.height, throwing_hand=args.hand)
