from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import mktime
from typing import Any
from urllib.parse import quote_plus

import feedparser

QUERIES = (
    ("US-Iran War", "US-Iran War"),
    ("UAE economy", "UAE economy"),
)
LIMIT = 5
USER_AGENT = "economic-recovery-dashboard/1.0 (+local)"


def _feed_url(query: str) -> str:
    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )


def _published_iso(entry: Any) -> str | None:
    if getattr(entry, "published_parsed", None):
        return datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc).isoformat()
    raw = getattr(entry, "published", None)
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def fetch_news(limit: int = LIMIT) -> dict[str, Any]:
    per_topic = max(1, (limit + len(QUERIES) - 1) // len(QUERIES))
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()

    for label, query in QUERIES:
        parsed = feedparser.parse(
            _feed_url(query),
            agent=USER_AGENT,
            request_headers={"User-Agent": USER_AGENT},
        )
        topic_items: list[dict[str, Any]] = []
        for entry in parsed.entries:
            link = (getattr(entry, "link", None) or "").strip()
            title = (getattr(entry, "title", None) or "").strip()
            if not link or not title or link in seen:
                continue
            source = ""
            if getattr(entry, "source", None) is not None:
                source = (getattr(entry.source, "title", None) or "").strip()
            topic_items.append(
                {
                    "title": title,
                    "url": link,
                    "source": source or "Google News",
                    "published": _published_iso(entry),
                    "topic": label,
                }
            )
        topic_items.sort(
            key=lambda row: _published_ts_from_iso(row.get("published")),
            reverse=True,
        )
        for row in topic_items[:per_topic]:
            seen.add(row["url"])
            picked.append(row)

    picked.sort(key=lambda row: _published_ts_from_iso(row.get("published")), reverse=True)
    return {
        "queries": [label for label, _ in QUERIES],
        "items": picked[:limit],
    }


def _published_ts_from_iso(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return 0.0
