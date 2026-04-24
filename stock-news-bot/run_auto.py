"""
Automated runner — called by GitHub Actions.
Fetches one fresh article, generates post, uploads and publishes to Instagram.
"""

import os
import sys
from datetime import datetime

from fetcher   import fetch_all_articles
from composer  import build_caption
from image_gen import create_post_image
from tracker   import load_posted, save_posted, is_posted, mark_posted
from poster    import upload_to_cloudinary, post_to_instagram, post_image_to_facebook
from config    import OUTPUT_FOLDER


def main():
    print(f"\n🌸 MarketWithGrace Auto-Post — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. Fetch articles
    print("\n[1/5] Fetching latest news...")
    articles = fetch_all_articles()
    if not articles:
        print("  [!] No articles found. Exiting.")
        sys.exit(1)

    # 2. Pick first article not already posted
    print("\n[2/5] Finding a fresh article...")
    posted = load_posted()
    selected = None
    for article in articles:
        if not is_posted(article, posted):
            selected = article
            break

    if not selected:
        print("  [!] All articles already posted today. Exiting.")
        sys.exit(0)

    print(f"  [✓] Selected: {selected['title'][:70]}")

    # 3. Generate image + caption
    print("\n[3/5] Generating post...")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir   = os.path.join(OUTPUT_FOLDER, timestamp)
    os.makedirs(out_dir, exist_ok=True)

    image_path   = os.path.join(out_dir, "post.jpg")
    caption_path = os.path.join(out_dir, "caption.txt")

    create_post_image(selected, image_path)
    caption = build_caption(selected)
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(caption)
    print(f"  [✓] Post saved to {out_dir}")

    # 4. Upload image + publish to Instagram + Facebook
    print("\n[4/5] Uploading and publishing...")
    image_url = upload_to_cloudinary(image_path)
    post_to_instagram(image_url, caption)
    try:
        post_image_to_facebook(image_url, caption)
    except Exception as e:
        print(f"  [!] Facebook post failed: {e}")

    # 5. Mark as posted
    print("\n[5/5] Updating tracker...")
    posted = mark_posted(selected, posted)
    save_posted(posted)
    print("  [✓] Tracker updated.")

    print(f"\n✅ Done! Post published successfully.\n")


if __name__ == "__main__":
    main()
