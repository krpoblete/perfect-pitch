# Perfect Pitch

A desktop application for analyzing and managing baseball pitching sessions, built with Python and PyQt6. It uses MediaPipe pose estimation and an LSTM autoencoder to evaluate pitching mechanics in real time, flagging joint-level risk and providing per-pitch feedback.

---

## Features

- **Role-based access** — Admin, Coach, and Pitcher roles with tailored navigation and permissions
- **Authentication** — Secure login and signup with bcrypt password hashing
- **Password recovery** — Email and date of birth verification with a 3-attempt, 15-minute lockout
- **Show/hide password** — Toggle visibility on all password fields across the auth window
- **ML-powered pose analysis** — MediaPipe Pose + LSTM autoencoder evaluates pitching form per pitch
- **Joint risk scoring** — 9 joints tracked (elbows, shoulders, hips, knees, pelvis) with 5 severity levels: Normal, Elevated, Moderate, High, Critical
- **Live session capture** — Real-time camera feed with skeleton overlay, per-pitch verdict, and audio cues
- **Session summary** — Accuracy, pitch count, mistake count, worst joint callout, and combined skeleton PNG
- **Dashboard** — Per-user performance overview across all sessions with history and skeleton viewer
- **Pitcher management** — Coaches can view, search, and manage their assigned pitchers
- **User management** — Admins can view all users and assign roles
- **Account settings** — Users can update their profile, throwing hand, and pitch threshold (age-gated via USA Baseball limits)
- **Guided tour** — Role-aware interactive overlay that walks new users through the app on first login
- **Soft delete & retention** — Deactivated accounts are purged after 90 days (Manila time, UTC+8)
- **Dark theme** — Fully styled dark UI using PyQt6 and modular QSS stylesheets
- **Frameless windows** — Custom minimize/close controls with themed confirmation dialogs
- **Toast notifications** — Bottom-left toasts for errors, success, warnings, and info

---

## Project Structure

```
perfect-pitch/
├── assets/
│   ├── icons/                          # SVG icons (Tabler Icons) — 21 files
│   ├── skeletons/                      # Joint-severity skeleton PNGs — 45 files
│   │   └── {joint}_{severity}.png      # e.g. left_elbow_critical.png
│   ├── sounds/
│   │   ├── alert.mp3                   # Played on Incorrect Form verdict
│   │   └── setgo.mp3                   # Played at session start
│   ├── app_icon.ico
│   └── side-banner.png
├── src/
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── login_page.py
│   │   │   ├── signup_page.py
│   │   │   └── forgot_password_page.py
│   │   ├── account_settings_page.py
│   │   ├── camera_manager.py           # Camera probe, combo, preview, and guide card logic
│   │   ├── dashboard_page.py
│   │   ├── pitchers_page.py
│   │   ├── session_summary.py          # Post-session summary dialog with skeleton viewer
│   │   ├── start_session_page.py
│   │   └── users_page.py
│   ├── styles/
│   │   ├── account_settings.qss
│   │   ├── auth.qss
│   │   ├── base.qss
│   │   ├── dashboard.qss
│   │   ├── dialogs.qss
│   │   ├── guide.qss
│   │   ├── main.qss
│   │   ├── pitchers.qss
│   │   ├── start_session.qss
│   │   ├── tour.qss
│   │   ├── users.qss
│   │   └── window_buttons.qss
│   ├── utils/
│   │   ├── animations.py               # fade_in / fade_out helpers
│   │   ├── icons.py                    # SVG recolor → QIcon
│   │   ├── toast.py                    # Wrapper around pyqt-toast-notification
│   │   └── validators.py               # Name, email, and password validation
│   ├── widgets/
│   │   ├── confirm_dialog.py           # Frameless modal Yes/No dialog
│   │   ├── password_input.py           # Password field with show/hide toggle
│   │   ├── tour_overlay.py             # Guided-tour overlay with animated spotlight
│   │   └── window_buttons.py           # Minimize + close buttons for frameless windows
│   ├── windows/
│   │   ├── auth_window.py              # Frameless auth window (login / signup / forgot)
│   │   └── main_window.py              # Frameless main window with sidebar nav
│   ├── analyze.py                      # LSTM autoencoder model definition, feature extraction, scoring
│   ├── config.py                       # Paths, env vars, app metadata
│   ├── db.py                           # SQLite schema, migrations, CRUD helpers
│   ├── live_capture.py                 # MediaPipe pose loop, skeleton drawing, session JSON writer
│   ├── pitch_summary.py                # CLI tool — summarizes session JSON(s) and builds combined skeleton PNG
│   └── pitch_worker.py                 # QThread wrapper around live_capture; emits Qt signals
├── .env
├── .gitignore
├── main.py
└── requirements.txt
```

---

## Requirements

