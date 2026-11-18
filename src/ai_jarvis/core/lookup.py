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
import xml.etree.ElementTree as ET
from typing import Callable, Optional

_API_URL = "https://en.wikipedia.org/w/api.php"
_DDG_URL = "https://api.duckduckgo.com/"
_BING_RSS_URL = "https://www.bing.com/search"
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


def duckduckgo_answer(
    query: str,
    timeout: float = 5.0,
    opener: Optional[Callable] = None,
) -> str | None:
    """Return a short instant answer for a query, or None on any failure.

    Uses DuckDuckGo's JSON API (no key, no HTML scraping). Coverage is
    narrower than a full search, but the call is cheap and fails soft.
    """
    if not query or not query.strip():
        return None

    params = urllib.parse.urlencode(
        {
            "q": query.strip(),
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
    )
    request = urllib.request.Request(
        f"{_DDG_URL}?{params}",
        headers={"User-Agent": _USER_AGENT},
    )
    fetch = opener or urllib.request.urlopen

    try:
        with fetch(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        direct = str(payload.get("Answer") or "").strip()
        if direct:
            text = direct
        else:
            abstract = str(payload.get("AbstractText") or "").strip()
            if not abstract:
                return None
            source = str(payload.get("AbstractSource") or "").strip()
            text = f"[{source}] {abstract}" if source else abstract
        text = " ".join(text.split())
        if len(text) > _MAX_CHARS:
            text = text[:_MAX_CHARS].rsplit(" ", 1)[0] + "…"
        return text
    except Exception:
        return None


def web_results(
    query: str,
    limit: int = 3,
    timeout: float = 5.0,
    opener: Optional[Callable] = None,
) -> str | None:
    """Return top web results (title + snippet) from Bing's RSS feed.

    Key-free and XML-based, so no HTML scraping is involved. Suitable for
    current events that Wikipedia/DDG instant answers do not cover.
    Fail-soft: returns None on any problem.
    """
    if not query or not query.strip():
        return None

    params = urllib.parse.urlencode({"q": query.strip(), "format": "rss"})
    request = urllib.request.Request(
        f"{_BING_RSS_URL}?{params}",
        headers={"User-Agent": _USER_AGENT},
    )
    fetch = opener or urllib.request.urlopen

    try:
        with fetch(request, timeout=timeout) as response:
            root = ET.fromstring(response.read())
        lines = []
        for item in root.findall("./channel/item")[:limit]:
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            snippet = " ".join((item.findtext("description") or "").split())
            if len(snippet) > 240:
                snippet = snippet[:240].rsplit(" ", 1)[0] + "…"
            lines.append(f"{title}: {snippet}" if snippet else title)
        return "\n".join(lines) or None
    except Exception:
        return None
