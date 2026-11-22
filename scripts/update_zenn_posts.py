#!/usr/bin/env python3
"""Fetch latest articles from Zenn RSS feed and update README.md."""

from __future__ import annotations

import email.utils
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

FEED_URL = "https://zenn.dev/nalt/feed"
MAX_POSTS = 5
START_MARKER = "<!-- ZENN-POSTS:START -->"
END_MARKER = "<!-- ZENN-POSTS:END -->"
README_PATH = Path(__file__).resolve().parent.parent / "README.md"


def fetch_posts(limit: int = MAX_POSTS) -> list[tuple[str, str, str]]:
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_bytes = resp.read()

    root = ET.fromstring(xml_bytes)
    posts: list[tuple[str, str, str]] = []
    for item in root.findall("./channel/item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_raw = (item.findtext("pubDate") or "").strip()
        date_str = ""
        if pub_raw:
            try:
                dt = email.utils.parsedate_to_datetime(pub_raw)
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = ""
        if title and link:
            posts.append((date_str, title, link))
    return posts


def update_readme(posts: list[tuple[str, str, str]]) -> bool:
    content = README_PATH.read_text(encoding="utf-8")
    lines = [
        f"- `{date}` [{title}]({link})" if date else f"- [{title}]({link})"
        for date, title, link in posts
    ]
    replacement = f"{START_MARKER}\n" + "\n".join(lines) + f"\n{END_MARKER}"
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    if not pattern.search(content):
        raise RuntimeError("Markers not found in README.md")

    updated = pattern.sub(replacement, content, count=1)
    if updated == content:
        return False
    README_PATH.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    posts = fetch_posts()
    changed = update_readme(posts)
    print(f"Fetched {len(posts)} posts. README updated={changed}")


if __name__ == "__main__":
    main()
