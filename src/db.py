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
            throwing_hand TEXT NOT NULL DEFAULT 'RHP'
                CHECK(throwing_hand IN ('RHP', 'LHP')),
            is_active INTEGER NOT NULL DEFAULT 1,
            deleted_at TEXT DEFAULT NULL,
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
    _purge_expired(conn)
    conn.close()

def _migrate(conn):
    """Add new columns to existing databases without breaking them."""
    existing = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "pitch_threshold" not in existing:
        conn.execute("ALTER TABLE users ADD COLUMN pitch_threshold INTEGER DEFAULT NULL")
    if "is_active" not in existing:
        conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    if "deleted_at" not in existing:
        conn.execute("ALTER TABLE users ADD COLUMN deleted_at TEXT DEFAULT NULL")
    if "throwing_hand" not in existing:
        conn.execute("ALTER TABLE users ADD COLUMN throwing_hand TEXT NOT NULL DEFAULT 'RHP' CHECK(throwing_hand IN ('RHP', 'LHP'))")
    conn.commit()

RETENTION_DAYS = 90

def _purge_expired(conn):
    """Permanently delete users inactive for longer than RETENTION_DAYS."""
    conn.execute("""
        DELETE FROM sessions WHERE user_id IN (
            SELECT id from users
            WHERE is_active = 0
            AND deleted_at IS NOT NULL
            AND julianday('now') - julianday(deleted_at) > ?
        )
    """, (RETENTION_DAYS,))
    conn.execute("""
        DELETE FROM users
        WHERE is_active = 0
        AND deleted_at IS NOT NULL
        AND julianday('now') - julianday(deleted_at) > ?
    """, (RETENTION_DAYS,))
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

def create_user(first_name, last_name, date_of_birth, email, password,
                throwing_hand: str = "RHP"):
    """Register a new user. If a soft-deleted account exists with the same
    email, restore it with the new credentials instead."""
    conn = get_connection()
    try:
        # Check for an inactive account with the same email
        existing = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 0",
            (email,)
        ).fetchone()

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        threshold = _calc_threshold(date_of_birth)

        if existing:
            # Restore the account with fresh credentials and profile
            conn.execute("""
                UPDATE users SET
                    first_name = ?,
                    last_name = ?,
                    date_of_birth = ?,
                    password = ?,
                    pitch_threshold = ?,
                    throwing_hand = ?,
                    is_active = 1,
                    deleted_at = NULL
                WHERE email = ? AND is_active = 0
            """, (first_name, last_name, date_of_birth,
                  hashed.decode('utf-8'), threshold, throwing_hand, email))
            conn.commit()
            return True, "restored"
        
        # Check for an already active account
        active = conn.execute(
            "SELECT id FROM users WHERE email = ? AND is_active = 1",
            (email,)
        ).fetchone()
        if active:
            return False, "Email already registered."

        # Brand new account
        conn.execute(
            """INSERT INTO users
                (first_name, last_name, date_of_birth, email, password,
                 role, pitch_threshold, throwing_hand) 
                VALUES (?, ?, ?, ?, ?, 'Pitcher', ?, ?)""",
            (first_name, last_name, date_of_birth, email, 
             hashed.decode('utf-8'), threshold, throwing_hand),
        )
        conn.commit()
        return True, "Account created successfully." 
    except sqlite3.IntegrityError:
        return False, "Email already registered."
    finally:
        conn.close()

def get_user_by_email(email):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)
    ).fetchone()
    conn.close()
    return row

def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)
    ).fetchone()
    conn.close()
    return row

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def get_all_users():
    """Admin: fetch all users regardless of active status."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return rows

def get_pitchers():
    """Coach: fetch all active users with role Pitcher."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM users WHERE role = 'Pitcher' AND is_active = 1 ORDER BY last_name"
    ).fetchall()
    conn.close()
    return rows

def deactivate_user(user_id: int) -> bool:
    """Soft-delete a user by marking them inactive and stamping deleted_at."""
    conn = get_connection()
    conn.execute(
        "UPDATE users SET is_active = 0, deleted_at = datetime('now') WHERE id = ?",
        (user_id,)
    )
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

def update_throwing_hand(user_id: int, hand: str) -> bool:
    """Update a user's throwing hand (RHP or LHP)."""
    if hand not in ("RHP", "LHP"):
        return False
    conn = get_connection()
    conn.execute(
        "UPDATE users SET throwing_hand = ? WHERE id = ?",
        (hand, user_id),
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

# Dashboard helpers
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

def get_coach_dashboard_stats():
    """Coach: combined stats across all active pitchers."""
    conn = get_connection()
    row = conn.execute("""
        SELECT 
            COUNT(DISTINCT s.id) AS total_sessions,
            COALESCE(SUM(s.total_pitch), 0) AS total_pitches,
            COALESCE(SUM(s.mistakes), 0) AS total_mistakes,
            COALESCE(AVG(s.total_pitch), 0) AS avg_pitch,
            COALESCE(AVG(s.mistakes), 0) AS avg_mistakes,
            COALESCE(AVG(s.accuracy), 0.0) AS avg_accuracy
        FROM sessions s
        INNER JOIN users u ON s.user_id = u.id
        WHERE u.role = 'Pitcher' AND u.is_active = 1 
    """).fetchone()
    conn.close()
    return row

def get_admin_dashboard_stats():
    """Admin: app-wide overview."""
    conn = get_connection()
    row = conn.execute("""
        SELECT 
            COUNT(*) AS total_users,
            SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_users,
            SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive_users,
            SUM(CASE WHEN role = 'Pitcher' AND is_active = 1 THEN 1 ELSE 0 END) AS total_pitchers,
            SUM(CASE WHEN role = 'Coach' AND is_active = 1 THEN 1 ELSE 0 END) AS total_coaches
        FROM users 
    """).fetchone()
    sessions = conn.execute(
        "SELECT COUNT(*) AS total_sessions FROM sessions"
    ).fetchone()
    conn.close()
    return row, sessions

def get_coach_pitcher_sessions():
    """Coach: recent sessions across all active pitchers with pitcher name."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            s.*,
            u.first_name || ' ' || u.last_name AS pitcher_name
        FROM sessions s
        INNER JOIN users u ON s.user_id = u.id
        WHERE u.role = 'Pitcher' AND u.is_active = 1
        ORDER BY s.date DESC
    """).fetchall()
    conn.close()
    return rows
