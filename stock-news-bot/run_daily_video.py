"""
StockDev.in — Daily Market Briefing Video
Run: python run_daily_video.py
Generates ~8-10 min Hindi market briefing and uploads to YouTube.
"""

import os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from daily_video.data_fetch  import fetch_all_data
from daily_video.script_gen  import get_hindi_script
from daily_video.audio_gen   import generate_audio
from daily_video.video_gen   import build_video
from youtube_upload          import upload_to_youtube
from config                  import OUTPUT_FOLDER


def main():
    print(f"\n📺 StockDev.in Daily Video — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    today     = datetime.now().strftime("%Y-%m-%d")
    out_dir   = os.path.join(OUTPUT_FOLDER, "daily_videos", today)
    os.makedirs(out_dir, exist_ok=True)

    # 1. Fetch all market data
    print("\n[1/5] Fetching market data...")
    data = fetch_all_data()

    # 2. Generate Hindi scripts
    print("\n[2/5] Generating Hindi scripts...")
    scripts = get_hindi_script(data)

    # 3. Generate audio
    print("\n[3/5] Generating Hindi narration...")
    audio_files = generate_audio(scripts, out_dir)

    # 4. Build video
    print("\n[4/5] Building video...")
    video_path = os.path.join(out_dir, "daily_briefing.mp4")
    build_video(data, audio_files, video_path)

    # 5. Upload to YouTube
    print("\n[5/5] Uploading to YouTube...")
    today_fmt = datetime.now().strftime("%d %B %Y")
    title     = f"Aaj Ka Market Update | {today_fmt} | Nifty Sensex Analysis | StockDev.in"
    desc      = (
        f"Aaj ka poora market update — Nifty 50, Sensex, Top Gainers, Top Losers, "
        f"Sector Performance aur aaj ki sabse important khabrein.\n\n"
        f"StockDev.in — Aapka Daily Market Saathi\n\n"
        f"#StockMarket #Nifty #Sensex #MarketUpdate #IndianStockMarket "
        f"#StockDevIn #Finance #Investing #ShareBazaar"
    )
    try:
        upload_to_youtube(video_path, title, desc)
    except FileNotFoundError:
        print("  [!] client_secrets.json not found — skipping YouTube upload")
    except Exception as e:
        print(f"  [!] YouTube upload failed: {e}")

    print(f"\n✅ Done! Video saved in: {out_dir}\n")


if __name__ == "__main__":
    main()
