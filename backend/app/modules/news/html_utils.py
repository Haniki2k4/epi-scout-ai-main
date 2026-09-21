"""Decode nested HTML entities from RSS feeds and stored headlines."""
import html


def decode_html_entities(text: str) -> str:
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return text
