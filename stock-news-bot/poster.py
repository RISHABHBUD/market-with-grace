"""
Instagram poster via Meta Graph API.
Uploads image to Cloudinary, then publishes to Instagram.
"""

import os
import time
import hashlib
import requests


def upload_to_cloudinary(image_path):
    """Upload image to Cloudinary using signed upload and return public URL."""
    cloud_name = os.environ["CLOUDINARY_CLOUD_NAME"]
    api_key    = os.environ["CLOUDINARY_API_KEY"]
    api_secret = os.environ["CLOUDINARY_API_SECRET"]

    timestamp = str(int(time.time()))

    # Signature: sha1 of "timestamp=<ts><api_secret>"
    sig_str   = f"timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(sig_str.encode("utf-8")).hexdigest()

    url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"

    with open(image_path, "rb") as f:
        resp = requests.post(url, files={"file": ("post.jpg", f, "image/jpeg")}, data={
            "api_key":   api_key,
            "timestamp": timestamp,
            "signature": signature,
        })

    # Always print response for debugging
    print(f"  Cloudinary status: {resp.status_code}")
    print(f"  Cloudinary response: {resp.text[:500]}")

    resp.raise_for_status()

    image_url = resp.json()["secure_url"]
    print(f"  [✓] Uploaded to Cloudinary: {image_url}")
    return image_url


def post_to_instagram(image_url, caption):
    """Publish a single image post to Instagram via Graph API."""
    ig_user_id   = os.environ["INSTAGRAM_USER_ID"]
    access_token = os.environ["INSTAGRAM_ACCESS_TOKEN"]

    base = f"https://graph.facebook.com/v19.0/{ig_user_id}"

    # Step 1: Create media container
    resp = requests.post(f"{base}/media", data={
        "image_url":    image_url,
        "caption":      caption,
        "access_token": access_token,
    })
    print(f"  Instagram container status: {resp.status_code}", flush=True)
    print(f"  Instagram container response: {resp.text}", flush=True)
    if not resp.ok:
        raise Exception(f"Instagram media creation failed: {resp.text}")
    container_id = resp.json()["id"]
    print(f"  [✓] Media container created: {container_id}")

    # Wait for Instagram to process the image
    time.sleep(8)

    # Step 2: Publish the container
    resp = requests.post(f"{base}/media_publish", data={
        "creation_id":  container_id,
        "access_token": access_token,
    })
    print(f"  Instagram publish status: {resp.status_code}")
    print(f"  Instagram publish response: {resp.text[:300]}")
    resp.raise_for_status()
    post_id = resp.json()["id"]
    print(f"  [✓] Published to Instagram! Post ID: {post_id}")
    return post_id


def post_reel_to_instagram(video_url, caption):
    """Publish a Reel to Instagram via Graph API."""
    ig_user_id   = os.environ["INSTAGRAM_USER_ID"]
    access_token = os.environ["INSTAGRAM_ACCESS_TOKEN"]

    base = f"https://graph.facebook.com/v19.0/{ig_user_id}"

    # Step 1: Create reel container
    resp = requests.post(f"{base}/media", data={
        "media_type":  "REELS",
        "video_url":   video_url,
        "caption":     caption,
        "share_to_feed": "true",
        "access_token": access_token,
    })
    print(f"  Reel container status: {resp.status_code}", flush=True)
    print(f"  Reel container response: {resp.text}", flush=True)
    if not resp.ok:
        raise Exception(f"Reel container creation failed: {resp.text}")
    container_id = resp.json()["id"]
    print(f"  [✓] Reel container created: {container_id}")

    # Step 2: Poll until video is ready (can take 30-120s for reels)
    print("  Waiting for video to process...")
    import time as _time
    for attempt in range(24):  # max 2 minutes
        _time.sleep(10)
        status_resp = requests.get(
            f"https://graph.facebook.com/v19.0/{container_id}",
            params={"fields": "status_code", "access_token": access_token}
        )
        status_data = status_resp.json()
        status_code = status_data.get("status_code", "")
        print(f"  Status check {attempt+1}: {status_code}")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise Exception(f"Instagram video processing failed: {status_data}")
    else:
        print("  [!] Timed out waiting — attempting publish anyway")

    # Step 3: Publish
    resp = requests.post(f"{base}/media_publish", data={
        "creation_id":  container_id,
        "access_token": access_token,
    })
    print(f"  Reel publish status: {resp.status_code}", flush=True)
    print(f"  Reel publish response: {resp.text}", flush=True)
    if not resp.ok:
        raise Exception(f"Reel publish failed: {resp.text}")
    post_id = resp.json()["id"]
    print(f"  [✓] Reel published! Post ID: {post_id}")
    return post_id


# ── Facebook Page posting ──────────────────────────────────────

FB_PAGE_ID = "61564699910301"


def get_page_access_token():
    """Exchange user token for Page access token."""
    access_token = os.environ["INSTAGRAM_ACCESS_TOKEN"]
    resp = requests.get(
        f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}",
        params={"fields": "access_token", "access_token": access_token}
    )
    if resp.ok and "access_token" in resp.json():
        return resp.json()["access_token"]
    # Fall back to user token if page token not available
    return access_token


def post_image_to_facebook(image_url, caption):
    """Post an image to Facebook Page."""
    page_token = get_page_access_token()
    resp = requests.post(
        f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
        data={
            "url":          image_url,
            "caption":      caption,
            "access_token": page_token,
        }
    )
    print(f"  Facebook image status: {resp.status_code}", flush=True)
    if not resp.ok:
        print(f"  Facebook image error: {resp.text}")
        return None
    post_id = resp.json().get("post_id") or resp.json().get("id")
    print(f"  [✓] Posted to Facebook! Post ID: {post_id}")
    return post_id


def post_video_to_facebook(video_path, caption, title=""):
    """Upload and post a video to Facebook Page."""
    page_token = get_page_access_token()

    print("  Uploading video to Facebook...")
    with open(video_path, "rb") as f:
        resp = requests.post(
            f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos",
            files={"source": ("video.mp4", f, "video/mp4")},
            data={
                "description":  caption,
                "title":        title or caption[:80],
                "access_token": page_token,
            }
        )
    print(f"  Facebook video status: {resp.status_code}", flush=True)
    if not resp.ok:
        print(f"  Facebook video error: {resp.text}")
        return None
    post_id = resp.json().get("id")
    print(f"  [✓] Posted to Facebook! Video ID: {post_id}")
    return post_id
