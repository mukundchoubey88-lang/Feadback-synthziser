import re
from typing import List, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Emails: RFC 5322 compliant regex
EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# Identification patterns (SSN: 3-2-4 digits, Credit Card: 4x4 digits or 16 digits)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_RE = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")

# Strict IPv4 Address regex (each octet strictly 0-255, isolated from trailing/leading digits or dots)
IPV4_STRICT_RE = re.compile(
    r"(?<![\w.])(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])(?![\w.])"
)

# Software version prefix indicators (e.g. v1.2.0.0, version 1.2.0.0, build 1.2.0.0)
VERSION_PREFIX_RE = re.compile(
    r"(?i)\b(?:v|ver|version|build|release|rev)\s*[:=]?\s*$"
)

# Standard HTTP/HTTPS and www URLs
URL_RE = re.compile(
    r"\bhttps?://[^\s<>\"']+|www\.[^\s<>\"']+"
)

# Query parameter names containing sensitive keys/tokens/credentials
SENSITIVE_PARAM_KEYWORDS = (
    "token",
    "access_token",
    "api_key",
    "apikey",
    "key",
    "secret",
    "password",
    "pass",
    "pwd",
    "auth",
    "authorization",
    "email",
    "session",
    "sig",
    "signature",
    "client_secret",
)

# International Phone Number Patterns
# 1. France: 10 digits starting with 0 or +33, grouped by 2
FRANCE_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+33[\s.-]?|0)[1-9](?:[\s.-]?\d{2}){4}(?!\w)"
)

# 2. India: 10 digits starting with 6-9, optional +91 prefix
INDIA_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+91[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}(?!\w)"
)

# 3. UK: +44 or 0 followed by 9-10 digits, formatted with spaces or hyphens
UK_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+44[\s.-]?(?:\(0\))?|0)[1-9]\d{1,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?!\w)"
)

# 4. Germany: +49 or 0 followed by area code and local number
GERMANY_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+49[\s.-]?(?:\(0\))?|0)[1-9]\d{1,4}[\s.-]?\d{3,8}(?!\w)"
)

# 5. North America / Generic International with explicit + prefix
US_INTL_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[\s.-]?)?\(?[2-9]\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)"
)


def _is_software_version(match_str: str, full_text: str, start_idx: int) -> bool:
    """Determine whether a 4-part numeric sequence represents a software version rather than an IPv4 address."""
    # Context before the match
    preceding_text = full_text[max(0, start_idx - 15) : start_idx]
    if VERSION_PREFIX_RE.search(preceding_text):
        return True

    # Software versions frequently end with .0.0 or .0.1 (e.g., 1.2.0.0), which are not valid host IP addresses
    parts = match_str.split(".")
    if len(parts) == 4 and parts[2] == "0" and parts[3] == "0":
        return True

    return False


def _sanitize_url(raw_url: str) -> Tuple[str, bool]:
    """Preserve URL host and path while redacting sensitive parameters and credentials."""
    try:
        has_scheme = bool(re.match(r"^https?://", raw_url, re.IGNORECASE))
        url_to_parse = raw_url if has_scheme else f"http://{raw_url}"
        parsed = urlparse(url_to_parse)

        changed = False
        netloc = parsed.netloc

        # Strip user credentials (e.g. user:password@host)
        if "@" in netloc:
            changed = True
            netloc = netloc.split("@", 1)[1]

        # Sanitize query parameters
        query_parts = parse_qsl(parsed.query, keep_blank_values=True)
        new_query_parts = []
        for key, val in query_parts:
            lower_key = key.lower()
            if any(k in lower_key for k in SENSITIVE_PARAM_KEYWORDS):
                new_query_parts.append((key, "[REDACTED]"))
                changed = True
            else:
                new_query_parts.append((key, val))

        new_query = urlencode(new_query_parts) if new_query_parts else ""

        rebuilt = urlunparse((
            parsed.scheme if has_scheme else "",
            netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        ))

        if not has_scheme and rebuilt.startswith("//"):
            rebuilt = rebuilt[2:]

        return rebuilt, changed
    except Exception:
        return "[URL]", True


class PIIDetector:
    """Conservative, deterministic PII detection and redaction engine."""

    @classmethod
    def redact_pii(cls, text: str) -> Tuple[str, bool, List[str]]:
        """Identify PII patterns, replace sensitive values, and record discovered categories.

        Returns:
            Tuple[str, bool, List[str]]:
                - redacted_text: Text with sensitive values substituted.
                - pii_detected: Boolean flag indicating if any PII was discovered.
                - pii_types: Sorted list of unique PII category names found.
        """
        if not text:
            return "", False, []

        discovered_types = set()
        redacted = text

        # 1. URLs: Preserve safe host & path, redact credentials and sensitive query parameters.
        # Run before Email detection to ensure user:password@host is not misclassified as email.
        def _replace_url(match: re.Match) -> str:
            raw_url = match.group(0)
            cleaned_url, sensitive_found = _sanitize_url(raw_url)
            if sensitive_found:
                discovered_types.add("url")
            return cleaned_url

        redacted = URL_RE.sub(_replace_url, redacted)

        # 2. Emails
        if EMAIL_RE.search(redacted):
            discovered_types.add("email")
            redacted = EMAIL_RE.sub("[EMAIL]", redacted)

        # 3. Credit Cards & SSN
        if CREDIT_CARD_RE.search(redacted):
            discovered_types.add("credit_card")
            redacted = CREDIT_CARD_RE.sub("[ID_NUMBER]", redacted)

        if SSN_RE.search(redacted):
            discovered_types.add("ssn")
            redacted = SSN_RE.sub("[ID_NUMBER]", redacted)

        # 4. Phone Numbers (International and domestic formats)
        for phone_re in (FRANCE_PHONE_RE, INDIA_PHONE_RE, UK_PHONE_RE, GERMANY_PHONE_RE, US_INTL_PHONE_RE):
            if phone_re.search(redacted):
                discovered_types.add("phone")
                redacted = phone_re.sub("[PHONE]", redacted)

        # 5. IPv4 Addresses (distinguishing from software versions like 10.0.19041.1 and 1.2.0.0)
        def _replace_ip(match: re.Match) -> str:
            ip_str = match.group(0)
            if _is_software_version(ip_str, redacted, match.start()):
                return ip_str
            discovered_types.add("ip_address")
            return "[IP_ADDRESS]"

        redacted = IPV4_STRICT_RE.sub(_replace_ip, redacted)

        pii_detected = len(discovered_types) > 0
        return redacted, pii_detected, sorted(list(discovered_types))
