#!/usr/bin/env python3
"""
Telegram News Bot — Free Version
- RSS feeds (free)
- Google Gemini API free tier (1500 req/day)
- GitHub Actions (free runner)
- JSON file in repo for deduplication
"""

import os
import json
import hashlib
import logging
import feedparser
import requests
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL_ID"]
GEMINI_API_KEY  = os.environ["GEMINI_API_KEY"]
POSTED_FILE     = Path("data/posted.json")
MAX_POST        = int(os.environ.get("MAX_POST", "6"))

RSS_FEEDS = [
    {"name": "Reuters World",    "url": "https://feeds.reuters.com/reuters/worldNews",    "cat": "🌍 THẾ GIỚI"},
    {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews", "cat": "💹 TÀI CHÍNH"},
    {"name": "BBC World",        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",     "cat": "🌍 THẾ GIỚI"},
    {"name": "CNBC",             "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "cat": "💹 TÀI CHÍNH"},
    {"name": "Al Jazeera",       "url": "https://www.aljazeera.com/xml/rss/all.xml",      "cat": "🏛️ CHÍNH TRỊ"},
    {"name": "AP Top News",      "url": "https://rsshub.app/apnews/topics/ap-top-news",   "cat": "🌍 THẾ GIỚI"},
    {"name": "Financial Times",  "url": "https://www.ft.com/rss/home",                    "cat": "💹 TÀI CHÍNH"},
    {"name": "Bloomberg Mkts",   "url": "https://feeds.bloomberg.com/markets/news.rss",   "cat": "💹 TÀI CHÍNH"},
]

KEYWORDS = [
    "fed", "federal reserve", "interest rate", "inflation", "gdp", "recession",
    "war", "sanction", "tariff", "trade", "opec", "oil", "dollar", "euro",
    "yuan", "stock", "nasdaq", "s&p", "bitcoin", "crypto", "imf", "world bank",
    "nato", "g7", "g20", "china", "russia", "ukraine", "middle east",
    "election", "policy", "central bank", "economy", "market", "geopolit",
]

SKIP_KEYWORDS = ["celebrity", "oscar", "grammy", "sport", "football", "nfl", "nba"]

# ── Deduplication ─────────────────────────────────────────────────────────────

def load_posted() -> set:
    if POSTED_FILE.exists():
        return set(json.loads(POSTED_FILE.read_text(encoding="utf-8")))
    return set()

def save_posted(hashes: set):
    POSTED_FILE.parent.mkdir(exist_ok=True)
    # Giữ tối đa 2000 hash gần nhất để file không phình
    recent = list(hashes)[-2000:]
    POSTED_FILE.write_text(json.dumps(recent), encoding="utf-8")

def url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]

# ── Collector ─────────────────────────────────────────────────────────────────

def fetch_articles(posted: set) -> list[dict]:
    articles = []
    for feed in RSS_FEEDS:
        try:
            logger.info(f"Fetching {feed['name']}...")
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries[:15]:
                url     = entry.get("link", "").strip()
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()

                if not url or not title:
                    continue
                if url_hash(url) in posted:
                    continue

                text = (title + " " + summary).lower()
                if any(k in text for k in SKIP_KEYWORDS):
                    continue
                if not any(k in text for k in KEYWORDS):
                    continue

                articles.append({
                    "url":     url,
                    "title":   title,
                    "summary": summary[:1200],
                    "source":  feed["name"],
                    "cat":     feed["cat"],
                    "hash":    url_hash(url),
                })
        except Exception as e:
            logger.warning(f"Feed error {feed['name']}: {e}")

    logger.info(f"Found {len(articles)} new relevant articles")
    return articles

# ── Gemini Summarizer ─────────────────────────────────────────────────────────

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key={key}"
)

PROMPT_TEMPLATE = """Bạn là biên tập viên kênh Telegram chuyên tài chính-kinh tế-địa chính trị.

Tóm tắt bài báo sau thành JSON (chỉ JSON, không markdown, không giải thích):
{{
  "headline": "tiêu đề tiếng Việt ngắn gọn ≤12 từ",
  "summary": "3-4 câu tiếng Việt: sự kiện chính + số liệu + tác động",
  "key": "1 câu quan trọng nhất độc giả cần nhớ",
  "tags": ["3-4 hashtag tiếng Anh không có dấu #"],
  "impact": "high|medium|low"
}}

Bài báo:
Tiêu đề: {title}
Nguồn: {source}
Nội dung: {content}
"""

def gemini_summarize(article: dict) -> dict | None:
    content = article["summary"]
    prompt  = PROMPT_TEMPLATE.format(
        title=article["title"],
        source=article["source"],
        content=content[:2000],
    )
    try:
        resp = requests.post(
            GEMINI_URL.format(key=GEMINI_API_KEY),
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Gemini error for '{article['title'][:50]}': {e}")
        return None

# ── Formatter ─────────────────────────────────────────────────────────────────

IMPACT_BADGE = {"high": "🔴", "medium": "🟡", "low": "🟢"}

def format_message(article: dict, s: dict) -> str:
    badge = IMPACT_BADGE.get(s.get("impact", "medium"), "🟡")
    tags  = " ".join(f"#{t}" for t in s.get("tags", [])[:4])
    now   = datetime.now()
    hour  = (datetime.utcnow().hour + 7) % 24   # UTC+7 Vietnam
    time_str = f"{hour:02d}:{now.minute:02d}"

    return (
        f"{article['cat']} {badge}\n\n"
        f"<b>{s.get('headline', article['title'])}</b>\n\n"
        f"{s.get('summary', '')}\n\n"
        f"💡 <i>{s.get('key', '')}</i>\n\n"
        f"🔗 <a href=\"{article['url']}\">Đọc thêm</a>"
        f" · 📡 {article['source']} · 🕐 {time_str} (VN)\n\n"
        f"{tags}"
    ).strip()

def format_digest(pairs: list[tuple]) -> str:
    date_str = datetime.utcnow().strftime("%d/%m/%Y")
    lines = [f"📋 <b>TIN TỨC NỔI BẬT — {date_str}</b>\n"]
    for i, (article, s) in enumerate(pairs[:8], 1):
        headline = s.get("headline", article["title"])
        key      = s.get("key", "")
        lines.append(
            f"{article['cat']} <b>{i}. {headline}</b>\n"
            f"   └ {key}\n"
            f"   <a href=\"{article['url']}\">🔗 {article['source']}</a>\n"
        )
    lines.append("#TàiChính #KinhTế #ChínhTrị #ThếGiới")
    return "\n".join(lines)

# ── Publisher ─────────────────────────────────────────────────────────────────

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def tg_post(text: str, preview: bool = False) -> bool:
    try:
        r = requests.post(
            f"{TG_API}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHANNEL,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": not preview,
            },
            timeout=20,
        )
        ok = r.json().get("ok", False)
        if not ok:
            logger.error(f"Telegram error: {r.json()}")
        return ok
    except Exception as e:
        logger.error(f"Telegram request error: {e}")
        return False

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    mode = os.environ.get("RUN_MODE", "flash")  # flash | digest
    logger.info(f"Starting bot — mode={mode}")

    posted  = load_posted()
    articles = fetch_articles(posted)

    if not articles:
        logger.info("No new articles to process.")
        return

    pairs = []
    for article in articles[:MAX_POST]:
        summary = gemini_summarize(article)
        if summary:
            pairs.append((article, summary))
            posted.add(article["hash"])
        else:
            # fallback: đăng không tóm tắt AI
            pairs.append((article, {
                "headline": article["title"][:80],
                "summary": article["summary"][:400],
                "key": "",
                "tags": [],
                "impact": "medium",
            }))
            posted.add(article["hash"])

    if mode == "digest":
        msg = format_digest(pairs)
        tg_post(msg, preview=False)
        logger.info(f"Digest posted — {len(pairs)} items")
    else:
        for article, s in pairs:
            msg = format_message(article, s)
            if tg_post(msg):
                logger.info(f"Posted: {article['title'][:60]}")
            import time; time.sleep(4)

    save_posted(posted)
    logger.info("Done.")

if __name__ == "__main__":
    main()
