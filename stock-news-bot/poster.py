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
    print(f"  Instagram container status: {resp.status_code}")
    print(f"  Instagram container response: {resp.text[:300]}")
    resp.raise_for_status()
    container_id = resp.json()["id"]
    print(f"  [✓] Media container created: {container_id}")

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
