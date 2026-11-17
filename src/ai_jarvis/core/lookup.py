"""Small, dependency-free factual lookup used to ground AI answers.

Wikipedia's public API needs no key. This module never raises: a lookup is
an optional enrichment, so any failure simply returns None.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from typing import Callable, Optional

_API_URL = "https://en.wikipedia.org/w/api.php"
_USER_AGENT = "AI-JARVIS/2.0 (personal assistant; contact: local user)"
_MAX_CHARS = 600


def wikipedia_summary(
    query: str,
    timeout: float = 5.0,
    opener: Optional[Callable] = None,
) -> str | None:
    """Return a short factual extract about *query*, or None on any failure.

    ``opener`` is injectable for testing and defaults to urlopen. The request
    carries a User-Agent because Wikipedia rejects unidentified clients.
    """
    if not query or not query.strip():
        return None

    params = urllib.parse.urlencode(
        {
            "action": "query",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "redirects": "1",
            "format": "json",
            "titles": query.strip(),
        }
    )
    request = urllib.request.Request(
        f"{_API_URL}?{params}",
        headers={"User-Agent": _USER_AGENT},
    )
    fetch = opener or urllib.request.urlopen

    try:
        with fetch(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        pages = payload["query"]["pages"]
        for page in pages.values():
            extract = page.get("extract", "")
            if not extract or "missing" in page:
                continue
            text = " ".join(extract.split())
            if len(text) > _MAX_CHARS:
                text = text[:_MAX_CHARS].rsplit(" ", 1)[0] + "…"
            return text
        return None
    except Exception:
        return None


def wikipedia_search(
    query: str,
    limit: int = 3,
    timeout: float = 5.0,
    opener: Optional[Callable] = None,
) -> str | None:
    """Return top article titles with short snippets for a broad query.

    Uses the same key-free API. Wikipedia snippets contain search-highlight
    HTML and entities, so those are stripped before returning.
    """
    if not query or not query.strip():
        return None

    params = urllib.parse.urlencode(
        {
            "action": "query",
            "list": "search",
            "srsearch": query.strip(),
            "srlimit": str(limit),
            "format": "json",
        }
    )
    request = urllib.request.Request(
        f"{_API_URL}?{params}",
        headers={"User-Agent": _USER_AGENT},
    )
    fetch = opener or urllib.request.urlopen

    try:
        with fetch(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        lines = []
        for item in payload.get("query", {}).get("search", [])[:limit]:
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            snippet = html.unescape(re.sub(r"<[^>]+>", "", str(item.get("snippet", ""))))
            snippet = " ".join(snippet.split())
            if len(snippet) > 240:
                snippet = snippet[:240].rsplit(" ", 1)[0] + "…"
            lines.append(f"{title}: {snippet}" if snippet else title)
        return "\n".join(lines) or None
    except Exception:
        return None
