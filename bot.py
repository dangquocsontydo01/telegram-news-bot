#!/usr/bin/env python3
import os, json, hashlib, logging, feedparser, requests, time, re
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL = os.environ["TELEGRAM_CHANNEL_ID"]
POSTED_FILE      = Path("data/posted.json")

# Số tin tối đa mỗi nhóm mỗi lần chạy
MAX_INTL    = 3  # Quốc tế
MAX_VN      = 3  # Việt Nam
MAX_TWITTER = 2  # Twitter/KOLs

RSS_FEEDS = {
    "intl": [
        {"name": "Reuters World",    "url": "https://feeds.reuters.com/reuters/worldNews",           "cat": "🌍 THẾ GIỚI"},
        {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews",        "cat": "💹 TÀI CHÍNH"},
        {"name": "BBC World",        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",            "cat": "🌍 THẾ GIỚI"},
        {"name": "CNBC",             "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "cat": "💹 TÀI CHÍNH"},
        {"name": "Al Jazeera",       "url": "https://www.aljazeera.com/xml/rss/all.xml",             "cat": "🏛️ CHÍNH TRỊ"},
        {"name": "AP Top News",      "url": "https://rsshub.app/apnews/topics/ap-top-news",          "cat": "🌍 THẾ GIỚI"},
        {"name": "Financial Times",  "url": "https://www.ft.com/rss/home",                           "cat": "💹 TÀI CHÍNH"},
        {"name": "Bloomberg Mkts",   "url": "https://feeds.bloomberg.com/markets/news.rss",          "cat": "💹 TÀI CHÍNH"},
    ],
    "vn": [
        {"name": "VnExpress",  "url": "https://vnexpress.net/rss/kinh-doanh.rss",        "cat": "🇻🇳 VIỆT NAM"},
        {"name": "Tuoi Tre",   "url": "https://tuoitre.vn/rss/kinh-te.rss",              "cat": "🇻🇳 VIỆT NAM"},
        {"name": "Dan Tri",    "url": "https://dantri.com.vn/kinh-doanh.rss",            "cat": "🇻🇳 VIỆT NAM"},
        {"name": "Zing News",  "url": "https://zingnews.vn/kinh-te.rss",                 "cat": "🇻🇳 VIỆT NAM"},
        {"name": "CafeF",      "url": "https://cafef.vn/rss/thi-truong-chung-khoan.rss", "cat": "📈 CHỨNG KHOÁN"},
        {"name": "Vietstock",  "url": "https://vietstock.vn/rss/tai-chinh.rss",          "cat": "📈 CHỨNG KHOÁN"},
    ],
    "twitter": [
        {"name": "Donald Trump",    "url": "https://nitter.privacyredirect.com/realDonaldTrump/rss",  "cat": "🏛️ TRUMP"},
        {"name": "Elon Musk",       "url": "https://nitter.privacyredirect.com/elonmusk/rss",         "cat": "🐦 ELON MUSK"},
        {"name": "Jim Cramer",      "url": "https://nitter.privacyredirect.com/jimcramer/rss",        "cat": "🐦 TWITTER"},
        {"name": "Cathie Wood",     "url": "https://nitter.privacyredirect.com/CathieDWood/rss",     "cat": "🐦 TWITTER"},
        {"name": "Raoul Pal",       "url": "https://nitter.privacyredirect.com/RaoulGMI/rss",        "cat": "🐦 TWITTER"},
        {"name": "Michael Saylor",  "url": "https://nitter.privacyredirect.com/saylor/rss",          "cat": "₿ CRYPTO"},
        {"name": "CZ Binance",      "url": "https://nitter.privacyredirect.com/cz_binance/rss",      "cat": "₿ CRYPTO"},
        {"name": "Vitalik Buterin", "url": "https://nitter.privacyredirect.com/VitalikButerin/rss",  "cat": "₿ CRYPTO"},
        {"name": "PlanB",           "url": "https://nitter.privacyredirect.com/100trillionUSD/rss",  "cat": "₿ CRYPTO"},
        {"name": "Pompliano",       "url": "https://nitter.privacyredirect.com/APompliano/rss",      "cat": "₿ CRYPTO"},
        {"name": "Altcoin Daily",   "url": "https://nitter.privacyredirect.com/AltcoinDailyio/rss", "cat": "₿ CRYPTO"},
        {"name": "Willy Woo",       "url": "https://nitter.privacyredirect.com/woonomic/rss",        "cat": "₿ CRYPTO"},
    ],
}

KEYWORDS_EN = [
    "fed", "federal reserve", "interest rate", "inflation", "gdp", "recession",
    "war", "sanction", "tariff", "trade", "opec", "oil", "dollar", "euro",
    "yuan", "stock", "nasdaq", "s&p", "imf", "world bank", "nato", "g7", "g20",
    "china", "russia", "ukraine", "middle east", "election", "policy",
    "central bank", "economy", "market", "geopolit",
    "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
]

SKIP_KEYWORDS = ["celebrity", "oscar", "grammy", "football", "nfl", "nba"]

def load_posted() -> set:
    if POSTED_FILE.exists():
        return set(json.loads(POSTED_FILE.read_text(encoding="utf-8")))
    return set()

def save_posted(hashes: set):
    POSTED_FILE.parent.mkdir(exist_ok=True)
    recent = list(hashes)[-2000:]
    POSTED_FILE.write_text(json.dumps(recent), encoding="utf-8")

def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()

def url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]

def fetch_group(feeds: list, posted: set, use_filter: bool, limit: int) -> list:
    articles = []
    for feed in feeds:
        if len(articles) >= limit:
            break
        try:
            logger.info(f"Fetching {feed['name']}...")
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries[:10]:
                url     = entry.get("link", "").strip()
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                if not url or not title:
                    continue
                if url_hash(url) in posted:
                    continue
                if use_filter:
                    text = (title + " " + summary).lower()
                    if any(k in text for k in SKIP_KEYWORDS):
                        continue
                    if not any(k in text for k in KEYWORDS_EN):
                        continue
                articles.append({
                    "url":     url,
                    "title":   title,
                    "summary": summary[:400],
                    "source":  feed["name"],
                    "cat":     feed["cat"],
                    "hash":    url_hash(url),
                })
                if len(articles) >= limit:
                    break
        except Exception as e:
            logger.warning(f"Feed error {feed['name']}: {e}")
    return articles

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def format_message(article: dict) -> str:
    hour   = (datetime.utcnow().hour + 7) % 24
    minute = datetime.utcnow().minute
    summary = clean_html(article["summary"])[:300] if article["summary"] else ""
    return (
        f"{article['cat']}\n\n"
        f"<b>{article['title']}</b>\n\n"
        f"{summary}\n\n"
        f"🔗 <a href=\"{article['url']}\">Đọc thêm</a>"
        f" · 📡 {article['source']} · 🕐 {hour:02d}:{minute:02d} (VN)"
    ).strip()

def tg_post(text: str) -> bool:
    try:
        r = requests.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": TELEGRAM_CHANNEL, "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": False},
            timeout=20,
        )
        ok = r.json().get("ok", False)
        if not ok:
            logger.error(f"Telegram error: {r.json()}")
        return ok
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def main():
    logger.info("Starting bot")
    posted = load_posted()

    intl_articles    = fetch_group(RSS_FEEDS["intl"],    posted, use_filter=True,  limit=MAX_INTL)
    vn_articles      = fetch_group(RSS_FEEDS["vn"],      posted, use_filter=False, limit=MAX_VN)
    twitter_articles = fetch_group(RSS_FEEDS["twitter"], posted, use_filter=False, limit=MAX_TWITTER)

    logger.info(f"Intl: {len(intl_articles)} | VN: {len(vn_articles)} | Twitter: {len(twitter_articles)}")

    all_articles = intl_articles + vn_articles + twitter_articles

    if not all_articles:
        logger.info("No new articles.")
        return

    for article in all_articles:
        msg = format_message(article)
        if tg_post(msg):
            logger.info(f"Posted: [{article['source']}] {article['title'][:50]}")
            posted.add(article["hash"])
        time.sleep(3)

    save_posted(posted)
    logger.info("Done.")

if __name__ == "__main__":
    main()
