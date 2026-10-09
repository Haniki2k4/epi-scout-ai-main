"""Resolve Google News RSS redirect URLs without adding dependencies."""
from functools import lru_cache
import base64
import json
import re
from urllib.parse import urlparse

import requests

_GOOGLE_HOST = "news.google.com"
_TIMEOUT_SECONDS = 10
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def is_google_news_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname == _GOOGLE_HOST and re.search(r"/(?:rss/)?(?:articles|read)/[^/?]+", parsed.path) is not None


def _article_id(url: str) -> str | None:
    match = re.search(r"/(?:articles|read)/([^/?]+)", urlparse(url).path)
    return match.group(1) if match else None


def _valid_source_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value if parsed.hostname != _GOOGLE_HOST else None


def _decode_embedded_url(article_id: str) -> str | None:
    try:
        padding = "=" * (-len(article_id) % 4)
        payload = base64.urlsafe_b64decode(article_id + padding)
        if payload.startswith(b"\x08\x13\x22"):
            payload = payload[3:]
        if payload.endswith(b"\xd2\x01\x00"):
            payload = payload[:-3]
        if not payload:
            return None
        length = payload[0]
        offset = 1
        if length >= 0x80:
            length = (length & 0x7F) | (payload[1] << 7)
            offset = 2
        return _valid_source_url(payload[offset:offset + length].decode("utf-8"))
    except (ValueError, UnicodeDecodeError, IndexError):
        return None


def _decode_dynamic_url(article_id: str) -> str | None:
    session = requests.Session()
    session.cookies.set("CONSENT", "PENDING+987", domain=".google.com")
    page_headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }
    page = session.get(
        f"https://news.google.com/articles/{article_id}",
        headers=page_headers,
        timeout=_TIMEOUT_SECONDS,
    )
    page.raise_for_status()
    signature_match = re.search(r'data-n-a-sg="([^"]+)"', page.text)
    timestamp_match = re.search(r'data-n-a-ts="([^"]+)"', page.text)
    if not signature_match or not timestamp_match:
        return None

    inner = [
        "garturlreq",
        [
            ["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
            "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0,
        ],
        article_id,
        int(timestamp_match.group(1)),
        signature_match.group(1),
    ]
    payload = json.dumps([[["Fbv4je", json.dumps(inner, separators=(",", ":"))]]], separators=(",", ":"))
    response = session.post(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        params={"rpcids": "Fbv4je"},
        data={"f.req": payload},
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": "https://news.google.com",
            "Referer": "https://news.google.com/",
            "X-Same-Domain": "1",
        },
        timeout=_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    parts = response.text.split("\n\n", 1)
    if len(parts) != 2:
        return None
    outer = json.loads(parts[1].strip())
    inner_response = json.loads(outer[0][2])
    return _valid_source_url(inner_response[1] if len(inner_response) > 1 else None)


@lru_cache(maxsize=2048)
def resolve_google_news_url(url: str) -> str:
    """Return the publisher URL, or the original URL when Google cannot resolve it."""
    if not is_google_news_url(url):
        return url
    article_id = _article_id(url)
    if not article_id:
        return url
    embedded = _decode_embedded_url(article_id)
    if embedded:
        return embedded
    try:
        return _decode_dynamic_url(article_id) or url
    except (requests.RequestException, ValueError, json.JSONDecodeError, IndexError, TypeError):
        return url

