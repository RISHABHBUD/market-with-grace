import re
from config import HASHTAGS, PAGE_HANDLE, TAGLINE


def build_caption(article):
    title   = article["title"]
    summary = re.sub(r"http\S+", "", article.get("summary", "")).strip()

    # Livemint summaries are clean 1-2 sentences — use as the core,
    # then pad to ~100 words with a follow-up investing note
    if summary and len(summary.split()) >= 10:
        body = summary
        # Pad to ~100 words if short
        if len(body.split()) < 60:
            body += (
                " This is an important development for investors tracking "
                "the Indian stock market. Keep a close eye on how this story "
                "unfolds over the next few trading sessions, and think about "
                "what it could mean for your portfolio and investment strategy."
            )
    else:
        body = (
            f"{title}. This is a key development for investors tracking "
            f"the Indian stock market. Watch how this plays out over the "
            f"coming sessions and consider what it means for your portfolio strategy."
        )

    # Trim to ~100 words
    words = body.split()
    if len(words) > 105:
        body = " ".join(words[:100]) + "..."

    lines = [
        body,
        "",
        "─" * 30,
        f"Follow {PAGE_HANDLE} for daily market updates",
        TAGLINE,
        "",
        " ".join(HASHTAGS[:12]),
    ]

    return "\n".join(lines)
