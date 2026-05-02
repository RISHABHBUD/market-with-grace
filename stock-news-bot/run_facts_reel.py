"""
StockDev.in — Facts Reel Runner
Picks today's fact from facts.json, generates cinematic reel,
posts to Instagram + YouTube Shorts.

Run normally:  python run_facts_reel.py
Run locally:   python run_facts_reel.py --test
"""

import os, sys, argparse
from datetime import datetime

from facts_reel    import create_facts_reel, get_todays_fact
from poster        import post_reel_to_instagram, post_video_to_facebook
from run_reel      import upload_video_to_cloudinary
from youtube_upload import upload_to_youtube
from config        import OUTPUT_FOLDER


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true",
                        help="Generate reel locally without posting")
    parser.add_argument("--id", type=str, default=None,
                        help="Specific fact ID to use (e.g. fact_042)")
    args = parser.parse_args()

    print(f"\n💡 StockDev.in Facts Reel — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if args.test:
        print("  [TEST MODE] — will NOT post to any platform")
    print("=" * 60)

    # Pick fact
    if args.id:
        import json
        facts_path = os.path.join(os.path.dirname(__file__), "facts.json")
        with open(facts_path, encoding="utf-8") as f:
            all_facts = json.load(f)
        fact = next((x for x in all_facts if x["id"]==args.id), None)
        if not fact:
            print(f"  [!] Fact ID '{args.id}' not found.")
            sys.exit(1)
        print(f"\n[1/4] Using specified fact: {args.id}")
    else:
        fact = get_todays_fact()
        print(f"\n[1/4] Today's fact: {fact['id']} ({fact['category']})")

    # Generate reel
    print("\n[2/4] Generating facts reel...")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir   = os.path.join(OUTPUT_FOLDER, "facts_reels", timestamp)
    os.makedirs(out_dir, exist_ok=True)

    reel_path    = os.path.join(out_dir, "reel.mp4")
    caption_path = os.path.join(out_dir, "caption.txt")

    success = create_facts_reel(fact, reel_path)
    if not success:
        print("  [!] Reel generation failed.")
        sys.exit(1)

    # Save caption
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(fact["caption"])
    print(f"  [✓] Caption saved")

    if args.test:
        print(f"\n✅ Test reel saved at: {reel_path}")
        print(f"   Caption: {caption_path}\n")
        return

    # Post to Instagram + Facebook
    print("\n[3/4] Posting to Instagram...")
    try:
        video_url = upload_video_to_cloudinary(reel_path)
        post_reel_to_instagram(video_url, fact["caption"])
        try:
            post_video_to_facebook(reel_path, fact["caption"],
                                   title=f"{fact['hook'][:60]} | StockDev.in")
        except Exception as e:
            print(f"  [!] Facebook failed: {e}")
    except Exception as e:
        print(f"  [!] Instagram failed: {e}")

    # Upload to YouTube Shorts
    print("\n[4/4] Uploading to YouTube Shorts...")
    try:
        yt_title = f"{fact['hook'][:80]} | StockDev.in #Shorts"
        upload_to_youtube(reel_path, yt_title, fact["caption"])
    except FileNotFoundError:
        print("  [!] YouTube credentials not found — skipping")
    except Exception as e:
        print(f"  [!] YouTube failed: {e}")

    print(f"\n✅ Facts reel done! Saved in: {out_dir}\n")


if __name__ == "__main__":
    main()
