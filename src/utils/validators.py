import re

_NAME_ALLOWED = re.compile(r"^[a-zA-ZÀ-ÿ\s\-']+$")
_CONSEC_SPECIAL = re.compile(r"[\s\-']{2,}")
_EDGE_SPECIAL = re.compile(r"^[\s\-']|[\s\-']$")

def validate_name(value: str, field: str = "Name") -> tuple[bool, str]:
    """
    Validate a first or last name.
    Returns (True, "") on success or (False, error_message) on failure.
    Rules:
        - Letters, spaces, hyphens, apostrophes only
        - No digits or other special characters
        - No consecutive spaces/hyphens/apostrophes
        - No leading or trailing spaces/hyphens/apostrophes
        - Minimum 2 characters 
    """
    v = value.strip()
    if len(v) < 2:
        return False, f"{field} must be at least 2 characters."
    if not _NAME_ALLOWED.match(v):
        return False, f"{field} may only contain letters, spaces, hyphens, and apostrophes."
    if _CONSEC_SPECIAL.search(v):
        return False, f"{field} cannot have consecutive spaces, hyphens, or apostrophes."
    if _EDGE_SPECIAL.search(v):
        return False, f"{field} cannot start or end with a hyphen or apostrophe."
    return True, ""
