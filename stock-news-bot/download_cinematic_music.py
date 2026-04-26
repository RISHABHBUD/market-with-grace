"""
Download cinematic music for investment reels.
Run once: python download_cinematic_music.py
"""
import urllib.request, os

MUSIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")
os.makedirs(MUSIC_DIR, exist_ok=True)

TRACKS = [
    {
        "name": "cinematic_epic.mp3",
        "url": "https://cdn.pixabay.com/download/audio/2023/09/05/audio_168a3e0cdf.mp3",
        "desc": "Epic Cinematic"
    },
    {
        "name": "cinematic_inspire.mp3",
        "url": "https://cdn.pixabay.com/download/audio/2022/10/25/audio_946b4a8a4e.mp3",
        "desc": "Inspiring Cinematic"
    },
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

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
            print(f"  [!] Too small, skipped")
        else:
            print(f"  [✓] {track['name']} ({size//1024}KB)")
    except Exception as e:
        print(f"  [!] Failed: {e}")
