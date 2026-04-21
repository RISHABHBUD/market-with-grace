"""
MarketWithGrace - Instagram Post Generator
Run: python main.py
Generates one post per article automatically inside posts/
"""

import os
from datetime import datetime
from fetcher import fetch_all_articles
from composer import build_caption
from image_gen import create_post_image
from config import OUTPUT_FOLDER


def main():
    print("\n🌸 MarketWithGrace - Post Generator")
    print("=" * 60)

    # 1. Fetch all articles
    print("\n[1/2] Fetching latest stock news...")
    articles = fetch_all_articles()

    if not articles:
        print("  [!] No articles found. Check your internet connection.")
        return

    # 2. Generate a post for every article
    print(f"\n[2/2] Creating {len(articles)} posts...\n")

    today = datetime.now().strftime("%Y-%m-%d")
    base_dir = os.path.join(OUTPUT_FOLDER, today)

    for i, article in enumerate(articles, 1):
        # Each article gets its own numbered subfolder
        post_dir = os.path.join(base_dir, f"post_{i:02d}")
        os.makedirs(post_dir, exist_ok=True)

        print(f"  [{i}/{len(articles)}] {article['title'][:65]}")

        try:
            create_post_image(article, os.path.join(post_dir, "post.jpg"))
            caption = build_caption(article)
            with open(os.path.join(post_dir, "caption.txt"), "w", encoding="utf-8") as f:
                f.write(caption)
        except Exception as e:
            print(f"    [!] Failed: {e}")
            continue

    print(f"\n✅ All posts saved in: {base_dir}")
    print(f"   Browse the folders and pick what you want to upload!\n")


if __name__ == "__main__":
    main()
