# Perfect Pitch

A desktop application for analyzing and managing baseball pitching sessions, built with Python and PyQt6. It uses MediaPipe pose estimation and an LSTM autoencoder to evaluate pitching mechanics in real time, flagging joint-level risk and providing per-pitch feedback.

---

## Features

- **Role-based access** — Admin, Coach, and Pitcher roles with tailored navigation and permissions
- **Authentication** — Secure login and signup with bcrypt password hashing
- **Password recovery** — Email and date of birth verification with a 3-attempt, 15-minute lockout that persists across auth page navigation within the same session
- **Show/hide password** — Toggle visibility on all password fields across the auth window
- **ML-powered pose analysis** — MediaPipe Pose + LSTM autoencoder evaluates pitching form per pitch
- **Joint risk scoring** — 9 joints tracked (elbows, shoulders, hips, knees, pelvis) with 5 severity levels: Normal, Elevated, Moderate, High, Critical
- **Weighted pitch tokens** — Incorrect Form pitches deduct 2 tokens from the daily pool; Correct Form pitches deduct 1, reflecting the greater physical strain of poor mechanics
- **Live session capture** — Real-time camera feed with skeleton overlay, per-pitch verdict, early joint risk alerts, and audio cues
- **Session summary** — Accuracy, pitch count, mistake count, worst joint callout, and combined skeleton PNG
- **Performance trend chart** — Cross-session line chart showing accuracy, mistakes, and pitch count over time; Coach view aggregates all pitchers; severity-colored dots mark the worst joint per session
- **Dashboard** — Per-user performance overview across all sessions with history table and skeleton viewer
- **Pitcher management** — Coaches can view, search, manage their assigned pitchers, and view a per-pitcher trend dialog
- **User management** — Admins can view all users and assign roles
- **Account settings** — Users can update their profile, throwing hand, and pitch threshold (age-gated via USA Baseball limits); spinbox shows remaining pitches for the day, not the raw stored value
- **Guided tour** — Role-aware interactive overlay that walks new users through the app on first login
- **Soft delete & retention** — Deactivated accounts are purged after 90 days (Manila time, UTC+8)
- **Dark theme** — Fully styled dark UI using PyQt6 and modular QSS stylesheets
- **Frameless windows** — Custom minimize/close controls with themed confirmation dialogs
- **Toast notifications** — Bottom-left toasts for errors, success, warnings, and info
- **Windows installer** — Inno Setup installer (`perfect_pitch.iss`) produces `PerfectPitch_Setup.exe` for clean end-user installation with Start Menu entry, Desktop shortcut, and uninstaller

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
│   ├── app_icon.ico                    # Multi-size app icon (16–256px)
│   └── side-banner.png
├── src/
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── auth_base.py            # Shared base class for all auth pages (logo, field helpers)
│   │   │   ├── login_page.py
│   │   │   ├── signup_page.py
│   │   │   └── forgot_password_page.py
│   │   ├── account_settings_page.py
│   │   ├── camera_manager.py           # Camera probe, combo, preview, and guide card logic
│   │   ├── dashboard_page.py           # Role-aware dashboard with performance trend chart
│   │   ├── pitchers_page.py            # Pitcher roster table + per-pitcher trend dialog
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
│   │   ├── pitch_rules.py              # Source for USA Baseball pitch limits
│   │   ├── toast.py                    # Wrapper around pyqt-toast-notification
│   │   └── validators.py               # Name, email, and password validation
│   ├── widgets/
│   │   ├── confirm_dialog.py           # Frameless modal Yes/No dialog
│   │   ├── hand_selector.py            # Reusable RHP / LHP toggle widget
│   │   ├── password_input.py           # Password field with show/hide toggle
│   │   ├── tour_overlay.py             # Guided-tour overlay with animated spotlight
│   │   ├── trend_chart.py              # Shared QPainter trend chart (accuracy, mistakes, pitch count)
│   │   └── window_buttons.py           # Minimize + close buttons for frameless windows
│   ├── windows/
│   │   ├── auth_window.py              # Frameless auth window (login / signup / forgot)
│   │   └── main_window.py              # Frameless main window with sidebar nav
│   ├── analyze.py                      # LSTM autoencoder model definition, feature extraction, scoring
│   ├── config.py                       # Paths, env vars, app metadata; AppData routing for frozen builds
│   ├── db.py                           # SQLite schema, migrations, CRUD helpers, trend queries
│   ├── live_capture.py                 # MediaPipe pose loop, skeleton drawing, session JSON writer
│   ├── pitch_summary.py                # CLI tool — summarizes session JSON(s) and builds combined skeleton PNG
│   └── pitch_worker.py                 # QThread wrapper around live_capture; emits Qt signals
├── .env
├── .gitignore
├── main.py
├── perfect_pitch.iss                   # Inno Setup installer script
├── perfect_pitch.spec                  # PyInstaller build spec
├── version_info.txt                    # Windows version resource (Task Manager process name)
└── requirements.txt
```

---

## Requirements

- Python 3.11+
- Windows 10 or 11 (frameless window support via `pywin32` and `PyQt6-Frameless-Window`)
- A webcam or OBS Virtual Camera (DirectShow-compatible)
- CUDA-capable GPU recommended for real-time inference (falls back to CPU)

---

## Installation (End Users)

If you just want to run Perfect Pitch without setting up a development environment, use the pre-built installer from Google Drive.

### 1. Download the latest release

Go to the [**PerfectPitch - Download**](https://drive.google.com/drive/folders/1BJ7cG4cKgKWUxfNPDsFahZPtDnHK8tWS?usp=sharing) folder on Google Drive and download `PerfectPitch_Setup.exe`.

### 2. Run the installer

Double-click `PerfectPitch_Setup.exe`. The installer:
- Installs to `%LocalAppData%\Programs\PerfectPitch\` (no admin rights required)
- Creates a Desktop shortcut and a Start Menu entry
- Registers an uninstaller in Add/Remove Programs

### 3. Launch the app

Open Perfect Pitch from the Desktop shortcut or Start Menu. On first launch the database is created automatically and seeded with a default Admin account. See [Default Admin Account](#default-admin-account) below.

> **Windows SmartScreen** may warn about an unrecognized app. Click **More info → Run anyway** to proceed. The app is not code-signed; this warning is expected for unsigned executables.

> **User data location** — The database (`perfect_pitch.db`) and all session output files are stored in `%AppData%\PerfectPitch\`, not in the install folder. This ensures the app can always write its data without requiring elevated permissions.

---

## Setup (Developers)

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

> **PyTorch (CUDA 12.1)** must be installed separately since it is not in `requirements.txt` because the index URL differs from PyPI:
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

> This is optional for local development because all three values have hardcoded fallback defaults in `config.py`.

### 5. Add ML model files

The heavy and sensitive files are stored in the [**PerfectPitch - Dev Files**](https://drive.google.com/drive/folders/15rqmS4fGAuyg3RTfMKbMtbCnNChKaRiD?usp=sharing) folder on Google Drive (private). Download them individually and place each in the project root.

| File | Purpose |
|------|---------|
| `pose_landmarker_heavy.task` | MediaPipe Pose Landmarker model |
| `models/` | Trained LSTM autoencoder, scaler, and threshold files |
| `.env` | Environment variables (see step 4) |

### 6. Run the app

```powershell
python main.py
```

---

## Building a Release

### PyInstaller (required first)

```powershell
pyinstaller perfect_pitch.spec
```

Output: `dist\PerfectPitch\`. After building, copy the ML files into the output folder:

```powershell
copy pose_landmarker_heavy.task dist\PerfectPitch\
xcopy models dist\PerfectPitch\models\ /E /I
```

### Inno Setup installer (optional)

Requires [Inno Setup 6](https://jrsoftware.org/isdl.php) to be installed.

Open `perfect_pitch.iss` in Inno Setup Compiler and press **F9**, or run:

```powershell
iscc perfect_pitch.iss
```

Output: `installer\PerfectPitch_Setup.exe`

> **Do not commit `dist\` or `installer\` to version control** — both are build artifacts. Distribute `PerfectPitch_Setup.exe` via Google Drive.

---

## Default Admin Account

On first launch, a default Admin account is seeded automatically:

| Field    | Value       |
|----------|-------------|
| Email    | `admin`     |
| Password | `Admin1234` |

> **Change the default password after first login.**

---

## ML Pipeline

Perfect Pitch uses a two-stage pipeline to evaluate pitching mechanics:

1. **Pose estimation** — MediaPipe Pose Landmarker (`pose_landmarker_heavy.task`) extracts 33 body landmarks per frame at up to 1080p.
2. **Feature extraction** — Joint angles are computed for 9 key joints across a 60-frame window and resampled/smoothed.
3. **LSTM Autoencoder** — Trained on correct-form pitches. At inference, reconstruction error (MSE) is compared against a learned threshold. Pitches exceeding the threshold are flagged as **Incorrect Form**.
4. **Joint risk scoring** — Per-joint risk scores are divided by individual thresholds and mapped to severity levels (Normal → Critical). The worst joint is highlighted in the session summary and stored in the database for trend charting.
5. **Skeleton visualization** — A combined skeleton PNG is generated by compositing the 9 per-joint severity images from `assets/skeletons/`.

The model bundle `(model, scaler, threshold, joint_thresholds)` is loaded once at startup and passed through the window chain to avoid reloading between sessions.

---

## Pitch Token System

Each pitcher has a daily pitch pool governed by three values:

| Value | Source | Meaning |
|---|---|---|
| `recommended_cap` | `pitch_rules.get_pitch_limit(dob)` | USA Baseball age-appropriate hard ceiling — never stored |
| `pitch_threshold` | `users.pitch_threshold` in DB | User's saved personal daily limit |
| `used_today` | `SUM(sessions.total_pitch)` for today | Tokens already consumed today |

**Token cost per pitch:**
- Correct Form → deducts **1 token**
- Incorrect Form → deducts **2 tokens** (reflects greater physical strain)

`sessions.total_pitch` stores the weighted token cost (`pitch_count + mistakes`). `sessions.pitch_count` stores the true number of pitches thrown and is used for all display purposes (Dashboard, history table, trend chart).

The Account Settings spinbox displays **remaining pitches** (`pitch_threshold − used_today`), not the raw stored value. On save, the absolute threshold is reconstructed as `spinbox_value + used_today`, capped at `recommended_cap`. The spinbox replenishes automatically at midnight Manila time (UTC+8) via a 60-second QTimer.

---

## Pitch Count Limits

Age-gated pitch thresholds follow USA Baseball guidelines and are enforced via `src/utils/pitch_rules.py`.

| Age Range    | Daily Limit |
|--------------|-------------|
| 13 – 16      | 95          |
| 17 – 18      | 105         |
| 19 – 22      | 120         |
| < 13 or > 22 | 95 / 120 (floor / ceiling) |

Pitchers' thresholds are set automatically on signup based on their date of birth. Coaches and Admins can override a pitcher's threshold in Account Settings, up to the recommended cap.

---

## Performance Trend Chart

The Dashboard includes a cross-session performance trend chart rendered with pure QPainter (no matplotlib dependency). It displays:

- **Bars** — true pitch count per session (right Y-axis, integer-snapped scale)
- **Green line** — accuracy percentage (left Y-axis, 0–100%)
- **Red dashed line** — mistake count per session
- **Dots** — one per session on the accuracy line, colored by worst joint severity on the Dashboard (plain green in the per-pitcher trend dialog)

Implemented in `src/widgets/trend_chart.py` as a shared `TrendChart` widget used by both `dashboard_page.py` and `pitchers_page.py`.

**Role behaviour:**
- **Pitcher** — personal sessions, plain green dots
- **Coach** — combined sessions across all active pitchers, severity-colored dots; per-pitcher detail via "View →" on pitcher overview cards
- **Admin** — personal sessions (for Start Session debugging), severity-colored dots

---

## Severity Levels

| Level    | Ratio (risk / threshold) | Color    |
|----------|--------------------------|----------|
| Normal   | < 1.0                    | Green    |
| Elevated | 1.0 – 1.25               | Yellow   |
| Moderate | 1.25 – 1.5               | Orange   |
| High     | 1.5 – 2.0                | Orange+  |
| Critical | ≥ 2.0                    | Red      |

The worst joint per session is stored in `sessions.worst_joint` and `sessions.worst_severity` and used to color trend chart dots on the Dashboard.

---

## Roles

| Role    | Exclusive Access |
|---------|-----------------|
| Admin   | Users           |
| Coach   | Pitchers        |
| Pitcher | —               |

All roles share: Dashboard, Start Session, and Account Settings. New accounts default to **Pitcher**. An Admin must assign Coach roles manually.

---

## Name Validation Rules

Names entered during signup and profile updates follow these rules:

- Letters (including accented characters), spaces, hyphens, and apostrophes only
- Each word must be at least 2 characters — single-letter words (e.g. `"B Smith"`) are rejected
- Each word must start with a capital letter
- No consecutive spaces, hyphens, or apostrophes
- No leading or trailing hyphens or apostrophes
- Recognised suffixes are allowed at the end: `Jr.`, `Sr.`, `II`, `III`, `IV`, `V`, `VI`, `VII`, `VIII`
- Suffixes must use the formal form — `Jr.` and `Sr.` require the trailing period; bare `Jr` or `Sr` without a period are rejected
- Any other use of a period (e.g. `Dr.`, `John.Doe`) is rejected

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
| `matplotlib`                | Required internally by MediaPipe           |
| `sounddevice`               | Audio playback (alert / set-go sounds)     |
| `soundfile`                 | MP3/WAV decoding for sounddevice           |

---

## Gitignore Highlights

The following are intentionally excluded from version control:

- `venv/`, `__pycache__/`, `*.pyc`
- `.env`, `*.db`
- `models/`, `pose_landmarker_heavy.task`, `*.pt`, `*.pkl`, `*.npy`, `*.task`
- `output/`
- `installer/`, `dist/`, `build/`
- `.vscode/`
