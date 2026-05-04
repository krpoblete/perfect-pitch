"""
QThread wrapper around live_capture.run_live().
Emits Qt signals instead of calling cv2.imshow(), so the feed
and pitch results flow into StartSessionPage without blocking
the PyQt6 event loop.
"""

import time
import warnings
import queue
import threading
import json
import numpy as np

from datetime import datetime
from pathlib import Path

import cv2
import sounddevice as sd
import soundfile as sf
from pathlib import Path as _Path

from PyQt6.QtCore import QThread, pyqtSignal

warnings.filterwarnings("ignore")

# Alert sound — played on every Incorrect Form verdict
from src.config import ASSETS_DIR as _ASSETS
_ALERT_PATH  = _Path(_ASSETS) / "sounds" / "alert.mp3"
_SETGO_PATH  = _Path(_ASSETS) / "sounds" / "setgo.mp3"
_alert_data, _alert_sr = (None, None)
_setgo_data, _setgo_sr = (None, None)

class PitchWorker(QThread):
    # Signals
    frame_ready = pyqtSignal(object)      # numpy BGR frame → feed_label
    pitch_done = pyqtSignal(dict)         # full pitch result dict
    stats_updated = pyqtSignal(int, int)  # (pitch_count, mistakes)
    state_changed = pyqtSignal(str)       # WAITING | COUNTDOWN | COLLECTING | ANALYZING | POST_PITCH
    model_loaded = pyqtSignal()           # camera + model ready
    skeleton_ready = pyqtSignal(str)      # path to combined skeleton PNG
    error_occurred = pyqtSignal(str)      # fatal error message
    session_ended = pyqtSignal(str)       # log_path when thread finishes

    def __init__(self, camera_id: int = 0, width: int = 1920,
                 height: int = 1080, throwing_hand: str = "RHP",
                 ml_bundle=None, user_id: int = 0, 
                 reference_resolution: tuple | None = None, parent = None):
        super().__init__(parent)
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.throwing_hand = throwing_hand
        self._ml_bundle = ml_bundle                        # pre-loaded (model, scaler, threshold, thresholds)
        self.user_id = user_id                             # used for artifact folder naming (collision-safe)
        self._reference_resolution = reference_resolution  # (w, h) of external cam, or None
        self._stop_event = threading.Event()
        self.skeleton_path = ""                            # written by worker thread, read by main after wait()

    def stop(self):
        self._stop_event.set()

    @staticmethod
    def _preload_sounds():
        """Load both sounds from disk once at session start so no I/O
        happens mid-session. Called from run() before the main loop."""
        global _alert_data, _alert_sr, _setgo_data, _setgo_sr
        try:
            if _alert_data is None and _ALERT_PATH.exists():
                _alert_data, _alert_sr = sf.read(
                    str(_ALERT_PATH), dtype="float32", always_2d=True
                )
        except Exception:
            pass
        try:
            if _setgo_data is None and _SETGO_PATH.exists():
                _setgo_data, _setgo_sr = sf.read(
                    str(_SETGO_PATH), dtype="float32", always_2d=True
                )
        except Exception:
            pass

    def _play_alert(self):
        """Play alert.mp3 fire-and-forget — no sd.wait() so the main
        loop is never stalled waiting for audio to finish."""
        global _alert_data, _alert_sr
        if _alert_data is None:
            return
        import threading as _t
        def _play():
            try:
                sd.stop()
                sd.play(_alert_data, _alert_sr)
                # no sd.wait() — return immediately
            except Exception:
                pass
        _t.Thread(target=_play, daemon=True).start()

    def _play_setgo(self):
        """Play setgo.mp3 in a daemon thread alongside the countdown.
        No sd.wait() — the sound plays freely while the loop continues."""
        global _setgo_data, _setgo_sr
        if _setgo_data is None:
            return
        import threading as _t
        def _play():
            try:
                sd.play(_setgo_data, _setgo_sr)
            except Exception:
                pass
        _t.Thread(target=_play, daemon=True).start()

    # Main thread body
    def run(self):
        try:
            self._run_capture()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _run_capture(self):
        import torch
        import mediapipe as mp
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision as mp_vision
        from mediapipe.tasks.python.vision import RunningMode

        from src.analyze import (
            LSTMAutoencoder, FRAMES, POSE_MODEL_DIR, MODEL_DIR, DEVICE,
            NUM_JOINTS, JOINT_NAMES, FEEDBACK,
            extract_features, compute_scores, check_verdict,
            risk_rank, resample, smooth, build_feedback_table,
        )
        from src.live_capture import (
            CameraThread, LandmarkSmoother,
            DETECT_WIDTH, DETECT_HEIGHT,
            COUNTDOWN_SECS, MAX_PITCH_FRAMES,
            INFER_EVERY, ALERT_RISK_RATIO, COOLDOWN,
            SHORT_NAMES, LOG_DIR,
            WAITING, COUNTDOWN, COLLECTING, ANALYZING, POST_PITCH,
            draw_waiting_overlay, draw_countdown_overlay,
            draw_collecting_overlay, draw_keypoints,
            draw_post_pitch_overlay,
            landmark_colors, severity_color,
        )
        import pickle

        # Load model
        if self._ml_bundle is not None:
            ae, scaler, threshold, thresholds = self._ml_bundle
            thresholds = np.array(thresholds, dtype=np.float32)
        else:
            # Fallback: load from disk if bundle wasn't passed
            checkpoint = torch.load(
                MODEL_DIR / "lstm_autoencoder.pt",
                map_location=DEVICE, weights_only=False,
            )
            cfg = checkpoint["config"]
            threshold = checkpoint["threshold"]
            thresholds = np.array(
                checkpoint.get("joint_thresholds",
                            [threshold] * NUM_JOINTS),
                dtype=np.float32,
            )
            ae = LSTMAutoencoder(
                cfg["input_size"], cfg["hidden_size"], cfg["latent_dim"],
                cfg["seq_len"], cfg["num_layers"],
            ).to(DEVICE)
            ae.load_state_dict(checkpoint["model_state_dict"])
            ae.eval()

            with open(MODEL_DIR / "scaler.pkl", "rb") as f:
                scaler = pickle.load(f)

        # Camera — CAP_DSHOW for Windows DirectShow (works with OBS Virtual Camera).
        # Do NOT force a FOURCC — let the driver negotiate its native format.
        # OpenCV automatically converts YUY2/NV12 from OBS to BGR on read().
        # Only set resolution softly; if OBS ignores it we use whatever it gives.
        cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            self.error_occurred.emit(
                f"Could not open camera {self.camera_id}."
            )
            return

        # Compute DETECT dimensions at 10% of actual capture size
        # so MediaPipe always works on a proportionally correct frame 
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        DETECT_WIDTH = max(1, round(actual_w * 0.1))
        DETECT_HEIGHT = max(1, round(actual_h * 0.1))

        # --- Integrated-camera FOV normalisation ---
        # When _reference_resolution is set the user previously ran the external
        # webcam which has "the perfect view".  We centre-crop the integrated
        # camera's larger (or differently-shaped) frame to match the external
        # camera's aspect ratio, so MediaPipe sees the same framing on both.
        _crop_rect: tuple | None = None   # (x, y, w, h) in actual_w × actual_h space
        if self._reference_resolution is not None:
            ref_w, ref_h = self._reference_resolution
            ref_ar = ref_w / max(ref_h, 1)
            src_ar = actual_w / max(actual_h, 1)
            if abs(src_ar - ref_ar) > 0.02:          # only crop when AR differs
                if src_ar > ref_ar:
                    # source is wider — crop sides
                    crop_w = int(actual_h * ref_ar)
                    crop_h = actual_h
                else:
                    # source is taller — crop top/bottom
                    crop_w = actual_w
                    crop_h = int(actual_w / ref_ar)
                cx = (actual_w - crop_w) // 2
                cy = (actual_h - crop_h) // 2
                _crop_rect = (cx, cy, crop_w, crop_h)
                # Recompute DETECT size from the cropped region
                DETECT_WIDTH  = max(1, round(crop_w * 0.1))
                DETECT_HEIGHT = max(1, round(crop_h * 0.1))
        
        # Mirror LHP so the model always see the same side-view
        flip = (self.throwing_hand == "LHP")

        cam_thread = CameraThread(cap)
        cam_thread.start()

        # signal UI that camera + model are ready
        self.model_loaded.emit()

        # Pose landmarker (LIVE_STREAM)
        result_list = [None]
        result_ts_list = [0]
        result_lock = threading.Lock()

        def _on_result(result, _img, ts_ms):
            with result_lock:
                result_list[0] = result
                result_ts_list[0] = ts_ms

        options = mp_vision.PoseLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(
                model_asset_path=str(POSE_MODEL_DIR)
            ),
            running_mode=RunningMode.LIVE_STREAM,
            result_callback=_on_result,
            num_poses=1,
            min_pose_detection_confidence=0.7,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        landmarker = mp_vision.PoseLandmarker.create_from_options(options)

        # Session log — each session gets its own subfolder under output/artifacts/
        # Named session_<timestamp>_uid<user_id> to prevent collisions between
        # two pitchers whose sessions happen to start at the same second.
        from src.config import EXE_DIR
        session_start = datetime.now()
        session_slug = f"session_{session_start.strftime('%Y%m%d_%H%M%S')}_uid{self.user_id}"
        session_dir = EXE_DIR / "output" / "artifacts" / session_slug
        session_dir.mkdir(parents=True, exist_ok=True)
        log_path = session_dir / f"{session_slug}.json"
        session_log = []

        # State
        smoother = LandmarkSmoother()
        state = WAITING
        cd_start = None
        post_start = None
        world_pts = None
        image_pts = None
        world_frames = []
        screen_frames = []
        since_infer = 0
        early_risk = None
        alert_joint = None
        lastresult = None
        seen_ts = [0]
        frame_count = 0
        t0 = time.perf_counter()
        n_pitches = 0
        n_correct = 0
        n_mistakes = 0

        def reset():
            nonlocal state, cd_start, post_start, world_pts, image_pts
            nonlocal world_frames, screen_frames, since_infer
            nonlocal early_risk, alert_joint, lastresult
            state = WAITING
            cd_start = None
            post_start = None
            world_pts = None
            image_pts = None
            world_frames = []
            screen_frames = []
            since_infer = 0
            early_risk = None
            alert_joint = None
            lastresult = None
            smoother.reset()

        # Preload sounds before main loop so no disk I/O during session
        self._preload_sounds()

        self.state_changed.emit(WAITING)

        # Main loop
        while not self._stop_event.is_set():
            cam_ok, frame = cam_thread.read()
            if not cam_ok:
                self.error_occurred.emit("__camera_disconnected__")
                break
            if frame is None:
                continue

            if flip:
                frame = cv2.flip(frame, 1)

            # Centre-crop to match external webcam's aspect ratio (integrated cam only)
            if _crop_rect is not None:
                cx, cy, cw, ch = _crop_rect
                frame = frame[cy:cy + ch, cx:cx + cw]

            frame_count += 1
            ts_ms = int((time.perf_counter() - t0) * 1000)

            # Send to MediaPipe every other frame — halves inference overhead
            # while display runs at full frame rate
            if frame_count % 2 == 1:
                small = cv2.resize(frame, (DETECT_WIDTH, DETECT_HEIGHT))
                mp_img = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB),
                )
                landmarker.detect_async(mp_img, ts_ms)

            with result_lock:
                detection = result_list[0]
                result_ts = result_ts_list[0]

            new_detection = (result_ts > seen_ts[0])
            if new_detection:
                seen_ts[0] = result_ts

            person_seen = bool(
                detection
                and detection.pose_world_landmarks
                and detection.pose_landmarks
            )

            if person_seen:
                world_pts = np.array(
                    [[lm.x, lm.y, lm.z] for lm in detection.pose_world_landmarks[0]],
                    dtype=np.float32,
                )
                image_pts = np.array(
                    [[lm.x, lm.y] for lm in detection.pose_landmarks[0]],
                    dtype=np.float32,
                )
                if flip:
                    # LHP: swap L↔R keypoints so model always sees RHP geometry
                    _SWAP = [(11,12),(13,14),(15,16),(23,24),(25,26),(27,28)]
                    for a, b in _SWAP:
                        world_pts[[a, b]] = world_pts[[b, a]]
                        image_pts[[a, b]] = image_pts[[b, a]]
                    # Also mirror the x-axis for world coords (flip was spatial)
                    world_pts[:, 0] *= -1
                    image_pts[:, 0]  = 1.0 - image_pts[:, 0]

            if person_seen and new_detection:
                display_lm = smoother.update(image_pts)
            elif smoother.ready:
                display_lm = smoother.predict()
            else:
                display_lm = None

            fps_live = frame_count / max(time.perf_counter() - t0, 1e-6)

            # State machine
            prev_state = state

            if state == WAITING:
                if person_seen:
                    state = COUNTDOWN
                    cd_start = time.perf_counter()
                    self._play_setgo()   # plays "3...2...1...go!" alongside countdown

            elif state == COUNTDOWN:
                if not person_seen:
                    state = WAITING
                elif time.perf_counter() - cd_start >= COUNTDOWN_SECS:
                    state = COLLECTING
                    world_frames = []
                    screen_frames = []
                    since_infer = 0
                    early_risk = None
                    alert_joint  = None

            elif state == COLLECTING:
                if person_seen:
                    world_frames.append(world_pts)
                    screen_frames.append(image_pts)

                n = len(world_frames)
                since_infer += 1
                if n >= FRAMES // 2 and since_infer >= INFER_EVERY:
                    since_infer = 0
                    arr = smooth(resample(np.stack(world_frames), FRAMES))
                    feat = extract_features(arr)
                    feat_sc = scaler.transform(feat)
                    _, early_risk, _ = compute_scores(feat_sc, ae)
                    worst = int(np.argmax(early_risk / (thresholds + 1e-10)))
                    prev_alert = alert_joint
                    alert_joint = (
                        SHORT_NAMES[worst]
                        if early_risk[worst] >= ALERT_RISK_RATIO * thresholds[worst]
                        else None
                    )
                    # Beep on every new or changed joint alert
                    if alert_joint is not None and alert_joint != prev_alert:
                        self._play_alert()

                if n >= MAX_PITCH_FRAMES:
                    state = ANALYZING

            elif state == ANALYZING:
                arr = smooth(resample(np.stack(world_frames), FRAMES))
                feat = extract_features(arr)
                feat_sc = scaler.transform(feat)
                _, joint_risks, mse = compute_scores(feat_sc, ae)

                is_incorrect, reason, *_ = check_verdict(
                    mse, threshold, joint_risks, thresholds
                )
                verdict = "Incorrect Form" if is_incorrect else "Correct Form"
                worst_joint = risk_rank(joint_risks, thresholds) if is_incorrect else None
                main_issue = JOINT_NAMES[worst_joint] if worst_joint is not None else None
                feedback_df = build_feedback_table(joint_risks, thresholds)

                n_pitches += 1
                if verdict == "Correct Form":
                    n_correct += 1
                else:
                    n_mistakes +=1

                # Emit pitch result to UI
                pitch_result = {
                    "pitch_number": n_pitches,
                    "verdict": verdict,
                    "main_issue": main_issue,
                    "reason": reason,
                    "mse": round(float(mse), 6),
                    "threshold": round(float(threshold), 6),
                    "joint_risks": [round(float(r), 6) for r in joint_risks],
                    "joint_thresholds": [round(float(t), 6) for t in thresholds],
                    "joint_names": JOINT_NAMES,
                    "joint_severities": [
                        str(row["Severity"])
                        for _, row in feedback_df.sort_values("Joint").iterrows()
                    ],
                    "n_frames": len(world_frames),
                }
                self.pitch_done.emit(pitch_result)
                self.stats_updated.emit(n_pitches, n_mistakes)

                # Session JSON log
                session_log.append({
                    **pitch_result,
                    "timestamp": datetime.now().isoformat(),
                })
                with open(log_path, "w") as f:
                    json.dump({
                        "session_start": session_start.isoformat(),
                        "pitches": session_log,
                    }, f, indent=2)

                lastresult = {
                    "verdict": verdict,
                    "main_issue": main_issue,
                    "joint_risks": joint_risks,
                    "thresholds": thresholds,
                    "feedback_df": feedback_df,
                    "n_frames": len(world_frames),
                }
                state = POST_PITCH
                post_start = time.perf_counter()
                early_risk = None
                alert_joint = None

            elif state == POST_PITCH:
                if time.perf_counter() - post_start >= COOLDOWN:
                    reset()

            if prev_state != state:
                self.state_changed.emit(state)

            # Build display frame
            lm = display_lm if display_lm is not None else (
                screen_frames[-1] if screen_frames else None
            )

            if state == WAITING:
                display = draw_waiting_overlay(frame)
            elif state == COUNTDOWN:
                secs = max(0.0, COUNTDOWN_SECS - (time.perf_counter() - cd_start))
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
                cv2.putText(display, "Analyzing...",
                            (20, display.shape[0] // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                            (0, 215, 255), 2, cv2.LINE_AA)
            else:
                secs = max(0.0, COOLDOWN - (time.perf_counter() - post_start))
                display = draw_post_pitch_overlay(
                    frame, lastresult, secs, n_pitches, n_correct, lm
                )

            cv2.putText(display, f"FPS {fps_live:.1f}", (8, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (200, 200, 200), 1, cv2.LINE_AA)
            
            # Emit frame to Qt (replaces cv2.imshow)
            self.frame_ready.emit(display)

        # Cleanup — landmarker.close() can block for 10-30 s waiting for
        # pending async inference callbacks to drain.  Run it in a daemon
        # thread so it doesn't delay the worker's exit (and the finished
        # signal) or skeleton generation.
        cam_thread.stop()
        cap.release()
        threading.Thread(target=landmarker.close, daemon=True).start()

        if session_log:
            # Store skeleton path on self — main thread reads it safely after wait() 
            self.skeleton_path = ""
            try:
                from src.pitch_summary import compute_summary, build_combined_skeleton
                from src.config import ASSETS_DIR
                images_folder = _Path(ASSETS_DIR) / "skeletons"
                stats = compute_summary(session_log)
                out_png = session_dir / f"{session_slug}_combined_skeleton.png"
                build_combined_skeleton(stats, images_folder, out_png)
                if out_png.exists():
                    self.skeleton_path = str(out_png)
                    print(f"[skeleton] ready -> {self.skeleton_path}")
            except Exception as e:
                import traceback
                print(f"[skeleton] {e}")
                traceback.print_exc()

            # Both paths emitted together — UI receives them before opening dialog
            self.session_ended.emit(str(log_path))
