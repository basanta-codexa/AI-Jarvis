import io
import json
import urllib.error
from contextlib import nullcontext

from ai_jarvis.core.lookup import wikipedia_search, wikipedia_summary


def fake_opener(payload, recorder=None):
    """Return an opener that serves *payload* as a fake HTTP response."""
    body = json.dumps(payload).encode("utf-8") if not isinstance(payload, bytes) else payload

    def opener(request, timeout=None):
        if recorder is not None:
            recorder.append((request, timeout))
        return nullcontext(io.BytesIO(body))

    return opener


def test_wikipedia_summary_returns_extract_and_builds_correct_request():
    seen = []
    opener = fake_opener(
        {
            "query": {
                "pages": {
                    "123": {
                        "title": "Python (programming language)",
                        "extract": "Python is a high-level programming language.",
                    }
                }
            }
        },
        recorder=seen,
    )

    result = wikipedia_summary("Python programming", opener=opener)

    assert result == "Python is a high-level programming language."
    request, timeout = seen[0]
    assert "titles=Python+programming" in request.full_url
    assert "explaintext=1" in request.full_url
    assert request.headers["User-agent"] == "AI-JARVIS/2.0 (personal assistant; contact: local user)"
    assert timeout == 5.0


def test_wikipedia_summary_collapses_whitespace_and_truncates():
    long_text = "word " * 400
    opener = fake_opener({"query": {"pages": {"1": {"extract": long_text}}}})

    result = wikipedia_summary("anything", opener=opener)

    assert "\n" not in result
    assert len(result) <= 601
    assert result.endswith("…")


def test_wikipedia_summary_returns_none_for_missing_page():
    opener = fake_opener({"query": {"pages": {"-1": {"missing": "", "title": "Nope"}}}})

    assert wikipedia_summary("no such page", opener=opener) is None


def test_wikipedia_summary_returns_none_for_empty_query():
    assert wikipedia_summary("   ", opener=fake_opener({})) is None


def test_wikipedia_summary_survives_network_error():
    def broken(request, timeout=None):
        raise urllib.error.URLError("offline")

    assert wikipedia_summary("Python", opener=broken) is None


def test_wikipedia_summary_survives_bad_json():
    opener = fake_opener(b"<html>not json</html>")

    assert wikipedia_summary("Python", opener=opener) is None


def test_wikipedia_search_returns_clean_titles_and_snippets():
    seen = []
    opener = fake_opener(
        {
            "query": {
                "search": [
                    {
                        "title": "Artificial intelligence",
                        "snippet": '<span class="searchmatch">AI</span> &amp; machine learning',
                    },
                    {"title": "Machine learning", "snippet": "A field of study."},
                ]
            }
        },
        recorder=seen,
    )

    result = wikipedia_search("AI & machine learning", opener=opener)

    assert "Artificial intelligence: AI & machine learning" in result
    assert "Machine learning: A field of study." in result
    assert "<span" not in result
    assert "srsearch=AI+%26+machine+learning" in seen[0][0].full_url
    assert "srlimit=3" in seen[0][0].full_url


def test_wikipedia_search_returns_none_for_empty_results_or_query():
    assert wikipedia_search("nothing", opener=fake_opener({"query": {"search": []}})) is None
    assert wikipedia_search("  ", opener=fake_opener({})) is None


def test_wikipedia_search_survives_network_error():
    def broken(request, timeout=None):
        raise OSError("offline")

    assert wikipedia_search("AI", opener=broken) is None
