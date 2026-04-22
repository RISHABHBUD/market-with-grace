"""
StockDev.in — Reel Auto Poster
Fetches one fresh article, generates a Stock Spotlight reel, posts to Instagram.
Run: python run_reel.py
"""

import os
import sys
from datetime import datetime

from fetcher   import fetch_all_articles
from composer  import build_caption
from reel_gen  import create_reel
from tracker   import load_posted, save_posted, is_posted, mark_posted
from poster    import upload_to_cloudinary, post_reel_to_instagram
from config    import OUTPUT_FOLDER


def main():
    print(f"\n🎬 StockDev.in Reel Generator — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. Fetch articles
    print("\n[1/5] Fetching latest news...")
    articles = fetch_all_articles()
    if not articles:
        print("  [!] No articles found.")
        sys.exit(1)

    # 2. Pick fresh article (use separate tracker key for reels)
    print("\n[2/5] Finding a fresh article for reel...")
    reel_tracker_key = "reel_"
    posted = load_posted()
    selected = None
    for article in articles:
        reel_article = dict(article)
        reel_article["title"] = reel_tracker_key + article["title"]
        if not is_posted(reel_article, posted):
            selected = article
            break

    if not selected:
        print("  [!] All articles already used for reels today.")
        sys.exit(0)

    print(f"  [✓] Selected: {selected['title'][:65]}")

    # 3. Generate reel
    print("\n[3/5] Generating reel video...")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir   = os.path.join(OUTPUT_FOLDER, "reels", timestamp)
    os.makedirs(out_dir, exist_ok=True)

    reel_path   = os.path.join(out_dir, "reel.mp4")
    caption_path = os.path.join(out_dir, "caption.txt")

    create_reel(selected, reel_path)
    caption = build_caption(selected)
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(caption)

    # 4. Upload + publish
    print("\n[4/5] Uploading and publishing reel...")
    video_url = upload_video_to_cloudinary(reel_path)
    post_reel_to_instagram(video_url, caption)

    # 5. Track
    print("\n[5/5] Updating tracker...")
    reel_article = dict(selected)
    reel_article["title"] = reel_tracker_key + selected["title"]
    posted = mark_posted(reel_article, posted)
    save_posted(posted)

    print(f"\n✅ Reel published! Saved in: {out_dir}\n")


def upload_video_to_cloudinary(video_path):
    """Upload video to Cloudinary and return public URL."""
    import time, hashlib, requests, os

    cloud_name = os.environ["CLOUDINARY_CLOUD_NAME"]
    api_key    = os.environ["CLOUDINARY_API_KEY"]
    api_secret = os.environ["CLOUDINARY_API_SECRET"]

    timestamp  = str(int(time.time()))
    sig_str    = f"resource_type=video&timestamp={timestamp}{api_secret}"
    signature  = hashlib.sha1(sig_str.encode()).hexdigest()

    url = f"https://api.cloudinary.com/v1_1/{cloud_name}/video/upload"

    print("  Uploading video to Cloudinary (this may take a moment)...")
    with open(video_path, "rb") as f:
        resp = requests.post(url, files={"file": ("reel.mp4", f, "video/mp4")}, data={
            "api_key":       api_key,
            "timestamp":     timestamp,
            "signature":     signature,
            "resource_type": "video",
        })

    print(f"  Cloudinary status: {resp.status_code}")
    if not resp.ok:
        print(f"  Cloudinary error: {resp.text}")
    resp.raise_for_status()

    video_url = resp.json()["secure_url"]
    print(f"  [✓] Video uploaded: {video_url}")
    return video_url


if __name__ == "__main__":
    main()
