"""
Tracks which articles have already been posted to avoid duplicates.
Reads/writes posted.json in the repo root.
"""

import json
import os

TRACKER_FILE = os.path.join(os.path.dirname(__file__), "posted.json")


def load_posted():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_posted(posted: list):
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(posted, f, indent=2, ensure_ascii=False)


def is_posted(article, posted: list) -> bool:
    key = article["title"][:80].lower().strip()
    return any(key == p[:80].lower().strip() for p in posted)


def mark_posted(article, posted: list) -> list:
    posted.append(article["title"])
    # Keep only last 200 to avoid file bloat
    return posted[-200:]
