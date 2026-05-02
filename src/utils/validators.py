import re

# Allowed: letters (incl. accented), spaces, hyphens, apostrophes
_NAME_ALLOWED = re.compile(r"^[a-zA-ZÀ-ÿ\s\-']+$")
_CONSEC_SPECIAL = re.compile(r"[\s\-']{2,}")        # 2+ consecutive specials
_EDGE_SPECIAL = re.compile(r"^[\s\-']|[\s\-']$")    # leading/trailing special

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
        - Each word must start with a capital letter 
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
    # Each word (split by space or hyphen) must start with a capital letter
    words = re.split(r"[\s\-]+", v)
    for word in words:
        if word and not word[0].isupper():
            return False, f"{field} — each word must start with a capital letter (e.g., 'John Mark')." 
    return True, ""

ALLOWED_DOMAINS = {"cvsu.edu.ph", "gmail.com", "yahoo.com", "outlook.com"}

def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength, collecting ALL failing rules at once.
    Returns (True, "") on success or (False, error_message) listing every issue.
    Rules:
        - At least 8 characters
        - At least one lowercase letter
        - At least one uppercase letter
        - At least one digit
    """
    errors = []
    if len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if not re.search(r"\d", password):
        errors.append("one number")
    if not errors:
        return True, ""
    if len(errors) == 1:
        msg = f"Password must contain {errors[0]}."
    else:
        joined = ", ".join(errors[:-1]) + f", and {errors[-1]}"
        msg = f"Password must contain {joined}."
    return False, msg


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email format and allowed domain."""
    import re
    if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$", email):
        return False, "Please enter a valid email address."
    domain = email.split("@")[-1].lower()
    if domain not in ALLOWED_DOMAINS:
        allowed = ", ".join(f"@{d}" for d in sorted(ALLOWED_DOMAINS))
        return False, f"Only {allowed} emails are allowed."
    return True, ""
