import re

# Allowed: letters (incl. accented), spaces, hyphens, apostrophes
_NAME_ALLOWED = re.compile(r"^[a-zA-ZÀ-ÿ\s\-']+$")
_CONSEC_SPECIAL = re.compile(r"[\s\-']{2,}")        # 2+ consecutive specials
_EDGE_SPECIAL = re.compile(r"^[\s\-']|[\s\-']$")    # leading/trailing special

# Recognised name suffixes — stored as frozenset for O(1) lookup.
# Only these exact tokens are accepted; anything else with a period is rejected.
_VALID_SUFFIXES: frozenset = frozenset({
    "Jr.",
    "Sr.",
    "II", "III", "IV", "V", "VI", "VII", "VIII",
})

# Matches a recognised suffix preceded by whitespace at end-of-string.
_SUFFIX_RE = re.compile(
    r"\s+(" + "|".join(re.escape(s) for s in _VALID_SUFFIXES) + r")$"
)

def validate_name(value: str, field: str = "Name") -> tuple:
    """
    Validate a first or last name.
    Returns (True, "") on success or (False, error_message) on failure.

    Rules:
        - Letters, spaces, hyphens, apostrophes only
        - Recognized suffixes (Jr., Sr., III, IV, ...) allowed at the end
        - No digits or other special characters
        - No consecutive spaces/hyphens/apostrophes
        - No leading or trailing spaces/hyphens/apostrophes
        - Minimum 2 characters (excluding suffix)
        - Each word must start with a capital letter 
    """
    v = value.strip()

    # Strip a recognised suffix before all other checks.
    m = _SUFFIX_RE.search(v)
    if m:
        base = v[: m.start()].strip()
    else:
        # No valid suffix — but any period means an invalid one (e.g. "Dr.", "John.Doe").
        if "." in v:
            return False, (
                f"{field} contains an invalid suffix or character. "
                f"Accepted suffixes: Jr., Sr., II, III, IV, V, VI, VII, VIII."
            )
        base = v

    # Run all core checks on the base name (suffix stripped).
    # Reject bare Jr/Sr (no period) — they pass the letter check but we
    # require the period for consistent formal formatting.
    if re.search(r"\b(Jr|Sr)$", base, re.IGNORECASE):
        return False, (
            f"{field} — use Jr. or Sr. with a period (e.g., John Jr.)."
        )
    if len(base) < 2:
        return False, f"{field} must be at least 2 characters."
    if not _NAME_ALLOWED.match(base):
        return False, (
            f"{field} may only contain letters, spaces, hyphens, and apostrophes."
        )
    if _CONSEC_SPECIAL.search(base):
        return False, (
            f"{field} cannot have consecutive spaces, hyphens, or apostrophes."
        )
    if _EDGE_SPECIAL.search(base):
        return False, (
            f"{field} cannot start or end with a hyphen or apostrophe."
        )

    # Each word (split by space or hyphen) must start with a capital letter
    words = re.split(r"[\s\-]+", v)
    for word in words:
        if word and not word[0].isupper():
            return False, (
                f"{field} — each word must start with a capital letter "
                f"(e.g., 'John Mark')."
            )

    return True, ""

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

ALLOWED_DOMAINS = {"cvsu.edu.ph", "gmail.com", "yahoo.com", "outlook.com"}

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
