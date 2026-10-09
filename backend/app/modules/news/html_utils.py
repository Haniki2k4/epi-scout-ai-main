"""Small helpers for cleaning text received from news feeds and pages."""
import html
import re
from urllib.parse import urlparse


def decode_html_entities(text: str) -> str:
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return text


def trim_feed_related_titles(text: str, feed_url: str) -> str:
    """Remove headline lists concatenated to the VNA RSS description.

    VNA emits one lead sentence followed immediately by related headlines in
    the same text node, for example ``...thở máy.Bộ Y tế yêu cầu...``. The
    missing whitespace is the only reliable boundary in that feed. Keep this
    rule source-specific so multi-sentence descriptions from other publishers
    are not truncated.
    """
    if urlparse(feed_url).netloc.lower().removeprefix("www.") != "vnanet.vn":
        return text

    boundary = re.search(r"(?<=[.!?])(?=[A-ZÀ-ỸĐ\d“‘])", text)
    return text[: boundary.start()].strip() if boundary else text
