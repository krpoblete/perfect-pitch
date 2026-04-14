import sqlite3
import bcrypt
from src.config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            date_of_birth TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Pitcher'
                CHECK(role IN ('Admin', 'Coach', 'Pitcher')),
            pitch_threshold INTEGER DEFAULT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
                         
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT DEFAULT (datetime('now')),
            total_pitch INTEGER DEFAULT 0,
            mistakes INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0.0, 
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.commit()
    _seed_admin(conn)
    _migrate(conn)
    conn.close()

def _migrate(conn):
    """Add new columns to existing databases without breaking them."""
    existing = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "pitch_threshold" not in existing:
        conn.execute("ALTER TABLE users ADD COLUMN pitch_threshold INTEGER DEFAULT NULL")
    if "is_active" not in existing:
        conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1") 
    conn.commit()

def _seed_admin(conn):
    """Create the default Admin account if it doesn't exist yet."""
    existing = conn.execute(
        "SELECT id FROM users WHERE role = 'Admin' LIMIT 1"
    ).fetchone()

    if existing:
        return

    hashed = bcrypt.hashpw("admin1234".encode("utf-8"), bcrypt.gensalt())
    conn.execute(
        """INSERT INTO users
            (first_name, last_name, date_of_birth, email, password, role)
            VALUES (?, ?, ?, ?, ?, ?)""",
        ("Admin", "User", "2000-01-01",
        "admin",
        hashed.decode("utf-8"),
        "Admin"),
    )
    conn.commit()

# User helpers
def _calc_threshold(date_of_birth: str) -> int:
    """Calculate the default pitch threshold from DOB using USA Baseball guidelines."""
    from datetime import date
    PITCH_LIMITS = [
        (7, 8, 50),
        (9, 10, 75),
        (11, 12, 85),
        (13, 14, 95),
        (15, 16, 95),
        (17, 18, 105),
        (19, 22, 120),
    ]
    try:
        dob = date.fromisoformat(date_of_birth)
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        for min_age, max_age, limit in PITCH_LIMITS:
            if min_age <= age <= max_age:
                return limit
    except Exception:
        pass
    return 50

def create_user(first_name, last_name, date_of_birth, email, password):
    """Register a new user. Default role is Pitcher — Admin assigns later"""
    conn = get_connection()
    try:
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        threshold = _calc_threshold(date_of_birth)
        conn.execute(
            """INSERT INTO users
                (first_name, last_name, date_of_birth, email, password, role, pitch_threshold) 
                VALUES (?, ?, ?, ?, ?, 'Pitcher', ?)""",
            (first_name, last_name, date_of_birth, email, hashed.decode('utf-8'), threshold),
        )
        conn.commit()
        return True, "Account created successfully." 
    except sqlite3.IntegrityError:
        return False, "Email already registered."
    finally:
        conn.close()

def get_user_by_email(email):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row

def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def get_all_users():
    """Admin: fetch all users."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return rows

def get_pitchers():
    """Coach: fetch all users with role Pitcher."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM users WHERE role = 'Pitcher' AND is_active = 1 ORDER BY last_name"
    ).fetchall()
    conn.close()
    return rows

def deactivate_user(user_id: int) -> bool:
    """Soft-delete a user by marking them inactive."""
    conn = get_connection()
    conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

def update_user_role(user_id: int, role: str) -> bool:
    """Admin: assign a role to a user."""
    if role not in ("Admin", "Coach", "Pitcher"):
        return False
    conn = get_connection()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()
    return True

# Profile helpers
def update_user_profile(user_id: int, first_name: str, last_name: str) -> bool:
    """Update a user's first and last name.""" 
    conn = get_connection()
    conn.execute(
        "UPDATE users SET first_name = ?, last_name = ? WHERE id = ?",
        (first_name, last_name, user_id),
    )
    conn.commit()
    conn.close()
    return True

def update_user_password(user_id: int, new_password: str) -> bool:
    """Hash and update a user's password.""" 
    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
    conn = get_connection()
    conn.execute(
        "UPDATE users SET password = ? WHERE id = ?",
        (hashed.decode("utf-8"), user_id),
    )
    conn.commit()
    conn.close()
    return True

def update_pitch_threshold(user_id: int, threshold: int) -> bool:
    """Update a user's pitch threshold."""
    conn = get_connection()
    conn.execute(
        "UPDATE users SET pitch_threshold = ? WHERE id = ?",
        (threshold, user_id),
    )
    conn.commit()
    conn.close()
    return True

# Session helpers
def get_sessions_for_user(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM sessions WHERE user_id = ? ORDER BY date DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows

def get_dashboard_stats(user_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT 
            COUNT(*) AS total_sessions,
            COALESCE(SUM(total_pitch), 0) AS total_pitches,
            COALESCE(SUM(mistakes), 0) AS total_mistakes,
            COALESCE(AVG(total_pitch), 0) AS avg_pitch,
            COALESCE(AVG(mistakes), 0) AS avg_mistakes,
            COALESCE(AVG(accuracy), 0.0) AS avg_accuracy
        FROM sessions
        WHERE user_id = ?
    """, (user_id,)).fetchone()
    conn.close()
    return row
