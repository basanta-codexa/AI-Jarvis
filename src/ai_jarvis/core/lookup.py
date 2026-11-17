"""Small, dependency-free factual lookup used to ground AI answers.

Wikipedia's public API needs no key. This module never raises: a lookup is
an optional enrichment, so any failure simply returns None.
"""
from __future__ import annotations

import json
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
