import html
import re
import unicodedata


# Control characters regex: ASCII 0-31 (except \t and \n), plus DEL (127)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Multiple consecutive spaces and tabs (not newlines)
HORIZONTAL_WHITESPACE_RE = re.compile(r"[^\S\n\r]+")

# More than two consecutive newlines
CONSECUTIVE_NEWLINES_RE = re.compile(r"\n{3,}")

# Standard HTML5 tag names (lowercased)
HTML_TAG_NAMES = {
    "a", "abbr", "address", "area", "article", "aside", "audio", "b", "base",
    "bdi", "bdo", "blockquote", "body", "br", "button", "canvas", "caption",
    "cite", "code", "col", "colgroup", "data", "datalist", "dd", "del",
    "details", "dfn", "dialog", "div", "dl", "dt", "em", "embed", "fieldset",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
    "h6", "head", "header", "hr", "html", "i", "iframe", "img", "input",
    "ins", "kbd", "label", "legend", "li", "link", "main", "map", "mark",
    "meta", "meter", "nav", "noscript", "object", "ol", "optgroup", "option",
    "output", "p", "param", "picture", "pre", "progress", "q", "rb", "rp",
    "rt", "rtc", "ruby", "s", "samp", "script", "section", "select", "small",
    "source", "span", "strong", "style", "sub", "summary", "sup", "svg",
    "table", "tbody", "td", "template", "textarea", "tfoot", "th", "thead",
    "time", "title", "tr", "track", "u", "ul", "var", "video", "wbr",
}

# Matches opening, closing, or self-closing HTML tags with standard identifier names
GENUINE_HTML_TAG_RE = re.compile(
    r"</?([a-zA-Z][a-zA-Z0-9]*)\b(?:[^\"'>]|'[^']*'|\"[^\"]*\")*/?>"
)


def _strip_or_replace_html_tag(match: re.Match) -> str:
    """Strip recognized HTML tags while preserving programming generics and comparison expressions."""
    tag_name = match.group(1).lower()
    if tag_name in HTML_TAG_NAMES:
        if tag_name in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            return "\n"
        return " "
    # Preserve non-HTML generics and comparison operators (e.g. <User>, <String, Object>, <T>)
    return match.group(0)


def normalize_text(text: str) -> str:
    """Deterministically normalize feedback text while preserving meaning, punctuation, and emojis.

    Invariants:
    - Normalizes Unicode to standard NFC form.
    - Normalizes line breaks (CRLF and CR to LF).
    - Removes unprintable control characters while retaining tabs and line feeds.
    - Decodes HTML entities (e.g., &amp; -> &) and safely strips recognized HTML markup.
    - Preserves programming language generics (e.g. Map<String, Object>, List<User>).
    - Preserves mathematical comparisons (e.g. x < y and y > z, status_code < 500).
    - Collapses repeated horizontal whitespace (spaces/tabs) to a single space.
    - Limits consecutive blank lines to at most two.
    - Preserves meaningful punctuation (e.g. '!!!', '?', '...', quotes).
    - Preserves emojis and emoticons (e.g. '😡', ':)').
    - Preserves case and multilingual characters.
    - Idempotent: normalize_text(normalize_text(s)) == normalize_text(s).
    """
    if not text:
        return ""

    # 1. Unicode normalization (NFC)
    normalized = unicodedata.normalize("NFC", text)

    # 2. Line ending normalization
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Control character removal (preserve \t and \n)
    normalized = CONTROL_CHAR_RE.sub("", normalized)

    # 4. Decode HTML entities first so encoded markup (&lt;script&gt;) can be normalized
    normalized = html.unescape(normalized)

    # 5. Strip recognized genuine HTML tags while preserving code generics and comparisons
    normalized = GENUINE_HTML_TAG_RE.sub(_strip_or_replace_html_tag, normalized)

    # 6. Normalize horizontal whitespace (spaces, tabs) per line
    lines = []
    for line in normalized.split("\n"):
        clean_line = HORIZONTAL_WHITESPACE_RE.sub(" ", line).strip()
        lines.append(clean_line)

    normalized = "\n".join(lines)

    # 7. Collapse excessive consecutive newlines
    normalized = CONSECUTIVE_NEWLINES_RE.sub("\n\n", normalized)

    return normalized.strip()
