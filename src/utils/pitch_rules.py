from datetime import date as _date

# USA Baseball age-bracket daily limits
PITCH_LIMITS: list[tuple[int, int, int]] = [
    (13, 16, 95),
    (17, 18, 105),
    (19, 22, 120),
]

_FLOOR = 95  # age < 13 (signup minimum)
_CEIL = 120  # age > 22

def get_age(dob_str: str) -> int:
    """Return the current age in whole years from an ISO date string."""
    try:
        dob = _date.fromisoformat(dob_str)
        today = _date.today()
        return today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )
    except Exception:
        return 0
    
def get_pitch_limit(dob_str: str) -> int:
    """
    Return the recommended daily pitch limit for a player based on date of birth.
 
    Age < 13  → 95  (signup floor — youngest allowed)
    13 — 16   → 95
    17 — 18   → 105
    19 — 22   → 120
    Age > 22  → 120 (ceiling)
    """
    age = get_age(dob_str)
    for min_age, max_age, limit in PITCH_LIMITS:
        if min_age <= age <= max_age:
            return limit
    return _CEIL if age > 22 else _FLOOR
