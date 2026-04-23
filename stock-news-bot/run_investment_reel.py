"""
StockDev.in — Investment Reel Runner
Picks today's stock from Nifty 500 rotation, generates reel,
posts to Instagram + uploads to YouTube Shorts.
"""

import os, sys, re
from datetime import datetime

from nifty500         import get_todays_stock
from investment_reel  import create_investment_reel
from poster           import upload_to_cloudinary, post_reel_to_instagram
from youtube_upload   import upload_to_youtube
from config           import OUTPUT_FOLDER


def main():
    print(f"\n💰 Investment Reel — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. Get today's stock
    display_name, ticker = get_todays_stock()
    print(f"\n[1/4] Today's stock: {display_name} ({ticker})")

    # 2. Generate reel
    print("\n[2/4] Generating investment reel...")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir   = os.path.join(OUTPUT_FOLDER, "investment_reels", timestamp)
    os.makedirs(out_dir, exist_ok=True)

    reel_path = os.path.join(out_dir, "reel.mp4")
    success   = create_investment_reel(display_name, ticker, reel_path)

    if not success:
        print("  [!] Reel generation failed. Exiting.")
        sys.exit(1)

    # 3. Post to Instagram
    print("\n[3/4] Posting to Instagram...")
    try:
        caption = (
            f"Agar aapne {display_name} mein invest kiya hota toh aaj "
            f"aapka paisa kitna hota? Dekho is reel mein!\n\n"
            f"Follow {chr(64)}stockdev.in for daily investment insights\n\n"
            f"#StockMarket #IndianStockMarket #Investing #WealthCreation "
            f"#StockDevIn #Nifty500 #LongTermInvesting #ShareBazaar "
            f"#{display_name.replace(' ','')} #StockReturns"
        )
        video_url = upload_to_cloudinary(reel_path)
        post_reel_to_instagram(video_url, caption)
    except Exception as e:
        print(f"  [!] Instagram post failed: {e}")

    # 4. Upload to YouTube Shorts
    print("\n[4/4] Uploading to YouTube Shorts...")
    try:
        yt_title = (
            f"{display_name}: Rs 1 Lakh → ? | "
            f"{datetime.now().strftime('%Y')} | StockDev.in #Shorts"
        )
        upload_to_youtube(reel_path, yt_title, caption)
    except FileNotFoundError:
        print("  [!] YouTube credentials not found — skipping")
    except Exception as e:
        print(f"  [!] YouTube upload failed: {e}")

    print(f"\n✅ Investment reel done! Saved in: {out_dir}\n")


if __name__ == "__main__":
    main()
