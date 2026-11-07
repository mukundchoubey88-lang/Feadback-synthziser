import re
from typing import List, Tuple
import unicodedata

# Repeated characters pattern: 5 or more identical consecutive characters
REPEATED_CHAR_RE = re.compile(r"(.)\1{4,}")

# Obvious spam keywords and phrases (lowercased)
SPAM_PHRASES = (
    "buy cheap",
    "free followers",
    "click here to win",
    "crypto investment",
    "whatsapp +",
    "telegram @",
    "free gift card",
    "earn money fast",
    "subscribe to my channel",
    "visit our site",
    "get rich quick",
    "casino bonus",
)

# Keyboard mash patterns (home row sequences or vowel-less ASCII sequences >= 6 chars)
KEYBOARD_MASH_RE = re.compile(
    r"\b(asdfg|hjkl|qwerty|zxcvb|[bcdfghjklmnpqrstvwxz]{6,})\b",
    re.IGNORECASE,
)


def count_meaningful_unicode_chars(text: str) -> int:
    """Count letters, numbers, and combining marks across all Unicode scripts.

    Supports Latin, Hindi/Devanagari, Arabic, Cyrillic, Chinese, Japanese, Korean,
    and all Unicode-defined writing systems (general categories starting with L, N, or M).
    Punctuation, symbols, separators, and control characters return 0.
    """
    return sum(
        1
        for char in text
        if unicodedata.category(char)[0] in ("L", "N", "M")
    )


class SpamAndQualityDetector:
    """Deterministic spam, noise, and quality assessment engine."""

    @classmethod
    def assess_quality(cls, text: str, original_raw_text: str = "") -> Tuple[str, List[str]]:
        """Evaluate text for spam, noise, and completeness across all languages and scripts.

        Args:
            text: Normalized and redacted text.
            original_raw_text: Original raw input before normalization.

        Returns:
            Tuple[str, List[str]]:
                - quality_status: 'clean', 'flagged', or 'rejected'.
                - quality_flags: List of diagnostic flags explaining the assessment.
        """
        flags: List[str] = []
        stripped = text.strip()

        # 1. Empty or whitespace-only check
        if not stripped:
            flags.append("EMPTY_TEXT")
            return "rejected", flags

        # 2. Meaningless content check:
        # - Solely punctuation/symbols/control chars (meaningful Unicode chars < 2)
        meaningful_count = count_meaningful_unicode_chars(stripped)
        if meaningful_count < 2:
            flags.append("MEANINGLESS_TEXT")
            return "rejected", flags

        # - Obvious keyboard mash sequences (e.g. asdfghjkl, zxcvbnm)
        if KEYBOARD_MASH_RE.search(stripped):
            flags.append("MEANINGLESS_TEXT")
            return "flagged", flags

        # 3. URL-only check (text consists entirely of [URL] tokens or a standalone URL)
        without_urls = re.sub(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+|\[URL\]", "", stripped).strip()
        if not without_urls and (stripped.startswith(("http://", "https://", "www.")) or "[URL]" in stripped):
            flags.append("URL_ONLY")

        # 4. Repeated character noise check
        # Check either 5+ identical consecutive chars or excessive dominance of a single character
        if REPEATED_CHAR_RE.search(original_raw_text or stripped):
            flags.append("REPEATED_CHARS")
        elif len(stripped) >= 10:
            char_counts = {}
            for c in stripped.replace(" ", ""):
                char_counts[c] = char_counts.get(c, 0) + 1
            if char_counts and max(char_counts.values()) / sum(char_counts.values()) > 0.70:
                flags.append("REPEATED_CHARS")

        # 5. Obvious spam pattern check
        lower_text = stripped.lower()
        for phrase in SPAM_PHRASES:
            if phrase in lower_text:
                flags.append("SPAM_PATTERN")
                break

        # 6. Informational short-text flag (meaningful, but brief)
        if len(stripped) < 20:
            flags.append("VERY_SHORT")

        # Status determination
        if "EMPTY_TEXT" in flags or "MEANINGLESS_TEXT" in flags:
            return "rejected", flags
        elif "URL_ONLY" in flags or "REPEATED_CHARS" in flags or "SPAM_PATTERN" in flags:
            return "flagged", flags
        else:
            return "clean", flags