- Python 3.11+
- Windows (frameless window support via `pywin32` and `PyQt6-Frameless-Window`)
- A webcam or OBS Virtual Camera (DirectShow-compatible)
- CUDA-capable GPU recommended for real-time inference (falls back to CPU)

---

## Setup

### 1. Clone the repository

```powershell
git clone https://github.com/krpoblete/perfect-pitch.git
cd perfect-pitch
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

> **PyTorch (CUDA 12.1)** must be installed separately — it is not in `requirements.txt` because the index URL differs from PyPI:
> ```powershell
> pip install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
> ```
> If you don't have a CUDA-capable GPU, the app falls back to CPU automatically, but real-time inference will be significantly slower.

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
DB_NAME=perfect_pitch.db
APP_NAME=Perfect Pitch
APP_VERSION=1.0.0
```

> This is optional for local development — all three values have hardcoded fallback defaults in `config.py`. It is included as a convenience for future developers who may want to swap the database name or app metadata without touching source code.

### 5. Add ML model files

Place the following in the project root (excluded from version control):

| File | Purpose |
|------|---------|
| `pose_landmarker_heavy.task` | MediaPipe Pose Landmarker model |
| `models/` | Trained LSTM autoencoder, scaler, and threshold files |

### 6. Run the app

```powershell
python main.py
```

---

## Default Admin Account

On first launch, a default Admin account is seeded automatically:

| Field    | Value       |
|----------|-------------|
| Email    | `admin`     |
| Password | `admin1234` |

> **Change the default password after first login.**

---

## ML Pipeline

Perfect Pitch uses a two-stage pipeline to evaluate pitching mechanics:

1. **Pose estimation** — MediaPipe Pose Landmarker (`pose_landmarker_heavy.task`) extracts 33 body landmarks per frame at up to 1080p.
2. **Feature extraction** — Joint angles are computed for 9 key joints across a 60-frame window and resampled/smoothed.
3. **LSTM Autoencoder** — Trained on correct-form pitches. At inference, reconstruction error (MSE) is compared against a learned threshold. Pitches exceeding the threshold are flagged as **Incorrect Form**.
4. **Joint risk scoring** — Per-joint risk scores are divided by individual thresholds and mapped to severity levels (Normal → Critical). The worst joint is highlighted in the session summary.
5. **Skeleton visualization** — A combined skeleton PNG is generated by compositing the 9 per-joint severity images from `assets/skeletons/`.

The model bundle `(model, scaler, threshold, joint_thresholds)` is loaded once at startup and passed through the window chain to avoid reloading between sessions.

---

## Pitch Count Limits

Age-gated pitch thresholds follow USA Baseball guidelines:

| Age Range | Daily Limit |
|-----------|-------------|
| 13 – 16   | 95          |
| 17 – 18   | 105         |
| 19 – 22   | 120         |
| < 13 or > 22 | 95 / 120 (floor / ceiling) |

Coaches and Admins can override a pitcher's threshold in Account Settings.

---

## Severity Levels

| Level    | Ratio (risk / threshold) | Color    |
|----------|--------------------------|----------|
| Normal   | < 1.0                    | Green    |
| Elevated | 1.0 – 1.25               | Yellow   |
| Moderate | 1.25 – 1.5               | Orange   |
| High     | 1.5 – 2.0                | Orange+  |
| Critical | ≥ 2.0                    | Red      |

---

## Roles

| Role    | Exclusive Access |
|---------|-----------------|
| Admin   | Users           |
| Coach   | Pitchers        |
| Pitcher | —               |

All roles share: Dashboard, Start Session, and Account Settings. New accounts default to **Pitcher**. An Admin must assign Coach roles manually.

---

## Dependencies

| Package                     | Purpose                                    |
|-----------------------------|--------------------------------------------|
| `PyQt6`                     | UI framework                               |
| `PyQt6-Frameless-Window`    | Frameless window support                   |
| `pyqt-toast-notification`   | Toast notifications                        |
| `bcrypt`                    | Password hashing                           |
| `python-dotenv`             | Environment variable loading               |
| `pywin32`                   | Windows taskbar integration                |
| `mediapipe`                 | Pose landmark detection                    |
| `torch`                     | LSTM autoencoder inference (CUDA or CPU)   |
| `opencv-python`             | Camera capture and skeleton rendering      |
| `numpy`                     | Numerical computation                      |
| `pandas`                    | Feature tabulation                         |
| `scikit-learn`              | Scaler loading                             |
| `sounddevice`               | Audio playback (alert / set-go sounds)     |
| `soundfile`                 | MP3/WAV decoding for sounddevice           |

---

## Gitignore Highlights

The following are intentionally excluded from version control:

- `venv/`, `__pycache__/`, `*.pyc`
- `.env`, `*.db`
- `models/`, `pose_landmarker_heavy.task`, `*.pt`, `*.pkl`, `*.npy`, `*.task`
- `output/`
- `.vscode/`, `dist/`, `build/`