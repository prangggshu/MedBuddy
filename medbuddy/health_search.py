"""Patient-facing search of MedlinePlus health topics."""
from __future__ import annotations

import html
import re
import threading
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


_URL = "https://wsearch.nlm.nih.gov/ws/query"
_CACHE_TTL = 12 * 60 * 60
_CACHE_LIMIT = 128
_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
_cache_lock = threading.Lock()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()


def search_medlineplus(query: str) -> list[dict[str, str]]:
    """Return up to five current MedlinePlus health-topic results, cached for 12 hours."""
    normalized = re.sub(r"\s+", " ", query).strip()
    cache_key = normalized.casefold()
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]

    params = urlencode({"db": "healthTopics", "term": normalized, "rettype": "brief", "retmax": 5, "tool": "medbuddy_web_chat"})
    request = Request(
        f"{_URL}?{params}",
        headers={"Accept": "application/xml", "User-Agent": "MedBuddy/0.1 (patient health-topic search)"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            root = ET.fromstring(response.read())
    except (URLError, TimeoutError, ET.ParseError) as exc:
        raise RuntimeError("MedlinePlus search is temporarily unavailable. Please try again.") from exc

    results: list[dict[str, str]] = []
    for document in root.findall(".//document"):
        url = document.attrib.get("url", "")
        parsed_url = urlsplit(url)
        if parsed_url.scheme != "https" or parsed_url.netloc.lower() not in {"medlineplus.gov", "www.medlineplus.gov"}:
            continue
        fields = {
            node.attrib.get("name", "").lower(): _plain_text("".join(node.itertext()))
            for node in document.findall("content")
        }
        title = fields.get("title")
        if not title:
            continue
        summary = fields.get("fullsummary") or fields.get("snippet") or "Open the MedlinePlus topic for details."
        results.append({"title": title, "summary": summary[:700], "url": url})
        if len(results) == 5:
            break

    with _cache_lock:
        if len(_cache) >= _CACHE_LIMIT:
            oldest = min(_cache, key=lambda key: _cache[key][0])
            _cache.pop(oldest, None)
        _cache[cache_key] = (time.monotonic(), results)
    return results
