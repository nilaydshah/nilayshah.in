#!/usr/bin/env python3
"""Fetch public Substack posts into Hugo's data directory."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


FEED_URL = "https://theainativeengineer.substack.com/feed"
RSS2JSON_URL = (
    "https://api.rss2json.com/v1/api.json?rss_url="
    + urllib.parse.quote(FEED_URL, safe="")
)
USER_AGENT = "nilayshah.in Substack feed sync (+https://nilayshah.in/)"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "substack.json"
ITEM_LIMIT = 6


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self.parts).split())


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, application/json, text/xml",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def plain_text(value: str) -> str:
    parser = TextExtractor()
    parser.feed(html.unescape(value or ""))
    return parser.text()


def truncate(value: str, limit: int = 220) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    shortened = value[: limit + 1].rsplit(" ", 1)[0]
    return f"{shortened}…"


def first_image(value: str) -> str:
    match = re.search(r"<img[^>]+src=[\"']([^\"']+)", value or "", re.IGNORECASE)
    return html.unescape(match.group(1)) if match else ""


def normalized_date(value: str) -> tuple[str, str]:
    if not value:
        return "", ""

    parsed: datetime
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.isoformat(), f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def normalize_item(item: dict[str, Any]) -> dict[str, str]:
    content = item.get("content", "") or ""
    description = item.get("description", "") or ""
    date_iso, date_display = normalized_date(
        item.get("pubDate", "") or item.get("published", "")
    )

    return {
        "title": plain_text(item.get("title", "")),
        "link": item.get("link", ""),
        "date": date_iso,
        "dateDisplay": date_display,
        "summary": truncate(plain_text(description) or plain_text(content)),
        "image": item.get("thumbnail", "") or first_image(content) or first_image(description),
        "author": plain_text(item.get("author", "")),
    }


def parse_rss(payload: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(payload)
    namespace = {"content": "http://purl.org/rss/1.0/modules/content/"}
    items: list[dict[str, str]] = []

    for node in root.findall("./channel/item")[:ITEM_LIMIT]:
        content = node.findtext("content:encoded", default="", namespaces=namespace)
        enclosure = node.find("enclosure")
        image = ""
        if enclosure is not None and enclosure.attrib.get("type", "").startswith("image/"):
            image = enclosure.attrib.get("url", "")

        items.append(
            normalize_item(
                {
                    "title": node.findtext("title", default=""),
                    "link": node.findtext("link", default=""),
                    "pubDate": node.findtext("pubDate", default=""),
                    "description": node.findtext("description", default=""),
                    "content": content,
                    "thumbnail": image,
                    "author": node.findtext("author", default=""),
                }
            )
        )

    return items


def parse_rss2json(payload: bytes) -> list[dict[str, str]]:
    result = json.loads(payload)
    if result.get("status") != "ok":
        raise RuntimeError(f"RSS-to-JSON returned status {result.get('status')!r}")
    return [normalize_item(item) for item in result.get("items", [])[:ITEM_LIMIT]]


def write_data(items: list[dict[str, str]], source: str) -> None:
    if not items:
        raise RuntimeError("The Substack feed returned no posts")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "feed": FEED_URL,
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": source,
        "items": items,
    }
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(items)} Substack post(s) to {OUTPUT_PATH} using {source}.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="Keep the committed feed snapshot if all network sources fail.",
    )
    args = parser.parse_args()

    failures: list[str] = []
    sources = (
        ("direct RSS", FEED_URL, parse_rss),
        ("RSS-to-JSON fallback", RSS2JSON_URL, parse_rss2json),
    )

    for name, url, parse in sources:
        try:
            write_data(parse(fetch(url)), name)
            return 0
        except (OSError, ValueError, RuntimeError, ET.ParseError, json.JSONDecodeError) as error:
            failures.append(f"{name}: {error}")
            print(f"WARNING: {failures[-1]}", file=sys.stderr)

    if args.allow_stale and OUTPUT_PATH.exists():
        print(
            f"WARNING: All feed sources failed; using committed snapshot at {OUTPUT_PATH}.",
            file=sys.stderr,
        )
        return 0

    print("ERROR: Unable to refresh the Substack feed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
