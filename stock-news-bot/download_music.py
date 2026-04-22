"""
One-time script to download royalty-free music tracks for reels.
Run locally: python download_music.py
Tracks from Pixabay — free for commercial use, no attribution required.
"""

import os
import urllib.request

MUSIC_DIR = os.path.join(os.path.dirname(__file__), "music")
os.makedirs(MUSIC_DIR, exist_ok=True)

TRACKS = [
    {
        "name": "track1.mp3",
        "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3",
        "desc": "Upbeat Corporate"
    },
    {
        "name": "track2.mp3",
        "url": "https://cdn.pixabay.com/download/audio/2022/08/02/audio_884fe92c21.mp3",
        "desc": "Corporate Background"
    },
    {
        "name": "track3.mp3",
        "url": "https://cdn.pixabay.com/download/audio/2023/03/09/audio_c3e8e5e9e8.mp3",
        "desc": "Business Upbeat"
    },
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

for track in TRACKS:
    path = os.path.join(MUSIC_DIR, track["name"])
    if os.path.exists(path):
        print(f"  Already exists: {track['name']}")
        continue
    print(f"  Downloading {track['desc']}...")
    try:
        req = urllib.request.Request(track["url"], headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as f:
            f.write(r.read())
        size = os.path.getsize(path)
        if size < 10000:
            os.remove(path)
            print(f"  [!] {track['name']} too small ({size} bytes) — skipped")
        else:
            print(f"  [✓] Saved {track['name']} ({size//1024}KB)")
    except Exception as e:
        print(f"  [!] Failed: {e}")

print("\nDone. Run: git add stock-news-bot/music/ && git commit -m 'add: royalty-free music tracks'")
