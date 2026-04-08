# Perfect Pitch

A desktop application for managing baseball pitching sessions, built with Python and PyQt6.

---

## Features

- **Role-based access** — Admin, Coach, and Pitcher roles with tailored navigation and permissions
- **Authentication** — Secure login and signup with bcrypt password hashing
- **Password recovery** — Email and date of birth verification with a 3-attempt, 30-minute lockout
- **Show/hide password** — Toggle visibility on all password fields across the auth window
- **Session tracking** — Log and review pitching sessions with accuracy and mistake stats
- **Dashboard** — Per-user performance overview across all sessions
- **Pitcher management** — Coaches can view and manage their assigned pitchers
- **User management** — Admins can view all users and assign roles
- **Dark theme** — Fully styled dark UI using PyQt6 and a custom QSS stylesheet
- **Frameless windows** — Custom minimize/close controls with themed confirmation dialogs

---

## Project Structure

```
perfect-pitch/
├── assets/
│   ├── icons/                        # SVG icons (Tabler Icons)
│   │   ├── ball-baseball.svg
│   │   ├── calendar-week.svg
│   │   ├── eye.svg
│   │   ├── eye-closed.svg
│   │   ├── help.svg
│   │   ├── home.svg
│   │   ├── logout.svg
│   │   ├── play-handball.svg
│   │   ├── settings.svg
│   │   ├── users.svg
│   │   └── users-group.svg
│   ├── app_icon.ico
│   └── side-banner.png
├── src/
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── login_page.py
│   │   │   ├── signup_page.py
│   │   │   └── forgot_password_page.py
│   │   ├── dashboard_page.py
│   │   ├── start_session_page.py
│   │   ├── pitchers_page.py
│   │   ├── users_page.py
│   │   ├── tutorial_page.py
│   │   └── account_settings_page.py
│   ├── styles/
│   │   └── global.qss
│   ├── utils/
│   │   ├── animations.py
│   │   ├── icons.py
│   │   └── toast.py
│   ├── widgets/
│   │   ├── confirm_dialog.py
│   │   ├── password_input.py
│   │   └── window_buttons.py
│   ├── windows/
│   │   ├── auth_window.py
│   │   └── main_window.py
│   ├── config.py
│   └── db.py
├── .env
├── .gitignore
├── main.py
└── requirements.txt
```

---

## Requirements

- Python 3.11+
- Windows (frameless window support via `pywin32` and `PyQt6-Frameless-Window`)

---

## Setup

### 1. Clone the repository

```powershell
git clone https://github.com/krpoblete/perfect-pitch.git
cd perfect-pitch
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv --upgrade-deps
venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Run the app

```powershell
python main.py
```

### TESTING. Configure environment variables

Create a `.env` file in the project root:

```env
DB_NAME=perfect_pitch.db
APP_NAME=Perfect Pitch
APP_VERSION=1.0.0
```

---

## Default Admin Account

On first launch, a default Admin account is seeded automatically:

| Field    | Value        |
|----------|--------------|
| Email    | `admin`      |
| Password | `admin1234`  |

> **Change the default password after first login.**

---

## Dependencies

| Package                     | Purpose                          |
|-----------------------------|----------------------------------|
| `PyQt6`                     | UI framework                     |
| `PyQt6-Frameless-Window`    | Frameless window support         |
| `pyqt-toast-notification`   | Toast notifications              |
| `bcrypt`                    | Password hashing                 |
| `python-dotenv`             | Environment variable loading     |
| `pywin32`                   | Windows taskbar integration      |

---

## Roles

| Role    | Exclusive Access |
|---------|-----------------|
| Admin   | Users           |
| Coach   | Pitchers        |
| Pitcher | —               |

All roles share: Dashboard, Start Session, Tutorial, and Account Settings. New accounts default to **Pitcher**. An Admin must assign Coach roles manually.