import re
import urllib.parse
from functools import lru_cache

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup

API_URL = "https://en.wikipedia.org/w/api.php"

NON_ARTICLE_PREFIXES = {
    "wikipedia", "help", "file", "category", "talk", "special", "portal",
    "template", "user", "draft", "module", "mediawiki", "book", "image",
}

session = requests.Session()
session.headers.update({"User-Agent": "Wikipedia game script"})
session.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(
        total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]
    )),
)


def href_to_title(href):
    raw = href[len("/wiki/") :].split("#", 1)[0]
    if ":" in raw and raw.split(":", 1)[0].lower() in NON_ARTICLE_PREFIXES:
        return None
    return urllib.parse.unquote(raw).replace("_", " ").strip() or None


def normalize_title(title):
    return re.sub(r"\s+", " ", title.strip().replace("_", " "))


@lru_cache(maxsize=2048)
def _most_frequent_links_cached(title, limit=6):
    """Cached internal helper returning a tuple of ranked wiki titles."""
    resp = session.get(
        API_URL,
        params={
            "action": "parse",
            "page": title,
            "format": "json",
            "prop": "text",
            "redirects": True,
        },
        timeout=15,
    )
    resp.raise_for_status()
    parse = resp.json().get("parse")
    if not parse:
        return ()

    soup = BeautifulSoup(parse["text"]["*"], "html.parser")
    content = soup.find("div", class_="mw-parser-output")
    if not content:
        return ()

    candidate_links = set()
    for a in content.find_all("a", href=True):
        href = a.get("href", "")
        if href.startswith("/wiki/") and ":" not in href and "#" not in href:
            link = href_to_title(href)
            if link:
                candidate_links.add(normalize_title(link))

    if not candidate_links:
        return ()

    text = content.get_text(" ", strip=True)
    counts = {}
    lower_text = text.lower()
    for title_name in candidate_links:
        counts[title_name] = lower_text.count(title_name.lower())

    ranked = sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    )

    return tuple(title_name for title_name, _ in ranked[:limit])


def most_frequent_links(title, limit=6):
    """Return the most frequent wiki-linked titles by exact phrase count (Ctrl+F style)."""
    return list(_most_frequent_links_cached(title, limit=limit))