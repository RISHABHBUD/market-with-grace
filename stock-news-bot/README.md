# StockDev.in — Instagram Auto Poster

Fetches Indian stock market news from Livemint and auto-posts to Instagram 8x/day via GitHub Actions. Completely free.

---

## How it works

1. GitHub Actions triggers on a cron schedule (8 times/day, weekdays only)
2. Fetches latest stock news from Livemint
3. Skips articles already posted (tracked in `posted.json`)
4. Generates a 1080x1080 image + caption
5. Uploads image to Cloudinary, gets a public URL
6. Posts to Instagram via Meta Graph API
7. Commits the post files and updated tracker back to the repo

---

## Posting Schedule (IST, Mon–Fri only)

| Post | IST Time |
|------|----------|
| 1 | 08:00 AM |
| 2 | 09:30 AM |
| 3 | 11:00 AM |
| 4 | 12:30 PM |
| 5 | 02:00 PM |
| 6 | 03:30 PM |
| 7 | 05:00 PM |
| 8 | 07:00 PM |

---

## GitHub Secrets Required

Go to: `Settings → Secrets and variables → Actions`

| Secret Name | Where to get it |
|-------------|----------------|
| `CLOUDINARY_CLOUD_NAME` | Cloudinary Dashboard |
| `CLOUDINARY_API_KEY` | Cloudinary Dashboard |
| `CLOUDINARY_API_SECRET` | Cloudinary Dashboard |
| `INSTAGRAM_USER_ID` | Meta Graph API Explorer → query `me/accounts` → get Page ID → query `PAGE_ID?fields=instagram_business_account` |
| `INSTAGRAM_ACCESS_TOKEN` | See token refresh guide below |

---

## Instagram Token — Refresh Every 60 Days

The access token expires in ~60 days. When it expires you will see this error in GitHub Actions:
```
Session has expired
OAuthException code 190
```

**Set a reminder every 55 days to refresh the token.**

### Step 1 — Get a short-lived token
1. Go to https://developers.facebook.com/tools/explorer
2. Select your app (PrettySmartMoney) in Meta App dropdown
3. Click "Get Token" → "Get User Access Token"
4. Add these permissions:
   - `instagram_content_publish`
   - `instagram_manage_insights`
   - `instagram_manage_comments`
   - `pages_read_engagement`
   - `pages_show_list`
   - `pages_manage_metadata`
5. Click "Generate Access Token" → log in → copy the token

### Step 2 — Exchange for long-lived token (60 days)
Open this URL in your browser (replace the 3 values):

```
https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=YOUR_SHORT_TOKEN
```

- `YOUR_APP_ID` → Meta Developer → App Settings → Basic → App ID
- `YOUR_APP_SECRET` → same page → App Secret → click Show
- `YOUR_SHORT_TOKEN` → token from Step 1

You will get a response like:
```json
{"access_token": "EAAxxxxxxx...", "expires_in": 5183944}
```

`expires_in` is in seconds. 5183944 seconds ≈ 60 days.

### Step 3 — Update GitHub Secret
1. Go to your repo → Settings → Secrets → Actions
2. Click `INSTAGRAM_ACCESS_TOKEN` → Update
3. Paste the new `EAAxxxxxxx...` token → Save
4. Done — the next scheduled run will use the new token

---

## Running Manually

```bash
# Install dependencies
pip install -r requirements.txt

# Run once manually (picks one article, generates post, uploads, publishes)
python run_auto.py

# Run locally without posting to Instagram (just generates image + caption)
python main.py
```

---

## Monitoring

- **GitHub Actions logs**: https://github.com/RISHABHBUD/market-with-grace/actions
- **Posted articles tracker**: `stock-news-bot/posted.json`
- **Generated posts archive**: `stock-news-bot/posts/`

Each run appears as green (success) or red (failed) in Actions. Click any run to see full logs.

---

## Customisation

| File | What to change |
|------|---------------|
| `config.py` | Branding, hashtags, posting count |
| `image_gen.py` | Image design, colors, layout |
| `composer.py` | Caption format and tone |
| `fetcher.py` | News source URL |
| `.github/workflows/post_to_instagram.yml` | Posting schedule (cron times) |

---

## Free Tier Limits

| Service | Free Limit | Our Usage |
|---------|-----------|-----------|
| GitHub Actions | 2,000 min/month | ~240 min/month |
| Cloudinary | 25 credits/month | ~1 credit/month |
| Meta Graph API | 25 posts/day | 8 posts/day |
