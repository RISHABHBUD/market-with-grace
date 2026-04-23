"""
YouTube Shorts uploader for StockDev.in
Uses YouTube Data API v3 with OAuth2.

First-time setup:
  1. Place client_secrets.json in stock-news-bot/
  2. Run: python youtube_upload.py --auth
     (opens browser, log in with your YouTube channel account)
  3. token.json is saved — never need to auth again

Normal upload (called by run_reel.py):
  upload_to_youtube(video_path, title, description)
"""

import os
import json
import pickle
import argparse
from datetime import datetime

SCOPES              = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "client_secrets.json")
TOKEN_FILE          = os.path.join(os.path.dirname(__file__), "token.pickle")

CHANNEL_NAME = "StockDev.in"
HASHTAGS     = "#Shorts #StockMarket #IndianStockMarket #Nifty #NSE #StockDevIn #Finance #Investing"


def get_credentials():
    """Load saved credentials or run OAuth flow."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
        print("  [✓] Credentials saved to token.pickle")

    return creds


def upload_to_youtube(video_path, title, description):
    """Upload a video as a YouTube Short."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds   = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    # YouTube Shorts: title should contain #Shorts
    yt_title = title[:90]  # YouTube title max 100 chars
    if "#Shorts" not in yt_title:
        yt_title = yt_title[:83] + " #Shorts"

    yt_description = f"{description}\n\n{HASHTAGS}"

    body = {
        "snippet": {
            "title":       yt_title,
            "description": yt_description,
            "tags":        ["Shorts", "StockMarket", "IndianStockMarket",
                            "Nifty", "NSE", "BSE", "Finance", "Investing",
                            "StockNews", "StockDevIn"],
            "categoryId":  "25",   # 25 = News & Politics (good for finance)
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
        }
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4",
                            resumable=True, chunksize=1024*1024)

    print(f"  Uploading to YouTube: {yt_title}")
    request = youtube.videos().insert(part="snippet,status",
                                      body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  Upload progress: {pct}%", end="\r")

    video_id  = response["id"]
    video_url = f"https://youtube.com/shorts/{video_id}"
    print(f"\n  [✓] Uploaded to YouTube: {video_url}")
    return video_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth", action="store_true",
                        help="Run OAuth flow to authorize YouTube access")
    args = parser.parse_args()

    if args.auth:
        print("Opening browser for YouTube authorization...")
        get_credentials()
        print("Authorization complete. token.pickle saved.")
    else:
        print("Usage: python youtube_upload.py --auth")
