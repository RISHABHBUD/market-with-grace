# 📈 Indian Stock Market - Instagram Post Generator

Fetches top Indian stock market news and generates a ready-to-post Instagram image + caption.

## Setup

```bash
cd stock-news-bot
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Output

Each run creates a timestamped folder inside `posts/`:
```
posts/
└── 2024-01-15_09-30/
    ├── post.jpg      ← upload this to Instagram
    └── caption.txt   ← copy-paste this as your caption
```

## Customize

- `config.py` → change hashtags, number of headlines, post title
- `image_gen.py` → tweak colors, fonts, layout
- `composer.py` → change caption format/tone
