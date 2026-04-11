#!/usr/bin/env python3
import os
import json
import hashlib
import logging
import feedparser
import requests
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL_ID"]
POSTED_FILE      = Path("data/posted.json")
MAX_POST         = int(os.environ.get("MAX_POST", "6"))

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

def load_posted() -> set:
    if POSTED_FILE.exists():
        return set(json.loads(POSTED_FILE.read_text(encoding="utf-8")))
    return set()

def save_posted(hashes: set):
    POSTED_FILE.parent.mkdir(exist_ok=True)
    recent = list(hashes)[-2000:]
    POSTED_FILE.write_text(json.dumps(recent), encoding="utf-8")

def url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]

def fetch_articles(posted: set) -> list:
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
                    "summary": summary[:500],
                    "source":  feed["name"],
                    "cat":     feed["cat"],
                    "hash":    url_hash(url),
                })
        except Exception as e:
            logger.warning(f"Feed error {feed['name']}: {e}")
    logger.info(f"Found {len(articles)} new relevant articles")
    return articles

def format_message(article: dict) -> str:
    hour = (datetime.utcnow().hour + 7) % 24
    minute = datetime.utcnow().minute
    summary = article["summary"][:300] if article["summary"] else ""
    return (
        f"{article['cat']}\n\n"
        f"<b>{article['title']}</b>\n\n"
        f"{summary}\n\n"
        f"🔗 <a href=\"{article['url']}\">Đọc thêm</a>"
        f" · 📡 {article['source']} · 🕐 {hour:02d}:{minute:02d} (VN)"
    ).strip()

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def tg_post(text: str) -> bool:
    try:
        r = requests.post(
            f"{TG_API}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHANNEL,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
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

def main():
    logger.info("Starting bot")
    posted   = load_posted()
    articles = fetch_articles(posted)
    if not articles:
        logger.info("No new articles.")
        return
    import time
    for article in articles[:MAX_POST]:
        msg = format_message(article)
        if tg_post(msg):
            logger.info(f"Posted: {article['title'][:60]}")
            posted.add(article["hash"])
        time.sleep(3)
    save_posted(posted)
    logger.info("Done.")

if __name__ == "__main__":
    main()
